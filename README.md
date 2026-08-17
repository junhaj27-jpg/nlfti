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

테스트는 NIfTI 손상 및 공간 불일치, 부피/지표, FastAPI 작업 상태, 역할별 접근, 승인 이후 수정 방지, BraTS DOCX 보고서와 작은 NumPy 배열 기반 mock inference를 포함합니다. 테스트 NIfTI는 pytest 임시 디렉터리에서만 만들어집니다. MONAI 실제 추론 테스트는 공개 데이터와 호환 가중치가 필요한 통합 검증 항목이므로 기본 테스트에서 제외됩니다.

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

- MONAI 모드는 사용자가 설치한 호환 가중치의 성능과 라이선스에 의존합니다. mock 모드는 intensity 규칙 기반입니다.
- Django 추론은 동기 실행이고 FastAPI 작업 상태는 메모리 기반이므로 운영 환경에는 Celery/RQ, Redis와 영속 작업 큐가 필요합니다.
- overlay는 중앙 axial slice 한 장이며 전문 뷰어/다중 평면/창폭 조절은 포함하지 않습니다.
- DOCX만 구현되어 있고 PDF 변환은 배포 환경의 LibreOffice 등 별도 엔진이 필요합니다.
- 실제 BraTS 사례에서 orientation 역변환, label mapping, 모델별 normalization 호환성과 정량 성능을 별도 검증해야 합니다.
- 규제 제출용 전자서명, 완전한 21 CFR Part 11 감사 추적, 데이터 무결성 검증 및 임상 검증을 제공하지 않습니다.
- Django 관리 화면의 사용자/모델 관리는 `is_staff` 권한도 필요합니다.
