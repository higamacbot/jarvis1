# HIGA HOUSE v2 — UI Audit Report
**Date:** 2026-05-18  
**Auditor:** Claude Code (claude-sonnet-4-6)  
**Target:** `http://localhost:8000/house` → `frontend/house_v2.html` (987 lines)  
**Method:** Read-only static analysis + live endpoint polling (3 passes)  
**Scope:** JavaScript data-binding correctness, API contract validation, CSS override bugs, dead code, UX regressions  

---

## Executive Summary

12 bugs found: **2 HIGH**, **5 MEDIUM**, **5 LOW**.

The two HIGH bugs both involve inline styles overriding CSS classes — a specificity conflict pattern that appears in two different places. The most visible user-facing issue is that **clicking a room lights it up but the cyan glow disappears within 3 seconds** due to the status poller overwriting inline styles. The second HIGH bug causes **reply flash animations to conflict**, leaving rooms in an incorrect border state after any bot response.

All 5 API endpoints returned correct data. The main gap between API and UI: the usage grid has full HTML but zero JavaScript backing it — live usage data from `/api/usage` never renders.

---

## Endpoints Verified

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/bots/status` | ✅ 200 | All bot fields present, all bots idle |
| `GET /api/bots/activity` | ✅ 200 | 30 events, handoff/task fields correct |
| `GET /api/bots/notifications` | ✅ 200 | Empty array `[]` (no pending) |
| `GET /api/workflows` | ✅ 200 | 7 workflows returned, all `done` |
| `GET /api/usage` | ✅ 200 | Real data — 37 req, 5.3M tokens |
| `WS /ws/house` | ⚠️ UNVERIFIED | Tool call unavailable during audit |

---

## Bug Report

### HIGH

---

#### BUG-01 — Active room glow overridden by status poller every 3 seconds

**File:** `frontend/house_v2.html:778-779`  
**Severity:** HIGH  
**Symptom:** Click a room → cyan glow appears → disappears within 3 seconds.

`applyBotStatuses()` runs every 3 seconds via `setInterval(pollBotStatuses, 3000)` (line 824). For every bot room it writes:

```js
room.style.borderColor = STATUS_COLORS[status] || STATUS_COLORS.idle;  // '#0044AA'
room.style.boxShadow  = STATUS_GLOW[status]   || STATUS_GLOW.idle;     // '0 0 10px rgba(0,100,255,0.4)'
```

These inline styles override the CSS class `.room.active` (line 106):
```css
.room.active { border-color: var(--cyan); box-shadow: 0 0 18px var(--cyan-glow)... }
```

Inline `style` attribute has higher specificity than a CSS class. Within 3 seconds, the active cyan glow is replaced by the idle dark-blue `#0044AA` color. The room visually deselects while `curBot` still points to it.

**Fix:** Skip the inline style write for the currently selected room:
```js
Object.entries(statuses).forEach(([botId, data]) => {
  if (botId === curBot) return;   // let CSS .active class handle it
  const room = document.getElementById('room-' + botId);
  // ...rest unchanged
});
```

---

#### BUG-02 — Dual setTimeout race in WebSocket answer handler

**File:** `frontend/house_v2.html:736-749`  
**Severity:** HIGH  
**Symptom:** Bot answer flash animation conflicts — rooms end up wrong color after every reply.

The `ws.onmessage` answer handler runs two competing blocks on the same DOM node:

```js
// Block A (lines 737-739):
room.style.borderColor = '#00FF88';  // bright green
room.style.boxShadow  = '0 0 25px rgba(0,255,136,0.7)';
setTimeout(() => {
  room.style.borderColor = '#0044AA';
  room.style.boxShadow   = 'none';
}, 3000);

// Block B (lines 746-749) — runs IMMEDIATELY after Block A, same tick:
doneRoom.style.borderColor = '#006600';  // dark green (overwrites A instantly)
doneRoom.style.boxShadow   = '0 0 14px rgba(0,255,100,0.7)';
setTimeout(() => {
  doneRoom.style.borderColor = '#0044AA';
  doneRoom.style.boxShadow   = '0 0 10px rgba(0,100,255,0.4)';
}, 2000);
```

Execution sequence:
- t=0ms: bright green (A) → immediately overwritten by dark green (B)  
- t=2000ms: B timeout fires → `#0044AA` / dim blue shadow  
- t=3000ms: A timeout fires → `#0044AA` / **`none`** (shadow removed)  

Net result: the answer glow is imperceptible, and the room ends with `box-shadow: none` — darker than the idle state.

