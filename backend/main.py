import os
from pathlib import Path
import asyncio
import hashlib
import json
import math
import re
import time
import threading
import httpx
from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAI
from pydantic import BaseModel, Field
from ytmusicapi import YTMusic
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


BUILD_ID = 'nova-hybrid-0.7.5'
PULSAR_RESOLVER_BUILD_ID = 'pulsar-ytmusic-resolver-0.2.0'
PULSAR_ANALYSIS_BUILD_ID = 'pulsar-signal-0.5.1'

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
print('Cyanite access token loaded:', bool(CYANITE_ACCESS_TOKEN))
print('==========================================')
if not LASTFM_API_KEY:
    raise RuntimeError(f'LASTFM_API_KEY could not be read from {ENV_PATH}')
app = FastAPI(title='Syncora Backend', version='0.7.5')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000', 'http://127.0.0.1:3000'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

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


ytmusic = YTMusic()

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
    density: str = Field(default='balanced', min_length=1, max_length=20)
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
    objective_payload = {'track_title': title, 'whole_track_analysis': analysis, 'editing_context': editing_context, 'edit_window': edit_window or {}, 'keypoints': [{'timestamp_seconds': keypoint.get('timestamp'), 'change_score': keypoint.get('change_score'), 'component_change': keypoint.get('component_change'), 'signed_change': keypoint.get('signed_change'), 'dominant_transitions': keypoint.get('dominant_transitions')} for keypoint in keypoints]}
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
                "You are Pulsar, Syncora's editing-cue interpreter. "
                "The supplied edit_window is authoritative for timing "
                "and may begin anywhere in the song. The editor does "
                "not need to restate duration or source-position rules "
                "inside editing_context. Treat editing_context purely "
                "as creative direction. Never invent timestamps or "
                "musical facts. Return valid JSON only."
            )
        },
        {
            'role': 'user',
            'content': prompt
        }
    ], temperature=0.2, top_p=0.8, max_tokens=1400)

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

        if (
            'Timeout' in error_name
            or
            'timeout' in error_text_lower
        ):
            raise HTTPException(
                status_code=504,
                detail={
                    'error':
                        "Pulsar's Qwen request timed out.",

                    'message':
                        (
                            'The local AI model did not finish '
                            'the Signal within the configured timeout.'
                        ),

                    'stage':
                        'pulsar_qwen_signal',

                    'retryable':
                        True,

                    'analysis_preserved':
                        True,

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

        if any(
            marker in error_text_lower
            for marker in mlx_crash_markers
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

                    'model':
                        QWEN_MODEL_ID,

                    'build':
                        PULSAR_ANALYSIS_BUILD_ID,
                }
            )

        raise HTTPException(
            status_code=502,
            detail={
                'error':
                    'Pulsar could not reach Qwen.',

                'message':
                    error_text,

                'stage':
                    'pulsar_qwen_signal',

                'retryable':
                    True,

                'analysis_preserved':
                    True,

                'model':
                    QWEN_MODEL_ID,

                'build':
                    PULSAR_ANALYSIS_BUILD_ID,
            }
        )
    
    if not completion.choices:
        raise HTTPException(status_code=502, detail={'error': 'LM Studio returned zero Pulsar choices.', 'stage': 'pulsar_qwen_validation', 'retryable': True, 'analysis_preserved': True, 'build': PULSAR_ANALYSIS_BUILD_ID})
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
        validated_cues.append({'cue_number': index + 1, 'timestamp_seconds': objective_timestamp, 'title': title_text.strip(), 'suggestion': suggestion_text.strip(), 'evidence': evidence_text.strip(), 'objective': {'change_score': keypoint.get('change_score'), 'component_change': keypoint.get('component_change'), 'signed_change': keypoint.get('signed_change'), 'dominant_transitions': keypoint.get('dominant_transitions')}})
    return {'signal_summary': signal_summary.strip(), 'cues': validated_cues}

def create_nova_profile(payload: NovaRequest):
    prompt = f"""\nYou are Nova, the music-discovery intelligence inside\nSyncora, a tool for video editors.\n\nAnalyze the editor's brief and produce two DIFFERENT\nkinds of music information.\n\n1. RETRIEVAL TAGS\n\nProduce exactly 6 established music tags that are likely\nto work as Last.fm search tags.\n\n2. SEMANTIC TRAITS\n\nProduce exactly 4 short descriptive qualities that\ndescribe the desired sound. These are used for semantic\nmatching and are NOT used directly as Last.fm searches.\n\n\nRETRIEVAL TAG RULES:\n\n- Use exactly 6.\n- Order them from strongest/specific to broader.\n- Use established genres, subgenres, styles, or common\n  music mood tags.\n- Prefer terms likely to exist on Last.fm.\n- Do not invent aesthetic phrases.\n- Do not use video terminology.\n- The six tags should represent complementary aspects\n  of the desired music where possible.\n\nBAD retrieval tags:\n\n"neon ambiance"\n"night drive music"\n"cinematic car edit"\n"city lights soundtrack"\n\nGOOD retrieval tags:\n\nsynthwave\ndream pop\nchillwave\nelectropop\nelectronic\natmospheric\ndarkwave\nshoegaze\nambient\ndowntempo\nindie pop\nalternative\nenergetic\n\n\nSEMANTIC TRAIT RULES:\n\n- Use exactly 4.\n- Keep each trait short.\n- They may describe atmosphere, texture, emotion,\n  momentum, build, payoff, sonic character, etc.\n- These ARE allowed to contain descriptive ideas that\n  would make poor Last.fm search tags.\n\nExamples:\n\n"neon nighttime atmosphere"\n"dreamy electronic texture"\n"gradual energetic build"\n"soft emotional vocals"\n\n\nGENERAL RULES:\n\n- Return valid JSON only.\n- Do not use Markdown.\n- Do not use code fences.\n- Do not recommend songs.\n- Do not recommend artists.\n- Do not explain your reasoning.\n- Keep everything concise.\n\nReturn exactly this JSON shape:\n\n{{\n    "retrieval_tags": [\n        "tag1",\n        "tag2",\n        "tag3",\n        "tag4",\n        "tag5",\n        "tag6"\n    ],\n    "semantic_traits": [\n        "trait1",\n        "trait2",\n        "trait3",\n        "trait4"\n    ],\n    "summary":\n        "one short sentence describing the desired music",\n    "energy":\n        "one short description",\n    "vocal_preference":\n        "one short description"\n}}\n\n\nEDITOR BRIEF\n\nProject:\n{payload.project_name}\n\nVideo type:\n{payload.video_type}\n\nDuration:\n{payload.target_duration_seconds} seconds\n\nMood:\n{payload.mood}\n\nPace:\n{payload.pace}\n\nVocals:\n{payload.vocal_style}\n\nStructure:\n{payload.structure_preference}\n\nCreative intent:\n{payload.creative_intent}\n"""
    try:
        completion = create_llm_completion(model=QWEN_MODEL_ID, messages=[{'role': 'system', 'content': "You are Nova, Syncora's music-discovery assistant. Return concise valid JSON only."}, {'role': 'user', 'content': prompt}], temperature=0.25, top_p=0.8, max_tokens=400)
    except Exception as error:
        error_name = type(error).__name__
        if 'Timeout' in error_name or 'timeout' in str(error).lower():
            raise HTTPException(status_code=504, detail={'error': "Nova's Qwen request timed out.", 'stage': 'qwen_profile', 'message': 'LM Studio did not complete the profile generation within the configured timeout.', 'model': QWEN_MODEL_ID, 'build': BUILD_ID})
        raise HTTPException(status_code=502, detail={'error': 'Nova could not reach Qwen.', 'stage': 'qwen_profile', 'message': str(error), 'model': QWEN_MODEL_ID, 'build': BUILD_ID})
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
        if tag.get('name')
    ]

    if not tag_names:
        tag_names = [
            match['tag']
            for match
            in candidate.get(
                'retrieval_matches',
                []
            )
        ]

    document_text = (
        'Candidate music profile. '
        'Music tags and qualities: '
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

def attach_semantic_similarity(profile, active_retrieval_tags, candidates):
    query = build_embedding_query(profile, active_retrieval_tags)
    documents = [build_candidate_embedding_document(candidate) for candidate in candidates]
    texts = [query, *documents]
    try:
        vectors = create_embedding_vectors(
            texts
        )
        
        if len(vectors) != len(texts):
            raise ValueError('Embedding model returned an unexpected vector count.')
        query_vector = vectors[0]
        semantic_candidates = []
        for candidate, vector in zip(candidates, vectors[1:]):
            candidate_copy = dict(candidate)
            candidate_copy['semantic_similarity'] = cosine_similarity(query_vector, vector)
            semantic_candidates.append(candidate_copy)
        return (semantic_candidates, True, None)
    except Exception as error:
        fallback_candidates = []
        for candidate in candidates:
            candidate_copy = dict(candidate)
            candidate_copy['semantic_similarity'] = None
            fallback_candidates.append(candidate_copy)
        warning = {'stage': 'embedding_similarity', 'message': 'Semantic embeddings were unavailable. Nova used Last.fm evidence only.', 'technical_error': str(error)}
        return (fallback_candidates, False, warning)

def calibrate_semantic_similarity(similarity):
    if similarity is None:
        return 0.0
    midpoint = 0.78
    steepness = 30.0
    exponent = -steepness * (similarity - midpoint)
    exponent = min(60.0, max(-60.0, exponent))
    return 1.0 / (1.0 + math.exp(exponent))

def score_enriched_candidates(active_retrieval_tags, enriched_candidates, semantic_available):
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
        retrieval_points = min(retrieval_max_points, retrieval_evidence / 1.4 * retrieval_max_points)
        score = tag_evidence_points + semantic_points + retrieval_points
        score = int(round(min(99, max(0, score))))
        scored.append({'title': candidate['title'], 'artist': candidate['artist'], 'match_score': score, 'semantic_similarity': round(raw_semantic_similarity, 4) if raw_semantic_similarity is not None else None, 'semantic_fit': round(semantic_fit, 4) if semantic_available else None, 'score_breakdown': {'lastfm_tag_evidence': round(tag_evidence_points, 2), 'semantic_fit': round(semantic_points, 2), 'lastfm_retrieval': round(retrieval_points, 2)}, 'matched_nova_tags': [match['nova_tag'] for match in matched_desired], 'match_evidence': matched_desired, 'retrieval_matches': candidate['retrieval_matches'], 'top_lastfm_tags': top_tags[:8], 'lastfm_url': candidate['lastfm_url'], 'mbid': candidate['mbid']})
    scored.sort(key=lambda item: (item['match_score'], item['semantic_similarity'] or 0, len(item['matched_nova_tags'])), reverse=True)
    return (scored, {'lastfm_tag_evidence': round(tag_max_points, 2), 'semantic_similarity': round(semantic_max_points, 2), 'lastfm_retrieval': round(retrieval_max_points, 2)})

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
        matched_tags = candidate['matched_nova_tags']
        semantic_similarity = candidate['semantic_similarity']
        if matched_tags and semantic_similarity is not None:
            reason = "Last.fm's track-specific tags matched Nova's retrieval profile on " + ', '.join(matched_tags) + f', with semantic similarity {semantic_similarity:.2f}.'
        elif matched_tags:
            reason = "Last.fm's track-specific tags matched Nova's retrieval profile on " + ', '.join(matched_tags) + '.'
        elif semantic_similarity is not None:
            reason = f"The track's Last.fm music profile showed semantic compatibility with Nova's desired sound ({semantic_similarity:.2f})."
        else:
            reason = "The track ranked strongly in Nova's Last.fm retrieval results."
        recommendations.append({'rank': rank, 'title': candidate['title'], 'artist': candidate['artist'], 'match_score': candidate['match_score'], 'reason': reason, 'semantic_similarity': candidate['semantic_similarity'], 'semantic_fit': candidate['semantic_fit'], 'score_breakdown': candidate['score_breakdown'], 'matched_tags': matched_tags, 'top_lastfm_tags': candidate['top_lastfm_tags'], 'match_evidence': candidate['match_evidence'], 'lastfm_url': candidate['lastfm_url'], 'mbid': candidate['mbid']})
    if len(recommendations) != 3:
        raise HTTPException(status_code=500, detail={'error': "Nova's final selection did not contain exactly three songs.", 'stage': 'final_selection', 'recommendation_count': len(recommendations), 'build': BUILD_ID})
    return recommendations

def normalize_ytmusic_text(value: str):
    value = str(value or '').casefold().strip()
    value = re.sub('[^a-z0-9]+', ' ', value)
    value = re.sub('\\s+', ' ', value)
    return value.strip()

def score_ytmusic_result(result: dict, desired_title: str, desired_artist: str):
    result_title = normalize_ytmusic_text(result.get('title', ''))
    result_artists = [normalize_ytmusic_text(artist.get('name', '')) for artist in result.get('artists', []) or [] if isinstance(artist, dict)]
    title_score = 0.0
    artist_score = 0.0
    if result_title == desired_title:
        title_score = 0.6
    elif desired_title and result_title and (desired_title in result_title or result_title in desired_title):
        title_score = 0.35
    if desired_artist in result_artists:
        artist_score = 0.35
    elif any((desired_artist and result_artist and (desired_artist in result_artist or result_artist in desired_artist) for result_artist in result_artists)):
        artist_score = 0.2
    playable_bonus = 0.05 if result.get('videoId') else 0.0
    score = title_score + artist_score + playable_bonus
    return round(min(score, 1.0), 4)

def normalize_ytmusic_result(result: dict, match_score: float):
    artists = [artist.get('name') for artist in result.get('artists', []) or [] if isinstance(artist, dict) and artist.get('name')]
    artist_ids = [artist.get('id') for artist in result.get('artists', []) or [] if isinstance(artist, dict) and artist.get('id')]
    album = result.get('album')
    album_name = album.get('name') if isinstance(album, dict) else None
    album_id = album.get('id') if isinstance(album, dict) else None
    video_id = result.get('videoId')
    youtube_music_url = f'https://music.youtube.com/watch?v={video_id}' if video_id else None
    return {'title': result.get('title'), 'artists': artists, 'artist_ids': artist_ids, 'album': album_name, 'album_id': album_id, 'duration': result.get('duration'), 'duration_seconds': result.get('duration_seconds'), 'video_id': video_id, 'youtube_music_url': youtube_music_url, 'is_explicit': result.get('isExplicit'), 'match_score': match_score}

@app.post('/pulsar/resolve')
async def pulsar_resolve(payload: PulsarResolveRequest):
    start_time = time.perf_counter()
    desired_title = normalize_ytmusic_text(payload.title)
    desired_artist = normalize_ytmusic_text(payload.artist)

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
                    str(
                        video_id
                    ),

                'youtube_music_url':
                    (
                        cached_track.get(
                            'youtube_music_url'
                        )
                        or
                        cached_track.get(
                            'youtube_url'
                        )
                        or
                        (
                            'https://music.youtube.com/'
                            f'watch?v={video_id}'
                        )
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
            }

            total_ms = round(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000
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
    query = f'{payload.artist} {payload.title}'.strip()
    try:
        search_results = await asyncio.to_thread(ytmusic.search, query, filter='songs', limit=20)
    except Exception as error:
        raise HTTPException(status_code=502, detail={'error': 'Pulsar could not search YouTube Music.', 'stage': 'pulsar_ytmusic_search', 'technical_error': str(error), 'build': PULSAR_RESOLVER_BUILD_ID})
    if not search_results:
        raise HTTPException(status_code=404, detail={'error': 'YouTube Music returned no song results.', 'stage': 'pulsar_ytmusic_search', 'query': query, 'build': PULSAR_RESOLVER_BUILD_ID})
    scored_results = []
    for result in search_results:
        if not isinstance(result, dict):
            continue
        match_score = score_ytmusic_result(result, desired_title, desired_artist)
        scored_results.append((match_score, result))
    scored_results.sort(key=lambda item: item[0], reverse=True)
    if not scored_results:
        raise HTTPException(status_code=404, detail={'error': 'Pulsar could not identify a usable YouTube Music result.', 'stage': 'pulsar_ytmusic_match', 'build': PULSAR_RESOLVER_BUILD_ID})
    best_score, best_result = scored_results[0]
    if best_score < 0.8:
        candidates = [normalize_ytmusic_result(result, score) for score, result in scored_results[:5]]
        raise HTTPException(status_code=404, detail={'error': 'YouTube Music returned results, but Pulsar could not confidently match the selected Nova song.', 'stage': 'pulsar_ytmusic_match', 'requested': {'title': payload.title, 'artist': payload.artist}, 'best_match_score': best_score, 'candidates': candidates, 'build': PULSAR_RESOLVER_BUILD_ID})
    resolved_track = normalize_ytmusic_result(best_result, best_score)
    if not resolved_track.get('video_id'):
        raise HTTPException(status_code=404, detail={'error': 'The matched YouTube Music song does not have a usable video ID.', 'stage': 'pulsar_ytmusic_match', 'build': PULSAR_RESOLVER_BUILD_ID})
    total_ms = round((time.perf_counter() - start_time) * 1000)
    return {'build': PULSAR_RESOLVER_BUILD_ID, 'resolved': True, 'source': 'YouTube Music', 'requested': {'title': payload.title, 'artist': payload.artist, 'mbid': payload.mbid}, 'track': resolved_track, 'timing_ms': {'total': total_ms}}

@app.post('/pulsar/analyze/start')
async def pulsar_analyze_start(payload: PulsarResolveRequest):
    start_time = time.perf_counter()
    resolution = await pulsar_resolve(payload)
    resolved_track = resolution.get('track', {})
    video_id = resolved_track.get('video_id')
    if not video_id:
        raise HTTPException(status_code=502, detail={'error': 'Pulsar resolved the song but did not receive a YouTube video ID.', 'stage': 'pulsar_ytmusic_resolution', 'build': PULSAR_ANALYSIS_BUILD_ID})
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
            # YouTube Music returned anything newer.
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


def get_pulsar_density_plan(density_key, edit_duration_seconds):
    profiles = {
        'minimal': {'seconds_per_cue': 15.0, 'minimum_cues': 2, 'maximum_cues': 8, 'minimum_change_score': 50, 'spacing_factor': 0.7},
        'balanced': {'seconds_per_cue': 10.0, 'minimum_cues': 3, 'maximum_cues': 12, 'minimum_change_score': 35, 'spacing_factor': 0.6},
        'detailed': {'seconds_per_cue': 7.0, 'minimum_cues': 4, 'maximum_cues': 16, 'minimum_change_score': 20, 'spacing_factor': 0.5},
    }
    profile = profiles[density_key]
    duration = max(float(edit_duration_seconds or 0), 1.0)
    target_count = int(round(duration / profile['seconds_per_cue']))
    target_count = max(profile['minimum_cues'], min(profile['maximum_cues'], target_count))
    minimum_spacing_seconds = max(3, int(round((duration / (target_count + 1)) * profile['spacing_factor'])))
    return {
        'target_count': target_count,
        'minimum_spacing_seconds': minimum_spacing_seconds,
        'minimum_change_score': profile['minimum_change_score'],
        'seconds_per_cue': profile['seconds_per_cue'],
    }


def choose_pulsar_edit_window(candidates, track_duration_seconds, requested_duration_seconds, target_count):
    track_duration = max(float(track_duration_seconds or 0), 0.0)
    requested_duration = float(requested_duration_seconds) if isinstance(requested_duration_seconds, (int, float)) and requested_duration_seconds > 0 else track_duration
    if track_duration <= 0:
        track_duration = max((float(candidate.get('timestamp')) for candidate in candidates if isinstance(candidate.get('timestamp'), (int, float))), default=requested_duration)
    if requested_duration <= 0:
        requested_duration = track_duration
    effective_duration = min(requested_duration, track_duration) if track_duration > 0 else requested_duration
    if effective_duration <= 0:
        effective_duration = track_duration
    if not candidates or track_duration <= 0 or effective_duration >= track_duration - 0.5:
        return {
            'requested_duration_seconds': round(requested_duration, 3) if requested_duration else None,
            'duration_seconds': round(track_duration, 3),
            'start_seconds': 0.0,
            'end_seconds': round(track_duration, 3),
            'track_duration_seconds': round(track_duration, 3),
            'uses_excerpt': False,
            'window_score': None,
        }
    latest_start = max(0.0, track_duration - effective_duration)
    possible_starts = {0.0, latest_start}
    for candidate in candidates:
        timestamp = candidate.get('timestamp')
        if not isinstance(timestamp, (int, float)):
            continue
        timestamp = float(timestamp)
        for start_value in (timestamp, timestamp - effective_duration, timestamp - effective_duration / 2.0):
            possible_starts.add(min(latest_start, max(0.0, start_value)))
    best = None
    for start_seconds in sorted(possible_starts):
        end_seconds = min(track_duration, start_seconds + effective_duration)
        window_candidates = [candidate for candidate in candidates if isinstance(candidate.get('timestamp'), (int, float)) and start_seconds <= float(candidate['timestamp']) <= end_seconds]
        ranked_scores = sorted((max(0.0, float(candidate.get('raw_change_score') or 0.0)) for candidate in window_candidates), reverse=True)
        top_scores = ranked_scores[:max(1, target_count)]
        top_score_sum = sum(top_scores)
        supporting_score = sum(ranked_scores[max(1, target_count):]) * 0.15
        if window_candidates:
            thirds = [False, False, False]
            for candidate in window_candidates:
                relative = (float(candidate['timestamp']) - start_seconds) / max(effective_duration, 1.0)
                third_index = min(2, max(0, int(relative * 3)))
                thirds[third_index] = True
            coverage = sum(thirds) / 3.0
        else:
            coverage = 0.0
        strongest = ranked_scores[0] if ranked_scores else 0.0
        coverage_bonus = strongest * 0.12 * coverage
        score = top_score_sum + supporting_score + coverage_bonus
        candidate_result = (score, len(window_candidates), -start_seconds, start_seconds, end_seconds)
        if best is None or candidate_result > best:
            best = candidate_result
    _, candidate_count, _, start_seconds, end_seconds = best
    return {
        'requested_duration_seconds': round(requested_duration, 3),
        'duration_seconds': round(end_seconds - start_seconds, 3),
        'start_seconds': round(start_seconds, 3),
        'end_seconds': round(end_seconds, 3),
        'track_duration_seconds': round(track_duration, 3),
        'uses_excerpt': True,
        'window_score': round(best[0], 6),
        'candidate_count': candidate_count,
    }


@app.get('/pulsar/analyze/keypoints/{library_track_id}')
async def pulsar_analyze_keypoints(library_track_id: str, density: str='balanced', edit_duration_seconds: int | None=None, track_duration_seconds: int | None=None):
    density_key = density.strip().casefold()
    if density_key not in ['minimal', 'balanced', 'detailed']:
        raise HTTPException(status_code=422, detail={'error': 'Invalid Pulsar cue density.', 'allowed_values': ['minimal', 'balanced', 'detailed'], 'build': PULSAR_ANALYSIS_BUILD_ID})
    segment_response = await pulsar_analyze_segments(library_track_id)
    segments = segment_response.get('segments', [])
    if not isinstance(segments, list) or len(segments) < 2:
        raise HTTPException(status_code=502, detail={'error': 'Pulsar needs at least two Cyanite segments to calculate key moments.', 'stage': 'pulsar_keypoint_scoring', 'build': PULSAR_ANALYSIS_BUILD_ID})
    candidates = []
    score_weights = None
    transition_bonus_weights = None
    for index in range(1, len(segments)):
        previous_segment = segments[index - 1]
        current_segment = segments[index]
        change_data = calculate_pulsar_segment_change(previous_segment, current_segment)
        score_weights = change_data['weights']
        transition_bonus_weights = change_data['transition_bonus_weights']
        candidates.append({'segment_index': current_segment.get('index'), 'from_timestamp': previous_segment.get('timestamp'), 'timestamp': current_segment.get('timestamp'), 'raw_change_score': change_data['raw_change_score'], 'base_change_score': change_data['base_change_score'], 'transition_bonus': change_data['transition_bonus'], 'component_change': change_data['component_change'], 'signed_change': change_data['signed_change'], 'dominant_transitions': change_data['dominant_transitions']})
    track_duration = estimate_track_duration_from_segments(segments, track_duration_seconds)
    requested_duration = edit_duration_seconds if edit_duration_seconds else track_duration
    effective_duration = min(float(requested_duration or track_duration), track_duration) if track_duration > 0 else float(requested_duration or 0)
    density_plan = get_pulsar_density_plan(density_key, effective_duration)
    edit_window = choose_pulsar_edit_window(candidates, track_duration, requested_duration, density_plan['target_count'])
    window_start = edit_window['start_seconds']
    window_end = edit_window['end_seconds']
    window_candidates = [candidate for candidate in candidates if isinstance(candidate.get('timestamp'), (int, float)) and window_start <= float(candidate['timestamp']) <= window_end]
    maximum_raw_score = max((candidate['raw_change_score'] for candidate in window_candidates), default=0.0)
    for candidate in window_candidates:
        relative_score = candidate['raw_change_score'] / maximum_raw_score * 100.0 if maximum_raw_score > 0 else 0.0
        candidate['change_score'] = int(round(relative_score))
        candidate['raw_change_score'] = round(candidate['raw_change_score'], 6)
        candidate['base_change_score'] = round(candidate['base_change_score'], 6)
        candidate['transition_bonus'] = round(candidate['transition_bonus'], 6)
    ranked_candidates = sorted(window_candidates, key=lambda item: (item['change_score'], len(item['dominant_transitions']), item['raw_change_score']), reverse=True)
    target_count = density_plan['target_count']
    minimum_spacing_seconds = density_plan['minimum_spacing_seconds']
    minimum_change_score = density_plan['minimum_change_score']
    selected = []
    for candidate in ranked_candidates:
        if candidate['change_score'] < minimum_change_score:
            continue
        timestamp = candidate.get('timestamp')
        if not isinstance(timestamp, (int, float)):
            continue
        spaced_enough = all(abs(timestamp - selected_candidate['timestamp']) >= minimum_spacing_seconds for selected_candidate in selected)
        if not spaced_enough:
            continue
        selected.append(candidate)
        if len(selected) >= target_count:
            break
    if len(selected) < min(target_count, len(ranked_candidates)):
        for candidate in ranked_candidates:
            if candidate in selected:
                continue
            timestamp = candidate.get('timestamp')
            if not isinstance(timestamp, (int, float)):
                continue
            relaxed_spacing = max(2, minimum_spacing_seconds // 2)
            spaced_enough = all(abs(timestamp - selected_candidate['timestamp']) >= relaxed_spacing for selected_candidate in selected)
            if not spaced_enough:
                continue
            selected.append(candidate)
            if len(selected) >= target_count:
                break
    selected.sort(key=lambda item: item['timestamp'])
    rejected_for_low_salience = [{'timestamp': candidate['timestamp'], 'change_score': candidate['change_score']} for candidate in ranked_candidates if candidate['change_score'] < minimum_change_score]
    return {'build': PULSAR_ANALYSIS_BUILD_ID, 'library_track_id': library_track_id, 'title': segment_response.get('title'), 'analysis': segment_response.get('analysis'), 'density': density_key, 'edit_window': edit_window, 'selection': {'target_count': target_count, 'minimum_spacing_seconds': minimum_spacing_seconds, 'minimum_change_score': minimum_change_score, 'seconds_per_cue': density_plan['seconds_per_cue'], 'selected_count': len(selected), 'target_reached': len(selected) >= target_count}, 'scoring': {'type': 'within-selected-window relative segment-change score', 'range': '0-100', 'weights': score_weights, 'transition_bonus_weights': transition_bonus_weights}, 'keypoints': selected, 'candidate_count': len(candidates), 'window_candidate_count': len(window_candidates), 'rejected_for_low_salience': rejected_for_low_salience}


@app.post('/pulsar/signal/generate')
async def pulsar_signal_generate(payload: PulsarSignalRequest):
    start_time = time.perf_counter()
    density_key = payload.density.strip().casefold()
    if density_key not in ['minimal', 'balanced', 'detailed']:
        raise HTTPException(status_code=422, detail={'error': 'Invalid Pulsar cue density.', 'allowed_values': ['minimal', 'balanced', 'detailed'], 'build': PULSAR_ANALYSIS_BUILD_ID})
    keypoint_response = await pulsar_analyze_keypoints(library_track_id=payload.library_track_id, density=density_key, edit_duration_seconds=payload.edit_duration_seconds, track_duration_seconds=payload.track_duration_seconds)
    keypoints = keypoint_response.get('keypoints') or []
    if not keypoints:
        raise HTTPException(status_code=502, detail={'error': 'Pulsar did not find any usable key moments in the selected edit window.', 'stage': 'pulsar_signal_generation', 'build': PULSAR_ANALYSIS_BUILD_ID})
    title = keypoint_response.get('title')
    analysis = keypoint_response.get('analysis') or {}
    edit_window = keypoint_response.get('edit_window') or {}
    qwen_start = time.perf_counter()
    qwen_signal = await asyncio.to_thread(create_pulsar_signal_with_qwen, title, analysis, keypoints, payload.editing_context, edit_window)
    qwen_ms = round((time.perf_counter() - qwen_start) * 1000)
    total_ms = round((time.perf_counter() - start_time) * 1000)
    return {'build': PULSAR_ANALYSIS_BUILD_ID, 'generated': True, 'library_track_id': payload.library_track_id, 'title': title, 'density': density_key, 'editing_context': payload.editing_context, 'analysis': analysis, 'edit_window': edit_window, 'selection': keypoint_response.get('selection'), 'signal': {'summary': qwen_signal['signal_summary'], 'cue_count': len(qwen_signal['cues']), 'cues': qwen_signal['cues']}, 'timing_ms': {'qwen_interpretation': qwen_ms, 'total': total_ms}}

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
    profile = await asyncio.to_thread(create_nova_profile, payload)
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
    scored, scoring_weights = score_enriched_candidates(active_retrieval_tags, semantic_candidates, semantic_available)
    recommendations = select_top_three(scored)
    total_ms = round((time.perf_counter() - total_start) * 1000)
    return {'build': BUILD_ID, 'qwen_model': QWEN_MODEL_ID, 'embedding_model': EMBEDDING_MODEL_ID, 'mode': 'six-tag-sigmoid-hybrid', 'profile_source': profile_source, 'profile': profile, 'retrieval_debug': {'requested_tags': profile['retrieval_tags'], 'active_tags': active_retrieval_tags, 'dead_tags': search_bundle['dead_tags'], 'failed_queries': search_bundle['failed_queries'], 'candidate_strategy': 'top-2-per-usable-tag'}, 'shortlist_debug': shortlist_debug, 'candidate_count': candidate_count, 'shortlist_count': len(shortlist), 'semantic_available': semantic_available, 'timing_ms': {'qwen_profile': profile_ms, 'lastfm_initial_search': search_ms, 'lastfm_enrichment': enrichment_ms, 'embedding_similarity': embedding_ms, 'total': total_ms}, 'scoring_weights': scoring_weights, 'warnings': warnings, 'recommendation_count': len(recommendations), 'recommendations': recommendations}