"""
Flask application factory
"""

from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flasgger import Swagger

from app.config import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class=Config):
    """Create and configure the Flask application"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)

    # Initialize Swagger API documentation
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/api/docs",
    }
    
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Bug Deduplication System API",
            "description": "AI-powered bug deduplication and classification system",
            "version": "1.0.0",
            "contact": {
                "name": "API Support",
                "url": "https://github.com/zaidku/ai-bug-deduplication",
            },
        },
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT token. Use format: Bearer <token>",
            },
            "ApiKey": {
                "type": "apiKey",
                "name": "X-API-Key",
                "in": "header",
                "description": "API key for authentication",
            },
        },
        "security": [{"Bearer": []}, {"ApiKey": []}],
    }
    
    Swagger(app, config=swagger_config, template=swagger_template)

    # Setup middleware
    from app.middleware.logging import setup_request_logging, setup_error_handlers
    from app.utils.cache import Cache
    
    setup_request_logging(app)
    setup_error_handlers(app)
    
    # Initialize cache
    app.cache = Cache(app.config.get("REDIS_URL", "redis://localhost:6379/0"))

    # Register blueprints
    from app.api.bugs import bugs_bp
    from app.api.monitoring import monitoring_bp
    from app.api.qa_interface import qa_bp
    from app.api.auth import bp as auth_bp

    app.register_blueprint(bugs_bp, url_prefix="/api/bugs")
    app.register_blueprint(qa_bp, url_prefix="/api/qa")
    app.register_blueprint(monitoring_bp, url_prefix="/api/monitoring")
    app.register_blueprint(auth_bp)

    # Initialize services on first request
    with app.app_context():
        from app.services.embedding_service import EmbeddingService
        from app.utils.vector_store import VectorStore

        # Initialize singleton services
        app.embedding_service = EmbeddingService()
        app.vector_store = VectorStore()

    @app.route("/health")
    def health_check():
        return {"status": "healthy", "service": "bug-deduplication-system"}, 200

    return app
