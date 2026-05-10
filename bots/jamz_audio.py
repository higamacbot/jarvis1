import os
import subprocess
from typing import Optional, Tuple

FLUIDSYNTH = "/opt/homebrew/bin/fluidsynth"
FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"

_SF2_CANDIDATES = [
    "/opt/homebrew/share/fluid-synth/sf2/VintageDreamsWaves-v2.sf2",
    "/usr/share/soundfonts/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
]


def _find_soundfont() -> Optional[str]:
    for path in _SF2_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def _probe_duration(path: str) -> float:
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=10,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def render_midi_to_aiff(midi_path: str, out_path: str,
                         target_duration: float = 0.0) -> Tuple[Optional[str], float]:
    """
    Render a MIDI file to AIFF using FluidSynth.
    If target_duration > 0, loops the rendered audio to fill that duration via ffmpeg.
    Returns (aiff_path, actual_duration_secs) on success, (None, 0.0) on any failure.
    Every failure is logged and handled gracefully — caller treats None as "no audio".
    """
    if not os.path.isfile(FLUIDSYNTH):
        print(f">> JAMZ AUDIO: fluidsynth not found at {FLUIDSYNTH}, skipping")
        return None, 0.0

    sf2 = _find_soundfont()
    if not sf2:
        print(">> JAMZ AUDIO: no soundfont found, skipping audio render")
        return None, 0.0

    base = out_path.rsplit(".", 1)[0]
    wav_raw = base + "_raw.wav"

    try:
        r = subprocess.run(
            [FLUIDSYNTH, "-ni", "-F", wav_raw, "-r", "44100", sf2, midi_path],
            capture_output=True, timeout=30,
        )
        if r.returncode != 0 or not os.path.isfile(wav_raw):
            print(f">> JAMZ AUDIO: fluidsynth failed: {r.stderr.decode()[:200]}")
            return None, 0.0
    except Exception as e:
        print(f">> JAMZ AUDIO: fluidsynth exception: {e}")
        return None, 0.0

    source_wav = wav_raw
    if target_duration > 0:
        wav_looped = base + "_looped.wav"
        try:
            r = subprocess.run(
                [FFMPEG, "-y", "-stream_loop", "-1", "-i", wav_raw,
                 "-t", f"{target_duration:.3f}", "-ac", "2", "-ar", "44100",
                 wav_looped],
                capture_output=True, timeout=30,
            )
            if r.returncode == 0 and os.path.isfile(wav_looped):
                source_wav = wav_looped
            else:
                print(">> JAMZ AUDIO: loop step failed, using raw render length")
        except Exception as e:
            print(f">> JAMZ AUDIO: loop exception: {e}, using raw render length")

    try:
        r = subprocess.run(
            [FFMPEG, "-y", "-i", source_wav, "-c:a", "pcm_s16be", out_path],
            capture_output=True, timeout=30,
        )
        if r.returncode != 0 or not os.path.isfile(out_path):
            print(f">> JAMZ AUDIO: aiff conversion failed: {r.stderr.decode()[:200]}")
            return None, 0.0
    except Exception as e:
        print(f">> JAMZ AUDIO: aiff conversion exception: {e}")
        return None, 0.0

    duration = _probe_duration(out_path)
    print(f">> JAMZ AUDIO: {os.path.basename(midi_path)} → {os.path.basename(out_path)} ({duration:.1f}s)")
    return out_path, duration
