# STATUS — Pitcheezy / transition-models

> 2026-10-09 H-12: 좌표 변환의 “보정 미적용” 고정 설명을 실제 적용값과 일치하도록 수정했다. 좌표·성능 수치와 기존 산출물은 그대로다. [정정 보고](docs/COORDINATE_EVIDENCE_CORRECTION_20261009.md).

> **2026-10-08 최신 후속 (`517280f`)**: 실제 사람 응답 **1개·26장**을 수신·검사·보존했다. 아래 응답0은 수신 이전 기록이다. [수신 보고](docs/CV_FIRST_HUMAN_REVIEW_20261008.md). 미완성 초안 저장·복원과 팩 단독 실행 도우미를 추가하고 [새 사용 안내](docs/CV_HUMAN_REVIEW_START_HERE.md)를 정리했다. Windows 합성 화면 검증, reviewer31파일의 비공개 ZIP 압축 해제·단독 검사 완료. 구현 `517280f` 원격 CI37788681108 성공: Linux/macOS 각각 2028passed/8skipped/2deselected. 실제 Mac 사용자 검토와 구분한다. 모델 재학습·독립 정확도 측정·실제 새 S 응답 연결·공개 배포는 이 변경에 포함되지 않는다. [검증 기록](docs/results/cv_independent_20261008/review_draft_launcher_v1.json).

> 2026-10-08 전달 준비 후속: [우리 운영 모델14파일 ZIP](docs/HANDOFF_OPERATIONAL_BUNDLE_V1.md) 생성·압축 해제 SHA 검증 완료(약5.14MB). 기존 전체 소스를 별도로 받아야 하며 새 환경 설치/맥 기동은 아직 미확인이다. ZIP은 로컬에만 있고 공개 배포하거나 팀원에게 전송하지 않았다.

> 2026-10-08 후속 변경: [투구별 발행 시간 진단](docs/CV_REPLAY_PITCH_DEADLINES_V1.md)과 [사람 점 자료 준비](docs/CV_REVIEW_POINT_DATA_V1.md)를 추가했다. 실제 새 사람 응답은0건이다. [운영 모델 경로 이관](docs/HANDOFF_OPERATIONAL_RELOCATION_V1.md)은 같은 Windows·기존 환경·예제1개에서 전체 결과가 같았다. 새 환경/팀원 서비스 통합 또는 성능 개선 검증은 아니다. 아래 10/7 조사 스냅샷과 구분한다.

> 2026-10-07 후속 변경: 아래 조사 스냅샷을 유지하면서 [S 응답 로컬 검사 도구](docs/SERVICE_GAME_V2_INTEGRATION.md)를 추가했다. 합성 자료에서 동작을 확인한 통합 준비이며, 실제 S 응답 수신·공개 화면 연결·라이브 검증은 아직 하지 않았다.

작성일: 2026-10-07. 두 프로토타입의 통합 판단을 위한 현황이며, 홍보 자료가 아니다.

조사 기준은 `Pitcheezy/transition-models`, `feature/intent-v0`, `050740e03a46eb8c704107da6d3225c0a12ee249`이다. 현재 웹·CV 작업이 있는 `transition-models-intent` 작업 폴더를 기준으로 했다. 같은 저장소의 다른 브랜치 `codex/fix-point-label-alignment@dad5522`와 합쳐지지 않은 부분은 따로 표시한다. 팀원 저장소는 수정하거나 재조사하지 않았다. 아래 팀원 모델 관련 사실은 **이 저장소에 전달·저장된 응답**에 한정된다.

`src`, `intent`, `scripts`, `web`, `tests`, `configs`, `notebooks`, 주요 지침·결과 문서를 확인했다. 원본 영상·전체 학습 데이터를 다시 수집하거나 모든 과거 실험을 재실행한 것은 아니다. 실행 확인과 저장된 평가 결과를 구분한다. 완성도 백분율은 산정하지 않는다.

## 1. 서비스 정의

목표는 야구 관전 중 **다음 공의 선택지와 실제 투구를 비교하고, 포수 미트 관측을 함께 보여주는 것**이다. 현재는 세 가지가 공존한다. ① 모델 비교·검증 도구, ② 실제 운영 모델을 호출하는 수동 입력 로컬 앱, ③ 저장 응답과 설명용 시나리오를 보여주는 공개 웹이다. 이 셋이 하나의 실시간 자동 서비스로 연결된 상태는 아니다.

| 사용자가 보는 기능 | 답하는 질문 | 현재 범위 |
|---|---|---|
| 홈의 야구 영상·기능 소개 | 무엇을 분석하는 서비스인가? | 4투구 약 24초 하이라이트와 설명 |
| 실제 첫 타석 재생 | 이 상황의 추천 후보와 실제 공은 무엇이었나? | 경기 849843 첫 타석 3구의 저장 추천·공식 투구 영상·결과 |
| 응답 파일 가져오기 | 전달받은 모델 응답을 같은 화면에 붙일 수 있나? | 브라우저 안에서 JSON 검증·표시; 서버 업로드 아님 |
| 미트 관측 탐색 | 포수가 어느 가로 위치에 미트를 두었나? | 저장된 39구 중 27좌표·12기권; 결과 공개 후 표시 |
| 검증 리포트 | 이 미트 판독을 어느 정도 믿을 수 있나? | 평가 2경기·86프레임의 고정 결과와 한계 |
| 수동 입력 모델 데모 | 입력한 카운트·주자·투수 조건에서 어떤 구종의 예측 비용이 낮나? | 로컬 실제 추론; 구종 추천만 지원 |
| 분석 스튜디오 | 투구 전·투수·타자·감독 분석을 최종적으로 어떻게 볼 것인가? | 4개 설명용 시나리오. 사건확률·수행지수·교체 판단은 모델 미연결 |
| 주석·검토 도구 | 영상의 시점·점수판·선수·미트를 어떻게 검토하는가? | 개발자/검토자용 로컬 도구 |

현재 실제 투수 의도, 제구 책임, 타자의 기여, 감독 교체 실책을 자동 판정하지 않는다. MLB부터 개발하며 KBO 운영 구현은 없다.

## 2. 전체 구조

