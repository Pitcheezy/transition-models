# rl-agent 팀원 가이드 — 다운로드 및 통합 방법

**작성일**: 2026-05-25  
**레포**: https://github.com/Pitcheezy/transition-models  
**최신 커밋**: `0e82820`

---

## 1단계: 레포 클론 (처음이라면)

```bash
git clone https://github.com/Pitcheezy/transition-models.git
cd transition-models
```

이미 클론한 경우:

```bash
cd transition-models
git pull origin main
```

> **Git LFS 필요**: `.pt` 체크포인트 파일은 Git LFS로 관리됩니다.  
> LFS가 없으면 먼저 설치하세요.
> ```bash
> # macOS
> brew install git-lfs
> git lfs install
>
> # Ubuntu/Debian
> sudo apt install git-lfs
> git lfs install
>
> # Windows (winget)
> winget install GitHub.GitLFS
> git lfs install
> ```

---

## 2단계: 필요한 파일 목록

`git pull` 후 아래 4개 파일이 준비됩니다.

| 파일 | 경로 | 크기 | 설명 |
|------|------|------|------|
| **체크포인트** | `outputs/checkpoints/model_b3_focal_135dim_10cls_best.pt` | ~0.4 MB | 135-dim 10-class MLP (focal loss, epoch 25) |
| **Arsenal JSON** | `outputs/arsenal_by_pitcher_cluster.json` | ~41 KB | pitcher 2,007명 → 4클러스터 매핑 + scaled arsenal 벡터 |
| **평가 결과** | `outputs/evaluation_mlp_135dim_10cls_focal.npz` | ~3 MB | 테스트셋 Top-1 67.6%, per-class accuracy |
| **통합 가이드** | `docs/handoff_to_rl_agent.md` | ~8 KB | 135-dim 벡터 구성법, mdp_vi.py 통합 코드 골격 |

### 파일 존재 확인 (클론 후)

```bash
ls -lh outputs/checkpoints/model_b3_focal_135dim_10cls_best.pt
ls -lh outputs/arsenal_by_pitcher_cluster.json
ls -lh outputs/evaluation_mlp_135dim_10cls_focal.npz
ls -lh docs/handoff_to_rl_agent.md
```

---

## 3단계: GitHub에서 직접 다운로드 (클론 없이)

클론 없이 파일만 받으려면 아래 GitHub 직접 다운로드 링크를 사용하세요.

### 체크포인트 (LFS)

```
https://github.com/Pitcheezy/transition-models/raw/main/outputs/checkpoints/model_b3_focal_135dim_10cls_best.pt
```

```bash
# wget
wget "https://github.com/Pitcheezy/transition-models/raw/main/outputs/checkpoints/model_b3_focal_135dim_10cls_best.pt" \
     -O model_b3_focal_135dim_10cls_best.pt

# curl
curl -L "https://github.com/Pitcheezy/transition-models/raw/main/outputs/checkpoints/model_b3_focal_135dim_10cls_best.pt" \
     -o model_b3_focal_135dim_10cls_best.pt
```

### Arsenal JSON

```
https://github.com/Pitcheezy/transition-models/raw/main/outputs/arsenal_by_pitcher_cluster.json
```

```bash
wget "https://github.com/Pitcheezy/transition-models/raw/main/outputs/arsenal_by_pitcher_cluster.json" \
     -O arsenal_by_pitcher_cluster.json
```

### 평가 결과 NPZ

```
https://github.com/Pitcheezy/transition-models/raw/main/outputs/evaluation_mlp_135dim_10cls_focal.npz
```

```bash
wget "https://github.com/Pitcheezy/transition-models/raw/main/outputs/evaluation_mlp_135dim_10cls_focal.npz" \
     -O evaluation_mlp_135dim_10cls_focal.npz
```

### 통합 가이드 (마크다운)

```
https://github.com/Pitcheezy/transition-models/blob/main/docs/handoff_to_rl_agent.md
```

---

## 4단계: 모델 스펙 요약

| 항목 | 값 |
|------|-----|
| 아키텍처 | MLP: 135 → 128 → 128 → 10 (dropout=0.2) |
| 학습 손실 | Focal Loss (γ=2.0) |
| Best epoch | 25 / 30 |
| Val focal loss | 0.4505 |
| **Top-1** | **67.6%** |
| Ball | 88.4% |
| Strike | 83.7% |
| Walk | 85.9% |
| Strikeout | 19.5% |
| FieldOut | 7.3% |
| HitByPitch | 2.9% |
| Single / Double / Triple / HR | **0%** (아래 주의사항 참조) |

### 출력 클래스 순서 (10-class)

```python
["Ball", "Strike", "Single", "Double", "Triple",
 "HomeRun", "FieldOut", "Strikeout", "Walk", "HitByPitch"]
```

---