**Fix:** Delete Block B entirely (lines 745-749). Block A already handles the return-to-idle transition.

---

### MEDIUM

---

#### BUG-03 — Usage grid always shows "not connected" — no polling function

**File:** `frontend/house_v2.html:332-337`  
**Severity:** MEDIUM  
**Symptom:** The 2×2 usage grid (`Claude Code`, `Codex`, `Requests`, `Remaining`) never updates from its default "not connected" text.

HTML elements exist: `#ug-claude`, `#ug-codex`, `#ug-req`, `#ug-rem`. The backend `/api/usage` returns live data:
```json
{
  "claude_code": { "label": "37 req · 5.3M tok", "detail": "out 15.1k · cache 5.3M" },
  "codex":       { "label": "2 req · local" },
  "requests":    { "label": "39 total today" },
  "remaining":   { "connected": false, "label": "local only" }
}
```

No `pollUsage()` function exists anywhere in the JS. The grid is entirely disconnected.

**Fix:** Add a `pollUsage()` function and call it on an interval:
```js
async function pollUsage() {
  try {
    const r = await fetch(`${API_ORIGIN}/api/usage`);
    if (!r.ok) return;
    const d = await r.json();
    const set = (id, val, dim) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = val;
      el.className = 'ugv' + (dim ? ' dim' : '');
    };
    set('ug-claude', d.claude_code?.label || '—', !d.claude_code?.connected);
    set('ug-codex',  d.codex?.label      || '—', !d.codex?.connected);
    set('ug-req',    d.requests?.label   || '—', !d.requests?.connected);
    set('ug-rem',    d.remaining?.label  || '—', !d.remaining?.connected);
  } catch (e) {}
}
pollUsage();
setInterval(pollUsage, 30000);
```

---

#### BUG-04 — Review card always shows stale done-job data

**File:** `frontend/house_v2.html:897-898`  
**Severity:** MEDIUM  
**Symptom:** The "Latest Review" ops card permanently shows data from the most recent adversarial_review job, even when idle.

```js
const reviewJob = (jobs||[]).find(j => j.name === 'adversarial_review') || null;
_latestReviewJob = reviewJob;
```

`.find()` returns the first match regardless of `status`. When no job is running, this returns the most recent done job. `renderReviewCard()` then displays it with a '✓' suffix, so the card permanently shows "ARBITER✓" (or "RUNNING✓" — see BUG-05) in idle state, giving false impression of recent review activity.

**Fix:** Prefer a running job, fall back to null when none is active:
```js
const reviewJob = (jobs||[]).find(j => j.name === 'adversarial_review' && j.status === 'running') || null;
```
Or if showing the latest completed job is desired, add a visual indicator that it's historical.

---

#### BUG-05 — renderReviewCard stages array out-of-bounds — shows "RUNNING✓ · step 4/3"

**File:** `frontend/house_v2.html:941-948`  
**Severity:** MEDIUM  
**Symptom:** Latest review card shows "RUNNING✓" and "done · step 4/3" instead of "ARBITER✓" and "done · step 3/3".

```js
const stages = ['PRODUCER', 'CHALLENGER', 'ARBITER'];  // indices 0, 1, 2
const stageName = stages[rv.current_step || 0] || 'RUNNING';
```

When a 3-step workflow completes, the DB stores `current_step: 3` (steps completed count). `stages[3]` = `undefined`, triggering the `|| 'RUNNING'` fallback. The sub-label also displays `(rv.current_step||0)+1` = 4 as the step number.

**Fix:**
```js
const stageIdx = Math.min((rv.current_step || 0), stages.length - 1);
const stageName = stages[stageIdx] || 'RUNNING';
// For sub-label:
const displayStep = Math.min((rv.current_step || 0), stages.length);
if (subEl) subEl.textContent = isRunning
  ? 'adversarial review active'
  : `done · step ${displayStep}/${stages.length}`;
```

---

#### BUG-06 — workflowBannerTimer always null — clearTimeout path is dead code

**File:** `frontend/house_v2.html:448, 903`  
**Severity:** MEDIUM  
**Symptom:** No visible runtime effect, but dead code indicates an incomplete feature.

`workflowBannerTimer` is declared at line 448 (`let lastStatuses=null,workflowBannerTimer=null`) and cleared at line 903 if truthy:
```js
if (workflowBannerTimer) { clearTimeout(workflowBannerTimer); workflowBannerTimer = null; }
```

But `workflowBannerTimer = setTimeout(...)` is never written anywhere in the file. The variable is always `null`, so the clearTimeout branch never executes. The feature that was meant to auto-clear the workflow banner chip after a delay was never wired up.

