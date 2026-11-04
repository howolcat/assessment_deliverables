<div align="center">

# 🌱 콩잎 질병 분류 Vision AI

콩잎 사진 한 장으로 **각진잎반점병 · 녹병 · 정상**을 판별하는 웹 서비스

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-2.5.1-EE4C2C?logo=pytorch&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-5.6-37814A?logo=celery&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7.4-DC382D?logo=redis&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Docker%20Compose-2496ED?logo=docker&logoColor=white)

</div>

## 📌 개요

교과 9 과제평가(2026.11.04) 프로젝트입니다. `microsoft/resnet-18`의 출력층을 3클래스로 바꿔 콩잎 데이터셋 [AI-Lab-Makerere/beans](https://huggingface.co/datasets/AI-Lab-Makerere/beans)(Train 1,034 · Val 133 · Test 128장)로 Fine-tuning했습니다. 학습한 모델은 **동기**(요청 → 바로 결과)와 **비동기**(202 접수 → Celery worker 처리 → 상태 조회) 두 경로로 서비스합니다.

## ✨ 핵심 결과

| 항목 | 결과 |
|---|---|
| **최종 서비스 모델** | C. Full Fine-tuning (lr 5e-5) — Val **97.0%** · Test **95.3%** (참고) |
| 필수 기준선 | A. Head-only — Val 76.7% · Test 71.9% (이 모델로 전체 기능 검증 후 교체) |
| 모델 선택 근거 | B·C의 Val이 같아(0.9699) **Val 안정성**으로 C 선택, Test는 선택에 쓰지 않음 |
| 캐시 효과 (동기) | 27.4ms → **2.7ms** (90.1% 감소) |
| 비동기 접수 | **8.8ms** (동기 대비 67.9% 빠름) · 서버 처리 MISS 32ms / HIT 8ms |
| 기능 테스트 | 실환경 **23건 PASS** · 모의 테스트 **4 passed** |

## 🏗 구성

```text
브라우저 ──HTTP──▶ web (FastAPI)
                   ├─ 동기   : Redis 캐시 확인 → 모델 추론 → 200 응답
                   └─ 비동기 : PostgreSQL 작업 기록 → Redis 큐 → worker(Celery) 추론 → 결과 저장
```

4개 컨테이너(`web`, `worker`, `redis`, `postgres`)를 Docker Compose로 실행하며, 추론은 CPU로 합니다. 자세한 구성도는 [산출물 2](reports/02_시스템_아키텍처.md)에 있습니다.

## ▶ 실행

`dataset/`과 `artifacts/`(학습 모델)는 용량 때문에 저장소에서 제외했습니다. 학습 설정과 실험별 명령은 [산출물 1](reports/01_FineTuning_결과보고서.md)에 있습니다.

**환경**: Windows 11 + WSL2 Ubuntu · Docker Desktop (Compose) · 학습은 Python 가상환경 (NVIDIA GPU가 있으면 자동 사용)

```bash
# 1) 데이터: beans의 train / validation / test.zip → dataset/{train,val,test} (validation은 val로)
# 2) 학습 (최종 모델 C)
python -m training.finetune --data dataset --output artifacts/beans_resnet18_full_lr5e-5 \
  --epochs 3 --batch-size 8 --lr 0.00005
# 3) 서비스 실행
cp .env.example .env
sed -i 's|^MODEL_PATH=.*|MODEL_PATH=artifacts/beans_resnet18_full_lr5e-5|' .env   # 최종 모델 C
docker compose up -d --build            # redis · postgres · web · worker
curl http://127.0.0.1:8000/health       # {"status":"ok"}
```

같은 컴퓨터의 브라우저에서 접속합니다: `http://127.0.0.1:8000/vision/sync/` (동기) · `/vision/async/` (비동기) · `/docs` (Swagger)

**확인할 응답**: 동기 200 (`top1`, `all`, `cache_hit`, `inference_ms`) · 비동기 202 `job_id` → 조회 `status=done` · PostgreSQL `image_jobs`에 작업 기록

## 📁 산출물

| 1. [Fine-tuning 결과](reports/01_FineTuning_결과보고서.md) | 2. [시스템 아키텍처](reports/02_시스템_아키텍처.md) | 3. [API 명세서](reports/03_API_명세서.md) | 4. [DB 구조·작업이력](reports/04_DB_구조_작업이력.md) |
|---|---|---|---|
| **5. [AI 버튼 처리흐름](reports/05_AI버튼_처리흐름.md)** | **6. [성능비교](reports/06_성능비교_보고서.md)** | **7. [기능테스트·오류분석](reports/07_기능테스트_오류분석.md)** | **8. [최종 기술보고서](reports/08_최종기술보고서.md)** |

실행 캡처 `reports/evidence/` · 측정 원본 `reports/data/` (`timings.csv` 등) · 그래프 `reports/figures/`

> 🔒 `.env`, `dataset/`, `artifacts/`, `media/jobs/`는 저장소에서 제외했고, 모든 포트는 `127.0.0.1`에만 열려 있습니다. 모델 `microsoft/resnet-18` (Apache-2.0) · 데이터 `AI-Lab-Makerere/beans` (MIT 표기)
