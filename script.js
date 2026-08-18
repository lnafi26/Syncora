const SUPABASE_URL = 'https://phxusxkhzxllrioxuzkr.supabase.co';
const SUPABASE_KEY = 'sb_publishable_3GHRzFe9g3kgcvTaeTBtyQ_GDih979C';
const db = supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

const AUTH_REDIRECT_URL =
    new URL(
        "./",
        window.location.href
    ).href;

// =====================================================
// SUPABASE AUTHENTICATION
// =====================================================

const authEmailInput = document.getElementById('accountEmail');
const authPasswordInput = document.getElementById('accountPassword');
const authForm = document.getElementById('accountForm');
const authSignupButton = document.getElementById('accountSignupButton');
const authMessage = document.getElementById('accountAuthMessage');

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

function updateAuthUI(session) {
    const user = session?.user || null;

    const signedOutAccount = document.getElementById('signedOutAccount');
    const signedInAccount = document.getElementById('signedInAccount');
    const sidebarName = document.getElementById('sidebarName');
    const sidebarEmail = document.getElementById('sidebarEmail');
    const sidebarAvatar = document.getElementById('sidebarAvatar');
    const topAccountButton = document.getElementById('topAccountButton');
    const signedInName = document.getElementById('signedInName');
    const signedInEmail = document.getElementById('signedInEmail');

    if (user) {
        const displayName = getAccountDisplayName(user);

        signedOutAccount?.classList.add('hidden');
        signedInAccount?.classList.remove('hidden');

        if (sidebarName) {
            sidebarName.textContent = displayName;
        }

        if (sidebarEmail) {
            sidebarEmail.textContent = user.email || '';
        }

        if (sidebarAvatar) {
            sidebarAvatar.textContent = displayName.charAt(0).toUpperCase();
        }

        if (topAccountButton) {
            topAccountButton.textContent = 'Account';
        }

        if (signedInName) {
            signedInName.textContent = displayName;
        }

        if (signedInEmail) {
            signedInEmail.textContent = user.email || '';
        }

        setAuthMessage();
    } else {
        signedOutAccount?.classList.remove('hidden');
        signedInAccount?.classList.add('hidden');

        if (sidebarName) {
            sidebarName.textContent = 'Guest editor';
        }

        if (sidebarEmail) {
            sidebarEmail.textContent = 'Sign in to Synchora';
        }

        if (sidebarAvatar) {
            sidebarAvatar.textContent = 'G';
        }

        if (topAccountButton) {
            topAccountButton.textContent = 'Sign in';
        }

        if (signedInName) {
            signedInName.textContent = 'Signed in';
        }

        if (signedInEmail) {
            signedInEmail.textContent = '';
        }
    }
}

async function signUp() {
    const email = authEmailInput?.value.trim();
    const password = authPasswordInput?.value || "";

    if (!email || !password) {
        setAuthMessage("Please enter an email and password.", "error");
        return;
    }

    if (password.length < 6) {
        setAuthMessage("Your password must be at least 6 characters.", "error");
        return;
    }

    setAuthMessage("Creating your account...");
    authSignupButton?.setAttribute("disabled", "");

    try {
        const { data, error } = await db.auth.signUp({
            email,
            password,
            options: {
                emailRedirectTo:
                    AUTH_REDIRECT_URL
            }
        }); //test

        if (error) {
            const message = error.message?.toLowerCase() || "";

            if (
                message.includes("already registered") ||
                message.includes("already exists")
            ) {
                setAuthMessage(
                    "An account with this email already exists. Log in instead.",
                    "error"
                );
                return;
            }

            if (message.includes("password")) {
                setAuthMessage(error.message, "error");
                return;
            }

            if (message.includes("email")) {
                setAuthMessage(error.message, "error");
                return;
            }

            setAuthMessage(
                "We couldn't create your account. Please try again.",
                "error"
            );

            console.error("Signup error:", error);
            return;
        }

        const identities = data?.user?.identities;

        if (
            data?.user &&
            Array.isArray(identities) &&
            identities.length === 0
        ) {
            setAuthMessage(
                "An account with this email already exists. Log in instead.",
                "error"
            );

            authPasswordInput.value = "";
            return;
        }

        if (data?.session) {
            setAuthMessage();
            closeModal("accountModal");
            showToast("Account created. You are signed in.");
            return;
        }

        if (
            data?.user &&
            Array.isArray(identities) &&
            identities.length > 0
        ) {
            authPasswordInput.value = "";

            setAuthMessage(
                "Account created. Check your email to confirm your address, then sign in.",
                "success"
            );

            return;
        }

        setAuthMessage(
            "We couldn't confirm whether your account was created. Please try again.",
            "error"
        );

        console.warn("Unexpected signup response:", data);
    } catch (error) {
        console.error("Unexpected signup error:", error);

        setAuthMessage(
            "Something went wrong while creating your account. Please try again.",
            "error"
        );
    } finally {
        authSignupButton?.removeAttribute("disabled");
    }
}

