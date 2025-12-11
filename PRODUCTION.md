# Production Deployment Guide

This guide covers deploying the Bug Deduplication System to production.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Authentication Setup](#authentication-setup)
- [Deployment Options](#deployment-options)
- [Monitoring & Observability](#monitoring--observability)
- [Security Considerations](#security-considerations)

## Prerequisites

- Python 3.9+
- PostgreSQL 14+ with pgvector extension
- Redis 6+
- Docker & Docker Compose (recommended)
- SSL/TLS certificates (for HTTPS)

## Environment Configuration

### Required Environment Variables

Create a `.env.production` file:

```bash
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=<generate-with-python-secrets-token-hex-32>
DEBUG=False

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/bugdedup_prod
SQLALCHEMY_POOL_SIZE=20
SQLALCHEMY_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT Authentication
JWT_SECRET_KEY=<generate-with-python-secrets-token-hex-32>
JWT_ACCESS_TOKEN_EXPIRES=3600  # 1 hour

# API Key Settings
API_KEY_PREFIX=bgd_live_

# Rate Limiting
RATE_LIMIT_ENABLED=True
RATE_LIMIT_STORAGE_URL=redis://localhost:6379/1

# Webhook Notifications
WEBHOOK_URLS=https://portal.example.com/webhooks,https://slack-webhook-url
WEBHOOK_SECRET=<generate-webhook-secret>

# External Integrations
JIRA_URL=https://your-company.atlassian.net
JIRA_USERNAME=automation@example.com
JIRA_API_TOKEN=<jira-api-token>
JIRA_PROJECT_KEY=BUGS

TP_API_URL=https://testplatform.example.com/api
TP_API_KEY=<tp-api-key>

# AI/ML Configuration
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
SIMILARITY_THRESHOLD=0.85
LOW_CONFIDENCE_THRESHOLD=0.70

# Quality Checker
MIN_DESCRIPTION_LENGTH=20
REQUIRE_REPRO_STEPS=True
REQUIRE_LOGS=False
MIN_QUALITY_SCORE=0.6

# Monitoring
SENTRY_DSN=<your-sentry-dsn>
PROMETHEUS_ENABLED=True

# CORS
CORS_ORIGINS=https://portal.example.com,https://admin.example.com

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Generate Secrets

```python
import secrets

# Generate SECRET_KEY
print("SECRET_KEY:", secrets.token_hex(32))

# Generate JWT_SECRET_KEY
print("JWT_SECRET_KEY:", secrets.token_hex(32))

# Generate WEBHOOK_SECRET
print("WEBHOOK_SECRET:", secrets.token_hex(16))
```

## Database Setup

### 1. Install pgvector Extension

```sql
-- Connect to PostgreSQL as superuser
psql -U postgres

-- Create database
CREATE DATABASE bugdedup_prod;

-- Connect to the database
\c bugdedup_prod

-- Install pgvector extension
CREATE EXTENSION vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### 2. Run Database Migrations

```bash
# Set environment
export FLASK_APP=run.py
export FLASK_ENV=production

# Run migrations
flask db upgrade

# Verify tables
flask db current
```

### 3. Database Optimization

```sql
-- Create indexes for performance
CREATE INDEX CONCURRENTLY idx_bugs_product ON bugs(product);
CREATE INDEX CONCURRENTLY idx_bugs_status ON bugs(status);
CREATE INDEX CONCURRENTLY idx_bugs_created_at ON bugs(created_at DESC);
CREATE INDEX CONCURRENTLY idx_bugs_duplicate_of ON bugs(duplicate_of_id) WHERE duplicate_of_id IS NOT NULL;

-- Add partial index for active bugs
CREATE INDEX CONCURRENTLY idx_bugs_active 
ON bugs(created_at DESC) 
WHERE status IN ('pending_review', 'approved');

-- Optimize autovacuum
ALTER TABLE bugs SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE bugs SET (autovacuum_analyze_scale_factor = 0.02);
```

## Authentication Setup

### 1. Create Admin API Key

```python
from app import create_app, db
from app.models.auth import APIKey

app = create_app()
with app.app_context():
    # Create admin API key
    admin_key = APIKey.create_key(
        name="Portal Integration - Production",
        role="integration",
        expires_in_days=365
    )
    
    db.session.add(admin_key)
    db.session.commit()
    
    print(f"API Key created: {admin_key.id}")
    print("Save this key securely - it won't be shown again!")
```

### 2. Create JWT Token for Admin User

```bash
curl -X POST https://api.example.com/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin@example.com",
    "password": "your-secure-password",
    "expires_in": 3600
  }'
```

## Deployment Options

### Option 1: Docker Compose (Recommended)

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg14
    environment:
      POSTGRES_DB: bugdedup_prod
      POSTGRES_USER: bugdedup
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - backend
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    networks:
      - backend
    restart: unless-stopped

  web:
    build:
      context: .
      dockerfile: Dockerfile
    command: gunicorn -w 4 -b 0.0.0.0:8000 --timeout 120 --access-logfile - run:app
    environment:
      FLASK_ENV: production
    env_file:
      - .env.production
    volumes:
      - ./logs:/app/logs
    ports:
      - "8000:8000"
    networks:
      - backend
      - frontend
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G

  celery_worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A app.tasks worker --loglevel=info --concurrency=2
    env_file:
      - .env.production
    networks:
      - backend
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G

  celery_beat:
    build:
      context: .
      dockerfile: Dockerfile
    command: celery -A app.tasks beat --loglevel=info
    env_file:
      - .env.production
    networks:
      - backend
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./logs/nginx:/var/log/nginx
    ports:
      - "80:80"
      - "443:443"
    networks:
      - frontend
    depends_on:
      - web
    restart: unless-stopped

networks:
  frontend:
  backend:

volumes:
  postgres_data:
  redis_data:
```

Deploy:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Option 2: Kubernetes

See `kubernetes/` directory for manifests.

```bash
# Apply configurations
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/secrets.yaml
kubectl apply -f kubernetes/configmap.yaml
kubectl apply -f kubernetes/postgres.yaml
kubectl apply -f kubernetes/redis.yaml
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml
kubectl apply -f kubernetes/ingress.yaml
```

## Monitoring & Observability

### 1. Prometheus Metrics

Access metrics at: `https://api.example.com/metrics`

Key metrics:
- `bug_submissions_total` - Total bug submissions
- `duplicate_detections_total` - Duplicates detected
- `low_quality_bugs_total` - Low quality submissions
- `api_request_duration_seconds` - Request latency

### 2. Sentry Error Tracking

Already integrated via `SENTRY_DSN` environment variable.

### 3. Application Logs

```bash
# View logs
docker-compose -f docker-compose.prod.yml logs -f web

# Search logs
grep "ERROR" logs/app.log
```

### 4. Health Checks

```bash
# Application health
curl https://api.example.com/health

# Database connectivity
curl https://api.example.com/api/monitoring/health

# Vector store status
curl -H "Authorization: Bearer <token>" \
  https://api.example.com/api/monitoring/stats
```

## Security Considerations

### 1. SSL/TLS Configuration

Use Let's Encrypt for certificates:

```bash
certbot certonly --webroot -w /var/www/html \
  -d api.example.com \
  --email admin@example.com \
  --agree-tos
```

### 2. Firewall Rules

```bash
# Allow HTTPS
ufw allow 443/tcp

# Allow SSH (change default port)
ufw allow 2222/tcp

# Block direct access to PostgreSQL/Redis
ufw deny 5432/tcp
ufw deny 6379/tcp
```

### 3. API Key Rotation

```python
# Rotate API keys every 90 days
from datetime import datetime, timedelta
from app import create_app, db
from app.models.auth import APIKey

app = create_app()
with app.app_context():
    # Find keys expiring soon
    expiring_soon = APIKey.query.filter(
        APIKey.expires_at < datetime.utcnow() + timedelta(days=7)
    ).all()
    
    for key in expiring_soon:
        print(f"Key '{key.name}' expires soon: {key.expires_at}")
```

### 4. Rate Limiting

Configure per-endpoint limits in code or via environment:

```python
# High rate limit for read operations
@rate_limit(limit=1000, window=3600)

# Low rate limit for write operations
@rate_limit(limit=100, window=3600)

# Strict limit for authentication
@rate_limit(limit=10, window=300)
```

### 5. Input Validation

All endpoints use Pydantic schemas for validation. Ensure schemas are strict.

### 6. SQL Injection Protection

Using SQLAlchemy ORM with parameterized queries. Never use raw SQL with user input.

### 7. XSS Protection

Flask automatically escapes template variables. API responses are JSON only.

## Backup & Recovery

### Database Backups

```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -h localhost -U bugdedup bugdedup_prod | gzip > backups/db_$DATE.sql.gz

# Retain only last 30 days
find backups/ -name "db_*.sql.gz" -mtime +30 -delete
```

### Vector Store Backups

```bash
# Backup FAISS index
cp -r vector_store/ backups/vector_store_$DATE/
```

### Recovery

```bash
# Restore database
gunzip < backups/db_20240115_120000.sql.gz | psql -h localhost -U bugdedup bugdedup_prod

# Restore vector store
cp -r backups/vector_store_20240115_120000/ vector_store/
```

## Performance Tuning

### 1. Database Connection Pooling

Already configured in `config.py`:
- Pool size: 20
- Max overflow: 40

### 2. Redis Caching

Cache frequently accessed data:
- Bug details: 5 minutes
- Statistics: 1 minute
- Search results: 30 seconds

### 3. Gunicorn Workers

```bash
# Calculate workers: (2 * CPU_CORES) + 1
# For 4 CPU cores: 9 workers
gunicorn -w 9 -b 0.0.0.0:8000 --timeout 120 run:app
```

### 4. FAISS Index Optimization

Rebuild index daily during off-peak hours:

```python
# In Celery beat schedule
@celery.task
def rebuild_vector_store_daily():
    """Rebuild FAISS index for better performance"""
    # See app/tasks.py
```

## Troubleshooting

### High Memory Usage

```bash
# Check memory usage
docker stats

# Reduce FAISS index size
# Use IndexIVFFlat instead of IndexFlatIP for large datasets
```

### Slow API Responses

```bash
# Enable query logging
SET log_min_duration_statement = 1000;  # Log queries > 1s

# Check slow queries
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;
```

### Celery Tasks Not Running

```bash
# Check worker status
celery -A app.tasks inspect active

# Check queue length
redis-cli LLEN celery

# Restart workers
docker-compose -f docker-compose.prod.yml restart celery_worker
```

## Scaling

### Horizontal Scaling

Add more web workers:

```yaml
# docker-compose.prod.yml
services:
  web:
    deploy:
      replicas: 3
```

### Load Balancing

Use nginx upstream:

```nginx
upstream backend {
    least_conn;
    server web-1:8000;
    server web-2:8000;
    server web-3:8000;
}
```

### Database Replication

Set up PostgreSQL streaming replication for read replicas.

---

**Next Steps:**
1. Review and customize configuration for your environment
2. Set up monitoring dashboards
3. Configure automated backups
4. Perform load testing
5. Set up alerting for critical issues
