(() => {
  "use strict";

  const categories = [
    {
      title: "Relations & keys",
      clues: [
        ["The structure and rules of a relation, rather than its rows at one moment.", "What is the schema?", "The current rows form an instance of that schema."],
        ["Because a relation is a set, it cannot contain two identical ones of these.", "What are tuples?", "Tuple order also has no meaning in the relational model."],
        ["A superkey with no attribute you can remove while keeping it a superkey.", "What is a candidate key?", "Minimal means no proper subset is a superkey; it does not mean shortest among all possible keys."],
        ["A player can have two saves for one game. Can (player_id, game_id) identify every save?", "No. The pair is not a superkey for saves.", "Two valid saves can share both values, so the pair cannot uniquely identify a row."],
        ["A non-NULL child foreign key contains 42, but the referenced parent has no key 42. Name the violated rule.", "What is referential integrity?", "Every non-NULL foreign-key value must match an existing referenced key."],
      ],
    },
    {
      title: "Relational algebra",
      clues: [
        ["This operator keeps rows that satisfy a condition, without changing the attributes.", "What is selection (σ)?", "Projection (π) chooses attributes instead."],
        ["Player has region values MT, MT, and WA. What tuples does π_region(Player) return?", "{(MT), (WA)}", "Projection removes duplicate output tuples under relational set semantics."],
        ["A natural join R ⋈ S compares values in which attributes?", "Every attribute name shared by R and S.", "It does not look only at declared primary or foreign keys."],
        ["What does π_member_id(Member) − π_member_id(Loan) describe, assuming both IDs have the same domain?", "Members with no loan.", "Set difference keeps tuples in the left input that are absent from the right input."],
        ["R(a,b) contains (1,x), (2,y). S(b,c) contains (x,9), (z,8). What is π_a(R ⋈ S)?", "{(1)}", "The natural join matches the shared b value x, then projection retains only a."],
      ],
    },
    {
      title: "SQL queries",
      clues: [
        ["Write a query returning usernames from player_account rows whose account_status is 'active'.", "SELECT username FROM player_account WHERE account_status = 'active';", "SELECT chooses output columns; WHERE filters rows."],
        ["Which WHERE predicate finds saves whose slot_label is missing?", "WHERE slot_label IS NULL", "An equality comparison with NULL evaluates to unknown."],
        ["Complete the intended join: FROM player_account p JOIN save_file s ON ____", "s.player_id = p.player_id", "The condition links the save's foreign key to its player."],
        ["A player has several saves. Which SELECT keyword returns the player ID only once after a join?", "DISTINCT", "DISTINCT removes repeated complete output rows."],
        ["Using video_game(game_id,title) and save_file(save_id,player_id,game_id), return each game title saved by player 7 once, alphabetically.", "SELECT DISTINCT g.title\nFROM video_game AS g\nJOIN save_file AS s ON s.game_id = g.game_id\nWHERE s.player_id = 7\nORDER BY g.title;", "The join finds each saved game; DISTINCT removes titles repeated by multiple saves."],
      ],
    },
    {
      title: "Tables & constraints",
      clues: [
        ["These SQL commands define or change database structures; CREATE TABLE and ALTER TABLE are examples.", "What is Data Definition Language (DDL)?", "DDL changes the schema."],
        ["A PRIMARY KEY enforces these two properties on its columns.", "Uniqueness and no NULL values.", "A primary key may contain more than one column."],
        ["CHECK (quantity > 0) rejects negative values but permits NULL. What additional constraint makes quantity required?", "NOT NULL", "A CHECK condition that evaluates to unknown passes."],
        ["If a foreign key says ON DELETE CASCADE, what happens when its referenced parent row is deleted?", "The referencing child rows are deleted automatically.", "Deleting a child row does not delete its parent."],
        ["A save must reference an existing player, and deleting that player while saves remain must be blocked. Give the player_id column definition.", "player_id integer NOT NULL REFERENCES player_account(player_id) ON DELETE RESTRICT", "NOT NULL makes the reference required; RESTRICT blocks deletion of a referenced player."],
      ],
    },
    {
      title: "ER diagrams",
      clues: [
        ["In our ER notation, this shape represents an entity set; a diamond represents a relationship.", "What is a rectangle?", "An entity set groups distinguishable objects of the same kind."],
        ["An arrow from a relationship toward an entity set means this maximum number of partners on that side.", "At most one.", "An arrow alone does not say participation is required."],
        ["A double line between an entity set and a relationship means what for every entity in that set?", "It must participate in the relationship.", "This is total participation; a single line means participation is optional."],
        ["Each employee–project assignment records hours_worked. Where does hours_worked belong in the ER diagram?", "On the employee–project relationship.", "The hours describe that particular assignment, not the employee or project alone."],
        ["Each quest has exactly one sponsor guild; a guild may sponsor many quests. Where does the foreign key go, and must it be UNIQUE?", "Put a NOT NULL guild_id foreign key in quest; it should not be UNIQUE.", "Quest is the many side. NOT NULL requires a sponsor, while repeated guild IDs allow one guild to sponsor many quests."],
      ],
    },
  ];

  const points = [100, 200, 300, 400, 500];
  const storageKey = "csci340-midterm-review-jeopardy-v1";
  const game = document.getElementById("review-game");
  if (!game) return;

  const board = document.getElementById("game-board");
  const status = document.getElementById("game-status");
  const teamList = document.getElementById("team-list");
  const overlay = document.getElementById("clue-overlay");
  const prompt = document.getElementById("clue-prompt");
  const answer = document.getElementById("clue-answer");
  const explanation = document.getElementById("clue-explanation");
  const answerWrap = document.getElementById("clue-answer-wrap");
  const scoring = document.getElementById("clue-team-actions");
  const timerDisplay = document.getElementById("clue-timer");
  const timerToggle = document.getElementById("timer-toggle");
  const revealButton = document.getElementById("clue-reveal");
  const fullscreenButton = document.getElementById("game-fullscreen");
  let activeId = null;
  let priorFocus = null;
  let timerHandle = null;
  let secondsLeft = 30;
  let state = loadState();

  function initialState() {
    return { teams: ["Team 1", "Team 2", "Team 3"], used: [], marks: {} };
  }

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey));
      if (saved && Array.isArray(saved.teams) && saved.teams.length >= 2 && saved.teams.length <= 4 &&
          saved.teams.every(name => typeof name === "string") && Array.isArray(saved.used) &&
          saved.marks && typeof saved.marks === "object") return saved;
    } catch (_) { /* Private browsing may disable storage. */ }
    return initialState();
  }

  function saveState() {
    try { localStorage.setItem(storageKey, JSON.stringify(state)); } catch (_) { /* Keep playing in memory. */ }
  }

  function clueId(categoryIndex, rowIndex) { return `${categoryIndex}-${rowIndex}`; }
  function activeClue() {
    const [categoryIndex, rowIndex] = activeId.split("-").map(Number);
    return { category: categories[categoryIndex], rowIndex, clue: categories[categoryIndex].clues[rowIndex] };
  }

  function teamScore(teamIndex) {
    return Object.entries(state.marks).reduce((total, [id, marks]) => {
      const row = Number(id.split("-")[1]);
      return total + (points[row] || 0) * (Number(marks[teamIndex]) || 0);
    }, 0);
  }

  function renderBoard() {
    board.replaceChildren();
    categories.forEach(category => {
      const heading = document.createElement("div");
      heading.className = "game-category";
      heading.textContent = category.title;
      board.append(heading);
    });
    points.forEach((value, rowIndex) => categories.forEach((category, categoryIndex) => {
      const id = clueId(categoryIndex, rowIndex);
      const played = state.used.includes(id);
      const button = document.createElement("button");
      button.type = "button";
      button.className = `game-tile${played ? " played" : ""}`;
      button.textContent = played ? "✓" : String(value);
      button.setAttribute("aria-label", `${category.title}, ${value} points${played ? ", played; reopen clue" : ""}`);
      button.addEventListener("click", () => openClue(id));
      board.append(button);
    }));
    status.textContent = `${state.used.length} of 25 clues played`;
  }

  function renderTeams() {
    teamList.replaceChildren();
    state.teams.forEach((name, index) => {
      const card = document.createElement("div");
      card.className = "team-card";
      const label = document.createElement("label");
      label.textContent = `Team ${index + 1}`;
      const input = document.createElement("input");
      input.type = "text";
      input.maxLength = 28;
      input.value = name;
      input.setAttribute("aria-label", `Name for team ${index + 1}`);
      input.addEventListener("input", () => { state.teams[index] = input.value; saveState(); });
      const score = document.createElement("div");
      score.className = "team-score";
      score.textContent = String(teamScore(index));
      score.setAttribute("aria-label", `${name || `Team ${index + 1}`} score ${teamScore(index)}`);
      card.append(label, input, score);
      teamList.append(card);
    });
    document.getElementById("game-add-team").disabled = state.teams.length >= 4;
    document.getElementById("game-remove-team").disabled = state.teams.length <= 2;
  }

  function renderScoring() {
    scoring.replaceChildren();
    const marks = state.marks[activeId] || {};
    state.teams.forEach((name, index) => {
      const card = document.createElement("div");
      card.className = "clue-team";
      const label = document.createElement("span");
      label.className = "clue-team-name";
      label.textContent = name || `Team ${index + 1}`;
      card.append(label);
      [[1, "+"], [-1, "−"]].forEach(([mark, symbol]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = symbol;
        button.className = Number(marks[index]) === mark ? "selected" : "";
        button.setAttribute("aria-label", `${mark === 1 ? "Award" : "Deduct"} ${points[activeClue().rowIndex]} points ${mark === 1 ? "to" : "from"} ${name || `Team ${index + 1}`}`);
        button.setAttribute("aria-pressed", Number(marks[index]) === mark ? "true" : "false");
        button.addEventListener("click", () => {
          state.marks[activeId] ||= {};
          if (Number(state.marks[activeId][index]) === mark) delete state.marks[activeId][index];
          else state.marks[activeId][index] = mark;
          saveState();
          renderScoring();
          renderTeams();
        });
        card.append(button);
      });
      scoring.append(card);
    });
  }

  function renderTimer() {
    timerDisplay.textContent = `0:${String(secondsLeft).padStart(2, "0")}`;
    timerDisplay.classList.toggle("expired", secondsLeft === 0);
    timerToggle.textContent = timerHandle ? "Pause timer" : secondsLeft === 0 ? "Restart timer" : "Start timer";
  }

  function stopTimer() { if (timerHandle) clearInterval(timerHandle); timerHandle = null; renderTimer(); }
  function toggleTimer() {
    if (timerHandle) { stopTimer(); return; }
    if (secondsLeft === 0) secondsLeft = 30;
    timerHandle = setInterval(() => {
      secondsLeft -= 1;
      if (secondsLeft <= 0) { secondsLeft = 0; stopTimer(); }
      renderTimer();
    }, 1000);
    renderTimer();
  }

  function openClue(id) {
    priorFocus = document.activeElement;
    activeId = id;
    const { category, rowIndex, clue } = activeClue();
    document.getElementById("clue-category").textContent = category.title;
    document.getElementById("clue-value").textContent = `${points[rowIndex]} points`;
    prompt.textContent = clue[0];
    answer.textContent = clue[1];
    explanation.textContent = clue[2];
    answerWrap.hidden = !state.used.includes(id);
    revealButton.hidden = !answerWrap.hidden;
    secondsLeft = 30;
    stopTimer();
    renderScoring();
    overlay.hidden = false;
    document.body.style.overflow = "hidden";
    (revealButton.hidden ? document.getElementById("clue-close") : revealButton).focus();
  }

  function closeClue() {
    if (!activeId) return;
    stopTimer();
    if (!answerWrap.hidden && !state.used.includes(activeId)) state.used.push(activeId);
    saveState();
    overlay.hidden = true;
    document.body.style.overflow = "";
    activeId = null;
    renderBoard();
    if (priorFocus && typeof priorFocus.focus === "function") {
      const label = priorFocus.getAttribute("aria-label");
      const replacement = [...board.querySelectorAll("button")].find(button => button.getAttribute("aria-label")?.split(", played")[0] === label?.split(", played")[0]);
      (replacement || board.querySelector("button"))?.focus();
    }
  }

  revealButton.addEventListener("click", () => {
    stopTimer();
    answerWrap.hidden = false;
    revealButton.hidden = true;
    document.getElementById("clue-close").focus();
  });
  document.getElementById("clue-close").addEventListener("click", closeClue);
  timerToggle.addEventListener("click", toggleTimer);
  document.getElementById("timer-reset").addEventListener("click", () => { stopTimer(); secondsLeft = 30; renderTimer(); });
  document.getElementById("game-add-team").addEventListener("click", () => {
    if (state.teams.length < 4) { state.teams.push(`Team ${state.teams.length + 1}`); saveState(); renderTeams(); }
  });
  document.getElementById("game-remove-team").addEventListener("click", () => {
    if (state.teams.length <= 2) return;
    const index = state.teams.length - 1;
    state.teams.pop();
    Object.values(state.marks).forEach(marks => delete marks[index]);
    saveState(); renderTeams();
  });
  document.getElementById("game-reset").addEventListener("click", () => {
    if (!window.confirm("Clear all team names, scores, and played clues for a new game?")) return;
    state = initialState(); saveState(); renderBoard(); renderTeams();
  });
  fullscreenButton.addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else game.requestFullscreen?.();
  });
  document.addEventListener("fullscreenchange", () => { fullscreenButton.textContent = document.fullscreenElement ? "Exit full screen" : "Full screen"; });
  document.addEventListener("keydown", event => {
    if (!activeId) return;
    if (event.key === "Escape") { event.preventDefault(); closeClue(); }
    if (event.key === "Tab") {
      const focusable = [...overlay.querySelectorAll("button:not([hidden]):not(:disabled)")].filter(button => button.offsetParent !== null);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });

  renderBoard();
  renderTeams();
  renderTimer();
})();
