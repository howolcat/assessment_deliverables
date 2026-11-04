# 콩잎 질병 분류 Vision AI — ResNet18 Fine-tuning · FastAPI · Redis · Celery

콩잎 사진 한 장을 업로드하면 Fine-tuning한 ResNet18이 잎 상태를 3가지로 분류하는 웹 서비스입니다.
결과는 **동기 방식**(바로 응답)과 **비동기 방식**(작업 접수 후 조회) 두 가지로 받을 수 있습니다.

| 클래스 | 의미 |
|---|---|
| `angular_leaf_spot` | 각진잎반점병 |
| `bean_rust` | 콩 녹병 |
| `healthy` | 정상 |

**주요 결과**

| 항목 | 값 |
|---|---|
| 서비스 모델 | Head-only Fine-tuning — Val Acc **0.7669**, Test Acc **0.7188** |
| 비교 모델 | Full Fine-tuning — Val Acc **0.9699**, Test Acc **0.9297** |
| 캐시 효과 | 동기 응답 41.2ms → 4.3ms (**89.6% 감소**) |
| 비동기 접수 | 13.4ms (동기 대비 HTTP 응답 **67.5% 빠름**) |

자세한 내용은 [최종 기술보고서](reports/08_최종기술보고서.md)를 참고하세요.

---

## 1. 구성

```text
브라우저 ──▶ web (FastAPI :8000) ──▶ redis (DB1 캐시 / DB2 브로커 / DB3 결과)
                │                        │
                ├──▶ postgres (image_jobs)◀── worker (Celery)
                └── ./artifacts, ./media/jobs 공유 ──┘
```

| 서비스 | 역할 |
|---|---|
| `web` | FastAPI — 동기 분류, 비동기 접수·상태 조회, 웹 화면 |
| `worker` | Celery — 비동기 추론, DB 상태 갱신 |
| `redis` | 결과 캐시(DB 1) + Celery 브로커(DB 2) + 결과 백엔드(DB 3) |
| `postgres` | 비동기 작업 기록 (`image_jobs`) |

4개 서비스 모두 Docker Compose로 한 번에 실행합니다. 추론은 컨테이너 안에서 **CPU**로 실행됩니다.

---

## 2. 실행 환경

| 항목 | 검증한 환경 |
|---|---|
| OS | Windows 11 Pro 25H2 + WSL2 Ubuntu 26.04.1 LTS |
| Docker | Docker Desktop (Docker 29.9.2, Compose v5.6.1) |
| 학습 (선택) | Python 3.11 이상 가상환경, NVIDIA GPU 있으면 자동 사용 (검증: Python 3.14.4, RTX 3060) |
| 서비스 컨테이너 | Python 3.11, torch 2.5.1+cpu (Dockerfile에서 자동 설치) |

---

## 3. 데이터 준비

> `dataset/`은 용량 문제로 저장소에 포함하지 않았습니다. 아래 방법으로 직접 받아주세요.

