from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Avg,Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.conf import settings
from pathlib import Path
import mimetypes
import json
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .decorators import roles_required
from django.core.exceptions import PermissionDenied,ValidationError
from .forms import ProjectForm, MedicalImageForm, ReviewForm, MRIStudyForm, JobReviewForm, CorrectionReviewForm, SubjectForm, HazardForm, RiskAssessmentForm, RiskControlForm, NonconformityForm, CAPAForm
from .models import Analysis, Review, AuditLog, ModelVersion, Project, MRIStudy, AnalysisJob, JobReview, AnalysisResult, MaskCorrection, CorrectionReview, Subject, Hazard, RiskAssessment, RiskControl, Nonconformity, CAPA, user_role
from .tracking import subject_timeline
from .quality import transition_capa
from .mask_editing import create_correction, slice_png
from .brats_service import execute_job, validate_study
from .reports import build_ra_report,build_risk_report,build_capa_report
from .services import run_mock_analysis

def health(request):
    from django.db import connection
    with connection.cursor() as cursor: cursor.execute("SELECT 1"); cursor.fetchone()
    return JsonResponse({"status":"ok","service":"django"})

@login_required
def protected_media(request,path):
    root=Path(settings.MEDIA_ROOT).resolve(); target=(root/path).resolve()
    try: target.relative_to(root)
    except ValueError: raise Http404
    if not target.is_file(): raise Http404
    response=FileResponse(target.open("rb"),content_type=mimetypes.guess_type(target.name)[0] or "application/octet-stream")
    response["Cache-Control"]="private, no-store"; response["X-Content-Type-Options"]="nosniff"; return response

@login_required
def dashboard(request):
    jobs=AnalysisJob.objects.all(); completed=jobs.filter(status="COMPLETED"); model_dice={}
    for result in AnalysisResult.objects.select_related("job").all():
        dice=result.metrics.get("whole_tumor",{}).get("dice")
        if dice is not None: model_dice.setdefault(str(result.job.model_version),[]).append(float(dice))
    legacy=Analysis.objects.all(); times=[x for x in completed.values_list("inference_seconds",flat=True) if x is not None]+[x for x in legacy.filter(status="COMPLETED").values_list("runtime_seconds",flat=True) if x is not None]; first_subject=Subject.objects.first(); volume_timeline=subject_timeline(first_subject) if first_subject else []
    stats={"total":jobs.count()+legacy.count(),"success":completed.count()+legacy.filter(status="COMPLETED").count(),"failed":jobs.filter(status="FAILED").count()+legacy.filter(status="FAILED").count(),"approved":JobReview.objects.filter(decision="APPROVED").count()+Review.objects.filter(decision="APPROVED").count(),"rejected":JobReview.objects.filter(decision="REJECTED").count()+Review.objects.filter(decision="REJECTED").count(),"avg_inference":sum(times)/len(times) if times else 0,"open_capa":CAPA.objects.exclude(status="CLOSED").count(),"overdue_capa":sum(1 for c in CAPA.objects.exclude(status="CLOSED") if c.overdue),"model_dice":{k:sum(v)/len(v) for k,v in model_dice.items()}}
    return render(request,"core/dashboard.html",{"projects":Project.objects.all().order_by("-created_at"),"role":user_role(request.user),"stats":stats,"subjects":Subject.objects.all()[:10],"volume_timeline":volume_timeline,"volume_subject":first_subject})
@roles_required("ANALYST","ADMIN")
def project_create(request):
    form=ProjectForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        obj=form.save(commit=False); obj.created_by=request.user; obj.save(); AuditLog.objects.create(actor=request.user,action="CREATE",entity_type="Project",entity_id=str(obj.pk)); return redirect("project_detail",pk=obj.pk)
    return render(request,"core/form.html",{"form":form,"title":"프로젝트 생성"})
@login_required
def project_detail(request,pk): return render(request,"core/project_detail.html",{"project":get_object_or_404(Project,pk=pk),"role":user_role(request.user),"models":ModelVersion.objects.filter(active=True)})
@roles_required("ANALYST","ADMIN")
def image_upload(request,pk):
    project=get_object_or_404(Project,pk=pk); form=MedicalImageForm(request.POST or None,request.FILES or None)
    if request.method=="POST" and form.is_valid():
        obj=form.save(commit=False); obj.project=project; obj.uploaded_by=request.user; obj.save(); AuditLog.objects.create(actor=request.user,action="UPLOAD",entity_type="MedicalImage",entity_id=str(obj.pk)); return redirect("project_detail",pk=pk)
    return render(request,"core/form.html",{"form":form,"title":"익명화 NIfTI 등록"})
@roles_required("ANALYST","ADMIN")
@require_POST
def analysis_run(request,image_id):
    model=get_object_or_404(ModelVersion,pk=request.POST.get("model_version"),active=True); from .models import MedicalImage
    image=get_object_or_404(MedicalImage,pk=image_id); analysis=Analysis.objects.create(image=image,model_version=model,created_by=request.user)
    try: run_mock_analysis(analysis); messages.success(request,"Mock 분석을 완료했습니다.")
    except Exception: messages.error(request,"분석에 실패했습니다. 오류 메시지를 확인하세요.")
    return redirect("analysis_detail",pk=analysis.pk)
