# v3 업데이트 — 3시즌 데이터 확장

> 작성: 2026-05-14
> 작성자: 조현준
> 변경 commit: 85ea650

## TL;DR

데이터 정합성 검증 후 2022 시즌을 추가하여 3시즌 (2022-2024, ~2.2M pitches)으로 안전 확장.
Model B/C 재학습 완료. 기존 2시즌 결과는 그대로 보존.

**MDP/DQN 작업하는 팀원**: 새 체크포인트 (`*_v2.pt`, `*_v3.pt`) 사용 권장. 코드 변경 없이 경로만 교체하면 됨.

---

## 📊 성능 비교

### Model B (Otremba MLP, 4-class)

| 지표 | v1 (2시즌) | v2 (3시즌) | 변화 |
|------|-----------|-----------|------|
| Top-1 accuracy | 60.8% | **60.9%** | +0.1pp ↑ |
| Top-3 accuracy | 96.6% | 96.6% | = |
| Cross-Entropy | 0.876 | 0.872 | ↓ 개선 |
| 학습 시간 | 8분 | 11분 | 데이터 1.5배 |

### Model C (Sloan Transformer, 10-class) ⭐ 추천

| 지표 | v2 (2시즌) | v3 (3시즌) | 변화 |
|------|-----------|-----------|------|
| Top-1 accuracy | 66.7% | **67.2%** | +0.5pp ↑ |
| Top-3 accuracy | 94.6% | 94.7% | +0.1pp ↑ |
| Cross-Entropy | 0.880 | 0.868 | ↓ 개선 |
| 학습 시간 | 4h 53m (Mac MPS) | ~10h (RTX 4070) | 데이터 1.5배 |

### 클래스별 정확도 (Model C, 10-class)

| Class | v2 (2시즌) | v3 (3시즌) | 변화 |
|-------|-----------|-----------|------|
| Ball | 88.2% | 87.6% | -0.6pp |
| Strike | 81.9% | 82.2% | +0.3pp |
| Walk | 87.7% | 85.6% | -2.1pp |
| **Strikeout** | 14.3% | **17.3%** | **+3.0pp** ⬆️ |
| **FieldOut** | 7.3% | **10.7%** | **+3.4pp** ⬆️ |
| Single | 0% | 0% | - |
| Double | 0% | 0% | - |
| Triple | 0% | 0% | - |
| HomeRun | 0% | 0% | - |

---

## 🎯 핵심 발견

### 1. Sequence model이 데이터 양 효과를 5배 더 활용

같은 1.5배 데이터 확장:
- Model B (단일 pitch MLP): +0.1pp
- Model C (Sequence Transformer): +0.5pp

→ Sequence model의 우월성 추가 입증

### 2. 소수 클래스 정확도 큰 개선

- Strikeout: 14.3% → 17.3% (21% 상대 향상)
- FieldOut: 7.3% → 10.7% (47% 상대 향상)

→ 데이터 양 증가가 어느 정도 효과

### 3. Class imbalance는 데이터 양으로 해결 안 됨

- Single/Double/Triple/HR: 0% → 0% (여전히)
- 전체의 약 2%로 극히 적음
- Future Work: weighted loss, focal loss

---

## 📂 파일 변경 요약

### 새 체크포인트 (3시즌)

```
outputs/checkpoints/
├── model_b_full_v2_best.pt  ← Model B 3시즌 (4-class) [NEW]
├── model_b_full_v2_last.pt
├── model_c_full_v3_best.pt  ← Model C 3시즌 (10-class) [NEW, 추천]
└── model_c_full_v3_last.pt
```

### 기존 체크포인트 보존 (2시즌)

```
outputs/checkpoints/
├── model_b_full_v1_best.pt  ← Model B 2시즌
├── model_b_full_v1_last.pt
├── model_c_full_v2_best.pt  ← Model C 2시즌
└── model_c_full_v2_last.pt
```

### Sequence 데이터

```
data/processed/  ← 3시즌 데이터로 덮어씀
backup_v1_2season/  ← 2시즌 데이터 백업
```

### Evaluation 결과

```
outputs/
├── evaluation_b.npz          ← Model B 2시즌
├── evaluation_b_3season.npz  ← Model B 3시즌 [NEW]
├── evaluation_c.npz          ← Model C 2시즌
└── evaluation_c_3season.npz  ← Model C 3시즌 [NEW]
```

---

## 💻 사용 방법

### 기본 사용 (3시즌 모델, 추천)

```python
from src.inference import TransitionModelC

model = TransitionModelC(
    checkpoint_path="outputs/checkpoints/model_c_full_v3_best.pt"
)
result = model.predict(sequence)  # (400, 87) numpy
# result["pitch_result"]: 10-class 확률 분포
# result["hit_location"]: 9-class 확률 분포 (InPlay 시 유효)
```

