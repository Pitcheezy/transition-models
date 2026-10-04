# 의도 모듈 v0 — 교수 시연 리허설

2026-10-04 사용자 확정 답변 반영. **10/5 12:00 자료 전달, 18:00 약 20분 리허설, 10/6 16:00 교수 시연 약 5분**(모두 KST).
Song이 실제 화면 연결과 전체 동선을 준비하며, 시연 화면과 고정 M3 결과 설명을 모두 사용한다. M3 측정은 다시 수행하지 않는다.

## 확정 화면·데이터 계약

- 경기 **849843**의 기존 IntentEstimate v1 JSONL 39행을 유지하고, 좌표가 있는 **27구의 미트 가로 위치만 실제 투구 공개 후** 표시한다. 높이·9구역·투수 의도는 표시하지 않는다.
- 화면 제목은 **포수 미트 위치 추정**. 화면 연결·맥북·아이폰·전체 5분 동선은 Song 담당이다.
- 시연 849843은 개발 경기다. M3 평가 849845·823407 두 경기의 수치와 구분한다.
- 사용자가 전달한 확인에 따르면, `1687c1e`의 `docs/results/mlb_p0/game_849843_intent_v0.jsonl`과 현재 서비스 파일의 해시가 같다. 이번 작업에서 원격 서비스 파일을 직접 검사했다는 뜻은 아니다. 재전달·축약 JSON·zone9 참고값은 만들지 않는다.
- 추후 해당 데이터가 바뀌면 **커밋·경로·SHA256만** 공유한다. 기존 JSONL과 `is_intent_proxy=true`, `claims.catcher_intent_verified=false`는 유지한다.

줄바꿈에 따라 파일 바이트 해시는 달라진다. 로컬에서 `1687c1e`와 현재 HEAD의 git blob은 동일함을 확인했다. 아래는 로컬 확인값이며, 원격 서비스와의 일치는 사용자 전달 사실이다.

| 849843 JSONL 바이트 기준 | 바이트 수 | SHA256 |
|---|---:|---|
| Windows 작업 파일 · CRLF (기존 서비스 검사 입력) | 457,107 | `5ad0c28847c12dcea3d6c8589e966553a44d1d8f5829381b87ec6d0b7e2d27dc` |
| `1687c1e` 및 현재 HEAD git blob · LF | 457,068 | `12c11e1d2976992d39a1c4e126ba192291cd6f90edd7d82c6a9be3412dd17d0b` |

두 로컬 버전의 차이는 39개 줄바꿈뿐이다. Mac 체크아웃과 해시를 비교할 때 바이트 기준을 함께 명시하며, 이를 위해 데이터를 수정하거나 다시 전달하지 않는다.

## 근거를 찾는 법

이 문서의 경로는 저장소 루트 기준이다. JSON 배열 인덱스는 0부터 센다.

- **R**: [docs/results/mlb_p0/intent_accuracy_report_v0.json](results/mlb_p0/intent_accuracy_report_v0.json), `code_commit=6245038`.
- **E1 / E2 / P / D**: 각각 R의 `evaluation_games[0]`(849845), `evaluation_games[1]`(823407), `evaluation_pooled`, `development_games[1]`(849843).
- **J(g)**: `docs/results/mlb_p0/game_<g>_intent_v0.jsonl`. 각 행의 `pitch_id`, `status`, `points.plate_feet`, `deepest_frame`, `is_intent_proxy`, `claims`를 센다. 행 순서로 다른 파일과 연결하지 않는다.
- **S(g)**: `docs/results/mlb_p0/game_<g>_intent_setup_check_v0.json`, `per_frame`에서 `pitch_id`로 찾는다.
- 판독·해석 한계: [M3 평가 문서](INTENT_V0_M3_EVAL.md)의 ‘계획에서 벗어난 점’, ‘알려진 한계’, ‘재현·연동’. 시연 경기의 관찰 기록은 [849843 문서](INTENT_V0_DEMO_849843.md).

## 발표용 숫자

개발·시연 경기 849843과 보충 경기 849849는 아래 평가 합산에 포함하지 않는다.
**사람 표시 84구와 오차 비교 58구는 다른 분모**다. M3의 경기·라벨 수 조건을 충족했으며, 정확도 합격선을 통과했다는 뜻은 아니다.
근거: R `m3_requirement.{met,person_marked,games_with_person_marks,fallback.triggered}`, `no_threshold`.

