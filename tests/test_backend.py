import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_preview_invalid_file():
    """Test preview endpoint with invalid file type"""
    files = {"file": ("test.txt", b"invalid content", "text/plain")}
    response = client.post("/api/ili/preview", files=files)
    assert response.status_code == 400
    assert "must be an Excel file" in response.json()["detail"]


def test_process_invalid_file():
    """Test process endpoint with invalid file type"""
    files = {"file": ("test.txt", b"invalid content", "text/plain")}
    data = {"sheet_name": "Sheet1"}
    response = client.post("/api/ili/process", files=files, data=data)
    assert response.status_code == 400
    assert "must be an Excel file" in response.json()["detail"]


# Additional tests can be added for:
# - Valid Excel file uploads
# - Column validation
# - Statistics calculation
# - Error handling 