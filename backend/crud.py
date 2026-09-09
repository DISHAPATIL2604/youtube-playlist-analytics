"""
crud.py — Database CRUD operations using SQLAlchemy.
All write operations use upsert (insert or update) to prevent duplicates.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.models import Playlist, Video
from backend.schemas import PlaylistCreate, VideoCreate, PlaylistKPIs

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Playlist operations
# ---------------------------------------------------------------------------

def upsert_playlist(db: Session, playlist_data: PlaylistCreate) -> Playlist:
    """Insert playlist or update existing record on playlist_id conflict."""
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(Playlist)
        .values(
            playlist_id=playlist_data.playlist_id,
            title=playlist_data.title,
            channel_name=playlist_data.channel_name,
            description=playlist_data.description,
            video_count=playlist_data.video_count,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["playlist_id"],
            set_={
                "title": playlist_data.title,
                "channel_name": playlist_data.channel_name,
                "description": playlist_data.description,
                "video_count": playlist_data.video_count,
                "updated_at": now,
            },
        )
        .returning(Playlist)
    )
    result = db.execute(stmt)
    db.commit()
    row = result.fetchone()
    # Refresh via query to get full ORM object
    return db.query(Playlist).filter(Playlist.playlist_id == playlist_data.playlist_id).first()


def get_playlist(db: Session, playlist_id: str) -> Optional[Playlist]:
    """Fetch playlist by playlist_id string."""
    return db.query(Playlist).filter(Playlist.playlist_id == playlist_id).first()


# ---------------------------------------------------------------------------
# Video operations
# ---------------------------------------------------------------------------

def upsert_video(db: Session, video_data: VideoCreate) -> Video:
    """Insert video or update statistics on video_id conflict."""
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(Video)
        .values(
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
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["video_id"],
            set_={
                "title": video_data.title,
                "channel_name": video_data.channel_name,
                "published_at": video_data.published_at,
                "duration_seconds": video_data.duration_seconds,
                "views": video_data.views,
                "likes": video_data.likes,
                "comments": video_data.comments,
                "thumbnail_url": video_data.thumbnail_url,
                "updated_at": now,
            },
        )
    )
    db.execute(stmt)
    db.commit()
    return db.query(Video).filter(Video.video_id == video_data.video_id).first()


def get_videos_for_playlist(db: Session, playlist_id: str) -> List[Video]:
    """Fetch all videos for a playlist ordered by views descending."""
    return (
        db.query(Video)
        .filter(Video.playlist_id == playlist_id)
        .order_by(Video.views.desc())
        .all()
    )


def bulk_upsert_videos(db: Session, videos: List[VideoCreate]) -> int:
    """Bulk upsert multiple videos. Returns count of processed videos."""
    count = 0
    for video_data in videos:
        try:
            upsert_video(db, video_data)
            count += 1
        except Exception as e:
            logger.error(f"Error upserting video {video_data.video_id}: {e}")
            db.rollback()
    return count


# ---------------------------------------------------------------------------
# Analytics / KPI aggregation
# ---------------------------------------------------------------------------

def get_playlist_kpis(db: Session, playlist_id: str) -> PlaylistKPIs:
    """Compute aggregated KPIs for a playlist directly in the database."""
    result = db.query(
        func.count(Video.id).label("total_videos"),
        func.coalesce(func.sum(Video.views), 0).label("total_views"),
        func.coalesce(func.sum(Video.likes), 0).label("total_likes"),
        func.coalesce(func.sum(Video.comments), 0).label("total_comments"),
        func.coalesce(func.avg(Video.views), 0.0).label("avg_views"),
        func.coalesce(func.avg(Video.likes), 0.0).label("avg_likes"),
        func.coalesce(func.avg(Video.comments), 0.0).label("avg_comments"),
    ).filter(Video.playlist_id == playlist_id).first()

    if not result or result.total_videos == 0:
        return PlaylistKPIs()

    # Average engagement rate: mean of per-video engagement rates
    videos = get_videos_for_playlist(db, playlist_id)
    avg_eng = 0.0
    if videos:
        rates = [v.engagement_rate for v in videos]
        avg_eng = round(sum(rates) / len(rates), 4)

    return PlaylistKPIs(
        total_videos=result.total_videos,
        total_views=int(result.total_views),
        total_likes=int(result.total_likes),
        total_comments=int(result.total_comments),
        avg_views=round(float(result.avg_views), 2),
        avg_likes=round(float(result.avg_likes), 2),
        avg_comments=round(float(result.avg_comments), 2),
        avg_engagement_rate=avg_eng,
    )
