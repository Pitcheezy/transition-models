# 양쪽 알림 후보 — WS-alert1

[협업 규약](../../docs/COLLABORATION_PROTOCOL.md) 6절 "발행 중단 알림은 둘 다 받는다. 맥미니 원인은 Song, 호스팅 원인은 우리가 먼저 조사한다.
분류가 안 되면 양쪽에 알리고 인계를 남긴다"를 **모의 전송으로** 구현·검증한 기록이다.
실제 연락처·채널·발송 승인은 WS-human1 결정이며 이 모듈에는 주소·토큰이 없다. **모의 전송의 "ok"는 로컬 확인이지 사람에게 전달됐다는 뜻이 아니다.**

## 무엇을 하는가

[감시 도구](MONITORING.md)의 상태 파일(`state.events`, `state.incident`)을 읽어, 아직 처리하지 않은 이벤트를 두 수신자(`song`, `ours`)에게
각각 한 번씩 전달한다. 전달 결과와 시도 횟수는 별도 알림 상태 파일에 남는다.

| 감시 issues | 분류 | 먼저 조사 |
|---|---|---|
| `freshness_*`, `health_missing`, `health_invalid_json*`, `health_invalid_utf8` | `publish_stalled` (발행 중단/지연) | **Song**(맥미니·발행기), 우리는 호스팅 확인 |
| `page_*`/`health_*`의 HTTP·네트워크·시간초과·본문·헤더 오류 | `host_error` (호스팅 오류) | **우리**, Song은 발행기 확인 |
| `access_login_*`, `*_access_session_rejected`, `*_access_gate_without_login` (감시 코드로 세션을 못 열거나 거절됨, WS-monitor2) | `host_error` | **우리**(접근 문·감시 코드) |
| 두 종류가 섞임 또는 모르는 issue | `unclassified` | 양쪽 |
| `*_notice_active` | `notice_active` (정보) | 조치 불필요(사람이 켠 안내) |
| `*_access_required` | `access_gate` (정보) | 조치 불필요(감시 코드 미설정; 게이트 뒤 발행 시각 미측정) |
| `recovered` 이벤트 | `recovered` (정보) | — |

- **중복 억제:** (장애 id, 종류, 수신자)마다 한 번만 보낸다. 같은 장애가 계속 열려 있어도 반복하지 않는다.
- **원인 재분류(WS-alert2):** 감시는 장애를 연 실행의 issues로 범주를 고정한다. 알림 CLI는 감시 상태 파일의 최신 `report`
  (상태에 마지막으로 기록된 실행일 때만; 같은 실행은 한 번만 센다)로 열린 장애의 원인을 따라간다.
  - **두 번 연속 규칙:** 감시가 장애를 여는 기준과 같이, 새 범주가 기록된 실행 두 번 연속 나와야 바꾼다. 한 번짜리 일시 오류는 경로를 바꾸지 않는다.
  - **알림 범주 기억:** 양쪽에 알리기로 마지막 확정한 범주를 장애별로 기억한다(`incidents`). 새 범주가 조치 필요(`publish_stalled`·`host_error`·`unclassified`)이고
    알린 범주와 다르면 양쪽에 **번호 붙은 재분류 알림**을 보낸다(키 `<장애 id>:reclassified:<번호>:<범주>:<수신자>`, `event_kind:"reclassified"`,
    `reclassified_from`). 예전 원인으로 되돌아가는 것도 새 번호로 알린다. 예: 안내 ON 중 열린 장애가 안내 OFF 뒤 발행 중단으로 이어지면 Song 우선 `publish_stalled`.
  - **정보성에서 올리기:** 알린 범주가 정보성(안내·접근 문)인데 기록된 실행 두 번 연속 조치가 필요하면, 원인이 번갈아도 올린다(같으면 그 범주, 다르면 `unclassified` 양쪽).
  - **낮추지 않음:** 정보성 범주는 알린 범주를 대신하지 않는다. 재알림은 마지막으로 알린 범주를 쓴다(발행 중단 중 안내를 켜도 "조치 불필요"로 바뀌지 않음).
  - **대체:** 새 재분류를 알리면 아직 전달되지 않은 이전 재분류는 모든 수신자에 대해 `abandoned`로 정리한다. 늦은 재시도가 새 알림 뒤에 도착해 옛 원인을 남기는 일이 없다.
    메시지에 알림 번호(`announcement`)가 들어간다.
  - **재시도와 정리:** 가장 최근 재분류 알림은 저장된 대기열에서 현재 원인과 무관하게 `max_attempts`까지 재시도한다. 장애가 닫히면 미전달 재분류·재알림은
    `abandoned`로 정리하고(지나간 재알림 창도 같음) 보관 기간 뒤 지운다. opened/recovered 행은 감시가 그 이벤트를 아직 목록에 두는 동안 지우지 않는다
    (지우면 이벤트가 새것처럼 보여 다시 보내진다 — WS-review1 정리 규칙의 결함을 함께 고침).
  - **순서:** 수신자의 opened 알림이 아직 재시도 중이면 그 수신자에게 복구·재분류·재알림을 미룬다(receipt `deferred`). 다른 수신자의 전달은 진행하며 opened가 시도 한도에 이르면 복구를 보낼 수 있다.
  - 형식이 틀린 감시 이벤트·장애는 건너뛰고 나머지를 보낸다(receipt `invalid_events`/`incident_invalid`, 종료 1).
  - report가 없거나 다른 실행의 것이면 원인 추적을 건너뛰고 마지막으로 알린 범주를 유지한다(재알림도 그 범주). 알림 CLI는 감시 CLI를 실행할 때마다 한 번
    실행해야 두 번 연속 규칙이 맞다. 건너뛴 실행은 알아챌 수 없다.
  - 상태 파일은 `pitcheezy-host-alert-state-v3`다(v1·v2는 읽을 때 올림). v3는 보존 범위를 나타내는 `history_complete_from_ms`,
    `history_pruned_through_ms`, `last_dispatch_ms`를 더한다. 신규/승격 상태는 첫 v3 실행부터 기록 완전성의 범위를 시작한다(이전 기록 완전성은 알 수 없음).
    전달 대기 상한은 현재 감시 이벤트 100건×양쪽+현재 재분류·재알림 각 양쪽을 합한 204건이다.
  - **이전 코드로 되돌릴 때는** `alerts-cli.mjs --config <설정> --state <v3 상태> --downgrade-to-v1 <새 파일>`로 v1 사본을 만든다.
    재분류 행·대기를 제거하고 `abandoned`는 시도 소진으로 표시한다. 대기 요약은 v1의 200건 상한에 맞추되 전달 행은 보존한다(기존 디스패처가 감시 이벤트에서 재구성).
    원본은 바꾸지 않는다. **v1은 보존 범위 메타데이터를 표현하지 못하므로 변환 영수증과 경기별 기록은 범위 `unknown`으로 다룬다.**
    다시 v3로 올려도 과거 완전성을 복원했다고 쓰지 않는다. 빈 상태로 시작하면 감시가 목록에 둔 모든 opened/recovered 이벤트(최대 100건, 양쪽)가 다시 보내진다.
