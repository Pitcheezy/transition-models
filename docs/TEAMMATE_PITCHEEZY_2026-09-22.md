# 팀원 레포(SongRoute/pitcheezy) 대조 요약 — 2026-09-22

대상: https://github.com/SongRoute/pitcheezy.git `main` @ `9d09694` (2026-09-22 11:47, "코덱스 세션").
읽기 전용으로 클론해 문서·인터페이스·코드를 대조했다. 수치는 그 레포 문서에 적힌 값이며
원본 산출물(맥미니 외장 SSD `/Volumes/T7 Shield/...`)은 Git에 없어 재현하지 못했다.
이 문서는 CHECKLIST.md의 I절(팀원 산출물 통합)과 C·D 이관 판단의 근거다.

## 1. 한 줄 결론

팀원 레포는 **우리 저장소·경기 747139·8770 데모·play_id·중계/점수판 작업을 전혀 참조하지 않는
별도 병렬 트랙**이다. 거기서 "SmartPitch"는 Otremba 2022 논문을 자기 프레임워크 안에서 재구현한
베이스라인(B1)을 뜻한다. 따라서 통합은 "이미 있는 접점을 잇는 일"이 아니라 **접점을 새로 정의하는
일**이며, 그 정의(I-0)가 A/B보다 먼저 합의돼야 C·D 이관이 실제로 성립한다.

## 2. 팀원 레포 구조 — 서로 다른 두 스택

| | 연구 스택 `src/pitcheezy` | 서비스 스택 `experiments/pitchmdp` + `apps/observer` |
|---|---|---|
| 결과 클래스 | **11종** `ball, strike, foul, K, BB, HBP, 1B, 2B, 3B, HR, in_play_out` (`src/pitcheezy/interfaces/outcomes.py`) | **10종** `ball, strike, foul, out, single, double, triple, home_run, hbp, double_play` (`experiments/pitchmdp/pitchmdp/model.py`; walk/strikeout은 카운트 규칙으로 파생) |
| 상태 | `((count_id×24+base_out_id)×K+cluster_id)×C+context_id`, S=288×K×C | (balls, strikes, prev_pitch_type); 경기 상태는 타석 내 고정 |
| 행동 | 9구종 × 25위치(5×5) = 225 | 구종(서비스) / 구종×3×3 목표 셀(연구) |
| 전이 모델 | 투수별 카운트 계층 평활(Dirichlet) 텐서 `P[pitcher,S,A,O]` | 시퀀스 `flatten_mlp` 5시드 앙상블 + 빈도 기준선 혼합(w=54.24%, CAL로 결정) |
| 보상/가치 | 리그 공통 **RE24** −ΔRE24, VI, tilt 정책 τ=0.02 | **승리확률(WE) %p**, 타석 전체 백워드 스윕 |
| 평가 | 2026 시즌 **OPE 전용**(SNIPS, 짝지은 Δ, 경기 클러스터 부트스트랩) | 독립 평가자(7월 적합) + 2025-08-16~09-30 |
| 채택 결과 | EXP-P0-009 채택. vs B1 Δ **+0.0026 [+0.0007, +0.0044]** −ΔRE24/결정. 검출 한계 ≈0.002 | 정책 이득 **+0.00403 pp, 97.5% CI [−0.00075, +0.00871]** — 0 포함, 미입증 |
| 데이터 | 2023–25 학습, 2025 홀드아웃(내부), 2026 OPE 전용(비동결, 9/27 이후 freeze) | 2023-05-15~2025-04-30 학습 / 5–6월 CAL / 7월~ DEV, 2026 금지 |

우리 10종 운영 모델(`Ball, Strike, Single, Double, Triple, HomeRun, FieldOut, Strikeout, Walk, HitByPitch`)은
계보상 **서비스 스택(10종)** 과 가깝고, 고정 계약인 연구 스택(11종)과는 다르다.

## 3. 결과 클래스 대응표 (통합 전 반드시 합의)

