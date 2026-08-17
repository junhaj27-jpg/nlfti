from datetime import date
import nibabel as nib
import numpy as np
import pytest
from django.contrib.auth.models import User
from django.core.files import File
from core.models import Analysis, MedicalImage, ModelVersion, Project
from core.services import run_mock_analysis

@pytest.mark.django_db
def test_mock_inference_with_array_fixture(tmp_path, settings):
    settings.MEDIA_ROOT=tmp_path/"media"
    arr=np.arange(125,dtype=np.float32).reshape(5,5,5); source=tmp_path/"array.nii.gz"
    nib.save(nib.Nifti1Image(arr,np.diag([2,2,2,1])),source)
    user=User.objects.create_user("analyst"); project=Project.objects.create(title="P",created_by=user)
    with source.open("rb") as fh:
        image=MedicalImage(project=project,study_date=date.today(),modality="MRI",uploaded_by=user); image.file.save("safe.nii.gz",File(fh))
    model=ModelVersion.objects.create(name="Mock",version="1"); analysis=Analysis.objects.create(image=image,model_version=model,created_by=user)
    run_mock_analysis(analysis); analysis.refresh_from_db()
    assert analysis.status=="COMPLETED" and analysis.voxel_count>0
    assert analysis.volume_cm3 == pytest.approx(analysis.voxel_count*8/1000)
    assert analysis.mask_file and analysis.overlay_file

