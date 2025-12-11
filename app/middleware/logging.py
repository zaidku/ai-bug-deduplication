"""
Request/Response logging middleware
"""
from flask import request, g
import time
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


def setup_request_logging(app):
    """Setup request/response logging"""
    
    @app.before_request
    def before_request():
        """Log request details"""
        g.start_time = time.time()
        g.request_id = request.headers.get('X-Request-ID', f"req_{int(time.time()*1000)}")
        
        # Log request
        logger.info(
            f"Request started",
            extra={
                'request_id': g.request_id,
                'method': request.method,
                'path': request.path,
                'ip': request.headers.get('X-Forwarded-For', request.remote_addr),
                'user_agent': request.headers.get('User-Agent'),
                'user_id': getattr(request, 'user_id', None),
            }
        )
    
    @app.after_request
    def after_request(response):
        """Log response details"""
        if hasattr(g, 'start_time'):
            elapsed = time.time() - g.start_time
            
            logger.info(
                f"Request completed",
                extra={
                    'request_id': g.request_id,
                    'method': request.method,
                    'path': request.path,
                    'status': response.status_code,
                    'duration_ms': round(elapsed * 1000, 2),
                    'user_id': getattr(request, 'user_id', None),
                }
            )
            
            # Add timing header
            response.headers['X-Request-ID'] = g.request_id
            response.headers['X-Response-Time'] = f"{elapsed:.3f}s"
        
        return response
    
    @app.teardown_request
    def teardown_request(exception=None):
        """Log any errors"""
        if exception:
            logger.error(
                f"Request failed",
                extra={
                    'request_id': getattr(g, 'request_id', 'unknown'),
                    'exception': str(exception),
                },
                exc_info=True
            )


def setup_error_handlers(app):
    """Setup global error handlers"""
    
    from app.utils.exceptions import BugDeduplicationError
    
    @app.errorhandler(BugDeduplicationError)
    def handle_custom_error(error):
        """Handle custom application errors"""
        response = error.to_dict()
        return response, error.status_code
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 errors"""
        return {
            'error': 'NotFound',
            'message': 'The requested resource was not found'
        }, 404
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        """Handle 500 errors"""
        logger.error(f"Internal server error: {error}", exc_info=True)
        return {
            'error': 'InternalServerError',
            'message': 'An internal server error occurred'
        }, 500
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle unexpected errors"""
        logger.error(f"Unexpected error: {error}", exc_info=True)
        return {
            'error': 'UnexpectedError',
            'message': 'An unexpected error occurred'
        }, 500
