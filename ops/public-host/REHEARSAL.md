# 로컬 호스팅 리허설 — WS-ops4c

이 도구는 **새 임시 Miniflare/workerd + R2만** 사용한다. 외부 대상 주소·계정·실제 자료를 입력받지 않는다.
공개 CDN 용량, 실제 사용자 수, Song 화면/계약/모델 성능을 측정하는 도구가 아니다.
소스 SHA·Node/Miniflare·OS 종류와 각 단계 결과를 JSON으로 남긴다. 인증값·접속 주소는 보고서에 없다.

## 실행

Node24, ops/public-host에서 npm ci --ignore-scripts를 먼저 실행한다. 저장소 루트에서:

~~~text
node ops/public-host/rehearse-local.mjs --requests 120 --concurrency 6 --bytes 32768 --output .cache/local-rehearsal-new.json
~~~

기본값은 위와 같다. 출력 파일 부모 폴더는 있어야 하고, 기존 파일은 덮어쓰지 않는다.
요청1~1000개, 동시1~16개, 파일256B~1MiB, 정상 부하의 총 본문64MiB 상한이다.
90초 요청/시작 중단 신호와 최대5초 정리 상태 판정을 사용한다. 정리가 failed/unconfirmed면 passed=false다.
unconfirmed는 런타임 강제 종료를 보장하지 않으며, 해당 실행의 로컬 자원 상태를 확인해야 한다.
기존 프로세스·서버·포트·자료는 삭제하거나 종료하지 않는다.

## 단계

1. 합성 game/health 파일 게시와 워밍업.
2. 고정 본문을 동시 GET. 각 응답의 상태·본문 길이·SHA·Date/Age·no-store 확인.
3. 같은 ETag로 두 갱신: 하나200·하나412 확인.
4. 삭제 후 GET/HEAD404, 같은 본문 복원 후 새 ETag, 낡은 삭제 ETag 거부 확인.
5. 합성 발행 시각을 stale로 바꿔 감시 실패1회/장애open2회, 정상1회/복구2회 확인.

이 단계들은 순차 실행한다. 의도한404·stale 구간은 정상 GET 부하 집계에 섞지 않는다.
요청 중인 작업을 모두 회수한 뒤 다음 단계로 진행하고, 정리 결과를 별도로 기록한다.
latency는 요청 시작부터 본문 수신·SHA 검사 완료까지다. 성공 응답만 p50/p95를 계산하고,
실패 수·코드·실제 최대 동시 요청 수를 함께 남긴다. 성공 표본이 없으면 null이다.
이 수치는 고정 동시 요청 폐쇄루프의 로컬 값이며 실제 접속자 처리량이나 SLO가 아니다.

## 확인 결과 — 2026-10-12

[고정 합성 실행 영수증](../../docs/results/ops/ws_local_rehearsal_20261012.json):
Windows x64·Node24.1.0·Miniflare4.20260730.0, 32KiB·동시6·120/120 성공, 실패0.
로컬 p50 21.50ms / p95 26.35ms. 시작346ms와 정상 GET444.14ms를 따로 기록했다.
전체1281ms, cleanup complete. 한 번의 개발 실행이며 대외 성능 홍보값이 아니다.

신규Node5검사와 별도 Codex 독립5검사를 통과했다. Chrome/WebKit 각2개 브라우저 검사도 통과했다.
브라우저는 합성 화면의 버튼으로 같은 Worker GET만 읽는다. 게시·삭제는 Node 측에서 수행하고,
토큰을 HTML/브라우저 전역으로 넘기거나 응답을 Playwright mock으로 바꾸지 않는다.
375px 화면·키보드·새 버전/삭제/복원과 실제 JSON404를 확인했다. 실제 Mac/iPhone 검사는 아니다.

Windows WebKit 종료 시 workerd의 WSARecv #64 연결 종료 진단이 두 번 재현됐다.
기능 검사와 브라우저 종료 후 Worker GET200은 통과했지만 이 런타임 진단을 해결했다고 하지 않는다.
운영 CDN/실제 Safari 결과와 구분한다. stderr를 숨기지 않았다.

## 회귀 명령

~~~text
node --test ops/public-host/tests/rehearsal.test.mjs
~~~

브라우저는 tests/browser/README.md에 따른다. CI가 잠긴 Miniflare/Playwright 의존성을 설치하고
두 엔진을 검사한다. 새 시도마다 임시 저장소·임시 인증값을 만들어 끝나면 정리한다.

