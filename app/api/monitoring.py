"""
Monitoring and metrics API endpoints
"""
from flask import Blueprint, request, jsonify
from app import db
from app.models.bug import Bug
from app.models.duplicate import DuplicateHistory, LowQualityQueue
from app.models.audit import SystemMetrics, AuditLog
from sqlalchemy import func
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint('monitoring', __name__)


@monitoring_bp.route('/stats', methods=['GET'])
def get_system_stats():
    """Get overall system statistics"""
    
    # Total bugs
    total_bugs = Bug.query.count()
    
    # Bugs by classification
    duplicates = Bug.query.filter_by(classification_tag='Duplicate').count()
    recurring = Bug.query.filter_by(classification_tag='Recurring').count()
    
    # Blocked duplicates
    blocked = DuplicateHistory.query.filter_by(was_blocked=True).count()
    
    # Low quality queue
    low_quality_pending = LowQualityQueue.query.filter_by(status='Pending').count()
    low_quality_approved = LowQualityQueue.query.filter_by(status='Approved').count()
    low_quality_rejected = LowQualityQueue.query.filter_by(status='Rejected').count()
    
    # Calculate prevention rate
    total_submissions = total_bugs + blocked
    prevention_rate = (blocked / total_submissions * 100) if total_submissions > 0 else 0
    
    return jsonify({
        'total_bugs': total_bugs,
        'duplicates_created': duplicates,
        'duplicates_blocked': blocked,
        'recurring_defects': recurring,
        'prevention_rate': round(prevention_rate, 2),
        'low_quality_queue': {
            'pending': low_quality_pending,
            'approved': low_quality_approved,
            'rejected': low_quality_rejected,
            'total': low_quality_pending + low_quality_approved + low_quality_rejected
        }
    }), 200


@monitoring_bp.route('/stats/duplicates', methods=['GET'])
def get_duplicate_stats():
    """Get detailed duplicate statistics"""
    
    # Top parent bugs by duplicate count
    top_parents = db.session.query(
        Bug.id,
        Bug.title,
        Bug.classification_tag,
        func.count(Bug.id).label('duplicate_count')
    ).join(
        Bug, Bug.parent_bug_id == Bug.id, isouter=True
    ).group_by(
        Bug.id
    ).having(
        func.count(Bug.id) > 0
    ).order_by(
        func.count(Bug.id).desc()
    ).limit(10).all()
    
    # Recent duplicates
    recent = DuplicateHistory.query.order_by(
        DuplicateHistory.detected_at.desc()
    ).limit(20).all()
    
    # Duplicate detection by method
    by_method = db.session.query(
        DuplicateHistory.match_method,
        func.count(DuplicateHistory.id).label('count')
    ).group_by(
        DuplicateHistory.match_method
    ).all()
    
    return jsonify({
        'top_parent_bugs': [
            {
                'bug_id': b.id,
                'title': b.title,
                'classification': b.classification_tag,
                'duplicate_count': b.duplicate_count
            }
            for b in top_parents
        ],
        'recent_duplicates': [r.to_dict() for r in recent],
        'by_detection_method': {
            method: count for method, count in by_method
        }
    }), 200


@monitoring_bp.route('/stats/regions', methods=['GET'])
def get_region_stats():
    """Get statistics by region"""
    
    bugs_by_region = db.session.query(
        Bug.region,
        func.count(Bug.id).label('count')
    ).group_by(Bug.region).all()
    
    duplicates_by_region = db.session.query(
        Bug.region,
        func.count(Bug.id).label('count')
    ).filter(
        Bug.classification_tag == 'Duplicate'
    ).group_by(Bug.region).all()
    
    return jsonify({
        'bugs_by_region': {region or 'Unknown': count for region, count in bugs_by_region},
        'duplicates_by_region': {region or 'Unknown': count for region, count in duplicates_by_region}
    }), 200


@monitoring_bp.route('/stats/builds', methods=['GET'])
def get_build_stats():
    """Get statistics by build version"""
    
    bugs_by_build = db.session.query(
        Bug.build_version,
        func.count(Bug.id).label('count')
    ).group_by(Bug.build_version).order_by(
        func.count(Bug.id).desc()
    ).limit(20).all()
    
    return jsonify({
        'bugs_by_build': {build or 'Unknown': count for build, count in bugs_by_build}
    }), 200


