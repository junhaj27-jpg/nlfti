from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .decorators import roles_required
from .forms import ProjectForm, MedicalImageForm, ReviewForm
from .models import Analysis, AuditLog, ModelVersion, Project, user_role
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
    project=get_object_or_404(Project,pk=pk); data=build_ra_report(project); AuditLog.objects.create(actor=request.user,action="REPORT_DOWNLOAD",entity_type="Project",entity_id=str(pk))
    response=HttpResponse(data,content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"); response["Content-Disposition"]=f'attachment; filename="RA-report-{pk}.docx"'; return response