| 수량·분모 | 849845 · NBC | 823407 · FOX | 평가 합산 |
|---|---:|---:|---:|
| 출력 행 / 경기 전체 투구 | 57/250 (22.8%) | 29/355 (8.2%) | 86/605 (14.2%) |
| AI 좌표 있음 / 출력 행 | 43/57 | 15/29 | 58/86 |
| AI 기권 / 출력 행 | 14/57 (24.6%) | 14/29 (48.3%) | 28/86 (32.6%) |
| 사람 표시 / 판단 프레임 | 56/57 | 28/29 | 84/86 |
| 사람 기권 / 판단 프레임 | 1/57 (1.8%) | 1/29 (3.4%) | 2/86 (2.3%) |
| 둘 다 표시 / 둘 다 기권 / 사람만 표시 / AI만 표시 | 43 / 1 / 13 / 0 | 15 / 1 / 13 / 0 | 58 / 2 / 26 / 0 |

근거: E1/E2 `coverage.feed_pitches`, `pitches_in_output`, `assistant.{estimated,unavailable}`, `person.{frames_decided,person_marked,person_abstained,availability}`; P의 `lines_in_output`, `assistant.{estimated,unavailable}`, `frames_decided_by_person`, `{person_marked,person_abstained,availability}`. 전체 투구 합계는 E1+E2이며 무작위 표본이 아니다. J(g)에서도 행·상태·좌표 수를 대조했다.

| 판독·출력 차이 (중앙값 / 90분위) | 849845 · n=43 | 823407 · n=15 | 합산 · n=58 |
|---|---:|---:|---:|
| 미트 점 거리 | 2.1 / 5.1 px | 5.8 / 9.4 px | 2.5 / 6.5 px |
| 사람 앞선 고정, 미트 거리 | 0.057 / 0.139 ft ≈ 0.68 / 1.67 in | 0.111 / 0.185 ft ≈ 1.33 / 2.23 in | 0.063 / 0.164 ft ≈ 0.75 / 1.97 in |
| 공개 출력 vs 사람 변환 좌표 거리 | 0.088 / 0.174 ft ≈ 1.06 / 2.09 in | 0.139 / 0.266 ft ≈ 1.67 / 3.19 in | 0.092 / 0.201 ft ≈ 1.11 / 2.41 in |
| 출력 z − 사람 z, 평균 (거리 통계와 별개) | −0.051 ft ≈ −0.61 in | −0.039 ft ≈ −0.47 in | −0.048 ft ≈ −0.57 in |

근거: E1/E2 `person` 및 P의 `mitt_reading_pixels.distance`, `mitt_reading_feet_same_plate.distance`, `output_vs_person_feet.distance` 각각 `{n,median,p90}`; z는 `output_vs_person_feet.z_published_minus_person.signed.mean`.
중앙값·90분위는 보고서의 **nearest-rank** 규약이다. 인치는 반올림 전 값에 12를 곱했다. S(g)의 `mitt_px_diff`, `mitt_feet_diff_same_plate`, `output_feet_diff`도 원본 점·라벨에서 별도로 재계산해 일치를 확인했다.

**물리 확인은 별도:** E1 포구 공 vs Statcast는 13구 RMS 0.149 ft ≈ 1.79 in이며 사람 검증은 0구다. E2는 2구뿐이라 최소 10구 조건 미달, RMS `null`(미측정)이다. 합산하지 않는다.
근거: E1/E2 `camera_check_catch_vs_statcast.{pitches_used,min_pitches,rms_error_feet,human_verified_count}`. 위 사람 비교의 작은 차이를 물리 정확도로 부르지 않는다.

## 발표에서 말할 수 있는 범위

**확정 검증 설명 문구 — 그대로 사용:**

> 평가 2경기에서 AI와 사람이 모두 표시한 58구의 미트 점 차이 중앙값은 2.5px입니다. 같은 변환 기준의 좌표 차이는 중앙값 약 1.1인치이며, 물리 정확도나 투수 의도를 검증한 값은 아닙니다.

**같은 장표에 함께 표기: 전체 86장 중 AI 출력 58장 / 기권 28장.**

