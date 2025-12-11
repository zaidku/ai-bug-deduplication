# Quick Start Guide

## Local Development Setup (Windows)

### 1. Install Prerequisites

**Install PostgreSQL with pgvector:**
```powershell
# Download and install PostgreSQL 14+ from https://www.postgresql.org/download/windows/
# After installation, enable pgvector extension
```

**Install Redis:**
```powershell
# Download Redis from https://github.com/microsoftarchive/redis/releases
# Or use WSL: wsl --install
# Then in WSL: sudo apt install redis-server
```

### 2. Setup Project

```powershell
# Clone/navigate to project
cd bug-deduplication-system

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Database

```powershell
# Connect to PostgreSQL (default password is what you set during installation)
psql -U postgres

# In PostgreSQL shell:
CREATE DATABASE bug_deduplication;
\c bug_deduplication
CREATE EXTENSION vector;
\q
```

### 4. Configure Environment

```powershell
# Copy example environment file
copy .env.example .env

# Edit .env file with your settings (use notepad or any editor)
notepad .env
```

**Minimum required settings in .env:**
```
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/bug_deduplication
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-random-secret-key
FLASK_ENV=development
```

### 5. Initialize Database

```powershell
# Run initialization script
python scripts\init_db.py
```

### 6. Start Services

**Terminal 1 - Start Redis (if using WSL):**
```powershell
wsl
redis-server
```

**Terminal 2 - Start Flask API:**
```powershell
cd bug-deduplication-system
.\venv\Scripts\activate
python run.py
```

**Terminal 3 - Start Celery Worker:**
```powershell
cd bug-deduplication-system
.\venv\Scripts\activate
celery -A app.tasks worker --loglevel=info --pool=solo
```

**Terminal 4 - Start Celery Beat (optional for scheduled tasks):**
```powershell
cd bug-deduplication-system
.\venv\Scripts\activate
celery -A app.tasks beat --loglevel=info
```

### 7. Test the API

Open browser and visit:
- http://localhost:5000/health - Health check
- http://localhost:5000/api/monitoring/stats - System stats

**Or use PowerShell:**
```powershell
# Submit a test bug
$body = @{
    title = "Test bug"
    description = "This is a test bug submission to verify the system is working correctly"
    repro_steps = "1. Test step 1\n2. Test step 2"
    reporter = "test@example.com"
    device = "Test Device"
    build_version = "1.0.0"
    region = "US"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5000/api/bugs/" -Method POST -Body $body -ContentType "application/json"
```

## Docker Setup (Alternative)

If you prefer using Docker:

```powershell
# Build and start all services
docker-compose up --build

# Initialize database (in another terminal)
docker-compose exec web python scripts/init_db.py

# View logs
docker-compose logs -f web

# Stop services
docker-compose down
```

## Common Issues

### Issue: PostgreSQL connection failed
**Solution:** Check if PostgreSQL service is running:
```powershell
# Check PostgreSQL service status
Get-Service -Name postgresql*

# Start if not running
Start-Service postgresql-x64-14  # Adjust version number
```

### Issue: Redis connection failed
**Solution:** 
```powershell
# If using WSL
wsl
sudo service redis-server start

# Or install Redis for Windows
```

### Issue: Import errors
**Solution:** Make sure virtual environment is activated:
```powershell
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Issue: Celery won't start on Windows
**Solution:** Use the `--pool=solo` flag:
```powershell
celery -A app.tasks worker --loglevel=info --pool=solo
```

## Next Steps

1. **Test the API** - Use the examples in `examples/api_usage.py`
2. **Configure Jira** - Add Jira credentials to `.env`
3. **Configure TP** - Add Test Platform credentials to `.env`
4. **Review Documentation** - Read the full `README.md`

## Support

If you encounter issues, check:
1. All services are running (PostgreSQL, Redis, Flask, Celery)
2. Database connection string in `.env` is correct
3. Virtual environment is activated
4. All dependencies are installed

For detailed API documentation, see [README.md](README.md)