async function logIn(event) {
    event?.preventDefault();

    const email =
        authEmailInput?.value.trim();

    const password =
        authPasswordInput?.value
        ||
        "";

    if (
        !email
        ||
        !password
    ) {
        setAuthMessage(
            "Please enter your email and password.",
            "error"
        );

        return;
    }

    const loginButton =
        document.getElementById(
            "accountLoginButton"
        );

    loginButton?.setAttribute(
        "disabled",
        ""
    );

    setAuthMessage(
        "Signing you in..."
    );

    try {
        const {
            error
        } = await db.auth
            .signInWithPassword({
                email,
                password
            });

        if (error) {
            setAuthMessage(
                error.message
                ||
                "Could not sign in. Please try again.",
                "error"
            );

            console.error(
                "Login error:",
                error
            );

            return;
        }

        authPasswordInput.value =
            "";

        setAuthMessage();

        closeModal(
            "accountModal"
        );

        showToast(
            "Signed in."
        );
    } catch (error) {
        console.error(
            "Unexpected login error:",
            error
        );

        setAuthMessage(
            "Could not reach the account service. Check your connection and try again.",
            "error"
        );
    } finally {
        loginButton
            ?.removeAttribute(
                "disabled"
            );
    }
}

async function logOut() {
    const logoutButton =
        document.getElementById(
            "signOutButton"
        );

    logoutButton?.setAttribute(
        "disabled",
        ""
    );

    try {
        const {
            error
        } = await db.auth
            .signOut();

        if (error) {
            showToast(
                "Could not log out. Please try again."
            );

            console.error(
                "Logout error:",
                error
            );

            return;
        }

        closeModal(
            "accountModal"
        );

        showToast(
            "Logged out."
        );
    } catch (error) {
        console.error(
            "Unexpected logout error:",
            error
        );

        showToast(
            "Could not reach the account service."
        );
    } finally {
        logoutButton
            ?.removeAttribute(
                "disabled"
            );
    }
}

authForm?.addEventListener('submit', logIn);
authSignupButton?.addEventListener('click', signUp);

document
    .getElementById('signOutButton')
    ?.addEventListener('click', logOut);

async function initializeAuth() {
    try {
        const {
            data: {
                session
            },
            error
        } = await db.auth
            .getSession();

        if (error) {
            console.error(
                "Session error:",
                error
            );

            updateAuthUI(
                null
            );

            return;
        }

        updateAuthUI(
            session
        );
    } catch (error) {
        console.error(
            "Unexpected session initialization error:",
            error
        );

        updateAuthUI(
            null
        );
    }
}

initializeAuth();

db.auth.onAuthStateChange((event, session) => {
    console.log('Auth event:', event);
    updateAuthUI(session);
    updateHistory();
});

// =====================================================
// SMALL DOM HELPERS
// =====================================================

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

let selectedTrack = null;
let currentBlueprint = null;
let currentNovaSessionId = null;

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
                "Try a different duration or suggestion density.",

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

function showView(name) {
    $$(".view").forEach(view => {
        view.classList.remove("active");
    });

    $$(".nav-item").forEach(item => {
        item.classList.remove("active");
    });

    $(`#${name}View`)?.classList.add("active");

    $(`.nav-item[data-view="${name}"]`)
        ?.classList
        .add("active");

    const [eyebrow, title] =
        pageInfo[name] ||
        pageInfo.dashboard;

    $("#pageEyebrow").textContent = eyebrow;
    $("#pageTitle").textContent = title;

    $("#sidebar")
        ?.classList
        .remove("open");

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });

    if (name === "history") {
        updateHistory();
    }
}

$$("[data-view], [data-go], [data-view-link]")
    .forEach(button => {
        button.addEventListener(
            "click",
            event => {
                event.preventDefault();

                const destination =
                    button.dataset.view ||
                    button.dataset.go ||
                    button.dataset.viewLink;

                showView(destination);
            }
        );
    });