## 실행 위치 수정

첫 Linux 브라우저 CI에서 `tests/browser` 실행 위치를 기준으로 Worker 모듈 이름에 상위 경로가 생겨 시작이 실패했다.
Windows에서도 같은 폴더에서 재현했다. Miniflare `modulesRoot`를 호스트 소스 디렉터리에 고정하여 실행 위치 의존을 제거했다. 기존 측정 영수증은 수정 전 소스의 Windows 측정 기록으로 보존한다.

## 운영 CLI 조합 리허설 — WS-laptop1

최근 운영 경로인 `publisher-cli.mjs`, `notice-cli.mjs`, `monitor-runner-cli.mjs`를 **실제 별도 Node 프로세스**로 실행한다.
기존 API별 리허설을 대신하는 부하 시험이 아니다. 입력은 새 출력 파일 경로 하나뿐이며 대상 주소·포트·토큰·계정은 입력받지 않는다.

~~~text
node ops/public-host/rehearse-operator-tools.mjs --output .cache/operator-rehearsal-new.json
node --test ops/public-host/tests/operator-tools-rehearsal.test.mjs
~~~

Node24와 기존 고정 Miniflare가 필요하다. 설치나 Wrangler 실행을 자동으로 하지 않는다. 출력 파일의 부모 폴더는 있어야 하며,
기존 출력·없는 부모·외부 대상 인자는 런타임 시작 전에 거부한다. 실행 중 다른 작성자가 출력 파일을 만들면 덮어쓰지 않는다.

새 임시 폴더의 R2와 `127.0.0.1`의 OS 할당 포트만 사용한다. 관람 접근 문 ON, 수집/피드백 OFF,
정확한 `v1/health.json` 발행 범위와 별도 합성 발행/안내/관람 자격을 만든다. 자식 프로세스에는 OS 필수 환경과
각 도구의 합성 자격만 전달한다. 기존 계정·프록시·Node preload 환경은 상속하지 않고 부모 환경도 변경하지 않는다.

검사 순서는 다음과 같다.

1. 세 CLI dry-run과 상태·잠금·안내 snapshot 미생성, 쿠키 없는 화면/JSON의401.
2. 생성·비공개 HEAD·갱신·낡은 조건412, 조건부 철회·tombstone HEAD·공개 GET/HEAD404·현재 tombstone 조건 복원.
3. 실제 감시 CLI의 코드 로그인, 정상1회·오래된 발행2회·정상2회. 같은 상태 파일을 재사용하고 opened/recovered와 두 담당자의 **모의** 알림을 확인한다. 복구 실행의 첫 표본에는 열린 장애가 있으므로 종료1을 보존한다.
4. 안내 CLI GET snapshot의 조건으로 ON, 안내 상태 감시, 새 snapshot의 조건으로 OFF, 감시 복구. 2초 안내 memo를 고려한다.
5. 다른 허용 키의 PUT/DELETE/HEAD403과 원본 바이트/ETag 보존. 그다음 자기 런타임을 정상 종료하고 같은 임시 R2에 만료된 설정으로 새 런타임을 시작하여 같은 키의 세 메서드403·원본 보존·안내OFF를 확인한다.
6. 계획/본문 원본 SHA 보존, CLI 출력·영수증과 JSON 파일의 토큰/코드/쿠키 미포함, 남은 잠금 없음, 자기 자식 프로세스·런타임·임시 폴더 정리.

전체 요청 작업의 중단 신호는60초, 자식 실행 대기는25초다. 자식 종료 요청 뒤5초 안에 `close`가 없으면 미확인으로 실패한다.
런타임 정리도 최대5초 판정이며, 종료가 확인되지 않으면 임시 폴더를 보존하고 `passed:false`로 기록한다.
OS/파일시스템 지연을 포함한 강제 종료 시각 보장은 아니다. 기존 프로세스 검색·종료, 포트 해제, 실제 서비스 변경은 하지 않는다.

