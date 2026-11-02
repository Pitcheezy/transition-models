# Claude 전시 작업 인계 — 2026-11-01

## 2026-11-02 Claude 인계 프롬프트

아래를 새 Claude 채팅의 재개 지시로 사용한다. 현재 상태의 정본은 CHECKLIST 상단이며, 이 절 뒤에 있는 단계별 과거 인계는 당시 이력이다.

Claude, Pitcheezy 11/24 전시 준비를 이 상태에서 이어받아줘.

### 작업 위치와 먼저 읽을 것

- 지정 폴더: `C:/Users/zpfh1/Projects/transition-models-exhibit-1101`
- 브랜치: `claude/exhibit-host1-1101`. 직전 완료 기준 `9a3f4b6`; 이 인계와 부분 사전 확인은 그 뒤의 로컬 커밋에 있다. 실제 `git log -1`과 변경 상태를 먼저 확인한다. 사용자 지시로 아직 push하지 않는다.
- PLAN.md → CHECKLIST.md 상단 → docs/COLLABORATION_PROTOCOL.md → 이 최신 절 → docs/EXHIBIT_SCOPED_HOST_PREPARATION_20261101.md의 단계5 → docs/results/exhibition_20261101/stage5-preflight-20261102.json 순서로 읽는다.
- 다른 worktree·기존 미커밋 변경·원본·실행 프로세스를 보존한다. `outputs/exhibit_scope_preparation_20261101/` 미추적 폴더는 기존 자료다. 담당 확인 없이 같은 파일을 동시에 수정하지 않는다.

### 이미 완료한 것 — 반복하지 말 것

- 새 시험 서버에 Song 웹 `c47fe6cb78479362e7250141da946814cc33bd31`과 자료6개를 별도로 올렸다. 자료 생성 소스는 전달자 선언 `cb1cfa8f759fd77adc75595316a389208c752dba`이며 그 ref 자체 확인과 웹 소스 확인은 구분한다.
- 받은 ZIP은 182517bytes, SHA-256 `3c3b8006b892872bfff3423e2bd6ba49ea3de17ee92fbecef07e0b076bc8da51`. 정적4·JSON6, 849843 한 경기·2026-09-30 하루, 262구·추천246·미지원16이다. 형 원본 바이트는 변경하지 않는다.
- 단계4 자동120/212요청·24/24판정, 10분 관찰, 안내ON→숨김→브라우저 합성 오류2건에서도 과거 추천 미노출→OFF복원→로그아웃을 완료했다. 업로드·수집·피드백OFF, 접근 제한ON이다.
- 사용자는 iPhone Safari와 Chrome 모두 날짜 하루·추천/존·투구 이동을 확인했다. 이는 시험 주소의 사용자 관측이다. 기기/OS/브라우저 상세 버전과 실제 app 전환 뒤 검사는 별도다.
- 다운로드 export2개는 원본 보존 복사·SHA 확인 후 단계3 13/13, 단계4 120/120이 Ray·방식·경로·status·시각·버전과 일치했다. 누락/중복/불일치0, 합성2건 제외다. 근거: docs/results/exhibition_20261101/stage34-server-log-correlation.json. 이 검사나 업로드·안내·10분 관찰을 반복하지 않는다.

### 이번 작업의 실제 중단점

사용자는 “이번 작업을 진행하고 끝난 뒤 Claude 인계 프롬프트를 만들라”고 지시했다. Codex는 기존 app Route 하나만 새 대상으로 옮기고 실패하면 옛 대상으로 복구하는 범위와 재로그인 필요를 설명했다. 이 범위의 전환을 이어가되, 예상 밖 대상·중복 Route·새 변경 필요는 따로 설명한다.

