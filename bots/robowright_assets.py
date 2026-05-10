import json
import re
from pathlib import Path
from typing import List, Dict


def _slug_purpose(line: str) -> str:
    t = line.lower()
    if "hook" in t:
        return "hook"
    if "cta" in t or "call to action" in t or "outro" in t:
        return "cta"
    if "bonus" in t:
        return "bonus"
    return "main"


def _extract_script_lines(script_text: str) -> List[str]:
    lines = []
    for raw in (script_text or "").splitlines():
        line = raw.strip(" -*\t")
        if not line:
            continue
        if line.upper().startswith(("CONCEPT:", "HOOK:", "SCRIPT:", "EDIT NOTES:", "AUDIO:", "CAPTION:", "BEST POST TIME:")):
            continue
        lines.append(line)
    return lines


def build_shot_prompts(title: str, script_text: str, aspect_ratio: str = "9:16") -> List[Dict]:
    lines = _extract_script_lines(script_text)

    if not lines:
        lines = [
            f"Hook scene for {title}",
            f"Main scene for {title}",
            f"Outro / CTA scene for {title}",
        ]

    shots = []
    for idx, line in enumerate(lines[:6], start=1):
        purpose = _slug_purpose(line)
        duration = 3 if idx == 1 else 4 if purpose == "main" else 2
        visual = line[:220]
        camera = "fast push-in" if idx == 1 else "handheld medium shot" if purpose == "main" else "slow pull-back"
        style = "vertical cinematic social video, high contrast, polished lighting, creator-friendly edit framing"

        video_prompt = (
            f"Create a {aspect_ratio} cinematic social video shot. "
            f"Scene: {visual}. "
            f"Purpose: {purpose}. "
            f"Camera: {camera}. "
            f"Style: {style}. "
            f"Keep the composition clear for text overlays and fast short-form editing."
        )

        image_prompt = (
            f"{aspect_ratio} cinematic frame of: {visual}. "
            f"{style}. Designed for a short-form social video storyboard."
        )

        shots.append({
            "shot": idx,
            "duration_sec": duration,
            "purpose": purpose,
            "visual": visual,
            "camera": camera,
            "style": style,
            "aspect_ratio": aspect_ratio,
            "video_prompt": video_prompt,
            "image_prompt": image_prompt,
        })

    return shots


def write_sora_prompts_markdown(title: str, prompts: List[Dict], output_path: str) -> None:
    lines = [f"# Sora Prompts — {title}", ""]
    for shot in prompts:
        lines.extend([
            f"## Shot {shot['shot']}",
            f"- Purpose: {shot['purpose']}",
            f"- Duration: {shot['duration_sec']}s",
            f"- Camera: {shot['camera']}",
            f"- Style: {shot['style']}",
            f"- Aspect Ratio: {shot['aspect_ratio']}",
            "",
            "Video Prompt:",
            shot["video_prompt"],
            "",
            "Fallback Image Prompt:",
            shot["image_prompt"],
            "",
        ])
    Path(output_path).write_text("\n".join(lines))


def write_prompts_json(prompts: List[Dict], output_path: str) -> None:
    Path(output_path).write_text(json.dumps(prompts, indent=2))
