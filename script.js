const SUPABASE_URL = 'https://phxusxkhzxllrioxuzkr.supabase.co';
const SUPABASE_KEY = 'sb_publishable_3GHRzFe9g3kgcvTaeTBtyQ_GDih979C';
const db = supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

const PAGE_KIND = document.body.dataset.pageKind || 'protected';
const CURRENT_PAGE = document.body.dataset.page || '';
const AUTH_PAGE_URL = new URL('./index.html', window.location.href).href;
const APP_HOME_URL = new URL('./launchpad.html', window.location.href).href;
const AUTH_REDIRECT_URL = AUTH_PAGE_URL;

function routeTo(relativePath, { replace = false } = {}) {
    const destination = new URL(relativePath, window.location.href).href;

    if (replace) {
        window.location.replace(destination);
    } else {
        window.location.assign(destination);
    }
}

// =====================================================
// SUPABASE AUTHENTICATION
// =====================================================

const authDisplayNameInput = document.getElementById('accountDisplayName');
const authEmailInput = document.getElementById('accountEmail');
const authPasswordInput = document.getElementById('accountPassword');
const authForm = document.getElementById('accountForm');
const authSignupButton = document.getElementById('accountSignupButton');
const authMessage = document.getElementById('accountAuthMessage');
const profileDisplayNameInput = document.getElementById('profileDisplayName');
const saveDisplayNameButton = document.getElementById('saveDisplayNameButton');
const displayNameMessage = document.getElementById('displayNameMessage');

function setAuthMessage(message = '', type = '') {
    if (!authMessage) return;

    authMessage.textContent = message;
    authMessage.classList.remove('error', 'success');

    if (type) {
        authMessage.classList.add(type);
    }
}

function getAccountDisplayName(user) {
    const metadataName =
        user?.user_metadata?.display_name ||
        user?.user_metadata?.full_name ||
        user?.user_metadata?.name;

    if (metadataName) {
        return metadataName;
    }

    const emailName = user?.email?.split('@')[0] || 'Editor';

    return emailName
        .replace(/[._-]+/g, ' ')
        .replace(/\b\w/g, character => character.toUpperCase());
}

function revealAuthenticatedPage() {
    document.body.classList.remove('auth-pending');
}

function updateAuthUI(session) {
    const user = session?.user || null;

    if (!user) {
        if (PAGE_KIND === 'protected') {
            routeTo('./index.html', { replace: true });
            return;
        }

        document.getElementById('signedOutAccount')?.classList.remove('hidden');
        revealAuthenticatedPage();
        return;
    }

    if (PAGE_KIND === 'auth') {
        routeTo('./launchpad.html', { replace: true });
        return;
    }

    const displayName = getAccountDisplayName(user);
    const signedInName = document.getElementById('signedInName');
    const signedInEmail = document.getElementById('signedInEmail');
    const navAccountName = document.getElementById('navAccountName');
    const navAccountEmail = document.getElementById('navAccountEmail');
    const navAccountAvatar = document.getElementById('navAccountAvatar');

    if (signedInName) signedInName.textContent = displayName;
    if (signedInEmail) signedInEmail.textContent = user.email || '';
    if (navAccountName) navAccountName.textContent = displayName;
    if (navAccountEmail) navAccountEmail.textContent = user.email || 'Signed in';
    if (navAccountAvatar) navAccountAvatar.textContent = displayName.charAt(0).toUpperCase();
    if (profileDisplayNameInput) profileDisplayNameInput.value = displayName;

    const launchDisplayName = document.getElementById('launchDisplayName');
    if (launchDisplayName) launchDisplayName.textContent = displayName;

    if (displayNameMessage) {
        displayNameMessage.textContent = '';
        displayNameMessage.classList.remove('error', 'success');
    }

    setAuthMessage();
    revealAuthenticatedPage();
}

async function signUp() {
    const displayName = authDisplayNameInput?.value.trim() || '';
    const email = authEmailInput?.value.trim();
    const password = authPasswordInput?.value || '';

    if (!displayName) {
        setAuthMessage('Choose a display name for your Syncora workspace.', 'error');
        authDisplayNameInput?.focus();
        return;
    }

    if (!email || !password) {
        setAuthMessage('Please enter an email and password.', 'error');
        return;
    }

    if (password.length < 6) {
        setAuthMessage('Your password must be at least 6 characters.', 'error');
        return;
    }

    setAuthMessage('Creating your account...');
    authSignupButton?.setAttribute('disabled', '');

    try {
        const { data, error } = await db.auth.signUp({
            email,
            password,
            options: {
                emailRedirectTo: AUTH_REDIRECT_URL,
                data: {
                    display_name: displayName
                }
            }
        });

        if (error) {
            const message = error.message?.toLowerCase() || '';

            if (message.includes('already registered') || message.includes('already exists')) {
                setAuthMessage('An account with this email already exists. Log in instead.', 'error');
                return;
            }

            setAuthMessage(error.message || "We couldn't create your account. Please try again.", 'error');
            console.error('Signup error:', error);
            return;
        }

        const identities = data?.user?.identities;

        if (data?.user && Array.isArray(identities) && identities.length === 0) {
            setAuthMessage('An account with this email already exists. Log in instead.', 'error');
            if (authPasswordInput) authPasswordInput.value = '';
            return;
        }

        if (data?.session) {
            setAuthMessage('Account created. Opening your workspace…', 'success');
            return;
        }

        if (data?.user && Array.isArray(identities) && identities.length > 0) {
            if (authPasswordInput) authPasswordInput.value = '';
            setAuthMessage('Account created. Check your email to confirm your address, then sign in.', 'success');
            return;
        }

        setAuthMessage("We couldn't confirm whether your account was created. Please try again.", 'error');
    } catch (error) {
        console.error('Unexpected signup error:', error);
        setAuthMessage('Something went wrong while creating your account. Please try again.', 'error');
    } finally {
        authSignupButton?.removeAttribute('disabled');
    }
}

async function logIn(event) {
    event?.preventDefault();

    const email = authEmailInput?.value.trim();
    const password = authPasswordInput?.value || '';

    if (!email || !password) {
        setAuthMessage('Please enter your email and password.', 'error');
        return;
    }

    const loginButton = document.getElementById('accountLoginButton');
    loginButton?.setAttribute('disabled', '');
    setAuthMessage('Signing you in...');

    try {
        const { error } = await db.auth.signInWithPassword({ email, password });

        if (error) {
            setAuthMessage(error.message || 'Could not sign in. Please try again.', 'error');
            console.error('Login error:', error);
            return;
        }

        if (authPasswordInput) authPasswordInput.value = '';
        setAuthMessage('Signed in. Opening your workspace…', 'success');
    } catch (error) {
        console.error('Unexpected login error:', error);
        setAuthMessage('Could not reach the account service. Check your connection and try again.', 'error');
    } finally {
        loginButton?.removeAttribute('disabled');
    }
}

async function logOut() {
    const logoutButton = document.getElementById('signOutButton');
    logoutButton?.setAttribute('disabled', '');

    try {
        const { error } = await db.auth.signOut();

        if (error) {
            showToast('Could not log out. Please try again.');
            console.error('Logout error:', error);
            return;
        }
    } catch (error) {
        console.error('Unexpected logout error:', error);
        showToast('Could not reach the account service.');
    } finally {
        logoutButton?.removeAttribute('disabled');
    }
}

async function saveDisplayName() {
    if (!profileDisplayNameInput) {
        return;
    }

    const displayName = profileDisplayNameInput.value.trim();

    if (!displayName) {
        if (displayNameMessage) {
            displayNameMessage.textContent = 'Display name cannot be empty.';
            displayNameMessage.classList.remove('success');
            displayNameMessage.classList.add('error');
        }
        profileDisplayNameInput.focus();
        return;
    }

    saveDisplayNameButton?.setAttribute('disabled', '');

    if (displayNameMessage) {
        displayNameMessage.textContent = 'Saving…';
        displayNameMessage.classList.remove('error', 'success');
    }

    try {
        const { data, error } = await db.auth.updateUser({
            data: {
                display_name: displayName
            }
        });

        if (error) {
            console.error('Display-name update error:', error);

            if (displayNameMessage) {
                displayNameMessage.textContent = error.message || 'Could not update your display name.';
                displayNameMessage.classList.remove('success');
                displayNameMessage.classList.add('error');
            }
            return;
        }

        if (data?.user) {
            updateAuthUI({ user: data.user });
        }

        if (displayNameMessage) {
            displayNameMessage.textContent = 'Display name saved.';
            displayNameMessage.classList.remove('error');
            displayNameMessage.classList.add('success');
        }

        showToast(`Hello, ${displayName}.`);
    } catch (error) {
        console.error('Unexpected display-name update error:', error);

        if (displayNameMessage) {
            displayNameMessage.textContent = 'Could not reach the account service.';
            displayNameMessage.classList.remove('success');
            displayNameMessage.classList.add('error');
        }
    } finally {
        saveDisplayNameButton?.removeAttribute('disabled');
    }
}

authForm?.addEventListener('submit', logIn);
authSignupButton?.addEventListener('click', signUp);
document.getElementById('signOutButton')?.addEventListener('click', logOut);
saveDisplayNameButton?.addEventListener('click', saveDisplayName);

async function initializeAuth() {
    try {
        const { data: { session }, error } = await db.auth.getSession();

        if (error) {
            console.error('Session error:', error);
            updateAuthUI(null);
            return;
        }

        updateAuthUI(session);
    } catch (error) {
        console.error('Unexpected session initialization error:', error);
        updateAuthUI(null);
    }
}

initializeAuth();

db.auth.onAuthStateChange((event, session) => {
    console.log('Auth event:', event);
    updateAuthUI(session);

    if (session?.user) {
        updateHistory();
    }
});

// =====================================================
// SMALL DOM HELPERS
// =====================================================

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

let selectedTrack = null;
let currentBlueprint = null;
let currentNovaSessionId = null;
let currentNovaPreviewIndex = null;
const novaPreviewCache = new Map();
let currentPulsarEditDurationSeconds = 30;
const activeSignalLayers = new Set(["primary"]);

// =====================================================
// PAGE INFORMATION
// =====================================================

const pageInfo = {
    dashboard: [
        "Launchpad",
        "Plan the music before you edit."
    ],

    nova: [
        "Nova",
        "Find the track that fits."
    ],

    pulsar: [
        "Pulsar",
        "Capture your song's Signal."
    ],

    history: [
        "Echoes",
        "Return to your captured Signals."
    ]
};

// =====================================================
// NOVA API CONFIGURATION
// =====================================================

const SYNCORA_API_URL = "https://lnafi-syncora-backend.hf.space";
const NOVA_REQUEST_TIMEOUT_MS = 120000;

let currentNovaProfile = null;
let novaRequestController = null;
let novaLoadingMessageTimer = null;

// =====================================================
// PULSAR API CONFIGURATION
// =====================================================

const PULSAR_STATUS_POLL_MS = 4000;
const PULSAR_MAX_STATUS_POLLS = 90;
const PULSAR_SIGNAL_TIMEOUT_MS = 210000;

let pulsarBusy = false;

let activePulsarStage = "resolve";

class SyncoraApiError extends Error {
    constructor(
        message,
        {
            status = null,
            stage = null,
            detail = null,
            kind = "api",
            retryable = false,
            safeToRetry = false
        } = {}
    ) {
        super(message);

        this.name = "SyncoraApiError";
        this.status = status;
        this.stage = stage;
        this.detail = detail;
        this.kind = kind;
        this.retryable = retryable;
        this.safeToRetry = safeToRetry;
    }
}

function getBackendErrorDetail(data) {
    const detail = data?.detail;

    if (
        detail &&
        typeof detail === "object"
    ) {
        return detail;
    }

    if (typeof detail === "string") {
        return {
            error: detail
        };
    }

    return {};
}

function getAiProviderLabel(provider) {
    if (
        provider ===
        "huggingface"
    ) {
        return "Hugging Face";
    }

    if (
        provider ===
        "local"
    ) {
        return "LM Studio";
    }

    return "the AI service";
}

function isQwenPulsarStage(stage) {
    return [
        "pulsar_qwen_signal",
        "pulsar_qwen_validation",
        "pulsar_qwen_backend_crash"
    ].includes(stage);
}

