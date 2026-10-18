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