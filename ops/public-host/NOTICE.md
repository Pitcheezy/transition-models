# 긴급 안내 화면 스위치 — WS-safe1

[협업 규약](../../docs/COLLABORATION_PROTOCOL.md) 6절의 "문제가 보이면 양쪽 담당 사람 누구든 즉시 공개 화면을 안내 문구로 바꿀 수 있다"를
우리 호스팅 후보에서 **로컬 구현·합성 검증**한 기록이다. 실제 공개 문구·실제 전환·운영자 토큰 전달·접속 대상은 사람 결정(WS-human1)이며,
이 문서는 실제 배포나 실경기 운영 완료를 뜻하지 않는다. Song 화면·발행기·모델 코드는 변경하지 않았다.

## 무엇이 바뀌는가

스위치가 **켜지면** 뷰어가 닿는 모든 경로가 사전 등록된 개발용 안내 응답으로 바뀐다. 업로드 경로와 운영자 경로는 그대로다.

| 경로 | 평소 | 스위치 ON |
|---|---|---|
| `/`, `/index.html`, 정적 asset, SPA 경로 (GET/HEAD) | ASSETS 제공 | **503** HTML 안내 페이지(스크립트·외부 자원 없음), HEAD는 본문 없음 |
| `/v1/...` 공개 JSON (GET/HEAD) | 원본 바이트 200 / 404 | **503** JSON `{"error":"service_notice","notice":{"id","message"}}`, 존재 여부 비노출, 허용 출처에 CORS 헤더 유지 |
| `/v1/...` OPTIONS | 204 | 204 (뒤이은 503을 화면이 읽을 수 있게) |
| `/_telemetry/...` POST | 수집 처리 | **503** JSON `service_notice` |
| `/_publish/...` 인증 업로드 | 조건부 저장 | **변경 없음** (발행기는 계속 쓸 수 있다) |
| `/_notice/v1/state` 운영자 경로 | 인증 조회/변경 | **변경 없음** (끄기 위해 필요) |

안내는 [관람 접근 문](ACCESS.md)보다 먼저 적용된다. 모든 안내 응답은 `Cache-Control: no-store`, `CDN-Cache-Control: no-store`, `Retry-After: 60`, `X-Robots-Tag: noindex`,
`X-Pitcheezy-Notice: <문구 id>` 헤더를 가진다. 내부 사유·조작자·토큰은 어떤 공개 응답에도 나오지 않는다.

문구는 코드의 고정 목록(`NOTICE_MESSAGES`)에서 **id로만** 고른다. 현재 두 id(`maintenance`, `data_hold`)의 텍스트는
"개발용 안내 문구(승인 전)"로 시작하는 임시 문구다. 자유 입력 문구는 받지 않는다. 실제 공개 문구는 사람이 승인한 뒤 코드 변경으로 바꾼다.

## 상태 저장과 운영자 인증

- 상태는 private R2(`PUBLISH_BUCKET`)의 예약 키 `_notice/state.json`에 있다. 이 키는 공개 허용 목록(`permittedKey`)에 없으므로
  `/v1/...`로 읽히거나 `/_publish/...`로 덮어써질 수 없다(런타임 검사로 확인).
- 운영자 경로 `/_notice/v1/state`는 비밀 `NOTICE_TOKEN_SHA256`가 설정된 배포에서만 동작한다(기본 503 `notice_control_not_configured`).
  값은 운영자별 토큰의 SHA-256 digest를 쉼표로 이은 목록(1~8개)이다. **발행기 토큰(`PUBLISH_TOKEN_SHA256`)과 다른 비밀**이며
  발행기 토큰으로는 스위치를 바꿀 수 없고 운영자 토큰으로는 업로드할 수 없다.
- 토큰은 32바이트 난수의 base64url(43~128자)이며 각 운영자가 스스로 만들어 digest만 계정 담당자에게 비공개로 전달한다.
  원문 토큰·digest·접속 주소는 공개 이슈에 적지 않는다. 설정 검사는 `vars`에 이 digest가 들어가면 거부한다(`inline_secret_not_allowed`).
