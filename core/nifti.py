import gzip
from pathlib import Path
import nibabel as nib
import numpy as np
from django.conf import settings
from django.core.exceptions import ValidationError

MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024

def validate_nifti_path(path):
    path=Path(path); name=path.name.lower()
    if not (name.endswith(".nii") or name.endswith(".nii.gz")): raise ValidationError("NIfTI(.nii, .nii.gz) 파일만 허용됩니다.")
    if not path.is_file() or path.stat().st_size > settings.MAX_UPLOAD_SIZE: raise ValidationError("파일이 없거나 크기 제한을 초과했습니다.")
    if name.endswith(".gz"):
        total=0
        try:
            with gzip.open(path,"rb") as stream:
                while chunk:=stream.read(1024*1024):
                    total+=len(chunk)
                    if total>MAX_UNCOMPRESSED_BYTES: raise ValidationError("압축 해제 크기 제한을 초과했습니다.")
        except (OSError,EOFError) as exc: raise ValidationError("손상된 gzip NIfTI 파일입니다.") from exc
    try:
        image=nib.load(str(path)); shape=tuple(int(x) for x in image.shape)
        if len(shape)!=3 or any(x<=0 for x in shape): raise ValidationError("3차원 NIfTI 영상만 허용됩니다.")
        affine=np.asarray(image.affine,dtype=float); spacing=tuple(float(x) for x in image.header.get_zooms()[:3])
        if affine.shape!=(4,4) or not np.isfinite(affine).all() or any(x<=0 or not np.isfinite(x) for x in spacing): raise ValidationError("affine 또는 spacing이 올바르지 않습니다.")
        image.dataobj[0,0,0]
    except ValidationError: raise
    except Exception as exc: raise ValidationError("손상되었거나 읽을 수 없는 NIfTI 파일입니다.") from exc
    return {"shape":shape,"affine":affine,"spacing":spacing}

def validate_brats_files(paths):
    metadata={key:validate_nifti_path(path) for key,path in paths.items()}
    base=metadata["t1"]
    for key,item in metadata.items():
        if item["shape"]!=base["shape"]: raise ValidationError(f"{key} 영상의 shape이 T1과 일치하지 않습니다.")
        if not np.allclose(item["affine"],base["affine"],rtol=1e-5,atol=1e-4): raise ValidationError(f"{key} 영상의 affine이 T1과 일치하지 않습니다.")
        if not np.allclose(item["spacing"],base["spacing"],rtol=1e-5,atol=1e-4): raise ValidationError(f"{key} 영상의 spacing이 T1과 일치하지 않습니다.")
    return {"shape":list(base["shape"]),"affine":base["affine"].tolist(),"spacing":list(base["spacing"])}