- 화면은 실제 투구 공개 후 가로 위치만 표시한다. 1.1인치는 M3의 x·z 좌표 거리 차이이며, 시연 화면 가로 위치만의 오차 수치가 아니다.
- **금지:** “물리 정확도 1인치”, “투수·포수 의도 검증 완료”, “실시간 자동 동기화·일반 OCR 완성”, “최적 투구·실점 감소 입증”, “화면 연동 검증·9구역 승인 완료”. 실제 화면 점검은 아래 리허설에서 수행한다.

## 예상 질문과 답

1. **왜 압축 경기인가?** 공식 압축 MP4를 확보해 재현 가능한 입력으로 삼았다. 전체 재방송은 MLB.TV 접근이 필요했고 Savant 접근 제한을 우회하지 않았다. 압축 영상에는 타석 마지막 공이 많아 전체 투구의 대표 표본으로 볼 수 없다. 근거: [시연 경기 문서](INTENT_V0_DEMO_849843.md)의 ‘영상’, M3 ‘알려진 한계’, E1/E2 `coverage.selection`.
2. **왜 라벨러가 한 명인가?** 현재 수집한 라벨은 저장소 주인 한 명이 한 번 표시한 자료다. 인력·예산 때문이라는 이유는 기록에 없어 추정하지 않는다. AI 점은 숨겼지만 AI가 고른 프레임에 표시했으므로 사람 간 일치도·재검사 신뢰도·프레임 선정 정확도는 측정하지 못했다. 근거: E1/E2 `person.provenance`, M3 ‘라벨 출처 요약’·‘알려진 한계’.
3. **물리 정확도는 얼마인가?** 아직 확정할 수 없다. 사람 비교는 동일한 홉 ② 행렬을 공유한다. 별도 포구 공 검사는 E1의 13구 RMS 0.149 ft뿐이고 사람 확인이 없으며 E2는 미측정이다. 근거: 위 카메라 검사 키, M3 ‘오차를 세 갈래로 나눈다’.
4. **높이가 왜 낮게 나오나?** 포수가 쉬는 글러브를 땅에 두는 장면이라 셋업 높이가 투구 목표 높이가 아닐 수 있다. 별도로 출력 z가 사람 변환 좌표보다 평균 0.048 ft 낮고, 사람 앞선을 고정한 미트 비교는 오히려 +0.025 ft다. 앞선 판독·변환 차이와 목표 정의 문제를 구분해야 한다. 근거: P `output_vs_person_feet.z_published_minus_person.signed.mean`, `mitt_reading_feet_same_plate.z_assistant_minus_person.signed.mean`, M3 ‘높이 편향’, 시연 경기 문서.
5. **AI 기권이 왜 많은가?** 두 AI 판독 에이전트의 합의 규칙뿐 아니라 ‘목표로 내민 미트’의 해석 차이가 있다. AI 기권 28구 중 사람은 26구를 표시했다. ‘땅에 놓인 글러브도 찍는다’는 사람 지시는 AI 출력을 본 뒤 추가한 해석이고 사전 등록되지 않았다. 단순히 안전한 기권이라고 설명하지 않는다. 근거: P `availability.person_only`, `assistant.unavailable`; E1/E2 `person.failure_cases.availability_disagreements`; M3 ‘계획에서 벗어난 점’.
6. **FOX 경기는 왜 차이가 큰가?** 해당 경기에서 낮은 카메라와 다리·흙에 겹친 글러브가 관찰됐지만 원인별 기여도는 측정하지 않았다. 비교 가능한 표본도 E2는 15구다. 팬과 카메라 검사가 미측정이므로 가로의 물리 정확도도 확인되지 않았다. 근거: E2 `person.mitt_reading_pixels.distance`, `camera_check_catch_vs_statcast`; M3 ‘알려진 한계’·‘진행’.
7. **실시간이 가능한가?** 현재는 오프라인 처리다. 릴리스 주변의 영상 창과 투구 후 그래픽을 쓰는 대응 절차가 있어 투구 전 시점만으로 작동하거나 정해진 지연 안에 출력한다고 검증하지 않았다. 근거: M3 ‘고정한 방법’·‘스캔과 feed 대응’, `intent/broadcast_windows.py`, `intent/condensed.py`. 자동 실시간 동기화의 근거로 제시하지 않는다.
8. **9구역 의도는 되나?** 현재 시연 JSONL은 `plate_feet`까지다. 좌표가 있는 행은 `blocked_by=no_batter_zone_bounds`이며 `plate_feet→zone9`의 서비스 계약·타자별 경계가 필요하다. 확정된 이번 시연 범위에서는 9구역을 표시하지 않으며 참고값도 만들지 않는다. 근거: J(849843) `deepest_frame`, `blocked_by`; [계약 수정 문서](INTENT_V0_CONTRACT_FIXES.md), [M2 노트](INTENT_V0_M2_NOTES.md)의 계약 정리. `annotated_image_zone`을 타자 스트라이크존으로 표시하지 않는다.
9. **투수 의도를 검증한 것인가?** 아니다. 화면에 보이는 셋업 글러브를 좌표로 옮긴 대리값이다. 실제 목표·사인·투수 의도 정답이 없고 `is_intent_proxy=true`, `claims.catcher_intent_verified=false`를 유지한다. 근거: J(g)의 해당 키 및 `claims.independent_ground_truth=false`, M3 ‘시연용 짧은 요약’.

