# Codex 재개 프롬프트 — 2026-09-24

Claude Code가 2026-09-24 사용량 크레딧 소진으로 멈춘 지점에서 Codex가 이어받기 위한 지시문이다.
아래 `---` 이하 본문을 Codex에 그대로 붙여 넣는다. 남은 작업의 단일 기준은 [CHECKLIST.md](../CHECKLIST.md)이고,
경위와 실제 검사 결과는 [MLB_P0_HANDOFF.md](MLB_P0_HANDOFF.md) 체크포인트 21~24에 있다.

---

저장소 `Pitcheezy/transition-models`, 브랜치 `codex/fix-point-label-alignment`에서 MLB P0 중계 시각 주석(CHECKLIST A-7)을
이어서 진행해라. 분석만 하고 끝내지 말고, 검증을 통과한 작은 단위를 커밋·푸시까지 끝내라.

## 0. 시작 전 확인 (반드시 이 순서)

```bash
git fetch origin
git status --short --branch
git log -8 --oneline
```

- 작업 트리가 깨끗하고 로컬 전용 커밋이 없을 때만 `git pull --ff-only`로 맞춘다.
- `reset --hard`, `git clean`, 강제 푸시는 금지한다. 미커밋 변경·로컬 전용 커밋이 있으면 먼저 대조하고 보존한다.
- 읽을 문서: `AGENTS.md`, `CHECKLIST.md`(상태 요약 표, 진행 순서, A-7·A-v2·A-v3·B·F-3a, 도구 교대 프로토콜),
  `docs/MLB_P0_HANDOFF.md` 체크포인트 21~24, `docs/MLB_BROADCAST_TIMING.md`("판단 프레임 규약 v2", "프레임 확인 도구",
  "점수판 OCR 프로토타입", "리드 시간 규약").
- 상태 요약 표의 '파일 수정 권한'을 `Codex (착수 날짜, 단위)`로 바꾸는 작은 커밋을 먼저 푸시한 뒤 작업한다.
  Claude Code가 다시 권한을 잡고 있으면 파일을 수정하지 말고 읽기 전용으로만 진행한다.

## 1. 첫 단위: PA 11~15 후보 20구 검증 → 병합

`docs/results/mlb_p0/game_747139_timing_candidates_pa11_15.json`(`mlb_broadcast_timing_candidates_v1`)에 2회말 20구의
판단·릴리스 시각이 **미검증 후보**로 들어 있다. `game_747139_timing.json`에는 아직 없다. 행마다 `verification.status`가
있다: `two_lens_passed_needs_spot_check` 2구(PA 13/1·2), `one_lens_passed` 3구(PA 12/1·2, PA 13/3), `none` 15구.
검증 에이전트 대부분이 크레딧 소진으로 실패했기 때문이다.

투구마다 다음을 **직접 프레임을 보고** 확인한다. 이미지를 볼 수 없는 환경이면 `verified`로 바꾸지 말고 멈춰서 보고한다.

```bash
uv run --frozen python scripts/65_grab_broadcast_frames.py --label cx11_1d --times <d-0.5> <d-0.25> <d> <d+0.5>
uv run --frozen python scripts/65_grab_broadcast_frames.py --label cx11_1r --times <r-0.15> <r-0.05> <r> <r+0.15>
```

(`outputs/frames/<label>_full.png` = 반크기 프레임, `<label>_bug.png` = 점수판 3배 확대. 한 번에 1~8개, 프레임당 약 7초.
원격 MP4 range 읽기가 가끔 "partial file"로 실패하며 도구가 3회 재시도한다. Windows에서는 `PYTHONIOENCODING=utf-8`.)

1. **판단 프레임(규약 v2)**: `d`에서 네 조건이 모두 성립 — 라이브 중계 샷(리플레이·회상·통계 그래픽·클로즈업 아님), 투수가
   러버 위에서 정지(사인 확인 또는 come-set, 레그 킥 전), 타자가 타석 안, 점수판 bug 판독 가능(라인스코어 그래픽이면 partial).
   `d-0.25`(그리고 `d-0.5`)에서는 적어도 한 조건이 깨져야 한다. 둘 다 통과하면 더 이른 프레임을 찾아 `d`를 고친다.
2. **점수판 판독**: `d` 프레임의 bug를 직접 읽어 후보의 `observed`와 비교한다(manifest 값을 베끼지 않는다).
3. **릴리스**: `r-0.15`는 아직 팔이 뒤, `r`은 팔이 뻗고 공이 떠남, `r+0.15`는 팔로스루. 벗어나면 고친다.
4. 통과하면 그 행의 `verification`에 `"status": "verified", "by": "Codex (프레임 확인)", "date": "YYYY-MM-DD"`를 쓴다.
   고친 값은 `note` 끝에 한 문장으로 남긴다. 조건을 만족하는 프레임이 없으면 `status`를 `"unavailable"`로, 시각 세 개를 `null`로 한다.

특히 볼 것: PA 14/1은 리드(릴리스−판단)가 15.65 s로 이상하게 길다(견제·스텝오프로 set이 끊기지 않았는지). PA 11/1(9.3 s),
PA 11/2(8.55 s), PA 14/5(9.15 s)도 길다. PA 11/1은 BOT 2ND 라인스코어 그래픽이라 partial이다. PA 12의 릴리스는
주석 실행마다 값이 달랐다(1162.2 vs 1162.45) — 브래킷을 다시 확인한다.

한 타석의 모든 투구가 `verified`면 병합한다(검증 안 된 행이 있으면 스크립트가 거부한다):

