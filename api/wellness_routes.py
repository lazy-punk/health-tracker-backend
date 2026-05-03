from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from pydantic import BaseModel, validator

from api.auth_routes import get_current_user
from auth import UserResponse
from models import UserModel, ProgressModel, AchievementModel, QuoteModel
import logging
import os
from logtail import LogtailHandler

handler = LogtailHandler(
    source_token=os.getenv("LOGTAIL_SOURCE_TOKEN"),
    host=os.getenv("LOGTAIL_HOST")
)


# Get logger for this module
logger = logging.getLogger(__name__)
logger.addHandler(handler)
router = APIRouter(prefix="/wellness", tags=["wellness"])

# Request models
class ProgressData(BaseModel):
    exercise: bool = False
    sleep_hours: Optional[float] = None
    water_glasses: Optional[int] = None
    meditation_minutes: Optional[int] = None
    mood_rating: Optional[int] = None
    notes: Optional[str] = None
    date: Optional[str] = None
    
    @validator('mood_rating')
    def validate_mood_rating(cls, v):
        if v is not None and (v < 1 or v > 10):
            raise ValueError('Mood rating must be between 1 and 10')
        return v
    
    @validator('sleep_hours')
    def validate_sleep_hours(cls, v):
        if v is not None and (v < 0 or v > 24):
            raise ValueError('Sleep hours must be between 0 and 24')
        return v
    
    @validator('water_glasses')
    def validate_water_glasses(cls, v):
        if v is not None and v < 0:
            raise ValueError('Water glasses must be non-negative')
        return v
    
    @validator('meditation_minutes')
    def validate_meditation_minutes(cls, v):
        if v is not None and v < 0:
            raise ValueError('Meditation minutes must be non-negative')
        return v

@router.post("/progress", response_model=dict)
async def mark_progress(
    progress_data: ProgressData,
    current_user: UserResponse = Depends(get_current_user)
):
    """Mark daily progress for wellness activities"""
    logger.info(f"Progress marking request from user: [REDACTED]")
    logger.debug(f"Progress data: {progress_data.dict()}")
    
    try:
        # Use current date if no date provided
        target_date = progress_data.date or datetime.now().strftime('%Y-%m-%d')
        logger.debug(f"Target date for progress: {target_date}")
        
        # Mark progress
        logger.debug("Calling ProgressModel.mark_progress...")
        result = ProgressModel.mark_progress(
            user_id=current_user.id,
            progress_data=progress_data.dict(),
            date=target_date
        )
        
        if result["success"]:
            logger.info(f"Progress marked successfully for user [REDACTED] on {target_date}")
            logger.debug(f"Progress result: {result}")
        else:
            logger.warning(f"Progress marking failed for user [REDACTED]: {result.get('message', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Progress marking error for user [REDACTED]: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark progress"
        )

@router.get("/progress", response_model=dict)
async def get_progress(
    current_user: UserResponse = Depends(get_current_user),
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format")
):
    """Get progress data for a specific date or current date"""
    logger.info(f"Progress retrieval request from user: [REDACTED]")
    
    try:
        target_date = date or datetime.now().strftime('%Y-%m-%d')
        logger.debug(f"Retrieving progress for date: {target_date}")
        
        progress = ProgressModel.get_user_progress(current_user.id, target_date)
        
        if progress:
            logger.info(f"Progress data retrieved for user [REDACTED] on {target_date}")
            logger.debug(f"Progress data found: {bool(progress)}")
        else:
            logger.info(f"No progress data found for user [REDACTED] on {target_date}")
        
        return {
            "success": True,
            "progress": progress,
            "date": target_date
        }
        
    except Exception as e:
        logger.error(f"Progress retrieval error for user [REDACTED]: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve progress"
        )

@router.get("/progress/monthly", response_model=dict)
async def get_monthly_progress(
    current_user: UserResponse = Depends(get_current_user),
    year: int = Query(datetime.now().year, description="Year"),
    month: int = Query(datetime.now().month, description="Month (1-12)")
):
    """Get monthly progress summary"""
    logger.info(f"Monthly progress request from user [REDACTED] for {year}-{month:02d}")
    
    try:
        logger.debug(f"Retrieving monthly progress for user {current_user.id}")
        
        monthly_data = ProgressModel.get_monthly_progress(current_user.id, year, month)
        
        logger.info(f"Monthly progress retrieved for user [REDACTED]")
        logger.debug(f"Monthly data entries: {len(monthly_data) if monthly_data else 0}")
        
        return {
            "success": True,
            "monthly_progress": monthly_data,
            "year": year,
            "month": month
        }
        
    except Exception as e:
        logger.error(f"Monthly progress retrieval error for user [REDACTED]: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve monthly progress"
        )

@router.get("/achievements", response_model=dict)
async def get_achievements(current_user: UserResponse = Depends(get_current_user)):
    """Get all available achievements"""
    logger.info(f"Achievements request from user: [REDACTED]")
    
    try:
        logger.debug("Retrieving all achievements...")
        achievements = AchievementModel.get_all_achievements()
        
        logger.info(f"Retrieved {len(achievements) if achievements else 0} achievements")
        
        return {
            "success": True,
            "achievements": achievements
        }
        
    except Exception as e:
        logger.error(f"Achievements retrieval error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve achievements"
        )

@router.get("/achievements/user", response_model=dict)
async def get_user_achievements(current_user: UserResponse = Depends(get_current_user)):
    """Get user's earned achievements"""
    logger.info(f"User achievements request from user: [REDACTED]")
    
    try:
        logger.debug(f"Retrieving achievements for user {current_user.id}")
        user_achievements = AchievementModel.get_user_achievements(current_user.id)
        
        achievement_count = len(user_achievements) if user_achievements else 0
        logger.info(f"User [REDACTED] has {achievement_count} achievements")
        
        return {
            "success": True,
            "user_achievements": user_achievements
        }
        
    except Exception as e:
        logger.error(f"User achievements retrieval error for user [REDACTED]: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user achievements"
        )