## 시연 경기 849843와 화면 점검

**전체 262구 중 JSONL 39구(14.9%)이며 좌표는 27구**다(출력 39구의 69.2%, 전체의 10.3%). 나머지 12행은 unavailable이다. 좌표 있는 27구도 실제 투구 공개 후 x만 표시하며, 높이는 표시하지 않는다. 이 경기에는 M3 사람 라벨 비교가 없다.
근거: D `coverage.feed_pitches`, `pitches_in_output`, `assistant.{estimated,unavailable}`, `person.status=awaiting_labels`; J(849843) `status`, `points.plate_feet`; [시연 경기 문서](INTENT_V0_DEMO_849843.md).

아래는 **Song 화면에서 실제로 확인할 미완료 체크리스트**다. 로컬 스키마 통과를 화면 연동 완료로 바꾸지 않는다.

- [ ] 서비스의 기존 J(849843) 39행과 영상을 `pitch_id`로 대응하고 중복·누락을 확인한다. 순서로 연결하지 않는다. 이전 스키마 검사는 39/39 통과했지만 실제 영상 대응은 별도 점검한다.
- [ ] `status=estimated` 27구에서 `points.plate_feet.x`의 좌우 방향·단위를 `x_convention`과 맞춘다. 높이·9구역·투수 의도는 미표시인지 확인한다.
- [ ] 실제 투구 공개 전에는 좌표를 숨기고 공개 후에만 해당 투구의 x를 표시한다. 이동·재생·되감기 때 이전 투구 값이 남지 않는지 확인한다.
- [ ] 기권 12행은 좌표를 표시하지 않는다. 이전 값·0·보간값으로 채우지 않고 기권 처리를 확인한다.
- [ ] 제목과 확정 검증 설명 문구, 같은 장표의 86장/58장/28장 표기를 확인한다. 내부 `is_intent_proxy=true`, `claims.catcher_intent_verified=false`를 유지한다. `claims.physical_plate_coordinates=true`는 좌표 단계이며 정확도 검증 표시가 아니다.
- [ ] 아래 보고서 선정 예시를 별도 평가 설명에 사용한다. **849845·823407의 예시는 849843 시연 타임라인에 존재하지 않는다.** 로컬 비교 그림의 pitch_id·선정 기준·AI/사람 범례를 확인한다.

| 설명용 예시 | pitch_id | 보고서의 선택 근거 |
|---|---|---|
| 합산 대표 | `849845:10:4` | P `example_cases.cases[0]` |
| 최소 차이 (전형 아님) | `849845:23:6` | P `example_cases.cases[1]` |
| 최대 출력 차이 | `849845:38:6` | P `example_cases.cases[2]` |
| 경기별 대표 | `849845:50:2`, `823407:50:1` | E1/E2 `person.example_cases.cases[0]` |
| 최대 미트 픽셀 차이 | `823407:21:2` | E2 `person.failure_cases.largest_mitt_pixel_differences[0]` |

### 실패 예시: 849845:38:6

S(849845) `per_frame[31]`의 `pitch_id`를 확인했다. `mitt_px_diff=[0.3,-1.0]`의 거리는 **1.044 px**지만, `output_feet_diff=[-0.0103,-0.3221]`에서 높이 차이는 **−0.3221 ft ≈ −3.87 in**다. 사람 앞선을 고정하면 `mitt_feet_diff_same_plate`의 z 차이는 **+0.0274 ft**다.

