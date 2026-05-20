import os
import pytest
from fastapi.testclient import TestClient
from main import app, db
import database
import logger

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db():
    # Ensure test environment uses clean DB tables
    db.init_db()
    # Clean up any existing test data to ensure test isolation
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email LIKE '%@lexai.app'")
    cursor.execute("DELETE FROM notifications WHERE user_email LIKE '%@lexai.app'")
    cursor.execute("DELETE FROM audit_logs WHERE user_email LIKE '%@lexai.app'")
    cursor.execute("DELETE FROM documents WHERE user_email LIKE '%@lexai.app'")
    conn.commit()
    conn.close()
    
    # Inject default admin for testing
    db.create_user("admin@lexai.app", "Admin", "User", "dummy_hash", "admin")
    yield

def test_database_user_creation():
    test_email = "test.user@lexai.app"
    success = db.create_user(test_email, "Test", "User", "hashed_pw", "user")
    assert success is True
    
    user = db.get_user_by_email(test_email)
    assert user is not None
    assert user["email"] == test_email
    assert user["role"] == "user"

def test_database_notifications():
    test_email = "notif.user@lexai.app"
    db.create_user(test_email, "Notif", "User", "hashed_pw", "user")
    
    db.create_notification(test_email, "Welcome", "Test notification message")
    notifs = db.get_user_notifications(test_email)
    assert len(notifs) >= 1
    assert notifs[0]["title"] == "Welcome"
    assert notifs[0]["is_read"] == 0
    
    db.mark_notifications_read(test_email)
    notifs_read = db.get_user_notifications(test_email)
    assert notifs_read[0]["is_read"] == 1

def test_database_analytics_and_audit():
    db.record_analytics("chat", "query", "Pakistan", "Tax", 1.0)
    summary = db.get_analytics_summary()
    assert "total_queries" in summary
    assert summary["total_queries"] >= 1
    
    db.record_audit_log("admin@lexai.app", "test_action", "Running test action", "127.0.0.1")
    logs = db.get_recent_audit_logs(10)
    assert len(logs) >= 1
    assert logs[0]["user_email"] == "admin@lexai.app"

def test_health_check_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "LexAI" in response.text

def test_auth_signup_validation():
    response = client.post("/api/v1/auth/signup", json={
        "first_name": "Invalid",
        "last_name": "User",
        "email": "invalid-email",
        "password": "short"
    })
    assert response.status_code == 400

def test_admin_rbac_protection():
    # Requesting admin endpoint without valid token should return 403 / 401
    response = client.get("/api/v1/admin/analytics")
    assert response.status_code in [401, 403]
