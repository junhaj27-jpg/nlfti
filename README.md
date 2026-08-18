# 의료영상 AI 분석·검증 및 RA 보고서 자동화 플랫폼

공개·비식별 BraTS 형식의 T1/T1ce/T2/FLAIR MRI를 등록하고 MONAI segmentation 결과, 영역별 부피와 성능지표를 검토·승인한 뒤 RA 형식의 DOCX 보고서를 내려받는 취업 포트폴리오용 MVP입니다. 기존 단일 MRI/CT mock 분석 흐름도 하위 호환을 위해 유지합니다.

> 본 서비스는 연구·포트폴리오용이며 의료진의 진단을 대체하지 않습니다.

## 주요 기능

- Django 인증과 `ANALYST`, `REVIEWER`, `ADMIN` 역할
- 한 검사당 T1, T1ce, T2, FLAIR 및 선택적 기준 마스크 등록, UUID 파일명 저장
- NIfTI 손상·크기·압축 해제 한도와 4채널 shape/affine/spacing 일치 검증
- MONAI orientation/spacing/normalization/crop/sliding-window/inverse 파이프라인
- CUDA 자동 선택, AMP 옵션, CUDA OOM 시 ROI와 batch를 낮춘 1회 재시도
- 모델이 없는 개발 환경을 위한 4채널 mock inference와 중앙 slice overlay
- voxel 수 × spacing(mm³) ÷ 1000으로 병변 부피(cm³) 계산
- 기준 마스크가 있을 때 Dice, IoU, 민감도, 정밀도 산출
- 승인/반려 의견과 시각, AuditLog 기록 및 승인 결과 불변 처리
- 프로젝트·모델·입력·결과·검토 이력·한계를 포함한 DOCX 보고서
- FastAPI 계산 API와 `/docs` Swagger UI
- 익명 Subject와 T01/T02 시점별 종양 부피 변화 추적
- 원본 AI 마스크를 보존하는 2D 브러시 수정본과 재검토
- Hazard/RiskAssessment/RiskControl 위험관리 및 DOCX 요약
- 분석 실패·검토 반려 기반 부적합과 CAPA 효과성 검증
- 분석·승인·모델 Dice·부피 변화·CAPA 통합 대시보드

## BraTS 데이터 준비

한 검사의 공개·비식별 NIfTI 네 개를 준비합니다. 모든 영상은 동일한 shape, affine, spacing을 가져야 합니다.

```text
case-001/
  case-001_t1.nii.gz
  case-001_t1ce.nii.gz
  case-001_t2.nii.gz
  case-001_flair.nii.gz
  case-001_seg.nii.gz     # 선택적 기준 마스크, label 1/2/4
```

DICOM과 환자 식별정보는 입력하지 않습니다. BraTS 데이터 이용 조건과 원 모델 라이선스는 사용자가 별도로 확인해야 합니다. 저장 파일명은 업로드 즉시 UUID로 바뀝니다.

## 모델 설치와 GPU 실행

저장소에는 모델 가중치가 포함되지 않습니다. 가장 안전한 배포 형식은 4채널 입력과 3채널 출력(WT/TC/ET sigmoid)을 갖는 TorchScript 모델입니다. 또는 코드에 정의된 MONAI 3D UNet과 정확히 같은 구조의 `state_dict`를 사용할 수 있습니다.

```env
INFERENCE_MODE=monai
MONAI_MODEL_PATH=/absolute/path/to/models/brats_model.ts
MONAI_MODEL_NAME=BraTS MONAI UNet
MONAI_MODEL_VERSION=1.0.0
MONAI_MIXED_PRECISION=1
```

