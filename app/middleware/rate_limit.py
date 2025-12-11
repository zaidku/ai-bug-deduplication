"""
Rate limiting middleware
"""
from functools import wraps
from flask import request, jsonify
from datetime import datetime, timedelta
import redis
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-based rate limiter"""
    
    def __init__(self, redis_client=None):
        """Initialize rate limiter with Redis client"""
        self.redis_client = redis_client
    
    def is_rate_limited(self, key: str, limit: int, window: int) -> tuple:
        """
        Check if a key is rate limited
        
        Args:
            key: Unique identifier for the rate limit
            limit: Maximum number of requests
            window: Time window in seconds
            
        Returns:
            Tuple of (is_limited, current_count, reset_time)
        """
        if not self.redis_client:
            return False, 0, 0
        
        try:
            current = self.redis_client.get(key)
            
            if current is None:
                # First request
                self.redis_client.setex(key, window, 1)
                return False, 1, window
            
            current = int(current)
            
            if current >= limit:
                ttl = self.redis_client.ttl(key)
                return True, current, ttl
            
            # Increment counter
            self.redis_client.incr(key)
            ttl = self.redis_client.ttl(key)
            
            return False, current + 1, ttl
        
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return False, 0, 0
    
    def get_client_identifier(self):
        """Get unique identifier for the client"""
        # Try to get user ID from auth
        user_id = getattr(request, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # Fall back to API key
        api_key = request.headers.get('X-API-Key')
        if api_key:
            return f"apikey:{api_key[:10]}"
        
        # Fall back to IP address
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        return f"ip:{ip}"


def rate_limit(limit: int = 100, window: int = 3600, key_prefix: str = ""):
    """
    Decorator for rate limiting
    
    Args:
        limit: Maximum requests allowed
        window: Time window in seconds
        key_prefix: Optional prefix for the rate limit key
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                from flask import current_app
                
                # Get Redis client
                redis_url = current_app.config.get('REDIS_URL')
                if not redis_url:
                    logger.warning("Rate limiting disabled: No Redis URL configured")
                    return f(*args, **kwargs)
                
                redis_client = redis.from_url(redis_url)
                limiter = RateLimiter(redis_client)
                
                # Get client identifier
                client_id = limiter.get_client_identifier()
                
                # Create rate limit key
                endpoint = request.endpoint or 'unknown'
                rate_key = f"ratelimit:{key_prefix}:{endpoint}:{client_id}"
                
                # Check rate limit
                is_limited, count, reset_time = limiter.is_rate_limited(
                    rate_key, limit, window
                )
                
                # Add rate limit headers
                response_headers = {
                    'X-RateLimit-Limit': str(limit),
                    'X-RateLimit-Remaining': str(max(0, limit - count)),
                    'X-RateLimit-Reset': str(int((datetime.utcnow() + timedelta(seconds=reset_time)).timestamp())),
                }
                
                if is_limited:
                    logger.warning(f"Rate limit exceeded: {client_id} on {endpoint}")
                    response = jsonify({
                        'error': 'Rate limit exceeded',
                        'message': f'Maximum {limit} requests per {window} seconds',
                        'retry_after': reset_time
                    })
                    response.status_code = 429
                    
                    for header, value in response_headers.items():
                        response.headers[header] = value
                    
                    response.headers['Retry-After'] = str(reset_time)
                    return response
                
                # Execute endpoint
                response = f(*args, **kwargs)
                
                # Add headers to successful response
                if hasattr(response, 'headers'):
                    for header, value in response_headers.items():
                        response.headers[header] = value
                
                return response
            
            except Exception as e:
                logger.error(f"Rate limiting error: {e}", exc_info=True)
                # Don't block request if rate limiting fails
                return f(*args, **kwargs)
        
        return decorated_function
    return decorator
