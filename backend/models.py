"""
models.py — SQLAlchemy ORM models for Playlist and Video.
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from backend.database import Base


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(512), nullable=False)
    channel_name = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)
    video_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship
    videos = relationship("Video", back_populates="playlist", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Playlist id={self.playlist_id} title={self.title!r}>"


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String(64), unique=True, nullable=False, index=True)
    playlist_id = Column(String(64), ForeignKey("playlists.playlist_id"), nullable=False, index=True)

    title = Column(String(512), nullable=False)
    channel_name = Column(String(256), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, default=0)

    views = Column(BigInteger, default=0)
    likes = Column(BigInteger, default=0)
    comments = Column(BigInteger, default=0)

    thumbnail_url = Column(String(1024), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship
    playlist = relationship("Playlist", back_populates="videos")

    # Computed properties (not stored in DB)
    @property
    def like_rate(self) -> float:
        """Likes / Views × 100. Returns 0.0 if views == 0."""
        if not self.views:
            return 0.0
        return round((self.likes / self.views) * 100, 4)

    @property
    def comment_rate(self) -> float:
        """Comments / Views × 100. Returns 0.0 if views == 0."""
        if not self.views:
            return 0.0
        return round((self.comments / self.views) * 100, 4)

    @property
    def engagement_rate(self) -> float:
        """(Likes + Comments) / Views × 100. Returns 0.0 if views == 0."""
        if not self.views:
            return 0.0
        return round(((self.likes + self.comments) / self.views) * 100, 4)

    def __repr__(self) -> str:
        return f"<Video id={self.video_id} title={self.title!r}>"
