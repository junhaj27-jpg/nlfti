import json, tempfile
from pathlib import Path
from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.utils import timezone
from analysis_api.inference import InferenceConfig, run_inference
from .models import AnalysisJob, AnalysisResult, AuditLog
from .nifti import validate_brats_files

def study_paths(study):
    paths={"t1":study.t1.path,"t1ce":study.t1ce.path,"t2":study.t2.path,"flair":study.flair.path}
    if study.reference_mask: paths["reference"]=study.reference_mask.path
    return paths

@transaction.atomic
def validate_study(study):
    metadata=validate_brats_files(study_paths(study)); study.shape=metadata["shape"]; study.affine=metadata["affine"]; study.spacing=metadata["spacing"]; study.save(update_fields=["shape","affine","spacing"]); return metadata

def execute_job(job,config=None):
    config=config or InferenceConfig(); job.status=AnalysisJob.Status.VALIDATING; job.progress=5; job.started_at=timezone.now(); job.inference_mode=config.mode; job.save()
    AuditLog.objects.create(actor=job.created_by,action="JOB_STARTED",entity_type="AnalysisJob",entity_id=str(job.pk),details={"mode":config.mode})
    last_status={"value":job.status}
    def update(status,progress):
        AnalysisJob.objects.filter(pk=job.pk).update(status=status,progress=progress)
        if status!=last_status["value"]:
            AuditLog.objects.create(actor=job.created_by,action="JOB_STATUS_CHANGED",entity_type="AnalysisJob",entity_id=str(job.pk),details={"from":last_status["value"],"to":status,"progress":progress}); last_status["value"]=status
    try:
        runtime_root=settings.BASE_DIR/"inference-work"/"django"; runtime_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime_root) as temp:
            payload=run_inference(study_paths(job.study),temp,config,update)
            with transaction.atomic():
                result=AnalysisResult(job=job,whole_tumor_voxels=payload["whole_tumor"],tumor_core_voxels=payload["tumor_core"],enhancing_tumor_voxels=payload["enhancing_tumor"],whole_tumor_cm3=payload["whole_tumor_cm3"],tumor_core_cm3=payload["tumor_core_cm3"],enhancing_tumor_cm3=payload["enhancing_tumor_cm3"],spacing=payload["spacing"],metrics=payload["metrics"])
                for field,key in (("segmentation_file","segmentation"),("overlay_file","overlay"),("metrics_file","metrics_file")):
                    with open(payload[key],"rb") as stream: getattr(result,field).save(Path(payload[key]).name,File(stream),save=False)
                result.save(); job.refresh_from_db(); job.status=AnalysisJob.Status.COMPLETED; job.progress=100; job.device=payload["device"]; job.mixed_precision=payload["mixed_precision"]; job.preprocessing_seconds=payload["preprocessing_seconds"]; job.inference_seconds=payload["inference_seconds"]; job.finished_at=timezone.now(); job.error_message=""; job.save()
        AuditLog.objects.create(actor=job.created_by,action="JOB_COMPLETED",entity_type="AnalysisJob",entity_id=str(job.pk),details={"device":job.device,"mode":job.inference_mode})
    except Exception as exc:
        job.refresh_from_db(); job.status=AnalysisJob.Status.FAILED; job.progress=100; job.finished_at=timezone.now(); job.error_message=str(exc)[:2000]; job.exception_history=[*job.exception_history,{"at":timezone.now().isoformat(),"message":str(exc)[:500]}]; job.save()
        AuditLog.objects.create(actor=job.created_by,action="JOB_FAILED",entity_type="AnalysisJob",entity_id=str(job.pk),details={"error_type":type(exc).__name__}); raise
    return job
