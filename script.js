const SUPABASE_URL = 'https://phxusxkhzxllrioxuzkr.supabase.co';
const SUPABASE_KEY = 'sb_publishable_3GHRzFe9g3kgcvTaeTBtyQ_GDih979C';

const db = supabase.createClient(
    SUPABASE_URL,
    SUPABASE_KEY
);


// =====================================================
// SUPABASE AUTHENTICATION
// =====================================================

const authEmailInput =
    document.getElementById('accountEmail');

const authPasswordInput =
    document.getElementById('accountPassword');

const authForm =
    document.getElementById('accountForm');

const authSignupButton =
    document.getElementById('accountSignupButton');

const authMessage =
    document.getElementById('accountAuthMessage');


function setAuthMessage(message = '', type = '') {
    if (!authMessage) return;

    authMessage.textContent = message;

    authMessage.classList.remove(
        'error',
        'success'
    );

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

    const emailName =
        user?.email?.split('@')[0] ||
        'Editor';

    return emailName
        .replace(/[._-]+/g, ' ')
        .replace(
            /\b\w/g,
            character =>
                character.toUpperCase()
        );
}


function updateAuthUI(session) {
    const user =
        session?.user || null;

    const signedOutAccount =
        document.getElementById(
            'signedOutAccount'
        );

    const signedInAccount =
        document.getElementById(
            'signedInAccount'
        );

    const sidebarName =
        document.getElementById(
            'sidebarName'
        );

    const sidebarEmail =
        document.getElementById(
            'sidebarEmail'
        );

    const sidebarAvatar =
        document.getElementById(
            'sidebarAvatar'
        );

    const topAccountButton =
        document.getElementById(
            'topAccountButton'
        );

    const signedInName =
        document.getElementById(
            'signedInName'
        );

    const signedInEmail =
        document.getElementById(
            'signedInEmail'
        );


    if (user) {
        const displayName =
            getAccountDisplayName(user);

        signedOutAccount?.classList.add(
            'hidden'
        );

        signedInAccount?.classList.remove(
            'hidden'
        );

        if (sidebarName) {
            sidebarName.textContent =
                displayName;
        }

        if (sidebarEmail) {
            sidebarEmail.textContent =
                user.email || '';
        }

        if (sidebarAvatar) {
            sidebarAvatar.textContent =
                displayName
                    .charAt(0)
                    .toUpperCase();
        }

        if (topAccountButton) {
            topAccountButton.textContent =
                'Account';
        }

        if (signedInName) {
            signedInName.textContent =
                displayName;
        }

        if (signedInEmail) {
            signedInEmail.textContent =
                user.email || '';
        }

        setAuthMessage();
    }

    else {
        signedOutAccount?.classList.remove(
            'hidden'
        );

        signedInAccount?.classList.add(
            'hidden'
        );

        if (sidebarName) {
            sidebarName.textContent =
                'Guest editor';
        }

        if (sidebarEmail) {
            sidebarEmail.textContent =
                'Sign in to Synchora';
        }

        if (sidebarAvatar) {
            sidebarAvatar.textContent =
                'G';
        }

        if (topAccountButton) {
            topAccountButton.textContent =
                'Sign in';
        }

        if (signedInName) {
            signedInName.textContent =
                'Signed in';
        }

        if (signedInEmail) {
            signedInEmail.textContent =
                '';
        }
    }
}


