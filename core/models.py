import uuid
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models

ROLES = ("ANALYST", "REVIEWER", "ADMIN")

def anonymized_upload_path(instance, filename):
    suffix = ".nii.gz" if filename.lower().endswith(".nii.gz") else ".nii"
    return f"nifti/{uuid.uuid4().hex}{suffix}"

def result_upload_path(instance, filename):
    suffix = ".nii.gz" if filename.lower().endswith(".nii.gz") else ".json" if filename.lower().endswith(".json") else ".png"
    return f"analysis-results/{uuid.uuid4().hex}{suffix}"

class ModelVersion(models.Model):
    name = models.CharField(max_length=120)
    version = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["name", "version"], name="unique_model_version")]
    def __str__(self): return f"{self.name} {self.version}"

class Project(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self): return self.title

class MedicalImage(models.Model):
    class Modality(models.TextChoices): MRI="MRI", "MRI"; CT="CT", "CT"
    project = models.ForeignKey(Project, related_name="images", on_delete=models.CASCADE)
    file = models.FileField(upload_to=anonymized_upload_path)
    reference_mask = models.FileField(upload_to=anonymized_upload_path, blank=True)
    study_date = models.DateField()
    modality = models.CharField(max_length=3, choices=Modality.choices)
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)

class Analysis(models.Model):
    class Status(models.TextChoices):
        PENDING="PENDING", "대기"; RUNNING="RUNNING", "실행 중"; COMPLETED="COMPLETED", "완료"; FAILED="FAILED", "실패"
    image = models.ForeignKey(MedicalImage, related_name="analyses", on_delete=models.CASCADE)
    model_version = models.ForeignKey(ModelVersion, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    mask_file = models.FileField(upload_to=anonymized_upload_path, blank=True)
    overlay_file = models.ImageField(upload_to="overlays/", blank=True)
    voxel_count = models.PositiveBigIntegerField(default=0)
    spacing_x = models.FloatField(null=True, blank=True); spacing_y = models.FloatField(null=True, blank=True); spacing_z = models.FloatField(null=True, blank=True)
    volume_cm3 = models.FloatField(null=True, blank=True)
    dice = models.FloatField(null=True, blank=True); iou = models.FloatField(null=True, blank=True)
    sensitivity = models.FloatField(null=True, blank=True); precision = models.FloatField(null=True, blank=True)
    runtime_seconds = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True); updated_at = models.DateTimeField(auto_now=True)
    @property
    def approved(self): return self.reviews.filter(decision=Review.Decision.APPROVED).exists()
    def save(self, *args, **kwargs):
        if self.pk and Analysis.objects.filter(pk=self.pk, reviews__decision=Review.Decision.APPROVED).exists():
            old = Analysis.objects.get(pk=self.pk)
            protected = ("image_id", "model_version_id", "status", "mask_file", "voxel_count", "volume_cm3", "dice", "iou", "sensitivity", "precision")
            if any(getattr(old, f) != getattr(self, f) for f in protected): raise ValidationError("승인된 분석 결과는 수정할 수 없습니다.")
        super().save(*args, **kwargs)

class Review(models.Model):
    class Decision(models.TextChoices): APPROVED="APPROVED", "승인"; REJECTED="REJECTED", "반려"
    analysis = models.ForeignKey(Analysis, related_name="reviews", on_delete=models.CASCADE)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=10, choices=Decision.choices)
    comment = models.TextField()
    reviewed_at = models.DateTimeField(auto_now_add=True)

class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80); entity_type = models.CharField(max_length=80); entity_id = models.CharField(max_length=80)
    details = models.JSONField(default=dict, blank=True); created_at = models.DateTimeField(auto_now_add=True)

class MRIStudy(models.Model):
    project = models.ForeignKey(Project, related_name="mri_studies", on_delete=models.CASCADE)
    study_date = models.DateField()
    description = models.TextField(blank=True)
    t1 = models.FileField(upload_to=anonymized_upload_path)
    t1ce = models.FileField(upload_to=anonymized_upload_path)
    t2 = models.FileField(upload_to=anonymized_upload_path)
    flair = models.FileField(upload_to=anonymized_upload_path)
    reference_mask = models.FileField(upload_to=anonymized_upload_path, blank=True)
    shape = models.JSONField(default=list)
    affine = models.JSONField(default=list)
    spacing = models.JSONField(default=list)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)

class AnalysisJob(models.Model):
    class Status(models.TextChoices):
        PENDING="PENDING", "대기"; VALIDATING="VALIDATING", "검증"; PREPROCESSING="PREPROCESSING", "전처리"; RUNNING="RUNNING", "추론"; POSTPROCESSING="POSTPROCESSING", "후처리"; COMPLETED="COMPLETED", "완료"; FAILED="FAILED", "실패"
    study = models.ForeignKey(MRIStudy, related_name="jobs", on_delete=models.CASCADE)
    model_version = models.ForeignKey(ModelVersion, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    progress = models.PositiveSmallIntegerField(default=0)
    model_name = models.CharField(max_length=120)
    model_version_name = models.CharField(max_length=50)
    inference_mode = models.CharField(max_length=20, default="mock")
    device = models.CharField(max_length=80, blank=True)
    mixed_precision = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    preprocessing_seconds = models.FloatField(null=True, blank=True)
    inference_seconds = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    exception_history = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    @property
    def approved(self): return self.reviews.filter(decision=JobReview.Decision.APPROVED).exists()

class AnalysisResult(models.Model):
    job = models.OneToOneField(AnalysisJob, related_name="result", on_delete=models.CASCADE)
    segmentation_file = models.FileField(upload_to=result_upload_path)
    overlay_file = models.ImageField(upload_to=result_upload_path)
    metrics_file = models.FileField(upload_to=result_upload_path)
    whole_tumor_voxels = models.PositiveBigIntegerField(default=0)
    tumor_core_voxels = models.PositiveBigIntegerField(default=0)
    enhancing_tumor_voxels = models.PositiveBigIntegerField(default=0)
    whole_tumor_cm3 = models.FloatField(default=0)
    tumor_core_cm3 = models.FloatField(default=0)
    enhancing_tumor_cm3 = models.FloatField(default=0)
    spacing = models.JSONField(default=list)
    metrics = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        if self.pk and AnalysisResult.objects.filter(pk=self.pk, job__reviews__decision=JobReview.Decision.APPROVED).exists():
            old=AnalysisResult.objects.get(pk=self.pk)
            protected=("segmentation_file","metrics_file","whole_tumor_voxels","tumor_core_voxels","enhancing_tumor_voxels","whole_tumor_cm3","tumor_core_cm3","enhancing_tumor_cm3","metrics")
            if any(getattr(old,f)!=getattr(self,f) for f in protected): raise ValidationError("승인된 분석 결과는 수정할 수 없습니다.")
        super().save(*args,**kwargs)

class JobReview(models.Model):
    class Decision(models.TextChoices): APPROVED="APPROVED", "승인"; REJECTED="REJECTED", "반려"
    job = models.ForeignKey(AnalysisJob, related_name="reviews", on_delete=models.CASCADE)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=10, choices=Decision.choices)
    comment = models.TextField()
    reviewed_at = models.DateTimeField(auto_now_add=True)

def user_role(user):
    if user.is_superuser: return "ADMIN"
    return next((r for r in ROLES if user.groups.filter(name=r).exists()), None)
