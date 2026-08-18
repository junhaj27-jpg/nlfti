# MedVision RA 운영 배포 가이드

이 문서는 공개 포트폴리오 데모를 단일 Linux 서버에 Docker Compose로 배포하는 절차입니다. 임상 진단이나 의료기관 운영 승인을 의미하지 않습니다.

## 운영 구성

- Caddy: HTTPS 인증서 발급·갱신, reverse proxy, 정적 파일
- Django + Gunicorn: 인증, 프로젝트, 검토·승인, 보고서
- FastAPI + Uvicorn: 추론 API, worker 1개
- PostgreSQL: 업무 및 감사 데이터
- Docker volumes: DB, media, static, 추론 결과, Caddy 인증서

DB, Django, FastAPI 포트는 외부에 공개하지 않고 Caddy의 80/443 포트만 공개합니다. `/media/` 요청은 Django 로그인 검사를 통과해야 합니다.

## 1. 서버 준비

DNS의 A/AAAA 레코드를 서버 IP로 연결하고 Linux 서버에 Docker Engine과 Compose plugin을 설치합니다. 방화벽에서는 SSH, HTTP 80, HTTPS 443만 허용합니다.

```bash
git clone https://github.com/junhaj27-jpg/nlfti.git
cd nlfti
cp .env.production.example .env.production
chmod 600 .env.production
```

## 2. 운영 환경변수

`.env.production`에서 다음 값을 반드시 변경합니다.

```env
DOMAIN=medvision.example.com
DJANGO_SECRET_KEY=<32자 이상의 랜덤 secret>
DJANGO_ALLOWED_HOSTS=medvision.example.com
CSRF_TRUSTED_ORIGINS=https://medvision.example.com
POSTGRES_PASSWORD=<강한 DB 비밀번호>
DATABASE_URL=postgresql://medai:<동일한 DB 비밀번호>@db:5432/medai
INFERENCE_MODE=mock
```

Secret 생성 예:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

`.env.production`은 Git에 포함하지 않습니다. 초기 배포는 `INFERENCE_MODE=mock`을 권장합니다.

## 3. 구성 검사와 실행

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml config
docker compose --env-file .env.production -f docker-compose.prod.yml build
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Django 컨테이너 시작 시 migration과 `collectstatic`을 한 번 실행한 뒤 Gunicorn이 시작됩니다. 여러 Django replica를 운영할 때는 migration을 별도 release job으로 분리해야 합니다.

## 4. 관리자와 역할 생성

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec django python manage.py init_roles
docker compose --env-file .env.production -f docker-compose.prod.yml exec django python manage.py createsuperuser
```

공개 서버에는 `create_demo_users`로 고정 데모 계정을 만들지 않는 것을 권장합니다.

## 5. 배포 확인

```bash
curl https://medvision.example.com/health/
curl https://medvision.example.com/api/health
docker compose --env-file .env.production -f docker-compose.prod.yml exec django python manage.py check --deploy --settings=config.settings_prod
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=100 django api caddy
```

브라우저에서 로그인, 프로젝트 생성, mock 추론, 검토·승인과 DOCX 다운로드를 확인합니다.

## 실제 MONAI GPU 실행

GPU 배포는 NVIDIA driver와 Container Toolkit, CUDA 호환 PyTorch 이미지가 필요합니다. 가중치는 Git에 넣지 않고 `/app/models` read-only volume이나 secret storage로 전달합니다.

```env
INFERENCE_MODE=monai
MONAI_MODEL_PATH=/app/models/brats_model.ts
MONAI_MODEL_NAME=BraTS MONAI UNet
MONAI_MODEL_VERSION=1.0.0
MONAI_MIXED_PRECISION=1
```

현재 production Compose는 범용 CPU 구성입니다. GPU를 사용하려면 `api` 서비스에 NVIDIA device reservation을 추가하고 CUDA 기반 Docker image를 별도로 빌드해야 합니다. 모델이 worker마다 메모리에 복제되므로 GPU API는 worker 1개부터 검증합니다.

## 백업과 복구

정기적으로 PostgreSQL과 `media` volume을 함께 백업해야 합니다. 둘 중 하나만 복구하면 DB 레코드와 결과 파일이 불일치할 수 있습니다.

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db \
  pg_dump -U medai -d medai -Fc > medvision-$(date +%F).dump
```

백업은 서버와 분리된 암호화 저장소에 보관하고 복구 훈련을 수행합니다.

## 운영 전 추가 권고

- Redis/Celery 또는 RQ 기반 영속 추론 큐
- S3/MinIO object storage와 만료·보존 정책
- 중앙 로그, 오류 추적, 메트릭, uptime alert
- rate limiting, 업로드 malware 검사, MFA
- CI에서 pytest, dependency scan, container scan
- 개인정보 영향평가와 조직별 접근통제·감사로그 정책

현재 시스템은 연구·포트폴리오용이며 의료진의 진단을 대체하지 않습니다. 실제 의료환경에는 임상 검증, 규제 검토, 전자서명, 데이터 보존과 QMS 절차가 추가로 필요합니다.
