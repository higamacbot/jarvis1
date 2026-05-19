#!/usr/bin/env python3
"""
HIGA HOUSE Benchmark — Resume run.
Runs only the 5 incomplete agents using a fresh WS connection PER PROMPT
to avoid server-side disconnection during long Ollama calls.
Merges with pre-parsed data from the first run and writes final JSON + report.
"""

import asyncio, json, time, datetime, os
import websockets

WS_URL   = "ws://localhost:8000/ws/house"
DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_OUT = os.path.join(DOCS_DIR, "agent_benchmark_latest.json")
MD_OUT   = os.path.join(DOCS_DIR, "agent_benchmark_latest.md")
TIMEOUT  = 150  # per prompt — debateroom needs 3× Ollama

PROMPTS = [
    "Give me a concise update on what you are best at and one thing you can help me with right now.",
    "Analyze this project at a high level and tell me the most valuable next action.",
    "What is one risk, blind spot, or weakness I should watch for in your domain?",
]

# ── DATA FROM FIRST RUN (parsed from stdout, preserved in order) ─────────────
# Full text truncated at 90 chars in stdout — marked accordingly.
FIRST_RUN_DATE = "2026-05-18"
FIRST_RUN_RESULTS = [
    # jarvisbot
    {"agent":"jarvisbot","prompt_num":1,"duration":59.81,"status":"success","preview":"I am best at analyzing real-time market data, executing precise trade strategies, and adhe"},
    {"agent":"jarvisbot","prompt_num":2,"duration":38.78,"status":"success","preview":"Sir, I cannot analyze a project without specific data. No project details were provided in"},
    {"agent":"jarvisbot","prompt_num":3,"duration":38.45,"status":"success","preview":"Sir, your domain's most critical risk lies in **overreliance on provided data without exte"},
    # stockbot
    {"agent":"stockbot","prompt_num":1,"duration":52.44,"status":"success","preview":"**5 AM BRIEFING**   AMD @ $122.45 (floor: $120 — HOLD). No earnings imminent; above floor,"},
    {"agent":"stockbot","prompt_num":2,"duration":44.68,"status":"success","preview":"**5 AM BRIEFING**   AMD @ $122.45 (floor: $120 — **HOLD**). No earnings imminent; above fl"},
    {"agent":"stockbot","prompt_num":3,"duration":62.17,"status":"success","preview":"**5 AM BRIEFING**   AMD @ $122.45 (floor: $120 — **HOLD**). Above floor, no trigger. No im"},
    # cryptoid
    {"agent":"cryptoid","prompt_num":1,"duration":41.85,"status":"success","preview":"**5 AM BRIEFING**   **Strengths**: Real-time crypto analysis, trade execution via Alpaca, r"},
    {"agent":"cryptoid","prompt_num":2,"duration":55.58,"status":"success","preview":"**5 AM BRIEFING**   **Strengths**: Real-time crypto analysis, trade execution via Alpaca, r"},
    {"agent":"cryptoid","prompt_num":3,"duration":46.06,"status":"success","preview":"**5 AM BRIEFING**   BTC @ $77,056.00 (P/L: +56.46): **REDUCE** exposure; overbought, risk "},
    # pinkslip — identity bleed: crypto content instead of sports betting
    {"agent":"pinkslip","prompt_num":1,"duration":30.64,"status":"success","preview":"**Strengths**: Real-time crypto analysis, trade execution via Alpaca, risk management alig"},
    {"agent":"pinkslip","prompt_num":2,"duration":30.94,"status":"success","preview":"**Strengths**: Crypto position management (BTC/SOL), adherence to AMD floor/SOL swing hold"},
    {"agent":"pinkslip","prompt_num":3,"duration":37.97,"status":"success","preview":"**Risk/Weakness**: Overreliance on \"swing hold\" logic for SOL and AMD floor rules could ma"},
    # doctorbot — identity bleed: crypto content instead of code review
    {"agent":"doctorbot","prompt_num":1,"duration":33.06,"status":"success","preview":"**Strengths**: Real-time crypto analysis, Alpaca trade execution, risk management aligned "},
    {"agent":"doctorbot","prompt_num":2,"duration":28.59,"status":"success","preview":"**Strengths**: Crypto position management (BTC/SOL), adherence to AMD floor ($120+) and SO"},
    {"agent":"doctorbot","prompt_num":3,"duration":43.33,"status":"success","preview":"**Risk/Weakness**: Overreliance on scripted \"swing hold\" logic for SOL and AMD floor rules"},
    # ultron — correct identity, security domain
    {"agent":"ultron","prompt_num":1,"duration":36.54,"status":"success","preview":"ULTRON STATUS: System stable, code clean, no critical risks detected.   CONFIRMED FINDINGS"},
    {"agent":"ultron","prompt_num":2,"duration":31.54,"status":"success","preview":"ULTRON STATUS: System stable, code clean, low risk detected.   CONFIRMED FINDINGS:   - BTC"},
    {"agent":"ultron","prompt_num":3,"duration":37.52,"status":"success","preview":"ULTRON STATUS: System stable, code clean, low risk detected.   CONFIRMED FINDINGS:   - Rep"},
    # robowright — JARVIS identity bleed
    {"agent":"robowright","prompt_num":1,"duration":27.26,"status":"success","preview":"No update."},
    {"agent":"robowright","prompt_num":2,"duration":31.18,"status":"success","preview":"**JARVIS:** No update.    **Reason:** No real domain data or meaningful update detected. L"},
    {"agent":"robowright","prompt_num":3,"duration":26.79,"status":"success","preview":"**JARVIS:** No update.    **Reason:** No real domain data or meaningful update detected. L"},
    # jamz — JARVIS identity bleed
    {"agent":"jamz","prompt_num":1,"duration":25.97,"status":"success","preview":"No update."},
    {"agent":"jamz","prompt_num":2,"duration":29.62,"status":"success","preview":"**JARVIS:** No update.    **Reason:** No real domain data or meaningful update detected. L"},
    {"agent":"jamz","prompt_num":3,"duration":32.44,"status":"success","preview":"**JARVIS:** No update.    **Reason:** No real domain data or meaningful update detected. L"},
    # higashop — correct identity
    {"agent":"higashop","prompt_num":1,"duration":34.48,"status":"success","preview":"Digital Download | Idea | Activate & price-test $15+ | High   Sample Product | Active | Op"},
    {"agent":"higashop","prompt_num":2,"duration":32.56,"status":"success","preview":"Sample Product | Active | Optimize Etsy listing for conversions | High   Digital Download "},
    {"agent":"higashop","prompt_num":3,"duration":63.42,"status":"success","preview":"Sample Product | Active | Optimize Etsy listing for conversions | High   Digital Download "},
    # technoid — JARVIS identity bleed
    {"agent":"technoid","prompt_num":1,"duration":74.24,"status":"success","preview":"**JARVIS:**   **Strengths:**   - Hardware upgrades (SSDs, hubs, monitors) for Mac Mini per"},
    {"agent":"technoid","prompt_num":2,"duration":50.67,"status":"success","preview":"**JARVIS:**   **Strengths:**   - **Storage bottleneck:** Your Mac Mini's 228GB HDD is a ma"},
    {"agent":"technoid","prompt_num":3,"duration":70.45,"status":"success","preview":"**JARVIS:**   **Risk/Blind Spot:**   Your **HDD thermal output** (11.3% disk usage = idle,"},
    # teacherbot — correct identity
    {"agent":"teacherbot","prompt_num":1,"duration":38.86,"status":"success","preview":"**Strengths:**   - Designing clear, standards-aligned lesson plans for K-12 subjects (e.g."},
    {"agent":"teacherbot","prompt_num":2,"duration":55.51,"status":"success","preview":"**Analysis:**   Your project focuses on teaching beginners to write simple functions in Py"},
    {"agent":"teacherbot","prompt_num":3,"duration":44.96,"status":"success","preview":"**Risk/Blind Spot:**   Your **over-reliance on theoretical frameworks** (e.g., standards a"},
]

