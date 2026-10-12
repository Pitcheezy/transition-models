# 월드시리즈 공개 호스팅 후보

이 디렉터리는 **우리 운영 코드**다. Song 모델/발행기/화면을 복사하거나 변경하지 않는다.
COLLAB-001의 파일 전달 경계를 구현한 후보이며, 실제 서비스 데이터 계약 검증이나 배포 완료가 아니다.

[현재 운영 인계·재현·다음 조건](../../docs/WS_OPERATIONS_HANDOFF.md)에서 전체 도구를 찾는다.

## 근거와 현재 경계

- 사용자 2026-10-12 요청: 협업 후 우리 담당 업무 진행.
- 협업 문서 기준: Song `collab/ws-2026@ed3a51c60482dbccdb084f437cc3c5e93f2dfc6a`.
- [COLLAB-001 추가 호스팅 조건](https://github.com/SongRoute/pitcheezy/blob/ed3a51c60482dbccdb084f437cc3c5e93f2dfc6a/docs/pm/transfers/COLLAB-001-ws-public-launch-request-draft.md)
- [공개 발행 계약 초안 v0](https://github.com/SongRoute/pitcheezy/blob/ed3a51c60482dbccdb084f437cc3c5e93f2dfc6a/docs/pm/service/public-publish-contract-draft.md)
- 실제 예제·JSON Schema·공개용 화면 고정 소스는 이번 작업에 수신되지 않았다.
  문서에 적힌 로컬 구현 완료를 전달 완료로 취급하지 않는다.
- 토큰/버킷/도메인을 만들지 않았고 Cloudflare·Sites·DNS·기존 서버는 변경하지 않았다.
- 모든 테스트 본문은 `synthetic`으로 표시한 임의 전송 자료다. Song 경기 스키마 예제가 아니다.

## 인증 업로드 요청 제한

[제한·오류·재시도](UPLOAD_LIMITS.md): 필수 PUBLISH_LIMITER가 허용한 요청만 저장소에 접근한다. 실제 한도는 별도 결정한다.

## 이용 기록·피드백

별도 private D1 기반의 [수집 계약·보관·제한](TELEMETRY.md)을 추가했다. 기본 비활성이며 실제 수집/배포는 별도다.

## 고정 배포 후보

[결정적 패키지 생성/검사](RELEASE.md)는 별도 도구다. 실제 배포/공급자 빌드 인증과 구분한다.

[오프라인 후보 설정 검사](CONFIG_CHECK.md)는 배포 폴더의 경로·바이트·수집 안내 일치를 확인한다.

## 첫 연결 검증 (COLLAB-001)

[검증 기록](../../docs/WS_OPS2_FIRST_CONNECTION_20261013.md): Song의 예시 13·스키마 6을 고정 커밋 SHA로 대조·스키마 검증하고, 문서 절차대로
이 Worker에 올린 뒤 고정 커밋의 공개 화면 빌드가 상태를 구별해 읽는지 Chromium으로 확인했다. `node ops/public-host/rehearse-first-connection.mjs`,
`uv run --frozen python scripts/verify_publish_contract.py`, `tests/browser/first-connection.test.cjs`(환경 변수 없으면 건너뜀). 실제 발행기·실계정 연결은 별도다.

## 교차 검토 (WS-review1)

[검토 기록](../../docs/WS_REVIEW1_20261013.md): main `70aa241`의 운영 코드를 네 관점 + 반박 2명으로 검토해 확정 12건을 수정하고 기각 12건의 사유를 남겼다
(재검사 [영수증](../../docs/results/ops/ws_review1_recheck_20261013.json)). 작성 모델 묶음별 규약 조건은 아직 미충족이다(Codex 모델 id 확인·비Claude 검토자 지정은 사람 결정).

## 긴급 안내 화면 스위치

[WS-safe1 스위치](NOTICE.md): 운영자 토큰(`NOTICE_TOKEN_SHA256`, 발행기 토큰과 별개)으로 `/_notice/v1/state`를 바꾸면
화면·asset·공개 JSON·수집이 503 안내 응답으로 바뀌고 업로드·운영자 경로는 유지된다. 감사 기록·복구 조건·로컬 실측·한계는 문서에 있다.
실제 공개 문구·전환·토큰 전달은 사람 결정이며 내려받은 자료 회수 기능이 아니다.

## 관람 접근 문

[WS-access1 접근 문](ACCESS.md): `ACCESS_GATE_ENABLED=true`이면 접속 코드(digest 비밀)로 연 무상태 세션 쿠키 없이는
화면·asset·공개 JSON·수집이 401이다. 업로드·안내 스위치와 인증이 분리되며, 화면은 호스트와 같은 출처여야 한다.
접근 제한은 MLB 이용 허가가 아니고 실제 대상·활성화·코드 전달은 사람 결정이다.

## 경기별 운영 기록 초안

[WS-report1 생성기](REPORT.md)는 경기 ID·집계 기간·증거 라벨·동의/누락·문제·조치·커밋/해시/명령·미측정을 담은 이슈 초안(Markdown+JSON)을
입력 파일에서 만든다. 수집 OFF/자료 없음은 미측정으로, 세션 0행은 0세션으로 구별하며 게시는 사람 승인 뒤 수동이다.

## 읽기 감시와 양쪽 알림 후보

[감시 도구](MONITORING.md)는 운영자용 단발 CLI다. 상시 실행은 별도이며 host ZIP에 자동 포함되지 않는다.
[알림 후보](ALERTS.md)는 감시 이벤트를 발행 중단(Song 우선)·호스팅 오류(우리 우선)·혼합(양쪽)·정보로 분류해 두 수신자에게
**모의 transport**로만 전달한다. 실제 채널·연락처·발송은 사람 결정이며 모의 확인은 전달 확인이 아니다.

## 로컬 전체 흐름 리허설

[합성 부하·충돌·철회/복구·감시·브라우저](REHEARSAL.md)를 계정 없이 재현할 수 있다. 실제 CDN 용량과 구분한다.

## 운영 절차와 비용 가정

[장애·롤백 절차](RUNBOOK.md) · [갱신 주기별 비용 산정](COST_PLAN.md). 실제 계정과 예산 승인은 별도다.

## 구현

`worker.mjs`는 Worker 진입점이며, 내부 `gateway.mjs`를 호출한다. `notice.mjs`는 긴급 안내 스위치, `access.mjs`는 관람 접근 문이다.
모델 호출·맥미니 프록시·임의 URL fetch·파일 목록 API는 없다.

- GET/HEAD: `/v1/manifest.json`, `health.json`, `dates.json`,
  `games/YYYY-MM-DD.json`, `game/<positive-id>.json`, `setup/<positive-id>.json`.
- 없는 파일/허용하지 않은 데이터 경로는 JSON 404. SPA index.html로 대체하지 않는다.
- public 데이터는 GET/HEAD만, 인증 업로드는 PUT/DELETE/HEAD만 지원.
- `Date`는 응답 시각, `Age: 0`은 R2에서 직접 읽은 응답의 캐시 나이.
  파일 자체가 최신이라는 의미가 아니다. 화면은 원래 `publish` 시각도 사용해야 한다.
- 모든 JSON 응답과 오류에 `Cache-Control: no-store`, `CDN-Cache-Control: no-store`.
  정정/삭제가 우선이다. 종료 파일 장기 캐시는 아직 구현하지 않았다.
- 공개 GET/HEAD의 `If-None-Match`가 현재 강한 ETag와 같으면 본문 없는 **304**(ETag·Date·Age·no-store 유지). 약한 태그·`*`·삭제/교체된 객체는 304가 아니다.
  이는 Song 화면의 ETag 재조회 변경 예고에 대응한 읽기 계약이며 업로드 조건부 ETag(If-Match/If-None-Match:*)와 다른 것이다.
- 선택한 단일 `READ_ORIGIN`만 CORS 허용하며 Date/Age/ETag를 노출한다.
  기본은 동일 출처. 업로드 CORS·credential cookie는 제공하지 않는다.
- UTF-8 JSON object, SHA-256, 본문 크기를 검증하고 원래 JSON 바이트를 그대로 제공.
  크기 상한 5MiB는 임시 운영 제한이며 실제 경기 파일 크기 측정 뒤 정한다.
- 경로는 ASCII 파일명만 받으며 percent-encoded 경로를 거부한다.
- 헤더/환경 변수/스토리지 오류에 포함된 비밀 값과 내부 경로를 응답하지 않는다.
- 두 기능 스위치는 **기본 비활성**이다. 스위치만 켜면 공개 계약 검증이 끝나는 것이 아니다.

## 업로드 방식 제안 — 아직 Song 발행기와 합의·연결 전

인증된 `/_publish/v1/...`에 HTTP 요청한다. 이는 우리 업로드 어댑터 제안이며
공개 JSON 본문의 계약을 변경하지 않는다. [단일 파일 전송 도구](PUBLISHER.md)는 기본 dry-run과 제한된 재시도만 제공한다.
Song 발행기/재시작 원장·다중 파일 순서는 별도 연결한다.

1. 인증: `Authorization: Bearer <token>`. 토큰은 32바이트 이상의 난수에서 만든 base64url
   43~128문자다. 실제 값은 Mac 발행기에만 두고 Worker는 SHA-256 digest를 설정한다.
2. PUT: `Content-Type: application/json`, `X-Content-SHA256: <원본 바이트 sha256>`.
   첫 저장은 `If-None-Match: *`, 갱신은 직전 응답의 `If-Match: "<ETag>"`.
3. HEAD: 인증 후 현재 ETag, 원본 SHA, `X-Publish-Deleted`만 확인한다. 본문/목록은 주지 않는다.
4. DELETE: 현재 ETag의 If-Match가 필수. public 조회에서 즉시 없는 파일로 처리한다.
5. 412는 충돌이다. **새 ETag를 읽어 낡은 본문을 자동 재전송하지 않는다.**
   발행기 상태/순번과 원본을 다시 대조해야 한다. 토큰은 쿼리·명령 인자·로그에 넣지 않는다.

성공 응답의 `stored: true`는 전송 완료이며 `schema_validated: false`를 함께 낸다.
스키마·투구 공개 가능 여부·원장·경기 종료/미트 규칙 검증은 제공하지 않는다.
그 내용은 Song 발행기/검사기 및 WS-ops2에서 확인한다. 순번 단조성이나 다중 파일
트랜잭션까지 ETag가 대신 보장하지 않는다. 파일별 순번과 업로드 순서를 별도로 관리해야 한다.

## 원자적 저장과 삭제/복원

R2의 조건부 put을 사용한다. HEAD 뒤 무조건 덮어쓰거나 삭제하지 않는다.
R2 delete에는 조건부 옵션이 없어 DELETE는 조건부 put으로 삭제 표식을 저장한다.
복원은 삭제 표식의 새 ETag로 PUT한다. 첫 생성 조건으로는 복원하지 않는다.

R2 ETag는 내용 기반이므로 같은 JSON 복원 시 예전 삭제 토큰이 유효해지는 문제가 있다.
이를 막기 위해 전용 **비공개 R2**에는 매 쓰기마다 새 UUID가 붙은 내부 헤더와 원본 바이트를
함께 저장한다. GET은 내부 헤더·길이·SHA를 확인하고 원본만 제공한다.
이 내부 형식은 Song의 JSON 본문과 무관하다.

버킷의 r2.dev/public domain을 켜거나 S3로 직접 JSON을 덮어쓰면 안 된다.
스토리지 객체를 백업할 때는 내부 헤더와 metadata를 함께 보존한다.
삭제 표식은 물리 삭제가 아니며 자동 정리 기능은 없다.
장기 보관/정리와 재해 복구는 실제 배포 전에 별도 검증한다.

## 재현 — 공개 계정 불필요

Node 24 이상을 사용한다. 검증 환경은 Node 24다.

```sh
cd ops/public-host
npm ci --ignore-scripts
npm run check
npm test
```

- 단위 검사 28개: 권한, 크기/UTF-8/무결성, 경로, CORS, 캐시, 충돌, 삭제/복원, 동일 본문 복원.
- Miniflare 4.20260730.0의 **실제 로컬 workerd/R2 API** 통합 검사 1개:
  생성/조회/동시 갱신/삭제/동일 본문 복원을 순차 확인한다.
- Miniflare는 안정 4.x 버전과 transitive dependencies를 package-lock에 고정했다.
- Node 내부 모의 저장소 검사와 로컬 R2 검사를 구별한다. Cloudflare 실계정/CDN 부하 검사는 아니다.
- CI `.github/workflows/public-host.yml`: Linux/Windows에서 위 검사를 실행. 배포 작업 없음.

## 배포 준비 상태

`wrangler.example.jsonc`는 설정 예시다. 기본 배포 파일·실계정 값·public 화면 빌드가 없다.
`assets.run_worker_first=true`가 필수다. asset-first이면 파일이 Worker의 차단·404 처리를 우회한다.
실제 배포에는 아래를 먼저 완료한다.

- 고정 공개용 화면 `npm run build:public` 산출물과 `VITE_PUBLISH_BASE`,
  합의된 `VITE_PUBLISH_STALE_S`, JSON Schema/예제·소스 SHA 수신.
- 발행기의 파일 내용 검증 및 우리 전송 방식과 전체 연결. 재시작/중복/412/철회/정정 확인.
- private R2 전용 버킷과 서비스 계정, 비공개 인증 전달, 회전/철회 절차.
- 실제 파일 크기·발행 주기·읽기 요청량에 맞춘 비용/사용량 상한 및 업로드 남용 제한.
- 실제 CDN에서 Date/Age/404/삭제/CORS 확인, 공개 재배포 범위 결정과 롤백 검사.
- 이용 기록·피드백·감시·부하/실기기는 별도 단위. 이 Worker만으로 완료되지 않는다.

환경 변수 이름은 `DATA_READ_ENABLED`, `UPLOAD_ENABLED`, `ACCESS_GATE_ENABLED`, `ACCESS_SESSION_SECONDS`, `PUBLISH_TOKEN_SHA256`,
`READ_ORIGIN`; 비밀 `NOTICE_TOKEN_SHA256`(운영자 digest 목록)·`ACCESS_CODE_SHA256`·`ACCESS_SESSION_SECRET`; binding은 `PUBLISH_BUCKET`, `PUBLISH_LIMITER`, `ASSETS`다.
기존 Sites 화면을 public 디렉터리에 자동 복사하지 않는다(공개 영상 없는 WS 범위와 다름).

## 참고

- [R2 조건부 put, checksum, delete API](https://developers.cloudflare.com/r2/api/workers/workers-api-reference/)
- [Worker 우선 경로 처리](https://developers.cloudflare.com/workers/static-assets/routing/advanced/)
- [R2 저장소와 CDN 캐시는 별개](https://developers.cloudflare.com/r2/reference/consistency/)

## 로컬 재시작 검사

[영속 R2/D1·키 회전·수집 OFF 예약 정리](LIFECYCLE.md). 실계정 백업 복원과 구별한다.
