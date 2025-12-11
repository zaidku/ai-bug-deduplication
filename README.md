# AI Bug Deduplication

AI-powered duplicate bug detection with semantic similarity, quality filtering, and automated Jira/TP integration.

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-14+-blue.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An automated pipeline that detects duplicate bugs, recurring defects, and low-quality submissions using AI similarity scoring, rule-based filters, and direct integration with databases, Jira, and Test Platforms.

## Features

- **AI-Powered Duplicate Detection**: Uses sentence transformers to generate embeddings and detect similar bugs
- **Quality Checker**: Automatically routes low-quality submissions to a triage queue
- **Similarity Engine**: Hybrid scoring combining semantic similarity and metadata matching
- **Vector Search**: FAISS-based fast similarity search across all bugs
- **External Integrations**: Syncs with Jira and Test Platform
- **QA Override Interface**: Manual review and override capabilities
- **Comprehensive Audit Trail**: Tracks all AI decisions and manual interventions
- **Real-time Metrics**: Monitoring dashboard for system performance

## Architecture

```
┌─────────────────┐
│  Bug Submission │
└────────┬────────┘
         │
         v
┌─────────────────────┐
│  Quality Checker    │
│  - Missing fields   │
│  - Low quality text │
└────────┬────────────┘
         │
         ├─── Low Quality ──→ [Triage Queue]
         │
         v
┌─────────────────────┐
│ Embedding Service   │
│ - Generate vectors  │
└────────┬────────────┘
         │
         v
┌─────────────────────┐
│  Similarity Engine  │
│  - Vector search    │
│  - Metadata match   │
└────────┬────────────┘
         │
         ├─── High Match ──→ [Block Duplicate]
         ├─── Med Match ───→ [Create + Flag]
         └─── No Match ────→ [Create New Bug]
                              │
                              v
                     ┌────────────────┐
                     │ Sync to Jira/TP│
                     └────────────────┘
```

## Installation

### Prerequisites

- Python 3.9+
- PostgreSQL 14+ with pgvector extension
- Redis (for Celery background tasks)

### Setup

1. **Clone and navigate to the project**
   ```bash
   cd bug-deduplication-system
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or
   source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup PostgreSQL**
   ```bash
   # Connect to PostgreSQL
   psql -U postgres
   
   # Create database
   CREATE DATABASE bug_deduplication;
   
   # Enable pgvector extension
   \c bug_deduplication
   CREATE EXTENSION vector;
   ```

5. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

6. **Initialize database**
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   
   # Or use the SQL schema directly
   psql -U postgres -d bug_deduplication -f migrations/schema.sql
   ```

7. **Start services**

   **Terminal 1 - Flask API:**
   ```bash
   python run.py
   ```

   **Terminal 2 - Celery Worker:**
   ```bash
   celery -A app.tasks worker --loglevel=info
   ```

   **Terminal 3 - Celery Beat (Scheduler):**
   ```bash
   celery -A app.tasks beat --loglevel=info
   ```

## API Documentation

### Submit a Bug

**POST** `/api/bugs/`

```json
{
  "title": "App crashes on startup",
  "description": "When I open the app, it immediately crashes",
  "repro_steps": "1. Open app\n2. Wait 2 seconds\n3. App crashes",
  "logs": "Error: NullPointerException at...",
  "severity": "Critical",
  "priority": "High",
  "reporter": "user@example.com",
  "device": "iPhone 14 Pro",
  "os_version": "iOS 17.1",
  "build_version": "1.2.3",
  "region": "US"
}
```

**Responses:**
- `201 Created` - New bug created
- `409 Conflict` - Duplicate detected and blocked
- `400 Bad Request` - Low quality submission

### Get Bug

**GET** `/api/bugs/<bug_id>?include_duplicates=true`

### List Bugs

**GET** `/api/bugs/?status=New&classification_tag=Duplicate&page=1&per_page=50`

### Update Bug

**PATCH** `/api/bugs/<bug_id>`

### QA Operations

**GET** `/api/qa/low-quality` - Get low quality queue

**POST** `/api/qa/low-quality/<id>/approve` - Approve low quality submission

**POST** `/api/qa/low-quality/<id>/reject` - Reject submission

**POST** `/api/qa/bugs/<bug_id>/promote` - Promote duplicate to independent bug

**POST** `/api/qa/bugs/<bug_id>/reclassify` - Reclassify bug

### Monitoring

**GET** `/api/monitoring/stats` - Overall system statistics

**GET** `/api/monitoring/stats/duplicates` - Duplicate detection stats

**GET** `/api/monitoring/stats/regions` - Stats by region

**GET** `/api/monitoring/stats/timeline?days=30` - Timeline statistics

**GET** `/api/monitoring/health` - Health check

## Configuration

Key configuration options in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `SIMILARITY_THRESHOLD` | Threshold to block duplicates | 0.85 |
| `LOW_CONFIDENCE_THRESHOLD` | Threshold to flag for review | 0.70 |
| `MIN_DESCRIPTION_LENGTH` | Minimum description length | 50 |
| `REQUIRE_REPRO_STEPS` | Require reproduction steps | true |
| `EMBEDDING_MODEL` | Sentence transformer model | all-MiniLM-L6-v2 |

## AI Model

