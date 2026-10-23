# 호스트 질문 4개 답안·새 최종본 수신 준비 — 2026-10-23

우리 코드 기준 `ecc9d7bd808e8a6bb8dcb89b1bd62456fd3b7780`(PR #57 병합), 선점 `dae4b3d`.
[상대 공식 회신](https://github.com/SongRoute/pitcheezy/issues/38#issuecomment-6343676338)을 읽고 우리 소스·기존 합성 검사를 확인했다. 우리 운영 코드·설정·팀원 코드·프로세스·배포는 변경하지 않았다. 회신은 미발신 초안이다.

## 1. 안내 고정 문구

`ops/public-host/notice.mjs:18`의 문구는 다음과 같다.

- `maintenance`: “개발용 안내 문구(승인 전): 서비스 점검 중입니다. 잠시 후 다시 확인해 주세요.”
- `data_hold`: “개발용 안내 문구(승인 전): 자료 확인 중이라 화면을 잠시 내렸습니다.”

둘 다 **새로고침 지시가 없다**. 문구는 개발용·승인 전 표시이며 현재 배포 문구와 같다고 확인한 것은 아니다. 임의 문구 변경·배포·외부 공지는 하지 않는다. Song은 새 화면에서 안내 시 카드·존 숨김/정상 응답 시 복원을 고쳐 전달하겠다고 보고했으나 새 파일을 받지 않았다.

## 2. 안내와 발행의 요청 제한

- `notice.mjs:94`: 같은 `PUBLISH_LIMITER` binding에 `key: "notice"`를 사용한다. 인증된 관리자 GET/HEAD/PUT은 이 키를 사용한다. PUT의 조건/본문 검사가 실패해도 앞선 limiter 호출은 이미 수행될 수 있다.
- `gateway.mjs:103`: 발행은 `key: "publisher"`. 같은 binding이지만 집계 키가 다르다.
- 기존 9회 안내 드릴을 경로에 대입하면 관리자 GET3+PUT2는 notice 5회, 일반 홈/health GET4는 notice/publisher 모두 0회다. 이 횟수는 **코드 경로 대조**이며 9회 드릴을 새로 실행한 결과는 아니다.
- 로그인 POST는 `access:<HMAC>`라는 별도 키다(`access.mjs:114`). 이 키·비밀·쿠키의 실제 값을 기록하지 않는다.
- 따라서 ‘같은 publisher 집계 키를 소모하므로 120초 대기’라는 전제는 현재 소스에 해당하지 않는다. 실제 배포 binding 값·WAF 등 별도 제한은 아직 미확인이다. 예제의 60회/60초를 실설정으로 주장하지 않는다.

[Cloudflare 공식 설명](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/)도 namespace/key와 처리 위치별 집계를 설명한다. 이 제한은 공동 원장의 정확한 총 요청 예산을 대신하지 않는다.

## 3. 옛 관람 세션 회수의 기대 응답

**접근 문 ON·notice OFF·제거 대상 외 유효 digest 최소 1개 유지**일 때, 옛 쿠키로 `GET /`를 보내면 HTTP401, 로그인 HTML, `X-Pitcheezy-Access: required`, `Cache-Control: no-store`다. 리다이렉트가 아니므로 `Location`은 없다. `/v1/*`는401과 `{"error":"access_required"}`를 돌려준다. 근거: `access.mjs:96`, `gateway.mjs:307`.

주의할 다른 경우:

- digest를 전부 없애면 설정 오류503(`access_not_configured`)이다. 401 회수 증거가 아니다. 회수 확인용 남은 digest는 기존 적법한 다른 코드 또는 전달/사용하지 않는 새 폐기용 값이어야 하며, 새 접속 대상 추가로 취급하지 않는다. 실제 설정 변경은 별도 승인 범위다.
- notice ON이면 안내503이 관람 검사보다 먼저 나온다. 기존 안내를 401 획득 목적으로 자동으로 끄지 않는다.
- `GET /_access/v1/session`은 무효 쿠키에도200·`authenticated:false`라 이번 401 확인 대상이 아니다.
- 접근 문 OFF는 회수 검증이 아니다. 단순 logout도 복제된 쿠키를 회수하지 않는다. 옛 digest를 재추가하면 세션이 되살아날 수 있다.
- 관람 자격과 발행 bearer는 독립이다. 발행401은 유효한 폐기용 digest 적용 후 옛 bearer로 확인하며, 업로드OFF/설정 누락503으로 대신하지 않는다.

근거: `access.mjs:32`, `:216`, `gateway.mjs:69`, `:301`; 기존 `tests/access.test.mjs`의 잘못된 설정·코드 제거·notice 우선순위 검사 통과.

## 4. 요청 대상·범위·만료의 서버 증거

아직 확보됐다고 답할 수 없다. `gateway.mjs:84`와`:328`은 요청 경로의 key와 환경변수 `PUBLISH_KEY_SCOPE`/`PUBLISH_EXPIRES_AT`를 검사한다. scope/expiry는 요청 필드가 아니다. 다른 키403과 만료403은 HEAD에서 본문이 없어 구분할 수 없다.

자체 요청별 로그/ID가 없고 설정 예제에 observability 선언이 없다. 이는 Cloudflare에 별도 로그가 없다는 증거는 아니다. [공식 조회 도구 설명](https://developers.cloudflare.com/workers/observability/query-builder/)은 요청 path/status 조회를 지원하지만, **우리 계정에서 활성화됐는지·해당 요청이 누락 없이 남는지·설정/버전에 연결되는지는 미확인**이다.

읽기 확인 순서:

1. 실제 Worker 배포 version과 트래픽 배분, 고정 source/runtime5의 원본·CR 제거 SHA 대응, 비밀을 제외한 scope/expiry 설정을 확인한다.
2. 기존 요청 기록의 시간·method·path·status·가능한 request ID/version, 보관 구간·샘플링·누락 여부를 확인한다. 집계 건수나 성공 객체 metadata만으로 거부된 HEAD의 대상 일치를 증명하지 않는다.
3. 시험 구간 설정/배포 변경 이력을 함께 대조한다. 시작/종료 스냅샷이 같다는 것만으로 중간 불변을 주장하지 않는다. 관리 감사가 실제 값을 제공하지 않으면 그 한계도 남긴다.
4. 실제 secret/Authorization/Cookie/전체 원시 로그를 공개 문서·이슈에 옮기지 않는다. 확인한 최소 근거의 비공개 원장/해시와 공개 요약을 구분한다.
5. 로그가 없거나 불완전하면 해당 합격 조건은 HOLD다. 이 작업에서 logging 설정을 켜거나 tail을 실행하거나 새 코드/권한을 배포하지 않는다. 수정 실행본이나 대체 근거의 수용은 별도 결정이다.

조회용 Cloudflare 탭은 현재도 2단계 인증 선택 안내를 표시했다. 이전 자동 승인 검토가 Skip 클릭을 보안 선택으로 거절했으므로 우회하지 않았다. 사용자 화면의 도메인 등록 완료와 실제 Worker 상태를 혼동하지 않는다. 마지막 실자원 확인10/16을 현재 확인으로 재사용하지 않는다.

## 5. 새 회신 반영과 수신 후 순서

- final2/v4.4의 전체 외부 SHA는 이제 #38의 값과 기존 보관값이 일치한다. 과거의 ‘외부 전체값 미확인’ 조건은 해소됐다. 원본/과거 실패 기록은 보존한다.
- v7/v4.5는 **전달 예정**이다. 새 고정 커밋으로 화면 수정·핀 갱신을 한다는 상대 보고이며 우리 파일 수신/검증/배포 완료가 아니다. 원래 final2/v4.4 후보를 새 실행본으로 간주하지 않는다.
- 세 결함은 새 v7에서도 미수정이라는 회신이다. OPS-CRED-01은 공동시험 미사용·운영 env 경로, ONEKEY-PROBE-01은 불변 원장+호스트 증거, OPS-ALERT-JSON01은 운영자 수동 감시라는 상대 제안을 구별한다. 우리 수용/운영 승인으로 바꾸지 않는다.
- 10/22 시험·판정은 상대가 미실시로 확인했다. 10/23 15:00 전달·17:30 준비 판단·18:00~19:30 시험·21:00 판단은 새 제안이다. 10/22 참석 답변을 새 창 GO로 재사용하지 않는다. CSS/문구 변경의 동결 예외도 사람 결정 미확인이다.

새 ZIP 수신 시 아래 순서로 진행한다. 아직 실행하지 않았다.

1. 원본을 별도 비공개 폴더에 보존하고 ZIP 전체 SHA/크기, 경로이탈·중복·case충돌·링크·암호화·CRC와 manifest를 확인한다. 불일치는 기존 파일을 덮어쓰지 않고 중단한다.
2. v7 등록/실행본/manifest와 v4.5 source/build·검토 대상이 같은 최종 커밋을 가리키는지 대조한다. runtime5 원본/CR제거 해시를 우리 고정본과 비교한다. 작성·검토 모델 ID 및 검토한 해시·남은 조건을 확인한다.
3. 기존 전달본 대비 변경 목록을 읽는다. ‘화면/핀만 변경’ 보고와 다르면 범위를 확인하고 등록·검토를 재평가한다. 3결함 수정으로 오인하지 않는다. 원본 Windows `verify_offline.py`의 fcntl 실패를 반복하거나 shim하지 않는다.
4. 우리 loopback 검증에서 안내ON 때 **이미 열린 화면의 추천 카드·존이 모두 숨겨지는지**, OFF 후 정상 응답에서 새로고침 없이 복원되는지 확인한다. 예전34기능 통과와 이 수정의 검증을 구분하고 새 요청 수를 기록한다.
5. 무결성/변경 검증 후에만 우리 후보를 새 폴더로 구성한다. 기존 `scripts/build_public_host_release.py check <새 release.zip>`·`scripts/check_public_host_config.py <새 candidate>`를 사용한다. 파일/CLI 모양이 달라지면 먼저 help/계약을 확인한다. 실제 배포는 이 절차에 포함하지 않는다.

## 6. 이번 검증

```text
node --test --test-reporter=dot ops/public-host/tests/notice.test.mjs ops/public-host/tests/access.test.mjs
node --test --test-reporter=tap ops/public-host/tests/publish-scope.test.mjs
PYTHONUTF8=1 python -B -m pytest tests/test_checklist_model.py -q -p no:cacheprovider
```

Node 기존 검사24+12=36 통과(메모리/loopback 합성, 실제 Cloudflare 요청 아님). 체크리스트8개·상대 링크17개·소스8파일 원본/CR제거 SHA·신규 문서 정보 제외·diff 검사 통과. 전체 모델/운영 검사는 변경과 무관해 반복하지 않았다. 정형 근거는 [JSON 기록](results/ops/ws_host_questions_20261023.json), SHA-256 `4df6590d23a8a802909a8b22079a22b6f0310c7c20b4b32eed8483b252195e47`다. 소스 원본/CR제거 SHA와 조회 본문 SHA도 기록했다. 별도 에이전트의 우리 소스·최종 문서·해시 읽기 대조는 PASS이며, 새 운영코드에 대한 다른 모델 검토를 의미하지 않는다.

[보낼 회신 초안](mail_drafts/COLLAB-001-host-answers-draft-20261023.md)은 발신 전이다. 실제 Cloudflare 로그·새 파일·새 창/동결 예외/배포·접속/GO 조건은 남아 있다.