function getPulsarErrorPresentation(error) {
    const stage =
        error?.stage ||
        null;

    if (
        error?.kind === "network"
        ||
        stage === "backend_connection"
    ) {
        return {
            title:
                "Syncora backend couldn't be reached.",

            detail:
                "The browser lost its connection to the Syncora backend service. Check your connection and try again in a moment.",
            
            toast:
                "Backend connection lost."
        };
    }

    if (
        error?.kind === "client_timeout"
    ) {
        if (
            activePulsarStage === "signal"
        ) {
            return {
                title:
                    "Signal generation is taking too long.",

                detail:
                    "The browser stopped waiting for the response. The audio analysis should already be cached, so retrying the Signal will not require a new Cyanite analysis.",

                toast:
                    "Signal generation timed out."
            };
        }

        return {
            title:
                "Pulsar took too long to respond.",

            detail:
                error?.message
                ||
                "Try again in a moment.",

            toast:
                "Pulsar timed out."
        };
    }

    if (
        stage ===
        "pulsar_qwen_backend_crash"
    ) {
        return {
            title:
                "The local AI engine crashed.",

            detail:
                "Your audio analysis is safe and cached. " +
                "Reload the Qwen model or restart the " +
                "LM Studio server, then try Generate " +
                "Signal again.",

            toast:
                "LM Studio's AI engine crashed; audio analysis is safe."
        };
    }

    if (
        stage === "pulsar_qwen_signal"
    ) {
        const provider =
            error?.detail?.provider
            ||
            null;

        const providerLabel =
            getAiProviderLabel(
                provider
            );

        const localProvider =
            provider ===
            "local";

        return {
            title:
                error?.status === 504
                    ? "Pulsar's AI interpretation timed out."
                    : `Pulsar couldn't reach ${providerLabel}.`,

            detail:
                error?.status === 504
                    ? "The audio analysis is complete and cached. Try Generate Signal again; Pulsar will reuse the existing analysis instead of spending another Cyanite analysis."
                    : localProvider
                        ? "Make sure LM Studio is running and the Qwen model is loaded. The audio analysis is already cached, so it is safe to retry."
                        : "The cloud AI service could not complete the Signal interpretation. The audio analysis is already cached, so it is safe to retry.",

            toast:
                error?.status === 504
                    ? "AI interpretation timed out; audio analysis is safe."
                    : "AI interpretation is unavailable; audio analysis is safe."
        };
    }

    if (
        stage === "pulsar_qwen_validation"
    ) {
        return {
            title:
                "Pulsar received an invalid AI response.",

            detail:
                "The audio analysis is already cached. Try Generate Signal again; only the interpretation step needs to be repeated.",

            toast:
                "Signal interpretation needs another try."
        };
    }

    if (
        stage === "pulsar_ytmusic_search"
        ||
        stage === "pulsar_ytmusic_match"
        ||
        stage === "pulsar_ytmusic_resolution"
    ) {
        return {
            title:
                "Pulsar couldn't identify the recording.",

            detail:
                error?.message
                ||
                "Check the song title and artist, then try again.",

            toast:
                "Recording could not be identified."
        };
    }

    if (
        stage === "cyanite_enqueue"
    ) {
        return {
            title:
                "Cyanite couldn't start the audio analysis.",

            detail:
                error?.message
                ||
                "The analysis service could not accept this recording. Check your Cyanite allowance and try again.",

            toast:
                "Audio analysis could not start."
        };
    }

    if (
        stage === "cyanite_analysis_status"
        ||
        stage === "cyanite_segments"
        ||
        stage === "cyanite_analysis_wait"
    ) {
        return {
            title:
                "Pulsar couldn't finish reading the audio analysis.",

            detail:
                error?.message
                ||
                "The recording may already be queued or analyzed. Retry before submitting the track as a new recording.",

            toast:
                "Audio-analysis retrieval failed."
        };
    }

    if (
        stage === "request_validation"
    ) {
        return {
            title:
                "Pulsar couldn't use this Signal request.",

            detail:
                error?.message
                ||
                "Check the song, duration, and Signal settings.",

            toast:
                "Signal settings need attention."
        };
    }

    if (
        stage === "pulsar_signal_generation"
    ) {
        return {
            title:
                "Pulsar couldn't build usable cues.",

            detail:
                error?.message
                ||
                "Try the track again or use a different edit duration.",

            toast:
                "No usable Signal was generated."
        };
    }

    if (
        stage === "internal"
    ) {
        return {
            title:
                "Syncora hit an internal backend error.",

            detail:
                "The backend encountered an unexpected error. Try again in a moment.",
            
            toast:
                "Backend error."
        };
    }

    return {
        title:
            "Pulsar couldn't finish the Signal.",

        detail:
            error?.message
            ||
            "An unexpected Pulsar error occurred.",

        toast:
            "Pulsar could not generate the Signal."
    };
}

// =====================================================
// NAVIGATION
// =====================================================

const pageRoutes = {
    dashboard: './launchpad.html',
    launchpad: './launchpad.html',
    nova: './nova.html',
    pulsar: './pulsar.html',
    history: './echoes.html',
    echoes: './echoes.html'
};

function showView(name) {
    const destination = pageRoutes[name] || pageRoutes.launchpad;
    routeTo(destination);
}

$$('[data-view], [data-go], [data-view-link]')
    .forEach(link => {
        link.addEventListener('click', event => {
            event.preventDefault();

            const destination =
                link.dataset.view ||
                link.dataset.go ||
                link.dataset.viewLink;

            showView(destination);
        });
    });

function setActiveNavigation() {
    const currentSection = document.body.dataset.section || '';

    $$('[data-nav-section]').forEach(link => {
        const active = link.dataset.navSection === currentSection;
        link.classList.toggle('active', active);

        if (active) {
            link.setAttribute('aria-current', 'page');
        } else {
            link.removeAttribute('aria-current');
        }
    });
}

setActiveNavigation();

// =====================================================
// NOVA DATABASE
// =====================================================

async function saveNovaSession(rankedSongs) {
    try {
        const {
            data: {
                user
            },
            error: userError
        } = await db.auth
            .getUser();

        if (userError) {
            console.error(
                "Could not get current user:",
                userError
            );

            showToast(
                "Nova generated, but your account could not be verified."
            );

            return null;
        }

        if (!user) {
            return null;
        }

        const mood =
            $('input[name="mood"]:checked')
                ?.value;

        const pace =
            $('input[name="pace"]:checked')
                ?.value;

        const {
            data: novaSession,
            error: sessionError
        } = await db
            .from("nova_sessions")
            .insert({
                user_id:
                    user.id,

                project_name:
                    $("#projectName")
                        .value
                        .trim(),

                video_type:
                    $("#videoType")
                        .value,

                target_duration_seconds:
                    Number(
                        $("#targetDuration")
                            .value
                    ),

                mood,
                pace,

                vocal_style:
                    $("#vocalStyle")
                        .value,

                structure_preference:
                    $("#structurePreference")
                        .value,

                creative_intent:
                    $("#creativeIntent")
                        .value
                        .trim()
                    ||
                    null
            })
            .select("id")
            .single();

        if (
            sessionError
            ||
            !novaSession?.id
        ) {
            console.error(
                "Could not save Nova session:",
                sessionError
                ||
                "Missing session ID."
            );

            showToast(
                "Nova generated, but the session could not be saved."
            );

            return null;
        }

        currentNovaSessionId =
            novaSession.id;

        const recommendations =
            rankedSongs.map(
                song => ({
                    nova_session_id:
                        currentNovaSessionId,

                    rank:
                        song.rank,

                    title:
                        song.title,

                    artist:
                        song.artist,

                    bpm:
                        null,

                    editability:
                        null,

                    energy:
                        null,

                    match_score:
                        song.score
                })
            );

        const {
            error:
                recommendationError
        } = await db
            .from(
                "nova_recommendations"
            )
            .insert(
                recommendations
            );

        if (
            recommendationError
        ) {
            console.error(
                "Could not save Nova recommendations:",
                recommendationError
            );

            const {
                error:
                    rollbackError
            } = await db
                .from("nova_sessions")
                .delete()
                .eq(
                    "id",
                    currentNovaSessionId
                );

            if (rollbackError) {
                console.error(
                    "Could not roll back incomplete Nova session:",
                    rollbackError
                );
            }

            currentNovaSessionId =
                null;

            showToast(
                "Nova generated, but the recommendations could not be saved."
            );

            return null;
        }

        console.log(
            "Nova session saved:",
            currentNovaSessionId
        );

        return currentNovaSessionId;
    } catch (error) {
        console.error(
            "Unexpected Nova save error:",
            error
        );

        currentNovaSessionId =
            null;

        showToast(
            "Nova generated, but Syncora could not reach your saved data."
        );

        return null;
    }
}

async function saveSelectedNovaTrack() {
    if (
        !currentNovaSessionId
        ||
        !selectedTrack
    ) {
        return;
    }

    try {
        const {
            error
        } = await db
            .from("nova_sessions")
            .update({
                selected_track_title:
                    selectedTrack.title,

                selected_track_artist:
                    selectedTrack.artist,

                selected_track_bpm:
                    null,

                selected_track_energy:
                    null,

                selected_track_score:
                    selectedTrack.score
            })
            .eq(
                "id",
                currentNovaSessionId
            );

        if (error) {
            console.error(
                "Could not save selected Nova track:",
                error
            );

            showToast(
                "Track selected, but the selection could not be saved."
            );

            return;
        }

        console.log(
            "Selected Nova track saved:",
            selectedTrack.title
        );
    } catch (error) {
        console.error(
            "Unexpected selected-track save error:",
            error
        );

        showToast(
            "Track selected, but Syncora could not reach your saved data."
        );
    }
}


// =====================================================
// NOVA API HELPERS
// =====================================================

function getSelectedOptionText(selector) {
    const element =
        $(selector);

    return (
        element
            ?.selectedOptions?.[0]
            ?.textContent
            ?.trim()
        ||
        element
            ?.value
        ||
        ""
    );
}

function getCheckedChoiceText(name) {
    const input =
        $(
            `input[name="${name}"]:checked`
        );

    return (
        input
            ?.nextElementSibling
            ?.textContent
            ?.trim()
        ||
        input
            ?.value
        ||
        ""
    );
}

function buildNovaRequestPayload() {
    return {
        project_name:
            $("#projectName")
                .value
                .trim(),

        video_type:
            getSelectedOptionText(
                "#videoType"
            ),

        target_duration_seconds:
            Number(
                $("#targetDuration")
                    .value
            ),

        mood:
            getCheckedChoiceText(
                "mood"
            ),

        pace:
            getCheckedChoiceText(
                "pace"
            ),

        vocal_style:
            getSelectedOptionText(
                "#vocalStyle"
            ),

        structure_preference:
            getSelectedOptionText(
                "#structurePreference"
            ),

        creative_intent:
            $("#creativeIntent")
                .value
                .trim()
    };
}

function getNovaApiErrorMessage(response, data) {
    const detail =
        getBackendErrorDetail(data);

    const stage =
        detail.stage ||
        null;

    if (
        stage === "qwen_profile"
    ) {
        const provider =
            detail.provider
            ||
            null;

        const providerLabel =
            getAiProviderLabel(
                provider
            );

        if (
            response.status === 504
        ) {
            return (
                `Nova's AI profile generation through ${providerLabel} took too long. Try generating the shortlist again.`
            );
        }

        if (
            provider === "local"
        ) {
            return (
                "Nova couldn't reach LM Studio. Make sure LM Studio is running and the Nova model is loaded."
            );
        }

        return (
            `Nova couldn't reach ${providerLabel}. Try generating the shortlist again in a moment.`
        );
    }

    if (
        stage === "nova_qwen_validation"
    ) {
        return (
            "Nova received an unusable AI response. Try generating the shortlist again."
        );
    }

    if (
        stage === "nova_qwen_validation"
    ) {
        return (
            "Nova received an unusable response from the local Qwen model. Try generating the shortlist again."
        );
    }

    if (
        stage === "lastfm_search"
    ) {
        return (
            detail.error
            ||
            "Last.fm did not return enough usable music results for this brief."
        );
    }

    if (
        stage === "final_selection"
        ||
        stage === "shortlist"
    ) {
        return (
            detail.error
            ||
            "Nova could not produce a complete three-track shortlist."
        );
    }

    if (
        stage === "request_validation"
        ||
        response.status === 422
    ) {
        return (
            detail.message
            ||
            detail.error
            ||
            "Nova could not use one or more fields in the brief."
        );
    }

    if (
        stage === "internal"
    ) {
        return (
            "The Syncora backend hit an unexpected error while running Nova. Try again in a moment."
        );
    }

    if (detail.error) {
        return detail.error;
    }

    if (detail.message) {
        return detail.message;
    }

    if (response.status === 504) {
        return (
            "Nova took too long to build the music profile."
        );
    }

    if (response.status >= 500) {
        return (
            "Nova's recommendation service is temporarily unavailable."
        );
    }

    return (
        `Nova request failed with status ${response.status}.`
    );
}

