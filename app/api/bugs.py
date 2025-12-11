"""
Bug submission and management API endpoints
"""
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models.bug import Bug
from app.models.duplicate import DuplicateHistory
from app.services.duplicate_detector import DuplicateDetector
from app.services.similarity_engine import SimilarityEngine
from app.services.quality_checker import QualityChecker
import logging

logger = logging.getLogger(__name__)

bugs_bp = Blueprint('bugs', __name__)

def get_duplicate_detector():
    """Get or create duplicate detector instance"""
    if not hasattr(current_app, 'duplicate_detector'):
        quality_checker = QualityChecker(
            min_description_length=current_app.config['MIN_DESCRIPTION_LENGTH'],
            require_repro_steps=current_app.config['REQUIRE_REPRO_STEPS'],
            require_logs=current_app.config['REQUIRE_LOGS']
        )
        
        similarity_engine = SimilarityEngine(
            current_app.embedding_service,
            current_app.vector_store
        )
        
        current_app.duplicate_detector = DuplicateDetector(
            current_app.embedding_service,
            similarity_engine,
            quality_checker,
            current_app.vector_store,
            similarity_threshold=current_app.config['SIMILARITY_THRESHOLD'],
            low_confidence_threshold=current_app.config['LOW_CONFIDENCE_THRESHOLD']
        )
    
    return current_app.duplicate_detector


@bugs_bp.route('/', methods=['POST'])
def create_bug():
    """
    Submit a new bug
    
    Request body:
    {
        "title": "App crashes on startup",
        "description": "When I open the app...",
        "repro_steps": "1. Open app\\n2. ...",
        "logs": "Error trace...",
        "severity": "Critical",
        "priority": "High",
        "reporter": "user@example.com",
        "device": "iPhone 14 Pro",
        "os_version": "iOS 17.1",
        "build_version": "1.2.3",
        "region": "US"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Validate required fields
        required_fields = ['title', 'description', 'reporter']
        missing_fields = [f for f in required_fields if not data.get(f)]
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        # Process bug through duplicate detection
        detector = get_duplicate_detector()
        bug, action, metadata = detector.process_incoming_bug(data)
        
        # Prepare response based on action
        if action == 'created':
            return jsonify({
                'status': 'created',
                'bug': bug.to_dict(),
                'message': 'Bug created successfully'
            }), 201
        
        elif action == 'blocked_duplicate':
            return jsonify({
                'status': 'duplicate',
                'message': 'This bug appears to be a duplicate',
                'parent_bug_id': metadata['parent_bug_id'],
                'parent_bug_title': metadata['parent_bug_title'],
                'match_score': metadata['match_score'],
                'match_details': metadata['match_details']
            }), 409  # Conflict
        
        elif action == 'flagged_for_review':
            return jsonify({
                'status': 'created_flagged',
                'bug': bug.to_dict(),
                'message': 'Bug created but flagged as potential duplicate',
                'parent_bug_id': metadata['parent_bug_id'],
                'match_score': metadata['match_score']
            }), 201
        
        elif action == 'low_quality':
            return jsonify({
                'status': 'low_quality',
                'message': 'Bug submission requires review due to quality issues',
                'low_quality_id': metadata['low_quality_id'],
                'issues': metadata['issues']
            }), 400
        
        else:
            return jsonify({'error': 'Unknown action'}), 500
    
    except Exception as e:
        logger.error(f"Error creating bug: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


@bugs_bp.route('/<int:bug_id>', methods=['GET'])
def get_bug(bug_id):
    """Get bug by ID"""
    bug = Bug.query.get(bug_id)
    
    if not bug:
        return jsonify({'error': 'Bug not found'}), 404
    
    include_duplicates = request.args.get('include_duplicates', 'false').lower() == 'true'
    
    return jsonify({
        'bug': bug.to_dict(include_duplicates=include_duplicates)
    }), 200


@bugs_bp.route('/<int:bug_id>/duplicates', methods=['GET'])
def get_bug_duplicates(bug_id):
    """Get all duplicates of a bug"""
    bug = Bug.query.get(bug_id)
    
    if not bug:
        return jsonify({'error': 'Bug not found'}), 404
    
    duplicates = Bug.query.filter_by(parent_bug_id=bug_id).all()
    
    return jsonify({
        'bug_id': bug_id,
        'bug_title': bug.title,
        'duplicate_count': len(duplicates),
        'duplicates': [d.to_dict() for d in duplicates]
    }), 200


@bugs_bp.route('/', methods=['GET'])
def list_bugs():
    """
    List bugs with optional filters
    
    Query parameters:
    - status: Filter by status
    - classification_tag: Filter by tag (Duplicate, Recurring, LowQuality)
    - region: Filter by region
    - build_version: Filter by build version
    - page: Page number (default: 1)
    - per_page: Items per page (default: 50, max: 100)
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)
    
    query = Bug.query
    
    # Apply filters
    if status := request.args.get('status'):
        query = query.filter_by(status=status)
    
    if classification_tag := request.args.get('classification_tag'):
        query = query.filter_by(classification_tag=classification_tag)
    
    if region := request.args.get('region'):
        query = query.filter_by(region=region)
    
    if build_version := request.args.get('build_version'):
        query = query.filter_by(build_version=build_version)
    
    # Paginate
    pagination = query.order_by(Bug.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    return jsonify({
        'bugs': [bug.to_dict() for bug in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200


@bugs_bp.route('/<int:bug_id>', methods=['PATCH'])
def update_bug(bug_id):
    """Update bug fields"""
    bug = Bug.query.get(bug_id)
    
    if not bug:
        return jsonify({'error': 'Bug not found'}), 404
    
    data = request.get_json()
    
    # Allowed fields for update
    allowed_fields = [
        'title', 'description', 'repro_steps', 'logs',
        'severity', 'priority', 'status', 'assignee'
    ]
    
    for field in allowed_fields:
        if field in data:
            setattr(bug, field, data[field])
    
    db.session.commit()
    
    return jsonify({
        'message': 'Bug updated successfully',
        'bug': bug.to_dict()
    }), 200


@bugs_bp.route('/<int:bug_id>/history', methods=['GET'])
def get_bug_history(bug_id):
    """Get duplicate detection history for a bug"""
    bug = Bug.query.get(bug_id)
    
    if not bug:
        return jsonify({'error': 'Bug not found'}), 404
    
    # Get history where this bug is the duplicate
    as_duplicate = DuplicateHistory.query.filter_by(duplicate_bug_id=bug_id).all()
    
    # Get history where this bug is the parent
    as_parent = DuplicateHistory.query.filter_by(parent_bug_id=bug_id).all()
    
    return jsonify({
        'bug_id': bug_id,
        'as_duplicate': [h.to_dict() for h in as_duplicate],
        'as_parent': [h.to_dict() for h in as_parent]
    }), 200
