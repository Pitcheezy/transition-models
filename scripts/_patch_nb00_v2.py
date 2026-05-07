"""Patch notebook 00: add Day 2 evening section + Phase 6 viz."""
import json


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


with open('notebooks/00_project_journey.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

# ── Cell 0: update header period (진행 중 → 2026-05-08 완료) ──
src0 = ''.join(nb['cells'][0]['source'])
src0 = src0.replace('**기간**: 2026-05-06 ~ (진행 중)', '**기간**: 2026-05-06 ~ 2026-05-08')
nb['cells'][0]['source'] = src0

# ── Insert "Day 2 저녁" section header before cell 12 ──
evening_md = """\
---
## 오후–저녁: Phase 5.5 Model C + Phase 6 평가 + 비교 노트북"""

phase6_viz_code = """\
# Phase 6 핵심 결과: Model B vs Model C 비교 (실제 evaluation 데이터)
import numpy as np
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

data_b = np.load('../outputs/evaluation_b.npz', allow_pickle=True)
data_c = np.load('../outputs/evaluation_c.npz', allow_pickle=True)

models = ['Model A\\n(Baseline)', 'Model B\\n(MLP, 4-class)', 'Model C\\n(Transformer, 10-class)']
top1 = [
    float(data_b['baseline_empirical_top_1']),
    float(data_b['top_1']),
    float(data_c['top_1_pr']),
]
ce = [
    float(data_b['baseline_empirical_ce']),
    float(data_b['ce']),
    float(data_c['ce_pr']),
]
colors = ['#bdc3c7', '#3498db', '#27ae60']

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# Top-1
bars = axes[0].bar(models, top1, color=colors, alpha=0.85, width=0.45)
axes[0].set_ylim(0, 1.0)
axes[0].set_ylabel('Top-1 Accuracy', fontsize=12)
axes[0].set_title('Top-1 Accuracy 비교', fontsize=13, fontweight='bold')
for bar, v in zip(bars, top1):
    axes[0].text(bar.get_x() + bar.get_width()/2, v + 0.02,
                f'{v:.1%}', ha='center', fontsize=12, fontweight='bold')
axes[0].grid(True, alpha=0.3, axis='y')

# CE
bars2 = axes[1].bar(models, ce, color=colors, alpha=0.85, width=0.45)
axes[1].set_ylabel('Cross-entropy (↓ 낮을수록 좋음)', fontsize=12)
axes[1].set_title('Cross-entropy 비교', fontsize=13, fontweight='bold')
axes[1].set_ylim(0, 1.6)
for bar, v in zip(bars2, ce):
    axes[1].text(bar.get_x() + bar.get_width()/2, v + 0.04,
                f'{v:.3f}', ha='center', fontsize=12, fontweight='bold')
axes[1].grid(True, alpha=0.3, axis='y')

plt.suptitle('Phase 6 최종 결과: Model A / B / C 비교', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.show()

print(f'Model B  top-1: {top1[1]:.4f} | CE: {ce[1]:.4f}')
print(f'Model C  top-1: {top1[2]:.4f} | CE: {ce[2]:.4f}  (10-class, 더 어려운 문제에서 더 높음!)')
"""

class_imbalance_md = """\
### Class Imbalance 발견 (Phase 6.1)

Model C 10-class 평가에서 명확한 패턴 발견:

| Class | 추정 비율 | Test Accuracy |
|-------|----------|--------------|
| Ball | ~30% | **88.2%** ⭐ |
| Strike | ~15% | **81.9%** ⭐ |
| Walk | ~3% | **87.7%** ⭐ |
| Strikeout | ~6% | 14.3% ⚠️ |
| FieldOut | ~12% | 7.3% ⚠️ |
| Single | ~4% | **0.0%** ❌ |
| Double | ~1% | **0.0%** ❌ |
| Triple | ~0.1% | **0.0%** ❌ |
| HomeRun | ~1% | **0.0%** ❌ |
| HitByPitch | ~0.5% | 3.1% ❌ |

**교훈**: Cross-entropy loss는 빈도에 따라 자동 가중치를 주지 않음.
소수 클래스 misclassification이 전체 loss에 미치는 영향이 미미해서 모델이 무시.
→ 향후 weighted loss 또는 focal loss 필요."""

# Current cell layout:
# ... cell 11 (stride viz)
# cell 12: Model C 완료 (already patched)
# cell 13: 핵심 Contribution
# ...

# Insert [evening_header, phase6_viz, class_imbalance] before current cell 12
new_cells = [
    md_cell(evening_md),
]

nb['cells'] = nb['cells'][:12] + new_cells + nb['cells'][12:]

# After the existing cell 12 (now at index 13 = Model C 완료), insert viz + imbalance
# Model C 완료 is now at 13, so insert at 14
nb['cells'] = nb['cells'][:14] + [code_cell(phase6_viz_code), md_cell(class_imbalance_md)] + nb['cells'][14:]

with open('notebooks/00_project_journey.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f'Done. Total cells: {len(nb["cells"])}')