컴퓨터 접근 승인이 시간 초과되어 Cloudflare 대시보드의 현재 Route를 읽거나 편집하지 못했다. 이후 사용자가 노트북에서 다시 열어 달라고 하여 연결된 Chrome 브라우저에 “☁️ 전시 전환” 탭을 열었고, Cloudflare 로그인 화면을 실제 확인했다. 그 탭이 사용자 노트북 화면에 보이는지는 확인하지 못했으므로 사용자에게 로그인 완료 또는 탭 안 보임 답변을 요청했다. 탭은 로그인 인계용으로 유지했다. 원래 컴퓨터 접근 시간초과를 자동 승인 검토 거절로 쓰지 않는다. 다음은 이 로그인/탭 연결 확인 뒤 관리 대시보드 읽기부터다.

**단계5 Route/DNS/배포/비밀 변경0·서비스 요청0·실행 입력 생성0이다.** 공개 앱 전환은 아직 수행하지 않았다. app의 마지막 확인 배포는 fba6b2ff지만 현재 Route를 이번에 재확인하지 못했으므로 최신 실측으로 쓰지 않는다.

2026-11-02 12:47:46 UTC의 새 관리 조회3개로 새 서버 버전 `5999cf0d-4f18-4d43-bcd6-320e04860369` 100%, 접근/자료읽기ON·업로드/수집/피드백OFF·비밀 이름4개를 확인했다. 원문 비밀은 출력하지 않았다. 아직 옛 서버 현재 버전·기존 app Route·양쪽의 현재 안내 상태/로그 설정/접속 경로는 새 확인이 필요하다. 이 부분 조회를 전체 사전 검사 합격으로 쓰지 않는다.

### 다음 한 단위 — app 연결 교체

1. 대시보드 접근이 가능해지면 정확한 `app.pitcheezy.com/*` 기존 Route의 식별자·옛 대상·새 대상, 양쪽 현재 적용 버전·접근/안내/업로드/로그 설정을 새로 읽고 비공개 원장에 보존한다. 중복/겹침·예상 밖 대상이면 멈춘다. 오래된 단계4/이번 부분 조회를 실행 시점의 전체 사전 확인으로 대신하지 않는다.
2. 고정 검토 `7ec2e69733cfc651435a3ca10aeabf4a794e7475`의 `ops/public-host/run-exhibit-stage5.mjs`를 사용한다. 코드 SHA `64bbf3a7737a851a93504ca460be4f45e2356c6c0e58b675466dea47eaa26d4e`, 검사 SHA `43a58d793de38beba88b10b38a1d7d4a2f7086b66fe3cdf80f16292ba5eeea3d`는 이번 읽기 감사에서도 같았다. 다른 모델 검토와39검사 근거는 docs/results/exhibition_20261101/stage5-confirmation-preparation.json이다. 새 변경 없이 검사를 반복하지 않는다.
3. 비공개 준비본은 `D:/pitcheezy_exhibit_check/scope2-c47fe6cb-20261101/deployment-stage5-preparation/`에 있다. approved=false·UTC null·버전0인 준비본은 보존한다. 실제 새 사본에 approved=true·현재 버전·최대15분 UTC 창·새 run_id·원본 입력 SHA를 고정한다. 정상24/복구5, 합계29요청 이내다. 실행 폴더 마지막 이름은 run_id와 같아야 한다. 전환·복구 입력의 로컬 dry-run 합격을 Route 변경 전에 확인한다.
4. **대시보드에서 기존 app Route의 대상 한 개만 교체**한다. DNS/AAAA·Custom Domain·배포·비밀·홈/apex/www/media·옛 시험 Route는 바꾸지 않는다. 설정 파일 routes나 호스트 와일드카드는 금지다. 접근/자료읽기ON, 업로드/수집/피드백/안내OFF·로그 저장을 유지한다. 코드 없는 공개는 이번 범위가 아니다.
5. Route 적용 뒤 고정 실행기에 `--execute`를 붙여 최대24요청을 한 번 실행한다. 인자는 입력 파일 경로와 입력 SHA뿐이며 코드는 파일에서 읽는다. 기존 단계4 실행기의 app 거부를 풀거나 그 실행기로 대체하지 않는다. 코드·쿠키를 명령/채팅에 붙이지 않는다.
6. 실패하면 일반 요청은 멈추고 세션이 있으면 예약 로그아웃만 수행한다. 준비한 옛 Route 대상으로 복구한다. 옛 현재 자격이 있는 버전을 유지하며 비밀 등록 전 버전으로 되돌리지 않는다. 옛 날짜·다른 경기 목록도 돌아오는 복구임을 기록한다. 완료 영수증/dispatch가 있는 회차에만 실제 전환 입력SHA·버전을 결속한 복구5요청을 허용한다. 미종료 회차를 재실행하거나 다른 폴더로 우회하지 않는다.
7. 적용·HTTP 결과를 기록한다. **공개 app 폰/QR·단계5 저장 서버 로그가 남으면 그대로 미완료**로 쓴다. 기존 탭 새로고침/재로그인, 새 비공개 탭 접속 코드→849843 추천/존/투구 이동을 구분한다. 시험호스트 폰 확인이나 관리 버전 핀은 실제 app 폰/요청별 서버버전 증거를 대신하지 않는다.

