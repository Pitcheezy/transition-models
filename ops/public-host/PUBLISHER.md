# 단일 파일 전송 후보 — WS-ops1c

우리 Worker의 제안 업로드 방식을 사용하는 운영자용 Node24 도구다.
Song 발행기·원장·공개 JSON 계약·다중 파일 순서는 구현하거나 변경하지 않는다.
입력 JSON은 담당 validator와 공개 범위 검토를 먼저 통과해야 한다. 본 도구는 JSON object·SHA만 확인하며
성공 응답도 항상 schema_validated=false다. 현재 실제 계정에는 한 번도 전송하지 않았다.

## 기본 실행은 dry-run

저장소 루트에서 다음은 파일만 읽는다. 토큰을 조회하거나 DNS/네트워크를 사용하지 않는다.

~~~text
node ops/public-host/publisher-cli.mjs --plan ops/public-host/examples/publish-plan.json
~~~

예제 대상·경기는 가상이며 payload에 synthetic:true가 있다. 예제 바이트는 .gitattributes로 고정했다.
이 예제에 --execute를 붙여 실제 서비스로 보내지 않는다.

계정/계약/공개 범위가 준비된 운영자가 **별도로 준비한 비공개 계획 파일**을 실행할 때만:

~~~text
node ops/public-host/publisher-cli.mjs --plan PRIVATE_REVIEWED_PLAN --execute
~~~

실행 직전에 비밀 저장소로부터 환경변수 PITCHEEZY_PUBLISH_TOKEN을 제공한다.
토큰은 인자·계획 파일·URL·이슈에 적지 않는다. dry-run은 토큰을 읽지도 않는다.
확인 없이 --execute를 붙이는 CI/상시 작업은 없다. 이 도구는 배포 도구가 아니다.

## 계획 형식

pitcheezy-upload-plan-v1은 **우리 운영 도구 형식**이며 Song 공개 데이터 형식과 다르다.
필드는 schema, origin, allow_loopback_http, method, path, condition, source_file, sha256다.

- origin: canonical HTTPS origin만. 사용자정보·경로·쿼리·fragment를 금지한다.
  로컬 합성 검사만 allow_loopback_http:true와 127.0.0.1/::1의 HTTP를 사용할 수 있다.
- path: gateway.permittedKey와 동일한 /v1/... 허용 경로. 도구가 /_publish를 앞에 붙인다.
- PUT 첫 생성: condition={"if_none_match":"*"}. 갱신/복원: {"if_match":"정확한 quoted ETag"}.
- DELETE: if_match가 필수다. Worker는 물리 삭제 대신 tombstone을 쓴다.
- HEAD: condition/source_file/sha256 모두 null이며 본문 없이 현재 메타데이터만 읽는다.
- PUT source_file: 계획 폴더 기준 상대 .json 파일. 상위 경로·절대 경로·링크를 거부한다.
  sha256은 **파일 원본 바이트**의64자리 소문자 SHA다. 재직렬화·줄바꿈 변환 없이 보낸다.
- DELETE source_file/sha256은 null이다. 성공 응답의 SHA는 빈 본문의 SHA다.

입력 계획16KiB·본문5MiB 상한이다. 본문은 처음 한 번 읽어 복사하고 재시도 때 다시 파일을 읽지 않는다.
기존 입력과 저장소 파일을 변경하거나 영수증 파일을 자동으로 만들지 않는다.
필요하면 stdout 영수증을 비공개 운영 기록으로 저장한다. 영수증에는 토큰·origin·본문·원문 오류가 없다.
신뢰한 로컬 폴더에서 사용한다. 적대적인 다른 프로세스의 동시 파일 변경을 OS 수준으로 격리하는 도구는 아니다.

## 재시도와 결과 의미

네트워크 구간은 최대3회·요청당5초·총20초다. 총시간은 연결·응답 본문·대기를 포함한다.
로컬 파일 읽기/검사 시간은 별도다. 리다이렉트는 따라가지 않으며 쿠키를 사용하지 않는다.
429·5xx·네트워크 장애는 조건과 바이트를 그대로 유지해서만 제한적으로 재시도한다.
Retry-After가 남은 시간보다 길거나 판독 불가하면 deferred/unknown으로 종료한다.
HTTP-date Retry-After는 지원하지 않으며 일정을 임의로 앞당겨 보내지 않는다.

- dry_run: 네트워크0. 실행 준비 검사만 통과.
- stored: 계약에 맞는200과 ETag·SHA·stored/deleted를 확인. 모델/공개 의미 검증 아님.
- observed: HEAD 메타데이터 확인. 본문 바이트/정합 검사가 아니며 내가 저장했다는 증거도 아님.
- missing: HEAD404. 정상 진단 결과이지 PUT 성공이 아님.
- rejected: 문서화된 저장 전 거부. 401/403/428·검증 오류를 자동 재시도하지 않는다.
- conflict: 불확실한 선행 요청 없이412를 받음. 현재 원장/버전을 다시 확인한다.
- unknown: 저장됐을 수도 있음. 연결/본문 시간초과·5xx·미검증200·예상 밖2xx·408 등이 해당한다.
- conflict_or_already_applied: 불확실한 전송 뒤412. 이전 요청 성공인지 다른 발행과 충돌인지 모름.
- deferred/unavailable/invalid_response: 제한·가용성·응답 계약을 확인 후 재개한다.

**412 뒤 최신 ETag를 자동으로 구해 낡은 본문을 다시 쓰지 않는다.** unknown도 실패로 확정하지 않는다.
별도 HEAD와 원본 SHA·발행 원장을 담당자가 대조한다. SHA가 같아도 누가 쓴 것인지/여러 파일이 같은
발행 묶음인지까지 증명하지 않으므로 임의로 원장의 완료 표시를 바꾸지 않는다.
재실행도 같은 계획으로 시작하고, 새 조건을 선택하려면 원본·순번·정정 상태를 먼저 확인해야 한다.

종료0=dry_run/stored/observed/missing, 종료1=확정 충돌/거부/응답 문제,
종료2=입력/도구 오류, 종료3=unknown/conflict_or_already_applied/deferred/unavailable이다.
**종료0만 보고 업로드 성공으로 해석하지 말고 outcome을 확인한다.**

## 검증 범위

신규17검사: 고정조건/바이트, SHA, 인증/입력 거부, 원문오류 비반사, 예상 밖2xx·408,
실제 loopback의 느린 본문/무응답/긴429/리다이렉트 차단, CLI dry-run/실행, 실제 로컬 Worker/R2의
생성·HEAD·철회·동일본문복원·낡은ETag거부를 확인했다. 별도 Codex가 최초14검사와 오류를 점검했다.

~~~text
node --test ops/public-host/tests/publisher.test.mjs
~~~

Windows 로컬 workerd에서는 취소/종료 때 WSARecv #64 진단이 재현된다. 기능 검사는 통과하고,
그 후 복원 JSON 조회도 성공했다. 이 진단을 해결했다고 하거나 실제 CDN 문제로 확정하지 않는다.
실계정 TLS/비밀회전/Cloudflare limiter·Song 원장 재시작·전체 발행 묶음 검증은 별도다.
