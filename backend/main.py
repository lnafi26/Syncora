from pathlib import Path
import asyncio
import hashlib
import json
import math
import re
import time

import httpx

from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel


# =====================================================
# BUILD / MODELS
# =====================================================

BUILD_ID = "nova-hybrid-0.7.2"

QWEN_MODEL_ID = "nova-qwen"
EMBEDDING_MODEL_ID = "nova-embed"


# =====================================================
# LAST.FM CONFIGURATION
# =====================================================

BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR / ".env"

config = dotenv_values(ENV_PATH)

LASTFM_API_KEY = config.get("LASTFM_API_KEY")
LASTFM_SHARED_SECRET = config.get("LASTFM_SHARED_SECRET")

LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"


print("==========================================")
print("Syncora backend build:", BUILD_ID)
print("Nova Qwen model:", QWEN_MODEL_ID)
print("Nova embedding model:", EMBEDDING_MODEL_ID)
print("Last.fm API key loaded:", bool(LASTFM_API_KEY))
print("==========================================")


if not LASTFM_API_KEY:
    raise RuntimeError(
        f"LASTFM_API_KEY could not be read from {ENV_PATH}"
    )


# =====================================================
# FASTAPI
# =====================================================

app = FastAPI(
    title="Syncora Backend",
    version="0.7.2"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================
# LM STUDIO
# =====================================================

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",
    timeout=90.0,
    max_retries=0
)


# =====================================================
# REQUEST MODEL
# =====================================================

class NovaRequest(BaseModel):
    project_name: str
    video_type: str
    target_duration_seconds: int
    mood: str
    pace: str
    vocal_style: str
    structure_preference: str
    creative_intent: str = ""


# =====================================================
# PROFILE CACHE
# =====================================================

PROFILE_CACHE_TTL_SECONDS = 15 * 60

nova_profile_cache = {}


