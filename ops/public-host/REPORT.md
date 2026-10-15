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
| `usage_summary` 또는 `null` | `summarizeTelemetry`(D1) 결과 `pitcheezy-usage-summary-v1` | 기존 요약 또는 [오프라인 스냅샷 내보내기](EXPORT.md)의 전체 포장 객체를 수용. 원격 D1 취득은 별도 |
| `monitor_state` 또는 `null` | 감시 상태 파일의 `state` | 이벤트·열린 장애·잘린 건수·`last_observed_ms`(마지막 관측) |
| `notice_audit` 또는 `null` | 안내 스위치 운영자 GET의 `audit` | 전환 시각·사유·조작자 |
| `notice_audit_meta`(선택) | 같은 운영자 GET의 `audit_unavailable`·`audit_truncated` | 두 boolean을 그대로 보존. 기존 입력에서 생략하면 감사 완전성은 미확인 |
| `alert_state` 또는 `null` | 알림 상태 파일(v1·v2·v3) | 보존된 최종 시도 행의 모의 확인/미전달/전달 전 정리/순서 대기 수. v3 보존 범위를 함께 확인 |
| `actions[]`, `sources{}`, `commands[]`, `unmeasured[]`, `notes` | 운영자 | 주소·토큰·43자 이상 토큰 모양 문자열이 있으면 거부 |

집계 행은 요약 범위 안의 실제 UTC 날짜, 정수 경기 번호·건수·0 이상 활성 시간을 요구한다. 활성 시간 합계도 안전한 정수 범위 안이어야 한다.
피드백 평가·사유는 수집 API의 고정 선택지만 받으며, 같은 날짜·경기의 세션 집계 또는 같은 평가·사유 집계가 중복되면 거부한다.
잘못된 집계 입력을 0분으로 바꾸거나 음수 시간·임의 평가 문구로 출력하지 않는다.

## 오프라인 스냅샷 입력 (WS-report2)

보고서 입력의 `usage_summary`에는 `pitcheezy-usage-snapshot-v1` 전체 객체도 받을 수 있다:
`schema`, `source_sha256`(소문자 64자리), `coverage="unverified"`, `aggregation="utc_day"`, `usage_summary`(기존 요약) 다섯 필드다.
이 포장과 안쪽 요약은 정해진 필드만 허용하며 생성 시각·날짜·중복/음수/0건 그룹 등을 검사한다.
기존 스냅샷 표시 없는 요약 입력은 이전 동작을 유지한다.

- 관련 날짜·경기의 활성 채널 보존 행이 없으면 `no_data`; 건수·활성 시간·피드백 모두 `null`.
- 행이 있으면 `partial_data`; 남아 있는 채널별 합계만 표시하며 행이 없거나 OFF인 채널은 `null`.
- 둘 다 OFF이면 `collection_off`이며 자료가 있어도 해당 수치를 표시하지 않는다.
- 전체 요약 날짜가 보고 기간을 덮어도 수집/보존 완전성을 입증하지 못하므로 `summary_covers_window=true`가 되지 않는다.
- 한 시간짜리 보고서에도 **겹치는 UTC 날짜 전체 집계**만 제공한다. 정확한 시각 구간 이용량과 수집·보존 누락은 미측정으로 적는다.
- 스냅샷 피드백 행에는 `utc_day`를 유지해 여러 날의 같은 평가/사유를 구별한다.
- 운영자 JSON에만 `usage_snapshot{schema,source_sha256,coverage,aggregation,from_day,to_day,generated_at}`을 보존한다.
  Markdown에는 DB 해시·경로·ID·입력의 자유문구 `limits`를 옮기지 않는다. SHA 일치는 출처 인증이 아니다.

## 출력

`game_<pk>_<from일>_report.md`(이슈 초안)와 같은 이름의 `.json`(기록). 둘 다 새 파일로만 쓰고 덮어쓰지 않는다.

이용 기록 상태는 여섯으로 구별한다. 꺼져 있던 채널의 수치는 `null`(미측정)이며 0으로 쓰지 않는다:

| 상태 | 뜻 |
|---|---|
| `collection_off` | 통계·피드백 수집 모두 OFF — 이용자 수 **미측정**(0명이 아님) |
| `no_data` | 수집 ON이었지만 집계 요약이 없거나, 날짜 범위가 기간을 덮지 않으면서 해당 경기 관측 행도 없음 — **미측정**(0명이 아님) |
| `partial_data` | 요약 날짜 범위가 기간을 일부만 덮지만 관측 행은 있음. 관측한 세션/활성 시간/피드백 합계와 요약 날짜를 보존하고 범위 밖은 **미측정**으로 표시 |
| `feedback_only` | 통계 수집 OFF·피드백 수집 ON — 이용자 수·활성 시간 **미측정**, 피드백 응답만 집계 |
| `zero_rows` | 통계 수집 ON, 집계 기간·이 경기의 opt-in 세션 행이 0개 — **0세션** |
| `counted` | opt-in 브라우저 세션 수·활성 시간 합계(사람 수·검증된 주의 시간이 아님); 피드백 OFF면 피드백은 `null` |

