"""
Script to initialize the database and create initial data
"""
from app import create_app, db
from app.models.bug import Bug
from app.models.duplicate import LowQualityQueue, DuplicateHistory
from app.models.audit import AuditLog, SystemMetrics
import numpy as np

def init_db():
    """Initialize database tables"""
    app = create_app()
    
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✓ Database tables created successfully")
        
        # Create sample data for testing
        create_sample_data(app)

def create_sample_data(app):
    """Create sample bugs for testing"""
    print("\nCreating sample data...")
    
    sample_bugs = [
        {
            'title': 'App crashes on startup in iOS 17',
            'description': 'The application crashes immediately when I try to open it on iOS 17. This happens every time.',
            'repro_steps': '1. Open app\n2. App crashes before loading',
            'severity': 'Critical',
            'priority': 'High',
            'reporter': 'user1@example.com',
            'device': 'iPhone 14 Pro',
            'os_version': 'iOS 17.1',
            'build_version': '2.0.0',
            'region': 'US',
            'status': 'New'
        },
        {
            'title': 'Login button not responding',
            'description': 'When I tap the login button, nothing happens. The button does not respond to touch.',
            'repro_steps': '1. Open app\n2. Enter credentials\n3. Tap login button\n4. No response',
            'severity': 'High',
            'priority': 'High',
            'reporter': 'user2@example.com',
            'device': 'Samsung Galaxy S23',
            'os_version': 'Android 14',
            'build_version': '2.0.0',
            'region': 'EU',
            'status': 'New'
        },
        {
            'title': 'Images not loading in gallery',
            'description': 'The gallery shows blank spaces instead of images. Images fail to load consistently.',
            'repro_steps': '1. Navigate to gallery\n2. Scroll through images\n3. Many images show as blank',
            'severity': 'Medium',
            'priority': 'Medium',
            'reporter': 'user3@example.com',
            'device': 'iPhone 13',
            'os_version': 'iOS 16.5',
            'build_version': '1.9.5',
            'region': 'APAC',
            'status': 'New'
        }
    ]
    
    for bug_data in sample_bugs:
        bug = Bug(**bug_data)
        
        # Generate embedding
        text = bug.get_text_for_embedding()
        embedding = app.embedding_service.generate_embedding(text)
        bug.embedding = embedding.tolist()
        
        db.session.add(bug)
    
    db.session.commit()
    print(f"✓ Created {len(sample_bugs)} sample bugs")
    
    # Add bugs to vector store
    bugs = Bug.query.all()
    embeddings = np.array([bug.embedding for bug in bugs], dtype=np.float32)
    bug_ids = [bug.id for bug in bugs]
    app.vector_store.add_vectors(embeddings, bug_ids)
    app.vector_store.save_index()
    print(f"✓ Added {len(bug_ids)} bugs to vector store")

if __name__ == '__main__':
    init_db()
    print("\n✅ Database initialization complete!")