| 우리 10종 | 팀원 서비스 10종 | 팀원 연구 11종 | 비고 |
|---|---|---|---|
| Ball | ball | ball | 동일 |
| Strike (**파울 포함**) | strike ∪ foul | strike ∪ foul | 우리 Strike는 파울을 합친 클래스. 그쪽은 분리 |
| Single/Double/Triple/HomeRun | single/double/triple/home_run | 1B/2B/3B/HR | 동일 |
| FieldOut | out ∪ double_play | in_play_out | 그쪽 서비스는 병살 분리 |
| Strikeout | (파생: s=2에서 strike) | K | 그쪽 서비스엔 클래스 없음 |
| Walk | (파생: b=3에서 ball) | BB | 상동 |
| HitByPitch | hbp | HBP | 동일 |

우리 새 8종 관찰 정답(볼/루킹/헛스윙/파울/파울팁/안타/인플레이 비안타/HBP)은 **어느 쪽에도 없다.**
루킹·헛스윙·파울팁 구분은 그쪽 `strike`의 세분화다. **정정(2026-09-22)**: 위 표는 *의미 대응 참고*이지
인덱스 재배열 규칙이 아니다. 우리 10종은 볼넷·삼진을 종결 클래스로 갖고 Strike에 파울을 합치며
FieldOut에 실책 등 비아웃 사건이 섞여 있고, 그쪽 서비스 10종은 파울·병살을 분리하고 볼넷·삼진을 카운트
규칙으로 파생한다. 이름·순서만 바꿔 서로 변환하면 안 된다. 또한 우리 8종은 안타 종류를 합치므로
`8종 + 카운트`만으로 단타·2루타·3루타·홈런을 복원할 수 없고, 서비스 10종의 `double_play`도 만들 수 없다.
팀원 서비스 스택은 10이 최소 6곳에 하드코딩돼 있어(`minimal_pitch_service.Engine`, `planner`,
`refresh_pitch_service`, 평가자들) 8종 헤드는 드롭인이 아니다.

**2026-09-27 I-6 코드 대조 보완:** 고정 검토 커밋 `9d096940b6fe065051979cd7ef4dbfde006e35c6`의
실제 코드에서 `foul_bunt`는 서비스10에서 2스트라이크 때 strike가 되고, 관찰8에서는 foul로 남는다.
우리 `catcher_interf→Walk`와 연구11의 `hit_into_play+catcher_interf→in_play_out`도 다르다.
연구11의 `in_play_out`은 안타 이외 인플레이의 미지 사건까지 합치고, 서비스 out/double_play는 사건 지원 범위가 더 좁다.
위 표의 같은 이름·의미 대응을 같은 모집단의 확률 또는 자동 변환으로 해석하면 안 된다.
[버전별 계약·실제 반례·사용법](OUTCOME_CLASS_CONTRACTS.md)을 따른다. 최신 서비스 합의나 실제 응답 검증은 별도 대기다.

## 4. C·D 이관에 대한 사실 확인

### C (새 8종 확률 모델)
- 팀원 레포에는 8종 헤드도, 루킹/헛스윙 구분도 없다. 있는 것: **strike/ball/foul 분리**(두 스택 모두),
  CE/Brier/상위라벨 ECE 보고(`pitchmdp/model.py::metrics`), CAL 전용 온도 보정, 엄격한 시간 분할,
  투구 키(`game_pk, at_bat_number, pitch_number`) 1:1 정렬과 재생 검증(오차 1.06e−7).
- 실용적 경로: UI의 독립 스트라이크·볼·파울에 필요한 것은 "파울 분리된 확률"이며, 이는 팀원
  서비스 10종 출력에 이미 있다. → **C의 1차 목표를 "팀원 10종 서비스를 어댑터로 소비"로 재정의**하고
  우리 8종 학습은 후순위(선택)로 둘 것을 제안한다(I-1). 팀원 레포 규칙: "NLL·ECE는 스크리닝용,
  채택은 e2e OPE로만" — CE/Brier 개선을 정책 근거로 쓰지 않는다.

