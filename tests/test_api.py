from fastapi.testclient import TestClient
from analysis_api.main import app
client=TestClient(app)
def test_volume_endpoint():
    response=client.post("/metrics/volume",json={"voxel_count":1000,"spacing_mm":[1,1,1]})
    assert response.status_code==200 and response.json()=={"volume_cm3":1.0,"unit":"cm³"}
