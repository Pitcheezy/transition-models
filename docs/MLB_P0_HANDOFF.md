# MLB P0 — Codex / Claude 인계 기록

현재 범위는 MLB 우선 개발이다. KBO는 최종 확장 목표로 유지한다.
2026-09-22 Codex가 아래 코드를 구현·검증했다. Claude의 첫 호출은 OAuth 만료(401)로
실행되지 않았다. 이후 사용자가 재로그인을 완료했으나, 비공개 코드 외부 전송에 대한
자동 승인 검토가 리뷰 실행을 거부해 구체적인 전송 승인을 기다리고 있다.
이 Codex 작업에서 수신한 Claude 리뷰 결과는 없다.
사용자는 별도 Claude 점검이 5시간 사용 한도로 중단됐다고 보고했다. 그 세션의 파일 변경과
검토 결과는 여기서 확인하지 못했다. 재개할 때 먼저 보존·대조하고,
[새 Claude 재개 프롬프트](CLAUDE_RESUME_PROMPT.md)를 사용한다.
[로컬 검토와 HTTP 수정](MLB_P0_REVIEW_2026-09-22.md)을 참고한다.
2026-09-22 Claude Code가 [재개 프롬프트](CLAUDE_RESUME_PROMPT.md)에 따라 3번 타석 주석을
추가했다(아래 체크포인트 7). 이전 Claude 전체 점검 세션의 파일 변경은 이 저장소에 없었다
(작업 트리 깨끗, HEAD 6a07125 확인 후 시작).

**2026-09-24 Codex 인계**: Claude Code가 사용량 크레딧 소진으로 멈췄다. Codex는 [CODEX_RESUME_PROMPT.md](CODEX_RESUME_PROMPT.md)를
그대로 받아 이어간다(체크포인트 23·24).

남은 작업의 단일 목록은 [../CHECKLIST.md](../CHECKLIST.md)다. 이 문서는 교대 기록이고,
체크리스트는 현재 상태와 다음 한 단위를 담는다. 둘을 같은 커밋에서 함께 갱신한다.

## 교대 원칙

- 한 번에 한 도구만 코드를 수정한다. 다른 도구는 명시한 커밋을 읽고 리뷰한다.
- AGENTS.md, docs/MLB_P0.md, docs/PREPITCH_CONTRACT.md,
  docs/OPERATIONAL_VALIDATION_2026-09-21.md를 먼저 읽는다.
- 브랜치는 `codex/fix-point-label-alignment`. 검증한 단위마다 커밋·푸시한다.
- 원본 영상, 데이터, 모델 캐시, 로그인 정보는 새로 Git에 넣지 않는다.
- 독립 스트라이크·볼·파울 확률과 목표 위치는 현재 미지원이다. 0으로 대체하지 않는다.
- 한도 약 20%에서는 인계 기록을 갱신하고 약 10%에서는 새 대형 작업을 시작하지 않는 것을
  운영 기준으로 삼는다. 서비스의 실제 한도·복구 시각은 별도로 확인한다.
- 두 도구 모두 제한되면 검증된 Python 작업은 별도 터미널에서 로그를 남겨 실행하고,
  영상 주석은 JSON으로 내보낸다. 자동 유료 전환·크레딧 사용은 하지 않는다.

## 완료한 체크포인트

1. `6fe5fbc`: 경기 747139의 322개 투구를 공식 feed와 Statcast ID로 연결했다.
   투수·타자·구종을 대조하며 중복/누락/충돌은 성공으로 처리하지 않는다.
2. `bb4fa75`: 엄격한 투구 전 상태 규약과 CLI/웹 공통 추천 서비스를 구현했다.
   기존 Strike에 파울이 포함되는 의미 문제를 드러내고 지원 범위 밖 추천을 보류한다.
3. 수동 웹 시연: 실제 운영 MLP 앙상블 → 구종 후보별 확률 → 추천 → 화면까지 연결했다.
   예시 SL 추천 / 피안타 약 7.12%. 입력 변경 시 기존 결과를 지운다.
4. 공식 MLB 전체 경기 입력과 첫 투구 클립을 점검했다. Chrome 실제 영상 재생 확인.
   전체 파일은 저장하지 않았으며 Codex 내장 브라우저 영상 재생은 실패했다.
5. 자료 점검 재현 CLI와 별도 8종 투구 관찰 정답 생성기를 추가했다.
   정규시즌 2,142,792행 중 2,135,726행 정답 생성, 자동 판정 6,796행 및 포수 방해
   270행 제외, 알 수 없는 유형 0행. 기존 10종 모델을 수정하거나 재학습한 결과는 아니다.
6. **중계 시각 주석**: `scripts/63_annotate_broadcast.py`와 브라우저 도구 구현.
   실제 SNY 영상 첫 두 타석에서 8개 시각 확인, 1개 판단 화면 확인 불가, 313개 미검토.
   두 번째 타석의 세 투구는 모두 주석 완료. 1/6은 통계 그래픽 때문에 보류했다.
   [결과·재개 명령](MLB_BROADCAST_TIMING.md). 주석 저장·복원·내보내기·출처 불일치 거부를
   Chrome에서 확인했고 CLI로 투구 ID·시각 순서·완전 타석 여부를 검증했다.
7. **3번 타석 시각 주석 (Claude Code, 2026-09-22)**: 데스크톱 앱 내장 브라우저에서
   `http://127.0.0.1:8772` 주석 페이지의 실제 SNY 영상을 재생해 Vientos 타석 3구(3/1, 3/2, 3/3)의
   판단·릴리스 시각을 추가했다. Git 저장 주석을 먼저 불러와 보존했고 기존 9개 항목은 바뀌지 않았다.
   누적 **11개 시각 확인, 1개 확인 불가, 310개 미검토**, 완전 타석 2·3.
   실행한 검사: `63_annotate_broadcast.py check --require-pa 3` 통과(검증 보고서 갱신),
   `--require-pa 2` 통과, `--require-pa 1` 예상대로 실패, `pytest tests/test_broadcast_timing.py`
   23 passed. 코드 변경 없음(JSON·검증 보고서·문서만)이라 전체 check_project는 재실행하지 않았다.
   내장 브라우저 제약: 탐색 직후 스크린샷 타임아웃이 잦고 zoom 크롭 미지원, 입력 포커스 시
   페이지가 스크롤돼 프레임마다 상단으로 되돌려 캡처했다. 8772는 이미 실행 중이던 같은
   주석 페이지 서버를 재사용했다.

