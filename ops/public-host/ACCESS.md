# 관람 접근 문 — WS-access1

[협업 규약](../../docs/COLLABORATION_PROTOCOL.md)과 COLLAB-001의 "접근 코드 같은 문을 켜고 끌 수 있는 자리"를 우리 호스팅 후보에서
**로컬 구현·합성 검증**한 기록이다. **접근 제한은 MLB 자료 이용 허가가 아니고**, 세션은 개인을 식별하지 않는다.
실제 접속 대상·활성화·코드 전달·문구는 사람 결정(WS-human1)이며 실제 배포·실경기 운영 완료가 아니다. Song 화면·발행기·모델은 변경하지 않았다.

## 무엇이 바뀌는가

`ACCESS_GATE_ENABLED=true`이면 유효한 세션 쿠키가 없는 모든 뷰어 요청이 401로 바뀐다. 업로드·안내 스위치·세션 경로는 별개다.

| 경로 | 게이트 OFF | 게이트 ON, 세션 없음 | 게이트 ON, 세션 있음 |
|---|---|---|---|
| `/`, 정적 asset, SPA 경로 (GET/HEAD) | ASSETS 제공 | **401** HTML 접속 코드 입력 화면(no-store, `X-Pitcheezy-Access: required`, `Vary: Cookie`) | ASSETS 제공, 단 `Cache-Control: private`(max-age 보존)·`Vary: Cookie` |
| `/v1/...` 공개 JSON (GET/HEAD) | 원본 바이트 | **401** JSON `{"error":"access_required"}` | 원본 바이트 |
| `/v1/...` OPTIONS | 204 | 204 | 204 |
| `/_telemetry/...` POST | 수집 처리 | **401** JSON | 수집 처리 |
| `/_publish/...` | 조건부 저장 | **변경 없음** | 변경 없음 |
| `/_notice/...` | 운영자 전환 | **변경 없음** | 변경 없음 |
| `/_access/v1/session` | 404 | 조회/로그인/로그아웃 | 조회/로그인/로그아웃 |

[긴급 안내 스위치](NOTICE.md)가 켜져 있으면 안내가 먼저다(게이트보다 앞서 503 안내).
게이트가 켜졌는데 비밀이 없거나 형식이 틀리면 **닫힌 쪽으로 실패**한다(503 `access_not_configured`, `X-Pitcheezy-Access: misconfigured`).

## 설정과 비밀

- `ACCESS_GATE_ENABLED`(문자열 `"true"`/`"false"`, 기본 false)와 `ACCESS_SESSION_SECONDS`(1~604800, 예제 43200)는 설정 변수다.
  설정 검사(`check_public_host_config.py`)가 다섯 토글과 이 숫자를 검증한다.
- 비밀 `ACCESS_CODE_SHA256`: 접속 코드의 SHA-256 digest를 쉼표로 이은 목록(1~8개). 코드는 8~128자, 공백·제어문자 없음. 12자 이상 난수 권장.
  코드 교체는 새 digest를 추가하고 옛 digest를 지우는 것이다. **digest를 지우면 그 코드로 연 세션이 모두 끝난다.**
- 비밀 `ACCESS_SESSION_SECRET`: base64url 43~128자. 세션 서명과 요청 제한 키에 쓴다. **바꾸면 모든 세션이 끝난다.**
- 발행기 토큰(`PUBLISH_TOKEN_SHA256`)·안내 운영자 토큰(`NOTICE_TOKEN_SHA256`)과 모두 다른 값이다. 뷰어 세션으로는 업로드·안내 전환을 할 수 없다.
- 설정 검사는 비밀을 `vars`에 넣으면 거부하고, 게이트가 켜진 설정에 `READ_ORIGIN`이 비어 있지 않으면 거부한다
  (`access_gate_same_origin_required`): 세션 쿠키는 SameSite=Strict라 **화면과 호스트가 같은 출처**여야 한다.
