# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-12-11

### Added
- Initial release of AI Bug Deduplication System
- AI-powered duplicate detection using sentence transformers
- Quality checker for incomplete bug submissions
- Hybrid similarity engine (semantic + metadata)
- FAISS vector store for fast similarity search
- PostgreSQL with pgvector extension support
- Jira integration for automatic issue sync
- Test Platform integration
- QA interface for manual overrides
- Low-quality bug triage queue
- Comprehensive audit trail
- Monitoring and metrics API
- Celery background tasks for async operations
- Docker deployment support
- Complete API documentation
- Unit tests and CI/CD pipeline

### Features
- Block duplicate bug submissions above 85% similarity threshold
- Flag potential duplicates between 70-85% similarity
- Detect recurring defects with 3+ duplicate reports
- Route incomplete submissions to triage queue
- Cross-region duplicate detection with normalization
- Real-time metrics and analytics
- Automated index rebuilding
- Export capabilities for audit logs

[1.0.0]: https://github.com/zaidku/ai-bug-deduplication/releases/tag/v1.0.0
