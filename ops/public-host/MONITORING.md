# 공개 호스트 감시 준비 — WS-ops4b

명시된 호스팅의 **읽기 가용성**과 파일 발행 시각을 한 번 검사하는 우리 운영 도구다.
Song 모델/수집기/Mac, 외부 알림, 스케줄러에 연결하지 않았다. 합성 응답과 로컬 HTTP로 검증한다.

## 판정 범위

- page: 루트 GET200, UTF-8 HTML 골격. 선택 SHA가 있으면 지정 빌드와 바이트 일치.
- health: /v1/health.json GET200, JSON object, Date/Age 헤더.
- freshness: 명시 JSON Pointer의 RFC3339 시각. fresh/stale/future/missing/invalid.
  pointer=null이면 unmeasured이며 전체 partial이다. 실제 Song 필드명을 추측하지 않는다.
- 업무상 health의 의미와 브라우저 JavaScript 실행은 항상 unmeasured다.
  HTTP200만으로 추천·정책·경기 피드가 정상이라는 뜻이 아니다.
- Date+Age는 캐시/응답 시계 검사다. Age=0이어도 본문은 오래될 수 있다.
  로컬 UTC와 큰 차이가 나면 clock_mismatch. 발행 시각으로 현재 시각을 대신하지 않는다.
- 503에 `X-Pitcheezy-Notice` 헤더가 있으면 [긴급 안내 스위치](NOTICE.md)가 켜진 상태다. 코드 `notice_active`,
  report `notice_active=true`, issues `page_notice_active`/`health_notice_active`로 기록하며 전체 상태는 여전히 `failed`다
  (뷰어에게는 이용 불가). 발행 중단·저장소 장애와 구별해 알림 경로(WS-alert1)에서 다르게 다룰 수 있다. 본문 문구는 기록하지 않는다.
- 401에 `X-Pitcheezy-Access: required`가 있으면 [관람 접근 문](ACCESS.md)이 켜진 상태다. 감시 코드를 설정하지 않았으면 코드 `access_required`,
  report `access_gate_active=true`로 기록하며 게이트 뒤의 발행 시각을 검사하지 못한다(알림 분류 `access_gate`, 정보).
- **접근 문 ON 감시(WS-monitor2):** 선택 키 `access_code_env`에 **환경 변수 이름**(예 `PZ_MONITOR_ACCESS_CODE`, 대문자·숫자·밑줄)을 적으면
  매 실행 그 변수의 코드로 `POST /_access/v1/session`(관람자와 같은 경로, 리다이렉트 미추적)에서 세션을 받아 page/health를 `Cookie`와 함께 읽는다.
  우회 경로나 새 자격 증명 종류는 없다. 감시 전용 코드를 접근 코드 목록에 따로 두기를 권한다(그 코드만 지워 감시 세션만 철회).
  - report `access_session`: `not_configured`(키 없음/null) · `established` · `gate_off`(로그인 경로 404 = 게이트 꺼짐, 쿠키 없이 읽음) · `login_failed`.
  - 로그인 실패는 issues 하나(`access_login_denied`/`_rate_limited`/`_unavailable`/`_http_error`/`_network_error`/`_timeout`/`_invalid_cookie`/`_error`)로 기록하고
    page/health는 `skipped`다(쪽 장애로 오기하지 않음). 세션을 받고도 401이면 `page_access_session_rejected`/`health_access_session_rejected`,
    로그인 경로가 404(게이트 꺼짐)였는데 읽기가 게이트에 막히면 `page_access_gate_without_login`/`health_access_gate_without_login`이다.
    모두 알림 분류 `host_error`(우리 우선)다.
  - `access_gate_active`는 이 실행에서 게이트 자체의 응답을 본 경우만 true다(세션 받음, 로그인 거절 401·제한 429·쿠키 없는 200, 읽기 401).
    네트워크 오류·시간 초과·기타 HTTP 응답은 게이트를 증명하지 않으므로 false다.
  - 로그인 뒤 두 읽기가 이어지므로 한 실행은 최대 약 `timeout_ms`의 2배가 걸린다.
  - 설정에 키를 추가하면(값이 null이어도) 설정 지문이 바뀌므로 새 상태 파일로 시작한다(`config_changed_use_new_state`).
  - 변수가 비었거나 코드 모양이 틀리면 요청 없이 종료 2(`access_code_unavailable`/`access_code_invalid`), 상태 파일을 쓰지 않는다.
  - 코드와 쿠키는 메모리에만 있고 report·state·stdout·stderr에 남지 않는다(검사로 확인). 로그인 1회가 접근 문 요청자 제한 1회를 쓴다.