- 요청 제한은 `PUBLISH_LIMITER`의 별도 키 `notice`를 쓴다(발행기 키 `publisher`와 분리). 잘못된 제한기 응답은 503, 거부는 429다.

### 사용 (토큰은 환경 변수/비밀 저장소에서만 읽는다)

~~~text
# 현재 상태와 최근 감사 기록 20건
curl -sS -H "Authorization: Bearer $NOTICE_TOKEN" https://<호스트>/_notice/v1/state

# 켜기 (상태 객체가 아직 없으면 If-None-Match: *, 있으면 현재 ETag로 If-Match)
curl -sS -X PUT -H "Authorization: Bearer $NOTICE_TOKEN" -H "Content-Type: application/json" \
  -H 'If-None-Match: *' --data '{"active":true,"operator":"<담당 표시>","reason":"<내부 사유>","message_id":"maintenance"}' \
  https://<호스트>/_notice/v1/state

# 끄기 (복구) — 현재 상태의 ETag가 필요하다
curl -sS -X PUT -H "Authorization: Bearer $NOTICE_TOKEN" -H "Content-Type: application/json" \
  -H 'If-Match: "<현재 ETag>"' --data '{"active":false,"operator":"<담당 표시>","reason":"<복구 근거>","message_id":"maintenance"}' \
  https://<호스트>/_notice/v1/state
~~~

본문은 `active`(boolean)·`operator`(`[A-Za-z0-9._-]{1,64}`)·`reason`(1~500자, 제어문자 없음)·`message_id`(목록 값) 네 항목만 받는다.
조건부 쓰기 하나(If-None-Match:* 또는 현재 ETag의 If-Match)를 요구하므로 두 담당자가 같은 상태를 동시에 바꾸면 한쪽은 412다.
412는 "다른 사람이 먼저 바꿨다"는 뜻이다. 상태를 다시 읽고 사유를 확인한 뒤 결정한다.

## 감사 기록

받아들인 변경마다 `_notice/audit/<UTC 시각>-<id>.json`에 `{at, active, operator, reason, message_id, operator_token_prefix(12 hex),
revision, etag_before, etag_after}`를 추가한다(덮어쓰기 금지). 운영자 GET은 최근 20건을 돌려준다. 어떤 digest 접두어가 누구인지는
비공개 운영 기록에 둔다. 상태 객체도 `revision`·`last_change_id`를 갖고 내용이 매번 달라지므로 옛 ETag가 되살아나지 않는다.

내린 뒤에는 규약대로 **사유·시각·영향을 우리 board 또는 관련 mail에 기록**한다(감사 객체는 공개 이슈를 대신하지 않는다).

## 복구 조건

- 끄기는 사람 결정 범위다. 원인을 확인하고 복구 근거를 `reason`에 적은 뒤 현재 ETag로 `active:false`를 보낸다.
- 끈 직후 운영자 GET으로 `state.active=false`와 감사 기록 2건 이상을 확인하고, 공개 GET `/`·`/v1/health.json`이 200으로 돌아왔는지 감시 도구로 본다.
- 켜 둔 동안 들어온 업로드는 그대로 저장되어 있다. 잘못 발행된 자료라면 [RUNBOOK](RUNBOOK.md)의 철회 절차를 먼저 끝낸 뒤 끈다.
- 운영자 토큰을 잃었으면 계정 담당자가 `NOTICE_TOKEN_SHA256`를 새 digest로 바꿔 배포한다(배포 시간이 걸린다). 자동 회전 기능은 없다.

## 로컬 실측 — 2026-10-13

[영수증](../../docs/results/ops/ws_notice_rehearsal_20261013.json): Windows x64·Node 24.1.0·Miniflare 4.20260730.0, 임시 loopback Worker/R2.

