from django import forms
from .models import Project, MedicalImage, Review
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

