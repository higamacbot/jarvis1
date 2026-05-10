import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict


def generate_stub_assets(generated_dir: str, prompts: List[Dict], title: str) -> None:
    """
    Write one .txt placeholder per shot into media/generated/ plus a manifest.
    Each file contains the ready-to-paste Sora / Runway / DALL-E prompt.
    Replace the .txt with the actual generated video or image when ready.
    """
    out = Path(generated_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest = {
        "title": title,
        "generated_at": datetime.now().isoformat(),
        "generator": "ROBOWRIGHT stub — replace each file with Sora/AI output",
        "shots": [],
    }

    for shot in prompts:
        num = shot["shot"]
        filename = f"shot_{num:02d}.txt"
        content = (
            f"SHOT {num:02d} — {title}\n"
            f"{'=' * 60}\n\n"
            f"Purpose      : {shot['purpose']}\n"
            f"Duration     : {shot['duration_sec']}s\n"
            f"Camera       : {shot['camera']}\n"
            f"Aspect Ratio : {shot['aspect_ratio']}\n\n"
            f"VIDEO PROMPT (paste into Sora or Runway):\n"
            f"{shot['video_prompt']}\n\n"
            f"FALLBACK IMAGE PROMPT (paste into DALL-E / Midjourney):\n"
            f"{shot['image_prompt']}\n\n"
            f"STATUS: stub — replace this file with the generated video/image\n"
        )
        (out / filename).write_text(content)
        manifest["shots"].append({
            "shot": num,
            "filename": filename,
            "purpose": shot["purpose"],
            "duration_sec": shot["duration_sec"],
            "status": "stub",
        })

    (out / "generation_manifest.json").write_text(json.dumps(manifest, indent=2))