### D (경기 시점 이전 자료만 쓰는 투수 프로필 / 신규 투수)
- `experiments/pitchmdp/scripts/refresh_pitch_service.py`: `--as-of` 날짜 이전 자료만으로 **타자** 프로필
  스냅샷(887명, 2025-08-15까지)과 **90일 내 ≥20구 레퍼토리 마스크**를 만드는 불변 사이드카. 같은 날
  더블헤더 격리, 2026 날짜 가드, 스냅샷 해시 고정 — 시간 정합성 패턴으로 재사용 가치가 크다.
- 이 사이드카는 **타자 프로필·레퍼토리 마스크**용이며 우리 135d 운영 투수 프로필(고정 2022)과 바로
  호환되지 않는다. 산출물(스냅샷 JSON)과 책임 범위(누가 우리 feature builder에 붙이는가)를 I-0에서 확인한다.
- 그러나 **투수 표현 자체는 없다**(서비스 모델에 투수 특성 없음, 지원 투수 6명 고정), 신규 투수는
  4곳에서 의도적으로 차단(HTTP 400 `unsupported_pitcher`). 9회 이후는 데이터·WE 특성·학습 자료 세 층에서
  미지원. → D의 팀원 산출물은 "as-of 프로필/레퍼토리 방식 + 스냅샷 데이터"이고, **우리 운영 135d
  feature builder의 고정 2022 프로필을 그 방식으로 갱신하는 코드는 우리 쪽 작업**(I-2)이다.

### 결정적 제약 — 시연 경기 불일치
팀원 서비스 번들이 지원하는 투수는 6명(Webb 657277, Gilbert 669302, Berríos 621244, Castillo 622491,
Valdez 664285, Bassitt 605135, 2025-08-16~09-30 경기). 우리 경기 747139(2024-09-30 NYM@ATL,
Schwellenbach 680885 / Megill)는 **그 서비스에서 400을 받는다.** 통합 시연을 하려면 (a) 팀원 번들의 투수
코호트 확장, (b) 우리 주석·평가셋을 팀원 12경기 중 하나(예: Webb 등판)에 추가, (c) 두 데모를 분리 유지
중 하나를 골라야 한다(I-5).

## 5. 우리 영역별 대조 (팀원 레포 기준)

| 우리 영역 | 팀원 레포 | 우리 방침 |
|---|---|---|
| A 중계 시각 주석 | 부분·다른 형태: Video Lab은 클립 상대 초(`seed/end/release_time`)·불변 SHA id, **`pitch_id` 항상 null**, 승인 클립 1개(삼진 하이라이트, 4구간), `release_time`은 배제 경계(우리 `release_seconds`는 사건 추정) | 계속(우리만 가진 실제 영상↔투구 자산). 팀원 스키마 v2 제안은 I-3 |
| B 점수판 인식 평가셋 | 없음(OCR·인식 코드 0건) | 계속 |
| F-1 목표 위치 | 관측 위치 재가중 proxy(σ=0.45ft) 구현·독립 평가됨. **좁은 σ 후보는 정책 효과 음성**(−0.019 %p, CI 0 제외) | "영상 기반 의도 라벨"로 재정의 검토 후 착수(I-0에서 합의) |
| F-2 타자 특성 | 완료(6 성향률+신뢰도, 전날까지 자료, 더블헤더 격리) | 새로 만들지 않고 소비(I-4) |
| F-3 점수판 OCR / F-4 추적 | 없음 / 픽셀 패치 추적만(선수·공 아님) | 계속 |
| E 구 영상 재검증 | 코드·데이터 재검증 장치는 강함, 영상은 1클립 | 계속 |
| G 효용 검증 | 짝지은 Δ OPE(`scripts/ope_compare.py`), 플라시보·민감도, 검출 한계 분석 | 같은 방식·공통 통화로 재평가(G-3) |

## 6. 인터페이스 사실 (I-0 합의 항목)

1. **투구 식별**: 팀원은 `game_pk + at_bat_number + pitch_number`(문자열 id `f"{game_pk}:{pa_id}:{pitch_number}"`),
   `play_id`는 어디에도 없음. 우리 manifest에는 둘 다 있으므로 조인표는 우리가 제공한다.