8. **PA 4 시각 주석 (Claude Code, 2026-09-22)**: 1회말 Megill vs Harris II 2구(4/1, 4/2)를 추가했다.
   누적 **13개 시각 확인, 1개 확인 불가, 308개 미검토**, 완전 타석 2·3·4.
   4/1 328.0→331.4초, 4/2 345.0→348.2초, 각 ±0.25초.
   판독을 위해 브라우저에서 점수판 영역을 canvas로 3배 확대해 카운트·아웃·주자·타자 배너를 확인했다
   (4/1은 `MEGILL P:0`으로 첫 투구임을 확인). 내보낸 JSON과 저장 파일이 모든 항목의 ID·상태·시각
   해시까지 일치하는지 대조했다.
   **중요 관찰**: feed UTC 간격과 영상 재생 초 간격이 맞지 않는다. PA 3 마지막 투구(17:15:15, 영상 293.1초)와
   PA 4 첫 투구(17:17:41) 사이 wall-clock 146초가 영상에서는 약 35초였다(이닝 교대 구간 편집).
   UTC 외삽으로 처음 찍은 지점은 PA 5 후반이었다. 탐색 참고로만 쓰라는 기존 규칙이 실제로 필요하다.
   실행한 검사: `check --require-pa 4` 통과(보고서 갱신), `--require-pa 3`·`2` 통과,
   `--require-pa 1` 예상대로 실패, `pytest tests/test_broadcast_timing.py` 23 passed. 코드 변경 없음.
   남은 작업 목록은 [../CHECKLIST.md](../CHECKLIST.md)에서 관리한다.
9. **PA 5 시각 주석 (Claude Code, 2026-09-22)**: 1회말 Megill vs Albies 6구(5/1~5/6)를 추가했다.
   누적 **19개 시각 확인, 1개 확인 불가, 302개 미검토**, 완전 타석 2·3·4·5.
   5/1 356.5→358.6, 5/2 370.0→373.2, 5/3 390.0→393.0, 5/4 410.0→413.0, 5/5 430.5→431.65,
   5/6 450.0→453.0초, 각 ±0.25초. 내장 브라우저 스크린샷이 불안정해 video.crossOrigin=anonymous
   재로드 후 canvas drawImage로 640px 프레임을 임시 로컬 수신 서버(8799)에 저장해 판독했다
   (저장소 코드·페이지는 수정하지 않음, 임시 파일은 커밋하지 않음).
   브라우저 localStorage 복원본은 4/1 note가 커밋본과 달랐다(초안). 기존 14개 항목은 Git 커밋본을
   유지하고 5/1~5/6만 덧붙였으며 diff는 annotator 문자열 외 순수 추가다.
   관찰: 5/1은 356.0초 디졸브 직후, 5/5는 글러브 클로즈업 뒤 430.5초에 와이드샷 복귀로
   판단-릴리스 간격이 약 2.1초·1.2초. UTC 외삽(6구 예상 ~475초)은 실제 453.0초와 다시 불일치.
   실행한 검사: `check --require-pa 5` 통과(보고서 갱신), `--require-pa 4` 통과,
   `--require-pa 1` 예상대로 실패, `pytest tests/test_broadcast_timing.py` 23 passed. 코드 변경 없음.
10. **I-0/I-5 통합 준비 + B 점수판 평가셋 (Claude Code, 2026-09-22)**: 동료 레포 `main` 9d09694 재확인(변경 없음).
    [TEAMMATE_PITCHEEZY_2026-09-22.md](TEAMMATE_PITCHEEZY_2026-09-22.md) §9에 ① 8765 최소 서비스 요청·응답(코드 기준),
    ② 지원 투수 6명·학습 2023-05-15~2025-04-30·보정 ~06-30·profile_cutoff 2025-04-30과 시점 함의(747139는 학습 창 안이라
    사전 예측 성능으로 제시 불가), ③ 공통 경기 후보(코호트 선발 42경기, 기본안 2025-08-17 TB@SF Webb)를 사실/기본안/질문으로
    구분해 기록했고, 이전 분석 정정과 동료 확인 항목(`prepare.py:49`→`pa_rewards` 구원투수 교체 반이닝 오판 가능성, 미측정)을 남겼다.
    질문은 작성만 하고 전송하지 않았다. 동료 저장소는 읽기 전용으로만 접근했다.
    B: `src/data/scoreboard_evalset.py`(규약: 검증된 timing 행만, 라벨은 manifest pre_state 기록 메타데이터·OCR 아님,
    상태 visible_checked/visible_unstated/occluded/unreviewed, 채점은 coverage·attempt·accuracy·error·abstain 분리),
    `scripts/64_build_scoreboard_evalset.py` build/check/score, `docs/results/mlb_p0/game_747139_scoreboard_evalset.json`
    (322 중 검토 20 / 평가 가능 19 / 가림 1 / 미검토 302, 완전 타석 2~5).
    실행한 검사: ruff check/format, `pytest tests/test_scoreboard_evalset.py` 5 passed, `check_project.py --cpu-only` 273 passed, 2 deselected,
    `64 build` 후 `64 check` 통과. 주석 확대는 하지 않았다(A-4는 공통 경기 결정 전까지 한 타석 단위).

11. `8f82f3c`: B-4·B-5 점수판 평가셋 판정 기준·분모 보완(Claude Code, 2026-09-22).
    note의 "scoreboard" 문자열로 확인 여부를 판정하던 규칙을 없앴다. 새 입력
    `docs/results/mlb_p0/game_747139_scoreboard_review.json`(`mlb_scoreboard_review_v1`)에 판단 프레임에서
    **사람이 점수판 bug를 읽은 값**을 필드별 `observed`(null = 판독 불가)·`readability`·검토자·방법과 함께 적는다.
    B-4의 PA 1 다섯 구(76.0·88.0·102.8·119.0·134.5초)를 in-app 브라우저 캔버스 프레임으로 받아 bug를 3배 확대해 읽었고
    (0-0/0-1/0-2/1-2/2-2, 0아웃, 주자 없음, ▲1, NYM 0·ATL 0), 같은 방법으로 PA 2~5의 14구도 다시 읽었다. 19구 × 10필드
    전부 manifest 라벨과 일치(`label_conflicts` 0). PA 1/6은 `occluded` 유지. 추정으로 채운 값은 없다.
    평가셋 v2(`mlb_scoreboard_evalset_v2`, `src/data/scoreboard_evalset.py`): confirmed 필드만 평가 대상이고 분모는 필드별이다.
    `excluded`(occluded / scoreboard_unreviewed / no_confirmed_field)·`label_conflicts`를 항목과 분리해 싣고, 제외 투구·미확인
    필드에 대한 예측은 `non_evaluable_attempts`로만 센다. 분모 정의는 모듈 docstring·docs/MLB_BROADCAST_TIMING.md·`score`
    출력의 `denominators`에 같은 문자열로 들어가며 테스트가 셋을 대조한다: `coverage = evaluable / total_pitches`,
    `attempt_rate = attempted / evaluable`, `correct_rate = correct / evaluable`, `error_rate = wrong / evaluable`,
    `abstain_rate = abstained / evaluable`(합 = 1), `accuracy = correct / attempted`(시도 없으면 null).
    CLI `scripts/64_build_scoreboard_evalset.py`에 `review-check` 모드와 `--review` 입력을 추가했다.
    동료 문서 §9: 지원 투수 6명은 `mlb_cohort_proposal.json`(제안 파일) 기준이라 **잠정**으로 정정 — 실제 목록은 번들 생성 시
    `select_cohort()`가 쓴 `metadata.json["pitchers"]`이며 `GET /metadata`로만 확정. 42경기는 잠정 후보 유지. 서비스가
    127.0.0.1:8765에만 바인딩하는 사실을 기록하고, 우선순위 요청 문안(실제 metadata → 요청·응답 예시 → 지원 경기 목록·영상
    확보 → 맥미니 주소·실행 위치 → 후순위 질문)을 작성했다(**미전송**). 동료 `main`은 9d09694 → 804f523(문서 3커밋:
    roadmap.md 신설, decisions D43~D45, plan.md; 코드·번들·서비스 변경 없음)으로 읽기 전용 확인.
    실행한 검사(실제 결과): 변경 파일 ruff check/format 통과, `pytest tests/test_scoreboard_evalset.py` **7 passed**,
    `check_project.py --cpu-only` **275 passed, 2 deselected**(42.0초), `64 review-check`(19 readable) → `64 build` →
    `64 check` 통과. 주석 확대(A-4)는 하지 않았다.

