# Wellness Tracker Backend API

A comprehensive FastAPI backend for the Wellness Tracker application with MongoDB database, JWT authentication, and secure user data management.

## Features

- **User Authentication**: JWT-based authentication with access and refresh tokens
- **Progress Tracking**: Track daily wellness progress with streak calculations
- **Achievement System**: Automated achievement detection and rewards
- **Leaderboards**: Anonymous leaderboards with multiple ranking types
- **Recovery Key System**: Reusable recovery keys for password reset
- **Security**: Password hashing, secure headers, CORS protection
- **Database**: MongoDB with collections and indexing

## Prerequisites

- Python 3.8+
- MongoDB 4.4+
- pip or pipenv

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up MongoDB:**
   
   **Option A: Local MongoDB**
   ```bash
   # Install MongoDB (Ubuntu/Debian)
   sudo apt update
   sudo apt install -y mongodb
   sudo systemctl start mongodb
   sudo systemctl enable mongodb
   
   # Install MongoDB (macOS with Homebrew)
   brew tap mongodb/brew
   brew install mongodb-community
   brew services start mongodb/brew/mongodb-community
   ```
   
   **Option B: MongoDB Atlas (Cloud)**
   - Create account at https://cloud.mongodb.com
   - Create a cluster and get connection string

3. **Configure environment variables:**
   
   Create a `.env` file in the backend directory with:
   ```env
   # MongoDB Configuration
   MONGO_DB_URI=mongodb://localhost:27017
   DATABASE_NAME=wellness_tracker

   # JWT Configuration (generate a secure secret key)
   JWT_SECRET_KEY=your_super_secret_jwt_key_here_make_it_long_and_random
   JWT_ALGORITHM=HS256
   JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
   JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

   # API Configuration
   PROJECT_NAME=Wellness Tracker API
   ```

   **For MongoDB Atlas:**
   ```env
   MONGO_DB_URI=mongodb+srv://username:password@cluster.mongodb.net/
   DATABASE_NAME=wellness_tracker
   ```

4. **Initialize the database:**
   The database will be automatically initialized when you first run the application.

## Running the Application

### Development Server
```bash
python main.py
```
or
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Production Server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at:
- **API Root**: http://127.0.0.1:8000
- **Interactive Docs**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc
- **Health Check**: http://127.0.0.1:8000/health

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user (returns recovery keys)
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user info
- `POST /api/v1/auth/logout` - User logout
- `POST /api/v1/auth/recover-password` - Reset password using recovery key
- `POST /api/v1/auth/validate-password` - Validate password strength

### Wellness Tracking
- `POST /api/v1/wellness/progress` - Mark daily progress
- `GET /api/v1/wellness/progress` - Get user progress
- `GET /api/v1/wellness/progress/monthly` - Get monthly progress
- `GET /api/v1/wellness/achievements` - Get all achievements
- `GET /api/v1/wellness/achievements/user` - Get user achievements
- `POST /api/v1/wellness/achievements/check` - Check for new achievements
- `GET /api/v1/wellness/leaderboard` - Get leaderboard
- `GET /api/v1/wellness/leaderboard/rank` - Get user rank
- `GET /api/v1/wellness/stats/user` - Get user statistics
- `GET /api/v1/wellness/quotes` - Get motivational quotes

## Database Collections

### Users Collection
```json
{
  "_id": "ObjectId",
  "username": "string (unique)",
  "email": "string (unique)",
  "password": "string (hashed)",
  "current_streak": "number",
  "best_streak": "number",
  "total_points": "number",
  "is_active": "boolean",
  "created_at": "datetime",
  "last_progress_date": "date"
}
```

### User Progress Collection
```json
{
  "_id": "ObjectId",
  "user_id": "string",
  "date": "date",
  "completed": "boolean",
  "notes": "string",
  "points_earned": "number",
  "created_at": "datetime"
}
```

### Achievements Collection
```json
{
  "_id": "ObjectId",
  "name": "string",
  "description": "string",
  "icon": "string",
  "requirement_type": "string",
  "requirement_value": "number",
  "points_reward": "number"
}
```

### User Achievements Collection
```json
{
  "_id": "ObjectId",
  "user_id": "string",
  "achievement_id": "ObjectId",
  "earned_at": "datetime"
}
```

### Recovery Keys Collection
```json
{
  "_id": "ObjectId",
  "user_id": "string",
  "key_hash": "string",
  "key_display": "string",
  "is_used": "boolean",
  "used_at": "datetime",
  "created_at": "datetime"
}
```

### Quotes Collection
```json
{
  "_id": "ObjectId",
  "text": "string",
  "author": "string",
  "category": "string"
}
```

## Security Features

- **Password Hashing**: bcrypt with salt
- **JWT Tokens**: Access and refresh token system
- **Recovery Keys**: Reusable recovery keys for password reset
- **CORS Protection**: Configured for frontend domains
- **Security Headers**: XSS, CSRF, and other security headers
- **Input Validation**: Pydantic models for request validation
- **MongoDB Injection Protection**: Secure query operations

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGO_DB_URI` | MongoDB connection string | mongodb://localhost:27017 |
| `DATABASE_NAME` | Database name | wellness_tracker |
| `JWT_SECRET_KEY` | JWT signing key | (required) |
| `JWT_ALGORITHM` | JWT algorithm | HS256 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token expiry | 30 |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token expiry | 7 |
| `PROJECT_NAME` | API project name | Wellness Tracker API |

## Development

### Adding New Features

1. **Database Changes**: Update `database.py` with new collections/indexes
2. **Models**: Add Pydantic models and database operations in `models.py`
3. **Routes**: Create new endpoints in appropriate route files
4. **Authentication**: Use `get_current_user` dependency for protected routes

### Testing Database Connection

```bash
python -c "from database import check_database_health; print('Success' if check_database_health() else 'Failed')"
```

### Manual Database Initialization

```bash
python -c "from database import init_database; init_database(); print('Database initialized')"
```

## Default Data

The application automatically creates:

### Default Achievements
- **First Step**: Mark your first day of progress (10 points)
- **Week Warrior**: Maintain a 7-day streak (50 points)
- **Consistency Champion**: Achieve a 30-day streak (200 points)
- **Wellness Master**: Reach a 100-day streak (500 points)
- **Monthly Dedication**: Complete 20 days in a single month (100 points)
- **Point Collector**: Accumulate 1000 total points (150 points)

### Default Quotes
- Various motivational quotes across different categories
- Random quotes served via API endpoint

## Troubleshooting

### Database Connection Issues
1. Verify MongoDB is running: `sudo systemctl status mongodb`
2. Check connection string in `.env`
3. For Atlas: verify network access and credentials
4. Check firewall/network settings

### Import Errors
1. Ensure all dependencies are installed: `pip install -r requirements.txt`
2. Check Python path and working directory
3. Install MongoDB driver: `pip install pymongo`

### JWT Token Issues
1. Verify JWT_SECRET_KEY is set and consistent
2. Check token expiration settings
3. Ensure frontend sends tokens in Authorization header

### Recovery Key Issues
1. Keys are reusable and never expire
2. 10 keys generated per user during registration
3. Keys are SHA256 hashed in database for security

## Contributing

1. Follow PEP 8 style guidelines
2. Add appropriate error handling and logging
3. Update documentation for new features
4. Test database operations thoroughly

## License

This project is licensed under the MIT License. 