def get_payload_cache_key(
    payload: NovaRequest
):

    serialized = json.dumps(
        payload.model_dump(),
        sort_keys=True,
        ensure_ascii=False
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def cache_nova_profile(
    payload: NovaRequest,
    profile
):

    key = get_payload_cache_key(
        payload
    )

    nova_profile_cache[key] = {
        "profile":
            profile,

        "expires_at":
            (
                time.time()
                +
                PROFILE_CACHE_TTL_SECONDS
            )
    }


def get_cached_nova_profile(
    payload: NovaRequest
):

    key = get_payload_cache_key(
        payload
    )

    cached = nova_profile_cache.get(
        key
    )


    if not cached:
        return None


    if time.time() >= cached[
        "expires_at"
    ]:

        nova_profile_cache.pop(
            key,
            None
        )

        return None


    return cached[
        "profile"
    ]


# =====================================================
# JSON PARSER
# =====================================================

def parse_nova_json(
    raw: str
):

    if raw is None or not raw.strip():

        raise HTTPException(
            status_code=500,
            detail=(
                f"{BUILD_ID}: Nova received "
                "an empty response from Qwen."
            )
        )


    cleaned = raw.strip()


    if cleaned.startswith(
        "```json"
    ):

        cleaned = cleaned[7:]


    elif cleaned.startswith(
        "```"
    ):

        cleaned = cleaned[3:]


    if cleaned.endswith(
        "```"
    ):

        cleaned = cleaned[:-3]


    cleaned = cleaned.strip()


    first_brace = cleaned.find(
        "{"
    )

    last_brace = cleaned.rfind(
        "}"
    )


    if (
        first_brace != -1
        and
        last_brace != -1
    ):

        cleaned = cleaned[
            first_brace:
            last_brace + 1
        ]


    try:

        return json.loads(
            cleaned
        )


    except json.JSONDecodeError as error:

        raise HTTPException(
            status_code=500,
            detail={
                "error":
                    (
                        f"{BUILD_ID}: "
                        "Nova returned invalid JSON."
                    ),

                "json_error":
                    str(error),

                "raw_response":
                    raw
            }
        )


# =====================================================
# QWEN MUSIC PROFILE
# =====================================================

def create_nova_profile(
    payload: NovaRequest
):

    prompt = f"""
You are Nova, the music-discovery intelligence inside
Syncora, a tool for video editors.

Analyze the editor's brief and produce two DIFFERENT
kinds of music information.

1. RETRIEVAL TAGS

Produce exactly 6 established music tags that are likely
to work as Last.fm search tags.

2. SEMANTIC TRAITS

Produce exactly 4 short descriptive qualities that
describe the desired sound. These are used for semantic
matching and are NOT used directly as Last.fm searches.


RETRIEVAL TAG RULES:

- Use exactly 6.
- Order them from strongest/specific to broader.
- Use established genres, subgenres, styles, or common
  music mood tags.
- Prefer terms likely to exist on Last.fm.
- Do not invent aesthetic phrases.
- Do not use video terminology.
- The six tags should represent complementary aspects
  of the desired music where possible.

BAD retrieval tags:

"neon ambiance"
"night drive music"
"cinematic car edit"
"city lights soundtrack"

GOOD retrieval tags:

synthwave
dream pop
chillwave
electropop
electronic
atmospheric
darkwave
shoegaze
ambient
downtempo
indie pop
alternative
energetic


SEMANTIC TRAIT RULES:

- Use exactly 4.
- Keep each trait short.
- They may describe atmosphere, texture, emotion,
  momentum, build, payoff, sonic character, etc.
- These ARE allowed to contain descriptive ideas that
  would make poor Last.fm search tags.

Examples:

"neon nighttime atmosphere"
"dreamy electronic texture"
"gradual energetic build"
"soft emotional vocals"


GENERAL RULES:

- Return valid JSON only.
- Do not use Markdown.
- Do not use code fences.
- Do not recommend songs.
- Do not recommend artists.
- Do not explain your reasoning.
- Keep everything concise.

Return exactly this JSON shape:

{{
    "retrieval_tags": [
        "tag1",
        "tag2",
        "tag3",
        "tag4",
        "tag5",
        "tag6"
    ],
    "semantic_traits": [
        "trait1",
        "trait2",
        "trait3",
        "trait4"
    ],
    "summary": "one short sentence describing the desired music",
    "energy": "one short description",
    "vocal_preference": "one short description"
}}


EDITOR BRIEF

Project:
{payload.project_name}

Video type:
{payload.video_type}

Duration:
{payload.target_duration_seconds} seconds

Mood:
{payload.mood}

Pace:
{payload.pace}

Vocals:
{payload.vocal_style}

Structure:
{payload.structure_preference}

Creative intent:
{payload.creative_intent}
"""


    try:

        completion = (
            client
            .chat
            .completions
            .create(
                model=QWEN_MODEL_ID,

                messages=[
                    {
                        "role":
                            "system",

                        "content":
                            (
                                "You are Nova, "
                                "Syncora's music-discovery "
                                "assistant. Return concise "
                                "valid JSON only."
                            )
                    },
                    {
                        "role":
                            "user",

                        "content":
                            prompt
                    }
                ],

                temperature=0.25,

                top_p=0.8,

                max_tokens=400
            )
        )


    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    (
                        f"{BUILD_ID}: "
                        "LM Studio Qwen request failed."
                    ),

                "message":
                    str(error)
            }
        )


    if not completion.choices:

        raise HTTPException(
            status_code=500,
            detail=(
                f"{BUILD_ID}: "
                "LM Studio returned zero "
                "Qwen choices."
            )
        )


    raw = (
        completion
        .choices[0]
        .message
        .content
    )


    profile = parse_nova_json(
        raw
    )


    retrieval_tags = profile.get(
        "retrieval_tags",
        []
    )

    semantic_traits = profile.get(
        "semantic_traits",
        []
    )


    if not isinstance(
        retrieval_tags,
        list
    ):

        raise HTTPException(
            status_code=500,
            detail=(
                f"{BUILD_ID}: "
                "retrieval_tags was not a list."
            )
        )


    if not isinstance(
        semantic_traits,
        list
    ):

        raise HTTPException(
            status_code=500,
            detail=(
                f"{BUILD_ID}: "
                "semantic_traits was not a list."
            )
        )


    clean_retrieval_tags = []


    for tag in retrieval_tags:

        if not isinstance(
            tag,
            str
        ):

            continue


        tag = tag.strip()


        if not tag:
            continue


        if tag.casefold() in [
            existing.casefold()
            for existing
            in clean_retrieval_tags
        ]:

            continue


        clean_retrieval_tags.append(
            tag
        )


    clean_retrieval_tags = (
        clean_retrieval_tags[:6]
    )


    if len(
        clean_retrieval_tags
    ) < 4:

        raise HTTPException(
            status_code=500,
            detail={
                "error":
                    (
                        f"{BUILD_ID}: Nova generated "
                        "fewer than four usable "
                        "retrieval tags."
                    ),

                "profile":
                    profile
            }
        )


    clean_semantic_traits = []


    for trait in semantic_traits:

        if not isinstance(
            trait,
            str
        ):

            continue


        trait = trait.strip()


        if not trait:
            continue


        if trait.casefold() in [
            existing.casefold()
            for existing
            in clean_semantic_traits
        ]:

            continue


        clean_semantic_traits.append(
            trait
        )


    clean_semantic_traits = (
        clean_semantic_traits[:4]
    )


    profile[
        "retrieval_tags"
    ] = clean_retrieval_tags


    profile[
        "semantic_traits"
    ] = clean_semantic_traits


    return profile


# =====================================================
# TAG NORMALIZATION
# =====================================================

def normalize_tag(
    value: str
):

    value = (
        value
        .casefold()
        .strip()
    )


    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )


    value = re.sub(
        r"\s+",
        " ",
        value
    )


    return value.strip()


# =====================================================
# TAG SIMILARITY
# =====================================================

