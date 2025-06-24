#!/usr/bin/env python3
"""
Script to mark progress for user sanepunk2 on June 21st, 2025
"""

import sys
import os

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)

from models import UserModel, ProgressModel, AchievementModel
from datetime import date

def mark_progress_for_sanepunk2():
    """Mark progress for user sanepunk2 on June 21st"""
    print("=== MARKING PROGRESS FOR SANEPUNK2 ===")
    
    # Find user sanepunk2
    user = UserModel.get_user_by_username("sanepunk")
    if not user:
        print("ERROR: User 'sanepunk2' not found!")
        return False
    
    user_id = user['id']
    username = user['username']
    print(f"Found user: {username} (ID: {user_id})")
    
    # Mark progress for June 21st, 2025
    target_date = date(2025, 6, 26)
    print(f"Marking progress for date: {target_date}")
    
    try:
        # Mark the progress as completed
        progress = ProgressModel.mark_progress(
            user_id=user_id,
            date=target_date,
            completed=True
        )
        
        if progress:
            print("✅ SUCCESS: Progress marked successfully!")
            print(f"   Date: {progress.date}")
            print(f"   Completed: {progress.completed}")
            print(f"   Points Earned: {progress.points_earned}")
            print(f"   Created At: {progress.created_at}")
            
            # Check and award achievements
            print("\nChecking for new achievements...")
            AchievementModel.check_and_award_achievements(user_id)
            print("✅ Achievement check completed")
            
            # Get updated user info
            updated_user = UserModel.get_user_by_id(user_id)
            if updated_user:
                print(f"\nUpdated User Stats:")
                print(f"   Current Streak: {updated_user.current_streak}")
                print(f"   Best Streak: {updated_user.best_streak}")
                print(f"   Total Points: {updated_user.total_points}")
            
            return True
        else:
            print("❌ ERROR: Failed to mark progress")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: Exception occurred: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = mark_progress_for_sanepunk2()
    if success:
        print("\n🎉 Script completed successfully!")
    else:
        print("\n💥 Script failed!")
        sys.exit(1)