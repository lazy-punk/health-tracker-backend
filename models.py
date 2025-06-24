import logging
import hashlib
import random
import string
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from database import get_collection, COLLECTIONS, serialize_doc, serialize_docs

# ==================== PYDANTIC MODELS ====================

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    current_streak: int = 0
    best_streak: int = 0
    total_points: int = 0
    is_active: bool = True
    created_at: datetime
    last_progress_date: Optional[date] = None

class ProgressEntry(BaseModel):
    date: date
    completed: bool = True
    notes: Optional[str] = None

class ProgressResponse(BaseModel):
    id: str
    user_id: str
    date: date
    completed: bool
    notes: Optional[str]
    points_earned: int
    created_at: datetime

class Achievement(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    requirement_type: str
    requirement_value: int
    points_reward: int

class UserAchievement(BaseModel):
    achievement: Achievement
    earned_at: datetime

class LeaderboardEntry(BaseModel):
    user_id: str
    username: str
    display_name: str
    current_streak: int
    best_streak: int
    total_points: int
    total_days: int
    join_date: datetime
    is_current_user: bool = False

class RecoveryKey(BaseModel):
    id: str
    user_id: str
    key_display: str
    is_used: bool
    used_at: Optional[datetime]
    created_at: datetime

class UserStats(BaseModel):
    total_users: int
    total_progress_entries: int
    average_streak: float
    top_streak: int

class PasswordRecoveryRequest(BaseModel):
    email: str
    recovery_key: str
    new_password: str

# ==================== DATABASE MODELS ====================

class UserModel:
    @staticmethod
    def create_user(username: str, email: str, password: str) -> Optional[UserResponse]:
        """Create a new user in MongoDB"""
        try:
            users_collection = get_collection(COLLECTIONS['users'])
            
            user_doc = {
                "username": username,
                "email": email,
                "password": password,
                "current_streak": 0,
                "best_streak": 0,
                "total_points": 0,
                "is_active": True,
                "created_at": datetime.now(),
                "last_progress_date": None
            }
            
            result = users_collection.insert_one(user_doc)
            user_doc['_id'] = result.inserted_id
            
            serialized_user = serialize_doc(user_doc)
            return UserResponse(**serialized_user)
            
        except DuplicateKeyError:
            logging.error(f"User with username {username} or email {email} already exists")
            return None
        except Exception as e:
            logging.error(f"Error creating user: {e}")
            return None

    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        """Get user by username or email"""
        try:
            users_collection = get_collection(COLLECTIONS['users'])
            
            # Search by username or email
            user = users_collection.find_one({
                "$or": [
                    {"username": username},
                    {"email": username}
                ]
            })
            
            return serialize_doc(user) if user else None
            
        except Exception as e:
            logging.error(f"Error fetching user by username: {e}")
            return None

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[UserResponse]:
        """Get user by ID"""
        try:
            users_collection = get_collection(COLLECTIONS['users'])
            
            user = users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return None
                
            serialized_user = serialize_doc(user)
            return UserResponse(**serialized_user)
            
        except Exception as e:
            logging.error(f"Error fetching user by ID: {e}")
            return None

    @staticmethod
    def authenticate_user(username: str, password: str) -> Optional[UserResponse]:
        """Authenticate user credentials"""
        try:
            user = UserModel.get_user_by_username(username)
            if not user:
                return None
            
            # Import here to avoid circular imports
            from auth import verify_password
            
            # Verify password
            if not verify_password(password, user["password"]):
                return None
                
            # Remove password from response
            user_copy = user.copy()
            del user_copy["password"]
            return UserResponse(**user_copy)
            
        except Exception as e:
            logging.error(f"Error authenticating user: {e}")
            return None

    @staticmethod
    def update_password(user_id: str, new_password_hash: str) -> bool:
        """Update user password"""
        try:
            users_collection = get_collection(COLLECTIONS['users'])
            
            result = users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"password": new_password_hash}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logging.error(f"Error updating password: {e}")
            return False

    @staticmethod
    def update_user_streaks(user_id: str, current_streak: int, best_streak: int):
        """Update user streak information"""
        try:
            users_collection = get_collection(COLLECTIONS['users'])
            
            users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "current_streak": current_streak,
                        "best_streak": best_streak,
                        "last_progress_date": datetime.combine(date.today(), datetime.min.time())
                    }
                }
            )
            
        except Exception as e:
            logging.error(f"Error updating user streaks: {e}")

    @staticmethod
    def update_user_points(user_id: str, points_to_add: int):
        """Add points to user total"""
        try:
            users_collection = get_collection(COLLECTIONS['users'])
            
            users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"total_points": points_to_add}}
            )
            
        except Exception as e:
            logging.error(f"Error updating user points: {e}")