**Fix:** Either implement the banner-auto-clear timeout:
```js
workflowBannerTimer = setTimeout(() => {
  chip.style.display = 'none';
  workflowBannerTimer = null;
}, 10000);
```
Or remove the dead variable and clearTimeout call entirely.

---

#### BUG-07 — Debateroom inline border persists indefinitely after deselection

**File:** `frontend/house_v2.html:603-604`  
**Severity:** MEDIUM  
**Symptom:** After clicking debateroom then any other room, the debateroom tile retains an orange border permanently.

When `id === 'debateroom'`, `selectBot()` sets:
```js
const arena = document.getElementById('room-debateroom');
if (arena) { arena.style.borderColor = '#FF6B35'; arena.style.boxShadow = '0 0 20px rgba(255,107,53,0.6)'; }
```

When you click away, `selectBot()` removes `.active` from debateroom but never clears the inline style. `applyBotStatuses()` skips debateroom because it's not in the API `/api/bots/status` response (not a polled bot). So the orange border persists on debateroom until page reload.

**Fix:** In the `else` branch of `selectBot()`, reset the arena inline style:
```js
} else {
  const arena = document.getElementById('room-debateroom');
  if (arena) { arena.style.borderColor = ''; arena.style.boxShadow = ''; }
  if (!['shaman', 'libmom', 'magadad'].includes(id)) {
    ['shaman', 'libmom', 'magadad'].forEach(bid => { const b = BA[bid]; if (b) b.wt = 0; });
  }
}
```

---

### LOW

---

#### BUG-08 — addMsg split condition may over-split messages containing colons

**File:** `frontend/house_v2.html:655-666`  
**Severity:** LOW

```js
if (role === 'bot' && text.includes(':') && text.split('\n').length > 1) {
  text.split('\n').forEach(line => { ... });
}
```

Any multi-line bot response that contains a colon (URLs, timestamps, "Status: working") gets split line-by-line into separate `.mb.bot` bubbles. A response like a JSON block or a formatted table containing ':' would be fragmented. The colon check was likely meant to detect "LABEL: content" format lines, but the AND condition with multi-line means any long code block or URL-containing response gets exploded.

**Fix:** Narrow the condition, e.g. check if the first line specifically matches `LABEL:` format, or remove the colon condition entirely and just split on double-newlines for paragraph separation.

---

#### BUG-09 — Message log DOM grows without bound

**File:** `frontend/house_v2.html:644-668`  
**Severity:** LOW

`addMsg()` always appends to `#msgs` and never removes old elements. In a long session with high bot activity, the DOM accumulates unbounded message nodes. Browser scroll performance degrades past ~500 nodes. This matters more for the activity feed (`pollActivity()` slices to 8) than the message log, where no cap exists.

**Fix:** Add a trim at end of `addMsg()`:
```js
while (msgsEl.children.length > 200) msgsEl.removeChild(msgsEl.firstChild);
```

---

#### BUG-10 — pollBotNotifications 1500ms throttle guard never triggers

**File:** `frontend/house_v2.html:804-806`  
**Severity:** LOW

```js
const now = Date.now();
if (now - lastNotificationPoll < 1500) return;
lastNotificationPoll = now;
```

`pollBotNotifications()` is called via `setInterval(pollBotNotifications, 2500)` (line 824). The interval guarantees at least 2500ms between calls, so `now - lastNotificationPoll` is always ≥ 2500ms. The `< 1500` guard is dead code — it never fires.

The only way it would matter is if `pollBotNotifications()` were called from multiple places in rapid succession, which it isn't. Safe to remove.

---

#### BUG-11 — .ract status indicator missing CSS for review_ready and blocked states

**File:** `frontend/house_v2.html:132-135, 793`  
**Severity:** LOW

CSS defines only two `.ract` styles:
```css
.ract      { color: rgba(0,255,255,0.4); }
.ract.busy { color: rgba(255,184,0,0.72); }
```

`applyBotStatuses()` assigns `.ract.busy` only for `working` status:
```js
ract.className = 'ract' + (status === 'working' && actText !== 'idle' ? ' busy' : '');
```

`review_ready` (green) and `blocked` (red) bots display with the default dim-cyan text — indistinguishable from idle. The `STATUS_DOT` colors for those states are correct, but the activity text label doesn't match.

**Fix:** Add CSS classes and extend the className logic:
```css
.ract.ready   { color: rgba(0,255,136,0.65); }
.ract.blocked { color: rgba(255,51,85,0.72); }
```
```js
const cls = { working:'busy', review_ready:'ready', blocked:'blocked' }[status] || '';
ract.className = 'ract' + (cls && actText !== 'idle' ? ' ' + cls : '');
```