영수증에는 소스 SHA·OS/Node/Miniflare·실제 CLI 호출 수/결과·장애 이력·정리 결과가 남고 주소·토큰·쿠키·개인 경로는 남지 않는다.
전체 HTTP 요청 수는 별도 관측하지 않아 null이며 **18요청/120초 공동 시험 예산 통과 증거가 아니다**.
만료는 과거 만료 설정의 로컬 재시작 검사로, 실제 시계의 만료 경계 통과는 미측정이다. 실제 Ctrl+C·Mac·Cloudflare·Song 발행기·실경기·외부 알림은 검증하지 않는다.
Windows workerd의 기존 WSARecv/WSASend 연결 종료 진단이 나올 수 있으며 이를 해결했다고 처리하지 않는다.
## 같은 런타임의 실제 만료 경계

`node ops/public-host/rehearse-live-expiry.mjs --output .cache/new-live-expiry.json`

새 loopback Worker1개·합성키1개에서 실제 만료를 기다리고 PUT/DELETE/HEAD403과 저장값 보존을 확인한다. 전체HTTP18/본문2KiB/부팅·대기·정리포함120초를 계수한다. 외부 대상·자격을 받지 않으며 실제 공동 시험이 아니다. [범위·결과](../../docs/WS_LIVE_EXPIRY_20261018.md).

## 전시회 고정 간격 폴링 — WS-capacity1

기존 폐쇄루프 모드와 별도의 `viewer-polling` 프로필이다.

~~~text
node ops/public-host/rehearse-local.mjs --mode viewer-polling --viewers 30 --output .cache/viewers30-new.json
node ops/public-host/rehearse-local.mjs --mode viewer-polling --viewers 50 --output .cache/viewers50-new.json
python scripts/218_estimate_viewer_budget.py --examples
~~~

30/50 가상 세션, 접근 문 ON, 임시 loopback Worker/R2만 사용한다. 5초 간격6슬롯·슬롯당2파일·각32KiB로 부하GET360/600건이며 준비 요청은 별도다. 마지막 예정 시작은25초다. 실제 사용자 브라우저·공용 CDN 용량 검사가 아니다. 지연500ms 초과/슬롯경계 초과/요청 실패는 중단하며 늦은 poll을 몰아 실행하지 않는다. 기존 closed-loop의 `--requests`/`--concurrency`/`--bytes`와 섞을 수 없다. 출력 경로는 실행 전에 확인하고 기존 파일을 덮어쓰지 않는다.

[합격 조건·실측·예산·한계](../../docs/WS_EXHIBITION_CAPACITY_20261025.md)를 함께 읽는다. Free 일일 예산 계산은 Paid 월간 비용 추정과 별개이며 계정 잔량을 API로 읽거나 설정/요금제를 바꾸지 않는다.

## 받은 전시 빌드의 우리 호스트 설치 리허설 — EXHIBIT-host1

받은 전시 빌드(정적4파일 + v1자료)를 **우리 호스트 계약대로 나누어** 로컬 Worker에 설치하고 읽어 보는 리허설이다.
정적4파일(index.html, favicon.svg, assets/index-*.js, assets/index-*.css)은 ASSETS binding으로, v1자료는 실제 인증 업로드 경로
`/_publish`(첫 생성 `If-None-Match: *`)로 올려 발행 기록 형식으로 저장된 뒤 공개 `/v1`로 읽는다. site/ 전체를 ASSETS나 R2에 그대로 복사하지 않는다.
입력은 인수 영수증(`pitcheezy-exhibition-intake-v1`)과 추출본 폴더이며, 모든 파일의 바이트 수·원본 SHA-256과 파일 집합이 영수증과 같아야 시작한다.
분류에서 벗어난 파일, 정적 파일 수 불일치, 허용되지 않는 v1 키, 자료 수 불일치(`--expect-data`, 기본24)는 거부한다.
받은 파일은 읽기만 하며 바이트로 올린다. 경기 파일 내용은 분석하지 않는다(평가 잠금 849844 포함).

~~~text
node ops/public-host/rehearse-exhibit-host.mjs --site <추출site> --receipt <intake-receipt.json> --out <새폴더> [--browser] [--access] [--playwright <playwright 모듈 경로>]
node --test ops/public-host/tests/exhibit-host.test.mjs
~~~

