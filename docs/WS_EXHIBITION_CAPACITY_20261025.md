# 전시회 30/50명 관람 준비 — WS-capacity1

기준: main `24fea70f12ba53d3503823c90b3b06cec045a277`, 선점 `67f523a`.
[착수 합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6388196522).
사용자가 전시회 30~50명 준비를 지시한 범위의 로컬 시험 도구와 계산이다.
실제 호스팅 설정·요금제·배포·팀원 화면/발행기·공개 계약은 변경하지 않는다.

## 사용자 우선순위 변경 — 2026-10-25

요금제·전시회 요청량 결정은11월 최종발표 준비로 보류한다. 아래 결과/계산은 완료 당시 근거로 보존한다.
지금 가격 비교·추가 부하 작업을 이어가지 않으며 실제부하/요금제/접근 변경은 승인된 것이 아니다.
현재 협업 후속은 [실행 계획](WS_COLLAB_V1_ACTIONS.md)을 따른다. 공동시험의 유한 요청 원장/양측GO는 유지한다.

## 기존 서버 로그 재조회와 전달 상태

- 10/25 03:00~03:05 KST 구간을 Cloudflare Observability에서 다시 조회하고 03:54:20 KST에 JSON을 내려받았다.
- 원래 13개 요청의 비공개 ray ID로 연결한 뒤 method/path/status/version 및 클라이언트 시각±2초를 대조했다. **12/13 일치, 안내 OFF PUT 한 건은 여전히 미확인**이다. 누락 원인은 모른다.
- 내보낸 원본은 60,360 bytes, SHA-256 `c43bd46748c1e03b17a392e45421bbe2dc8bcebf59d4846163f78c023497b0b4`. 앞선 내보내기와 바이트 해시까지 동일하다. 원본은 비공개 로컬 다운로드에 보존한다.
- 이번에는 서비스 요청·설정 변경·재배포가 각각 0건이다. 안내 OFF 상태 확인·감사 기록은 요청별 invocation 로그의 대체 증거가 아니다.
- [공개 가능한 재조회 영수증](results/ops/ws_notice_log_recheck_20261025.json)의 SHA-256은 `5e87c7ffcf752f37adc0e9f5e3365d1108b8b9db7385d21e84e0710c32ec10c7`이다.
- 사용자가 메시지와 ZIP을 직접 보냈다고 보고했다. 상대 수신·검증 확인은 아직 없다. ZIP 21,561 bytes, SHA-256 `e8e4d70f9b844ce31e5a2f3af7ca600030032099624141340e5c33254581867f`는 변경하지 않았다.
- 기존 [PR64](https://github.com/Pitcheezy/transition-models/pull/64)의 [고정 운영 기록](https://github.com/Pitcheezy/transition-models/blob/abddb240a698e91923d14ef413e36081a4af5315/docs/WS_NOTICE_TRIAL_20261025.md)은 별도 브랜치에 보존한다. PR64는 main 미병합이며 WS-notice3는 로그12/13으로 미완료다. 새 최종본 수신·공동시험·공개 GO는 대기다.

## 시험 전 고정한 조건

- 기존 폐쇄루프 시험의 동시요청 상한 16은 유지하고 별도 `viewer-polling` 모드를 사용한다.
- 30 또는 50 가상 관람자가 각각 별도의 임시 로그인 세션을 가진다. 접근 문 ON, 이용 기록·피드백 OFF다. 운영 자격이나 기존 서버를 읽지 않는다.
- 임시 loopback Worker/R2에 각 32,768 bytes의 합성 JSON 두 개를 준비한다. 실제 경기/health 스키마 검증이 아니다.
- 매 관람자마다 공통 단조시계의 0·5·10·15·20·25초에 두 GET을 순서대로 수행한다. 예정 GET은 360 또는 600개다. 첫 GET부터 본문·SHA 확인까지 끝낸 뒤 두 번째를 시작한다.
- 슬롯 시작 허용 지연은 500ms다. 늦은 슬롯·이전 poll의 슬롯 경계 초과·요청 실패 시 중단하고 밀린 요청을 몰아 보내지 않는다. 90초 전체 제한, 요청별 5초 제한, 정리 5초 제한을 둔다.
- 합격은 예정 요청 전부 성공, HTTP200/바이트/SHA/Date/Age0/no-store 일치, 실패·누락0, 실제 동시요청≤관람자 수, 정리 완료다. p50/p95/max는 성공 요청의 시작~본문 검증 종료 시간을 기록한다. 공개 서비스 응답 SLA를 이 시험에서 정하지 않는다.
- 준비 PUT·로그인·워밍업과 폴링 GET은 따로 센다. 마지막 예정 시작은25초이며, `[0,30초)`의6슬롯을 30초 내내 지속 관측한 것으로 부르지 않는다. 실제 소요시간을 기록한다.
- 외부 origin/자격 입력, 재시도, 리다이렉트, 무한 실행을 제공하지 않는다. 기존 결과 파일은 덮어쓰지 않는다.

## 실제 결과

고정 코드 `f7e65bb98990feae7d423bbaf9f32855e61db363`에서 각 프로필을1회 실행했다. Windows x64·Node24.1.0·Miniflare4.20260730.0, 실행 전후 실제 소스 SHA가 동일하다. [결과 목록](results/ops/ws_exhibition_capacity_20261025.json) SHA-256 `68475e7871b5bcd46e11a1910eb56d64097bd6ff897ae6ddd519aab78440cab4`.

|항목|30 가상 관람|50 가상 관람|
|---|---:|---:|
|부하 GET 성공/예정|360/360|600/600|
|실패·취소·미시작·누락 슬롯|모두0|모두0|
|준비 요청(401확인+로그인+PUT+워밍업)|35|55|
|전체 runtime 입구 요청|395|655|
|실제 최대 동시 GET|30|50|
|응답 p50 / p95 / 최대|105.30 / 121.42 / 132.78ms|162.37 / 196.77 / 205.90ms|
|최대 슬롯 시작 지연(기준≤500ms)|39.49ms|50.64ms|
|폴링 시작~끝|25,219.37ms|25,350.75ms|
|준비·정리 포함 총 소요|26,297ms|26,664ms|
|정리|complete|complete|

[30명 원본 영수증](results/ops/ws_viewers30_local_20261025.json) 67,191bytes/SHA `2e2adb6c67427937d41b11c30f1248bbc2243a075e3e5f9651f4b052ee35b308`, [50명 원본 영수증](results/ops/ws_viewers50_local_20261025.json) 108,715bytes/SHA `5aea4141583e5f07c7fc5246f87095a79cd9c6e7790e533d604d5cc42f640c8f`.

고유 nonce 세션30/50개, HTTP200·본문 길이/SHA·헤더 검증, 실제 in-flight 종료0을 확인했다. 자동 재시도/리다이렉트0, stderr 비어 있음. 토큰·쿠키·접속 주소는 영수증에 없다. 로그인은 순차 준비이며 동시에 로그인하는 부하는 미측정이다. 실제 Cloudflare 요청은0건이다. 이 결과는 한 노트북의 짧은 합성 반복이며 실브라우저50명, 큰 실제 응답, 장시간 운영, 여러 회선, Cloudflare CPU/청구 한도를 검증하지 않는다.

## 무료 요금제 일일 요청 예산

공식 문서 2026-10-25 조회: Workers Free는 **계정 전체 하루100,000 요청**, **UTC00:00(KST09:00) 초기화**, 초과 시 Error1027이다. 요청당 CPU10ms 제한도 별개다. [Cloudflare limits](https://developers.cloudflare.com/workers/platform/limits/).

동일 관람자가3시간 내내 접속하고, 시작 즉시 한 번 읽은 뒤 `[0,10800초)` 동안 반복한다고 가정한다. 계산식은 `관람자 × ceil(관람초/갱신초) × 파일 수`다.

| 가정 |30명|50명|
|---|---:|---:|
|5초마다2파일|129,600|216,000|
|15초마다2파일|43,200|72,000|
|1초마다1파일|324,000|540,000|

이는 폴링 GET만 계산한다. 로그인·홈/스크립트·다른 화면·발행·감시·재시도·계정의 다른 Worker 사용량은 더해야 한다. 실제 다른 사용량은 미확인이다. 304 또는 Worker를 거친 캐시 응답도 요청 수에서 빼지 않는다.5초/2파일 가정은 폴링만으로 Free 한도를 넘는다.15초/2파일은 그 부분만 한도 안이며 전시 전체의 안전한 운영을 보장하지 않는다.

[예산 계산 결과](results/ops/ws_viewer_budget_20261025.json) SHA-256 `43809b993408ff7a00408f29a464045a51b11a3172ff7802a5a233044b374be7`. `src/operations/viewer_budget.py`는 정수 계산으로 즉시 첫 poll을 포함하고 계정 사용량 `null`을0으로 바꾸지 않는다. 예시에서는 기타 트래픽 미상이라15초 안도 `headroom_unknown`이다. 시작~종료가 UTC 자정을 넘더라도 이 단순 계산기는 초기화 크레딧을 적용하지 않고 하루에 합산한다.

갱신 간격은 아직 Song의 최종 화면 동작으로 확정하지 않았다. 이 계산을 근거로 상대 화면을 수정하지 않는다. 조건부요청/압축은 바이트 절약에 도움이 될 수 있으나 요청 수 절감과 구분한다. 이미 구현된 Paid 월간 계산기 `src/operations/host_cost.py`와 이번 Free 일일 한도 계산은 별개다.

유료 Workers는 월 기본$5와 포함량 이후 사용량 과금 구조다. [공식 가격](https://developers.cloudflare.com/workers/platform/pricing/). 기존 월$10 준비 예산은 자동 청구 상한이나 유료 전환 승인이 아니다. 현재 Free를 유지한다.

## 출시 전에 남는 확인

1. 고정 최종 UI/파일을 받으면 실제 폴링 경로·간격·파일 크기·열린 화면의 안내 전환을 측정한다. 이번32KiB 합성2파일은 실제 응답 크기와 동작을 대표한다고 주장하지 않는다.
2. 계정 일일 잔량·예정 운영시간·기타 트래픽·CPU를 확인해 갱신 간격 또는 유료 전환안을 사람에게 제시한다. 로컬 벽시계 지연에서 Cloudflare CPU를 추정하지 않는다.
3. 실제 시험 자격·대상·시간·요청 상한을 고정하고 승인된 제한적 클라우드30/50명 시험을 수행한다. 현재 도구는 loopback만 허용한다.
4. 실제 브라우저/기기·여러 회선·최종 UI를 포함한 리허설과 운영 감시/회수 기록을 확보한다. 기능13건과 로그12/13이라는 남은 증거 조건을 이 부하 시험으로 닫지 않는다.

## 재현·검토

저장소 루트, Node24 및 잠긴 `ops/public-host` 의존성이 있는 환경에서 실행한다. 출력 부모 폴더를 먼저 만들고 새 파일명을 사용한다.

~~~text
node ops/public-host/rehearse-local.mjs --mode viewer-polling --viewers 30 --output .cache/viewers30-new.json
node ops/public-host/rehearse-local.mjs --mode viewer-polling --viewers 50 --output .cache/viewers50-new.json
uv run --frozen python scripts/218_estimate_viewer_budget.py --examples
uv run --frozen python scripts/218_estimate_viewer_budget.py --viewers 50 --duration-seconds 10800 --poll-seconds 15 --objects-per-poll 2
node --test ops/public-host/tests/viewer-polling.test.mjs ops/public-host/tests/rehearsal.test.mjs
uv run --frozen python -m pytest tests/test_viewer_budget.py tests/test_public_host_cost.py tests/test_checklist_model.py -q
~~~

- 작성: Codex GPT-6 계열(정확한 세션 모델 ID는 미확인). 검토: `gpt-5.6-sol`, 고정 `f7e65bb98990feae7d423bbaf9f32855e61db363`, PASS/P1·P2 지적 없음. 같은 모델의 세션 분리가 아니다.
- 새 폴링9+기존6=Node15검사 통과. 별도 모델도15검사를 다시 통과했다. 가짜 시계 검사는 정상 개수·시간 밀림·첫/둘째 GET 실패·슬롯 초과·외부 취소·출력 선행거부를 검증하며 위 실제 측정과 구분한다.
- 예산/기존 Paid 계산 Python132검사, 체크리스트8검사, Ruff 통과. 별도 모델의 예산107검사도 통과했다. 수치는 서로 겹치므로 합산하지 않는다.
- 전체 Node 회귀377/377, `npm run check` 통과(22.60초 테스트). 문서 상대 링크·파일 해시·영수증 계수·비공개값 미포함·diff 검사를 통과했다.
- 운영 gateway/인증/발행/안내 코드는 바꾸지 않았다. 로컬 도구에는 모드 분기·순수 스케줄러·출력 선행검사와 누락됐던 access/notice 소스 해시를 추가했다. 기존 동시16 제한은 유지한다.

최종 문서 대조에서도 영수증5개와 소스10파일의 해시·바이트·수치 일치를 확인했다. 최종 원격 CI/병합 상태는 [PR65](https://github.com/Pitcheezy/transition-models/pull/65)와 우리 board 종료 댓글을 따른다.