def tag_similarity(
    desired_tag: str,
    actual_tag: str
):

    desired = normalize_tag(
        desired_tag
    )

    actual = normalize_tag(
        actual_tag
    )


    if not desired or not actual:
        return 0.0


    # Exact match.

    if desired == actual:
        return 1.0


    desired_compact = (
        desired.replace(
            " ",
            ""
        )
    )

    actual_compact = (
        actual.replace(
            " ",
            ""
        )
    )


    # Formatting variants:
    #
    # synth pop -> synthpop

    if (
        desired_compact
        ==
        actual_compact
    ):

        return 0.95


    desired_words = (
        desired.split()
    )

    actual_words = (
        actual.split()
    )


    desired_word_set = set(
        desired_words
    )

    actual_word_set = set(
        actual_words
    )


    # =================================================
    # SPECIFIC MULTI-WORD DESIRED TAG
    #
    # dream pop -> pop = NO
    # =================================================

    if len(
        desired_words
    ) > 1:


        if len(
            actual_words
        ) == 1:

            return 0.0


        if desired_word_set.issubset(
            actual_word_set
        ):

            return 0.88


        overlap = len(
            desired_word_set
            &
            actual_word_set
        )


        coverage = (
            overlap
            /
            len(
                desired_word_set
            )
        )


        if coverage >= 0.75:
            return 0.65


        return 0.0


    # =================================================
    # BROAD SINGLE-WORD DESIRED TAG
    #
    # electronic -> electronic rock
    # =================================================

    desired_word = (
        desired_words[0]
    )


    if desired_word in actual_word_set:
        return 0.78


    if (
        len(
            desired_word
        ) >= 4
        and
        desired_word
        in actual_compact
    ):

        return 0.60


    return 0.0


# =====================================================
# LAST.FM SEARCH
# =====================================================

async def get_lastfm_tracks_for_tag(
    http_client: httpx.AsyncClient,
    tag: str,
    limit: int = 10
):

    params = {
        "method":
            "tag.getTopTracks",

        "tag":
            tag,

        "api_key":
            LASTFM_API_KEY,

        "format":
            "json",

        "limit":
            limit
    }


    try:

        response = await http_client.get(
            LASTFM_API_URL,
            params=params
        )


        response.raise_for_status()


        data = response.json()


    except Exception as error:

        print(
            f"Last.fm search failed for "
            f"'{tag}': {error}"
        )

        return []


    if "error" in data:

        print(
            f"Last.fm API error for "
            f"'{tag}': "
            f"{data.get('message')}"
        )

        return []


    tracks = (
        data
        .get(
            "tracks",
            {}
        )
        .get(
            "track",
            []
        )
    )


    results = []


    for position, track in enumerate(
        tracks,
        start=1
    ):

        title = track.get(
            "name"
        )


        artist_data = track.get(
            "artist",
            {}
        )


        if isinstance(
            artist_data,
            dict
        ):

            artist_name = (
                artist_data.get(
                    "name"
                )
            )


        else:

            artist_name = (
                str(
                    artist_data
                )
                if artist_data
                else None
            )


        if not title or not artist_name:
            continue


        results.append(
            {
                "title":
                    title,

                "artist":
                    artist_name,

                "lastfm_url":
                    track.get(
                        "url"
                    ),

                "mbid":
                    track.get(
                        "mbid"
                    )
                    or None,

                "source_tag":
                    tag,

                "tag_rank":
                    position
            }
        )


    return results


# =====================================================
# ALL SIX LAST.FM SEARCHES
# =====================================================

async def search_lastfm_all_usable(
    retrieval_tags
):

    # All six Qwen retrieval tags are queried
    # concurrently.
    #
    # Unlike 0.7.1, we no longer discard valid
    # tags #5 and #6.
    #
    # Every tag that successfully returns tracks
    # is allowed to contribute candidates.

    async with httpx.AsyncClient(
        timeout=10.0
    ) as http_client:


        tasks = [

            get_lastfm_tracks_for_tag(
                http_client=http_client,
                tag=tag,
                limit=10
            )

            for tag in retrieval_tags

        ]


        results = await asyncio.gather(
            *tasks
        )


    search_results = [

        {
            "tag":
                tag,

            "tracks":
                tracks
        }

        for tag, tracks
        in zip(
            retrieval_tags,
            results
        )

    ]


    dead_tags = [

        item[
            "tag"
        ]

        for item
        in search_results

        if not item[
            "tracks"
        ]

    ]


    usable_results = [

        item

        for item
        in search_results

        if item[
            "tracks"
        ]

    ]


    if len(
        usable_results
    ) < 2:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    (
                        f"{BUILD_ID}: Last.fm "
                        "returned usable results "
                        "for fewer than two "
                        "retrieval tags."
                    ),

                "retrieval_tags":
                    retrieval_tags,

                "dead_tags":
                    dead_tags
            }
        )


    active_tags = [

        item[
            "tag"
        ]

        for item
        in usable_results

    ]


    tag_results = [

        item[
            "tracks"
        ]

        for item
        in usable_results

    ]


    return {
        "tag_results":
            tag_results,

        "active_tags":
            active_tags,

        "dead_tags":
            dead_tags
    }