2. **결과 클래스**: 3절 표. 우리 Strike의 파울 포함이 가장 큰 의미 차이.
3. **통화**: RE24(`re24-2023_2025-d20260911-s2325-82b008b`, 경기 마지막 반이닝 제외, 인플레이 아웃 통합)
   vs WE %p vs Statcast `delta_run_exp`. 공동 표에는 하나만.
4. **시즌 규칙**: 2026 자료는 학습·튜닝·선택 금지, OPE 전용. 경기 747139는 2024라 저촉 없음.
5. **서비스 요청 스키마**(`minimal_pitch_service.validate_request`): `inning 1..99, topbot, outs 0..2, bases 0..7(1B=1,2B=2,3B=4),
   home/away_score, balls 0..3, strikes 0..2, pitcher_id, batter_stand, date, batter_id|batter_profile{rates[6],reliabilities[6]}`;
   응답은 후보 구종별 `defensive_we`, `delta_vs_baseline_policy`, `outcome_probabilities{10종}`. 우리 PREPITCH 계약과 어댑터 필요.
6. **관측자 앱**: FastAPI 8766/8768, 9존 id(`low_left`…`high_right`, catcher_view, 좌우 반전 없음),
   추천은 12카운트 전체 텐서를 요구 → 우리 8770 API를 붙이려면 12카운트 배치 응답 필요. macOS SSD 경로
   하드코딩으로 Windows에서 실행 불가.
7. **명칭**: 공동 문서에서 우리는 "transition-models P0"로 표기(그쪽 "SmartPitch"=Otremba 베이스라인).

## 7. 팀원에게 확인할 질문

1. C의 목적이 "UI 독립 스트라이크·볼·파울 표시"라면 팀원 10종 서비스 소비로 갈음해도 되는가? 8종 학습은 보류?
2. D 산출물은 (a) as-of 스냅샷 데이터+방식 인계, (b) 우리 모델용 투수 프로필까지, (c) 신규 투수 정책 중 어디까지인가?
3. 시연 경기: 747139 유지(팀원 코호트 확장 필요) vs 팀원 12경기 중 하나로 이동 vs 분리 유지?
4. 공동 표의 통화·평가 프로토콜(RE24 버전, 짝지은 Δ, 2026 freeze 재실행 대기 여부)?
5. Video Lab 스키마 v2(`pitch_id` 채움, `decision_seconds`·`uncertainty_seconds`·`note`·`manifest_sha256` 추가,
   `usable_for_tracking` 하드코딩 해제, SSD 경로 제거)를 받아줄 수 있는가?
6. 결과 클래스 대응표(3절)에 동의하는가? 특히 우리 Strike의 파울 포함.

## 8. 재현·주의

- 클론은 Windows 경로 길이 제한(`apps/observer/runtime_src/third_party_notices/...`)으로 부분 체크아웃되며
  `git show HEAD:<path>` 또는 `git archive HEAD <subpaths>`로 읽어야 한다.
- 팀원 문서의 모든 수치는 외장 SSD 산출물 기준 자기 보고이며 여기서 재현하지 않았다.
- `docs/baselines.md`(SmartPitch PDF 미열람)와 `experiments/pitchmdp/docs/RESEARCH_GAP_REVIEW.md`(열람, 타자 성향 사용·
  무주자 0아웃 보상 고정)가 서로 모순 — B1 정의가 원문과 다를 수 있음을 공동 표에 적을 것.

## 9. I-0·I-5 통합 준비 (2026-09-22, 검토 기준 `main` 9d09694; 같은 날 재확인 시 `main` 804f523)

**2026-09-22 재확인**: `main`이 9d09694 → 804f523로 3커밋 앞섰고 모두 문서다(`docs/roadmap.md` 신설 237행,
`docs/decisions.md` D43~D45, `docs/plan.md`, `CLAUDE.md` 1행). 코드·번들·서비스·설정 변경은 없어 아래 사실은 그대로다.
통합에 관련된 내용만 적는다(읽기 전용, 재현·평가 없음).
- D43 최종 목표: 팬이 경기를 보며 참고하는 **웹페이지 하나** — (1) 다음 공의 구종·위치 (2) 실제 투구와 비교 (3) 중요 사건의
  원인 비중. "신뢰"(근거·보정·미지원의 정직한 표시)가 정확도와 같은 급의 요구.
