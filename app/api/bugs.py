"""
Bug submission and management API endpoints with authentication and bot detection
"""

import logging
from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request
from flasgger import swag_from

from app import db
from app.middleware.auth import (
    detect_bot_request,
    extract_environment_context,
    optional_auth,
    require_auth,
)
from app.middleware.rate_limit import rate_limit
from app.models.audit import AuditLog
from app.models.bug import Bug
from app.models.duplicate import DuplicateHistory
from app.services.duplicate_detector import DuplicateDetector
from app.services.quality_checker import QualityChecker
from app.services.similarity_engine import SimilarityEngine
from app.utils.exceptions import (
    DuplicateResourceError,
    ResourceNotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)

bugs_bp = Blueprint("bugs", __name__)


def get_duplicate_detector():
    """Get or create duplicate detector instance"""
    if not hasattr(current_app, "duplicate_detector"):
        quality_checker = QualityChecker(
            min_description_length=current_app.config["MIN_DESCRIPTION_LENGTH"],
            require_repro_steps=current_app.config["REQUIRE_REPRO_STEPS"],
            require_logs=current_app.config["REQUIRE_LOGS"],
        )

        similarity_engine = SimilarityEngine(
            current_app.embedding_service, current_app.vector_store
        )

        current_app.duplicate_detector = DuplicateDetector(
            current_app.embedding_service,
            similarity_engine,
            quality_checker,
            current_app.vector_store,
            similarity_threshold=current_app.config["SIMILARITY_THRESHOLD"],
            low_confidence_threshold=current_app.config["LOW_CONFIDENCE_THRESHOLD"],
        )

    return current_app.duplicate_detector


