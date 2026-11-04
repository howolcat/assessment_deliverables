"""산출물 6 성능 측정: 동기/비동기 x 캐시 MISS/HIT, 조건별 5회 (제공 API 호출만 수행)"""
import csv
import glob
import statistics
import time
from pathlib import Path
import httpx

BASE = "http://127.0.0.1:8000"
OUT = Path("reports/data/timings.csv")
POLL = 0.05  # 비동기 상태 조회 간격(초)

imgs = sorted(glob.glob("dataset/test/*/*.jpg"))[::12][:10]  # 클래스가 섞이도록 간격 선택
sync_imgs, async_imgs = imgs[:5], imgs[5:]


def post(client, url, path):
    data = Path(path).read_bytes()
    return client.post(url, files={"image": (Path(path).name, data, "image/jpeg")})


def sync_call(client, path):
    t0 = time.perf_counter()
    r = post(client, f"{BASE}/api/sync/classify/", path)
    ms = (time.perf_counter() - t0) * 1000
    j = r.json()
    return r.status_code, ms, ms, j["inference_ms"], j["cache_hit"], j["top1"]["label"], ""


def async_call(client, path):
    t0 = time.perf_counter()
    r = post(client, f"{BASE}/api/async/classify/", path)
    accept_ms = (time.perf_counter() - t0) * 1000
    job_id = r.json()["job_id"]
    while True:
        j = client.get(f"{BASE}/api/async/jobs/{job_id}/").json()
        if j["status"] in ("done", "failed") or time.perf_counter() - t0 > 60:
            break
        time.sleep(POLL)
    final_ms = (time.perf_counter() - t0) * 1000
    label = (j["top1"] or {}).get("label")
    return r.status_code, accept_ms, final_ms, j["inference_ms"], j["cache_hit"], label, job_id


plan = [("sync", "MISS", sync_imgs, sync_call), ("sync", "HIT", sync_imgs, sync_call),
        ("async", "MISS", async_imgs, async_call), ("async", "HIT", async_imgs, async_call)]

rows = []
with httpx.Client(timeout=60) as client:
    for mode, expect, images, fn in plan:
        for i, path in enumerate(images, 1):
            status, http_ms, final_ms, inf_ms, hit, label, job_id = fn(client, path)
            rows.append({"run_id": i, "path": mode, "cache_status": expect, "image": Path(path).name,
                         "gt_label": Path(path).parent.name, "http_status": status,
                         "http_ms": round(http_ms, 1), "final_ms": round(final_ms, 1),
                         "inference_ms": inf_ms, "cache_hit": hit, "top1_label": label, "job_id": job_id})
            print(rows[-1])

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)

print("\n[중앙값 ms]")
for mode, expect, *_ in plan:
    g = [r for r in rows if r["path"] == mode and r["cache_status"] == expect]
    inf = [r["inference_ms"] for r in g if r["inference_ms"] is not None]
    print(f"{mode:5} {expect:4} | HTTP {statistics.median(r['http_ms'] for r in g):7.1f}"
          f" | 최종 {statistics.median(r['final_ms'] for r in g):7.1f}"
          f" | 추론 {statistics.median(inf) if inf else 'NULL'}")
print(f"\n저장: {OUT}")