- 로드맵 M0는 기본 문제를 **수비 팀 WE**로 두자고 제안하지만 `design.md`는 학습 보상을 RE24로 고정 — **그쪽에서도 미결**.
  두 트랙 수치를 같은 표에 섞기 전 결정 한 줄이 필요하다고 스스로 기록(우리 G-3와 같은 쟁점).
- M1(실제 기록·목표 위치·교체 정보 확보)이 모든 단계의 앞에 있고 **영상 확보가 병목**이라고 명시. "원본 영상 서비스는 별도이며
  필수 의존성으로 만들지 않는다." → 요청 문안 3번(지원 경기 목록과 확보된 영상)이 그쪽 계획과도 맞물린다.
- G7(실제 경기 연동·중계 동기화)은 M6, 마지막 단계. 우리 A/B(중계 시각·점수판)와 겹치는 영역이지만 그쪽은 아직 착수 전.
- D44: 일정 관리 중단, 의존성 순서로 진행. 유일한 날짜 제약은 2026 freeze(9/27 이후 자료는 OPE 전용).

첫 통합의 완료 기준: **한 타석 영상 → 투구 전 상태 → 동료 서비스 → 확률 표시.**
전체 경기나 두 UI 동시 완성은 범위 밖. 아래는 "코드로 확인된 사실 / 우리 기본안 / 동료 답변 필요"로 구분한다.

### ① 사용할 서비스와 요청·응답

**코드로 확인된 사실** (`experiments/pitchmdp/scripts/minimal_pitch_service.py`, `MINIMAL_SERVICE.md`)
- 127.0.0.1:8765. `GET /health`, `GET /metadata`(지원 투수·구종·`profile_order`·`profile_cutoff`·`delivery_draws`·assumptions),
  `POST /recommend`(JSON 본문 1~65536바이트, 10초 소켓 타임아웃). 서버 없이 `--request file.json`도 가능.
- 필수 입력(정수는 `type is int`, bool 거부): `inning` 1..99, `topbot` Top/Bot, `outs` 0..2, `bases` 0..7(1루=1, 2루=2, 3루=4),
  `home_score`/`away_score` 0..999, `balls` 0..3, `strikes` 0..2, `pitcher_id`, `batter_stand` L/R.
  선택: `top_k`(1..20, 기본 3), `date`(YYYY-MM-DD), `batter_id`(TRAIN 스냅샷 조회) 또는
  `batter_profile{rates[6], reliabilities[6]}`(순서 contact, swing, walk, strikeout, isolated_power, groundball; 요청 날짜 이전 자료여야 함).
- 응답: `recommendations[{pitch_type, defensive_we, delta_vs_baseline_policy, outcome_probabilities{ball, strike, foul, out,
  single, double, triple, home_run, hbp, double_play}}]`, `objective: "full_pa_defensive_we"`, `baseline_defensive_we`,
  `baseline_policy`(train_repertoire_frequency | uniform_pitch_types), `probability_kind: "model_internal_next_pitch_outcomes"`,
  `profile_source`, `profile_as_of`, `neural_weight`, `delivery_tiers`, `solver`, `assumptions[8]`, `latency_ms`.
- 오류: HTTP 400 `{error, message}` — `invalid_request`, `invalid_state`(경기 종료 상태 포함), `unsupported_pitcher`,
  `unknown_batter`, `profile_date_conflict`; 408 타임아웃; 500 `inference_failed`.
- 형식 예시(코드 기준으로 우리가 작성; 실제 `example_request.json`/`example_response.json`은 맥미니 SSD에 있어 미확인):

```json
{"inning": 1, "topbot": "Top", "outs": 0, "bases": 0, "home_score": 0, "away_score": 0,
 "balls": 0, "strikes": 0, "pitcher_id": 657277, "batter_stand": "R", "date": "2025-08-17", "top_k": 3}
```