async function fetchNovaRecommendations(payload) {
    novaRequestController =
        new AbortController();

    const timeoutId =
        window.setTimeout(
            () => {
                novaRequestController
                    ?.abort();
            },
            NOVA_REQUEST_TIMEOUT_MS
        );

    try {
        const response =
            await fetch(
                `${SYNCORA_API_URL}/nova/recommend`,
                {
                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(
                            payload
                        ),

                    signal:
                        novaRequestController
                            .signal
                }
            );

        let data =
            null;

        try {
            data =
                await response.json();
        } catch (parseError) {
            console.error(
                "Nova returned invalid JSON:",
                parseError
            );

            if (response.ok) {
                throw new SyncoraApiError(
                    "Nova received an unreadable response from the backend.",
                    {
                        status:
                            response.status,

                        stage:
                            "backend_response",

                        kind:
                            "protocol"
                    }
                );
            }
        }

        if (!response.ok) {
            const detail =
                getBackendErrorDetail(
                    data
                );

            throw new SyncoraApiError(
                getNovaApiErrorMessage(
                    response,
                    data
                ),
                {
                    status:
                        response.status,

                    stage:
                        detail.stage
                        ||
                        null,

                    detail,

                    retryable:
                        Boolean(
                            detail.retryable
                        )
                        ||
                        response.status >= 500
                }
            );
        }

        if (
            !data ||
            !Array.isArray(
                data.recommendations
            ) ||
            data.recommendations.length !== 3
        ) {
            throw new SyncoraApiError(
                "Nova returned an incomplete shortlist.",
                {
                    status:
                        response.status,

                    stage:
                        "nova_response_validation",

                    kind:
                        "protocol",

                    retryable:
                        true
                }
            );
        }

        return data;
    } catch (error) {
        if (
            error instanceof
            SyncoraApiError
        ) {
            throw error;
        }

        if (
            error?.name ===
            "AbortError"
        ) {
            throw new SyncoraApiError(
                "Nova took too long to respond. Please try again.",
                {
                    stage:
                        "nova_client_timeout",

                    kind:
                        "client_timeout",

                    retryable:
                        true
                }
            );
        }

        if (
            error instanceof TypeError
        ) {
            throw new SyncoraApiError(
                "Could not reach the Syncora backend. Make sure FastAPI is running.",
                {
                    stage:
                        "backend_connection",

                    kind:
                        "network",

                    retryable:
                        true
                }
            );
        }

        throw error;
    } finally {
        window.clearTimeout(
            timeoutId
        );

        novaRequestController =
            null;
    }
}

function escapeHtml(value) {
    return String(
        value ?? ""
    )
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );
}

function safeLastfmUrl(value) {
    if (!value) {
        return null;
    }

    try {
        const url =
            new URL(value);

        const isLastfmHost =
            url.hostname ===
                "last.fm"
            ||
            url.hostname
                .endsWith(
                    ".last.fm"
                );

        if (
            url.protocol !== "https:"
            ||
            !isLastfmHost
        ) {
            return null;
        }

        return url.href;
    } catch {
        return null;
    }
}

function makeSongColors(title, artist) {
    const seed =
        `${title}|${artist}`;

    let hash =
        0;

    for (
        let index = 0;
        index < seed.length;
        index += 1
    ) {
        hash =
            (
                (
                    hash * 31
                )
                +
                seed.charCodeAt(
                    index
                )
            )
            >>> 0;
    }

    const hueA =
        hash % 360;

    const hueB =
        (
            hueA
            +
            48
            +
            (
                hash % 72
            )
        )
        %
        360;

    return [
        `hsl(${hueA} 58% 34%)`,
        `hsl(${hueB} 62% 26%)`
    ];
}

function semanticFitLabel(fit) {
    if (
        fit === null ||
        fit === undefined
    ) {
        return "Unavailable";
    }

    if (fit >= 0.82) {
        return "Very strong";
    }

    if (fit >= 0.65) {
        return "Strong";
    }

    if (fit >= 0.45) {
        return "Moderate";
    }

    return "Light";
}

function normalizeNovaRecommendations(data) {
    return data
        .recommendations
        .map(
            (
                recommendation,
                index
            ) => {
                const score =
                    Number(
                        recommendation
                            .match_score
                    );

                const semanticFit =
                    recommendation
                        .semantic_fit ===
                        null
                    ||
                    recommendation
                        .semantic_fit ===
                        undefined

                        ? null

                        : Number(
                            recommendation
                                .semantic_fit
                        );

                const matchedTags =
                    Array.isArray(
                        recommendation
                            .matched_tags
                    )

                        ? recommendation
                            .matched_tags
                            .filter(
                                tag =>
                                    typeof tag ===
                                    "string"
                            )

                        : [];

                const topTags =
                    Array.isArray(
                        recommendation
                            .top_lastfm_tags
                    )

                        ? recommendation
                            .top_lastfm_tags
                            .map(
                                tag =>
                                    tag?.name
                            )
                            .filter(
                                tag =>
                                    typeof tag ===
                                    "string"
                            )

                        : [];

                return {
                    rank:
                        Number(
                            recommendation.rank
                        )
                        ||
                        index + 1,

                    title:
                        recommendation.title
                        ||
                        "Unknown track",

                    artist:
                        recommendation.artist
                        ||
                        "Unknown artist",

                    score:
                        Number.isFinite(
                            score
                        )
                            ? score
                            : 0,

                    reason:
                        recommendation.reason
                        ||
                        "Ranked highly for this Nova brief.",

                    matchedTags,
                    topTags,

                    semanticSimilarity:
                        recommendation
                            .semantic_similarity,

                    semanticFit,

                    semanticLabel:
                        semanticFitLabel(
                            semanticFit
                        ),

                    scoreBreakdown:
                        recommendation
                            .score_breakdown
                        ||
                        {},

                    lastfmUrl:
                        safeLastfmUrl(
                            recommendation
                                .lastfm_url
                        ),

                    mbid:
                        recommendation.mbid
                        ||
                        null,

                    colors:
                        makeSongColors(
                            recommendation.title,
                            recommendation.artist
                        )
                };
            }
        );
}

function setNovaLoading(isLoading) {
    const submitButton = $("#novaSubmitButton");

    if (!submitButton) {
        return;
    }

    if (isLoading) {
        submitButton.disabled = true;
        submitButton.dataset.defaultLabel = submitButton.textContent;
        submitButton.textContent = "Nova is building your shortlist…";
        return;
    }

    if (novaLoadingMessageTimer) {
        window.clearInterval(novaLoadingMessageTimer);
        novaLoadingMessageTimer = null;
    }

    submitButton.disabled = false;
    submitButton.textContent =
        submitButton.dataset.defaultLabel
        ||
        "Generate shortlist →";
}

function renderNovaLoading() {
    const messages = [
        "Reading the musical shape of your brief…",
        "Searching the catalog for a coherent neighborhood…",
        "Comparing the strongest candidates…",
        "Narrowing the decision to three tracks…"
    ];

    $("#songResults").innerHTML = `
        <div class="nova-fluid-loader" role="status" aria-live="polite">
            <div class="nova-loader-visual" aria-hidden="true">
                <span class="nova-loader-core"></span>
                <span class="nova-loader-ring ring-one"></span>
                <span class="nova-loader-ring ring-two"></span>
                <span class="nova-loader-particle particle-one"></span>
                <span class="nova-loader-particle particle-two"></span>
                <span class="nova-loader-particle particle-three"></span>
            </div>

            <div class="nova-loader-copy">
                <p class="eyebrow">Nova is listening to the brief</p>
                <h3>Finding three tracks worth your attention.</h3>
                <p id="novaLoadingMessage">${messages[0]}</p>
            </div>

            <div class="nova-loader-flow" aria-hidden="true">
                <span>Brief</span>
                <i></i>
                <span>Search</span>
                <i></i>
                <span>Compare</span>
                <i></i>
                <strong>Shortlist</strong>
            </div>
        </div>
    `;

    $("#novaResults")?.classList.remove("hidden");

    $("#novaResults")?.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

    if (novaLoadingMessageTimer) {
        window.clearInterval(novaLoadingMessageTimer);
    }

    let messageIndex = 0;

    novaLoadingMessageTimer = window.setInterval(() => {
        const target = $("#novaLoadingMessage");

        if (!target) {
            window.clearInterval(novaLoadingMessageTimer);
            novaLoadingMessageTimer = null;
            return;
        }

        messageIndex = (messageIndex + 1) % messages.length;
        target.classList.add("changing");

        window.setTimeout(() => {
            if (!target.isConnected) return;
            target.textContent = messages[messageIndex];
            target.classList.remove("changing");
        }, 160);
    }, 1800);
}

function renderNovaError(message) {
    $("#songResults").innerHTML =
        `
            <div class="nova-error-card">
                <strong>
                    Nova couldn't build the shortlist.
                </strong>

                <p>
                    ${escapeHtml(message)}
                </p>

                <button
                    class="button primary"
                    id="retryNovaButton"
                    type="button"
                >
                    Try again
                </button>
            </div>
        `;

    $("#novaResults")
        .classList
        .remove("hidden");

    $("#retryNovaButton")
        ?.addEventListener(
            "click",
            () => {
                $("#novaForm")
                    ?.requestSubmit();
            }
        );
}

// =====================================================
// NOVA
// =====================================================

$("#novaForm")
    ?.addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            if (novaRequestController) {
                return;
            }

            selectedTrack =
                null;

            currentNovaSessionId =
                null;

            currentNovaProfile =
                null;

            stopNovaPreview();

            const payload =
                buildNovaRequestPayload();

            setNovaLoading(
                true
            );

            renderNovaLoading();

            try {
                const data =
                    await fetchNovaRecommendations(
                        payload
                    );

                currentNovaProfile =
                    data.profile ||
                    null;

                const rankedSongs =
                    normalizeNovaRecommendations(
                        data
                    );

                await saveNovaSession(
                    rankedSongs
                );

                renderSongResults(
                    rankedSongs
                );

                if (
                    Number(
                        data.warning_count
                    ) > 0
                ) {
                    console.warn(
                        "Nova completed with warnings:",
                        data.warnings
                    );

                    showToast(
                        "Nova generated the shortlist with limited supporting data."
                    );
                } else {
                    showToast(
                        "Nova shortlist ready."
                    );
                }

                console.log(
                    "Nova backend response:",
                    data
                );
            } catch (error) {
                console.error(
                    "Nova recommendation error:",
                    error
                );

                renderNovaError(
                    error?.message
                    ||
                    "An unexpected Nova error occurred."
                );

                showToast(
                    "Nova could not generate the shortlist."
                );
            } finally {
                setNovaLoading(
                    false
                );
            }
        }
    );

$("#novaForm")
    ?.addEventListener(
        "reset",
        () => {
            novaRequestController
                ?.abort();

            novaRequestController =
                null;

            selectedTrack =
                null;

            currentNovaSessionId =
                null;

            currentNovaProfile =
                null;

            $("#novaResults")
                ?.classList
                .add("hidden");
        }
    );

$("#rerunTrackfit")
    ?.addEventListener(
        "click",
        () => {
            $("#novaForm")
                ?.scrollIntoView({
                    behavior: "smooth"
                });
        }
    );

function novaRankLabel(index) {
    if (index === 0) return "Best fit";
    if (index === 1) return "Second fit";
    return "Third fit";
}

function novaOptionLabel(index) {
    return `Option ${String(index + 1).padStart(2, "0")}`;
}

function humanizeNovaTraits(song) {
    const source = [
        ...(song.matchedTags || []),
        ...(song.topTags || [])
    ];

    return [...new Set(
        source
            .map(tag => String(tag || "").trim())
            .filter(Boolean)
    )].slice(0, 4);
}

function buildNovaFitCopy(song) {
    const reason = String(song.reason || "").trim();

    if (
        reason
        &&
        !/semantic similarity|semantic compatibility|nova score|score breakdown|last\.fm/i.test(reason)
    ) {
        return reason;
    }

    const traits = humanizeNovaTraits(song);

    if (traits.length >= 2) {
        return `This track stays close to the ${traits[0]} and ${traits[1]} direction in your brief, while its overall feel remains compatible with the atmosphere and pacing you described.`;
    }

    if (traits.length === 1) {
        return `This track fits the ${traits[0]} direction in your brief and remained one of Nova's strongest overall matches.`;
    }

    return "This track remained one of Nova's strongest overall fits for the sound, atmosphere, and movement described in your brief.";
}

