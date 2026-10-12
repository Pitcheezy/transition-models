# 경기별 운영 기록 초안 생성 — WS-report1

[협업 규약](../../docs/COLLABORATION_PROTOCOL.md) 6절 "경기 종료마다 이용 기록 요약과 문제 목록을 이슈에 남긴다. 경기 ID·집계 기간·동의/누락 범위·
장애와 조치·커밋/해시/명령·미측정을 포함한다. 수집 OFF/자료 없음은 사용자 0명으로 바꾸지 않는다"를 위한 **초안 생성기**다.
생성기는 파일만 쓴다. 이슈에 게시하지 않으며(자동 게시 없음) 게시 문구·범위는 사람의 발신 승인을 따른다.

## 입력 (`pitcheezy-game-report-input-v1`)

운영자가 모은 재료를 한 JSON에 담는다. 모든 값은 입력에서만 오며 생성기가 숫자를 추정하지 않는다.

| 항목 | 출처 | 비고 |
|---|---|---|
| `game_pk`, `window{from,to}`(UTC, ≤14일), `evidence` | 운영자 | `evidence`는 `synthetic`(합성 자료) / `offline_replay`(오프라인 재생) / `live`(실경기) 중 하나 |
| `collection{telemetry_enabled,feedback_enabled,consent_note,retain_days}` | 배포 설정·운영 기록 | 동의/누락 범위 설명 |
| `usage_summary` 또는 `null` | `summarizeTelemetry`(D1) 결과 `pitcheezy-usage-summary-v1` | D1 내보내기 CLI는 아직 없다(계정 도구로 실행) |
| `monitor_state` 또는 `null` | 감시 상태 파일의 `state` | 이벤트·열린 장애·잘린 건수 |
| `notice_audit` 또는 `null` | 안내 스위치 운영자 GET의 `audit` | 전환 시각·사유·조작자 |
| `alert_state` 또는 `null` | 알림 상태 파일 | 모의 확인/미전달 수 |
| `actions[]`, `sources{}`, `commands[]`, `unmeasured[]`, `notes` | 운영자 | 주소·토큰·43자 이상 토큰 모양 문자열이 있으면 거부 |

## 출력

`game_<pk>_<from일>_report.md`(이슈 초안)와 같은 이름의 `.json`(기록). 둘 다 새 파일로만 쓰고 덮어쓰지 않는다.

이용 기록 상태는 다섯으로 구별한다. 꺼져 있던 채널의 수치는 `null`(미측정)이며 0으로 쓰지 않는다:

| 상태 | 뜻 |
|---|---|
| `collection_off` | 통계·피드백 수집 모두 OFF — 이용자 수 **미측정**(0명이 아님) |
| `no_data` | 수집 ON이었지만 집계 요약이 없거나 요약의 날짜 범위가 집계 기간을 덮지 않음(`summary_covers_window:false`) — **미측정**(0명이 아님) |
| `feedback_only` | 통계 수집 OFF·피드백 수집 ON — 이용자 수·활성 시간 **미측정**, 피드백 응답만 집계 |
| `zero_rows` | 통계 수집 ON, 집계 기간·이 경기의 opt-in 세션 행이 0개 — **0세션** |
| `counted` | opt-in 브라우저 세션 수·활성 시간 합계(사람 수·검증된 주의 시간이 아님); 피드백 OFF면 피드백은 `null` |

문제 목록은 집계 기간 안의 감시 open/복구 이벤트, 안내 전환 기록, 알림 모의 확인/미전달 수(집계 기간 안에 시도한 전달만; 실제 전달 확인 아님)를 담는다.
비고·명령·조치·동의 문구·미측정·계약 버전·안내 사유·피드백 사유 등 초안에 들어가는 모든 자유 문구에서 주소·토큰 모양을 거부한다.
감시·안내·알림 자료가 없으면 "기록 없음/미측정"으로 쓴다. 증거 라벨은 제목과 본문에 반복된다.

~~~text
node ops/public-host/report-cli.mjs --input <입력.json> --output-dir <폴더>
~~~

## 리허설 — 2026-10-13

[영수증](../../docs/results/ops/ws_report_rehearsal_20261013.json): 실제 로컬 D1(커밋된 migration)에 합성 세션 2개·피드백 1건을 저장해
`summarizeTelemetry`로 요약하고, 실제 감시 상태 기계(open→복구 2이벤트)·모의 알림·합성 안내 감사 2건을 넣어 네 상태(`counted`·`zero_rows`·
`no_data`·`collection_off`)의 초안을 생성했다. `counted`는 세션 2·활성 90,000 ms·감시 2·안내 2건을 기록했다.

## 한계

- 게시·회신·라벨링은 하지 않는다. 사람이 초안을 읽고 발신 승인 범위 안에서 게시한다.
- D1 요약을 운영 계정에서 내보내는 CLI는 없다. 실제 경기에서는 계정 도구로 `summarizeTelemetry` 결과를 만들어 입력한다.
- 집계는 opt-in 브라우저 세션이며 사람 수·실제 시청률이 아니다. 실경기 수치는 **미측정**이다.
- 입력의 사실 관계(조치·명령·커밋)는 운영자가 책임진다. 생성기는 형식과 라벨만 보장한다.

## 재현

~~~text
node --test ops/public-host/tests/report.test.mjs
node ops/public-host/rehearse-report.mjs --output .cache/report-rehearsal-new.json
~~~
