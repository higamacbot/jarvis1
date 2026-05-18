# HIGA HOUSE v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `frontend/house_v2a.html` as a parity-plus replacement candidate for HIGA HOUSE, then compare it against a parallel Claude-built `house_v2b` before choosing a final `house_v2`.

**Architecture:** Keep the current `frontend/house.html` runtime model intact: one self-contained HTML file with inline CSS and JavaScript, driven by `/ws/house`, `/api/bots/status`, `/api/bots/activity`, `/api/bots/notifications`, and `/api/workflows`. Build `house_v2a.html` as a separate candidate page that reuses the existing room data model, canvas animation system, debate renderer, and message flow, then layer on the new operations rail and status line without changing backend contracts.

**Tech Stack:** Static HTML, inline CSS, inline browser JavaScript, WebSocket, existing Jarvis JSON API endpoints, local browser smoke verification

---

## File Structure

- Create: `/Users/higabot1/jarvis1-1/frontend/house_v2a.html`
  - Purpose: Codex-built replacement candidate UI with parity-plus behavior
- Modify: `/Users/higabot1/jarvis1-1/frontend/house.html`
  - Purpose: None during implementation unless a tiny shared bugfix is unavoidable; prefer no change
- Reference: `/Users/higabot1/jarvis1-1/docs/superpowers/specs/2026-05-17-higa-house-v2-design.md`
  - Purpose: Approved replacement spec
- Create: `/Users/higabot1/jarvis1-1/docs/superpowers/plans/2026-05-17-higa-house-v2-implementation.md`
  - Purpose: This implementation plan
- Optional later create: `/Users/higabot1/jarvis1-1/frontend/house_v2_compare.md`
  - Purpose: Short comparison notes after `house_v2a` and `house_v2b` both exist

## Task 1: Scaffold `house_v2a.html` With the Approved Layout Shell

**Files:**
- Create: `/Users/higabot1/jarvis1-1/frontend/house_v2a.html`
- Reference: `/Users/higabot1/jarvis1-1/frontend/house.html`
- Reference: `/Users/higabot1/jarvis1-1/docs/superpowers/specs/2026-05-17-higa-house-v2-design.md`

- [ ] **Step 1: Write the failing structure target**

Create the initial page skeleton in `house_v2a.html` with the required high-level regions but no live logic yet:

```html
<div id="app">
  <div id="topbar"></div>
  <div id="statusline"></div>
  <div id="main">
    <div id="house-shell">
      <div id="hero"></div>
      <div id="hgrid"></div>
    </div>
    <div id="opsrail">
      <section id="workflow-card"></section>
      <section id="review-card"></section>
      <section id="handoff-feed"></section>
      <section id="artifact-list"></section>
      <section id="usage-panel"></section>
      <section id="chatpane"></section>
      <section id="composer"></section>
    </div>
  </div>
  <div id="bbar"></div>
</div>
```

- [ ] **Step 2: Run a static smoke check to verify the file exists and contains the required regions**

Run:

```bash
rg -n "statusline|opsrail|workflow-card|artifact-list|composer" /Users/higabot1/jarvis1-1/frontend/house_v2a.html
```

Expected: five matches, one for each required region id

- [ ] **Step 3: Write the minimal visual shell**

Port the approved visual language into the new page:

```css
#app { display:grid; grid-template-rows:60px 40px 1fr 34px; height:100vh; }
#main { display:grid; grid-template-columns:minmax(760px,1fr) 400px; gap:14px; }
#hgrid { display:grid; grid-template-columns:repeat(4,1fr); grid-template-rows:repeat(6,1fr); gap:10px; }
#opsrail { display:grid; grid-template-rows:auto auto auto auto auto minmax(240px,1fr) auto; gap:10px; overflow-y:auto; }
.room { position:relative; border:1px solid var(--line); border-radius:12px; }
.panel { border:1px solid var(--line); border-radius:14px; background:var(--panel); }
```

Use the approved draft style direction, but keep the current HIGA HOUSE retro feel.

- [ ] **Step 4: Run a visual load check**

