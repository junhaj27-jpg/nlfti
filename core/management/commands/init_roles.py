from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help="ANALYST, REVIEWER, ADMIN 역할 그룹과 기본 권한을 생성합니다."
    def handle(self,*args,**options):
        analyst,_=Group.objects.get_or_create(name="ANALYST"); reviewer,_=Group.objects.get_or_create(name="REVIEWER"); admin,_=Group.objects.get_or_create(name="ADMIN")
        analyst.permissions.set(Permission.objects.filter(codename__in=["add_project","view_project","add_medicalimage","view_medicalimage","add_analysis","view_analysis","add_mristudy","view_mristudy","add_analysisjob","view_analysisjob","view_analysisresult"]))
        reviewer.permissions.set(Permission.objects.filter(codename__in=["view_project","view_medicalimage","view_analysis","add_review","view_review","view_mristudy","view_analysisjob","view_analysisresult","add_jobreview","view_jobreview"]))
        admin.permissions.set(Permission.objects.filter(content_type__app_label="core"))
        self.stdout.write(self.style.SUCCESS("역할과 권한을 초기화했습니다."))