- **재알림:** `remind_after_minutes`(0=끔, 최대 1440)마다 열린 장애에 대해 창(window)당 한 번 재알림을 보낸다. 복구 뒤에는 보내지 않는다.
  재알림 전송이 실패하면 같은 창 안에서 다른 전달과 똑같이 `max_attempts`까지 재시도한다(모의 확인된 재알림은 반복하지 않는다).
- **전송 실패·재시도:** 실패는 `undelivered`로 기록하고 다음 실행에서 다시 시도한다(`max_attempts` 1~5). 모두 실패하면 상태에 남기되 영원히 큐에 두지 않는다.
  전송 예외 문구는 기록하지 않는다(코드만).
- **동시 실행 금지·상태 크기:** CLI는 `<알림 상태>.lock`을 만들어 겹치는 실행을 거부한다(종료 2, `already_running_or_stale_lock`;
  비정상 종료로 남은 잠금 파일은 사람이 확인하고 지운다). 감시가 보존하는 opened/recovered 이벤트의 전달 행, 현재 대기 행,
  시도 한도 전의 미전달 행, 현재 장애의 최신 재분류·재알림 행을 보호한다. 나머지는 마지막 시도 30일 뒤 정리하며,
  그 전에도 **최근 최대 1,000행·출력 1 MiB**에 맞춰 오래된 행부터 정리한다. 삭제한 행의 가장 늦은 마지막 시각을 `history_pruned_through_ms`에 기록한다.
  필수 보호 행만으로 한도를 넘으면 `state_capacity_exceeded`로 거부하고 기존 파일을 유지한다. 보호 행을 조용히 삭제하지 않는다.
  구버전이 이미 1 MiB를 넘겨 쓴 파일은 **최대 8 MiB까지 읽은 뒤** 첫 실행에서 압축한다. 새 상태와 롤백 사본은 쓰기 전에 1 MiB 한도를 검사한다.
  큰 구버전 파일은 v3로 먼저 실행·압축한 뒤 롤백 사본을 만든다. 시각이 마지막 실행보다 뒤로 가면 `clock_error`로 거부해 과거 재알림 창을 다시 보내지 않는다.
