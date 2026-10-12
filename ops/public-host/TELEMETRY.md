# 이용 기록·선택형 피드백 — WS-ops3

구현 대상은 COLLAB-001 4·5의 접속량/유지 시간/짧은 피드백이다.
공개 경기 JSON의 R2와 분리한 private D1에 저장한다. 실제 사용자 수집·배포는 아직 하지 않았다.

## 무엇을 측정하는가

- 동의한 브라우저 세션 수: 탭/경기/UTC 날짜별 새 임의 UUID. 고유 인원 수가 아니다.
- 브라우저가 보고한 화면 활성 시간(ms): 서버에서 경과 시간보다 큰 값과 8시간 초과를 거부한다.
  봇/위조 입력·실제 시청 집중 여부를 판별하지 않는다. 브라우저 코드와 연결 전에는 현실 정확도 미검증이다.
- 선택형 의견: helpful / unclear / problem, 선택적 범주 none / recommendation /
  explanation / delay / display / other. 자유문·이름·연락처는 받지 않는다.
- D1에 IP, User-Agent, Referer, URL, 장기 쿠키/계정 ID를 넣지 않는다.
  요청 제한은 Cloudflare가 제공하는 IP를 비밀키 HMAC으로 일별 변환해 일시 사용한다.
  인프라 제공자의 네트워크 처리·로그 정책까지 개인정보가 전혀 없다고 주장하지 않는다.

## 입력 계약

두 POST 경로만 지원한다. 공개 GET/집계/목록 API는 없다. 알 수 없는 필드는 거부한다.
동의하지 않으면 보내지 않아야 하며 서버도 consent=true만 받는다.
DNT=1 또는 Sec-GPC=1이면 수집하지 않는다.

`POST /_telemetry/session`, UTF-8 JSON, 1024 bytes 이하:

```json
{"v":1,"consent":true,"session_id":"11111111-1111-4111-8111-111111111111","game_pk":123,"sequence":0,"active_ms":0}
```

- game_pk: 정수 0~999999999999. 0은 경기 미선택이며 임의 URL 대신 사용한다.
- session_id: 임의 UUID v4 소문자. 개인별 영구 식별자로 재사용하면 안 된다.
- sequence: 0~10000 정수. 첫 요청은 0/0, 이후 증가 순번 + 누적 active_ms.
- 같은 값 재전송과 과거 순번은 합산하지 않는다. 같은 순번의 다른 값, 경기/날짜 변경,
  감소한 누적 시간, 서버 경과 시간+1초를 넘는 보고는 거부한다.
- UTC 날짜/경기를 바꾸면 새 세션을 만든다. 이 기준은 경기 개최지 날짜와 다를 수 있다.
- 클라이언트가 종료 전에 전송하지 못한 시간은 누락될 수 있다.

`POST /_telemetry/feedback`:

```json
{"v":1,"consent":true,"feedback_id":"22222222-2222-4222-8222-222222222222","game_pk":123,"rating":"helpful","reason":"none"}
```

feedback_id 동일 요청은 한 번만 저장한다. 같은 ID의 다른 내용은 409다.
세션 ID와 연결하지 않는다. 개인이 여러 번 응답했는지 판별하지 않는다. 자정 전 응답의 재전송이 자정 뒤 도착하면 409다.
새 ID로 자동 재시도해 중복 의견을 만들지 말고 전송 여부 미확인으로 안내한다.

공통: 200 accepted / 400 invalid / 403 출처·거부 설정 / 409 순서·식별 충돌 /
413 크기 / 415 MIME / 429 제한 / 503 비활성·구성·저장소 실패.
응답에는 입력/DB 오류/저장 내용/비밀 값을 반사하지 않는다.

## 운영 설정과 제한

예시 설정은 기본 비활성이다. 수집 활성화와 보관 기간은 별도 운영 결정이다.

- TELEMETRY_ENABLED, FEEDBACK_ENABLED: 각 문자열 true일 때만 해당 기능 허용.
- COLLECTION_ORIGIN: 정확한 HTTPS origin 한 개. 교차 출처 허용/CORS 없음.
- TELEMETRY_DB: 전용 private D1 binding. `migrations/0001_telemetry.sql` 적용.
- TELEMETRY_LIMITER: Cloudflare rate-limit binding. 예시 60회/60초/키/Cloudflare 위치.
- TELEMETRY_RATE_SECRET: 32바이트 이상 임의 비밀키의 base64url(43~128자); 레포에 넣지 않는다.
- TELEMETRY_RETAIN_DAYS: 1~90, 제안 30일.
- SESSION_WRITES_PER_DAY: 중복을 제외한 하루 세션 상태 쓰기 횟수, 제안100000.
- FEEDBACK_ROWS_PER_DAY: 하루 신규 피드백 행 수, 제안5000.
- 위 설정은 측정 전 제안값이다. Origin은 인증이 아니고 rate-limit은 위치별 근사 제한이다.
  D1 일별 상한은 트랜잭션 안에서 검사/반영하지만 HTTP 요청·D1 읽기 비용의 상한은 아니다.
  실제 WAF/비용 감시/알림은 WS-ops4에서 검증한다. 직접 프록시가 CF IP 헤더를 신뢰하면 안 된다.

