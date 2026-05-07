"""Append 2026-05-08 daily memo row to README.md."""

new_row = (
    "| 2026-05-08 | 조현준 | **Phase 5 + Phase 6 완료 - 학교 RTX 4070 환경에서 본격 학습 + 평가 + 비교 노트북**<br><br>"
    "**한 일**<br>"
    "- Mac → Windows (HP OMEN Transcend 16, RTX 4070 8GB) 환경 이전: PyTorch CUDA 셋업 (pyproject.toml [tool.uv.sources]에 cu124 인덱스 추가), `get_device()` multi-platform helper 추가 (CUDA → MPS → CPU)<br>"
    "- Phase 5.1~5.4: Training loop + W&B integration + Sanity check 완료 (TrainingConfig, AdamW + CosineAnnealingLR, multi-task loss, early stopping patience=5, checkpoint best+last). 4 unit tests + 두 sanity training 통과<br>"
    "- **Model B 본격 학습**: 749K samples × max 200 epochs (early stopped epoch 20, best epoch 10), best val_loss 0.873, val_acc **60.6%** (baseline 35.6% 대비 **+25pp**), 8분 소요. W&B run: bspnzo7m<br>"
    "- 노트북 02, 03, 04 작성 (Model A baseline + Model B/C walkthrough, 한국어 markdown + matplotlib 시각화, sub-token masking 시각화 포함)<br>"
    "- **Model C 시도 1 (실패)**: stride=1로 30 epochs 시도 → 1 epoch에 76분 → 30 epochs = 38시간 예상 → KeyboardInterrupt로 중단. Epoch 1 결과 train=1.95, val=1.87 (학습 자체는 잘 됨, 시간만 문제)<br>"
    "- **Stride 최적화 (8배 단축)**: stride=1 → stride=8로 데이터 재처리 (sequences 521K → 65K), 학습 시간 38h → 5h. Architecture는 그대로 유지 (sequence_length=400)<br>"
    "- **Model C 본격 학습**: 65K sequences × 30 epochs (full, early stopping 안 됨), best val_loss 1.833 (epoch 29), val pr_acc **67.1%**, val hl_acc 37.4%, 4시간 53분 소요. W&B run: nawthn1p<br>"
    "- 한글 폰트 깨짐 수정: Windows에서 matplotlib 한글 □□□ → Malgun Gothic 폰트 명시 (03/04 노트북)<br>"
    "- 노트북 00 (project_journey) 신규 작성: Day 1 + Day 2 진행 일지 + 시각화 (메모리 비교, GPU 성능, Model B 결과, Stride 효과) + 트러블슈팅 + 회고<br>"
    "- **Phase 6 평가 (test set)**: scripts/10_evaluate_models.py로 Model B + Model C + baseline 평가 → outputs/evaluation_b.npz, evaluation_c.npz 저장<br>"
    "  - Model B test top-1: **60.8%** (CE 0.876, top-3 96.6%)<br>"
    "  - Model C test top-1 (Pitch Result, 10-class): **66.7%** (CE 0.880, top-3 94.6%) — **더 어려운 10-class에서 Model B 4-class보다 높음**<br>"
    "  - Per-class accuracy 정량 분석<br>"
    "- 노트북 04에 Model C 결과 채우기 (TODO → 실제 결과)<br>"
    "- 노트북 05 (comparison_results) 신규 작성: Model A baseline / Model B (MLP) / Model C (Transformer) 3-way 비교, top-1 / CE / per-class / confusion matrix 시각화, 논문 결과 비교 (Model B +8pp), 결론<br><br>"
    "**배운 것**<br>"
    "- **Architecture가 결정적**: Model C가 더 어려운 10-class 문제 (66.7%)에서 Model B의 4-class (60.8%)보다 더 높은 정확도. Sequence + Transformer의 효과를 정량적으로 입증<br>"
    "- **Stride trade-off**: stride=1은 메모리뿐만 아니라 **시간**도 큰 문제 (38h). stride=8은 데이터 다양성 ↑, 중복 ↓, 학습 시간 8배 ↓ — sweet spot<br>"
    "- **Class Imbalance 영향 정량적 발견**: 다수 클래스 (Ball/Strike/Walk) 80%+, 소수 클래스 (Single/Double/Triple/HomeRun) **0%** — 무처리 결정의 결과를 정량적으로 발견. 향후 weighted loss 또는 focal loss 필요<br>"
    "- **PyTorch CUDA + uv**: 첫 uv sync 시 PyTorch CPU 버전 자동 설치됨. pyproject.toml의 [tool.uv.sources] + [[tool.uv.index]]로 platform별 PyTorch 인덱스 분리하면 깔끔하게 해결<br>"
    "- **Multi-platform 추상화의 가치**: get_device() helper 하나로 Mac MPS / Windows CUDA / CPU 코드 통합. 일찍 만들어두면 환경 이전 시 큰 도움<br>"
    "- **W&B의 강력함**: 학습 진행 중에도 폰으로 loss curve 모니터링 가능. 발표 자료로 바로 사용 가능한 그래프 자동 생성<br>"
    "- **Sanity check의 가치**: 64 sequences × 5 epochs로 학습 동작 미리 검증. 본격 학습 전 자신감 확보<br><br>"
    "**이슈/다음 작업**<br>"
    "- Class imbalance 처리 (Triple/HR 0% accuracy 해결): weighted loss / focal loss / weighted random sampler 도입<br>"
    "- Continuous regression target 실제 구현 (현재 placeholder 0)<br>"
    "- Model A wrapper 구현 (실제 SmartPitch 통합)<br>"
    "- Data 확장 (2018-2022 추가 후 재학습)<br>"
    "- Ablation study (sub-token mask, last-pitch residual 효과 분리 검증)<br>"
    "- 발표 슬라이드 자료 작성 (노트북 05 활용) |"
)

with open('README.md', encoding='utf-8') as f:
    content = f.read()

# The table ends with the last row. Append new row at the end.
content = content.rstrip('\n') + '\n' + new_row + '\n'

with open('README.md', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done. README.md updated.')
