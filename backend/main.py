import os
from pathlib import Path
import asyncio
import hashlib
import json
import math
import re
import time
import threading
import unicodedata
import html as html_lib
from difflib import SequenceMatcher
import httpx
from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAI
from pydantic import BaseModel, Field
from huggingface_hub import InferenceClient
from datetime import datetime, timezone
from supabase import create_client

BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR / '.env'

config = dotenv_values(ENV_PATH)

def get_setting(name, default=None):
    environment_value = os.environ.get(name)

    if (
        environment_value is not None
        and str(environment_value).strip()
    ):
        return environment_value

    env_file_value = config.get(name)

    if (
        env_file_value is not None
        and str(env_file_value).strip()
    ):
        return env_file_value

    return default


BUILD_ID = 'nova-hybrid-0.7.8'
PULSAR_RESOLVER_BUILD_ID = 'pulsar-youtube-data-resolver-0.3.1'
PULSAR_ANALYSIS_BUILD_ID = 'pulsar-signal-0.6.0'

LLM_PROVIDER = (
    get_setting(
        'LLM_PROVIDER',
        'local',
    )
    .strip()
    .casefold()
)

EMBEDDING_PROVIDER = (
    get_setting(
        'EMBEDDING_PROVIDER',
        'local',
    )
    .strip()
    .casefold()
)

NOVA_DEBUG_RESPONSES = (
    str(
        get_setting(
            'NOVA_DEBUG_RESPONSES',
            'false',
        )
    )
    .strip()
    .casefold()
    in {
        '1',
        'true',
        'yes',
        'on',
    }
)

HF_TOKEN = get_setting(
    'HF_TOKEN'
)

HF_ROUTER_BASE_URL = get_setting(
    'HF_ROUTER_BASE_URL',
    'https://router.huggingface.co/v1',
)

HF_EMBEDDING_INFERENCE_PROVIDER = get_setting(
    'HF_EMBEDDING_INFERENCE_PROVIDER',
    'scaleway',
)

LOCAL_AI_BASE_URL = get_setting(
    'LOCAL_AI_BASE_URL',
    'http://localhost:1234/v1',
)

LOCAL_AI_API_KEY = get_setting(
    'LOCAL_AI_API_KEY',
    'lm-studio',
)

QWEN_MODEL_ID = get_setting(
    'QWEN_MODEL_ID',
    (
        'Qwen/Qwen3.6-35B-A3B:cheapest'
        if LLM_PROVIDER == 'huggingface'
        else
        'nova-qwen'
    ),
)

EMBEDDING_MODEL_ID = get_setting(
    'EMBEDDING_MODEL_ID',
    (
        'Qwen/Qwen3-Embedding-8B'
        if EMBEDDING_PROVIDER == 'huggingface'
        else
        'nova-embed'
    ),
)

SEMANTIC_CALIBRATION_PROFILES = {
    'Qwen/Qwen3-Embedding-8B': {
        'type':
            'bounded_sigmoid',

        'floor':
            0.40,

        'midpoint':
            0.50,

        'ceiling':
            0.64,

        'steepness':
            16.0,
    },
}


DEFAULT_SEMANTIC_CALIBRATION = {
    'type':
        'bounded_sigmoid',

    'floor':
        0.40,

    'midpoint':
        0.50,

    'ceiling':
        0.64,

    'steepness':
        16.0,
}


def get_semantic_calibration_profile():
    profile = (
        SEMANTIC_CALIBRATION_PROFILES.get(
            EMBEDDING_MODEL_ID
        )
        or
        DEFAULT_SEMANTIC_CALIBRATION
    )

    return dict(
        profile
    )

if LLM_PROVIDER not in {
    'local',
    'huggingface',
}:
    raise RuntimeError(
        f'Unsupported LLM_PROVIDER: {LLM_PROVIDER}'
    )

if EMBEDDING_PROVIDER not in {
    'local',
    'huggingface',
}:
    raise RuntimeError(
        'Unsupported EMBEDDING_PROVIDER: '
        f'{EMBEDDING_PROVIDER}'
    )

LLM_PROVIDER_LABEL = {
    'local':
        'LM Studio',

    'huggingface':
        'Hugging Face',
}[LLM_PROVIDER]

if (
    (
        LLM_PROVIDER == 'huggingface'
        or
        EMBEDDING_PROVIDER == 'huggingface'
    )
    and
    not HF_TOKEN
):
    raise RuntimeError(
        'HF_TOKEN is required when using '
        'Hugging Face inference.'
    )

LASTFM_API_KEY = get_setting(
    'LASTFM_API_KEY'
)

LASTFM_SHARED_SECRET = get_setting(
    'LASTFM_SHARED_SECRET'
)

LASTFM_API_URL = (
    'https://ws.audioscrobbler.com/2.0/'
)

YOUTUBE_API_KEY = get_setting(
    'YOUTUBE_API_KEY'
)

YOUTUBE_API_BASE_URL = get_setting(
    'YOUTUBE_API_BASE_URL',
    'https://www.googleapis.com/youtube/v3',
)

CYANITE_ACCESS_TOKEN = get_setting(
    'CYANITE_ACCESS_TOKEN'
)

CYANITE_WEBHOOK_SECRET = get_setting(
    'CYANITE_WEBHOOK_SECRET'
)

CYANITE_API_URL = get_setting(
    'CYANITE_API_URL',
    'https://api.cyanite.ai/graphql',
)

SUPABASE_URL = get_setting(
    'SUPABASE_URL'
)

SUPABASE_SECRET_KEY = (
    get_setting(
        'SUPABASE_SECRET_KEY'
    )
    or
    get_setting(
        'SUPABASE_SERVICE_ROLE_KEY'
    )
)

if not SUPABASE_URL:
    raise RuntimeError(
        'SUPABASE_URL was not found.'
    )

if not SUPABASE_SECRET_KEY:
    raise RuntimeError(
        'SUPABASE_SECRET_KEY was not found.'
    )

supabase_cache_client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)

PULSAR_CACHE_TABLE = (
    'pulsar_analysis_cache'
)

print('==========================================')
print('Syncora backend build:', BUILD_ID)
print('Nova Qwen model:', QWEN_MODEL_ID)
print('Nova embedding model:', EMBEDDING_MODEL_ID)
print('Pulsar resolver:', PULSAR_RESOLVER_BUILD_ID)
print('Pulsar analysis:', PULSAR_ANALYSIS_BUILD_ID)
print('Last.fm API key loaded:', bool(LASTFM_API_KEY))
print('YouTube Data API key loaded:', bool(YOUTUBE_API_KEY))
print('Cyanite access token loaded:', bool(CYANITE_ACCESS_TOKEN))
print('==========================================')
if not LASTFM_API_KEY:
    raise RuntimeError(f'LASTFM_API_KEY could not be read from {ENV_PATH}')
app = FastAPI(title='Syncora Backend', version='0.7.5')


ALLOWED_ORIGINS = [
    origin.strip().rstrip('/')

    for origin
    in get_setting(
        'ALLOWED_ORIGINS',
        (
            'http://localhost:3000,'
            'http://127.0.0.1:3000'
        ),
    ).split(',')

    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

def apply_nova_explicit_constraints(
    profile,
    payload
):
    if not isinstance(
        profile,
        dict,
    ):
        return profile

    adjusted = dict(
        profile
    )

    retrieval_tags = list(
        adjusted.get(
            'retrieval_tags'
        )
        or
        []
    )

    requested_vocal_mode = (
        classify_requested_vocal_mode(
            payload.vocal_style
        )
    )

    if (
        requested_vocal_mode
        ==
        'instrumental'
    ):
        already_present = any(
            normalize_tag(
                tag
            )
            ==
            'instrumental'
            for tag
            in retrieval_tags
        )

        if not already_present:
            if len(
                retrieval_tags
            ) >= 6:
                retrieval_tags[
                    -1
                ] = 'instrumental'

            else:
                retrieval_tags.append(
                    'instrumental'
                )

    adjusted[
        'retrieval_tags'
    ] = clean_string_list(
        retrieval_tags,
        6,
    )

    return adjusted


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            'detail': {
                'error': 'Invalid request body.',
                'message': 'One or more required fields were missing or invalid.',
                'issues': exc.errors(),
                'stage': 'request_validation',
                'retryable': False,
                'build': BUILD_ID,
            }
        },
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print(
        f'[UNHANDLED ERROR] {request.method} {request.url.path}: '
        f'{type(exc).__name__}: {exc}'
    )
    return JSONResponse(
        status_code=500,
        content={
            'detail': {
                'error': 'Internal Syncora backend error.',
                'message': 'An unexpected backend error occurred. Check the backend terminal for details.',
                'stage': 'internal',
                'retryable': True,
                'build': BUILD_ID,
            }
        },
    )

local_ai_client = None

if (
    LLM_PROVIDER == 'local'
    or
    EMBEDDING_PROVIDER == 'local'
):
    local_ai_client = OpenAI(
        base_url=LOCAL_AI_BASE_URL,
        api_key=LOCAL_AI_API_KEY,
        timeout=180.0,
        max_retries=0,
    )


if LLM_PROVIDER == 'huggingface':
    llm_client = OpenAI(
        base_url=HF_ROUTER_BASE_URL,
        api_key=HF_TOKEN,
        timeout=180.0,
        max_retries=0,
    )

else:
    llm_client = local_ai_client


embedding_client = None

if EMBEDDING_PROVIDER == 'huggingface':
    embedding_client = InferenceClient(
        provider=HF_EMBEDDING_INFERENCE_PROVIDER,
        api_key=HF_TOKEN,
    )


def create_llm_completion(**kwargs):
    if LLM_PROVIDER == 'huggingface':
        kwargs[
            'reasoning_effort'
        ] = 'none'

    return (
        llm_client
        .chat
        .completions
        .create(
            **kwargs
        )
    )


def create_embedding_vectors(texts):
    if not isinstance(texts, list) or not texts:
        raise ValueError(
            'Embedding input must be a non-empty list.'
        )

    if EMBEDDING_PROVIDER == 'huggingface':
        result = (
            embedding_client
            .feature_extraction(
                texts,
                model=EMBEDDING_MODEL_ID,
            )
        )

        if hasattr(
            result,
            'tolist'
        ):
            result = result.tolist()

        if (
            len(texts) == 1
            and isinstance(result, list)
            and result
            and isinstance(
                result[0],
                (int, float)
            )
        ):
            result = [
                result
            ]

        if (
            not isinstance(result, list)
            or
            len(result) != len(texts)
        ):
            raise ValueError(
                'Hugging Face returned an unexpected '
                'embedding vector count.'
            )

        return result

    response = (
        local_ai_client
        .embeddings
        .create(
            model=EMBEDDING_MODEL_ID,
            input=texts,
        )
    )

    ordered_data = sorted(
        response.data,
        key=lambda item:
            item.index
    )

    vectors = [
        item.embedding
        for item in ordered_data
    ]

    if len(vectors) != len(texts):
        raise ValueError(
            'Local embedding model returned an '
            'unexpected vector count.'
        )

    return vectors

class NovaRequest(BaseModel):
    project_name: str = Field(min_length=1, max_length=200)
    video_type: str = Field(min_length=1, max_length=200)
    target_duration_seconds: int = Field(gt=0, le=86400)
    mood: str = Field(min_length=1, max_length=200)
    pace: str = Field(min_length=1, max_length=200)
    vocal_style: str = Field(min_length=1, max_length=200)
    structure_preference: str = Field(min_length=1, max_length=300)
    creative_intent: str = Field(default='', max_length=2000)

class PulsarResolveRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    artist: str = Field(min_length=1, max_length=300)
    mbid: str | None = Field(default=None, max_length=100)

class PulsarSignalRequest(BaseModel):
    library_track_id: str = Field(min_length=1, max_length=100)
    # Kept optional for backward compatibility with older clients.
    # Pulsar 0.6 no longer uses user-selected cue density.
    density: str | None = Field(default=None, max_length=20)
    editing_context: str = Field(default='', max_length=2000)
    edit_duration_seconds: int | None = Field(default=None, gt=0, le=86400)
    track_duration_seconds: int | None = Field(default=None, gt=0, le=86400)
PROFILE_CACHE_TTL_SECONDS = 15 * 60
nova_profile_cache = {}

PULSAR_CACHE_VERSION = 1

PULSAR_CACHE_DIR = (
    BACKEND_DIR
    / '.syncora_cache'
)

PULSAR_CACHE_PATH = (
    PULSAR_CACHE_DIR
    / 'pulsar_analysis_cache.json'
)

pulsar_cache_lock = (
    threading.RLock()
)


def create_empty_pulsar_cache():
    return {
        'version':
            PULSAR_CACHE_VERSION,

        'tracks':
            {},
    }


def load_pulsar_analysis_cache():
    """
    Load the old local JSON cache.

    This remains temporarily during the Supabase
    migration so previously-paid Cyanite analyses
    are never lost.
    """

    if not PULSAR_CACHE_PATH.exists():
        return (
            create_empty_pulsar_cache()
        )

    try:
        data = json.loads(
            PULSAR_CACHE_PATH.read_text(
                encoding='utf-8'
            )
        )

    except (
        OSError,
        ValueError,
    ) as error:
        print(
            '[PULSAR LOCAL CACHE] '
            'Could not load cache: '
            f'{error}'
        )

        return (
            create_empty_pulsar_cache()
        )

    if not isinstance(
        data,
        dict,
    ):
        return (
            create_empty_pulsar_cache()
        )

    tracks = data.get(
        'tracks'
    )

    if not isinstance(
        tracks,
        dict,
    ):
        return (
            create_empty_pulsar_cache()
        )

    data['version'] = (
        PULSAR_CACHE_VERSION
    )

    return data


pulsar_analysis_cache = (
    load_pulsar_analysis_cache()
)