The system uses **sentence-transformers** with the `all-MiniLM-L6-v2` model:
- **Embedding Dimension**: 384
- **Performance**: Fast inference, good accuracy
- **Similarity Metric**: Cosine similarity

### Similarity Scoring

The hybrid score combines:
- **Vector Similarity** (70%): Semantic similarity of text content
- **Metadata Similarity** (30%): Matching device, build, region, etc.

## Database Schema

### Core Tables

- **bugs** - Main bug tracking table with embeddings
- **low_quality_queue** - Holds incomplete submissions
- **duplicate_history** - Tracks all duplicate detections
- **audit_log** - Comprehensive audit trail
- **system_metrics** - Performance metrics

### Key Fields

```sql
-- Bug with AI fields
embedding vector(384)      -- Semantic embedding
parent_bug_id integer      -- Link to original bug
match_score float          -- AI confidence score
classification_tag varchar -- Duplicate/Recurring/LowQuality
```

## Jira & Test Platform Integration

The system automatically syncs bugs to external systems:

### Jira Integration

- Creates issues in configured project
- Links duplicates using Jira's issue linking
- Adds labels: `Duplicate`, `Recurring`, `LowQuality`
- Posts comments with AI match scores

### Test Platform Integration

- Creates defects via REST API
- Links related defects
- Tags with classification
- Updates priority for recurring issues

## Quality Rules

Submissions are flagged for low quality if they have:

- Missing or very short title (< 10 chars)
- Missing or short description (< 50 chars)
- Missing reproduction steps (if required)
- Generic titles ("bug", "error", "help")
- Low quality text (excessive repetition, all caps, etc.)
- Missing device/build/region information

## Monitoring & Metrics

Track system performance:

- **Duplicate Prevention Rate**: % of submissions blocked
- **False Positive Rate**: % of duplicates promoted by QA
- **Average Match Score**: Confidence across all detections
- **Top Parent Bugs**: Bugs with most duplicates
- **Quality Issues Distribution**: Common quality problems
- **Timeline Analytics**: Trends over time

## Background Tasks

Celery handles asynchronous operations:

- **Jira Sync**: Sync bugs to Jira
- **TP Sync**: Sync bugs to Test Platform
- **Index Rebuild**: Daily vector index rebuild (2 AM)
- **Metrics Update**: Hourly metrics calculation

## Security Considerations

- API authentication (add JWT/OAuth as needed)
- Rate limiting for bug submissions
- Input validation and sanitization
- SQL injection prevention via ORM
- Cross-region data privacy controls

## Performance Optimization

- Vector index uses HNSW for fast approximate search
- Database indexes on frequently queried fields
- Batch embedding generation
- Connection pooling for database
- Redis caching for frequently accessed data

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/test_duplicate_detector.py
```

## Troubleshooting

### Vector Index Issues

```bash
# Rebuild index manually
python -c "from app import create_app; from app.tasks import rebuild_vector_index; app = create_app(); app.app_context().push(); rebuild_vector_index()"
```

### Database Migration Issues

```bash
# Reset migrations
flask db downgrade
flask db upgrade
```

### Celery Not Running

```bash
# Check Redis connection
redis-cli ping

# Clear Celery queue
celery -A app.tasks purge
```

## Contributing

1. Create feature branch
2. Add tests for new functionality
3. Ensure all tests pass
4. Submit pull request

## Project Structure

```
ai-bug-deduplication/
├── app/
│   ├── api/              # REST API endpoints
│   ├── integrations/     # Jira and TP integrations
│   ├── models/           # Database models
│   ├── services/         # Core business logic
│   └── utils/            # Utility functions
├── migrations/           # Database migrations
├── scripts/              # Utility scripts
├── tests/                # Test suite
├── examples/             # Usage examples
├── docker-compose.yml    # Docker orchestration
├── requirements.txt      # Python dependencies
└── README.md
```

## Documentation

- [Quick Start Guide](QUICKSTART.md) - Get up and running quickly
- [Development Guide](DEVELOPMENT.md) - Development setup and workflows
- [Contributing](CONTRIBUTING.md) - How to contribute
- [Security Policy](SECURITY.md) - Security guidelines
- [Changelog](CHANGELOG.md) - Version history

## Roadmap

- [ ] GraphQL API support
- [ ] Machine learning model fine-tuning
- [ ] Multi-language support for embeddings
- [ ] Advanced analytics dashboard
- [ ] Slack/Teams integration
- [ ] Custom ML model training pipeline

## Citation

If you use this project in your research or production systems, please cite:

```bibtex
@software{ai_bug_deduplication,
  author = {Kurdi, Zaid},
  title = {AI Bug Deduplication},
  year = {2025},
  url = {https://github.com/zaidku/ai-bug-deduplication}
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/)
- Vector search powered by [FAISS](https://github.com/facebookresearch/faiss)
- Embeddings from [Sentence Transformers](https://www.sbert.net/)
- Database extensions from [pgvector](https://github.com/pgvector/pgvector)

## Support

- **Issues**: [GitHub Issues](https://github.com/zaidku/ai-bug-deduplication/issues)
- **Discussions**: [GitHub Discussions](https://github.com/zaidku/ai-bug-deduplication/discussions)
- **Security**: See [SECURITY.md](SECURITY.md)

---

**Maintainer**: [Zaid Kurdi](https://github.com/zaidku)
