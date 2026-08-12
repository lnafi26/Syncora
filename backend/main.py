from pathlib import Path
import asyncio
import hashlib
import json
import math
import re
import time

import httpx

from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAI
from pydantic import BaseModel, Field


# =====================================================
# BUILD / MODELS
# =====================================================

BUILD_ID = "nova-hybrid-0.7.3"

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
    version="0.7.3"
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
# GLOBAL ERROR HANDLING
# =====================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):

    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "error":
                    "Invalid Nova request body.",

                "message":
                    (
                        "One or more required fields "
                        "were missing or invalid."
                    ),

                "issues":
                    exc.errors(),

                "build":
                    BUILD_ID
            }
        }
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception
):

    # Full error still appears in the backend
    # terminal for development.
    print(
        f"[UNHANDLED ERROR] "
        f"{request.method} {request.url.path}: "
        f"{type(exc).__name__}: {exc}"
    )

    # Do not expose a Python traceback to the
    # browser/frontend.
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "error":
                    "Internal Syncora backend error.",

                "message":
                    (
                        "An unexpected backend error "
                        "occurred."
                    ),

                "build":
                    BUILD_ID
            }
        }
    )


# =====================================================
# LM STUDIO CLIENT
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

    project_name: str = Field(
        min_length=1,
        max_length=200
    )

    video_type: str = Field(
        min_length=1,
        max_length=200
    )

    target_duration_seconds: int = Field(
        gt=0,
        le=86400
    )

    mood: str = Field(
        min_length=1,
        max_length=200
    )

    pace: str = Field(
        min_length=1,
        max_length=200
    )

    vocal_style: str = Field(
        min_length=1,
        max_length=200
    )

    structure_preference: str = Field(
        min_length=1,
        max_length=300
    )

    creative_intent: str = Field(
        default="",
        max_length=2000
    )


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


    profile = cached.get(
        "profile"
    )


    # Protect against an old cached profile if the
    # backend schema changes during development.

    if not isinstance(
        profile,
        dict
    ):

        nova_profile_cache.pop(
            key,
            None
        )

        return None


    if (
        "retrieval_tags"
        not in profile
        or
        "semantic_traits"
        not in profile
    ):

        nova_profile_cache.pop(
            key,
            None
        )

        return None


    return profile


# =====================================================
# UTILITY: CLEAN STRING LIST
# =====================================================

def clean_string_list(
    values,
    limit
):

    if not isinstance(
        values,
        list
    ):

        return []


    cleaned = []


    for value in values:

        if not isinstance(
            value,
            str
        ):

            continue


        value = value.strip()


        if not value:
            continue


        if value.casefold() in [
            existing.casefold()
            for existing
            in cleaned
        ]:

            continue


        cleaned.append(
            value
        )


        if len(
            cleaned
        ) >= limit:

            break


    return cleaned


# =====================================================
# JSON PARSER
# =====================================================

