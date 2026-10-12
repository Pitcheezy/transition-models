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
| 두 종류가 섞임 또는 모르는 issue | `unclassified` | 양쪽 |
| `*_notice_active` | `notice_active` (정보) | 조치 불필요(사람이 켠 안내) |
| `*_access_required` | `access_gate` (정보) | 조치 불필요(감시에 세션 없음) |
| `recovered` 이벤트 | `recovered` (정보) | — |

- **중복 억제:** (장애 id, 종류, 수신자)마다 한 번만 보낸다. 같은 장애가 계속 열려 있어도 반복하지 않는다.
- **재알림:** `remind_after_minutes`(0=끔, 최대 1440)마다 열린 장애에 대해 창(window)당 한 번 재알림을 보낸다. 복구 뒤에는 보내지 않는다.
- **전송 실패·재시도:** 실패는 `undelivered`로 기록하고 다음 실행에서 다시 시도한다(`max_attempts` 1~5). 모두 실패하면 상태에 남기되 영원히 큐에 두지 않는다.
  전송 예외 문구는 기록하지 않는다(코드만).
- **메시지:** 분류·심각도·먼저 조사할 쪽·장애 id·종류·관측 시각·issues·개발용 문구. 접속 주소·토큰·연락처는 넣지 않는다. 문구는 승인 전이다.

## 실행

~~~text
node ops/public-host/alerts-cli.mjs --monitor-state <감시 상태.json> --config ops/public-host/examples/alerts.example.json --state <알림 상태.json>
~~~

감시 CLI를 한 번 실행한 뒤 이 CLI를 한 번 실행한다. 둘 다 단발이며 스케줄러·상시 실행은 별도다.
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

이는 합성 시퀀스이며 실제 발행 중단·실제 수신·응답 시간은 미측정이다.

## 한계

- 실제 전달·수신 확인·응답 가능 시간대는 없다. 10/20 연락 수단 결정(WS-human1) 뒤 transport를 붙여야 한다.
- 감시가 단발이므로 알림도 단발이다. 실행 간격·상시 실행·장애 지속 시간 측정은 별도다.
- 분류는 감시 issue 이름에 기반한 추정이다. 실제 원인 확정은 사람이 한다.
- 접근 문이 켜지면 감시가 세션 없이 401만 보므로 그 동안 발행 지연을 감지하지 못한다(감시용 세션 미구현).

## 재현

~~~text
node --test ops/public-host/tests/alerts.test.mjs
node ops/public-host/rehearse-alerts.mjs --output .cache/alert-rehearsal-new.json
~~~
