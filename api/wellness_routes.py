from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional
from datetime import date, datetime
from models import (
    ProgressModel, AchievementModel, LeaderboardModel, QuoteModel, StatsModel,
    ProgressEntry, ProgressResponse, Achievement, UserAchievement, LeaderboardEntry
)
from api.auth_routes import get_current_user, get_optional_current_user
from auth import UserResponse
import logging

router = APIRouter(prefix="/wellness", tags=["wellness"])

# Progress endpoints
@router.post("/progress", response_model=ProgressResponse)
async def mark_progress(
    progress_data: ProgressEntry,
    current_user: UserResponse = Depends(get_current_user)
):
    """Mark progress for a specific date"""
    try:
        progress = ProgressModel.mark_progress(
            user_id=current_user.id,
            date=progress_data.date,
            completed=progress_data.completed
        )
        
        if not progress:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to mark progress"
            )
        
        # Check for new achievements
        AchievementModel.check_and_award_achievements(current_user.id)
        
        return progress
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Progress marking error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark progress"
        )

@router.get("/progress", response_model=List[ProgressResponse])
async def get_user_progress(
    start_date: Optional[date] = Query(None, description="Start date for progress range"),
    end_date: Optional[date] = Query(None, description="End date for progress range"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get user's progress for a date range"""
    try:
        progress = ProgressModel.get_user_progress(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date
        )
        return progress
        
    except Exception as e:
        logging.error(f"Progress retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve progress"
        )

@router.get("/progress/monthly", response_model=List[ProgressResponse])
async def get_monthly_progress(
    year: int = Query(..., description="Year"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get user's progress for a specific month"""
    try:
        progress = ProgressModel.get_monthly_progress(
            user_id=current_user.id,
            year=year,
            month=month
        )
        return progress
        
    except Exception as e:
        logging.error(f"Monthly progress retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve monthly progress"
        )

# Achievement endpoints
@router.get("/achievements", response_model=List[Achievement])
async def get_all_achievements():
    """Get all available achievements"""
    try:
        achievements = AchievementModel.get_all_achievements()
        return achievements
        
    except Exception as e:
        logging.error(f"Achievements retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve achievements"
        )

@router.get("/achievements/user", response_model=List[UserAchievement])
async def get_user_achievements(current_user: UserResponse = Depends(get_current_user)):
    """Get user's earned achievements"""
    try:
        user_achievements = AchievementModel.get_user_achievements(current_user.id)
        return user_achievements
        
    except Exception as e:
        logging.error(f"User achievements retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user achievements"
        )

@router.post("/achievements/check")
async def check_achievements(current_user: UserResponse = Depends(get_current_user)):
    """Manually check and award new achievements"""
    try:
        AchievementModel.check_and_award_achievements(current_user.id)
        return {"message": "Achievements checked successfully"}
        
    except Exception as e:
        logging.error(f"Achievement check error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check achievements"
        )

# Leaderboard endpoints
@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(
    leaderboard_type: str = Query("current_streak", regex="^(current_streak|best_streak|total_days|total_points)$"),
    limit: int = Query(10, ge=1, le=100),
    current_user: Optional[UserResponse] = Depends(get_optional_current_user)
):
    """Get leaderboard data"""
    try:
        leaderboard = LeaderboardModel.get_leaderboard(
            leaderboard_type=leaderboard_type,
            limit=limit
        )
        
        # Mark current user if authenticated
        if current_user:
            for entry in leaderboard:
                if entry.user_id == current_user.id:
                    entry.is_current_user = True
                    break
        
        return leaderboard
        
    except Exception as e:
        logging.error(f"Leaderboard retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve leaderboard"
        )

@router.get("/leaderboard/rank")
async def get_user_rank(
    leaderboard_type: str = Query("current_streak", regex="^(current_streak|best_streak|total_days|total_points)$"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Get user's rank in leaderboard"""
    try:
        rank = LeaderboardModel.get_user_rank(
            user_id=current_user.id,
            leaderboard_type=leaderboard_type
        )
        
        return {
            "user_id": current_user.id,
            "username": current_user.username,
            "rank": rank,
            "leaderboard_type": leaderboard_type
        }
        
    except Exception as e:
        logging.error(f"User rank retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user rank"
        )

# Statistics endpoints
@router.get("/stats/user")
async def get_user_stats(current_user: UserResponse = Depends(get_current_user)):
    """Get user's personal statistics"""
    try:
        user_stats = StatsModel.get_user_stats(current_user.id)
        
        # Get ranks for different leaderboards
        current_streak_rank = LeaderboardModel.get_user_rank(current_user.id, "current_streak")
        best_streak_rank = LeaderboardModel.get_user_rank(current_user.id, "best_streak")
        points_rank = LeaderboardModel.get_user_rank(current_user.id, "total_points")
        
        # Combine user stats with ranks
        user_stats["ranks"] = {
            "current_streak": current_streak_rank,
            "best_streak": best_streak_rank,
            "total_points": points_rank
        }
        
        return user_stats
        
    except Exception as e:
        logging.error(f"User stats retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user statistics"
        )

@router.get("/quotes")
async def get_motivational_quotes():
    """Get random motivational quotes from database"""
    try:
        quotes = QuoteModel.get_random_quotes(limit=1)
        
        if quotes:
            return {"quote": quotes[0]["text"], "author": quotes[0]["author"]}
        else:
            # Fallback quote
            return {
                "quote": "Every journey begins with a single step. You've already started.",
                "author": "Unknown"
            }
        
    except Exception as e:
        logging.error(f"Quote retrieval error: {e}")
        # Return fallback quote on error
        return {
            "quote": "Progress, not perfection, is the goal.",
            "author": "Unknown"
        } 