"""
QA interface API endpoints for override and review operations
"""

import logging
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from app import db
from app.models.audit import AuditLog
from app.models.bug import Bug
from app.models.duplicate import LowQualityQueue

logger = logging.getLogger(__name__)

qa_bp = Blueprint("qa", __name__)


@qa_bp.route("/low-quality", methods=["GET"])
def get_low_quality_queue():
    """
    Get bugs in low quality queue

    Query parameters:
    - status: Filter by status (Pending, Approved, Rejected)
    - page: Page number
    - per_page: Items per page
    """
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 100)

    query = LowQualityQueue.query

    if status := request.args.get("status"):
        query = query.filter_by(status=status)

    pagination = query.order_by(LowQualityQueue.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return (
        jsonify(
            {
                "items": [item.to_dict() for item in pagination.items],
                "total": pagination.total,
                "page": page,
                "per_page": per_page,
                "pages": pagination.pages,
            }
        ),
        200,
    )


@qa_bp.route("/low-quality/<int:item_id>/approve", methods=["POST"])
def approve_low_quality(item_id):
    """
    Approve a low quality submission and create bug

    Request body:
    {
        "reviewed_by": "qa@example.com",
        "notes": "Reviewed and approved"
    }
    """
    item = LowQualityQueue.query.get(item_id)

    if not item:
        return jsonify({"error": "Item not found"}), 404

    if item.status != "Pending":
        return jsonify({"error": "Item already reviewed"}), 400

    data = request.get_json() or {}

    # Create bug from low quality item
    bug = Bug(
        title=item.title,
        description=item.description,
        repro_steps=item.repro_steps,
        logs=item.logs,
        reporter=item.reporter,
        device=item.device,
        build_version=item.build_version,
        region=item.region,
        status="New",
    )

    db.session.add(bug)
    db.session.flush()

    # Generate embedding and add to vector store
    text = bug.get_text_for_embedding()
    embedding = current_app.embedding_service.generate_embedding(text)
    bug.embedding = embedding.tolist()
    current_app.vector_store.add_vectors(embedding.reshape(1, -1), [bug.id])

    # Update low quality item
    item.status = "Approved"
    item.reviewed_by = data.get("reviewed_by")
    item.review_notes = data.get("notes")
    item.reviewed_at = datetime.utcnow()
    item.created_bug_id = bug.id

    # Log audit
    audit = AuditLog(
        event_type="qa_override",
        bug_id=bug.id,
        low_quality_id=item_id,
        user=data.get("reviewed_by"),
        previous_state={"status": "Pending"},
        new_state={"status": "Approved", "bug_id": bug.id},
        notes=data.get("notes"),
    )
    db.session.add(audit)

    db.session.commit()

    logger.info(f"QA approved low quality item {item_id}, created bug {bug.id}")

    return (
        jsonify(
            {
                "message": "Bug approved and created",
                "bug": bug.to_dict(),
                "low_quality_item": item.to_dict(),
            }
        ),
        201,
    )


@qa_bp.route("/low-quality/<int:item_id>/reject", methods=["POST"])
def reject_low_quality(item_id):
    """
    Reject a low quality submission

    Request body:
    {
        "reviewed_by": "qa@example.com",
        "notes": "Insufficient information"
    }
    """
    item = LowQualityQueue.query.get(item_id)

    if not item:
        return jsonify({"error": "Item not found"}), 404

    if item.status != "Pending":
        return jsonify({"error": "Item already reviewed"}), 400

    data = request.get_json() or {}

    # Update item
    item.status = "Rejected"
    item.reviewed_by = data.get("reviewed_by")
    item.review_notes = data.get("notes")
    item.reviewed_at = datetime.utcnow()

    # Log audit
    audit = AuditLog(
        event_type="qa_override",
        low_quality_id=item_id,
        user=data.get("reviewed_by"),
        previous_state={"status": "Pending"},
        new_state={"status": "Rejected"},
        notes=data.get("notes"),
    )
    db.session.add(audit)

    db.session.commit()

    logger.info(f"QA rejected low quality item {item_id}")

    return jsonify({"message": "Bug rejected", "low_quality_item": item.to_dict()}), 200


@qa_bp.route("/bugs/<int:bug_id>/promote", methods=["POST"])
def promote_duplicate(bug_id):
    """
    Promote a duplicate bug to an independent bug

    Request body:
    {
        "user": "qa@example.com",
        "reason": "Different root cause"
    }
    """
    bug = Bug.query.get(bug_id)

    if not bug:
        return jsonify({"error": "Bug not found"}), 404

    if not bug.parent_bug_id:
        return jsonify({"error": "Bug is not a duplicate"}), 400

    data = request.get_json() or {}

    # Store previous state
    previous_state = {
        "parent_bug_id": bug.parent_bug_id,
        "classification_tag": bug.classification_tag,
        "match_score": bug.match_score,
    }

    # Promote bug
    bug.parent_bug_id = None
    bug.classification_tag = None
    bug.match_score = None

    # Log audit
    audit = AuditLog(
        event_type="bug_promoted",
        bug_id=bug_id,
        user=data.get("user"),
        previous_state=previous_state,
        new_state={"parent_bug_id": None, "classification_tag": None},
        notes=data.get("reason"),
    )
    db.session.add(audit)

    db.session.commit()

    logger.info(f"QA promoted bug {bug_id} from duplicate to independent")

    return jsonify({"message": "Bug promoted successfully", "bug": bug.to_dict()}), 200


@qa_bp.route("/bugs/<int:bug_id>/reclassify", methods=["POST"])
def reclassify_bug(bug_id):
    """
    Reclassify a bug's duplicate status

    Request body:
    {
        "user": "qa@example.com",
        "parent_bug_id": 123,
        "classification_tag": "Duplicate",
        "reason": "Actually a duplicate of #123"
    }
    """
    bug = Bug.query.get(bug_id)

    if not bug:
        return jsonify({"error": "Bug not found"}), 404

    data = request.get_json() or {}

    # Validate parent bug if provided
    if parent_bug_id := data.get("parent_bug_id"):
        parent_bug = Bug.query.get(parent_bug_id)
        if not parent_bug:
            return jsonify({"error": "Parent bug not found"}), 404

        if parent_bug_id == bug_id:
            return jsonify({"error": "Bug cannot be its own parent"}), 400

    # Store previous state
    previous_state = {
        "parent_bug_id": bug.parent_bug_id,
        "classification_tag": bug.classification_tag,
        "match_score": bug.match_score,
    }

    # Update classification
    bug.parent_bug_id = data.get("parent_bug_id")
    bug.classification_tag = data.get("classification_tag")

    # Log audit
    audit = AuditLog(
        event_type="classification_changed",
        bug_id=bug_id,
        parent_bug_id=data.get("parent_bug_id"),
        user=data.get("user"),
        previous_state=previous_state,
        new_state={
            "parent_bug_id": bug.parent_bug_id,
            "classification_tag": bug.classification_tag,
        },
        notes=data.get("reason"),
    )
    db.session.add(audit)

    db.session.commit()

    logger.info(f"QA reclassified bug {bug_id}")

    return (
        jsonify({"message": "Bug reclassified successfully", "bug": bug.to_dict()}),
        200,
    )


@qa_bp.route("/audit", methods=["GET"])
def get_audit_log():
    """
    Get audit log with filters

    Query parameters:
    - event_type: Filter by event type
    - user: Filter by user
    - bug_id: Filter by bug ID
    - start_date: Filter by start date (ISO format)
    - end_date: Filter by end date (ISO format)
    - page: Page number
    - per_page: Items per page
    """
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 100, type=int), 100)

    query = AuditLog.query

    if event_type := request.args.get("event_type"):
        query = query.filter_by(event_type=event_type)

    if user := request.args.get("user"):
        query = query.filter_by(user=user)

    if bug_id := request.args.get("bug_id", type=int):
        query = query.filter_by(bug_id=bug_id)

    pagination = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return (
        jsonify(
            {
                "audit_log": [log.to_dict() for log in pagination.items],
                "total": pagination.total,
                "page": page,
                "per_page": per_page,
                "pages": pagination.pages,
            }
        ),
        200,
    )
