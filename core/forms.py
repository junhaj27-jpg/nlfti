from django import forms
from .models import Project, MedicalImage, Review, MRIStudy, JobReview
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
    class Meta: model=MRIStudy; fields=["study_date","description","t1","t1ce","t2","flair","reference_mask"]; widgets={"study_date":forms.DateInput(attrs={"type":"date"})}
    def clean(self):
        cleaned=super().clean()
        for key in ("t1","t1ce","t2","flair","reference_mask"):
            upload=cleaned.get(key)
            if upload: validate_nifti(upload)
        return cleaned

class JobReviewForm(forms.ModelForm):
    class Meta: model=JobReview; fields=["decision","comment"]
