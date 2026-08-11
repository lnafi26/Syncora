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


    // -----------------------------
    // Basic validation
    // -----------------------------

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


        // -----------------------------
        // Supabase returned an error
        // -----------------------------

        if (error) {

            const message =
                error.message
                    ?.toLowerCase() ||
                "";


            // This usually appears when
            // email confirmation is disabled.
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


        // -----------------------------
        // DUPLICATE ACCOUNT DETECTION
        //
        // With email confirmation enabled,
        // Supabase may return a fake user
        // instead of "already registered".
        //
        // The fake duplicate response can
        // contain an empty identities array.
        // -----------------------------

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


        // -----------------------------
        // Account immediately signed in
        //
        // This would happen if email
        // confirmation were disabled.
        // -----------------------------

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


        // -----------------------------
        // Genuine new account awaiting
        // email verification
        // -----------------------------

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


        // -----------------------------
        // Unexpected response fallback
        // -----------------------------

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
// FAKE SONGS FOR THE PROTOTYPE ONLY
// =====================================================

const songs = [

    {
        title:
            "Afterglow Circuit",

        artist:
            "Nova Vale",

        mood:
            "dreamy",

        pace:
            "moderate",

        type:
            "cinematic",

        bpm:
            112,

        editability:
            92,

        energy:
            "Rising",

        colors: [
            "#3d72ff",
            "#8d59ff"
        ]
    },


    {
        title:
            "Signal Rush",

        artist:
            "Kairo Frame",

        mood:
            "intense",

        pace:
            "fast",

        type:
            "sports",

        bpm:
            148,

        editability:
            96,

        energy:
            "Explosive",

        colors: [
            "#ff6b4a",
            "#ffcb57"
        ]
    },


    {
        title:
            "Still Between Us",

        artist:
            "Mara Sol",

        mood:
            "emotional",

        pace:
            "slow",

        type:
            "emotional",

        bpm:
            78,

        editability:
            86,

        energy:
            "Gradual",

        colors: [
            "#395c7b",
            "#b778ad"
        ]
    },


    {
        title:
            "Midnight Architecture",

        artist:
            "Vector Bloom",

        mood:
            "dark",

        pace:
            "dynamic",

        type:
            "gaming",

        bpm:
            124,

        editability:
            90,

        energy:
            "Layered",

        colors: [
            "#10143f",
            "#7652a8"
        ]
    },


    {
        title:
            "Open Horizon",

        artist:
            "Elio North",

        mood:
            "uplifting",

        pace:
            "moderate",

        type:
            "travel",

        bpm:
            98,

        editability:
            88,

        energy:
            "Warm",

        colors: [
            "#3b8e8a",
            "#e0a758"
        ]
    },


    {
        title:
            "Velocity Bloom",

        artist:
            "Rin Atlas",

        mood:
            "confident",

        pace:
            "fast",

        type:
            "social",

        bpm:
            136,

        editability:
            93,

        energy:
            "Driving",

        colors: [
            "#42b883",
            "#245d82"
        ]
    }

];


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

async function saveNovaSession(rankedSongs) {

    const {
        data: { user },
        error: userError
    } = await db.auth.getUser();


    if (userError) {
        console.error(
            "Could not get current user:",
            userError
        );

        return null;
    }


    // Guests can still use Nova,
    // but their generation is not saved.
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


    // ---------------------------------------------
    // Create the parent Nova session
    // ---------------------------------------------

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
            "Nova generated, but could not be saved."
        );

        return null;
    }


    currentNovaSessionId =
        novaSession.id;


    // ---------------------------------------------
    // Create the three recommendation rows
    // ---------------------------------------------

    const recommendations =
        rankedSongs.map(
            (song, index) => ({

                nova_session_id:
                    currentNovaSessionId,

                rank:
                    index + 1,

                title:
                    song.title,

                artist:
                    song.artist,

                bpm:
                    song.bpm,

                editability:
                    song.editability,

                energy:
                    song.energy,

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

        showToast(
            "Nova session saved, but recommendations could not be saved."
        );

        return currentNovaSessionId;
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
                selectedTrack.bpm,

            selected_track_energy:
                selectedTrack.energy,

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

        return;
    }


    console.log(
        "Selected Nova track saved:",
        selectedTrack.title
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


            const mood =
                $(
                    'input[name="mood"]:checked'
                )?.value;


            const pace =
                $(
                    'input[name="pace"]:checked'
                )?.value;


            const type =
                $("#videoType").value;


            const rankedSongs =
                songs
                    .map(
                        song => {

                            let score =
                                70;


                            if (
                                song.mood ===
                                mood
                            ) {
                                score +=
                                    12;
                            }


                            if (
                                song.pace ===
                                pace
                            ) {
                                score +=
                                    10;
                            }


                            if (
                                song.type ===
                                type
                            ) {
                                score +=
                                    8;
                            }


                            return {
                                ...song,

                                score:
                                    Math.min(
                                        score,
                                        99
                                    )
                            };

                        }
                    )

                    .sort(
                        (a, b) =>
                            b.score -
                            a.score
                    )

                    .slice(
                        0,
                        3
                    );

            await saveNovaSession(
                rankedSongs
            );

            renderSongResults(
                rankedSongs
            );


            $("#novaResults")
                .classList
                .remove("hidden");


            $("#novaResults")
                .scrollIntoView({
                    behavior:
                        "smooth"
                });

        }
    );


$("#novaForm")
    ?.addEventListener(
        "reset",
        () => {

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
                                    ${song.score}% fit
                                </span>

                            </div>


                            <div class="song-body">

                                <div class="song-meta">

                                    <div>

                                        <h3>
                                            ${song.title}
                                        </h3>

                                        <p>
                                            ${song.artist}
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
                                            BPM
                                        </span>

                                        <strong>
                                            ${song.bpm}
                                        </strong>

                                    </div>


                                    <div class="song-detail">

                                        <span>
                                            Editability
                                        </span>

                                        <strong>
                                            ${song.editability}
                                        </strong>

                                    </div>


                                    <div class="song-detail">

                                        <span>
                                            Energy
                                        </span>

                                        <strong>
                                            ${song.energy}
                                        </strong>

                                    </div>

                                </div>


                                <ul class="fit-reasons">

                                    <li>
                                        Matches a ${song.mood} mood
                                    </li>

                                    <li>
                                        ${song.pace} pacing provides useful editing rhythm
                                    </li>

                                    <li>
                                        Strong prototype editability score
                                    </li>

                                </ul>


                                <button
                                    class="button primary choose-song"
                                    data-title="${song.title}"
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

                            selectedTrack =
                                results.find(
                                    song =>
                                        song.title ===
                                        button.dataset.title
                                );

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


    $("#handoffTrack").innerHTML =
        `
            <strong>
                ${selectedTrack.title}
                —
                ${selectedTrack.artist}
            </strong>

            <small>
                ${selectedTrack.bpm} BPM ·
                ${selectedTrack.energy} ·
                ${selectedTrack.score}% fit
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

            closeModal(
                "handoffModal"
            );


            showView(
                "pulsar"
            );


            $("#blueprintSong").value =
                selectedTrack.title;


            $("#songDuration").value =
                $("#targetDuration").value ||
                60;


            $("#selectedTrackName")
                .textContent =
                `${selectedTrack.title} — ${selectedTrack.artist}`;


            $("#selectedTrackMeta")
                .textContent =
                `${selectedTrack.bpm} BPM · ${selectedTrack.energy}`;


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
            currentNovaSessionId = null;


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

            const musicProfile = $("#musicProfile").value;

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
                id: Date.now(),
                song,
                artist:
                    cameFromNova
                        ? selectedTrack.artist
                        : null,

                duration,
                musicProfile,
                density,
                selectedTypes,
                novaSessionId: cameFromNova ? currentNovaSessionId : null,
                created: new Date().toLocaleDateString(),

                cues: createCues(
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


    // Timeline markers
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


    // Signal table
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


    // Allow suggestion text to be edited
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


    // ---------------------------------------------
    // Get logged-in user
    // ---------------------------------------------

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


    // ---------------------------------------------
    // Create parent Pulsar Signal
    // ---------------------------------------------

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


    // ---------------------------------------------
    // Create cue rows
    // ---------------------------------------------

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


        // Remove the parent Signal so we don't
        // leave behind a half-saved record.
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

    // ---------------------------------------------
    // Check which user is signed in
    // ---------------------------------------------

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


    // Guests have no account-backed Echoes
    if (!user) {
        return [];
    }


    // ---------------------------------------------
    // Load Signals + their related cues
    // ---------------------------------------------

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


    // ---------------------------------------------
    // Convert database rows into the same shape
    // the existing UI already understands
    // ---------------------------------------------

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

    // Make a copy so editing the reopened Signal
    // doesn't accidentally mutate the Echoes list
    currentBlueprint =
        structuredClone(signal);


    // ---------------------------------------------
    // Restore the Pulsar form fields
    // ---------------------------------------------

    $("#blueprintSong").value =
        signal.song || "";


    $("#songDuration").value =
        signal.duration || 60;


    $("#musicProfile").value =
        signal.musicProfile || "dynamic";


    // Restore suggestion density
    $$('input[name="density"]')
        .forEach(input => {

            input.checked =
                input.value ===
                signal.density;

        });


    // Restore selected cue types
    $$('input[name="cueType"]')
        .forEach(input => {

            input.checked =
                signal.selectedTypes
                    ?.includes(
                        input.value
                    ) || false;

        });


    // ---------------------------------------------
    // Restore Nova relationship if one existed
    // ---------------------------------------------

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
                signal.artist
        };


        $("#selectedTrackName")
            .textContent =
            signal.song;


        $("#selectedTrackMeta")
            .textContent =
            signal.artist;


        $("#selectedTrackBanner")
            .classList
            .remove("hidden");

    } else {

        selectedTrack = null;


        $("#selectedTrackBanner")
            .classList
            .add("hidden");

    }


    // ---------------------------------------------
    // Go to Pulsar
    // ---------------------------------------------

    showView(
        "pulsar"
    );


    // ---------------------------------------------
    // Re-render the ORIGINAL saved Signal
    // ---------------------------------------------

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
                                ${item.song}
                            </h3>


                            <p>
                                ${item.cues.length} editing suggestions
                            </p>


                            <div class="history-meta">

                                <span>
                                    ${item.created}
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
                                    data-signal-id="${item.id}"
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
                                        item.id ===
                                        button.dataset.signalId
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

            // -------------------------------------
            // Make sure someone is logged in
            // -------------------------------------

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


            // -------------------------------------
            // Prevent accidental deletion
            // -------------------------------------

            const confirmed =
                window.confirm(
                    "Delete all of your captured Signals? This cannot be undone."
                );


            if (!confirmed) {
                return;
            }


            // -------------------------------------
            // Delete this user's Pulsar Signals
            // -------------------------------------

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


    // ---------------------------------------------
    // Update Signal counts
    // ---------------------------------------------

    $("#blueprintCount")
        .textContent =
        count;


    $("#accountBlueprintCount")
        .textContent =
        count;


    // ---------------------------------------------
    // Full Echoes page
    // ---------------------------------------------

    renderHistoryInto(
        $("#historyList"),
        history
    );


    // ---------------------------------------------
    // Launchpad — only the newest three
    // ---------------------------------------------

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

    const minutes =
        Math.floor(
            seconds / 60
        );


    const remaining =
        Math.round(
            seconds % 60
        );


    return `${minutes}:${String(
        remaining
    ).padStart(
        2,
        "0"
    )}`;

}


function capitalize(text) {

    return (

        text
            .charAt(0)
            .toUpperCase() +

        text
            .slice(1)

    );

}


// =====================================================
// INTERACTION POLISH
// =====================================================

// Add material separation to the floating
// top bar once scrolling begins.
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


// Clicking the dimmed area dismisses a modal.
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


// Escape also dismisses open modals.
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