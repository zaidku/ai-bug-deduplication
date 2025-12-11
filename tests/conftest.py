"""
Test configuration
"""

import pytest

from app import create_app, db
from app.config import TestConfig


@pytest.fixture
def app():
    """Create application for testing"""
    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create CLI runner"""
    return app.test_cli_runner()
