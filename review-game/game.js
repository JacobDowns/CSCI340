(() => {
  "use strict";

  // Clues support \(math\), `inline code`, and fenced code blocks.
  const categories = [
    {
      title: "Relations & keys",
      clues: [
        "`Member(member_id, name)` describes the columns; today's Member rows are (1, Ada) and (2, Ben). Which is the schema, and which is the instance?",
        "A username happens to be unique in today's rows, but the rules permit repeats. Is username a candidate key?",
        "`Loan.member_id` contains 42, but Member has no `member_id` 42. Which relational integrity rule is violated?",
        "Every checkout has a unique `checkout_id`. Is \\(\\{\\mathrm{checkout\\_id},\\mathrm{member\\_id}\\}\\) a candidate key? Explain.",
        "Member has `member_id PRIMARY KEY` and `email UNIQUE NOT NULL`. Which of \\(\\{\\mathrm{member\\_id}\\}\\), \\(\\{\\mathrm{email}\\}\\), and \\(\\{\\mathrm{member\\_id},\\mathrm{email}\\}\\) are candidate keys?",
        "`Attendance(student_id, section_id, meeting_date)` allows a student to attend the same section on many dates, at most once per date. Give a plausible composite key.",
      ],
    },
    {
      title: "Relational algebra",
      clues: [
        "Which relational-algebra operator keeps selected attributes and removes duplicate output tuples?",
        "What does \\(\\rho_{\\mathrm{Recent}}(\\mathrm{Checkout})\\) change about the relation Checkout?",
        "R has 3 tuples and S has 4 tuples. How many tuples are in \\(R \\times S\\)? Can a theta join of R and S have more tuples?",
        "Which of union, intersection, and difference need compatible schemas? Why are `R(a, b)` and `S(a, b, c)` incompatible?",
        "Using `Member(member_id, region)` and `Loan(member_id, item_id)`, write an algebra expression for IDs of MT members with no loans.",
        String.raw`R(a,b) = \(\{(1,\mathrm{x}), (1,\mathrm{y}), (2,\mathrm{x})\}\)
S(b,c) = \(\{(\mathrm{x},9), (\mathrm{y},8)\}\)

Give the output schema and every tuple of \(\pi_{a,c}(R \bowtie S)\).`,
      ],
    },
    {
      title: "SQL queries",
      clues: [
        "In `ORDER BY created_at DESC`, do older or newer timestamps come first?",
        "Write the `WHERE` condition for active accounts in either MT or WY. Columns: `status` and `region`.",
        "`SELECT DISTINCT member_id, checkout_id` returns two rows for one member's two checkouts. Why?",
        "Complete the join: `FROM escape_room r JOIN escape_booking b ON ____`",
        "Using these tables:\n\n```sql\nmember(member_id, name)\ncheckout(checkout_id, member_id, item_id, returned_on)\nitem(item_id, label)\n```\n\nReturn each member_id and name once for members with an unreturned checkout of an item labeled 'Camera'.",
        "Write a query returning each username once for active players with a save whose `completion_percent` is `NULL` in a game by 'Juniper Byte'.\n\nUse these tables and order by username:\n\n```sql\nplayer_account(player_id, username, account_status)\nsave_file(player_id, game_id, completion_percent)\nvideo_game(game_id, studio_name)\n```",
      ],
    },
    {
      title: "Tables & constraints",
      clues: [
        "Write an `ALTER TABLE` statement that adds an optional text note to a table named `booking`.",
        "Which constraint prevents repeated non-`NULL` email values but does not make email required?",
        "Define a required text `status` column whose only allowed values are 'open' and 'closed'.",
        "`Booking.room_id` references `Room(room_id)`. What differs between `ON DELETE RESTRICT` and `ON DELETE CASCADE` when a room with bookings is deleted?",
        "`party_size integer DEFAULT 2 CHECK (party_size BETWEEN 1 AND 8)`: Is an explicit `NULL` rejected? Revise the column definition to make `party_size` required.",
        "Write `CREATE TABLE loan` with:\n• generated integer primary key `loan_id`\n• required `member_id` referencing `member(member_id)` `ON DELETE RESTRICT`\n• required `days` from 1 through 14",
      ],
    },
    {
      title: "ER diagrams",
      clues: [
        "A guild may sponsor no quests. Is its participation in Sponsors total or partial, and which line style shows it?",
        "In our ER notation, how are an entity set, a relationship set, and a primary key attribute drawn?",
        "An arrow points from Teaches toward Instructor, and Section participates totally in Teaches. How many instructors teach each section?",
        "Each quest has exactly one sponsor guild; a guild may sponsor many quests. Which relation gets the foreign key?",
        "Artist and Festival are many-to-many; each pair appears once, and fee belongs to that appearance.\n\nFor `appearance(artist_id, festival_id, fee)`, give its primary key and foreign keys. Where does fee belong in the ER diagram?",
        "A member may borrow the same item multiple times, creating a new loan row each time.\n\nWhy can't `(member_id, item_id)` be the primary key of `loan`? Name a suitable primary key.",
      ],
    },
    {
      title: "Trace & debug",
      clues: [
        "Which predicate keeps rows whose progress has not been recorded: `progress = NULL` or `progress IS NULL`?",
        "A `SELECT` query has no `ORDER BY`. Is the row order guaranteed?",
        "Player has IDs 1, 2, 3. Save has `player_id` values 1, 1, 3 (with different save IDs). How many rows result from an inner join on `player_id`?",
        "Each locker is assigned exactly one student; each student has at most one locker. `locker.student_id` is a foreign key. Which two constraints are still needed?",
        "`WHERE region = 'MT' OR region = 'WA' AND progress >= 80`: Which region bypasses the progress test? Rewrite so the test applies to both regions.",
        "`Player(id,name)` = \\(\\{(1,\\mathrm{Ada}),(2,\\mathrm{Ben}),(3,\\mathrm{Cy})\\}\\)\n`Save(save_id,player_id,progress)` = \\(\\{(10,1,80),(11,1,\\mathrm{NULL}),(12,2,80)\\}\\)\n\nWhich names does this query return?\n\n```sql\nSELECT DISTINCT p.name\nFROM Player p JOIN Save s ON p.id = s.player_id\nWHERE s.progress >= 80 OR s.progress IS NULL\nORDER BY p.name;\n```",
      ],
    },
    {
      title: "Mixed review",
      clues: [
        "In the relational model, what is an attribute's domain?",
        "`Booking(status, shipped_at)` has a required status. Write a `WHERE` condition for bookings that are not 'cancelled' and have a known `shipped_at`. Use `NOT` in your condition.",
        "`R(id)` = \\(\\{(1), (2), (3)\\}\\)\n`S(id)` = \\(\\{(2), (3), (4)\\}\\)\n\nGive both \\(R \\cap S\\) and \\(R \\cup S\\).",
        "Choose PostgreSQL types for a price stored exactly to cents, a calendar-only birthday, and the instant a payment was received with time-zone-aware handling.",
        "`Member(mid, region)` and `Loan(lid, borrower_mid)` have no shared attribute names. Write a theta join that pairs each loan with its member (`Member.mid = Loan.borrower_mid`), and give the output attributes.",
        "Each lab has exactly one supervisor; each supervisor oversees at most one lab and may oversee none. For Supervises, give the ER arrows and participation lines. If `Lab.supervisor_id` references `Supervisor(id)`, which further constraints on `supervisor_id` enforce these rules?",
      ],
    },
  ];

  const points = [100, 200, 300, 400, 500, 600];
  const dailyDoubleId = "6-2";
  const storageKey = "csci340-midterm-review-jeopardy-v3";
  const game = document.getElementById("review-game");
  if (!game) return;

  const board = document.getElementById("game-board");
  const status = document.getElementById("game-status");
  const scoreDisplay = document.getElementById("class-score");
  const overlay = document.getElementById("clue-overlay");
  const dailyDoubleBanner = document.getElementById("daily-double-banner");
  const prompt = document.getElementById("clue-prompt");
  const awardButton = document.getElementById("clue-award");
  const clueClassTotal = document.getElementById("clue-class-total");
  const finishButton = document.getElementById("clue-finish");
  const fullscreenButton = document.getElementById("game-fullscreen");
  let activeId = null;
  let priorFocus = null;
  let state = loadState();

  function initialState() {
    return { used: [], awarded: [] };
  }

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey));
      if (saved && Array.isArray(saved.used) && Array.isArray(saved.awarded) &&
          saved.used.every(id => typeof id === "string") &&
          saved.awarded.every(id => typeof id === "string")) return saved;
    } catch (_) { /* Private browsing may disable storage. */ }
    return initialState();
  }

  function saveState() {
    try { localStorage.setItem(storageKey, JSON.stringify(state)); } catch (_) { /* Keep playing in memory. */ }
  }

  function clueId(categoryIndex, rowIndex) { return `${categoryIndex}-${rowIndex}`; }
  function awardValue(id) {
    const value = points[Number(id.split("-")[1])] || 0;
    return id === dailyDoubleId ? value * 2 : value;
  }
  function activeClue() {
    const [categoryIndex, rowIndex] = activeId.split("-").map(Number);
    return { category: categories[categoryIndex], rowIndex, clue: categories[categoryIndex].clues[rowIndex] };
  }

  function totalScore() {
    return state.awarded.reduce((total, id) => total + awardValue(id), 0);
  }

  function renderScore() {
    const total = totalScore();
    scoreDisplay.textContent = `$${total}`;
    clueClassTotal.textContent = `Class total: $${total}`;
  }

  function renderBoard() {
    board.replaceChildren();
    board.style.setProperty("--category-count", String(categories.length));
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
      button.textContent = played ? "✓" : `$${value}`;
      button.setAttribute("aria-label", `${category.title}, $${value}${played ? ", played; reopen clue" : ""}`);
      button.addEventListener("click", () => openClue(id));
      board.append(button);
    }));
    status.textContent = `${state.used.length} of ${categories.length * points.length} clues played`;
  }

  function renderScoring() {
    const awarded = state.awarded.includes(activeId);
    const value = awardValue(activeId);
    awardButton.textContent = awarded ? `Undo $${value} award` : `Award $${value} to class`;
    awardButton.setAttribute("aria-pressed", String(awarded));
    renderScore();
  }

  function renderClue(clue) {
    prompt.replaceChildren();
    const codePattern = /```(?:sql)?\n([\s\S]*?)\n```|`([^`\n]+)`/g;
    let cursor = 0;
    for (const match of clue.matchAll(codePattern)) {
      if (match.index > cursor) prompt.append(document.createTextNode(clue.slice(cursor, match.index)));
      const code = document.createElement("code");
      code.textContent = match[1] ?? match[2];
      if (match[1] === undefined) prompt.append(code);
      else {
        const block = document.createElement("pre");
        block.append(code);
        prompt.append(block);
      }
      cursor = match.index + match[0].length;
    }
    if (cursor < clue.length) prompt.append(document.createTextNode(clue.slice(cursor)));
  }

  function openClue(id) {
    priorFocus = document.activeElement;
    activeId = id;
    const { category, clue } = activeClue();
    document.getElementById("clue-category").textContent = category.title;
    document.getElementById("clue-value").textContent = `$${awardValue(id)}`;
    dailyDoubleBanner.hidden = id !== dailyDoubleId;
    renderClue(clue);
    renderScoring();
    overlay.hidden = false;
    document.body.style.overflow = "hidden";
    window.MathJax?.typesetPromise?.([prompt]);
    document.getElementById("clue-heading").focus();
  }

  function closeClue(markPlayed) {
    if (!activeId) return;
    if (markPlayed && !state.used.includes(activeId)) state.used.push(activeId);
    if (!markPlayed && !state.used.includes(activeId)) {
      state.awarded = state.awarded.filter(id => id !== activeId);
      renderScore();
    }
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

  awardButton.addEventListener("click", () => {
    if (!activeId) return;
    if (state.awarded.includes(activeId)) state.awarded = state.awarded.filter(id => id !== activeId);
    else state.awarded.push(activeId);
    saveState();
    renderScoring();
  });
  finishButton.addEventListener("click", () => closeClue(true));
  document.getElementById("clue-close").addEventListener("click", () => closeClue(false));
  document.getElementById("game-reset").addEventListener("click", () => {
    if (!window.confirm("Clear the class score and played clues for a new game?")) return;
    state = initialState(); saveState(); renderBoard(); renderScore();
  });
  fullscreenButton.addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else game.requestFullscreen?.();
  });
  document.addEventListener("fullscreenchange", () => { fullscreenButton.textContent = document.fullscreenElement ? "Exit full screen" : "Full screen"; });
  document.addEventListener("keydown", event => {
    if (!activeId) return;
    if (event.key === "Escape") { event.preventDefault(); closeClue(false); }
    if (event.key === "Tab") {
      const focusable = [...overlay.querySelectorAll("button:not([hidden]):not(:disabled)")].filter(button => button.offsetParent !== null);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement.id === "clue-heading")) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });

  renderBoard();
  renderScore();
})();
