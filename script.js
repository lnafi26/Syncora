const SUPABASE_URL = 'https://phxusxkhzxllrioxuzkr.supabase.co'
const SUPABASE_KEY = 'sb_publishable_3GHRzFe9g3kgcvTaeTBtyQ_GDih979C'

const db = supabase.createClient(
    SUPABASE_URL,
    SUPABASE_KEY
)

async function testSupabaseConnection() {
    const { data, error } = await db
        .from('connection_test')
        .select('*')

    if (error) {
        console.error('Supabase connection failed:', error)
        return
    }

    console.log('Supabase connected!', data)
}

testSupabaseConnection()

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

let selectedTrack = null;
let currentBlueprint = null;

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

// Fake songs for the prototype only
const songs = [
    {
        title: "Afterglow Circuit",
        artist: "Nova Vale",
        mood: "dreamy",
        pace: "moderate",
        type: "cinematic",
        bpm: 112,
        editability: 92,
        energy: "Rising",
        colors: ["#3d72ff", "#8d59ff"]
    },
    {
        title: "Signal Rush",
        artist: "Kairo Frame",
        mood: "intense",
        pace: "fast",
        type: "sports",
        bpm: 148,
        editability: 96,
        energy: "Explosive",
        colors: ["#ff6b4a", "#ffcb57"]
    },
    {
        title: "Still Between Us",
        artist: "Mara Sol",
        mood: "emotional",
        pace: "slow",
        type: "emotional",
        bpm: 78,
        editability: 86,
        energy: "Gradual",
        colors: ["#395c7b", "#b778ad"]
    },
    {
        title: "Midnight Architecture",
        artist: "Vector Bloom",
        mood: "dark",
        pace: "dynamic",
        type: "gaming",
        bpm: 124,
        editability: 90,
        energy: "Layered",
        colors: ["#10143f", "#7652a8"]
    },
    {
        title: "Open Horizon",
        artist: "Elio North",
        mood: "uplifting",
        pace: "moderate",
        type: "travel",
        bpm: 98,
        editability: 88,
        energy: "Warm",
        colors: ["#3b8e8a", "#e0a758"]
    },
    {
        title: "Velocity Bloom",
        artist: "Rin Atlas",
        mood: "confident",
        pace: "fast",
        type: "social",
        bpm: 136,
        editability: 93,
        energy: "Driving",
        colors: ["#42b883", "#245d82"]
    }
];


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
    $(`.nav-item[data-view="${name}"]`)?.classList.add("active");

    const [eyebrow, title] = pageInfo[name] || pageInfo.dashboard;

    $("#pageEyebrow").textContent = eyebrow;
    $("#pageTitle").textContent = title;

    $("#sidebar")?.classList.remove("open");

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });

    if (name === "history") {
        renderHistory();
    }
}

$$("[data-view], [data-go], [data-view-link]").forEach(button => {
    button.addEventListener("click", event => {
        event.preventDefault();

        const destination =
        button.dataset.view ||
        button.dataset.go ||
        button.dataset.viewLink;

        showView(destination);
    });
});

$("#mobileMenu")?.addEventListener("click", () => {
    $("#sidebar")?.classList.toggle("open");
});


// =====================================================
// NOVA
// =====================================================

$("#novaForm")?.addEventListener("submit", event => {
    event.preventDefault();

    const mood = $('input[name="mood"]:checked')?.value;
    const pace = $('input[name="pace"]:checked')?.value;
    const type = $("#videoType").value;

    const rankedSongs = songs
        .map(song => {
        let score = 70;

        if (song.mood === mood) {
            score += 12;
        }

        if (song.pace === pace) {
            score += 10;
        }

        if (song.type === type) {
            score += 8;
        }

        return {
            ...song,
            score: Math.min(score, 99)
        };
        })
        .sort((a, b) => b.score - a.score)
        .slice(0, 3);

    renderSongResults(rankedSongs);

    $("#novaResults").classList.remove("hidden");

    $("#novaResults").scrollIntoView({
        behavior: "smooth"
    });
});

$("#novaForm")?.addEventListener("reset", () => {
    $("#novaResults")?.classList.add("hidden");
});

$("#rerunTrackfit")?.addEventListener("click", () => {
    $("#novaForm")?.scrollIntoView({
        behavior: "smooth"
    });
});


function renderSongResults(results) {
    $("#songResults").innerHTML = results
        .map((song, index) => {
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
                    <h3>${song.title}</h3>
                    <p>${song.artist}</p>
                </div>

                <span class="pill">
                    ${index === 0 ? "Best match" : `Option ${index + 1}`}
                </span>
                </div>

                <div class="song-details">

                <div class="song-detail">
                    <span>BPM</span>
                    <strong>${song.bpm}</strong>
                </div>

                <div class="song-detail">
                    <span>Editability</span>
                    <strong>${song.editability}</strong>
                </div>

                <div class="song-detail">
                    <span>Energy</span>
                    <strong>${song.energy}</strong>
                </div>

                </div>

                <ul class="fit-reasons">
                <li>Matches a ${song.mood} mood</li>
                <li>${song.pace} pacing provides useful editing rhythm</li>
                <li>Strong prototype editability score</li>
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
        })
        .join("");

    $$(".choose-song").forEach(button => {
        button.addEventListener("click", () => {
        selectedTrack = results.find(
            song => song.title === button.dataset.title
        );

        openHandoff();
        });
    });
}