- 코드·digest·세션 비밀은 공개 이슈·로그·응답·영수증에 쓰지 않는다. 코드는 사람이 비공개로 전달한다.

## 세션

- 로그인 성공 시 쿠키 `__Host-pz_viewer`(https) / `pz_viewer`(http loopback 검사용)를 발급한다:
  `HttpOnly; SameSite=Strict; Path=/; Max-Age=<ACCESS_SESSION_SECONDS>`(https에서는 `Secure`).
- 값은 `v1.<만료 ms>.<코드 digest 앞 8자>.<난수>.<HMAC-SHA256>`이며 서버에 저장하지 않는다(무상태). 만료·서명·코드 유효 여부를 매 요청 검사한다.
- **로그아웃(DELETE)은 브라우저의 쿠키를 지운다.** 복사된 쿠키 값은 만료·코드 삭제·비밀 회전 전까지 유효하다(영수증에 기록).
  개별 세션 강제 종료 목록은 없다. 필요하면 코드 교체 또는 비밀 회전으로 끝낸다.
- 로그인/로그아웃은 same-origin 검사(`Sec-Fetch-Site`가 same-origin/none, `Origin`이 있으면 호스트와 같아야 함)를 거친다.
- 로그인 시도는 `PUBLISH_LIMITER`의 별도 키 `access:<요청자 HMAC>`로 제한한다(발행기 키·안내 키와 분리, 같은 binding). 요청자 식별은
  Cloudflare가 붙이는 `CF-Connecting-IP`이며 로컬 런타임처럼 없으면 공용 풀 하나를 쓴다. 거부는 429, 제한기 오류는 503이다.

### 사용

~~~text
# 상태 (쿠키가 있으면 같이 보냄)
curl -sS -b "$COOKIE_JAR" https://<호스트>/_access/v1/session
# 로그인 (JSON) — 코드는 환경 변수/비밀 저장소에서만
curl -sS -c "$COOKIE_JAR" -H "Content-Type: application/json" --data "{\"code\":\"$ACCESS_CODE\"}" https://<호스트>/_access/v1/session
# 로그아웃
curl -sS -X DELETE -b "$COOKIE_JAR" https://<호스트>/_access/v1/session
~~~

브라우저에서는 401 입력 화면의 form(POST `application/x-www-form-urlencoded`)이 성공 시 303으로 `/`에 돌아간다. 입력 화면에는 스크립트가 없다.

## Song 화면에 필요한 것 (요청 초안 — 미발송, 발신 승인 후 mail)

> 접근 문이 켜지면 공개 JSON은 유효한 세션 쿠키 없이는 401 `{"error":"access_required"}`(헤더 `X-Pitcheezy-Access: required`)로 응답합니다.
> 공개 화면은 (1) 호스트와 **같은 출처**에서 제공되고 (2) `fetch`에 `credentials: "same-origin"`(기본값)을 사용해야 하며 `credentials: "omit"`은
> 세션을 보내지 않아 항상 401이 됩니다. (3) 401을 받으면 "접속 코드 필요" 상태를 표시하고 입력 화면(`/`)으로 안내해 주세요.
> 로컬 합성 화면에서 `omit`으로 인한 401을 실제로 재현했습니다. 이는 HTTP 응답 규칙이며 공개 파일 v1의 항목 의미는 바꾸지 않습니다.

## 양쪽 담당자 절차

1. 사람이 접속 대상과 기간을 정한다. 접근 제한이 이용 허가가 아님을 전제로 한다.
2. 계정 담당자가 코드를 만들고 digest를 `ACCESS_CODE_SHA256`에, 난수를 `ACCESS_SESSION_SECRET`에 비밀로 설치한 뒤 `ACCESS_GATE_ENABLED=true`로 배포한다.
   코드 원문은 초대할 사람에게만 비공개로 전달한다.