| 단계 | 실제 흐름 | 주요 파일·디렉터리 |
|---|---|---|
| 기록 수집 | pybaseball Statcast → 연도별 Parquet | `scripts/01_download_data.py`, `data/raw/` |
| 연구용 전처리 | 실제 투구 물리량·구종·위치 → point/sequence 입력 | `src/data/preprocess.py`, `src/data/dataset.py`, `scripts/04_preprocess.py` |
| 정렬 복구 | 투구 키로 입력·정답 결합, 중복·분할 중복 검사 | `src/data/point_data.py`, `scripts/48_prepare_aligned_points.py` |
| 운영용 전처리 | 2022 프로필 + 투구 전 상황 + 후보 구종 → 77/135차원 | `src/data/operational.py`, `scripts/51_prepare_operational.py` |
| 학습·확률 평가 | empirical/LR/LGB/MLP → 선택 → 별도 기간 확률 보정 | `src/training/point_baselines.py`, `src/inference/operational.py`, `scripts/53_evaluate_operational.py` |
| 정책 평가 | 결과별 기대 실점 비용 + 행동 지원 조건 → 구종 후보 비교 | `src/evaluation/run_value.py`, `src/evaluation/policy_value.py`, `scripts/52_train_policy_nuisance.py`, `scripts/54_evaluate_policy.py` |
| 로컬 실제 서빙 | 상태 JSON → OperationalRecommender → localhost HTTP | `src/inference/prepitch_contract.py`, `src/inference/recommendation.py`, `src/web/manual_server.py`, `scripts/59_serve_manual_demo.py` |
| 로컬 모델 화면 | 수동 상태 입력 → `/api/predict` → 확률·비용·추천 | `src/web/static/index.html`, `app.js`, `style.css` |
| 방송 인식 연구 | 영상/피드 식별 → 수동 시점 → 고정 레이아웃 OCR | `scripts/58_*`–`74_*`, `src/data/`, `src/vision/` |
| 기존 미트 판독 | 외부 AI 판독 기록 + 투구 시점 + 카메라 변환 → JSONL | `intent/workflows/`, `intent/condensed.py`, `intent/run.py`, `intent/schema.py` |
| 새 CV 실험 | 영상 PTS·프레임 결속 → 관측기 → 기권/후보·지연 기록 | `intent/clip_frames.py`, `intent/observation_session.py`, `intent/local_glove_observer.py` 및 관련 worker/report 모듈 |
| 공개 화면 데이터 | 기존 JSONL/평가 결과 → 정적 JS; 팀원 저장 응답 → 수신 계약 | `scripts/export_pitch_studio.py`, `web/pitch-studio/data.js`, `receiver-demo-849843.js`, `receiver-contract.js` |
| 공개 화면·배포 | HTML/CSS/JS/MP4/JPEG → Sites → pitcheezy.com | `web/pitch-studio/`, `docs/INTENT_DEMO_SITE.md` |

현재 공개 사이트는 로컬 추론 API나 새 CV 관측 루프를 호출하지 않는다. 팀원 모델 가중치도 공개 사이트에 포함되어 있지 않다.

## 3. 계층별 상태

상태의 “동작 확인됨”은 아래에 적은 경로·입력에서 확인했다는 뜻이며, 일반 운영 완성을 뜻하지 않는다. 명령은 해당 브랜치의 저장소 루트에서 실행한다. `uv run --frozen`은 준비된 고정 환경을 사용하는 예이며, 별도 데이터가 필요한 명령에는 조건을 적었다.

### 데이터 수집과 전처리 — 일부 동작

- Statcast 수집, 시간 분할, 정렬된 point 데이터, 운영 특징 생성기가 구현되어 있다. 이번에는 네트워크 재수집·전체 재전처리를 실행하지 않았다.
- 저장된 운영 감사에서는 **1,426,309행**을 추론용 특징 생성기로 재구축해 저장 벡터와 일치시켰다. 근거: `docs/results/operational_20260921/feature_identity_audit.json`.
- 747139 방송은 **322구 수동 검토, 297구 시점 확정, 25구 사용 불가**다. 자동 영상 동기화가 아니다. 독립 44구 시점 검토 응답은 대기한다.
- ID·클래스 순서·미래 정보 차단 검사는 강하다. 반면 수집/주석/모델 준비가 여러 스크립트로 분산되고, 최신 작업 폴더에는 실행에 필요한 운영 데이터가 없다.

재현 진입점은 `scripts/01_download_data.py --help`, `scripts/51_prepare_operational.py --help`다. 전체 운영 실험 명령은 아래와 같다. **이번 미실행**이며 원본 2022–2024 Parquet와 새 출력 경로가 필요하다.

```text
uv run --frozen python scripts/55_run_operational_validation.py --data-dir data/operational_NEW --run-dir outputs/operational_NEW --device auto --threads 4
```

### 모델 — 종류별 상태

| 모델/방법 | 예측·계산 내용 | 상태와 솔직한 평가 |
|---|---|---|
| 운영 empirical | 상태·구종·좌우별 계층적 빈도, smoothing 50 | 동작 확인됨. 2023 학습 자료로 만든 유효 기준선 |
| 운영 LR 77d | 다항 로지스틱 회귀, 결과 10종 | 일부 동작. 학습·평가 코드와 저장 결과 확인; 이번 재추론 안 함 |
| 운영 LightGBM 77/135d | 트리 기반 결과 10종 | 일부 동작. 저장 평가 확인; 이번 모델 재실행 안 함 |
| 운영 MLP 77/135d | 입력→128→128→10, ReLU/dropout; 3 seed 확률 앙상블 | 선택된 135d 동작 확인됨. 외부 기존 산출물을 지정해 실제 HTTP 추론 성공. 77d는 저장 평가 확인 |
| 한 단계 구종 정책 | 결과 확률 × 기대 실점 비용으로 후보 비교 | 동작 확인됨. 구종 선택만 가능; 실점 감소는 입증 못 함 |
| 역사적 4종 MLP | Ball/Strike/Foul/InPlay 분류 | 일부 동작. 연구 코드·가중치 존재; 현재 운영 선택 모델 아님 |
| 역사적 10종 point/Arsenal135/matchup151 | 실제 투구 특징 또는 legacy 프로필을 이용한 분류 | 일부 동작. 관측 분류 연구; 최신 운영 특징과 호환 안 됨. 151 경로는 별도 입력/정답 파일 사용 등 정합성 부채가 남음 |
| RNN/LSTM | 400×87 투구 이력 → 결과 10종 | 일부 동작. 학습 결과 보존, 이번 재실행 안 함 |
| Transformer | 12층·256차원·8 head → 결과10 + 타구위치9 + 연속값5 | 일부 동작. 연속값5의 학습 손실이 0이므로 해당 head는 미학습 |
| RNN/Transformer hybrid | sequence + legacy static58 | 일부 동작. 연구 결과 보존; 상류 UMAP/Arsenal 출처 제약 |
| Model A SmartPitch wrapper | 원래 계획된 외부 모델 연결 | 미완성. 실제 구현은 majority/empirical 기준선 함수이며 독립 wrapper가 아님 |
| M3 미트 판독 | 외부 AI 두 판독자 + 합의·기권 + 좌표 변환 | 일부 동작. 저장 결과 생성·평가 가능; 자체 가중치만으로 새 영상 자동 처리하는 모델이 아님 |
| SNY 점수판/이름 OCR | 고정 방송 레이아웃의 템플릿/Windows OCR | 일부 동작. 한 레이아웃 개발 결과; 일반 방송 자동 인식 아님 |
| 범용 로컬 glove 탐지기 | SSDLite/Faster R-CNN의 COCO glove 후보 | 일부 동작. 실제 실행되나 판독 품질 부족으로 채택 안 함 |
| TinyCNN 미트 점 회귀 | 이미지 → 중심점, 14,369 parameters | 일부 동작. 6회 학습 완료했으나 채택 기준 0/6 통과 |
| 투수/타자 책임·감독 교체 모델 | 최종 서비스가 지향하는 판단 | 없음. 공개 UI의 관련 수치는 설명용 |

