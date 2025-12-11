"""
Authentication and authorization middleware
"""
from functools import wraps
from flask import request, jsonify, current_app
import jwt
from datetime import datetime, timedelta
import hashlib
import secrets
from app import db
from app.models.audit import AuditLog
import logging

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Authentication failed"""
    pass


class AuthorizationError(Exception):
    """Authorization failed"""
    pass


def generate_api_key():
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Verify an API key against its hash"""
    return hash_api_key(provided_key) == stored_hash


def create_jwt_token(user_id: str, role: str = "user", expires_in: int = 3600):
    """
    Create a JWT token
    
    Args:
        user_id: User identifier
        role: User role (user, qa, admin, bot)
        expires_in: Token expiration in seconds
        
    Returns:
        JWT token string
    """
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(seconds=expires_in),
        "iat": datetime.utcnow(),
    }
    
    token = jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm="HS256"
    )
    
    return token


def verify_jwt_token(token: str):
    """
    Verify and decode a JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload
        
    Raises:
        AuthenticationError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")


def get_auth_from_request():
    """
    Extract authentication from request
    
    Returns:
        Tuple of (auth_type, credentials, metadata)
    """
    # Check for API Key in header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return "api_key", api_key, {"source": "header"}
    
    # Check for Bearer token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        return "jwt", token, {"source": "bearer"}
    
    # Check for Basic auth
    if auth_header and auth_header.startswith("Basic "):
        return "basic", auth_header.split(" ")[1], {"source": "basic"}
    
    return None, None, {}


def detect_bot_request():
    """
    Detect if request is from an automated bot/system
    
    Returns:
        Dict with bot detection results
    """
    user_agent = request.headers.get("User-Agent", "").lower()
    
    # Bot indicators
    bot_keywords = [
        "bot", "crawler", "spider", "scraper", "automation",
        "curl", "wget", "python-requests", "postman", "insomnia",
        "automated", "jenkins", "circleci", "github-actions"
    ]
    
    is_bot = any(keyword in user_agent for keyword in bot_keywords)
    
    # Check for automation headers
    automation_headers = {
        "X-Automated": request.headers.get("X-Automated"),
        "X-Bot-Name": request.headers.get("X-Bot-Name"),
        "X-CI-Build": request.headers.get("X-CI-Build"),
    }
    
    has_automation_headers = any(automation_headers.values())
    
    return {
        "is_bot": is_bot or has_automation_headers,
        "user_agent": request.headers.get("User-Agent"),
        "automation_headers": {k: v for k, v in automation_headers.items() if v},
        "confidence": "high" if has_automation_headers else ("medium" if is_bot else "low")
    }


def extract_environment_context():
    """
    Extract environment and context from request
    
    Returns:
        Dict with environment information
    """
    return {
        "ip_address": request.headers.get("X-Forwarded-For", request.remote_addr),
        "user_agent": request.headers.get("User-Agent"),
        "referer": request.headers.get("Referer"),
        "origin": request.headers.get("Origin"),
        "environment": request.headers.get("X-Environment", "production"),
        "client_version": request.headers.get("X-Client-Version"),
        "request_id": request.headers.get("X-Request-ID"),
        "correlation_id": request.headers.get("X-Correlation-ID"),
    }


def require_auth(roles=None):
    """
    Decorator to require authentication
    
    Args:
        roles: List of allowed roles (optional)
    """
    if roles is None:
        roles = []
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                auth_type, credentials, metadata = get_auth_from_request()
                
                if not auth_type:
                    return jsonify({
                        "error": "Authentication required",
                        "message": "Please provide valid authentication credentials"
                    }), 401
                
                # Verify based on auth type
                if auth_type == "jwt":
                    payload = verify_jwt_token(credentials)
                    user_id = payload.get("user_id")
                    user_role = payload.get("role", "user")
                    
                elif auth_type == "api_key":
                    # Verify API key against database
                    from app.models.auth import APIKey
                    api_key_record = APIKey.verify_key(credentials)
                    
                    if not api_key_record:
                        raise AuthenticationError("Invalid API key")
                    
                    user_id = api_key_record.user_id
                    user_role = api_key_record.role
                    
                    # Update last used
                    api_key_record.record_usage(request.remote_addr)
                
                else:
                    raise AuthenticationError("Unsupported authentication method")
                
                # Check role authorization
                if roles and user_role not in roles:
                    raise AuthorizationError(
                        f"Role '{user_role}' not authorized. Required: {roles}"
                    )
                
                # Add user context to request
                request.user_id = user_id
                request.user_role = user_role
                request.auth_type = auth_type
                
                # Detect bot
                request.bot_info = detect_bot_request()
                
                # Extract environment
                request.environment_context = extract_environment_context()
                
                # Log authentication
                logger.info(
                    f"Authenticated request: user={user_id}, role={user_role}, "
                    f"type={auth_type}, bot={request.bot_info['is_bot']}"
                )
                
                return f(*args, **kwargs)
            
            except AuthenticationError as e:
                logger.warning(f"Authentication failed: {e}")
                return jsonify({
                    "error": "Authentication failed",
                    "message": str(e)
                }), 401
            
            except AuthorizationError as e:
                logger.warning(f"Authorization failed: {e}")
                return jsonify({
                    "error": "Authorization failed",
                    "message": str(e)
                }), 403
            
            except Exception as e:
                logger.error(f"Auth error: {e}", exc_info=True)
                return jsonify({
                    "error": "Authentication error",
                    "message": "An error occurred during authentication"
                }), 500
        
        return decorated_function
    return decorator


def optional_auth(f):
    """
    Decorator for optional authentication
    Sets user context if auth is provided, but doesn't require it
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            auth_type, credentials, metadata = get_auth_from_request()
            
            if auth_type:
                if auth_type == "jwt":
                    payload = verify_jwt_token(credentials)
                    request.user_id = payload.get("user_id")
                    request.user_role = payload.get("role", "user")
                elif auth_type == "api_key":
                    from app.models.auth import APIKey
                    api_key_record = APIKey.verify_key(credentials)
                    if api_key_record:
                        request.user_id = api_key_record.user_id
                        request.user_role = api_key_record.role
            
            # Always set bot detection and environment
            request.bot_info = detect_bot_request()
            request.environment_context = extract_environment_context()
            
        except Exception as e:
            logger.warning(f"Optional auth failed: {e}")
            request.user_id = None
            request.user_role = "anonymous"
        
        return f(*args, **kwargs)
    
    return decorated_function
