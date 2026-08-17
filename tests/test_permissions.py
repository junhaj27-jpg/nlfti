import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from core.models import Project

@pytest.fixture
def users(db):
    out={}
    for role in ("ANALYST","REVIEWER","ADMIN"):
        g,_=Group.objects.get_or_create(name=role); u=User.objects.create_user(role.lower(),password="pw"); u.groups.add(g); out[role]=u
    return out

@pytest.mark.django_db
def test_analyst_can_create_project(client,users):
    client.force_login(users["ANALYST"]); response=client.post(reverse("project_create"),{"title":"P","description":"D"})
    assert response.status_code == 302 and Project.objects.filter(title="P").exists()

@pytest.mark.django_db
def test_reviewer_cannot_create_project(client,users):
    client.force_login(users["REVIEWER"]); assert client.get(reverse("project_create")).status_code == 403