function stopNovaPreview(index = null) {
    const targets = index === null
        ? $$(".nova-preview-host")
        : [document.querySelector(`[data-preview-host="${index}"]`)].filter(Boolean);

    targets.forEach(host => {
        host.innerHTML = "";
        host.classList.add("hidden");
        host.closest(".song-card")?.classList.remove("previewing");
    });

    $$(".preview-song").forEach(button => {
        if (
            index === null
            ||
            Number(button.dataset.index) === Number(index)
        ) {
            button.textContent = "Listen";
            button.removeAttribute("disabled");
        }
    });

    if (
        index === null
        ||
        Number(currentNovaPreviewIndex) === Number(index)
    ) {
        currentNovaPreviewIndex = null;
    }
}

async function toggleNovaPreview(results, index, button) {
    const song = results[index];
    const host = document.querySelector(`[data-preview-host="${index}"]`);

    if (!song || !host) {
        return;
    }

    if (Number(currentNovaPreviewIndex) === Number(index) && !host.classList.contains("hidden")) {
        stopNovaPreview(index);
        return;
    }

    stopNovaPreview();

    button.setAttribute("disabled", "");
    button.textContent = "Finding audio…";

    const cacheKey = `${song.title}::${song.artist}`.toLowerCase();

    try {
        let preview = novaPreviewCache.get(cacheKey);

        if (!preview) {
            const data = await fetchPulsarJson(
                "/pulsar/resolve",
                {
                    method: "POST",
                    body: {
                        title: song.title,
                        artist: song.artist,
                        mbid: song.mbid || null
                    },
                    timeoutMs: 35000
                }
            );

            const track = data?.track || {};
            const videoId = track.video_id;

            if (!videoId || track.embeddable === false) {
                throw new Error("A playable canonical audio source was not available for this track.");
            }

            preview = {
                videoId,
                title: track.youtube_title || song.title,
                channelTitle: track.channel_title || song.artist
            };

            novaPreviewCache.set(cacheKey, preview);
        }

        host.innerHTML = `
            <div class="nova-preview-frame">
                <iframe
                    src="https://www.youtube-nocookie.com/embed/${encodeURIComponent(preview.videoId)}?autoplay=1&rel=0&modestbranding=1"
                    title="Preview ${escapeHtml(song.title)} by ${escapeHtml(song.artist)}"
                    loading="lazy"
                    allow="autoplay; encrypted-media; picture-in-picture"
                    allowfullscreen
                ></iframe>
            </div>
            <div class="nova-preview-meta">
                <span>Canonical audio preview</span>
                <small>${escapeHtml(preview.channelTitle)}</small>
            </div>
        `;

        host.classList.remove("hidden");
        host.closest(".song-card")?.classList.add("previewing");
        currentNovaPreviewIndex = index;
        button.textContent = "Stop preview";
    } catch (error) {
        console.error("Nova preview error:", error);
        button.textContent = "Listen";
        showToast(error?.message || "This track could not be previewed right now.");
    } finally {
        button.removeAttribute("disabled");
    }
}

function renderSongResults(results) {
    stopNovaPreview();

    $("#songResults").innerHTML =
        results
            .map((song, index) => {
                const traits = humanizeNovaTraits(song);
                const traitMarkup = traits.length
                    ? `
                        <div class="song-traits">
                            ${traits.map(trait => `<span>${escapeHtml(trait)}</span>`).join("")}
                        </div>
                    `
                    : "";

                return `
                    <article class="song-card" data-song-index="${index}">
                        <div
                            class="song-art"
                            style="
                                --art-a:${song.colors[0]};
                                --art-b:${song.colors[1]};
                            "
                        >
                            <span class="match-badge">${novaOptionLabel(index)}</span>
                            <div class="song-art-rank">
                                <strong>${novaRankLabel(index)}</strong>
                                <small>Nova shortlist</small>
                            </div>
                        </div>

                        <div class="song-body">
                            <div class="song-meta">
                                <div>
                                    <p class="song-rank-copy">${novaOptionLabel(index)} · ${novaRankLabel(index)}</p>
                                    <h3>${escapeHtml(song.title)}</h3>
                                    <p>${escapeHtml(song.artist)}</p>
                                </div>
                            </div>

                            <p class="song-fit-copy">
                                ${escapeHtml(buildNovaFitCopy(song))}
                            </p>

                            ${traitMarkup}

                            <div
                                class="nova-preview-host hidden"
                                data-preview-host="${index}"
                            ></div>

                            <div class="song-card-actions">
                                <button
                                    class="button ghost preview-song"
                                    data-index="${index}"
                                    type="button"
                                >
                                    Listen
                                </button>

                                <button
                                    class="button primary choose-song"
                                    data-index="${index}"
                                    type="button"
                                >
                                    Choose this song
                                </button>
                            </div>
                        </div>
                    </article>
                `;
            })
            .join("");

    $$(".preview-song").forEach(button => {
        button.addEventListener("click", () => {
            toggleNovaPreview(
                results,
                Number(button.dataset.index),
                button
            );
        });
    });

    $$(".choose-song").forEach(button => {
        button.addEventListener("click", async () => {
            const index = Number(button.dataset.index);

            selectedTrack =
                results[index]
                ||
                null;

            if (!selectedTrack) {
                return;
            }

            stopNovaPreview();
            await saveSelectedNovaTrack();
            openHandoff();
        });
    });
}

function openHandoff() {
    if (!selectedTrack) {
        return;
    }

    const rankIndex = Math.max(
        0,
        Number(selectedTrack.rank || 1) - 1
    );

    const traits = humanizeNovaTraits(selectedTrack)
        .slice(0, 2)
        .join(", ");

    $("#handoffTrack").innerHTML = `
        <strong>
            ${escapeHtml(selectedTrack.title)}
            —
            ${escapeHtml(selectedTrack.artist)}
        </strong>

        <small>
            ${novaOptionLabel(rankIndex)} · ${novaRankLabel(rankIndex)}
            ${traits ? ` · ${escapeHtml(traits)}` : ""}
        </small>
    `;

    $("#handoffModal")?.classList.remove("hidden");
}

// =====================================================
// NOVA → PULSAR HANDOFF
// =====================================================

$('#continueToBlueprint')
    ?.addEventListener('click', () => {
        if (!selectedTrack) {
            return;
        }

        const novaTargetDuration = $('#targetDuration')?.value || '30';
        const novaIntent = $('#creativeIntent')?.value?.trim() || '';

        sessionStorage.setItem(
            'syncoraPulsarHandoff',
            JSON.stringify({
                selectedTrack,
                currentNovaSessionId,
                targetDuration: novaTargetDuration,
                creativeIntent: novaIntent
            })
        );

        closeModal('handoffModal');
        routeTo('./pulsar-workflow.html');
    });

$('#changeTrackButton')
    ?.addEventListener(
        "click",
        () => {
            selectedTrack =
                null;

            currentNovaSessionId =
                null;

            currentNovaProfile =
                null;

            currentPulsarEditDurationSeconds =
                30;

            $("#selectedTrackBanner")
                .classList
                .add("hidden");

            $("#blueprintSong").value =
                "";

            $("#blueprintArtist").value =
                "";
        }
    );

// =====================================================
// PULSAR
// =====================================================

function sleep(milliseconds) {
    return new Promise(
        resolve =>
            window.setTimeout(
                resolve,
                milliseconds
            )
    );
}

function getPulsarApiErrorMessage(response, data) {
    const detail =
        getBackendErrorDetail(data);

    const stage =
        detail.stage ||
        null;

    if (
        stage ===
        "pulsar_qwen_backend_crash"
    ) {
        return (
            detail.message
            ||
            "LM Studio's MLX inference backend crashed."
        );
    }

    if (
        stage === "pulsar_qwen_signal"
    ) {
        if (response.status === 504) {
            return (
                "Pulsar's Qwen interpretation timed out."
            );
        }

        return (
            detail.error
            ||
            "Pulsar could not reach Qwen."
        );
    }

    if (
        stage === "pulsar_qwen_validation"
    ) {
        return (
            detail.error
            ||
            "Qwen returned an invalid Signal response."
        );
    }

    if (
        stage === "pulsar_ytmusic_search"
        ||
        stage === "pulsar_ytmusic_match"
        ||
        stage === "pulsar_ytmusic_resolution"
    ) {
        return (
            detail.error
            ||
            "Pulsar could not identify the requested recording."
        );
    }

    if (
        stage === "cyanite_enqueue"
    ) {
        return (
            detail.cyanite_message
            ||
            detail.error
            ||
            "Cyanite could not start analysis for this recording."
        );
    }

    if (
        stage === "cyanite_analysis_status"
        ||
        stage === "cyanite_segments"
    ) {
        return (
            detail.error
            ||
            detail.message
            ||
            "Pulsar could not retrieve the audio analysis."
        );
    }

    if (
        stage === "request_validation"
        ||
        response.status === 422
    ) {
        return (
            detail.message
            ||
            detail.error
            ||
            "Pulsar could not use one or more Signal settings."
        );
    }

    if (
        stage === "internal"
    ) {
        return (
            "The Syncora backend hit an unexpected internal error."
        );
    }

    if (detail.cyanite_message) {
        return detail.cyanite_message;
    }

    if (detail.error) {
        return detail.error;
    }

    if (detail.message) {
        return detail.message;
    }

    if (response.status >= 500) {
        return (
            "Pulsar's analysis service is temporarily unavailable."
        );
    }

    return (
        `Pulsar request failed with status ${response.status}.`
    );
}

async function fetchPulsarJson(
    path,
    {
        method = "GET",
        body = null,
        timeoutMs = 45000
    } = {}
) {
    const controller =
        new AbortController();

    const timeoutId =
        window.setTimeout(
            () =>
                controller.abort(),
            timeoutMs
        );

    try {
        const response =
            await fetch(
                `${SYNCORA_API_URL}${path}`,
                {
                    method,

                    headers:
                        body
                            ? {
                                "Content-Type":
                                    "application/json"
                            }
                            : undefined,

                    body:
                        body
                            ? JSON.stringify(
                                body
                            )
                            : undefined,

                    signal:
                        controller.signal
                }
            );

        let data =
            null;

        try {
            data =
                await response.json();
        } catch (parseError) {
            console.error(
                "Pulsar returned invalid JSON:",
                parseError
            );

            if (response.ok) {
                throw new SyncoraApiError(
                    "Pulsar received an unreadable response from the backend.",
                    {
                        status:
                            response.status,

                        stage:
                            "backend_response",

                        kind:
                            "protocol",

                        retryable:
                            true
                    }
                );
            }
        }

        if (!response.ok) {
            const detail =
                getBackendErrorDetail(
                    data
                );

            const stage =
                detail.stage
                ||
                null;

            throw new SyncoraApiError(
                getPulsarApiErrorMessage(
                    response,
                    data
                ),
                {
                    status:
                        response.status,

                    stage,

                    detail,

                    retryable:
                        Boolean(
                            detail.retryable
                        )
                        ||
                        response.status >= 500,

                    safeToRetry:
                        Boolean(
                            detail.analysis_preserved
                        )
                        ||
                        isQwenPulsarStage(
                            stage
                        )
                }
            );
        }

        if (
            data === null
            ||
            data === undefined
        ) {
            throw new SyncoraApiError(
                "Pulsar received an empty response from the backend.",
                {
                    status:
                        response.status,

                    stage:
                        "backend_response",

                    kind:
                        "protocol",

                    retryable:
                        true
                }
            );
        }

        return data;
    } catch (error) {
        if (
            error instanceof
            SyncoraApiError
        ) {
            throw error;
        }

        if (
            error?.name ===
            "AbortError"
        ) {
            throw new SyncoraApiError(
                "Pulsar took too long to respond.",
                {
                    stage:
                        "client_timeout",

                    kind:
                        "client_timeout",

                    retryable:
                        true,

                    safeToRetry:
                        activePulsarStage ===
                        "signal"
                }
            );
        }

        if (
            error instanceof TypeError
        ) {
            throw new SyncoraApiError(
                "Could not reach the Syncora backend.",
                {
                    stage:
                        "backend_connection",

                    kind:
                        "network",

                    retryable:
                        true
                }
            );
        }

        throw error;
    } finally {
        window.clearTimeout(
            timeoutId
        );
    }
}

function setPulsarBusy(isBusy) {
    pulsarBusy =
        isBusy;

    const submitButton =
        $("#pulsarSubmitButton");

    const demoButton =
        $("#loadDemoBlueprint");

    if (submitButton) {
        submitButton.disabled =
            isBusy;

        submitButton.textContent =
            isBusy
                ? "Building Signal…"
                : "Generate Signal ⌁";
    }

    if (demoButton) {
        demoButton.disabled =
            isBusy;
    }
}