$("#mobileMenu")
    ?.addEventListener(
        "click",
        () => {
            $("#sidebar")
                ?.classList
                .toggle("open");
        }
    );

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
    const submitButton =
        $("#novaSubmitButton");

    if (!submitButton) {
        return;
    }

    if (isLoading) {
        submitButton.disabled =
            true;

        submitButton.dataset
            .defaultLabel =
            submitButton.textContent;

        submitButton.textContent =
            "Nova is building your shortlist…";
    } else {
        submitButton.disabled =
            false;

        submitButton.textContent =
            submitButton.dataset
                .defaultLabel
            ||
            "Generate shortlist →";
    }
}

function renderNovaLoading() {
    $("#songResults").innerHTML =
        Array.from(
            {
                length: 3
            },
            (
                _,
                index
            ) => `
                <article
                    class="song-card nova-loading-card"
                    aria-hidden="true"
                >
                    <div class="song-art nova-loading-art">
                        <span class="match-badge">
                            Option ${index + 1}
                        </span>
                    </div>

                    <div class="song-body">
                        <div class="nova-loading-line wide"></div>
                        <div class="nova-loading-line medium"></div>

                        <div class="song-details">
                            <div class="nova-loading-block"></div>
                            <div class="nova-loading-block"></div>
                            <div class="nova-loading-block"></div>
                        </div>

                        <div class="nova-loading-line wide"></div>
                        <div class="nova-loading-line medium"></div>
                    </div>
                </article>
            `
        )
        .join("");

    $("#novaResults")
        .classList
        .remove("hidden");

    $("#novaResults")
        .scrollIntoView({
            behavior: "smooth"
        });
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

function renderSongResults(results) {
    $("#songResults").innerHTML =
        results
            .map(
                (
                    song,
                    index
                ) => {
                    const matchedTagsText =
                        song.matchedTags.length

                            ? song
                                .matchedTags
                                .join(", ")

                            : "Semantic profile match";

                    const profileTagsText =
                        song.topTags
                            .slice(
                                0,
                                3
                            )
                            .join(", ");

                    const lastfmLink =
                        song.lastfmUrl

                            ? `
                                <a
                                    class="song-source-link"
                                    href="${escapeHtml(song.lastfmUrl)}"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    View on Last.fm ↗
                                </a>
                            `

                            : "";

                    return `
                        <article class="song-card">

                            <div
                                class="song-art"
                                style="
                                    --art-a:${song.colors[0]};
                                    --art-b:${song.colors[1]};
                                "
                            >
                                <span class="match-badge">
                                    Nova ${song.score}
                                </span>
                            </div>

                            <div class="song-body">

                                <div class="song-meta">

                                    <div>
                                        <h3>
                                            ${escapeHtml(song.title)}
                                        </h3>

                                        <p>
                                            ${escapeHtml(song.artist)}
                                        </p>
                                    </div>

                                    <span class="pill">
                                        ${
                                            index === 0
                                                ? "Best match"
                                                : `Option ${index + 1}`
                                        }
                                    </span>

                                </div>


                                <div class="song-details">

                                    <div class="song-detail">
                                        <span>
                                            Nova score
                                        </span>

                                        <strong>
                                            ${song.score}
                                        </strong>
                                    </div>

                                    <div class="song-detail">
                                        <span>
                                            Semantic
                                        </span>

                                        <strong>
                                            ${escapeHtml(song.semanticLabel)}
                                        </strong>
                                    </div>

                                    <div class="song-detail">
                                        <span>
                                            Tag signals
                                        </span>

                                        <strong>
                                            ${song.matchedTags.length}
                                        </strong>
                                    </div>

                                </div>


                                <ul class="fit-reasons">

                                    <li>
                                        ${escapeHtml(song.reason)}
                                    </li>

                                    <li>
                                        Matched: ${escapeHtml(matchedTagsText)}
                                    </li>

                                    ${
                                        profileTagsText
                                            ? `
                                                <li>
                                                    Last.fm profile: ${escapeHtml(profileTagsText)}
                                                </li>
                                            `
                                            : ""
                                    }

                                </ul>

                                ${lastfmLink}

                                <button
                                    class="button primary choose-song"
                                    data-index="${index}"
                                    type="button"
                                >
                                    Choose this song
                                </button>

                            </div>

                        </article>
                    `;
                }
            )
            .join("");

    $$(".choose-song")
        .forEach(
            button => {
                button
                    .addEventListener(
                        "click",
                        async () => {
                            const index =
                                Number(
                                    button.dataset.index
                                );

                            selectedTrack =
                                results[index]
                                ||
                                null;

                            if (!selectedTrack) {
                                return;
                            }

                            await saveSelectedNovaTrack();

                            openHandoff();
                        }
                    );
            }
        );
}

function openHandoff() {
    if (!selectedTrack) {
        return;
    }

    const tags =
        selectedTrack
            .matchedTags
            .slice(
                0,
                2
            )
            .join(", ");

    $("#handoffTrack").innerHTML =
        `
            <strong>
                ${escapeHtml(selectedTrack.title)}
                —
                ${escapeHtml(selectedTrack.artist)}
            </strong>

            <small>
                Nova score ${selectedTrack.score}
                ${
                    tags
                        ? ` · ${escapeHtml(tags)}`
                        : ""
                }
            </small>
        `;

    $("#handoffModal")
        .classList
        .remove("hidden");
}

// =====================================================
// NOVA → PULSAR HANDOFF
// =====================================================

$("#continueToBlueprint")
    ?.addEventListener(
        "click",
        () => {
            if (!selectedTrack) {
                return;
            }

            closeModal(
                "handoffModal"
            );

            showView(
                "pulsar"
            );

            $("#blueprintSong").value =
                selectedTrack.title;

            $("#blueprintArtist").value =
                selectedTrack.artist;

            const novaTargetDuration =
                $("#targetDuration")
                    ?.value;

            if (
                novaTargetDuration
                &&
                $("#pulsarEditDuration")
            ) {
                $("#pulsarEditDuration").value =
                    novaTargetDuration;
            }

            const novaIntent =
                $("#creativeIntent")
                    ?.value
                    ?.trim();

            if (
                novaIntent &&
                !$("#pulsarEditingContext")
                    ?.value
                    ?.trim()
            ) {
                $("#pulsarEditingContext").value =
                    novaIntent;
            }

            $("#selectedTrackName")
                .textContent =
                `${selectedTrack.title} — ${selectedTrack.artist}`;

            const handoffTags =
                selectedTrack
                    .matchedTags
                    .slice(
                        0,
                        2
                    )
                    .join(", ");

            const handoffDuration =
                Number(
                    $("#pulsarEditDuration")
                        ?.value
                );

            $("#selectedTrackMeta")
                .textContent =
                (
                    `Nova score ${selectedTrack.score}`
                    +
                    (
                        handoffTags
                            ? ` · ${handoffTags}`
                            : ""
                    )
                    +
                    (
                        Number.isFinite(handoffDuration)
                            ? ` · ${formatTime(handoffDuration)} edit`
                            : ""
                    )
                );

            $("#selectedTrackBanner")
                .classList
                .remove("hidden");
        }
    );

$("#changeTrackButton")
    ?.addEventListener(
        "click",
        () => {
            selectedTrack =
                null;

            currentNovaSessionId =
                null;

            currentNovaProfile =
                null;

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

    if (
        numericScore >= 85
    ) {
        return "primary";
    }

    if (
        numericScore >= 60
    ) {
        return "secondary";
    }

    return "optional";
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

            $("#pulsarEditDuration").value =
                "30";

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

            const editDurationValue =
                $("#pulsarEditDuration")
                    ?.value
                ||
                "60";

            const editDurationSeconds =
                editDurationValue === "full"
                    ? null
                    : Number(
                        editDurationValue
                    );

            const density =
                $(
                    'input[name="density"]:checked'
                )?.value
                ||
                "balanced";

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
                    "Pulsar is selecting the strongest measured moments and turning them into editing suggestions."
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

                                density,

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
                                    priorityFromChangeScore(
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

                    density,

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
                        "Pulsar identified the strongest measured changes in the track.",

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

function renderBlueprint(blueprint) {
    $("#outputTitle")
        .textContent =
        blueprint.artist
            ? `${blueprint.song} — ${blueprint.artist}`
            : blueprint.song;

    $("#outputSummary")
        .textContent =
        blueprint.summary
        ||
        `${blueprint.cues.length} suggested edit points across ${
            formatTime(
                blueprint.duration
            )
        }.`;

    const editWindow =
        getBlueprintEditWindow(
            blueprint
        );

    $("#cueCount")
        .textContent =
        `${blueprint.cues.length} cues · ${formatTime(editWindow.durationSeconds)} window`;

    const timelineWindowLabel =
        $("#timelineWindowLabel");

    if (timelineWindowLabel) {
        timelineWindowLabel.textContent =
            editWindow.usesExcerpt
                ? `Suggested source window: ${formatTime(editWindow.startSeconds)}–${formatTime(editWindow.endSeconds)} of ${formatTime(blueprint.duration)}. Cue times below are absolute song times.`
                : `Full-track Signal across ${formatTime(blueprint.duration)}. Cue times below are absolute song times.`;
    }

    renderSignalAnalysis(
        blueprint
    );

    const colors = {
        primary:
            "var(--pulsar)",

        secondary:
            "var(--accent)",

        optional:
            "var(--purple)"
    };

    $("#visualTimeline")
        .innerHTML =
        blueprint.cues
            .map(
                (
                    cue,
                    index
                ) => {
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

                    return `
                        <button
                            class="timeline-marker"
                            type="button"
                            data-time="${escapeHtml(cue.time)}"
                            title="${escapeHtml(
                                cue.title ||
                                cue.moment
                            )}"
                            style="
                                left:${percentage}%;
                                --marker:${colors[cue.priority] || "var(--pulsar)"};
                                --label-top:${index % 2 ? "24px" : "-42px"};
                            "
                        ></button>
                    `;
                }
            )
            .join("");

    $("#cueTableBody")
        .innerHTML =
        blueprint.cues
            .map(
                (
                    cue,
                    index
                ) => {
                    const scoreMarkup =
                        Number.isFinite(
                            Number(
                                cue.changeScore
                            )
                        )
                        &&
                        Number(
                            cue.changeScore
                        ) > 0

                            ? `
                                <small class="cue-score">
                                    ${Number(cue.changeScore)}/100
                                </small>
                            `

                            : "";

                    return `
                        <tr>

                            <td>
                                <strong>
                                    ${escapeHtml(cue.time)}
                                </strong>
                            </td>

                            <td>

                                <span
                                    class="priority-chip ${escapeHtml(cue.priority)}"
                                >
                                    ${escapeHtml(
                                        capitalize(
                                            cue.priority
                                        )
                                    )}
                                </span>

                                ${scoreMarkup}

                            </td>

                            <td>

                                <div class="cue-moment">

                                    <strong>
                                        ${escapeHtml(
                                            cue.title ||
                                            "Musical change"
                                        )}
                                    </strong>

                                    <small>
                                        ${escapeHtml(
                                            cue.moment
                                        )}
                                    </small>

                                </div>

                            </td>

                            <td>
                                ${escapeHtml(
                                    cue.suggestion
                                )}
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
                }
            )
            .join("");

    $$(".edit-cue")
        .forEach(
            button => {
                button
                    .addEventListener(
                        "click",
                        () => {
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

                            if (
                                newSuggestion
                                    ?.trim()
                            ) {
                                cue.suggestion =
                                    newSuggestion
                                        .trim();

                                renderBlueprint(
                                    currentBlueprint
                                );
                            }
                        }
                    );
            }
        );

    $("#blueprintOutput")
        .classList
        .remove("hidden");

    $("#blueprintOutput")
        .scrollIntoView({
            behavior: "smooth"
        });
}

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

    if ($("#pulsarEditDuration")) {
        // Existing Echoes do not yet persist excerpt metadata,
        // so reopen them as full-track Signals.
        $("#pulsarEditDuration").value =
            "full";
    }

    $("#pulsarEditingContext").value =
        "";

    $$('input[name="density"]')
        .forEach(
            input => {
                input.checked =
                    input.value ===
                    signal.density;
            }
        );

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

    showView(
        "pulsar"
    );

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
        $(".topbar")
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
// INITIAL SETUP
// =====================================================

updateHistory();

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
// NOVA → PULSAR WORKSPACE SCROLL
// =====================================================

$("#continueToBlueprint")
    ?.addEventListener(
        "click",
        () => {
            window.requestAnimationFrame(
                () => {
                    $("#pulsarWorkflow")
                        ?.scrollIntoView({
                            behavior: "smooth",
                            block: "start"
                        });
                }
            );
        }
    );

// =====================================================
// INITIAL NOVA JOURNEY STATE
// =====================================================

setNovaJourneyStep(1);