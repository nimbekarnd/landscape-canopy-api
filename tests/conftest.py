import pytest
from fastapi.testclient import TestClient
from landscape_api.main import app

@pytest.fixture()
def client():
    return TestClient(app)