- 시각은 초 단위 이상·시간대가 있는 RFC3339 문자열만 받는다. 숫자의 초/밀리초는 추정하지 않는다.
  예제의 지연120초·시계차30초는 합의된 운영값이 아니며 실제 리허설에서 정해야 한다.

## 실행

Node24 이상. examples/monitor.example.json을 비공개 운영 폴더로 복사한 뒤 origin을 명시한다.
실제 스키마 확인 뒤 timestamp_pointer를 지정한다. 예제는 null이다. state 부모 폴더는 있어야 한다.

~~~text
node ops/public-host/monitor-cli.mjs --config <운영-설정.json> --state <상태-기록.json>
~~~

한 번 실행하고 종료한다. 대상 발견·재시도 루프·상시 실행·알림 전송 기능이 아니다.
HTTPS origin만 받으며 credentials/query/fragment/path를 거부한다.
**공개 인터넷 목적지인지 DNS까지 검증하는 SSRF 필터는 아니다.** 신뢰하는 운영자만 설정한다.
프록시·DNS·네트워크 정책은 실행 환경에서 관리한다.
로컬 검증은 allow_loopback_http=true와 문자 그대로 127.0.0.1 또는 [::1]의 HTTP만 허용한다.
이 옵션으로 hostname이나 사설 LAN 주소를 HTTP 대상으로 열지 않는다.

GET /와 GET /v1/health.json 각1회. `access_code_env`가 없으면 인증·Cookie를 보내지 않는다. 있으면 그 앞에 로그인 POST 1회를 하고
두 GET에 받은 세션 Cookie만 붙인다. 외부 메시지는 보내지 않는다.
리다이렉트를 따라가지 않고 헤더만 온 응답도 본문까지 전체 제한 시간으로 중단한다.
선언 길이와 실제 스트림 길이를 제한한다. 원문·URL·서버 예외 텍스트는 결과에 기록하지 않는다.
실행 환경의 네트워크/프록시 로그까지 지우는 도구는 아니다.

## 기록과 종료 코드

- 0: 측정한 전송·발행 시각 검사 통과, 열린 장애 없음.
- 1: 이번 검사 실패 또는 열린 장애의 복구 확인이 한 번뿐.
- 2: 설정·상태·중복 실행·시계 역행 등 감시 자체 오류.
- 3: 전송은 열리지만 발행 시각 미측정. 완전한 정상 판정 아님.

연속 **기록 실행** 두 번 실패하면 opened, 두 번 통과하면 recovered 이벤트를 남긴다.
실행 간격을 정하는 기능은 없으며 장애 지속 시간·가동률·실경기 지연률 측정 결과가 아니다.
열린 장애의 원인이 바뀌어도 opened를 반복하지 않는다. 최신 원인은 report.issues다.
pointer=null의 partial은 가용성 복구만 나타낸다. 시각 미측정은 계속 남는다.

상태 파일 하나에 state와 최신 report를 함께 기록한다. 전체 probe/저장 동안 잠금을 잡고,
동기화한 임시 파일을 원자적으로 교체한다. 최근 이벤트100개와 버린 수 dropped_events를 보존한다.
전송/수신 확인이 없으므로 양쪽 담당자에게 알렸다고 기록하지 않는다.
설정 fingerprint 변경은 새 상태 파일을 요구한다. 기존 장애를 성공으로 자동 전환하지 않는다.
손상된 상태·시계 역행·중복 실행은 원본을 보존한다.

강제 종료 후 .lock이 남을 수 있다. 같은 상태 파일의 감시 프로세스가 실제로 없는지 운영자가
확인한 뒤 그 잠금만 수동 처리한다. 자동 삭제·프로세스 종료는 하지 않는다.
신뢰하는 로컬 폴더에서 쓴다. OS 격리·전원 장애·다중 호스트 공유 FS의 내구성 도구는 아니다.
상태를 지워 장애를 숨기지 않고, 설정 변경 때 이전 기록을 보존한다.

## 알림 연결 후보

[ALERTS.md](ALERTS.md)의 단발 CLI가 이 상태 파일의 이벤트를 읽어 두 수신자에게 모의 전달한다. 실제 채널은 미연결이다.

## 재현과 남은 연결

~~~text
node --test ops/public-host/tests/monitor.test.mjs
~~~

합성/로컬 HTTP의 오류·복구·본문 제한·타임아웃·상태 보존·잠금을 확인한다.
실제 도메인·CDN·알림 수신·실기기·실경기는 미검증이다.
실제 health 발행 시각 필드, 합의한 지연 기준, 실행 주기/로그 보관/알림 채널을 받아 연결해야 한다.
별도 브라우저 검사에서 DOM/JS 기능도 확인해야 한다.
