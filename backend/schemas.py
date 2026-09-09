"""
schemas.py — Pydantic v2 schemas for request/response validation.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    playlist_url: str = Field(..., description="Full YouTube Playlist URL or playlist ID")


# ---------------------------------------------------------------------------
# Playlist schemas
# ---------------------------------------------------------------------------

class PlaylistBase(BaseModel):
    playlist_id: str
    title: str
    channel_name: Optional[str] = None
    description: Optional[str] = None
    video_count: int = 0


class PlaylistCreate(PlaylistBase):
    pass


class PlaylistResponse(PlaylistBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Video schemas
# ---------------------------------------------------------------------------

class VideoBase(BaseModel):
    video_id: str
    playlist_id: str
    title: str
    channel_name: Optional[str] = None
    published_at: Optional[datetime] = None
    duration_seconds: int = 0
    views: int = 0
    likes: int = 0
    comments: int = 0
    thumbnail_url: Optional[str] = None


class VideoCreate(VideoBase):
    pass


class VideoResponse(VideoBase):
    id: int
    like_rate: float = 0.0
    comment_rate: float = 0.0
    engagement_rate: float = 0.0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_metrics(cls, video) -> "VideoResponse":
        """Build response including computed metric properties from ORM model."""
        return cls(
            id=video.id,
            video_id=video.video_id,
            playlist_id=video.playlist_id,
            title=video.title,
            channel_name=video.channel_name,
            published_at=video.published_at,
            duration_seconds=video.duration_seconds,
            views=video.views,
            likes=video.likes,
            comments=video.comments,
            thumbnail_url=video.thumbnail_url,
            like_rate=video.like_rate,
            comment_rate=video.comment_rate,
            engagement_rate=video.engagement_rate,
            created_at=video.created_at,
            updated_at=video.updated_at,
        )


# ---------------------------------------------------------------------------
# Analytics / KPI schemas
# ---------------------------------------------------------------------------

class PlaylistKPIs(BaseModel):
    total_videos: int = 0
    total_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    avg_views: float = 0.0
    avg_likes: float = 0.0
    avg_comments: float = 0.0
    avg_engagement_rate: float = 0.0


class AnalyticsResponse(BaseModel):
    playlist: PlaylistResponse
    kpis: PlaylistKPIs
    videos: List[VideoResponse]


# ---------------------------------------------------------------------------
# Health check schema
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    database: str
    message: str = ""
