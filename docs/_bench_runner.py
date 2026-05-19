#!/usr/bin/env python3
"""
HIGA HOUSE Agent Benchmark Runner
Connects via WebSocket to ws://localhost:8000/ws/house,
sends 3 standardized prompts to every routable agent,
records timing + output, writes JSON + Markdown report.
"""

import asyncio
import json
import time
import datetime
import os
import sys
import re
import textwrap

import websockets

# ── CONFIG ────────────────────────────────────────────────────────────────────

WS_URL = "ws://localhost:8000/ws/house"

# All selectable agents — shaman/libmom/magadad included to confirm failure mode
AGENTS = [
    "jarvisbot",
    "stockbot",
    "cryptoid",
    "pinkslip",
    "doctorbot",
    "ultron",
    "robowright",
    "jamz",
    "higashop",
    "technoid",
    "teacherbot",
    "roundtable",
    "debateroom",
    "shaman",
    "libmom",
    "magadad",
]

PROMPTS = [
    "Give me a concise update on what you are best at and one thing you can help me with right now.",
    "Analyze this project at a high level and tell me the most valuable next action.",
    "What is one risk, blind spot, or weakness I should watch for in your domain?",
]

TIMEOUT_PER_PROMPT  = 120   # seconds — debateroom calls Ollama 3× sequentially
PAUSE_BETWEEN_RUNS  = 1.5   # seconds — brief cooldown between prompts

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_OUT = os.path.join(DOCS_DIR, "agent_benchmark_latest.json")
MD_OUT   = os.path.join(DOCS_DIR, "agent_benchmark_latest.md")


# ── BENCHMARK CORE ────────────────────────────────────────────────────────────

async def send_and_wait(ws, agent: str, prompt: str) -> dict:
    ts_start = datetime.datetime.now().isoformat(timespec="seconds")
    t0 = time.perf_counter()

    await ws.send(json.dumps({"bot": agent, "message": prompt}))

    try:
        while True:
            elapsed = time.perf_counter() - t0
            remain  = TIMEOUT_PER_PROMPT - elapsed
            if remain <= 0:
                raise asyncio.TimeoutError

            raw = await asyncio.wait_for(ws.recv(), timeout=min(25, remain))
            msg = json.loads(raw)

            if msg.get("type") == "answer" and msg.get("bot") == agent:
                duration = round(time.perf_counter() - t0, 2)
                return {
                    "status":    "success",
                    "response":  msg.get("text", ""),
                    "duration":  duration,
                    "ts_start":  ts_start,
                    "ts_end":    datetime.datetime.now().isoformat(timespec="seconds"),
                }
            # skip: telemetry, thinking, other-agent answers

    except asyncio.TimeoutError:
        duration = round(time.perf_counter() - t0, 2)
        return {
            "status":   "timeout",
            "response": "",
            "duration": duration,
            "ts_start": ts_start,
            "ts_end":   datetime.datetime.now().isoformat(timespec="seconds"),
        }
    except Exception as exc:
        duration = round(time.perf_counter() - t0, 2)
        return {
            "status":   "error",
            "response": str(exc),
            "duration": duration,
            "ts_start": ts_start,
            "ts_end":   datetime.datetime.now().isoformat(timespec="seconds"),
        }


async def run_benchmark() -> list[dict]:
    results = []

    async with websockets.connect(WS_URL, open_timeout=10) as ws:
        # Drain the initial telemetry burst before starting
        await asyncio.sleep(0.6)
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.3)
                _ = json.loads(raw)  # discard
        except asyncio.TimeoutError:
            pass

        for agent in AGENTS:
            print(f"\n── {agent.upper()} ──")
            for p_idx, prompt in enumerate(PROMPTS, 1):
                label = prompt[:55] + "..."
                print(f"  [{p_idx}/3] {label}", flush=True)

                result = await send_and_wait(ws, agent, prompt)
                status_icon = {"success": "✓", "timeout": "⏱", "error": "✗"}.get(result["status"], "?")
                resp_preview = result["response"][:90].replace("\n", " ")
                print(f"  {status_icon} {result['duration']}s | {resp_preview}", flush=True)

                results.append({
                    "agent":     agent,
                    "prompt_num": p_idx,
                    "prompt":    prompt,
                    **result,
                })

                if p_idx < len(PROMPTS):
                    await asyncio.sleep(PAUSE_BETWEEN_RUNS)

            await asyncio.sleep(PAUSE_BETWEEN_RUNS)

    return results