Run:

```bash
python3 -m http.server 8765 --directory /Users/higabot1/jarvis1-1/frontend
```

Then open:

```text
http://localhost:8765/house_v2a.html
```

Expected: the page loads with the new top bar, status line, room grid shell, operations rail shell, and bottom bar, even if all content is still placeholder text

- [ ] **Step 5: Commit**

```bash
git -C /Users/higabot1/jarvis1-1 add frontend/house_v2a.html
git -C /Users/higabot1/jarvis1-1 commit -m "feat: scaffold house v2a layout shell"
```

## Task 2: Port the Shared Room Model and Room Rendering

**Files:**
- Modify: `/Users/higabot1/jarvis1-1/frontend/house_v2a.html`
- Reference: `/Users/higabot1/jarvis1-1/frontend/house.html:110-328`

- [ ] **Step 1: Write the failing room data target**

Copy the room metadata contract into `house_v2a.html` so it uses the same bot ids and layout expectations:

```js
const BOTS = { /* same ids as house.html */ };
const BOT_IDS = [/* same non-roundtable ids as house.html */];
const LAYOUT = [/* same room positions as house.html */];
```

Keep ids exactly aligned with the current page so backend status updates map correctly.

- [ ] **Step 2: Run a data-presence check**

Run:

```bash
rg -n "const BOTS|const BOT_IDS|const LAYOUT|debateroom|roundtable" /Users/higabot1/jarvis1-1/frontend/house_v2a.html
```

Expected: matches for all three constants plus `debateroom` and `roundtable`

- [ ] **Step 3: Write the minimal grid population code**

Render the room cards from the shared data model:

```js
const grid = document.getElementById('hgrid');
LAYOUT.forEach(room => {
  const bot = BOTS[room.id];
  const div = document.createElement('div');
  div.className = 'room' + (room.id === 'roundtable' ? ' rt' : '');
  div.id = 'room-' + room.id;
  div.style.gridColumn = `${room.col}/span ${room.w}`;
  div.style.gridRow = `${room.row}/span ${room.h}`;
  div.innerHTML = `<div class="rlabel">${bot.label}</div><div class="room-body"></div>`;
  grid.appendChild(div);
});
```

Also add special visual markup for:

- `roundtable`
- `debateroom`
- regular bot rooms

- [ ] **Step 4: Port the existing canvas animation contract**

Carry over the current canvas-based identity instead of replacing it:

```js
const BA = {};
let tick = 0;

function drawRoom(id) { /* port current room sprite rendering */ }
function drawDebateArena(ctx, W, H) { /* port current arena rendering */ }
function drawRT(ctx, W, H, isAct) { /* port current roundtable rendering */ }
function loop() {
  tick++;
  [...BOT_IDS, 'roundtable'].forEach(id => drawRoom(id));
  requestAnimationFrame(loop);
}
```

Required parity details:

- regular room sprites still render
- roundtable still renders its constellation layout
- debate arena still renders its seated characters
- individual debate rooms still show `IN ARENA` while `debateroom` is active

- [ ] **Step 5: Run a DOM and canvas verification**

Open the page and verify:

- 16 rooms render
- roundtable spans two columns/two rows
- debate arena spans two columns/two rows
- room labels match the current UI
- canvas sprites render instead of empty boxes

Expected: the v2 grid remains unmistakably HIGA HOUSE rather than a new layout

- [ ] **Step 6: Commit**

```bash
git -C /Users/higabot1/jarvis1-1 add frontend/house_v2a.html
git -C /Users/higabot1/jarvis1-1 commit -m "feat: port house room model to v2a"
```

## Task 3: Restore Room Selection, Chat Flow, and Debate Rendering

**Files:**
- Modify: `/Users/higabot1/jarvis1-1/frontend/house_v2a.html`
- Reference: `/Users/higabot1/jarvis1-1/frontend/house.html:332-518`

- [ ] **Step 1: Write the failing interaction target**

Add the required chat and selection surface ids:

```html
<div id="chatpane">
  <div id="cheader"></div>
  <div id="msgs"></div>
  <div id="iarea">
    <textarea id="minput"></textarea>
    <button id="sbtn">↑</button>
  </div>
</div>
```

Even though the operations rail is redesigned, the page still needs these core ids and behaviors.

- [ ] **Step 2: Run a selector check**

Run:

```bash
rg -n "id=\"msgs\"|id=\"minput\"|id=\"sbtn\"|function selectBot|function send|function colorDebateMsg" /Users/higabot1/jarvis1-1/frontend/house_v2a.html
```

Expected: matches for all core chat ids and functions

- [ ] **Step 3: Port the minimal live behavior**

Port and adapt the current logic for:

- `selectBot(id)`
- `addMsg(role, text, botId)`
- `colorDebateMsg(text)`
- `showThink()` / `hideThink()`
- `send()`
- textarea autosize

Use the existing behavior contract:

```js
inp.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

document.getElementById('sbtn').addEventListener('click', send);
```

Preserve debate room special rendering for `[SHAMAN]`, `[LIB MOM]`, and `[MAGA DAD]`.
Also preserve the current `debateroom` side effects:

- `shaman`, `libmom`, and `magadad` shift into debate visual state
- debate bot rooms show `IN ARENA`
- debate arena receives the highlighted active state

- [ ] **Step 4: Run a manual chat smoke test**

Open `house_v2a.html` against the live app server and verify:

- clicking a room changes the active context
- the composer placeholder updates to the selected bot
- pressing Enter sends
- bot replies append in the new layout
- debate room messages keep special rendering

Expected: v2a is already usable for chat before the new operations extras are added

- [ ] **Step 5: Commit**

```bash
git -C /Users/higabot1/jarvis1-1 add frontend/house_v2a.html
git -C /Users/higabot1/jarvis1-1 commit -m "feat: restore chat and debate behavior in v2a"
```

## Task 4: Restore WebSocket, Telemetry, Status, and Reconnect Behavior

**Files:**
- Modify: `/Users/higabot1/jarvis1-1/frontend/house_v2a.html`
- Reference: `/Users/higabot1/jarvis1-1/frontend/house.html:460-706`

- [ ] **Step 1: Write the failing runtime target**

Add all live shell targets used by the current page:

```html
<div id="t-btc"></div>
<div id="t-eth"></div>
<div id="t-sol"></div>
<div id="t-port"></div>
<div id="t-pl"></div>
<span id="systxt"></span>
<b id="b-cpu"></b>
<b id="b-ram"></b>
<b id="b-up"></b>
<b id="b-agents"></b>
<span id="ctxt"></span>
```

- [ ] **Step 2: Run a runtime id check**

Run:

```bash
rg -n "t-btc|t-eth|t-sol|t-port|t-pl|systxt|b-cpu|b-ram|b-up|b-agents|ctxt|function connect" /Users/higabot1/jarvis1-1/frontend/house_v2a.html
```

Expected: matches for every telemetry id plus `connect`

- [ ] **Step 3: Port the transport and shell logic**

Port and adapt:

- `connect()`
- WebSocket open / message / close / error handling
- telemetry updates
- reconnect state

Keep the current endpoint contract:

```js
const proto = location.protocol === 'https:' ? 'wss' : 'ws';
ws = new WebSocket(`${proto}://${location.host}/ws/house`);
```

Also preserve:

- answer rendering
- reconnect text
- status dot behavior
- notification-safe room flash/reset behavior

- [ ] **Step 4: Run a live transport smoke test**

With the Jarvis server running, verify:

- the page connects without console errors
- telemetry values populate
- connection state changes from offline to online
- disconnect/reconnect behavior still works if the server is restarted

Expected: v2a matches current operational shell behavior

- [ ] **Step 5: Commit**

```bash
git -C /Users/higabot1/jarvis1-1 add frontend/house_v2a.html
git -C /Users/higabot1/jarvis1-1 commit -m "feat: restore live transport and telemetry in v2a"
```

## Task 5: Restore Bot Status, Room Activity Text, Activity Feed, and Workflow Chip

**Files:**
- Modify: `/Users/higabot1/jarvis1-1/frontend/house_v2a.html`
- Reference: `/Users/higabot1/jarvis1-1/frontend/house.html:521-706`

- [ ] **Step 1: Write the failing operations target**

Add the live operation ids:

```html
<div id="actfeed"></div>
<span id="wfchip"></span>
<div id="syswelcome"></div>
```

Every room must also still support:

```html
<div class="ract"></div>
```

- [ ] **Step 2: Run a polling-target check**

Run:

```bash
rg -n "function applyBotStatuses|function pollBotStatuses|function pollActivity|function pollWorkflows|wfchip|syswelcome|ract" /Users/higabot1/jarvis1-1/frontend/house_v2a.html
```

Expected: matches for all functions and required operation ids

- [ ] **Step 3: Port the live polling logic**

Port and adapt:

- `STATUS_COLORS`
- `STATUS_GLOW`
- `STATUS_DOT`
- `applyBotStatuses(statuses)`
- `pollBotStatuses()`
- `pollBotNotifications()`
- `pollActivity()`
- `pollWorkflows()`

Keep these live endpoints:

```js
await fetch('/api/bots/status');
await fetch('/api/bots/notifications');
await fetch('/api/bots/activity');
await fetch('/api/workflows');
```

In v2a, map them into:

- stronger room-state styling
- a cleaner activity list
- a top status-line summary
- an active workflow card

- [ ] **Step 4: Run a parity-plus smoke test**

Verify:

- room subtitles update from `activity_text`
- status colors still reflect idle/working/review_ready/blocked
- unsolicited notifications still appear in the message log
- the activity feed updates
- the workflow chip/status line reacts to active workflow state
- dynamic agent count updates correctly from bot status payloads

Expected: all current observability features work, plus the state is easier to read than the old sidebar

- [ ] **Step 5: Commit**

```bash
git -C /Users/higabot1/jarvis1-1 add frontend/house_v2a.html
git -C /Users/higabot1/jarvis1-1 commit -m "feat: add live status and workflow visibility to v2a"
```

## Task 6: Build the Operations Rail Sections and Quick Commands

**Files:**
- Modify: `/Users/higabot1/jarvis1-1/frontend/house_v2a.html`
- Reference: `/Users/higabot1/jarvis1-1/docs/superpowers/specs/2026-05-17-higa-house-v2-design.md`

- [ ] **Step 1: Write the failing rail target**

Add all rail section ids and quick command chips:

```html
<section id="workflow-card"></section>
<section id="review-card"></section>
<section id="handoff-feed"></section>
<section id="artifact-list"></section>
<section id="usage-panel"></section>
<div id="quick-actions">
  <button data-cmd="review latest carousel"></button>
  <button data-cmd="review latest clip report"></button>
  <button data-cmd="workflow clip_to_carousel"></button>
  <button data-cmd="review latest workflow"></button>