원본 관리 출력과 설정 포인터는 `D:/pitcheezy_exhibit_check/host-1101/deploy-private-notes.json` 및 `D:/pitcheezy_exhibit_check/scope2-c47fe6cb-20261101/` 아래에 있다. 이번 부분 조회는 `deployment-stage5-preflight/`에만 보존했다. 호스트명·계정·자원명/ID·자격·원본 로그는 Git/이슈/채팅에 옮기지 않는다. 허용 공개 호스트와 버전UUID·SHA·비식별 집계만 보고한다.

### 전환 뒤 이어갈 일과 계속 보류할 것

- 클립팩v4 비공개 전달·형 수신 SHA 확인, 두 모니터 리허설, 형 전체 소스 검토 범위/모델ID 확인, 11/11 저녁(대안11/12) 공동시험의 시각·유한 원장·양측GO를 준비한다. 클립과 관전 화면은 같은 투구 ID로 수동 맞추며 자동 동기화로 설명하지 않는다.
- 새133건으로 10/26 미대조2건·옛host1 로그 꼬리를 닫지 않는다. 성능30/50명·요금/접근OFF·공개운영 완료도 별개다.
- #38 reply2는 실제 결과를 모아 사용자에게 보여주며 지금 발신하지 않는다. push·PR 병합/닫기·비용·접근 제한OFF·임시 자원 삭제는 따로 승인 범위를 확인한다.
- 팀원 저장소·프로세스·배포 변경, 기존 연구/페이지/worktree 삭제, 새CV·추가경기 개발은 하지 않는다. 형 원본 빌드 바이트 불변. 고정 Wrangler4.151.0만 사용하고 npx wrangler는 쓰지 않는다. Web Analytics Disabled 유지.
- 11/20 기능 동결, 11/21~23 리허설, 11/24 전시. 종료 시 CHECKLIST에 실제 결과·근거·다음 한 단위를 적고 같은 커밋에 인계 연결을 갱신한다. 크레딧 잔량은 자동으로 알 수 없으므로 단위마다 기록한다.

---