function setPulsarProgress(
    stage,
    title,
    detail = ""
) {
    if (
        stage !== "done"
    ) {
        activePulsarStage =
            stage;
    }

    const progress =
        $("#pulsarProgress");

    if (!progress) {
        return;
    }

    progress.classList.remove(
        "hidden",
        "error"
    );

    $("#pulsarProgressTitle")
        .textContent =
        title;

    $("#pulsarProgressDetail")
        .textContent =
        detail;

    const order = [
        "resolve",
        "analyze",
        "signal"
    ];

    const currentIndex =
        stage === "done"
            ? order.length
            : order.indexOf(
                stage
            );

    $$(".pulsar-progress-step")
        .forEach(
            step => {
                const stepIndex =
                    order.indexOf(
                        step.dataset
                            .pulsarStage
                    );

                step.classList.remove(
                    "active",
                    "completed"
                );

                if (
                    stepIndex <
                    currentIndex
                ) {
                    step.classList.add(
                        "completed"
                    );
                } else if (
                    stepIndex ===
                    currentIndex
                ) {
                    step.classList.add(
                        "active"
                    );
                }
            }
        );
}

function setPulsarProgressError(error) {
    const progress =
        $("#pulsarProgress");

    const presentation =
        getPulsarErrorPresentation(
            error
        );

    if (!progress) {
        return presentation;
    }

    progress.classList.remove(
        "hidden"
    );

    progress.classList.add(
        "error"
    );

    $("#pulsarProgressTitle")
        .textContent =
        presentation.title;

    $("#pulsarProgressDetail")
        .textContent =
        presentation.detail;

    return presentation;
}

function hidePulsarProgress() {
    $("#pulsarProgress")
        ?.classList
        .add("hidden");
}

function normalizeComparableText(value) {
    return String(
        value || ""
    )
        .trim()
        .toLowerCase();
}

function isCurrentNovaTrack(song, artist) {
    if (!selectedTrack) {
        return false;
    }

    return (
        normalizeComparableText(
            selectedTrack.title
        )
        ===
        normalizeComparableText(
            song
        )
        &&
        normalizeComparableText(
            selectedTrack.artist
        )
        ===
        normalizeComparableText(
            artist
        )
    );
}

function buildPulsarEditingContext(
    musicProfile,
    selectedTypes,
    userContext,
    cameFromNova
) {
    const typeLabels = {
        cut: "cuts",
        transition: "transitions",
        effect: "visual effects",
        speed: "speed changes",
        text: "text moments"
    };

    const parts = [
        `Editing direction: ${
            getSelectedOptionText("#musicProfile")
            || musicProfile
        }.`,

        `Focus suggestions on: ${
            selectedTypes
                .map(
                    type =>
                        typeLabels[type]
                        || type
                )
                .join(", ")
        }.`
    ];

    if (userContext) {
        parts.push(
            `Editor context: ${userContext}.`
        );
    }

    if (cameFromNova) {
        const projectName =
            $("#projectName")
                ?.value
                ?.trim();

        const videoType =
            getSelectedOptionText(
                "#videoType"
            );

        const mood =
            getCheckedChoiceText(
                "mood"
            );

        const pace =
            getCheckedChoiceText(
                "pace"
            );

        if (projectName) {
            parts.push(
                `Nova project: ${projectName}.`
            );
        }

        if (videoType) {
            parts.push(
                `Video type: ${videoType}.`
            );
        }

        if (mood) {
            parts.push(
                `Desired mood: ${mood}.`
            );
        }

        if (pace) {
            parts.push(
                `Editing pace: ${pace}.`
            );
        }
    }

    return parts
        .filter(Boolean)
        .join(" ")
        .slice(0, 2000);
}

function priorityFromChangeScore(score) {
    const numericScore =
        Number(score) ||
        0;

    if (numericScore >= 85) {
        return "primary";
    }

    if (numericScore >= 60) {
        return "secondary";
    }

    return "tertiary";
}

function normalizeCuePriority(priority, score = 0) {
    const normalized =
        String(priority || "")
            .trim()
            .toLowerCase();

    if (normalized === "optional") {
        return "tertiary";
    }

    if (
        normalized === "primary"
        ||
        normalized === "secondary"
        ||
        normalized === "tertiary"
    ) {
        return normalized;
    }

    return priorityFromChangeScore(score);
}

function inferCueType(
    suggestion,
    selectedTypes
) {
    const text =
        String(
            suggestion || ""
        )
            .toLowerCase();

    const patterns = {
        cut:
            /\bcut\b|new angle|shot change|close-up|wide shot|low-angle|insert shot/,

        transition:
            /transition|crossfade|fade|whip|wipe|dissolve/,

        effect:
            /effect|flash|blur|shake|overlay|glow|flicker/,

        speed:
            /speed|ramp|slow motion|slow down|accelerat|fast motion/,

        text:
            /\btext\b|title|caption|typograph|word|label/
    };

    for (
        const type
        of selectedTypes
    ) {
        if (
            patterns[type]
                ?.test(text)
        ) {
            return type;
        }
    }

    return (
        selectedTypes[0]
        ||
        "generated"
    );
}

function formatAnalysisKey(value) {
    if (!value) {
        return "—";
    }

    let display =
        String(value)
            .trim();

    display =
        display
            .replace(
                /^([a-g])(?:s|#)/i,
                (_, note) =>
                    `${note.toUpperCase()}♯`
            )
            .replace(
                /^([a-g])b/i,
                (_, note) =>
                    `${note.toUpperCase()}♭`
            )
            .replace(
                /^([a-g])/i,
                note =>
                    note.toUpperCase()
            )
            .replace(
                /Major$/i,
                " major"
            )
            .replace(
                /Minor$/i,
                " minor"
            );

    return display;
}

function formatAnalysisBpm(value) {
    if (
        value === null
        ||
        value === undefined
        ||
        value === ""
    ) {
        return null;
    }

    const text =
        String(value).trim();

    return /\bbpm\b/i.test(text)
        ? text
        : `${text} BPM`;
}

function mergeDefinedObjects(...sources) {
    const merged = {};

    sources.forEach(
        source => {
            if (
                !source
                ||
                typeof source !== "object"
            ) {
                return;
            }

            Object.entries(source)
                .forEach(
                    ([key, value]) => {
                        if (
                            value !== null
                            &&
                            value !== undefined
                            &&
                            value !== ""
                        ) {
                            merged[key] =
                                value;
                        }
                    }
                );
        }
    );

    return merged;
}

function getBlueprintEditWindow(blueprint) {
    const startSeconds =
        Number(
            blueprint
                ?.editWindow
                ?.start_seconds
        );

    const endSeconds =
        Number(
            blueprint
                ?.editWindow
                ?.end_seconds
        );

    const durationSeconds =
        Number(
            blueprint
                ?.editWindow
                ?.duration_seconds
        );

    if (
        Number.isFinite(startSeconds)
        &&
        Number.isFinite(endSeconds)
        &&
        endSeconds > startSeconds
    ) {
        return {
            startSeconds,
            endSeconds,
            durationSeconds:
                Number.isFinite(durationSeconds)
                &&
                durationSeconds > 0
                    ? durationSeconds
                    : endSeconds - startSeconds,
            usesExcerpt:
                Boolean(
                    blueprint
                        ?.editWindow
                        ?.uses_excerpt
                )
        };
    }

    const trackDuration =
        Number(blueprint?.duration)
        ||
        0;

    return {
        startSeconds: 0,
        endSeconds: trackDuration,
        durationSeconds: trackDuration,
        usesExcerpt: false
    };
}

function renderSignalAnalysis(blueprint) {
    const container =
        $("#signalAnalysis");

    if (!container) {
        return;
    }

    const analysis =
        blueprint.analysis
        ||
        {};

    const editWindow =
        getBlueprintEditWindow(
            blueprint
        );

    const editWindowLabel =
        editWindow.usesExcerpt
            ? `${formatTime(editWindow.startSeconds)}–${formatTime(editWindow.endSeconds)} (${formatTime(editWindow.durationSeconds)} edit)`
            : null;

    const items = [
        [
            "Artist",
            blueprint.artist
        ],

        [
            "Track length",
            blueprint.duration
                ? formatTime(
                    blueprint.duration
                )
                : null
        ],

        [
            "Edit window",
            editWindowLabel
        ],

        [
            "BPM",
            formatAnalysisBpm(
                analysis.bpm
            )
        ],

        [
            "Key",
            analysis.key
                ? formatAnalysisKey(
                    analysis.key
                )
                : null
        ],

        [
            "Meter",
            analysis.time_signature
        ]
    ]
        .filter(
            ([, value]) =>
                value !== null
                &&
                value !== undefined
                &&
                value !== ""
        );

    if (!items.length) {
        container
            .classList
            .add("hidden");

        container.innerHTML =
            "";

        return;
    }

    container.innerHTML =
        items
            .map(
                ([label, value]) => `
                    <div class="signal-analysis-item">
                        <span>
                            ${escapeHtml(label)}
                        </span>
                        <strong>
                            ${escapeHtml(value)}
                        </strong>
                    </div>
                `
            )
            .join("");

    container
        .classList
        .remove("hidden");
}

async function pollPulsarAnalysis(libraryTrackId) {
    for (
        let attempt = 0;
        attempt <
            PULSAR_MAX_STATUS_POLLS;
        attempt += 1
    ) {
        const data =
            await fetchPulsarJson(
                `/pulsar/analyze/status/${
                    encodeURIComponent(
                        libraryTrackId
                    )
                }`,
                {
                    timeoutMs:
                        30000
                }
            );

        const status =
            data?.status ||
            "unknown";

        if (
            status ===
            "finished"
        ) {
            return data;
        }

        if (
            status ===
            "failed"
        ) {
            throw new SyncoraApiError(
                "The audio analysis failed.",
                {
                    stage:
                        "cyanite_analysis_status",

                    kind:
                        "api",

                    retryable:
                        false
                }
            );
        }

        if (
            status ===
            "not_authorized"
        ) {
            throw new SyncoraApiError(
                "This Cyanite account is not authorized for the requested analysis.",
                {
                    stage:
                        "cyanite_analysis_status",

                    kind:
                        "api",

                    retryable:
                        false
                }
            );
        }

        if (
            status ===
            "unknown"
        ) {
            throw new SyncoraApiError(
                "Pulsar received an unknown analysis status.",
                {
                    stage:
                        "cyanite_analysis_status",

                    kind:
                        "protocol",

                    retryable:
                        true
                }
            );
        }

        const detail =
            status ===
                "enqueued"

                ? "The recording is queued for objective audio analysis."

                : status ===
                    "not_started"

                    ? "The recording is waiting for analysis to begin."

                    : "Pulsar is reading how the track changes over time.";

        setPulsarProgress(
            "analyze",
            "Analyzing the track…",
            detail
        );

        await sleep(
            PULSAR_STATUS_POLL_MS
        );
    }

    throw new SyncoraApiError(
        "The audio analysis did not finish within the expected time.",
        {
            stage:
                "cyanite_analysis_wait",

            kind:
                "timeout",

            retryable:
                true,

            safeToRetry:
                true
        }
    );
}

$("#loadDemoBlueprint")
    ?.addEventListener(
        "click",
        () => {
            if (pulsarBusy) {
                return;
            }

            selectedTrack =
                null;

            currentNovaSessionId =
                null;

            $("#selectedTrackBanner")
                .classList
                .add("hidden");

            $("#blueprintSong").value =
                "Resonance";

            $("#blueprintArtist").value =
                "HOME";

            currentPulsarEditDurationSeconds =
                30;

            $("#musicProfile").value =
                "dynamic";

            $("#pulsarEditingContext").value =
                "A cinematic nighttime automotive edit with clean cuts, visual transitions, and speed changes that respond to noticeable changes in the music.";
        }
    );

$("#blueprintForm")
    ?.addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            if (pulsarBusy) {
                return;
            }

            const song =
                $("#blueprintSong")
                    .value
                    .trim();

            const artist =
                $("#blueprintArtist")
                    .value
                    .trim();

            const musicProfile =
                $("#musicProfile")
                    .value;

            const editDurationSeconds =
                Number(
                    currentPulsarEditDurationSeconds
                )
                ||
                30;

            const selectedTypes =
                $$(
                    'input[name="cueType"]:checked'
                )
                    .map(
                        box =>
                            box.value
                    );

            const userContext =
                $("#pulsarEditingContext")
                    .value
                    .trim();

            if (
                !song ||
                !artist
            ) {
                showToast(
                    "Enter both the song title and artist."
                );

                return;
            }

            if (
                !selectedTypes.length
            ) {
                showToast(
                    "Choose at least one suggestion type."
                );

                return;
            }

            const cameFromNova =
                isCurrentNovaTrack(
                    song,
                    artist
                );

            const editingContext =
                buildPulsarEditingContext(
                    musicProfile,
                    selectedTypes,
                    userContext,
                    cameFromNova,
                );

            setPulsarBusy(
                true
            );

            $("#blueprintOutput")
                .classList
                .add("hidden");

            setPulsarProgress(
                "resolve",
                "Identifying the recording…",
                "Pulsar is matching the title and artist to the exact recording."
            );

            try {
                const startData =
                    await fetchPulsarJson(
                        "/pulsar/analyze/start",
                        {
                            method:
                                "POST",

                            body: {
                                title:
                                    song,

                                artist,

                                mbid:
                                    cameFromNova
                                        ? selectedTrack
                                            ?.mbid
                                            ||
                                            null
                                        : null
                            },

                            timeoutMs:
                                45000
                        }
                    );

                const libraryTrackId =
                    startData
                        ?.cyanite
                        ?.library_track_id;

                if (!libraryTrackId) {
                    throw new Error(
                        "Pulsar did not receive an analysis ID for this recording."
                    );
                }

                const resolvedTrack =
                    startData.track ||
                    {};

                const resolvedTitle =
                    resolvedTrack.title
                    ||
                    song;

                const resolvedArtists =
                    Array.isArray(
                        resolvedTrack.artists
                    )

                        ? resolvedTrack
                            .artists
                            .filter(Boolean)

                        : [];

                const resolvedArtist =
                    resolvedArtists.join(", ")
                    ||
                    artist;

                const duration =
                    Number(
                        resolvedTrack
                            .duration_seconds
                    )
                    ||
                    0;

                $("#blueprintSong").value =
                    resolvedTitle;

                $("#blueprintArtist").value =
                    resolvedArtist;

                setPulsarProgress(
                    "analyze",
                    "Analyzing the track…",
                    "The exact recording is resolved. Pulsar is now measuring how the music changes over time."
                );

                const analysisStatusData =
                    await pollPulsarAnalysis(
                        libraryTrackId
                    );

                setPulsarProgress(
                    "signal",
                    "Building your Signal…",
                    "Pulsar is mapping the measured transitions in the selected window and turning them into editing suggestions."
                );

                const signalData =
                    await fetchPulsarJson(
                        "/pulsar/signal/generate",
                        {
                            method:
                                "POST",

                            body: {
                                library_track_id:
                                    String(
                                        libraryTrackId
                                    ),

                                editing_context:
                                    editingContext,

                                edit_duration_seconds:
                                    editDurationSeconds,

                                track_duration_seconds:
                                    duration > 0
                                        ? Math.round(duration)
                                        : null
                            },

                            timeoutMs:
                                PULSAR_SIGNAL_TIMEOUT_MS
                        }
                    );

                const backendCues =
                    signalData
                        ?.signal
                        ?.cues;

                if (
                    !Array.isArray(
                        backendCues
                    )
                    ||
                    !backendCues.length
                ) {
                    throw new Error(
                        "Pulsar returned a Signal without usable cues."
                    );
                }

                const cues =
                    backendCues.map(
                        cue => {
                            const seconds =
                                Number(
                                    cue.timestamp_seconds
                                );

                            const changeScore =
                                Number(
                                    cue
                                        ?.objective
                                        ?.change_score
                                )
                                ||
                                0;

                            return {
                                time:
                                    formatTime(
                                        seconds
                                    ),

                                seconds,

                                type:
                                    inferCueType(
                                        cue.suggestion,
                                        selectedTypes
                                    ),

                                priority:
                                    normalizeCuePriority(
                                        cue.priority
                                        ||
                                        cue?.objective?.tier,
                                        changeScore
                                    ),

                                title:
                                    cue.title
                                    ||
                                    "Measured musical change",

                                moment:
                                    cue.evidence
                                    ||
                                    "A meaningful musical change was detected here.",

                                suggestion:
                                    cue.suggestion
                                    ||
                                    "Consider changing the visual treatment here.",

                                changeScore
                            };
                        }
                    );

                const fallbackDuration =
                    Math.max(
                        ...cues.map(
                            cue =>
                                cue.seconds
                        ),
                        0
                    )
                    +
                    15;

                const editWindow =
                    signalData
                        ?.edit_window
                    ||
                    {
                        start_seconds: 0,
                        end_seconds:
                            duration
                            ||
                            fallbackDuration,
                        duration_seconds:
                            duration
                            ||
                            fallbackDuration,
                        track_duration_seconds:
                            duration
                            ||
                            fallbackDuration,
                        uses_excerpt: false
                    };

                const mergedAnalysis =
                    mergeDefinedObjects(
                        signalData
                            ?.analysis,
                        analysisStatusData
                            ?.analysis
                    );

                currentBlueprint = {
                    id:
                        Date.now(),

                    libraryTrackId:
                        String(
                            libraryTrackId
                        ),

                    song:
                        resolvedTitle,

                    artist:
                        resolvedArtist,

                    duration:
                        duration
                        ||
                        fallbackDuration,

                    editDuration:
                        Number(
                            editWindow
                                ?.duration_seconds
                        )
                        ||
                        editDurationSeconds
                        ||
                        duration
                        ||
                        fallbackDuration,

                    editWindow,

                    musicProfile,

                    density:
                        "balanced",

                    keypointMode:
                        signalData?.keypoint_mode
                        ||
                        "all-ranked-transitions",

                    selectedTypes,

                    novaSessionId:
                        cameFromNova
                            ? currentNovaSessionId
                            : null,

                    created:
                        new Date()
                            .toLocaleDateString(),

                    summary:
                        signalData
                            ?.signal
                            ?.summary
                        ||
                        "Pulsar mapped the measured musical changes in the selected source window.",

                    analysis:
                        mergedAnalysis,

                    cues
                };

                const selectedWindow =
                    getBlueprintEditWindow(
                        currentBlueprint
                    );

                setPulsarProgress(
                    "done",
                    "Signal ready.",
                    selectedWindow.usesExcerpt
                        ? `${cues.length} editing opportunities were mapped inside ${formatTime(selectedWindow.startSeconds)}–${formatTime(selectedWindow.endSeconds)}.`
                        : `${cues.length} editing opportunities were generated from the analyzed recording.`
                );

                renderBlueprint(
                    currentBlueprint
                );

                showToast(
                    "Pulsar Signal ready."
                );

                window.setTimeout(
                    hidePulsarProgress,
                    700
                );

                console.log(
                    "Pulsar Signal response:",
                    signalData
                );
            } catch (error) {
                console.error(
                    "Pulsar generation error:",
                    error
                );

                const presentation =
                    setPulsarProgressError(
                        error
                    );

                showToast(
                    presentation?.toast
                    ||
                    "Pulsar could not generate the Signal."
                );
            } finally {
                setPulsarBusy(
                    false
                );
            }
        }
    );