12. `9ff2181`: A-4 PA 6(Ozuna) 6구 시각 주석 + A-w 프레임 추출 도구(Claude Code, 2026-09-23).
    방식: 사용자가 Workflow(ultracode)를 켠 Fable 5.1 세션에서 태그 모델 Opus 5(`claude-opus-5`) 주석 에이전트 1명이
    ffmpeg 단일 프레임 추출(원격 MP4, 재생 초)로 6구의 판단·릴리스 프레임을 찾고, 투구마다 독립 검증 에이전트 2명
    (시각 렌즈: 판단 프레임 정지 자세·릴리스 브래킷 재확인 / 점수판·식별 렌즈: bug 값을 직접 읽어 manifest와 대조)이
    반박을 시도했다. 12건 모두 반박 없음(high). Fable 5.1 세션이 판단 6장·릴리스 6장을 다시 뽑아 육안 확인 후
    `docs/results/mlb_p0/game_747139_timing.json`에 6행, `game_747139_scoreboard_review.json`에 필드별 판독 6행을 추가했다.
    결과: 25 확인 / 1 확인 불가 / 296 미검토, 완전 타석 2~6. 판단 482.5·534.5·556.2·577.3·616.2·671.0 s,
    릴리스 483.78·535.55·557.33·578.35·617.25·672.28 s(±0.15, 브래킷 0.05~0.10 s). 평가셋 v2: timing 26 / 리뷰 25 /
    10필드 모두 confirmed / 라벨 충돌 0. feed UTC는 탐색 출발점으로만 썼고 초로 변환하지 않았다.
    관찰: 476–480 s "JULY 27" 회상 그래픽 뒤 1구의 살아있는 판단 창은 약 2.5초; 572–576 s는 3루측 광각(라이브);
    601–603 s 1루 견제(투구 아님, P:12 유지); ffmpeg 원격 range 읽기가 간헐적으로 "partial file"로 실패해 재시도 필요.
    A-w: 페이지 확대 뷰 대신 `scripts/65_grab_broadcast_frames.py`(timing JSON의 media_url 바인딩, 프레임 재사용,
    3회 재시도, `_full`/`_bug` 몽타주)로 결정. 테스트 3개. `outputs/frames/`는 .gitignore.
    실행한 검사(실제 결과): `63 check --require-pa 6` 통과(validation.json 갱신), `64 review-check`(25 readable) →
    `64 build` → `64 check` 통과, `pytest` timing·evalset·grab 3개 파일 33 passed, `check_project.py --cpu-only` 278 passed, 2 deselected.
    다음 한 단위: **A-5 PA 7**(4구, 2아웃, 주자 1루) — 같은 워크플로 방식 권장; 완료 시 1회말 종료(누적 30구).

13. `fc3d18b`: F-3 점수판 OCR v0 프로토타입(Claude Code Fable 5.1, 2026-09-23, PA 7 주석 워크플로와 병행).
    `src/vision/frames.py`(65번의 프레임 추출을 모듈로 이동, 65번은 얇은 CLI), `src/vision/sny_scoreboard.py`(SNY bug 판독기),
    `scripts/66_sny_scoreboard_ocr.py`(templates → predict → score). 아웃·주자·초말은 구조적 판독, 숫자는 검증 프레임의
    글리프 템플릿 최근접 매칭이며 불확실하면 기권(null). 평가셋 25구의 판단 프레임을 `65 --label evalset`로 뽑아 사용.
    템플릿은 PA 1~2(in-sample), 측정은 `66 score --exclude-pas 1 2`로 PA 3~7 held-out 17구: 10필드 모두 오답 0,
    볼 1건 기권(PA 5/6 "3" 템플릿 없음), all_fields correct 16 / abstained 1 / wrong 0. 첫 실행에서는 그 "3"이 "2"로
    매칭돼 오답 1이었고(거리 0.224, 여유 0.079; 정상 글리프는 거리 ≤0.062·여유 ≥0.28) 임계값을 0.12/0.15로 조여 기권시켰다 —
    이 1건은 더 이상 blind 측정이 아님을 코드 주석과 CHECKLIST에 적었다. 결과 파일은 docs/results/mlb_p0/…ocr_v0*.json,
    템플릿 sny_digit_templates_v0.json. 실행한 검사: `pytest tests/test_sny_scoreboard.py`(5 passed, 합성 bug + 실제 프레임
    구조 필드 대조), `tests/test_grab_broadcast_frames.py`(3 passed), ruff, `check_project.py --cpu-only` 283 passed, 2 deselected.

14. `b1ab6a5`: F-3b 점수판 OCR 음성 평가셋(Claude Code Fable 5.1, 2026-09-23, PA 7·PA 8~10 주석 워크플로와 병행).
    `docs/results/mlb_p0/game_747139_scoreboard_negatives.json`: 판단 프레임 밖 12프레임을 65번 프레임으로 뽑아 눈으로 분류
    (bug 없음 7, 라인스코어 대체 1, 컷어웨이인데 bug 보임 4 — 보이는 값은 직접 읽어 기록). `src/vision/negatives.py`
    (검증·채점: false/wrong/correct/missed reads), `66 negatives` 모드. 첫 채점에서 780 s 라인스코어 그래픽이 navy 패널
    게이트를 통과해 아웃 0·주자 False를 자신 있게 냈다(거짓 판독 4). bug 상단 흰 경계선(정상 0.86~0.97 vs 0.07)과 패널 내
    흰색 비율(≤0.09 vs 0.36) 게이트를 추가해 거짓 판독 0, 컷어웨이 40/44 정답(4 기권은 라인스코어의 이닝·득점), 오답 0.
    게이트 추가 후 평가셋 점수 불변(held-out 16/17 정답·1 기권, in-sample 24/25·1 기권). 결과
    `game_747139_scoreboard_negatives_score_v0.json`. 검사: `pytest tests/test_sny_scoreboard.py tests/test_scoreboard_negatives.py`
    (7 passed), ruff, `check_project.py --cpu-only` 285 passed, 2 deselected.