# ── ANALYSIS ──────────────────────────────────────────────────────────────────

def judge_response(status: str, response: str, agent: str) -> tuple[str, str]:
    """Return (judgment_tag, notes)."""
    if status == "timeout":
        return "timeout", "No response within timeout window."
    if status == "error":
        return "error", f"WS error: {response[:120]}"

    text = response.strip()
    wc   = len(text.split())

    # Hard failure: unknown bot
    if text.lower().startswith("unknown bot"):
        return "error", "Agent not routed — returns 'Unknown bot' error."

    # Debateroom — check all 3 personas present
    if agent == "debateroom":
        has_shaman  = "[SHAMAN]"   in text
        has_libmom  = "[LIB MOM]"  in text
        has_maga    = "[MAGA DAD]" in text
        if has_shaman and has_libmom and has_maga:
            return "strong", "All 3 personas present."
        elif any([has_shaman, has_libmom, has_maga]):
            return "weak", "Only partial personas returned."
        else:
            return "vague", "No persona tags in output."

    # Generic quality heuristics
    if wc < 15:
        return "weak", f"Very short response ({wc} words)."
    if wc > 400:
        return "strong", f"Detailed response ({wc} words)."
    if any(p in text.lower() for p in ("i cannot", "i'm unable", "i don't have access", "as an ai")):
        return "weak", "Hedge / AI-disclaimer detected."
    if any(p in text.lower() for p in ("error", "traceback", "exception", "offline")):
        return "error", "Error text in response."
    if wc < 40:
        return "vague", f"Brief response ({wc} words), may lack depth."
    return "useful", f"{wc} words."


def analyze(results: list[dict]) -> dict:
    by_agent: dict[str, list[dict]] = {}
    for r in results:
        by_agent.setdefault(r["agent"], []).append(r)

    agent_summaries = {}
    for agent, runs in by_agent.items():
        successes  = [r for r in runs if r["status"] == "success"]
        timeouts   = [r for r in runs if r["status"] == "timeout"]
        errors     = [r for r in runs if r["status"] == "error"]
        judgments  = [judge_response(r["status"], r["response"], agent) for r in runs]

        durations  = [r["duration"] for r in successes] or [0]
        avg_dur    = round(sum(durations) / len(durations), 1)
        max_dur    = round(max(durations), 1)

        for i, r in enumerate(runs):
            j_tag, j_note = judgments[i]
            r["judgment"] = j_tag
            r["notes"]    = j_note

        agent_summaries[agent] = {
            "agent":          agent,
            "success_count":  len(successes),
            "timeout_count":  len(timeouts),
            "error_count":    len(errors),
            "avg_duration":   avg_dur,
            "max_duration":   max_dur,
            "judgments":      [j[0] for j in judgments],
            "overall":        _overall_rating(judgments, len(timeouts), len(errors)),
        }

    return agent_summaries


def _overall_rating(judgments, n_timeout, n_error) -> str:
    if n_timeout == 3 or n_error == 3:
        return "FAIL"
    tags = [j[0] for j in judgments]
    score = {"strong": 2, "useful": 1, "vague": 0, "weak": -1, "error": -2, "timeout": -3, "off-topic": -1}
    total = sum(score.get(t, 0) for t in tags)
    if total >= 4:  return "EXCELLENT"
    if total >= 2:  return "GOOD"
    if total >= 0:  return "FAIR"
    return "POOR"


# ── MARKDOWN REPORT ───────────────────────────────────────────────────────────