# =====================================================
# UNIQUE INITIAL CANDIDATE COUNT
# =====================================================

def count_unique_initial_candidates(
    tag_results
):

    keys = set()


    for tag_tracks in tag_results:

        for track in tag_tracks:

            keys.add(
                (
                    track[
                        "title"
                    ]
                    .strip()
                    .casefold(),

                    track[
                        "artist"
                    ]
                    .strip()
                    .casefold()
                )
            )


    return len(
        keys
    )


# =====================================================
# BALANCED SHORTLIST
# =====================================================

def build_balanced_shortlist(
    tag_results,
    per_tag: int = 2
):

    # 0.7.2:
    #
    # Up to 6 usable retrieval tags
    # ×
    # top 2 songs from each
    #
    # = maximum ~12 candidates
    #
    # Duplicate songs across tags are merged.

    candidates = {}


    for tag_tracks in tag_results:

        for track in tag_tracks[
            :per_tag
        ]:

            key = (
                track[
                    "title"
                ]
                .strip()
                .casefold(),

                track[
                    "artist"
                ]
                .strip()
                .casefold()
            )


            if key not in candidates:

                candidates[
                    key
                ] = {
                    "title":
                        track[
                            "title"
                        ],

                    "artist":
                        track[
                            "artist"
                        ],

                    "lastfm_url":
                        track[
                            "lastfm_url"
                        ],

                    "mbid":
                        track[
                            "mbid"
                        ],

                    "retrieval_matches":
                        []
                }


            candidates[
                key
            ][
                "retrieval_matches"
            ].append(
                {
                    "tag":
                        track[
                            "source_tag"
                        ],

                    "rank":
                        track[
                            "tag_rank"
                        ]
                }
            )


    return list(
        candidates.values()
    )


# =====================================================
# TRACK TAG ENRICHMENT
# =====================================================

async def enrich_candidate_tags(
    http_client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    candidate
):

    params = {
        "method":
            "track.getTopTags",

        "artist":
            candidate[
                "artist"
            ],

        "track":
            candidate[
                "title"
            ],

        "autocorrect":
            1,

        "api_key":
            LASTFM_API_KEY,

        "format":
            "json"
    }


    try:

        async with semaphore:

            response = await http_client.get(
                LASTFM_API_URL,
                params=params
            )


        response.raise_for_status()


        data = response.json()


    except Exception as error:

        print(
            "Last.fm enrichment failed for "
            f"{candidate['artist']} - "
            f"{candidate['title']}: "
            f"{error}"
        )


        enriched = dict(
            candidate
        )


        enriched[
            "top_tags"
        ] = []


        return enriched


    if "error" in data:

        enriched = dict(
            candidate
        )


        enriched[
            "top_tags"
        ] = []


        return enriched


    tag_data = (
        data
        .get(
            "toptags",
            {}
        )
        .get(
            "tag",
            []
        )
    )


    if isinstance(
        tag_data,
        dict
    ):

        tag_data = [
            tag_data
        ]


    top_tags = []


    for tag in tag_data[
        :20
    ]:

        if not isinstance(
            tag,
            dict
        ):

            continue


        name = tag.get(
            "name"
        )


        if not name:
            continue


        try:

            count = int(
                tag.get(
                    "count",
                    0
                )
            )


        except (
            TypeError,
            ValueError
        ):

            count = 0


        top_tags.append(
            {
                "name":
                    name,

                "count":
                    count
            }
        )


    enriched = dict(
        candidate
    )


    enriched[
        "top_tags"
    ] = top_tags


    return enriched


async def enrich_shortlist_parallel(
    shortlist
):

    semaphore = asyncio.Semaphore(
        6
    )


    async with httpx.AsyncClient(
        timeout=10.0
    ) as http_client:


        tasks = [

            enrich_candidate_tags(
                http_client=http_client,
                semaphore=semaphore,
                candidate=candidate
            )

            for candidate
            in shortlist

        ]


        return await asyncio.gather(
            *tasks
        )


# =====================================================
# EMBEDDING TEXT BUILDERS
# =====================================================

def build_embedding_query(
    profile,
    active_retrieval_tags
):

    retrieval_text = ", ".join(
        active_retrieval_tags
    )


    semantic_text = ", ".join(
        profile.get(
            "semantic_traits",
            []
        )
    )


    summary = profile.get(
        "summary",
        ""
    )


    energy = profile.get(
        "energy",
        ""
    )


    vocals = profile.get(
        "vocal_preference",
        ""
    )


    return (
        "search_query: "
        "Desired music profile. "
        f"Genres and styles: {retrieval_text}. "
        f"Semantic qualities: {semantic_text}. "
        f"Overall sound: {summary}. "
        f"Energy: {energy}. "
        f"Vocals: {vocals}."
    )