**새 전시 범위 재개 — 11/1 후속:** PLAN → CHECKLIST 상단 → COLLABORATION_PROTOCOL → [전시 호스트 분리 감사](EXHIBIT_HANDOFF_REVIEW_20261101.md#전시-전용-호스트-분리-인계-재검토--2026-11-01) → [미발신 reply2](mail_drafts/EXHIBIT-song-reply2-20261101.md). 현재 단계/담당은 CHECKLIST만 정본이다. 아래 인계 프롬프트와24자료 실행서는 당시 이력이며 그대로 재실행하지 않는다. 실제 신규 자원·배포·발행·안내·앱Route·발신은 각각 승인 뒤다. 새 ZIP은 받기 전 형식/검사 합격을 추정하지 않는다. 버전ID·SHA는 공유 가능하지만 자원명·시험주소·계정·자격값은 공개하지 않는다. 사용자가 규칙 수정·커밋과 host 후보 aa6f7ab 채택을 승인했다. 신규 이름은 지정 비공개 메모/계획에 준비했으며 자원 생성·배포는 별도 승인이다. 옛 시험 Route는 코드ON 유지. #38 회신은 후속 사용자 지시대로 요청 작업을 먼저 수행한 뒤 준비한다. 지금 발신하지 않는다. 실제 다음 단위·검증은 CHECKLIST 상단을 따른다.

**11/1 후속 재개 안내:** apex 전환·승인된 #38 회신·안내 문구 배포를 완료했다. 아래 날짜별 프롬프트는 과거 인계 기록이다. [CHECKLIST 상단](../CHECKLIST.md)과 [실제 배포·QR·리뷰 증거](EXHIBIT_NOTICE_DEPLOY_20261101.md)에서 남은 항목만 확인하며, 완료된 발신·배포·도메인 전환을 반복하지 않는다. iPhone Safari·Chrome 홈/접속 화면은 사용자 확인됐고 인증 뒤 경기까지의 전체 동선은 미확인이다.

## 현재 재개 위치

단계3/4 [저장 서버 로그133/133 대조 영수증](results/exhibition_20261101/stage34-server-log-correlation.json)과 iPhone Safari·Chrome 사용자 확인을 수신했다. 실제 결과·범위는 [단계4 후속 기록](EXHIBIT_STAGE4_RESULT_20261102.md#112-저장-서버-로그-대조-완료)을 읽는다. 완료한 인수/폰/저장로그를 다시 요청하지 않는다. 다음은 단계5의 현재 Route·양쪽 버전/설정 읽기 확인과 비공개 전환 원장 준비, 그 뒤 사용자 전환 승인이다. 아래 로그수신 대기는 수신 전 절차 설명이다.

JSON6의 [고정 공개 스키마 대조](results/exhibition_20261101/scoped-json-schema-validation.json)와 [포스터 알고리즘 제안](EXHIBIT_SONG_REQ_PLAN_20261101.md#포스터-데이터-흐름-보완-제안--2026-11-02-미발신)을 먼저 참고한다. 새 입력이나 결함 없이 같은 검사를 반복하지 않는다. 포스터는 팀원 검토 전 초안이며 원본 수정·발신은 하지 않았다.

[단계4 실제 결과](EXHIBIT_STAGE4_RESULT_20261102.md)가 있으면 동일 원격 검사를 다시 돌리지 않는다. 실제 폰 응답·두 구간 저장 로그를 받은 뒤 `scripts/correlate_exhibit_stage34_logs.py`로 오프라인 대조한다. 사용자 확인을 대신하지 않는다. 기다리는 동안에는 [단계5 전환·복구 계획](EXHIBIT_SCOPED_HOST_PREPARATION_20261101.md#승인-단계-5--공개-앱-연결-교체)과 [두 모니터 운영표](EXHIBIT_OPERATIONS_20261101.md)의 독립 준비만 이어간다. 단계4 CLI의 공개 주소 거부를 해제하지 않는다. 별도 `run-exhibit-stage5.mjs`의 [고정 검토·로컬 준비 영수증](results/exhibition_20261101/stage5-confirmation-preparation.json)을 먼저 확인한다. 현재 실행 여부는 CHECKLIST에서만 확인한다. 기본 dry-run 입력은 승인false/버전자리표시자이며 실제 전환 승인이 아니다. 이전 단계4 실행기로 app을 검사하지 않는다. #38은 결과를 모은 뒤 문안을 다시 보여 주며, 지금 발신·push하지 않는다.

단계3 완료 영수증이 있으면 발행 열쇠 등록·업로드를 다시 하지 않는다. 이후 전체 인수 준비/실행은 [단계4 유한 원장과 복구 계획](EXHIBIT_STAGE4_ACCEPTANCE_20261102.md)을 사용하고, 실제 승인·진행·완료 여부는 CHECKLIST 상단에서 확인한다. 준비용 approved=false와 로컬 검사를 원격 합격으로 취급하지 않는다.

단계2의 [고정15요청 합격 영수증](results/exhibition_20261101/stage2-predata-pass.json)이 있으면 등록·DNS 연결·같은 원격 검사를 반복하지 않는다. 서비스 검사기의 시작표식·부분/최종 원장을 모두 보존한다. 단계2 저장 로그는 [원본 대조 영수증](results/exhibition_20261101/stage2-server-log-correlation.json)을 확인한다. 해당 영수증이 있으면 같은 원격15요청을 로그 확보 목적으로 반복하지 않는다. 이번14개 Worker이벤트와 HTTP301 클라이언트1건을 구분하며, 기존host1 8단계·10/26 미대조2건은 별도다. 다음은 별도 승인 단계3 자료6 업로드이며, 후속 전체 인수/안내/폴링/폰·app전환도 별개다. 클라이언트 응답이나 관리 버전 조회만으로 요청별 서버 로그를 확인했다고 쓰지 않는다. 아래 단계2 시작 방법은 이전 경로 안내다. 실제 현재 상태/담당은 CHECKLIST 상단이 정본이다.

고정15요청 합격 영수증이 아직 없고 대시보드/주소 연결 확인점이 미완료인 경우에만: 단계2 등록 완료 근거가 있으면 [등록 완료 영수증](results/exhibition_20261101/stage2-registration-complete.json)을 먼저 읽는다. 최초 배포와 세 비밀 등록은 이미 수행되었으므로 원래 실행기와 복구 실행기를 모두 다시 실행하지 않는다. 다음은 사용자 대시보드 확인점과 정확한 시험 DNS/Route 생성 확인이며, 실제 생성 확인 전에는 시험 호스트 조회/서비스 요청을 하지 않는다. 버전/설정/바인딩 확인과 아직 미확인인 실제 대시보드·서비스 응답을 구분한다. 최신 완료·담당·다음 행동은 CHECKLIST 상단만 갱신한다.

이전 등록 중단 시점의 안내(등록 완료 또는15요청 합격 근거가 있으면 실행하지 않음): 사용자 등록이 최초 조회에서 중단된 경우 [중단·복구 근거](results/exhibition_20261101/stage2-registration-stop.json)를 먼저 확인한다. 이전 registration.started와 오류로그는 보존하며 삭제하지 않는다. 검토된 --resume-before-secrets는 최초버전·비밀0·등록원장 부재를 다시 확인하는 사용자 일회 실행이다. 재개 표식 또는 pending이 생겼으면 이 복구를 반복하지 않는다.

단계2는 [배포 영수증](results/exhibition_20261101/scoped-worker-deployed.json)·[등록 도구 검토](results/exhibition_20261101/stage2-registration-review.json)를 먼저 확인한다. 완료된 Worker 배포를 반복하지 않는다. 사용자 등록 완료 답변 뒤 비공개 등록 원장의3버전·최종 비밀 이름/vars/bindings를 읽어 확인하고, 사용자의 Logs/Web Analytics·DNS/Route 확인점으로 이어간다. 등록 실행기가 STOP 또는 시작 표식을 남겼으면 재실행하거나 비밀 등록 이전 버전으로 되돌리지 않는다. 일반 원격 검증기는 자료 업로드 뒤에만 사용하며 단계2는 `scripts/verify_exhibit_stage2_predata.py`의 고정15요청이다. DNS 생성 확인 전 실행 금지. 서비스HTTP 원장의 실제 실행 여부와 작업 담당은 CHECKLIST만 정본이며, 단계3 자료 업로드와 이후 전환은 별도 승인이다. 이번 기록은 미push로 유지한다.

새 호스트를 준비할 때는 [고정 후보·승인 단계별 실행서](EXHIBIT_SCOPED_HOST_PREPARATION_20261101.md)를 따른다. 단계1 자원 생성 결과가 있으면 비공개 원장의 완료 영수증과 새 DB ID를 재조회하고 이어가며 같은 이름을 다시 만들지 않는다. 실제 상태는 CHECKLIST 최상단을 따른다. 합성 자원 설정을 실제 배포하지 않는다. HEAD6/PUT6 계획과 후보는 비공개로 보관하며 실제 생성·배포·발신 여부는 CHECKLIST만 정본이다.

새 첨부 인수를 재개할 때는 [EXHIBIT-scope1 실제 검증 기록](EXHIBIT_SCOPED_INTAKE_20261101.md)과 그 안의 비공개 원본/최종 시험 경로를 먼저 확인한다. 이미 받은 c47fe6cb ZIP을 다시 요청하거나 fba6b2ff로 대체하지 않는다. 우리 도구 검토와 Song 앱 소스 검토·실제 서버 배포를 구별한다. 최신 상태/다음 단위는 CHECKLIST 상단만 갱신한다.

PR 정리를 이어갈 때는 [고정head 사전 검토](EXHIBIT_PR_PREFLIGHT_20261101.md)를 먼저 읽는다. 옛 준비 문서만 main에 먼저 반영하거나 연구 브랜치를 삭제하지 않는다. PR 상태 변경·push는 해당 승인 범위를 확인하며 진행 상태는 CHECKLIST를 따른다.

PLAN.md → CHECKLIST.md 맨 위를 먼저 읽는다. 11/1 17:22 KST 사용자 직접 Sites 도메인 해제 뒤 새 apex 홈의 바이트·HTTPS·영상·앱 접근 제한을 확인했다. 상세 증거는 [전환 검토 기록](EXHIBIT_HANDOFF_REVIEW_20261101.md#apex-전환-완료--2026-11-01-1722-kst)이며, 현재 수정자·완료 검사·다음 한 단위는 CHECKLIST만 정본이다. 아래 Claude 진행 기록과 최초 인수 종료 기록은 시점별 이력이다.

## Claude 진행 기록 (Codex 인계 전 이력)

- 작업 폴더 `C:/Users/zpfh1/Projects/transition-models-exhibit-1101`, 브랜치 `claude/exhibit-host1-1101`(Codex `233ad17`에서 시작). Codex 폴더는 읽기만.
- 완료: ①② 독립 재검증(받은 ZIP SHA·인수 재현, Python57·Node29, 팩 v2 SHA·270파일, 261클립을 형 경기 파일·팩 등록부·CV-47 등록부와 타석·구·선수·구종·SHA 대조 0불일치, 브라우저 이어재생·제외구 정지). 독립 추출본 `D:/pitcheezy_exhibit_check/clips-v2-claude`.
- 완료: Codex 코드 Claude 교차 검토(확인 16건, CHECKLIST EXHIBIT-review2), 로컬 Worker 인수 `ops/public-host/rehearse-exhibit-host.mjs`(84/0, 접근 코드 92/0).
- 완료: EXHIBIT-clips2 — 검토 지적 16건 수정(Fable 5.1 수정, Opus 검토·재시작 포트 규칙 보정), 최종 팩 v4 `D:/pitcheezy_exhibit_check/pitcheezy-849843-clips-v4.zip`(SHA 32f4377e…), Chrome 19/19.
- 완료(11/1 밤): 홈 전용 폴더·정적 호스트 설정(6af1d54), [운영표](EXHIBIT_OPERATIONS_20261101.md), [CV 발표 문단](EXHIBIT_CV_PRESENTATION_NOTE_20261101.md), #38 회신 초안 갱신. 사용자 방향: Codex 없이 되는 일 먼저, 홈은 Cloudflare로 이전(Sites 대기 안 함).
- 완료: ③ 준비 도구·배포 후보·[③ 명령 순서](EXHIBIT_HOST_DEPLOY_STEPS_20261101.md), Opus 검토 20건 수정(CHECKLIST EXHIBIT-host1b). Wrangler 4.151.0은 ops/public-host-tooling에 설치돼 있음.
- 완료(11/1 낮): **③ 시험 호스트 실제 연결** — 사용자 로그인(고정 Wrangler `node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js login`, 2분 안에 승인) → 배포·토큰 교체·업로드 24개·업로드 OFF·접속 코드 교체 → 원격 검사 35/35. 버전·발견 7건은 [③ 명령 순서 "실행 결과"](EXHIBIT_HOST_DEPLOY_STEPS_20261101.md), CHECKLIST EXHIBIT-host1c. 호스트명·코드는 채팅과 사용자 파일에만 있다(Git 밖 보관: `D:/pitcheezy_exhibit_check/host-1101/`, 접속 코드는 사용자 비공개 폴더(Projects 밖)의 `access-code.txt`).
- 완료(11/1 오후): ③-6 안내 ON/OFF 시험, ④-a `app.pitcheezy.com` 라우트·검사 35/35·iPhone 확인, ④-b 홈 Worker 배포·영상 R2 분리(`media.pitcheezy.com`, 정적 호스트 Range 미지원 때문)·iPhone 영상 확인. 결정: 안내 문구 채택, 클립팩 비공개 클라우드 링크, 모니터 2 = 이 노트북, #38은 ④ 뒤 발신. 상세는 [③ 문서 "④ 진행"](EXHIBIT_HOST_DEPLOY_STEPS_20261101.md).
- 11/1 14:3x: apex 전환 1차 시도는 OpenAI Sites의 SaaS custom hostname 때문에 미완(`www`는 새 홈, apex는 옛 홈; 상세는 ③ 문서 "④ 진행"). **사용자 결정: 여기서부터 Codex에 인계** — [인계 문서·프롬프트](CODEX_HANDOFF_EXHIBIT_20261101.md) 5절을 Codex 채팅에 붙여 넣는다. 다음 순서: apex (c) → #38 발신 → PR 정리 → 안내 문구 코드 변경 → ③ 꼬리.
- 실행 전 설명: [docs/EXHIBIT_HOST_PLAN_20261101.md](EXHIBIT_HOST_PLAN_20261101.md). 형 회신 초안(미발신): [mail_drafts/EXHIBIT-song-reply-20261101.md](mail_drafts/EXHIBIT-song-reply-20261101.md).
- 중단되면: `git -C <작업 폴더> status`로 미커밋 파일을 확인하고, 위 두 문서와 CHECKLIST 맨 위를 읽은 뒤 남은 단위만 이어간다. 실제 배포·도메인·형 발신은 사용자 승인 전 금지.

먼저 PLAN.md와 CHECKLIST.md 상단을 읽는다. 현재 지정 폴더는 C:/Users/zpfh1/Projects/transition-models-exhibit-1101, 브랜치는 claude/exhibit-host1-1101이다. 이전 Codex intake/site-first와 Claude site-games2 폴더는 읽기만 한다. 최신 진입은 CODEX_HANDOFF_EXHIBIT_20261101.md와 CHECKLIST 상단이다. 기존 코드·연구·비공개 자료를 삭제하지 않는다. 팀원 저장소·도메인·Sites는 변경하지 않는다(우리 Cloudflare 시험 Worker는 11/1 사용자 승인으로 변경했고, 추가 변경은 매번 설명·승인 뒤).

현재 단계/합격 근거는 CHECKLIST.md가 정본이다. 아래는 재개 방법이다.

## 세션 확인

1. 실제 pwd, git status --short --branch, git log -1, git worktree list 확인. 다른 수정자가 작업 중이면 같은 파일을 수정하지 않는다.
2. 사용자 순서는 받은 빌드 인수 →261클립팩/영상 전용 플레이어 →시험호스트 →도메인전환 →PR정리다. 어느 단계까지 실제 완료했는지는 CHECKLIST 맨 위를 확인하고 이미 끝난 배포·전환을 반복하지 않는다.
3. 다른 모델 검토와 로컬 브라우저 검사 결과를 보고 빠진 부분만 수행한다. 남은 크레딧 수치 자동 확인은 불가능하므로 작업 단위마다 기록한다.

## 입력과 보존

- 받은 ZIP bundle-849843-fba6b2ff: 867682bytes, SHA af10293d5134219b7f750d00786366b93b0134c895519b939fd99a356d77a4bc. Song 소스 fba6b2ff846dcfa9afad9ea5df4204007e0604c1.
- ZIP 원본은 사용자 첨부에 보존. 추출본/영상/브라우저 기록은 outputs/exhibition_1101/ (Git 제외).
- 원본 미디어 등록부는 이전 site-first worktree의 web/pitch-studio/game-849843-media.json, 클립·첨부·런타임의 정확한 로컬 위치는 Git 제외 outputs/exhibition_1101/local-inputs.private.json. 원본은 읽기만 한다.
- 849843:69:2는 구종 불일치로 제외. 262투구 중261영상. 잠금849844는 바이트 검사 외 열지 않는다.
- 날짜 목록23개 대비 날짜 파일5개, 최종 빌드 재검토 미실시, 실제iPhone未검수, 자동 두모니터 동기화未구현은 기존 인수 쟁점이다.

## 작업 경계

원본 Song 빌드를 수정하지 않는다. 변경 필요 사항은 근거와 함께 우리 초안에 적는다. 로컬 인수 합격을 배포·공동시험 합격으로 쓰지 않는다. 실제 배포/도메인 전환 전에는 사용자에게 적용 범위와 되돌리는 방법을 설명한다.

## 작업 중단 시

CHECKLIST에 마지막 완료 검사·현재 명령/프로세스·다음 한 단위를 적고, 추적할 파일만 명시적으로 커밋한다. 출력 ZIP과 원본 영상은 Git에 넣지 않는다. 이 문서를 새 Claude 채팅의 진입 파일로 사용한다.

## 최초 인수 종료 기록 — 제품 4cec0f8 당시 (현재 실행 지시 아님)

제품 고정4cec0f8, 로컬검사 및 내부다른모델검토완료. 상세최신상태는CHECKLIST맨위에 있다. 최종비공개팩은 outputs/exhibition_1101/pitcheezy-849843-clips-v2.zip, 같은이름.receipt.json과 함께 전달한다. v1은최종전달대상이아니다.

입력ZIP·미디어등록부·클립DB·런타임절대경로는 outputs/exhibition_1101/local-inputs.private.json. 받은원본추출은 received/site, 실행가능팩은 clips-849843-v2. 출력이없는다른기기에서는 이비공개파일을받기전 임의재생성/다운로드하지 않는다.

다음은 EXHIBIT-host1의 로컬호스트적용계획이다. 정적4파일과v1자료24파일을분리해야 하며 received/site 전체를ASSETS나R2에단순복사하지 않는다. 날짜목록23개/실제5개차이를형에게확인할초안은준비가능하나새발신은별도승인. 실제배포/접근/도메인변경전 사용자설명이필요하다. 기존페이지/CV/PR86/다른worktree는보존하고재개발하지 않는다.

계정크레딧300잔여를AI가자동감지할수없다. 작업한단위마다기록하고사용자가중단을알리면CHECKLIST를갱신한다. Claude전송은이번고정코드의명시승인부재로자동검토에서거절됐으므로재시도하지말고, 현재인수문서·우리제품코드에서이어간다.
