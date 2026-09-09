"""
tests/test_api.py — Integration tests for FastAPI endpoints.
Mocks both YouTube service AND crud operations to avoid DB dialect issues.
"""
import pytest
import sys
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from backend.main import app
from backend.database import get_db
from backend.schemas import PlaylistCreate, VideoCreate, PlaylistResponse, VideoResponse, PlaylistKPIs, AnalyticsResponse


# ---------------------------------------------------------------------------
# Mock DB session dependency
# ---------------------------------------------------------------------------

def mock_get_db():
    """Return a MagicMock session — no real DB needed."""
    yield MagicMock()


@pytest.fixture(autouse=True)
def override_db():
    app.dependency_overrides[get_db] = mock_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

MOCK_PLAYLIST_ID = "PLBqzsE3test12345678"
MOCK_PLAYLIST_URL = f"https://www.youtube.com/playlist?list={MOCK_PLAYLIST_ID}"
NOW = datetime.now(timezone.utc)

MOCK_PLAYLIST_CREATE = PlaylistCreate(
    playlist_id=MOCK_PLAYLIST_ID,
    title="Mock Test Playlist",
    channel_name="Mock Channel",
    description="A mock playlist for testing",
    video_count=2,
)

MOCK_VIDEOS_CREATE = [
    VideoCreate(
        video_id="vid_mock_001",
        playlist_id=MOCK_PLAYLIST_ID,
        title="Mock Video 1",
        channel_name="Mock Channel",
        published_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
        duration_seconds=300,
        views=10000,
        likes=500,
        comments=50,
        thumbnail_url="https://img.youtube.com/vi/vid_mock_001/hqdefault.jpg",
    ),
    VideoCreate(
        video_id="vid_mock_002",
        playlist_id=MOCK_PLAYLIST_ID,
        title="Mock Video 2",
        channel_name="Mock Channel",
        published_at=datetime(2024, 2, 20, tzinfo=timezone.utc),
        duration_seconds=600,
        views=5000,
        likes=200,
        comments=20,
        thumbnail_url="https://img.youtube.com/vi/vid_mock_002/hqdefault.jpg",
    ),
]


def _make_playlist_orm():
    """Build a mock ORM Playlist object."""
    m = MagicMock()
    m.id = 1
    m.playlist_id = MOCK_PLAYLIST_ID
    m.title = "Mock Test Playlist"
    m.channel_name = "Mock Channel"
    m.description = "A mock playlist for testing"
    m.video_count = 2
    m.created_at = NOW
    m.updated_at = NOW
    return m


def _make_video_orm(video_id: str, views: int, likes: int, comments: int, title: str):
    """Build a mock ORM Video object."""
    m = MagicMock()
    m.id = 1
    m.video_id = video_id
    m.playlist_id = MOCK_PLAYLIST_ID
    m.title = title
    m.channel_name = "Mock Channel"
    m.published_at = NOW
    m.duration_seconds = 300
    m.views = views
    m.likes = likes
    m.comments = comments
    m.thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    m.like_rate = round((likes / views) * 100, 4) if views else 0.0
    m.comment_rate = round((comments / views) * 100, 4) if views else 0.0
    m.engagement_rate = round(((likes + comments) / views) * 100, 4) if views else 0.0
    m.created_at = NOW
    m.updated_at = NOW
    return m


MOCK_VIDEO_ORMS = [
    _make_video_orm("vid_mock_001", 10000, 500, 50, "Mock Video 1"),
    _make_video_orm("vid_mock_002", 5000, 200, 20, "Mock Video 2"),
]

MOCK_KPIS = PlaylistKPIs(
    total_videos=2,
    total_views=15000,
    total_likes=700,
    total_comments=70,
    avg_views=7500.0,
    avg_likes=350.0,
    avg_comments=35.0,
    avg_engagement_rate=5.0,
)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