앞선 폭은 원자료 좌표로 다시 계산했다. `game_849845_intent_points_v0.json`의 `frames[31].plate_corners`는 `[620,360]→[678,360]`(58 px), `game_849845_intent_human_labels_raw_v0.json`의 `frames[31].plate_front`는 `[622,360.8]→[674.1,361.6]`(52.106 px)다. J(849845)의 해당 행 `transform_chain[0].evidence.diagnostics.width_used_px`도 58이다.

따라서 **폭 차이는 5.894 px**이며 인계문의 “약 4 px”와 다르다. S의 `plate_end_px_diff=[2.15,4.22]`는 끝점 차이이지 폭 차이가 아니다. 미트 점은 가까워도 앞선 기하 변환을 포함하면 높이 차이가 커지는 사례다. 앞선 위치·각도도 달라 **폭 하나만의 인과 효과나 미트 판독 3.87인치 오판으로 단정하지 않는다**.

## 기존 재검증 기록 (2026-10-04, 확정 답변 반영 전)

- 기존 의도 테스트 **69 passed**. 보고서를 저장소 밖 임시 폴더에 `python -m intent.accuracy_report --code-commit 6245038 --out <임시>/r.json`으로 재생성해 **30,903바이트 전부 일치**했다. SHA256: `0133f8982111d79340243dfed01572699df6c6786b5392dc718ce96de1f62d48`.
- 별도 계산으로 원본 점·사람 라벨·JSONL에서 S의 비교 가능한 58구 차이와 경기별·합산 지표를 대조했다. 새 영상 판독·라벨·보정·추정은 수행하지 않았다.
- `intent.service_check --validator <저장소 밖 임시>/intent_8771c06.py`에 세 JSONL을 주고 `--out` 없이 실행했다. **849843 39/39, 849845 57/57, 823407 29/29, 총 125/125 통과**, 실패 0. 검증 결과의 `files[].{lines,passed,failed}`가 근거다.
- 2026-10-04 조회에서 SongRoute/pitcheezy의 `main`과 `demo/ws-2026` 모두 `apps/observer/backend/observer_app/intent.py`의 마지막 변경은 `8771c06e4e4bf57f63ccab6482ecf8c6658e7fda`였다. 양쪽 파일과 지정 버전 SHA256은 모두 `52f46e9ae09d6f3297c3ac6acc26016e34f5788d8dbd75c8864de4a82a15609d`로 같다.
- 이는 해당 검사 함수의 **스키마 검증**이다. 보조 import를 제공하는 검사 하네스로 실행했으며 HTTP 서비스·실제 적재·화면 표시까지 검증한 것은 아니다. 선택 사항인 map/assemble/calibrate/run 재실행은 이번에 하지 않았다. 고정 M3 파일은 변경하지 않았다.

## 전달 자료와 일정

- **10/5 12:00 KST까지:** [CV 요약 한 장 PPTX](demo/intent_cv_summary_20261006.pptx) · [PNG](demo/intent_cv_summary_20261006.png). MLB 화면 없이 처리 과정·핵심 수치·주요 한계를 담고, 위 확정 문구와 86장/58장/28장을 같은 장표에 둔다.
- **현장 로컬 자료:** `outputs/intent_label/demo_examples/rehearsal_local.html`에서 기존 비교 그림 5개를 연다(git 제외). 대표 `849845:10:4`는 본 설명, 성공 `849845:23:6`·실패 `849845:38:6`·FOX 대표 `823407:50:1`·최대 미트 차이 `823407:21:2`는 질문 대응에 쓴다. 각 그림에 pitch_id·선정 기준·AI/사람 표시 범례를 함께 보여 준다. MLB 그림과 로컬 HTML은 공유 링크·공개 자료에 포함하지 않는다.
- **10/5 18:00 KST, 약 20분:** 위 미완료 체크리스트로 영상↔투구 키, 좌우 방향·단위, 공개 전후 표시, 기권 처리, 문구를 리허설한다. 일정이 어려우면 가능한 시간을 공유한다.
- **10/6 16:00 KST, 약 5분:** Song이 맥북·아이폰과 전체 동선을 준비한다. 화면 연결 확인 전에는 연동 완료로 기록하지 않는다.
- 이번 확정 답변 반영에서는 문서·발표 자료만 준비하며, 기존 M3 측정·고정 JSONL을 다시 만들지 않는다. F-4i·M4·판독 방법 변경으로 범위를 넓히지 않는다.
