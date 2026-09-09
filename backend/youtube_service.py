"""
youtube_service.py — YouTube Data API v3 integration.

Handles:
- Playlist ID extraction from all URL formats
- Playlist metadata fetching
- Paginated video fetching with batched statistics
- ISO 8601 duration parsing
- Quota-aware error handling
"""
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import isodate
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.config import settings
from backend.schemas import PlaylistCreate, VideoCreate

logger = logging.getLogger(__name__)

# Regex patterns for playlist ID extraction
_PLAYLIST_ID_PATTERNS = [
    r"[?&]list=([A-Za-z0-9_-]+)",          # ?list= or &list=
    r"playlist\?list=([A-Za-z0-9_-]+)",    # playlist?list=
    r"^([A-Za-z0-9_-]{18,})$",             # raw playlist ID
]

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
MAX_RESULTS_PER_PAGE = 50  # YouTube API maximum


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def extract_playlist_id(url_or_id: str) -> Optional[str]:
    """
    Extract YouTube playlist ID from various URL formats or raw ID.

    Supported formats:
    - https://www.youtube.com/playlist?list=PLxxxxxx
    - https://youtu.be/...?list=PLxxxxxx
    - https://www.youtube.com/watch?v=...&list=PLxxxxxx
    - https://m.youtube.com/playlist?list=PLxxxxxx
    - PLxxxxxx (raw ID)
    """
    url_or_id = url_or_id.strip()
    if not url_or_id:
        return None

    for pattern in _PLAYLIST_ID_PATTERNS:
        match = re.search(pattern, url_or_id)
        if match:
            playlist_id = match.group(1)
            # Validate basic format: YouTube playlist IDs are 18+ chars
            if len(playlist_id) >= 10:
                return playlist_id
    return None


def parse_duration(iso_duration: str) -> int:
    """Convert ISO 8601 duration string (e.g. PT4M13S) to total seconds."""
    if not iso_duration:
        return 0
    try:
        duration = isodate.parse_duration(iso_duration)
        return int(duration.total_seconds())
    except Exception:
        return 0


def _get_youtube_client():
    """Build authenticated YouTube API client."""
    if not settings.youtube_api_key:
        raise ValueError(
            "YOUTUBE_API_KEY is not configured. "
            "Add it to your .env file."
        )
    return build(
        YOUTUBE_API_SERVICE_NAME,
        YOUTUBE_API_VERSION,
        developerKey=settings.youtube_api_key,
        cache_discovery=False,
    )


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def fetch_playlist_metadata(playlist_id: str) -> PlaylistCreate:
    """
    Fetch playlist title, channel name, description, and item count.
    Uses 1 API call (playlists.list).
    """
    youtube = _get_youtube_client()
    try:
        response = (
            youtube.playlists()
            .list(
                part="snippet,contentDetails",
                id=playlist_id,
                maxResults=1,
            )
            .execute()
        )
    except HttpError as e:
        _handle_http_error(e)

    items = response.get("items", [])
    if not items:
        raise ValueError(
            f"Playlist '{playlist_id}' not found. "
            "It may be private, deleted, or the ID is incorrect."
        )

    item = items[0]
    snippet = item.get("snippet", {})
    content_details = item.get("contentDetails", {})

    return PlaylistCreate(
        playlist_id=playlist_id,
        title=snippet.get("title", "Untitled Playlist"),
        channel_name=snippet.get("channelTitle"),
        description=snippet.get("description"),
        video_count=content_details.get("itemCount", 0),
    )


