import pytest
from fastapi.testclient import TestClient
from analysis_api.main import app
from django.contrib.auth.models import User
from django.urls import reverse

@pytest.mark.django_db
def test_health_checks_database(client):
    response=client.get(reverse("health")); assert response.status_code==200 and response.json()=={"status":"ok","service":"django"}
    assert TestClient(app).get("/api/health").json()["status"]=="ok"

@pytest.mark.django_db
def test_media_requires_login_and_blocks_traversal(client,tmp_path,settings):
    settings.MEDIA_ROOT=tmp_path; protected=tmp_path/"result.json"; protected.write_text("{}",encoding="utf-8")
    response=client.get(reverse("protected_media",args=["result.json"])); assert response.status_code==302 and "/accounts/login/" in response.url
    client.force_login(User.objects.create_user("viewer")); response=client.get(reverse("protected_media",args=["result.json"])); assert response.status_code==200 and response["Cache-Control"]=="private, no-store"
    assert client.get("/media/../manage.py").status_code==404