function getSignalLayerLabel(priority) {
    const normalized = normalizeCuePriority(priority);

    if (normalized === "primary") return "Primary";
    if (normalized === "secondary") return "Secondary";
    return "Tertiary";
}

function syncSignalLayerStateFromControls() {
    activeSignalLayers.clear();

    $$('input[name="signalLayer"]:checked').forEach(input => {
        activeSignalLayers.add(
            normalizeCuePriority(input.value)
        );
    });
}

function getVisibleSignalCues(blueprint) {
    syncSignalLayerStateFromControls();

    return (blueprint?.cues || []).filter(cue =>
        activeSignalLayers.has(
            normalizeCuePriority(
                cue.priority,
                cue.changeScore
            )
        )
    );
}

function openCueDetail(cue) {
    const modal = $("#cueDetailModal");

    if (!modal || !cue) {
        return;
    }

    const priority =
        normalizeCuePriority(
            cue.priority,
            cue.changeScore
        );

    $("#cueDetailEyebrow").textContent =
        `${getSignalLayerLabel(priority)} key point · ${cue.time}`;

    $("#cueDetailTitle").textContent =
        cue.title
        ||
        "Musical change";

    $("#cueDetailMeta").innerHTML = `
        <span class="priority-chip ${escapeHtml(priority)}">
            ${escapeHtml(getSignalLayerLabel(priority))}
        </span>
        <span>${escapeHtml(cue.type ? capitalize(cue.type) : "Editing opportunity")}</span>
    `;

    $("#cueDetailMoment").textContent =
        cue.moment
        ||
        "A meaningful musical change was detected here.";

    $("#cueDetailSuggestion").textContent =
        cue.suggestion
        ||
        "Consider changing the visual treatment here.";

    modal.classList.remove("hidden");
}

function renderPulsarTimeline(blueprint) {
    const timeline = $("#visualTimeline");

    if (!timeline) {
        return;
    }

    const editWindow =
        getBlueprintEditWindow(
            blueprint
        );

    const colors = {
        primary:
            "var(--accent)",

        secondary:
            "var(--blue)",

        tertiary:
            "var(--purple)"
    };

    const visibleCues =
        getVisibleSignalCues(
            blueprint
        );

    const layerNames =
        [...activeSignalLayers]
            .map(
                layer =>
                    getSignalLayerLabel(
                        layer
                    )
            );

    const status =
        $("#timelineLayerStatus");

    if (status) {
        status.textContent =
            layerNames.length
                ? `Showing ${layerNames.join(", ")}`
                : "No timeline layers selected";
    }

    const cueCount =
        $("#cueCount");

    if (cueCount) {
        cueCount.textContent =
            `${visibleCues.length} shown · ${blueprint.cues.length} mapped`;
    }

    timeline.innerHTML =
        visibleCues
            .map(cue => {
                const priority =
                    normalizeCuePriority(
                        cue.priority,
                        cue.changeScore
                    );

                const percentage =
                    Math.max(
                        0,
                        Math.min(
                            100,
                            (
                                (
                                    cue.seconds
                                    -
                                    editWindow.startSeconds
                                )
                                /
                                Math.max(
                                    editWindow.durationSeconds,
                                    1
                                )
                            )
                            *
                            100
                        )
                    );

                const edgeClass =
                    percentage < 18
                        ? "edge-left"
                        : percentage > 82
                            ? "edge-right"
                            : "";

                return `
                    <button
                        class="timeline-marker ${escapeHtml(priority)} ${edgeClass}"
                        type="button"
                        data-cue-number="${escapeHtml(cue.cueNumber || "")}"
                        data-time="${escapeHtml(cue.time)}"
                        aria-label="${escapeHtml(`${getSignalLayerLabel(priority)} key point at ${cue.time}: ${cue.title || cue.moment}`)}"
                        style="
                            left:${percentage}%;
                            --marker:${colors[priority] || "var(--purple)"};
                        "
                    >
                        <span class="timeline-marker-core" aria-hidden="true"></span>
                        <span class="timeline-tooltip" aria-hidden="true">
                            <small>${escapeHtml(cue.time)} · ${escapeHtml(getSignalLayerLabel(priority))}</small>
                            <strong>${escapeHtml(cue.title || "Musical change")}</strong>
                            <span>${escapeHtml(cue.moment || "")}</span>
                            <em>Click for full details</em>
                        </span>
                    </button>
                `;
            })
            .join("");

    $$(".timeline-marker").forEach((button, visibleIndex) => {
        button.addEventListener("click", () => {
            const visibleCue = visibleCues[visibleIndex];
            openCueDetail(visibleCue);
        });
    });
}

