import copy, json, os, time
from dataclasses import dataclass
from pathlib import Path
import nibabel as nib
import numpy as np
from core.metrics import lesion_volume_cm3, segmentation_metrics
from core.nifti import validate_brats_files

@dataclass
class InferenceConfig:
    mode: str = os.getenv("INFERENCE_MODE","mock")
    model_path: str = os.getenv("MONAI_MODEL_PATH","")
    model_name: str = os.getenv("MONAI_MODEL_NAME","BraTS MONAI UNet")
    model_version: str = os.getenv("MONAI_MODEL_VERSION","unconfigured")
    roi_size: tuple = (128,128,128)
    sw_batch_size: int = 2
    mixed_precision: bool = os.getenv("MONAI_MIXED_PRECISION","1")=="1"
    min_component_voxels: int = 10

def _remove_small(mask,min_size):
    try:
        from scipy import ndimage
        output=np.zeros_like(mask,dtype=np.uint8)
        structure=ndimage.generate_binary_structure(3,1)
        for label_value in (1,2,4):
            labeled,count=ndimage.label(mask==label_value,structure=structure)
            sizes=np.bincount(labeled.ravel()); keep=np.flatnonzero(sizes>=min_size); keep=keep[keep!=0]
            output[np.isin(labeled,keep)]=label_value
        return output
    except ImportError:
        pass
    output=np.zeros_like(mask,dtype=np.uint8)
    for label_value in (1,2,4):
        candidates=set(map(tuple,np.argwhere(mask==label_value)))
        while candidates:
            seed=candidates.pop(); component=[seed]; stack=[seed]
            while stack:
                point=stack.pop()
                for axis in range(3):
                    for delta in (-1,1):
                        neighbor=list(point); neighbor[axis]+=delta; neighbor=tuple(neighbor)
                        if neighbor in candidates: candidates.remove(neighbor); component.append(neighbor); stack.append(neighbor)
            if len(component)>=min_size:
                coordinates=np.array(component); output[tuple(coordinates.T)]=label_value
    return output

def _mock(paths):
    volumes=[np.asarray(nib.load(str(paths[k])).dataobj,dtype=np.float32) for k in ("t1","t1ce","t2","flair")]
    flair,t1ce=volumes[3],volumes[1]; foreground=flair[np.isfinite(flair) & (flair!=0)]
    if foreground.size==0: return np.zeros(flair.shape,dtype=np.uint8)
    whole=flair>np.percentile(foreground,85); core=whole & (t1ce>np.percentile(t1ce[np.isfinite(t1ce)],85)); enhancing=core & (t1ce>np.percentile(t1ce[np.isfinite(t1ce)],95))
    result=np.zeros(flair.shape,dtype=np.uint8); result[whole]=1; result[core]=2; result[enhancing]=4; return result

def _load_model(config,device):
    import torch
    from monai.networks.nets import UNet
    if not config.model_path or not Path(config.model_path).is_file(): raise FileNotFoundError("MONAI_MODEL_PATH에 사전 학습 가중치를 지정하십시오. 개발 시 INFERENCE_MODE=mock을 사용할 수 있습니다.")
    try: return torch.jit.load(config.model_path,map_location=device).eval()
    except Exception:
        model=UNet(spatial_dims=3,in_channels=4,out_channels=3,channels=(16,32,64,128,256),strides=(2,2,2,2),num_res_units=2)
        state=torch.load(config.model_path,map_location=device,weights_only=True); model.load_state_dict(state.get("state_dict",state)); return model.to(device).eval()

