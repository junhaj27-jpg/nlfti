from io import BytesIO
from docx import Document
from docx.shared import Inches

DISCLAIMER = "본 서비스는 연구·포트폴리오용이며 의료진의 진단을 대체하지 않습니다."
def build_ra_report(project):
    doc=Document(); doc.add_heading("의료영상 AI 분석·검증 보고서", 0); doc.add_paragraph(DISCLAIMER)
    doc.add_heading("1. 프로젝트 개요", 1); doc.add_paragraph(f"프로젝트명: {project.title}\n설명: {project.description or '-'}\n생성일: {project.created_at:%Y-%m-%d}")
    doc.add_heading("2. 입력 데이터 및 분석 결과", 1)
    for image in project.images.prefetch_related("analyses__reviews").all():
        doc.add_heading(f"{image.modality} / 검사일 {image.study_date}", 2); doc.add_paragraph(f"익명화 파일 ID: {image.pk}\n설명: {image.description or '-'}")
        for a in image.analyses.all():
            doc.add_paragraph(f"모델: {a.model_version.name} {a.model_version.version}\n상태: {a.status}\n병변 voxel: {a.voxel_count}\nSpacing: {a.spacing_x}, {a.spacing_y}, {a.spacing_z} mm\n부피: {a.volume_cm3 if a.volume_cm3 is not None else '-'} cm³\n실행시간: {a.runtime_seconds if a.runtime_seconds is not None else '-'} s")
            doc.add_heading("성능평가", 3); table=doc.add_table(rows=1, cols=2); table.style="Table Grid"; table.rows[0].cells[0].text="지표"; table.rows[0].cells[1].text="값"
            for label,value in (("Dice = 2TP/(2TP+FP+FN)",a.dice),("IoU = TP/(TP+FP+FN)",a.iou),("민감도 = TP/(TP+FN)",a.sensitivity),("정밀도 = TP/(TP+FP)",a.precision)):
                cells=table.add_row().cells; cells[0].text=label; cells[1].text="-" if value is None else f"{value:.4f}"
            doc.add_heading("검토·승인 이력", 3)
            for r in a.reviews.all(): doc.add_paragraph(f"{r.reviewed_at:%Y-%m-%d %H:%M} / {r.reviewer.username} / {r.get_decision_display()} / {r.comment}")
    doc.add_heading("3. 한계와 주의사항", 1); doc.add_paragraph("본 MVP의 추론은 검증되지 않은 임계값 기반 mock inference입니다. 임상 사용, 진단, 치료 결정에 사용할 수 없으며 실제 의료기기 검증 및 규제 제출 요건을 충족하지 않습니다. 기준 마스크가 없는 경우 성능지표는 산출되지 않습니다.")
    stream=BytesIO(); doc.save(stream); return stream.getvalue()