def build_candidate_embedding_document(
    candidate
):

    tag_names = [

        tag[
            "name"
        ]

        for tag
        in candidate.get(
            "top_tags",
            []
        )[:12]

        if tag.get(
            "name"
        )

    ]


    if not tag_names:

        tag_names = [

            match[
                "tag"
            ]

            for match
            in candidate.get(
                "retrieval_matches",
                []
            )

        ]


    tag_text = ", ".join(
        tag_names
    )


    return (
        "search_document: "
        "Candidate music profile. "
        f"Music tags and qualities: {tag_text}."
    )


# =====================================================
# COSINE SIMILARITY
# =====================================================

def cosine_similarity(
    vector_a,
    vector_b
):

    dot_product = sum(

        a * b

        for a, b
        in zip(
            vector_a,
            vector_b
        )

    )


    magnitude_a = math.sqrt(
        sum(
            a * a
            for a
            in vector_a
        )
    )


    magnitude_b = math.sqrt(
        sum(
            b * b
            for b
            in vector_b
        )
    )


    if (
        magnitude_a == 0
        or
        magnitude_b == 0
    ):

        return 0.0


    return (
        dot_product
        /
        (
            magnitude_a
            *
            magnitude_b
        )
    )


# =====================================================
# EMBEDDING CANDIDATES
# =====================================================

def attach_semantic_similarity(
    profile,
    active_retrieval_tags,
    candidates
):

    query = build_embedding_query(
        profile,
        active_retrieval_tags
    )


    documents = [

        build_candidate_embedding_document(
            candidate
        )

        for candidate
        in candidates

    ]


    texts = [
        query,
        *documents
    ]


    try:

        response = (
            client
            .embeddings
            .create(
                model=EMBEDDING_MODEL_ID,
                input=texts
            )
        )


    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    (
                        f"{BUILD_ID}: "
                        "Nova embedding request failed."
                    ),

                "message":
                    str(error)
            }
        )


    ordered_data = sorted(
        response.data,
        key=lambda item:
            item.index
    )


    vectors = [

        item.embedding

        for item
        in ordered_data

    ]


    if len(
        vectors
    ) != len(
        texts
    ):

        raise HTTPException(
            status_code=500,
            detail=(
                f"{BUILD_ID}: embedding model "
                "returned an unexpected number "
                "of vectors."
            )
        )


    query_vector = (
        vectors[0]
    )


    enriched = []


    for candidate, vector in zip(
        candidates,
        vectors[1:]
    ):

        candidate_copy = dict(
            candidate
        )


        candidate_copy[
            "semantic_similarity"
        ] = cosine_similarity(
            query_vector,
            vector
        )


        enriched.append(
            candidate_copy
        )


    return enriched


# =====================================================
# SEMANTIC CALIBRATION
# =====================================================

def calibrate_semantic_similarity(
    similarity: float
):

    lower_bound = 0.55
    upper_bound = 0.85


    normalized = (
        similarity
        -
        lower_bound
    ) / (
        upper_bound
        -
        lower_bound
    )


    return min(
        1.0,
        max(
            0.0,
            normalized
        )
    )


# =====================================================
# HYBRID SCORING
# =====================================================

