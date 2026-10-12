# WS-ops1 — 월드시리즈 공개 호스팅 기반

이 문서는 초기 WS-ops1–4c 구현 이력이다. 현재 전체 범위와 다음 작업은 [운영 인계](WS_OPERATIONS_HANDOFF.md)·CHECKLIST 상단을 따른다.

2026-10-12, 우리 main `7128cd3`에서 `codex/ws-host-foundation`으로 진행.
선점 `c932219`. 사용자 직접 요청에 따라 우리 운영 범위를 개발했다.

## 새로 확인한 것

Song 상황판에는 발행기와 공개용 화면의 로컬 구현/교차 검토가 기록돼 있으나,
우리 열린 mail은 조회 시0건이고 해당 구현 소스·예제·스키마는 수신되지 않았다.
문서 브랜치는 이전 `e8dc9ca`에서 `ed3a51c60482dbccdb084f437cc3c5e93f2dfc6a`로 바뀌었다.
COLLAB-001 1-1의 Date/Age, 실제404, 삭제, CORS, 임시 파일 배제 조건을 반영했다.
계약 본문의 `publish` 세부 필드를 추측해 구현하지 않았다.

## 완료 범위

[운영 코드/재현 안내](../ops/public-host/README.md): Cloudflare Worker/R2용 제한된
GET/HEAD·인증 PUT/DELETE/HEAD, 정확한 JSON 바이트·크기·SHA, 조건부 갱신,
삭제 표식과 동일 본문 복원 충돌 방지, no-store·Date/Age·선택적 CORS.

외부 서비스를 건드리지 않고 합성 Node 검사28개와 실제 로컬 workerd/R2 통합 검사1개를 실행했다.
단위 검사만으로 놓쳤던 Worker 진입점 export 제약을 로컬 런타임 검사로 찾아 수정했다.
별도 Codex 검토에서 인코딩된 API 경로의 SPA 우회와 동일 본문 복원 ETag 재활성화를 발견해 수정했다.
작성: root Codex / 검토: 별도 Codex 보조 세션. Claude 교차 검토·사람 검토는 아니다.

## 완료로 표시하지 않은 것

공개 배포/계정 구성, Song 화면 실제 연결, JSON Schema 검사, 실경기 발행,
사용량 분석/피드백/감시, 공개 주소 부하·실기기 확인은 미완료다.
실제 MLB 자료·영상·모델·미트/사람 라벨은 변경하지 않았다. 기존 서버·Sites·DNS도 그대로다.
기존 I-run1 모델 이식·A-y 사람 검토를 파일 발행 서비스의 필수 선행 조건으로 삼지 않는다.
그 항목들의 원래 보류/평가 조건을 완료로 바꾸지는 않았다.

## 다음 단위

- WS-ops2: Song 공개 빌드·schema/예제·고정 버전 수신 → 전송 어댑터/내용 검증/비공개 첫 연결.
- WS-ops3: 외부 회신 없이 익명 이용 기록·짧은 피드백의 저장·검사 기반을 우리 레포에서 구현 가능.
  실제 화면 삽입과 운영 수집은 host-slot 상세/안내·보관 규칙/계정에 맞춰 별도 검증한다.
- WS-ops4: 계정·비용/수집 안내·알림 채널 및 공개 범위 확정 → 배포·감시·부하·실기기 리허설.

우리 board만 선점/종료를 기록한다. 팀원에게 이슈/댓글/메시지를 발신하지 않았으며
팀원 파일·브랜치·프로세스는 수정하지 않았다.

## WS-ops3 후속 — 2026-10-12