```bash
uv run --frozen python scripts/69_append_timing_rows.py --candidates docs/results/mlb_p0/game_747139_timing_candidates_pa11_15.json --pa 12 --reviewer "Codex frame check + Claude workflow annotator" --annotator-suffix "Codex verification PA12, YYYY-MM-DD" --date YYYY-MM-DD
uv run --frozen python scripts/69_append_timing_rows.py --candidates docs/results/mlb_p0/game_747139_timing_candidates_pa11_15.json --pa 12 --reviewer "Codex frame check + Claude workflow annotator" --annotator-suffix "Codex verification PA12, YYYY-MM-DD" --date YYYY-MM-DD --write
```

`--write`는 timing·리뷰 파일을 저장하고 검증 보고서·평가셋·조인표를 다시 만든다. 병합한 타석의 행은 **후보 파일에서 제거**하고
(테스트 `tests/test_append_timing_rows.py`가 후보와 timing의 중복을 막는다) 파일 상단 `status` 문장에 병합 기록(날짜·PA·커밋)을 남긴다.

병합 후 점수판 OCR을 다시 잰다(새 판단 프레임은 자동으로 받는다):

```bash
uv run --frozen python scripts/66_sny_scoreboard_ocr.py predict --templates docs/results/mlb_p0/sny_digit_templates_v1.json --output docs/results/mlb_p0/game_747139_scoreboard_ocr_v1_predictions.json
uv run --frozen python scripts/66_sny_scoreboard_ocr.py score --predictions docs/results/mlb_p0/game_747139_scoreboard_ocr_v1_predictions.json --exclude-pas 1 2 9 --output docs/results/mlb_p0/game_747139_scoreboard_ocr_v1.json
uv run --frozen python scripts/66_sny_scoreboard_ocr.py negatives --templates docs/results/mlb_p0/sny_digit_templates_v1.json --output docs/results/mlb_p0/game_747139_scoreboard_negatives_score_v0.json
uv run --frozen python scripts/check_project.py --cpu-only
```

오답(`wrong`)이 0이 아니게 되면 숨기지 말고 CHECKLIST F-3a에 사례로 기록한다. 템플릿을 늘리려면 해당 타석을 held-out에서 빼야 한다.

## 2. 다음 단위: A-7 나머지 (PA 16~19 → PA 20~26)

- 3회초 PA 16~19(10구, 투수 Schwellenbach) → 3회말 PA 20~26(29구, 투수 Megill). 3회 종료 시 누적 101구.
- 출발 기준: PA 15 마지막 릴리스 후보 1563.64 s(검증 후 값을 쓴다). 이닝 교대는 영상에서 수 초로 편집돼 있고, 교대 직후
  첫 투구는 count bug 대신 라인스코어 그래픽일 수 있다. 투구 식별은 bug의 카운트·`P:N`(투수 투구 수)·아웃·주자로 한다.
- 새 행은 먼저 새 후보 파일(예: `game_747139_timing_candidates_pa16_19.json`, 같은 스키마)에 쓰고, 1의 방법으로 검증한 뒤 69로 병합한다.
- manifest 사전 상태는 `docs/results/mlb_p0/game_747139_manifest.json`의 `pre_state`(카운트·아웃·주자·이닝·점수)와
  `ground_truth.description`/`events`에서 확인한다. 이것은 탐색 기준일 뿐 판독값(`observed`)으로 베끼지 않는다.

## 3. 지켜야 할 규칙

- feed UTC(`video.event_start_utc`)를 재생 초로 바꾸거나 보간하지 않는다. 탐색 출발점으로만 쓴다(편집으로 실제로 어긋난다).
- 영상으로 확인하지 않은 값을 주석·판독값·OCR 정답으로 만들지 않는다. 불확실하면 `unavailable`/`null`.
- 확인 불가 사례를 지워 커버리지를 높이지 않는다. 미검증을 완료로 표시하지 않는다.
- CHECKLIST C·D는 팀원 담당이다. 팀원 저장소(SongRoute/pitcheezy)는 읽기 전용이며, 팀원에게 메시지를 보내지 않는다
  (요청 문안은 `docs/TEAMMATE_PITCHEEZY_2026-09-22.md` §9 말미, `docs/VIDEO_LAB_SCHEMA_V2_PROPOSAL.md` — 둘 다 미전송).
- 경기 747139는 기존 test cohort에 포함된 개발·시연 자료다. 새 독립 성능으로 보고하지 않는다.
- 한 단위를 커밋할 때 `CHECKLIST.md`(상태 표·항목 `[x]`+커밋 해시·새 항목은 `[추가되었음 · 날짜 · Codex]`)와
  `docs/MLB_P0_HANDOFF.md`(체크포인트: 한 일, 실행한 검사와 실제 결과)를 같은 커밋에 넣는다. 커밋 메시지에 파일 목록을 적는다.
- 작업을 끝내거나 멈출 때 '파일 수정 권한'을 `비어 있음`으로 되돌리고, 다음 도구의 첫 실행 명령을 인계 문서에 남긴다.

## 4. 마지막 보고 형식

1. 검증·병합한 타석과 투구 수(고친 값이 있으면 무엇을 왜)
2. 아직 후보로 남은 투구와 이유
3. 실제로 실행한 검사와 결과(`check_project.py` 합계, OCR held-out 오답·기권 수, 음성 거짓 판독 수)
4. 커밋 해시와 푸시 상태
5. 다음 한 단위
