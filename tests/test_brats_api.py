import time
import nibabel as nib
import numpy as np
from fastapi.testclient import TestClient
from analysis_api import main
from analysis_api.jobs import clear_jobs

def nifti_bytes(offset=0):
    data=(np.arange(512,dtype=np.float32)+offset).reshape(8,8,8); return nib.Nifti1Image(data,np.eye(4)).to_bytes()
def test_fastapi_mock_job_lifecycle(tmp_path,monkeypatch):
    clear_jobs(); monkeypatch.setattr(main,"WORK_ROOT",tmp_path); monkeypatch.setenv("INFERENCE_MODE","mock"); client=TestClient(main.app)
    files={key:(f"{key}.nii",nifti_bytes(i),"application/octet-stream") for i,key in enumerate(("t1","t1ce","t2","flair"))}
    response=client.post("/api/v1/inference/jobs",files=files); assert response.status_code==202; job_id=response.json()["job_id"]
    for _ in range(100):
        status=client.get(f"/api/v1/inference/jobs/{job_id}").json()
        if status["status"] in ("COMPLETED","FAILED"): break
        time.sleep(.02)
    assert status["status"]=="COMPLETED",status
    result=client.get(f"/api/v1/inference/jobs/{job_id}/results"); assert result.status_code==200
    assert result.json()["mode"]=="mock" and result.json()["whole_tumor_cm3"]>=0
def test_metrics_v1_endpoint():
    response=TestClient(main.app).post("/api/v1/metrics",json={"prediction":[1,0],"reference":[1,1]})
    assert response.status_code==200 and response.json()["dice"]==2/3