@bugs_bp.route("/", methods=["POST"])
@rate_limit(limit=100, window=3600)  # 100 requests per hour
@require_auth(roles=["admin", "integration", "user"])
def create_bug():
    """
    Submit a new bug report with duplicate detection and quality validation.

    This endpoint validates the bug submission, detects potential duplicates using AI,
    and tracks the submission context (user, environment, bot detection).

    ---
    tags:
      - Bugs
    security:
      - Bearer: []
      - ApiKey: []
    parameters:
      - in: body
        name: body
        description: Bug report details
        required: true
        schema:
          type: object
          required:
            - title
            - description
            - product
          properties:
            title:
              type: string
              example: "Login button not responding on mobile"
              minLength: 10
              maxLength: 200
            description:
              type: string
              example: "When user clicks login button on iOS Safari, nothing happens."
              minLength: 20
            product:
              type: string
              example: "Mobile App"
            component:
              type: string
              example: "Authentication"
            version:
              type: string
              example: "2.1.0"
            severity:
              type: string
              enum: [critical, major, minor, trivial]
            environment:
              type: string
              enum: [production, staging, development, qa]
            reporter_email:
              type: string
              format: email
            steps_to_reproduce:
              type: array
              items:
                type: string
            expected_result:
              type: string
            actual_result:
              type: string
    responses:
      201:
        description: Bug created successfully
        schema:
          type: object
          properties:
            id:
              type: string
              format: uuid
            title:
              type: string
            status:
              type: string
            quality_score:
              type: number
      409:
        description: Duplicate bug blocked
        schema:
          type: object
          properties:
            message:
              type: string
            is_duplicate:
              type: boolean
            original_bug:
              type: object
            similarity_score:
              type: number
      400:
        description: Low quality submission
        schema:
          type: object
          properties:
            message:
              type: string
            quality_score:
              type: number
            issues:
              type: array
              items:
                type: string
    """
    data = request.get_json()

    if not data:
        raise ValidationError("Request body is required")

    # Extract environment and bot context
    env_context = extract_environment_context()
    is_bot = detect_bot_request()

    # Get authenticated user info from g (set by @require_auth decorator)
    user_id = getattr(g, "user_id", None)
    api_key_id = getattr(g, "api_key_id", None)

    # Validate required fields
    required_fields = ["title", "description", "product"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    # Get duplicate detector
    detector = get_duplicate_detector()

    # Prepare bug data
    bug_data = {
        "title": data["title"],
        "description": data["description"],
        "product": data["product"],
        "component": data.get("component"),
        "version": data.get("version"),
        "severity": data.get("severity", "minor"),
        "environment": data.get("environment", "production"),
        "reporter_email": data.get("reporter_email"),
        "steps_to_reproduce": data.get("steps_to_reproduce", []),
        "expected_result": data.get("expected_result"),
        "actual_result": data.get("actual_result"),
        "attachments": data.get("attachments", []),
        "tags": data.get("tags", []),
        # Add tracking context
        "submitted_by": user_id,
        "submitted_via_api_key": api_key_id,
        "submission_ip": env_context.get("ip_address"),
        "user_agent": env_context.get("user_agent"),
        "is_automated": is_bot,
        "client_version": env_context.get("client_version"),
    }

    # Process through duplicate detection
    result = detector.process_incoming_bug(bug_data)

    # Log the submission
    audit_log = AuditLog(
        action="bug_submitted",
        user_id=user_id,
        bug_id=str(result["bug"].id) if result.get("bug") else None,
        details={
            "is_duplicate": result.get("is_duplicate", False),
            "is_bot": is_bot,
            "quality_score": result.get("quality_score"),
            "similarity_score": result.get("similarity_score"),
            "status": result.get("status"),
        },
        ip_address=env_context.get("ip_address"),
    )
    db.session.add(audit_log)
    db.session.commit()

    # Handle different outcomes
    if result["status"] == "blocked_duplicate":
        # Return 409 Conflict for blocked duplicates
        raise DuplicateResourceError(
            message=f"This bug is a duplicate of an existing issue",
            details={
                "is_duplicate": True,
                "original_bug": {
                    "id": str(result["duplicate_of"].id),
                    "title": result["duplicate_of"].title,
                    "jira_key": result["duplicate_of"].jira_key,
                },
                "similarity_score": result["similarity_score"],
                "reason": "Similarity score above blocking threshold (85%)",
            },
        )

    elif result["status"] == "low_quality":
        # Return 400 Bad Request for low quality
        response = {
            "message": "Bug submission has quality issues and requires QA review",
            "quality_score": result["quality_score"],
            "issues": result["issues"],
            "bug_id": str(result["bug"].id),
            "status": result["status"],
        }
        return jsonify(response), 400

    # Success - bug created
    bug = result["bug"]
    response = {
        "id": str(bug.id),
        "title": bug.title,
        "status": bug.status,
        "quality_score": bug.quality_score,
        "is_duplicate": bug.is_duplicate,
        "similarity_score": bug.similarity_score,
        "duplicate_of_id": str(bug.duplicate_of_id) if bug.duplicate_of_id else None,
        "created_at": bug.created_at.isoformat(),
        "is_automated_submission": is_bot,
    }

    return jsonify(response), 201


@bugs_bp.route("/<bug_id>", methods=["GET"])
@rate_limit(limit=1000, window=3600)  # 1000 requests per hour for reads
@optional_auth()
def get_bug(bug_id):
    """
    Get bug details by ID.

    ---
    tags:
      - Bugs
    parameters:
      - name: bug_id
        in: path
        type: string
        required: true
        description: Bug UUID
      - name: include_duplicates
        in: query
        type: boolean
        description: Include duplicate bug IDs
    responses:
      200:
        description: Bug details
      404:
        description: Bug not found
    """
    bug = Bug.query.get(bug_id)

    if not bug:
        raise ResourceNotFoundError(f"Bug with ID {bug_id} not found")

    include_duplicates = (
        request.args.get("include_duplicates", "false").lower() == "true"
    )

    response = {
        "id": str(bug.id),
        "title": bug.title,
        "description": bug.description,
        "product": bug.product,
        "component": bug.component,
        "version": bug.version,
        "severity": bug.severity,
        "environment": bug.environment,
        "status": bug.status,
        "quality_score": bug.quality_score,
        "is_duplicate": bug.is_duplicate,
        "duplicate_of_id": str(bug.duplicate_of_id) if bug.duplicate_of_id else None,
        "similarity_score": bug.similarity_score,
        "jira_key": bug.jira_key,
        "tp_defect_id": bug.tp_defect_id,
        "created_at": bug.created_at.isoformat(),
        "updated_at": bug.updated_at.isoformat(),
    }

    if include_duplicates:
        duplicates = Bug.query.filter_by(duplicate_of_id=bug.id).all()
        response["duplicate_bugs"] = [
            {"id": str(d.id), "title": d.title, "similarity_score": d.similarity_score}
            for d in duplicates
        ]

    return jsonify(response)


@bugs_bp.route("/<bug_id>/duplicates", methods=["GET"])
@rate_limit(limit=500, window=3600)
@optional_auth()
def get_bug_duplicates(bug_id):
    """
    Get all duplicates of a specific bug.

    ---
    tags:
      - Bugs
    parameters:
      - name: bug_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: List of duplicate bugs
      404:
        description: Bug not found
    """
    bug = Bug.query.get(bug_id)

    if not bug:
        raise ResourceNotFoundError(f"Bug with ID {bug_id} not found")

    # Get all bugs that are marked as duplicates of this one
    duplicates = Bug.query.filter_by(duplicate_of_id=bug.id).all()

    # Also get duplicate history
    history = DuplicateHistory.query.filter_by(duplicate_bug_id=bug.id).all()

    return jsonify(
        {
            "bug_id": str(bug.id),
            "title": bug.title,
            "duplicate_count": len(duplicates),
            "duplicates": [
                {
                    "id": str(d.id),
                    "title": d.title,
                    "similarity_score": d.similarity_score,
                    "status": d.status,
                    "created_at": d.created_at.isoformat(),
                }
                for d in duplicates
            ],
            "history": [
                {
                    "detected_at": h.detected_at.isoformat(),
                    "similarity_score": h.similarity_score,
                    "action_taken": h.action_taken,
                }
                for h in history
            ],
        }
    )


@bugs_bp.route("/search", methods=["GET"])
@rate_limit(limit=200, window=3600)
@optional_auth()
def search_bugs():
    """
    Search bugs by various criteria.

    ---
    tags:
      - Bugs
    parameters:
      - name: q
        in: query
        type: string
        description: Search query (title/description)
      - name: product
        in: query
        type: string
      - name: status
        in: query
        type: string
      - name: severity
        in: query
        type: string
      - name: limit
        in: query
        type: integer
        default: 50
      - name: offset
        in: query
        type: integer
        default: 0
    responses:
      200:
        description: Search results
    """
    query = Bug.query

    # Text search
    search_query = request.args.get("q")
    if search_query:
        query = query.filter(
            db.or_(
                Bug.title.ilike(f"%{search_query}%"),
                Bug.description.ilike(f"%{search_query}%"),
            )
        )

    # Filters
    if product := request.args.get("product"):
        query = query.filter_by(product=product)

    if status := request.args.get("status"):
        query = query.filter_by(status=status)

    if severity := request.args.get("severity"):
        query = query.filter_by(severity=severity)

    # Pagination
    limit = min(int(request.args.get("limit", 50)), 100)
    offset = int(request.args.get("offset", 0))

    total = query.count()
    bugs = query.offset(offset).limit(limit).all()

    return jsonify(
        {
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": [
                {
                    "id": str(bug.id),
                    "title": bug.title,
                    "product": bug.product,
                    "status": bug.status,
                    "severity": bug.severity,
                    "is_duplicate": bug.is_duplicate,
                    "created_at": bug.created_at.isoformat(),
                }
                for bug in bugs
            ],
        }
    )