### 2시즌 모델 사용 (비교용)

```python
model = TransitionModelC(
    checkpoint_path="outputs/checkpoints/model_c_full_v2_best.pt"
)
```

### Model B 사용 (4-class 필요 시)

```python
from src.inference import TransitionModelB

model = TransitionModelB(
    checkpoint_path="outputs/checkpoints/model_b_full_v2_best.pt"
)
result = model.predict(features)  # (77,) numpy
# result: 4-class 확률 분포 (Ball/Strike/Foul/InPlay)
```

### 데모 실행

```bash
uv run python scripts/11_inference_demo.py
```

---

## 🔍 데이터 정합성 검증 결과

3시즌 통합 전 수행한 검증:

| 항목 | 결과 | 평가 |
|------|------|------|
| 컬럼 수 | 118개 (모든 시즌 동일) | ✅ 완벽 |
| FT (Two-seam) | 0건 (모든 시즌) | ✅ 이미 재라벨링됨 |
| Pitch type taxonomy | 16-17/17 커버 | ✅ 안전 |
| release_spin_rate 차이 | 10.4 RPM (임계값 50의 1/5) | ✅ 정합성 충분 |
| Continuous features null | < 3% (모든 시즌) | ✅ 데이터 품질 일관 |

→ 별도 정규화 없이 단순 합산 학습 안전

### 검증 도구

```bash
uv run python scripts/12_statcast_year_comparison.py
```

---

## 🔧 코드 변경 사항

### src/data/preprocess.py
- `split_by_season(df, train_years)` 파라미터화
- 마지막 시즌 자동 val/test split

### scripts/04_preprocess.py
- `--years` argparse 추가
- `load_seasons(years)` 함수로 동적 로딩

### src/data/features.py
- `sac_bunt_double_play` → FIELD_OUT 매핑 추가 (2022 신규 이벤트)
- NaN guard 추가 (build_vectors_batch)

### scripts/01_download_data.py
- 2022 시즌 날짜 추가

### scripts/08_train_model_b.py, 09_train_model_c.py
- run_name 업데이트 (v2 → v3)

---

## ⚠️ 주의사항

### MDP/DQN 작업 영향

1. **Sequence 데이터 변경**:
   - `data/processed/` 가 3시즌 기준으로 덮어써짐
   - 기존 2시즌 학습 결과와 비교 시 `backup_v1_2season/` 사용

2. **Class imbalance 미해결**:
   - Single/Double/Triple/HR 여전히 0%
   - MDP/DQN 학습 시 안타류 보상 정밀 예측 어려움
   - Future work: weighted loss 도입

3. **Train/Val/Test split 변경**:
   - v1 (2시즌): Train 2023 / Val 2024 1-6월 / Test 2024 7월+
   - v2/v3 (3시즌): Train 2022+2023 / Val 2024 1-6월 / Test 2024 7월+
   - Val/Test는 동일, Train만 1년 추가

### 권장 작업

MDP/DQN 팀이 v3 모델 사용 시:
1. Inference wrapper 경로만 v3로 변경
2. 기존 학습 코드 변경 불필요
3. 성능 비교 위해 v2 (2시즌)으로도 한 번 실행 권장

---

## 📋 비교 작업 (선택)

기존 v2 (2시즌)과 새 v3 (3시즌)의 효과를 비교하려면:

```python
# 두 모델 모두 로드
model_v2 = TransitionModelC(checkpoint_path="outputs/checkpoints/model_c_full_v2_best.pt")
model_v3 = TransitionModelC(checkpoint_path="outputs/checkpoints/model_c_full_v3_best.pt")

# 같은 입력에 대한 예측 비교
pred_v2 = model_v2.predict(sequence)
pred_v3 = model_v3.predict(sequence)

print(f"v2 (2시즌): {pred_v2['pitch_result']}")
print(f"v3 (3시즌): {pred_v3['pitch_result']}")
```

---

## 🔗 참고 링크

- GitHub: https://github.com/Pitcheezy/transition-models
- 최신 commit: 85ea650
- Inference 가이드: [INFERENCE_GUIDE.md](INFERENCE_GUIDE.md)
- Phase 8 변경 이력: [../CLAUDE.md](../CLAUDE.md)

---

## ❓ 질문 / 이슈

- 카톡 또는 GitHub Issues
- 데이터 정합성 관련: `scripts/12_statcast_year_comparison.py` 실행 결과 공유
- 학습 재실행 필요: `scripts/08_train_model_b.py`, `scripts/09_train_model_c.py`

---

*작성: 조현준, 2026-05-14*