문제 목록은 집계 기간 안의 감시 open/복구 이벤트, 안내 전환 기록, 알림 모의 확인/미전달 수(최종 시도가 기간 안에 속하는 보존 행만; 실제 전달 확인 아님)를 담는다.
비고·명령·조치·동의 문구·미측정·계약 버전·안내 사유·피드백 사유 등 초안에 들어가는 모든 자유 문구에서 주소·토큰 모양을 거부한다.
감시·안내·알림 자료가 없으면 "기록 없음/미측정"으로 쓴다. 증거 라벨은 제목과 본문에 반복된다.
감시 상태는 마지막 관측 시각만 남기므로 그 앞의 기간을 계속 감시했다고 보증하지 않는다(`monitor_coverage`):
`after_window`(기간 뒤 마지막 관측 — 이 시각만으로 기간 중 실행 여부를 확인할 수 없음) ·
`at_window_end`(기간 끝에서 한 번 관측한 증거) · `stopped_in_window`(기간 중 마지막 관측 — 그 이후 미측정) ·
`before_window`/`never`(기간 중 관측 없음 — 장애 유무 미측정) · `unknown`(마지막 관측 시각 없음 — 실행 범위 미측정).
이전 `covers_end` 출력은 `after_window`/`at_window_end`로 바뀐다. 입력 형식은 바뀌지 않는다.
기간 안의 open/복구 이벤트와 마지막 관측은 실제 기록으로 계속 표시하며, **기록 사이의 누락·기간 전체 장애 유무·지속 시간만 미측정**으로 남긴다.
감시를 경기 종료 후 처음 실행하거나 환경 변수 오류 뒤 재개해도 과거 기간이 관측 완료로 표시되지 않는다.

### 안내 감사 입력 예시

운영자 GET 응답에서 배열뿐 아니라 같은 응답의 두 플래그도 옮긴다. 예를 들어 스위치 변경은 성공했으나 현재 버전의 감사 저장이 실패했다면:

~~~json
{
  "notice_audit": [],
  "notice_audit_meta": { "audit_unavailable": true, "audit_truncated": false }
}
~~~

위는 전체 입력 중 해당 필드만 보인 예다. 보고서는 `notice_audit_coverage`를 `absent`/`unknown`/`unavailable`/`truncated`/`available`로 구별한다.
기존 배열/null 입력도 계속 받지만 메타데이터가 없는 배열의 완전성은 `unknown`이다. 조회 실패·잘림·메타데이터 부재는
미측정 목록에 남기며, 전달된 실제 전환 행은 그대로 표시한다. 빈 배열은 **제공된 기록 안에 전환 행이 없음**일 뿐
실제 전환이 없었다는 뜻으로 바꾸지 않는다. 두 플래그가 false여도 과거 모든 감사 저장의 완전성까지 검증하는 도구는 아니다.

### 알림 이력의 보존 범위

v3 입력은 `history_complete_from_ms`(완전한 보존을 추적하기 시작한 시각), `history_pruned_through_ms`(삭제된 행의 가장 늦은 최종 시도 시각),
`last_dispatch_ms`(마지막 실행 시각)를 전달한다. 각 값은 밀리초 정수 또는 null이다. `problems.alerts.history_coverage`는 다음과 같다:

- `complete`: 기간 시작 ≥ 추적 시작, 기간 시작 > 잘린 최종 시각(잘림 null이면 해당 조건 없음), 기간 끝 ≤ 마지막 실행.
- `partial`: v3이지만 위 범위를 충족하지 않음(처음 실행 전·잘린 이력과 겹침·마지막 실행 뒤 등).
- `unknown`: v1/v2 입력. 기존 파일도 계속 받으며, 승격 전 보존 범위를 추정하지 않음.

`partial`/`unknown`이면 **보존된 행 기준, 기간 전체합계 미측정**을 본문과 미측정 목록에 표시한다. 남아 있는 관측값은 버리지 않는다.
`complete`는 위 보존 범위 검사만 통과했다는 뜻이다. 재시도가 `last_attempt_ms`·상태를 덮어쓰므로 전체 시도 횟수나 임의의 과거 시점 상태를 재구성한 결과가 아니다.
모든 출력의 알림 숫자는 **보존된 최종 시도 행 기준**이며, `pending`은 보고기간 당시가 아니라 현재 대기 상태다.

~~~text
node ops/public-host/report-cli.mjs --input <입력.json> --output-dir <폴더>
~~~

## 리허설 — 2026-10-13

[영수증](../../docs/results/ops/ws_report_rehearsal_20261013.json): 실제 로컬 D1(커밋된 migration)에 합성 세션 2개·피드백 1건을 저장해
`summarizeTelemetry`로 요약하고, 실제 감시 상태 기계(open→복구 2이벤트)·모의 알림·합성 안내 감사 2건을 넣어 네 상태(`counted`·`zero_rows`·
`no_data`·`collection_off`)의 초안을 생성했다. `counted`는 세션 2·활성 90,000 ms·감시 2·안내 2건을 기록했다.

## 한계

- 게시·회신·라벨링은 하지 않는다. 사람이 초안을 읽고 발신 승인 범위 안에서 게시한다.
- 원격 D1 자료를 취득하는 CLI는 없다. [로컬 SQLite 내보내기](EXPORT.md)의 전체 포장 객체를 연결할 수 있다. 포장 형식을 벗겨 내부 `usage_summary`만 넣으면 수집·보존 범위 미확인이 사라지므로 금지한다.
- 집계는 opt-in 브라우저 세션이며 사람 수·실제 시청률이 아니다. 실경기 수치는 **미측정**이다.
- 입력의 사실 관계(조치·명령·커밋)는 운영자가 책임진다. 생성기는 형식과 라벨만 보장한다.

## 재현

~~~text
node --test ops/public-host/tests/report.test.mjs
node ops/public-host/rehearse-report.mjs --output .cache/report-rehearsal-new.json
~~~
