from datetime import date
import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from core.models import Analysis, MedicalImage, ModelVersion, Project, Review
from core.reports import build_ra_report

@pytest.fixture
def analysis(db):
    a=User.objects.create_user("analyst"); p=Project.objects.create(title="Brain MRI",created_by=a)
    image=MedicalImage.objects.create(project=p,file="nifti/test.nii",study_date=date(2026,1,1),modality="MRI",uploaded_by=a)
    model=ModelVersion.objects.create(name="MockSeg",version="1.0")
    return Analysis.objects.create(image=image,model_version=model,created_by=a,status="COMPLETED",voxel_count=10,volume_cm3=1.0)

@pytest.mark.django_db
def test_approved_analysis_is_immutable(analysis):
    reviewer=User.objects.create_user("reviewer"); Review.objects.create(analysis=analysis,reviewer=reviewer,decision="APPROVED",comment="ok")
    analysis.volume_cm3=2.0
    with pytest.raises(ValidationError): analysis.save()

@pytest.mark.django_db
def test_report_generation_contains_required_sections(analysis):
    data=build_ra_report(analysis.image.project)
    assert data[:2] == b"PK" and len(data)>1000
    from docx import Document
    from io import BytesIO
    text="\n".join(p.text for p in Document(BytesIO(data)).paragraphs)
    assert "프로젝트 개요" in text and "한계와 주의사항" in text and "의료진의 진단을 대체" in text