def test_health_endpoint_reachable(client):
    """GET /health should return HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_structure(client):
    """Health response must contain status and database fields."""
    data = client.get("/health").json()
    assert "status" in data
    assert "database" in data


# ---------------------------------------------------------------------------
# POST /playlist/analyze — success
# ---------------------------------------------------------------------------

@patch("backend.routes.playlist.youtube_service.extract_playlist_id", return_value=MOCK_PLAYLIST_ID)
@patch("backend.routes.playlist.youtube_service.fetch_playlist_metadata", return_value=MOCK_PLAYLIST_CREATE)
@patch("backend.routes.playlist.youtube_service.fetch_all_videos", return_value=MOCK_VIDEOS_CREATE)
@patch("backend.routes.playlist.crud.upsert_playlist", return_value=_make_playlist_orm())
@patch("backend.routes.playlist.crud.bulk_upsert_videos", return_value=2)
@patch("backend.routes.playlist.crud.get_playlist_kpis", return_value=MOCK_KPIS)
@patch("backend.routes.playlist.crud.get_videos_for_playlist", return_value=MOCK_VIDEO_ORMS)
def test_analyze_playlist_success(
    mock_videos_for, mock_kpis, mock_bulk, mock_upsert_pl,
    mock_fetch_videos, mock_fetch_meta, mock_extract,
    client,
):
    response = client.post("/playlist/analyze", json={"playlist_url": MOCK_PLAYLIST_URL})
    assert response.status_code == 200

    data = response.json()
    assert "playlist" in data
    assert "kpis" in data
    assert "videos" in data
    assert data["playlist"]["playlist_id"] == MOCK_PLAYLIST_ID
    assert data["kpis"]["total_videos"] == 2
    assert data["kpis"]["total_views"] == 15000
    assert len(data["videos"]) == 2


# ---------------------------------------------------------------------------
# POST /playlist/analyze — error cases
# ---------------------------------------------------------------------------

@patch("backend.routes.playlist.youtube_service.extract_playlist_id", return_value=None)
def test_analyze_invalid_url_returns_422(mock_extract, client):
    response = client.post("/playlist/analyze", json={"playlist_url": "https://www.google.com"})
    assert response.status_code == 422


@patch("backend.routes.playlist.youtube_service.extract_playlist_id", return_value=MOCK_PLAYLIST_ID)
@patch(
    "backend.routes.playlist.youtube_service.fetch_playlist_metadata",
    side_effect=ValueError("Playlist not found"),
)
def test_analyze_playlist_not_found_returns_404(mock_meta, mock_extract, client):
    response = client.post("/playlist/analyze", json={"playlist_url": MOCK_PLAYLIST_URL})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@patch("backend.routes.playlist.youtube_service.extract_playlist_id", return_value=MOCK_PLAYLIST_ID)
@patch(
    "backend.routes.playlist.youtube_service.fetch_playlist_metadata",
    side_effect=PermissionError("API key invalid"),
)
def test_analyze_api_key_error_returns_403(mock_meta, mock_extract, client):
    response = client.post("/playlist/analyze", json={"playlist_url": MOCK_PLAYLIST_URL})
    assert response.status_code == 403


@patch("backend.routes.playlist.youtube_service.extract_playlist_id", return_value=MOCK_PLAYLIST_ID)
@patch(
    "backend.routes.playlist.youtube_service.fetch_playlist_metadata",
    side_effect=RuntimeError("quotaExceeded"),
)
def test_analyze_quota_exceeded_returns_429(mock_meta, mock_extract, client):
    response = client.post("/playlist/analyze", json={"playlist_url": MOCK_PLAYLIST_URL})
    assert response.status_code == 429


# ---------------------------------------------------------------------------
# GET /playlist/{id}
# ---------------------------------------------------------------------------

@patch("backend.routes.playlist.crud.get_playlist", return_value=_make_playlist_orm())
def test_get_playlist_found(mock_get, client):
    response = client.get(f"/playlist/{MOCK_PLAYLIST_ID}")
    assert response.status_code == 200
    data = response.json()
    assert data["playlist_id"] == MOCK_PLAYLIST_ID
    assert data["title"] == "Mock Test Playlist"


@patch("backend.routes.playlist.crud.get_playlist", return_value=None)
def test_get_playlist_not_found(mock_get, client):
    response = client.get("/playlist/PLnonexistent123456")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /playlist/{id}/videos
# ---------------------------------------------------------------------------

@patch("backend.routes.playlist.crud.get_playlist", return_value=_make_playlist_orm())
@patch("backend.routes.playlist.crud.get_videos_for_playlist", return_value=MOCK_VIDEO_ORMS)
def test_get_videos_returns_with_metrics(mock_videos, mock_playlist, client):
    response = client.get(f"/playlist/{MOCK_PLAYLIST_ID}/videos")
    assert response.status_code == 200
    videos = response.json()
    assert len(videos) == 2
    for v in videos:
        assert "like_rate" in v
        assert "comment_rate" in v
        assert "engagement_rate" in v


@patch("backend.routes.playlist.crud.get_playlist", return_value=None)
def test_get_videos_playlist_not_found(mock_playlist, client):
    response = client.get("/playlist/PLnonexistent123456/videos")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Verify metrics on VideoResponse
# ---------------------------------------------------------------------------

@patch("backend.routes.playlist.youtube_service.extract_playlist_id", return_value=MOCK_PLAYLIST_ID)
@patch("backend.routes.playlist.youtube_service.fetch_playlist_metadata", return_value=MOCK_PLAYLIST_CREATE)
@patch("backend.routes.playlist.youtube_service.fetch_all_videos", return_value=MOCK_VIDEOS_CREATE)
@patch("backend.routes.playlist.crud.upsert_playlist", return_value=_make_playlist_orm())
@patch("backend.routes.playlist.crud.bulk_upsert_videos", return_value=2)
@patch("backend.routes.playlist.crud.get_playlist_kpis", return_value=MOCK_KPIS)
@patch("backend.routes.playlist.crud.get_videos_for_playlist", return_value=MOCK_VIDEO_ORMS)
def test_video_metrics_are_nonzero(
    mock_videos_for, mock_kpis, mock_bulk, mock_upsert_pl,
    mock_fetch_videos, mock_fetch_meta, mock_extract,
    client,
):
    response = client.post("/playlist/analyze", json={"playlist_url": MOCK_PLAYLIST_URL})
    videos = response.json()["videos"]
    # vid_mock_001: 10000 views, 500 likes, 50 comments → like_rate=5%
    vid1 = next(v for v in videos if v["video_id"] == "vid_mock_001")
    assert vid1["like_rate"] == pytest.approx(5.0, abs=0.01)
    assert vid1["engagement_rate"] == pytest.approx(5.5, abs=0.01)


# ---------------------------------------------------------------------------
# Test missing request body field
# ---------------------------------------------------------------------------

def test_analyze_missing_url_field(client):
    """Missing playlist_url in request body should return 422."""
    response = client.post("/playlist/analyze", json={})
    assert response.status_code == 422
