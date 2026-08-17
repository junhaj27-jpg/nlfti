import os, threading, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .inference import InferenceConfig, run_inference

_jobs={}; _lock=threading.Lock(); _executor=ThreadPoolExecutor(max_workers=int(os.getenv("INFERENCE_WORKERS","1")))
def create_job(paths,output_root,config=None):
    job_id=str(uuid.uuid4()); job={"job_id":job_id,"status":"PENDING","progress":0,"error":"","result":None}
    with _lock: _jobs[job_id]=job
    def update(status,progress):
        with _lock: job.update(status=status,progress=progress)
    def work():
        try: job["result"]=run_inference(paths,Path(output_root)/job_id,config or InferenceConfig(),update)
        except Exception as exc: job.update(status="FAILED",error=str(exc)[:2000],progress=100)
    _executor.submit(work); return dict(job)
def get_job(job_id):
    with _lock: return dict(_jobs[job_id]) if job_id in _jobs else None
def clear_jobs():
    with _lock: _jobs.clear()
