# handoff_v1.parquet 분석 보고서

> 분석일: 2026-05-22  
> 팀원 데이터셋: [송동선] `pitcheezy-data` → `data/outputs/handoff_v1.parquet`  
> 분석 기준: `handoff_v1_schema.json` (27KB, 팀원 빌드 완료 결과 기반)

---

## 빌드 상황

로컬에서 `assemble_v1.py` 직접 빌드 시도 → **실패**

필요한 의존성 파일이 로컬에 없음:
- `C:\Users\zpfh1\Projects\data\data\clean\statcast_{year}_clean.parquet` (2022-2025)
- `C:\Users\zpfh1\Projects\clustering\outputs\pitch_embeddings.parquet`
- `C:\Users\zpfh1\Projects\clustering\outputs\count_clusters_v1.parquet`
- `C:\Users\zpfh1\Projects\clustering\outputs\arsenal_features_v1.parquet`

대안: `handoff_v1_schema.json`에 실제 빌드 통계(`row_counts`)가 기록되어 있으므로
**스키마 기반으로 완전한 호환성 분석 수행**. parquet 수령 후 `scripts/12_analyze_handoff_v1.py --parquet <경로>` 실행 시 overlap 통계 자동 추가됨.

---

## 1. 팀원 데이터셋 기본 정보

| 항목 | 값 |
|------|-----|
| 버전 | v1 |
| 행 수 | **2,983,621** |
| 컬럼 수 | **99** |
| 시즌 | **2022-2025 (4시즌)** |
| join keys | `game_pk`, `at_bat_number`, `pitch_number` |

**Row counts 상세 (스키마 기록)**

| 항목 | 수 | 비율 |
|------|----|------|
| statcast_input | 2,983,621 | 100.000% |
| after_embed_join | 2,983,621 | 100.000% |
| final | 2,983,621 | 100.000% |
| arsenal_fallback_rows | 45,521 | 1.526% |
| count_cluster_unmapped | 0 | 0.000% |
| embed_miss (UMAP NaN) | 2,171 | 0.073% |

**컬럼 그룹별 수**

| 그룹 | 컬럼 수 | 설명 |
|------|---------|------|
| Statcast 원본 | 40 | keys + 물리량 + 상황 + 결과 |
| UMAP 임베딩 | 7 | umap_5d_0..4 + umap_2d_x/y |
| 카운트 클러스터 | 1 | count_cluster_id |
| Arsenal func | 32 | arsenal_func_00..31 |
| Arsenal moment | 20 | arsenal_moment_00..19 |
| 메타 | 2 | arsenal_fallback, batter_cluster_ready |
| **합계** | **99** | |

---

## 2. 새 Features 자세한 분석

### 2-1. UMAP 임베딩 (7컬럼)

| 컬럼 | 차원 | 용도 |
|------|------|------|
| `umap_5d_0..4` | 5 | **모델 입력용** — 전체 구종 특성 공간의 비선형 압축 |
| `umap_2d_x`, `umap_2d_y` | 2 | 시각화 전용 (모델 입력 부적합) |

- 소스: `clustering/outputs/pitch_embeddings.parquet`
- `embed_miss`: **2,171건 (0.073%)** → NaN 처리 전략 필요 (drop 권장, 소수)
- 의미: 구종 물리량(속도, 회전, 변화량) 공간을 전체 MLB pitch에 대해 학습한 UMAP. 같은 구종이라도 투수마다 다른 클러스터에 위치할 수 있음 → 구종 유사성을 dense하게 표현.

### 2-2. 카운트 클러스터 (1컬럼)

| 클래스 | 의미 | 볼카운트 |
|--------|------|----------|
| 0 | pitcher-favored | 3-1, 3-2 |
| 1 | 0strikes | 0-0, 1-0, 2-0, 0-1, 1-1, 2-1 |
| 2 | hitter-favored | 0-2, 1-2, 2-2 |
| 3 | 3-0 take | 3-0 |

- Ward linkage 기반 4-way 클러스터
- `count_cluster_unmapped` = 0 → 완전 매핑
- 의미: 기존 balls/strikes OHE(7d)를 4개 클래스로 압축하면서 의미적 구분 유지.

### 2-3. 투수 레퍼토리 벡터 (52컬럼)

| 컬럼군 | 차원 | 의미 |
|--------|------|------|
| `arsenal_func_00..31` | 32 | 투수 구종 물리량 function-fit 임베딩 |
| `arsenal_moment_00..19` | 20 | 투수 구종 분포 moment 임베딩 |

- 소스: `clustering/outputs/arsenal_features_v1.parquet`
- `arsenal_fallback`: **45,521건 (1.53%)** — <250 pitches 투수는 fleet-mean 대체
- 의미: **개별 투구에 "해당 투수의 전체 레퍼토리" 정보를 주입**. 같은 직구라도 주무기가 다른 투수면 다른 벡터가 붙음.

---

## 3. 본인 데이터와의 호환성

### 3-1. Feature 컬럼 가용성

| 모델 | 필요 원본 컬럼 수 | v1 누락 | 재추출 가능 |
|------|-----------------|---------|------------|
| Model B (77-dim) | 26개 | **0개** | **100%** |
| Model C (87-dim) | 28개 | **0개** | **100%** |

→ v1에서 기존 전처리(`preprocess.py`)를 그대로 실행하면 77/87-dim 벡터 완전 재생성 가능.

### 3-2. 시즌 비교

| 데이터 | 시즌 | 행 수 |
|--------|------|-------|
| handoff_v1 | 2022–**2025** | 2,983,621 |
| 본인 raw statcast | 2022–2024 | ~2,309,616 |
| 본인 processed (train+val+test) | 2022–2024 | ~1,488,976 |