`--out`은 없는 폴더여야 하고 영수증은 `<새폴더>/receipt.json`, 화면은 같은 폴더의 PNG다. 입력 검증·분류를 통과한 뒤에만 폴더와 런타임을 만든다.
`--browser`는 설치된 Chrome(Playwright channel chrome, headless)으로 1440×900·390×844에서 `/?game=849843` 표시, 첫 투구 문구, 가로 넘침·페이지 오류 없음을 확인하고,
실제 `/_notice` 스위치 ON→앱의 추천 목록 숨김·안내 문구, OFF→새로고침 없이 복원(각 최대40초 실시간 대기)을 본다. loopback 외 요청은 모두 차단한다.
`--access`는 접근 문 ON으로 시작해 쿠키 없는 401, 로그인 화면 401, 실제 form 로그인 뒤 앱 표시와 `/v1` 읽기를 확인한다. 접속 코드는 출력·영수증에 넣지 않는다.
날짜 목록에만 있고 파일이 없는 날짜의 `/?date=` 진입은 **관찰 기록**이며 합격 판정이 아니다.

Node 검사는 합성 4+6 미니 빌드만 쓴다. 종료0은 모든 검사 통과, 1은 검사 실패(영수증 기록), 2는 입력/출력 거부다.
이것은 Cloudflare가 아니다. 정적 파일 처리는 Node 흉내(정확한 경로·`/`·HTML 수용 미스→index.html)이고 CDN·TLS·실도메인·실기기·저장 로그 대조는 없다.
안내 문구는 승인 전 개발용 문구다. 누락된 날짜 파일은 그대로 404다. 2026-11-01 두 실행(--browser 84/0, --browser --access 92/0)의 영수증은 Git 제외 로컬 폴더에 있다.

## ③ 준비 도구 — 배포된 호스트 읽기 전용 검사·업로드 계획·발행 토큰 (EXHIBIT-host1)

실제 Cloudflare 배포(③)는 사용자 로그인과 승인 뒤에만 한다. 아래 세 도구는 그 전후에 **이 노트북에서** 돌리는 보조 도구이며 배포·업로드·안내 전환을 하지 않는다. 순서와 운영자 명령은 [docs/EXHIBIT_HOST_DEPLOY_STEPS_20261101.md](../../docs/EXHIBIT_HOST_DEPLOY_STEPS_20261101.md)에 있다.
세 도구와 공용 모듈 `exhibit-site.mjs`(영수증 검증·site 바이트 대조·분류·정적 파일 흉내·`hash`; `node:` 모듈과 우리 gateway/notice/access 코드만 import)는 `ops/public-host/node_modules`(Miniflare) 없이도 실행된다. `rehearse-exhibit-host.mjs`는 같은 함수를 `exhibit-site.mjs`에서 가져와 재수출한다(`tests/exhibit-tools-imports.test.mjs`가 import 그래프와 자식 Node import로 확인).

