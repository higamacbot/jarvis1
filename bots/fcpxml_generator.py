import os
import uuid
from typing import List, Dict
from urllib.parse import quote
from xml.sax.saxutils import escape


def _file_url(path: str) -> str:
    return "file://" + quote(os.path.abspath(path), safe="/:")


def generate_fcpxml(title: str, prompts: List[Dict], clip_paths: List[str], project_dir: str,
                    audio_path: str = None, audio_duration: float = 0.0) -> str:
    """
    Write project.fcpxml into project_dir sequencing clip_paths in timeline order.
    prompts and clip_paths are zipped (stops at the shorter list).
    If audio_path and audio_duration are provided, the audio is placed as a connected
    clip at lane=-1 under the first spine clip (background music bed).
    Returns absolute path to the written .fcpxml file.
    """
    resources = ['    <format id="r1" name="FFVideoFormat1080p30" frameDuration="100/3000s" width="1920" height="1080" colorSpace="1-1-1 (Rec. 709)"/>']

    pairs = list(zip(prompts, clip_paths))
    total_video_dur = sum(max(1, s.get("duration_sec", 3)) for s, _ in pairs)

    # Audio asset — added to resources if audio is available
    audio_asset_id = None
    if audio_path and audio_duration > 0 and os.path.isfile(audio_path):
        audio_asset_id = f"r{len(pairs) + 2}"
        audio_uid = str(uuid.uuid4()).upper()
        audio_name = escape(os.path.splitext(os.path.basename(audio_path))[0])
        resources.append(
            f'    <asset id="{audio_asset_id}" name="{audio_name}" uid="{audio_uid}"'
            f' src="{_file_url(audio_path)}" start="0s" duration="{audio_duration:.3f}s"'
            f' hasVideo="0" hasAudio="1"/>'
        )

    clips = []
    offset = 0

    for i, (shot, clip_path) in enumerate(pairs):
        asset_id = f"r{i + 2}"
        dur = max(1, shot.get("duration_sec", 3))
        name = escape(f"shot_{shot['shot']:02d}")
        uid = str(uuid.uuid4()).upper()

        resources.append(
            f'    <asset id="{asset_id}" name="{name}" uid="{uid}"'
            f' src="{_file_url(clip_path)}" start="0s" duration="{dur}s"'
            f' format="r1" hasVideo="1" hasAudio="0"/>'
        )

        if i == 0 and audio_asset_id:
            # Connect the audio bed to the first clip at lane -1
            audio_clip_dur = min(audio_duration, total_video_dur)
            clips.append(
                f'          <asset-clip name="{name}" ref="{asset_id}"'
                f' offset="{offset}s" duration="{dur}s" start="0s">\n'
                f'            <asset-clip name="jamz_beat" ref="{audio_asset_id}"'
                f' lane="-1" offset="0s" duration="{audio_clip_dur:.3f}s"'
                f' start="0s"/>\n'
                f'          </asset-clip>'
            )
        else:
            clips.append(
                f'          <asset-clip name="{name}" ref="{asset_id}"'
                f' offset="{offset}s" duration="{dur}s" start="0s"/>'
            )
        offset += dur

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE fcpxml>',
        '<fcpxml version="1.8">',
        '  <resources>',
        *resources,
        '  </resources>',
        f'  <library location="{_file_url(os.path.expanduser("~/Movies/iMovie Library.imovielibrary"))}">',
        '    <event name="ROBOWRIGHT">',
        f'      <project name="{escape(title)}" uid="{str(uuid.uuid4()).upper()}">',
        f'        <sequence duration="{offset}s" format="r1"'
        ' tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">',
        '          <spine>',
        *clips,
        '          </spine>',
        '        </sequence>',
        '      </project>',
        '    </event>',
        '  </library>',
        '</fcpxml>',
    ]

    out_path = os.path.join(project_dir, "project.fcpxml")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return out_path