`_INVALID_GEMINI_DUMMY/`의 193d 모델과 하드코딩 성능은 **무효 자료**다. 서비스나 비교표에 사용하면 안 된다.

**운영 확률 모델의 검증**

2022 정규시즌으로 프로필을 만들고, 2023년 717,401구로 학습했다. 2024년 1–5월 250,970구로 선택하고 6월 115,884구로 온도 보정했다. 최종 평가는 7–9월 **342,054구 / 1,167경기**다. MLP seed는 42/43/44다. 아래는 이번 재학습 수치가 아니라 코드와 대조한 커밋된 평가 결과다.

| 모델 | Top-1 | CE↓ | Brier↓ | ECE↓ |
|---|---:|---:|---:|---:|
| empirical | 45.23% | 1.287400 | 0.659526 | 0.008113 |
| LR77 | 45.31% | 1.278760 | 0.658599 | 0.010977 |
| LightGBM77 | 45.43% | 1.276610 | 0.657190 | 0.006835 |
| LightGBM135 | 45.40% | 1.276912 | 0.657143 | 0.006680 |
| MLP77 ensemble | 45.51% | 1.274636 | 0.657025 | 0.008441 |
| MLP135 ensemble | 45.51% | 1.274251 | 0.656815 | 0.007569 |

CE는 실제 결과에 부여한 확률을 평가하는 손실이다. Brier는 10종 확률의 제곱오차 합, ECE는 15개 등간격 bin의 top-label 보정 오차다. MLP135−empirical CE 차이 **−0.013149**, 경기 bootstrap 95% 구간 **[−0.013744, −0.012551]**로 이 평가에서는 확률 점수가 개선됐다. 135d가 77d보다 일반적으로 우수하다는 주장은 seed 변동까지 고려하면 성립하지 않는다.

정책 평가는 **195,066구 / 1,165경기**, 최종 test의 57.03%만 지원한다. 1–8회, 과거 구종 표본 ≥30, propensity ≥0.02, 후보 ≥2 조건이다. 학습 정책과 empirical 정책의 비용 차이는 **−0.0862 runs/100결정**, 95% 구간 **[−0.4046, +0.2304]**다. **실점 개선은 입증되지 않았다.** 완전한 MDP 최적 정책이나 승리확률 개선으로 해석할 수 없다.

과거 warm CPU 측정은 9구종 특징 생성+모델 추론 중앙 **73.4ms**, p95 **83.1ms**, 30회·3 threads다. 로딩·HTTP·propensity 필터 등은 제외됐다. 이번 단일 API 응답의 `elapsed_ms=390.39`와 같은 측정이 아니다. 근거: `docs/OPERATIONAL_VALIDATION_2026-09-21.md`, 그 아래 probability/policy JSON.

**과거 모델 결과의 사용 범위**

- 입력/정답 정렬을 복구한 관측 MLP seed42는 동일 353,667구에서 77d 정확도 67.67%/CE 0.8517, 135d 67.60%/0.8546이다. 실제 투구 정보를 포함하므로 투구 전 성능이 아니다.
- RNN 66.90%/CE 0.872766, Transformer 67.20%/0.868150; hybrid는 약 66.82–67.15%다. sequence 표본은 최대 22,127 windows로 point 전체와 다르다. 마지막 투구 결과를 가려도 현재 투구의 물리량·zone은 남는다.
- 과거 “77d 41% → 135d 67%, 맥락 효과”는 입력/정답 정렬 오류로 철회됐다. 구형 Model A 평가에는 test 정답에서 계산한 빈도가 사용됐다. 최신 운영 empirical과 구분한다.
- 구형 UMAP/Arsenal의 엄격한 학습 시점 출처는 미확정이다. 근거: `docs/ALIGNMENT_REPAIR_2026-09-21.md`, `src/data/dataset.py`, `src/training/train.py`, `scripts/10_evaluate_models.py`.

**영상 모델의 검증**

- M3: 평가 2경기 **86프레임**, AI 출력58/기권28, 사람 1명 표시84/기권2. 함께 표시한58장에서 점 차이 중앙 **2.53px**, p90 **6.51px**. 동일 변환의 2차원 좌표 차이 중앙 **0.092ft**, 가로 차이 중앙 **0.055ft**다. 사람 판독과의 일치도이며 물리 정확도·투수 의도 정확도가 아니다. `docs/INTENT_V0_M3_EVAL.md`.
- SNY 점수판 v2: 템플릿 타석 제외 자료에서 10필드 모두 평가 가능한281구 중 완전 정답75구. 개별 필드에는 아웃1건·초말15건 오류가 있다. 출력한 일부의 정확도만으로 전체 인식 성공률을 표현하면 안 된다. 이름 OCR도 개발 자료204역할에서 혼합된 버전 기록이며 독립 검증이 아니다.
- 범용 탐지기: 86장 중 SSDLite 후보0장, Faster R-CNN 전체16장/crop5장. 후보 중심과 사람 점의 조건부 거리 중앙151.93/64.61px. 후보 검출 수는 정확도가 아니다. TinyCNN은 84점·경기 분리 양방향×3 seeds에서 기준선 통과0/6이다.
- 최신 CV24는 같은14프레임의 추출 중앙 **2.185→0.848초**, 실제 관측14건 발행 중앙 **3.883초**, 최대4.047초, 준비18.563초다. **단일 후보5/복수1/없음8, 확정 미트0**이다. 개선된 것은 처리 경로이며 판독 정확도가 아니다. `docs/CV_EXACT_FRAME_SEEK_V1.md`.
- 기존 M3 사람 검토는 완료됐다. 별도의26장 추가 검토는 응답0으로 대기 중이며 새 표본26장이 아니다. 새 영상의 독립 평가도 미완료다.

저장 주석→JSONL 명령은 `uv run --frozen python -m intent.run --game 849843 --out outputs/intent_NEW.jsonl`이다. `--verify-frames`는 로컬 원본 프레임이 필요하다. 이 명령은 **새 영상 AI 판독 명령이 아니다**. 이번에는 CLI 도움말·저장 결과·정적 내보내기 대조만 확인했다.

### 서빙 — 일부 동작

