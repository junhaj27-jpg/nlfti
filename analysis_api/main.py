import os, shutil, uuid
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from core.metrics import lesion_volume_cm3, segmentation_metrics
from .jobs import create_job, get_job

app=FastAPI(title="MedVision BraTS Inference API",version="1.0.0",description="MONAI 기반 4-channel 뇌종양 MRI segmentation 작업 API")
WORK_ROOT=Path(os.getenv("INFERENCE_WORK_DIR","inference-work")).resolve()
MAX_UPLOAD=int(os.getenv("MAX_UPLOAD_MB","50"))*1024*1024

class MetricsRequest(BaseModel): prediction:list; reference:list
class VolumeRequest(BaseModel): voxel_count:int=Field(ge=0); spacing_mm:tuple[float,float,float]
def _save(upload,directory,label):
    name=(upload.filename or "").lower(); suffix=".nii.gz" if name.endswith(".nii.gz") else ".nii" if name.endswith(".nii") else None
    if not suffix: raise HTTPException(422,f"{label}: .nii 또는 .nii.gz만 허용됩니다.")
    target=directory/f"{uuid.uuid4().hex}{suffix}"; size=0
    with target.open("wb") as out:
        while chunk:=upload.file.read(1024*1024):
            size+=len(chunk)
            if size>MAX_UPLOAD: out.close(); target.unlink(missing_ok=True); raise HTTPException(413,f"{label}: 파일 크기 제한 초과")
            out.write(chunk)
    return target

@app.get("/health")
def health(): return {"status":"ok","inference_mode":os.getenv("INFERENCE_MODE","mock")}
@app.post("/api/v1/inference/jobs",status_code=202)
def submit_job(t1:UploadFile=File(...),t1ce:UploadFile=File(...),t2:UploadFile=File(...),flair:UploadFile=File(...),reference:UploadFile|None=File(None)):
    directory=WORK_ROOT/"uploads"/uuid.uuid4().hex; directory.mkdir(parents=True,exist_ok=False)
    try:
        paths={key:_save(upload,directory,key) for key,upload in (("t1",t1),("t1ce",t1ce),("t2",t2),("flair",flair))}
        if reference: paths["reference"]=_save(reference,directory,"reference")
        return create_job(paths,WORK_ROOT/"results")
    except Exception:
        shutil.rmtree(directory,ignore_errors=True); raise
@app.get("/api/v1/inference/jobs/{job_id}")
def job_status(job_id:str):
    job=get_job(job_id)
    if not job: raise HTTPException(404,"작업을 찾을 수 없습니다.")
    return {k:v for k,v in job.items() if k!="result"}
@app.get("/api/v1/inference/jobs/{job_id}/results")
def job_results(job_id:str):
    job=get_job(job_id)
    if not job: raise HTTPException(404,"작업을 찾을 수 없습니다.")
    if job["status"]!="COMPLETED": raise HTTPException(409,"작업이 아직 완료되지 않았습니다.")
    return job["result"]
@app.post("/api/v1/metrics")
def metrics(req:MetricsRequest): return segmentation_metrics(req.prediction,req.reference)
@app.post("/metrics/volume",deprecated=True)
def legacy_volume(req:VolumeRequest): return {"volume_cm3":lesion_volume_cm3(req.voxel_count,req.spacing_mm),"unit":"cm³"}
@app.post("/metrics/segmentation",deprecated=True)
def legacy_metrics(req:MetricsRequest): return metrics(req)
