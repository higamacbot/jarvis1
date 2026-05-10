import os
import uuid
from typing import List, Dict
from urllib.parse import quote
from xml.sax.saxutils import escape


def _file_url(path: str) -> str:
    return "file://" + quote(os.path.abspath(path), safe="/:")


def generate_fcpxml(title: str, prompts: List[Dict], clip_paths: List[str], project_dir: str) -> str:
    """
    Write project.fcpxml into project_dir sequencing clip_paths in timeline order.
    prompts and clip_paths are zipped (stops at the shorter list).
    Returns absolute path to the written .fcpxml file.
    """
    resources = ['    <format id="r1" name="FFVideoFormat1080p30" frameDuration="100/3000s" width="1920" height="1080" colorSpace="1-1-1 (Rec. 709)"/>']
    clips = []
    offset = 0

    for i, (shot, clip_path) in enumerate(zip(prompts, clip_paths)):
        asset_id = f"r{i + 2}"
        dur = max(1, shot.get("duration_sec", 3))
        name = escape(f"shot_{shot['shot']:02d}")
        uid = str(uuid.uuid4()).upper()

        resources.append(
            f'    <asset id="{asset_id}" name="{name}" uid="{uid}"'
            f' src="{_file_url(clip_path)}" start="0s" duration="{dur}s"'
            f' format="r1" hasVideo="1" hasAudio="0"/>'
        )
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