로컬 실제 모델 API는 동작 확인됐다. 기본 실행은 다음과 같다. 해당 경로에 9절의 모델 번들이 있어야 한다.

```text
uv run --frozen python scripts/59_serve_manual_demo.py --data-dir data/operational_20260921_v2 --evaluation-dir outputs/operational_20260921/evaluation --nuisance-dir outputs/operational_20260921/policy_nuisance_v2 --runs-dir outputs/operational_20260921 --port 8770
```

이번에는 위 네 경로를 다른 **우리 작업 폴더** `C:/Users/zpfh1/Projects/transition-models/` 안의 기존 산출물로 지정했다. 서버 CLI 실제 기동과 health 200을 확인하고 종료했다. 별도 API 검사에서는 `/`, `/api/health`, `/api/example`, 유효한 `/api/predict`가 200이었다. 9개 후보·SL 추천을 받았고, 금지된 `plate_x`를 추가한 입력은 400으로 거부됐다.

stdlib HTTP 서버는 127.0.0.1 전용이다. JSON 16KB 제한, Host/Origin·필드 검사, 추론 잠금이 있다. 반면 공개 인증·사용자 DB·분산 처리·운영용 다중 인스턴스 구성은 없다. 인터넷 공개 백엔드로 바로 쓰는 수준은 아니다.

공개 웹은 **사전 계산 파일 방식**이다. JS의 실시간 `fetch`/XHR/WebSocket 모델 호출은 없다. 팀원 API 원문을 검증해서 화면용 구조로 옮기는 도구이지, 팀원 모델 서버를 이 저장소에서 실행하는 구성이 아니다.

### 프런트엔드 — 페이지별

| 페이지 | 상태 | 확인·완성도·품질 |
|---|---|---|
| `web/pitch-studio/index.html` | 동작 확인됨 | 현재 공개 HTTPS 페이지 열림. 영상·미트 대표 장면·내비게이션. 고정 데이터에 맞춘 전시 화면 |
| `receiver.html?demo=849843-pa1` | 동작 확인됨 | 이번 브라우저에서 투구 변경→결과 숨김→공개→미트 정지 장면 확인. 3구 중 미트는 3구만 있음 |
| receiver 파일 수신 | 동작 확인됨 | 코드·Node 회귀 통과. JSON 크기/UTF-8/키/index/출처 검사. 이번 실제 새 파일 UI 업로드는 미실행 |
| `report.html#analysis` | 동작 확인됨 | 정적 검사로39고유키/27좌표/12기권 대조. 고정 관측 탐색 화면이며 이번 브라우저 전 항목 재검사는 안 함 |
| `report.html#validation`, `#story` | 동작 확인됨 | 저장 평가·구현 범위 표시, 정적 검사 통과. 새 평가 수행 없음 |
| `service.html` | 일부 동작 | 이번 브라우저에서 PRODUCT PREVIEW와 모델 미연결 표시 확인. 4개 시나리오의 분석 값은 설명용 상수 |
| `src/web/static/index.html` | 일부 동작 | HTML·API 제공 확인. 이번 로컬 화면의 모든 조작을 브라우저로 재검사하지는 않음 |
| 주석/블라인드 검토 화면 | 일부 동작 | 데이터 삽입 생성기용 템플릿. 원본 HTML을 단독 서비스로 배포하면 안 됨 |

프런트 검사는 다음 두 명령을 **이번 실행하여 통과**했다. 두 번째 명령은 기본 읽기 전용 모드다.

```text
uv run --frozen python scripts/check_pitch_studio.py
uv run --frozen python scripts/export_pitch_studio.py
```

실제로는 기존 `.venv` Python으로 실행했다. JS 문법·자산·5개 Node 회귀 파일·공식 영상3개와 홈4투구 해시가 통과했다. 로컬 정적 화면은 `python -m http.server 8769 --bind 127.0.0.1 --directory web/pitch-studio`로 볼 수 있다.

출처 구분, 투구 변경 시 공개 상태 초기화, 오래된 비동기 처리 무시, 영상 오류 복구는 장점이다. 다만 reveal 원문도 이미 브라우저에 있으므로 “숨김”은 화면 순서 제어이며 정보 접근 통제나 투구 전 가용성 증명이 아니다.

### 배포와 실행 환경 — 일부 동작

- 공개 정적 웹은 Sites, 도메인은 Cloudflare DNS다. **이번 `https://pitcheezy.com/`, `/receiver?demo=849843-pa1`, `/service`의 브라우저 접근을 확인했다.** 모델 서버의 공개 배포는 없다.
- 저장된 배포 기록은 Site v9, 2026-10-06, 소스 `a3a7a6bb7bc434c6ba93ae45f12bca23c8898012`다. 현재 저장소 HEAD와 배포 소스 버전을 구분해야 한다. DNS 관리 화면·www 호스트·실기기 Safari/iPhone은 이번 재검증하지 않았다.
- `uv.lock`, Ruff/pytest, Linux/macOS CI가 있다. 직전 동일 구현의 전체 CPU 결과는 **1667 passed / 5 skipped / 2 deselected**, 실제 FFmpeg 합성 영상2건 포함이다. 이 문서 작업에서 전체 검사를 재실행하지 않았다. 기록: `docs/results/cv_local_20261007/exact_seek_validation_v1.json`.
- 원격 CI 기록은 Linux/macOS 각각1664 passed/8 skipped/2 deselected다. 실제 GPU·맥미니 성능 보장이 아니다. 공개 웹 검사 `check_pitch_studio.py`는 현재 CI에 연결되어 있지 않다.
- 이번 문서의9개 목차·JSON 예시3개·기재 파일 경로를 검사했다. 체크리스트 회귀는6개 통과했다. 첫 시도는 기존 임시 폴더 접근 권한 오류였으며, 새 작업용 임시 경로로 실행해 통과했다.
- 일반 검사: `uv run --frozen python scripts/check_project.py --cpu-only`. 설치: `uv sync --frozen`, 로컬 CV는 `uv sync --frozen --extra local-cv`. 이번 재설치하지 않았다.

## 4. 데이터 형태

### 수집·학습 데이터

기본 투구 식별자는 `(game_pk, at_bat_number, pitch_number)`의 정수3개다. 외부 표시에서는 `849843:1:3` 같은 문자열로 합친다. 목록 순서로 영상과 기록을 연결하면 안 된다. Statcast 원본은 Parquet이며 실제 `plate_x`, `plate_z`는 ft, `release_speed`는 mph 등 원자료 단위를 가진다. 전처리 벡터는 표준화 값·one-hot·확률이 섞여 있어 벡터 전체에 하나의 물리 단위를 붙일 수 없다.

`point_<split>.npz`의 필수 구조 (`src/data/point_data.py`):

