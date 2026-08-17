from django.conf import settings
from django.core.exceptions import ValidationError

def validate_nifti(upload):
    name = upload.name.lower()
    if not (name.endswith(".nii") or name.endswith(".nii.gz")): raise ValidationError("NIfTI(.nii, .nii.gz) 파일만 허용됩니다.")
    if upload.size > settings.MAX_UPLOAD_SIZE: raise ValidationError("파일 크기 제한을 초과했습니다.")
    if "/" in upload.name or "\\" in upload.name or ".." in upload.name: raise ValidationError("안전하지 않은 파일명입니다.")