function renderBlueprint(blueprint) {
    blueprint.cues =
        (blueprint.cues || [])
            .map((cue, index) => ({
                ...cue,
                cueNumber:
                    cue.cueNumber
                    ||
                    cue.cue_number
                    ||
                    index + 1,

                priority:
                    normalizeCuePriority(
                        cue.priority,
                        cue.changeScore
                    )
            }));

    $("#outputTitle").textContent =
        blueprint.artist
            ? `${blueprint.song} — ${blueprint.artist}`
            : blueprint.song;

    $("#outputSummary").textContent =
        blueprint.summary
        ||
        `${blueprint.cues.length} mapped edit points across ${formatTime(blueprint.duration)}.`;

    const editWindow =
        getBlueprintEditWindow(
            blueprint
        );

    const timelineWindowLabel =
        $("#timelineWindowLabel");

    if (timelineWindowLabel) {
        timelineWindowLabel.textContent =
            editWindow.usesExcerpt
                ? `Suggested source window: ${formatTime(editWindow.startSeconds)}–${formatTime(editWindow.endSeconds)} of ${formatTime(blueprint.duration)}. Cue times are absolute song times.`
                : `Full-track Signal across ${formatTime(blueprint.duration)}. Cue times are absolute song times.`;
    }

    renderSignalAnalysis(
        blueprint
    );

    renderPulsarTimeline(
        blueprint
    );

    $("#cueTableBody").innerHTML =
        blueprint.cues
            .map((cue, index) => {
                const priority =
                    normalizeCuePriority(
                        cue.priority,
                        cue.changeScore
                    );

                return `
                    <tr>
                        <td>
                            <strong>${escapeHtml(cue.time)}</strong>
                        </td>

                        <td>
                            <span class="priority-chip ${escapeHtml(priority)}">
                                ${escapeHtml(getSignalLayerLabel(priority))}
                            </span>
                        </td>

                        <td>
                            <div class="cue-moment">
                                <strong>${escapeHtml(cue.title || "Musical change")}</strong>
                                <small>${escapeHtml(cue.moment || "")}</small>
                            </div>
                        </td>

                        <td>
                            ${escapeHtml(cue.suggestion || "")}
                        </td>

                        <td>
                            <button
                                class="table-action edit-cue"
                                data-index="${index}"
                                aria-label="Edit suggestion"
                            >
                                ✎
                            </button>
                        </td>
                    </tr>
                `;
            })
            .join("");

    $$(".edit-cue").forEach(button => {
        button.addEventListener("click", () => {
            const cue =
                currentBlueprint
                    .cues[
                        Number(
                            button.dataset.index
                        )
                    ];

            const newSuggestion =
                prompt(
                    "Edit this suggestion:",
                    cue.suggestion
                );

            if (newSuggestion?.trim()) {
                cue.suggestion =
                    newSuggestion.trim();

                renderBlueprint(
                    currentBlueprint
                );
            }
        });
    });

    $("#blueprintOutput")?.classList.remove("hidden");

    $("#blueprintOutput")?.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}

$$('input[name="signalLayer"]').forEach(input => {
    input.addEventListener("change", () => {
        syncSignalLayerStateFromControls();

        if (currentBlueprint) {
            renderPulsarTimeline(
                currentBlueprint
            );
        }
    });
});

// =====================================================
// PULSAR DATABASE
// =====================================================

async function savePulsarSignal() {
    if (!currentBlueprint) {
        return null;
    }

    try {
        const {
            data: {
                user
            },
            error: userError
        } = await db.auth
            .getUser();

        if (userError) {
            console.error(
                "Could not get current user:",
                userError
            );

            showToast(
                "Could not verify your account."
            );

            return null;
        }

        if (!user) {
            showToast(
                "Sign in to save this Signal."
            );

            return null;
        }

        const {
            data: signal,
            error: signalError
        } = await db
            .from("pulsar_signals")
            .insert({
                user_id:
                    user.id,

                nova_session_id:
                    currentBlueprint
                        .novaSessionId,

                song_title:
                    currentBlueprint
                        .song,

                song_artist:
                    currentBlueprint
                        .artist,

                song_duration_seconds:
                    currentBlueprint
                        .duration,

                music_profile:
                    currentBlueprint
                        .musicProfile,

                density:
                    currentBlueprint
                        .density,

                cue_types:
                    currentBlueprint
                        .selectedTypes
            })
            .select("id")
            .single();

        if (
            signalError
            ||
            !signal?.id
        ) {
            console.error(
                "Could not save Pulsar Signal:",
                signalError
                ||
                "Missing Signal ID."
            );

            showToast(
                "Signal could not be saved."
            );

            return null;
        }

        const cueRows =
            currentBlueprint
                .cues
                .map(
                    (
                        cue,
                        index
                    ) => ({
                        signal_id:
                            signal.id,

                        cue_order:
                            index + 1,

                        time_seconds:
                            cue.seconds,

                        cue_type:
                            cue.type,

                        priority:
                            cue.priority,

                        musical_moment:
                            cue.moment,

                        suggestion:
                            cue.suggestion
                    })
                );

        const {
            error:
                cuesError
        } = await db
            .from("pulsar_cues")
            .insert(
                cueRows
            );

        if (cuesError) {
            console.error(
                "Could not save Pulsar cues:",
                cuesError
            );

            const {
                error:
                    rollbackError
            } = await db
                .from("pulsar_signals")
                .delete()
                .eq(
                    "id",
                    signal.id
                );

            if (rollbackError) {
                console.error(
                    "Could not roll back incomplete Signal:",
                    rollbackError
                );
            }

            showToast(
                "Signal could not be saved."
            );

            return null;
        }

        console.log(
            "Pulsar Signal saved:",
            signal.id
        );

        return signal.id;
    } catch (error) {
        console.error(
            "Unexpected Signal save error:",
            error
        );

        showToast(
            "Signal is still open, but Syncora could not reach your saved data."
        );

        return null;
    }
}


// =====================================================
// SAVE / COPY / ECHOES
// =====================================================

$("#saveBlueprint")
    ?.addEventListener(
        "click",
        async event => {
            if (!currentBlueprint) {
                return;
            }

            const button =
                event.currentTarget;

            button.disabled =
                true;

            try {
                const signalId =
                    await savePulsarSignal();

                if (!signalId) {
                    return;
                }

                await updateHistory();

                showToast(
                    "Signal captured."
                );
            } finally {
                button.disabled =
                    false;
            }
        }
    );

$("#copyBlueprint")
    ?.addEventListener(
        "click",
        async () => {
            if (!currentBlueprint) {
                return;
            }

            const notes =
                currentBlueprint
                    .cues
                    .map(
                        cue =>
                            `${cue.time} — ${cue.suggestion}`
                    )
                    .join("\n");

            try {
                await navigator
                    .clipboard
                    .writeText(
                        `${currentBlueprint.song}\n\n${notes}`
                    );

                showToast(
                    "Signal cloned."
                );
            } catch {
                showToast(
                    "Clipboard access is unavailable."
                );
            }
        }
    );

async function getHistory() {
    try {
        const {
            data: {
                user
            },
            error: userError
        } = await db.auth
            .getUser();

        if (userError) {
            console.error(
                "Could not get current user:",
                userError
            );

            return null;
        }

        if (!user) {
            return [];
        }

        const {
            data,
            error
        } = await db
            .from("pulsar_signals")
            .select(`
                id,
                nova_session_id,
                song_title,
                song_artist,
                song_duration_seconds,
                music_profile,
                density,
                cue_types,
                created_at,
                pulsar_cues (
                    id,
                    cue_order,
                    time_seconds,
                    cue_type,
                    priority,
                    musical_moment,
                    suggestion
                )
            `)
            .eq(
                "user_id",
                user.id
            )
            .order(
                "created_at",
                {
                    ascending:
                        false
                }
            );

        if (error) {
            console.error(
                "Could not load Echoes:",
                error
            );

            return null;
        }

        return (
            data
            ||
            []
        )
            .map(
                signal => {
                    const cues =
                        (
                            signal.pulsar_cues
                            ||
                            []
                        )
                            .sort(
                                (
                                    a,
                                    b
                                ) =>
                                    a.cue_order
                                    -
                                    b.cue_order
                            )
                            .map(
                                cue => ({
                                    id:
                                        cue.id,

                                    time:
                                        formatTime(
                                            cue.time_seconds
                                        ),

                                    seconds:
                                        cue.time_seconds,

                                    type:
                                        cue.cue_type,

                                    priority:
                                        cue.priority,

                                    moment:
                                        cue.musical_moment,

                                    suggestion:
                                        cue.suggestion
                                })
                            );

                    return {
                        id:
                            signal.id,

                        novaSessionId:
                            signal.nova_session_id,

                        song:
                            signal.song_title,

                        artist:
                            signal.song_artist,

                        duration:
                            signal.song_duration_seconds,

                        musicProfile:
                            signal.music_profile,

                        density:
                            signal.density,

                        selectedTypes:
                            signal.cue_types
                            ||
                            [],

                        createdAt:
                            signal.created_at,

                        created:
                            new Date(
                                signal.created_at
                            )
                                .toLocaleDateString(),

                        cues
                    };
                }
            );
    } catch (error) {
        console.error(
            "Unexpected Echoes load error:",
            error
        );

        return null;
    }
}

function openSavedSignal(signal) {
    if (!$("#blueprintForm")) {
        sessionStorage.setItem(
            "syncoraDeferredSignal",
            JSON.stringify(signal)
        );

        routeTo("./pulsar-workflow.html");
        return;
    }

    currentBlueprint =
        structuredClone(
            signal
        );

    $("#blueprintSong").value =
        signal.song ||
        "";

    $("#blueprintArtist").value =
        signal.artist ||
        "";

    $("#musicProfile").value =
        signal.musicProfile ||
        "dynamic";

    currentPulsarEditDurationSeconds =
        Number(
            signal.editDuration
        )
        ||
        30;

    $("#pulsarEditingContext").value =
        "";

    $$('input[name="cueType"]')
        .forEach(
            input => {
                input.checked =
                    signal.selectedTypes
                        ?.includes(
                            input.value
                        )
                    ||
                    false;
            }
        );

    currentNovaSessionId =
        signal.novaSessionId
        ||
        null;

    if (
        signal.novaSessionId &&
        signal.artist
    ) {
        selectedTrack = {
            title:
                signal.song,

            artist:
                signal.artist,

            score:
                null,

            matchedTags:
                [],

            mbid:
                null
        };

        $("#selectedTrackName")
            .textContent =
            `${signal.song} — ${signal.artist}`;

        $("#selectedTrackMeta")
            .textContent =
            "Restored from Echoes";

        $("#selectedTrackBanner")
            .classList
            .remove("hidden");
    } else {
        selectedTrack =
            null;

        $("#selectedTrackBanner")
            .classList
            .add("hidden");
    }

    hidePulsarProgress();

    renderBlueprint(
        currentBlueprint
    );
}

function renderHistoryInto(container, items) {
    if (!container) {
        return;
    }

    if (!items.length) {
        container.innerHTML =
            `
                <div class="empty-state">

                    <div>
                        <strong>
                            No Echoes yet
                        </strong>

                        <p>
                            Capture a Signal and it will appear here.
                        </p>
                    </div>

                </div>
            `;

        return;
    }

    container.innerHTML =
        items
            .map(
                item => {
                    return `
                        <article class="history-card">

                            <p class="eyebrow">
                                Pulsar
                            </p>

                            <h3>
                                ${escapeHtml(item.song)}
                            </h3>

                            <p>
                                ${item.cues.length} editing suggestions
                            </p>

                            <div class="history-meta">

                                <span>
                                    ${escapeHtml(item.created)}
                                </span>

                                <span>
                                    ${formatTime(
                                        item.duration
                                    )}
                                </span>

                            </div>

                            <div class="history-actions">

                                <button
                                    class="button ghost small open-echo"
                                    data-signal-id="${escapeHtml(item.id)}"
                                >
                                    Open Signal →
                                </button>

                            </div>

                        </article>
                    `;
                }
            )
            .join("");

    container
        .querySelectorAll(
            ".open-echo"
        )
        .forEach(
            button => {
                button.addEventListener(
                    "click",
                    () => {
                        const signal =
                            items.find(
                                item =>
                                    String(
                                        item.id
                                    )
                                    ===
                                    String(
                                        button.dataset.signalId
                                    )
                            );

                        if (!signal) {
                            console.error(
                                "Could not find saved Signal:",
                                button.dataset.signalId
                            );

                            return;
                        }

                        openSavedSignal(
                            signal
                        );
                    }
                );
            }
        );
}

$("#clearHistory")
    ?.addEventListener(
        "click",
        async event => {
            const button =
                event.currentTarget;

            button.disabled =
                true;

            try {
                const {
                    data: {
                        user
                    },
                    error:
                        userError
                } = await db.auth
                    .getUser();

                if (
                    userError
                    ||
                    !user
                ) {
                    showToast(
                        "Sign in to manage your Echoes."
                    );

                    if (userError) {
                        console.error(
                            "Could not verify account before clearing Echoes:",
                            userError
                        );
                    }

                    return;
                }

                const confirmed =
                    window.confirm(
                        "Delete all of your captured Signals? This cannot be undone."
                    );

                if (!confirmed) {
                    return;
                }

                const {
                    error
                } = await db
                    .from("pulsar_signals")
                    .delete()
                    .eq(
                        "user_id",
                        user.id
                    );

                if (error) {
                    console.error(
                        "Could not clear Echoes:",
                        error
                    );

                    showToast(
                        "Echoes could not be cleared."
                    );

                    return;
                }

                await updateHistory();

                showToast(
                    "Echoes cleared."
                );
            } catch (error) {
                console.error(
                    "Unexpected Echoes clear error:",
                    error
                );

                showToast(
                    "Could not reach your saved data. Nothing was cleared."
                );
            } finally {
                button.disabled =
                    false;
            }
        }
    );

