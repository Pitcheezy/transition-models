# 2026-10-12 초기 운영 인계 원문 보존

기준 main f312b87354dfe4985237ebdb7a5f92c2746ab9dd. 아래는 당시 파일 앞부분의 원문이다. 코드 블록 안 상대 링크는 원래 파일 기준이며, 과거 다음 단위를 새 작업 지시로 읽지 않는다. 현재는 [운영 인계](../WS_OPERATIONS_HANDOFF.md)를 따른다.

## AGENTS.md

````markdown

## WS-ops4f 로컬 재시작 검사 완료 — 2026-10-12

[영속 저장소 리허설](ops/public-host/LIFECYCLE.md): 4회 시작·3회 재시작·키 교체·수집 OFF 실제 scheduled 정리를 확인했다. 신규/독립 각3·Node93통과.
정상 종료 후 로컬 검사이며 실계정/강제종료/백업복원은 미검증이다. Windows WSARecv64 진단을 유지한다. 실제 연결·배포는 WS-ops2/4 전달·결정 조건을 따른다.


## WS-ops1c 단일 파일 전송 후보 완료 — 2026-10-12

[전송 도구](ops/public-host/PUBLISHER.md)는 기본 dry-run·고정 조건 재시도·모호한 저장 결과 분리를 제공한다. 신규17·독립17통과.
Windows WSARecv64 종료 진단은 남아 있다. 실제 발행기/계약/계정 연결은 별도다. 다음 독립 단위 WS-ops4f는 로컬 영속 재시작 리허설이다.


## WS-ops4e 운영 준비 완료 — 2026-10-12

[장애·복구 절차](ops/public-host/RUNBOOK.md)와 [비용 가정](ops/public-host/COST_PLAN.md)을 작성했다. 산정25·별도 Codex25통과.
계정·예산·실측/실복구 승인은 별도다. 다음 독립 단위 WS-ops1c는 우리 제안 계약의 제한된 전송 클라이언트다.


## WS-ops4d 후보 설정 검사 완료 — 2026-10-12

[오프라인 설정 검사](ops/public-host/CONFIG_CHECK.md)는 새 공개 파일 혼입·경로·수집 안내·정리 cron을 확인한다. 신규66·기존58·별도 Codex64/경계6검사 통과.
실제 계정/배포 검증은 별도이며 deployable=false다. 다음 독립 단위는 WS-ops4e 운영 절차·비용 산정이다.


## WS-ops3c 수집 설정·안내 일치 완료 — 2026-10-12

[수집 안내](ops/public-host/TELEMETRY.md)의 telemetryEnabled/feedbackEnabled/retainDays를 명시한다. old enabled는 켜지지 않는다.
Node73·Chrome/WebKit 각7·별도 Codex client10통과. 다음 WS-ops4d 오프라인 후보 설정 검사. 실제 계정/배포와 팀원 자료 대기는 유지한다.

## WS-ops1b 인증 업로드 제한 완료 — 2026-10-12

[제한·재시도·경계](ops/public-host/UPLOAD_LIMITS.md): Node71·별도 Codex 관련39통과. 실제 계정/주기 확정은 별도다.
다음 독립 작업은 WS-ops3c 수집 UI 토글·보관 안내 설정 연결이다. 팀원 파일·공개 배포 변경 금지를 유지한다.

## WS-ops4c 로컬 호스팅 리허설 완료 — 2026-10-12

[조회·철회/복구·감시·브라우저 리허설](ops/public-host/REHEARSAL.md)을 수행했다. 합성120/120·Node66·Chrome/WebKit 각2통과.
Windows WebKit 종료의 WSARecv64 진단은 남아 있으나 종료 후 Worker GET200도 확인했다.
공개 CDN/실제 Song/Safari 검사가 아니다. 다음은 WS-ops1b 인증 업로드 제한이며 실제 배포 조건은 유지한다.


## WS-ops4b 읽기 감시 완료 — 2026-10-12

[단발 감시·장애/복구](ops/public-host/MONITORING.md)를 합성/실제 로컬 HTTP로 검증했다. 신규15·전체Node61검사 통과.
시각 필드 미설정은 partial/unmeasured이고 업무 health·JS 실행을 정상 판정하지 않는다.
외부 알림·상시 실행·실제 도메인 연결은 미완료다. 다음 독립 단위 WS-ops4c는 로컬 Worker 합성 리허설이다.