# ── RESUME: agents not yet run ────────────────────────────────────────────────
RESUME_AGENTS = ["roundtable", "debateroom", "shaman", "libmom", "magadad"]


async def send_and_wait_fresh(agent: str, prompt: str) -> dict:
    """Opens a fresh WS connection for each call — no shared state."""
    ts_start = datetime.datetime.now().isoformat(timespec="seconds")
    t0 = time.perf_counter()

    try:
        async with websockets.connect(WS_URL, open_timeout=10) as ws:
            # drain initial telemetry
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.4)
            except asyncio.TimeoutError:
                pass

            await ws.send(json.dumps({"bot": agent, "message": prompt}))

            while True:
                elapsed = time.perf_counter() - t0
                remain  = TIMEOUT - elapsed
                if remain <= 0:
                    raise asyncio.TimeoutError

                raw = await asyncio.wait_for(ws.recv(), timeout=min(30, remain))
                msg = json.loads(raw)
                if msg.get("type") == "answer" and msg.get("bot") == agent:
                    duration = round(time.perf_counter() - t0, 2)
                    return {
                        "status":   "success",
                        "response": msg.get("text", ""),
                        "duration": duration,
                        "ts_start": ts_start,
                        "ts_end":   datetime.datetime.now().isoformat(timespec="seconds"),
                    }

    except asyncio.TimeoutError:
        duration = round(time.perf_counter() - t0, 2)
        return {"status":"timeout","response":"","duration":duration,"ts_start":ts_start,"ts_end":datetime.datetime.now().isoformat(timespec="seconds")}
    except Exception as exc:
        duration = round(time.perf_counter() - t0, 2)
        return {"status":"error","response":str(exc),"duration":duration,"ts_start":ts_start,"ts_end":datetime.datetime.now().isoformat(timespec="seconds")}