def score_enriched_candidates(
    active_retrieval_tags,
    enriched_candidates
):

    desired_tags = (
        active_retrieval_tags
    )


    # 0.7.2:
    #
    # Qwen can now contribute up to six active
    # retrieval tags.
    #
    # Earlier tags still receive slightly more
    # importance because Qwen orders them from
    # strongest to broader.

    importance_weights = [
        1.00,
        0.94,
        0.88,
        0.82,
        0.76,
        0.70
    ]


    total_importance = sum(
        importance_weights[
            :len(
                desired_tags
            )
        ]
    )


    normalized_desired_tags = [

        normalize_tag(
            tag
        )

        for tag
        in desired_tags

    ]


    scored = []


    for candidate in enriched_candidates:

        top_tags = candidate.get(
            "top_tags",
            []
        )


        matched_desired = []

        weighted_tag_evidence = (
            0.0
        )


        # =========================================
        # 1. LAST.FM TRACK-SPECIFIC TAG EVIDENCE
        #
        # Maximum: 45 points
        # =========================================

        for desired_index, desired_tag in enumerate(
            desired_tags
        ):

            importance = (
                importance_weights[
                    desired_index
                ]

                if desired_index
                < len(
                    importance_weights
                )

                else 0.65
            )


            best_similarity = 0.0
            best_tag = None
            best_count = 0


            for actual_tag in top_tags:

                similarity = tag_similarity(
                    desired_tag,
                    actual_tag[
                        "name"
                    ]
                )


                if similarity > best_similarity:

                    best_similarity = (
                        similarity
                    )

                    best_tag = (
                        actual_tag[
                            "name"
                        ]
                    )

                    best_count = (
                        actual_tag[
                            "count"
                        ]
                    )


            if best_similarity > 0:

                strength = (
                    0.70
                    +
                    (
                        min(
                            max(
                                best_count,
                                0
                            ),
                            100
                        )
                        / 100
                    )
                    * 0.30
                )


                evidence = (
                    importance
                    *
                    best_similarity
                    *
                    strength
                )


                weighted_tag_evidence += (
                    evidence
                )


                matched_desired.append(
                    {
                        "nova_tag":
                            desired_tag,

                        "lastfm_tag":
                            best_tag,

                        "lastfm_count":
                            best_count,

                        "similarity":
                            round(
                                best_similarity,
                                2
                            )
                    }
                )


        if total_importance > 0:

            tag_evidence_points = (
                weighted_tag_evidence
                /
                total_importance
            ) * 45


        else:

            tag_evidence_points = (
                0.0
            )


        # =========================================
        # 2. EMBEDDING SEMANTIC FIT
        #
        # Maximum: 35 points
        # =========================================

        raw_semantic_similarity = (
            candidate.get(
                "semantic_similarity",
                0.0
            )
        )


        semantic_fit = (
            calibrate_semantic_similarity(
                raw_semantic_similarity
            )
        )


        semantic_points = (
            semantic_fit
            *
            35
        )


        # =========================================
        # 3. LAST.FM RETRIEVAL EVIDENCE
        #
        # Maximum: 20 points
        # =========================================

        retrieval_evidence = (
            0.0
        )


        for retrieval in candidate[
            "retrieval_matches"
        ]:

            normalized_retrieval_tag = (
                normalize_tag(
                    retrieval[
                        "tag"
                    ]
                )
            )


            try:

                desired_index = (
                    normalized_desired_tags
                    .index(
                        normalized_retrieval_tag
                    )
                )


            except ValueError:

                desired_index = (
                    0
                )


            importance = (
                importance_weights[
                    desired_index
                ]

                if desired_index
                < len(
                    importance_weights
                )

                else 0.65
            )


            rank = retrieval[
                "rank"
            ]


            rank_quality = max(
                0.10,
                (11 - rank) / 10
            )


            retrieval_evidence += (
                importance
                *
                rank_quality
            )


        retrieval_points = min(
            20,
            (
                retrieval_evidence
                /
                1.4
            )
            * 20
        )


        # =========================================
        # FINAL SCORE
        # =========================================

        score = (
            tag_evidence_points
            +
            semantic_points
            +
            retrieval_points
        )


        score = int(
            round(
                min(
                    99,
                    max(
                        0,
                        score
                    )
                )
            )
        )


        scored.append(
            {
                "title":
                    candidate[
                        "title"
                    ],

                "artist":
                    candidate[
                        "artist"
                    ],

                "match_score":
                    score,

                "semantic_similarity":
                    round(
                        raw_semantic_similarity,
                        4
                    ),

                "semantic_fit":
                    round(
                        semantic_fit,
                        4
                    ),

                "score_breakdown": {
                    "lastfm_tag_evidence":
                        round(
                            tag_evidence_points,
                            2
                        ),

                    "semantic_fit":
                        round(
                            semantic_points,
                            2
                        ),

                    "lastfm_retrieval":
                        round(
                            retrieval_points,
                            2
                        )
                },

                "matched_nova_tags": [

                    match[
                        "nova_tag"
                    ]

                    for match
                    in matched_desired

                ],

                "match_evidence":
                    matched_desired,

                "retrieval_matches":
                    candidate[
                        "retrieval_matches"
                    ],

                "top_lastfm_tags":
                    top_tags[:8],

                "lastfm_url":
                    candidate[
                        "lastfm_url"
                    ],

                "mbid":
                    candidate[
                        "mbid"
                    ]
            }
        )


    scored.sort(
        key=lambda item: (
            item[
                "match_score"
            ],

            item[
                "semantic_similarity"
            ],

            len(
                item[
                    "matched_nova_tags"
                ]
            )
        ),

        reverse=True
    )


    return scored


# =====================================================
# SELECT FINAL THREE
# =====================================================