**우리 기본안**
- 얇은 연결 계층 하나(예: `src/inference/teammate_service.py`): 우리 `PrePitchState`(docs/PREPITCH_CONTRACT.md) →
  위 요청으로 변환(주자 ID → `bases` 비트마스크, `inning_topbot` → `topbot`, `stand` → `batter_stand`, `batter` → `batter_id`),
  응답은 **동료 스키마 그대로**(10종 이름·순서, WE 값, `probability_kind`, assumptions) UI에 표시. 우리 legacy 10종으로
  변환하지 않고, 추천 로직·planner·12카운트 텐서를 우리 쪽에 구현하지 않는다. 서비스 불가/400은 "unavailable"로 표시.
- 8종 학습 완료로 표시하지 않는다. 이 연결은 "동료 확률 표시"일 뿐이다.

**동료 답변 필요**
- Q1. 통합 대상은 8765 최소 서비스(관측자 앱 세션 API가 아님)이고, 실행은 맥미니에서 하며 우리는 HTTP로만 호출 — 동의하는가?
- Q2. `date`·타자 입력 규칙: 우리는 전날까지 프로필을 계산하지 못하므로 `batter_id` 스냅샷 조회로 가고, `profile_date_conflict`를
  피하려면 요청 `date`가 스냅샷 `as_of` 이후여야 한다 — 시연 경기 전날 기준 refresh 스냅샷을 만들어 줄 수 있는가?
- Q3. `example_request.json`·`example_response.json` 파일을 공유해 줄 수 있는가(스키마 회귀 테스트 고정용)?

### ② 지원 투수와 모델·프로필 시점

**코드로 확인된 사실**
- **지원 투수 목록은 미확정(2026-09-22 정정).** `configs/mlb_cohort_proposal.json`은
  `status: selection_proposal_frozen_before_new_MLB_cohort_model_metrics`인 **제안 파일**이다. 서비스가 실제로 받는 목록은
  번들 생성 시 `select_cohort()`(`scripts/run_temporal_blend.py:52`, TRAIN 선발 아웃 내림차순 6명, "no future filter" —
  제안 파일의 DEV 50이닝 조건이 없다)가 쓴 `metadata.json["pitchers"]`이고, `GET /metadata`의 `pitchers`(id 문자열 키)로만
  확인된다. 제안 파일의 6명(657277 Webb, 669302 Gilbert, 621244 Berríos, 622491 Castillo, 664285 Valdez, 605135 Bassitt)은
  **잠정**으로만 쓴다. 목록 밖 `pitcher_id`는 400 `unsupported_pitcher`.
- 서비스는 `HTTPServer(("127.0.0.1", 8765))`로 루프백에만 바인딩한다. 우리 Windows 노트북에서 호출하려면 바인딩 변경,
  SSH 터널, 또는 동료가 정한 프록시가 필요하다(§③ 요청 문안 4번).
- 분할(`pitchmdp/data.py::add_splits`): history <2023-05-15 / **train 2023-05-15~2025-04-30** / **calibration 2025-05-01~06-30** / dev 2025-07-01~.
  번들 `training_cutoff`·`profile_cutoff` = 2025-04-30(`build_minimal_pitch_service.py`), 온도 보정은 CAL 전용,
  `model_calibration_cutoff` 2025-06-30. refresh 사이드카(as-of 2025-08-16): 타자 프로필 887명, 90일 ≥20구 레퍼토리 마스크,
  지원 투수 6명 중 5명 사용 가능(문서 기준).
- **시점 함의**: 경기 747139(2024-09-30)는 이 모델의 학습 창 안이다. 이 모델을 747139에 적용한 결과를 "당시의 사전 예측
  성능"으로 제시할 수 없고, 과거 프로필만 넣어도 모델 자체의 시점 문제는 해결되지 않는다. 시연 경기는 **2025-07-01 이후(DEV)**,
  실질적으로 refresh 스냅샷 이후(2025-08-16~)여야 한다.