def build_report(results: list[dict], summaries: dict, run_start: str, run_end: str) -> str:
    total_dur = sum(r["duration"] for r in results)
    n_success = sum(1 for r in results if r["status"] == "success")
    n_timeout = sum(1 for r in results if r["status"] == "timeout")
    n_error   = sum(1 for r in results if r["status"] == "error")

    # Sort agents by overall rating for tables
    rating_order = {"EXCELLENT": 0, "GOOD": 1, "FAIR": 2, "POOR": 3, "FAIL": 4}
    sorted_agents = sorted(summaries.values(), key=lambda x: (rating_order.get(x["overall"], 5), x["avg_duration"]))

    lines = []
    def w(*args): lines.append(" ".join(str(a) for a in args))

    # ── Header ────────────────────────────────────────────────────────────────
    w("# HIGA HOUSE Agent Benchmark")
    w(f"**Run date:** {run_start[:10]}  ")
    w(f"**Window:** {run_start} → {run_end}  ")
    w(f"**Total wall time:** {round(total_dur/60, 1)} min  ")
    w(f"**Method:** WebSocket client (`ws://localhost:8000/ws/house`) — no UI automation  ")
    w("")

    # ── Executive Summary ─────────────────────────────────────────────────────
    w("## Executive Summary")
    w("")
    w(f"Tested **{len(AGENTS)} agents** × **3 prompts** = **{len(results)} runs total**.")
    w(f"- Successful responses: **{n_success}/{len(results)}**")
    w(f"- Timeouts: **{n_timeout}**")
    w(f"- Errors/failures: **{n_error}**")
    w("")

    excellent = [s for s in summaries.values() if s["overall"] == "EXCELLENT"]
    good      = [s for s in summaries.values() if s["overall"] == "GOOD"]
    poor      = [s for s in summaries.values() if s["overall"] in ("POOR", "FAIL")]

    if excellent:
        w(f"Top performers: {', '.join(s['agent'] for s in excellent)}")
    if poor:
        w(f"Weakest / failures: {', '.join(s['agent'] for s in poor)}")
    w("")

    # Key observation
    routed_fails = [s for s in summaries.values() if s["overall"] == "FAIL" and s["agent"] in ("shaman","libmom","magadad")]
    if routed_fails:
        w("> **Note:** `shaman`, `libmom`, and `magadad` are not routed as standalone agents — they exist only within")
        w("> `debateroom` context. All three return `Unknown bot: X`. Included for completeness.")
        w("")

    # ── Timing Table ──────────────────────────────────────────────────────────
    w("## Agent Results Table")
    w("")
    w("| Agent | P1 | P2 | P3 | Avg (s) | Max (s) | Overall |")
    w("|---|---|---|---|---|---|---|")

    for s in sorted_agents:
        agent = s["agent"]
        runs  = [r for r in results if r["agent"] == agent]
        cells = []
        for r in runs:
            tag  = r.get("judgment", "?")
            dur  = r["duration"]
            icon = {"strong": "✦", "useful": "✓", "vague": "~", "weak": "▽",
                    "error": "✗", "timeout": "⏱", "off-topic": "?"}.get(tag, "?")
            cells.append(f"{icon} {dur}s")
        rating_icon = {"EXCELLENT": "🟢", "GOOD": "🟡", "FAIR": "🟠", "POOR": "🔴", "FAIL": "⛔"}.get(s["overall"], "")
        w(f"| `{agent}` | {' | '.join(cells)} | {s['avg_duration']} | {s['max_duration']} | {rating_icon} {s['overall']} |")

    w("")
    w("**Legend:** ✦ strong  ✓ useful  ~ vague  ▽ weak  ✗ error  ⏱ timeout")
    w("")

    # ── Best performers ───────────────────────────────────────────────────────
    w("## Best-Performing Agents")
    w("")
    top = [s for s in sorted_agents if s["overall"] in ("EXCELLENT", "GOOD")]
    if top:
        for s in top:
            agent_runs = [r for r in results if r["agent"] == s["agent"]]
            w(f"### `{s['agent']}` — {s['overall']}")
            w(f"Avg response: {s['avg_duration']}s | Judgments: {', '.join(s['judgments'])}")
            w("")
            for r in agent_runs:
                w(f"**P{r['prompt_num']}** ({r['duration']}s, {r.get('judgment','?')}): {r['notes']}")
                snippet = r['response'][:300].replace('\n', ' ')
                if snippet:
                    w(f"> {snippet}{'…' if len(r['response']) > 300 else ''}")
                w("")
    else:
        w("_No agents rated EXCELLENT or GOOD._")
        w("")

    # ── Weakest / most problematic ─────────────────────────────────────────────
    w("## Weakest / Most Problematic Agents")
    w("")
    weak = [s for s in sorted_agents if s["overall"] in ("POOR", "FAIL")]
    if weak:
        for s in weak:
            agent_runs = [r for r in results if r["agent"] == s["agent"]]
            w(f"### `{s['agent']}` — {s['overall']}")
            w(f"Success: {s['success_count']}/3 | Timeouts: {s['timeout_count']} | Errors: {s['error_count']}")
            w("")
            for r in agent_runs:
                w(f"**P{r['prompt_num']}** ({r['duration']}s, {r.get('judgment','?')}): {r['notes']}")
                if r["response"]:
                    w(f"> {r['response'][:200].replace(chr(10), ' ')}…")
                w("")
    else:
        w("_No agents rated POOR or FAIL (excluding unrouted debate participants)._")
        w("")

    # ── Failures / Timeouts ───────────────────────────────────────────────────
    w("## Failures and Timeouts")
    w("")
    failures = [r for r in results if r["status"] in ("timeout", "error")]
    if failures:
        w("| Agent | Prompt # | Status | Duration | Notes |")
        w("|---|---|---|---|---|")
        for r in failures:
            note = r.get("notes", r["response"][:80])
            w(f"| `{r['agent']}` | P{r['prompt_num']} | {r['status'].upper()} | {r['duration']}s | {note} |")
        w("")
    else:
        w("_No timeouts or connection errors._")
        w("")

    # ── Patterns ──────────────────────────────────────────────────────────────
    w("## Patterns Across Agent Roles")
    w("")

    # Speed distribution
    success_runs = [r for r in results if r["status"] == "success"]
    if success_runs:
        fast = [r for r in success_runs if r["duration"] < 15]
        mid  = [r for r in success_runs if 15 <= r["duration"] < 60]
        slow = [r for r in success_runs if r["duration"] >= 60]

        w("### Response Speed")
        w(f"- Fast (< 15s): {len(fast)} runs — {', '.join(set(r['agent'] for r in fast))}")
        w(f"- Medium (15–60s): {len(mid)} runs — {', '.join(set(r['agent'] for r in mid))}")
        w(f"- Slow (> 60s): {len(slow)} runs — {', '.join(set(r['agent'] for r in slow)) or 'none'}")
        w("")

    w("### Quality Patterns")
    tag_counts: dict[str, int] = {}
    for r in results:
        t = r.get("judgment", "?")
        tag_counts[t] = tag_counts.get(t, 0) + 1
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        w(f"- **{tag}**: {count} runs")
    w("")

    # Role observations
    w("### Role-Specific Observations")
    w("")
    observations = build_role_observations(results, summaries)
    for obs in observations:
        w(f"- {obs}")
    w("")

    # ── Per-agent full detail ──────────────────────────────────────────────────
    w("## Full Response Log")
    w("")
    w("<details>")
    w("<summary>Expand to see all raw responses</summary>")
    w("")

    for agent in AGENTS:
        agent_runs = [r for r in results if r["agent"] == agent]
        s = summaries.get(agent, {})
        w(f"### {agent.upper()} — {s.get('overall', '?')}")
        w("")
        for r in agent_runs:
            w(f"**Prompt {r['prompt_num']}** | {r['duration']}s | {r['status']} | {r.get('judgment','?')}")
            w(f"> *{r['prompt']}*")
            w("")
            if r["response"]:
                # Wrap long lines
                resp = r["response"][:1200]
                w("```")
                w(resp)
                w("```")
            else:
                w("_(no response)_")
            w("")
        w("---")
        w("")

    w("</details>")
    w("")

    # ── Recommendations ───────────────────────────────────────────────────────
    w("## Recommended Follow-up Improvements")
    w("")
    recs = build_recommendations(results, summaries)
    for i, rec in enumerate(recs, 1):
        w(f"{i}. {rec}")
    w("")

    w("---")
    w(f"*Generated by `docs/_bench_runner.py` on {run_start[:10]}. Read-only audit — no app code modified.*")

    return "\n".join(lines)


