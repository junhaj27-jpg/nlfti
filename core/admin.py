from django.contrib import admin
from .models import ModelVersion, Project, MedicalImage, Analysis, Review, AuditLog
admin.site.register([ModelVersion, Project, MedicalImage, Analysis, Review, AuditLog])

