# HIGA HOUSE v2 Replacement Design

Date: 2026-05-17
Project: `/Users/higabot1/jarvis1-1`
Branch: `codex/jarvis-review-workflows`
Status: Approved design, pre-implementation

## Goal

Create a new HIGA HOUSE UI that can fully replace the current `frontend/house.html` only after it reaches parity with the old UI and adds the new workflow, review, handoff, and artifact visibility that Jarvis now supports.

This is a replacement candidate, not a speculative redesign. The new screen must preserve the command-center identity, the room-grid metaphor, and the existing real-time behavior while making multi-step autonomous work much easier to see and use.

## Product Standard: Parity-Plus

The replacement must satisfy a `parity-plus` rule:

- Keep everything the current UI already does
- Add visibility for workflows, adversarial review, handoffs, and artifact-aware review
- Avoid fake system state or decorative motion disconnected from backend events
- Avoid turning HIGA HOUSE into a generic dark dashboard

The replacement is not allowed to displace the current UI until parity-plus is met.

## Why v2 Is Needed

The current UI is still visually strong, but it is organized around bot presence and room engagement more than operational state. Since the backend now supports workflows, adversarial review, artifact-aware review, handoffs, and live room activity, the interface needs to evolve from `room map + message log` into `room map + operations console`.

The room grid should remain the visual anchor. The main change is information architecture, not product identity.

## Existing Behavior That Must Be Preserved

The v2 screen must preserve all current working behavior from `frontend/house.html`:

- Room grid layout and room labels
- Click-to-engage room selection
- Active room state
- Roundtable behavior
- Debate arena behavior and debate-specific rendering
- Continuous canvas animation loop and per-room canvas rendering
- Live WebSocket chat over `/ws/house`
- Command input, send button, Enter-to-send, and textarea autosize
- Initial system/welcome messaging
- Live telemetry strip for BTC, ETH, SOL, portfolio, and day P&L
- CPU, RAM, uptime, and connection state in the shell
- Polling from `/api/bots/status`
- Polling from `/api/bots/activity`
- Polling from `/api/bots/notifications`
- Per-room `activity_text` subtitles
- Existing room status coloring and working/idle/offline signals
- Reconnect and offline handling

If any of the above is missing or degraded, v2 is not ready to replace the old UI.

## New Behavior That Must Be Added

The replacement must visibly expose newer Jarvis capabilities that currently exist in backend code or workflow behavior:

- Workflow visibility from `/api/workflows`
- Active workflow name, status, current step, and assigned bot
- Clearer review workflow visibility
- Stronger handoff visibility, especially between producing and consuming bots
- Artifact-aware review entry points and shortcuts
- Quick commands for workflow and review actions
- Optional tracked provider usage surface for Claude Code and Codex

This new behavior should be additive and operationally honest. If a feature is not yet backed by real data, the UI should label it as not connected instead of inventing a state.

## Layout Direction

The approved direction is a balanced command-center layout that keeps the HIGA HOUSE identity while upgrading the right side into an operations rail.

### 1. Top Telemetry Bar

Retain the current market and portfolio strip:

- BTC
- ETH
- SOL
- Portfolio
- Day P&L

Retain system shell awareness:

- CPU
- RAM
- Uptime
- Connection state

This area should remain compact, fast, and familiar.

### 2. Persistent Status Line

Add a dedicated operational line directly under the top bar that summarizes the most important active system state.

Examples:

- `Active: clip_to_carousel — step 2/2 — robowright packaging carousel`
- `Review: workflow #5 — challenger running`
- `Idle — no active workflows`

Rules:

- This line must come from real state, primarily `/api/workflows` plus existing activity/status signals
- It should prefer the single most important active operation
- Priority order for v1: active workflow > active review step > recent handoff within 30 seconds > idle
- It should degrade gracefully to idle text when nothing is running

This is the “PAI status line” idea translated into Jarvis-native UI.

### 3. Room Grid

The room grid remains the center of gravity of the interface.

Required behavior:

- Preserve the current grid metaphor and house identity
- Keep the current room topology recognizable
- Preserve click-to-engage interactions
- Preserve roundtable and debate arena special cases
- Preserve the existing canvas-based sprite animation system rather than replacing it in v1

Visual upgrade goals:

- Active rooms should look materially different from idle rooms
- Non-idle rooms should have stronger edge glow and/or subtle pulsing
- Room subtitles should remain concise and tied to real `activity_text`
- Reviewing rooms and workflow-active rooms should be distinguishable without being noisy

