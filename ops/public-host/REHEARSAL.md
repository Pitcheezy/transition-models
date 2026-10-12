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