function openHandoff() {
    if (!selectedTrack) {
        return;
    }

    $("#handoffTrack").innerHTML = `
        <strong>
        ${selectedTrack.title} — ${selectedTrack.artist}
        </strong>

        <small>
        ${selectedTrack.bpm} BPM ·
        ${selectedTrack.energy} ·
        ${selectedTrack.score}% fit
        </small>
    `;

    $("#handoffModal").classList.remove("hidden");
}


// Automatically move Nova selection into Pulsar
$("#continueToBlueprint")?.addEventListener("click", () => {
    closeModal("handoffModal");

    showView("pulsar");

    $("#blueprintSong").value = selectedTrack.title;

    $("#songDuration").value =
        $("#targetDuration").value || 60;

    $("#selectedTrackName").textContent =
        `${selectedTrack.title} — ${selectedTrack.artist}`;

    $("#selectedTrackMeta").textContent =
        `${selectedTrack.bpm} BPM · ${selectedTrack.energy}`;

    $("#selectedTrackBanner").classList.remove("hidden");
});


$("#changeTrackButton")?.addEventListener("click", () => {
    selectedTrack = null;

    $("#selectedTrackBanner").classList.add("hidden");

    $("#blueprintSong").value = "";
});


// =====================================================
// PULSAR
// =====================================================

$("#loadDemoBlueprint")?.addEventListener("click", () => {
    $("#blueprintSong").value = "Signal Rush";
    $("#songDuration").value = 60;
    $("#musicProfile").value = "dynamic";
});


$("#blueprintForm")?.addEventListener("submit", event => {
    event.preventDefault();

    const song = $("#blueprintSong").value.trim();

    const duration = Number(
        $("#songDuration").value
    );

    const density =
        $('input[name="density"]:checked')?.value ||
        "balanced";

    const selectedTypes = $$(
        'input[name="cueType"]:checked'
    ).map(box => box.value);

    if (!selectedTypes.length) {
        showToast("Choose at least one suggestion type.");
        return;
    }

    currentBlueprint = {
        id: Date.now(),
        song,
        duration,
        density,
        created: new Date().toLocaleDateString(),

        cues: createCues(
        duration,
        density,
        selectedTypes
        )
    };

    renderBlueprint(currentBlueprint);
});


function createCues(duration, density, types) {
    const cueAmounts = {
        minimal: 4,
        balanced: 6,
        detailed: 9
    };

    const count =
        cueAmounts[density] || 6;

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
        { length: count },

        (_, index) => {
        const seconds =
            Math.round(
            ((index + 1) / (count + 1)) *
            duration
            );

        const type =
            types[index % types.length];

        const options =
            suggestions[type];

        let priority = "optional";

        if (
            index === 0 ||
            index === Math.floor(count / 2)
        ) {
            priority = "primary";
        }
        else if (index % 2 === 0) {
            priority = "secondary";
        }

        return {
            time: formatTime(seconds),
            seconds,
            priority,

            moment:
            index === Math.floor(count / 2)
                ? "Major musical change"
                : "Rhythmic accent",

            suggestion:
            options[index % options.length]
        };
        }
    );
}


