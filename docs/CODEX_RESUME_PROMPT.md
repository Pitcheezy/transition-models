# Codex 재개 프롬프트 — 2026-09-27

A-15까지 병합해 경기 747139의 322구를 모두 검토했다: **297 annotated / 25 unavailable / 0 unreviewed**.
PA 79–82의 마지막 19구는 17구 시각 확인·2구 판단 화면 불가다. A-15 결과는
[MLB_P0_HANDOFF.md](MLB_P0_HANDOFF.md) 체크포인트 43과 [MLB_BROADCAST_TIMING.md](MLB_BROADCAST_TIMING.md)를 따른다.
**A-z도 완료했다.** 주석 화면과 scripts 63·65·71의 안내에 영상 재생 초와 feed UTC의 구분을 명시했다.
JS 동작·주석 값·OCR 결과는 바꾸지 않았다. A-z 결과는 HANDOFF 체크포인트44를 따른다.
최근 Claude/Codex 작업은 [대조 감사](CROSS_AGENT_AUDIT_2026-09-27.md)와 HANDOFF 체크포인트46을 따른다.
H-5에서 병합 경로·영상 캐시 출처·A-y 안내 자산 바인딩을 보강했다. A-y 실제 응답은 아직 없고 측정은 대기다.
검토 묶음은 v2이며 scripts72의 기본 출력 `outputs/blind_review/game_747139_ay_v2/`를 사용한다.
원본 주석·기준4파일·OCR 결과는 보존했다. I-6의 의미 계약·검사·변환 거부도 구현했다(HANDOFF47,
[계약 안내](OUTCOME_CLASS_CONTRACTS.md)). 다음 독립 단위는 **F-4a 투수·타자 식별 규약과 평가 준비**다.
남은 작업 기준은 [CHECKLIST.md](../CHECKLIST.md)이며, C·D는 팀원 담당이다.

---

저장소 `Pitcheezy/transition-models`, 브랜치 `codex/fix-point-label-alignment`에서 **CHECKLIST F-4a**를 진행해라.
점수판 상태만으로는 선수 ID가 확인되지 않는다. 화면에서 읽은 선수 정보와 feed 기준값의 출처를 구분하는 규약·평가 준비부터 한다.
새 모델 학습이나 실제 외부 서비스 연결은 이번 범위가 아니다. 동료 저장소를 수정하거나 메시지를 보내지 않는다.

## 0. 시작 전 확인

```bash
git fetch origin
git status --short --branch
git log -8 --oneline
```

- 작업 트리가 깨끗하고 로컬 전용 커밋이 없을 때만 `git pull --ff-only`로 맞춘다.
- `reset --hard`, `git clean`, 강제 푸시는 금지한다. 미커밋 변경·로컬 전용 커밋이 있으면 먼저 대조하고 보존한다.
- 읽을 문서: `AGENTS.md`, `CHECKLIST.md`의 상태 표·진행 순서·A-y·교대 프로토콜,
  `docs/MLB_P0_HANDOFF.md` 최신 체크포인트, `docs/MLB_BROADCAST_TIMING.md`의 판단 프레임 규약 v2·프레임 확인 도구·리드 시간 규약.
- 상태 표의 파일 수정 권한을 `Codex (착수 날짜, F-4a 선수 식별)`로 바꾸는 작은 커밋을 먼저 푸시한다.
  다른 작업자가 권한을 잡고 있으면 파일 수정 없이 상태를 대조한다.

## 1. 다음 작업: F-4a 선수 식별 규약·평가 준비

읽을 자료: `src/data/mlb_video.py`, `src/data/broadcast_timing.py`, `src/data/scoreboard_evalset.py`,
`src/vision/state_tracker.py`, `docs/PREPITCH_CONTRACT.md`, 경기747139 manifest/source/timing/review.
I-6 모듈은 실제 HTTP 연결 없이 독립적으로 준비된 검사기다. 현재 UI를 동료 계약으로 임의 교체하지 않는다.

1. 기존 선수 ID가 manifest/feed에서 온 값인지 화면 판독으로 확인된 값인지 조사하고 명시적으로 구분한다.
   이름·팀·타순·시점·근거 프레임·확인 상태를 가진 작은 식별 평가 규약을 먼저 만든다. 투구 키와 play_id로 연결한다.
