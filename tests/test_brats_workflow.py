from datetime import date
import pytest
from django.contrib.auth.models import Group,User
from django.core.exceptions import ValidationError
from django.urls import reverse
from core.models import AnalysisJob,AnalysisResult,JobReview,MRIStudy,ModelVersion,Project
from core.reports import build_ra_report

@pytest.fixture
def brats_result(db):
    analyst=User.objects.create_user("a"); project=Project.objects.create(title="B",created_by=analyst); study=MRIStudy.objects.create(project=project,study_date=date.today(),t1="a.nii",t1ce="b.nii",t2="c.nii",flair="d.nii",uploaded_by=analyst)
    model=ModelVersion.objects.create(name="MONAI",version="1"); job=AnalysisJob.objects.create(study=study,model_version=model,model_name="MONAI",model_version_name="1",status="COMPLETED",created_by=analyst)
    return AnalysisResult.objects.create(job=job,segmentation_file="s.nii.gz",overlay_file="o.png",metrics_file="m.json",whole_tumor_cm3=1)
@pytest.mark.django_db
def test_approved_brats_result_is_locked(brats_result):
    reviewer=User.objects.create_user("r"); JobReview.objects.create(job=brats_result.job,reviewer=reviewer,decision="APPROVED",comment="ok"); brats_result.whole_tumor_cm3=2
    with pytest.raises(ValidationError): brats_result.save()
@pytest.mark.django_db
def test_reviewer_cannot_request_brats_job(client,brats_result):
    reviewer=User.objects.create_user("reviewer"); group=Group.objects.create(name="REVIEWER"); reviewer.groups.add(group); client.force_login(reviewer)
    assert client.post(reverse("brats_job_run",args=[brats_result.job.study_id]),{"model_version":brats_result.job.model_version_id}).status_code==403
@pytest.mark.django_db
def test_brats_report_contains_regulatory_sections(brats_result):
    from docx import Document
    from io import BytesIO
    text="\n".join(p.text for p in Document(BytesIO(build_ra_report(brats_result.job.study.project))).paragraphs)
    for section in ("사용 목적","입력 구성","전처리 과정","전체 종양","실패 및 예외 기록","알려진 한계","진단을 대체하지"):
        assert section in text