def _monai(paths,config):
    import torch
    from monai.inferers import sliding_window_inference
    from monai.transforms import Compose, CropForegroundd, EnsureChannelFirstd, Invertd, LoadImaged, NormalizeIntensityd, Orientationd, Spacingd
    device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pre=Compose([LoadImaged("image"),EnsureChannelFirstd("image"),Orientationd("image",axcodes="RAS"),Spacingd("image",pixdim=(1,1,1),mode="bilinear"),NormalizeIntensityd("image",nonzero=True,channel_wise=True),CropForegroundd("image",source_key="image")])
    transformed=pre({"image":[str(paths[k]) for k in ("t1","t1ce","t2","flair")]}); image=transformed["image"].unsqueeze(0).to(device); model=_load_model(config,device)
    roi,batch=config.roi_size,config.sw_batch_size
    for attempt in range(2):
        try:
            with torch.inference_mode(), torch.autocast(device_type=device.type,enabled=config.mixed_precision and device.type=="cuda"):
                logits=sliding_window_inference(image,roi,batch,model,overlap=.5)
            break
        except torch.cuda.OutOfMemoryError:
            if attempt: raise
            torch.cuda.empty_cache(); roi=tuple(max(32,x//2) for x in roi); batch=1
    probs=torch.sigmoid(logits[0]); pred=torch.zeros(probs.shape[1:],dtype=torch.uint8,device=device); pred[probs[0]>.5]=1; pred[probs[1]>.5]=2; pred[probs[2]>.5]=4
    transformed["pred"]=pred.unsqueeze(0)
    restored=Invertd(keys="pred",transform=pre,orig_keys="image",nearest_interp=True,to_tensor=True)(transformed)["pred"].squeeze().detach().cpu().numpy().astype(np.uint8)
    original=nib.load(str(paths["t1"]))
    if restored.shape!=original.shape: raise RuntimeError(f"원본 공간 복원 shape 불일치: {restored.shape} != {original.shape}")
    return restored,str(device),roi,batch

def _overlay(base,mask,path):
    from PIL import Image
    z=int(np.argmax((mask>0).sum(axis=(0,1)))) if np.any(mask) else mask.shape[2]//2
    plane=np.nan_to_num(base[:,:,z]); plane=(255*(plane-plane.min())/(np.ptp(plane) or 1)).astype(np.uint8); rgb=np.stack([plane]*3,-1); colors={1:(255,215,0),2:(255,80,80),4:(180,40,255)}
    for label,color in colors.items():
        hit=mask[:,:,z]==label; rgb[hit]=(0.45*rgb[hit]+0.55*np.array(color)).astype(np.uint8)
    Image.fromarray(np.rot90(rgb)).save(path)

def run_inference(paths,output_dir,config=None,progress=None):
    config=config or InferenceConfig(); output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True); progress=progress or (lambda *args:None)
    progress("VALIDATING",5); metadata=validate_brats_files(paths); start_pre=time.perf_counter(); progress("PREPROCESSING",20)
    if config.mode=="mock":
        pre_done=time.perf_counter(); progress("RUNNING",45); inference_start=time.perf_counter(); mask=_mock(paths); device="cpu/mock"; effective_roi=config.roi_size; effective_batch=config.sw_batch_size
    else:
        pre_done=time.perf_counter(); progress("RUNNING",45); mask,device,effective_roi,effective_batch=_monai(paths,config); start_infer=pre_done
    preprocessing_seconds=pre_done-start_pre
    if config.mode!="mock": inference_start=start_infer
    progress("POSTPROCESSING",85); mask=_remove_small(mask,config.min_component_voxels); image=nib.load(str(paths["t1"])); segmentation=output_dir/"segmentation.nii.gz"; nib.save(nib.Nifti1Image(mask,image.affine,image.header),segmentation)
    spacing=metadata["spacing"]; counts={"whole_tumor":int(np.isin(mask,[1,2,4]).sum()),"tumor_core":int(np.isin(mask,[2,4]).sum()),"enhancing_tumor":int((mask==4).sum())}; volumes={k+"_cm3":lesion_volume_cm3(v,spacing) for k,v in counts.items()}
    metrics={}
    if "reference" in paths and paths["reference"]:
        ref=np.asarray(nib.load(str(paths["reference"])).dataobj); metrics={"whole_tumor":segmentation_metrics(np.isin(mask,[1,2,4]),np.isin(ref,[1,2,4])),"tumor_core":segmentation_metrics(np.isin(mask,[2,4]),np.isin(ref,[2,4])),"enhancing_tumor":segmentation_metrics(mask==4,ref==4)}
    overlay=output_dir/"overlay.png"; _overlay(np.asarray(image.dataobj,dtype=np.float32),mask,overlay)
    result={**counts,**volumes,"spacing":spacing,"metrics":metrics,"model_name":config.model_name,"model_version":config.model_version,"mode":config.mode,"device":device,"mixed_precision":config.mixed_precision and device.startswith("cuda"),"preprocessing_seconds":preprocessing_seconds,"inference_seconds":time.perf_counter()-inference_start,"effective_roi_size":effective_roi,"effective_sw_batch_size":effective_batch}
    metrics_path=output_dir/"metrics.json"; metrics_path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8"); progress("COMPLETED",100)
    return {"segmentation":str(segmentation),"overlay":str(overlay),"metrics_file":str(metrics_path),**result}