15. `29eef93`: A-v 리드 시간 파생 필드(Claude Code Fable 5.1, 2026-09-23). `63 check` 보고서에 `short_lead_threshold_seconds`
    (1.5)·`short_lead_pitches`·`lead_seconds_min`, 평가셋 항목에 `lead_seconds`. 26구 중 짧은 리드 7(PA 5/5, PA 6 전부) —
    PA 6는 워크플로 주석 에이전트가 "동작 직전 마지막 set 프레임"을 고른 규약 차이로 확인돼 A-v2(가장 이른 set 프레임 규약 확정 +
    PA 6~10 재검토, Opus 5)를 추가했다. 검사: 관련 pytest 36 passed, `check_project.py --cpu-only` 286 passed.
16. `f7dcac6`: F-4 상태 추적 v0(Claude Code Fable 5.1, 2026-09-23). `src/vision/state_tracker.py` + 테스트 3개 +
    데모 `scripts/67_track_scoreboard_state.py`. PA 6 구간 460~535 s를 5초 간격으로 판독기(v0 템플릿)에 넣어 유지·신선도를 확인:
    16프레임 중 판독 13·기권 3(470 OZUNA 인트로 그래픽, 475·480 JULY 27 회상 — 눈으로 확인), 기권 구간에서 마지막 확인 상태(0-0·1아웃·1루)를 유지하며 age 5→10→15 s(15 s에서 stale), 485 s 복귀 시 즉시 재확인, 거부 0·suspect 0. 결과 `docs/results/mlb_p0/game_747139_scoreboard_track_demo.json`(시연). 선수 식별은 F-4a로 분리.
    검사: `pytest tests/test_state_tracker.py`(3 passed), ruff, `check_project.py --cpu-only` 289 passed, 2 deselected.

17. `9271231`: A-5 PA 7(Olson) 4구 주석 → **1회말 완료**(Claude Code, 2026-09-23). 방식은 체크포인트 12와 같다
    (Workflow: Opus 5 주석 에이전트 1명 + 투구별 시각/점수판 렌즈 검증 2명, 반박 시 Opus 5 수리 후 재검증). 사용량 한도로 한 번
    중단됐다가 `resumeFromRunId`로 재개해 캐시된 에이전트는 재사용했다. 4구는 시각 렌즈가 릴리스 763.43을 반박(브래킷 재확인)해
    763.31로 수리됐고 재검증 2렌즈 모두 통과. Fable 5.1 세션이 판단 4장·릴리스 4장을 다시 뽑아 육안 확인 후 통합.
    결과 29 확인 / 1 확인 불가 / 292 미검토, 완전 타석 2~7. 평가셋 v2 timing 30 / 리뷰 29 / 10필드 confirmed / 충돌 0.
    조인표 `docs/results/mlb_p0/game_747139_pitch_timing_join.json`(`scripts/68_export_pitch_timing_join.py`, 30행) 갱신.
    검사: `63 check --require-pa 7` 통과, `64 review-check → build → check` 통과, `pytest` timing·evalset·join 3파일 32 passed,
    `check_project.py --cpu-only` 290 passed, 2 deselected. 다음 주석 단위: A-6(PA 8~10, 2회초) — 별도 워크플로로 진행 중.

18. `9271231`: I-3 Video Lab 스키마 v2 제안서(Claude Code, 2026-09-23, 미전송). Workflow로 Opus 5 에이전트가
    `docs/VIDEO_LAB_SCHEMA_V2_PROPOSAL.md`를 쓰고 검증 에이전트가 팀원 레포(`main` 804f523, 읽기 전용 GitHub API)와 우리
    파일의 경로·행·필드·예시값을 대조(1차 72건 중 5건, 2차 78건 중 3건 반박 → 수리)했다. 조인표는 실제 파일
    `game_747139_pitch_timing_join.json`(30행)과 `scripts/68`·테스트로 제공. 팀원 레포는 수정·클론·실행하지 않았다.

19. `bf5f06b`: H-1 Arrow "멈춤" 원인 규명(Claude Code Fable 5.1, 2026-09-23). Workflow로 새 프로세스 실험 12셀 + 종합 에이전트의
    TLS 슬롯 덤프·`TlsAlloc` 재현·PE 검사 + 검증 에이전트 재현 4회/완화 3회. 결론: 멈춤이 아니라 `0xC0000005` 크래시 — pyarrow 24
    `arrow.dll` 내 mimalloc v3.2.7이 미할당 TLS 슬롯 63을 읽는데, hashlib가 슬롯 8개를 먼저 쓰면 torch DLL이 그 슬롯에 놓인다.
    채택: `src/__init__.py` Windows 가드(torch 전 `import pyarrow`), `tests/test_broadcast_timing.py`에 최악 순서 회귀 테스트,
    `broadcast_timing.py` 주석 정정. 문서 `docs/H1_ARROW_CRASH_2026-09-23.md`. 검사: 새 프로세스 테스트 2개 통과, ruff, `check_project.py --cpu-only` 291 passed, 2 deselected.

20. `0bb442e`: A-6 부분 — PA 8(Nimmo)·PA 9(Alonso) 6구 통합(Claude Code, 2026-09-24). PA 8~10 워크플로(체크포인트 12 방식,
    PA별 Opus 5 주석 에이전트 병렬)가 한도로 두 번 끊겨 `resumeFromRunId`로 재개했고, PA 8·9는 12판정 모두 반박 없음. PA 10은 검증
    재개 중이라 이 커밋에 없다. 결과 35 확인 / 1 확인 불가 / 286 미검토, 완전 타석 2~9. 평가셋 v2 timing 36 / 리뷰 35 / 완전 34
    (PA 8/1은 라인스코어 그래픽 때문에 partial: 이닝·초말·득점만 confirmed) / 충돌 0. 조인표 36행 갱신. Fable 5.1 세션이 판단 6장·릴리스
    6장을 다시 뽑아 육안 확인. 관찰: 이닝 교대 구간이 수 초로 편집돼 top 2 첫 투구의 판단 창은 약 2초, bug는 플레이보다 2~3초 늦게 갱신됨.
    검사: `63 check --require-pa 9`, `64 review-check → build → check`, `68`, pytest timing·evalset·join 33 passed, `check_project.py --cpu-only` 291 passed, 2 deselected.

