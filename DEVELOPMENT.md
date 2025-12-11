# Development Setup

This guide covers advanced setup and development workflows.

## Prerequisites

- Python 3.9 or higher
- PostgreSQL 14+ with pgvector extension
- Redis 6+
- Git

## Full Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/zaidku/ai-bug-deduplication.git
cd ai-bug-deduplication
```

### 2. Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov flake8 black isort
```

### 3. Database Setup

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create database
CREATE DATABASE bug_deduplication;
\c bug_deduplication

-- Enable pgvector
CREATE EXTENSION vector;

-- Create test database
CREATE DATABASE bug_deduplication_test;
\c bug_deduplication_test
CREATE EXTENSION vector;
\q
```

### 4. Environment Configuration

```bash
cp .env.example .env
# Edit .env with your settings
```

Required settings:
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/bug_deduplication
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
```

### 5. Initialize Database

```bash
python scripts/init_db.py
```

### 6. Run Development Server

```bash
# Terminal 1 - Flask
python run.py

# Terminal 2 - Celery Worker
celery -A app.tasks worker --loglevel=info

# Terminal 3 - Celery Beat
celery -A app.tasks beat --loglevel=info
```

## Development Workflow

### Code Style

This project follows PEP 8 with Black formatting:

```bash
# Format code
black app/

# Sort imports
isort app/

# Check linting
flake8 app/
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test
pytest tests/test_duplicate_detector.py -v

# Watch mode (install pytest-watch)
ptw
```

### Database Migrations

```bash
# Create migration
flask db migrate -m "Description of changes"

# Apply migrations
flask db upgrade

# Rollback
flask db downgrade
```

### Working with Vector Store

```bash
# Rebuild index
python -c "from app import create_app; from app.tasks import rebuild_vector_index; app = create_app(); app.app_context().push(); rebuild_vector_index()"

# Check index stats
python -c "from app import create_app; app = create_app(); app.app_context().push(); print(app.vector_store.get_stats())"
```

## Debugging

### Flask Debug Mode

Set in `.env`:
```env
FLASK_ENV=development
FLASK_DEBUG=1
```

### VS Code Launch Configuration

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Flask",
      "type": "python",
      "request": "launch",
      "module": "flask",
      "env": {
        "FLASK_APP": "run.py",
        "FLASK_ENV": "development"
      },
      "args": ["run", "--no-debugger"],
      "jinja": true
    }
  ]
}
```

### Logging

Adjust log level in `.env`:
```env
LOG_LEVEL=DEBUG
```

## Performance Profiling

```bash
# Install profiling tools
pip install py-spy

# Profile Flask app
py-spy record -o profile.svg -- python run.py

# Memory profiling
pip install memory_profiler
python -m memory_profiler run.py
```

## Docker Development

```bash
# Build and run
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f web

# Execute commands in container
docker-compose exec web python scripts/init_db.py

# Rebuild specific service
docker-compose up --build web

# Clean up
docker-compose down -v
```

## Common Development Tasks

### Add New API Endpoint

1. Add route in `app/api/` blueprint
2. Update models if needed
3. Write tests in `tests/`
4. Update API documentation in README
5. Run tests and commit

### Add New Model Field

1. Update model in `app/models/`
2. Create migration: `flask db migrate -m "Add field"`
3. Review migration file
4. Apply: `flask db upgrade`
5. Update related code and tests

### Modify AI Model

1. Update `app/services/embedding_service.py`
2. Rebuild vector index
3. Test with sample data
4. Update configuration docs

## Troubleshooting

### Port Already in Use

```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:5000 | xargs kill -9
```

### Database Connection Issues

```bash
# Check PostgreSQL status
pg_isready -U postgres

# Check connection
psql -U postgres -d bug_deduplication -c "SELECT 1"
```

### Redis Issues

```bash
# Check Redis
redis-cli ping

# Clear cache
redis-cli FLUSHALL
```

### Vector Index Corruption

```bash
# Delete and rebuild
rm -rf data/faiss_index*
python scripts/init_db.py
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [PostgreSQL pgvector](https://github.com/pgvector/pgvector)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)
- [Sentence Transformers](https://www.sbert.net/)
- [Celery Documentation](https://docs.celeryproject.org/)
