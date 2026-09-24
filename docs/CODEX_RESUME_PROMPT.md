# Codex 재개 프롬프트 — 2026-09-24

PA 16~19(3회초 10구)를 검토·병합한 뒤 PA 20~26부터 이어가기 위한 지시문이다.
아래 `---` 이하를 다음 도구에 전달한다. 남은 작업의 기준은 [CHECKLIST.md](../CHECKLIST.md),
최신 결과는 [MLB_P0_HANDOFF.md](MLB_P0_HANDOFF.md) 체크포인트 26이다.

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
  `docs/MLB_P0_HANDOFF.md` 최신 체크포인트, `docs/MLB_BROADCAST_TIMING.md`("판단 프레임 규약 v2", "프레임 확인 도구",
  "점수판 OCR 프로토타입", "리드 시간 규약").
- 상태 요약 표의 '파일 수정 권한'을 `Codex (착수 날짜, 단위)`로 바꾸는 작은 커밋을 먼저 푸시한 뒤 작업한다.
  Claude Code나 다른 작업자가 권한을 잡고 있으면 파일을 수정하지 말고 읽기 전용으로만 진행한다.

## 1. 첫 단위: PA 20~26(3회말 29구) 후보 작성 → 검증 → 타석별 병합

현재 timing은 79구(74 annotated / 5 unavailable), 미검토 243구다. 완전 타석은 PA 2~4·6~15·18~19·23·25다.
PA 1/6·5/5·16/2·17/1·22/1은 판단 화면 불가로 남겨 뒀다. PA 8/1·16/1은 라인스코어 partial이다.
PA 11~15·16~19 후보 파일의 rows는 비어 있으므로 다시 병합하지 않는다.
**2026-09-25 Claude Code 진행분**: PA 22·23·25(7구)는 이미 검증·병합됐다(`game_747139_timing_verification_pa20_26.json`, 후보 파일 merge_history).
남은 것은 PA 20(7구)·21(5구)·24(5구)·26(5구)이며, 후보 파일에 아직 행이 없으면 새로 미검증 후보로 쓴다. 이미 병합된 타석은 69가 거부한다.
주의: PA 20 워크플로 주석은 릴리스를 약 0.2초 이르게(글러브 팔 전진을 릴리스로) 적는 경향이 있었다. 릴리스는 던지는 팔이 머리 위에서 앞으로 뻗고 공이 손을 떠난 프레임으로 잡는다.

수정 권한 확보 후 기존 PA 19를 검증하고 그 이후를 영상에서 찾는다.

```bash
uv run --frozen python scripts/63_annotate_broadcast.py check --annotations docs/results/mlb_p0/game_747139_timing.json --require-pa 19
uv run --frozen python scripts/65_grab_broadcast_frames.py --label pa20_scan --times 1851 1860 1870 1880
```

- 마지막 검증 릴리스는 **1850.16 s**다. 이닝 교대가 편집되어 있으므로 feed UTC를 재생 초로 변환·보간하지 않는다.
- PA 20~26은 3회말 29구, 투수 Megill이다. 카운트·P:N·아웃·주자·이닝·타자 표시를 대조해 각 투구를 식별한다.
- 새 파일 `docs/results/mlb_p0/game_747139_timing_candidates_pa20_26.json`을 `mlb_broadcast_timing_candidates_v1`로 만들고
  source·manifest 해시를 기존 파일과 맞춘다. 모든 행은 미검증으로 시작한다.
- `game_pk + at_bat_number + pitch_number` 및 `play_id`로 연결한다. 목록 순서로 짝짓지 않는다.
- manifest pre_state/ground_truth는 탐색·정합성 확인용이다. 화면 observed로 복사하지 않는다.
- 한도가 부족하면 완료한 타석까지 병합·검사·커밋하고 남은 후보는 미검증으로 인계한다. A-7 전체는 PA 26까지 끝나야 완료다.

투구마다 다음을 **직접 프레임을 보고** 확인한다. 이미지를 볼 수 없는 환경이면 `verified`로 바꾸지 말고 멈춰서 보고한다.

```bash
uv run --frozen python scripts/65_grab_broadcast_frames.py --label cx20_1d --times <d-0.5> <d-0.25> <d> <d+0.5>
uv run --frozen python scripts/65_grab_broadcast_frames.py --label cx20_1r --times <r-0.15> <r-0.05> <r> <r+0.15>
```