def build_role_observations(results, summaries) -> list[str]:
    obs = []
    debateroom_runs = [r for r in results if r["agent"] == "debateroom" and r["status"] == "success"]
    if debateroom_runs:
        avg = round(sum(r["duration"] for r in debateroom_runs) / len(debateroom_runs), 1)
        obs.append(f"**debateroom** is the slowest agent by design — 3 sequential Ollama calls. Avg {avg}s per prompt.")

    roundtable_runs = [r for r in results if r["agent"] == "roundtable" and r["status"] == "success"]
    if roundtable_runs:
        avg = round(sum(r["duration"] for r in roundtable_runs) / len(roundtable_runs), 1)
        obs.append(f"**roundtable** aggregates all agents into one response. Avg {avg}s; quality depends on live market data availability.")

    # Debate persona bots
    unrouted = [ag for ag in ["shaman", "libmom", "magadad"] if summaries.get(ag, {}).get("overall") == "FAIL"]
    if unrouted:
        obs.append(f"**{', '.join(unrouted)}** are sub-personas of debateroom, not standalone agents — they return 'Unknown bot' when addressed directly.")

    # LLM-heavy vs lightweight
    fast_agents = [ag for ag, s in summaries.items() if s["avg_duration"] < 10 and s["success_count"] > 0]
    if fast_agents:
        obs.append(f"Fastest agents: {', '.join(fast_agents)} — likely using local data or short prompts.")

    # Agents with any weak/vague
    vague_agents = [ag for ag, s in summaries.items() if "vague" in s["judgments"] or "weak" in s["judgments"]]
    if vague_agents:
        obs.append(f"Agents returning vague/weak responses on at least one prompt: {', '.join(vague_agents)}.")

    # Prompt 3 (risk/weakness) tends to be hardest
    p3_runs = [r for r in results if r["prompt_num"] == 3]
    p3_vague = sum(1 for r in p3_runs if r.get("judgment") in ("vague", "weak"))
    obs.append(f"Prompt 3 ('risk/blind spot') returned vague or weak responses {p3_vague}/{len(p3_runs)} times — agents tend to hedge on self-critique.")

    return obs


