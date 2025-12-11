"""
Celery tasks for asynchronous operations
"""
from celery import Celery
from app import create_app, db
from app.models.bug import Bug
from app.integrations.jira_integration import JiraIntegration
from app.integrations.tp_integration import TPIntegration
import logging

logger = logging.getLogger(__name__)

flask_app = create_app()
celery = Celery(
    flask_app.import_name,
    broker=flask_app.config['CELERY_BROKER_URL'],
    backend=flask_app.config['CELERY_RESULT_BACKEND']
)
celery.conf.update(flask_app.config)


class ContextTask(celery.Task):
    """Task that runs within Flask application context"""
    def __call__(self, *args, **kwargs):
        with flask_app.app_context():
            return self.run(*args, **kwargs)

celery.Task = ContextTask


@celery.task
def sync_bug_to_jira(bug_id: int):
    """
    Sync bug to Jira
    
    Args:
        bug_id: Bug ID to sync
    """
    try:
        bug = Bug.query.get(bug_id)
        if not bug:
            logger.error(f"Bug {bug_id} not found")
            return
        
        # Initialize Jira integration
        jira = JiraIntegration(
            url=flask_app.config['JIRA_URL'],
            username=flask_app.config['JIRA_USERNAME'],
            api_token=flask_app.config['JIRA_API_TOKEN'],
            project_key=flask_app.config['JIRA_PROJECT_KEY']
        )
        
        if not bug.jira_key:
            # Create new Jira issue
            jira_key = jira.create_issue({
                'title': bug.title,
                'description': bug.description,
                'repro_steps': bug.repro_steps,
                'logs': bug.logs,
                'severity': bug.severity,
                'device': bug.device,
                'os_version': bug.os_version,
                'build_version': bug.build_version,
                'region': bug.region
            })
            
            if jira_key:
                bug.jira_key = jira_key
                db.session.commit()
                logger.info(f"Created Jira issue {jira_key} for bug {bug_id}")
        
        # Handle duplicate status
        if bug.parent_bug_id and bug.classification_tag in ['Duplicate', 'Recurring']:
            parent_bug = Bug.query.get(bug.parent_bug_id)
            if parent_bug and parent_bug.jira_key and bug.jira_key:
                jira.update_duplicate_status(
                    parent_bug.jira_key,
                    bug.jira_key,
                    bug.match_score or 0.0
                )
        
        # Handle recurring status
        if bug.classification_tag == 'Recurring' and bug.jira_key:
            duplicate_count = Bug.query.filter_by(parent_bug_id=bug.id).count()
            jira.mark_as_recurring(bug.jira_key, duplicate_count)
    
    except Exception as e:
        logger.error(f"Failed to sync bug {bug_id} to Jira: {e}", exc_info=True)


@celery.task
def sync_bug_to_tp(bug_id: int):
    """
    Sync bug to Test Platform
    
    Args:
        bug_id: Bug ID to sync
    """
    try:
        bug = Bug.query.get(bug_id)
        if not bug:
            logger.error(f"Bug {bug_id} not found")
            return
        
        # Initialize TP integration
        tp = TPIntegration(
            api_url=flask_app.config['TP_API_URL'],
            api_key=flask_app.config['TP_API_KEY'],
            project_id=flask_app.config['TP_PROJECT_ID']
        )
        
        if not bug.tp_id:
            # Create new TP defect
            tp_id = tp.create_defect({
                'title': bug.title,
                'description': bug.description,
                'repro_steps': bug.repro_steps,
                'logs': bug.logs,
                'severity': bug.severity,
                'priority': bug.priority,
                'reporter': bug.reporter,
                'device': bug.device,
                'os_version': bug.os_version,
                'build_version': bug.build_version,
                'region': bug.region
            })
            
            if tp_id:
                bug.tp_id = tp_id
                db.session.commit()
                logger.info(f"Created TP defect {tp_id} for bug {bug_id}")
        
        # Handle duplicate status
        if bug.parent_bug_id and bug.classification_tag in ['Duplicate', 'Recurring']:
            parent_bug = Bug.query.get(bug.parent_bug_id)
            if parent_bug and parent_bug.tp_id and bug.tp_id:
                tp.update_duplicate_status(
                    parent_bug.tp_id,
                    bug.tp_id,
                    bug.match_score or 0.0
                )
        
        # Handle recurring status
        if bug.classification_tag == 'Recurring' and bug.tp_id:
            duplicate_count = Bug.query.filter_by(parent_bug_id=bug.id).count()
            tp.mark_as_recurring(bug.tp_id, duplicate_count)
    
    except Exception as e:
        logger.error(f"Failed to sync bug {bug_id} to TP: {e}", exc_info=True)


@celery.task
def rebuild_vector_index():
    """
    Rebuild the entire vector index from all bugs
    Scheduled to run daily
    """
    try:
        logger.info("Starting vector index rebuild")
        
        # Get all bugs with embeddings
        bugs = Bug.query.filter(Bug.embedding.isnot(None)).all()
        
        if not bugs:
            logger.info("No bugs with embeddings found")
            return
        
        # Extract embeddings and IDs
        import numpy as np
        embeddings = np.array([bug.embedding for bug in bugs], dtype=np.float32)
        bug_ids = [bug.id for bug in bugs]
        
        # Rebuild index
        flask_app.vector_store.rebuild_index(embeddings, bug_ids)
        
        logger.info(f"Vector index rebuilt with {len(bug_ids)} bugs")
    
    except Exception as e:
        logger.error(f"Failed to rebuild vector index: {e}", exc_info=True)


@celery.task
def update_metrics():
    """
    Update system metrics
    Scheduled to run periodically
    """
    try:
        from app.models.audit import SystemMetrics
        from datetime import datetime
        from sqlalchemy import func
        
        # Calculate prevented duplicates
        total_bugs = Bug.query.count()
        from app.models.duplicate import DuplicateHistory
        blocked = DuplicateHistory.query.filter_by(was_blocked=True).count()
        
        if total_bugs + blocked > 0:
            prevention_rate = blocked / (total_bugs + blocked) * 100
        else:
            prevention_rate = 0
        
        # Record metric
        metric = SystemMetrics(
            metric_name='duplicate_prevention_rate',
            metric_value=prevention_rate,
            time_period='hourly'
        )
        db.session.add(metric)
        
        # Calculate average match scores
        avg_score = db.session.query(func.avg(Bug.match_score)).filter(
            Bug.match_score.isnot(None)
        ).scalar()
        
        if avg_score:
            metric = SystemMetrics(
                metric_name='average_match_score',
                metric_value=avg_score,
                time_period='hourly'
            )
            db.session.add(metric)
        
        db.session.commit()
        logger.info("Metrics updated successfully")
    
    except Exception as e:
        logger.error(f"Failed to update metrics: {e}", exc_info=True)
        db.session.rollback()


# Configure periodic tasks
@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks"""
    # Rebuild vector index daily at 2 AM
    sender.add_periodic_task(
        crontab(hour=2, minute=0),
        rebuild_vector_index.s(),
        name='rebuild-vector-index-daily'
    )
    
    # Update metrics every hour
    sender.add_periodic_task(
        crontab(minute=0),
        update_metrics.s(),
        name='update-metrics-hourly'
    )


from celery.schedules import crontab
