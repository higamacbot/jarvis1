import os
import subprocess
import textwrap
from typing import List, Dict

from PIL import Image, ImageDraw, ImageFont

FFMPEG = "/opt/homebrew/bin/ffmpeg"
_FONT = "/System/Library/Fonts/Helvetica.ttc"

_COLORS = {
    "hook":  "#E63946",
    "main":  "#1D3557",
    "cta":   "#2A9D8F",
    "bonus": "#E9C46A",
}
_DEFAULT_COLOR = "#457B9D"


def _hex_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _make_png(shot: Dict, png_path: str) -> None:
    color = _hex_rgb(_COLORS.get(shot.get("purpose", "").lower(), _DEFAULT_COLOR))
    img = Image.new("RGB", (1080, 1920), color)
    draw = ImageDraw.Draw(img)

    try:
        f_xl = ImageFont.truetype(_FONT, 120)
        f_lg = ImageFont.truetype(_FONT, 72)
        f_sm = ImageFont.truetype(_FONT, 48)
    except Exception:
        f_xl = f_lg = f_sm = ImageFont.load_default()

    draw.text((540, 500), f"SHOT {shot['shot']:02d}", font=f_xl, fill="white", anchor="mm")
    draw.text((540, 680), shot.get("purpose", "").upper(), font=f_lg, fill="white", anchor="mm")
    draw.line([(240, 780), (840, 780)], fill="white", width=3)

    y = 870
    for line in textwrap.wrap(shot.get("visual", "")[:160], width=32)[:5]:
        draw.text((540, y), line, font=f_sm, fill=(220, 220, 220), anchor="mm")
        y += 68

    img.save(png_path)


def generate_placeholder_clips(prompts: List[Dict], generated_dir: str) -> List[str]:
    """
    Render one .mp4 per shot into generated_dir.
    Tries real image generation first (via bots.image_provider); falls back to
    the Pillow title-card if generation is unavailable or fails.
    Returns absolute paths to successfully created .mp4 files in shot order.
    """
    os.makedirs(generated_dir, exist_ok=True)

    try:
        from bots.image_provider import generate_shot_image
    except Exception:
        generate_shot_image = None

    clip_paths = []

    for shot in prompts:
        num = shot["shot"]
        mp4_path = os.path.join(generated_dir, f"shot_{num:02d}.mp4")
        duration = max(1, shot.get("duration_sec", 3))

        # Attempt real image generation
        png_path = None
        if generate_shot_image:
            try:
                png_path = generate_shot_image(
                    shot.get("image_prompt", shot.get("visual", f"shot {num}")),
                    num,
                    generated_dir,
                )
            except Exception as e:
                print(f">> ROBOWRIGHT: image_provider error for shot {num}: {e}")

        # Fall back to Pillow title card
        if not png_path:
            card_path = os.path.join(generated_dir, f"shot_{num:02d}_card.png")
            try:
                _make_png(shot, card_path)
                png_path = card_path
            except Exception as e:
                print(f">> ROBOWRIGHT: card render failed for shot {num}: {e}")
                continue

        r = subprocess.run(
            [FFMPEG, "-y", "-loop", "1", "-i", png_path,
             "-t", str(duration), "-r", "30",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", mp4_path],
            capture_output=True, timeout=60,
        )
        if r.returncode == 0:
            clip_paths.append(mp4_path)
        else:
            print(f">> ROBOWRIGHT: ffmpeg failed for shot {num}: {r.stderr.decode()[:200]}")

    return clip_paths