(`outputs/frames/<label>_full.png` = 반크기 프레임, `<label>_bug.png` = 점수판 3배 확대. 한 번에 1~8개, 원격 요청은 수십 초 걸릴 수 있으므로 동일 MP4/시각 캐시를 재사용한다.
원격 MP4 range 읽기가 가끔 "partial file"로 실패하며 도구가 3회 재시도한다. Windows에서는 `PYTHONIOENCODING=utf-8`.)

1. **판단 프레임(규약 v2)**: `d`에서 네 조건이 모두 성립 — 라이브 중계 샷(리플레이·회상·통계 그래픽·클로즈업 아님), 투수가
   러버 위에서 정지(사인 확인 또는 come-set, 레그 킥 전), 타자가 타석 안, 점수판 판독 가능. 라인스코어 그래픽으로
   일부 필드만 읽히면 `partial`로 허용하되 안 보이는 필드는 `null`로 둔다. `d-0.25`에서는 적어도 한 조건이 깨져야 한다.
   이전 프레임도 통과하면 더 앞에서 실패 경계를 찾아 가장 이른 0.25초 격자 프레임을 고른다. 임의의 탐색 한도에 걸린 시각을
   최초 프레임으로 확정하지 않는다. `d`부터 투구 동작 시작까지 중간 프레임도 본다. 견제·스텝오프·타자 이탈·컷어웨이뿐
   아니라 점수판 전체가 하얗게 지워지는 전환도 조건을 끊는다. 이때 마지막 단절 이후의 첫 유효 프레임을 찾는다.
   다른 라이브 광각도 투수와 타자가 보이면 허용하고 note에 적는다. 확인한 시각과 표본 간격·한계를 남긴다.
2. **점수판 판독**: `d` 프레임의 bug를 직접 읽어 후보의 `observed`와 비교한다(manifest 값을 베끼지 않는다).
3. **릴리스**: 전후 프레임의 팔 위치·공 분리·팔로스루로 브래킷한다. 후보가 벗어나면 추가 프레임을 확인해 고친다.
   방송 영상의 흐림을 감안해 양의 오차 범위를 유지하고 프레임 단위 정답으로 주장하지 않는다.
4. **검증 증거**: 각 투구에 timing 렌즈와 scoreboard/identity 렌즈의 실제 확인 결과·이미지 경로·시각을 기록한다.
   한 렌즈만 반환되었거나 사용량 제한·오류로 결과가 없으면 통과가 아니다. 통과 문구만 믿지 말고,
   최종 병합 담당 세션이 판단·릴리스·점수판 증거를 직접 스팟체크한다. 실제로 수행하지 않은 독립 검증을 적지 않는다.
5. 두 검증 측면과 최종 점검이 끝난 행에만 `verification`의 `"status": "verified"`, 실제 검토자 `by`, 검토 날짜 `date`를
   쓴다. 값이 바뀌면 이전값·새값·이유를 note에 남긴다. 직접 확인한 결과 유효 판단 창이 없으면 `status`는 `unavailable`,
   시각 세 개는 `null`로 두고 근거를 남긴다. 영상을 못 봤다는 이유만으로 unavailable 판정을 만들지 않는다.

한 타석의 모든 투구가 `verified`면 병합한다(검증 안 된 행이 있으면 스크립트가 거부한다):

```bash
uv run --frozen python scripts/69_append_timing_rows.py --candidates docs/results/mlb_p0/game_747139_timing_candidates_pa20_26.json --pa 20 --reviewer "Codex direct frame review" --annotator-suffix "Codex PA20, YYYY-MM-DD" --date YYYY-MM-DD
uv run --frozen python scripts/69_append_timing_rows.py --candidates docs/results/mlb_p0/game_747139_timing_candidates_pa20_26.json --pa 20 --reviewer "Codex direct frame review" --annotator-suffix "Codex PA20, YYYY-MM-DD" --date YYYY-MM-DD --write
```

`--write`는 timing·리뷰 파일을 저장하고 검증 보고서·평가셋·조인표를 다시 만든다. 병합한 타석의 행은 **후보 파일에서 제거**하고
(테스트 `tests/test_append_timing_rows.py`가 후보와 timing의 중복을 막는다) 파일 상단 `status` 문장에 병합 기록(날짜·PA·커밋)을 남긴다.

위 PA 20 예시는 타석별로 반복하며 검토자·날짜는 실제 수행한 내용으로 적는다.
병합 후 점수판 OCR을 다시 잰다(새 판단 프레임은 자동으로 받는다). 최신 수치는 실행 결과와 인계 문서가 기준이며,
이전 PA 범위의 수치를 새 평가셋에 그대로 쓰지 않는다.