출처: Hugging Face [`AI-Lab-Makerere/beans`](https://huggingface.co/datasets/AI-Lab-Makerere/beans) (데이터셋 라이선스 표기: MIT)

```bash
# 원본 보관 폴더에 받기
mkdir -p ~/beans_source && cd ~/beans_source
for f in train validation test; do
  wget https://huggingface.co/datasets/AI-Lab-Makerere/beans/resolve/main/data/$f.zip
  unzip -q $f.zip
done

# 프로젝트로 복사 (validation → val 로 이름 변경 필수)
cd ~/fastapi_resnet18
mkdir -p dataset/{train,val,test}
cp -r ~/beans_source/train/*      dataset/train/
cp -r ~/beans_source/validation/* dataset/val/
cp -r ~/beans_source/test/*       dataset/test/
```

결과 구조:

```text
dataset/
├── train/{angular_leaf_spot, bean_rust, healthy}/   # 1,035 파일 (학습 사용 1,034장)
├── val/  {angular_leaf_spot, bean_rust, healthy}/   # 133장
└── test/ {angular_leaf_spot, bean_rust, healthy}/   # 128장
```

---

## 4. 모델 준비

> `artifacts/`도 저장소에 포함하지 않았습니다. 서버를 실행하기 전에 **학습된 모델이 반드시 있어야** 합니다.

**방법 A — 로컬 가상환경에서 학습 (검증한 방법)**

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python -m training.finetune --data dataset --output artifacts/beans_resnet18 \
  --epochs 3 --batch-size 8 --freeze-backbone
```

**방법 B — Docker trainer로 학습**

```bash
cp .env.example .env
docker compose build
docker compose run --rm trainer
```

학습이 끝나면 `artifacts/beans_resnet18/`에 `config.json`, `model.safetensors`, `preprocessor_config.json`, `training_report.json`이 생깁니다.

(선택) 비교용 Full Fine-tuning: `--freeze-backbone`을 빼고 `--output artifacts/beans_resnet18_full`로 실행

---

## 5. 서비스 실행

```bash
cd ~/fastapi_resnet18
cp .env.example .env          # MODEL_PATH=artifacts/beans_resnet18
mkdir -p media/jobs
docker compose up -d --build  # redis, postgres, web, worker 동시 실행
```

상태 확인:

```bash
docker compose ps                       # 4개 Up, web·redis·postgres는 (healthy)
docker compose logs --tail=40 web worker # worker에 "celery@... ready." 확인
curl http://127.0.0.1:8000/health        # {"status":"ok"}
```

| 주소 | 화면 |
|---|---|
| http://127.0.0.1:8000/vision/sync/ | 동기 분류 화면 |
| http://127.0.0.1:8000/vision/async/ | 비동기 분류 화면 |
| http://127.0.0.1:8000/docs | Swagger API 문서 |

> 로컬에서 따로 `uvicorn`을 실행하지 마세요. web 컨테이너가 8000 포트를 사용합니다.

---

## 6. API 사용 예

```bash
IMG="$(find dataset/test/healthy -maxdepth 1 -iname '*.jpg' -print -quit)"

# 동기: 결과가 바로 응답에 포함 (200)
curl -X POST -F "image=@${IMG}" http://127.0.0.1:8000/api/sync/classify/

# 비동기: 작업 번호만 먼저 반환 (202)
curl -i -X POST -F "image=@${IMG}" http://127.0.0.1:8000/api/async/classify/

# 상태 조회: status가 done이면 완료 (받은 job_id로 교체)
curl http://127.0.0.1:8000/api/async/jobs/1/

# DB 기록 확인 (비동기 작업만 저장)
docker compose exec postgres psql -U vision_user -d vision_db -c \
  'SELECT id, status, top1_label, top1_score, cache_hit, inference_ms FROM image_jobs ORDER BY id DESC LIMIT 10;'
```

자세한 요청·응답은 [API 명세서](reports/03_API_명세서.md)를 참고하세요.

---

## 7. 테스트

```bash
# 모의 통합 테스트 (모델·Redis·Celery를 가짜로 바꿔 API 동작 검증)
docker compose exec web python -m pytest -q tests/test_api.py   # 4 passed
```

> `pytest`만 입력하면 `ModuleNotFoundError: No module named 'ai'`가 납니다. 반드시 `python -m pytest`로 실행하세요.

측정 도구 (제공 코드가 아닌 평가용 보조 스크립트):

```bash
python reports/measure_timings.py      # 동기/비동기 × 캐시 MISS/HIT 응답시간 → reports/data/timings.csv
python reports/evaluate_test.py artifacts/beans_resnet18 artifacts/beans_resnet18_full  # Test 1회 평가
```

---

## 8. 종료와 재시작

```bash
docker compose stop                          # 중지 (데이터 보존)
docker compose up -d                         # 재시작
docker compose up -d --build                 # 코드·Dockerfile 변경 시
docker compose up -d --force-recreate web worker   # 모델이나 .env 변경 시
```

> ⚠️ `docker compose down -v`는 PostgreSQL·Redis 데이터를 삭제합니다.

---

## 9. 문제 해결

| 현상 | 확인할 것 |
|---|---|
| `web`이 뜨지 않음 | `docker compose logs web`, postgres가 healthy인지 |
| 비동기 작업이 계속 `queued` | `docker compose logs worker`, worker 컨테이너가 Up인지 |
| 비동기 접수가 503 | Redis 컨테이너 상태 (`docker compose ps redis`) |
| 라벨이 ImageNet 사물 이름으로 나옴 | `.env`의 `MODEL_PATH`가 `artifacts/beans_resnet18`인지, 학습했는지 |
| `address already in use` | 8000·6379·5432 포트를 쓰는 다른 프로그램(로컬 uvicorn 등) 종료 |
| 첫 요청만 2~3초 걸림 | 정상 — 프로세스마다 첫 요청에서 모델을 로드 |

---

## 10. 폴더 구조

```text
fastapi_resnet18/
├── ai/                    # FastAPI 라우터, 모델 로드, 캐시, DB, Celery 작업
├── training/finetune.py   # Fine-tuning 코드
├── templates/, static/    # 웹 화면
├── tests/test_api.py      # 모의 통합 테스트
├── main.py                # FastAPI 앱
├── Dockerfile, compose.yaml, .dockerignore
├── requirements.txt, .env.example
├── reports/               # 산출물 1~8, 증빙, 측정 데이터, 그래프, 측정 도구
├── dataset/               # (저장소 제외) 콩잎 이미지
├── artifacts/             # (저장소 제외) 학습 모델
└── media/jobs/            # (저장소 제외) 비동기 업로드 이미지
```

## 11. 산출물

| # | 문서 |
|---|---|
| 1 | [Fine-tuning 결과보고서](reports/01_FineTuning_결과보고서.md) |
| 2 | [시스템 아키텍처](reports/02_시스템_아키텍처.md) |
| 3 | [API 명세서](reports/03_API_명세서.md) |
| 4 | [DB 구조·작업이력](reports/04_DB_구조_작업이력.md) |
| 5 | [AI 버튼 처리흐름](reports/05_AI버튼_처리흐름.md) |
| 6 | [성능비교 보고서](reports/06_성능비교_보고서.md) |
| 7 | [기능테스트·오류분석](reports/07_기능테스트_오류분석.md) |
| 8 | [최종 기술보고서](reports/08_최종기술보고서.md) |

## 12. 보안·라이선스

- `.env`, `dataset/`, `artifacts/`, `media/jobs/`는 `.gitignore`로 저장소에서 제외했습니다.
- `compose.yaml`의 DB 계정(`vision_user` / `vision_pass`)은 로컬 실습용이며, 포트는 `127.0.0.1`에만 열려 있습니다.
- 모델: `microsoft/resnet-18` (Apache-2.0) · 데이터: `AI-Lab-Makerere/beans` (MIT 표기) — 사용·공유 전 각 저장소의 이용 조건을 확인하세요.