**우리 기본안**
- 지원 투수는 실제 `/metadata` 출력 또는 동료가 전달한 번들 `metadata.json`으로만 확정한다. 그전까지 아래 ③의 42경기는
  **잠정 후보**로 유지하고 특정 투수·경기를 확정하지 않는다.
- 동료 서비스 연결 시연은 2025-08-16 이후 코호트 투수 경기로 한정한다. 경기 747139 자산(manifest·주석·평가셋)은 중계 인식(A/B)
  개발용으로 유지하고 동료 서비스와 연결하지 않는다(분리).

**동료 답변 필요**
- Q4. 코호트 확장 계획이 있는가(없으면 747139 연결은 포기)? 시연 경기 전날 as-of로 refresh 스냅샷을 만들어 줄 수 있는가?

### ③ 공통 시연 경기와 한 타석

**코드로 확인된 사실**
- 관측자 카탈로그 규칙(`apps/observer/scripts/build_catalog.py`): 2025-08-16~09-30, 코호트 투수 경기 날짜순, 투수당 최대 3경기,
  90일 ≥20구 레퍼토리 지원 타석만. 문서상 12경기·249타석·975구(`dataset.json`은 SSD에 있어 미확인).
- `apps/observer/CONTRACT.md` 예시 view: game **777262**, 2025-08-17, TB @ SF, Logan Webb, PA id 32.
- 공개 MLB schedule API(probable pitcher 기준, 실제 선발·dataset 포함 여부 미확인)로 조회한 코호트 선발 후보 — 투수별 첫 3경기:
  Webb 08-17 **776703**(TB@SF) · 08-23 776621 · 08-28 776550 / Gilbert 08-18 776689 · 08-24 776602 · 08-30 776537 /
  Berríos 08-17 776710 · 08-23 776630 · 09-02 776491 / Castillo 08-20 776662 · 08-26 776577 · 09-01 776504 /
  Bassitt 08-20 776661 · 08-26 776582 · 09-01 776503 / Valdez 08-20 776673 · 08-27 776571 · 09-02 776489 (창 전체 42경기,
  **잠정 후보** — 제안 파일의 투수 6명 기준이며 `/metadata`로 지원 투수가 확정되면 다시 계산한다).
  **주의**: 08-17 TB@SF의 gamePk가 예시의 777262와 다르다(776703). 예시가 가공 값인지 확인 필요.

**우리 기본안**
- 첫 통합 타석(잠정): **2025-08-17 TB @ SF(Webb 선발)** 의 동료 `dataset.json` 첫 지원 타석(예시의 PA 32가 실제라면 그것).
  Webb이 실제 `/metadata`에 없으면 이 기본안은 폐기한다.
  확정 후 순서: MLB 공식 전체 경기 영상 페이지·MP4 점검(60번 방식) → 투구 ID manifest(58번) → 그 타석만 시각 주석(63번) →
  동료 서비스 호출 → 표시. 공통 경기 확정 전에는 747139 주석을 크게 확대하지 않는다(A-4 한 타석 단위만).

**동료 답변 필요**
- Q5. `dataset.json`의 경기 목록(game_pk·날짜·타석 id). Webb 08-17 경기가 포함되는가, game_pk는 776703인가 777262인가?
- Q6. 그 경기의 MLB 공식 전체 영상(또는 사용 가능한 방송 소스) 확보 가능 여부.

### 동료 확인 항목 (연구 스택, 수정 요청 아님)

- `src/pitcheezy/data/prepare.py:49`는 풀 투수(`pitcher_index`)의 투구만 남긴 뒤 `pa_rewards`(같은 파일 152행 이하)로 넘긴다.
  `pa_rewards`는 남은 타석의 순서로 `same_half`(171행)와 다음 타석 `b_start`(172행)를 계산하므로, **미등록 구원투수로 교체된
  반이닝**에서는 풀 투수의 마지막 타석 다음 행이 다른 반이닝이 되어 이닝 종료로 오판(`re_next=0`)할 수 있다.
  RE24 표 자체(`data/re24.py::compute`)는 전체 투수로 계산되지만, 학습 보상 쪽은 위 경로다. 영향 건수와 기존 성능 수치의 변화는
  **미측정**이며 우리는 수정하지 않는다. → 동료 확인 요청(Q7).