async function updateHistory() {
    const history =
        await getHistory();

    if (
        !Array.isArray(
            history
        )
    ) {
        console.warn(
            "Echoes update skipped because saved data could not be loaded."
        );

        return;
    }

    const count =
        history.length;

    const blueprintCount =
        $("#blueprintCount");

    const accountBlueprintCount =
        $("#accountBlueprintCount");

    if (blueprintCount) {
        blueprintCount.textContent =
            count;
    }

    if (accountBlueprintCount) {
        accountBlueprintCount.textContent =
            count;
    }

    renderHistoryInto(
        $("#historyList"),
        history
    );

    renderHistoryInto(
        $("#recentBlueprints"),
        history.slice(
            0,
            3
        )
    );
}

// =====================================================
// ACCOUNT MODAL
// =====================================================

function openAccount() {
    setAuthMessage();

    $("#accountModal")
        .classList
        .remove("hidden");
}

$("#accountButton")
    ?.addEventListener(
        "click",
        openAccount
    );

$("#topAccountButton")
    ?.addEventListener(
        "click",
        openAccount
    );

// =====================================================
// MODALS + SMALL HELPERS
// =====================================================

$$("[data-close]")
    .forEach(
        button => {
            button
                .addEventListener(
                    "click",
                    () => {
                        closeModal(
                            button.dataset.close
                        );
                    }
                );
        }
    );

function closeModal(id) {
    $(`#${id}`)
        ?.classList
        .add("hidden");
}

function showToast(message) {
    const toast =
        $("#toast");

    if (!toast) {
        return;
    }

    toast.textContent =
        message;

    toast.classList.remove(
        "hidden"
    );

    setTimeout(
        () => {
            toast.classList.add(
                "hidden"
            );
        },
        2200
    );
}

function formatTime(seconds) {
    const safeSeconds =
        Number(seconds) ||
        0;

    const minutes =
        Math.floor(
            safeSeconds /
            60
        );

    const remaining =
        Math.round(
            safeSeconds %
            60
        );

    return `${minutes}:${String(
        remaining
    ).padStart(
        2,
        "0"
    )}`;
}

function capitalize(text) {
    const value =
        String(
            text || ""
        );

    return (
        value
            .charAt(0)
            .toUpperCase()
        +
        value
            .slice(1)
    );
}

// =====================================================
// INTERACTION POLISH
// =====================================================

window.addEventListener(
    "scroll",
    () => {
        $(".site-header")
            ?.classList
            .toggle(
                "scrolled",
                window.scrollY > 8
            );
    }
);

$$(".modal-backdrop")
    .forEach(
        backdrop => {
            backdrop
                .addEventListener(
                    "click",
                    event => {
                        if (
                            event.target ===
                            backdrop
                        ) {
                            backdrop
                                .classList
                                .add(
                                    "hidden"
                                );
                        }
                    }
                );
        }
    );

document.addEventListener(
    "keydown",
    event => {
        if (
            event.key ===
            "Escape"
        ) {
            $$(".modal-backdrop")
                .forEach(
                    modal => {
                        modal
                            .classList
                            .add(
                                "hidden"
                            );
                    }
                );
        }
    }
);

// =====================================================
// MULTI-PAGE BOOTSTRAP
// =====================================================

function setAuthMode(mode) {
    if (PAGE_KIND !== 'auth') {
        return;
    }

    const nextMode = mode === 'signup' ? 'signup' : 'login';
    document.body.dataset.authMode = nextMode;

    const copy = nextMode === 'signup'
        ? {
            eyebrow: 'Create your workspace',
            title: 'Create a Syncora account.',
            intro: 'Choose how Syncora should greet you, then save Nova decisions, capture Signals, and return to your work from Echoes.'
        }
        : {
            eyebrow: 'Welcome back',
            title: 'Sign in to Syncora.',
            intro: 'Your workspace, shortlists, and captured Signals stay connected to your account.'
        };

    $('#authEyebrow')?.replaceChildren(document.createTextNode(copy.eyebrow));
    $('#authTitle')?.replaceChildren(document.createTextNode(copy.title));
    $('#authIntro')?.replaceChildren(document.createTextNode(copy.intro));

    $$('.auth-mode-button').forEach(button => {
        const active = button.dataset.authMode === nextMode;
        button.classList.toggle('active', active);
        button.setAttribute('aria-selected', active ? 'true' : 'false');
    });

    if (authDisplayNameInput) {
        const creatingAccount = nextMode === 'signup';
        authDisplayNameInput.disabled = !creatingAccount;
        authDisplayNameInput.required = creatingAccount;

        if (!creatingAccount) {
            authDisplayNameInput.value = '';
        }
    }

    if (authPasswordInput) {
        authPasswordInput.autocomplete = nextMode === 'signup' ? 'new-password' : 'current-password';
        authPasswordInput.placeholder = nextMode === 'signup' ? 'Create a password' : 'Enter your password';
    }

    setAuthMessage();
}

$$('.auth-mode-button').forEach(button => {
    button.addEventListener('click', () => setAuthMode(button.dataset.authMode));
});


function initAuthJumpLinks() {
    $$('[data-auth-jump]').forEach(link => {
        link.addEventListener('click', () => {
            const mode = link.dataset.authJump || 'login';
            setAuthMode(mode);

            window.setTimeout(() => {
                if (mode === 'signup') {
                    authDisplayNameInput?.focus({ preventScroll: true });
                } else {
                    authEmailInput?.focus({ preventScroll: true });
                }
            }, 500);
        });
    });
}

function initScrollReveal() {
    const elements = $$('.reveal-on-scroll');

    if (!elements.length) {
        return;
    }

    if (
        window.matchMedia
        &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
        elements.forEach(element => element.classList.add('is-visible'));
        return;
    }

    const observer = new IntersectionObserver(
        entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            });
        },
        {
            rootMargin: '0px 0px -10% 0px',
            threshold: 0.12
        }
    );

    elements.forEach(element => observer.observe(element));
}

function initLandingScrollDynamics() {
    if (PAGE_KIND !== 'auth') {
        return;
    }

    const root = document.documentElement;

    const update = () => {
        const scrollRange =
            Math.max(
                document.documentElement.scrollHeight - window.innerHeight,
                1
            );

        const progress =
            Math.min(
                1,
                Math.max(
                    0,
                    window.scrollY / scrollRange
                )
            );

        root.style.setProperty('--landing-scroll', progress.toFixed(4));
        root.style.setProperty('--landing-scroll-px', `${window.scrollY}px`);
    };

    update();
    window.addEventListener('scroll', update, { passive: true });
}

function restorePulsarHandoff() {
    if (CURRENT_PAGE !== 'pulsar-workflow' || !$('#blueprintForm')) {
        return;
    }

    const raw = sessionStorage.getItem('syncoraPulsarHandoff');
    if (!raw) return;

    try {
        const handoff = JSON.parse(raw);
        const track = handoff?.selectedTrack;
        if (!track?.title || !track?.artist) return;

        selectedTrack = track;
        currentNovaSessionId = handoff.currentNovaSessionId || null;

        $('#blueprintSong').value = track.title;
        $('#blueprintArtist').value = track.artist;

        currentPulsarEditDurationSeconds =
            Number(handoff.targetDuration)
            ||
            30;

        if ($('#pulsarEditingContext') && handoff.creativeIntent) {
            $('#pulsarEditingContext').value = handoff.creativeIntent;
        }

        const tags = (track.matchedTags || []).slice(0, 2).join(', ');
        const rankIndex = Math.max(0, Number(track.rank || 1) - 1);

        $('#selectedTrackName').textContent = `${track.title} — ${track.artist}`;
        $('#selectedTrackMeta').textContent =
            `${novaOptionLabel(rankIndex)} · ${novaRankLabel(rankIndex)}` +
            (tags ? ` · ${tags}` : '') +
            ` · ${currentPulsarEditDurationSeconds}s edit`;
        $('#selectedTrackBanner').classList.remove('hidden');
    } catch (error) {
        console.error('Could not restore Nova → Pulsar handoff:', error);
    } finally {
        sessionStorage.removeItem('syncoraPulsarHandoff');
    }
}

function restoreDeferredSignal() {
    if (CURRENT_PAGE !== 'pulsar-workflow' || !$('#blueprintForm')) {
        return;
    }

    const raw = sessionStorage.getItem('syncoraDeferredSignal');
    if (!raw) return;

    try {
        const signal = JSON.parse(raw);
        openSavedSignal(signal);

        window.requestAnimationFrame(() => {
            $('#blueprintOutput')?.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        });
    } catch (error) {
        console.error('Could not restore saved Signal:', error);
    } finally {
        sessionStorage.removeItem('syncoraDeferredSignal');
    }
}

function initCosmicPointer() {
    $$('.auth-visual, .landing-tool-card, .landing-principle, .module-intro, .hero-card').forEach(surface => {
        surface.addEventListener('pointermove', event => {
            const rect = surface.getBoundingClientRect();
            const x = ((event.clientX - rect.left) / rect.width) * 100;
            const y = ((event.clientY - rect.top) / rect.height) * 100;
            surface.style.setProperty('--pointer-x', `${x}%`);
            surface.style.setProperty('--pointer-y', `${y}%`);
        });
    });
}

setAuthMode(document.body.dataset.authMode || 'login');
initAuthJumpLinks();
initScrollReveal();
initLandingScrollDynamics();
restorePulsarHandoff();
restoreDeferredSignal();
initCosmicPointer();

// =====================================================
// INITIAL SETUP
// =====================================================

if (PAGE_KIND === 'protected') {
    updateHistory();
}

// =====================================================
// FRONTEND POLISH — MODULE INTROS + NOVA JOURNEY
// =====================================================

let currentNovaJourneyStep = 1;

function setNovaJourneyStep(step) {
    currentNovaJourneyStep =
        Math.max(
            1,
            Math.min(
                Number(step) ||
                1,
                3
            )
        );

    $$(".nova-step")
        .forEach(
            item => {
                const itemStep =
                    Number(
                        item.dataset.novaStep
                    );

                item.classList.remove(
                    "active",
                    "completed",
                    "upcoming"
                );

                item.removeAttribute(
                    "aria-current"
                );

                if (
                    itemStep ===
                    currentNovaJourneyStep
                ) {
                    item.classList.add(
                        "active"
                    );

                    item.setAttribute(
                        "aria-current",
                        "step"
                    );
                } else if (
                    itemStep <
                    currentNovaJourneyStep
                ) {
                    item.classList.add(
                        "completed"
                    );
                } else {
                    item.classList.add(
                        "upcoming"
                    );
                }
            }
        );
}

// =====================================================
// MODULE INTRO BUTTONS
// =====================================================

$$("[data-scroll-target]")
    .forEach(
        button => {
            button.addEventListener(
                "click",
                () => {
                    const target =
                        document.querySelector(
                            button.dataset.scrollTarget
                        );

                    target
                        ?.scrollIntoView({
                            behavior: "smooth",
                            block: "start"
                        });
                }
            );
        }
    );

// =====================================================
// NOVA STEP 1
// =====================================================

$("#novaForm")
    ?.addEventListener(
        "submit",
        () => {
            setNovaJourneyStep(
                1
            );
        }
    );

$("#novaForm")
    ?.addEventListener(
        "reset",
        () => {
            setNovaJourneyStep(
                1
            );
        }
    );

$("#rerunTrackfit")
    ?.addEventListener(
        "click",
        () => {
            setNovaJourneyStep(
                1
            );
        }
    );

// =====================================================
// NOVA STEP 2 / STEP 3
// =====================================================

const novaSongResults =
    $("#songResults");

if (novaSongResults) {
    const novaResultsObserver =
        new MutationObserver(
            () => {
                const recommendationButtons =
                    novaSongResults
                        .querySelectorAll(
                            ".choose-song"
                        );

                if (
                    recommendationButtons.length ===
                    3
                ) {
                    setNovaJourneyStep(
                        2
                    );
                }
            }
        );

    novaResultsObserver.observe(
        novaSongResults,
        {
            childList: true,
            subtree: true
        }
    );

    novaSongResults.addEventListener(
        "click",
        event => {
            const chooseButton =
                event.target.closest(
                    ".choose-song"
                );

            if (!chooseButton) {
                return;
            }

            setNovaJourneyStep(
                3
            );
        }
    );
}


// =====================================================
// INITIAL NOVA JOURNEY STATE
// =====================================================