class ProgressModel:
    @staticmethod
    def mark_progress(user_id: str, date: date, completed: bool = True) -> Optional[ProgressResponse]:
        """Mark daily progress for user"""
        try:
            progress_collection = get_collection(COLLECTIONS['user_progress'])
            
            # Convert date to datetime for MongoDB storage
            date_datetime = datetime.combine(date, datetime.min.time())
            
            # Check if progress already exists for this date
            existing = progress_collection.find_one({
                "user_id": user_id,
                "date": date_datetime
            })
            
            points_change = 0  # Track points change for user total
            
            if existing:
                # Update existing progress
                old_completed = existing.get("completed", False)
                old_points = existing.get("points_earned", 0)
                new_points = 10 if completed else 0
                
                progress_collection.update_one(
                    {"_id": existing["_id"]},
                    {
                        "$set": {
                            "completed": completed,
                            "points_earned": new_points
                        }
                    }
                )
                
                # Calculate points change
                points_change = new_points - old_points
                
                existing["completed"] = completed
                existing["points_earned"] = new_points
                result_doc = existing
            else:
                # Create new progress entry
                new_points = 10 if completed else 0
                progress_doc = {
                    "user_id": user_id,
                    "date": date_datetime,
                    "completed": completed,
                    "notes": None,
                    "points_earned": new_points,
                    "created_at": datetime.now()
                }
                
                result = progress_collection.insert_one(progress_doc)
                progress_doc['_id'] = result.inserted_id
                result_doc = progress_doc
                
                # For new entries, points change is the new points earned
                points_change = new_points
            
            # Update user streaks and points based on completion status
            try:
                ProgressModel._update_user_streaks(user_id)
                
                # Update points only if there's a change
                if points_change != 0:
                    UserModel.update_user_points(user_id, points_change)
                    
            except Exception as streak_error:
                logging.error(f"Error updating streaks and points: {streak_error}")
                # Continue even if streak/points update fails
            
            # Serialize the document
            try:
                serialized_progress = serialize_doc(result_doc)
                # Convert datetime back to date for the response model
                if 'date' in serialized_progress and isinstance(result_doc['date'], datetime):
                    serialized_progress['date'] = result_doc['date'].date()
                return ProgressResponse(**serialized_progress)
            except Exception as serialize_error:
                logging.error(f"Error serializing progress response: {serialize_error}")
                # Fallback: manually create response
                return ProgressResponse(
                    id=str(result_doc['_id']),
                    user_id=user_id,
                    date=date,  # Use the original date parameter
                    completed=completed,
                    notes=result_doc.get('notes'),
                    points_earned=result_doc.get('points_earned', 0),
                    created_at=result_doc.get('created_at', datetime.now())
                )
            
        except Exception as e:
            logging.error(f"Error marking progress: {e}")
            import traceback
            logging.error(f"Progress marking traceback: {traceback.format_exc()}")
            return None

    @staticmethod
    def _update_user_streaks(user_id: str):
        """Update user's current and best streaks"""
        try:
            progress_collection = get_collection(COLLECTIONS['user_progress'])
            
            # Get user's progress sorted by date
            progress_docs = list(progress_collection.find({
                "user_id": user_id,
                "completed": True
            }).sort("date", -1))
            
            if not progress_docs:
                # No completed progress, set streaks to 0
                UserModel.update_user_streaks(user_id, 0, 0)
                return
            
            # Calculate current streak
            current_streak = 0
            today = date.today()
            check_date = today
            
            for progress in progress_docs:
                try:
                    # Convert datetime back to date for comparison
                    progress_date = progress["date"].date() if isinstance(progress["date"], datetime) else progress["date"]
                    if progress_date == check_date:
                        current_streak += 1
                        check_date -= timedelta(days=1)
                    else:
                        break
                except Exception as date_error:
                    logging.error(f"Error processing progress date: {date_error}")
                    continue
            
            # Calculate best streak
            try:
                all_dates = []
                for p in progress_docs:
                    try:
                        progress_date = p["date"].date() if isinstance(p["date"], datetime) else p["date"]
                        all_dates.append(progress_date)
                    except Exception as date_error:
                        logging.error(f"Error converting progress date: {date_error}")
                        continue
                
                all_dates = sorted(all_dates)
                best_streak = 1 if all_dates else 0
                temp_streak = 1
                
                for i in range(1, len(all_dates)):
                    if all_dates[i] == all_dates[i-1] + timedelta(days=1):
                        temp_streak += 1
                    else:
                        best_streak = max(best_streak, temp_streak)
                        temp_streak = 1
                
                best_streak = max(best_streak, temp_streak, current_streak)
            except Exception as best_streak_error:
                logging.error(f"Error calculating best streak: {best_streak_error}")
                best_streak = current_streak  # Fallback to current streak
            
            # Update user
            UserModel.update_user_streaks(user_id, current_streak, best_streak)
            
        except Exception as e:
            logging.error(f"Error updating streaks: {e}")
            import traceback
            logging.error(f"Streak update traceback: {traceback.format_exc()}")

    @staticmethod
    def get_user_progress(user_id: str, start_date: date = None, end_date: date = None) -> List[ProgressResponse]:
        """Get user's progress within date range"""
        try:
            progress_collection = get_collection(COLLECTIONS['user_progress'])
            
            query = {"user_id": user_id}
            
            if start_date and end_date:
                start_datetime = datetime.combine(start_date, datetime.min.time())
                end_datetime = datetime.combine(end_date, datetime.max.time())
                query["date"] = {"$gte": start_datetime, "$lte": end_datetime}
            elif start_date:
                start_datetime = datetime.combine(start_date, datetime.min.time())
                query["date"] = {"$gte": start_datetime}
            elif end_date:
                end_datetime = datetime.combine(end_date, datetime.max.time())
                query["date"] = {"$lte": end_datetime}
            
            progress_docs = list(progress_collection.find(query).sort("date", -1))
            
            serialized_progress = serialize_docs(progress_docs)
            # Convert datetime back to date for the response models
            for doc in serialized_progress:
                if 'date' in doc:
                    # Find the original doc to get the actual datetime
                    original_doc = next(p for p in progress_docs if str(p['_id']) == doc['id'])
                    if isinstance(original_doc['date'], datetime):
                        doc['date'] = original_doc['date'].date()
            
            return [ProgressResponse(**doc) for doc in serialized_progress]
            
        except Exception as e:
            logging.error(f"Error fetching user progress: {e}")
            return []

    @staticmethod
    def get_monthly_progress(user_id: str, year: int, month: int) -> List[ProgressResponse]:
        """Get user's progress for specific month"""
        try:
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            
            return ProgressModel.get_user_progress(user_id, start_date, end_date)
            
        except Exception as e:
            logging.error(f"Error fetching monthly progress: {e}")
            return []