```bash
uv run --frozen python scripts/66_sny_scoreboard_ocr.py predict --templates docs/results/mlb_p0/sny_digit_templates_v1.json --output docs/results/mlb_p0/game_747139_scoreboard_ocr_v1_predictions.json
uv run --frozen python scripts/66_sny_scoreboard_ocr.py score --predictions docs/results/mlb_p0/game_747139_scoreboard_ocr_v1_predictions.json --exclude-pas 1 2 9 --output docs/results/mlb_p0/game_747139_scoreboard_ocr_v1.json
uv run --frozen python scripts/66_sny_scoreboard_ocr.py negatives --templates docs/results/mlb_p0/sny_digit_templates_v1.json --output docs/results/mlb_p0/game_747139_scoreboard_negatives_score_v0.json
uv run --frozen python scripts/check_project.py --cpu-only
```

오답(`wrong`)을 숨기지 말고 CHECKLIST F-3a에 사례로 기록한다. 템플릿을 늘리려면 해당 타석을 held-out에서 빼야 한다.
이 판독기는 SNY 한 화면 형식의 프로토타입이며 보편적인 중계 OCR 완료를 의미하지 않는다.

## 2. 병행 가능한 다음 OCR 단위

- 현 v1 템플릿은 PA 1·2·9(숫자 0/1/2) 고정이다. 최신 held-out 전 필드 56구에서 44 정답·12 기권·오답 0.
- 새 3회초 8개 판단 화면 중 6개는 이닝 3만 기권, PA 19/2는 전 필드 기권, PA 16/1 라인스코어는 보이는 4필드도 기권했다.
- F-3a에서 숫자 3을 추가하면 **v2 별도 파일**로 만들고, 사용한 타석을 held-out에서 제외한다. 기존 v1 보고서·범위를 보존한다.
  PA 19/2 전 필드 기권도 원인을 먼저 확인한다. 지금 결과를 보며 조정한 사례를 blind 검증이라고 부르지 않는다.
- 새 평가 실행 후 `..._ocr_v1_provenance.json`의 해시/행 수를 실제 입력에 맞춰 갱신하거나 버전별 출처 기록을 별도로 만든다.
- PA 20~26 완료 후에는 CHECKLIST에서 다음 미완료 단위를 선택한다. 자동 동기화·사람 간 일치도·C/D 모델 완성을 추정하지 않는다.

Windows에서는 `PYTHONIOENCODING=utf-8`, 사용자 캐시가 막히면 `uv --cache-dir .cache/uv run --frozen ...`을 쓴다.

## 3. 지켜야 할 규칙

- feed UTC(`video.event_start_utc`)를 재생 초로 바꾸거나 보간하지 않는다. 탐색 출발점으로만 쓴다(편집으로 실제로 어긋난다).
- 영상으로 확인하지 않은 값을 주석·판독값·OCR 정답으로 만들지 않는다. 확인한 프레임의 판독 불가는 `null`, 미검증은 미검증으로 둔다.
- 확인 불가 사례를 지워 커버리지를 높이지 않는다. 미검증을 완료로 표시하지 않는다.
- CHECKLIST C·D는 팀원 담당이다. 팀원 저장소(SongRoute/pitcheezy)는 읽기 전용이며, 팀원에게 메시지를 보내지 않는다
  (요청 문안은 `docs/TEAMMATE_PITCHEEZY_2026-09-22.md` §9 말미, `docs/VIDEO_LAB_SCHEMA_V2_PROPOSAL.md` — 둘 다 미전송).
- 경기 747139는 기존 test cohort에 포함된 개발·시연 자료다. 새 독립 성능으로 보고하지 않는다.
- 한 단위를 커밋할 때 `CHECKLIST.md`(상태 표·완료 항목과 커밋 해시·새 항목은 `[추가되었음 · 날짜 · Codex]`)와
  `docs/MLB_P0_HANDOFF.md`(체크포인트: 한 일, 실행한 검사와 실제 결과)를 같은 커밋에 넣는다. A-7은 PA 26까지 끝나야 완료다.
  커밋 메시지에 파일 목록을 적고 푸시·원격 동기화를 확인한다.
- 작업을 끝내거나 멈출 때 '파일 수정 권한'을 `비어 있음`으로 되돌리고, 다음 도구의 첫 실행 명령을 인계 문서에 남긴다.

## 4. 마지막 보고 형식

1. 검증·병합한 타석과 투구 수(고친 값이 있으면 무엇을 왜)
2. 아직 후보로 남은 투구와 이유
3. 실제로 실행한 검사와 결과(`check_project.py` 합계, OCR held-out 오답·기권 수, 음성 거짓 판독 수)
4. 커밋 해시와 푸시 상태
5. 다음 한 단위