---

#### BUG-12 — created_at space-separator may cause non-standard Date parsing for recency coloring

**File:** `frontend/house_v2.html:872`  
**Severity:** LOW

```js
const ago = hf.created_at
  ? Math.round((Date.now() - new Date(hf.created_at).getTime()) / 1000)
  : null;
const isRecent = ago !== null && ago < 30;
```

The DB stores timestamps as `"2026-05-18 05:31:59"` (space separator). ISO 8601 requires `"2026-05-18T05:31:59"`. `new Date("2026-05-18 05:31:59")` is accepted by V8 (Chrome/Node) but is technically non-standard. In other environments it may return `NaN`, making `isRecent` always `false` and the amber <30s highlight never appearing.

**Fix:**
```js
const tsStr = (hf.created_at || '').replace(' ', 'T');
const ago = tsStr ? Math.round((Date.now() - new Date(tsStr).getTime()) / 1000) : null;
```

---

## Summary Table

| ID | Severity | Component | One-line description |
|---|---|---|---|
| BUG-01 | HIGH | `applyBotStatuses()` | Inline style overrides `.room.active` CSS every 3s — active glow lost |
| BUG-02 | HIGH | `ws.onmessage` | Dual setTimeout race — rooms end up `box-shadow: none` after replies |
| BUG-03 | MEDIUM | Usage grid | No `pollUsage()` — `#ug-*` cells always show "not connected" |
| BUG-04 | MEDIUM | `pollWorkflows()` | `_latestReviewJob` includes done jobs — review card always stale |
| BUG-05 | MEDIUM | `renderReviewCard()` | `stages[3]` OOB — shows "RUNNING✓" and "done · step 4/3" |
| BUG-06 | MEDIUM | `pollWorkflows()` | `workflowBannerTimer` always null — clearTimeout is dead code |
| BUG-07 | MEDIUM | `selectBot()` | Debateroom inline border never cleared on deselection |
| BUG-08 | LOW | `addMsg()` | `includes(':')` condition over-splits multi-line messages with colons |
| BUG-09 | LOW | `addMsg()` | Message log DOM unbounded — no message cap |
| BUG-10 | LOW | `pollBotNotifications()` | 1500ms throttle guard never fires (setInterval = 2500ms) |
| BUG-11 | LOW | `applyBotStatuses()` | `.ract` missing CSS for `review_ready` and `blocked` status states |
| BUG-12 | LOW | `renderHandoffCard()` | `created_at` space separator → non-standard `new Date()` parsing |

---

## Top 3 Recommended Fixes (by user impact)

### 1. Fix BUG-01 — Skip inline style override for active room (line 775)

Highest visible impact. Add one guard at the top of the `forEach` inside `applyBotStatuses()`:

```js
Object.entries(statuses).forEach(([botId, data]) => {
  if (botId === curBot) return;   // ← add this line
  const room = document.getElementById('room-' + botId);
  ...
```

### 2. Fix BUG-02 — Remove duplicate answer flash block (lines 745-749)

Delete the 5-line "Block B" (`doneRoom` block). Block A already handles the flash and reset. The duplicate was likely a copy-paste artifact:

```js
// DELETE lines 745-749:
const doneRoom = document.getElementById('room-' + ansBot);
if (doneRoom) {
  doneRoom.style.borderColor = '#006600'; doneRoom.style.boxShadow = '0 0 14px rgba(0,255,100,0.7)';
  setTimeout(() => { doneRoom.style.borderColor='#0044AA'; doneRoom.style.boxShadow='0 0 10px rgba(0,100,255,0.4)'; }, 2000);
}
```

### 3. Fix BUG-03 — Wire up pollUsage() for the usage grid

Add the `pollUsage()` function (see fix code in BUG-03 section above) and call it after line 984:
```js
pollUsage();
setInterval(pollUsage, 30000);
```

This immediately shows real token/request data in the 2×2 grid that currently always reads "not connected".

---

## Unverified Items

- **WebSocket `/ws/house`** — live telemetry path (telemetry, answer, handoff push) not exercised during audit. Static analysis of `ws.onmessage` handler is complete but runtime behavior unconfirmed.
- **WS reconnect path** — `ws.onclose` → 3s retry → `connect()`. Logic looks correct but not tested.

---

*Generated: 2026-05-18 | Audit method: read-only static analysis + HTTP polling | No code was modified.*
