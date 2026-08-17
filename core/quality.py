from django.core.exceptions import PermissionDenied,ValidationError
from django.utils import timezone
from .models import AuditLog,CAPA,user_role

TRANSITIONS={CAPA.Status.OPEN:CAPA.Status.INVESTIGATING,CAPA.Status.INVESTIGATING:CAPA.Status.ACTION_IN_PROGRESS,CAPA.Status.ACTION_IN_PROGRESS:CAPA.Status.EFFECTIVENESS_REVIEW,CAPA.Status.EFFECTIVENESS_REVIEW:CAPA.Status.CLOSED}
def transition_capa(capa,new_status,actor):
    if TRANSITIONS.get(capa.status)!=new_status: raise ValidationError(f"허용되지 않은 CAPA 상태 전환입니다: {capa.status} → {new_status}")
    if new_status==CAPA.Status.CLOSED:
        if user_role(actor) not in ("REVIEWER","ADMIN"): raise PermissionDenied("CAPA 종료는 REVIEWER 또는 ADMIN만 승인할 수 있습니다.")
        if not capa.effectiveness_result.strip(): raise ValidationError("CAPA 종료 전 효과성 검증 결과가 필요합니다.")
        capa.closure_approved_by=actor; capa.closed_at=timezone.now()
    old=capa.status; capa.status=new_status; capa.save()
    AuditLog.objects.create(actor=actor,action="CAPA_STATUS_CHANGED",entity_type="CAPA",entity_id=str(capa.pk),details={"from":old,"to":new_status})
    return capa
