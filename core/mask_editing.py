import io, json, tempfile
from pathlib import Path
import nibabel as nib
import numpy as np
from PIL import Image
from django.conf import settings
from django.core.files import File
from django.core.exceptions import ValidationError
from .metrics import lesion_volume_cm3,segmentation_metrics
from .models import AuditLog,MaskCorrection

def slice_png(result,z):
    source=nib.load(result.job.study.flair.path); volume=np.asarray(source.dataobj,dtype=np.float32)
    if z<0 or z>=volume.shape[2]: raise ValidationError("유효하지 않은 slice입니다.")
    plane=np.nan_to_num(volume[:,:,z]); plane=(255*(plane-plane.min())/(np.ptp(plane) or 1)).astype(np.uint8)
    out=io.BytesIO(); Image.fromarray(plane).save(out,"PNG"); return out.getvalue(),volume.shape

def _brush(mask,z,stroke):
    mode=stroke.get("mode"); label=int(stroke.get("label",1)); radius=max(1,min(int(stroke.get("radius",3)),50))
    if mode not in ("add","remove") or label not in (1,2,4): raise ValidationError("브러시 설정이 올바르지 않습니다.")
    rows,cols=mask.shape[:2]
    for point in stroke.get("points",[]):
        if len(point)!=2: continue
        x,y=int(point[0]),int(point[1]); y0,y1=max(0,y-radius),min(rows,y+radius+1); x0,x1=max(0,x-radius),min(cols,x+radius+1)
        yy,xx=np.ogrid[y0:y1,x0:x1]; hit=(xx-x)**2+(yy-y)**2<=radius**2
        target=mask[y0:y1,x0:x1,z]; target[hit]=label if mode=="add" else 0

def create_correction(result,editor,reason,z,strokes):
    if not reason.strip(): raise ValidationError("수정 이유를 입력해야 합니다.")
    original=nib.load(result.segmentation_file.path); mask=np.asarray(original.dataobj,dtype=np.uint8).copy()
    if z<0 or z>=mask.shape[2]: raise ValidationError("유효하지 않은 slice입니다.")
    for stroke in strokes: _brush(mask,z,stroke)
    spacing=tuple(float(x) for x in original.header.get_zooms()[:3]); counts={"whole_tumor":int(np.isin(mask,[1,2,4]).sum()),"tumor_core":int(np.isin(mask,[2,4]).sum()),"enhancing_tumor":int((mask==4).sum())}
    metrics={}
    if result.job.study.reference_mask:
        ref=np.asarray(nib.load(result.job.study.reference_mask.path).dataobj)
        metrics={"whole_tumor":segmentation_metrics(np.isin(mask,[1,2,4]),np.isin(ref,[1,2,4])),"tumor_core":segmentation_metrics(np.isin(mask,[2,4]),np.isin(ref,[2,4])),"enhancing_tumor":segmentation_metrics(mask==4,ref==4)}
    runtime=settings.BASE_DIR/"inference-work"/"corrections"; runtime.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=runtime) as temp:
        target=Path(temp)/"corrected.nii.gz"; nib.save(nib.Nifti1Image(mask,original.affine,original.header),target)
        overlay_target=Path(temp)/"corrected-overlay.png"; base=np.asarray(nib.load(result.job.study.flair.path).dataobj,dtype=np.float32); best=int(np.argmax((mask>0).sum(axis=(0,1)))) if np.any(mask) else z; plane=np.nan_to_num(base[:,:,best]); plane=(255*(plane-plane.min())/(np.ptp(plane) or 1)).astype(np.uint8); rgb=np.stack([plane]*3,-1)
        for value,color in ((1,(255,215,0)),(2,(255,80,80)),(4,(180,40,255))):
            hit=mask[:,:,best]==value; rgb[hit]=(0.45*rgb[hit]+0.55*np.array(color)).astype(np.uint8)
        Image.fromarray(rgb).save(overlay_target)
        correction=MaskCorrection(result=result,reason=reason,editor=editor,whole_tumor_voxels=counts["whole_tumor"],tumor_core_voxels=counts["tumor_core"],enhancing_tumor_voxels=counts["enhancing_tumor"],whole_tumor_cm3=lesion_volume_cm3(counts["whole_tumor"],spacing),tumor_core_cm3=lesion_volume_cm3(counts["tumor_core"],spacing),enhancing_tumor_cm3=lesion_volume_cm3(counts["enhancing_tumor"],spacing),metrics=metrics)
        with target.open("rb") as stream: correction.corrected_mask_file.save("corrected.nii.gz",File(stream),save=False)
        with overlay_target.open("rb") as stream: correction.corrected_overlay_file.save("corrected-overlay.png",File(stream),save=False)
        correction.save()
    AuditLog.objects.create(actor=editor,action="MASK_CORRECTION_CREATED",entity_type="MaskCorrection",entity_id=str(correction.pk),details={"result_id":result.pk,"slice":z,"reason":reason,"requires_re_review":result.job.approved})
    return correction
