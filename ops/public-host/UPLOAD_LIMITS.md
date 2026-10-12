# 인증 업로드 제한 — WS-ops1b

인증된 발행기의 PUT·DELETE·비공개 HEAD 요청을 저장소 접근 전에 제한한다. 실제 계정/발행기 주기에는 아직 연결하지 않았다.

## 동작

- 허용 경로·기능 활성화·인증·메서드 확인 후 PUBLISH_LIMITER.limit({key: "publisher"})를 호출한다.
- 정상 인증 요청은 파일과 메서드에 관계없이 같은 한도를 사용한다. IP·파일명·토큰을 key에 저장하지 않는다.
- success=true만 본문 읽기/R2 접근을 허용한다. false는429, binding 누락·예외·응답 형식 오류는503이다.
- 429에는 Retry-After:60을 준다. 다음60초 뒤 반드시 허용된다는 보장이 아닌 보수적 재시도 안내다.
- 공개 GET/HEAD와 잘못된 인증 요청은 발행자의 한도를 사용하지 않는다.
- 잘못된 본문, 조건 없는 요청,412 충돌도 인증된 발행 시도이므로 한도에 포함된다.
- 한도에 걸린 비공개 HEAD는 본문이 없지만 상태429/Retry-After는 동일하다.
- 거부 경로는 본문을 읽거나 R2 메서드를 호출하지 않는다. 공급자 오류나 비밀 값을 응답하지 않는다.

## 잠정 설정과 비용 경계

예제는 **60요청/60초/Cloudflare 위치**, namespace_id1002다. 실제 승인된 발행 주기가 아니다.
HEAD 다음 PUT은2회이며 health·manifest·setup 갱신과 실패 재시도도 각각 요청이다.
일괄 발행이 한도를 차지하면 health·철회도 잠시 거부될 수 있다. 실제 파일 수와 발행 주기를 측정해 결정한다.

namespace는 TELEMETRY_LIMITER(예제1001), 다른 Worker와 개발/운영 환경 모두와 분리한다.
Cloudflare 같은 계정에서 동일 namespace+key는 Worker 사이에도 카운터를 공유한다.
[공식 rate-limit 계약](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/)의
위치별 근사 제한이므로 전 세계 정확한60회 제한이나 과금 상한이 아니다.
인증 실패와 차단 응답에도 Worker 요청 비용은 생길 수 있고, 공개 읽기·다른 계정 자원 비용을 제한하지 않는다.

## 재시도와 장애 대응

- 429: 최소 안내 시간 뒤 지연을 두고 기존 본문·원래 If-Match/If-None-Match 조건으로 재시도한다.
- 503: binding/계정 설정을 확인한다. 자동으로 limiter를 끄거나 무조건 쓰기로 우회하지 않는다.
- 412: 다른 쓰기가 반영됐으므로 원장·순번을 재확인한다. 새 ETag를 얻어 낡은 본문을 자동 덮어쓰지 않는다.
- PUT 성공 응답을 잃었을 때의 발행기 원장·재시도 규칙은 WS-ops2의 실제 계약 연결에서 확인한다.

긴급 업로드 중지는 UPLOAD_ENABLED=false로 가능하지만 실제 변경 권한·절차는 출시 전에 확인해야 한다.
이 단위는 업로더 프로그램이나 실제 경보 채널을 만들지 않는다.

## 검증

`node --test ops/public-host/tests/worker.test.mjs ops/public-host/tests/runtime.test.mjs ops/public-host/tests/rehearsal.test.mjs`

단위 검사에서 모든 거부의 본문/R2 접근0회, 인증 실패의 quota0회, 파일·메서드 공통 키,
한도 뒤 재시도에도 stale ETag412를 확인했다. 실제 Miniflare binding을2회로 설정하여
PUT+HEAD 뒤 서로 다른 파일/메서드가429이고 공개 조회·저장 내용은 유지됨을 확인했다.
실제 CDN·계정의 분산 제한이나 과금은 미측정이다.

전체 Node71 및 별도 Codex 관련39검사가 통과했다.