The grid should feel more alive, but not cartoonish.

Canvas preservation rule:

- Port the existing `requestAnimationFrame` loop and per-room canvas rendering logic from `house.html` into v2 for the first implementation pass
- Do not replace the canvas system with CSS-only room cards in v1
- Any later canvas redesign should be treated as a separate iteration after parity is proven

Debate preservation rule:

- Preserve `colorDebateMsg()` behavior for `[DEBATE]`, `[SHAMAN]`, `[LIB MOM]`, and `[MAGA DAD]`
- Preserve the debate arena canvas composition with three seated debate characters around a central table
- Preserve the special `IN ARENA` state on the individual debate bot rooms while `debateroom` is active
- Preserve the current coupling where selecting `debateroom` moves `shaman`, `libmom`, and `magadad` into debate-specific visual state

### 4. Operations Rail

The right-side panel should become a stacked operations rail, but it must still include the live message log as a first-class surface.

The v1 layout decision is:

- Keep the message log and command composer in the right-side system surface
- Add the operations sections above the message log instead of replacing it
- Make the right rail wider than the current 300px layout
- Use a scrollable rail so the stacked sections do not clip on shorter screens

Default v1 rail sizing:

- Main layout: `grid-template-columns: minmax(760px, 1fr) 400px`
- Operations/message rail: vertically scrollable
- Message log: flexes to take remaining height after the compact operations cards above it

It should contain these sections:

#### Message Log

Purpose:

- Preserve the current bot conversation history, thinking state, debate formatting, unsolicited notifications, and command-driven feel

Contents:

- Current room/bot conversation history
- Thinking dots
- Debate-specific message rendering
- System/engagement messages

Primary sources:

- `/ws/house`
- `/api/bots/notifications`

#### Active Workflow

Purpose:

- Surface the currently running workflow clearly

Contents:

- Workflow name
- Step count
- Assigned bot
- Status text
- Recent update timestamp
- Progress indicator tied to real step count

Primary source:

- `/api/workflows`

#### Latest Review

Purpose:

- Make adversarial review feel like a first-class system capability

Contents:

- Latest verdict or current review stage
- Reviewed target label
- One-line recommendation or summary

Primary source:

- Existing review workflow outputs and activity data

v1 source constraint:

- There is no dedicated review verdict API yet
- v1 should derive latest review state from `/api/workflows` and `/api/bots/activity`
- If no trustworthy verdict or recommendation text is available, the UI should show stage/status only rather than inventing a summary

#### Recent Handoffs

Purpose:

- Highlight the “team thinking” moments where one bot produces usable context for another

Contents:

- From bot
- To bot
- Topic or target
- Timestamp
- Short summary

Primary source:

- Existing handoff/activity data already logged by Jarvis

This should be more visually prominent than a normal log item.

#### Artifact Shortcuts

Purpose:

- Make generated outputs immediately reachable and reviewable

Contents:

- Latest carousel
- Latest clip report
- Latest workflow result

v1 action rule:

- These are action shortcuts, not arbitrary filesystem links
- Preferred v1 actions are:
  - `review latest carousel`
  - `review latest clip report`
  - `review latest workflow`
- If a richer artifact API is added later, the rail can evolve into direct file or result navigation

#### Tracked Usage

Purpose:

- Give the user a practical view of model usage without pretending to know provider limits that are not exposed

Contents:

- Claude Code tracked usage
- Codex tracked usage
- Request or session totals
- Provider “remaining” only if a real source exists

Rules:

- Actual tracked usage may be shown when logged locally
- Remaining credits/tokens must be labeled unavailable unless a provider exposes them

#### Command Composer

Purpose:

- Keep command-driven control intact while making common actions faster

Contents:

- Text input area
- Send action
- Quick-command chips

Suggested chips:

- `review latest carousel`
- `review latest clip report`
- `workflow clip_to_carousel`
- `review latest workflow`

Quick commands must send real commands through the same command path as typed input.

### 5. Bottom Status Bar

Retain the current shell/status feel at the bottom:

- CPU
- RAM
- Uptime
- Agent count
- Online/reconnect state

This should remain lightweight and not duplicate the main operations rail.

## Data Sources

The new UI should maximize reuse of existing data paths.

### Existing Sources

- `/ws/house`
- `/api/bots/status`
- `/api/bots/activity`
- `/api/bots/notifications`
- Existing telemetry payloads

