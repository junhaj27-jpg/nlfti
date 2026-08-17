from datetime import date
import pytest
from django.contrib.auth.models import User
from core.models import AnalysisJob,AnalysisResult,MRIStudy,ModelVersion,Project,Subject
from core.tracking import percent_change,subject_timeline

def test_percent_change():
    assert percent_change(10,15)==50
    assert percent_change(10,8)==-20
    assert percent_change(0,0) is None

@pytest.mark.django_db
def test_timeline_warns_when_hospital_or_equipment_changes():
    user=User.objects.create_user("analyst"); project=Project.objects.create(title="P",created_by=user); subject=Subject.objects.create(project=project,subject_code="SUB-001"); model=ModelVersion.objects.create(name="M",version="1")
    def point(order,hospital,equipment,volume):
        study=MRIStudy.objects.create(project=project,subject=subject,timepoint_code=f"T{order:02}",timepoint_order=order,study_date=date(2026,order,1),hospital_code=hospital,equipment_code=equipment,t1="a.nii",t1ce="b.nii",t2="c.nii",flair="d.nii",uploaded_by=user)
        job=AnalysisJob.objects.create(study=study,model_version=model,model_name="M",model_version_name="1",status="COMPLETED",created_by=user)
        AnalysisResult.objects.create(job=job,segmentation_file="s.nii.gz",overlay_file="o.png",metrics_file="m.json",whole_tumor_cm3=volume)
    point(1,"H1","E1",10); point(2,"H2","E1",12)
    rows=subject_timeline(subject); assert rows[1]["delta_cm3"]==2 and rows[1]["change_percent"]==20
    assert "병원 변경" in rows[1]["comparison_warning"]
