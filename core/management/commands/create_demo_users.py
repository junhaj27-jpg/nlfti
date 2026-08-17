import os
from django.contrib.auth.models import Group,User
from django.core.management import call_command
from django.core.management.base import BaseCommand,CommandError

class Command(BaseCommand):
    help="로컬 포트폴리오 데모용 analyst/reviewer/admin 계정을 생성합니다."
    def handle(self,*args,**options):
        password=os.getenv("DEMO_PASSWORD")
        if not password or len(password)<10: raise CommandError("10자 이상의 DEMO_PASSWORD 환경변수가 필요합니다.")
        call_command("init_roles")
        for username,role in (("demo_analyst","ANALYST"),("demo_reviewer","REVIEWER"),("demo_admin","ADMIN")):
            user,_=User.objects.get_or_create(username=username); user.set_password(password); user.is_staff=role=="ADMIN"; user.save(); user.groups.set([Group.objects.get(name=role)])
        self.stdout.write(self.style.SUCCESS("demo_analyst, demo_reviewer, demo_admin 계정을 생성했습니다."))