@login_required
def analysis_detail(request,pk): return render(request,"core/analysis_detail.html",{"analysis":get_object_or_404(Analysis,pk=pk),"role":user_role(request.user),"review_form":ReviewForm()})
@roles_required("REVIEWER","ADMIN")
@require_POST
@transaction.atomic
def review_create(request,pk):
    analysis=get_object_or_404(Analysis.objects.select_for_update(),pk=pk); form=ReviewForm(request.POST)
    if form.is_valid():
        review=form.save(commit=False); review.analysis=analysis; review.reviewer=request.user; review.save(); AuditLog.objects.create(actor=request.user,action=review.decision,entity_type="Analysis",entity_id=str(pk),details={"comment":review.comment}); messages.success(request,"검토 결과를 기록했습니다.")
    return redirect("analysis_detail",pk=pk)
@login_required
def report_download(request,pk):
    project=get_object_or_404(Project,pk=pk)
    if project.mri_studies.exists() and not JobReview.objects.filter(job__study__project=project,decision=JobReview.Decision.APPROVED).exists():
        messages.error(request,"BraTS RA 보고서는 하나 이상의 분석 결과가 승인된 후 생성할 수 있습니다."); return redirect("project_detail",pk=pk)
    data=build_ra_report(project); AuditLog.objects.create(actor=request.user,action="REPORT_DOWNLOAD",entity_type="Project",entity_id=str(pk))
    response=HttpResponse(data,content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"); response["Content-Disposition"]=f'attachment; filename="RA-report-{pk}.docx"'; return response

@roles_required("ANALYST","ADMIN")
def mri_study_upload(request,pk):
    project=get_object_or_404(Project,pk=pk); form=MRIStudyForm(request.POST or None,request.FILES or None,project=project)
    if request.method=="POST" and form.is_valid():
        study=form.save(commit=False); study.project=project; study.uploaded_by=request.user; study.save()
        try: validate_study(study)
        except ValidationError as exc:
            for field in (study.t1,study.t1ce,study.t2,study.flair,study.reference_mask):
                if field: field.delete(save=False)
            study.delete(); form.add_error(None,exc)
        else:
            AuditLog.objects.create(actor=request.user,action="BRATS_UPLOAD",entity_type="MRIStudy",entity_id=str(study.pk),details={"shape":study.shape,"spacing":study.spacing}); return redirect("project_detail",pk=pk)
    return render(request,"core/form.html",{"form":form,"title":"BraTS MRI 4채널 등록"})

@roles_required("ANALYST","ADMIN")
@require_POST
def brats_job_run(request,study_id):
    study=get_object_or_404(MRIStudy,pk=study_id); model=get_object_or_404(ModelVersion,pk=request.POST.get("model_version"),active=True)
    job=AnalysisJob.objects.create(study=study,model_version=model,model_name=model.name,model_version_name=model.version,created_by=request.user,inference_mode=request.POST.get("inference_mode","mock"))
    from analysis_api.inference import InferenceConfig
    try: execute_job(job,InferenceConfig(mode=job.inference_mode,model_name=model.name,model_version=model.version))
    except Exception: messages.error(request,"추론에 실패했습니다. 작업 오류를 확인하세요.")
    return redirect("brats_job_detail",pk=job.pk)

@login_required
def brats_job_detail(request,pk): return render(request,"core/brats_job_detail.html",{"job":get_object_or_404(AnalysisJob,pk=pk),"role":user_role(request.user),"review_form":JobReviewForm()})

@roles_required("REVIEWER","ADMIN")
@require_POST
@transaction.atomic
def brats_review_create(request,pk):
    job=get_object_or_404(AnalysisJob.objects.select_for_update(),pk=pk); form=JobReviewForm(request.POST)
    if form.is_valid():
        review=form.save(commit=False); review.job=job; review.reviewer=request.user; review.save(); AuditLog.objects.create(actor=request.user,action=review.decision,entity_type="AnalysisJob",entity_id=str(pk),details={"comment":review.comment}); messages.success(request,"검토 결과를 기록했습니다.")
    return redirect("brats_job_detail",pk=pk)

@roles_required("ANALYST","ADMIN")
def mask_editor(request,pk):
    result=get_object_or_404(AnalysisResult,pk=pk); import nibabel as nib
    shape=nib.load(result.segmentation_file.path).shape
    return render(request,"core/mask_editor.html",{"result":result,"shape":shape,"initial_slice":shape[2]//2})

@login_required
def mask_slice(request,pk,z):
    data,_=slice_png(get_object_or_404(AnalysisResult,pk=pk),z); return HttpResponse(data,content_type="image/png")

@roles_required("ANALYST","ADMIN")
@require_POST
def mask_correction_create(request,pk):
    result=get_object_or_404(AnalysisResult,pk=pk)
    try:
        payload=json.loads(request.body); correction=create_correction(result,request.user,payload.get("reason",""),int(payload.get("slice",-1)),payload.get("strokes",[]))
        return JsonResponse({"id":correction.pk,"status":correction.status,"redirect":request.build_absolute_uri(f"/brats/jobs/{result.job_id}/")})
    except (ValueError,ValidationError,json.JSONDecodeError) as exc: return JsonResponse({"error":str(exc)},status=400)

@roles_required("REVIEWER","ADMIN")
@require_POST
@transaction.atomic
def correction_review_create(request,pk):
    correction=get_object_or_404(MaskCorrection.objects.select_for_update(),pk=pk); form=CorrectionReviewForm(request.POST)
    if correction.status!=MaskCorrection.Status.PENDING_REVIEW:
        messages.error(request,"이미 재검토가 완료된 수정본입니다."); return redirect("brats_job_detail",pk=correction.result.job_id)
    if form.is_valid():
        review=form.save(commit=False); review.correction=correction; review.reviewer=request.user; review.save(); correction.status=MaskCorrection.Status.APPROVED if review.decision==JobReview.Decision.APPROVED else MaskCorrection.Status.REJECTED; correction.save(update_fields=["status","updated_at"]); AuditLog.objects.create(actor=request.user,action=f"CORRECTION_{review.decision}",entity_type="MaskCorrection",entity_id=str(pk),details={"comment":review.comment})
    return redirect("brats_job_detail",pk=correction.result.job_id)

@roles_required("ANALYST","ADMIN")
def subject_create(request,pk):
    project=get_object_or_404(Project,pk=pk); form=SubjectForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        subject=form.save(commit=False); subject.project=project; subject.save(); AuditLog.objects.create(actor=request.user,action="SUBJECT_CREATED",entity_type="Subject",entity_id=str(subject.pk)); return redirect("subject_detail",pk=subject.pk)
    return render(request,"core/form.html",{"form":form,"title":"익명 Subject 등록"})
@login_required
def subject_detail(request,pk):
    subject=get_object_or_404(Subject,pk=pk); return render(request,"core/subject_detail.html",{"subject":subject,"timeline":subject_timeline(subject)})

@login_required
def quality_dashboard(request,pk):
    project=get_object_or_404(Project,pk=pk); return render(request,"core/quality_dashboard.html",{"project":project,"role":user_role(request.user)})

@roles_required("ANALYST","ADMIN")
def quality_create(request,pk,kind):
    project=get_object_or_404(Project,pk=pk); mapping={"hazard":(HazardForm,"위험요인 등록"),"risk":(RiskAssessmentForm,"위험평가 등록"),"nc":(NonconformityForm,"부적합 등록"),"capa":(CAPAForm,"CAPA 등록")}
    if kind not in mapping: raise ValidationError("지원하지 않는 품질 항목입니다.")
    form_class,title=mapping[kind]; kwargs={"project":project} if kind in ("risk","nc","capa") else {}; form=form_class(request.POST or None,**kwargs)
    if request.method=="POST" and form.is_valid():
        obj=form.save(commit=False)
        if kind in ("hazard","nc"): obj.project=project
        if kind=="nc": obj.created_by=request.user
        obj.save(); AuditLog.objects.create(actor=request.user,action=f"{kind.upper()}_CREATED",entity_type=obj.__class__.__name__,entity_id=str(obj.pk)); return redirect("quality_dashboard",pk=pk)
    return render(request,"core/form.html",{"form":form,"title":title})

@roles_required("ANALYST","ADMIN")
def risk_control_create(request,pk):
    assessment=get_object_or_404(RiskAssessment,pk=pk); form=RiskControlForm(request.POST or None)
    if request.method=="POST" and form.is_valid(): obj=form.save(commit=False); obj.assessment=assessment; obj.save(); AuditLog.objects.create(actor=request.user,action="RISK_CONTROL_CREATED",entity_type="RiskControl",entity_id=str(obj.pk)); return redirect("quality_dashboard",pk=assessment.hazard.project_id)
    return render(request,"core/form.html",{"form":form,"title":"위험통제 등록"})

@login_required
@require_POST
def capa_transition(request,pk):
    capa=get_object_or_404(CAPA,pk=pk)
    try: transition_capa(capa,request.POST.get("status"),request.user); messages.success(request,"CAPA 상태를 변경했습니다.")
    except (ValidationError,PermissionDenied) as exc: messages.error(request,str(exc))
    return redirect("quality_dashboard",pk=capa.nonconformity.project_id)

def _docx(data,name):
    response=HttpResponse(data,content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"); response["Content-Disposition"]=f'attachment; filename="{name}"'; return response
@login_required
def risk_report_download(request,pk):
    project=get_object_or_404(Project,pk=pk); AuditLog.objects.create(actor=request.user,action="RISK_REPORT_DOWNLOAD",entity_type="Project",entity_id=str(pk)); return _docx(build_risk_report(project),f"risk-{pk}.docx")
@login_required
def capa_report_download(request,pk):
    project=get_object_or_404(Project,pk=pk); AuditLog.objects.create(actor=request.user,action="CAPA_REPORT_DOWNLOAD",entity_type="Project",entity_id=str(pk)); return _docx(build_capa_report(project),f"capa-{pk}.docx")
