"""
tests/test_utils.py — Unit tests for URL extraction and metric calculations.
No external dependencies required.
"""
import pytest
import sys
import os

# Make backend importable when running from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.youtube_service import extract_playlist_id, parse_duration


# ---------------------------------------------------------------------------
# Playlist ID extraction tests
# ---------------------------------------------------------------------------

VALID_URL_CASES = [
    # Standard playlist page
    (
        "https://www.youtube.com/playlist?list=PLBqzsE3-oYEWUPEEzFAVCn6pzrRDdHWG0",
        "PLBqzsE3-oYEWUPEEzFAVCn6pzrRDdHWG0",
    ),
    # Watch URL with list param
    (
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLBqzsE3-oYEWUPEEzFAVCn6pzrRDdHWG0",
        "PLBqzsE3-oYEWUPEEzFAVCn6pzrRDdHWG0",
    ),
    # Mobile URL
    (
        "https://m.youtube.com/playlist?list=PLBqzsE3-oYEWUPEEzFAVCn6pzrRDdHWG0",
        "PLBqzsE3-oYEWUPEEzFAVCn6pzrRDdHWG0",
    ),
    # Short URL with list param
    (
        "https://youtu.be/dQw4w9WgXcQ?list=PLBqzsE3-oYEWUPEEzFAVCn6pzrRDdHWG0",
        "PLBqzsE3-oYEWUPEEzFAVCn6pzrRDdHWG0",
    ),
    # Raw playlist ID
    (
        "PLBqzsE3-oYEWUPEEzFAVCn6pzrRDdHWG0",
        "PLBqzsE3-oYEWUPEEzFAVCn6pzrRDdHWG0",
    ),
    # URL with extra params
    (
        "https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx&si=abc123",
        "PLxxxxxxxxxxxxxxxx",
    ),
]


@pytest.mark.parametrize("url, expected_id", VALID_URL_CASES)
def test_extract_playlist_id_valid(url, expected_id):
    """Valid URLs should return correct playlist ID."""
    result = extract_playlist_id(url)
    assert result == expected_id, f"Expected {expected_id!r}, got {result!r}"


INVALID_URL_CASES = [
    "",
    "   ",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # no list param
    "https://www.google.com",
    "not a url",
    "PL",  # too short
]


@pytest.mark.parametrize("url", INVALID_URL_CASES)
def test_extract_playlist_id_invalid(url):
    """Invalid URLs should return None."""
    result = extract_playlist_id(url)
    assert result is None, f"Expected None for {url!r}, got {result!r}"


# ---------------------------------------------------------------------------
# Duration parsing tests
# ---------------------------------------------------------------------------

DURATION_CASES = [
    ("PT4M13S", 253),       # 4 min 13 sec
    ("PT1H2M3S", 3723),     # 1h 2m 3s
    ("PT30S", 30),           # 30 seconds
    ("PT0S", 0),
    ("", 0),
    ("invalid", 0),
    ("P1D", 86400),          # 1 day
]


@pytest.mark.parametrize("iso, expected_seconds", DURATION_CASES)
def test_parse_duration(iso, expected_seconds):
    result = parse_duration(iso)
    assert result == expected_seconds, f"Duration {iso!r}: expected {expected_seconds}, got {result}"


# ---------------------------------------------------------------------------
# Metric calculation tests
# ---------------------------------------------------------------------------

def make_video(views: int, likes: int, comments: int):
    """Create a mock video object with computed metric properties."""
    from backend.models import Video
    v = Video()
    v.views = views
    v.likes = likes
    v.comments = comments
    return v


def test_like_rate_normal():
    v = make_video(views=1000, likes=50, comments=10)
    assert v.like_rate == pytest.approx(5.0, abs=1e-4)


def test_comment_rate_normal():
    v = make_video(views=1000, likes=50, comments=10)
    assert v.comment_rate == pytest.approx(1.0, abs=1e-4)


def test_engagement_rate_normal():
    v = make_video(views=1000, likes=50, comments=10)
    assert v.engagement_rate == pytest.approx(6.0, abs=1e-4)


def test_like_rate_zero_views():
    """Zero views should return 0.0 without raising ZeroDivisionError."""
    v = make_video(views=0, likes=0, comments=0)
    assert v.like_rate == 0.0
    assert v.comment_rate == 0.0
    assert v.engagement_rate == 0.0


def test_engagement_rate_high_engagement():
    v = make_video(views=100, likes=80, comments=20)
    assert v.engagement_rate == pytest.approx(100.0, abs=1e-4)


def test_like_rate_precision():
    """Like rate should handle fractional results correctly."""
    v = make_video(views=3, likes=1, comments=0)
    assert v.like_rate == pytest.approx(33.3333, abs=0.001)