- v1이 **2025 시즌 추가** → 비교 실험 시 2022-2024로 필터링 권장
- 행 수 차이: v1은 clean Statcast 기반(4시즌), 본인은 raw에서 NaN drop 적용(3시즌)

### 3-3. Pitch 일치 여부

- JOIN key (`game_pk, at_bat_number, pitch_number`) 모두 v1에 존재
- 동일한 Statcast 소스 + 동일한 CLAUDE.md 계약(동일 NaN drop, pitch_type 필터) → 2022-2024 pitch rows는 실질적으로 동일 집합 예상
- **정확한 overlap은 parquet 수령 후 `scripts/12_analyze_handoff_v1.py` 실행으로 확인**

### 3-4. 추가 가능 차원

```
기존 Model B: 77-dim
v1 추가:     +58-dim  (UMAP 5 + count_cluster 1 + arsenal 52)
→ 새 Model B: 135-dim

기존 Model C: 87-dim
v1 추가:     +58-dim
→ 새 Model C: 145-dim
```

---

## 4. 권장 시나리오

### 시나리오 평가 요약

| | A: feature 추가 재학습 | **B: 병행 비교 (권장)** | C: v1 미사용 |
|--|--|--|--|
| 입력 dim | 77→135 / 87→145 | 기존 + v1 별도 트랙 | 기존 유지 |
| 재학습 | 전체 (Model C ~10h) | v1 트랙만 | 없음 |
| 발표 narrative | "통합 데이터 강화" | "기존 vs 통합 비교" | "5모델 비교" |
| 추가 작업 | 중~대 | 중 | 없음 |

### 권장: **시나리오 B**

**근거**:
1. 호환성 100%로 v1-enhanced 실험 부담이 적음
2. 기존 Phase 9(5모델 비교) 결과를 baseline으로 유지하면서 비교 실험 추가 가능
3. "통합 데이터셋이 전이확률 추정에 얼마나 도움되는가"를 정량화할 수 있음
4. batter_cluster가 없는 v1 제약을 고려하면, 지금 당장 A로 전환하기보다 B로 효과를 먼저 검증하는 것이 합리적

**실행 방법**:
1. Phase 9(5모델 비교)를 기존 2022-2024 데이터로 완료
2. v1 parquet 수령 → 2022-2024 필터링 → overlap JOIN 확인
3. preprocess.py 수정: v1 extra features 추가 (58d) → 재학습 (Model B ~11분)
4. 결과 비교: 기존 60.9% vs v1-enhanced ?%

---

## 5. 발표 Timeline 영향

| 작업 | 예상 소요 시간 |
|------|--------------|
| parquet 수령 (팀원 요청) | 0.5일 |
| overlap 확인 + 전처리 수정 | 0.5일 |
| Model B v3 재학습 (135-dim) | ~11분 |
| Model C v4 재학습 (145-dim) | ~10시간 (RTX 4070) |
| 결과 분석 + 비교 보고서 | 0.5일 |
| **v1-enhanced 전체 트랙** | **~2일** |

- Phase 9(5모델 비교)는 v1 작업과 **병행 진행** 가능
- 5/19 발표는 이미 경과 → timeline 압박 없음, 품질 위주로 진행 가능

---

## 6. 주의사항

### 6-1. batter_cluster 미포함
- `batter_cluster_ready = False` (전체 v1)
- 타자 특성(vs LHP/RHP 등) 반영 불가
- v2 출시(handedness_leak 수정) 후 재평가 필요
- 현재 v1 실험은 **투수 중심 feature**로만 평가됨을 명시해야 함

### 6-2. embed_miss (UMAP NaN)
- 2,171건(0.07%)에 `umap_5d_*` = NaN
- 권장 처리: `dropna(subset=umap_5d)` (소수라 row 제거해도 통계에 영향 미미)
- 대안: NaN을 UMAP centroid(0벡터)로 imputation

### 6-3. arsenal_fallback
- 45,521건(1.53%)이 fleet-mean 대체
- fallback 행만 따로 분석해 fallback 여부가 성능에 미치는 영향 확인 권장

### 6-4. StandardScaler 재fit 필요
- 본인 `data/processed/scaler.pkl`은 본인 raw(2022-2024) 기준으로 fit
- v1 사용 시 v1의 training set(2022-2023)으로 **scaler 재fit 필수**
- 특히 continuous 15개 features의 스케일이 clean vs raw에 따라 미세하게 다를 수 있음

### 6-5. 시즌 정합성
- v1은 2022-2025, 본인은 2022-2024
- 비교 실험 시 v1을 `game_year <= 2024`로 필터링
- 또는 2025 포함 실험으로 시즌 범위를 확장하는 방향도 가능 (별도 논의 필요)

---

## 다음 단계

분석 결과 후 선택:

- **시나리오 B 선택 시**:
  1. 팀원에게 `handoff_v1.parquet` 직접 수령 요청
  2. `scripts/12_analyze_handoff_v1.py --parquet <경로>` 실행 → overlap 확인
  3. `notebooks/06_handoff_v1_compat.ipynb` 섹션 4 실행 → 실제 통계 확인
  4. Phase 9 병행 진행
  5. v1-enhanced 재학습 트랙 시작

- **시나리오 C 선택 시**:
  - Phase 9 즉시 진행
  - v1 → Future Work로 기록

---

*분석 스크립트: `scripts/12_analyze_handoff_v1.py`*  
*분석 노트북: `notebooks/06_handoff_v1_compat.ipynb`*  
*JSON 결과: `outputs/reports/handoff_v1_analysis.json`*
