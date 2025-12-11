# Setup Instructions

cd bug-deduplication-system

# Initialize Git repository
git init
git add .
git commit -m "Initial commit: AI Bug Deduplication System

- Complete Flask-based bug deduplication system
- AI-powered duplicate detection with sentence transformers
- Quality checker and triage queue
- FAISS vector store for similarity search
- Jira and Test Platform integrations
- QA override interface
- Comprehensive monitoring and metrics
- Docker deployment support
- Full test suite and CI/CD"

# Add remote repository
git remote add origin https://github.com/zaidku/ai-bug-deduplication.git

# Create main branch and push
git branch -M main
git push -u origin main

# Optional: Create develop branch for active development
git checkout -b develop
git push -u origin develop
git checkout main

# Done! Your repository is now available at:
# https://github.com/zaidku/ai-bug-deduplication