class AchievementModel:
    @staticmethod
    def get_all_achievements() -> List[Achievement]:
        """Get all available achievements"""
        try:
            achievements_collection = get_collection(COLLECTIONS['achievements'])
            
            achievements = list(achievements_collection.find())
            serialized_achievements = serialize_docs(achievements)
            
            return [Achievement(**doc) for doc in serialized_achievements]
            
        except Exception as e:
            logging.error(f"Error fetching achievements: {e}")
            return []

    @staticmethod
    def get_user_achievements(user_id: str) -> List[UserAchievement]:
        """Get user's earned achievements"""
        try:
            user_achievements_collection = get_collection(COLLECTIONS['user_achievements'])
            achievements_collection = get_collection(COLLECTIONS['achievements'])
            
            # Get user achievements with achievement details
            pipeline = [
                {"$match": {"user_id": user_id}},
                {
                    "$lookup": {
                        "from": COLLECTIONS['achievements'],
                        "localField": "achievement_id",
                        "foreignField": "_id",
                        "as": "achievement"
                    }
                },
                {"$unwind": "$achievement"},
                {"$sort": {"earned_at": -1}}
            ]
            
            user_achievements = list(user_achievements_collection.aggregate(pipeline))
            
            result = []
            for ua in user_achievements:
                achievement_data = serialize_doc(ua["achievement"])
                achievement = Achievement(**achievement_data)
                result.append(UserAchievement(
                    achievement=achievement,
                    earned_at=ua["earned_at"]
                ))
            
            return result
            
        except Exception as e:
            logging.error(f"Error fetching user achievements: {e}")
            return []

    @staticmethod
    def check_and_award_achievements(user_id: str):
        """Check if user has earned any new achievements"""
        try:
            user = UserModel.get_user_by_id(user_id)
            if not user:
                return
            
            achievements_collection = get_collection(COLLECTIONS['achievements'])
            user_achievements_collection = get_collection(COLLECTIONS['user_achievements'])
            
            # Get achievements user hasn't earned yet
            earned_achievement_ids = [
                ua["achievement_id"] for ua in 
                user_achievements_collection.find({"user_id": user_id})
            ]
            
            unearned_achievements = list(achievements_collection.find({
                "_id": {"$nin": earned_achievement_ids}
            }))
            
            for achievement in unearned_achievements:
                should_award = False
                
                if achievement['requirement_type'] == 'streak':
                    should_award = user.best_streak >= achievement['requirement_value']
                elif achievement['requirement_type'] == 'points':
                    should_award = user.total_points >= achievement['requirement_value']
                elif achievement['requirement_type'] == 'monthly':
                    # Check current month progress
                    today = datetime.now()
                    monthly_progress = ProgressModel.get_monthly_progress(
                        user_id, today.year, today.month
                    )
                    completed_days = len([p for p in monthly_progress if p.completed])
                    should_award = completed_days >= achievement['requirement_value']
                
                if should_award:
                    # Award the achievement
                    user_achievements_collection.insert_one({
                        "user_id": user_id,
                        "achievement_id": achievement["_id"],
                        "earned_at": datetime.now()
                    })
                    
                    # Award points
                    UserModel.update_user_points(user_id, achievement['points_reward'])
                    logging.info(f"Awarded achievement {achievement['name']} to user {user_id}")
                    
        except Exception as e:
            logging.error(f"Error checking achievements: {e}")