def parse_nova_json(
    raw: str
):

    if raw is None or not raw.strip():

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    "Nova received an empty Qwen response.",

                "stage":
                    "qwen_profile",

                "build":
                    BUILD_ID
            }
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

        parsed = json.loads(
            cleaned
        )


    except json.JSONDecodeError as error:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    "Qwen returned invalid JSON.",

                "stage":
                    "qwen_profile",

                "json_error":
                    str(error),

                "raw_response":
                    raw[:1000],

                "build":
                    BUILD_ID
            }
        )


    if not isinstance(
        parsed,
        dict
    ):

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    (
                        "Qwen returned JSON, but the "
                        "top-level value was not an object."
                    ),

                "stage":
                    "qwen_profile",

                "build":
                    BUILD_ID
            }
        )


    return parsed


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

        error_name = (
            type(error).__name__
        )


        if (
            "Timeout"
            in error_name
            or
            "timeout"
            in str(error).lower()
        ):

            raise HTTPException(
                status_code=504,
                detail={
                    "error":
                        "Nova's Qwen request timed out.",

                    "stage":
                        "qwen_profile",

                    "message":
                        (
                            "LM Studio did not complete "
                            "the profile generation within "
                            "the configured timeout."
                        ),

                    "model":
                        QWEN_MODEL_ID,

                    "build":
                        BUILD_ID
                }
            )


        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    "Nova could not reach Qwen.",

                "stage":
                    "qwen_profile",

                "message":
                    str(error),

                "model":
                    QWEN_MODEL_ID,

                "build":
                    BUILD_ID
            }
        )


    if not completion.choices:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    "LM Studio returned zero Qwen choices.",

                "stage":
                    "qwen_profile",

                "model":
                    QWEN_MODEL_ID,

                "build":
                    BUILD_ID
            }
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


    retrieval_tags = clean_string_list(
        profile.get(
            "retrieval_tags",
            []
        ),
        limit=6
    )


    semantic_traits = clean_string_list(
        profile.get(
            "semantic_traits",
            []
        ),
        limit=4
    )


    if len(
        retrieval_tags
    ) < 4:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    (
                        "Qwen generated fewer than four "
                        "usable retrieval tags."
                    ),

                "stage":
                    "qwen_profile",

                "profile":
                    profile,

                "build":
                    BUILD_ID
            }
        )


    if len(
        semantic_traits
    ) < 2:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    (
                        "Qwen generated fewer than two "
                        "usable semantic traits."
                    ),

                "stage":
                    "qwen_profile",

                "profile":
                    profile,

                "build":
                    BUILD_ID
            }
        )


    profile[
        "retrieval_tags"
    ] = retrieval_tags


    profile[
        "semantic_traits"
    ] = semantic_traits


    summary = profile.get(
        "summary"
    )


    energy = profile.get(
        "energy"
    )


    vocal_preference = profile.get(
        "vocal_preference"
    )


    if not isinstance(
        summary,
        str
    ) or not summary.strip():

        profile[
            "summary"
        ] = (
            f"{payload.mood} music for "
            f"{payload.video_type}."
        )


    if not isinstance(
        energy,
        str
    ) or not energy.strip():

        profile[
            "energy"
        ] = payload.pace


    if not isinstance(
        vocal_preference,
        str
    ) or not vocal_preference.strip():

        profile[
            "vocal_preference"
        ] = payload.vocal_style


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


    # Specific requested genre cannot be
    # satisfied by its generic parent.
    #
    # dream pop -> pop = 0

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


    # Broad term can partially match a
    # more specific tag.
    #
    # electronic -> electronic rock

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
# LAST.FM INITIAL SEARCH
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


    except httpx.TimeoutException:

        return {
            "tag":
                tag,

            "tracks":
                [],

            "error":
                "Last.fm request timed out."
        }


    except httpx.HTTPStatusError as error:

        return {
            "tag":
                tag,

            "tracks":
                [],

            "error":
                (
                    "Last.fm returned HTTP "
                    f"{error.response.status_code}."
                )
        }


    except httpx.RequestError as error:

        return {
            "tag":
                tag,

            "tracks":
                [],

            "error":
                f"Last.fm network error: {error}"
        }


    except ValueError:

        return {
            "tag":
                tag,

            "tracks":
                [],

            "error":
                "Last.fm returned invalid JSON."
        }


    if "error" in data:

        return {
            "tag":
                tag,

            "tracks":
                [],

            "error":
                (
                    "Last.fm API error: "
                    f"{data.get('message', 'Unknown error')}"
                )
        }


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


    if not isinstance(
        tracks,
        list
    ):

        tracks = []


    results = []


    for position, track in enumerate(
        tracks,
        start=1
    ):

        if not isinstance(
            track,
            dict
        ):

            continue


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
                    str(title).strip(),

                "artist":
                    str(artist_name).strip(),

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


    return {
        "tag":
            tag,

        "tracks":
            results,

        "error":
            None
    }


# =====================================================
# ALL USABLE LAST.FM SEARCHES
# =====================================================

