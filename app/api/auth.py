"""Authentication API endpoints."""

from datetime import timedelta
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app import db
from app.middleware.auth import (
    create_jwt_token,
    generate_api_key,
    hash_api_key,
    require_auth,
)
from app.models.auth import APIKey
from app.utils.exceptions import AuthenticationError, ValidationError

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.route("/token", methods=["POST"])
def create_token():
    """
    Create JWT token for authentication.

    Request:
        {
            "username": "user@example.com",
            "password": "password123",
            "expires_in": 3600  # optional, seconds
        }

    Response:
        {
            "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
    """
    data = request.get_json()

    if not data:
        raise ValidationError("Request body is required")

    username = data.get("username")
    password = data.get("password")
    expires_in = data.get("expires_in", 3600)

    if not username or not password:
        raise ValidationError("Username and password are required")

    # TODO: Implement actual user authentication against database
    # For now, this is a placeholder that accepts any credentials
    # In production, you should:
    # 1. Query User model to find user by username/email
    # 2. Verify password using bcrypt/werkzeug security
    # 3. Check if user is active/enabled

    # Placeholder validation
    if not username or not password:
        raise AuthenticationError("Invalid credentials")

    # Create token with user info
    token = create_jwt_token(
        user_id=username,
        email=username,
        roles=["user"],  # Default role, should come from user record
        expires_delta=timedelta(seconds=expires_in),
    )

    return (
        jsonify(
            {
                "token": token,
                "expires_in": expires_in,
                "token_type": "Bearer",
            }
        ),
        201,
    )


@bp.route("/api-keys", methods=["POST"])
@require_auth(roles=["admin"])
def create_api_key_endpoint():
    """
    Create a new API key (admin only).

    Request:
        {
            "name": "Portal Integration Key",
            "role": "integration",
            "expires_in_days": 365  # optional
        }

    Response:
        {
            "api_key": "bgd_live_abc123...",
            "key_id": "uuid",
            "name": "Portal Integration Key",
            "role": "integration",
            "expires_at": "2025-01-15T10:30:00Z",
            "created_at": "2024-01-15T10:30:00Z"
        }
    """
    data = request.get_json()

    if not data:
        raise ValidationError("Request body is required")

    name = data.get("name")
    role = data.get("role", "integration")
    expires_in_days = data.get("expires_in_days")

    if not name:
        raise ValidationError("API key name is required")

    # Generate API key
    api_key_value = generate_api_key()
    api_key_hash = hash_api_key(api_key_value)

    # Create API key record
    api_key = APIKey.create_key(
        name=name,
        role=role,
        expires_in_days=expires_in_days,
    )

    # Store the hash instead of the actual key
    api_key.key_hash = api_key_hash

    db.session.add(api_key)
    db.session.commit()

    return (
        jsonify(
            {
                "api_key": api_key_value,  # Only returned once!
                "key_id": str(api_key.id),
                "name": api_key.name,
                "role": api_key.role,
                "expires_at": (
                    api_key.expires_at.isoformat() if api_key.expires_at else None
                ),
                "created_at": api_key.created_at.isoformat(),
                "warning": "Save this API key securely. It will not be shown again.",
            }
        ),
        201,
    )


@bp.route("/api-keys", methods=["GET"])
@require_auth(roles=["admin"])
def list_api_keys():
    """
    List all API keys (admin only).

    Response:
        {
            "api_keys": [
                {
                    "key_id": "uuid",
                    "name": "Portal Integration Key",
                    "role": "integration",
                    "is_active": true,
                    "last_used_at": "2024-01-15T10:30:00Z",
                    "last_used_ip": "192.168.1.1",
                    "usage_count": 1523,
                    "created_at": "2024-01-15T10:30:00Z",
                    "expires_at": "2025-01-15T10:30:00Z"
                }
            ],
            "total": 1
        }
    """
    api_keys = APIKey.query.order_by(APIKey.created_at.desc()).all()

    return jsonify(
        {
            "api_keys": [
                {
                    "key_id": str(key.id),
                    "name": key.name,
                    "role": key.role,
                    "is_active": key.is_active,
                    "last_used_at": (
                        key.last_used_at.isoformat() if key.last_used_at else None
                    ),
                    "last_used_ip": key.last_used_ip,
                    "usage_count": key.usage_count,
                    "created_at": key.created_at.isoformat(),
                    "expires_at": (
                        key.expires_at.isoformat() if key.expires_at else None
                    ),
                }
                for key in api_keys
            ],
            "total": len(api_keys),
        }
    )


@bp.route("/api-keys/<key_id>", methods=["DELETE"])
@require_auth(roles=["admin"])
def revoke_api_key(key_id):
    """
    Revoke an API key (admin only).

    Response:
        {
            "message": "API key revoked successfully",
            "key_id": "uuid"
        }
    """
    api_key = APIKey.query.filter_by(id=key_id).first()

    if not api_key:
        raise ValidationError(f"API key {key_id} not found")

    api_key.revoke()
    db.session.commit()

    return jsonify(
        {
            "message": "API key revoked successfully",
            "key_id": str(api_key.id),
        }
    )


@bp.route("/api-keys/stats", methods=["GET"])
@require_auth(roles=["admin"])
def api_key_stats():
    """
    Get API key usage statistics (admin only).

    Response:
        {
            "total_keys": 5,
            "active_keys": 3,
            "expired_keys": 1,
            "revoked_keys": 1,
            "total_requests": 15234,
            "keys_by_role": {
                "integration": 2,
                "admin": 1
            }
        }
    """
    from datetime import datetime

    total_keys = APIKey.query.count()
    active_keys = APIKey.query.filter_by(is_active=True).count()
    expired_keys = APIKey.query.filter(
        APIKey.expires_at < datetime.utcnow(), APIKey.is_active == True
    ).count()
    revoked_keys = APIKey.query.filter_by(is_active=False).count()

    # Get total requests across all keys
    total_requests = db.session.query(func.sum(APIKey.usage_count)).scalar() or 0

    # Get key counts by role
    keys_by_role = {}
    role_counts = (
        db.session.query(APIKey.role, func.count(APIKey.id)).group_by(APIKey.role).all()
    )

    for role, count in role_counts:
        keys_by_role[role] = count

    return jsonify(
        {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "revoked_keys": revoked_keys,
            "total_requests": int(total_requests),
            "keys_by_role": keys_by_role,
        }
    )