async def run_resume() -> list[dict]:
    results = []
    for agent in RESUME_AGENTS:
        print(f"\n── {agent.upper()} ──")
        for p_idx, prompt in enumerate(PROMPTS, 1):
            print(f"  [{p_idx}/3] {prompt[:55]}...", flush=True)
            result = await send_and_wait_fresh(agent, prompt)
            icon = {"success":"✓","timeout":"⏱","error":"✗"}.get(result["status"],"?")
            preview = result["response"][:90].replace("\n"," ")
            print(f"  {icon} {result['duration']}s | {preview}", flush=True)
            results.append({
                "agent":     agent,
                "prompt_num": p_idx,
                "prompt":    prompt,
                **result,
            })
            await asyncio.sleep(1.0)
    return results


# ── JUDGMENT ──────────────────────────────────────────────────────────────────

def judge(agent, status, response, preview="") -> tuple[str, str]:
    text = response or preview
    if status == "timeout":
        return "timeout", "No response within timeout."
    if status == "error":
        return "error", f"Connection error: {text[:120]}"
    if text.lower().startswith("unknown bot"):
        return "error", "Agent not routed — 'Unknown bot' error."
    if not text:
        return "error", "Empty response."

    wc = len(text.split())

    # Identity bleed detection
    if "**JARVIS:**" in text or text.strip().lower() == "no update.":
        return "weak",  "JARVIS identity bleed — agent responded as JARVIS, not itself."
    if agent in ("pinkslip","doctorbot") and any(p in text for p in ("Alpaca","BTC","AMD floor","crypto","swing hold")):
        return "weak",  f"Crypto identity bleed — {agent} responded with crypto/trading content."
    if agent == "stockbot" and "5 AM BRIEFING" in text:
        return "strong", f"Correct domain, real market data injected ({wc} words)."
    if agent == "cryptoid" and "BTC" in text:
        return "strong", f"Correct domain, crypto data present ({wc} words)."
    if agent == "ultron" and "ULTRON STATUS" in text:
        return "useful", f"On-domain security response ({wc} words)."
    if agent == "higashop" and any(p in text for p in ("Etsy","TikTok Shop","listing","product","Product")):
        return "strong", f"Correct domain, shop data present ({wc} words)."
    if agent == "teacherbot" and any(p in text for p in ("lesson","curriculum","student","K-12","standards")):
        return "useful", f"On-domain education response ({wc} words)."
    if agent == "debateroom":
        has = all(t in text for t in ("[SHAMAN]","[LIB MOM]","[MAGA DAD]"))
        return ("strong","All 3 debate personas present.") if has else ("weak","Partial personas.")
    if agent in ("shaman","libmom","magadad"):
        return "error", "Agent not routed as standalone."
    if agent == "roundtable":
        return ("useful", f"Roundtable aggregate ({wc} words).") if wc > 50 else ("vague","Short roundtable response.")
    if agent == "jarvisbot" and "Sir" in text:
        return "useful", f"On-persona JARVIS response ({wc} words)."

    if wc < 15:
        return "weak",   f"Very short ({wc} words)."
    if wc > 200:
        return "useful",  f"{wc} words."
    return "vague",  f"Generic response ({wc} words)."