@router.post("/achievements/check", response_model=dict)
async def check_achievements(current_user: UserResponse = Depends(get_current_user)):
    """Check and award new achievements for user"""
    logger.info(f"Achievement check request from user: [REDACTED]")
    
    try:
        logger.debug(f"Checking achievements for user {current_user.id}")
        new_achievements = AchievementModel.check_and_award_achievements(current_user.id)
        
        if new_achievements:
            logger.info(f"New achievements awarded to user [REDACTED]: {len(new_achievements)}")
            for achievement in new_achievements:
                logger.info(f"Achievement awarded: {achievement.get('name', 'Unknown')} to user [REDACTED]")
        else:
            logger.debug(f"No new achievements for user [REDACTED]")
        
        return {
            "success": True,
            "new_achievements": new_achievements or []
        }
        
    except Exception as e:
        logger.error(f"Achievement check error for user [REDACTED]: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check achievements"
        )

# Leaderboard endpoints
@router.get("/leaderboard/points", response_model=dict)
async def get_points_leaderboard(
    current_user: UserResponse = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50, description="Number of users to return")
):
    """Get points leaderboard"""
    logger.info(f"Points leaderboard request from user [REDACTED] (limit: {limit})")
    
    try:
        logger.debug("Retrieving points leaderboard...")
        leaderboard = UserModel.get_points_leaderboard(limit)
        
        logger.info(f"Points leaderboard retrieved with {len(leaderboard) if leaderboard else 0} entries")
        
        return {
            "success": True,
            "leaderboard": leaderboard,
            "type": "points",
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Points leaderboard retrieval error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve points leaderboard"
        )

@router.get("/leaderboard/streaks", response_model=dict)
async def get_streaks_leaderboard(
    current_user: UserResponse = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50, description="Number of users to return")
):
    """Get streaks leaderboard"""
    logger.info(f"Streaks leaderboard request from user [REDACTED] (limit: {limit})")
    
    try:
        logger.debug("Retrieving streaks leaderboard...")
        leaderboard = UserModel.get_streaks_leaderboard(limit)
        
        logger.info(f"Streaks leaderboard retrieved with {len(leaderboard) if leaderboard else 0} entries")
        
        return {
            "success": True,
            "leaderboard": leaderboard,
            "type": "streaks",
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Streaks leaderboard retrieval error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve streaks leaderboard"
        )

@router.get("/user/rank", response_model=dict)
async def get_user_rank(current_user: UserResponse = Depends(get_current_user)):
    """Get current user's rank in various categories"""
    logger.info(f"User rank request from user: [REDACTED]")
    
    try:
        logger.debug(f"Retrieving rank for user {current_user.id}")
        
        points_rank = UserModel.get_user_rank(current_user.id, "points")
        streaks_rank = UserModel.get_user_rank(current_user.id, "current_streak")
        
        logger.info(f"User [REDACTED] ranks - Points: {points_rank}, Streaks: {streaks_rank}")
        
        return {
            "success": True,
            "user_rank": {
                "points": points_rank,
                "current_streak": streaks_rank,
                "username": current_user.username
            }
        }
        
    except Exception as e:
        logger.error(f"User rank retrieval error for user [REDACTED]: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user rank"
        )

# Statistics endpoints
@router.get("/stats/platform", response_model=dict)
async def get_platform_stats(current_user: UserResponse = Depends(get_current_user)):
    """Get platform-wide statistics"""
    logger.info(f"Platform stats request from user: [REDACTED]")
    
    try:
        logger.debug("Retrieving platform statistics...")
        stats = UserModel.get_platform_stats()
        
        logger.info("Platform statistics retrieved successfully")
        logger.debug(f"Platform stats: {stats}")
        
        return {
            "success": True,
            "platform_stats": stats
        }
        
    except Exception as e:
        logger.error(f"Platform stats retrieval error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve platform statistics"
        )

@router.get("/stats/user", response_model=dict)
async def get_user_stats(current_user: UserResponse = Depends(get_current_user)):
    """Get detailed user statistics"""
    logger.info(f"User stats request from user: [REDACTED]")
    
    try:
        logger.debug(f"Retrieving detailed stats for user {current_user.id}")
        user_stats = UserModel.get_user_stats(current_user.id)
        
        logger.info(f"User statistics retrieved for [REDACTED]")
        logger.debug(f"User stats keys: {list(user_stats.keys()) if user_stats else []}")
        
        return {
            "success": True,
            "user_stats": user_stats
        }
        
    except Exception as e:
        logger.error(f"User stats retrieval error for user [REDACTED]: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user statistics"
        )

# Motivational quotes endpoint
@router.get("/quotes", response_model=dict)
async def get_motivational_quotes(
    current_user: UserResponse = Depends(get_current_user),
    count: int = Query(1, ge=1, le=10, description="Number of quotes to return")
):
    """Get motivational quotes"""
    logger.info(f"Motivational quotes request from user [REDACTED] (count: {count})")
    
    try:
        logger.debug(f"Retrieving {count} motivational quotes...")
        quotes = QuoteModel.get_random_quotes(count)
        
        quote_count = len(quotes) if quotes else 0
        logger.info(f"Retrieved {quote_count} motivational quotes")
        
        return {
            "success": True,
            "quotes": quotes,
            "count": quote_count
        }
        
    except Exception as e:
        logger.error(f"Motivational quotes retrieval error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve motivational quotes"
        ) 