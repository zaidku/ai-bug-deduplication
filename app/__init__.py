"""
Flask application factory
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
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
    
    # Register blueprints
    from app.api.bugs import bugs_bp
    from app.api.qa_interface import qa_bp
    from app.api.monitoring import monitoring_bp
    
    app.register_blueprint(bugs_bp, url_prefix='/api/bugs')
    app.register_blueprint(qa_bp, url_prefix='/api/qa')
    app.register_blueprint(monitoring_bp, url_prefix='/api/monitoring')
    
    # Initialize services on first request
    with app.app_context():
        from app.services.embedding_service import EmbeddingService
        from app.utils.vector_store import VectorStore
        
        # Initialize singleton services
        app.embedding_service = EmbeddingService()
        app.vector_store = VectorStore()
    
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'bug-deduplication-system'}, 200
    
    return app