| 필드 | 타입/형태 | 의미 |
|---|---|---|
| `schema_version` | 정수 scalar, 1 | 데이터 계약 버전 |
| `vectors` | 유한 숫자 `[N,D]`, D=77/135/151; 로더 출력 float32 | 특징. 차원만 같다고 호환되지 않음 |
| `labels_4`, `labels_10` | 정수 `[N]` | 각각 -1 또는 클래스 범위; -1은 미매핑 |
| `pitch_ids` | 정수 `[N,3]` | 중복 없는 투구 키 |
| `class_names` | 문자열 `[10]` | 아래 legacy10 클래스 순서 |

운영 파일은 추가로 `feature_schema` 문자열 scalar를 저장하며 `vectors`는 float32 `[N,135]`다. 운영77은 같은 행의 앞77열을 사용한다. `metadata_<split>.parquet`에는 대응 투구 키·상태·구종과 `state_code,next_state,runs,label_10,run_cost`가 있다. 모델별 `predictions_<split>.npz`는 `probs:[N,10]`, `targets:[N]`, `pitch_ids:[N,3]`, `class_names:[10]`을 저장한다.

역사적 sequence는 `vectors_c_<split>.npy:[N,87]`, `labels_10_<split>.npy:[N]`, `hit_locs_<split>.npy:[N]`, `indices_<split>.pkl`의 `(batter_id,start_index)` 목록으로 구성한다. 한 입력은 `[400,87]`이고 hybrid는 window 마지막 행의 `static_58`을 추가한다. 이 sequence 정답 파일을 point 입력에 별도로 붙이는 방식은 금지한다.

운영135는 기본77 + 레퍼토리17 + 물리 평균15/표준편차15 + 결과율10 + 표본수1이다. 구형135의 추가58은 UMAP5+cluster1+arsenal32+moment20이므로 다른 데이터다. 운영 feature schema는 `prepitch_profiles_2022_v1`이며 builder SHA·checkpoint manifest가 맞아야 한다.

### 실제 운영 모델 입력·출력

`PrePitchState`의 필드는 다음과 같다. 임의 필드·실제 현재 투구 물리량·결과는 거부한다.

| 필드 | 타입/허용 범위 | 의미/단위 |
|---|---|---|
| `game_date` | 문자열 YYYY-MM-DD | 경기일 |
| `pitcher` | 양의 정수 | 투수 MLB ID |
| `balls`, `strikes` | 정수 0–3 / 0–2 | 개수 |
| `outs_when_up`, `inning` | 정수 0–2 / 1–30 | 아웃·회; 추천 지원은1–8회 |
| `stand`, `p_throws` | `L` 또는 `R` | 타자·투수 좌우 |
| `batter`, `on_1b`, `on_2b`, `on_3b` | 양의 정수 또는 null, 선택 | 선수 ID; 주자는 서로 달라야 함 |
| `inning_topbot` | `Top`/`Bot`/null, 선택 | 초/말 |
| `home_score`, `away_score` | 0 이상 정수 또는 null, 선택 | 득점 |
| `home_team`, `away_team` | ASCII 알파벳1–8자 또는 null, 선택 | 팀 코드 |

선택 필드를 받는다는 사실이 타자별 능력·점수 효과를 모델이 사용한다는 뜻은 아니다. 실제 이번 요청:

```json
{"pitcher":621242,"game_date":"2024-09-30","balls":3,"strikes":2,"outs_when_up":2,"inning":8,"on_1b":null,"on_2b":645277,"on_3b":null,"stand":"R","p_throws":"R"}
```

응답의 핵심 구조는 `schema="manual_recommendation_v1"`, `selected_model`, `feature_schema`, `recommendation`, `empirical_recommendation`, `reason`, `target_location`, `scope`, `limitations`, `candidates`다. HTTP 응답에 `elapsed_ms`(ms), `input_source="manual"`이 추가된다. 추천/이유는 문자열 또는 null, `target_location`은 현재 null이다.

각 `candidates[]`에는 `action`(구종 코드), `supported`(bool), `policy_probability`(0–1 선택 비중), `expected_cost`(기대 실점 비용인 숫자 또는 null), `probabilities`/`legacy_probabilities`(결과별0–1), `display_probabilities`, 표시 schema와 한계가 있다. 9회 이후의 비용 null과 지원 여부에 따른 기권을 보존해야 한다.

이번 반환 중 선택 후보의 실제 값 발췌이며, 다른 후보·중복 확률·설명 필드는 생략했다:

```json
{
  "recommendation":"SL",
  "target_location":null,
  "candidates":[{
    "action":"SL",
    "policy_probability":0.9500000000000001,
    "expected_cost":0.00829289242264377,
    "display_probabilities":{"strike":null,"ball":null,"foul":null,"hit":0.07118714665357931}
  }]
}
```

위 예시는 `candidates[]` 중 선택된 한 항목만 남긴 발췌다. 실제 결과 클래스 순서는 다음과 같다.

```text
Ball, Strike, Single, Double, Triple, HomeRun, FieldOut, Strikeout, Walk, HitByPitch
```

legacy `Strike`는 비종결 파울을 포함하고 `Ball`은 종결 볼넷을 제외한다. `FieldOut`에는 실책·야수선택, `Walk`에는 포수 타격방해가 포함된다. 따라서 독립 strike/ball/foul을 복원할 수 없어 null이다. `hit`는 Single~HomeRun의 합으로 **다음 투구의 무조건부 기록상 안타확률**이다. 구종 비중·사건확률·기대 실점·승리확률을 같은 값으로 표시하면 안 된다.

### 팀원 저장 응답 → 공개 화면

`web/pitch-studio/receiver-demo-849843.js`의 `packet`은 `pitcheezy-receiver-v1`이다. 내부 `timeline`은 `pitcheezy-watch-along-v1`. 전달 응답의 주요 필드는 다음과 같다. 허용 키가 모두 정규화된 화면 입력에 유지되는 것은 아니다.

| 경로 | 타입/단위 |
|---|---|
| `source.kind`, `revision`, `model_id`, `exported_at` | 문자열; 제공 방식·생성 코드·모델 설명·ISO시각 |
| `game_pk`, `at_bat_number` | 정수 |
| `timeline.game` | `game_pk`, `date`, `game_type`, `away_team`, `home_team` |
| `timeline.decisions[]` | 원본 `index`, `pa_id`, `at_bat_number`, `pitch_number`, `situation`, `pitcher`, `batter`, `pre` |
| `situation` | 정수 inning/outs/balls/strikes/bases/home_score/away_score, 문자열 half; bases는 주자 비트마스크 |
| `pitcher`, `batter` | 정수 id, 문자열 name; hand/side는 문자열 또는 null |
| `pre.status`, `pre.reason` | 상태 문자열, 이유 문자열/null |
| `pre.recommendation.candidates[]` | 정수 rank, 문자열 pitch_type/pitch_label/zone_label; zone_id는 이름 문자열·legacy 정수1–9·null |
| 후보의 `target.x`, `target.z` | target 객체가 있으면 숫자, ft; target 자체는 null 허용. 과거 분포에 근거한 근사 위치 |
| 후보의 `detail.probability` | 숫자0–1, **구종 선택 비중** |
| `reveals[]` | `pitch_id`, `source_endpoint` 문자열과 `response` 객체; response의 index는 원본 투구 index |
| `reveals[].response.actual` | 구종·결과 문자열, `speed_mph`(mph), `x`,`z`(ft); 표시 필드 null 허용 |
| `reveals[].response.we` | `home_before`, `home_after`는0–1, `home_delta`, `batting_delta`는 확률 차이; null 허용, 화면은×100하여 %p |

