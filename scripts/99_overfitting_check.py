"""MLP 135-dim 10-class 과적합 점검 스크립트."""
import sys
from pathlib import Path
import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CLASS_NAMES = ['Ball','Strike','Single','Double','Triple','HomeRun','FieldOut','Strikeout','Walk','HBP']
DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUT_DIR = PROJECT_ROOT / "outputs"
CKPT_DIR = OUT_DIR / "checkpoints"

# ── 1. Checkpoint 메타데이터 ────────────────────────────────────────
print("=" * 65)
print("1. Checkpoint 메타데이터")
print("=" * 65)
ckpt_b3 = torch.load(CKPT_DIR / "model_b3_135dim_10cls_best.pt", weights_only=False, map_location="cpu")
print(f"  Best epoch    : {ckpt_b3['epoch']}")
print(f"  Val loss      : {ckpt_b3['val_metrics']['loss']:.4f}")
print(f"  Val accuracy  : {ckpt_b3['val_metrics']['accuracy']*100:.2f}%")

# 기존 77-dim 10-class 모델 비교
try:
    ckpt_mlp10 = torch.load(CKPT_DIR / "model_b_10cls_v1_best.pt", weights_only=False, map_location="cpu")
    print(f"\n  [비교] 77-dim MLP 10cls best epoch: {ckpt_mlp10['epoch']}")
    print(f"  [비교] 77-dim MLP 10cls val loss  : {ckpt_mlp10['val_metrics']['loss']:.4f}")
    print(f"  [비교] 77-dim MLP 10cls val acc   : {ckpt_mlp10['val_metrics']['accuracy']*100:.2f}%")
except Exception as e:
    print(f"  [비교] 77-dim MLP 체크포인트 없음: {e}")

# ── 2. Train / Val / Test 손실 비교 ──────────────────────────────────
print("\n" + "=" * 65)
print("2. Train / Val / Test 손실 비교 (과적합 핵심 지표)")
print("=" * 65)
# 학습 로그에서 기록된 값 (scripts/23 실행 결과)
train_loss_at_best = 0.8665  # epoch 11 train_loss
val_loss_best = 0.8564       # epoch 11 val_loss (best)

d = np.load(OUT_DIR / "evaluation_mlp_135dim_10cls.npz", allow_pickle=True)
test_ce = float(d["ce"])
test_top1 = float(d["top1"])

print(f"  Train loss (epoch 11) : {train_loss_at_best:.4f}")
print(f"  Val   loss (epoch 11) : {val_loss_best:.4f}  ← best checkpoint")
print(f"  Test  CE              : {test_ce:.4f}")
print(f"  Train-Val gap         : {train_loss_at_best - val_loss_best:+.4f}")
print(f"  Val-Test gap          : {val_loss_best - test_ce:+.4f}")
print()
print("  해석: train_loss > val_loss는 dropout(0.2) 때문 (정상)")
print("  Val~=Test: 시간분할 일반화 유효")

# ── 3. 테스트셋 클래스 분포 ──────────────────────────────────────────
print("\n" + "=" * 65)
print("3. 테스트셋 클래스 분포 vs 예측 분포")
print("=" * 65)
probs = d["probs"]    # (N, 10)
targets = d["targets"]  # (N,)
preds = probs.argmax(axis=1)
total = len(targets)

print(f"  {'Class':<12} {'실제 N':>8} {'실제%':>7} {'예측 N':>8} {'예측%':>7} {'diff':>7}")
print("  " + "-" * 55)
for i, name in enumerate(CLASS_NAMES):
    actual_n = int((targets == i).sum())
    pred_n = int((preds == i).sum())
    actual_pct = actual_n / total * 100
    pred_pct = pred_n / total * 100
    diff = pred_pct - actual_pct
    print(f"  {name:<12} {actual_n:>8,} {actual_pct:>7.1f} {pred_n:>8,} {pred_pct:>7.1f} {diff:>+7.1f}")

# ── 4. 혼동행렬 ────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("4. 혼동행렬 요약 (주요 오분류 경로)")
print("=" * 65)
cm = d["confusion_matrix"]
print(f"  {'':12}" + "".join(f"{n:>9}" for n in ['Ball','Strike','Sng','Dbl','Trp','HR','FOut','K','Walk','HBP']))
for i, name in enumerate(CLASS_NAMES):
    row_total = cm[i].sum()
    tp = cm[i, i]
    row = "  " + f"{name:<12}" + "".join(f"{v:>9,}" for v in cm[i]) + f"  | {tp/row_total*100:.0f}%"
    print(row)