### 이전 분석 정정 (사용자 지적 반영)

- 우리 10종 ↔ 동료 10종은 이름 대응이 아니라 의미가 다르다(볼넷·삼진 종결 처리, 파울, 병살, 실책). 인덱스 재배열 금지.
- 우리 8종은 안타 종류를 합치므로 8종+카운트로 단타~홈런을 복원할 수 없다(3절 정정).
- 2025년까지 학습·보정한 동료 모델을 2024년 경기에 적용한 결과는 당시 사전 예측 성능이 아니다.
- 12카운트 텐서는 동료 planner 내부 계약이다. 우리는 서비스 API만 소비하며 텐서·배치 모드를 구현하지 않는다.
- 동료의 타자 프로필·레퍼토리 갱신은 우리 135d 투수 프로필과 바로 호환되지 않는다.
- 위치 추천 proxy는 실제 목표 위치 효과가 입증된 것이 아니다(F-1은 영상 기반 의도 라벨로 재정의).

### 동료에게 보낼 요청 문안 (우선순위순, 2026-09-22 정리, **미전송**)

보내기 전 사용자가 확인한다. 항목 1~4가 먼저 필요하고, 5는 그 답을 받은 뒤라도 된다.

> 안녕하세요. transition-models 쪽에서 minimal pitch service(8765) 연결을 준비하고 있습니다. 아래 순서로 부탁드립니다.
>
> 1. **실제 metadata**: 맥미니에서 `curl -s http://127.0.0.1:8765/metadata` 출력(JSON 그대로), 또는 번들 폴더의
>    `metadata.json`과 `bundle_manifest.json`. 특히 `pitchers` 목록, `profile_cutoff`, `profile_count`가 필요합니다.
>    (지금은 `configs/mlb_cohort_proposal.json`의 6명을 잠정으로만 보고 있습니다.)
> 2. **요청·응답 예시**: 번들의 `example_request.json`, `example_response.json` (가능하면 `evaluation.json`도).
>    우리 쪽 스키마 회귀 테스트에 그대로 고정하려고 합니다.
> 3. **지원 경기 목록과 영상**: 관측자 `dataset.json`의 game_pk·날짜·타석 id 목록과, 그중 **전체 경기 영상이 확보된 경기**
>    (MLB 공식 페이지/MP4 또는 다른 방송 소스, 경로나 URL). 08-17 TB@SF의 gamePk가 776703인지 CONTRACT.md 예시의
>    777262인지도 알려 주세요.
> 4. **서비스 연결 정보**: 우리가 HTTP로 호출할 **주소**(맥미니 LAN IP 또는 Tailscale 호스트명과 포트 — 현재 코드는
>    127.0.0.1:8765에만 바인딩됩니다. 바인딩을 바꿀지, SSH 터널로 갈지), **실행 위치**(어느 기기·저장소 경로·번들 경로,
>    문서 기준 `/Volumes/T7 Shield/pitcheezy/pitchmdp/runs/minimal-pitch-service-v1`), 실행 명령과 켜 둘 수 있는 시간대.
> 5. (후순위) 시연 경기 전날 as-of refresh 스냅샷 생성 가능 여부와 `batter_id` 조회 방식 / 코호트 확장 계획(없으면 747139
>    연결은 포기) / Video Lab 스키마 v2(`pitch_id` 채움 등) 수용 여부 / `src/pitcheezy/data/prepare.py:49` 풀 필터 →
>    `pa_rewards` same_half에서 미등록 구원투수 교체 반이닝의 이닝 종료 오판 가능성 확인(영향 건수 미측정, 수정 요청 아님).

이전 질문 목록(Q1~Q7)은 위 문안에 통합됐다. 답을 받으면 §9 ①~③의 "동료 답변 필요" 항목을 사실로 바꾸고
CHECKLIST I-0·I-5를 갱신한다.