| 항목 | 값 |
|---|---:|
| 켜기: 운영자 PUT 왕복 | 18.45 ms |
| 켜기: PUT 200 이후 첫 공개 응답이 안내로 바뀔 때까지 | 11.71 ms (1회 조회) |
| 끄기: 운영자 PUT 왕복 | 17.45 ms |
| 끄기: PUT 200 이후 첫 정상 응답까지 | 7.37 ms (1회 조회) |
| 켜진 동안 인증 업로드 | 200 수락 |
| 켜진 동안 감시 판정 | `failed`, `notice_active=true`, issues `page_notice_active`/`health_notice_active` |

이 값은 **단일 isolate loopback**이다. 게이트웨이는 isolate별로 2초(`NOTICE_CACHE_MS`) 메모를 두므로, 실제 배포에서는
isolate·colo별로 최대 약 2초 + 전파 지연이 추가될 수 있다. 실제 CDN/다중 colo 전환 지연은 **미측정**이다.

## 한계 (주장하지 않는 것)

- **이미 내려받은 자료는 원격으로 삭제하거나 회수할 수 없다.** 안내는 새 응답만 바꾼다.
- 브라우저가 뒤로가기로 옛 문서를 메모리(bfcache)에서 복원하면 옛 화면이 잠시 보일 수 있다. 그 화면의 다음 읽기는 안내를 받는다.
  로컬 Chromium 검사에서는 뒤로가기가 문서를 다시 요청해 안내가 나왔다(영수증의 브라우저 검사 진단 참조). 실제 Safari/모바일은 미검사다.
- 상태 저장소를 읽을 수 없거나 상태 객체가 깨지면 **닫힌 쪽으로 실패**한다(503, 안내 아님·화면 아님). 버킷 binding이 없는 배포에는 스위치가 없다
  (설정 검사가 binding을 요구하므로 실제 배포에는 해당하지 않는다).
- 켜도 요청 과금이 멈추지 않는다. 비용 상한이 아니다.
- Song 공개 화면이 503 `service_notice`를 "안내/중단" 상태로 표시하는지는 **Song 화면의 변경 사항**이다. 아래 요청 초안으로 분리했고 상대 코드는 고치지 않았다.
- 실제 운영자 토큰·계정·도메인·배포는 만들지 않았다. 문구는 승인 전 개발용이다.

## Song 화면 요청 초안 (미발송 — 발신 승인 후 mail로)

> 호스트가 긴급 안내 상태일 때 모든 공개 JSON(`/v1/...`)은 HTTP 503, 본문 `{"error":"service_notice","notice":{"id":"<문구 id>","message":"<문구>"}}`,
> 헤더 `X-Pitcheezy-Notice: <문구 id>`, `Retry-After: 60`, `Cache-Control: no-store`로 응답하고 OPTIONS는 204를 유지합니다.
> 공개 화면이 이 응답을 받으면 (1) 이미 표시된 추천/투구 화면을 새 자료로 갱신하지 않고 (2) "안내 상태"임을 구별해 표시하고
> (3) `Retry-After` 뒤에 health부터 다시 읽는 동작을 요청합니다. 이는 공개 파일 v1에 항목을 추가하는 것이 아니라 HTTP 오류 응답 규칙이며,
> 기존 파일의 의미는 바꾸지 않습니다. 실제 문구·전환 조건은 양쪽 사람이 정합니다.

## 재현

~~~text
cd ops/public-host && npm ci --ignore-scripts && npm run check && npm test
node --test ops/public-host/tests/notice.test.mjs
node ops/public-host/rehearse-notice.mjs --output .cache/notice-rehearsal-new.json
cd tests/browser && BROWSER_ENGINE=chromium npm run test:host
uv run --frozen python -m pytest tests/test_public_host_config.py -q
~~~

검증 결과(2026-10-13, Windows): 신규 Node 7(단위·메모·감시·실제 로컬 Worker/R2 런타임)·전체 Node 102 통과, 브라우저 Chromium 호스트 묶음 11 통과
(WebKit은 CI), Python 설정 검사 67·관련 132 통과, 리허설 영수증 passed. 작성 모델 Claude Fable 5.1(`claude-fable-5-1`);
**다른 모델의 출시 검토(WS-review1)는 아직 없다.** 실제 운영 투입 전 조건이다.