## 보관·집계

- 서버 생성 시각과 고정 만료 시각 사용. pulse가 보관 기간을 늘리지 않는다.
- UTC 매일03:17의 scheduled handler가 만료된 행과 지난 일별 budget을 삭제한다.
  수집 스위치를 꺼도 정리는 계속된다. 실제 배포에서 cron 설정과 실행 기록을 확인해야 한다.
- 집계는 만료된 행을 즉시 제외한다. 물리 삭제는 다음 성공한 정리 실행 시점이다.
  Cloudflare Time Travel/백업의 보존은 별도여서 모든 사본 즉시 삭제를 뜻하지 않는다.
- `summarizeTelemetry(db, fromDay, toDay, now)`: 최대90일 UTC 범위, 경기별 세션 수·
  활성 시간 합계/평균·평가 분포. ID를 출력하지 않으며 public endpoint에 연결하지 않는다.
- 실제 자료 추출은 계정 권한이 있는 관리 실행 경로로만 한다. 합성 DB와 운영 DB를 분리한다.
- 11월 전시까지 원자료를 보관한다고 가정하지 않는다. 확정된 보관 기간 안에서 집계 내보내기와
  집계 보관 규칙을 별도로 정해야 한다.

## 검증·경계

`npm test`는 기본 비활성, 출처·본문·숫자·개인정보 필드 거부, rate-limit, 오류 비반사와
실제 로컬 workerd/D1의 중복·동시 갱신·상한·집계·만료 삭제를 확인한다.
실제 Cloudflare 계정·Song host-slot·실기기·실제 사용자 수집은 이 검사의 증거가 아니다.

공식 근거:
[D1 batch 트랜잭션](https://developers.cloudflare.com/d1/worker-api/d1-database/),
[위치별 rate-limit 한계](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/),
[Time Travel](https://developers.cloudflare.com/d1/reference/time-travel/).

## 브라우저 모듈

- `client/widget.mjs`의 `mountUsageWidget(element, {enabled:false, gamePk:0})`와
  `client/widget.css`를 우리 호스트에서 사용한다. 기본 비활성이다. `setGame(gamePk)`로
  명시적 경기 번호만 전달하고 `destroy()`로 이벤트/타이머를 해제한다.
- Song의 실제 slot 이벤트 형식은 아직 연결하지 않았다. 실제 화면 코드를 변경하지 않았다.
- 방문 통계 체크박스와 의견 버튼은 별도다. 체크 전 자동 전송 없음. GPC/DNT 거부 시 둘 다 비활성.
- UUID는 메모리에만 있다. 새로고침·경기·UTC 날짜 변경에 새 세션을 만든다.
- 최초 저장 성공 응답 뒤부터 시간 측정. hidden 제외, 60초 넘는 sleep/throttle 간격은 제외,
  30초마다 누적 값을 보낸다. 종료·전환 때 마지막 일부가 유실될 수 있어 과소 집계 가능하다.
- 동의 해제는 이후 전송을 중단한다. 이미 전송된 자료의 즉시 삭제는 아니다.
- 네트워크/본문 응답 전체에 5초 제한. 같은 payload 재시도, 3회 연속 실패 시 통계 일시 정지.
  실패해도 관전 기능은 중단하지 않는다. 피드백 확인 실패 시 같은 선택만 다시 시도한다.
- fetch에 credentials=omit을 지정한다. 실제 Chrome 검사에서는 쿠키가 전송되지 않았다.
  **Windows Playwright WebKit2336에서는 omit 지정에도 같은 출처 쿠키가 전송됐다.**
  keepalive 여부를 바꿔도 동일했다. 이는 해결된 것으로 표시하지 않는다. 서버 저장 경로는
  Cookie를 읽거나 D1에 넣지 않으며, 무쿠키 전송을 모든 브라우저에 보장하지 않는다.
  실제 Safari/공개 도메인 확인과 인프라 로그 정책은 출시 전 별도 검사다.
- `tests/browser/host-telemetry.test.cjs`는 실제 엔진 UI와 합성 HTTP 응답을 검사한다.
  D1까지 포함한 검사는 telemetry-runtime과 별도이며 실제 Song 연결 증거가 아니다.