2. 이미 확인된 한 타석에서 투구 전 배너가 있는지 실제 프레임으로 확인한다. 없으면 범위를 무작정 넓히지 말고
   불가/미확인으로 기록한다. feed ID를 복사한 값을 화면 판독 정답으로 만들지 않는다.
3. 인식값과 정답 분리·기권·선수 교체·모호한 이름·오래된 상태를 다룬다. 수동 시각으로 정렬된 개발 자료를
   실시간 feed 동기화나 자동 선수 인식 완료라고 부르지 않는다. OCR 구현은 이 근거와 작은 평가셋 뒤에 진행한다.
4. 첫 단위는 규약·작은 검증 가능한 평가 준비까지다. F-4a 전체는 실제 선수 식별 경로가 검증돼야 완료한다.
   CHECKLIST/HANDOFF에 부분 완료·검증·남은 사항을 적고 함께 커밋·푸시한다.

A-y에 실제 별도 검토자 응답이 먼저 도착했다면 원문을 보존하고 아래처럼 검사한다.

```bash
uv run --frozen python scripts/72_prepare_blind_review.py check-response --response <받은_JSON_경로>
```

이후 [고정 비교 규약](BLIND_REVIEW_PROTOCOL.md)을 그대로 적용한다. v1 응답은 자동 변환하지 않는다.
응답이 없으면 수치를 만들지 않는다. 기존 정답을 이미 본 이번 감사 세션이나 합성 시험은 독립 응답이 아니다.
A-y의 선택 표본·비교 규칙·기준 주석은 바꾸지 않는다. 다른 사람에게 묶음을 보내는 것은 별도 요청이 있을 때만 한다.

## 2. 이후 영상 주석을 추가할 때의 규약

경기 747139에는 미검토 투구가 없다. 아래는 **새 영상 또는 명시적으로 지정된 재검토**에만 쓰는 절차다.
완료된 후보 파일을 다시 병합하거나 과거 PA 20 등의 탐색 시각을 현재 작업 지시로 사용하지 않는다.

- `(game_pk, at_bat_number, pitch_number)`와 `play_id`로 연결한다. 목록 순서로 짝짓지 않는다.
- 후보 스키마 `mlb_broadcast_timing_candidates_v1`의 source·manifest 해시를 실제 입력과 맞추고 모든 새 행은 미검증으로 시작한다.
- manifest의 pre_state/ground_truth는 식별·정합성 대조용이다. `observed`는 판단 프레임의 bug를 직접 읽어 기록한다.
- 이미지를 볼 수 없으면 verified로 바꾸지 말고 미검증 후보와 한계를 인계한다. 추출 실패를 unavailable로 바꾸지 않는다.

투구마다 다음을 직접 확인한다.

1. **판단 프레임 v2:** 라이브 화면·러버 위에서 정지한 투수·타석 안 타자·판독 가능한 점수판의 네 조건이 동시에 성립하는
   가장 이른 0.25초 격자를 고른다. 직전 격자는 적어도 한 조건을 깨야 한다. 다른 라이브 광각도 허용하되 식별 한계를 남긴다.
   라인스코어로 일부 필드만 보이면 partial, 보이지 않는 필드는 null이다.
2. **연속성:** 판단부터 동작 시작까지 최대 1초 간격으로 확인한다. 견제·스텝오프·타자 이탈·컷어웨이·점수판 전환으로
   조건이 끊기면 마지막 단절 이후의 첫 유효 프레임을 찾는다. 표본 검사임을 기록하며 연속 재생 검증으로 표현하지 않는다.
3. **릴리스:** 약 0.05초 간격의 전후 프레임에서 던지는 팔·공 분리·팔로스루를 확인한다. 수동 오차 범위를 유지하고
   프레임 단위 정답이라고 주장하지 않는다. 글러브 팔 전진을 릴리스로 오인하지 않는다.
4. **검증 증거:** timing과 scoreboard/identity 두 측면의 실제 확인 결과·이미지 경로·시각·한계를 기록한다.
   한 렌즈만 반환되거나 오류로 결과가 없으면 통과가 아니다. 병합 담당 세션도 이미지를 직접 확인한다.
   AI 에이전트 검토를 사람 간 일치도 측정이라고 적지 않는다.