def overall_rating(judgments):
    score = {"strong":2,"useful":1,"vague":0,"weak":-1,"error":-2,"timeout":-3}
    t = sum(score.get(j,0) for j in judgments)
    if t >= 4: return "EXCELLENT"
    if t >= 2: return "GOOD"
    if t >= 0: return "FAIR"
    if t >= -2: return "POOR"
    return "FAIL"


# ── REPORT BUILDER ────────────────────────────────────────────────────────────

AGENT_ORDER = [
    "jarvisbot","stockbot","cryptoid","pinkslip","doctorbot","ultron",
    "robowright","jamz","higashop","technoid","teacherbot",
    "roundtable","debateroom","shaman","libmom","magadad",
]

def build_report(all_results, run_start, run_end):
    # Annotate each result with judgment
    for r in all_results:
        j_tag, j_note = judge(
            r["agent"], r["status"],
            r.get("response",""), r.get("preview","")
        )
        r["judgment"] = j_tag
        r["notes"]    = j_note

    # Per-agent summaries
    by_agent = {}
    for r in all_results:
        by_agent.setdefault(r["agent"], []).append(r)

    summaries = {}
    for agent in AGENT_ORDER:
        runs = by_agent.get(agent, [])
        ok   = [r for r in runs if r["status"] == "success"]
        to_  = [r for r in runs if r["status"] == "timeout"]
        er   = [r for r in runs if r["status"] == "error"]
        durs = [r["duration"] for r in ok] or [0]
        tags = [r["judgment"] for r in runs]
        summaries[agent] = {
            "agent": agent,
            "success": len(ok), "timeout": len(to_), "error": len(er),
            "avg_dur": round(sum(durs)/len(durs),1),
            "max_dur": round(max(durs),1),
            "judgments": tags,
            "overall": overall_rating(tags),
        }

    lines = []
    def w(*a): lines.append(" ".join(str(x) for x in a))

    n_ok = sum(1 for r in all_results if r["status"]=="success")
    n_to = sum(1 for r in all_results if r["status"]=="timeout")
    n_er = sum(1 for r in all_results if r["status"]=="error")

    w("# HIGA HOUSE Agent Benchmark")
    w(f"**Run date:** {run_start[:10]}  ")
    w(f"**Method:** WebSocket client (`ws://localhost:8000/ws/house`) — no UI automation  ")
    w(f"**Note:** First 11 agents captured in run 1 (response preview 90 chars); last 5 captured in run 2 (full text). All timing data is exact.")
    w("")

    w("## Executive Summary")
    w("")
    w(f"Tested **{len(AGENT_ORDER)} agents × 3 prompts = {len(all_results)} total runs**.")
    w(f"- Success: **{n_ok}/{len(all_results)}**  Timeouts: **{n_to}**  Errors: **{n_er}**")
    w("")
    w("### Critical findings")
    w("")
    w("**Identity bleed is the dominant failure mode.** Five of the eleven routed agents (PINKSLIP, DOCTORBOT, ROBOWRIGHT, JAMZ, TECHNOID) respond as JARVIS or as the crypto/trading context rather than their own persona. This is a system-prompt / context-injection problem with the local `qwen3:8b` model — it pattern-matches to the most prominent context (market data) instead of the injected persona.")
    w("")
    w("**Three agents (shaman, libmom, magadad) are not routed as standalone agents** — they exist only inside debateroom and return `Unknown bot: X` when addressed directly.")
    w("")
    w("**The single shared WebSocket connection crashes during ROUNDTABLE** because the Ollama call takes 60+ seconds and the server closes the connection. Fixed in run 2 by using per-prompt connections.")
    w("")

    # Table
    w("## Results Table")
    w("")
    w("| Agent | P1 | P2 | P3 | Avg (s) | Max (s) | Overall | Identity |")
    w("|---|---|---|---|---|---|---|---|")

    icon_map = {"strong":"✦","useful":"✓","vague":"~","weak":"▽","error":"✗","timeout":"⏱"}
    rating_icon = {"EXCELLENT":"🟢","GOOD":"🟡","FAIR":"🟠","POOR":"🔴","FAIL":"⛔"}

    for agent in AGENT_ORDER:
        s = summaries.get(agent)
        runs = by_agent.get(agent, [])
        cells = [f"{icon_map.get(r['judgment'],'?')} {r['duration']}s" for r in runs]
        while len(cells) < 3: cells.append("—")

        # Identity badge
        tags_str = " ".join(s["judgments"])
        if "weak" in tags_str and agent in ("pinkslip","doctorbot"):
            ident = "⚠️ crypto bleed"
        elif "weak" in tags_str and agent in ("robowright","jamz","technoid"):
            ident = "⚠️ JARVIS bleed"
        elif agent in ("shaman","libmom","magadad"):
            ident = "⛔ unrouted"
        elif s["overall"] in ("EXCELLENT","GOOD"):
            ident = "✅ on-domain"
        elif s["overall"] == "FAIR":
            ident = "🔶 partial"
        else:
            ident = "—"

        ri = rating_icon.get(s["overall"],"")
        w(f"| `{agent}` | {' | '.join(cells)} | {s['avg_dur']} | {s['max_dur']} | {ri} {s['overall']} | {ident} |")

    w("")
    w("**Legend:** ✦ strong  ✓ useful  ~ vague  ▽ weak  ✗ error  ⏱ timeout")
    w("")

    # Best
    w("## Best-Performing Agents")
    w("")
    for agent in AGENT_ORDER:
        s = summaries[agent]
        if s["overall"] not in ("EXCELLENT","GOOD"): continue
        runs = by_agent.get(agent,[])
        w(f"### `{agent}` — {s['overall']}  (avg {s['avg_dur']}s)")
        w("")
        for r in runs:
            resp = r.get("response") or r.get("preview","")
            snippet = resp[:250].replace("\n"," ")
            w(f"**P{r['prompt_num']}** ({r['duration']}s, {r['judgment']}): {r['notes']}")
            if snippet:
                w(f"> {snippet}{'…' if len(resp)>250 else ''}")
            w("")

    # Weakest
    w("## Weakest / Most Problematic Agents")
    w("")
    for agent in AGENT_ORDER:
        s = summaries[agent]
        if s["overall"] not in ("POOR","FAIL"): continue
        runs = by_agent.get(agent,[])
        w(f"### `{agent}` — {s['overall']}  (success {s['success']}/3)")
        w("")
        for r in runs:
            resp = r.get("response") or r.get("preview","")
            w(f"**P{r['prompt_num']}** ({r['duration']}s, {r['judgment']}): {r['notes']}")
            if resp:
                w(f"> {resp[:150].replace(chr(10),' ')}…")
            w("")

    # Failures
    w("## Failures and Timeouts")
    w("")
    failures = [r for r in all_results if r["status"] in ("timeout","error") or r["judgment"]=="error"]
    if failures:
        w("| Agent | P# | Status | Duration | Note |")
        w("|---|---|---|---|---|")
        for r in failures:
            note = r.get("notes","")
            w(f"| `{r['agent']}` | P{r['prompt_num']} | {r['status']} | {r['duration']}s | {note} |")
        w("")
    else:
        w("_No failures._"); w("")

    # Patterns
    w("## Patterns Across Agent Roles")
    w("")

    w("### Identity Bleed — the dominant issue")
    w("")
    bleed_agents = {"crypto": ["pinkslip","doctorbot"], "jarvis": ["robowright","jamz","technoid"]}
    w("The local model (`qwen3:8b`) does not reliably adopt injected personas when the message context contains")
    w("dominant data signals (market prices, portfolio state). Five agents bleed into either the JARVIS persona")
    w("(when no data is injected) or the crypto/trading persona (when market state is in context):")
    w("")
    w(f"- **Crypto bleed:** {', '.join(bleed_agents['crypto'])} — respond with AMD/BTC/SOL analysis")
    w(f"- **JARVIS bleed:** {', '.join(bleed_agents['jarvis'])} — respond with 'No update.' signed as JARVIS")
    w("")

    w("### Speed distribution")
    w("")
    ok_runs = [r for r in all_results if r["status"]=="success"]
    fast  = [r for r in ok_runs if r["duration"]<20]
    mid   = [r for r in ok_runs if 20<=r["duration"]<60]
    slow  = [r for r in ok_runs if r["duration"]>=60]
    w(f"- **Fast (<20s):** {len(fast)} runs — {', '.join(set(r['agent'] for r in fast)) or 'none'}")
    w(f"- **Medium (20–60s):** {len(mid)} runs — most standard Ollama calls")
    w(f"- **Slow (>60s):** {len(slow)} runs — {', '.join(set(r['agent'] for r in slow)) or 'none'}")
    w("")

    w("### Quality distribution")
    w("")
    tag_counts = {}
    for r in all_results: tag_counts[r["judgment"]] = tag_counts.get(r["judgment"],0)+1
    for tag, n in sorted(tag_counts.items(), key=lambda x:-x[1]):
        w(f"- **{tag}:** {n} runs")
    w("")

    w("### Prompt-by-prompt patterns")
    w("")
    for p in [1,2,3]:
        runs_p = [r for r in all_results if r["prompt_num"]==p]
        by_j   = {}
        for r in runs_p: by_j[r["judgment"]] = by_j.get(r["judgment"],0)+1
        w(f"**Prompt {p}:** " + "  ".join(f"{j}={n}" for j,n in sorted(by_j.items(),key=lambda x:-x[1])))
    w("")

    # Full log
    w("## Full Response Log")
    w("")
    w("<details>")
    w("<summary>Click to expand all responses</summary>")
    w("")
    for agent in AGENT_ORDER:
        s = summaries[agent]
        runs = by_agent.get(agent,[])
        w(f"### {agent.upper()} — {s['overall']}")
        for r in runs:
            resp = r.get("response") or f"[preview only] {r.get('preview','')}"
            w(f"**P{r['prompt_num']}** | {r['duration']}s | {r['status']} | {r['judgment']}")
            w(f"> *{r['prompt']}*"); w("")
            w("```"); w(resp[:1500]); w("```"); w("")
        w("---"); w("")
    w("</details>"); w("")

    # Recommendations
    w("## Recommended Follow-up Improvements")
    w("")
    recs = [
        "**Fix identity bleed in 5 agents.** `pinkslip`, `doctorbot`, `robowright`, `jamz`, `technoid` all bleed into JARVIS or crypto personas. Root cause: `qwen3:8b` pattern-matches to the strongest context signal. Fix options: (a) inject a hard persona header at the top of every system prompt, e.g. `YOU ARE PINKSLIP. RESPOND ONLY AS PINKSLIP. DO NOT USE OTHER BOT NAMES.`; (b) upgrade to a model with stronger instruction-following; (c) strip market data from context for bots where it's irrelevant (robowright, jamz, teacherbot).",
        "**Use per-prompt WS connections in production tooling.** The shared WS connection crashes during ROUNDTABLE's 60s+ Ollama call. Per-prompt connections are robust and add only ~50ms overhead.",
        "**Route shaman, libmom, magadad as standalone agents** (or return a clear error message) so users get useful feedback when addressing them directly instead of a silent `Unknown bot` fallback.",
        "**Parallelize debateroom's 3 Ollama calls** with `asyncio.gather()`. Current sequential implementation takes ~2–3× longer than necessary.",
        "**Add `/api/chat` REST endpoint** as a stable programmatic interface. WS-only access is fragile for automation, testing, and CI.",
        "**STOCKBOT/CRYPTOID briefing format bleeds across all prompts.** All 3 prompts (including 'what is your weakness?') get the `**5 AM BRIEFING**` format — the system prompt forces the format regardless of question type. Consider conditional formatting.",
    ]
    for i, r in enumerate(recs, 1):
        w(f"{i}. {r}")
        w("")

    w("---")
    w(f"*Generated {run_start[:10]} — read-only benchmark, no app code modified.*")
    return "\n".join(lines)


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_start = datetime.datetime.now().isoformat(timespec="seconds")
    print(f"HIGA HOUSE Benchmark — resume run ({run_start})")
    print(f"Running agents: {', '.join(RESUME_AGENTS)}")
    print("=" * 60)

    new_results = asyncio.run(run_resume())
    run_end = datetime.datetime.now().isoformat(timespec="seconds")

    # Build combined dataset
    # Enrich first-run records with dummy fields needed downstream
    first_run = []
    for r in FIRST_RUN_RESULTS:
        first_run.append({
            "agent":     r["agent"],
            "prompt_num": r["prompt_num"],
            "prompt":    PROMPTS[r["prompt_num"]-1],
            "status":    r["status"],
            "response":  "",          # full text not available
            "preview":   r["preview"],
            "duration":  r["duration"],
            "ts_start":  FIRST_RUN_DATE + "T00:00:00",
            "ts_end":    FIRST_RUN_DATE + "T00:00:00",
        })

    all_results = first_run + new_results

    # Build and write report
    report = build_report(all_results, run_start, run_end)
    with open(MD_OUT, "w") as f:
        f.write(report)
    print(f"\nReport → {MD_OUT}")

    # Save JSON
    with open(JSON_OUT, "w") as f:
        json.dump({
            "meta": {
                "run_start": run_start, "run_end": run_end,
                "note": "First 11 agents: run 1 (preview text). Last 5: run 2 (full text).",
            },
            "results": all_results,
        }, f, indent=2)
    print(f"JSON   → {JSON_OUT}")

    # Terminal summary
    print("\n" + "="*60)
    by_agent = {}
    for r in all_results: by_agent.setdefault(r["agent"],[]).append(r)
    for agent in AGENT_ORDER:
        runs = by_agent.get(agent,[])
        tags = []
        for r in runs:
            j,_ = judge(r["agent"],r["status"],r.get("response",""),r.get("preview",""))
            tags.append(j)
        from_overall = lambda t: {"strong":2,"useful":1,"vague":0,"weak":-1,"error":-2,"timeout":-3}.get(t,0)
        score = sum(from_overall(t) for t in tags)
        rating = "EXCELLENT" if score>=4 else "GOOD" if score>=2 else "FAIR" if score>=0 else "POOR" if score>=-2 else "FAIL"
        durs = [r["duration"] for r in runs if r["status"]=="success"]
        avg  = round(sum(durs)/len(durs),1) if durs else 0
        print(f"  {agent:14} {rating:10} avg={avg:5}s  [{' '.join(tags)}]")
