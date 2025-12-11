"""
Configuration settings for the application
"""

import os
from datetime import timedelta


class Config:
    """Base configuration class"""

    # Flask settings
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    # Database settings
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql://localhost/bug_deduplication"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    }

    # AI/ML settings
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
    LOW_CONFIDENCE_THRESHOLD = float(os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.70"))
    VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "384"))

    # FAISS settings
    FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "./data/faiss_index")
    INDEX_REBUILD_SCHEDULE = os.getenv("INDEX_REBUILD_SCHEDULE", "0 2 * * *")

    # Jira settings
    JIRA_URL = os.getenv("JIRA_URL")
    JIRA_USERNAME = os.getenv("JIRA_USERNAME")
    JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
    JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "BUG")

    # Test Platform settings
    TP_API_URL = os.getenv("TP_API_URL")
    TP_API_KEY = os.getenv("TP_API_KEY")
    TP_PROJECT_ID = os.getenv("TP_PROJECT_ID")

    # Redis/Celery settings
    CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Quality rules
    MIN_DESCRIPTION_LENGTH = int(os.getenv("MIN_DESCRIPTION_LENGTH", "50"))
    REQUIRE_REPRO_STEPS = os.getenv("REQUIRE_REPRO_STEPS", "true").lower() == "true"
    REQUIRE_LOGS = os.getenv("REQUIRE_LOGS", "false").lower() == "true"

    # Region settings
    CROSS_REGION_ENABLED = os.getenv("CROSS_REGION_ENABLED", "true").lower() == "true"
    SUPPORTED_REGIONS = os.getenv("SUPPORTED_REGIONS", "US,EU,APAC").split(",")

    # Monitoring
    ENABLE_PROMETHEUS = os.getenv("ENABLE_PROMETHEUS", "true").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


class DevelopmentConfig(Config):
    """Development configuration"""

    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""

    DEBUG = False


class TestConfig(Config):
    """Testing configuration"""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost/bug_deduplication_test"
