from fastapi import FastAPI
from pydantic import BaseModel, Field
from core.metrics import lesion_volume_cm3, segmentation_metrics

app = FastAPI(title="Medical Imaging AI Analysis API", version="0.1.0", description="연구·포트폴리오용 mock 분석 및 성능지표 API")
class VolumeRequest(BaseModel): voxel_count: int = Field(ge=0); spacing_mm: tuple[float, float, float]
class MetricsRequest(BaseModel): prediction: list; reference: list
@app.get("/health")
def health(): return {"status": "ok"}
@app.post("/metrics/volume")
def volume(req: VolumeRequest): return {"volume_cm3": lesion_volume_cm3(req.voxel_count, req.spacing_mm), "unit": "cm³"}
@app.post("/metrics/segmentation")
def metrics(req: MetricsRequest): return segmentation_metrics(req.prediction, req.reference)
