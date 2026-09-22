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
루킹·헛스윙·파울팁 구분은 그쪽 `strike`의 세분화이며, `8종 + 카운트 → 11종`은 유도 가능하지만
`11 → 8`은 손실이고, 서비스 10종의 `double_play`는 만들 수 없다. 팀원 서비스 스택은 10이 최소 6곳에
하드코딩돼 있어(`minimal_pitch_service.Engine`, `planner`, `refresh_pitch_service`, 평가자들) 8종 헤드는
드롭인이 아니다.

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