### New or Expanded Sources

- `/api/workflows`
- Optional future usage endpoint if local provider usage logging is added

The replacement should not require a backend rewrite. It should mostly recompose existing signals and only add small new fetches where necessary.

## Interaction Model

The replacement keeps the current interaction model rather than changing the product into a navigation-heavy application.

Core interaction rules:

- The user still engages bots by selecting rooms
- The command input remains central
- Workflows can be observed without leaving the command context
- Artifacts and reviews should be reachable from the rail without displacing room engagement
- The message log remains visible in the replacement UI, not hidden behind a second mode or tab in v1

The UI should feel like one command center, not a collection of disconnected dashboards.

## Functional Parity Checklist

The following checklist must pass before v2 can replace the current page:

- WebSocket connection works
- Room selection works
- Active bot context updates correctly
- Sending a message works
- Enter-to-send works
- Textarea autosize works
- Bot replies render correctly
- Debate room special formatting still works
- Roundtable selection still works
- Telemetry updates live
- Activity feed updates live
- Notification polling works and unsolicited bot messages still appear
- Per-room subtitles update live
- Bot status coloring remains correct
- Reconnect flow remains correct
- Initial welcome state remains correct
- Dynamic agent count still updates from `/api/bots/status`
- Canvas animation loop still runs
- Debate arena visual state still works, including `IN ARENA` behavior

## New Capability Checklist

These additions must also work before replacement:

- Workflow card shows real running workflow state
- Status line reflects real workflow/review state
- Handoffs are clearly visible
- Artifact shortcuts trigger honest review or workflow commands for real recent artifacts
- Review-oriented quick commands are present
- Workflow quick commands are present
- Usage panel is either connected to real data or explicitly labeled not connected

## File Strategy

Implementation should happen in a separate candidate page first:

- `frontend/house_v2.html`

Do not overwrite `frontend/house.html` during initial implementation.

Replacement options after validation:

- Rename `house_v2.html` into `house.html`
- Or update the app to serve `house_v2.html` instead

This keeps rollback simple and avoids breaking the currently working interface.

## Implementation Order

### Phase 1: Build v2 Shell

- Create `frontend/house_v2.html`
- Port the approved visual shell and layout
- Keep styling consistent with HIGA HOUSE identity

### Phase 2: Restore Old Behavior First

Port and verify the current working behaviors before layering new features:

- Message log placement and sizing
- WebSocket chat
- Notification polling
- Room selection
- Canvas animation loop
- Debate behavior
- Telemetry updates
- Status polling
- Activity polling
- Reconnect behavior
- Command input behavior

The principle is: no new surface area before old behavior works in v2.

### Phase 3: Add Operations Rail Wiring

- Wire the active workflow section to `/api/workflows`
- Recompose activity data into clearer handoff/review presentation
- Add artifact shortcut surfaces as action shortcuts, not filesystem links

### Phase 4: Add Quick Commands

- Wire quick chips into the existing command send path
- Keep behavior identical to typed commands

### Phase 5: Add Usage Panel

- Connect only when a real logging source exists
- Otherwise ship with explicit unavailable/not-connected state

### Phase 6: Side-by-Side Validation

Compare old and new UIs against:

- Normal chat flow
- Debate room flow
- Workflow run
- Artifact-aware review command
- Unsolicited notification flow
- Reconnect/offline behavior

Only after the comparison passes should v2 become the replacement candidate.

## Risks and Safeguards

### Risk: Losing Existing Behavior

Mitigation:

- Implement in `house_v2.html`
- Parity checklist is mandatory
- Replace only after comparison

### Risk: Overdesigning the Dashboard

Mitigation:

- Keep the room grid central
- Use operations rail as augmentation, not replacement
- Avoid adding navigation layers or fake analytics clutter

### Risk: Fake Usage or Workflow State

Mitigation:

- Use only real backend signals
- Label unavailable sources honestly
- Do not animate autonomous behavior without event backing

### Risk: UI Regresses into Generic SaaS

Mitigation:

- Preserve retro command-center visual language
- Maintain HIGA HOUSE spatial identity
- Use the draft as a guide, not a template for flattening the personality

## Success Criteria

The replacement is successful when:

- It still unmistakably feels like HIGA HOUSE
- It can perform everything the old UI can perform
- It makes workflows, reviews, handoffs, and artifacts much easier to understand
- It improves observability without adding backend complexity
- It can be tested side-by-side and win on clarity without losing reliability