실제 저장된 첫 구 후보의 발췌:

```json
{"rank":1,"pitch_type":"ST","pitch_label":"스위퍼","zone_id":"low_middle","zone_label":"낮은 중앙","target":{"x":0,"z":1.8983166666666667},"detail":{"probability":0.2747000042139988}}
```

출처는 `provided_export`, 생성 revision `2eb718ef13024ad2d98d28e248388db7f8dc1bc9`, 시각 `2026-09-30T17:48:53+09:00`, 모델 표기는 `ARM-B P3 (pitch type only), frozen <=2025 (ML-POLICY-VAL-v1)`이다. 이 메타데이터가 실제 실행 중인 백엔드 커밋을 인증하는 것은 아니다. 현재 저장 응답에는 strike/foul/hit 사건확률이 없다.

`src/inference/outcome_contracts.py`에는 우리 legacy10, 팀원 과거 service10/research11, 관찰8을 별도 schema로 정의하고 있다. 팀원 정의는 `9d09694` 시점의 참고 계약이며 최신 라이브 API를 확정한 것이 아니다. 클래스 수가 같아도 자동 변환하지 않는다.

### 미트 출력 → 화면

`IntentEstimate v1`은 JSONL 한 줄당 한 투구다. 정확한 validator는 `intent/schema.py`다.

| 필드 | 타입·의미 |
|---|---|
| `schema_version`, `pitch_id` | 정수1, 투구 키 문자열 |
| `clip_id`, `clip_sha256` | 식별 문자열, 소문자16진64자; 현재는 결정 프레임 이미지에 결속 |
| `status`, `unavailable_reason` | `estimated`/`unavailable`, 이유 문자열/null |
| `method` | `{kind:string, version:string}` |
| `evidence` | `{frame_index:int, frame_time:number}`; 영상 프레임·초 |
| `provenance` | `{label_source:string, review_status:string}`; 사람/AI 출처와 검토 여부 |
| `deepest_frame`, `blocked_by` | 도달 좌표계·다음 변환이 막힌 이유, 문자열/null |
| `points.image_pixels` | `{x:number,y:number}`; 원본 이미지 px, 오른쪽/아래 방향 |
| `points.annotated_image_zone` | `{x:number,y:number,inside_annotated_quad:bool}`; 홈플레이트 앞변 폭 기준 값, 스트라이크존 아님 |
| `points.plate_feet` | `{x:number,z:number,x_convention:string}`; ft, `statcast_plate_x_catcher_view` |
| `transform_chain[]` | `source_frame,target_frame,method,version,error,error_units,error_status,evidence`; 측정 안 된 error는 null |
| `uncertainty` | `{value:number 또는 null,units:string,basis:string}`; 기존 결과는 px |
| `is_intent_proxy` | 항상 true |
| `claims` | `catcher_intent_verified`, `independent_ground_truth`, `physical_plate_coordinates` bool 및 `accuracy_estimate` object/null |

좌표는 도달한 단계까지만 존재한다. unavailable은 빈 points/transform_chain이다. `physical_plate_coordinates=true`는 ft 좌표계까지 계산됐다는 뜻이며 물리 정확도 인증이 아니다. 현재 투수 의도 확인·독립 정답 플래그는 false다. 원본 검증을 하지 않은 zero SHA placeholder도 가능하므로 스키마 통과와 이미지 검증을 구분해야 한다.

실제 `849843:1:3`: 프레임3084 / 51.4514초, 픽셀 **(571,372.5)**, x **−0.05172667411468945ft**, z **2.0163602871167363ft**, `review_status="unreviewed"`. 공개 화면에는 결과 공개 후 x만 표시한다. z는 계산값은 있어도 목표 높이로 검증되지 않았다.

화면용 `DEMO_DATA.schema="pitcheezy_demo_display_v1"`에는 `mitt_x_ft`, `actual_plate_x_ft`, `status`, `unavailable_reason` 등이 있다. 같은 구의 실제 plate x는 **−0.4124845298848476ft**다. 미트 자체의 위치와 공의 plate 통과점은 다른 평면이므로 두 값을 빼서 제구 오차라고 하지 않는다.

새 관측 응답 `intent_visual_observation_v1`은 별도 계약이다: `schema,observation_id,image_sha256,status,mitt,visibility,pose,reason`. `status=marked|unavailable|unknown`, `mitt`는 원본 px `[x,y]` 또는 null이다. 투구 ID·ft 좌표가 없고 로컬 범용 탐지기는 항상 `mitt:null`을 유지한다. 후보 박스는 별도 sidecar에만 남긴다.

마지막으로 `preview-data.js`는 `source_kind="illustrative"`, `model_connected=false`, `causal_attribution=false`인 설명 자료다. 그 안의 `probabilities`, `command_score`, `contact_score`, `keep`, `replace`는 모델 출력으로 가져가면 안 된다.

## 5. 기술 스택

이번 로컬 설치 버전이며, 플랫폼별 선언과 구분한다. 재현 기준 파일은 `pyproject.toml`과 `uv.lock`이다.

| 계층 | 언어·프레임워크·주요 버전 |
|---|---|
| 공통 | Python3.12.12, uv0.10.4; 프로젝트 요구 Python≥3.12 |
| 데이터 | pybaseball2.2.7, pandas3.0.2, NumPy2.4.4, PyArrow24.0.0 |
| 모델 | PyTorch2.6.0+cu124, scikit-learn1.8.0, LightGBM4.6.0, SciPy1.17.1 |
| 로컬 CV | torchvision0.21.0+cu124, Pillow12.2.0, 외부 FFmpeg8.0; OpenCV는 현재 미설치 |
| 이름 OCR | Windows PowerShell5.1/WinRT en-US OCR; OS 모델은 uv.lock으로 고정되지 않음 |
| AI 판독 | Claude Code 로그인·외부 agent workflow; Python만 설치해서 재현 불가 |
| 실험 설정·기록 | OmegaConf2.3.0, W&B0.26.1, YAML/JSON/JSONL |
| 서빙 | Python stdlib HTTPServer/ThreadingHTTPServer; FastAPI/Django 서비스 구성 아님 |
| 공개 프런트 | HTML/CSS/순수 JavaScript; React/Next/Vite/npm 의존성 없음 |
| 웹 검사 | Node24.1.0 실제 사용; 프런트 요구 버전으로 고정된 숫자는 아님 |
| 품질 검사 | Ruff0.15.12, pytest9.0.3, GitHub Actions |
| 호스팅 | Sites 정적 호스팅 + Cloudflare DNS; 별도 상시 모델 서버 없음 |

