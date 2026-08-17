from django import forms
from .models import Project, MedicalImage, Review, MRIStudy, JobReview, CorrectionReview, Subject, Hazard, RiskAssessment, RiskControl, Nonconformity, CAPA, AnalysisJob
from .validators import validate_nifti

class ProjectForm(forms.ModelForm):
    class Meta: model = Project; fields = ["title", "description"]

class MedicalImageForm(forms.ModelForm):
    class Meta: model = MedicalImage; fields = ["file", "reference_mask", "study_date", "modality", "description"]; widgets = {"study_date": forms.DateInput(attrs={"type":"date"})}
    def clean_file(self): f=self.cleaned_data["file"]; validate_nifti(f); return f
    def clean_reference_mask(self):
        f=self.cleaned_data.get("reference_mask")
        if f: validate_nifti(f)
        return f

class ReviewForm(forms.ModelForm):
    class Meta: model = Review; fields = ["decision", "comment"]

class MRIStudyForm(forms.ModelForm):
    class Meta: model=MRIStudy; fields=["subject","timepoint_code","timepoint_order","study_date","hospital_code","equipment_code","treatment_event","description","t1","t1ce","t2","flair","reference_mask"]; widgets={"study_date":forms.DateInput(attrs={"type":"date"})}
    def __init__(self,*args,project=None,**kwargs):
        super().__init__(*args,**kwargs)
        if project: self.fields["subject"].queryset=project.subjects.all()
    def clean(self):
        cleaned=super().clean()
        code=cleaned.get("timepoint_code","")
        if code and (not code.startswith("T") or not code[1:].isdigit()): self.add_error("timepoint_code","T01, T02 형식을 사용하십시오.")
        for key in ("t1","t1ce","t2","flair","reference_mask"):
            upload=cleaned.get(key)
            if upload: validate_nifti(upload)
        return cleaned

class JobReviewForm(forms.ModelForm):
    class Meta: model=JobReview; fields=["decision","comment"]

class CorrectionReviewForm(forms.ModelForm):
    class Meta: model=CorrectionReview; fields=["decision","comment"]

class SubjectForm(forms.ModelForm):
    class Meta: model=Subject; fields=["subject_code","description"]
class HazardForm(forms.ModelForm):
    class Meta: model=Hazard; fields=["code","hazard","hazardous_situation","harm"]
class RiskAssessmentForm(forms.ModelForm):
    class Meta: model=RiskAssessment; fields=["hazard","analysis_job","rejected_review","severity","probability","residual_severity","residual_probability","rationale"]
    def __init__(self,*args,project=None,**kwargs):
        super().__init__(*args,**kwargs)
        if project:
            self.fields["hazard"].queryset=project.hazards.all(); self.fields["analysis_job"].queryset=AnalysisJob.objects.filter(study__project=project); self.fields["rejected_review"].queryset=JobReview.objects.filter(job__study__project=project,decision="REJECTED")
class RiskControlForm(forms.ModelForm):
    class Meta: model=RiskControl; fields=["control_measure","verification","implemented"]
class NonconformityForm(forms.ModelForm):
    class Meta: model=Nonconformity; fields=["title","description","source","analysis_job","rejected_review"]
    def __init__(self,*args,project=None,**kwargs):
        super().__init__(*args,**kwargs)
        if project:
            self.fields["analysis_job"].queryset=AnalysisJob.objects.filter(study__project=project,status="FAILED"); self.fields["rejected_review"].queryset=JobReview.objects.filter(job__study__project=project,decision="REJECTED")
class CAPAForm(forms.ModelForm):
    class Meta: model=CAPA; fields=["nonconformity","root_cause","corrective_action","preventive_action","owner","target_date","effectiveness_result"]; widgets={"target_date":forms.DateInput(attrs={"type":"date"})}
    def __init__(self,*args,project=None,**kwargs):
        super().__init__(*args,**kwargs)
        if project: self.fields["nonconformity"].queryset=project.nonconformities.filter(capa__isnull=True)