## WS-ops4a 고정 배포 패키지 완료 — 2026-10-12

[패키지 생성/검사](ops/public-host/RELEASE.md)는 관련58검사·체크리스트7검사를 통과했다.
고정 우리 host와 합성 화면11파일을 두 번 생성해 ZIP SHA가 일치했다. 공급자 출처/공개 권리/배포는 검증하지 않으며 deployable=false다.
다음 독립 단위는 WS-ops4b 감시·오류/복구 판정 기반이다. 실제 Song 전달물·계정·기기는 기존 조건을 유지한다.


## WS-ops3 구현 완료 — 2026-10-12

D1 저장·집계·정리와 브라우저 동의·시간 측정·의견 UI를 구현했다. Node46, Chrome/WebKit 각5 통과.
Windows WebKit 쿠키 전송 한계·실제 Safari 미검증을 유지한다. 다음 독립 단위는 WS-ops4a 배포 목록/패키지 검증이다.
[수집 계약과 한계](ops/public-host/TELEMETRY.md)를 읽는다. 실제 계정·수집·Song 화면은 변경하지 않았다.


## 월드시리즈 우리 운영 기반 — 2026-10-12

WS-ops1의 Cloudflare Worker/R2 전송 기반과 합성·로컬 런타임 검사를 구현했다.
[현재 범위·재현·다음 단위](docs/WS_PUBLIC_HOST_20261012.md) 및 CHECKLIST 상단을 먼저 읽는다.
공개 배포·Song 화면/schema 연결은 미완료이며 두 활성화 스위치는 기본 비활성이다.
WS-ops3 구현 완료 상태는 위 최신 절을 따른다. WS-ops2는 실제 전달물 수신 후 진행한다.
팀원 저장소 수정 금지, 기존 서버·영상·사람 자료 보존, A-y/F-4i 보류를 유지한다.


````

## CLAUDE.md

````markdown

## WS-ops4f 로컬 재시작 검사 완료 — 2026-10-12

[영속 저장소 리허설](ops/public-host/LIFECYCLE.md): 4회 시작·3회 재시작·키 교체·수집 OFF 실제 scheduled 정리를 확인했다. 신규/독립 각3·Node93통과.
정상 종료 후 로컬 검사이며 실계정/강제종료/백업복원은 미검증이다. Windows WSARecv64 진단을 유지한다. 실제 연결·배포는 WS-ops2/4 전달·결정 조건을 따른다.


## WS-ops1c 단일 파일 전송 후보 완료 — 2026-10-12

[전송 도구](ops/public-host/PUBLISHER.md)는 기본 dry-run·고정 조건 재시도·모호한 저장 결과 분리를 제공한다. 신규17·독립17통과.
Windows WSARecv64 종료 진단은 남아 있다. 실제 발행기/계약/계정 연결은 별도다. 다음 독립 단위 WS-ops4f는 로컬 영속 재시작 리허설이다.


## WS-ops4e 운영 준비 완료 — 2026-10-12

[장애·복구 절차](ops/public-host/RUNBOOK.md)와 [비용 가정](ops/public-host/COST_PLAN.md)을 작성했다. 산정25·별도 Codex25통과.
계정·예산·실측/실복구 승인은 별도다. 다음 독립 단위 WS-ops1c는 우리 제안 계약의 제한된 전송 클라이언트다.


## WS-ops4d 후보 설정 검사 완료 — 2026-10-12

[오프라인 설정 검사](ops/public-host/CONFIG_CHECK.md)는 새 공개 파일 혼입·경로·수집 안내·정리 cron을 확인한다. 신규66·기존58·별도 Codex64/경계6검사 통과.
실제 계정/배포 검증은 별도이며 deployable=false다. 다음 독립 단위는 WS-ops4e 운영 절차·비용 산정이다.


## WS-ops3c 수집 설정·안내 일치 완료 — 2026-10-12

[수집 안내](ops/public-host/TELEMETRY.md)의 telemetryEnabled/feedbackEnabled/retainDays를 명시한다. old enabled는 켜지지 않는다.
Node73·Chrome/WebKit 각7·별도 Codex client10통과. 다음 WS-ops4d 오프라인 후보 설정 검사. 실제 계정/배포와 팀원 자료 대기는 유지한다.

## WS-ops1b 인증 업로드 제한 완료 — 2026-10-12

