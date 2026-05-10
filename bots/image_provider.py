import os
import time
from typing import Optional


def generate_shot_image(image_prompt: str, shot_num: int, out_dir: str) -> Optional[str]:
    """
    Try to generate a real image for a shot.
    Provider order: DALL-E 3 (if OPENAI_API_KEY set) → None.
    Returns absolute path to a valid PNG on success, None on any failure.
    Caller is responsible for falling back to the Pillow placeholder card.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        return _dalle3(image_prompt, shot_num, out_dir, openai_key)
    return None


def _dalle3(prompt: str, shot_num: int, out_dir: str, api_key: str) -> Optional[str]:
    try:
        import httpx
        r = httpx.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "dall-e-3", "prompt": prompt, "n": 1,
                  "size": "1024x1792", "response_format": "url"},
            timeout=60.0,
        )
        if r.status_code != 200:
            print(f">> ROBOWRIGHT IMAGE: DALL-E 3 {r.status_code}: {r.text[:200]}")
            return None

        url = r.json()["data"][0]["url"]
        img_r = httpx.get(url, timeout=30.0)
        if img_r.status_code != 200:
            print(f">> ROBOWRIGHT IMAGE: download failed {img_r.status_code}")
            return None

        out_path = os.path.join(out_dir, f"shot_{shot_num:02d}_generated.png")
        with open(out_path, "wb") as f:
            f.write(img_r.content)

        # Sanity-check the file is a valid image before returning it
        from PIL import Image
        with Image.open(out_path) as img:
            img.verify()

        print(f">> ROBOWRIGHT IMAGE: shot_{shot_num:02d} generated via DALL-E 3")
        time.sleep(0.5)  # stay under rate limit between shots
        return out_path

    except Exception as e:
        print(f">> ROBOWRIGHT IMAGE: DALL-E 3 failed for shot {shot_num}: {e}")
        return None