class RecoveryKeyModel:
    @staticmethod
    def generate_recovery_key() -> str:
        """Generate a recovery key"""
        chars = string.ascii_uppercase + string.digits
        key_parts = []
        for _ in range(4):
            part = ''.join(random.choices(chars, k=4))
            key_parts.append(part)
        return '-'.join(key_parts)

    @staticmethod
    def hash_recovery_key(key: str) -> str:
        """Hash recovery key for secure storage"""
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def create_recovery_keys(user_id: str) -> List[str]:
        """Create 10 recovery keys for user"""
        try:
            recovery_keys_collection = get_collection(COLLECTIONS['recovery_keys'])
            
            keys = []
            for _ in range(10):
                key = RecoveryKeyModel.generate_recovery_key()
                key_hash = RecoveryKeyModel.hash_recovery_key(key)
                
                key_doc = {
                    "user_id": user_id,
                    "key_hash": key_hash,
                    "key_display": key,  # For admin purposes only
                    "is_used": False,
                    "used_at": None,
                    "created_at": datetime.now()
                }
                
                recovery_keys_collection.insert_one(key_doc)
                keys.append(key)
            
            return keys
            
        except Exception as e:
            logging.error(f"Error creating recovery keys: {e}")
            return []

    @staticmethod
    def verify_recovery_key(user_id: str, key: str) -> bool:
        """Verify if recovery key is valid (keys are now reusable)"""
        try:
            recovery_keys_collection = get_collection(COLLECTIONS['recovery_keys'])
            key_hash = RecoveryKeyModel.hash_recovery_key(key)
            
            key_doc = recovery_keys_collection.find_one({
                "user_id": user_id,
                "key_hash": key_hash
            })
            
            return key_doc is not None
            
        except Exception as e:
            logging.error(f"Error verifying recovery key: {e}")
            return False

    @staticmethod
    def use_recovery_key(user_id: str, key: str) -> bool:
        """Log recovery key usage (keys remain reusable)"""
        try:
            recovery_keys_collection = get_collection(COLLECTIONS['recovery_keys'])
            key_hash = RecoveryKeyModel.hash_recovery_key(key)
            
            # Just verify the key exists and update usage timestamp
            result = recovery_keys_collection.update_one(
                {
                    "user_id": user_id,
                    "key_hash": key_hash
                },
                {"$set": {"used_at": datetime.now()}}
            )
            
            if result.modified_count > 0:
                logging.info(f"Recovery key accessed successfully for user {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Error accessing recovery key: {e}")
            return False

    @staticmethod
    def count_unused_keys(user_id: str) -> int:
        """Count total recovery keys a user has (all keys are reusable)"""
        try:
            recovery_keys_collection = get_collection(COLLECTIONS['recovery_keys'])
            
            count = recovery_keys_collection.count_documents({"user_id": user_id})
            return count
            
        except Exception as e:
            logging.error(f"Error counting recovery keys: {e}")
            return 0