def select_top_three(
    candidates
):

    # This remains the user-facing behavior:
    #
    # Nova always returns THREE recommendations.

    if len(
        candidates
    ) < 3:

        raise HTTPException(
            status_code=500,
            detail=(
                f"{BUILD_ID}: fewer than "
                "three candidate tracks "
                "were available."
            )
        )


    selected = []

    used_artists = set()


    # Prefer three different artists.

    for candidate in candidates:

        artist_key = (
            candidate[
                "artist"
            ]
            .strip()
            .casefold()
        )


        if artist_key in used_artists:
            continue


        selected.append(
            candidate
        )


        used_artists.add(
            artist_key
        )


        if len(
            selected
        ) == 3:

            break


    # Fallback if artist diversity prevents
    # us from reaching three.

    if len(
        selected
    ) < 3:

        for candidate in candidates:

            if candidate in selected:
                continue


            selected.append(
                candidate
            )


            if len(
                selected
            ) == 3:

                break


    recommendations = []


    for rank, candidate in enumerate(
        selected,
        start=1
    ):

        matched_tags = candidate[
            "matched_nova_tags"
        ]


        semantic_similarity = candidate[
            "semantic_similarity"
        ]


        if matched_tags:

            reason = (
                "Last.fm's track-specific tags "
                "matched Nova's retrieval profile on "
                +
                ", ".join(
                    matched_tags
                )
                +
                f", with semantic similarity "
                f"{semantic_similarity:.2f}."
            )


        else:

            reason = (
                "The track's Last.fm music profile "
                "showed semantic compatibility with "
                "Nova's desired sound "
                f"({semantic_similarity:.2f})."
            )


        recommendations.append(
            {
                "rank":
                    rank,

                "title":
                    candidate[
                        "title"
                    ],

                "artist":
                    candidate[
                        "artist"
                    ],

                "match_score":
                    candidate[
                        "match_score"
                    ],

                "reason":
                    reason,

                "semantic_similarity":
                    candidate[
                        "semantic_similarity"
                    ],

                "semantic_fit":
                    candidate[
                        "semantic_fit"
                    ],

                "score_breakdown":
                    candidate[
                        "score_breakdown"
                    ],

                "matched_tags":
                    matched_tags,

                "top_lastfm_tags":
                    candidate[
                        "top_lastfm_tags"
                    ],

                "match_evidence":
                    candidate[
                        "match_evidence"
                    ],

                "lastfm_url":
                    candidate[
                        "lastfm_url"
                    ],

                "mbid":
                    candidate[
                        "mbid"
                    ]
            }
        )


    return recommendations


# =====================================================
# ROOT
# =====================================================

@app.get("/")
def root():

    return {
        "message":
            "Syncora backend is running.",

        "build":
            BUILD_ID,

        "qwen_model":
            QWEN_MODEL_ID,

        "embedding_model":
            EMBEDDING_MODEL_ID,

        "nova_mode":
            "six-tag-balanced-hybrid"
    }


# =====================================================
# QWEN TEST
# =====================================================

@app.get("/test-llm")
def test_llm():

    try:

        completion = (
            client
            .chat
            .completions
            .create(
                model=QWEN_MODEL_ID,

                messages=[
                    {
                        "role":
                            "user",

                        "content":
                            (
                                "Reply with exactly: "
                                "Syncora backend can "
                                "talk to Nova Qwen."
                            )
                    }
                ],

                temperature=0,

                max_tokens=30
            )
        )


        return {
            "build":
                BUILD_ID,

            "model":
                QWEN_MODEL_ID,

            "response":
                (
                    completion
                    .choices[0]
                    .message
                    .content
                )
        }


    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    str(error)
            }
        )


# =====================================================
# EMBEDDING TEST
# =====================================================

@app.get("/test-embed")
def test_embed():

    try:

        response = (
            client
            .embeddings
            .create(
                model=EMBEDDING_MODEL_ID,

                input=[
                    (
                        "search_query: "
                        "dreamy synthwave music"
                    ),
                    (
                        "search_document: "
                        "atmospheric electronic "
                        "synthwave music"
                    )
                ]
            )
        )


        ordered = sorted(
            response.data,
            key=lambda item:
                item.index
        )


        similarity = cosine_similarity(
            ordered[
                0
            ].embedding,

            ordered[
                1
            ].embedding
        )


        return {
            "build":
                BUILD_ID,

            "model":
                EMBEDDING_MODEL_ID,

            "vector_length":
                len(
                    ordered[
                        0
                    ].embedding
                ),

            "similarity":
                round(
                    similarity,
                    4
                )
        }


    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    str(error)
            }
        )


# =====================================================
# LAST.FM TEST
# =====================================================

@app.get("/test-lastfm")
async def test_lastfm(
    tag: str = "dreamy"
):

    async with httpx.AsyncClient(
        timeout=10.0
    ) as http_client:


        tracks = await (
            get_lastfm_tracks_for_tag(
                http_client=http_client,
                tag=tag,
                limit=10
            )
        )


    return {
        "build":
            BUILD_ID,

        "tag":
            tag,

        "count":
            len(
                tracks
            ),

        "tracks":
            tracks
    }


# =====================================================
# NOVA PROFILE
# =====================================================

@app.post("/nova/generate")
async def nova_generate(
    payload: NovaRequest
):

    start = (
        time.perf_counter()
    )


    profile = (
        await asyncio.to_thread(
            create_nova_profile,
            payload
        )
    )


    cache_nova_profile(
        payload,
        profile
    )


    elapsed_ms = round(
        (
            time.perf_counter()
            -
            start
        )
        * 1000
    )


    return {
        "build":
            BUILD_ID,

        "model":
            QWEN_MODEL_ID,

        "profile_source":
            "qwen",

        "timing_ms": {
            "qwen_profile":
                elapsed_ms
        },

        "profile":
            profile
    }