# ── 5. 희귀 클래스별 상세 분석 ────────────────────────────────────
print("\n" + "=" * 65)
print("5. 희귀 클래스 예측 분석 (Single~HBP)")
print("=" * 65)
rare_classes = [2, 3, 4, 5, 6, 7, 8, 9]
for i in rare_classes:
    name = CLASS_NAMES[i]
    mask = targets == i
    if not mask.any():
        continue
    prob_true_class = probs[mask, i]
    prob_ball = probs[mask, 0]
    prob_strike = probs[mask, 1]
    actual_pred = preds[mask]
    pred_correct = (actual_pred == i).sum()
    # 가장 많이 잘못 예측한 클래스
    wrong_preds = actual_pred[actual_pred != i]
    if len(wrong_preds) > 0:
        wrong_mode = np.bincount(wrong_preds, minlength=10).argmax()
    else:
        wrong_mode = -1
    print(f"\n  [{name}] n={mask.sum()}")
    print(f"    맞춘 수   : {pred_correct} ({pred_correct/mask.sum()*100:.1f}%)")
    print(f"    가장 많은 오분류 → {CLASS_NAMES[wrong_mode] if wrong_mode >= 0 else 'N/A'}")
    print(f"    모델이 부여한 해당 클래스 평균 확률: {prob_true_class.mean():.4f}")
    print(f"    모델의 Ball 평균 확률: {prob_ball.mean():.4f}")
    print(f"    모델의 Strike 평균 확률: {prob_strike.mean():.4f}")

# ── 6. 상위 클래스 의존도 계산 ────────────────────────────────────
print("\n" + "=" * 65)
print("6. 정확도 기여 분해 (Ball + Strike 의존도)")
print("=" * 65)
ball_correct = int(cm[0, 0])
strike_correct = int(cm[1, 1])
other_correct = int(np.diag(cm).sum() - ball_correct - strike_correct)
ball_n = int(cm[0].sum())
strike_n = int(cm[1].sum())
other_n = total - ball_n - strike_n

print(f"  Ball   정확도 기여 : {ball_correct}/{total} = {ball_correct/total*100:.2f}%")
print(f"  Strike 정확도 기여 : {strike_correct}/{total} = {strike_correct/total*100:.2f}%")
print(f"  나머지 정확도 기여 : {other_correct}/{total} = {other_correct/total*100:.2f}%")
print(f"  Ball+Strike 합산   : {(ball_correct+strike_correct)/total*100:.2f}%")
print(f"  전체 Top-1         : {test_top1*100:.2f}%")
print()
print(f"  나머지 클래스({other_n:,}개) 기여 없을 때 예상 Top-1: "
      f"{(ball_correct+strike_correct)/total*100:.2f}%")
ball_only_acc = ball_n / total * 0.897 + strike_n / total * 0.830
print(f"  Ball/Strike 비율 × 각 정확도 = {ball_only_acc*100:.2f}%  (가중 평균)")

# ── 7. 캘리브레이션 점검 ────────────────────────────────────────────
print("\n" + "=" * 65)
print("7. 캘리브레이션 점검 (예측 확률 신뢰도)")
print("=" * 65)
max_probs = probs.max(axis=1)
print(f"  예측 최대 확률 평균 : {max_probs.mean():.4f}")
print(f"  예측 최대 확률 중앙 : {np.median(max_probs):.4f}")
print(f"  예측 최대 확률 분포:")
thresholds = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
for thr in thresholds:
    cnt = (max_probs >= thr).sum()
    correct = ((max_probs >= thr) & (preds == targets)).sum()
    if cnt > 0:
        print(f"    max_prob >= {thr:.2f}: {cnt:>6,}개 ({cnt/total*100:.1f}%), 실제 정확도: {correct/cnt*100:.1f}%")

# ── 8. Val vs Test 세부 비교 ────────────────────────────────────────
print("\n" + "=" * 65)
print("8. Val / Test split 날짜 분포 점검")
print("=" * 65)
try:
    import pickle, pandas as pd
    # val, test 레이블 분포 비교
    val_labels = np.load(DATA_DIR / "labels_10_b3_val.npy")
    test_labels = np.load(DATA_DIR / "labels_10_b3_test.npy")
    val_valid = val_labels[val_labels >= 0]
    test_valid = test_labels[test_labels >= 0]
    print(f"  Val  총 {len(val_valid):,}개 | Test 총 {len(test_valid):,}개")
    print(f"  {'Class':<12} {'Val%':>7} {'Test%':>7} {'diff':>7}")
    for i, name in enumerate(CLASS_NAMES):
        vp = (val_valid==i).sum() / len(val_valid) * 100
        tp2 = (test_valid==i).sum() / len(test_valid) * 100
        print(f"  {name:<12} {vp:>7.1f} {tp2:>7.1f} {tp2-vp:>+7.1f}")
except Exception as e:
    print(f"  분포 비교 오류: {e}")

print("\n" + "=" * 65)
print("분석 완료")
print("=" * 65)
