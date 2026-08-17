# 의료영상 AI 분석·검증 및 RA 보고서 자동화 플랫폼

익명화된 MRI/CT NIfTI 영상을 등록하고 mock segmentation 결과, 병변 부피, 성능지표를 검토·승인한 뒤 RA 형식의 DOCX 보고서를 내려받는 취업 포트폴리오용 MVP입니다.

> 본 서비스는 연구·포트폴리오용이며 의료진의 진단을 대체하지 않습니다.

## 주요 기능

- Django 인증과 `ANALYST`, `REVIEWER`, `ADMIN` 역할
- 프로젝트 및 익명화 NIfTI(`.nii`, `.nii.gz`) 등록, UUID 파일명 저장
- 상위 10% intensity 기반 mock inference와 중앙 slice overlay
- voxel 수 × spacing(mm³) ÷ 1000으로 병변 부피(cm³) 계산
- 기준 마스크가 있을 때 Dice, IoU, 민감도, 정밀도 산출
- 승인/반려 의견과 시각, AuditLog 기록 및 승인 결과 불변 처리
- 프로젝트·모델·입력·결과·검토 이력·한계를 포함한 DOCX 보고서
- FastAPI 계산 API와 `/docs` Swagger UI

## 설치와 실행

Python 3.11 이상을 권장합니다.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py init_roles
python manage.py createsuperuser
python manage.py runserver
```

다른 터미널에서 FastAPI를 실행합니다.

```bash
uvicorn analysis_api.main:app --reload --port 8001
```

- Django: http://127.0.0.1:8000
- 관리 화면: http://127.0.0.1:8000/admin/
- FastAPI Swagger: http://127.0.0.1:8001/docs

PostgreSQL까지 한 번에 실행하려면 Docker가 있는 환경에서 `docker compose up --build`를 사용합니다. 로컬에서 `DATABASE_URL`이 없으면 편의상 SQLite를 사용하고, 운영 구성은 `.env.example` 형식의 PostgreSQL URL을 사용합니다.

## 데모 흐름

1. 관리자 화면에서 사용자를 만들고 `ANALYST`, `REVIEWER`, `ADMIN` 중 그룹을 지정합니다. 모델 이름/버전을 하나 등록합니다.
2. ANALYST로 로그인해 프로젝트를 생성하고 개인정보가 제거된 NIfTI를 등록합니다. 환자 이름·생년월일·병원번호 입력란은 없습니다.
3. 활성 모델 버전을 골라 mock 분석을 실행하고 overlay, voxel 수, spacing, 부피와 성능지표를 확인합니다.
4. REVIEWER로 로그인해 승인 또는 반려와 의견을 기록합니다. 승인된 핵심 분석 결과는 모델 계층에서도 수정이 거부됩니다.
5. 프로젝트에서 `RA DOCX`를 내려받습니다.

## 계산식과 단위

- 부피(cm³) = 병변 voxel 수 × spacing X(mm) × spacing Y(mm) × spacing Z(mm) ÷ 1000
- Dice = 2TP / (2TP + FP + FN)
- IoU = TP / (TP + FP + FN)
- 민감도 = TP / (TP + FN)
- 정밀도 = TP / (TP + FP)
- 예측과 기준이 모두 빈 마스크인 경우 네 지표를 1.0으로 정의합니다.

## 테스트

```bash
pytest -q
```

테스트는 부피/지표, 역할별 접근, 승인 이후 수정 방지, DOCX 보고서, FastAPI, 작은 NumPy 배열 기반 mock inference를 포함합니다. 테스트 NIfTI는 pytest 임시 디렉터리에서만 만들어집니다.

## 구조

```text
config/          Django 설정과 URL
core/            모델, 폼, 뷰, 분석 서비스, 보고서, 감사로그
analysis_api/    FastAPI 앱
templates/       Bootstrap 기반 Django 화면
tests/           pytest 테스트
docker-compose.yml  Django/FastAPI/PostgreSQL 개발 구성
```

## 보안과 데이터 정책

- 확장자·최대 크기·경로 문자를 검사하며 저장 파일명은 UUID로 교체합니다.
- `.gitignore`는 NIfTI, DICOM, 모델 가중치, `media/`, 환경변수를 제외합니다.
- 실제 환자 데이터, 원본 DICOM/NIfTI, 모델 가중치를 저장소에 추가하지 마십시오.
- 운영 환경에서는 `DEBUG=0`, 강한 secret key, HTTPS, object storage malware 검사, MIME/헤더 심층 검사, 접근 로그 보존 정책을 추가해야 합니다.

## MVP 한계

- 추론은 실제 학습 모델이 아닌 intensity percentile 기반 mock입니다.
- 동기 실행이므로 대용량 영상에는 Celery/RQ 같은 작업 큐가 필요합니다.
- overlay는 중앙 axial slice 한 장이며 전문 뷰어/다중 평면/창폭 조절은 포함하지 않습니다.
- DOCX만 구현되어 있고 PDF 변환은 배포 환경의 LibreOffice 등 별도 엔진이 필요합니다.
- 규제 제출용 전자서명, 완전한 21 CFR Part 11 감사 추적, 데이터 무결성 검증 및 임상 검증을 제공하지 않습니다.
- Django 관리 화면의 사용자/모델 관리는 `is_staff` 권한도 필요합니다.