5. 검증이 끝난 행만 `verification.status=verified`와 실제 검토자·날짜를 적는다. 수정 시 이전값·새값·이유를 남긴다.
   직접 확인한 결과 유효 판단 창이 없으면 unavailable로 두며 decision/release/uncertainty·observed/readability/bug_text는 null,
   비판단 화면에서 얻은 식별 정보는 note에만 남긴다.

`scripts/65_grab_broadcast_frames.py`는 1~8개의 재생 초를 받아 전체/bug 확대 몽타주를 만든다.
`scripts/71_timing_review_sheet.py`로 경계·연속성·릴리스를 묶고 기존 프레임 캐시를 재사용한다.
타석의 모든 행이 verified이면 `scripts/69_append_timing_rows.py`를 dry-run 후 `--write`로 실행한다.
검증 보고서·평가셋·조인표 재생성을 확인한 뒤 병합 행은 검증 기록에 보존하고 후보 rows에서 제거하며 merge_history를 남긴다.
큰 이미지·영상은 Git에 넣지 않는다.

## 3. OCR 평가와 결과 해석

- 현행 판독기는 SNY 한 화면 형식의 **v2**다. v1~v4와 각각의 템플릿·provenance를 보존한다.
- v3는 무회귀 기준 실패, v4는 A-10에서 사전 등록 기준 (1) 실패로 기록됐다. 후속 프레임의 개선으로 과거 판정을 바꾸지 않는다.
- 새 주석 병합 후에는 `scripts/70_refresh_ocr_reports.py --reference <병합 전 커밋> --label <단위> --date <실행 날짜>`로
  모든 버전의 보고서를 갱신한다. 실행 전 커밋 해시를 고정하고 실제 산출물의 분모·정답·기권·오답을 보고한다.
- scripts/70이 새 오판독으로 실패하면 프레임을 직접 본다. 라벨이 맞고 판독기가 틀렸을 때만 원인·증거와 함께
  `game_747139_scoreboard_known_misreads.json`에 기록한다. 실패를 숨기기 위해 템플릿·라벨을 고치지 않는다.
- 경기 747139는 기존 test cohort에 포함됐고 이제 전 경기 프레임을 검토한 **개발·시연 자료**다.
  새 OCR 버전을 이 경기로 수정한 뒤 이 프레임을 새 blind 검증이라고 부를 수 없다.
  새 blind 증거에는 규칙·기준을 사전 등록한 뒤 보는 새 미검토 영상이 필요하다.
- 수동 시각 주석·이 레이아웃의 OCR 결과는 자동 방송 동기화·일반 중계 OCR·독립 모델 성능을 입증하지 않는다.

## 4. 공통 운영 규칙과 마지막 보고

- CHECKLIST C·D는 팀원 담당이다. 팀원 저장소(SongRoute/pitcheezy)는 읽기 전용이며 메시지를 보내지 않는다.
  질문 문안은 `docs/TEAMMATE_PITCHEEZY_2026-09-22.md` §9와 `docs/VIDEO_LAB_SCHEMA_V2_PROPOSAL.md`에 미전송으로 남아 있다.
- 현재 UI의 독립 스트라이크·볼·파울 및 목표 위치 미지원 상태를 유지한다. 실제 실점 개선은 입증되지 않았다.
- CHECKLIST와 HANDOFF를 작업과 같은 커밋에서 갱신한다. 새 항목은 `[추가되었음 · 날짜 · Codex]`를 붙이고
  Claude 실행 모델 태그도 넣는다. 커밋 메시지에 파일 목록을 적고 푸시·원격 동기화를 확인한다.
- 끝내거나 멈출 때 파일 수정 권한을 `비어 있음`으로 돌리고 다음 도구의 첫 행동을 남긴다.
- Windows에서는 `PYTHONIOENCODING=utf-8`, 사용자 캐시가 막히면 `uv --cache-dir .cache/uv run --frozen ...`을 쓴다.

마지막 보고:

1. 완료한 단위와 변경 내용·이유(주석 작업이면 타석·투구 수와 정정값)
2. 미완료·미검증 후보와 이유
3. 실제 검사 결과와 한계(실행한 테스트 합계, OCR을 갱신했다면 분모·오답·기권·음성 거짓 판독)
4. 작업/해시 고정 커밋과 푸시 상태
5. 다음 한 단위
