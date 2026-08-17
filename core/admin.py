from django.contrib import admin
from .models import ModelVersion, Project, MedicalImage, Analysis, Review, AuditLog, MRIStudy, AnalysisJob, AnalysisResult, JobReview
admin.site.register([ModelVersion, Project, MedicalImage, Analysis, Review, AuditLog, MRIStudy, AnalysisJob, AnalysisResult, JobReview])