## 5단계: rl-agent에서 모델 로드

```python
import sys
sys.path.insert(0, "path/to/transition-models")

from src.inference import TransitionModelMLP10

model = TransitionModelMLP10(
    checkpoint="path/to/model_b3_focal_135dim_10cls_best.pt"
)

# 예측 (135-dim 입력)
import numpy as np
x = np.zeros(135, dtype=np.float32)   # 아래 6단계에서 채우는 법 설명
probs = model.predict(x)              # (10,) softmax 확률
```

---

## 6단계: 135-dim 입력 벡터 구성법

```
인덱스       내용                            처리
[0:77]      Model B 77-dim features          기존 build_model_b_feature() 결과
[77:82]     UMAP 5d                          0.0 으로 채울 것 (inference time 미보유)
[82:83]     count_cluster_id (scaled)        arsenal_by_pitcher_cluster.json에서
[83:115]    arsenal_func_00..31 (scaled)     arsenal_by_pitcher_cluster.json에서
[115:135]   arsenal_moment_00..19 (scaled)   arsenal_by_pitcher_cluster.json에서
```

```python
import json
import numpy as np

# Arsenal JSON 로드 (1회만)
with open("arsenal_by_pitcher_cluster.json", encoding="utf-8") as f:
    arsenal = json.load(f)

def build_135dim_feature(base_77, arsenal_data, pitcher_cluster=None, pitcher_id=None):
    """base_77: build_model_b_feature() 결과 (77-dim numpy array)
    pitcher_cluster: rl-agent state의 pitcher_cluster (0-3). 있으면 우선 사용.
    pitcher_id: MLB MLBAM pitcher ID (int). pitcher_cluster 없을 때 사용.
    """
    vec = np.zeros(135, dtype=np.float32)
    vec[:77] = base_77
    # [77:82] = 0.0 (UMAP 미보유 → 학습 데이터 평균값으로 대체)

    if pitcher_cluster is not None:
        cluster_id = str(pitcher_cluster)                                        # 0-3 직접 사용
    elif pitcher_id is not None:
        cluster_id = arsenal_data["pitcher_to_cluster"].get(str(pitcher_id), "0")  # MLBAM ID lookup
    else:
        cluster_id = "0"

    data = arsenal_data["clusters"][cluster_id]
    vec[82]      = data["count_cluster_id_scaled"]
    vec[83:115]  = data["arsenal_func_scaled"]       # 32-dim
    vec[115:135] = data["arsenal_moment_scaled"]     # 20-dim
    return vec

# 사용 예시 (rl-agent에서 pitcher_cluster가 있는 경우)
# feat = build_135dim_feature(base_77, arsenal, pitcher_cluster=state.pitcher_cluster)
```

---

## 7단계: MDP-VI 통합 (tm_import.py 수정)

`rl-agent/src/utils/tm_import.py`에서 `_CKPT_C` 경로를 교체합니다.

```python
# 기존
_CKPT_C = "model_c_full_v3_best.pt"

# 교체
_CKPT_C = "model_b3_focal_135dim_10cls_best.pt"
```

> 단, `_precompute_model_c()`는 Transformer(87-dim 시퀀스) 전용이므로  
> 135-dim MLP를 위한 `_precompute_model_mlp10()` 함수를 별도 추가해야 합니다.  
> 구체적인 코드 골격은 `docs/handoff_to_rl_agent.md` 를 참조하세요.

---

## 주의사항

### Single / Double / Triple / HomeRun = 0%

Focal Loss (γ=2.0)로 Walk·Strikeout·FieldOut은 개선됐지만  
단타~홈런은 훈련 데이터에서 극희소 (Single 3.6%, HR 0.78%)라 여전히 0%.

**현재 권장 대응**: 기존 BIP 테이블 (`_expand_transitions_4class()`)과 병행  
→ FieldOut / Walk / Strikeout / HitByPitch는 MLP 직접 예측값 사용  
→ Single / Double / Triple / HR는 InPlay 확률 × BIP 테이블 비율로 추정

**장기 개선**: γ=3.0 + weighted sampler (transition-models 팀에 요청 가능)

### pitcher_to_cluster 미등록 pitcher

`arsenal["pitcher_to_cluster"].get(str(id), "0")` — 없으면 cluster 0 (가장 큰 클러스터, 1,484명 / 1,708,807투구)으로 fallback.

### UMAP 0-fill 영향

UMAP [77:82] = 0.0은 StandardScaler 기준 평균값이므로  
"평균적인 투구 메카닉"으로 처리됩니다. Top-1 정확도에 미치는 영향은 미미합니다.

---

## 문의

문제가 있으면 transition-models 담당자에게 GitHub Issue 또는 직접 연락하세요.  
세부 기술 문서: [`docs/handoff_to_rl_agent.md`](handoff_to_rl_agent.md)