3. 켜고 끈 시각·사유·대상 범위를 우리 board 또는 관련 mail에 적는다(코드·digest 제외).
4. 코드 유출 의심 시 새 코드를 추가하고 옛 digest를 지운다(옛 세션 즉시 종료). 전체 종료는 비밀 회전이다.
5. 끄기(`ACCESS_GATE_ENABLED=false`)는 배포 변경이며 사람 결정이다. 게이트를 끄면 세션 경로는 404가 되고 쿠키는 무시된다.

## 로컬 실측 — 2026-10-13

[영수증](../../docs/results/ops/ws_access_rehearsal_20261013.json): Windows x64·Node 24.1.0·Miniflare 4.20260730.0, 임시 loopback Worker/R2.

- 잠김: `/`·`/fixture.mjs`·`/v1/game/123.json`·`/v1/health.json`의 GET/HEAD와 telemetry POST 모두 401 `required`·no-store, OPTIONS 204. 잠긴 동안 인증 업로드 200.
- 감시: `failed`, `access_gate_active=true`, issues `page_access_required`/`health_access_required`.
- 로그인: 잘못된 코드 401(쿠키 없음), JSON 로그인 왕복 3.69 ms(로컬), form 로그인 303 → `/`, 쿠키 `HttpOnly; SameSite=Strict; Path=/`.
- 열림: 화면 200 `private` 캐시·`Vary: Cookie`, 데이터 원본 바이트 일치, telemetry 핸들러 도달.
- 로그아웃 204 → 쿠키 없는 요청 401; 2초 세션은 2.3초 뒤 401.

브라우저(Chromium, `tests/browser/public-host-access.test.cjs`): 401 입력 화면(스크립트 0) → 잘못된 코드 경고 → 올바른 코드로 303 → 화면·쿠키
속성(HttpOnly·Strict·`document.cookie`에서 보이지 않음) → 직접 asset/JSON 200(`private`) → 로그아웃 204 → 새로고침 401; 1초 세션 만료 후 401. WebKit은 CI.

## 한계 (주장하지 않는 것)

- 공유 코드이므로 누가 들어왔는지 알 수 없고, 코드가 퍼지면 접근 제한은 무력하다. 접근 통계·사용자 수가 아니다.
- 무상태 세션이라 개별 세션을 서버에서 끊을 수 없다(코드 교체/비밀 회전으로 집단 종료).
- 요청자별 제한은 Cloudflare 위치별 근사치이며 전역 상한·무차별 대입 완전 방어가 아니다. 코드 길이와 난수성이 1차 방어다.
- 로컬 http 검사는 `Secure`·`__Host-` 없이 수행했다. 실제 https·실제 Safari/모바일·CDN은 미검사다.
- 화면이 다른 출처에서 제공되면 동작하지 않는다(설계상 거부). 교차 출처 자격 증명은 지원하지 않는다.
- 감시 도구는 세션을 갖지 않으므로 게이트가 켜진 동안 `access_required`로만 기록한다. 감시용 세션 연결은 미구현이다.
- 실제 코드·비밀·접속 대상·활성화는 만들지 않았다. 입력 화면 문구는 승인 전 개발용이다.

## 재현

~~~text
cd ops/public-host && npm ci --ignore-scripts && npm run check && npm test
node --test ops/public-host/tests/access.test.mjs
node ops/public-host/rehearse-access.mjs --output .cache/access-rehearsal-new.json
cd tests/browser && BROWSER_ENGINE=chromium npm run test:host
uv run --frozen python -m pytest tests/test_public_host_config.py tests/test_public_host_release.py -q
~~~

검증 결과(2026-10-13, Windows): 신규 Node 9(단위·만료/변조/철회/회전·감시·실제 로컬 Worker 런타임)·전체 Node 111, Chromium 호스트 브라우저 13(신규 2),
Python 설정/패키지 검사 130, 리허설 영수증 passed. 작성 모델 Claude Fable 5.1(`claude-fable-5-1`); **다른 모델의 출시 검토(WS-review1)는 아직 없다.**