21. `faa2eed`: A-v2 판단 프레임 규약 v2 적용(Claude Code, 2026-09-24). Workflow(PA별 Opus 5 에이전트 + 투구별 검증, 한도로 세 번
    재개)로 PA 1~7 29구를 재검토: 27구 이동(옛 값보다 0.25~9 s 앞), PA 1/3 유지, PA 2/2는 옛 프레임(투수 클로즈업)이 규약 위반이라 1.25 s 뒤로,
    PA 6/4는 워크플로 값 569.3 s(3루측 광각, 투수 미표시)를 세션이 프레임 확인 후 576.5 s로 정정, PA 6/2는 9 s 탐색 한도(리드 하한).
    **PA 5/5는 unavailable로 변경** — 카메라가 투수 클로즈업에서 430.5 s에 복귀할 때 이미 레그 킥 정점(검증 4건 일치), v1 값은 note에 보존.
    리뷰 파일 frame_seconds·판독값도 새 프레임에서 읽은 값으로 갱신(충돌 0). 결과 34 확인 / 2 확인 불가 / 286 미검토, 완전 타석 2·3·4·6~9;
    리드 최소 1.15 / 중앙값 3.95 / 최대 10.05 s. OCR 재측정(새 프레임): v1 held-out PA 3~8 23구 오답 0·20 정답·3 기권, v0 25구 오답 0·18 정답·7 기권.
    세션 스팟체크 8프레임(216·341.5·525.5·548.95·569.3·663.5·713.75·756.5 s)에서 PA 6/4 문제를 발견해 정정. 검사: `63 check`, `64`, `68`,
    pytest timing·evalset·join·OCR 38 passed, `check_project.py --cpu-only` 291 passed, 2 deselected.

22. `15c67cf`: A-6 완료 — PA 10(Martinez) 6구 통합(Claude Code, 2026-09-24). 판단 901.35 / 916.1 / 936.8 / 956.8 / 972.8 / 995.1,
    릴리스 902.62 / 917.35 / 938.18 / 958.13 / 973.95 / 996.45 s. 1·3·4·6구는 첫 판정에서 "판단 프레임이 이미 레그 킥"으로 반박돼 수리
    (0.1~0.2 s 앞으로) 후 재검증 통과. Fable 5.1 세션이 12프레임을 다시 뽑아 확인. 결과 40 확인 / 2 확인 불가 / 280 미검토, 완전 타석
    2·3·4·6~10(2회초 완료). 평가셋 timing 42 / 리뷰 40 / 완전 39 / 충돌 0. 조인표 42행. PA 8~10은 규약 v2 재검토 대상(A-v3).
    검사: `63 check --require-pa 10`, `64`, `68`, pytest timing·evalset·join·OCR 38 passed, `check_project.py --cpu-only` 291 passed, 2 deselected.

23. `692bd07`: A-v3 — PA 8~10 판단 프레임에 규약 v2 적용(Claude Code, 2026-09-24). Workflow(PA별 Opus 5 에이전트 + 투구별 검증,
    한도로 한 번 재개)로 12구 중 9구를 앞당기고(최대 5.25 s) 3구는 유지. 12판정 반박 없음, 세션이 이동한 8프레임을 다시 뽑아 확인.
    이제 PA 1~10 전부 규약 v2. 리드 최소 1.15 / 중앙값 4.4 / 최대 10.05 s. OCR 재측정: v1 held-out 29구 오답 0·25 정답·4 기권,
    v0 31구 오답 0·18 정답·13 기권, 음성 14프레임 거짓 판독 0. 적용은 세션 스크립트(scratch `apply_av2.py`)로 했고 결과만 커밋한다.
24. `692bd07`: A-7 부분 — PA 11~15 후보와 병합 도구, Codex 인계(Claude Code, 2026-09-24). 2회말 20구를 규약 v2 워크플로로
    주석했으나 검증 에이전트 대부분이 **사용량 크레딧 소진**으로 실패했다. 워크플로 로직이 "한 렌즈만 반환"을 통과로 셌던 것도
    발견했다(PA 12/1·2, PA 13/3). 그래서 20구 전부를 timing에 넣지 않고 `docs/results/mlb_p0/game_747139_timing_candidates_pa11_15.json`
    (미검증 후보, 행별 `verification.status`와 반환된 판정 원문, PA별 주석자 문제점·타석 종료 증거)에 보존했다.
    `scripts/69_append_timing_rows.py`: 후보 파일에서 **모든 투구가 `verified`인 타석만** timing·리뷰에 추가하고 파생 파일을 재생성한다
    (미검증·누락·이미 있는 타석·manifest 불일치 거부). 테스트 `tests/test_append_timing_rows.py` 3개.
    인계 지시문 `docs/CODEX_RESUME_PROMPT.md`(검증 절차, 병합·OCR 재측정 명령, 주의 투구, 규칙, 보고 형식).
    검사: 관련 pytest 7파일 47 passed, `check_project.py --cpu-only` 294 passed, 2 deselected. 파일 수정 권한은 비워 두었다.