전용 private D1 저장·집계·만료 정리와 선택 참여/의견 브라우저 모듈을 구현했다.
[수집 계약·재현·한계](../ops/public-host/TELEMETRY.md). Node46검사, 실제 로컬 Chrome/WebKit
각5검사 통과. 전체 응답 타임아웃 결함은 별도 Codex 검토에서 발견·수정·재현 확인했다.
Windows WebKit은 credentials omit 지정에도 쿠키가 서버까지 전송돼 그 현상을 남겼다.
서버는 Cookie를 저장하지 않는다. 실제 Safari와 배포 로그 정책은 별도 검증이다.
실제 계정·수집·Song 화면·기존 공개 사이트는 활성화/변경하지 않았다.
다음 독립 단위 WS-ops4a는 고정 배포 목록·파일 패키지 검사다.

CI 브라우저 시간 검사의 실행 중 실제16~110ms 혼입은 가상 시계 pauseAt 고정으로 수정했다.
허용 오차를 넓히지 않고 30초 누적값 검사를 유지한다.

## WS-ops4a 후속 — 고정 배포 후보

기준 main c8a6865, 선점09b28ca. [패키지 형식·명령](../ops/public-host/RELEASE.md).
우리 Git blob10개와 별도 합성 화면1파일을 고정 목록·ZIP·영수증으로 묶었다.
CLI로 두 번 생성한 SHA-256은 7f3d73af82f35e0d0c98bd50f6edf4e78696ef7f876f5e53e5cdfe5b4a369e54,
manifest SHA는 070eb354a7c2dc577dc0a5348b5cc30f13d52fb689e398b17da8e87740639d21다.
공급자 화면/계약 커밋은 예제용 가상값이며 실전 배포가 아니다.

관련58·체크리스트7검사, ruff 통과. 별도 Codex 검토가 ZIP 여분 데이터·잘못된 mode 타입·
provenance 입력 경계를 발견했고 모두 수정한 뒤 독립적으로58검사를 통과했다.
Claude/사람 교차 검토는 아니다. WS-ops4b 감시/오류·복구 기반을 다음 독립 단위로 둔다.

## WS-ops4b 후속 — 읽기 감시

기준 main b00ec71, 선점55598a5. [운영자 명령·판정](../ops/public-host/MONITORING.md).
루트 HTML 골격과 health JSON/Date/Age를 확인하고, 지정 발행 시각만 freshness로 계산한다.
필드 미설정은 unmeasured/partial이며 업무상 정상 여부와 JS 실행은 미측정이다.
전체 본문 타임아웃·크기 제한·redirect 거부·설정 지문·중복 실행 잠금·손상/시계 역행 보존을 구현했다.

신규15·기존46 포함 Node61검사 통과. 실제 로컬 HTTP CLI로 2회 실패/2회 복구·잠금·
설정 변경/손상 상태 보존을 확인했다. 별도 Codex 검토에서 JSON Pointer 배열 처리 누락을
발견해 수정하고 회귀를 추가했다. 클라이언트/Worker/R2/D1의 기존 검사는 계속 통과했다.
실제 도메인/스키마/상시 실행/메신저 알림은 미완료다. 다음 단위는 WS-ops4c 로컬 합성 리허설이다.

## WS-ops4c 후속 — 로컬 리허설

기준3898083·선점a648376. [리허설 명령·범위](../ops/public-host/REHEARSAL.md)와
[합성 영수증](results/ops/ws_local_rehearsal_20261012.json)을 저장했다.
32KiB·동시6·120/120 정상 조회, 변경 충돌200/412·삭제404·같은 본문 복원과 낡은 ETag 거부,
합성 stale로 장애open·정상2회로recovered를 확인했다. 전체Node66·신규5·독립Codex5 통과.
브라우저Chrome/WebKit 각2도 실제 Worker에 GET하여 확인했다. 토큰은 Node 내부만 쓴다.
별도 검토의 시작/정리 timeout·정리 실패 보고 문제를 수정했고, cleanup complete를 기록했다.
Windows WebKit 종료 WSARecv64 런타임 진단은 재현돼 남겼다. 종료 후에도 Worker GET200은 통과했다.
이 값을 CDN 수용량·실사용 지연·Song 서비스 완료 근거로 쓰지 않는다.
다음 독립 단위 WS-ops1b는 인증 업로드 제한과 제한기 장애 시 차단이다.