[제한·재시도·경계](ops/public-host/UPLOAD_LIMITS.md): Node71·별도 Codex 관련39통과. 실제 계정/주기 확정은 별도다.
다음 독립 작업은 WS-ops3c 수집 UI 토글·보관 안내 설정 연결이다. 팀원 파일·공개 배포 변경 금지를 유지한다.

## WS-ops4c 로컬 호스팅 리허설 완료 — 2026-10-12

[조회·철회/복구·감시·브라우저 리허설](ops/public-host/REHEARSAL.md)을 수행했다. 합성120/120·Node66·Chrome/WebKit 각2통과.
Windows WebKit 종료의 WSARecv64 진단은 남아 있으나 종료 후 Worker GET200도 확인했다.
공개 CDN/실제 Song/Safari 검사가 아니다. 다음은 WS-ops1b 인증 업로드 제한이며 실제 배포 조건은 유지한다.


## WS-ops4b 읽기 감시 완료 — 2026-10-12

[단발 감시·장애/복구](ops/public-host/MONITORING.md)를 합성/실제 로컬 HTTP로 검증했다. 신규15·전체Node61검사 통과.
시각 필드 미설정은 partial/unmeasured이고 업무 health·JS 실행을 정상 판정하지 않는다.
외부 알림·상시 실행·실제 도메인 연결은 미완료다. 다음 독립 단위 WS-ops4c는 로컬 Worker 합성 리허설이다.


## WS-ops4a 고정 배포 패키지 완료 — 2026-10-12

[패키지 생성/검사](ops/public-host/RELEASE.md)는 관련58검사·체크리스트7검사를 통과했다.
고정 우리 host와 합성 화면11파일을 두 번 생성해 ZIP SHA가 일치했다. 공급자 출처/공개 권리/배포는 검증하지 않으며 deployable=false다.
다음 독립 단위는 WS-ops4b 감시·오류/복구 판정 기반이다. 실제 Song 전달물·계정·기기는 기존 조건을 유지한다.


## WS-ops3 구현 완료 — 2026-10-12

D1 저장·집계·정리와 브라우저 동의·시간 측정·의견 UI를 구현했다. Node46, Chrome/WebKit 각5 통과.
Windows WebKit 쿠키 전송 한계·실제 Safari 미검증을 유지한다. 다음 독립 단위는 WS-ops4a 배포 목록/패키지 검증이다.
[수집 계약과 한계](ops/public-host/TELEMETRY.md)를 읽는다. 실제 계정·수집·Song 화면은 변경하지 않았다.


## 월드시리즈 우리 운영 기반 — 2026-10-12

WS-ops1의 Cloudflare Worker/R2 전송 기반과 합성·로컬 런타임 검사를 구현했다.
[현재 범위·재현·다음 단위](docs/WS_PUBLIC_HOST_20261012.md) 및 CHECKLIST 상단을 먼저 읽는다.
공개 배포·Song 화면/schema 연결은 미완료이며 두 활성화 스위치는 기본 비활성이다.
WS-ops3 구현 완료 상태는 위 최신 절을 따른다. WS-ops2는 실제 전달물 수신 후 진행한다.
팀원 저장소 수정 금지, 기존 서버·영상·사람 자료 보존, A-y/F-4i 보류를 유지한다.


````

## docs/CODEX_RESUME_PROMPT.md

````markdown

## WS-ops4f 로컬 재시작 검사 완료 — 2026-10-12

[영속 저장소 리허설](../ops/public-host/LIFECYCLE.md): 4회 시작·3회 재시작·키 교체·수집 OFF 실제 scheduled 정리를 확인했다. 신규/독립 각3·Node93통과.
정상 종료 후 로컬 검사이며 실계정/강제종료/백업복원은 미검증이다. Windows WSARecv64 진단을 유지한다. 실제 연결·배포는 WS-ops2/4 전달·결정 조건을 따른다.


## WS-ops1c 단일 파일 전송 후보 완료 — 2026-10-12

[전송 도구](../ops/public-host/PUBLISHER.md)는 기본 dry-run·고정 조건 재시도·모호한 저장 결과 분리를 제공한다. 신규17·독립17통과.
Windows WSARecv64 종료 진단은 남아 있다. 실제 발행기/계약/계정 연결은 별도다. 다음 독립 단위 WS-ops4f는 로컬 영속 재시작 리허설이다.


## WS-ops4e 운영 준비 완료 — 2026-10-12