~~~text
node ops/public-host/verify-exhibit-remote.mjs --origin https://<호스트> --site <추출site> --receipt <intake-receipt.json> --out <새파일.json> [--game 849843] [--expect-data 24] [--notice-check]
node ops/public-host/exhibit-upload-plans.mjs --site <추출site> --receipt <intake-receipt.json> --out <새비공개폴더> [--origin https://<호스트>] [--head | --if-match '<키>="<32hex ETag>"' ...]
node ops/public-host/exhibit-token-helper.mjs --out <새비공개파일> [--config <후보>/host/wrangler.deploy.json]
node --test ops/public-host/tests/verify-exhibit-remote.test.mjs ops/public-host/tests/exhibit-upload-plans.test.mjs ops/public-host/tests/exhibit-token-helper.test.mjs ops/public-host/tests/exhibit-tools-imports.test.mjs
~~~

- **verify-exhibit-remote**: 배포된 호스트를 GET/HEAD로만 읽는다. 입력 검증·분류는 `exhibit-site.mjs`의 함수를 쓴다(영수증·site 바이트 일치 뒤 시작).
  자료 24개 전부 바이트 = 원본 SHA(`Cache-Control: no-store, no-transform`·ETag 확인), 정적 4개·`/`·`/?game=`가 원본 index.html, 없는 경기·목록에만 있는 날짜 404, `HEAD /v1/manifest.json`을 확인한다.
  `--origin`은 경로·쿼리·사용자정보 없는 https 출처만 받고, `http://127.0.0.1:포트`는 `--allow-loopback`(검사용)일 때만 받는다. 리다이렉트는 따라가지 않고 실패로 적는다
  (예외: Cloudflare 정적 파일이 `/index.html`을 `/`로 보내는 경우만 `/` 비교로 대신한다). 요청당 15초, 전체 5분.
  환경 변수 `PITCHEEZY_ACCESS_CODE`가 있으면(앞뒤 공백·CR/LF는 지우고 받는다 — 파일에서 `Get-Content -Raw`로 읽어도 된다) `/_access/v1/session`에 JSON 로그인 1회 뒤 쿠키를 메모리에만 들고 읽는다. 영수증(`pitcheezy-exhibit-remote-verify-v1`, stdout과 `--out`)에는 출처·코드·쿠키가 없고
  `access_used`·로그인 상태만 남는다. `--notice-check`는 `/v1/manifest.json`이 503+안내 머리말인지 기록만 한다(운영자 경로를 읽거나 바꾸지 않는다). CDN은 `Age`·`CF-Cache-Status` 머리말 기록만이며 브라우저 검사가 아니다.
  종료0은 전부 통과+영수증 기록, 1은 검사 실패, 2는 입력·출처 거부. 통과는 "지금 호스트가 원본 바이트를 답한다"까지이며 누가 올렸는지는 증명하지 않는다. 요청 수는 접근 코드 ON·`--notice-check`일 때 35(로그인 1·manifest 2·자료 23·정적 4·`/` 2·404 2·HEAD 1), `--notice-check` 없이 34.
- **exhibit-upload-plans**: 기본은 자료 파일마다 `publisher-cli` PUT 계획(`pitcheezy-upload-plan-v1`, `If-None-Match: *`) 하나와 바이트 복사본을 **새 비공개 폴더**에 만든다(setup→game→games→dates→manifest→health 순, `index.json` 포함).
  `--head`는 대신 HEAD 계획만 만든다(`head-NN-….json`, condition·source_file·sha256 null, 바이트 복사본 없음) — 실행하면 키가 이미 있는지(`observed`+ETag·현재 SHA) 없는지(`missing`) 알 수 있고 아무것도 쓰지 않는다.
  `--if-match '<키>="<32자리 hex ETag>"'`(반복 가능)는 그 키의 PUT 계획을 `{"if_match": ETag}`로 바꿔 기존 기록을 교체한다(HEAD로 받은 ETag 그대로, 따옴표 포함). 형식이 틀린 ETag·site에 없는 키·중복 키는 `if_match_invalid`·`if_match_unknown_key`·`if_match_duplicate_key`로 거부하고, `--head`와 함께 쓰면 `head_excludes_if_match`다. `index.json`은 키 이름만 적고 ETag는 적지 않는다.
  `--origin`을 생략하면 URL이 아닌 자리표시자가 들어가 dry-run도 거부되므로 실행 전에 사용자가 실제 https 출처를 넣어야 한다. PUT 계획 폴더에는 형 자료 바이트가 들어 있으니 Git·첨부에 넣지 않는다.
- **exhibit-token-helper**: 사용자가 직접 실행한다. 32바이트 난수 토큰(base64url 43자)을 **없는 파일**에만 쓰고(줄바꿈 없음), 화면에는 그 SHA-256 hex(Worker 비밀 `PUBLISH_TOKEN_SHA256` 값)와 다음 명령만 찍는다. 토큰 원문은 찍지 않는다.
  파일의 비공개성은 ACL에서 온다(mode 0600은 Windows에서 무시된다): Windows에서는 파일 ACL을 현재 사용자(`DOMAIN\USER`)만으로 제한하고(상속 제거) 다시 읽어 확인하며, 실패하면 파일을 지우고 `acl_restrict_failed`로 끝낸다. 파일은 Projects·`%TEMP%`·Documents·exFAT `D:` 밖 폴더에 두고 업로드 OFF 확인 뒤 지운다. PowerShell 읽기 줄은 `(Get-Content -Raw "...").Trim()`이다.

검사: 합성 4+6 빌드로 전부 통과(all-pass·바이트 변조·접근 문 ON과 CR/LF 코드·http 비loopback 거부·리다이렉트 거부), 토큰 helper 4건(win32 ACL 1건·ACL 실패 경로 1건 포함), 계획 생성기 4건(HEAD·if-match·거부, 실제 publisher dry-run 포함), import 그래프 2건. 2026-11-01 받은 site 24개를 loopback 우리 gateway에 올린 뒤 검사기로 읽은 결과 35/35(접근 문 ON, 영수증은 Git 밖). 실제 Cloudflare 결과가 아니다.