class LeaderboardModel:
    @staticmethod
    def get_leaderboard(leaderboard_type: str = "current_streak", limit: int = 10) -> List[LeaderboardEntry]:
        """Get leaderboard data"""
        try:
            users_collection = get_collection(COLLECTIONS['users'])
            progress_collection = get_collection(COLLECTIONS['user_progress'])
            
            # Aggregate pipeline to get leaderboard with total days
            pipeline = [
                {"$match": {"is_active": True}},
                {
                    "$lookup": {
                        "from": COLLECTIONS['user_progress'],
                        "let": {"user_id": {"$toString": "$_id"}},
                        "pipeline": [
                            {"$match": {
                                "$expr": {"$eq": ["$user_id", "$$user_id"]},
                                "completed": True
                            }},
                            {"$count": "total_days"}
                        ],
                        "as": "progress_stats"
                    }
                },
                {
                    "$addFields": {
                        "total_days": {
                            "$ifNull": [
                                {"$arrayElemAt": ["$progress_stats.total_days", 0]},
                                0
                            ]
                        }
                    }
                }
            ]
            
            # Add sorting based on leaderboard type
            if leaderboard_type == "current_streak":
                pipeline.append({"$sort": {"current_streak": -1, "created_at": 1}})
            elif leaderboard_type == "best_streak":
                pipeline.append({"$sort": {"best_streak": -1, "created_at": 1}})
            elif leaderboard_type == "total_days":
                pipeline.append({"$sort": {"total_days": -1, "created_at": 1}})
            else:
                pipeline.append({"$sort": {"total_points": -1, "created_at": 1}})
            
            pipeline.append({"$limit": limit})
            
            leaderboard_data = list(users_collection.aggregate(pipeline))
            
            result = []
            for user in leaderboard_data:
                # Generate anonymous display name
                display_name = LeaderboardModel.generate_display_name(user['username'])
                
                serialized_user = serialize_doc(user)
                result.append(LeaderboardEntry(
                    user_id=serialized_user['id'],
                    username=user['username'],
                    display_name=display_name,
                    current_streak=user.get('current_streak', 0),
                    best_streak=user.get('best_streak', 0),
                    total_points=user.get('total_points', 0),
                    total_days=user.get('total_days', 0),
                    join_date=user['created_at']
                ))
            
            return result
            
        except Exception as e:
            logging.error(f"Error fetching leaderboard: {e}")
            return []

    @staticmethod
    def generate_display_name(username: str) -> str:
        """Generate anonymous display name for privacy"""
        adjectives = ['Swift', 'Steady', 'Bright', 'Strong', 'Calm', 'Focused', 'Peaceful', 'Vibrant']
        nouns = ['Warrior', 'Seeker', 'Champion', 'Explorer', 'Guardian', 'Dreamer', 'Builder', 'Navigator']
        
        # Simple hash function
        hash_val = sum(ord(c) for c in username)
        adj_index = hash_val % len(adjectives)
        noun_index = (hash_val // len(adjectives)) % len(nouns)
        
        return f"{adjectives[adj_index]} {nouns[noun_index]}"

    @staticmethod
    def get_user_rank(user_id: str, leaderboard_type: str = "current_streak") -> int:
        """Get user's rank in leaderboard"""
        try:
            leaderboard = LeaderboardModel.get_leaderboard(leaderboard_type, limit=1000)
            for index, entry in enumerate(leaderboard):
                if entry.user_id == user_id:
                    return index + 1
            return 0
        except Exception as e:
            logging.error(f"Error getting user rank: {e}")
            return 0

class StatsModel:
    @staticmethod
    def get_platform_stats() -> UserStats:
        """Get platform-wide statistics"""
        try:
            users_collection = get_collection(COLLECTIONS['users'])
            progress_collection = get_collection(COLLECTIONS['user_progress'])
            
            # Total active users
            total_users = users_collection.count_documents({"is_active": True})
            
            # Total progress entries
            total_progress_entries = progress_collection.count_documents({"completed": True})
            
            # Average streak calculation
            users_with_streaks = list(users_collection.find(
                {"is_active": True, "current_streak": {"$gt": 0}},
                {"current_streak": 1}
            ))
            
            if users_with_streaks:
                average_streak = sum(u["current_streak"] for u in users_with_streaks) / len(users_with_streaks)
            else:
                average_streak = 0.0
            
            # Top streak
            top_user = users_collection.find_one(
                {"is_active": True},
                sort=[("best_streak", -1)]
            )
            top_streak = top_user.get("best_streak", 0) if top_user else 0
            
            return UserStats(
                total_users=total_users,
                total_progress_entries=total_progress_entries,
                average_streak=round(average_streak, 1),
                top_streak=top_streak
            )
            
        except Exception as e:
            logging.error(f"Error fetching platform stats: {e}")
            return UserStats(
                total_users=0,
                total_progress_entries=0,
                average_streak=0.0,
                top_streak=0
            )

    @staticmethod
    def get_user_stats(user_id: str) -> Dict[str, Any]:
        """Get user-specific statistics"""
        try:
            user = UserModel.get_user_by_id(user_id)
            if not user:
                return {}
            
            progress_collection = get_collection(COLLECTIONS['user_progress'])
            
            # Total completed days
            total_days = progress_collection.count_documents({
                "user_id": user_id,
                "completed": True
            })
            
            # Current month progress
            today = datetime.now()
            monthly_progress = ProgressModel.get_monthly_progress(user_id, today.year, today.month)
            monthly_days = len([p for p in monthly_progress if p.completed])
            
            # User achievements count
            user_achievements_collection = get_collection(COLLECTIONS['user_achievements'])
            achievements_count = user_achievements_collection.count_documents({"user_id": user_id})
            
            return {
                "current_streak": user.current_streak,
                "best_streak": user.best_streak,
                "total_points": user.total_points,
                "total_days": total_days,
                "monthly_days": monthly_days,
                "achievements_count": achievements_count,
                "join_date": user.created_at
            }
            
        except Exception as e:
            logging.error(f"Error fetching user stats: {e}")
            return {}

class QuoteModel:
    @staticmethod
    def get_random_quotes(limit: int = 5) -> List[Dict[str, str]]:
        """Get random motivational quotes"""
        try:
            quotes_collection = get_collection(COLLECTIONS['quotes'])
            
            # Get random quotes using aggregation
            quotes = list(quotes_collection.aggregate([
                {"$sample": {"size": limit}}
            ]))
            
            return serialize_docs(quotes)
            
        except Exception as e:
            logging.error(f"Error fetching quotes: {e}")
            return [] 