import io, time, uuid
import nibabel as nib
import numpy as np
from PIL import Image
from django.core.files.base import ContentFile
from django.db import transaction
from .metrics import lesion_volume_cm3, segmentation_metrics
from .models import Analysis, AuditLog

def _overlay_png(volume, mask):
    z = volume.shape[2] // 2
    base = np.nan_to_num(volume[:, :, z]); base = (255*(base-base.min())/(np.ptp(base) or 1)).astype("uint8")
    rgb = np.stack([base]*3, axis=-1); hit = mask[:, :, z].astype(bool)
    rgb[hit] = (0.65*rgb[hit] + 0.35*np.array([255, 40, 40])).astype("uint8")
    out=io.BytesIO(); Image.fromarray(np.rot90(rgb)).save(out, "PNG"); return out.getvalue()

@transaction.atomic
def run_mock_analysis(analysis):
    started=time.perf_counter(); analysis.status=Analysis.Status.RUNNING; analysis.save(update_fields=["status", "updated_at"])
    try:
        image=nib.load(analysis.image.file.path); data=np.asarray(image.dataobj, dtype=np.float32)
        threshold=float(np.percentile(data, 90)); mask=(data > threshold).astype(np.uint8)
        spacing=tuple(float(x) for x in image.header.get_zooms()[:3]); count=int(mask.sum())
        mask_img=nib.Nifti1Image(mask, image.affine, image.header)
        analysis.mask_file.save(f"{uuid.uuid4().hex}.nii", ContentFile(mask_img.to_bytes()), save=False)
        analysis.overlay_file.save(f"{uuid.uuid4().hex}.png", ContentFile(_overlay_png(data, mask)), save=False)
        analysis.voxel_count=count; analysis.spacing_x,analysis.spacing_y,analysis.spacing_z=spacing
        analysis.volume_cm3=lesion_volume_cm3(count, spacing)
        if analysis.image.reference_mask:
            ref=np.asarray(nib.load(analysis.image.reference_mask.path).dataobj)>0
            for key,value in segmentation_metrics(mask, ref).items(): setattr(analysis,key,value)
        analysis.runtime_seconds=time.perf_counter()-started; analysis.status=Analysis.Status.COMPLETED; analysis.error_message=""; analysis.save()
    except Exception as exc:
        analysis.status=Analysis.Status.FAILED; analysis.error_message=str(exc)[:2000]; analysis.runtime_seconds=time.perf_counter()-started; analysis.save(); raise
    AuditLog.objects.create(actor=analysis.created_by, action="ANALYSIS_COMPLETED", entity_type="Analysis", entity_id=str(analysis.pk), details={"mock_inference":True})
    return analysis