- **기록의 범위:** 경기별 집계는 보존된 행의 최종 시도 상태만 센다. 삭제 구간과 겹치거나 첫 기록 전/마지막 실행 후를 포함한 기간은
  보존분을 보여 주면서 전체 합계는 미측정으로 쓴다. v1·v2에는 보존 범위 정보가 없어 `unknown`이다. 모든 재시도의 이력 합계가 아니다.
- **메시지(`pitcheezy-host-alert-message-v2`):** 분류·심각도·먼저 조사할 쪽·장애 id·종류(`opened`/`recovered`/`reclassified`)·재알림 번호·
  장애가 열린 시각(`observed_at`)·알리는 원인의 관측 시각(`cause_observed_at`, 재분류만)·그 원인의 issues·`reclassified_from`·개발용 문구.
  접속 주소·토큰·연락처는 넣지 않는다. 문구는 승인 전이다.

## 실행

~~~text
node ops/public-host/alerts-cli.mjs --monitor-state <감시 상태.json> --config ops/public-host/examples/alerts.example.json --state <알림 상태.json>
~~~

감시 CLI를 한 번 실행한 뒤 이 CLI를 한 번 실행한다. 둘 다 단발이며 스케줄러·상시 실행은 별도다.
종료 1은 전달 실패가 남았거나 형식이 틀린 감시 이벤트/장애를 건너뛴 경우다(`invalid_events`/`incident_invalid`).
지원 transport는 `mock`뿐이다. 다른 값은 설정 단계에서 거부한다(종료 2). 전달 실패가 남으면 종료 1, 아니면 0.
출력에는 모의로 보낸 메시지 목록과 `delivery_confirmed:false`가 항상 들어간다.

실제 채널(메일·메신저·SMS 등)과 수신자 연락처는 사람이 정한 뒤 별도 transport로 붙인다. 그때도 "전달 확인"은 수신자 응답으로만 기록한다.

## 모의 리허설 — 2026-10-13

[영수증](../../docs/results/ops/ws_alert_rehearsal_20261013.json): 실제 감시 상태 기계(`advanceState`)에 합성 관측을 넣고 mock transport로 전달했다.

1. 발행 지연 → 2회 연속 실패 뒤 open: 양쪽 1건씩(먼저 조사 Song), 이후 반복 관측은 억제, 31분 뒤 재알림 양쪽 1건씩, 복구 2회 뒤 `recovered` 양쪽 1건씩.
2. 호스팅 오류 + 우리 쪽 transport 2회 실패: Song 즉시, 우리 쪽은 3번째 시도에서 확인, 큐 비움.
3. 안내 상태·접근 문: 정보성, 조치 불필요로 표시.
4. 두 원인 혼합: `unclassified`로 양쪽.
5. transport 영구 실패: 3회 시도 뒤 `undelivered`로 남고 큐에서 제거(숨기지 않음).
6. (WS-alert2, [영수증](../../docs/results/ops/ws_alert2_rehearsal_20261013.json)) 안내 ON 중 open → 안내 OFF 뒤 발행 중단 2회: 양쪽에 재분류 `publish_stalled`(Song 우선) → 복구.
7. (WS-alert2) 감시 로그인 일시 실패로 open(우리 우선) → 발행 중단 2회: 양쪽에 재분류 `publish_stalled`(Song 우선).

이는 합성 시퀀스이며 실제 발행 중단·실제 수신·응답 시간은 미측정이다.

## 한계

- 실제 전달·수신 확인·응답 가능 시간대는 없다. 10/20 연락 수단 결정(WS-human1) 뒤 transport를 붙여야 한다.
- 감시가 단발이므로 알림도 단발이다. 실행 간격·상시 실행·장애 지속 시간 측정은 별도다.
- 분류는 감시 issue 이름에 기반한 추정이다. 실제 원인 확정은 사람이 한다.
- 접근 문이 켜져도 WS-monitor2의 `access_code_env`를 설정하면 실제 로그인 경로로 세션을 열어 감시한다. 코드 미설정 시 게이트 뒤 발행 시각은 미측정이다.
- **별도 후속 결함:** 알림 실행을 건너뛰는 동안 감시 이벤트가 최근 100건 밖으로 밀리면, 과거 opened/recovered 대기가 다음 실행에서 재구성되지 않을 수 있다.
  미전달 행은 상태 압축에서 보존하지만 이 상태의 재시도를 보장하지 않는다. 이중 영속 대기열·배압 정책은 별도 후속 작업이며,
  현재는 문서의 감시 1회마다 알림 1회 실행 조건을 지켜야 한다. 대규모 누적 대기의 무손실 처리를 보장하는 구현은 아니다.

## 재현

~~~text
node --test ops/public-host/tests/alerts.test.mjs
node ops/public-host/rehearse-alerts.mjs --output .cache/alert-rehearsal-new.json
~~~
