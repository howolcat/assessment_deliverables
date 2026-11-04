"""Test 세트 1회 평가 도구 (모델 선택에는 사용하지 않음, 결과 기록용)"""
import json
import sys
from pathlib import Path
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

EXTS = {".jpg", ".jpeg", ".png", ".webp"}  # finetune.py와 같은 확장자 기준


def evaluate(model_dir, data_dir="dataset/test"):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # 학습 때 저장한 전처리기와 모델을 그대로 불러온다
    processor = AutoImageProcessor.from_pretrained(model_dir)
    model = AutoModelForImageClassification.from_pretrained(model_dir).to(device).eval()
    classes = [model.config.id2label[i] for i in range(model.config.num_labels)]
    cm = [[0] * len(classes) for _ in classes]  # 혼동행렬: cm[정답][예측]

    for gt, name in enumerate(classes):  # 정답은 폴더 이름(라벨)을 따른다
        for path in sorted((Path(data_dir) / name).iterdir()):
            if path.suffix.lower() not in EXTS:
                continue
            with Image.open(path) as im:
                x = processor(images=im.convert("RGB"), return_tensors="pt")["pixel_values"].to(device)
            with torch.no_grad():  # 평가만 하므로 기울기 계산 안 함
                pred = model(pixel_values=x).logits.argmax(-1).item()
            cm[gt][pred] += 1

    total = sum(map(sum, cm))
    correct = sum(cm[i][i] for i in range(len(classes)))
    per_class = {}
    for i, name in enumerate(classes):
        tp = cm[i][i]
        pred_cnt = sum(cm[r][i] for r in range(len(classes)))  # 이 클래스로 예측한 수
        true_cnt = sum(cm[i])                                    # 실제 이 클래스인 수
        p = tp / pred_cnt if pred_cnt else 0.0
        r = tp / true_cnt if true_cnt else 0.0
        per_class[name] = {"precision": round(p, 4), "recall": round(r, 4),
                           "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0, "support": true_cnt}
    return {"model": model_dir, "test_count": total, "test_accuracy": round(correct / total, 4),
            "classes": classes, "confusion_matrix_rows_gt_cols_pred": cm, "per_class": per_class}


results = [evaluate(m) for m in sys.argv[1:]]
out = Path("reports/data/test_eval.json")
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(results, ensure_ascii=False, indent=2))
print(f"저장: {out}")