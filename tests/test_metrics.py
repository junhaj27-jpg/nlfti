import numpy as np
import pytest
from core.metrics import lesion_volume_cm3, segmentation_metrics

def test_volume_converts_mm3_to_cm3(): assert lesion_volume_cm3(1000,(0.5,0.5,2.0)) == pytest.approx(0.5)
def test_volume_rejects_invalid_spacing():
    with pytest.raises(ValueError): lesion_volume_cm3(10,(1,0,1))
def test_segmentation_metrics_known_values():
    result=segmentation_metrics(np.array([1,1,0,0]),np.array([1,0,1,0]))
    assert result == pytest.approx({"dice":.5,"iou":1/3,"sensitivity":.5,"precision":.5})
def test_empty_masks_are_perfect(): assert segmentation_metrics([0,0],[0,0]) == {"dice":1,"iou":1,"sensitivity":1,"precision":1}