def persist_pulsar_analysis_cache():
    """
    Temporary local fallback writer.

    Supabase is now the primary persistent cache,
    but we keep the local copy during migration.
    """

    with pulsar_cache_lock:
        try:
            PULSAR_CACHE_DIR.mkdir(
                parents=True,
                exist_ok=True,
            )

            temporary_path = (
                PULSAR_CACHE_PATH
                .with_suffix(
                    '.tmp'
                )
            )

            temporary_path.write_text(
                json.dumps(
                    pulsar_analysis_cache,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding='utf-8',
            )

            temporary_path.replace(
                PULSAR_CACHE_PATH
            )

            return True

        except OSError as error:
            print(
                '[PULSAR LOCAL CACHE WRITE ERROR] '
                f'{type(error).__name__}: {error}'
            )

            return False


def get_pulsar_cache_primary_artist(
    track
):
    if not isinstance(
        track,
        dict,
    ):
        return None

    artists = track.get(
        'artists'
    )

    if isinstance(
        artists,
        str,
    ):
        return (
            artists.strip()
            or None
        )

    if isinstance(
        artists,
        list,
    ):
        for artist in artists:
            if (
                isinstance(
                    artist,
                    str,
                )
                and
                artist.strip()
            ):
                return (
                    artist.strip()
                )

    return None


def clean_pulsar_cache_payload(
    entry
):
    if not isinstance(
        entry,
        dict,
    ):
        return {}

    return {
        key:
            value

        for (
            key,
            value
        )
        in entry.items()

        if not str(
            key
        ).startswith(
            '_'
        )
    }


def build_supabase_pulsar_cache_row(
    video_id,
    entry
):
    clean_entry = (
        clean_pulsar_cache_payload(
            entry
        )
    )

    track = (
        clean_entry.get(
            'track'
        )
        or
        {}
    )

    return {
        'video_id':
            str(
                video_id
            ),

        'library_track_id':
            (
                str(
                    clean_entry.get(
                        'library_track_id'
                    )
                )
                if clean_entry.get(
                    'library_track_id'
                )
                else None
            ),

        'title':
            track.get(
                'title'
            ),

        'artist':
            get_pulsar_cache_primary_artist(
                track
            ),

        'payload':
            clean_entry,

        'analysis_provider':
            'cyanite',

        'updated_at':
            datetime.now(
                timezone.utc
            ).isoformat(),
    }


def write_pulsar_cache_to_supabase(
    video_id,
    entry
):
    if (
        not video_id
        or
        not isinstance(
            entry,
            dict,
        )
    ):
        return False

    row = (
        build_supabase_pulsar_cache_row(
            video_id,
            entry,
        )
    )

    try:
        (
            supabase_cache_client
            .table(
                PULSAR_CACHE_TABLE
            )
            .upsert(
                row,
                on_conflict='video_id',
            )
            .execute()
        )

        return True

    except Exception as error:
        print(
            '[PULSAR SUPABASE CACHE WRITE ERROR] '
            f'{type(error).__name__}: {error}'
        )

        return False


def parse_supabase_pulsar_cache_row(
    row
):
    if not isinstance(
        row,
        dict,
    ):
        return None

    payload = row.get(
        'payload'
    )

    if not isinstance(
        payload,
        dict,
    ):
        return None

    result = dict(
        payload
    )

    result[
        'video_id'
    ] = str(
        row.get(
            'video_id'
        )
        or
        result.get(
            'video_id'
        )
        or
        ''
    )

    result[
        '_cache_source'
    ] = 'supabase'

    return result


def get_supabase_pulsar_track_by_video_id(
    video_id
):
    if not video_id:
        return None

    try:
        response = (
            supabase_cache_client
            .table(
                PULSAR_CACHE_TABLE
            )
            .select(
                'video_id,library_track_id,payload'
            )
            .eq(
                'video_id',
                str(
                    video_id
                ),
            )
            .execute()
        )

    except Exception as error:
        print(
            '[PULSAR SUPABASE CACHE READ ERROR] '
            f'{type(error).__name__}: {error}'
        )

        return None

    rows = (
        response.data
        if isinstance(
            response.data,
            list,
        )
        else []
    )

    if not rows:
        return None

    return (
        parse_supabase_pulsar_cache_row(
            rows[0]
        )
    )


def get_supabase_pulsar_track_by_library_id(
    library_track_id
):
    if not library_track_id:
        return None

    try:
        response = (
            supabase_cache_client
            .table(
                PULSAR_CACHE_TABLE
            )
            .select(
                'video_id,library_track_id,payload'
            )
            .eq(
                'library_track_id',
                str(
                    library_track_id
                ),
            )
            .execute()
        )

    except Exception as error:
        print(
            '[PULSAR SUPABASE CACHE READ ERROR] '
            f'{type(error).__name__}: {error}'
        )

        return None

    rows = (
        response.data
        if isinstance(
            response.data,
            list,
        )
        else []
    )

    if not rows:
        return None

    return (
        parse_supabase_pulsar_cache_row(
            rows[0]
        )
    )

def get_supabase_pulsar_track_by_title_artist(
    title,
    artist,
):
    if (
        not title
        or
        not artist
    ):
        return None

    try:
        response = (
            supabase_cache_client
            .table(
                PULSAR_CACHE_TABLE
            )
            .select(
                (
                    'video_id,'
                    'library_track_id,'
                    'title,'
                    'artist,'
                    'payload'
                )
            )
            .ilike(
                'title',
                str(
                    title
                ),
            )
            .limit(
                10
            )
            .execute()
        )

    except Exception as error:
        print(
            '[PULSAR SUPABASE CACHE READ ERROR] '
            f'{type(error).__name__}: {error}'
        )

        return None

    rows = (
        response.data
        if isinstance(
            response.data,
            list,
        )
        else []
    )

    desired_title = (
        normalize_ytmusic_text(
            title
        )
    )

    desired_artist = (
        normalize_ytmusic_text(
            artist
        )
    )

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        stored_title = (
            normalize_ytmusic_text(
                row.get(
                    'title'
                )
            )
        )

        stored_artist = (
            normalize_ytmusic_text(
                row.get(
                    'artist'
                )
            )
        )

        if (
            stored_title
            !=
            desired_title
        ):
            continue

        if (
            stored_artist
            !=
            desired_artist
        ):
            continue

        return (
            parse_supabase_pulsar_cache_row(
                row
            )
        )

    return None

def get_local_pulsar_track_by_video_id(
    video_id
):
    if not video_id:
        return None

    with pulsar_cache_lock:
        entry = (
            pulsar_analysis_cache
            .get(
                'tracks',
                {},
            )
            .get(
                str(
                    video_id
                )
            )
        )

        if not isinstance(
            entry,
            dict,
        ):
            return None

        result = dict(
            entry
        )

        result[
            'video_id'
        ] = str(
            video_id
        )

        result[
            '_cache_source'
        ] = 'local_disk'

        return result


def get_local_pulsar_track_by_library_id(
    library_track_id
):
    if not library_track_id:
        return None

    target_id = str(
        library_track_id
    )

    with pulsar_cache_lock:
        tracks = (
            pulsar_analysis_cache
            .get(
                'tracks',
                {},
            )
        )

        for (
            video_id,
            entry,
        ) in tracks.items():
            if not isinstance(
                entry,
                dict,
            ):
                continue

            stored_library_id = (
                entry.get(
                    'library_track_id'
                )
            )

            if (
                str(
                    stored_library_id
                    or
                    ''
                )
                !=
                target_id
            ):
                continue

            result = dict(
                entry
            )

            result[
                'video_id'
            ] = str(
                video_id
            )

            result[
                '_cache_source'
            ] = 'local_disk'

            return result

    return None


def get_cached_pulsar_track_by_video_id(
    video_id
):
    """
    Supabase first, old local JSON second.
    """

    cached_entry = (
        get_supabase_pulsar_track_by_video_id(
            video_id
        )
    )

    if cached_entry:
        return cached_entry

    return (
        get_local_pulsar_track_by_video_id(
            video_id
        )
    )


def get_cached_pulsar_track_by_library_id(
    library_track_id
):
    """
    Supabase first, old local JSON second.
    """

    cached_entry = (
        get_supabase_pulsar_track_by_library_id(
            library_track_id
        )
    )

    if cached_entry:
        return cached_entry

    return (
        get_local_pulsar_track_by_library_id(
            library_track_id
        )
    )

def get_cached_pulsar_track_by_title_artist(
    title,
    artist,
):
    cached_entry = (
        get_supabase_pulsar_track_by_title_artist(
            title,
            artist,
        )
    )

    if cached_entry:
        return cached_entry

    desired_title = (
        normalize_ytmusic_text(
            title
        )
    )

    desired_artist = (
        normalize_ytmusic_text(
            artist
        )
    )

    with pulsar_cache_lock:
        tracks = (
            pulsar_analysis_cache
            .get(
                'tracks',
                {},
            )
        )

        for (
            video_id,
            entry,
        ) in tracks.items():
            if not isinstance(
                entry,
                dict,
            ):
                continue

            track = (
                entry.get(
                    'track'
                )
                or
                {}
            )

            stored_title = (
                normalize_ytmusic_text(
                    track.get(
                        'title'
                    )
                )
            )

            artists = (
                track.get(
                    'artists'
                )
                or
                []
            )

            if isinstance(
                artists,
                str,
            ):
                artists = [
                    artists
                ]

            stored_artists = [
                normalize_ytmusic_text(
                    item
                )
                for item
                in artists
                if item
            ]

            if (
                stored_title
                !=
                desired_title
            ):
                continue

            if (
                desired_artist
                not in
                stored_artists
            ):
                continue

            result = dict(
                entry
            )

            result[
                'video_id'
            ] = str(
                video_id
            )

            result[
                '_cache_source'
            ] = 'local_disk'

            return result

    return None

def cache_pulsar_resolution(
    video_id,
    library_track_id,
    track,
):
    if (
        not video_id
        or
        not library_track_id
    ):
        return

    video_id = str(
        video_id
    )

    with pulsar_cache_lock:
        tracks = (
            pulsar_analysis_cache
            .setdefault(
                'tracks',
                {},
            )
        )

        entry = tracks.setdefault(
            video_id,
            {},
        )

        entry[
            'library_track_id'
        ] = str(
            library_track_id
        )

        entry[
            'track'
        ] = (
            dict(
                track
            )
            if isinstance(
                track,
                dict,
            )
            else {}
        )

        entry[
            'updated_at'
        ] = time.time()

        snapshot = dict(
            entry
        )

        persist_pulsar_analysis_cache()

    write_pulsar_cache_to_supabase(
        video_id,
        snapshot,
    )


def cache_pulsar_finished_analysis(
    library_track_id,
    analysis=None,
    segments_response=None,
):
    cached_entry = (
        get_cached_pulsar_track_by_library_id(
            library_track_id
        )
    )

    if not cached_entry:
        return

    video_id = (
        cached_entry.get(
            'video_id'
        )
    )

    if not video_id:
        return

    video_id = str(
        video_id
    )

    with pulsar_cache_lock:
        tracks = (
            pulsar_analysis_cache
            .setdefault(
                'tracks',
                {},
            )
        )

        entry = tracks.setdefault(
            video_id,
            clean_pulsar_cache_payload(
                cached_entry
            ),
        )

        if (
            not entry.get(
                'library_track_id'
            )
        ):
            entry[
                'library_track_id'
            ] = str(
                library_track_id
            )

        if isinstance(
            analysis,
            dict,
        ):
            existing_analysis = (
                entry.get(
                    'analysis'
                )
            )

            if not isinstance(
                existing_analysis,
                dict,
            ):
                existing_analysis = {}

            for (
                key,
                value,
            ) in analysis.items():
                if (
                    value is not None
                    and
                    value != ''
                ):
                    existing_analysis[
                        key
                    ] = value

            entry[
                'analysis'
            ] = existing_analysis

        if isinstance(
            segments_response,
            dict,
        ):
            entry[
                'segments_response'
            ] = (
                segments_response
            )

        entry[
            'updated_at'
        ] = time.time()

        snapshot = dict(
            entry
        )

        persist_pulsar_analysis_cache()

    write_pulsar_cache_to_supabase(
        video_id,
        snapshot,
    )


def migrate_local_pulsar_cache_to_supabase():
    """
    One-time migration helper.

    Copies existing local JSON cache entries into
    Supabase without contacting Cyanite.
    """

    with pulsar_cache_lock:
        tracks = dict(
            pulsar_analysis_cache.get(
                'tracks',
                {},
            )
        )

    migrated = 0
    failed = 0
    skipped = 0

    for (
        video_id,
        entry,
    ) in tracks.items():
        if not isinstance(
            entry,
            dict,
        ):
            skipped += 1
            continue

        success = (
            write_pulsar_cache_to_supabase(
                video_id,
                entry,
            )
        )

        if success:
            migrated += 1

        else:
            failed += 1

    return {
        'total_local_entries':
            len(
                tracks
            ),

        'migrated':
            migrated,

        'failed':
            failed,

        'skipped':
            skipped,
    }

def get_payload_cache_key(payload: NovaRequest):
    serialized = json.dumps(payload.model_dump(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

def cache_nova_profile(payload: NovaRequest, profile):
    key = get_payload_cache_key(payload)
    nova_profile_cache[key] = {'profile': profile, 'expires_at': time.time() + PROFILE_CACHE_TTL_SECONDS}

def get_cached_nova_profile(payload: NovaRequest):
    key = get_payload_cache_key(payload)
    cached = nova_profile_cache.get(key)
    if not cached:
        return None
    if time.time() >= cached['expires_at']:
        nova_profile_cache.pop(key, None)
        return None
    profile = cached.get('profile')
    if not isinstance(profile, dict):
        nova_profile_cache.pop(key, None)
        return None
    if 'retrieval_tags' not in profile or 'semantic_traits' not in profile:
        nova_profile_cache.pop(key, None)
        return None
    return profile

def clean_string_list(values, limit):
    if not isinstance(values, list):
        return []
    cleaned = []
    for value in values:
        if not isinstance(value, str):
            continue
        value = value.strip()
        if not value:
            continue
        if value.casefold() in [existing.casefold() for existing in cleaned]:
            continue
        cleaned.append(value)
        if len(cleaned) >= limit:
            break
    return cleaned

def safe_array_value(values, index):
    if not isinstance(values, list):
        return None
    if index < 0 or index >= len(values):
        return None
    return values[index]

def extract_segment_category(category_data, index):
    if not isinstance(category_data, dict):
        return {}
    result = {}
    for key, values in category_data.items():
        value = safe_array_value(values, index)
        if value is None:
            continue
        result[key] = value
    return result

def strongest_segment_label(category_data):
    if not isinstance(category_data, dict):
        return None
    usable = [(key, value) for key, value in category_data.items() if isinstance(value, (int, float))]
    if not usable:
        return None
    key, value = max(usable, key=lambda item: item[1])
    return {'label': key, 'score': value}

def numeric_change_amount(previous_value, current_value):
    if not isinstance(previous_value, (int, float)) or not isinstance(current_value, (int, float)):
        return 0.0
    return min(1.0, abs(float(current_value) - float(previous_value)))

def signed_numeric_change(previous_value, current_value):
    if not isinstance(previous_value, (int, float)) or not isinstance(current_value, (int, float)):
        return 0.0
    return float(current_value) - float(previous_value)

def category_change_distance(previous_values, current_values):
    if not isinstance(previous_values, dict):
        previous_values = {}
    if not isinstance(current_values, dict):
        current_values = {}
    keys = set(previous_values.keys()) | set(current_values.keys())
    deltas = []
    for key in keys:
        previous_value = previous_values.get(key)
        current_value = current_values.get(key)
        if not isinstance(previous_value, (int, float)) or not isinstance(current_value, (int, float)):
            continue
        deltas.append(min(1.0, abs(float(current_value) - float(previous_value))))
    if not deltas:
        return 0.0
    mean_delta = sum(deltas) / len(deltas)
    max_delta = max(deltas)
    return mean_delta * 0.65 + max_delta * 0.35

def dominant_label(segment, field_name):
    value = segment.get(field_name)
    if not isinstance(value, dict):
        return None
    label = value.get('label')
    if isinstance(label, str) and label:
        return label
    return None

def build_dominant_transitions(previous_segment, current_segment):
    field_map = {'mood': 'dominant_mood', 'voice': 'dominant_voice', 'instrument': 'dominant_instrument', 'movement': 'dominant_movement', 'character': 'dominant_character'}
    transitions = {}
    for output_name, field_name in field_map.items():
        before = dominant_label(previous_segment, field_name)
        after = dominant_label(current_segment, field_name)
        if before and after and (before != after):
            transitions[output_name] = {'from': before, 'to': after}
    return transitions

def calculate_pulsar_segment_change(previous_segment, current_segment):
    previous_raw = previous_segment.get('raw') or {}
    current_raw = current_segment.get('raw') or {}
    arousal_change = numeric_change_amount(previous_segment.get('arousal'), current_segment.get('arousal'))
    valence_change = numeric_change_amount(previous_segment.get('valence'), current_segment.get('valence'))
    mood_change = category_change_distance(previous_raw.get('mood'), current_raw.get('mood'))
    voice_change = category_change_distance(previous_raw.get('voice'), current_raw.get('voice'))
    instrument_change = category_change_distance(previous_raw.get('instruments'), current_raw.get('instruments'))
    movement_change = category_change_distance(previous_raw.get('movement'), current_raw.get('movement'))
    character_change = category_change_distance(previous_raw.get('character'), current_raw.get('character'))
    weights = {'arousal': 0.18, 'valence': 0.18, 'mood': 0.18, 'voice': 0.04, 'instruments': 0.2, 'movement': 0.12, 'character': 0.1}
    base_change_score = arousal_change * weights['arousal'] + valence_change * weights['valence'] + mood_change * weights['mood'] + voice_change * weights['voice'] + instrument_change * weights['instruments'] + movement_change * weights['movement'] + character_change * weights['character']
    dominant_transitions = build_dominant_transitions(previous_segment, current_segment)
    transition_bonus_weights = {'instrument': 0.035, 'movement': 0.025, 'mood': 0.025, 'voice': 0.025, 'character': 0.015}
    transition_bonus = sum((transition_bonus_weights.get(transition_type, 0.0) for transition_type in dominant_transitions.keys()))
    raw_score = base_change_score + transition_bonus
    return {'raw_change_score': raw_score, 'base_change_score': base_change_score, 'transition_bonus': transition_bonus, 'component_change': {'arousal': round(arousal_change, 4), 'valence': round(valence_change, 4), 'mood': round(mood_change, 4), 'voice': round(voice_change, 4), 'instruments': round(instrument_change, 4), 'movement': round(movement_change, 4), 'character': round(character_change, 4)}, 'signed_change': {'arousal': round(signed_numeric_change(previous_segment.get('arousal'), current_segment.get('arousal')), 4), 'valence': round(signed_numeric_change(previous_segment.get('valence'), current_segment.get('valence')), 4)}, 'dominant_transitions': dominant_transitions, 'weights': weights, 'transition_bonus_weights': transition_bonus_weights}

def parse_nova_json(raw: str):
    if raw is None or not raw.strip():
        raise HTTPException(status_code=502, detail={'error': 'Nova received an empty Qwen response.', 'stage': 'nova_qwen_validation', 'retryable': True, 'build': BUILD_ID})
    cleaned = raw.strip()
    if cleaned.startswith('```json'):
        cleaned = cleaned[7:]
    elif cleaned.startswith('```'):
        cleaned = cleaned[3:]
    if cleaned.endswith('```'):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    first_brace = cleaned.find('{')
    last_brace = cleaned.rfind('}')
    if first_brace != -1 and last_brace != -1:
        cleaned = cleaned[first_brace:last_brace + 1]
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=502, detail={'error': 'Qwen returned invalid JSON.', 'stage': 'nova_qwen_validation', 'retryable': True, 'json_error': str(error), 'raw_response': raw[:1000], 'build': BUILD_ID})
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail={'error': 'Qwen returned JSON, but the top-level value was not an object.', 'stage': 'nova_qwen_validation', 'retryable': True, 'build': BUILD_ID})
    return parsed

def parse_pulsar_json(raw: str):
    if raw is None or not raw.strip():
        raise HTTPException(status_code=502, detail={'error': 'Pulsar received an empty Qwen response.', 'stage': 'pulsar_qwen_validation', 'retryable': True, 'analysis_preserved': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
    cleaned = raw.strip()
    if cleaned.startswith('```json'):
        cleaned = cleaned[7:]
    elif cleaned.startswith('```'):
        cleaned = cleaned[3:]
    if cleaned.endswith('```'):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    first_brace = cleaned.find('{')
    last_brace = cleaned.rfind('}')
    if first_brace != -1 and last_brace != -1:
        cleaned = cleaned[first_brace:last_brace + 1]
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=502, detail={'error': 'Qwen returned invalid Pulsar Signal JSON.', 'stage': 'pulsar_qwen_validation', 'retryable': True, 'analysis_preserved': True, 'json_error': str(error), 'raw_response': raw[:1500], 'build': PULSAR_ANALYSIS_BUILD_ID})
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail={'error': "Qwen's Pulsar response was not a JSON object.", 'stage': 'pulsar_qwen_validation', 'retryable': True, 'analysis_preserved': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
    return parsed

def create_pulsar_signal_with_qwen(title, analysis, keypoints, editing_context, edit_window=None):
    objective_payload = {'track_title': title, 'whole_track_analysis': analysis, 'editing_context': editing_context, 'edit_window': edit_window or {}, 'keypoints': [{'timestamp_seconds': keypoint.get('timestamp'), 'priority': keypoint.get('tier'), 'change_score': keypoint.get('change_score'), 'component_change': keypoint.get('component_change'), 'signed_change': keypoint.get('signed_change'), 'dominant_transitions': keypoint.get('dominant_transitions')} for keypoint in keypoints]}
    prompt = f"""\nYou are Pulsar, Syncora's music-to-edit interpretation\nassistant for video editors.\n\nYou are NOT analyzing audio yourself.\n\nObjective audio analysis has already been performed by\nCyanite, and deterministic Python code has already chosen\nthe important musical timestamps.\n\nYour ONLY job is to translate those objective moments\ninto useful editing suggestions.\n\n\nCRITICAL RULES:\n\n- Use every supplied keypoint exactly once.\n- Keep the keypoints in the exact supplied order.\n- Do not add timestamps.\n- Do not remove timestamps.\n- Do not move timestamps.\n- timestamp_seconds must exactly match the supplied value.\n- Never invent a beat drop, chorus, verse, bridge,\n  vocal entrance, drum hit, instrument entrance,\n  instrument exit, or other musical event that the\n  objective evidence does not establish.\n- A dominant instrument transition means the classifier\n  changed which instrument was most prominent in the\n  segment. It does NOT prove that the new instrument\n  literally entered at that timestamp.\n- Describe dominant instrument transitions using language\n  such as "becomes more prominent", "takes prominence",\n  "the texture shifts toward", or "becomes dominant".\n- Never say an instrument "enters", "drops out",\n  "starts", "stops", or "intensifies" unless the\n  objective data explicitly establishes that fact.\n- Do not claim millisecond or beat-level precision.\n- Treat each timestamp as an approximate musical\n  transition region identified from Cyanite's\n  segment-level analysis.\n- The Signal may cover only a selected excerpt of the\n  full song. When edit_window.uses_excerpt is true,\n  treat edit_window.start_seconds through\n  edit_window.end_seconds as the recommended source\n  region for the edit. Do not assume the edit begins\n  at 0:00. Cue timestamps remain absolute song times.\n- edit_window is authoritative for the duration and
  source position of the edit.
- Never require the editor to restate the intended edit
  length inside editing_context.
- Never require the editor to say that later portions of
  the song may be used.
- editing_context is creative direction only. It may
  describe visual style, pacing, atmosphere, subject
  matter, narrative intention, editing preferences, or
  other creative goals.
- If editing_context contains no timing instructions,
  never interpret that as a request to begin at 0:00 or
  use the entire song.
- Base suggestions on the actual changes provided.
- - change_score measures the relative magnitude or
  salience of a transition within the selected edit
  window. It does NOT measure energy, loudness,
  intensity, arousal, or whether the song is at a peak.
- Never describe a high change_score as "peak energy",
  "maximum energy", "highest intensity", or similar.
- Use signed_change.arousal when describing the
  direction of an energy/arousal change:
  positive means arousal increased,
  negative means arousal decreased.
- Use signed_change.valence only to describe the
  direction of a valence change:
  positive means valence increased,
  negative means valence decreased.
- component_change values describe the magnitude of
  change in each category, not its direction.
  Never infer "increased" or "decreased" from a
  component_change value alone.
- dominant_transitions describe classifier prominence
  changes. They do not establish overall energy level.
- Do not claim that a timestamp is an absolute musical
  peak unless the supplied objective data explicitly
  establishes that fact.\n- Editing suggestions may include cuts, transitions,\n  speed changes, visual emphasis, shot changes,\n  motion changes, overlays, or similar editing ideas.\n- Suggestions should be practical rather than flowery.\n- Different cues should not all recommend the same edit.\n- If the evidence is subtle, say so rather than\n  exaggerating it.\n- Do not mention Cyanite, Qwen, Python, APIs, models,\n  classifiers, or internal scoring to the user.\n- Return valid JSON only.\n- Do not use Markdown.\n- Do not use code fences.\n\n\nReturn exactly this structure:\n\n{{\n    "signal_summary":\n        "One concise sentence describing how the track develops for editing.",\n\n    "cues": [\n        {{\n            "timestamp_seconds": 0,\n            "title":\n                "Short editor-facing cue title",\n            "suggestion":\n                "One or two concise sentences describing an editing opportunity.",\n            "evidence":\n                "A concise plain-language description of the musical change supporting the suggestion."\n        }}\n    ]\n}}\n\n\nOBJECTIVE PULSAR DATA\n\n{json.dumps(objective_payload, ensure_ascii=False, indent=2)}\n"""
    try:
        completion = create_llm_completion(model=QWEN_MODEL_ID,     messages=[
        {
            'role': 'system',
            'content': (
                "You are Pulsar, Syncora's music-to-edit interpretation assistant. "
                "Translate supplied objective musical changes into concise, "
                "practical editing opportunities without inventing musical "
                "events or changing timestamps. Return valid JSON only."
            )
        },
        {
            'role': 'user',
            'content': prompt
        }
    ], temperature=0.2, top_p=0.8, max_tokens=3200)


    except Exception as error:
        error_name = (
            type(error).__name__
        )

        error_text = str(
            error
        )

        error_text_lower = (
            error_text.casefold()
        )

        print(
            '[PULSAR AI ERROR] '
            f'provider={LLM_PROVIDER} '
            f'{error_name}: {error_text}'
        )

        if (
            'Timeout' in error_name
            or
            'timeout' in error_text_lower
        ):
            provider_message = (
                (
                    'Hugging Face inference did not finish '
                    'the Signal within the configured timeout.'
                )
                if LLM_PROVIDER == 'huggingface'
                else
                (
                    'The local AI model did not finish '
                    'the Signal within the configured timeout.'
                )
            )

            raise HTTPException(
                status_code=504,
                detail={
                    'error':
                        (
                            "Pulsar's AI interpretation "
                            "timed out."
                        ),

                    'message':
                        provider_message,

                    'stage':
                        'pulsar_qwen_signal',

                    'retryable':
                        True,

                    'analysis_preserved':
                        True,

                    'provider':
                        LLM_PROVIDER,

                    'model':
                        QWEN_MODEL_ID,

                    'build':
                        PULSAR_ANALYSIS_BUILD_ID,
                }
            )

        mlx_crash_markers = [
            'fatal exception in the backend scheduler',
            'broadcast_shapes',
            'mlx_engine',
            'mlx_lm',
        ]

        if (
            LLM_PROVIDER == 'local'
            and
            any(
                marker in error_text_lower
                for marker in mlx_crash_markers
            )
        ):
            raise HTTPException(
                status_code=502,
                detail={
                    'error':
                        (
                            "LM Studio's MLX inference "
                            "backend crashed."
                        ),

                    'message':
                        (
                            'The audio analysis is safe and cached. '
                            'Reload the Qwen model or restart the '
                            'LM Studio server, then try generating '
                            'the Signal again.'
                        ),

                    'stage':
                        'pulsar_qwen_backend_crash',

                    'retryable':
                        True,

                    'analysis_preserved':
                        True,

                    'provider':
                        LLM_PROVIDER,

                    'model':
                        QWEN_MODEL_ID,

                    'build':
                        PULSAR_ANALYSIS_BUILD_ID,
                }
            )

        provider_message = (
            (
                'The cloud AI provider could not complete '
                'the Signal interpretation. Try again in '
                'a moment.'
            )
            if LLM_PROVIDER == 'huggingface'
            else
            (
                'The local AI model could not complete '
                'the Signal interpretation. Make sure '
                'LM Studio and the Qwen model are running.'
            )
        )

        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    (
                        'Pulsar could not complete '
                        'AI interpretation.'
                    ),

                'message':
                    provider_message,

                'stage':
                    'pulsar_qwen_signal',

                'retryable':
                    True,

                'analysis_preserved':
                    True,

                'provider':
                    LLM_PROVIDER,

                'model':
                    QWEN_MODEL_ID,

                'build':
                    PULSAR_ANALYSIS_BUILD_ID,
            }
        )
    
    if not completion.choices:
        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    (
                        f'{LLM_PROVIDER_LABEL} returned '
                        'zero Pulsar choices.'
                    ),

                'stage':
                    'pulsar_qwen_validation',

                'retryable':
                    True,

                'analysis_preserved':
                    True,

                'provider':
                    LLM_PROVIDER,

                'model':
                    QWEN_MODEL_ID,

                'build':
                    PULSAR_ANALYSIS_BUILD_ID,
            }
        )

    raw = completion.choices[0].message.content
    parsed = parse_pulsar_json(raw)
    signal_summary = parsed.get('signal_summary')
    cues = parsed.get('cues')
    if not isinstance(signal_summary, str) or not signal_summary.strip():
        raise HTTPException(status_code=502, detail={'error': 'Qwen did not provide a usable Signal summary.', 'stage': 'pulsar_qwen_validation', 'retryable': True, 'analysis_preserved': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
    if not isinstance(cues, list):
        raise HTTPException(status_code=502, detail={'error': 'Qwen did not return a Pulsar cue list.', 'stage': 'pulsar_qwen_validation', 'retryable': True, 'analysis_preserved': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
    if len(cues) != len(keypoints):
        raise HTTPException(status_code=502, detail={'error': 'Qwen changed the number of Pulsar keypoints.', 'expected_cue_count': len(keypoints), 'received_cue_count': len(cues), 'stage': 'pulsar_qwen_validation', 'retryable': True, 'analysis_preserved': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
    validated_cues = []
    for index, (keypoint, cue) in enumerate(zip(keypoints, cues)):
        if not isinstance(cue, dict):
            raise HTTPException(status_code=502, detail={'error': 'Qwen returned an invalid Pulsar cue.', 'cue_index': index, 'stage': 'pulsar_qwen_validation', 'retryable': True, 'analysis_preserved': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
        objective_timestamp = keypoint.get('timestamp')
        qwen_timestamp = cue.get('timestamp_seconds')
        if qwen_timestamp != objective_timestamp:
            raise HTTPException(status_code=502, detail={'error': 'Qwen attempted to change a Pulsar timestamp.', 'cue_index': index, 'expected_timestamp': objective_timestamp, 'received_timestamp': qwen_timestamp, 'stage': 'pulsar_qwen_validation', 'retryable': True, 'analysis_preserved': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
        title_text = cue.get('title')
        suggestion_text = cue.get('suggestion')
        evidence_text = cue.get('evidence')
        if not isinstance(title_text, str) or not title_text.strip() or (not isinstance(suggestion_text, str)) or (not suggestion_text.strip()) or (not isinstance(evidence_text, str)) or (not evidence_text.strip()):
            raise HTTPException(status_code=502, detail={'error': 'Qwen returned an incomplete Pulsar cue.', 'cue_index': index, 'stage': 'pulsar_qwen_validation', 'retryable': True, 'analysis_preserved': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
        validated_cues.append({'cue_number': index + 1, 'timestamp_seconds': objective_timestamp, 'priority': keypoint.get('tier') or classify_pulsar_keypoint_tier(keypoint.get('change_score')), 'title': title_text.strip(), 'suggestion': suggestion_text.strip(), 'evidence': evidence_text.strip(), 'objective': {'tier': keypoint.get('tier') or classify_pulsar_keypoint_tier(keypoint.get('change_score')), 'change_score': keypoint.get('change_score'), 'component_change': keypoint.get('component_change'), 'signed_change': keypoint.get('signed_change'), 'dominant_transitions': keypoint.get('dominant_transitions')}})
    return {'signal_summary': signal_summary.strip(), 'cues': validated_cues}

def create_nova_profile(payload: NovaRequest):
    prompt = f"""
    You are Nova, the music-discovery intelligence inside
    Syncora, a tool for video editors.

    Your job is to translate an editor's creative brief into
    a musically coherent retrieval profile.

    You must carefully separate:

    1. SEARCHABLE MUSICAL IDENTITY
    2. DESCRIPTIVE SOUND / CREATIVE INTENT

    These are related, but they are NOT interchangeable.


    =======================================================
    1. RETRIEVAL TAGS
    =======================================================

    Produce exactly 6 established music tags suitable for
    searching Last.fm.

    Retrieval tags determine which musical neighborhood
    Nova searches, so precision matters.

    TAG COMPOSITION:

    - Exactly 4 or 5 of the 6 tags should be genres,
    subgenres, or established musical styles.
    - At most 1 or 2 tags may be broader established
    musical mood, texture, or energy tags.
    - Order tags from strongest and most specific to
    broader supporting tags.

    ANCHOR-FAMILY RULE:

    - Before choosing the six tags, silently determine the
    single strongest musical family suggested by the
    brief.
    - The first 3 retrieval tags must establish that
    musical family.
    - Tags 4 through 6 must either:
        a) belong to that same family,
        b) be a clearly adjacent style, or
        c) be a broader umbrella/tag that plausibly
        contains or describes the first three.
    - Do NOT use the final tags to introduce an unrelated
    second musical family merely because it matches the
    project's visual aesthetic.
    - If two musical families are both plausible but the
    brief does not explicitly request contrast, choose
    the better-supported family and stay within it.

    Examples:

    COHERENT:
    minimal techno
    deep house
    tech house
    electronic
    house
    downtempo

    COHERENT:
    synthwave
    chillwave
    dream pop
    electronic
    atmospheric
    downtempo

    COHERENT:
    indie folk
    singer-songwriter
    acoustic
    folk
    slowcore
    melancholic

    INCOHERENT:
    minimal techno
    deep house
    progressive house
    electronic
    modern classical
    ambient

    INCOHERENT:
    industrial
    breakcore
    drum and bass
    electronic
    indie folk
    dream pop

    The incoherent examples fail because the final tags
    introduce a substantially different musical family
    without explicit evidence that the editor wants a
    cross-genre or contrasting soundtrack.

    EVIDENCE RULES:

    - Prefer information that describes the MUSIC itself:
    mood, pace, vocals, structure, instrumentation,
    rhythm, energy, texture, or explicitly requested genre.
    - Treat video type and project subject as CONTEXT, not
    direct genre evidence.
    - Creative visual language may influence the desired
    sound, but it must not automatically become a genre.
    - Do not infer a niche genre merely because its cultural
    associations match the visuals.
    - Do not over-specialize when the brief does not provide
    enough musical evidence. Prefer a broader credible
    style over an unsupported niche subgenre.

    Examples of INVALID reasoning:

    "luxury" -> modern classical
    "premium" -> ambient
    "cars" -> synthwave
    "motorsport" -> industrial
    "cinematic video" -> cinematic music
    "nighttime" -> darkwave

    Those genres MAY still be correct, but only when other
    musical evidence in the brief supports them.

    Examples of VALID musical evidence:

    dreamy + electronic texture + smooth rhythm
        -> dream pop / chillwave / synthwave may be plausible

    fast + aggressive + heavily rhythmic + instrumental
        -> drum and bass / industrial / breakcore may be plausible

    soft + intimate vocals + acoustic texture + slow build
        -> indie folk / singer-songwriter / acoustic may be plausible

    Before returning the final JSON, silently validate the six retrieval tags as a SET:

    1. Do the first three establish a recognizable musical
    family?
    2. Can every remaining tag be reasonably connected to
    that family?
    3. Did any tag enter only because of the visual subject,
    luxury level, setting, editing style, or aesthetic?
    4. Would searching all six tags retrieve substantially
    overlapping kinds of music rather than unrelated
    catalogs?

    If one tag breaks the musical neighborhood, remove it
    and replace it with a more coherent adjacent or broader
    music tag before returning the JSON.

    Then validate each tag individually:

    - Does it describe music rather than the video?
    - Is it a useful established Last.fm search concept?
    - Is there musical evidence for it?
    - Is it coherent with the anchor family?

    If the answer to #1 or #3 is no, move that idea into
    semantic_traits instead.

    DO NOT use:

    - invented aesthetic phrases
    - project subjects
    - editing terminology
    - camera terminology
    - visual styles presented as music genres
    - extremely niche genres unsupported by the brief

    Bad retrieval tags:

    "neon ambiance"
    "night drive music"
    "luxury soundtrack"
    "cinematic car edit"
    "premium atmosphere"
    "city lights soundtrack"

    Good retrieval tags can include established terms such as:

    synthwave
    dream pop
    chillwave
    electropop
    darkwave
    shoegaze
    downtempo
    indie pop
    indie folk
    deep house
    tech house
    drum and bass
    industrial
    electronic
    alternative
    acoustic
    atmospheric

    Do NOT copy these examples unless they actually fit the
    editor's brief.


    =======================================================
    2. SEMANTIC TRAITS
    =======================================================

    Produce exactly 4 short descriptive qualities describing
    the desired SOUND and musical development.

    These are used for semantic embedding similarity and are
    NOT sent to Last.fm as retrieval searches.

    Semantic traits are the correct place for aesthetic,
    emotional, textural, cinematic, visual-adjacent, and
    movement-oriented ideas.

    They may describe:

    - atmosphere
    - sonic texture
    - perceived polish
    - emotional character
    - rhythmic feel
    - momentum
    - restraint
    - intensity
    - build
    - payoff
    - vocal character
    - sense of space
    - elegance or roughness

    Examples:

    "neon nighttime atmosphere"
    "dreamy electronic texture"
    "gradual energetic build"
    "soft emotional vocals"
    "restrained upscale polish"
    "precise rhythmic movement"

    Keep each trait concise.


    =======================================================
    INPUT PRIORITY
    =======================================================

    When fields appear to conflict, use this priority:

    1. Explicit musical requirements in creative intent
    2. Mood
    3. Pace
    4. Vocal preference
    5. Structure preference
    6. Video type
    7. Project name

    Video type and project name provide situational context
    but must NEVER be the sole justification for a genre.


    =======================================================
    GENERAL RULES
    =======================================================

    - Return valid JSON only.
    - Do not use Markdown.
    - Do not use code fences.
    - Do not recommend songs.
    - Do not recommend artists.
    - Do not explain your reasoning.
    - Do not output your internal checks.
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

        "summary":
            "one short sentence describing the desired music",

        "energy":
            "one short description",

        "vocal_preference":
            "one short description"
    }}

    EDITOR BRIEF

    Project name:
    {payload.project_name}

    Video type:
    {payload.video_type}

    Target duration:
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
        completion = create_llm_completion(model=QWEN_MODEL_ID, messages=[{'role': 'system', 'content': "You are Nova, Syncora's music-discovery assistant. "
            "Translate creative briefs into one coherent musical "
            "retrieval neighborhood for Last.fm. The first three "
            "retrieval tags establish an anchor musical family; "
            "remaining tags must stay within, adjacent to, or "
            "broaden that family unless the editor explicitly "
            "requests stylistic contrast. Keep visual and "
            "aesthetic concepts in semantic traits unless they "
            "have independent musical support. Return concise "
            "valid JSON only."},
        {'role': 'user', 'content': prompt}], temperature=0.25, top_p=0.8, max_tokens=400)
    except Exception as error:
        error_name = (
            type(error).__name__
        )

        error_text = str(
            error
        )

        error_text_lower = (
            error_text.casefold()
        )

        print(
            '[NOVA AI ERROR] '
            f'provider={LLM_PROVIDER} '
            f'{error_name}: {error_text}'
        )

        if (
            'Timeout' in error_name
            or
            'timeout' in error_text_lower
        ):
            provider_message = (
                (
                    'Hugging Face inference did not finish '
                    'the Nova profile within the configured '
                    'timeout.'
                )
                if LLM_PROVIDER == 'huggingface'
                else
                (
                    'LM Studio did not complete the Nova '
                    'profile within the configured timeout.'
                )
            )

            raise HTTPException(
                status_code=504,
                detail={
                    'error':
                        (
                            "Nova's AI profile generation "
                            "timed out."
                        ),

                    'message':
                        provider_message,

                    'stage':
                        'qwen_profile',

                    'retryable':
                        True,

                    'provider':
                        LLM_PROVIDER,

                    'model':
                        QWEN_MODEL_ID,

                    'build':
                        BUILD_ID,
                }
            )

        provider_message = (
            (
                'The cloud AI provider could not complete '
                'Nova profile generation. Try again in a '
                'moment.'
            )
            if LLM_PROVIDER == 'huggingface'
            else
            (
                'The local AI model could not complete '
                'Nova profile generation. Make sure '
                'LM Studio and the Nova model are running.'
            )
        )

        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    (
                        'Nova could not complete '
                        'AI profile generation.'
                    ),

                'message':
                    provider_message,

                'stage':
                    'qwen_profile',

                'retryable':
                    True,

                'provider':
                    LLM_PROVIDER,

                'model':
                    QWEN_MODEL_ID,

                'build':
                    BUILD_ID,
            }
        )

    if not completion.choices:
        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    (
                        f'{LLM_PROVIDER_LABEL} returned '
                        'zero Nova choices.'
                    ),

                'stage':
                    'nova_qwen_validation',

                'retryable':
                    True,

                'provider':
                    LLM_PROVIDER,

                'model':
                    QWEN_MODEL_ID,

                'build':
                    BUILD_ID,
            }
        )

    if not completion.choices:
        raise HTTPException(status_code=502, detail={'error': 'LM Studio returned zero Qwen choices.', 'stage': 'nova_qwen_validation', 'retryable': True, 'model': QWEN_MODEL_ID, 'build': BUILD_ID})
    raw = completion.choices[0].message.content
    profile = parse_nova_json(raw)
    retrieval_tags = clean_string_list(profile.get('retrieval_tags', []), limit=6)
    semantic_traits = clean_string_list(profile.get('semantic_traits', []), limit=4)
    if len(retrieval_tags) < 4:
        raise HTTPException(status_code=502, detail={'error': 'Qwen generated fewer than four usable retrieval tags.', 'stage': 'nova_qwen_validation', 'retryable': True, 'profile': profile, 'build': BUILD_ID})
    if len(semantic_traits) < 2:
        raise HTTPException(status_code=502, detail={'error': 'Qwen generated fewer than two usable semantic traits.', 'stage': 'nova_qwen_validation', 'retryable': True, 'profile': profile, 'build': BUILD_ID})
    profile['retrieval_tags'] = retrieval_tags
    profile['semantic_traits'] = semantic_traits
    summary = profile.get('summary')
    energy = profile.get('energy')
    vocal_preference = profile.get('vocal_preference')
    if not isinstance(summary, str) or not summary.strip():
        profile['summary'] = f'{payload.mood} music for {payload.video_type}.'
    if not isinstance(energy, str) or not energy.strip():
        profile['energy'] = payload.pace
    if not isinstance(vocal_preference, str) or not vocal_preference.strip():
        profile['vocal_preference'] = payload.vocal_style
    return profile

def normalize_tag(value: str):
    value = value.casefold().strip()
    value = re.sub('[^a-z0-9]+', ' ', value)
    value = re.sub('\\s+', ' ', value)
    return value.strip()

def tag_similarity(desired_tag: str, actual_tag: str):
    desired = normalize_tag(desired_tag)
    actual = normalize_tag(actual_tag)
    if not desired or not actual:
        return 0.0
    if desired == actual:
        return 1.0
    desired_compact = desired.replace(' ', '')
    actual_compact = actual.replace(' ', '')
    if desired_compact == actual_compact:
        return 0.95
    desired_words = desired.split()
    actual_words = actual.split()
    desired_word_set = set(desired_words)
    actual_word_set = set(actual_words)
    if len(desired_words) > 1:
        if len(actual_words) == 1:
            return 0.0
        if desired_word_set.issubset(actual_word_set):
            return 0.88
        overlap = len(desired_word_set & actual_word_set)
        coverage = overlap / len(desired_word_set)
        if coverage >= 0.75:
            return 0.65
        return 0.0
    desired_word = desired_words[0]
    if desired_word in actual_word_set:
        return 0.78
    if len(desired_word) >= 4 and desired_word in actual_compact:
        return 0.6
    return 0.0

async def get_lastfm_tracks_for_tag(http_client: httpx.AsyncClient, tag: str, limit: int=10):
    params = {'method': 'tag.getTopTracks', 'tag': tag, 'api_key': LASTFM_API_KEY, 'format': 'json', 'limit': limit}
    try:
        response = await http_client.get(LASTFM_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        return {'tag': tag, 'tracks': [], 'error': 'Last.fm request timed out.'}
    except httpx.HTTPStatusError as error:
        return {'tag': tag, 'tracks': [], 'error': f'Last.fm returned HTTP {error.response.status_code}.'}
    except httpx.RequestError as error:
        return {'tag': tag, 'tracks': [], 'error': f'Last.fm network error: {error}'}
    except ValueError:
        return {'tag': tag, 'tracks': [], 'error': 'Last.fm returned invalid JSON.'}
    if 'error' in data:
        return {'tag': tag, 'tracks': [], 'error': f"Last.fm API error: {data.get('message', 'Unknown error')}"}
    tracks = data.get('tracks', {}).get('track', [])
    if not isinstance(tracks, list):
        tracks = []
    results = []
    for position, track in enumerate(tracks, start=1):
        if not isinstance(track, dict):
            continue
        title = track.get('name')
        artist_data = track.get('artist', {})
        if isinstance(artist_data, dict):
            artist_name = artist_data.get('name')
        else:
            artist_name = str(artist_data) if artist_data else None
        if not title or not artist_name:
            continue
        results.append({'title': str(title).strip(), 'artist': str(artist_name).strip(), 'lastfm_url': track.get('url'), 'mbid': track.get('mbid') or None, 'source_tag': tag, 'tag_rank': position})
    return {'tag': tag, 'tracks': results, 'error': None}

async def search_lastfm_all_usable(retrieval_tags):
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        tasks = [get_lastfm_tracks_for_tag(http_client=http_client, tag=tag, limit=10) for tag in retrieval_tags]
        results = await asyncio.gather(*tasks)
    usable_results = [result for result in results if result['tracks']]
    dead_tags = [result['tag'] for result in results if not result['tracks']]
    failed_queries = [{'tag': result['tag'], 'error': result['error']} for result in results if result['error']]
    if len(usable_results) < 2:
        raise HTTPException(status_code=502, detail={'error': 'Last.fm returned usable results for fewer than two retrieval tags.', 'stage': 'lastfm_search', 'retrieval_tags': retrieval_tags, 'dead_tags': dead_tags, 'failed_queries': failed_queries, 'build': BUILD_ID})
    return {'tag_results': [result['tracks'] for result in usable_results], 'active_tags': [result['tag'] for result in usable_results], 'dead_tags': dead_tags, 'failed_queries': failed_queries}

def count_unique_initial_candidates(tag_results):
    keys = set()
    for tag_tracks in tag_results:
        for track in tag_tracks:
            keys.add((track['title'].strip().casefold(), track['artist'].strip().casefold()))
    return len(keys)

def build_balanced_shortlist(tag_results, per_tag: int=2):
    candidates = {}
    raw_slots = 0
    for tag_tracks in tag_results:
        selected_tracks = tag_tracks[:per_tag]
        raw_slots += len(selected_tracks)
        for track in selected_tracks:
            key = (track['title'].strip().casefold(), track['artist'].strip().casefold())
            if key not in candidates:
                candidates[key] = {'title': track['title'], 'artist': track['artist'], 'lastfm_url': track['lastfm_url'], 'mbid': track['mbid'], 'retrieval_matches': []}
            candidates[key]['retrieval_matches'].append({'tag': track['source_tag'], 'rank': track['tag_rank']})
    candidate_list = list(candidates.values())
    merged_candidates = []
    for candidate in candidate_list:
        retrieval_matches = candidate['retrieval_matches']
        if len(retrieval_matches) > 1:
            merged_candidates.append({'title': candidate['title'], 'artist': candidate['artist'], 'retrieved_by': [match['tag'] for match in retrieval_matches]})
    debug = {'raw_slots': raw_slots, 'unique_candidates': len(candidate_list), 'duplicates_removed': raw_slots - len(candidate_list), 'merged_candidates': merged_candidates}
    return (candidate_list, debug)

async def enrich_candidate_tags(http_client: httpx.AsyncClient, semaphore: asyncio.Semaphore, candidate):
    params = {'method': 'track.getTopTags', 'artist': candidate['artist'], 'track': candidate['title'], 'autocorrect': 1, 'api_key': LASTFM_API_KEY, 'format': 'json'}
    enriched = dict(candidate)
    enriched['top_tags'] = []
    enriched['enrichment_error'] = None
    try:
        async with semaphore:
            response = await http_client.get(LASTFM_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        enriched['enrichment_error'] = 'Last.fm enrichment timed out.'
        return enriched
    except httpx.HTTPStatusError as error:
        enriched['enrichment_error'] = f'Last.fm enrichment returned HTTP {error.response.status_code}.'
        return enriched
    except httpx.RequestError as error:
        enriched['enrichment_error'] = f'Last.fm enrichment network error: {error}'
        return enriched
    except ValueError:
        enriched['enrichment_error'] = 'Last.fm enrichment returned invalid JSON.'
        return enriched
    if 'error' in data:
        enriched['enrichment_error'] = f"Last.fm enrichment API error: {data.get('message', 'Unknown error')}"
        return enriched
    tag_data = data.get('toptags', {}).get('tag', [])
    if isinstance(tag_data, dict):
        tag_data = [tag_data]
    if not isinstance(tag_data, list):
        tag_data = []
    top_tags = []
    for tag in tag_data[:20]:
        if not isinstance(tag, dict):
            continue
        name = tag.get('name')
        if not name:
            continue
        try:
            count = int(tag.get('count', 0))
        except (TypeError, ValueError):
            count = 0
        top_tags.append({'name': str(name).strip(), 'count': count})
    enriched['top_tags'] = top_tags
    return enriched

async def enrich_shortlist_parallel(shortlist):
    semaphore = asyncio.Semaphore(6)
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        tasks = [enrich_candidate_tags(http_client=http_client, semaphore=semaphore, candidate=candidate) for candidate in shortlist]
        enriched = await asyncio.gather(*tasks)
    warnings = []
    for candidate in enriched:
        error = candidate.get('enrichment_error')
        if error:
            warnings.append({'stage': 'lastfm_enrichment', 'track': candidate['title'], 'artist': candidate['artist'], 'message': error})
    return (enriched, warnings)


def build_embedding_query(
    profile,
    active_retrieval_tags
):
    retrieval_text = ', '.join(
        active_retrieval_tags
    )

    semantic_text = ', '.join(
        profile.get(
            'semantic_traits',
            []
        )
    )

    task_instruction = (
        'Given a video editor\'s desired music profile, '
        'retrieve candidate music profiles that best '
        'match the requested genres, atmosphere, '
        'energy, vocal character, and sonic qualities.'
    )

    query_text = (
        'Desired music profile. '
        f'Genres and styles: {retrieval_text}. '
        f'Semantic qualities: {semantic_text}. '
        f'Overall sound: {profile.get("summary", "")}. '
        f'Energy: {profile.get("energy", "")}. '
        f'Vocals: {profile.get("vocal_preference", "")}.'
    )

    if (
        EMBEDDING_PROVIDER
        ==
        'huggingface'
    ):
        return (
            f'Instruct: {task_instruction}\n'
            f'Query: {query_text}'
        )

    return (
        'search_query: '
        + query_text
    )


def build_candidate_embedding_document(
    candidate
):
    tag_names = [
        tag['name']
        for tag
        in candidate.get(
            'top_tags',
            []
        )[:12]
        if tag.get(
            'name'
        )
    ]

    if not tag_names:
        return None

    document_text = (
        'Candidate music profile. '
        'Track-specific music tags and qualities: '
        + ', '.join(
            tag_names
        )
        + '.'
    )

    if (
        EMBEDDING_PROVIDER
        ==
        'huggingface'
    ):
        return document_text

    return (
        'search_document: '
        + document_text
    )

def cosine_similarity(vector_a, vector_b):
    dot_product = sum((a * b for a, b in zip(vector_a, vector_b)))
    magnitude_a = math.sqrt(sum((a * a for a in vector_a)))
    magnitude_b = math.sqrt(sum((b * b for b in vector_b)))
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    return dot_product / (magnitude_a * magnitude_b)

def attach_semantic_similarity(
    profile,
    active_retrieval_tags,
    candidates
):
    query = build_embedding_query(
        profile,
        active_retrieval_tags
    )

    semantic_candidates = []

    eligible_candidates = []
    eligible_documents = []

    for candidate in candidates:
        candidate_copy = dict(
            candidate
        )

        candidate_copy[
            'semantic_similarity'
        ] = None

        semantic_candidates.append(
            candidate_copy
        )

        document = (
            build_candidate_embedding_document(
                candidate
            )
        )

        if not document:
            continue

        eligible_candidates.append(
            len(
                semantic_candidates
            )
            -
            1
        )

        eligible_documents.append(
            document
        )

    if not eligible_documents:
        warning = {
            'stage':
                'embedding_similarity',

            'message':
                (
                    'Nova had no track-specific '
                    'metadata suitable for semantic '
                    'candidate scoring. Last.fm '
                    'evidence was used instead.'
                ),
        }

        return (
            semantic_candidates,
            False,
            warning,
        )

    texts = [
        query,
        *eligible_documents,
    ]

    try:
        vectors = (
            create_embedding_vectors(
                texts
            )
        )

        if (
            len(
                vectors
            )
            !=
            len(
                texts
            )
        ):
            raise ValueError(
                (
                    'Embedding model returned '
                    'an unexpected vector count.'
                )
            )

        query_vector = (
            vectors[0]
        )

        for (
            candidate_index,
            vector,
        ) in zip(
            eligible_candidates,
            vectors[1:],
        ):
            semantic_candidates[
                candidate_index
            ][
                'semantic_similarity'
            ] = (
                cosine_similarity(
                    query_vector,
                    vector,
                )
            )

        return (
            semantic_candidates,
            True,
            None,
        )

    except Exception as error:
        warning = {
            'stage':
                'embedding_similarity',

            'message':
                (
                    'Semantic embeddings were '
                    'unavailable. Nova used '
                    'Last.fm evidence only.'
                ),

            'technical_error':
                str(
                    error
                ),
        }

        for candidate in semantic_candidates:
            candidate[
                'semantic_similarity'
            ] = None

        return (
            semantic_candidates,
            False,
            warning,
        )

def build_nova_calibration_debug(
    scored_candidates
):
    candidate_rows = []
    similarities = []

    for candidate in scored_candidates:
        similarity = candidate.get(
            'semantic_similarity'
        )

        if isinstance(
            similarity,
            (int, float),
        ):
            similarities.append(
                float(
                    similarity
                )
            )

        score_breakdown = (
            candidate.get(
                'score_breakdown'
            )
            or
            {}
        )

        candidate_rows.append(
            {
                'title':
                    candidate.get(
                        'title'
                    ),

                'artist':
                    candidate.get(
                        'artist'
                    ),

                'match_score':
                    candidate.get(
                        'match_score'
                    ),

                'semantic_similarity':
                    candidate.get(
                        'semantic_similarity'
                    ),

                'semantic_fit':
                    candidate.get(
                        'semantic_fit'
                    ),

                'semantic_points':
                    score_breakdown.get(
                        'semantic_fit'
                    ),

                'lastfm_tag_points':
                    score_breakdown.get(
                        'lastfm_tag_evidence'
                    ),

                'lastfm_retrieval_points':
                    score_breakdown.get(
                        'lastfm_retrieval'
                    ),

                'matched_tags':
                    candidate.get(
                        'matched_nova_tags'
                    )
                    or
                    [],
            }
        )

    candidate_rows.sort(
        key=lambda candidate:
            (
                candidate.get(
                    'semantic_similarity'
                )
                if isinstance(
                    candidate.get(
                        'semantic_similarity'
                    ),
                    (int, float),
                )
                else
                -1.0
            ),
        reverse=True,
    )

    distribution = {
        'count':
            len(
                similarities
            ),

        'minimum':
            None,

        'maximum':
            None,

        'mean':
            None,

        'median':
            None,

        'spread':
            None,
    }

    if similarities:
        ordered = sorted(
            similarities
        )

        count = len(
            ordered
        )

        mean = (
            sum(
                ordered
            )
            /
            count
        )

        if count % 2:
            median = ordered[
                count // 2
            ]

        else:
            middle = (
                count // 2
            )

            median = (
                ordered[
                    middle - 1
                ]
                +
                ordered[
                    middle
                ]
            ) / 2

        minimum = ordered[0]
        maximum = ordered[-1]

        distribution = {
            'count':
                count,

            'minimum':
                round(
                    minimum,
                    4,
                ),

            'maximum':
                round(
                    maximum,
                    4,
                ),

            'mean':
                round(
                    mean,
                    4,
                ),

            'median':
                round(
                    median,
                    4,
                ),

            'spread':
                round(
                    maximum
                    -
                    minimum,
                    4,
                ),
        }

    return {
        'embedding_provider':
            EMBEDDING_PROVIDER,

        'embedding_model':
            EMBEDDING_MODEL_ID,

        'current_calibration':
            get_semantic_calibration_profile(),

        'distribution':
            distribution,

        'candidates':
            candidate_rows,
    }

def calibrate_semantic_similarity(
    similarity
):
    if not isinstance(
        similarity,
        (int, float),
    ):
        return 0.0

    profile = (
        get_semantic_calibration_profile()
    )

    floor = float(
        profile[
            'floor'
        ]
    )

    midpoint = float(
        profile[
            'midpoint'
        ]
    )

    ceiling = float(
        profile[
            'ceiling'
        ]
    )

    steepness = float(
        profile[
            'steepness'
        ]
    )

    similarity = float(
        similarity
    )

    if similarity <= floor:
        return 0.0

    if similarity >= ceiling:
        return 1.0

    def sigmoid(
        value
    ):
        exponent = (
            -steepness
            *
            (
                value
                -
                midpoint
            )
        )

        exponent = min(
            60.0,
            max(
                -60.0,
                exponent,
            ),
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

    raw_fit = sigmoid(
        similarity
    )

    floor_fit = sigmoid(
        floor
    )

    ceiling_fit = sigmoid(
        ceiling
    )

    usable_range = (
        ceiling_fit
        -
        floor_fit
    )

    if usable_range <= 0:
        return 0.0

    calibrated_fit = (
        (
            raw_fit
            -
            floor_fit
        )
        /
        usable_range
    )

    return max(
        0.0,
        min(
            1.0,
            calibrated_fit,
        ),
    )

def classify_requested_vocal_mode(
    vocal_style
):
    normalized = normalize_tag(
        str(
            vocal_style
            or
            ''
        )
    )

    if not normalized:
        return 'neutral'

    if (
        'instrumental'
        in normalized
        or
        'no vocal'
        in normalized
        or
        'without vocal'
        in normalized
    ):
        return 'instrumental'

    if (
        'minimal'
        in normalized
        or
        'sparse vocal'
        in normalized
        or
        'light vocal'
        in normalized
        or
        'few vocal'
        in normalized
    ):
        return 'minimal'

    if (
        'vocal'
        in normalized
        or
        'singer'
        in normalized
        or
        'lyric'
        in normalized
    ):
        return 'vocal'

    return 'neutral'


def classify_candidate_vocal_state(
    top_tags
):
    instrumental_tags = []
    strong_vocal_tags = []
    soft_vocal_tags = []

    soft_vocal_markers = {
        'pop',
        'indie pop',
        'dance pop',
        'electropop',
        'synthpop',
        'pop rock',
        'folk',
        'indie folk',
        'punk',
        'soul',
    }

    for tag in (
        top_tags
        or
        []
    ):
        tag_name = str(
            tag.get(
                'name',
                ''
            )
            or
            ''
        )

        normalized = normalize_tag(
            tag_name
        )

        if not normalized:
            continue

        try:
            count = float(
                tag.get(
                    'count',
                    0
                )
                or
                0
            )

        except (
            TypeError,
            ValueError,
        ):
            count = 0.0

        words = set(
            normalized.split()
        )

        if (
            'instrumental'
            in normalized
        ):
            instrumental_tags.append(
                tag_name
            )

        strong_vocal = (
            'vocal'
            in normalized
            or
            'singer songwriter'
            in normalized
            or
            'rap'
            in words
            or
            'rapper'
            in words
            or
            'hip hop'
            in normalized
            or
            normalized
            in {
                'k pop',
                'kpop',
                'j pop',
                'jpop',
                'r b',
                'rnb',
                'a cappella',
                'spoken word',
            }
        )

        if strong_vocal:
            strong_vocal_tags.append(
                tag_name
            )

            continue

        if (
            normalized
            in soft_vocal_markers
            and
            count >= 5
        ):
            soft_vocal_tags.append(
                tag_name
            )

    if (
        instrumental_tags
        and
        strong_vocal_tags
    ):
        state = 'mixed'

    elif instrumental_tags:
        state = 'instrumental'

    elif strong_vocal_tags:
        state = 'vocal'

    elif soft_vocal_tags:
        state = 'likely_vocal'

    else:
        state = 'unknown'

    return {
        'state':
            state,

        'instrumental_evidence':
            instrumental_tags,

        'strong_vocal_evidence':
            strong_vocal_tags,

        'soft_vocal_evidence':
            soft_vocal_tags,
    }


def evaluate_vocal_preference(
    vocal_style,
    top_tags
):
    requested_mode = (
        classify_requested_vocal_mode(
            vocal_style
        )
    )

    evidence = (
        classify_candidate_vocal_state(
            top_tags
        )
    )

    candidate_state = (
        evidence[
            'state'
        ]
    )

    penalty = 0.0

    if (
        requested_mode
        ==
        'instrumental'
    ):
        if (
            candidate_state
            ==
            'vocal'
        ):
            penalty = 14.0

        elif (
            candidate_state
            ==
            'likely_vocal'
        ):
            penalty = 8.0

        elif (
            candidate_state
            ==
            'mixed'
        ):
            penalty = 4.0

    elif (
        requested_mode
        ==
        'minimal'
    ):
        if (
            candidate_state
            ==
            'vocal'
        ):
            penalty = 10.0

        elif (
            candidate_state
            ==
            'likely_vocal'
        ):
            penalty = 5.0

        elif (
            candidate_state
            ==
            'mixed'
        ):
            penalty = 2.0

    elif (
        requested_mode
        ==
        'vocal'
    ):
        if (
            candidate_state
            ==
            'instrumental'
        ):
            penalty = 10.0

    return {
        'requested_mode':
            requested_mode,

        'candidate_state':
            candidate_state,

        'penalty':
            penalty,

        'instrumental_evidence':
            evidence[
                'instrumental_evidence'
            ],

        'strong_vocal_evidence':
            evidence[
                'strong_vocal_evidence'
            ],

        'soft_vocal_evidence':
            evidence[
                'soft_vocal_evidence'
            ],
    }

def score_enriched_candidates(active_retrieval_tags, enriched_candidates, semantic_available, vocal_style=''):
    desired_tags = active_retrieval_tags
    importance_weights = [1.0, 0.94, 0.88, 0.82, 0.76, 0.7]
    total_importance = sum(importance_weights[:len(desired_tags)])
    normalized_desired_tags = [normalize_tag(tag) for tag in desired_tags]
    if semantic_available:
        tag_max_points = 45.0
        semantic_max_points = 35.0
        retrieval_max_points = 20.0
    else:
        tag_max_points = 45.0 / 65.0 * 100.0
        semantic_max_points = 0.0
        retrieval_max_points = 20.0 / 65.0 * 100.0
    scored = []
    for candidate in enriched_candidates:
        top_tags = candidate.get('top_tags', [])
        matched_desired = []
        weighted_tag_evidence = 0.0
        for desired_index, desired_tag in enumerate(desired_tags):
            importance = importance_weights[desired_index] if desired_index < len(importance_weights) else 0.65
            best_similarity = 0.0
            best_tag = None
            best_count = 0
            for actual_tag in top_tags:
                similarity = tag_similarity(desired_tag, actual_tag['name'])
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_tag = actual_tag['name']
                    best_count = actual_tag['count']
            if best_similarity > 0:
                strength = 0.7 + min(max(best_count, 0), 100) / 100 * 0.3
                evidence = importance * best_similarity * strength
                weighted_tag_evidence += evidence
                matched_desired.append({'nova_tag': desired_tag, 'lastfm_tag': best_tag, 'lastfm_count': best_count, 'similarity': round(best_similarity, 2)})
        if total_importance > 0:
            tag_evidence_points = weighted_tag_evidence / total_importance * tag_max_points
        else:
            tag_evidence_points = 0.0
        raw_semantic_similarity = candidate.get('semantic_similarity')
        semantic_fit = calibrate_semantic_similarity(raw_semantic_similarity) if semantic_available else 0.0
        semantic_points = semantic_fit * semantic_max_points
        retrieval_evidence = 0.0
        for retrieval in candidate['retrieval_matches']:
            normalized_retrieval_tag = normalize_tag(retrieval['tag'])
            try:
                desired_index = normalized_desired_tags.index(normalized_retrieval_tag)
            except ValueError:
                continue
            importance = importance_weights[desired_index] if desired_index < len(importance_weights) else 0.65
            rank = retrieval['rank']
            rank_quality = max(0.1, (11 - rank) / 10)
            retrieval_evidence += importance * rank_quality

        retrieval_points = min(
            retrieval_max_points,
            retrieval_evidence
            /
            1.4
            *
            retrieval_max_points
        )

        vocal_constraint = (
            evaluate_vocal_preference(
                vocal_style,
                top_tags
            )
        )

        vocal_penalty = float(
            vocal_constraint[
                'penalty'
            ]
        )

        base_score = (
            tag_evidence_points
            +
            semantic_points
            +
            retrieval_points
        )

        score = (
            base_score
            -
            vocal_penalty
        )
        score = int(round(min(99, max(0, score))))
        scored.append({'title': candidate['title'], 'artist': candidate['artist'], 'match_score': score, 'semantic_similarity': round(raw_semantic_similarity, 4) if raw_semantic_similarity is not None else None, 'semantic_fit': round(semantic_fit, 4) if semantic_available else None, 'score_breakdown': {
    'lastfm_tag_evidence':
        round(
            tag_evidence_points,
            2
        ),

    'semantic_fit':
        round(
            semantic_points,
            2
        ),

    'lastfm_retrieval':
        round(
            retrieval_points,
            2
        ),

    'vocal_preference_penalty':
        round(
            vocal_penalty,
            2
        ),
},

'vocal_constraint':
    vocal_constraint, 'matched_nova_tags': [match['nova_tag'] for match in matched_desired], 'match_evidence': matched_desired, 'retrieval_matches': candidate['retrieval_matches'], 'top_lastfm_tags': top_tags[:8], 'lastfm_url': candidate['lastfm_url'], 'mbid': candidate['mbid']})
    scored.sort(key=lambda item: (item['match_score'], item['semantic_similarity'] or 0, len(item['matched_nova_tags'])), reverse=True)
    return (scored, {'lastfm_tag_evidence': round(tag_max_points, 2), 'semantic_similarity': round(semantic_max_points, 2), 'lastfm_retrieval': round(retrieval_max_points, 2)})

def build_nova_recommendation_reason(
    candidate
):
    """
    Build a user-facing explanation for a Nova result.

    Internal similarity values and score components remain available
    in the API response for debugging, but they are deliberately not
    exposed in the recommendation copy.
    """

    matched_tags = [
        str(tag).strip()
        for tag in (
            candidate.get(
                'matched_nova_tags'
            )
            or
            []
        )
        if str(tag).strip()
    ]

    top_tags = [
        str(tag.get('name')).strip()
        for tag in (
            candidate.get(
                'top_lastfm_tags'
            )
            or
            []
        )
        if (
            isinstance(tag, dict)
            and
            tag.get('name')
        )
    ]

    score_breakdown = (
        candidate.get(
            'score_breakdown'
        )
        or
        {}
    )

    try:
        vocal_penalty = float(
            score_breakdown.get(
                'vocal_preference_penalty',
                0.0,
            )
            or
            0.0
        )
    except (
        TypeError,
        ValueError,
    ):
        vocal_penalty = 0.0

    vocal_constraint = (
        candidate.get(
            'vocal_constraint'
        )
        or
        {}
    )

    requested_mode = (
        vocal_constraint.get(
            'requested_mode'
        )
    )

    if matched_tags:
        strongest_tags = (
            matched_tags[:3]
        )

        if len(strongest_tags) == 1:
            musical_direction = (
                strongest_tags[0]
            )
        elif len(strongest_tags) == 2:
            musical_direction = (
                f'{strongest_tags[0]} and '
                f'{strongest_tags[1]}'
            )
        else:
            musical_direction = (
                ', '.join(
                    strongest_tags[:-1]
                )
                +
                f', and {strongest_tags[-1]}'
            )

        reason = (
            'This track sits naturally in the '
            f'{musical_direction} direction your brief points toward, '
            'while its overall feel stays close to the atmosphere '
            'and movement you described.'
        )

    elif top_tags:
        strongest_tags = (
            top_tags[:2]
        )

        musical_direction = (
            ' and '.join(
                strongest_tags
            )
        )

        reason = (
            'This track surfaced consistently in the same musical '
            f'neighborhood as your brief, especially around '
            f'{musical_direction}.'
        )

    else:
        reason = (
            'This track consistently surfaced as one of the closest '
            'overall fits for the musical direction in your brief.'
        )

    if vocal_penalty <= 0:
        return reason

    if (
        requested_mode
        ==
        'instrumental'
    ):
        adjustment = (
            'Its available metadata suggests more vocal presence than '
            'you asked for, so Nova ranked it a little more cautiously.'
        )

    elif (
        requested_mode
        ==
        'minimal'
    ):
        adjustment = (
            'Its available metadata suggests a more vocal-forward '
            'sound than requested, so Nova ranked it more cautiously.'
        )

    elif (
        requested_mode
        ==
        'vocal'
    ):
        adjustment = (
            'Its available metadata is less clearly vocal-forward than '
            'your brief requested, so Nova ranked it more cautiously.'
        )

    else:
        adjustment = (
            'Nova also treated the vocal fit a little more cautiously '
            'for this option.'
        )

    return (
        reason
        +
        ' '
        +
        adjustment
    )

def select_top_three(candidates):
    if len(candidates) < 3:
        raise HTTPException(status_code=502, detail={'error': 'Nova could not produce three rankable song candidates.', 'stage': 'final_selection', 'candidate_count': len(candidates), 'build': BUILD_ID})
    selected = []
    used_artists = set()
    for candidate in candidates:
        artist_key = candidate['artist'].strip().casefold()
        if artist_key in used_artists:
            continue
        selected.append(candidate)
        used_artists.add(artist_key)
        if len(selected) == 3:
            break
    if len(selected) < 3:
        for candidate in candidates:
            if candidate in selected:
                continue
            selected.append(candidate)
            if len(selected) == 3:
                break
    recommendations = []
    for rank, candidate in enumerate(selected, start=1):
        matched_tags = (
            candidate[
                'matched_nova_tags'
            ]
        )

        reason = (
            build_nova_recommendation_reason(
                candidate
            )
        )
        
        recommendations.append({'rank': rank, 'title': candidate['title'], 'artist': candidate['artist'], 'match_score': candidate['match_score'], 'reason': reason, 'semantic_similarity': candidate['semantic_similarity'], 'semantic_fit': candidate['semantic_fit'], 'score_breakdown': candidate['score_breakdown'], 'matched_tags': matched_tags, 'top_lastfm_tags': candidate['top_lastfm_tags'], 'match_evidence': candidate['match_evidence'], 'lastfm_url': candidate['lastfm_url'], 'mbid': candidate['mbid']})
    if len(recommendations) != 3:
        raise HTTPException(status_code=500, detail={'error': "Nova's final selection did not contain exactly three songs.", 'stage': 'final_selection', 'recommendation_count': len(recommendations), 'build': BUILD_ID})
    return recommendations

def normalize_ytmusic_text(value: str):
    """
    Legacy function name retained because the Pulsar cache
    already calls it. The normalization is provider-neutral.
    """

    value = html_lib.unescape(
        str(value or '')
    )

    value = unicodedata.normalize(
        'NFKD',
        value,
    )

    value = ''.join(
        character
        for character in value
        if not unicodedata.combining(
            character
        )
    )

    value = value.casefold().strip()
    value = re.sub(
        r'[^a-z0-9]+',
        ' ',
        value,
    )
    value = re.sub(
        r'\s+',
        ' ',
        value,
    )

    return value.strip()


def youtube_text_similarity(
    value_a,
    value_b,
):
    normalized_a = (
        normalize_ytmusic_text(
            value_a
        )
    )

    normalized_b = (
        normalize_ytmusic_text(
            value_b
        )
    )

    if (
        not normalized_a
        or
        not normalized_b
    ):
        return 0.0

    if (
        normalized_a
        ==
        normalized_b
    ):
        return 1.0

    if (
        len(normalized_a) >= 4
        and
        len(normalized_b) >= 4
        and
        (
            normalized_a
            in
            normalized_b
            or
            normalized_b
            in
            normalized_a
        )
    ):
        containment_score = 0.92
    else:
        containment_score = 0.0

    sequence_score = (
        SequenceMatcher(
            None,
            normalized_a,
            normalized_b,
        )
        .ratio()
    )

    tokens_a = set(
        normalized_a.split()
    )

    tokens_b = set(
        normalized_b.split()
    )

    token_union = (
        tokens_a
        |
        tokens_b
    )

    token_score = (
        len(
            tokens_a
            &
            tokens_b
        )
        /
        len(
            token_union
        )
        if token_union
        else 0.0
    )

    return round(
        max(
            containment_score,
            sequence_score,
            token_score,
        ),
        4,
    )


YOUTUBE_HARD_REJECT_MARKERS = [
    'official music video',
    'official video',
    'music video',
    'visualizer',
    'visualiser',
    'lyric video',
    'lyrics video',
    'official lyric video',
    'official lyrics video',
    'live performance',
    'performance video',
    'short film',
    'trailer',
    'teaser',
    'behind the scenes',
    'behind scenes',
]

YOUTUBE_ALTERNATE_VERSION_MARKERS = [
    # Performance / alternate-recording variants. These are
    # rejected unless the user explicitly included the marker
    # in the requested song title.
    'live',
    'live at',
    'live from',
    'concert',
    'unplugged',
    'mtv unplugged',
    'session',
    'sessions',
    'studio session',
    'stripped',
    'acoustic',
    'acoustic version',
    'piano version',
    'orchestral version',
    'alternate take',
    'alternate version',
    're recorded',
    're-recorded',
    're recording',
    're-recording',

    # Mix / speed / release variants.
    'remix',
    'sped up',
    'slowed',
    'slowed reverb',
    'nightcore',
    'instrumental',
    'karaoke',
    'cover',
    'radio edit',
    'extended mix',
    'club mix',
    'demo',
    'demo version',
    'remaster',
    'remastered',
]

YOUTUBE_ART_TRACK_DESCRIPTION_MARKERS = [
    'provided to youtube by',
    'auto generated by youtube',
    'auto-generated by youtube',
]


def strip_harmless_youtube_title_qualifiers(
    value,
):
    text = html_lib.unescape(
        str(value or '')
    )

    harmless_group_pattern = (
        r'[\(\[\{]\s*'
        r'(?:official\s+audio|audio\s+only|audio|explicit|clean|uncensored)'
        r'\s*[\)\]\}]'
    )

    text = re.sub(
        harmless_group_pattern,
        ' ',
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r'\bofficial\s+audio\b',
        ' ',
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r'\baudio\s+only\b',
        ' ',
        text,
        flags=re.IGNORECASE,
    )

    return re.sub(
        r'\s+',
        ' ',
        text,
    ).strip()


def remove_artist_prefix_from_youtube_title(
    title,
    desired_artist,
):
    normalized_title = (
        normalize_ytmusic_text(
            title
        )
    )

    normalized_artist = (
        normalize_ytmusic_text(
            desired_artist
        )
    )

    if (
        normalized_artist
        and
        normalized_title.startswith(
            normalized_artist
            +
            ' '
        )
    ):
        return normalized_title[
            len(normalized_artist):
        ].strip()

    return normalized_title


def score_youtube_title_match(
    candidate_title,
    desired_title,
    desired_artist,
):
    cleaned_candidate = (
        strip_harmless_youtube_title_qualifiers(
            candidate_title
        )
    )

    normalized_candidate = (
        normalize_ytmusic_text(
            cleaned_candidate
        )
    )

    candidate_without_artist = (
        remove_artist_prefix_from_youtube_title(
            cleaned_candidate,
            desired_artist,
        )
    )

    normalized_desired = (
        normalize_ytmusic_text(
            desired_title
        )
    )

    return max(
        youtube_text_similarity(
            normalized_candidate,
            normalized_desired,
        ),
        youtube_text_similarity(
            candidate_without_artist,
            normalized_desired,
        ),
    )


def normalize_youtube_channel_artist(
    channel_title,
):
    normalized = (
        normalize_ytmusic_text(
            channel_title
        )
    )

    suffixes = [
        ' topic',
        ' vevo',
        ' official',
        ' official channel',
        ' music',
    ]

    changed = True

    while changed:
        changed = False

        for suffix in suffixes:
            if normalized.endswith(
                suffix
            ):
                normalized = normalized[
                    :-len(suffix)
                ].strip()

                changed = True
                break

    return normalized


def score_youtube_artist_channel_match(
    channel_title,
    desired_artist,
):
    channel_artist = (
        normalize_youtube_channel_artist(
            channel_title
        )
    )

    desired_artist_normalized = (
        normalize_ytmusic_text(
            desired_artist
        )
    )

    return youtube_text_similarity(
        channel_artist,
        desired_artist_normalized,
    )


def youtube_title_contains_marker(
    normalized_title,
    marker,
):
    normalized_marker = (
        normalize_ytmusic_text(
            marker
        )
    )

    if not normalized_marker:
        return False

    padded_title = (
        ' '
        +
        normalize_ytmusic_text(
            normalized_title
        )
        +
        ' '
    )

    padded_marker = (
        ' '
        +
        normalized_marker
        +
        ' '
    )

    return (
        padded_marker
        in
        padded_title
    )


def find_unrequested_youtube_version_marker(
    candidate_title,
    desired_title,
):
    normalized_candidate = (
        normalize_ytmusic_text(
            candidate_title
        )
    )

    normalized_desired = (
        normalize_ytmusic_text(
            desired_title
        )
    )

    for marker in (
        YOUTUBE_ALTERNATE_VERSION_MARKERS
    ):
        normalized_marker = (
            normalize_ytmusic_text(
                marker
            )
        )

        if (
            youtube_title_contains_marker(
                normalized_candidate,
                normalized_marker,
            )
            and
            not youtube_title_contains_marker(
                normalized_desired,
                normalized_marker,
            )
        ):
            return marker

    return None


def classify_youtube_search_result(
    item,
    desired_title,
    desired_artist,
    search_query,
    search_rank,
):
    if not isinstance(
        item,
        dict,
    ):
        return None

    video_id = (
        item.get('id', {})
        .get('videoId')
        if isinstance(
            item.get('id'),
            dict,
        )
        else None
    )

    snippet = (
        item.get('snippet')
        if isinstance(
            item.get('snippet'),
            dict,
        )
        else {}
    )

    title = html_lib.unescape(
        str(
            snippet.get('title')
            or
            ''
        )
    ).strip()

    channel_title = html_lib.unescape(
        str(
            snippet.get('channelTitle')
            or
            ''
        )
    ).strip()

    channel_id = (
        snippet.get('channelId')
        or
        None
    )

    description = html_lib.unescape(
        str(
            snippet.get('description')
            or
            ''
        )
    ).strip()

    if (
        not video_id
        or
        not title
        or
        not channel_title
    ):
        return None

    normalized_title = (
        normalize_ytmusic_text(
            title
        )
    )

    normalized_channel = (
        normalize_ytmusic_text(
            channel_title
        )
    )

    normalized_description = (
        normalize_ytmusic_text(
            description
        )
    )

    normalized_artist = (
        normalize_ytmusic_text(
            desired_artist
        )
    )

    title_match = (
        score_youtube_title_match(
            title,
            desired_title,
            desired_artist,
        )
    )

    artist_channel_match = (
        score_youtube_artist_channel_match(
            channel_title,
            desired_artist,
        )
    )

    is_official_audio = (
        'official audio'
        in
        normalized_title
    )

    hard_reject_marker = next(
        (
            marker
            for marker
            in YOUTUBE_HARD_REJECT_MARKERS
            if youtube_title_contains_marker(
                normalized_title,
                marker,
            )
        ),
        None,
    )

    alternate_marker = (
        find_unrequested_youtube_version_marker(
            title,
            desired_title,
        )
    )

    is_topic_channel = (
        normalized_channel.endswith(
            ' topic'
        )
        and
        artist_channel_match >= 0.58
    )

    description_has_art_track_marker = any(
        normalize_ytmusic_text(
            marker
        )
        in
        normalized_description
        for marker
        in YOUTUBE_ART_TRACK_DESCRIPTION_MARKERS
    )

    description_mentions_artist = (
        bool(normalized_artist)
        and
        normalized_artist
        in
        normalized_description
    )

    is_art_track = (
        is_topic_channel
        or
        (
            description_has_art_track_marker
            and
            (
                description_mentions_artist
                or
                artist_channel_match >= 0.68
            )
        )
    )

    accepted = False
    resolver_type = None
    resolver_priority = 99
    rejection_reason = None

    if hard_reject_marker:
        rejection_reason = (
            'audiovisual_variant:'
            +
            hard_reject_marker
        )

    elif alternate_marker:
        rejection_reason = (
            'alternate_recording:'
            +
            alternate_marker
        )

    elif title_match < 0.78:
        rejection_reason = (
            'title_match_too_low'
        )

    elif is_art_track:
        accepted = True
        resolver_type = (
            'youtube_art_track'
        )
        resolver_priority = 1

    elif (
        is_official_audio
        and
        artist_channel_match >= 0.72
    ):
        accepted = True
        resolver_type = (
            'youtube_official_audio'
        )
        resolver_priority = 2

    else:
        rejection_reason = (
            'not_canonical_audio_source'
        )

    match_score = (
        title_match * 0.68
        +
        artist_channel_match * 0.22
        +
        (
            0.08
            if is_topic_channel
            else 0.0
        )
        +
        (
            0.05
            if description_has_art_track_marker
            else 0.0
        )
        +
        (
            0.03
            if is_official_audio
            else 0.0
        )
    )

    match_score = round(
        min(
            1.0,
            match_score,
        ),
        4,
    )

    return {
        'video_id':
            str(video_id),

        'title':
            title,

        'channel_title':
            channel_title,

        'channel_id':
            channel_id,

        'description':
            description,

        'title_match':
            round(
                title_match,
                4,
            ),

        'artist_channel_match':
            round(
                artist_channel_match,
                4,
            ),

        'is_topic_channel':
            is_topic_channel,

        'is_art_track':
            is_art_track,

        'is_official_audio':
            is_official_audio,

        'accepted':
            accepted,

        'resolver_type':
            resolver_type,

        'resolver_priority':
            resolver_priority,

        'rejection_reason':
            rejection_reason,

        'match_score':
            match_score,

        'search_query':
            search_query,

        'search_rank':
            search_rank,
    }


def compact_youtube_candidate_debug(
    candidate,
):
    if not isinstance(
        candidate,
        dict,
    ):
        return {}

    return {
        'video_id':
            candidate.get(
                'video_id'
            ),

        'title':
            candidate.get(
                'title'
            ),

        'channel_title':
            candidate.get(
                'channel_title'
            ),

        'accepted':
            candidate.get(
                'accepted'
            ),

        'resolver_type':
            candidate.get(
                'resolver_type'
            ),

        'rejection_reason':
            candidate.get(
                'rejection_reason'
            ),

        'title_match':
            candidate.get(
                'title_match'
            ),

        'artist_channel_match':
            candidate.get(
                'artist_channel_match'
            ),

        'match_score':
            candidate.get(
                'match_score'
            ),

        'search_query':
            candidate.get(
                'search_query'
            ),
    }


def parse_youtube_duration_seconds(
    value,
):
    text = str(
        value
        or
        ''
    ).strip()

    match = re.fullmatch(
        (
            r'P'
            r'(?:(?P<days>\d+)D)?'
            r'(?:T'
            r'(?:(?P<hours>\d+)H)?'
            r'(?:(?P<minutes>\d+)M)?'
            r'(?:(?P<seconds>\d+(?:\.\d+)?)S)?'
            r')?'
        ),
        text,
    )

    if not match:
        return None

    days = float(
        match.group('days')
        or
        0
    )

    hours = float(
        match.group('hours')
        or
        0
    )

    minutes = float(
        match.group('minutes')
        or
        0
    )

    seconds = float(
        match.group('seconds')
        or
        0
    )

    total = (
        days * 86400
        +
        hours * 3600
        +
        minutes * 60
        +
        seconds
    )

    if total <= 0:
        return None

    return int(
        round(total)
    )


def format_youtube_duration(
    duration_seconds,
):
    if not isinstance(
        duration_seconds,
        (int, float),
    ):
        return None

    duration_seconds = max(
        0,
        int(
            round(
                duration_seconds
            )
        ),
    )

    hours, remainder = divmod(
        duration_seconds,
        3600,
    )

    minutes, seconds = divmod(
        remainder,
        60,
    )

    if hours:
        return (
            f'{hours}:'
            f'{minutes:02d}:'
            f'{seconds:02d}'
        )

    return (
        f'{minutes}:'
        f'{seconds:02d}'
    )


async def youtube_api_get(
    http_client,
    path,
    params,
    stage,
):
    if not YOUTUBE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail={
                'error':
                    (
                        'YOUTUBE_API_KEY was not '
                        'found.'
                    ),

                'message':
                    (
                        'Pulsar cannot resolve new '
                        'recordings until the YouTube '
                        'Data API key is configured.'
                    ),

                'stage':
                    stage,

                'retryable':
                    False,

                'resolver':
                    'youtube_data_api',

                'build':
                    PULSAR_RESOLVER_BUILD_ID,
            }
        )

    request_params = dict(
        params
        or
        {}
    )

    request_params[
        'key'
    ] = YOUTUBE_API_KEY

    try:
        response = await http_client.get(
            (
                YOUTUBE_API_BASE_URL.rstrip('/')
                +
                '/'
                +
                path.lstrip('/')
            ),
            params=request_params,
        )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={
                'error':
                    (
                        'The YouTube Data API '
                        'request timed out.'
                    ),

                'stage':
                    stage,

                'retryable':
                    True,

                'resolver':
                    'youtube_data_api',

                'build':
                    PULSAR_RESOLVER_BUILD_ID,
            }
        )

    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    (
                        'Pulsar could not reach the '
                        'YouTube Data API.'
                    ),

                'technical_error':
                    str(error),

                'stage':
                    stage,

                'retryable':
                    True,

                'resolver':
                    'youtube_data_api',

                'build':
                    PULSAR_RESOLVER_BUILD_ID,
            }
        )

    try:
        data = response.json()
    except ValueError:
        data = None

    if response.is_error:
        google_error = (
            data.get('error')
            if isinstance(
                data,
                dict,
            )
            and
            isinstance(
                data.get('error'),
                dict,
            )
            else {}
        )

        google_message = (
            google_error.get(
                'message'
            )
            or
            (
                'The YouTube Data API '
                'rejected the request.'
            )
        )

        google_reasons = []

        for item in (
            google_error.get(
                'errors'
            )
            or
            []
        ):
            if not isinstance(
                item,
                dict,
            ):
                continue

            reason = item.get(
                'reason'
            )

            if reason:
                google_reasons.append(
                    str(reason)
                )

        raise HTTPException(
            status_code=(
                429
                if any(
                    'quota'
                    in
                    reason.casefold()
                    for reason
                    in google_reasons
                )
                else 502
            ),
            detail={
                'error':
                    (
                        'YouTube Data API search '
                        'could not be completed.'
                    ),

                'message':
                    google_message,

                'youtube_status_code':
                    response.status_code,

                'youtube_reasons':
                    google_reasons,

                'stage':
                    stage,

                'retryable':
                    response.status_code >= 500,

                'resolver':
                    'youtube_data_api',

                'build':
                    PULSAR_RESOLVER_BUILD_ID,
            }
        )

    if not isinstance(
        data,
        dict,
    ):
        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    (
                        'YouTube Data API returned '
                        'an unreadable response.'
                    ),

                'stage':
                    stage,

                'retryable':
                    True,

                'resolver':
                    'youtube_data_api',

                'build':
                    PULSAR_RESOLVER_BUILD_ID,
            }
        )

    return data


async def search_youtube_data_api(
    http_client,
    query,
    max_results=25,
):
    data = await youtube_api_get(
        http_client=http_client,
        path='search',
        params={
            'part':
                'snippet',

            'type':
                'video',

            'q':
                query,

            'maxResults':
                max_results,

            'order':
                'relevance',

            'safeSearch':
                'none',

            'videoCategoryId':
                '10',
        },
        # Keep the legacy stage name so the current
        # frontend can display the existing resolver
        # error treatment without a JS migration.
        stage='pulsar_ytmusic_search',
    )

    items = data.get(
        'items'
    )

    if not isinstance(
        items,
        list,
    ):
        return []

    return items


async def get_youtube_video_details(
    http_client,
    video_id,
):
    data = await youtube_api_get(
        http_client=http_client,
        path='videos',
        params={
            'part':
                'snippet,contentDetails,status',

            'id':
                str(video_id),

            'maxResults':
                1,
        },
        stage='pulsar_ytmusic_resolution',
    )

    items = data.get(
        'items'
    )

    if (
        not isinstance(
            items,
            list,
        )
        or
        not items
    ):
        return None

    video = items[0]

    return (
        video
        if isinstance(
            video,
            dict,
        )
        else None
    )


def choose_best_youtube_candidate(
    candidates,
):
    accepted = [
        candidate
        for candidate
        in candidates
        if (
            isinstance(
                candidate,
                dict,
            )
            and
            candidate.get(
                'accepted'
            )
        )
    ]

    if not accepted:
        return None

    accepted.sort(
        key=lambda candidate: (
            int(
                candidate.get(
                    'resolver_priority'
                )
                or
                99
            ),
            -float(
                candidate.get(
                    'match_score'
                )
                or
                0.0
            ),
            int(
                candidate.get(
                    'search_rank'
                )
                or
                999
            ),
        )
    )

    return accepted[0]


def build_resolved_youtube_track(
    payload,
    candidate,
    video_details,
):
    snippet = (
        video_details.get(
            'snippet'
        )
        if isinstance(
            video_details,
            dict,
        )
        and
        isinstance(
            video_details.get(
                'snippet'
            ),
            dict,
        )
        else {}
    )

    content_details = (
        video_details.get(
            'contentDetails'
        )
        if isinstance(
            video_details,
            dict,
        )
        and
        isinstance(
            video_details.get(
                'contentDetails'
            ),
            dict,
        )
        else {}
    )

    status = (
        video_details.get(
            'status'
        )
        if isinstance(
            video_details,
            dict,
        )
        and
        isinstance(
            video_details.get(
                'status'
            ),
            dict,
        )
        else {}
    )

    video_id = str(
        candidate.get(
            'video_id'
        )
    )

    actual_title = html_lib.unescape(
        str(
            snippet.get('title')
            or
            candidate.get('title')
            or
            payload.title
        )
    ).strip()

    actual_channel_title = html_lib.unescape(
        str(
            snippet.get(
                'channelTitle'
            )
            or
            candidate.get(
                'channel_title'
            )
            or
            ''
        )
    ).strip()

    duration_seconds = (
        parse_youtube_duration_seconds(
            content_details.get(
                'duration'
            )
        )
    )

    youtube_url = (
        'https://www.youtube.com/'
        f'watch?v={video_id}'
    )

    return {
        # Keep the editor-facing title and artist exactly
        # as requested. The raw YouTube metadata is retained
        # separately for diagnostics.
        'title':
            payload.title.strip(),

        'artists': [
            payload.artist.strip()
        ],

        'artist_ids':
            [],

        'album':
            None,

        'album_id':
            None,

        'duration':
            format_youtube_duration(
                duration_seconds
            ),

        'duration_seconds':
            duration_seconds,

        'video_id':
            video_id,

        'youtube_url':
            youtube_url,

        # Retained for backward compatibility with cached
        # track payloads. New resolution does not depend on
        # music.youtube.com.
        'youtube_music_url':
            youtube_url,

        'is_explicit':
            None,

        'match_score':
            candidate.get(
                'match_score'
            ),

        'resolver_type':
            candidate.get(
                'resolver_type'
            ),

        'canonical_audio':
            True,

        'youtube_title':
            actual_title,

        'channel_title':
            actual_channel_title,

        'channel_id':
            (
                snippet.get(
                    'channelId'
                )
                or
                candidate.get(
                    'channel_id'
                )
            ),

        'licensed_content':
            bool(
                content_details.get(
                    'licensedContent'
                )
            ),

        'embeddable':
            status.get(
                'embeddable'
            ),

        'resolver_evidence': {
            'topic_channel':
                candidate.get(
                    'is_topic_channel'
                ),

            'art_track':
                candidate.get(
                    'is_art_track'
                ),

            'official_audio':
                candidate.get(
                    'is_official_audio'
                ),

            'title_match':
                candidate.get(
                    'title_match'
                ),

            'artist_channel_match':
                candidate.get(
                    'artist_channel_match'
                ),

            'search_query':
                candidate.get(
                    'search_query'
                ),
        },
    }


@app.post('/pulsar/resolve')
async def pulsar_resolve(
    payload: PulsarResolveRequest
):
    start_time = time.perf_counter()

    cached_entry = (
        get_cached_pulsar_track_by_title_artist(
            payload.title,
            payload.artist,
        )
    )

    if cached_entry:
        cached_track = (
            cached_entry.get(
                'track'
            )
            or
            {}
        )

        video_id = (
            cached_entry.get(
                'video_id'
            )
            or
            cached_track.get(
                'video_id'
            )
        )

        library_track_id = (
            cached_entry.get(
                'library_track_id'
            )
        )

        if (
            video_id
            and
            library_track_id
        ):
            artists = (
                cached_track.get(
                    'artists'
                )
                or
                [
                    payload.artist
                ]
            )

            if isinstance(
                artists,
                str,
            ):
                artists = [
                    artists
                ]

            youtube_url = (
                cached_track.get(
                    'youtube_url'
                )
                or
                (
                    'https://www.youtube.com/'
                    f'watch?v={video_id}'
                )
            )

            resolved_track = {
                'title':
                    (
                        cached_track.get(
                            'title'
                        )
                        or
                        payload.title
                    ),

                'artists':
                    artists,

                'artist_ids':
                    (
                        cached_track.get(
                            'artist_ids'
                        )
                        or
                        []
                    ),

                'album':
                    cached_track.get(
                        'album'
                    ),

                'album_id':
                    cached_track.get(
                        'album_id'
                    ),

                'duration':
                    cached_track.get(
                        'duration'
                    ),

                'duration_seconds':
                    cached_track.get(
                        'duration_seconds'
                    ),

                'video_id':
                    str(video_id),

                'youtube_url':
                    youtube_url,

                'youtube_music_url':
                    (
                        cached_track.get(
                            'youtube_music_url'
                        )
                        or
                        youtube_url
                    ),

                'is_explicit':
                    cached_track.get(
                        'is_explicit'
                    ),

                'match_score':
                    (
                        cached_track.get(
                            'resolver_match_score'
                        )
                        or
                        cached_track.get(
                            'match_score'
                        )
                        or
                        1.0
                    ),

                'resolver_type':
                    (
                        cached_track.get(
                            'resolver_type'
                        )
                        or
                        'legacy_ytmusic_song_cache'
                    ),

                'canonical_audio':
                    cached_track.get(
                        'canonical_audio',
                        True,
                    ),

                'youtube_title':
                    cached_track.get(
                        'youtube_title'
                    ),

                'channel_title':
                    cached_track.get(
                        'channel_title'
                    ),

                'channel_id':
                    cached_track.get(
                        'channel_id'
                    ),

                'licensed_content':
                    cached_track.get(
                        'licensed_content'
                    ),

                'resolver_evidence':
                    cached_track.get(
                        'resolver_evidence'
                    ),
            }

            total_ms = round(
                (
                    time.perf_counter()
                    -
                    start_time
                )
                *
                1000
            )

            print(
                '[PULSAR RESOLVER CACHE HIT] '
                f'{resolved_track["title"]} — '
                f'{", ".join(artists)} '
                f'-> {library_track_id}'
            )

            return {
                'build':
                    PULSAR_RESOLVER_BUILD_ID,

                'resolved':
                    True,

                'source':
                    'Syncora Cache',

                'requested': {
                    'title':
                        payload.title,

                    'artist':
                        payload.artist,

                    'mbid':
                        payload.mbid,
                },

                'track':
                    resolved_track,

                'cache': {
                    'hit':
                        True,

                    'source':
                        cached_entry.get(
                            '_cache_source',
                            'supabase',
                        ),

                    'library_track_id':
                        str(
                            library_track_id
                        ),
                },

                'timing_ms': {
                    'total':
                        total_ms,
                },
            }

    if not YOUTUBE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail={
                'error':
                    'YOUTUBE_API_KEY was not found.',

                'message':
                    (
                        'Add YOUTUBE_API_KEY to the '
                        'backend environment before '
                        'resolving uncached tracks.'
                    ),

                'stage':
                    'pulsar_ytmusic_search',

                'retryable':
                    False,

                'resolver':
                    'youtube_data_api',

                'build':
                    PULSAR_RESOLVER_BUILD_ID,
            }
        )

    generic_query = (
        f'{payload.artist} {payload.title}'
        .strip()
    )

    topic_query = (
        f'{payload.artist} - Topic '
        f'{payload.title}'
    ).strip()

    all_candidates = []
    seen_video_ids = set()
    search_queries = []

    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=True,
        trust_env=False,
    ) as http_client:
        generic_results = (
            await search_youtube_data_api(
                http_client=http_client,
                query=generic_query,
                max_results=25,
            )
        )

        search_queries.append(
            generic_query
        )

        for index, item in enumerate(
            generic_results,
            start=1,
        ):
            candidate = (
                classify_youtube_search_result(
                    item=item,
                    desired_title=payload.title,
                    desired_artist=payload.artist,
                    search_query=generic_query,
                    search_rank=index,
                )
            )

            if not candidate:
                continue

            video_id = candidate.get(
                'video_id'
            )

            if video_id in seen_video_ids:
                continue

            seen_video_ids.add(
                video_id
            )

            all_candidates.append(
                candidate
            )

        art_track_candidates = [
            candidate
            for candidate
            in all_candidates
            if (
                candidate.get(
                    'accepted'
                )
                and
                candidate.get(
                    'resolver_type'
                )
                ==
                'youtube_art_track'
            )
        ]

        # Even when a good Official Audio fallback exists,
        # make one targeted Topic search before using it.
        # This preserves Art Track / Topic as the primary
        # resolver policy requested for Pulsar.
        if not art_track_candidates:
            topic_results = (
                await search_youtube_data_api(
                    http_client=http_client,
                    query=topic_query,
                    max_results=20,
                )
            )

            search_queries.append(
                topic_query
            )

            for index, item in enumerate(
                topic_results,
                start=1,
            ):
                candidate = (
                    classify_youtube_search_result(
                        item=item,
                        desired_title=payload.title,
                        desired_artist=payload.artist,
                        search_query=topic_query,
                        search_rank=index,
                    )
                )

                if not candidate:
                    continue

                video_id = candidate.get(
                    'video_id'
                )

                if video_id in seen_video_ids:
                    continue

                seen_video_ids.add(
                    video_id
                )

                all_candidates.append(
                    candidate
                )

        best_candidate = (
            choose_best_youtube_candidate(
                all_candidates
            )
        )

        if not best_candidate:
            debug_candidates = sorted(
                all_candidates,
                key=lambda candidate: (
                    -float(
                        candidate.get(
                            'title_match'
                        )
                        or
                        0.0
                    ),
                    -float(
                        candidate.get(
                            'artist_channel_match'
                        )
                        or
                        0.0
                    ),
                    int(
                        candidate.get(
                            'search_rank'
                        )
                        or
                        999
                    ),
                ),
            )[:8]

            raise HTTPException(
                status_code=404,
                detail={
                    'error':
                        (
                            'Pulsar could not identify '
                            'a trustworthy canonical '
                            'audio source on YouTube.'
                        ),

                    'message':
                        (
                            'Pulsar found YouTube results, '
                            'but none were a confident Art '
                            'Track / Topic match or an '
                            'Official Audio upload from the '
                            'artist channel. Music videos '
                            'and alternate recordings were '
                            'not used.'
                        ),

                    # Legacy stage name retained for the
                    # current frontend error mapping.
                    'stage':
                        'pulsar_ytmusic_match',

                    'requested': {
                        'title':
                            payload.title,

                        'artist':
                            payload.artist,

                        'mbid':
                            payload.mbid,
                    },

                    'queries':
                        search_queries,

                    'candidates': [
                        compact_youtube_candidate_debug(
                            candidate
                        )
                        for candidate
                        in debug_candidates
                    ],

                    'retryable':
                        False,

                    'resolver':
                        'youtube_data_api',

                    'build':
                        PULSAR_RESOLVER_BUILD_ID,
                }
            )

        video_details = (
            await get_youtube_video_details(
                http_client=http_client,
                video_id=best_candidate[
                    'video_id'
                ],
            )
        )

    if not video_details:
        raise HTTPException(
            status_code=404,
            detail={
                'error':
                    (
                        'The matched YouTube audio '
                        'source is no longer available.'
                    ),

                'stage':
                    'pulsar_ytmusic_resolution',

                'video_id':
                    best_candidate.get(
                        'video_id'
                    ),

                'retryable':
                    True,

                'resolver':
                    'youtube_data_api',

                'build':
                    PULSAR_RESOLVER_BUILD_ID,
            }
        )

    resolved_track = (
        build_resolved_youtube_track(
            payload=payload,
            candidate=best_candidate,
            video_details=video_details,
        )
    )

    if not resolved_track.get(
        'duration_seconds'
    ):
        raise HTTPException(
            status_code=404,
            detail={
                'error':
                    (
                        'The matched canonical audio '
                        'source did not expose a usable '
                        'duration.'
                    ),

                'stage':
                    'pulsar_ytmusic_resolution',

                'video_id':
                    resolved_track.get(
                        'video_id'
                    ),

                'retryable':
                    False,

                'resolver':
                    'youtube_data_api',

                'build':
                    PULSAR_RESOLVER_BUILD_ID,
            }
        )

    total_ms = round(
        (
            time.perf_counter()
            -
            start_time
        )
        *
        1000
    )

    print(
        '[PULSAR YOUTUBE RESOLVE] '
        f'{payload.title} — '
        f'{payload.artist} -> '
        f'{resolved_track["video_id"]} '
        f'({resolved_track["resolver_type"]}, '
        f'{resolved_track["channel_title"]})'
    )

    return {
        'build':
            PULSAR_RESOLVER_BUILD_ID,

        'resolved':
            True,

        'source':
            'YouTube Data API v3',

        'requested': {
            'title':
                payload.title,

            'artist':
                payload.artist,

            'mbid':
                payload.mbid,
        },

        'track':
            resolved_track,

        'resolver': {
            'type':
                resolved_track.get(
                    'resolver_type'
                ),

            'canonical_audio':
                True,

            'policy':
                (
                    'Art Track / Topic first; '
                    'Official Audio on artist '
                    'channel second; audiovisual '
                    'and alternate versions rejected.'
                ),

            'queries':
                search_queries,
        },

        'timing_ms': {
            'total':
                total_ms,
        },
    }


@app.post('/pulsar/analyze/start')
async def pulsar_analyze_start(payload: PulsarResolveRequest):
    start_time = time.perf_counter()
    resolution = await pulsar_resolve(payload)
    resolved_track = resolution.get('track', {})
    video_id = resolved_track.get('video_id')
    if not video_id:
        raise HTTPException(status_code=502, detail={'error': 'Pulsar resolved the song but did not receive a usable YouTube video ID.', 'stage': 'pulsar_ytmusic_resolution', 'build': PULSAR_ANALYSIS_BUILD_ID})
    youtube_url = f'https://www.youtube.com/watch?v={video_id}'

    track_payload = {
        'title': resolved_track.get('title'),
        'artists': resolved_track.get('artists'),
        'album': resolved_track.get('album'),
        'duration': resolved_track.get('duration'),
        'duration_seconds': resolved_track.get('duration_seconds'),
        'video_id': video_id,
        'youtube_url': youtube_url,
        'resolver_match_score': resolved_track.get('match_score'),
        'resolver_type': resolved_track.get('resolver_type'),
        'canonical_audio': resolved_track.get('canonical_audio'),
        'youtube_title': resolved_track.get('youtube_title'),
        'channel_title': resolved_track.get('channel_title'),
        'channel_id': resolved_track.get('channel_id'),
        'licensed_content': resolved_track.get('licensed_content'),
        'resolver_evidence': resolved_track.get('resolver_evidence'),
    }

    cached_entry = get_cached_pulsar_track_by_video_id(
        video_id
    )

    if cached_entry:
        cached_library_track_id = cached_entry.get(
            'library_track_id'
        )

        if cached_library_track_id:
            # Refresh the stored track metadata in case
            # The resolver returned newer YouTube metadata.
            cache_pulsar_resolution(
                video_id=video_id,
                library_track_id=cached_library_track_id,
                track=track_payload,
            )

            total_ms = round(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000
            )

            print(
                '[PULSAR CACHE HIT] '
                f'{track_payload["title"]} — '
                f'{", ".join(track_payload["artists"] or [])} '
                f'-> {cached_library_track_id}'
            )

            return {
                'build': PULSAR_ANALYSIS_BUILD_ID,
                'started': True,
                'track': track_payload,
                'cache': {
                    'hit': True,
                    'source': cached_entry.get(
                        '_cache_source',
                        'local_disk',
                    ),
                },
                'cyanite': {
                    'enqueued': False,
                    'reused_library_track': True,
                    'library_track_id': cached_library_track_id,
                },
                'timing_ms': {
                    'total': total_ms
                },
            }

    if not CYANITE_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail={'error': 'CYANITE_ACCESS_TOKEN was not found.', 'stage': 'cyanite_enqueue', 'build': PULSAR_ANALYSIS_BUILD_ID})
    mutation = '\n    mutation PulsarYouTubeTrackEnqueue(\n        $input: YouTubeTrackEnqueueInput!\n    ) {\n        youTubeTrackEnqueue(\n            input: $input\n        ) {\n            __typename\n\n            ... on YouTubeTrackEnqueueSuccess {\n                enqueuedLibraryTrack {\n                    id\n                }\n            }\n\n            ... on YouTubeTrackEnqueueError {\n                code\n                message\n            }\n        }\n    }\n    '
    request_body = {'query': mutation, 'variables': {'input': {'videoUrl': youtube_url}}}
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + CYANITE_ACCESS_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(CYANITE_API_URL, headers=headers, json=request_body)
        response.raise_for_status()
        cyanite_response = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail={'error': 'Cyanite timed out while enqueueing the YouTube track.', 'stage': 'cyanite_enqueue', 'retryable': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
    except httpx.HTTPStatusError as error:
        raise HTTPException(status_code=502, detail={'error': 'Cyanite returned an HTTP error while enqueueing the YouTube track.', 'status_code': error.response.status_code, 'stage': 'cyanite_enqueue', 'retryable': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
    except httpx.RequestError as error:
        raise HTTPException(status_code=502, detail={'error': 'Syncora could not reach Cyanite while enqueueing the track.', 'message': str(error), 'stage': 'cyanite_enqueue', 'retryable': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
    except ValueError:
        raise HTTPException(status_code=502, detail={'error': 'Cyanite returned an unreadable response while enqueueing the track.', 'stage': 'cyanite_enqueue', 'retryable': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
    if cyanite_response.get('errors'):
        raise HTTPException(status_code=502, detail={'error': 'Cyanite rejected the GraphQL enqueue request.', 'cyanite_errors': cyanite_response.get('errors'), 'stage': 'cyanite_enqueue', 'build': PULSAR_ANALYSIS_BUILD_ID})
    enqueue_result = cyanite_response.get('data', {}).get('youTubeTrackEnqueue')
    if not isinstance(enqueue_result, dict):
        raise HTTPException(status_code=502, detail={'error': 'Cyanite did not return a usable enqueue result.', 'stage': 'cyanite_enqueue', 'build': PULSAR_ANALYSIS_BUILD_ID})
    result_type = enqueue_result.get('__typename')
    if result_type == 'YouTubeTrackEnqueueError':
        raise HTTPException(status_code=422, detail={'error': 'Cyanite could not enqueue this YouTube track.', 'cyanite_code': enqueue_result.get('code'), 'cyanite_message': enqueue_result.get('message'), 'stage': 'cyanite_enqueue', 'build': PULSAR_ANALYSIS_BUILD_ID})
    library_track = enqueue_result.get('enqueuedLibraryTrack', {})
    cyanite_track_id = library_track.get('id')
    if not cyanite_track_id:
        raise HTTPException(status_code=502, detail={'error': 'Cyanite did not provide a library track ID.', 'stage': 'cyanite_enqueue', 'build': PULSAR_ANALYSIS_BUILD_ID})

    cache_pulsar_resolution(
        video_id=video_id,
        library_track_id=cyanite_track_id,
        track=track_payload,
    )

    print(
        '[PULSAR CACHE STORE] '
        f'{track_payload["title"]} — '
        f'{", ".join(track_payload["artists"] or [])} '
        f'-> {cyanite_track_id}'
    )

    total_ms = round((time.perf_counter() - start_time) * 1000)

    return {
        'build': PULSAR_ANALYSIS_BUILD_ID,
        'started': True,
        'track': track_payload,
        'cache': {
            'hit': False,
            'source': 'cyanite',
        },
        'cyanite': {
            'enqueued': True,
            'reused_library_track': False,
            'library_track_id': cyanite_track_id,
        },
        'timing_ms': {
            'total': total_ms
        },
    }

@app.get('/pulsar/analyze/status/{library_track_id}')
async def pulsar_analyze_status(
    library_track_id: str
):
    # -------------------------------------------------
    # 1. Check Syncora's persistent local cache first.
    # -------------------------------------------------

    cached_entry = (
        get_cached_pulsar_track_by_library_id(
            library_track_id
        )
    )

    cached_analysis = (
        cached_entry.get('analysis')
        if cached_entry
        else None
    )

    if (
        isinstance(cached_analysis, dict)
        and cached_analysis
    ):
        cached_track = (
            cached_entry.get('track')
            or {}
        )

        print(
            '[PULSAR ANALYSIS CACHE HIT] '
            f'{cached_track.get("title") or library_track_id}'
        )

        return {
            'build':
                PULSAR_ANALYSIS_BUILD_ID,

            'library_track_id':
                str(library_track_id),

            'title':
                cached_track.get('title'),

            'status':
                'finished',

            'analysis_type':
                'SyncoraCachedAudioAnalysis',

            'finished':
                True,

            'analysis':
                cached_analysis,

            'cache': {
                'hit':
                    True,

                'source':
                    cached_entry.get(
                        '_cache_source',
                        'local_disk',
                    ),
            },
        }

    # -------------------------------------------------
    # 2. No cached analysis yet, so retrieve the
    #    already-enqueued Cyanite library track.
    # -------------------------------------------------

    if not CYANITE_ACCESS_TOKEN:
        raise HTTPException(
            status_code=500,
            detail={
                'error':
                    'CYANITE_ACCESS_TOKEN was not found.',

                'stage':
                    'cyanite_analysis_status',

                'build':
                    PULSAR_ANALYSIS_BUILD_ID,
            }
        )

    query = '''
    query PulsarAnalysisStatus(
        $id: ID!
    ) {
        libraryTrack(
            id: $id
        ) {
            __typename

            ... on LibraryTrackNotFoundError {
                message
            }

            ... on LibraryTrack {
                id
                title

                audioAnalysisV7 {
                    __typename

                    ... on AudioAnalysisV7Finished {
                        result {
                            bpmRangeAdjusted

                            keyPrediction {
                                value
                                confidence
                            }

                            timeSignature
                            arousal
                            valence
                            transformerCaption
                        }
                    }

                    ... on AudioAnalysisV7Failed {
                        error {
                            message
                        }
                    }
                }
            }
        }
    }
    '''

    headers = {
        'Content-Type':
            'application/json',

        'Authorization':
            'Bearer '
            + CYANITE_ACCESS_TOKEN,
    }

    body = {
        'query':
            query,

        'variables': {
            'id':
                str(library_track_id)
        },
    }

    try:
        async with httpx.AsyncClient(
            timeout=20.0
        ) as http_client:
            response = await http_client.post(
                CYANITE_API_URL,
                headers=headers,
                json=body,
            )

        response.raise_for_status()
        data = response.json()

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={
                'error':
                    'Cyanite timed out while checking '
                    'the audio analysis.',

                'stage':
                    'cyanite_analysis_status',

                'build':
                    PULSAR_ANALYSIS_BUILD_ID,
            }
        )

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    'Cyanite returned an HTTP error '
                    'while checking the audio analysis.',

                'status_code':
                    error.response.status_code,

                'stage':
                    'cyanite_analysis_status',

                'build':
                    PULSAR_ANALYSIS_BUILD_ID,
            }
        )

    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    'Syncora could not reach Cyanite '
                    'while checking the audio analysis.',

                'message':
                    str(error),

                'stage':
                    'cyanite_analysis_status',

                'retryable':
                    True,

                'build':
                    PULSAR_ANALYSIS_BUILD_ID,
            }
        )

    except ValueError:
        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    'Cyanite returned an unreadable '
                    'analysis-status response.',

                'stage':
                    'cyanite_analysis_status',

                'retryable':
                    True,

                'build':
                    PULSAR_ANALYSIS_BUILD_ID,
            }
        )

    # -------------------------------------------------
    # 3. Validate Cyanite response.
    # -------------------------------------------------

    if data.get('errors'):
        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    'Cyanite rejected the analysis '
                    'status request.',

                'cyanite_errors':
                    data.get('errors'),

                'build':
                    PULSAR_ANALYSIS_BUILD_ID,
            }
        )

    track = (
        data
        .get('data', {})
        .get('libraryTrack')
    )

    if not isinstance(track, dict):
        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    'Cyanite returned an invalid '
                    'track response.',

                'build':
                    PULSAR_ANALYSIS_BUILD_ID,
            }
        )

    if (
        track.get('__typename')
        ==
        'LibraryTrackNotFoundError'
    ):
        raise HTTPException(
            status_code=404,
            detail={
                'error':
                    track.get('message')
                    or
                    'Cyanite could not find that track.'
            }
        )

    analysis = (
        track.get('audioAnalysisV7')
        or {}
    )

    analysis_type = (
        analysis.get('__typename')
    )

    status_map = {
        'AudioAnalysisV7NotStarted':
            'not_started',

        'AudioAnalysisV7Enqueued':
            'enqueued',

        'AudioAnalysisV7Processing':
            'processing',

        'AudioAnalysisV7Finished':
            'finished',

        'AudioAnalysisV7Failed':
            'failed',

        'AudioAnalysisV7NotAuthorized':
            'not_authorized',
    }

    status = status_map.get(
        analysis_type,
        'unknown'
    )

    # -------------------------------------------------
    # 4. Analysis has not finished yet.
    # -------------------------------------------------

    if (
        analysis_type
        !=
        'AudioAnalysisV7Finished'
    ):
        if (
            analysis_type
            ==
            'AudioAnalysisV7Failed'
        ):
            analysis_error = (
                analysis.get('error')
                or {}
            )

            raise HTTPException(
                status_code=502,
                detail={
                    'error':
                        'Cyanite audio analysis failed.',

                    'message':
                        analysis_error.get('message'),

                    'analysis_type':
                        analysis_type,

                    'build':
                        PULSAR_ANALYSIS_BUILD_ID,
                }
            )

        return {
            'build':
                PULSAR_ANALYSIS_BUILD_ID,

            'library_track_id':
                track.get('id'),

            'title':
                track.get('title'),

            'status':
                status,

            'analysis_type':
                analysis_type,

            'finished':
                False,

            'cache': {
                'hit':
                    False,

                'source':
                    'cyanite',
            },
        }

    # -------------------------------------------------
    # 5. Analysis is finished.
    #    Normalize it BEFORE referencing result.
    # -------------------------------------------------

    result = (
        analysis.get('result')
        or {}
    )

    key_prediction = (
        result.get('keyPrediction')
        or {}
    )

    normalized_analysis = {
        'bpm':
            result.get(
                'bpmRangeAdjusted'
            ),

        'key':
            key_prediction.get(
                'value'
            ),

        'key_confidence':
            key_prediction.get(
                'confidence'
            ),

        'time_signature':
            result.get(
                'timeSignature'
            ),

        'arousal':
            result.get(
                'arousal'
            ),

        'valence':
            result.get(
                'valence'
            ),

        'description':
            result.get(
                'transformerCaption'
            ),
    }

    # -------------------------------------------------
    # 6. Persist the completed analysis locally.
    # -------------------------------------------------

    cache_pulsar_finished_analysis(
        library_track_id=library_track_id,
        analysis=normalized_analysis,
    )

    print(
        '[PULSAR ANALYSIS CACHE STORE] '
        f'{track.get("title") or library_track_id}'
    )

    return {
        'build':
            PULSAR_ANALYSIS_BUILD_ID,

        'library_track_id':
            track.get('id'),

        'title':
            track.get('title'),

        'status':
            status,

        'analysis_type':
            analysis_type,

        'finished':
            True,

        'analysis':
            normalized_analysis,

        'cache': {
            'hit':
                False,

            'source':
                'cyanite',
        },
    }

@app.get('/pulsar/analyze/segments/{library_track_id}')
async def pulsar_analyze_segments(library_track_id: str):
    start_time = time.perf_counter()

    cached_entry = (
        get_cached_pulsar_track_by_library_id(
            library_track_id
        )
    )

    cached_segments_response = (
        cached_entry.get(
            'segments_response'
        )
        if cached_entry
        else None
    )

    if (
        isinstance(
            cached_segments_response,
            dict
        )
        and isinstance(
            cached_segments_response.get(
                'segments'
            ),
            list
        )
    ):
        total_ms = round(
            (
                time.perf_counter()
                - start_time
            )
            * 1000
        )

        print(
            '[PULSAR SEGMENT CACHE HIT] '
            f'{cached_segments_response.get("title") or library_track_id}'
        )

        return {
            'build':
                PULSAR_ANALYSIS_BUILD_ID,

            'library_track_id':
                str(
                    library_track_id
                ),

            'title':
                cached_segments_response.get(
                    'title'
                ),

            'analysis':
                cached_segments_response.get(
                    'analysis'
                )
                or
                {},

            'segment_metadata':
                cached_segments_response.get(
                    'segment_metadata'
                )
                or
                {},

            'segments':
                cached_segments_response.get(
                    'segments'
                )
                or
                [],

            'cache': {
                'hit':
                    True,

                'source':
                    cached_entry.get(
                        '_cache_source',
                        'local_disk',
                    ),
            },

            'timing_ms': {
                'total':
                    total_ms
            },
        }

    if not CYANITE_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail={'error': 'CYANITE_ACCESS_TOKEN was not found.', 'stage': 'cyanite_segments', 'build': PULSAR_ANALYSIS_BUILD_ID})
    query = '\n    query PulsarSegmentAnalysis(\n        $id: ID!\n    ) {\n        libraryTrack(\n            id: $id\n        ) {\n            __typename\n\n            ... on LibraryTrackNotFoundError {\n                message\n            }\n\n            ... on LibraryTrack {\n                id\n                title\n\n                audioAnalysisV7 {\n                    __typename\n\n                    ... on AudioAnalysisV7Finished {\n                        result {\n                            bpmRangeAdjusted\n\n                            keyPrediction {\n                                value\n                                confidence\n                            }\n\n                            timeSignature\n                            transformerCaption\n\n                            segments {\n                                representativeSegmentIndex\n                                timestamps\n                                arousal\n                                valence\n\n                                mood {\n                                    aggressive\n                                    calm\n                                    chilled\n                                    dark\n                                    energetic\n                                    epic\n                                    happy\n                                    romantic\n                                    sad\n                                    scary\n                                    sexy\n                                    ethereal\n                                    uplifting\n                                }\n\n                                voice {\n                                    female\n                                    instrumental\n                                    male\n                                }\n\n                                instruments {\n                                    percussion\n                                    synth\n                                    piano\n                                    acousticGuitar\n                                    electricGuitar\n                                    strings\n                                    bass\n                                    bassGuitar\n                                    brassWoodwinds\n                                }\n\n                                movement {\n                                    bouncy\n                                    driving\n                                    flowing\n                                    groovy\n                                    nonrhythmic\n                                    pulsing\n                                    robotic\n                                    running\n                                    steady\n                                    stomping\n                                }\n\n                                character {\n                                    bold\n                                    cool\n                                    epic\n                                    ethereal\n                                    heroic\n                                    luxurious\n                                    magical\n                                    mysterious\n                                    playful\n                                    powerful\n                                    retro\n                                    sophisticated\n                                    sparkling\n                                    sparse\n                                    unpolished\n                                    warm\n                                }\n                            }\n                        }\n                    }\n                }\n            }\n        }\n    }\n    '
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + CYANITE_ACCESS_TOKEN}
    body = {'query': query, 'variables': {'id': str(library_track_id)}}
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(CYANITE_API_URL, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail={'error': 'Cyanite timed out while retrieving segment data.', 'stage': 'cyanite_segments', 'retryable': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
    except httpx.HTTPStatusError as error:
        raise HTTPException(status_code=502, detail={'error': 'Cyanite returned an HTTP error while retrieving segment data.', 'status_code': error.response.status_code, 'stage': 'cyanite_segments', 'build': PULSAR_ANALYSIS_BUILD_ID})
    except httpx.RequestError as error:
        raise HTTPException(status_code=502, detail={'error': 'Syncora could not reach Cyanite for segment data.', 'message': str(error), 'stage': 'cyanite_segments', 'retryable': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
    except ValueError:
        raise HTTPException(status_code=502, detail={'error': 'Cyanite returned unreadable segment data.', 'stage': 'cyanite_segments', 'retryable': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
    if data.get('errors'):
        raise HTTPException(status_code=502, detail={'error': 'Cyanite rejected the segment analysis query.', 'cyanite_errors': data.get('errors'), 'stage': 'cyanite_segments', 'build': PULSAR_ANALYSIS_BUILD_ID})
    track = data.get('data', {}).get('libraryTrack')
    if not isinstance(track, dict):
        raise HTTPException(status_code=502, detail={'error': 'Cyanite returned an invalid library track.', 'stage': 'cyanite_segments', 'build': PULSAR_ANALYSIS_BUILD_ID})
    if track.get('__typename') == 'LibraryTrackNotFoundError':
        raise HTTPException(status_code=404, detail={'error': 'Cyanite could not find that library track.', 'message': track.get('message'), 'build': PULSAR_ANALYSIS_BUILD_ID})
    analysis = track.get('audioAnalysisV7') or {}
    if analysis.get('__typename') != 'AudioAnalysisV7Finished':
        raise HTTPException(status_code=409, detail={'error': 'Cyanite analysis is not finished yet.', 'analysis_type': analysis.get('__typename'), 'build': PULSAR_ANALYSIS_BUILD_ID})
    result = analysis.get('result', {})
    segments = result.get('segments')
    if not isinstance(segments, dict):
        raise HTTPException(status_code=502, detail={'error': 'Cyanite analysis finished but returned no usable segment data.', 'stage': 'cyanite_segments', 'build': PULSAR_ANALYSIS_BUILD_ID})
    timestamps = segments.get('timestamps') or []
    arousal_values = segments.get('arousal') or []
    valence_values = segments.get('valence') or []
    mood_data = segments.get('mood') or {}
    voice_data = segments.get('voice') or {}
    instrument_data = segments.get('instruments') or {}
    movement_data = segments.get('movement') or {}
    character_data = segments.get('character') or {}
    normalized_segments = []
    for index, timestamp in enumerate(timestamps):
        segment_mood = extract_segment_category(mood_data, index)
        segment_voice = extract_segment_category(voice_data, index)
        segment_instruments = extract_segment_category(instrument_data, index)
        segment_movement = extract_segment_category(movement_data, index)
        segment_character = extract_segment_category(character_data, index)
        normalized_segments.append({'index': index, 'timestamp': timestamp, 'arousal': safe_array_value(arousal_values, index), 'valence': safe_array_value(valence_values, index), 'dominant_mood': strongest_segment_label(segment_mood), 'dominant_voice': strongest_segment_label(segment_voice), 'dominant_instrument': strongest_segment_label(segment_instruments), 'dominant_movement': strongest_segment_label(segment_movement), 'dominant_character': strongest_segment_label(segment_character), 'raw': {'mood': segment_mood, 'voice': segment_voice, 'instruments': segment_instruments, 'movement': segment_movement, 'character': segment_character}})

    key_prediction = (
        result.get('keyPrediction')
        or {}
    )

    normalized_analysis = {
        'bpm':
            result.get(
                'bpmRangeAdjusted'
            ),

        'key':
            key_prediction.get(
                'value'
            ),

        'key_confidence':
            key_prediction.get(
                'confidence'
            ),

        'time_signature':
            result.get(
                'timeSignature'
            ),

        'description':
            result.get(
                'transformerCaption'
            ),
    }

    segment_cache_payload = {
        'title':
            track.get(
                'title'
            ),

        'analysis':
            normalized_analysis,

        'segment_metadata': {
            'count':
                len(
                    normalized_segments
                ),

            'representative_segment_index':
                segments.get(
                    'representativeSegmentIndex'
                ),
        },

        'segments':
            normalized_segments,
    }

    cache_pulsar_finished_analysis(
        library_track_id=library_track_id,
        analysis=normalized_analysis,
        segments_response=segment_cache_payload,
    )

    print(
        '[PULSAR SEGMENT CACHE STORE] '
        f'{track.get("title") or library_track_id} '
        f'({len(normalized_segments)} segments)'
    )

    total_ms = round(
        (
            time.perf_counter()
            - start_time
        )
        * 1000
    )

    return {
        'build':
            PULSAR_ANALYSIS_BUILD_ID,

        'library_track_id':
            track.get(
                'id'
            ),

        **segment_cache_payload,

        'cache': {
            'hit':
                False,

            'source':
                'cyanite',
        },

        'timing_ms': {
            'total':
                total_ms
        },
    }

def estimate_track_duration_from_segments(segments, supplied_duration=None):
    if isinstance(supplied_duration, (int, float)) and supplied_duration > 0:
        return float(supplied_duration)
    timestamps = [float(segment.get('timestamp')) for segment in segments if isinstance(segment.get('timestamp'), (int, float))]
    if not timestamps:
        return 0.0
    timestamps = sorted(timestamps)
    positive_deltas = [current - previous for previous, current in zip(timestamps, timestamps[1:]) if current > previous]
    estimated_tail = 0.0
    if positive_deltas:
        sorted_deltas = sorted(positive_deltas)
        estimated_tail = sorted_deltas[len(sorted_deltas) // 2]
    return max(timestamps) + estimated_tail


def classify_pulsar_keypoint_tier(
    change_score
):
    """
    Preserve the Signal-strength thresholds the frontend already used,
    but apply them to every measured transition in the selected window.
    """

    numeric_score = float(
        change_score
        or
        0.0
    )

    if numeric_score >= 85:
        return 'primary'

    if numeric_score >= 60:
        return 'secondary'

    return 'tertiary'


def choose_pulsar_edit_window(
    candidates,
    track_duration_seconds,
    requested_duration_seconds,
):
    """
    Pick the source window using the musical change present inside it.

    Pulsar 0.6 intentionally does not optimize toward a fixed cue count.
    Every measured transition in the chosen window can become a Signal
    keypoint, then the UI lets the editor reveal Primary, Secondary, and
    Tertiary layers independently.
    """

    track_duration = max(
        float(
            track_duration_seconds
            or
            0
        ),
        0.0,
    )

    requested_duration = (
        float(
            requested_duration_seconds
        )
        if (
            isinstance(
                requested_duration_seconds,
                (int, float),
            )
            and
            requested_duration_seconds > 0
        )
        else
        track_duration
    )

    if track_duration <= 0:
        track_duration = max(
            (
                float(
                    candidate.get(
                        'timestamp'
                    )
                )
                for candidate in candidates
                if isinstance(
                    candidate.get(
                        'timestamp'
                    ),
                    (int, float),
                )
            ),
            default=requested_duration,
        )

    if requested_duration <= 0:
        requested_duration = (
            track_duration
        )

    effective_duration = (
        min(
            requested_duration,
            track_duration,
        )
        if track_duration > 0
        else
        requested_duration
    )

    if effective_duration <= 0:
        effective_duration = (
            track_duration
        )

    if (
        not candidates
        or
        track_duration <= 0
        or
        effective_duration
        >=
        track_duration - 0.5
    ):
        return {
            'requested_duration_seconds':
                round(
                    requested_duration,
                    3,
                )
                if requested_duration
                else None,

            'duration_seconds':
                round(
                    track_duration,
                    3,
                ),

            'start_seconds':
                0.0,

            'end_seconds':
                round(
                    track_duration,
                    3,
                ),

            'track_duration_seconds':
                round(
                    track_duration,
                    3,
                ),

            'uses_excerpt':
                False,

            'window_score':
                None,

            'candidate_count':
                len(
                    candidates
                ),
        }

    latest_start = max(
        0.0,
        track_duration
        -
        effective_duration,
    )

    possible_starts = {
        0.0,
        latest_start,
    }

    for candidate in candidates:
        timestamp = candidate.get(
            'timestamp'
        )

        if not isinstance(
            timestamp,
            (int, float),
        ):
            continue

        timestamp = float(
            timestamp
        )

        for start_value in (
            timestamp,
            timestamp
            -
            effective_duration,
            timestamp
            -
            effective_duration / 2.0,
        ):
            possible_starts.add(
                min(
                    latest_start,
                    max(
                        0.0,
                        start_value,
                    ),
                )
            )

    best = None

    for start_seconds in sorted(
        possible_starts
    ):
        end_seconds = min(
            track_duration,
            start_seconds
            +
            effective_duration,
        )

        window_candidates = [
            candidate
            for candidate
            in candidates
            if (
                isinstance(
                    candidate.get(
                        'timestamp'
                    ),
                    (int, float),
                )
                and
                start_seconds
                <=
                float(
                    candidate[
                        'timestamp'
                    ]
                )
                <=
                end_seconds
            )
        ]

        raw_scores = [
            max(
                0.0,
                float(
                    candidate.get(
                        'raw_change_score'
                    )
                    or
                    0.0
                ),
            )
            for candidate
            in window_candidates
        ]

        if raw_scores:
            salience_sum = sum(
                raw_scores
            )

            strongest = max(
                raw_scores
            )

            average = (
                salience_sum
                /
                len(
                    raw_scores
                )
            )

            thirds = [
                False,
                False,
                False,
            ]

            for candidate in window_candidates:
                relative = (
                    (
                        float(
                            candidate[
                                'timestamp'
                            ]
                        )
                        -
                        start_seconds
                    )
                    /
                    max(
                        effective_duration,
                        1.0,
                    )
                )

                third_index = min(
                    2,
                    max(
                        0,
                        int(
                            relative
                            *
                            3
                        ),
                    ),
                )

                thirds[
                    third_index
                ] = True

            coverage = (
                sum(
                    thirds
                )
                /
                3.0
            )

            score = (
                salience_sum
                +
                strongest
                *
                0.25
                +
                average
                *
                0.15
                +
                strongest
                *
                0.12
                *
                coverage
            )

        else:
            score = 0.0

        candidate_result = (
            score,
            len(
                window_candidates
            ),
            -start_seconds,
            start_seconds,
            end_seconds,
        )

        if (
            best is None
            or
            candidate_result
            >
            best
        ):
            best = (
                candidate_result
            )

    (
        _,
        candidate_count,
        _,
        start_seconds,
        end_seconds,
    ) = best

    return {
        'requested_duration_seconds':
            round(
                requested_duration,
                3,
            ),

        'duration_seconds':
            round(
                end_seconds
                -
                start_seconds,
                3,
            ),

        'start_seconds':
            round(
                start_seconds,
                3,
            ),

        'end_seconds':
            round(
                end_seconds,
                3,
            ),

        'track_duration_seconds':
            round(
                track_duration,
                3,
            ),

        'uses_excerpt':
            True,

        'window_score':
            round(
                best[0],
                6,
            ),

        'candidate_count':
            candidate_count,
    }


@app.get(
    '/pulsar/analyze/keypoints/{library_track_id}'
)
async def pulsar_analyze_keypoints(
    library_track_id: str,
    density: str | None = None,
    edit_duration_seconds: int | None = None,
    track_duration_seconds: int | None = None,
):
    """
    Map every measured transition inside Pulsar's selected source window.

    The legacy density query parameter is accepted but ignored so older
    clients do not break during the staging transition.
    """

    segment_response = (
        await pulsar_analyze_segments(
            library_track_id
        )
    )

    segments = (
        segment_response.get(
            'segments',
            [],
        )
    )

    if (
        not isinstance(
            segments,
            list,
        )
        or
        len(
            segments
        )
        <
        2
    ):
        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    (
                        'Pulsar needs at least two '
                        'audio-analysis segments to '
                        'calculate key moments.'
                    ),

                'stage':
                    'pulsar_keypoint_scoring',

                'build':
                    PULSAR_ANALYSIS_BUILD_ID,
            }
        )

    candidates = []
    score_weights = None
    transition_bonus_weights = None

    for index in range(
        1,
        len(
            segments
        ),
    ):
        previous_segment = (
            segments[
                index - 1
            ]
        )

        current_segment = (
            segments[
                index
            ]
        )

        change_data = (
            calculate_pulsar_segment_change(
                previous_segment,
                current_segment,
            )
        )

        score_weights = (
            change_data[
                'weights'
            ]
        )

        transition_bonus_weights = (
            change_data[
                'transition_bonus_weights'
            ]
        )

        candidates.append(
            {
                'segment_index':
                    current_segment.get(
                        'index'
                    ),

                'from_timestamp':
                    previous_segment.get(
                        'timestamp'
                    ),

                'timestamp':
                    current_segment.get(
                        'timestamp'
                    ),

                'raw_change_score':
                    change_data[
                        'raw_change_score'
                    ],

                'base_change_score':
                    change_data[
                        'base_change_score'
                    ],

                'transition_bonus':
                    change_data[
                        'transition_bonus'
                    ],

                'component_change':
                    change_data[
                        'component_change'
                    ],

                'signed_change':
                    change_data[
                        'signed_change'
                    ],

                'dominant_transitions':
                    change_data[
                        'dominant_transitions'
                    ],
            }
        )

    track_duration = (
        estimate_track_duration_from_segments(
            segments,
            track_duration_seconds,
        )
    )

    requested_duration = (
        edit_duration_seconds
        if edit_duration_seconds
        else
        track_duration
    )

    edit_window = (
        choose_pulsar_edit_window(
            candidates,
            track_duration,
            requested_duration,
        )
    )

    window_start = (
        edit_window[
            'start_seconds'
        ]
    )

    window_end = (
        edit_window[
            'end_seconds'
        ]
    )

    window_candidates = [
        candidate
        for candidate
        in candidates
        if (
            isinstance(
                candidate.get(
                    'timestamp'
                ),
                (int, float),
            )
            and
            window_start
            <=
            float(
                candidate[
                    'timestamp'
                ]
            )
            <=
            window_end
        )
    ]

    maximum_raw_score = max(
        (
            float(
                candidate.get(
                    'raw_change_score'
                )
                or
                0.0
            )
            for candidate
            in window_candidates
        ),
        default=0.0,
    )

    keypoints = []

    for candidate in window_candidates:
        raw_change_score = float(
            candidate.get(
                'raw_change_score'
            )
            or
            0.0
        )

        relative_score = (
            raw_change_score
            /
            maximum_raw_score
            *
            100.0
            if maximum_raw_score > 0
            else
            0.0
        )

        candidate[
            'change_score'
        ] = int(
            round(
                relative_score
            )
        )

        candidate[
            'tier'
        ] = (
            classify_pulsar_keypoint_tier(
                candidate[
                    'change_score'
                ]
            )
        )

        candidate[
            'raw_change_score'
        ] = round(
            raw_change_score,
            6,
        )

        candidate[
            'base_change_score'
        ] = round(
            candidate[
                'base_change_score'
            ],
            6,
        )

        candidate[
            'transition_bonus'
        ] = round(
            candidate[
                'transition_bonus'
            ],
            6,
        )

        # Exact zero-change boundaries are not meaningful keypoints.
        # Every non-zero measured transition is retained.
        if raw_change_score > 0:
            keypoints.append(
                candidate
            )

    keypoints.sort(
        key=lambda item:
            item[
                'timestamp'
            ]
    )

    tier_counts = {
        'primary':
            0,

        'secondary':
            0,

        'tertiary':
            0,
    }

    for keypoint in keypoints:
        tier = keypoint.get(
            'tier'
        )

        if tier in tier_counts:
            tier_counts[
                tier
            ] += 1

    return {
        'build':
            PULSAR_ANALYSIS_BUILD_ID,

        'library_track_id':
            library_track_id,

        'title':
            segment_response.get(
                'title'
            ),

        'analysis':
            segment_response.get(
                'analysis'
            ),

        'mode':
            'all-ranked-transitions',

        'legacy_density_ignored':
            density,

        'edit_window':
            edit_window,

        'selection': {
            'selected_count':
                len(
                    keypoints
                ),

            'window_candidate_count':
                len(
                    window_candidates
                ),

            'primary_count':
                tier_counts[
                    'primary'
                ],

            'secondary_count':
                tier_counts[
                    'secondary'
                ],

            'tertiary_count':
                tier_counts[
                    'tertiary'
                ],

            'fixed_target_count':
                False,

            'fixed_spacing':
                False,
        },

        'scoring': {
            'type':
                (
                    'within-selected-window relative '
                    'segment-change score'
                ),

            'range':
                '0-100',

            'tier_thresholds': {
                'primary':
                    '>=85',

                'secondary':
                    '60-84',

                'tertiary':
                    '<60',
            },

            'weights':
                score_weights,

            'transition_bonus_weights':
                transition_bonus_weights,
        },

        'keypoints':
            keypoints,

        'candidate_count':
            len(
                candidates
            ),

        'window_candidate_count':
            len(
                window_candidates
            ),
    }


@app.post(
    '/pulsar/signal/generate'
)
async def pulsar_signal_generate(
    payload: PulsarSignalRequest
):
    start_time = (
        time.perf_counter()
    )

    keypoint_response = (
        await pulsar_analyze_keypoints(
            library_track_id=
                payload.library_track_id,

            density=
                payload.density,

            edit_duration_seconds=
                payload.edit_duration_seconds,

            track_duration_seconds=
                payload.track_duration_seconds,
        )
    )

    keypoints = (
        keypoint_response.get(
            'keypoints'
        )
        or
        []
    )

    if not keypoints:
        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    (
                        'Pulsar did not find any usable '
                        'musical changes in the selected '
                        'edit window.'
                    ),

                'message':
                    (
                        'Try the track again or use a '
                        'different edit duration.'
                    ),

                'stage':
                    'pulsar_signal_generation',

                'build':
                    PULSAR_ANALYSIS_BUILD_ID,
            }
        )

    title = (
        keypoint_response.get(
            'title'
        )
    )

    analysis = (
        keypoint_response.get(
            'analysis'
        )
        or
        {}
    )

    edit_window = (
        keypoint_response.get(
            'edit_window'
        )
        or
        {}
    )

    qwen_start = (
        time.perf_counter()
    )

    qwen_signal = (
        await asyncio.to_thread(
            create_pulsar_signal_with_qwen,
            title,
            analysis,
            keypoints,
            payload.editing_context,
            edit_window,
        )
    )

    qwen_ms = round(
        (
            time.perf_counter()
            -
            qwen_start
        )
        *
        1000
    )

    total_ms = round(
        (
            time.perf_counter()
            -
            start_time
        )
        *
        1000
    )

    return {
        'build':
            PULSAR_ANALYSIS_BUILD_ID,

        'generated':
            True,

        'library_track_id':
            payload.library_track_id,

        'title':
            title,

        'keypoint_mode':
            'all-ranked-transitions',

        'editing_context':
            payload.editing_context,

        'analysis':
            analysis,

        'edit_window':
            edit_window,

        'selection':
            keypoint_response.get(
                'selection'
            ),

        'signal': {
            'summary':
                qwen_signal[
                    'signal_summary'
                ],

            'cue_count':
                len(
                    qwen_signal[
                        'cues'
                    ]
                ),

            'cues':
                qwen_signal[
                    'cues'
                ],
        },

        'timing_ms': {
            'qwen_interpretation':
                qwen_ms,

            'total':
                total_ms,
        },
    }


@app.get('/')
def root():
    return {'message': 'Syncora backend is running.', 'build': BUILD_ID, 'qwen_model': QWEN_MODEL_ID, 'embedding_model': EMBEDDING_MODEL_ID, 'nova_mode': 'six-tag-sigmoid-hybrid', 'pulsar_resolver': PULSAR_RESOLVER_BUILD_ID, 'pulsar_analysis': PULSAR_ANALYSIS_BUILD_ID}

@app.get('/test-llm')
def test_llm():
    try:
        completion = create_llm_completion(model=QWEN_MODEL_ID, messages=[{'role': 'user', 'content': 'Reply with exactly: Syncora backend can talk to Nova Qwen.'}], temperature=0, max_tokens=30)
        return {'build': BUILD_ID, 'model': QWEN_MODEL_ID, 'response': completion.choices[0].message.content}
    except Exception as error:
        raise HTTPException(status_code=502, detail={'error': 'Qwen health check failed.', 'message': str(error), 'build': BUILD_ID})

@app.get('/test-embed')
def test_embed():
    try:
        vectors = create_embedding_vectors(
            [
                'search_query: dreamy synthwave music',
                (
                    'search_document: atmospheric '
                    'electronic synthwave music'
                ),
            ]
        )

        similarity = cosine_similarity(
            vectors[0],
            vectors[1],
        )

        return {
            'build':
                BUILD_ID,

            'provider':
                EMBEDDING_PROVIDER,

            'model':
                EMBEDDING_MODEL_ID,

            'dimensions':
                len(
                    vectors[0]
                ),

            'similarity':
                round(
                    similarity,
                    4
                ),
        }

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    'Embedding health check failed.',

                'message':
                    str(error),

                'provider':
                    EMBEDDING_PROVIDER,

                'model':
                    EMBEDDING_MODEL_ID,

                'build':
                    BUILD_ID,
            }
        )

@app.get('/test-lastfm')
async def test_lastfm(tag: str='dreamy'):
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        result = await get_lastfm_tracks_for_tag(http_client=http_client, tag=tag, limit=10)
    if result['error']:
        raise HTTPException(status_code=502, detail={'error': 'Last.fm health check failed.', 'message': result['error'], 'build': BUILD_ID})
    return {'build': BUILD_ID, 'tag': tag, 'tracks': result['tracks']}

@app.get('/test-cyanite')
async def test_cyanite():
    if not CYANITE_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail={'error': 'CYANITE_ACCESS_TOKEN was not found.'})
    query = '\n    query SyncoraCyaniteHealthCheck {\n        libraryTracks(first: 1) {\n            pageInfo {\n                hasNextPage\n            }\n\n            edges {\n                node {\n                    id\n                }\n            }\n        }\n    }\n    '
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + CYANITE_ACCESS_TOKEN}
    body = {'query': query}
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        response = await http_client.post(CYANITE_API_URL, headers=headers, json=body)
    response.raise_for_status()
    data = response.json()
    if data.get('errors'):
        raise HTTPException(status_code=502, detail={'error': 'Cyanite rejected the GraphQL request.', 'cyanite_errors': data.get('errors')})
    return {'build': BUILD_ID, 'cyanite_authenticated': True, 'message': 'Syncora successfully authenticated with Cyanite.'}

@app.post('/nova/generate')
async def nova_generate(payload: NovaRequest):
    start = time.perf_counter()
    profile = await asyncio.to_thread(
    create_nova_profile,
    payload
)

    profile = (
        apply_nova_explicit_constraints(
            profile,
            payload,
        )
    )

    cache_nova_profile(
        payload,
        profile
    )
    cache_nova_profile(payload, profile)
    elapsed_ms = round((time.perf_counter() - start) * 1000)
    return {'build': BUILD_ID, 'model': QWEN_MODEL_ID, 'profile_source': 'qwen', 'timing_ms': {'qwen_profile': elapsed_ms}, 'profile': profile}

@app.post('/nova/recommend')
async def nova_recommend(payload: NovaRequest):
    total_start = time.perf_counter()
    warnings = []
    profile_start = time.perf_counter()
    profile = get_cached_nova_profile(payload)
    if profile is not None:
        profile_source = 'cache'
    else:
        profile_source = 'qwen'
        profile = await asyncio.to_thread(create_nova_profile, payload)
        cache_nova_profile(payload, profile)

    profile = (
        apply_nova_explicit_constraints(
            profile,
            payload,
        )
    )
    
    profile_ms = round((time.perf_counter() - profile_start) * 1000)
    search_start = time.perf_counter()
    search_bundle = await search_lastfm_all_usable(profile['retrieval_tags'])
    search_ms = round((time.perf_counter() - search_start) * 1000)
    active_retrieval_tags = search_bundle['active_tags']
    tag_results = search_bundle['tag_results']
    if search_bundle['failed_queries']:
        warnings.append({'stage': 'lastfm_search', 'message': 'One or more Last.fm tag queries failed, but Nova had enough remaining results.', 'failed_queries': search_bundle['failed_queries']})
    candidate_count = count_unique_initial_candidates(tag_results)
    shortlist, shortlist_debug = build_balanced_shortlist(tag_results, per_tag=2)
    if len(shortlist) < 3:
        raise HTTPException(status_code=502, detail={'error': 'Last.fm returned fewer than three unique shortlist candidates.', 'stage': 'shortlist', 'build': BUILD_ID})
    enrichment_start = time.perf_counter()
    enriched, enrichment_warnings = await enrich_shortlist_parallel(shortlist)
    warnings.extend(enrichment_warnings)
    enrichment_ms = round((time.perf_counter() - enrichment_start) * 1000)
    embedding_start = time.perf_counter()
    semantic_candidates, semantic_available, embedding_warning = await asyncio.to_thread(attach_semantic_similarity, profile, active_retrieval_tags, enriched)
    if embedding_warning:
        warnings.append(embedding_warning)
    embedding_ms = round((time.perf_counter() - embedding_start) * 1000)

    scored, scoring_weights = score_enriched_candidates(
        active_retrieval_tags,
        semantic_candidates,
        semantic_available,
        payload.vocal_style
    )

    calibration_debug = (
        build_nova_calibration_debug(
            scored
        )
    )

    recommendations = select_top_three(
        scored
    )
    
    total_ms = round((time.perf_counter() - total_start) * 1000)
    return {'build': BUILD_ID, 'qwen_model': QWEN_MODEL_ID, 'embedding_model': EMBEDDING_MODEL_ID, 'mode': 'six-tag-sigmoid-hybrid', 'profile_source': profile_source, 'profile': profile, 'retrieval_debug': {'requested_tags': profile['retrieval_tags'], 'active_tags': active_retrieval_tags, 'dead_tags': search_bundle['dead_tags'], 'failed_queries': search_bundle['failed_queries'], 'candidate_strategy': 'top-2-per-usable-tag'}, 'shortlist_debug': shortlist_debug, 'candidate_count': candidate_count, 'shortlist_count': len(shortlist), 'semantic_available': semantic_available, 'timing_ms': {'qwen_profile': profile_ms, 'lastfm_initial_search': search_ms, 'lastfm_enrichment': enrichment_ms, 'embedding_similarity': embedding_ms, 'total': total_ms}, 'scoring_weights': scoring_weights, **(
    {
        'calibration_debug':
            calibration_debug
    }

    if NOVA_DEBUG_RESPONSES

    else {}
), 'warnings': warnings, 'recommendation_count': len(recommendations), 'recommendations': recommendations}
