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

def test_document_verification_endpoint(monkeypatch):
    # Mock groq function to return a clean JSON string
    mock_response = """
    {
        "score": 95,
        "status": "Compliant",
        "doc_type_identified": "Tenancy Agreement",
        "jurisdiction": "Punjab, Pakistan",
        "strengths": ["Excellent clause definition."],
        "vulnerabilities": ["None identified."],
        "recommendations": ["Make sure to register it."],
        "detailed_analysis": "### Analysis\\nAll good."
    }
    """
    async def mock_groq(*args, **kwargs):
        return mock_response

    import main
    monkeypatch.setattr(main, "groq", mock_groq)

    # First, sign up/login to get a token
    signup_resp = client.post("/api/v1/auth/signup", json={
        "first_name": "Verify",
        "last_name": "User",
        "email": "verify.user@lexai.app",
        "password": "password123"
    })
    assert signup_resp.status_code == 200
    token = signup_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Write a dummy document to UPLOAD_DIR
    import uuid
    doc_id = str(uuid.uuid4())
    test_filepath = os.path.join(main.UPLOAD_DIR, f"{doc_id}.txt")
    with open(test_filepath, "w") as f:
        f.write("This is a lease agreement between Landlord A and Tenant B.")

    # Save metadata to DB
    db.save_document_metadata(doc_id, "verify.user@lexai.app", "lease.txt", "contract", test_filepath)

    # Call verify endpoint
    verify_resp = client.post(f"/api/v1/documents/verify/{doc_id}", headers=headers)
    assert verify_resp.status_code == 200
    report = verify_resp.json()
    assert report["score"] == 95
    assert report["status"] == "Compliant"
    assert report["doc_type_identified"] == "Tenancy Agreement"

    # Clean up test file
    if os.path.exists(test_filepath):
        os.remove(test_filepath)