[장애·복구 절차](../ops/public-host/RUNBOOK.md)와 [비용 가정](../ops/public-host/COST_PLAN.md)을 작성했다. 산정25·별도 Codex25통과.
계정·예산·실측/실복구 승인은 별도다. 다음 독립 단위 WS-ops1c는 우리 제안 계약의 제한된 전송 클라이언트다.


## WS-ops4d 후보 설정 검사 완료 — 2026-10-12

[오프라인 설정 검사](../ops/public-host/CONFIG_CHECK.md)는 새 공개 파일 혼입·경로·수집 안내·정리 cron을 확인한다. 신규66·기존58·별도 Codex64/경계6검사 통과.
실제 계정/배포 검증은 별도이며 deployable=false다. 다음 독립 단위는 WS-ops4e 운영 절차·비용 산정이다.


## WS-ops3c 수집 설정·안내 일치 완료 — 2026-10-12

[수집 안내](../ops/public-host/TELEMETRY.md)의 telemetryEnabled/feedbackEnabled/retainDays를 명시한다. old enabled는 켜지지 않는다.
Node73·Chrome/WebKit 각7·별도 Codex client10통과. 다음 WS-ops4d 오프라인 후보 설정 검사. 실제 계정/배포와 팀원 자료 대기는 유지한다.

## WS-ops1b 인증 업로드 제한 완료 — 2026-10-12

[제한·재시도·경계](../ops/public-host/UPLOAD_LIMITS.md): Node71·별도 Codex 관련39통과. 실제 계정/주기 확정은 별도다.
다음 독립 작업은 WS-ops3c 수집 UI 토글·보관 안내 설정 연결이다. 팀원 파일·공개 배포 변경 금지를 유지한다.

## WS-ops4c 로컬 호스팅 리허설 완료 — 2026-10-12