function renderBlueprint(blueprint) {
    $("#outputTitle").textContent =
        blueprint.song;

    $("#outputSummary").textContent =
        `${blueprint.cues.length} suggested edit points across ${formatTime(
        blueprint.duration
        )}.`;

    $("#cueCount").textContent =
        `${blueprint.cues.length} cues`;

    const colors = {
        primary: "var(--accent)",
        secondary: "var(--blue)",
        optional: "var(--purple)"
    };


    // Timeline markers
    $("#visualTimeline").innerHTML =
        blueprint.cues
        .map((cue, index) => {
            const percentage =
            (cue.seconds / blueprint.duration) * 100;

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
        })
        .join("");


    // Blueprint table
    $("#cueTableBody").innerHTML =
        blueprint.cues
        .map((cue, index) => {
            return `
            <tr>

                <td>
                <strong>${cue.time}</strong>
                </td>

                <td>
                <span class="priority-chip ${cue.priority}">
                    ${capitalize(cue.priority)}
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
                >
                    ✎
                </button>
                </td>

            </tr>
            `;
        })
        .join("");


    // Allow suggestion text to be edited
    $$(".edit-cue").forEach(button => {
        button.addEventListener("click", () => {
        const cue =
            currentBlueprint.cues[
            Number(button.dataset.index)
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


    $("#blueprintOutput").classList.remove("hidden");

    $("#blueprintOutput").scrollIntoView({
        behavior: "smooth"
    });
}


// =====================================================
// SAVE / COPY / HISTORY
// =====================================================

$("#saveBlueprint")?.addEventListener("click", () => {
    if (!currentBlueprint) {
        return;
    }

    const history =
        getHistory();

    history.unshift(
        currentBlueprint
    );

    localStorage.setItem(
        "syncoraHistory",
        JSON.stringify(
        history.slice(0, 12)
        )
    );

    updateHistory();

    showToast(
        "Signal captured."
    );
});


$("#copyBlueprint")?.addEventListener("click", async () => {
    if (!currentBlueprint) {
        return;
    }

    const notes =
        currentBlueprint.cues
        .map(
            cue =>
            `${cue.time} — ${cue.suggestion}`
        )
        .join("\n");

    try {
        await navigator.clipboard.writeText(
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
});


function getHistory() {
    return JSON.parse(
        localStorage.getItem(
        "syncoraHistory"
        ) || "[]"
    );
}


function renderHistory() {
    const history =
        getHistory();

    renderHistoryInto(
        $("#historyList"),
        history
    );

    renderHistoryInto(
        $("#recentBlueprints"),
        history.slice(0, 3)
    );
}


function renderHistoryInto(container, items) {
    if (!container) {
        return;
    }

    if (!items.length) {
        container.innerHTML = `
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
        .map(item => {
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
                    ${formatTime(item.duration)}
                </span>

                </div>

            </article>
            `;
        })
        .join("");
}


$("#clearHistory")?.addEventListener("click", () => {
    localStorage.removeItem(
        "syncoraHistory"
    );

    updateHistory();
});


function updateHistory() {
    const count =
        getHistory().length;

    $("#blueprintCount").textContent =
        count;

    $("#accountBlueprintCount").textContent =
        count;

    renderHistory();
}


// =====================================================
// SIMPLE LOCAL ACCOUNT MOCKUP
// =====================================================

function openAccount() {
    $("#accountModal").classList.remove("hidden");
}


$("#accountButton")?.addEventListener(
    "click",
    openAccount
);

$("#topAccountButton")?.addEventListener(
    "click",
    openAccount
);


$("#accountForm")?.addEventListener("submit", event => {
    event.preventDefault();

    const user = {
        name: $("#accountName").value.trim(),
        email: $("#accountEmail").value.trim()
    };

    localStorage.setItem(
        "syncoraUser",
        JSON.stringify(user)
    );

    updateAccount();

    showToast(
        "Local test account created."
    );
});


$("#signOutButton")?.addEventListener("click", () => {
    localStorage.removeItem(
        "syncoraUser"
    );

    updateAccount();

    closeModal(
        "accountModal"
    );
});


function updateAccount() {
    const user =
        JSON.parse(
        localStorage.getItem(
            "syncoraUser"
        ) || "null"
        );

    if (user) {
        $("#sidebarName").textContent =
        user.name;

        $("#sidebarEmail").textContent =
        user.email;

        $("#sidebarAvatar").textContent =
        user.name.charAt(0).toUpperCase();

        $("#topAccountButton").textContent =
        "Account";

        $("#signedOutAccount").classList.add(
        "hidden"
        );

        $("#signedInAccount").classList.remove(
        "hidden"
        );

        $("#signedInName").textContent =
        user.name;

        $("#signedInEmail").textContent =
        user.email;
    }
    else {
        $("#sidebarName").textContent =
        "Guest editor";

        $("#sidebarEmail").textContent =
        "Sign in to save history";

        $("#sidebarAvatar").textContent =
        "G";

        $("#topAccountButton").textContent =
        "Sign in";

        $("#signedOutAccount").classList.remove(
        "hidden"
        );

        $("#signedInAccount").classList.add(
        "hidden"
        );
    }
}


// =====================================================
// MODALS + SMALL HELPERS
// =====================================================

$$("[data-close]").forEach(button => {
    button.addEventListener("click", () => {
        closeModal(
        button.dataset.close
        );
    });
});


function closeModal(id) {
    $(`#${id}`)?.classList.add(
        "hidden"
    );
}


function showToast(message) {
    const toast =
        $("#toast");

    toast.textContent =
        message;

    toast.classList.remove(
        "hidden"
    );

    setTimeout(() => {
        toast.classList.add(
        "hidden"
        );
    }, 2200);
}


function formatTime(seconds) {
    const minutes =
        Math.floor(seconds / 60);

    const remaining =
        Math.round(seconds % 60);

    return `${minutes}:${String(
        remaining
    ).padStart(2, "0")}`;
}


function capitalize(text) {
    return (
        text.charAt(0).toUpperCase() +
        text.slice(1)
    );
}

// =====================================================
// INTERACTION POLISH
// =====================================================

// Add material separation to the floating top bar once scrolling begins
window.addEventListener("scroll", () => {
    $(".topbar")?.classList.toggle(
        "scrolled",
        window.scrollY > 8
    );
});

// Clicking the dimmed area dismisses a modal
$$(".modal-backdrop").forEach(backdrop => {
    backdrop.addEventListener("click", event => {
        if (event.target === backdrop) {
            backdrop.classList.add("hidden");
        }
    });
});

// Escape also dismisses open modals
document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
        $$(".modal-backdrop").forEach(modal => {
            modal.classList.add("hidden");
        });
    }
});

// =====================================================
// INITIAL SETUP
// =====================================================

updateAccount();
updateHistory();