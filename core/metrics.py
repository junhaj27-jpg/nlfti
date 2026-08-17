import numpy as np

def lesion_volume_cm3(voxel_count, spacing_mm):
    if voxel_count < 0 or len(spacing_mm) != 3 or any(float(x) <= 0 for x in spacing_mm):
        raise ValueError("voxel_count와 3축 spacing은 유효한 양수여야 합니다.")
    return float(voxel_count) * float(np.prod(spacing_mm)) / 1000.0

def segmentation_metrics(prediction, reference):
    pred, ref = np.asarray(prediction, dtype=bool), np.asarray(reference, dtype=bool)
    if pred.shape != ref.shape: raise ValueError("마스크 크기가 같아야 합니다.")
    tp = np.logical_and(pred, ref).sum(); fp = np.logical_and(pred, ~ref).sum(); fn = np.logical_and(~pred, ref).sum()
    return {
        "dice": 1.0 if 2*tp+fp+fn == 0 else float(2*tp/(2*tp+fp+fn)),
        "iou": 1.0 if tp+fp+fn == 0 else float(tp/(tp+fp+fn)),
        "sensitivity": 1.0 if tp+fn == 0 else float(tp/(tp+fn)),
        "precision": 1.0 if tp+fp == 0 else float(tp/(tp+fp)),
    }