25. `06abd0c`: A-7 PA 11~15 20구 프레임 검증·병합(Codex, 2026-09-24). 선점 커밋 `9eb1c66`, 기준 후보 `1573268`.
    기존 JPEG 캐시와 필요한 경계 프레임을 직접 보고 timing·점수판 두 측면을 확인했다. PA 11~12는 세션 확인+추가 릴리스 렌즈,
    PA 13~15는 독립 작업 에이전트 확인+세션 스팟체크. AI 검토이며 별도 사람 간 일치도 측정은 수행하지 않았다.
    **PA 11/1 판단 1034.00→1038.00**: 1037.00/1037.25의 흰 bug 전환이 연속성을 끊고 1037.50/1037.75는 아직 조립 중이다.
    1038.00에서 0-0·0아웃·빈 베이스·2회말·0:0을 직접 읽어 partial→readable로 정정했다(P:N은 이 프레임에서 아직 안 보임).
    릴리스 정정: PA 11/2 1060.80→1060.85, 11/5 1121.53→1121.58, 12/1 1162.45→1162.50, 12/2 1177.50→1177.55,
    15/1 1468.44→1468.50, 15/2 1490.82→1490.90 s. 모두 ±0.15초, 공 분리의 프레임 단위 정답은 아니다.
    PA 13/3의 1258.75 제안은 이미 팔로스루이므로 1258.48 유지. PA 14/1·5의 긴 리드도 표본 검사에서 준비 중단을 발견하지 못해 유지.
    타자 표시 PA 14 Urshela / PA 15 Arcia를 확인했다. 전수 연속 재생은 아니며 일부 PA 11 표본 간격은 최대 2.25초다.
    `69` 전체 dry-run 후 PA 11→15 각각 write 및 63/64/68 재생성·검증 통과. **60 확인 / 2 확인 불가 / 260 미검토**, 완전 PA 2~4·6~15.
    리뷰 60(59 전 필드·PA 8/1 partial), 충돌 0. 후보 rows 0, 원본 후보/과거 notes는 `1573268`, 검증값/수정 전후/증거는
    `game_747139_timing_verification_pa11_15.json`. 검토용 파일은 `outputs/verification/`로 모아 git-ignore 처리했다.
    OCR v1 템플릿(PA 1·2·9) 고정: held-out 50구 중 전 필드 평가 가능 49구 **44 정답·5 기권·오답 0**. 새 20구는 17 정답·3 기권
    (11/1 이닝, 11/2 전 필드, 13/3 볼). 기존 8/2·10/1 이닝 기권이 재실행에서 2로 달라졌으나 과거 프레임 해시 부재로 원인 미확정,
    모델 개선으로 해석하지 않는다. 현재 캐시의 반복 예측은 60/60 동일. `..._ocr_v1_provenance.json`에 해시·환경·재현 한계를 보존했다.
    음성 평가: 14프레임, 판독 불가 96필드 거짓 판독 0, 판독 가능 44필드 40 정답·4 기권·오답 0. 템플릿·OCR 코드는 변경하지 않았다.
    첫 전체 검사에서 검토자를 Claude Code로 고정한 테스트 1건이 실패했다. `tests/test_scoreboard_evalset.py`를 투구 키별로
    원본 리뷰의 실제 검토자 보존을 확인하도록 고쳐 교대 작업을 지원했다. 최종 `check_project.py --cpu-only` **294 passed, 2 deselected**,
    Ruff 47경로 및 변경 테스트 파일 Ruff 통과, 문서 반영 후 체크리스트 가드 4 passed. Windows 실행은 `PYTHONIOENCODING=utf-8`, uv 사용자 캐시 접근 제한은
    `uv --cache-dir .cache/uv run --frozen ...`으로 작업 폴더 캐시를 사용해 해결했다.
    다음 단위 **PA 16~19 10구**. 수정 권한 반납, 다음 첫 명령은 아래 '남은 순서'와 `CODEX_RESUME_PROMPT.md` 참조.

26. `eb1cdf6`: A-7b 3회초 PA 16~19 10구 검토·병합(Codex, 2026-09-24). 기준 `1796873`, 선점 `0746fab`.
    PA 16은 세션 직접 판독 뒤 다른 에이전트 교차검토, PA 17~19는 타석 담당 에이전트 판독 뒤 세션이 판단/릴리스/bug 증거를 직접 확인.
    **8구 annotated + 2구 unavailable**. PA 16/2는 클로즈업에서 레그 킥 이후 복귀, PA 17/1은 리플레이/로고가 투구 전 창을 가림.
    불가 2구의 시각은 null이며 리뷰/평가 입력을 만들지 않았다. PA 16/1 d1590.50 라인스코어는 읽히는 4필드만 기록(partial).
    PA 18/1 d1706.25·PA 19/4 d1817.50은 투수/타자/bug를 포함하는 라이브 광각. PA 19/3은 타임 후 새 창 d1803.00.
    최종 PA 19/5 릴리스 **1850.16 s**. 모든 새 릴리스 수동 오차 ±0.15 s. 준비 구간 최대 1초 간격 표본 검토이며 연속 재생·사람 간 일치도 검증 아님.
    69 dry-run, PA별 write와 63/64/68 재생성 통과. **68 확인 / 4 불가 / 250 미검토**, 완전 PA 2~4·6~15·18~19.
    리뷰 68(66 전 필드, PA 8/1·16/1 partial), 충돌 0. 기존 62 timing행과 60 review행 보존. 새 후보 rows 0,
    검증 근거는 `game_747139_timing_verification_pa16_19.json`; 프레임은 로컬 캐시이며 전체 MP4를 받지 않았다.
    원격 지연을 줄인 임시 split/trim 추출은 기존 65의 단일 프레임과 1590.50·1591·1592·1592.85 s JPEG 바이트 일치 확인.
    OCR v1 템플릿(PA 1·2·9) 고정: held-out 58구 중 전 필드 56구 **44 정답·12 기권·오답 0**.
    새 8구 중 6구 이닝 3만 기권, PA 19/2 전 필드 기권(원인 미진단), PA 16/1 라인스코어의 4필드 기권.
    새 판독 가능 74필드 = 54 정답·20 기권·오답 0. 이닝 3 템플릿 부재를 새 한계로 확인했고 이번 데이터로 튜닝하지 않았다.
    음성 14프레임/판독 불가 96필드 거짓 판독 0; 판독 가능 44필드 40 정답·4 기권. 기존 60구 예측 불변, 68구 반복 실행 동일.
    최신 provenance에 현재 입력·출력·코드·템플릿·프레임 해시 및 과거 8/2·10/1 미해결 변동의 Git 기록을 연결했다.
    유지보수: 합성 PA 20 병합 시험을 실제 PA 20 이후 주석과 분리하고 모든 후보 파일을 검사. 실제 전체 주석 검사는 유지한다.
    검사: `check_project.py --cpu-only` **295 passed, 2 deselected**, 변경 테스트 Ruff 통과. 임시 캐시 정리 중 Windows 기본 cp949 읽기 오류는
    UTF-8 명시 후 해결했고, 캐시 복사/예측/채점을 다시 실행한 최종 결과만 위에 기록했다.
    수정 권한 반납. 다음 단위 **PA 20~26(3회말 29구)**; F-3a에는 숫자 3용 v2를 별도 평가하는 후속 작업을 기록했다.

27. `5f69f26`: A-7 3회말 중 PA 22·23·25 7구 검증·병합(Claude Code, 2026-09-25). 선점 `3e395b2`. 세션 Opus 5.5, 주석·수리 에이전트 Opus 5.
    타석별 Opus 5 주석 → 투구마다 두 검증 렌즈(시각·점수판/식별; 불가 행은 가용성) **모두 반환·통과** → 세션이 투구별 리뷰 시트와 확대 크롭을 직접 확인.
    **6구 annotated + PA 22/1 unavailable**. 22/1은 홈런 리플레이 → SNY 로고 와이프 아래에서 이미 레그 킥, 세 시각 null.
    세션 정정: 22/1 note의 릴리스 서술(2197.70~.80 → 약 2197.50)과 비판단 프레임 observed/readability를 null로. 23/1은 렌즈 반박→수리(릴리스 2255.95, 동작 2254.72).
    69 dry-run → PA별 write, 63/64/68 재생성(uv 환경 재실행 결과 바이트 동일). **74 확인 / 5 불가 / 243 미검토**, 완전 PA 2~4·6~15·18~19·23·25.
    리뷰 74(72 전 필드, PA 8/1·16/1 partial), 충돌 0. 기존 timing 72행·리뷰 68행 보존. 후보 파일 rows 0(PA 20·21·24·26은 아직 미기록).
    검증 근거 `game_747139_timing_verification_pa20_26.json`(렌즈 판정·세션 확인 문장·프레임 해시). 프레임은 로컬 캐시.
    OCR v1 템플릿(PA 1·2·9) 고정: held-out 64구 중 전 필드 62구 **44 정답·18 기권·오답 0**. 새 6구 모두 이닝 3만 기권(9/10 정답).
    기존 68구 예측 불변, 74구 반복 예측 동일, 음성 14프레임 거짓 판독 0. provenance 갱신(기준 `3e395b2`).
    검사: `check_project.py --cpu-only` **296 passed, 2 deselected**(새 후보 파일이 매개변수 시험에 추가).
    남은 단위: PA 20(7구)·21(5구)·24(5구)·26(5구) — 워크플로 반박·수리 진행 중. PA 20 릴리스는 약 0.2초 이르게 적혀 시각 렌즈가 반박했다.

