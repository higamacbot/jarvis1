#!/usr/bin/env python3
"""
Mini verification benchmark — identity bleed fix for 5 agents.
Tests pinkslip, doctorbot, robowright, jamz, technoid with 1 generic prompt each.
A "generic" prompt is one that does NOT trigger any keyword gate in router.py,
forcing the fallthrough path (line 1217) that was the bleed vector.
"""
import asyncio, json, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

AGENTS = {
    "pinkslip":  "What advice do you have for me today?",
    "doctorbot":  "Tell me something useful about the project.",
    "robowright": "What kind of content should I focus on?",
    "jamz":       "What's your take on my creative direction?",
    "technoid":   "How's everything looking right now?",
}

EXPECTED_NAMES = {
    "pinkslip":  ["pinkslip", "pink slip"],
    "doctorbot":  ["doctorbot", "doctor"],
    "robowright": ["robowright", "robo"],
    "jamz":       ["jamz"],
    "technoid":   ["technoid"],
}

JARVIS_SIGNALS = ["jarvis", "sir,", "sir.", "stark"]


async def run_one(bot_id: str, msg: str) -> dict:
    import websockets
    uri = "ws://localhost:8000/ws/house"
    t0 = time.time()
    try:
        async with websockets.connect(uri, open_timeout=5, close_timeout=5) as ws:
            await ws.send(json.dumps({"bot": bot_id, "message": msg}))
            # drain telemetry/thinking frames until we get the actual answer
            text = ""
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=90)
                data = json.loads(raw)
                if data.get("type") == "answer":
                    text = data.get("text", "").strip()
                    break
                # keep draining telemetry/thinking frames
            elapsed = round(time.time() - t0, 1)
            text_lc = text.lower()

            jarvis_bleed = any(s in text_lc for s in JARVIS_SIGNALS)
            correct_persona = any(n in text_lc for n in EXPECTED_NAMES[bot_id])
            crypto_bleed = any(t in text_lc for t in ["btc", "eth", "bitcoin", "ethereum", "crypto"])

            status = "PASS" if (correct_persona and not jarvis_bleed) else \
                     "WARN" if (not jarvis_bleed) else "FAIL"

            return {
                "bot": bot_id,
                "prompt": msg,
                "elapsed": elapsed,
                "status": status,
                "jarvis_bleed": jarvis_bleed,
                "correct_persona": correct_persona,
                "crypto_bleed": crypto_bleed,
                "preview": text[:200],
            }
    except Exception as e:
        return {
            "bot": bot_id,
            "prompt": msg,
            "elapsed": round(time.time() - t0, 1),
            "status": "ERROR",
            "error": str(e)[:120],
        }


async def main():
    results = []
    for bot_id, msg in AGENTS.items():
        print(f"  >> {bot_id} ...", end=" ", flush=True)
        r = await run_one(bot_id, msg)
        results.append(r)
        status = r["status"]
        if status == "ERROR":
            print(f"ERROR: {r.get('error')}")
        else:
            jb = "JARVIS-BLEED" if r["jarvis_bleed"] else "no-jarvis"
            cb = "CRYPTO-BLEED" if r["crypto_bleed"] else "no-crypto"
            cp = "persona-ok" if r["correct_persona"] else "persona-missing"
            print(f"{status} | {jb} | {cb} | {cp} | {r['elapsed']}s")
            print(f"     preview: {r['preview'][:120]!r}")
        print()

    print("\n=== SUMMARY ===")
    for r in results:
        line = f"  {r['bot']:12s}  {r['status']}"
        if r["status"] not in ("ERROR",):
            line += f"  jarvis={'YES' if r['jarvis_bleed'] else 'no ':3s}  crypto={'YES' if r['crypto_bleed'] else 'no ':3s}  persona={'YES' if r['correct_persona'] else 'NO ':3s}"
        print(line)

    out = os.path.join(os.path.dirname(__file__), "identity_verify_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out}")


asyncio.run(main())