@monitoring_bp.route('/stats/timeline', methods=['GET'])
def get_timeline_stats():
    """
    Get timeline statistics
    
    Query parameters:
    - days: Number of days to look back (default: 30)
    """
    days = request.args.get('days', 30, type=int)
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Bugs created per day
    bugs_per_day = db.session.query(
        func.date(Bug.created_at).label('date'),
        func.count(Bug.id).label('count')
    ).filter(
        Bug.created_at >= start_date
    ).group_by(
        func.date(Bug.created_at)
    ).order_by('date').all()
    
    # Duplicates detected per day
    duplicates_per_day = db.session.query(
        func.date(DuplicateHistory.detected_at).label('date'),
        func.count(DuplicateHistory.id).label('count')
    ).filter(
        DuplicateHistory.detected_at >= start_date
    ).group_by(
        func.date(DuplicateHistory.detected_at)
    ).order_by('date').all()
    
    return jsonify({
        'start_date': start_date.isoformat(),
        'end_date': datetime.utcnow().isoformat(),
        'bugs_per_day': [
            {'date': str(date), 'count': count}
            for date, count in bugs_per_day
        ],
        'duplicates_per_day': [
            {'date': str(date), 'count': count}
            for date, count in duplicates_per_day
        ]
    }), 200


@monitoring_bp.route('/stats/quality', methods=['GET'])
def get_quality_stats():
    """Get quality-related statistics"""
    
    # Quality issues distribution
    all_issues = db.session.query(LowQualityQueue.quality_issues).all()
    
    issue_counts = {}
    for (issues,) in all_issues:
        if issues:
            for issue in issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
    
    # Low quality by reporter (top offenders)
    by_reporter = db.session.query(
        LowQualityQueue.reporter,
        func.count(LowQualityQueue.id).label('count')
    ).group_by(
        LowQualityQueue.reporter
    ).order_by(
        func.count(LowQualityQueue.id).desc()
    ).limit(10).all()
    
    return jsonify({
        'quality_issues_distribution': issue_counts,
        'top_reporters_with_quality_issues': [
            {'reporter': reporter, 'count': count}
            for reporter, count in by_reporter
        ]
    }), 200


@monitoring_bp.route('/stats/performance', methods=['GET'])
def get_performance_stats():
    """Get AI performance metrics"""
    
    # False positive rate (bugs promoted from duplicates)
    total_duplicates = Bug.query.filter(
        Bug.classification_tag.in_(['Duplicate', 'Recurring'])
    ).count()
    
    promotions = AuditLog.query.filter_by(event_type='bug_promoted').count()
    
    false_positive_rate = (promotions / total_duplicates * 100) if total_duplicates > 0 else 0
    
    # Average match scores
    avg_match_score = db.session.query(
        func.avg(Bug.match_score)
    ).filter(
        Bug.match_score.isnot(None)
    ).scalar()
    
    # Score distribution
    score_ranges = {
        '0.85-1.0': Bug.query.filter(Bug.match_score >= 0.85).count(),
        '0.70-0.85': Bug.query.filter(
            Bug.match_score >= 0.70,
            Bug.match_score < 0.85
        ).count(),
        '0.0-0.70': Bug.query.filter(Bug.match_score < 0.70).count()
    }
    
    return jsonify({
        'false_positive_rate': round(false_positive_rate, 2),
        'false_positive_count': promotions,
        'total_duplicates': total_duplicates,
        'average_match_score': round(avg_match_score, 3) if avg_match_score else None,
        'score_distribution': score_ranges
    }), 200


@monitoring_bp.route('/health', methods=['GET'])
def health_check():
    """Detailed health check"""
    try:
        # Check database
        db.session.execute('SELECT 1')
        db_status = 'healthy'
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = 'unhealthy'
    
    # Check vector store
    try:
        from flask import current_app
        vector_store_stats = current_app.vector_store.get_stats()
        vector_store_status = 'healthy'
    except Exception as e:
        logger.error(f"Vector store health check failed: {e}")
        vector_store_stats = {}
        vector_store_status = 'unhealthy'
    
    overall_status = 'healthy' if db_status == 'healthy' and vector_store_status == 'healthy' else 'degraded'
    
    return jsonify({
        'status': overall_status,
        'components': {
            'database': db_status,
            'vector_store': vector_store_status
        },
        'vector_store_stats': vector_store_stats
    }), 200 if overall_status == 'healthy' else 503