async def search_lastfm_all_usable(
    retrieval_tags
):

    async with httpx.AsyncClient(
        timeout=10.0
    ) as http_client:


        tasks = [

            get_lastfm_tracks_for_tag(
                http_client=http_client,
                tag=tag,
                limit=10
            )

            for tag
            in retrieval_tags

        ]


        results = await asyncio.gather(
            *tasks
        )


    usable_results = [

        result

        for result
        in results

        if result[
            "tracks"
        ]

    ]


    dead_tags = [

        result[
            "tag"
        ]

        for result
        in results

        if not result[
            "tracks"
        ]

    ]


    failed_queries = [

        {
            "tag":
                result[
                    "tag"
                ],

            "error":
                result[
                    "error"
                ]
        }

        for result
        in results

        if result[
            "error"
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
                        "Last.fm returned usable results "
                        "for fewer than two retrieval tags."
                    ),

                "stage":
                    "lastfm_search",

                "retrieval_tags":
                    retrieval_tags,

                "dead_tags":
                    dead_tags,

                "failed_queries":
                    failed_queries,

                "build":
                    BUILD_ID
            }
        )


    return {
        "tag_results": [
            result[
                "tracks"
            ]

            for result
            in usable_results
        ],

        "active_tags": [
            result[
                "tag"
            ]

            for result
            in usable_results
        ],

        "dead_tags":
            dead_tags,

        "failed_queries":
            failed_queries
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
# BALANCED SHORTLIST + DEDUP DEBUGGING
# =====================================================

def build_balanced_shortlist(
    tag_results,
    per_tag: int = 2
):

    candidates = {}

    raw_slots = 0


    for tag_tracks in tag_results:

        selected_tracks = (
            tag_tracks[
                :per_tag
            ]
        )


        raw_slots += len(
            selected_tracks
        )


        for track in selected_tracks:

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


    candidate_list = list(
        candidates.values()
    )


    merged_candidates = []


    for candidate in candidate_list:

        retrieval_matches = (
            candidate[
                "retrieval_matches"
            ]
        )


        if len(
            retrieval_matches
        ) > 1:

            merged_candidates.append(
                {
                    "title":
                        candidate[
                            "title"
                        ],

                    "artist":
                        candidate[
                            "artist"
                        ],

                    "retrieved_by": [
                        match[
                            "tag"
                        ]

                        for match
                        in retrieval_matches
                    ]
                }
            )


    debug = {
        "raw_slots":
            raw_slots,

        "unique_candidates":
            len(
                candidate_list
            ),

        "duplicates_removed":
            (
                raw_slots
                -
                len(
                    candidate_list
                )
            ),

        "merged_candidates":
            merged_candidates
    }


    return (
        candidate_list,
        debug
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


    enriched = dict(
        candidate
    )


    enriched[
        "top_tags"
    ] = []


    enriched[
        "enrichment_error"
    ] = None


    try:

        async with semaphore:

            response = await http_client.get(
                LASTFM_API_URL,
                params=params
            )


        response.raise_for_status()


        data = response.json()


    except httpx.TimeoutException:

        enriched[
            "enrichment_error"
        ] = "Last.fm enrichment timed out."

        return enriched


    except httpx.HTTPStatusError as error:

        enriched[
            "enrichment_error"
        ] = (
            "Last.fm enrichment returned HTTP "
            f"{error.response.status_code}."
        )

        return enriched


    except httpx.RequestError as error:

        enriched[
            "enrichment_error"
        ] = (
            "Last.fm enrichment network error: "
            f"{error}"
        )

        return enriched


    except ValueError:

        enriched[
            "enrichment_error"
        ] = (
            "Last.fm enrichment returned invalid JSON."
        )

        return enriched


    if "error" in data:

        enriched[
            "enrichment_error"
        ] = (
            "Last.fm enrichment API error: "
            f"{data.get('message', 'Unknown error')}"
        )

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


    if not isinstance(
        tag_data,
        list
    ):

        tag_data = []


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
                    str(name).strip(),

                "count":
                    count
            }
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


        enriched = await asyncio.gather(
            *tasks
        )


    warnings = []


    for candidate in enriched:

        error = candidate.get(
            "enrichment_error"
        )


        if error:

            warnings.append(
                {
                    "stage":
                        "lastfm_enrichment",

                    "track":
                        candidate[
                            "title"
                        ],

                    "artist":
                        candidate[
                            "artist"
                        ],

                    "message":
                        error
                }
            )


    return (
        enriched,
        warnings
    )


# =====================================================
# EMBEDDING QUERY
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


    return (
        "search_query: "
        "Desired music profile. "
        f"Genres and styles: {retrieval_text}. "
        f"Semantic qualities: {semantic_text}. "
        f"Overall sound: {profile.get('summary', '')}. "
        f"Energy: {profile.get('energy', '')}. "
        f"Vocals: {profile.get('vocal_preference', '')}."
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


    return (
        "search_document: "
        "Candidate music profile. "
        "Music tags and qualities: "
        +
        ", ".join(
            tag_names
        )
        +
        "."
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
# EMBEDDING LAYER
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

            raise ValueError(
                (
                    "Embedding model returned "
                    "an unexpected vector count."
                )
            )


        query_vector = (
            vectors[0]
        )


        semantic_candidates = []


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


            semantic_candidates.append(
                candidate_copy
            )


        return (
            semantic_candidates,
            True,
            None
        )


    except Exception as error:

        # Embeddings improve ranking but are not
        # required to return recommendations.
        #
        # If nova-embed fails, Nova falls back to
        # Last.fm tag + retrieval evidence rather
        # than killing the whole POST request.

        fallback_candidates = []


        for candidate in candidates:

            candidate_copy = dict(
                candidate
            )


            candidate_copy[
                "semantic_similarity"
            ] = None


            fallback_candidates.append(
                candidate_copy
            )


        warning = {
            "stage":
                "embedding_similarity",

            "message":
                (
                    "Semantic embeddings were unavailable. "
                    "Nova used Last.fm evidence only."
                ),

            "technical_error":
                str(error)
        }


        return (
            fallback_candidates,
            False,
            warning
        )


# =====================================================
# SEMANTIC CALIBRATION — 0.7.3
# =====================================================

def calibrate_semantic_similarity(
    similarity
):

    if similarity is None:
        return 0.0


    # Sigmoid calibration.
    #
    # Our local tests showed that unrelated music
    # can still produce cosine similarities in the
    # mid/high 0.60s.
    #
    # This curve therefore gives little credit to
    # mediocre semantic similarity and becomes much
    # more generous once a candidate reaches the
    # genuinely strong ~0.78+ region.
    #
    # Approximate behavior:
    #
    # 0.64 -> ~1%
    # 0.68 -> ~5%
    # 0.72 -> ~14%
    # 0.78 -> 50%
    # 0.81 -> ~71%
    # 0.84 -> ~86%
    # 0.88 -> ~95%

    midpoint = 0.78
    steepness = 30.0


    exponent = (
        -steepness
        *
        (
            similarity
            -
            midpoint
        )
    )


    # Protect math.exp from absurd unexpected
    # values, even though cosine similarity
    # should normally remain between -1 and 1.

    exponent = min(
        60.0,
        max(
            -60.0,
            exponent
        )
    )


    return (
        1.0
        /
        (
            1.0
            +
            math.exp(
                exponent
            )
        )
    )


# =====================================================
# HYBRID SCORING
# =====================================================

def score_enriched_candidates(
    active_retrieval_tags,
    enriched_candidates,
    semantic_available
):

    desired_tags = (
        active_retrieval_tags
    )


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


    # Normal operation:
    #
    # 45% tag evidence
    # 35% semantic
    # 20% retrieval
    #
    # If embeddings fail, preserve the same
    # relationship between the remaining two
    # signals and rescale them instead of making
    # every score artificially tiny.

    if semantic_available:

        tag_max_points = 45.0
        semantic_max_points = 35.0
        retrieval_max_points = 20.0


    else:

        tag_max_points = (
            45.0
            /
            65.0
            *
            100.0
        )

        semantic_max_points = 0.0

        retrieval_max_points = (
            20.0
            /
            65.0
            *
            100.0
        )


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
        # =========================================

        for desired_index, desired_tag in enumerate(
            desired_tags
        ):

            importance = (
                importance_weights[
                    desired_index
                ]

                if desired_index
                <
                len(
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
            ) * tag_max_points


        else:

            tag_evidence_points = (
                0.0
            )


        # =========================================
        # 2. SEMANTIC EMBEDDING EVIDENCE
        # =========================================

        raw_semantic_similarity = (
            candidate.get(
                "semantic_similarity"
            )
        )


        semantic_fit = (
            calibrate_semantic_similarity(
                raw_semantic_similarity
            )

            if semantic_available

            else 0.0
        )


        semantic_points = (
            semantic_fit
            *
            semantic_max_points
        )


        # =========================================
        # 3. LAST.FM RETRIEVAL EVIDENCE
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

                continue


            importance = (
                importance_weights[
                    desired_index
                ]

                if desired_index
                <
                len(
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
            retrieval_max_points,

            (
                retrieval_evidence
                /
                1.4
            )
            *
            retrieval_max_points
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
                    (
                        round(
                            raw_semantic_similarity,
                            4
                        )

                        if raw_semantic_similarity
                        is not None

                        else None
                    ),

                "semantic_fit":
                    (
                        round(
                            semantic_fit,
                            4
                        )

                        if semantic_available

                        else None
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

            (
                item[
                    "semantic_similarity"
                ]
                or 0
            ),

            len(
                item[
                    "matched_nova_tags"
                ]
            )
        ),

        reverse=True
    )


    return (
        scored,
        {
            "lastfm_tag_evidence":
                round(
                    tag_max_points,
                    2
                ),

            "semantic_similarity":
                round(
                    semantic_max_points,
                    2
                ),

            "lastfm_retrieval":
                round(
                    retrieval_max_points,
                    2
                )
        }
    )


# =====================================================
# FINAL THREE
# =====================================================

def select_top_three(
    candidates
):

    if len(
        candidates
    ) < 3:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    (
                        "Nova could not produce three "
                        "rankable song candidates."
                    ),

                "stage":
                    "final_selection",

                "candidate_count":
                    len(
                        candidates
                    ),

                "build":
                    BUILD_ID
            }
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
    # Nova from reaching three.

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


        if (
            matched_tags
            and
            semantic_similarity
            is not None
        ):

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


        elif matched_tags:

            reason = (
                "Last.fm's track-specific tags "
                "matched Nova's retrieval profile on "
                +
                ", ".join(
                    matched_tags
                )
                +
                "."
            )


        elif semantic_similarity is not None:

            reason = (
                "The track's Last.fm music profile "
                "showed semantic compatibility with "
                "Nova's desired sound "
                f"({semantic_similarity:.2f})."
            )


        else:

            reason = (
                "The track ranked strongly in "
                "Nova's Last.fm retrieval results."
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


    if len(
        recommendations
    ) != 3:

        raise HTTPException(
            status_code=500,
            detail={
                "error":
                    (
                        "Nova's final selection did not "
                        "contain exactly three songs."
                    ),

                "stage":
                    "final_selection",

                "recommendation_count":
                    len(
                        recommendations
                    ),

                "build":
                    BUILD_ID
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
            "six-tag-sigmoid-hybrid"
    }


# =====================================================
# QWEN HEALTH TEST
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
                    "Qwen health check failed.",

                "message":
                    str(error),

                "model":
                    QWEN_MODEL_ID,

                "build":
                    BUILD_ID
            }
        )


# =====================================================
# EMBEDDING HEALTH TEST
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


        if len(
            ordered
        ) != 2:

            raise ValueError(
                (
                    "Embedding health check "
                    "returned unexpected vector count."
                )
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
                ),

            "calibrated_fit":
                round(
                    calibrate_semantic_similarity(
                        similarity
                    ),
                    4
                )
        }


    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    "Embedding health check failed.",

                "message":
                    str(error),

                "model":
                    EMBEDDING_MODEL_ID,

                "build":
                    BUILD_ID
            }
        )


# =====================================================
# LAST.FM HEALTH TEST
# =====================================================

@app.get("/test-lastfm")
async def test_lastfm(
    tag: str = "dreamy"
):

    async with httpx.AsyncClient(
        timeout=10.0
    ) as http_client:


        result = await (
            get_lastfm_tracks_for_tag(
                http_client=http_client,
                tag=tag,
                limit=10
            )
        )


    if result[
        "error"
    ]:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    "Last.fm health check failed.",

                "message":
                    result[
                        "error"
                    ],

                "tag":
                    tag,

                "build":
                    BUILD_ID
            }
        )


    return {
        "build":
            BUILD_ID,

        "tag":
            tag,

        "count":
            len(
                result[
                    "tracks"
                ]
            ),

        "tracks":
            result[
                "tracks"
            ]
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


    warnings = []


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
    # 2. LAST.FM RETRIEVAL
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


    active_retrieval_tags = (
        search_bundle[
            "active_tags"
        ]
    )


    tag_results = (
        search_bundle[
            "tag_results"
        ]
    )


    if search_bundle[
        "failed_queries"
    ]:

        warnings.append(
            {
                "stage":
                    "lastfm_search",

                "message":
                    (
                        "One or more Last.fm tag "
                        "queries failed, but Nova had "
                        "enough remaining results."
                    ),

                "failed_queries":
                    search_bundle[
                        "failed_queries"
                    ]
            }
        )


    candidate_count = (
        count_unique_initial_candidates(
            tag_results
        )
    )


    # ---------------------------------------------
    # 3. BALANCED SHORTLIST
    # ---------------------------------------------

    (
        shortlist,
        shortlist_debug
    ) = build_balanced_shortlist(
        tag_results,
        per_tag=2
    )


    if len(
        shortlist
    ) < 3:

        raise HTTPException(
            status_code=502,
            detail={
                "error":
                    (
                        "Last.fm returned fewer than "
                        "three unique shortlist candidates."
                    ),

                "stage":
                    "shortlist",

                "shortlist_debug":
                    shortlist_debug,

                "build":
                    BUILD_ID
            }
        )


    # ---------------------------------------------
    # 4. LAST.FM TRACK TAG ENRICHMENT
    # ---------------------------------------------

    enrichment_start = (
        time.perf_counter()
    )


    (
        enriched,
        enrichment_warnings
    ) = (
        await enrich_shortlist_parallel(
            shortlist
        )
    )


    warnings.extend(
        enrichment_warnings
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
    # 5. NOMIC EMBEDDINGS
    # ---------------------------------------------

    embedding_start = (
        time.perf_counter()
    )


    (
        semantic_candidates,
        semantic_available,
        embedding_warning
    ) = (
        await asyncio.to_thread(
            attach_semantic_similarity,

            profile,

            active_retrieval_tags,

            enriched
        )
    )


    if embedding_warning:

        warnings.append(
            embedding_warning
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

    (
        scored,
        scoring_weights
    ) = (
        score_enriched_candidates(
            active_retrieval_tags,
            semantic_candidates,
            semantic_available
        )
    )


    # ---------------------------------------------
    # 7. FINAL THREE
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


    # ---------------------------------------------
    # RESPONSE
    # ---------------------------------------------

    return {
        "build":
            BUILD_ID,

        "qwen_model":
            QWEN_MODEL_ID,

        "embedding_model":
            EMBEDDING_MODEL_ID,

        "mode":
            "six-tag-sigmoid-hybrid",

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

            "failed_queries":
                search_bundle[
                    "failed_queries"
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

        "shortlist_debug":
            shortlist_debug,

        "candidate_count":
            candidate_count,

        "shortlist_count":
            len(
                shortlist
            ),

        "semantic_available":
            semantic_available,

        "semantic_calibration": {
            "type":
                "sigmoid",

            "midpoint":
                0.78,

            "steepness":
                30.0
        },

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

        "scoring_weights":
            scoring_weights,

        "warning_count":
            len(
                warnings
            ),

        "warnings":
            warnings,

        "recommendation_count":
            len(
                recommendations
            ),

        "recommendations":
            recommendations
    }