import nibabel as nib
import numpy as np
import pytest
from django.core.exceptions import ValidationError
from core.nifti import validate_brats_files, validate_nifti_path

def save_nifti(path,shape=(8,8,8),affine=None):
    nib.save(nib.Nifti1Image(np.zeros(shape,dtype=np.float32),affine if affine is not None else np.eye(4)),path); return path
def test_valid_brats_nifti(tmp_path,settings):
    settings.MAX_UPLOAD_SIZE=10*1024*1024; paths={key:save_nifti(tmp_path/f"{key}.nii") for key in ("t1","t1ce","t2","flair")}
    metadata=validate_brats_files(paths); assert metadata["shape"]==[8,8,8] and metadata["spacing"]==[1,1,1]
def test_shape_mismatch_is_rejected(tmp_path,settings):
    settings.MAX_UPLOAD_SIZE=10*1024*1024; paths={key:save_nifti(tmp_path/f"{key}.nii") for key in ("t1","t1ce","t2","flair")}; paths["flair"]=save_nifti(tmp_path/"bad.nii",(7,8,8))
    with pytest.raises(ValidationError,match="shape"): validate_brats_files(paths)
def test_corrupt_nifti_is_rejected(tmp_path,settings):
    settings.MAX_UPLOAD_SIZE=1024; path=tmp_path/"broken.nii"; path.write_bytes(b"not nifti")
    with pytest.raises(ValidationError,match="손상"): validate_nifti_path(path)