def build_recommendations(results, summaries) -> list[str]:
    recs = []

    timeouts = [r for r in results if r["status"] == "timeout"]
    if timeouts:
        agents = list(set(r["agent"] for r in timeouts))
        recs.append(f"Investigate timeout agents: {', '.join(agents)}. Check Ollama model load or bot-specific context-building overhead.")

    weak_runs = [r for r in results if r.get("judgment") in ("weak", "vague") and r["status"] == "success"]
    if len(weak_runs) > 4:
        recs.append("Multiple agents give vague responses — consider tightening system prompts to force concrete, domain-specific outputs.")

    # Debate routing
    recs.append("Add explicit routing for `shaman`, `libmom`, `magadad` as individual message targets (or surface a clear error message) to avoid silent 'Unknown bot' failures.")

    debateroom_runs = [r for r in results if r["agent"] == "debateroom"]
    debateroom_avg  = round(sum(r["duration"] for r in debateroom_runs) / len(debateroom_runs), 1) if debateroom_runs else 0
    if debateroom_avg > 60:
        recs.append(f"debateroom averages {debateroom_avg}s — consider parallelizing the 3 Ollama persona calls with `asyncio.gather()`.")

    recs.append("Add a `/api/chat` REST endpoint as a fallback for programmatic testing and CI use — WebSocket-only access is fragile for scripted runs.")
    recs.append("Run this benchmark weekly (or after major router changes) to catch regressions in agent response quality and latency.")

    return recs


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_start = datetime.datetime.now().isoformat(timespec="seconds")
    print(f"HIGA HOUSE Agent Benchmark — {run_start}")
    print(f"Target: {WS_URL}")
    print(f"Agents: {len(AGENTS)}  Prompts: {len(PROMPTS)}  Timeout: {TIMEOUT_PER_PROMPT}s each")
    print("=" * 60)

    try:
        results = asyncio.run(run_benchmark())
    except Exception as exc:
        print(f"\nFATAL: {exc}")
        sys.exit(1)

    run_end = datetime.datetime.now().isoformat(timespec="seconds")
    summaries = analyze(results)

    # Save JSON
    with open(JSON_OUT, "w") as f:
        json.dump({"meta": {"run_start": run_start, "run_end": run_end,
                            "agent_count": len(AGENTS), "prompt_count": len(PROMPTS)},
                   "results": results,
                   "summaries": list(summaries.values())}, f, indent=2)
    print(f"\nJSON saved → {JSON_OUT}")

    # Save Markdown
    report = build_report(results, summaries, run_start, run_end)
    with open(MD_OUT, "w") as f:
        f.write(report)
    print(f"Report saved → {MD_OUT}")

    # Terminal summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for s in sorted(summaries.values(), key=lambda x: x["avg_duration"]):
        tag = s["overall"].ljust(10)
        j   = " ".join(s["judgments"])
        print(f"  {s['agent']:14} {tag}  avg={s['avg_duration']}s  [{j}]")
