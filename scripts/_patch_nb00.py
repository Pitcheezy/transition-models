"""Patch notebook 00: update Model C section + Phase 6 progress."""
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

# ------ Cell 12: Model C 본격 학습 → 완료로 업데이트 ------
nb['cells'][12] = md_cell("""\
## Model C 본격 학습 ✅ 완료

- **시작**: 2026-05-07 14:27
- **완료**: 2026-05-07 19:20 (4시간 53분)
- **설정**: stride=8, batch_size=32, lr=1e-4, 30 epochs, patience=5
- **W&B**: [model_c_full_v2](https://wandb.ai/pitcheezy/transition-models/runs/nawthn1p)

### 학습 결과

| Epoch | Val Loss | PR Acc | HL Acc |
|-------|---------|--------|--------|
| 10 | 1.9821 | 64.8% | 35.1% |
| 20 | 1.8712 | 66.3% | 36.8% |
| **29 (Best)** | **1.8334** | **67.1%** | **37.4%** |
| 30 (Final) | 1.8367 | 67.0% | 37.3% |

> Early stopping 미발동 — 30 epochs 완주. patience=5 이내에 계속 개선.

### Phase 6.1: Test 평가 결과

**Pitch Result (10-class)**:
- **Top-1: 66.7%** (Model B 60.8%보다 +5.9pp ↑)
- Top-3: 94.6%
- CE: 0.8795, Brier: 0.4495
- Ball 88.2% / Strike 81.9% / Walk 87.7% ⭐
- Single/Double/Triple/HR: **0.0%** ❌ (class imbalance)

**Hit Location (9-class, InPlay)**:
- 유효 샘플: 4,917 / 22,127
- Top-1: 36.6%, Top-3: 65.9%""")

# ------ Cell 14: 진행 상황 시각화 → Phase 6 반영 ------
nb['cells'][14] = code_cell("""\
# Phase별 진행 상황 시각화 (Phase 6 완료 반영)
phases = [
    ('Phase 1\\n환경 셋업', 100, '#2ECC71'),
    ('Phase 2\\n데이터', 100, '#2ECC71'),
    ('Phase 3\\n전처리', 100, '#2ECC71'),
    ('Phase 4\\n모델 정의', 100, '#2ECC71'),
    ('Phase 5\\n학습', 100, '#2ECC71'),
    ('Phase 6\\n평가', 100, '#2ECC71'),
]

fig, ax = plt.subplots(figsize=(13, 4))

for i, (label, progress, color) in enumerate(phases):
    ax.barh(i, 100, color='#ecf0f1', height=0.6)
    ax.barh(i, progress, color=color, height=0.6, alpha=0.85)
    ax.text(progress - 3, i, f'{progress}%',
            va='center', ha='right', fontsize=11, fontweight='bold', color='white')
    ax.text(-2, i, label, va='center', ha='right', fontsize=10)

ax.set_xlim(-25, 110)
ax.set_ylim(-0.5, len(phases) - 0.5)
ax.set_xlabel('진행률 (%)', fontsize=11)
ax.set_title('SmartPitch MDP 전이확률 모델 비교 — Phase별 진행 상황 (최종)', fontsize=13, fontweight='bold')
ax.set_yticks([])

for spine in ax.spines.values():
    spine.set_visible(False)

plt.tight_layout()
plt.show()
""")

# ------ Cell 15: 남은 작업 → 완료 항목 체크 ------
nb['cells'][15] = md_cell("""\
---
# 완료된 작업

## Phase 6: 평가 ✅ 완료

- [x] `04_model_c 노트북` 결과 섹션 채우기
- [x] `05_comparison_results.ipynb` 신규 작성
- [x] 이 노트북 Model C 결과 업데이트
- [x] `src/evaluation/metrics.py` (CE, Brier, top-k, per-class)
- [x] `src/evaluation/evaluate.py` (Model B/C eval + baselines)
- [x] `scripts/10_evaluate_models.py` (end-to-end evaluation)
- [x] `tests/test_evaluation.py` (13 tests, all pass)

## 남은 미래 작업 (선택)

- [ ] Model A wrapper 구현 (SmartPitch 통합)
- [ ] 데이터 확장 (2018–2022 추가)
- [ ] Class weighting / Focal loss (소수 클래스 개선)
- [ ] Ablation study (sub-token mask, residual 효과 분리)
- [ ] Calibration 분석 (reliability diagram)""")

with open('notebooks/00_project_journey.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f'Done. Total cells: {len(nb["cells"])}')