28. `ca76e65`: A-7 PA 21·24·26 15구 검증·병합(Claude Code, 2026-09-25). 기준 `5f69f26`. 15구 모두 annotated.
    반박→수리 후 세션 확인: 21/3 d2071.75(홈 뒤 라이브 항공 샷, 한계적), 26/1 d2586.00(타자가 투수를 향한 첫 격자), 21/1·21/4·26/2 동작 시작.
    세션 정정: 24/4 d2460.25(워크플로 2460.50; 양발이 러버에 놓인 첫 격자, 창 안 회전과 같은 기준, 대안은 note), 26/4 note 배너 시각.
    **89 확인 / 5 불가 / 228 미검토**, 완전 PA 2~4·6~15·18~19·21·23~26. 리뷰 89(87 전 필드), 충돌 0. 기존 79 timing행 보존.
    OCR v1 고정: held-out 전 필드 77구 **44 정답·33 기권·오답 0**. 새 15구 모두 이닝 3 기권, PA 24/5 홈 득점 기권(원인 미진단).
    기존 74구 예측 불변, 89구 반복 동일, 음성 거짓 판독 0. provenance 기준 `5f69f26`.
    검사: `check_project.py --cpu-only` **296 passed, 2 deselected**, Ruff 통과; 63 check --require-pa 26, 64 review-check/check, 68 조인 재생성 일치.
    남은 단위: **PA 20(7구)** — 20/6 unavailable 확인, 20/4 판단 프레임은 워크플로 3차 검증 중(렌즈 제안 1949.00~1949.25, 세션 기준 1947.75).

29. `2887a52`: A-7 PA 20 7구 검증·병합 → **A-7 완료, 3회 종료**(Claude Code, 2026-09-25). 기준 `ca76e65`.
    6 annotated + 20/6 unavailable(클로즈업 중 와인드업 시작). 20/1·2·3·5·7 릴리스는 렌즈 반박→수리, 세션 크롭으로 확인.
    세션 정정: 20/4 d1949.25→1947.75(러버 도착 경계 해석, 24/4와 동일; 엄격한 대안은 note), 20/6 note 릴리스·observed null.
    **95 확인 / 6 불가 / 221 미검토**(101구 검토), 리뷰 95(93 전 필드), 충돌 0. 후보 rows 0, merge_history에 PA 20~26 전부.
    PA 20~26 합계: 27 확인·2 불가, 세션 정정 5행(20/4·20/6·22/1·24/4·26/4), 리드 최소 1.60 s.
    OCR v1 고정: held-out 전 필드 83구 **44 정답·39 기권·오답 0**; 3회말 27구 전부 이닝 3 기권, PA 24/5 홈 득점 기권(미진단),
    PA 19/2 전 필드 기권 유지(미진단). 기존 89구 예측 불변, 95구 반복 동일, 음성 거짓 판독 0. provenance 기준 `ca76e65`.
    검사: `check_project.py --cpu-only` **296 passed, 2 deselected**, Ruff 통과; 63 check --require-pa 26, 64 review-check/check, 68 조인 재생성 일치.
    한계: 선택 프레임 AI 검토(연속 재생·사람 간 일치도 아님), 수동 ±0.15 s, 같은 경기 개발 데이터. 러버 도착 경계 해석은 A-y에서 재확인 필요.
    수정 권한 반납. 다음 한 단위: F-3a OCR v2(숫자 3 템플릿, v1과 분리 평가) 또는 진행 순서 표의 독립 단위.

30. (이 커밋): F-3a **OCR v2**(Claude Code, 2026-09-25). 선점 `64b6b56`. CHECKLIST 태그 모델 Fable 5.1 → 실제 작업은 Fable 5.1 워크플로 에이전트
    (제안자 2·심판·진단·빌더·수리), 검증은 세션 모델 렌즈 3개(무결성·판독 정확성·진단) 2라운드, 통합·커밋은 세션(Opus 5.5).
    사전 등록 템플릿 PA = 1·2·9·18(PA 18/1의 이닝 '3' 1개와 '0' 4개 추가). 코드·임계값·v1 파일 불변(출처 기록에 기준 대비 동일 확인).
    같은 held-out(PA 1·2·9·18 제외) 전 필드 82구: v1 44·38·0 → **v2 75 정답·7 기권·오답 0**; 이닝 None→3 32구 외 변화 0. 음성 거짓 판독 0.
    세션 직접 확인: v2 채점 재실행 바이트 동일, '3' 템플릿 렌더링, 3회 bug 10장, 13/3 고립 픽셀(0.129→잘라내면 0.076), 19/2·11/2 윗선·4/1·11/1 테두리 이미지.
    진단 검증 2라운드에서 남은 차단 3건은 진단 보고서 서술(13/3 주원인·휘도 수치·개수) 오류였고 v2 파일과 무관; 정정된 원인만 문서화했다.
    위험: '3' 템플릿 1개, 3-2 여유 최소 0.177, 이닝 '2'의 2위가 '3'으로 바뀌어 13/3 여유 0.171. 새 항목 F-3c(v3 수정)·A-8(4회 19구 주석) 추가.
    새 시험: 저장된 held-out 점수가 템플릿 PA를 제외하는지(v1·v2) 구조 검사. `check_project.py --cpu-only` **298 passed, 2 deselected**, Ruff 통과. 파일: `sny_digit_templates_v2.json`, `..._ocr_v2*.json`, `..._negatives_score_v2.json`.
    수정 권한 반납. 다음 한 단위: **A-8**(Opus 5), 이어서 그 프레임으로 F-3c v3(Fable 5.1).