# =====================================================
# NOVA RECOMMEND
# =====================================================

@app.post("/nova/recommend")
async def nova_recommend(
    payload: NovaRequest
):

    total_start = (
        time.perf_counter()
    )


    # ---------------------------------------------
    # 1. QWEN PROFILE
    # ---------------------------------------------

    profile_start = (
        time.perf_counter()
    )


    profile = (
        get_cached_nova_profile(
            payload
        )
    )


    if profile is not None:

        profile_source = (
            "cache"
        )


    else:

        profile_source = (
            "qwen"
        )


        profile = (
            await asyncio.to_thread(
                create_nova_profile,
                payload
            )
        )


        cache_nova_profile(
            payload,
            profile
        )


    profile_ms = round(
        (
            time.perf_counter()
            -
            profile_start
        )
        * 1000
    )


    # ---------------------------------------------
    # 2. ALL SIX LAST.FM RETRIEVAL TAGS
    # ---------------------------------------------

    search_start = (
        time.perf_counter()
    )


    search_bundle = (
        await search_lastfm_all_usable(
            profile[
                "retrieval_tags"
            ]
        )
    )


    search_ms = round(
        (
            time.perf_counter()
            -
            search_start
        )
        * 1000
    )


    tag_results = (
        search_bundle[
            "tag_results"
        ]
    )


    active_retrieval_tags = (
        search_bundle[
            "active_tags"
        ]
    )


    candidate_count = (
        count_unique_initial_candidates(
            tag_results
        )
    )


    # ---------------------------------------------
    # 3. BALANCED SHORTLIST
    #
    # Up to six usable tags × top two tracks.
    #
    # Still approximately twelve candidates.
    # ---------------------------------------------

    shortlist = (
        build_balanced_shortlist(
            tag_results,
            per_tag=2
        )
    )


    if len(
        shortlist
    ) < 3:

        raise HTTPException(
            status_code=500,
            detail=(
                f"{BUILD_ID}: Last.fm "
                "returned fewer than three "
                "shortlist candidates."
            )
        )


    # ---------------------------------------------
    # 4. LAST.FM TRACK TAG ENRICHMENT
    # ---------------------------------------------

    enrichment_start = (
        time.perf_counter()
    )


    enriched = (
        await enrich_shortlist_parallel(
            shortlist
        )
    )


    enrichment_ms = round(
        (
            time.perf_counter()
            -
            enrichment_start
        )
        * 1000
    )


    # ---------------------------------------------
    # 5. NOMIC SEMANTIC SIMILARITY
    # ---------------------------------------------

    embedding_start = (
        time.perf_counter()
    )


    semantic_candidates = (
        await asyncio.to_thread(
            attach_semantic_similarity,

            profile,

            active_retrieval_tags,

            enriched
        )
    )


    embedding_ms = round(
        (
            time.perf_counter()
            -
            embedding_start
        )
        * 1000
    )


    # ---------------------------------------------
    # 6. HYBRID SCORING
    # ---------------------------------------------

    scored = (
        score_enriched_candidates(
            active_retrieval_tags,
            semantic_candidates
        )
    )


    # ---------------------------------------------
    # 7. FINAL THREE RECOMMENDATIONS
    # ---------------------------------------------

    recommendations = (
        select_top_three(
            scored
        )
    )


    total_ms = round(
        (
            time.perf_counter()
            -
            total_start
        )
        * 1000
    )


    return {
        "build":
            BUILD_ID,

        "qwen_model":
            QWEN_MODEL_ID,

        "embedding_model":
            EMBEDDING_MODEL_ID,

        "mode":
            "six-tag-balanced-hybrid",

        "profile_source":
            profile_source,

        "profile":
            profile,

        "retrieval_debug": {

            "requested_tags":
                profile[
                    "retrieval_tags"
                ],

            "active_tags":
                active_retrieval_tags,

            "dead_tags":
                search_bundle[
                    "dead_tags"
                ],

            "candidate_strategy":
                "top-2-per-usable-tag",

            "usable_tag_count":
                len(
                    active_retrieval_tags
                ),

            "maximum_shortlist_size":
                (
                    len(
                        active_retrieval_tags
                    )
                    * 2
                )
        },

        "candidate_count":
            candidate_count,

        "shortlist_count":
            len(
                shortlist
            ),

        "timing_ms": {

            "qwen_profile":
                profile_ms,

            "lastfm_initial_search":
                search_ms,

            "lastfm_enrichment":
                enrichment_ms,

            "embedding_similarity":
                embedding_ms,

            "total":
                total_ms
        },

        "scoring_weights": {

            "lastfm_tag_evidence":
                45,

            "semantic_similarity":
                35,

            "lastfm_retrieval":
                20
        },

        "recommendation_count":
            len(
                recommendations
            ),

        "recommendations":
            recommendations
    }