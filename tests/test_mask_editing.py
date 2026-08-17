from datetime import date
import nibabel as nib
import numpy as np
import pytest
from django.contrib.auth.models import User
from django.core.files import File
from core.mask_editing import create_correction
from core.models import AnalysisJob,AnalysisResult,JobReview,MRIStudy,ModelVersion,Project

@pytest.mark.django_db
def test_correction_preserves_original_and_recalculates_volume(tmp_path,settings):
    settings.MEDIA_ROOT=tmp_path/"media"; user=User.objects.create_user("a"); project=Project.objects.create(title="P",created_by=user)
    source=tmp_path/"source.nii"; mask_path=tmp_path/"mask.nii.gz"; nib.save(nib.Nifti1Image(np.zeros((8,8,3),dtype=np.float32),np.eye(4)),source); nib.save(nib.Nifti1Image(np.zeros((8,8,3),dtype=np.uint8),np.eye(4)),mask_path)
    study=MRIStudy(project=project,study_date=date.today(),uploaded_by=user)
    for name in ("t1","t1ce","t2","flair"):
        with source.open("rb") as stream: getattr(study,name).save(f"{name}.nii",File(stream),save=False)
    study.save(); model=ModelVersion.objects.create(name="M",version="1"); job=AnalysisJob.objects.create(study=study,model_version=model,model_name="M",model_version_name="1",status="COMPLETED",created_by=user)
    result=AnalysisResult(job=job,overlay_file="o.png",metrics_file="m.json")
    with mask_path.open("rb") as stream: result.segmentation_file.save("original.nii.gz",File(stream))
    original_bytes=open(result.segmentation_file.path,"rb").read(); reviewer=User.objects.create_user("r"); JobReview.objects.create(job=job,reviewer=reviewer,decision="APPROVED",comment="ok")
    correction=create_correction(result,user,"경계 보정",1,[{"mode":"add","label":1,"radius":1,"points":[[4,4]]}])
    assert correction.whole_tumor_voxels==5 and correction.whole_tumor_cm3==pytest.approx(.005)
    assert correction.status=="PENDING_REVIEW" and open(result.segmentation_file.path,"rb").read()==original_bytes