[조회·철회/복구·감시·브라우저 리허설](../ops/public-host/REHEARSAL.md)을 수행했다. 합성120/120·Node66·Chrome/WebKit 각2통과.
브라우저 실행 폴더에서 Worker 모듈 경로 실패를 재현해 modulesRoot를 명시했다. 원격 Chromium/WebKit 각29·Node66·전체 CPU Linux/macOS CI 통과(PR #9).
Windows WebKit 종료의 WSARecv64 진단은 남아 있으나 종료 후 Worker GET200도 확인했다.
공개 CDN/실제 Song/Safari 검사가 아니다. 다음은 WS-ops1b 인증 업로드 제한이며 실제 배포 조건은 유지한다.


## WS-ops4b 읽기 감시 완료 — 2026-10-12

[단발 감시·장애/복구](../ops/public-host/MONITORING.md)를 합성/실제 로컬 HTTP로 검증했다. 신규15·전체Node61검사 통과.
시각 필드 미설정은 partial/unmeasured이고 업무 health·JS 실행을 정상 판정하지 않는다.
외부 알림·상시 실행·실제 도메인 연결은 미완료다. 다음 독립 단위 WS-ops4c는 로컬 Worker 합성 리허설이다.


## WS-ops4a 고정 배포 패키지 완료 — 2026-10-12

[패키지 생성/검사](../ops/public-host/RELEASE.md)는 관련58검사·체크리스트7검사를 통과했다.
고정 우리 host와 합성 화면11파일을 두 번 생성해 ZIP SHA가 일치했다. 공급자 출처/공개 권리/배포는 검증하지 않으며 deployable=false다.
다음 독립 단위는 WS-ops4b 감시·오류/복구 판정 기반이다. 실제 Song 전달물·계정·기기는 기존 조건을 유지한다.


## WS-ops3 구현 완료 — 2026-10-12

D1 저장·집계·정리와 브라우저 동의·시간 측정·의견 UI를 구현했다. Node46, Chrome/WebKit 각5 통과.
Windows WebKit 쿠키 전송 한계·실제 Safari 미검증을 유지한다. 다음 독립 단위는 WS-ops4a 배포 목록/패키지 검증이다.
[수집 계약과 한계](../ops/public-host/TELEMETRY.md)를 읽는다. 실제 계정·수집·Song 화면은 변경하지 않았다.


## 월드시리즈 우리 운영 기반 — 2026-10-12

WS-ops1의 Cloudflare Worker/R2 전송 기반과 합성·로컬 런타임 검사를 구현했다.
[현재 범위·재현·다음 단위](WS_PUBLIC_HOST_20261012.md) 및 CHECKLIST 상단을 먼저 읽는다.
공개 배포·Song 화면/schema 연결은 미완료이며 두 활성화 스위치는 기본 비활성이다.
WS-ops3 구현 완료 상태는 위 최신 절을 따른다. WS-ops2는 실제 전달물 수신 후 진행한다.
팀원 저장소 수정 금지, 기존 서버·영상·사람 자료 보존, A-y/F-4i 보류를 유지한다.


````

## docs/handoff/README.md

````markdown

## WS-ops3d 수집 제한기 차단 보강 — 2026-10-12

[수집 계약](../../ops/public-host/TELEMETRY.md)의 제한기는 boolean true만 허용한다. false는429, 나머지/예외는503이며 본문/DB 접근 전에 차단한다. 신규2·Node95통과. 실제 수집 활성화 없음. 다음 H-ops1은 인계·CI 중복 정리다.

## WS-ops4f 로컬 재시작 검사 완료 — 2026-10-12

[영속 저장소 리허설](../../ops/public-host/LIFECYCLE.md): 4회 시작·3회 재시작·키 교체·수집 OFF 실제 scheduled 정리를 확인했다. 신규/독립 각3·Node93통과.
정상 종료 후 로컬 검사이며 실계정/강제종료/백업복원은 미검증이다. Windows WSARecv64 진단을 유지한다. 실제 연결·배포는 WS-ops2/4 전달·결정 조건을 따른다.


## WS-ops1c 단일 파일 전송 후보 완료 — 2026-10-12

[전송 도구](../../ops/public-host/PUBLISHER.md)는 기본 dry-run·고정 조건 재시도·모호한 저장 결과 분리를 제공한다. 신규17·독립17통과.
Windows WSARecv64 종료 진단은 남아 있다. 실제 발행기/계약/계정 연결은 별도다. 다음 독립 단위 WS-ops4f는 로컬 영속 재시작 리허설이다.


## WS-ops4e 운영 준비 완료 — 2026-10-12

[장애·복구 절차](../../ops/public-host/RUNBOOK.md)와 [비용 가정](../../ops/public-host/COST_PLAN.md)을 작성했다. 산정25·별도 Codex25통과.
계정·예산·실측/실복구 승인은 별도다. 다음 독립 단위 WS-ops1c는 우리 제안 계약의 제한된 전송 클라이언트다.


## WS-ops4d 후보 설정 검사 완료 — 2026-10-12

[오프라인 설정 검사](../../ops/public-host/CONFIG_CHECK.md)는 새 공개 파일 혼입·경로·수집 안내·정리 cron을 확인한다. 신규66·기존58·별도 Codex64/경계6검사 통과.
실제 계정/배포 검증은 별도이며 deployable=false다. 다음 독립 단위는 WS-ops4e 운영 절차·비용 산정이다.


## WS-ops3c — 2026-10-12

수집 UI에 독립 토글/보관일이 필수다. Node73·브라우저각7·별도 client10통과. 다음 WS-ops4d 설정검사. [계약](../../ops/public-host/TELEMETRY.md). 기존 ZIP 변경 없음.

## WS-ops1b — 2026-10-12

[업로드 제한](../../ops/public-host/UPLOAD_LIMITS.md) 구현·Node71/별도 관련39검사 통과. 다음 WS-ops3c 수집 UI 설정 일치. 기존 영상/소스 ZIP은 그대로다.

## WS 로컬 리허설 — 2026-10-12

[Worker 합성 리허설](../../ops/public-host/REHEARSAL.md)은 신규 임시 저장소만 사용한다.
실제 공개 서버나 Song 모델을 실행하지 않는다. 기존 v5/v9 검토 자료와 별개다.


## WS 감시 운영자 도구 — 2026-10-12

[읽기 감시 CLI](../../ops/public-host/MONITORING.md)는 우리 저장소의 별도 운영자용 도구다.
기존 v5 팩과 배포 후보 ZIP을 변경하지 않는다. 실제 필드/알림/상시 실행은 아직 연결하지 않았다.


## WS 운영 소스와 별도 배포 후보 — 2026-10-12

기존 서비스 검토 v5·영상팩과 WS 배포 후보는 서로 다르다.
[WS 패키지 생성/검사](../../ops/public-host/RELEASE.md)는 우리 호스트 고정 커밋과 별도 공개 화면 빌드를 묶는다.
합성 예제·58회귀 검증 완료이며 실제 Song 빌드/스키마 수신과 배포는 미완료다.


````
