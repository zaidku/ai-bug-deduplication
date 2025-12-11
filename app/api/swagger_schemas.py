"""Swagger/OpenAPI schema definitions for API documentation."""

# Bug submission schema
bug_submission_schema = {
    "type": "object",
    "required": ["title", "description", "product"],
    "properties": {
        "title": {
            "type": "string",
            "example": "Login button not responding on mobile",
            "minLength": 10,
            "maxLength": 200,
        },
        "description": {
            "type": "string",
            "example": "When user clicks login button on iOS Safari, nothing happens. Expected behavior: login form should submit.",
            "minLength": 20,
        },
        "product": {
            "type": "string",
            "example": "Mobile App",
        },
        "component": {
            "type": "string",
            "example": "Authentication",
        },
        "version": {
            "type": "string",
            "example": "2.1.0",
        },
        "severity": {
            "type": "string",
            "enum": ["critical", "major", "minor", "trivial"],
            "example": "major",
        },
        "environment": {
            "type": "string",
            "enum": ["production", "staging", "development", "qa"],
            "example": "production",
        },
        "reporter_email": {
            "type": "string",
            "format": "email",
            "example": "qa@example.com",
        },
        "steps_to_reproduce": {
            "type": "array",
            "items": {"type": "string"},
            "example": [
                "Open mobile app",
                "Navigate to login page",
                "Enter credentials",
                "Click login button",
            ],
        },
        "expected_result": {
            "type": "string",
            "example": "User should be logged in and redirected to dashboard",
        },
        "actual_result": {
            "type": "string",
            "example": "Button click has no effect, user stays on login page",
        },
        "attachments": {
            "type": "array",
            "items": {"type": "string"},
            "example": ["screenshot.png", "console_logs.txt"],
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "example": ["mobile", "ios", "authentication"],
        },
    },
}

# Bug response schema
bug_response_schema = {
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "format": "uuid",
        },
        "title": {"type": "string"},
        "description": {"type": "string"},
        "product": {"type": "string"},
        "component": {"type": "string"},
        "version": {"type": "string"},
        "severity": {"type": "string"},
        "status": {
            "type": "string",
            "enum": [
                "pending_review",
                "approved",
                "rejected",
                "duplicate",
                "in_jira",
                "in_tp",
            ],
        },
        "quality_score": {
            "type": "number",
            "format": "float",
        },
        "is_duplicate": {"type": "boolean"},
        "duplicate_of_id": {
            "type": "string",
            "format": "uuid",
            "nullable": True,
        },
        "similarity_score": {
            "type": "number",
            "format": "float",
            "nullable": True,
        },
        "jira_key": {
            "type": "string",
            "nullable": True,
        },
        "tp_defect_id": {
            "type": "string",
            "nullable": True,
        },
        "created_at": {
            "type": "string",
            "format": "date-time",
        },
        "updated_at": {
            "type": "string",
            "format": "date-time",
        },
    },
}

# Duplicate detection response
duplicate_detected_schema = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "is_duplicate": {"type": "boolean"},
        "original_bug": bug_response_schema,
        "similarity_score": {"type": "number", "format": "float"},
        "reason": {"type": "string"},
    },
}

# Low quality response
low_quality_schema = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "quality_score": {"type": "number", "format": "float"},
        "issues": {
            "type": "array",
            "items": {"type": "string"},
        },
        "bug_id": {"type": "string", "format": "uuid"},
        "status": {"type": "string"},
    },
}

# API key creation request
api_key_request_schema = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {
            "type": "string",
            "example": "Portal Integration Key",
        },
        "role": {
            "type": "string",
            "enum": ["admin", "integration", "user"],
            "example": "integration",
        },
        "expires_in_days": {
            "type": "integer",
            "example": 365,
            "nullable": True,
        },
    },
}

# API key response
api_key_response_schema = {
    "type": "object",
    "properties": {
        "api_key": {
            "type": "string",
            "example": "bgd_live_abc123...",
        },
        "key_id": {
            "type": "string",
            "format": "uuid",
        },
        "name": {"type": "string"},
        "role": {"type": "string"},
        "expires_at": {
            "type": "string",
            "format": "date-time",
            "nullable": True,
        },
        "created_at": {
            "type": "string",
            "format": "date-time",
        },
        "warning": {"type": "string"},
    },
}

# JWT token request
token_request_schema = {
    "type": "object",
    "required": ["username", "password"],
    "properties": {
        "username": {
            "type": "string",
            "example": "user@example.com",
        },
        "password": {
            "type": "string",
            "format": "password",
        },
        "expires_in": {
            "type": "integer",
            "example": 3600,
        },
    },
}

# JWT token response
token_response_schema = {
    "type": "object",
    "properties": {
        "token": {"type": "string"},
        "expires_in": {"type": "integer"},
        "token_type": {"type": "string"},
    },
}

# Error response schema
error_response_schema = {
    "type": "object",
    "properties": {
        "error": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "details": {"type": "object", "nullable": True},
            },
        },
        "status": {"type": "integer"},
        "timestamp": {"type": "string", "format": "date-time"},
        "request_id": {"type": "string"},
    },
}

# Statistics response
stats_response_schema = {
    "type": "object",
    "properties": {
        "total_bugs": {"type": "integer"},
        "duplicates_detected": {"type": "integer"},
        "duplicates_blocked": {"type": "integer"},
        "low_quality_bugs": {"type": "integer"},
        "avg_quality_score": {"type": "number", "format": "float"},
        "avg_similarity_score": {"type": "number", "format": "float"},
        "bugs_by_status": {"type": "object"},
        "bugs_by_severity": {"type": "object"},
        "recent_duplicates": {
            "type": "array",
            "items": bug_response_schema,
        },
    },
}