Mac 선언은 torch2.8.0/torchvision0.23.0이다. Windows CUDA 설치와 같은 바이너리를 복사하면 안 된다. 공개 웹의 Web Crypto·dialog 등은 현대 브라우저를 전제로 한다.

## 6. 설계 결정과 이유

| 결정 | 코드·문서에 남은 이유/근거 |
|---|---|
| 입력·정답·투구 키를 한 파일에 저장 | 실제 정렬 오류 재발 방지. `src/data/point_data.py`, 정렬 복구 보고서 |
| 현재 물리량 대신 과거 프로필 사용 | 투구 전에 모르는 정보 유입 방지. `src/data/operational.py`, 운영 검증 보고서 |
| 선택·보정·최종 평가 기간 분리 | test로 모델·온도를 고르지 않기 위해. `scripts/53_evaluate_operational.py` |
| CE/Brier와 정책 효용을 별도 평가 | 확률 개선이 더 좋은 선택을 보장하지 않음. `scripts/54_evaluate_policy.py` |
| 행동 지원 조건·기권 | 관측 근거가 없는 구종/상황 외삽 제한. `src/inference/recommendation.py` |
| schema·단위·SHA를 명시 | 같은135차원, 같은10종도 의미가 달라 혼용 방지. outcome/intent 계약 코드 |
| 미트 합의 실패 시 기권 | 한 판독자 또는 큰 불일치를 확정 좌표로 승격하지 않기 위해. `intent/condensed.py` |
| 공개 후 가로 위치만 표시 | 사전 가용성·높이·실제 의도·같은 평면 정확도를 검증하지 못했기 때문. 시연/CV 문서 |
| 정확한 PTS·해시와 미래 cutoff 검사 | 피드 UTC를 재생초로 오인하거나 다른 프레임을 같은 입력으로 쓰지 않기 위해. `intent/clip_frames.py` |
| 지속 worker·정확한 탐색 | 모델 반복 초기화와 처음부터 디코딩하는 비용 감소. CV17–24 문서 |
| 정적 응답 수신기 | 기존 응답을 변경 없이 받아 시연하고 출처·투구 대응을 확인. `docs/INTENT_DEMO_SITE.md` |
| 특정 Transformer12층/8 heads가 최선이라는 선택 | 참고 모델 구조는 기록되어 있으나 이 프로젝트에서 최적이라는 근거 없음 |
| 모든 역할을 하나의 거대한 연구 저장소에 둔 이유 | 역사적 추가 기록은 있으나 최종 서비스 아키텍처로 선택한 근거 없음 |

미트 좌표 변환에는 홈플레이트 폭17인치와 가정한 미트 깊이2.5ft 등이 사용된다. 카메라 보정에 뒤 시점 자료가 포함될 수 있다. 이 구조를 투구 전 실시간 물리 좌표 추정으로 소개할 근거는 없다.

## 7. 이 프로토타입의 강점

1. **데이터·출력 계약과 추적성.** 투구 키, 클래스 순서, schema, 출처/해시, 기권을 함께 다룬다. 양쪽 시스템을 연결할 때 가장 먼저 보존할 부분이다.
2. **운영 조건을 분리한 확률 평가.** 실제 투구 특징을 이용한 연구 성능과 투구 전 조건을 혼동하지 않는다. 기준선·시간 분리·보정·경기 신뢰구간이 남아 있다.
3. **좋지 않은 결과도 남기는 검증.** 정렬 오류·정책 효과 미입증·CV 모델 탈락을 숨기지 않는다. 모델 선택의 재검증 기반으로 쓸 수 있다.
4. **미트 관측과 검토 도구.** 사람/AI, 관측/의도, px/ft, 미검토/기권을 분리한 JSONL과 검토 패키지는 통합 후에도 재사용 가치가 높다.
5. **영상 입력의 정확성·실행 기록.** PTS, 이미지 해시, 시간 경계, cold/warm 지연을 구분하는 처리 경로가 있다. 속도 개선 후에도 같은 프레임인지 검증한다.
6. **관객용 화면과 수신 도구.** 실제 저장 추천→영상→결과→미트 순서를 이미 보여준다. 최종 백엔드와 연결할 프런트 출발점으로 쓸 수 있다.

통합 제안은 **평가·계약·CV 검토·프런트 수신 부분은 우선 보존**, 핵심 모델은 상대 저장소와 같은 과제·코호트·출력 의미로 비교한 뒤 선택하는 것이다. 이번 조사만으로 어느 쪽 모델이 더 낫다고 결론 내릴 수 없다.

## 8. 이 프로토타입의 약점

1. **제품의 핵심 연결이 끊어져 있다.** 공개 화면, 수동 추론 서버, 영상 인식 실험이 별도다. 자동 중계 상태→실제 모델→화면까지의 운영 경로는 미완성이다.
2. **공개 분석 스튜디오의 핵심 값이 예시다.** 사건확률·투수/타자/감독 평가를 실제 기능으로 오해하면 통합 판단이 틀어진다. 데이터 공급 계층을 교체해야 한다.
3. **추천 범위가 좁다.** 우리 운영 모델은 오래된 고정 프로필·구종 선택·1–8회 제한이고, 타자 개별 능력·목표 위치·완전한 상태 전이를 모델링하지 않는다. 실제 효용도 미입증이다.
4. **CV는 처리 속도보다 판독 품질이 막혀 있다.** 범용 탐지기/작은 회귀 모델은 채택되지 않았다. M3 판독 일치도와 최신 로컬 루프 속도는 서로 다른 방법의 결과라 합쳐서 고성능 실시간 모델이라 할 수 없다.
5. **데이터와 평가 범위가 작거나 편향돼 있다.** OCR은 SNY 한 경기 개발, M3는 편집 영상2경기와 사람1명이다. 시간 선택·새 방송·다른 카메라 일반화를 검증하지 못했다.
6. **연구 코드와 운영 코드가 섞였다.** 옛/새135d, 여러10종 의미, 전용 스크립트, placeholder head, 무효 실험 자료가 공존한다. 통합할 때 실행 경로를 명시적으로 제한해야 한다.
7. **배포·패키징이 완결되지 않았다.** fresh clone에 운영 번들이 없고 실제 Sites checkout은 Git 밖에 있다. wheel 설정도 `packages=["src"]`라 `intent`, `web`, `scripts` 전체 서비스가 패키지에 포함되지 않는다.
8. **검사가 많아도 운영 검증을 대신하지 않는다.** 합성·계약 테스트 중심이며 실제 모델/FFmpeg/기기별 검사는 별도다. 공개 웹 검사는 CI 누락이다.
9. **같은 우리 저장소 안에도 미통합 브랜치가 있다.** 현재 CV 브랜치에는 이름 OCR v4와 첫 투구 전 교체 허용 수정이 없다. 다른 우리 브랜치의 `2876d8f`에 존재한다. 두 tip은 공통 조상 이후 각각117/7개 고유 커밋이며 단순 fast-forward 관계가 아니다. 현재 기능이라고 합산하면 안 된다.
10. **오래된 문서가 최신 기록과 공존한다.** “실제 응답 대기”, 과거 테스트 수, 철회된 성능 등이 남아 있다. 최신 코드·결과를 기준으로 안내를 정리할 필요가 있다.

