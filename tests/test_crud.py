"""
tests/test_crud.py — Tests for database CRUD operations using SQLite in-memory DB.
No PostgreSQL required for these tests.
"""
import pytest
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import Playlist, Video
from backend.schemas import PlaylistCreate, VideoCreate


# ---------------------------------------------------------------------------
# Test fixtures — SQLite in-memory database
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session():
    """Provide a clean in-memory SQLite session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def make_playlist_create(**kwargs) -> PlaylistCreate:
    defaults = dict(
        playlist_id="PLtest12345678901",
        title="Test Playlist",
        channel_name="Test Channel",
        description="A test playlist",
        video_count=5,
    )
    defaults.update(kwargs)
    return PlaylistCreate(**defaults)


def make_video_create(**kwargs) -> VideoCreate:
    defaults = dict(
        video_id="vid001",
        playlist_id="PLtest12345678901",
        title="Test Video",
        channel_name="Test Channel",
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        duration_seconds=300,
        views=1000,
        likes=50,
        comments=10,
        thumbnail_url="https://img.youtube.com/vi/vid001/hqdefault.jpg",
    )
    defaults.update(kwargs)
    return VideoCreate(**defaults)


# ---------------------------------------------------------------------------
# SQLite-compatible upsert helpers (replaces PostgreSQL-specific pg_insert)
# ---------------------------------------------------------------------------

def sqlite_upsert_playlist(db, playlist_data: PlaylistCreate) -> Playlist:
    """SQLite-compatible upsert (merge) for tests."""
    existing = db.query(Playlist).filter(Playlist.playlist_id == playlist_data.playlist_id).first()
    if existing:
        existing.title = playlist_data.title
        existing.channel_name = playlist_data.channel_name
        existing.description = playlist_data.description
        existing.video_count = playlist_data.video_count
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        p = Playlist(
            playlist_id=playlist_data.playlist_id,
            title=playlist_data.title,
            channel_name=playlist_data.channel_name,
            description=playlist_data.description,
            video_count=playlist_data.video_count,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return p


def sqlite_upsert_video(db, video_data: VideoCreate) -> Video:
    """SQLite-compatible upsert for tests."""
    existing = db.query(Video).filter(Video.video_id == video_data.video_id).first()
    if existing:
        existing.title = video_data.title
        existing.views = video_data.views
        existing.likes = video_data.likes
        existing.comments = video_data.comments
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        v = Video(
            video_id=video_data.video_id,
            playlist_id=video_data.playlist_id,
            title=video_data.title,
            channel_name=video_data.channel_name,
            published_at=video_data.published_at,
            duration_seconds=video_data.duration_seconds,
            views=video_data.views,
            likes=video_data.likes,
            comments=video_data.comments,
            thumbnail_url=video_data.thumbnail_url,
        )
        db.add(v)
        db.commit()
        db.refresh(v)
        return v


# ---------------------------------------------------------------------------
# Playlist CRUD tests
# ---------------------------------------------------------------------------

def test_insert_playlist(db_session):
    """New playlist should be inserted correctly."""
    data = make_playlist_create()
    playlist = sqlite_upsert_playlist(db_session, data)

    assert playlist.id is not None
    assert playlist.playlist_id == "PLtest12345678901"
    assert playlist.title == "Test Playlist"
    assert playlist.channel_name == "Test Channel"
    assert playlist.video_count == 5


def test_upsert_playlist_no_duplicate(db_session):
    """Re-upserting same playlist_id should update, not insert a duplicate."""
    data1 = make_playlist_create(title="Old Title", video_count=5)
    data2 = make_playlist_create(title="New Title", video_count=10)

    sqlite_upsert_playlist(db_session, data1)
    sqlite_upsert_playlist(db_session, data2)

    count = db_session.query(Playlist).filter(
        Playlist.playlist_id == "PLtest12345678901"
    ).count()
    assert count == 1

    playlist = db_session.query(Playlist).filter(
        Playlist.playlist_id == "PLtest12345678901"
    ).first()
    assert playlist.title == "New Title"
    assert playlist.video_count == 10


def test_get_playlist_not_found(db_session):
    """Querying a non-existent playlist returns None."""
    result = db_session.query(Playlist).filter(
        Playlist.playlist_id == "nonexistent"
    ).first()
    assert result is None


# ---------------------------------------------------------------------------
# Video CRUD tests
# ---------------------------------------------------------------------------

def test_insert_video(db_session):
    """New video should be inserted with correct statistics."""
    # Insert playlist first (FK requirement)
    pl = sqlite_upsert_playlist(db_session, make_playlist_create())

    data = make_video_create()
    video = sqlite_upsert_video(db_session, data)

    assert video.id is not None
    assert video.video_id == "vid001"
    assert video.views == 1000
    assert video.likes == 50
    assert video.comments == 10


def test_upsert_video_updates_stats(db_session):
    """Re-upserting same video_id should update stats, not duplicate."""
    sqlite_upsert_playlist(db_session, make_playlist_create())

    data1 = make_video_create(views=1000, likes=50)
    data2 = make_video_create(views=5000, likes=300)

    sqlite_upsert_video(db_session, data1)
    sqlite_upsert_video(db_session, data2)

    count = db_session.query(Video).filter(Video.video_id == "vid001").count()
    assert count == 1

    video = db_session.query(Video).filter(Video.video_id == "vid001").first()
    assert video.views == 5000
    assert video.likes == 300


def test_multiple_videos_no_duplicate(db_session):
    """Multiple different videos should all be inserted."""
    sqlite_upsert_playlist(db_session, make_playlist_create())

    for i in range(5):
        sqlite_upsert_video(db_session, make_video_create(video_id=f"vid{i:03d}", views=i * 100))

    count = db_session.query(Video).filter(
        Video.playlist_id == "PLtest12345678901"
    ).count()
    assert count == 5


# ---------------------------------------------------------------------------
# Metric property tests via ORM model
# ---------------------------------------------------------------------------

def test_video_metrics_after_insert(db_session):
    """ORM computed properties should be correct after DB round-trip."""
    sqlite_upsert_playlist(db_session, make_playlist_create())
    sqlite_upsert_video(db_session, make_video_create(views=2000, likes=100, comments=20))

    video = db_session.query(Video).filter(Video.video_id == "vid001").first()
    assert video.like_rate == pytest.approx(5.0, abs=1e-4)
    assert video.comment_rate == pytest.approx(1.0, abs=1e-4)
    assert video.engagement_rate == pytest.approx(6.0, abs=1e-4)


def test_video_metrics_zero_views(db_session):
    """Zero-view video should not raise and return 0.0 for all rates."""
    sqlite_upsert_playlist(db_session, make_playlist_create())
    sqlite_upsert_video(db_session, make_video_create(views=0, likes=0, comments=0))

    video = db_session.query(Video).filter(Video.video_id == "vid001").first()
    assert video.like_rate == 0.0
    assert video.comment_rate == 0.0
    assert video.engagement_rate == 0.0
