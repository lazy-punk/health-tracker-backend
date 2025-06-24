import os
import logging
from contextlib import contextmanager
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, IndexModel, ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import PyMongoError, DuplicateKeyError
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_DB_URI = os.getenv("MONGO_DB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "wellness_tracker")

# Global MongoDB client and database
mongo_client: Optional[MongoClient] = None
db: Optional[Database] = None

# Collection names
COLLECTIONS = {
    'users': 'users',
    'user_progress': 'user_progress', 
    'achievements': 'achievements',
    'user_achievements': 'user_achievements',
    'recovery_keys': 'recovery_keys',
    'quotes': 'quotes'
}

def get_mongo_client() -> MongoClient:
    """Get MongoDB client instance"""
    global mongo_client
    if mongo_client is None:
        try:
            mongo_client = MongoClient(MONGO_DB_URI)
            # Test the connection
            mongo_client.admin.command('ping')
            logging.info("Connected to MongoDB successfully")
        except Exception as e:
            logging.error(f"Failed to connect to MongoDB: {e}")
            raise
    return mongo_client

def get_database() -> Database:
    """Get database instance"""
    global db
    if db is None:
        client = get_mongo_client()
        db = client[DATABASE_NAME]
    return db

def get_collection(collection_name: str) -> Collection:
    """Get collection instance"""
    database = get_database()
    return database[collection_name]

@contextmanager
def get_db_session():
    """Context manager for database operations"""
    try:
        database = get_database()
        yield database
    except Exception as e:
        logging.error(f"Database session error: {e}")
        raise

def create_indexes():
    """Create database indexes for optimal performance"""
    try:
        db = get_database()
        
        # Users collection indexes
        users_collection = db[COLLECTIONS['users']]
        users_collection.create_index([("username", ASCENDING)], unique=True)
        users_collection.create_index([("email", ASCENDING)], unique=True)
        users_collection.create_index([("is_active", ASCENDING)])
        users_collection.create_index([("created_at", DESCENDING)])
        
        # User progress collection indexes
        progress_collection = db[COLLECTIONS['user_progress']]
        progress_collection.create_index([("user_id", ASCENDING), ("date", ASCENDING)], unique=True)
        progress_collection.create_index([("user_id", ASCENDING)])
        progress_collection.create_index([("date", DESCENDING)])
        progress_collection.create_index([("completed", ASCENDING)])
        
        # Achievements collection indexes
        achievements_collection = db[COLLECTIONS['achievements']]
        achievements_collection.create_index([("name", ASCENDING)], unique=True)
        achievements_collection.create_index([("requirement_type", ASCENDING)])
        
        # User achievements collection indexes
        user_achievements_collection = db[COLLECTIONS['user_achievements']]
        user_achievements_collection.create_index([("user_id", ASCENDING), ("achievement_id", ASCENDING)], unique=True)
        user_achievements_collection.create_index([("user_id", ASCENDING)])
        user_achievements_collection.create_index([("earned_at", DESCENDING)])
        
        # Recovery keys collection indexes
        recovery_keys_collection = db[COLLECTIONS['recovery_keys']]
        recovery_keys_collection.create_index([("user_id", ASCENDING)])
        recovery_keys_collection.create_index([("key_hash", ASCENDING)])
        recovery_keys_collection.create_index([("created_at", DESCENDING)])
        
        # Quotes collection indexes
        quotes_collection = db[COLLECTIONS['quotes']]
        quotes_collection.create_index([("category", ASCENDING)])
        
        logging.info("Database indexes created successfully")
        
    except Exception as e:
        logging.error(f"Error creating indexes: {e}")
        raise

def initialize_default_data():
    """Initialize default achievements and quotes"""
    try:
        db = get_database()
        
        # Default achievements
        achievements_collection = db[COLLECTIONS['achievements']]
        default_achievements = [
            {
                "name": "First Step",
                "description": "Mark your first day of progress",
                "icon": "🌟",
                "requirement_type": "streak",
                "requirement_value": 1,
                "points_reward": 10
            },
            {
                "name": "Week Warrior",
                "description": "Maintain a 7-day streak",
                "icon": "🔥",
                "requirement_type": "streak",
                "requirement_value": 7,
                "points_reward": 50
            },
            {
                "name": "Consistency Champion",
                "description": "Achieve a 30-day streak",
                "icon": "🏆",
                "requirement_type": "streak",
                "requirement_value": 30,
                "points_reward": 200
            },
            {
                "name": "Wellness Master",
                "description": "Reach a 100-day streak",
                "icon": "👑",
                "requirement_type": "streak",
                "requirement_value": 100,
                "points_reward": 500
            },
            {
                "name": "Monthly Dedication",
                "description": "Complete 20 days in a single month",
                "icon": "📅",
                "requirement_type": "monthly",
                "requirement_value": 20,
                "points_reward": 100
            },
            {
                "name": "Point Collector",
                "description": "Accumulate 1000 total points",
                "icon": "💎",
                "requirement_type": "points",
                "requirement_value": 1000,
                "points_reward": 150
            }
        ]
        
        for achievement in default_achievements:
            try:
                achievements_collection.insert_one(achievement)
            except DuplicateKeyError:
                # Achievement already exists, skip
                pass
        
        # Default motivational quotes
        quotes_collection = db[COLLECTIONS['quotes']]
        default_quotes = [
            {
                "text": "Every day is a new beginning. Take a deep breath and start again.",
                "author": "Unknown",
                "category": "motivation"
            },
            {
                "text": "Progress, not perfection, is the goal.",
                "author": "Unknown", 
                "category": "progress"
            },
            {
                "text": "Small steps every day lead to big changes.",
                "author": "Unknown",
                "category": "consistency"
            },
            {
                "text": "Your only limit is your mindset.",
                "author": "Unknown",
                "category": "mindset"
            },
            {
                "text": "Wellness is not a destination, it's a journey.",
                "author": "Unknown",
                "category": "wellness"
            },
            {
                "text": "Consistency is the key to achieving your goals.",
                "author": "Unknown",
                "category": "consistency"
            },
            {
                "text": "Take care of your body. It's the only place you have to live.",
                "author": "Jim Rohn",
                "category": "health"
            },
            {
                "text": "The groundwork for all happiness is good health.",
                "author": "Leigh Hunt",
                "category": "happiness"
            }
        ]
        
        for quote in default_quotes:
            try:
                quotes_collection.insert_one(quote)
            except DuplicateKeyError:
                # Quote already exists, skip
                pass
        
        logging.info("Default data initialized successfully")
        
    except Exception as e:
        logging.error(f"Error initializing default data: {e}")
        raise

def init_database():
    """Initialize database with collections, indexes, and default data"""
    try:
        # Test connection
        client = get_mongo_client()
        
        # Create indexes
        create_indexes()
        
        # Initialize default data
        initialize_default_data()
        
        logging.info("Database initialized successfully")
        
    except Exception as e:
        logging.error(f"Database initialization failed: {e}")
        raise

def check_database_health() -> bool:
    """Check if database is healthy and accessible"""
    try:
        client = get_mongo_client()
        # Ping the database
        client.admin.command('ping')
        return True
    except Exception as e:
        logging.error(f"Database health check failed: {e}")
        return False

def close_database_connection():
    """Close database connection"""
    global mongo_client, db
    try:
        if mongo_client:
            mongo_client.close()
            mongo_client = None
            db = None
            logging.info("Database connection closed")
    except Exception as e:
        logging.error(f"Error closing database connection: {e}")

# Utility functions for MongoDB ObjectId handling
def str_to_objectid(id_str: str) -> ObjectId:
    """Convert string to ObjectId"""
    try:
        return ObjectId(id_str)
    except Exception:
        raise ValueError(f"Invalid ObjectId: {id_str}")

def objectid_to_str(obj_id: ObjectId) -> str:
    """Convert ObjectId to string"""
    return str(obj_id)

def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize MongoDB document for JSON response"""
    if doc is None:
        return None
    
    serialized = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            if key == '_id':
                serialized['id'] = str(value)
            else:
                serialized[key] = str(value)
        elif isinstance(value, datetime):
            serialized[key] = value.isoformat()
        elif isinstance(value, date):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    
    return serialized

def serialize_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Serialize list of MongoDB documents"""
    return [serialize_doc(doc) for doc in docs] 