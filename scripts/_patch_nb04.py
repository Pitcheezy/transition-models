"""Patch notebook 04: replace TODO results cell with actual Model C results."""
import json

with open('notebooks/04_model_c_mit_sloan_2025.ipynb', encoding='utf-8') as f:
    nb = json.load(f)


def md_cell(source):
    return {"cell_type": "markdown", "metadata": {}, "source": source}


def code_cell(source):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source,
    }


results_md = """## 11. 결과 (학습 완료 ✅)

### 학습 통계

| 항목 | 값 |
|------|-----|
| 학습 시간 | 4시간 53분 (RTX 4070, batch_size=32) |
| Best epoch | 29 |
| 30 epochs 완주 | ✅ (early stopping 안 됨) |
| W&B URL | https://wandb.ai/pitcheezy/transition-models/runs/nawthn1p |

### Validation 결과 (Best epoch 29)

| 항목 | 값 |
|------|-----|
| Total val_loss | 1.8334 |
| pr_loss | 0.8835 |
| hl_loss | 1.7357 |
| pr_accuracy | 67.1% |
| hl_accuracy | 37.4% |

### Test 결과 (Pitch Result, 10-class)

| Metric | 값 |
|--------|-----|
| Cross-entropy | 0.8795 |
| Brier score | 0.4495 |
| Top-1 accuracy | **66.7%** ⭐ |
| Top-3 accuracy | 94.6% |
| Baseline (Empirical) | 41.4% |

### Test 결과 (Hit Location, 9-class, InPlay 한정)

| Metric | 값 |
|--------|-----|
| Valid samples | 4,917 / 22,127 |
| Top-1 accuracy | 36.6% |
| Top-3 accuracy | 65.9% |

### Per-class accuracy (Pitch Result)

| Class | Accuracy | 평가 |
|-------|----------|------|
| Ball | 88.2% | ⭐ |
| Strike | 81.9% | ⭐ |
| Walk | 87.7% | ⭐ |
| Strikeout | 14.3% | ⚠️ |
| FieldOut | 7.3% | ⚠️ |
| Single | 0.0% | ❌ |
| Double | 0.0% | ❌ |
| Triple | 0.0% | ❌ |
| HomeRun | 0.0% | ❌ |
| HitByPitch | 3.1% | ❌ |

**Ball/Strike/Walk**: 다수 클래스라 80%+ 정확도
**Single ~ HitByPitch**: 소수 클래스 — class imbalance 미처리의 결과"""

viz_code = """\
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

data_c = np.load('../outputs/evaluation_c.npz', allow_pickle=True)

classes_10 = ['Ball', 'Strike', 'Single', 'Double', 'Triple',
              'HomeRun', 'FieldOut', 'Strikeout', 'Walk', 'HitByPitch']
per_class_acc = data_c['per_class_accuracy_pr']

fig, ax = plt.subplots(figsize=(12, 6))
colors = ['#27ae60' if a > 0.5 else '#f39c12' if a > 0.1 else '#e74c3c'
          for a in per_class_acc]
bars = ax.bar(classes_10, per_class_acc, color=colors, alpha=0.8)
ax.set_ylabel('Accuracy', fontsize=12)
ax.set_title('Model C: Per-class Accuracy (Test Set, 10-class)', fontsize=14, fontweight='bold')
ax.set_ylim(0, 1.1)

for bar, val in zip(bars, per_class_acc):
    ax.text(bar.get_x() + bar.get_width()/2, val + 0.03,
            f'{val:.1%}', ha='center', fontsize=9, fontweight='bold')

ax.axhline(y=0.5, color='red', linestyle='--', alpha=0.5, label='50% 기준선')
ax.legend(fontsize=11)
plt.xticks(rotation=30, ha='right')
plt.tight_layout()
plt.show()
print(f'Top-1: {float(data_c[\"top_1_pr\"]):.4f}  Top-3: {float(data_c[\"top_3_pr\"]):.4f}')
print(f'CE: {float(data_c[\"ce_pr\"]):.4f}  Brier: {float(data_c[\"brier_pr\"]):.4f}')
"""

cm_code = """\
cm = data_c['confusion_matrix_pr']

fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=classes_10, yticklabels=classes_10, ax=ax)
ax.set_xlabel('Predicted', fontsize=12)
ax.set_ylabel('True', fontsize=12)
ax.set_title('Model C: Confusion Matrix (Pitch Result, 10-class)', fontsize=14, fontweight='bold')
ax.tick_params(axis='x', rotation=30)
plt.tight_layout()
plt.show()
"""

analysis_md = """### 분석

**잘 작동하는 부분:**
- Ball/Strike/Walk: 80%+ 정확도 (다수 클래스, 학습 샘플 충분)
- Top-3 accuracy 94.6%: 모델이 거의 항상 정답을 후보 3개 안에 포함

**문제점 발견:**
- Single/Double/Triple/HomeRun: 0% (전혀 예측 못함)
- 원인: Class imbalance — Triple/HR는 전체의 1% 미만
- Loss 가중치 무처리 + Weighted sampler 미사용의 결과

**다음 단계:**
- Class weights: `F.cross_entropy(logits, targets, weight=class_weights)`
- Focal loss: 잘 분류된 sample 가중치 감소
- Oversampling: 소수 클래스 더 자주 샘플링"""

# Replace cell 19 (TODO results) with actual results
nb['cells'][19] = md_cell(results_md)

# Insert visualization cells before the existing cell 20
nb['cells'] = (
    nb['cells'][:20]
    + [code_cell(viz_code), code_cell(cm_code), md_cell(analysis_md)]
    + nb['cells'][20:]
)

with open('notebooks/04_model_c_mit_sloan_2025.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f'Done. Total cells: {len(nb["cells"])}')