이 문서와 함께 추가되는 후속 커밋의 해시는 `git log -6 --oneline`으로 확인한다.
최신 Windows CPU 검사: **298 passed, 2 deselected**(체크포인트 30, `check_project.py --cpu-only`, Ruff 통과). 아래 브라우저·서비스 검증은 이전 체크포인트 기록이다.
JavaScript 구문 검사 및 Chrome 수동 입력·실제 추론·9회 이후 추천 보류 확인.
GitHub CI 결과는 해당 커밋의 validation 워크플로에서 따로 확인한다.
주석 모듈을 먼저 import한 새 프로세스에서도 Torch→Pandas 문자열 생성이 성공하는지
회귀 검사한다. 조기 hashlib/urllib.request 초기화로 Windows Arrow가 멈추는 조건을
재현해 주석 모듈의 관련 import를 실제 검증 함수 호출 시점으로 늦췄다.
기존 직접 임베딩 경로의 모든 초기화 문제가 해결됐다는 뜻은 아니다.

전체 경기 322개 상태의 실제 서비스 점검도 완료했다. 188개 추천, 94개는 과거 구종 지원 부족,
40개는 9회 이후 범위 제외로 보류한다. `scripts/62_check_game_service.py`로 재현한다.
기존 고정 2022 프로필은 신규 투수에 대응하지 못하므로 시점 이전 자료만 사용하는 갱신이 필요하다.
62번은 실행 중인 59번 서버를 호출하는 표준 라이브러리 기반 HTTP 검사다.
모델을 별도 새 프로세스에 직접 임베딩한 진단 중 첫 Arrow 문자열 변환 멈춤을 관찰했다.
선행 pandas 초기화로 정상 완료한 실행도 있으나 근본 원인은 미확정이다.
정상인 59번 서버와 HTTP 경로를 유지하고 직접 임베딩 경로는 별도로 조사한다.

## 바로 실행하기

기존 운영 아티팩트가 있는 저장소 루트에서:

```bash
uv run --frozen python scripts/59_serve_manual_demo.py --with-example-video
uv run --frozen python scripts/check_project.py --cpu-only
node --check src/web/static/app.js
```

Chrome에서 `http://127.0.0.1:8770`을 연다. 포트 충돌 시 `--port 8771`.
필수 모델/데이터 경로와 Mac 이관은 docs/MLB_P0.md를 따른다.

## Claude 재로그인 후 첫 작업

아래는 이전 읽기 전용 리뷰 요청이다. **최신 구현을 이어갈 때는 CHECKLIST와
[CODEX_RESUME_PROMPT.md](CODEX_RESUME_PROMPT.md)를 우선한다.** Claude도 같은 절차에서 작업자 이름과
CHECKLIST의 Claude 모델 배정을 적용한다. `CLAUDE_RESUME_PROMPT.md`의 옛 본문은 역사 기록이다.

우선 읽기 전용 리뷰를 맡긴다. 기존 입력 규약을 새로 만들라는 오래된 지시는 사용하지 않는다.
아래 내용을 Claude Code에 전달할 수 있다.

> 현재 브랜치의 6fe5fbc부터 HEAD까지 MLB P0 변경을 읽기 전용으로 리뷰해라.
> AGENTS.md와 docs/MLB_P0_HANDOFF.md, docs/PREPITCH_CONTRACT.md부터 읽어라.
> 투구 ID 대응, 미래 정보 누수, 레거시 확률 의미, 추천 지원 범위,
> HTTP 입력 검증과 UI의 오래된 결과 표시, 새 8종 정답의 타석 종료 사건 구분을 집중 점검해라.
> src/data/mlb_video.py, mlb_sources.py, pitch_observation.py,
> src/inference/prepitch_contract.py, recommendation.py, src/web 및 관련 tests가 범위다.
> 파일을 수정하거나 커밋하지 말고, 재현 가능한 결함을 경로·행·영향과 함께 보고해라.
> 실제 결함이 없다면 없다고 쓰고 검토 한계를 밝혀라. 이후 Codex가 확인하고 수정한다.

## 남은 순서

2026-09-22 변경: C(새 8종 확률 모델)·D(투수 프로필/추천 지원 범위)는 **다른 팀원 담당**으로 이관했다.
Claude/Codex의 순서는 [../CHECKLIST.md](../CHECKLIST.md)의 "진행 순서" 표가 기준이다
(A 1회말 완료 → B 평가셋 → A-w → A/F-3 병행 → E/H → I 통합 검증 → G). 아래 3·4번은 참고용 배경이다.
팀원 레포(SongRoute/pitcheezy) 대조 결과는 [TEAMMATE_PITCHEEZY_2026-09-22.md](TEAMMATE_PITCHEEZY_2026-09-22.md) — 우리 쪽 참조가 없는 별도
트랙이라 I-0(인터페이스 합의)·I-5(시연 경기)·I-6(클래스 대응표)·G-3(통화)를 A/B와 병행해 먼저 진행한다.

1. **영상 시간 주석 확대**: 3회 종료(PA 1~26, 101구: 95 확인·6 불가). 다음은 CHECKLIST **A-8(4회 PA 27–32, 19구)**이며 같은 절차로 진행한다.

```bash
uv run --frozen python scripts/63_annotate_broadcast.py check --annotations docs/results/mlb_p0/game_747139_timing.json --require-pa 19
uv run --frozen python scripts/65_grab_broadcast_frames.py --label pa20_scan --times 1851 1860 1870 1880
```

1850.16 s는 PA 19 마지막 검증 릴리스다. 위 초들은 이닝 교대 이후를 찾기 위한 탐색 표본이며 PA 20의 확정 시각이 아니다.
PA 20~26(3회말 29구, 투수 Megill)을 새 `game_747139_timing_candidates_pa20_26.json`에 미검증으로 기록하고,
직접 확인한 타석부터 `69`로 병합한다. 기존 PA 11~15·16~19 후보 파일은 비었으므로 재병합하지 않는다.
feed UTC를 재생 초로 보간하지 않는다. 상세 절차는 [CODEX_RESUME_PROMPT.md](CODEX_RESUME_PROMPT.md).

2. **기존 영상 재검증**: 옛 오타니 수집기는 CSV `iloc[i]`를 사용했다.
   기존 영상 파일명은 재확인 전 정답이 아니다. 원본 확보 후 playId로 재대조한다.
3. **새 확률 모델(팀원 담당, 수신 후 I-1로 통합 검증)**: 8종 정답을 기존 특징에 투구 ID로 연결하고 시간 분할을 유지한다.
   학습·독립 보정·CE/Brier 검증을 거친 뒤에만 UI의 미지원 확률을 활성화한다.
4. **위치/인식**: 목표 위치와 제구 오차, 타자 특성, 점수판 OCR, 선수·상태 추적을 순차 구현한다.
5. **효용 검증**: 기존 정책 실점 차이 CI는 0을 포함한다. 실제 실점 개선 입증으로 발표하지 않는다.

경기 747139는 이미 기존 test cohort에 포함되어 있다. 개발·시연용이며,
이 경기를 보고 튜닝한 뒤 새로운 독립 검증 성능으로 보고하지 않는다.