</div>
```

- [ ] **Step 2: Run a rail-structure check**

Run:

```bash
rg -n "workflow-card|review-card|handoff-feed|artifact-list|usage-panel|data-cmd=" /Users/higabot1/jarvis1-1/frontend/house_v2a.html
```

Expected: matches for each rail section and all quick-command buttons

- [ ] **Step 3: Write minimal data-mapping helpers**

Add small helpers that map existing live data into the rail:

```js
function renderWorkflowCard(job) { /* map /api/workflows job */ }
function renderReviewCard(events) { /* infer latest review state from activity */ }
function renderHandoffFeed(events) { /* filter handoff events */ }
function renderArtifactList() { /* action shortcuts, not filesystem links */ }
function wireQuickActions() {
  document.querySelectorAll('[data-cmd]').forEach(btn => {
    btn.addEventListener('click', () => {
      inp.value = btn.dataset.cmd;
      send();
    });
  });
}
```

Rules:

- quick commands must reuse the existing `send()` path
- artifact shortcuts must trigger honest commands like `review latest carousel`, not raw file paths
- review card must degrade to stage/status text if no trustworthy verdict text exists
- usage panel must show real tracked values only if a data source exists
- usage panel must otherwise show `not connected`

- [ ] **Step 4: Run a rail behavior check**

Verify:

- quick-action buttons send real commands
- workflow section updates when a workflow runs
- handoff section highlights real handoff events
- artifact section remains honest if only partial data is available
- the message log remains visible and usable beneath the compact operations cards
- usage panel does not invent token balances

Expected: v2a clearly surfaces the new Jarvis upgrades without backend changes

- [ ] **Step 5: Commit**

```bash
git -C /Users/higabot1/jarvis1-1 add frontend/house_v2a.html
git -C /Users/higabot1/jarvis1-1 commit -m "feat: add operations rail and quick commands to v2a"
```

## Task 7: Prepare the Parallel Claude Build Brief and Comparison Pass

**Files:**
- Create: `/Users/higabot1/jarvis1-1/frontend/house_v2b.html` (Claude-owned, not Codex-generated in this task)
- Optional later create: `/Users/higabot1/jarvis1-1/frontend/house_v2_compare.md`

- [ ] **Step 1: Write the failing comparison target**

Create a comparison checklist in notes form before reviewing both versions:

```markdown
- visual identity preserved
- message log remains visible
- room selection works
- websocket chat works
- notifications work
- debate rendering works
- canvas animation preserved
- telemetry works
- status polling works
- workflow visibility works
- quick commands work
- artifact shortcuts are honest
- no fake usage state
```

- [ ] **Step 2: Hand Claude the exact parallel build prompt**

Use this prompt in Claude Code:

```text
Build /Users/higabot1/jarvis1-1/frontend/house_v2b.html as a parity-plus replacement candidate for /Users/higabot1/jarvis1-1/frontend/house.html.

Requirements:
- preserve current canvas animation behavior
- preserve current websocket chat behavior
- preserve room selection
- preserve debate room behavior
- preserve roundtable behavior
- preserve telemetry and reconnect handling
- preserve /api/bots/status, /api/bots/activity, and /api/bots/notifications polling
- preserve /api/workflows support
- keep the message log visible as a first-class pane
- add a visible status line
- add operations rail sections for workflow, review, handoffs, artifacts, and usage
- add quick commands that reuse the real send path
- do not touch house.html
- do not commit yet

Reference spec:
- /Users/higabot1/jarvis1-1/docs/superpowers/specs/2026-05-17-higa-house-v2-design.md
```

- [ ] **Step 3: Run the side-by-side comparison**

Open and compare:

- `frontend/house.html`
- `frontend/house_v2a.html`
- `frontend/house_v2b.html`

Judge them against the checklist from Step 1.

- [ ] **Step 4: Write the merge recommendation**

Document:

- what `v2a` got right
- what `v2b` got right
- what should move into the final `house_v2.html`

Expected: a clean synthesis path rather than choosing by vibes

- [ ] **Step 5: Commit comparison notes if a file is created**

```bash
git -C /Users/higabot1/jarvis1-1 add frontend/house_v2_compare.md
git -C /Users/higabot1/jarvis1-1 commit -m "docs: compare house v2a and v2b candidates"
```

## Self-Review

### Spec Coverage

The plan covers:

- separate candidate file strategy
- parity restoration before new features
- room-grid preservation
- workflow, review, handoff, artifact, and usage surfaces
- quick commands
- side-by-side comparison against a Claude-built parallel version

No spec sections are intentionally dropped.

### Placeholder Scan

This plan avoids `TBD`, `TODO`, and undefined future tasks. Where a source does not yet exist, the implementation requirement is explicit: render an honest `not connected` state instead of fabricating data.

### Type Consistency

The plan keeps the existing page’s naming contract:

- `BOTS`
- `BOT_IDS`
- `LAYOUT`
- `selectBot`
- `send`
- `connect`
- `applyBotStatuses`
- `pollActivity`
- `pollWorkflows`

This reduces drift while building the replacement candidate.