CUDA용 PyTorch는 NVIDIA 드라이버와 CUDA 버전에 맞춰 [PyTorch 공식 설치 안내](https://pytorch.org/get-started/locally/)로 먼저 설치한 뒤 `pip install -r requirements.txt`를 실행하십시오. 실행 시 `torch.cuda.is_available()`이 참이면 CUDA, 아니면 CPU를 사용합니다. CPU 추론은 정상 동작하지만 3D 영상에서는 매우 느릴 수 있습니다. CUDA OOM 발생 시 ROI 각 축과 `sw_batch_size`를 낮춰 한 번 자동 재시도합니다.

가중치가 없을 때는 다음처럼 mock 모드를 사용합니다.

```env
INFERENCE_MODE=mock
MONAI_MODEL_PATH=
```

mock 결과는 영상 intensity 규칙 기반이며 모델 성능을 나타내지 않습니다.

## 전체 업무 흐름

1. ADMIN이 사용자와 모델 버전을 등록하고 역할을 부여합니다.
2. ANALYST가 프로젝트와 환자정보가 아닌 익명 `Subject Code`를 생성합니다.
3. Subject에 T01, T02 순서로 촬영일, 병원·장비 코드, 치료 이벤트와 MRI 4채널을 등록합니다.
4. FastAPI/MONAI 또는 mock 분석을 실행하고 원본 segmentation, overlay, JSON 지표를 확인합니다.
5. 이전 시점 대비 전체 종양 부피 증감량·증감률을 확인합니다. 병원 또는 장비 변경 구간에는 직접 비교 경고가 표시됩니다.
6. 필요한 경우 ANALYST가 2D 브러시로 mask를 수정합니다. 원본은 보존되고 수정본은 별도 NIfTI로 저장되어 재검토 상태가 됩니다.
7. REVIEWER가 원본 결과 또는 수정본을 승인·반려합니다. 승인된 결과는 수정할 수 없습니다.
8. 실패나 반려를 Hazard/Risk 및 Nonconformity에 연결하고 CAPA 원인·시정·예방조치와 효과성을 관리합니다.
9. 승인된 분석의 RA DOCX, 위험관리 요약 DOCX와 CAPA DOCX를 다운로드합니다.

## 데모 계정

실제 비밀번호는 저장소에 기록하지 않습니다. 로컬에서 다음과 같이 환경변수를 지정합니다.

```powershell
$env:DEMO_PASSWORD="로컬에서만-사용할-강한-비밀번호"
python manage.py create_demo_users
```

`demo_analyst`, `demo_reviewer`, `demo_admin`이 생성됩니다. 공개 배포 전에는 데모 계정을 비활성화하거나 비밀번호를 교체하십시오.

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

FastAPI 작업 API:

- `POST /api/v1/inference/jobs`: T1/T1ce/T2/FLAIR multipart 업로드
- `GET /api/v1/inference/jobs/{job_id}`: 상태와 진행률
- `GET /api/v1/inference/jobs/{job_id}/results`: NIfTI/PNG/JSON 결과 메타데이터
- `POST /api/v1/metrics`: 배열 기반 Dice, IoU, 민감도, 정밀도

FastAPI 작업 레지스트리는 MVP에서 프로세스 메모리에 있으므로 서버 재시작 시 상태가 사라집니다. Django에서 실행한 작업과 결과는 PostgreSQL에 영속화됩니다.

PostgreSQL까지 한 번에 실행하려면 Docker가 있는 환경에서 `docker compose up --build`를 사용합니다. 로컬에서 `DATABASE_URL`이 없으면 편의상 SQLite를 사용하고, 운영 구성은 `.env.example` 형식의 PostgreSQL URL을 사용합니다.

## 데모 흐름

1. 관리자 화면에서 사용자를 만들고 `ANALYST`, `REVIEWER`, `ADMIN` 중 그룹을 지정합니다. 모델 이름/버전을 하나 등록합니다.
2. ANALYST로 로그인해 프로젝트를 생성하고 `BraTS MRI 4채널 등록`에서 개인정보가 제거된 네 NIfTI를 등록합니다. 환자 이름·생년월일·병원번호 입력란은 없습니다.
3. 활성 모델 버전과 mock/MONAI 모드를 골라 분석하고 진행률, overlay, 영역별 voxel·부피, 환경과 성능지표를 확인합니다.
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

테스트는 NIfTI 검증, 부피/지표, FastAPI 상태, 권한과 승인 잠금, 시점별 증감률·비교 경고, 원본 마스크 보존·수정본 재계산, 위험등급, CAPA 전환·권한·기한 초과, RA/위험/CAPA DOCX를 포함합니다. synthetic NIfTI는 pytest 임시 디렉터리에서만 생성됩니다. 실제 MONAI 추론은 공개 데이터와 호환 가중치가 필요한 통합 검증 항목이므로 기본 테스트에서 제외됩니다.

## 구조

```text
config/          Django 설정과 URL
core/            모델, 폼, 뷰, 분석 서비스, 보고서, 감사로그
analysis_api/    FastAPI 앱
templates/       Bootstrap 기반 Django 화면
tests/           pytest 테스트
docker-compose.yml  Django/FastAPI/PostgreSQL 개발 구성
```

## 시스템 아키텍처

```text
Browser / Bootstrap UI
        │
        ▼
Django Web Application
  ├─ 인증 및 역할 권한(ANALYST / REVIEWER / ADMIN)
  ├─ Project / Subject / Study Timepoint 관리
  ├─ 분석 결과 검토·승인·AuditLog
  ├─ 마스크 수정본 재검토
  └─ RA / Risk / CAPA DOCX 보고서
        │
        ├──────── PostgreSQL
        │          메타데이터, 분석 상태, 검토·품질 이력
        │
        ▼
FastAPI Inference Service
  ├─ NIfTI 무결성 및 공간정보 검증
  ├─ MONAI preprocessing
  ├─ sliding-window inference
  ├─ 원본 공간 복원 및 후처리
  └─ NIfTI / PNG / JSON 결과 생성
        │
        ▼
Protected File Storage
  NIfTI, segmentation, overlay, model weights
```

Django는 업무 상태와 규제 문서 흐름을 담당하고 FastAPI는 계산 집약적인 추론을 담당합니다. 추론 어댑터를 Django 모델과 분리해 mock 및 MONAI 구현을 같은 인터페이스로 교체할 수 있습니다.

## 핵심 데이터 관계

```text
Project
 ├─ Subject ── MRIStudy(T01, T02, ...)
 │               └─ AnalysisJob ── AnalysisResult
 │                                  └─ MaskCorrection ── CorrectionReview
 ├─ Hazard ── RiskAssessment ── RiskControl
 └─ Nonconformity ── CAPA
```

- `AnalysisResult`는 AI가 생성한 원본 결과이며 승인 이후 변경할 수 없습니다.
- 수동 보정은 `MaskCorrection`에 별도 저장되어 원본 추적성을 유지합니다.
- 분석 실패와 검토 반려는 위험평가 및 부적합 항목에 연결할 수 있습니다.
- 모든 상태 변경과 주요 사용자 작업은 `AuditLog`에 기록됩니다.

## API 사용 예시

4채널 MRI 추론 작업을 생성합니다.

```bash
curl -X POST http://127.0.0.1:8001/api/v1/inference/jobs \
  -F "t1=@case_t1.nii.gz" \
  -F "t1ce=@case_t1ce.nii.gz" \
  -F "t2=@case_t2.nii.gz" \
  -F "flair=@case_flair.nii.gz"
```

```bash
curl http://127.0.0.1:8001/api/v1/inference/jobs/{job_id}
curl http://127.0.0.1:8001/api/v1/inference/jobs/{job_id}/results
```

응답에는 작업 상태와 진행률이 포함되며 완료 후 segmentation NIfTI, overlay PNG, 영역별 부피와 JSON 지표를 확인할 수 있습니다. 전체 요청·응답 스키마는 FastAPI `/docs`에서 제공합니다.

## 포트폴리오 핵심 설계 판단

- 실제 환자 식별정보 대신 프로젝트 범위의 익명 Subject Code만 저장했습니다.
- 원본 AI 결과와 수정 결과를 분리해 데이터 무결성과 변경 추적성을 확보했습니다.
- 승인 잠금을 화면이 아닌 모델 계층에서도 검사해 우회 수정을 차단했습니다.
- GPU가 없는 개발 환경에서도 전체 업무 흐름을 검증할 수 있도록 mock 모드를 유지했습니다.
- 병원·장비 변경 시 단순 수치 비교의 한계를 사용자에게 명시적으로 경고합니다.
- AI 실패와 검토 반려를 위험관리, 부적합, CAPA까지 연결해 의료기기 소프트웨어 품질 흐름을 표현했습니다.

## 이력서용 프로젝트 요약

> Django와 FastAPI를 기반으로 BraTS 4채널 MRI의 MONAI 뇌종양 segmentation, 시점별 병변 변화 추적, AI 마스크 수동 보정, 검토·승인 및 감사 추적, 위험관리·CAPA와 RA DOCX 자동화를 구현했습니다. Synthetic NIfTI 기반 pytest로 영상 검증, 정량지표, 권한, 승인 잠금과 품질 프로세스를 검증했습니다.

기술 키워드: `Django`, `FastAPI`, `PostgreSQL`, `MONAI`, `PyTorch`, `NIfTI`, `Bootstrap`, `pytest`, `Docker`, `python-docx`

## 역할별 권한

| 기능 | ANALYST | REVIEWER | ADMIN |
|---|:---:|:---:|:---:|
| 프로젝트·Subject 생성 | 가능 | 조회 | 가능 |
| MRI 등록·AI 분석 요청 | 가능 | 조회 | 가능 |
| 2D 마스크 수정본 생성 | 가능 | 조회 | 가능 |
| 분석 결과 승인·반려 | 불가 | 가능 | 가능 |
| 수정 마스크 재검토 | 불가 | 가능 | 가능 |
| 위험·부적합·CAPA 등록 | 가능 | 조회 | 가능 |
| CAPA 종료 승인 | 불가 | 가능 | 가능 |
| 사용자·모델 버전 관리 | 불가 | 불가 | 가능 |

권한은 화면 표시뿐 아니라 Django view decorator와 모델·서비스 계층의 상태 검사를 함께 사용해 적용합니다.

## 3분 데모 시나리오

1. `demo_analyst`로 로그인해 프로젝트와 익명 Subject를 생성합니다.
2. T01과 T02에 synthetic 또는 공개·비식별 BraTS MRI 4채널을 등록합니다.
3. mock 분석을 실행하고 segmentation overlay와 WT/TC/ET 부피를 확인합니다.
4. Subject 화면에서 이전 시점 대비 부피 증감률과 병원·장비 변경 경고를 확인합니다.
5. 2D 브러시로 AI 마스크 수정본을 만들고 원본 파일이 유지되는 것을 확인합니다.
6. `demo_reviewer`로 수정본 또는 분석 결과를 승인·반려합니다.
7. 실패·반려 건을 위험평가와 부적합에 연결하고 CAPA를 진행합니다.
8. RA, 위험관리, CAPA DOCX 보고서를 다운로드합니다.

실제 환자 데이터나 모델 가중치 없이 시연할 때는 `INFERENCE_MODE=mock`을 사용합니다.

## 테스트 전략

| 테스트 계층 | 검증 범위 |
|---|---|
| 계산 단위 테스트 | voxel 부피, Dice, IoU, 민감도, 정밀도, 시점별 증감률 |
| NIfTI 검증 테스트 | 손상 파일, shape·affine·spacing 불일치, 확장자와 크기 제한 |
| 추론 API 테스트 | 작업 생성, 진행 상태, mock 결과와 지표 API |
| 권한 테스트 | ANALYST·REVIEWER·ADMIN별 접근 제어와 CAPA 종료 권한 |
| 데이터 무결성 테스트 | 승인 결과 잠금, 원본 마스크 보존, 수정본 별도 저장 |
| 품질 프로세스 테스트 | 위험등급, 잔여위험, CAPA 상태 전환과 기한 초과 |
| 문서 테스트 | RA·위험관리·CAPA DOCX 생성과 필수 섹션 포함 여부 |

모든 영상 테스트는 작은 NumPy 배열로 만든 synthetic NIfTI를 사용하며 실제 환자 영상은 사용하지 않습니다.

## 구현 중 해결한 문제

- Nibabel이 일반 `BytesIO` 대상 저장을 지원하지 않는 문제를 NIfTI 바이트 직렬화 또는 안전한 임시 파일 방식으로 해결했습니다.
- 네 MRI 채널의 shape만 비교할 경우 발생할 수 있는 공간 오정렬을 affine과 spacing 검증까지 확장해 차단했습니다.
- GPU 메모리 부족 시 동일 설정으로 반복 실패하지 않도록 ROI 크기와 sliding-window batch를 낮춰 한 번 재시도합니다.
- 승인 잠금을 UI에만 의존하지 않고 Django 모델의 `save()`와 검토 서비스에서도 검사하도록 구성했습니다.
- 수동 보정이 AI 원본을 덮어쓰지 않도록 수정본과 재검토 이력을 독립 모델로 분리했습니다.
- `.nii.gz` 압축파일은 압축된 크기뿐 아니라 해제된 데이터 크기 상한도 검사해 비정상 압축파일 위험을 줄였습니다.

## 향후 로드맵

- Celery 또는 RQ와 Redis를 이용한 영속 비동기 추론 작업
- S3/MinIO 기반 암호화 object storage와 보존기간 정책
- Cornerstone 또는 OHIF 기반 다중 평면 의료영상 뷰어
- 3D contour 편집, undo/redo와 slice interpolation
- 실제 공개 BraTS 데이터 기반 모델별 Dice·추론시간 벤치마크
- PDF 전자서명과 문서 버전관리
- GitHub Actions 기반 테스트·보안검사·컨테이너 빌드 자동화
- 조직별 ISO 14971 위험행렬과 CAPA 승인 워크플로 설정

## 보안과 데이터 정책

- 확장자·최대 크기·경로 문자를 검사하며 저장 파일명은 UUID로 교체합니다.
- `.gitignore`는 NIfTI, DICOM, 모델 가중치, `media/`, 환경변수를 제외합니다.
- 실제 환자 데이터, 원본 DICOM/NIfTI, 모델 가중치를 저장소에 추가하지 마십시오.
- 운영 환경에서는 `DEBUG=0`, 강한 secret key, HTTPS, object storage malware 검사, MIME/헤더 심층 검사, 접근 로그 보존 정책을 추가해야 합니다.

## MVP 한계

- MONAI 모드는 사용자가 설치한 호환 가중치의 성능과 라이선스에 의존합니다. mock 모드는 intensity 규칙 기반입니다.
- Django 추론은 동기 실행이고 FastAPI 작업 상태는 메모리 기반이므로 운영 환경에는 Celery/RQ, Redis와 영속 작업 큐가 필요합니다.
- overlay는 중앙 axial slice 한 장이며 전문 뷰어/다중 평면/창폭 조절은 포함하지 않습니다.
- DOCX만 구현되어 있고 PDF 변환은 배포 환경의 LibreOffice 등 별도 엔진이 필요합니다.
- 실제 BraTS 사례에서 orientation 역변환, label mapping, 모델별 normalization 호환성과 정량 성능을 별도 검증해야 합니다.
- 2D 보정기는 axial 단일 slice용 포트폴리오 UI이며 전문 contour 편집기, undo/redo, interpolation을 제공하지 않습니다.
- 병원·장비 변경 경고는 정량 harmonization을 수행하지 않습니다.
- 위험 행렬은 예시 5×5 규칙이며 조직의 ISO 14971 절차나 규제 QMS를 대체하지 않습니다.

## 개인정보 보호 원칙

- Patient 이름 대신 프로젝트 범위에서 유일한 익명 Subject Code만 저장합니다.
- 이름, 생년월일, 병원번호, 주소 등 직접 식별자는 입력하지 않습니다.
- 병원·장비에는 포트폴리오용 코드만 사용하고 원본 DICOM은 받지 않습니다.
- NIfTI, 수정본, 모델 가중치와 runtime 결과는 Git에서 제외됩니다.
- 로그와 AuditLog에는 원본 voxel 데이터나 파일 내용을 기록하지 않습니다.
- 규제 제출용 전자서명, 완전한 21 CFR Part 11 감사 추적, 데이터 무결성 검증 및 임상 검증을 제공하지 않습니다.
- Django 관리 화면의 사용자/모델 관리는 `is_staff` 권한도 필요합니다.
