from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .decorators import roles_required
from django.core.exceptions import ValidationError
from .forms import ProjectForm, MedicalImageForm, ReviewForm, MRIStudyForm, JobReviewForm
from .models import Analysis, AuditLog, ModelVersion, Project, MRIStudy, AnalysisJob, JobReview, user_role
from .brats_service import execute_job, validate_study
from .reports import build_ra_report
from .services import run_mock_analysis

@login_required
def dashboard(request): return render(request,"core/dashboard.html",{"projects":Project.objects.all().order_by("-created_at"),"role":user_role(request.user)})
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
    project=get_object_or_404(Project,pk=pk); form=MRIStudyForm(request.POST or None,request.FILES or None)
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
