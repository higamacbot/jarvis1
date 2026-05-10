"""
jamz_midi.py — MIDI file generator for JAMZ beat handoff to GarageBand.

Takes a parsed beat spec (bpm, key, bars) and writes a .mid file containing
a basic 4-bar drum + bass loop that GarageBand will open as a new project.

Drum note mapping follows GM standard:
  36 = Bass Drum, 38 = Snare, 42 = Closed Hi-Hat, 46 = Open Hi-Hat
"""
import os
import re
from midiutil import MIDIFile

BEATS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "beats")
os.makedirs(BEATS_DIR, exist_ok=True)

# General MIDI drum channel is always channel 9 (0-indexed)
DRUM_CH = 9

# Key name → MIDI root note (C3 = 48)
KEY_ROOT = {
    "c":  48, "c#": 49, "db": 49, "d":  50, "d#": 51, "eb": 51,
    "e":  52, "f":  53, "f#": 54, "gb": 54, "g":  55, "g#": 56,
    "ab": 56, "a":  57, "a#": 58, "bb": 58, "b":  59,
    "cmin": 48, "dmin": 50, "emin": 52, "fmin": 53,
    "gmin": 55, "amin": 57, "bmin": 59,
    "cmaj": 48, "dmaj": 50, "emaj": 52, "fmaj": 53,
    "gmaj": 55, "amaj": 57, "bmaj": 59,
}

def _parse_key(key_str: str) -> int:
    """Return MIDI root note from a key string like 'Cmin', 'F#', 'Eb major'."""
    if not key_str:
        return 48  # default C
    k = key_str.lower().strip().replace(" ", "").replace("major", "maj").replace("minor", "min")
    k = re.sub(r"maj(or)?$", "maj", k)
    k = re.sub(r"min(or)?$", "min", k)
    # try full match first, then just root
    if k in KEY_ROOT:
        return KEY_ROOT[k]
    root = k[:2] if k[1:2] in ("#", "b") else k[:1]
    return KEY_ROOT.get(root, 48)

def _minor_pentatonic(root: int) -> list[int]:
    """Return one octave of minor pentatonic starting at root."""
    intervals = [0, 3, 5, 7, 10]
    return [root + i for i in intervals]

def generate_midi(bpm: int = 120, key: str = "C", bars: int = 4,
                  output_dir: str = None, filename: str = None) -> str:
    """
    Generate a 4-bar MIDI loop and save it as a .mid file.
    Returns the absolute path to the saved file.

    Track layout:
      Track 0 (ch 9)  — GM drums: kick, snare, hi-hat
      Track 1 (ch 0)  — Bass: minor pentatonic root-pattern
    """
    bpm = max(60, min(240, int(bpm)))
    root = _parse_key(key)
    scale = _minor_pentatonic(root)

    midi = MIDIFile(2)  # 2 tracks

    # ── Track 0: Drums ────────────────────────────────────────────────────────
    midi.addTempo(0, 0, bpm)
    midi.addTrackName(0, 0, "Drums")

    KICK   = 36
    SNARE  = 38
    HIHAT  = 42
    volume = 100

    for bar in range(bars):
        offset = bar * 4  # 4 beats per bar
        # Kick: beats 1 and 3
        midi.addNote(0, DRUM_CH, KICK,  offset + 0, 0.5, volume)
        midi.addNote(0, DRUM_CH, KICK,  offset + 2, 0.5, volume)
        # Snare: beats 2 and 4
        midi.addNote(0, DRUM_CH, SNARE, offset + 1, 0.5, volume)
        midi.addNote(0, DRUM_CH, SNARE, offset + 3, 0.5, volume)
        # Hi-hat: every 8th note
        for eighth in range(8):
            midi.addNote(0, DRUM_CH, HIHAT, offset + eighth * 0.5, 0.25, 80)

    # ── Track 1: Bass ─────────────────────────────────────────────────────────
    midi.addTempo(1, 0, bpm)
    midi.addTrackName(1, 0, "Bass")

    bass_pattern = [scale[0], scale[0], scale[2], scale[1],
                    scale[0], scale[3], scale[2], scale[0]]
    duration = 0.5  # 8th notes

    for bar in range(bars):
        offset = bar * 4
        for i, note in enumerate(bass_pattern):
            midi.addNote(1, 0, note, offset + i * duration, duration, 90)

    # ── Save ──────────────────────────────────────────────────────────────────
    if output_dir is None:
        output_dir = BEATS_DIR
    os.makedirs(output_dir, exist_ok=True)

    if filename is None:
        from datetime import datetime
        safe_key = re.sub(r"[^a-zA-Z0-9]", "", key)[:8]
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{ts}_{bpm}bpm_{safe_key}.mid"

    path = os.path.join(output_dir, filename)
    with open(path, "wb") as f:
        midi.writeFile(f)

    return path
