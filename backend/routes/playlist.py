"""
routes/playlist.py — FastAPI route handlers for playlist analytics.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend import crud, youtube_service
from backend.database import get_db
from backend.schemas import (
    AnalyzeRequest,
    AnalyticsResponse,
    PlaylistResponse,
    VideoResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playlist", tags=["playlist"])


@router.post(
    "/analyze",
    response_model=AnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze a YouTube playlist",
    description=(
        "Fetches playlist and video data from YouTube API, "
        "upserts it into PostgreSQL, and returns full analytics."
    ),
)
def analyze_playlist(request: AnalyzeRequest, db: Session = Depends(get_db)):
    # 1. Extract playlist ID
    playlist_id = youtube_service.extract_playlist_id(request.playlist_url)
    if not playlist_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Could not extract a valid playlist ID from the provided URL. "
                "Please use a full YouTube playlist URL (e.g. "
                "https://www.youtube.com/playlist?list=PLxxxxxxxx)."
            ),
        )

    # 2. Fetch playlist metadata from YouTube
    try:
        playlist_data = youtube_service.fetch_playlist_metadata(playlist_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error fetching playlist metadata")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch playlist: {str(e)}",
        )

    # 3. Fetch all videos from YouTube
    try:
        videos_data = youtube_service.fetch_all_videos(playlist_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error fetching videos")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch videos: {str(e)}",
        )

    # 4. Upsert playlist into database
    playlist_data.video_count = len(videos_data)
    try:
        db_playlist = crud.upsert_playlist(db, playlist_data)
    except Exception as e:
        logger.exception("Database error upserting playlist")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error saving playlist: {str(e)}",
        )

    # 5. Bulk upsert videos
    try:
        count = crud.bulk_upsert_videos(db, videos_data)
        logger.info(f"Upserted {count} videos for playlist {playlist_id}")
    except Exception as e:
        logger.exception("Database error upserting videos")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error saving videos: {str(e)}",
        )

    # 6. Compute KPIs and return
    kpis = crud.get_playlist_kpis(db, playlist_id)
    db_videos = crud.get_videos_for_playlist(db, playlist_id)
    video_responses = [VideoResponse.from_orm_with_metrics(v) for v in db_videos]

    return AnalyticsResponse(
        playlist=PlaylistResponse.model_validate(db_playlist),
        kpis=kpis,
        videos=video_responses,
    )


@router.get(
    "/{playlist_id}",
    response_model=PlaylistResponse,
    summary="Get playlist metadata",
)
def get_playlist(playlist_id: str, db: Session = Depends(get_db)):
    db_playlist = crud.get_playlist(db, playlist_id)
    if not db_playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Playlist '{playlist_id}' not found in database. Analyze it first.",
        )
    return PlaylistResponse.model_validate(db_playlist)


@router.get(
    "/{playlist_id}/videos",
    response_model=List[VideoResponse],
    summary="Get all videos for a playlist",
)
def get_playlist_videos(playlist_id: str, db: Session = Depends(get_db)):
    db_playlist = crud.get_playlist(db, playlist_id)
    if not db_playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Playlist '{playlist_id}' not found in database. Analyze it first.",
        )
    videos = crud.get_videos_for_playlist(db, playlist_id)
    return [VideoResponse.from_orm_with_metrics(v) for v in videos]