대체 후보는 공개 모델 서빙·자동 상태 연결·장기 저장·인증 같은 운영 계층이다. 상대 구현이 실제로 검증됐다면 그 계층을 기준으로 삼고 이 저장소의 계약/검토/화면을 옮기는 편이 합리적이라는 **설계 제안**이다. 상대 구현의 우수성을 이번 문서에서 검증한 것은 아니다.

## 9. 외부 의존과 이식 시 주의점

| 의존/대상 | 현재 상태와 이식 조건 |
|---|---|
| 운영 데이터 | `data/operational_20260921_v2/`의 `dataset_manifest.json`, `feature_builder.pkl`, `run_value_model.npz` 등이 필요. 현재 CV 작업 폴더에는 없음 |
| 운영 모델 | `outputs/operational_20260921/evaluation/{probability_report.json,empirical.pkl}`, 선택된 `mlp135_seed*/{manifest.json,best.pt}`, `policy_nuisance_v2/{manifest.json,propensity.txt}` 필요. 재평가에는 reward/test 자료도 필요 |
| 현재 실제 실행 위치 | 위 자료는 다른 우리 폴더 `C:/Users/zpfh1/Projects/transition-models/`에서 확인·사용했다. 수신자 컴퓨터에는 별도 복사와 SHA 검사가 필요 |
| 원본 학습 자료 | 운영 재학습에는 2022–2024 Statcast Parquet가 필요. 정렬 복구·legacy135 재현에만 별도 handoff·구형 scaler가 필요. Git clone만으로 자료가 따라오지 않음 |
| CV 자료/가중치 | 원본 영상·프레임·capture receipt·로컬 torchvision 가중치가 별도. 기기별 새 실행 계획을 만들어야 하며 기존 절대 경로 계획을 복사 실행하면 안 됨 |
| Git LFS | `*.pt` 규칙 있음. 이번 확인한 일부 구형 가중치는 실파일이지만 새 clone에서는 LFS 수신 여부 확인 필요. 구형 가중치를 최신 운영 모델 대신 쓰면 안 됨 |
| 외부 API/영상 | pybaseball/MLB Stats·미디어 URL 가용성에 의존. 이번 네트워크 전체 재수집 안 함. 영상 재배포 권리는 저장소만으로 확인되지 않음 |
| Claude 판독 | Claude Code CLI와 구독 로그인, workflow 실행 환경 필요. 어댑터는 API fallback을 거부한다. 토큰/인증값은 문서나 저장소에 포함하면 안 됨 |
| W&B | 기록을 사용하려면 계정 설정이 필요할 수 있음. 저장 모델의 로컬 추론 자체는 W&B 서버 호출을 요구하지 않음 |
| Windows OCR | en-US WinRT OCR 필요. Mac에서 같은 이름 OCR 예측을 바로 실행할 수 없음. 저장 결과 채점은 이식 가능 |
| FFmpeg/CUDA | FFmpeg 실행 파일 별도, GPU 드라이버·기기별 torch 설치 필요. 현재 지연 수치는 Windows RTX4070 Laptop 환경 결과 |
| 하드코딩 경로 | `scripts/21_preprocess_135dim.py`, `25_extract_arsenal_by_cluster.py`, `30_align_static58_for_sequence.py`, `33_preprocess_matchup151.py` 등에 `C:/Users/zpfh1/Projects/data/data/...` 존재. 운영 경로의 `--runs-dir` 지원과 혼동 금지 |
| Sites 배포 | `web/pitch-studio`는 보존 사본. 실제 checkout은 기존 폴더의 ignored `outputs/cv_followup_20261005/pitcheezy-demo-site`에 있음. Sites 프로젝트 권한·소스 동기화가 별도로 필요 |
| 도메인 | `pitcheezy.com` 실제 접근 확인. Cloudflare/Sites 관리자 권한 이전은 별도. www 설정은 이번 미확인 |
| 오프라인 자료 | 오프라인 v4 ZIP은 Site v8 스냅샷으로 최신 v9와 다름. 비공개 비교 그림이 있어 공개 웹에 통째로 올리면 안 됨 |
| 스키마 통합 | 우리 결과10종·팀원 구종 비중·관찰8종·IntentEstimate·새 관측 응답을 구분. 변환은 의미와 단위를 합의한 필드만 허용 |

현재 코드에서 사용되지 않는 비밀 키가 있는지 모든 사용자 홈·외부 환경을 조사한 것은 아니다. 필요한 인증 방식과 파일 의존만 확인했으며 비밀 값은 읽거나 수록하지 않았다.

통합 전에 사람이 확인할 항목은 다음과 같다.

- **기준 브랜치:** 최신 CV/웹의 `feature/intent-v0`를 기준으로 하고 다른 우리 브랜치의 OCR 변경을 선별 이식할지.
- **운영 번들 전달:** 기존 우리 폴더의 최종 모델·데이터를 누가 어디에 보관하고 팀원에게 어떤 방식으로 전달할지.
- **최종 모델/API:** 저장 첫 타석 이후의 최신 팀원 계약·지원 경기/투수·가중치·생성 버전. 이 문서의 과거 응답만으로 확정할 수 없음.
- **실제 시연/기기 결과:** Song의 숫자 의미·표시 순서 최종 확인, 맥북/아이폰 리허설 기록이 별도로 존재하는지.
- **검토·새 평가:** CV6 추가26장 실제 응답, 새 영상 독립 검토자·자료 확보 여부.
- **배포 자산/권한:** MLB 영상·비공개 비교 자료의 공유 범위와 재배포 권한, Sites·Cloudflare 소유/운영 권한.

이번 작업은 문서 작성과 읽기·실행 확인에 한정했다. 모델 재학습, 코드 수정, 팀원 저장소 변경, 공개 배포는 하지 않았다.