async function signUp() {

    const email =
        authEmailInput?.value.trim();

    const password =
        authPasswordInput?.value || "";


    if (!email || !password) {

        setAuthMessage(
            "Please enter an email and password.",
            "error"
        );

        return;
    }


    if (password.length < 6) {

        setAuthMessage(
            "Your password must be at least 6 characters.",
            "error"
        );

        return;
    }


    setAuthMessage(
        "Creating your account..."
    );


    authSignupButton?.setAttribute(
        "disabled",
        ""
    );


    try {

        const { data, error } =
            await db.auth.signUp({

                email,

                password,

                options: {
                    emailRedirectTo:
                        window.location.origin
                }

            });


        if (error) {

            const message =
                error.message
                    ?.toLowerCase() ||
                "";


            if (
                message.includes(
                    "already registered"
                ) ||
                message.includes(
                    "already exists"
                )
            ) {

                setAuthMessage(
                    "An account with this email already exists. Log in instead.",
                    "error"
                );

                return;
            }


            if (
                message.includes(
                    "password"
                )
            ) {

                setAuthMessage(
                    error.message,
                    "error"
                );

                return;
            }


            if (
                message.includes(
                    "email"
                )
            ) {

                setAuthMessage(
                    error.message,
                    "error"
                );

                return;
            }


            setAuthMessage(
                "We couldn't create your account. Please try again.",
                "error"
            );


            console.error(
                "Signup error:",
                error
            );


            return;
        }


        const identities =
            data?.user?.identities;


        if (
            data?.user &&
            Array.isArray(
                identities
            ) &&
            identities.length === 0
        ) {

            setAuthMessage(
                "An account with this email already exists. Log in instead.",
                "error"
            );


            authPasswordInput.value =
                "";


            return;
        }


        if (data?.session) {

            setAuthMessage();


            closeModal(
                "accountModal"
            );


            showToast(
                "Account created. You are signed in."
            );


            return;
        }


        if (
            data?.user &&
            Array.isArray(
                identities
            ) &&
            identities.length > 0
        ) {

            authPasswordInput.value =
                "";


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


        console.warn(
            "Unexpected signup response:",
            data
        );

    }

    catch (error) {

        console.error(
            "Unexpected signup error:",
            error
        );


        setAuthMessage(
            "Something went wrong while creating your account. Please try again.",
            "error"
        );

    }

    finally {

        authSignupButton
            ?.removeAttribute(
                "disabled"
            );

    }

}


async function logIn(event) {
    event?.preventDefault();


    const email =
        authEmailInput?.value.trim();

    const password =
        authPasswordInput?.value || '';


    if (!email || !password) {
        setAuthMessage(
            'Please enter your email and password.',
            'error'
        );

        return;
    }


    setAuthMessage(
        'Signing you in...'
    );


    const { error } =
        await db.auth.signInWithPassword({
            email,
            password
        });


    if (error) {
        setAuthMessage(
            error.message,
            'error'
        );

        console.error(
            'Login error:',
            error
        );

        return;
    }


    authPasswordInput.value = '';

    setAuthMessage();

    closeModal(
        'accountModal'
    );

    showToast(
        'Signed in.'
    );
}


async function logOut() {
    const { error } =
        await db.auth.signOut();


    if (error) {
        showToast(
            'Could not log out. Please try again.'
        );

        console.error(
            'Logout error:',
            error
        );

        return;
    }


    closeModal(
        'accountModal'
    );

    showToast(
        'Logged out.'
    );
}


authForm?.addEventListener(
    'submit',
    logIn
);


authSignupButton?.addEventListener(
    'click',
    signUp
);


document
    .getElementById('signOutButton')
    ?.addEventListener(
        'click',
        logOut
    );


async function initializeAuth() {
    const {
        data: { session },
        error
    } =
        await db.auth.getSession();


    if (error) {
        console.error(
            'Session error:',
            error
        );

        updateAuthUI(null);

        return;
    }


    updateAuthUI(session);
}


initializeAuth();


db.auth.onAuthStateChange(
    (event, session) => {
        console.log(
            'Auth event:',
            event
        );

        updateAuthUI(session);

        updateHistory();
    }
);


// =====================================================
// SMALL DOM HELPERS
// =====================================================

const $ =
    selector =>
        document.querySelector(selector);


const $$ =
    selector => [
        ...document.querySelectorAll(
            selector
        )
    ];


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

const SYNCORA_API_URL =
    "http://127.0.0.1:8000";

const NOVA_REQUEST_TIMEOUT_MS =
    120000;

let currentNovaProfile = null;

let novaRequestController = null;


// =====================================================
// NAVIGATION
// =====================================================

function showView(name) {

    $$(".view").forEach(
        view => {
            view.classList.remove(
                "active"
            );
        }
    );


    $$(".nav-item").forEach(
        item => {
            item.classList.remove(
                "active"
            );
        }
    );


    $(`#${name}View`)
        ?.classList
        .add("active");


    $(
        `.nav-item[data-view="${name}"]`
    )
        ?.classList
        .add("active");


    const [eyebrow, title] =
        pageInfo[name] ||
        pageInfo.dashboard;


    $("#pageEyebrow").textContent =
        eyebrow;


    $("#pageTitle").textContent =
        title;


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


$$(
    "[data-view], [data-go], [data-view-link]"
).forEach(button => {

    button.addEventListener(
        "click",
        event => {

            event.preventDefault();


            const destination =
                button.dataset.view ||
                button.dataset.go ||
                button.dataset.viewLink;


            showView(
                destination
            );

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

async function saveNovaSession(
    rankedSongs
) {

    const {
        data: { user },
        error: userError
    } = await db.auth.getUser();


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
        $(
            'input[name="mood"]:checked'
        )?.value;


    const pace =
        $(
            'input[name="pace"]:checked'
        )?.value;


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
                    .trim() || null

        })

        .select("id")

        .single();


    if (sessionError) {

        console.error(
            "Could not save Nova session:",
            sessionError
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
        error: recommendationError
    } = await db

        .from("nova_recommendations")

        .insert(
            recommendations
        );


    if (recommendationError) {

        console.error(
            "Could not save Nova recommendations:",
            recommendationError
        );


        await db
            .from("nova_sessions")
            .delete()
            .eq(
                "id",
                currentNovaSessionId
            );


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
}


async function saveSelectedNovaTrack() {

    if (
        !currentNovaSessionId ||
        !selectedTrack
    ) {
        return;
    }


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
}


// =====================================================
// NOVA API HELPERS
// =====================================================

function getSelectedOptionText(
    selector
) {

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


function getCheckedChoiceText(
    name
) {

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


function getNovaApiErrorMessage(
    response,
    data
) {

    const detail =
        data?.detail;


    if (
        detail &&
        typeof detail === "object"
    ) {

        if (detail.error) {
            return detail.error;
        }


        if (detail.message) {
            return detail.message;
        }

    }


    if (
        typeof detail === "string"
    ) {
        return detail;
    }


    if (
        response.status === 422
    ) {

        return (
            "Nova could not use one or more fields in the brief."
        );

    }


    if (
        response.status === 504
    ) {

        return (
            "Nova took too long to build the music profile."
        );

    }


    if (
        response.status >= 500
    ) {

        return (
            "Nova's recommendation service is temporarily unavailable."
        );

    }


    return (
        `Nova request failed with status ${response.status}.`
    );

}


async function fetchNovaRecommendations(
    payload
) {

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

        }

        catch (parseError) {

            console.error(
                "Nova returned invalid JSON:",
                parseError
            );

        }


        if (!response.ok) {

            throw new Error(
                getNovaApiErrorMessage(
                    response,
                    data
                )
            );

        }


        if (
            !data ||
            !Array.isArray(
                data.recommendations
            ) ||
            data.recommendations.length !== 3
        ) {

            throw new Error(
                "Nova returned an incomplete shortlist."
            );

        }


        return data;

    }

    catch (error) {

        if (
            error?.name ===
            "AbortError"
        ) {

            throw new Error(
                "Nova took too long to respond. Please try again."
            );

        }


        if (
            error instanceof TypeError
        ) {

            throw new Error(
                "Could not reach the Syncora backend. Make sure FastAPI is running."
            );

        }


        throw error;

    }

    finally {

        window.clearTimeout(
            timeoutId
        );


        novaRequestController =
            null;

    }

}


function escapeHtml(
    value
) {

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


function safeLastfmUrl(
    value
) {

    if (!value) {
        return null;
    }


    try {

        const url =
            new URL(
                value
            );


        const isLastfmHost =
            url.hostname ===
                "last.fm"
            ||
            url.hostname.endsWith(
                ".last.fm"
            );


        if (
            url.protocol !==
                "https:"
            ||
            !isLastfmHost
        ) {

            return null;

        }


        return url.href;

    }

    catch {

        return null;

    }

}


function makeSongColors(
    title,
    artist
) {

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


function semanticFitLabel(
    fit
) {

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


function normalizeNovaRecommendations(
    data
) {

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


function setNovaLoading(
    isLoading
) {

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

    }

    else {

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
                length:
                    3
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
            behavior:
                "smooth"
        });

}


function renderNovaError(
    message
) {

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


            if (
                novaRequestController
            ) {
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
                    data.profile
                    ||
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

                }

                else {

                    showToast(
                        "Nova shortlist ready."
                    );

                }


                console.log(
                    "Nova backend response:",
                    data
                );

            }

            catch (error) {

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

            }

            finally {

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
                    behavior:
                        "smooth"
                });

        }
    );


function renderSongResults(
    results
) {

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
                                results[
                                    index
                                ]
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


            $("#songDuration").value =
                $("#targetDuration").value
                ||
                60;


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

        }
    );


// =====================================================
// PULSAR
// =====================================================

$("#loadDemoBlueprint")
    ?.addEventListener(
        "click",
        () => {
            selectedTrack = null;
            currentNovaSessionId = null;

            $("#blueprintSong").value =
                "Signal Rush";


            $("#songDuration").value =
                60;


            $("#musicProfile").value =
                "dynamic";

        }
    );


$("#blueprintForm")
    ?.addEventListener(
        "submit",
        event => {

            event.preventDefault();


            const song =
                $("#blueprintSong")
                    .value
                    .trim();


            const duration =
                Number(
                    $("#songDuration")
                        .value
                );


            const musicProfile =
                $("#musicProfile").value;


            const density =
                $(
                    'input[name="density"]:checked'
                )?.value ||
                "balanced";


            const selectedTypes =
                $$(
                    'input[name="cueType"]:checked'
                )
                    .map(
                        box =>
                            box.value
                    );


            if (
                !selectedTypes.length
            ) {

                showToast(
                    "Choose at least one suggestion type."
                );

                return;
            }


            const cameFromNova =
                selectedTrack &&
                selectedTrack.title === song &&
                currentNovaSessionId;


            currentBlueprint = {

                id:
                    Date.now(),

                song,

                artist:
                    cameFromNova
                        ? selectedTrack.artist
                        : null,

                duration,

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

                cues:
                    createCues(
                        duration,
                        density,
                        selectedTypes
                    )

            };


            renderBlueprint(
                currentBlueprint
            );

        }
    );


function createCues(
    duration,
    density,
    types
) {

    const cueAmounts = {

        minimal:
            4,

        balanced:
            6,

        detailed:
            9

    };


    const count =
        cueAmounts[density] ||
        6;


    const suggestions = {

        cut: [
            "Cut to a new angle",
            "Use a clean match cut"
        ],

        transition: [
            "Use a short crossfade",
            "Try a whip transition"
        ],

        effect: [
            "Add a brightness flash",
            "Add a subtle impact shake"
        ],

        speed: [
            "Begin a speed ramp",
            "Return to normal speed"
        ],

        text: [
            "Reveal text here",
            "Remove text on the beat"
        ]

    };


    return Array.from(

        {
            length:
                count
        },

        (
            _,
            index
        ) => {

            const seconds =
                Math.round(

                    (
                        (index + 1) /
                        (count + 1)
                    ) *

                    duration

                );


            const type =
                types[
                    index %
                    types.length
                ];


            const options =
                suggestions[type];


            let priority =
                "optional";


            if (
                index === 0 ||
                index ===
                    Math.floor(
                        count / 2
                    )
            ) {

                priority =
                    "primary";

            }

            else if (
                index % 2 === 0
            ) {

                priority =
                    "secondary";

            }


            return {

                time:
                    formatTime(
                        seconds
                    ),

                seconds,

                type,

                priority,

                moment:
                    index ===
                    Math.floor(
                        count / 2
                    )
                        ? "Major musical change"
                        : "Rhythmic accent",

                suggestion:
                    options[
                        index %
                        options.length
                    ]

            };

        }

    );

}


function renderBlueprint(
    blueprint
) {

    $("#outputTitle")
        .textContent =
        blueprint.song;


    $("#outputSummary")
        .textContent =
        `${blueprint.cues.length} suggested edit points across ${formatTime(
            blueprint.duration
        )}.`;


    $("#cueCount")
        .textContent =
        `${blueprint.cues.length} cues`;


    const colors = {

        primary:
            "var(--accent)",

        secondary:
            "var(--blue)",

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
                        (
                            cue.seconds /
                            blueprint.duration
                        ) *
                        100;


                    return `
                        <button
                            class="timeline-marker"
                            data-time="${cue.time}"
                            style="
                                left:${percentage}%;
                                --marker:${colors[cue.priority]};
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

                    return `
                        <tr>

                            <td>
                                <strong>
                                    ${cue.time}
                                </strong>
                            </td>


                            <td>

                                <span
                                    class="priority-chip ${cue.priority}"
                                >
                                    ${capitalize(
                                        cue.priority
                                    )}
                                </span>

                            </td>


                            <td>
                                ${cue.moment}
                            </td>


                            <td>
                                ${cue.suggestion}
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
            behavior:
                "smooth"
        });

}


// =====================================================
// PULSAR DATABASE
// =====================================================

async function savePulsarSignal() {

    if (!currentBlueprint) {
        return null;
    }


    const {
        data: { user },
        error: userError
    } = await db.auth.getUser();


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
                currentBlueprint.novaSessionId,

            song_title:
                currentBlueprint.song,

            song_artist:
                currentBlueprint.artist,

            song_duration_seconds:
                currentBlueprint.duration,

            music_profile:
                currentBlueprint.musicProfile,

            density:
                currentBlueprint.density,

            cue_types:
                currentBlueprint.selectedTypes

        })
        .select("id")
        .single();


    if (signalError) {

        console.error(
            "Could not save Pulsar Signal:",
            signalError
        );

        showToast(
            "Signal could not be saved."
        );

        return null;
    }


    const cueRows =
        currentBlueprint.cues.map(
            (cue, index) => ({

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
        error: cuesError
    } = await db
        .from("pulsar_cues")
        .insert(cueRows);


    if (cuesError) {

        console.error(
            "Could not save Pulsar cues:",
            cuesError
        );


        await db
            .from("pulsar_signals")
            .delete()
            .eq(
                "id",
                signal.id
            );


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
}


// =====================================================
// SAVE / COPY / ECHOES
// =====================================================

$("#saveBlueprint")
    ?.addEventListener(
        "click",
        async () => {

            if (
                !currentBlueprint
            ) {
                return;
            }


            const signalId =
                await savePulsarSignal();


            if (
                !signalId
            ) {
                return;
            }


            await updateHistory();


            showToast(
                "Signal captured."
            );

        }
    );


$("#copyBlueprint")
    ?.addEventListener(
        "click",
        async () => {

            if (
                !currentBlueprint
            ) {
                return;
            }


            const notes =
                currentBlueprint
                    .cues

                    .map(
                        cue =>
                            `${cue.time} — ${cue.suggestion}`
                    )

                    .join(
                        "\n"
                    );


            try {

                await navigator
                    .clipboard
                    .writeText(

                        `${currentBlueprint.song}\n\n${notes}`

                    );


                showToast(
                    "Signal cloned."
                );

            }

            catch {

                showToast(
                    "Clipboard access is unavailable."
                );

            }

        }
    );


async function getHistory() {

    const {
        data: { user },
        error: userError
    } = await db.auth.getUser();


    if (userError) {

        console.error(
            "Could not get current user:",
            userError
        );

        return [];
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
                ascending: false
            }
        );


    if (error) {

        console.error(
            "Could not load Echoes:",
            error
        );

        return [];
    }


    return (data || []).map(
        signal => {

            const cues =
                (signal.pulsar_cues || [])

                    .sort(
                        (a, b) =>
                            a.cue_order -
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
                    signal.cue_types || [],

                createdAt:
                    signal.created_at,

                created:
                    new Date(
                        signal.created_at
                    ).toLocaleDateString(),

                cues

            };

        }
    );
}


function openSavedSignal(signal) {

    currentBlueprint =
        structuredClone(signal);


    $("#blueprintSong").value =
        signal.song || "";


    $("#songDuration").value =
        signal.duration || 60;


    $("#musicProfile").value =
        signal.musicProfile || "dynamic";


    $$('input[name="density"]')
        .forEach(input => {

            input.checked =
                input.value ===
                signal.density;

        });


    $$('input[name="cueType"]')
        .forEach(input => {

            input.checked =
                signal.selectedTypes
                    ?.includes(
                        input.value
                    ) || false;

        });


    currentNovaSessionId =
        signal.novaSessionId || null;


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
                []
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

    }

    else {

        selectedTrack = null;


        $("#selectedTrackBanner")
            .classList
            .add("hidden");

    }


    showView(
        "pulsar"
    );


    renderBlueprint(
        currentBlueprint
    );

}


function renderHistoryInto(
    container,
    items
) {

    if (!container) {
        return;
    }


    if (
        !items.length
    ) {

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
        .forEach(button => {

            button.addEventListener(
                "click",
                () => {

                    const signal =
                        items.find(
                            item =>
                                String(item.id) ===
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

        });

}


$("#clearHistory")
    ?.addEventListener(
        "click",
        async () => {

            const {
                data: { user },
                error: userError
            } = await db.auth.getUser();


            if (
                userError ||
                !user
            ) {

                showToast(
                    "Sign in to manage your Echoes."
                );

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

        }
    );


async function updateHistory() {

    const history =
        await getHistory();


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
        Number(seconds) || 0;


    const minutes =
        Math.floor(
            safeSeconds / 60
        );


    const remaining =
        Math.round(
            safeSeconds % 60
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
            .toUpperCase() +

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
                Number(step) || 1,
                3
            )
        );


    $$(".nova-step")
        .forEach(item => {

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

            }

            else if (
                itemStep <
                currentNovaJourneyStep
            ) {

                item.classList.add(
                    "completed"
                );

            }

            else {

                item.classList.add(
                    "upcoming"
                );

            }

        });

}


// =====================================================
// MODULE INTRO BUTTONS
// =====================================================

$$(
    "[data-scroll-target]"
)
    .forEach(button => {

        button.addEventListener(
            "click",
            () => {

                const target =
                    document.querySelector(
                        button.dataset.scrollTarget
                    );


                target?.scrollIntoView({
                    behavior:
                        "smooth",

                    block:
                        "start"
                });

            }
        );

    });


// =====================================================
// NOVA STEP 1
// =====================================================

// Any new submission represents a fresh brief.
// The existing backend submit listener still does all
// of the real Nova work.

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
// NOVA STEP 2
// =====================================================

// Your existing Nova frontend replaces #songResults:
//
// 1. Loading placeholders
// 2. An error state
// 3. Three real recommendations
//
// We only advance to Step 2 when all three real
// "Choose this song" buttons actually exist.
//
// This means the UI reflects the real backend result,
// not merely the fact that the user clicked Submit.

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
            childList:
                true,

            subtree:
                true
        }
    );


    // =================================================
    // NOVA STEP 3
    // =================================================
    //
    // The recommendation cards are created dynamically,
    // so delegation lets one listener handle whichever
    // three songs Nova returns.

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
// NOVA → PULSAR HANDOFF
// =====================================================

// Normal navigation to Pulsar intentionally begins at
// the new explanation section.
//
// The Nova handoff is different. Once the user has
// already chosen a song, the existing handoff code
// switches to Pulsar and populates the selected track.
//
// This listener then moves directly to the workspace
// so that the user does not have to manually scroll
// past the introduction they have effectively already
// progressed beyond.

$("#continueToBlueprint")
    ?.addEventListener(
        "click",
        () => {

            window.requestAnimationFrame(
                () => {

                    $("#pulsarWorkflow")
                        ?.scrollIntoView({
                            behavior:
                                "smooth",

                            block:
                                "start"
                        });

                }
            );

        }
    );


// =====================================================
// INITIAL NOVA JOURNEY STATE
// =====================================================

setNovaJourneyStep(
    1
);