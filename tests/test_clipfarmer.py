import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bots.clipfarmer import (
    _classify_download_error,
    _extract_video_id,
    _is_youtube,
    _normalize_clip_url,
)


# ── _classify_download_error ──────────────────────────────────────────────────

def test_classify_bot_detection():
    kind, hint = _classify_download_error("Sign in to confirm you're not a bot.")
    assert kind == "bot_detection"


def test_classify_private():
    kind, hint = _classify_download_error("This video is private.")
    assert kind == "unavailable"


def test_classify_login_required():
    kind, hint = _classify_download_error("You need to log in to watch this video.")
    assert kind == "auth_required"


def test_classify_geo():
    kind, hint = _classify_download_error("This video is not available in your country.")
    assert kind == "geo"


def test_classify_network():
    kind, hint = _classify_download_error("HTTP Error 503: Service Unavailable / network timeout")
    assert kind == "network"


def test_classify_unknown():
    kind, hint = _classify_download_error("something completely unexpected happened")
    assert kind == "unknown"
    assert "console" in hint


# ── _is_youtube ───────────────────────────────────────────────────────────────

def test_is_youtube_long():
    assert _is_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True


def test_is_youtube_short():
    assert _is_youtube("https://youtu.be/dQw4w9WgXcQ") is True


def test_is_youtube_tiktok_full():
    assert _is_youtube("https://www.tiktok.com/@user/video/7123456789012345678") is False


def test_is_youtube_tiktok_shortlink():
    assert _is_youtube("https://www.tiktok.com/t/ZP8pmQ1nS/") is False


def test_is_youtube_vm_tiktok():
    assert _is_youtube("https://vm.tiktok.com/ZP8pmQ1nS/") is False


# ── _extract_video_id ─────────────────────────────────────────────────────────

def test_extract_video_id_youtube_watch():
    vid = _extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert vid == "dQw4w9WgXcQ"


def test_extract_video_id_youtube_short():
    vid = _extract_video_id("https://youtu.be/dQw4w9WgXcQ")
    assert vid == "dQw4w9WgXcQ"


def test_extract_video_id_tiktok_shortlink():
    vid = _extract_video_id("https://www.tiktok.com/t/ZP8pmQ1nS/")
    assert "ZP8pmQ1nS" in vid


# ── _normalize_clip_url ───────────────────────────────────────────────────────

def test_normalize_clip_url_passthrough_for_full_tiktok_url():
    url = "https://www.tiktok.com/@user/video/7123456789012345678"
    normalized, err = _normalize_clip_url(url, resolver=lambda _: "should-not-run")
    assert normalized == url
    assert err == ""


def test_normalize_clip_url_resolves_tiktok_shortlink():
    short = "https://www.tiktok.com/t/ZP8pmQ1nS/"
    full = "https://www.tiktok.com/@user/video/7123456789012345678"
    normalized, err = _normalize_clip_url(short, resolver=lambda _: full)
    assert normalized == full
    assert err == ""


def test_normalize_clip_url_handles_vm_shortlink_resolution_failure():
    short = "https://vm.tiktok.com/ZP8pmQ1nS/"

    def _boom(_):
        raise RuntimeError("redirect blocked")

    normalized, err = _normalize_clip_url(short, resolver=_boom)
    assert normalized == short
    assert "redirect" in err.lower()