def fetch_all_videos(playlist_id: str) -> List[VideoCreate]:
    """
    Fetch all videos in a playlist with full statistics.

    Strategy to minimize quota:
    1. playlistItems.list (cost=1 per page) → get video IDs (50/page)
    2. videos.list (cost=1 per batch of 50) → get stats + duration
    Total quota: ~2 units per 50 videos
    """
    youtube = _get_youtube_client()

    # Step 1: Collect all video IDs from playlist pages
    video_ids: List[Tuple[str, str]] = []  # (video_id, position)
    next_page_token = None

    while True:
        try:
            page_response = (
                youtube.playlistItems()
                .list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=MAX_RESULTS_PER_PAGE,
                    pageToken=next_page_token,
                )
                .execute()
            )
        except HttpError as e:
            _handle_http_error(e)

        for item in page_response.get("items", []):
            vid_id = item.get("contentDetails", {}).get("videoId")
            if vid_id:
                video_ids.append(vid_id)

        next_page_token = page_response.get("nextPageToken")
        if not next_page_token:
            break

    if not video_ids:
        raise ValueError(f"Playlist '{playlist_id}' is empty or contains no accessible videos.")

    # Step 2: Batch fetch statistics (50 videos per API call)
    videos: List[VideoCreate] = []
    for i in range(0, len(video_ids), MAX_RESULTS_PER_PAGE):
        batch_ids = video_ids[i : i + MAX_RESULTS_PER_PAGE]
        batch_videos = _fetch_video_batch(youtube, batch_ids, playlist_id)
        videos.extend(batch_videos)

    logger.info(f"Fetched {len(videos)} videos for playlist {playlist_id}")
    return videos


def _fetch_video_batch(youtube, video_ids: List[str], playlist_id: str) -> List[VideoCreate]:
    """Fetch statistics for a batch of up to 50 video IDs."""
    try:
        response = (
            youtube.videos()
            .list(
                part="snippet,statistics,contentDetails",
                id=",".join(video_ids),
                maxResults=MAX_RESULTS_PER_PAGE,
            )
            .execute()
        )
    except HttpError as e:
        _handle_http_error(e)

    videos = []
    for item in response.get("items", []):
        video = _parse_video_item(item, playlist_id)
        if video:
            videos.append(video)
    return videos


def _parse_video_item(item: Dict, playlist_id: str) -> Optional[VideoCreate]:
    """Parse a YouTube video API item into a VideoCreate schema."""
    try:
        video_id = item.get("id", "")
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        content_details = item.get("contentDetails", {})

        # Parse published_at
        published_at_str = snippet.get("publishedAt")
        published_at = None
        if published_at_str:
            try:
                published_at = datetime.fromisoformat(
                    published_at_str.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        # Parse duration
        duration_seconds = parse_duration(content_details.get("duration", ""))

        # Parse statistics (may be missing for some videos)
        views = int(statistics.get("viewCount", 0))
        likes = int(statistics.get("likeCount", 0))
        comments = int(statistics.get("commentCount", 0))

        # Best available thumbnail
        thumbnails = snippet.get("thumbnails", {})
        thumbnail_url = (
            thumbnails.get("maxres", {}).get("url")
            or thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
        )

        return VideoCreate(
            video_id=video_id,
            playlist_id=playlist_id,
            title=snippet.get("title", "Untitled"),
            channel_name=snippet.get("channelTitle"),
            published_at=published_at,
            duration_seconds=duration_seconds,
            views=views,
            likes=likes,
            comments=comments,
            thumbnail_url=thumbnail_url,
        )
    except Exception as e:
        logger.warning(f"Failed to parse video item {item.get('id', '?')}: {e}")
        return None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def _handle_http_error(error: HttpError) -> None:
    """Translate YouTube API HTTP errors to descriptive exceptions."""
    status = error.resp.status
    reason = ""
    try:
        import json
        error_details = json.loads(error.content)
        reason = error_details.get("error", {}).get("message", "")
    except Exception:
        reason = str(error)

    if status == 400:
        raise ValueError(f"Bad request to YouTube API: {reason}")
    elif status == 403:
        if "quotaExceeded" in reason or "dailyLimitExceeded" in reason:
            raise RuntimeError(
                "YouTube API daily quota exceeded. Try again tomorrow or use a different API key."
            )
        raise PermissionError(
            f"YouTube API access denied: {reason}. "
            "Check that your API key is valid and YouTube Data API v3 is enabled."
        )
    elif status == 404:
        raise ValueError(f"YouTube resource not found: {reason}")
    else:
        raise RuntimeError(f"YouTube API error (HTTP {status}): {reason}")
