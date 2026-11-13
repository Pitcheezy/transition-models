# Claude 전시 작업 인계 — 2026-11-02

## 2026-11-02 Claude 인계 프롬프트

아래를 새 Claude 채팅에 전달한다. 현재 상태 정본은 CHECKLIST 상단이다. 이 절 이후 과거 단계별 인계는 당시 이력이며 재실행 지시가 아니다.

Claude, Pitcheezy 11/24 전시 준비를 이어받아줘. **app Route 전환·24요청 검사·공개 앱 iPhone 두 브라우저 사용자 확인·저장 로그 24/24 대조가 11/2 밤에 모두 끝나 공개 app 전환 인수는 완료다. 동일 시험·대조를 반복하지 마.** 근거는 [단계5 결과 문서](EXHIBIT_STAGE5_RESULT_20261102.md#저장-로그-대조-완료--2026-11-02-밤-claude)와 [대조 영수증](results/exhibition_20261101/stage5-server-log-correlation-20261102.json). 실행기 `scripts/correlate_exhibit_stage5_logs.py`는 다른 모델 검토를 마쳤고 코드를 바꾸면 재검토가 필요하다. 11/3 교수님 시연의 접속 코드 유지 판단은 같은 문서 마지막 절에 있고 사용자 결정 대기다.

### 위치·진입 순서

- 작업 폴더 `C:/Users/zpfh1/Projects/transition-models-exhibit-1101`, 브랜치 `claude/exhibit-host1-1101`.
- 먼저 실제 pwd·git status·git log -1을 확인한다. 전환 결과 기록 커밋은 `e335974`이고 그 뒤에 Claude의 로그 대조 준비 커밋이 있다(현재 상태는 CHECKLIST 상단). 미커밋 변경과 기존 미추적 `outputs/exhibit_scope_preparation_20261101/`는 보존한다. 다른 작업자가 수정 중이면 같은 파일을 고치지 않는다.
- PLAN.md → CHECKLIST.md 상단 → docs/COLLABORATION_PROTOCOL.md → docs/EXHIBIT_STAGE5_RESULT_20261102.md → docs/results/exhibition_20261101/stage5-cutover-client-result-20261102.json → docs/EXHIBIT_SCOPED_HOST_PREPARATION_20261101.md 단계5 순서로 읽는다.
- 로컬 커밋은 미push 유지한다. 사용자 요청은 작업 후 인계이며 새 발신·push·PR 병합/닫기 승인이 아니다.

### 완료 — 반복하지 말 것

1. 새 전시 시험 서버에 Song c47 고정 빌드·JSON6을 올리고 별도 인수 완료. 웹 `c47fe6cb78479362e7250141da946814cc33bd31`, 자료생성 선언 `cb1cfa8f759fd77adc75595316a389208c752dba`를 구별한다. ZIP182517bytes, SHA `3c3b8006b892872bfff3423e2bd6ba49ea3de17ee92fbecef07e0b076bc8da51`. 형 원본 불변, 849843 한 경기·9/30 하루·262구/71타석·추천246/미지원16.
2. 시험 호스트 자동120/212요청·24/24판정·600초관찰·안내ON숨김→브라우저 합성오류2건에도숨김→OFF복원·로그아웃 완료. 시험 주소의 iPhone Safari/Chrome도 사용자 확인. 업로드13건+인수120건 저장 로그133/133 일치·누락/중복/불일치0. 이 검사·폰·내보내기를 반복하지 않는다.
3. 사용자 노트북 Cloudflare 대시보드의 전체Route5개에서 기존 app 정확경로1개와 새 시험 대상 확인. 자동 UI는 현재URL 식별 실패라 사용자 수동 조작으로 진행했다. 다시 로그인시키거나 Parsec 원인으로 확정하지 않는다. 사용자가 app 편집창의 새 대상 선택 캡처, 양쪽 Logs/Invocation/Persist ON·100% 확인, 마지막 Save 완료를 보고했다.
4. app Route 한 개 저장 뒤 **2026-11-02 22:21:54.576~22:22:01.417 KST**에 검토된 단계5 실행을1회 완료: **24요청·24판정 통과, 재시도0, 복구0, 로그아웃204**. app에서 새 정적4/자료6/보조1 바이트, 비로그인401·업로드OFF503·제외3경로404 확인. 홈/apex/www/media·옛시험Route·DNS·배포·자격·형저장소 변경 없음. 공개app는 c47바이트 응답을 확인했지만 **공개app 폰 동선은 이후 사용자 “Safari·Chrome 모두 정상” 응답을 받았고, 요청별 저장로그 대조만 남는다.**

### 현재 핀과 비공개 기록

- 새 관리 버전 `5999cf0d-4f18-4d43-bcd6-320e04860369`; 기존 `6d652d4b-7d3c-4897-aefd-f37d0edce50c`. 관리 핀은 요청별 실제 서버버전 증거가 아니다.
- 도구 `ops/public-host/run-exhibit-stage5.mjs` 소스 `7ec2e69733cfc651435a3ca10aeabf4a794e7475`, SHA `64bbf3a7737a851a93504ca460be4f45e2356c6c0e58b675466dea47eaa26d4e`. 다른모델 검토+39검사 근거는 stage5-confirmation-preparation.json. 새 코드 변경 없이 다시 검사하지 않는다.
- 실행 회차: `D:/pitcheezy_exhibit_check/scope2-c47fe6cb-20261101/deployment-stage5-dashboard-preflight/stage5-app-20261102/`. `cutover/result.private.json`, `cutover/requests/`, `cycle.private.json`, `route-save-and-client-result.private.json` 보존.
- 부모의 active-inputs-131719.private.json과 승인 입력2개는 이미 사용한 창(13:17:19.623Z~13:32:19.623Z)이다. **다른 폴더/새창으로 같은 시험을 반복하지 않는다.** 정상24/복구5 합계29원칙은 유지하되 현재 복구할 이유는 없다.
- 사용자 안내는 회차의 stage5-followup.private.txt, 로그 폴더는 server-log-exports/. 비공개 호스트/계정/자원명/자격/Ray/원본로그를 Git·이슈·채팅에 쓰지 않는다. 공개호스트·버전UUID·SHA·비식별집계만 허용한다.

### 완료된 증거 — 반복하지 말 것 (11/2 밤)

1. 공개 app iPhone Safari/Chrome은 **사용자 “Safari·Chrome 모두 정상” 응답으로 완료**했다(기존app탭 새로고침/같은코드 재로그인, 새비공개탭 홈→서비스열기→코드→9/30하루·추천/존·투구이동). 도구 관측은 아니며 상세 버전/정확 관측시각은 미제공이다.
2. 새 서버 Observability export(23:29 KST 생성, SHA `4d767bba…`)는 회차 server-log-exports/에 보존 복사했다. `scripts/correlate_exhibit_stage5_logs.py` 1회 실행으로 **서버 26행 중 원장24건 전부 matched**, 실제 서버 버전 5999cf0d, 추가2건(모바일 UA 정적 GET 401)은 집계만. [대조 영수증](results/exhibition_20261101/stage5-server-log-correlation-20261102.json), [원장 사전 검증](results/exhibition_20261101/stage5-ledger-precheck-20261102.json). 같은 export·명령을 다시 돌리지 않는다(출력 파일이 있으면 실행기가 거부한다).
3. CHECKLIST 공개 버전 줄·단계5 결과·이 인계·미발신 reply2를 갱신했다.
4. **11/2~11/3 완료(반복 금지):** reply2 게시(11/2 23:43 KST, 댓글 6580008880), review3 정적 검토(PASS_WITH_NOTES), 11/1 8단계 로그 대조(700건 7규칙), PR 정리(병합 5·닫기 16·전시 PR #87, 기록 PR #88 → main `a0c6906`), 임시 홈 시험 호스트 정리 확인, 클립팩 v4 Drive 업로드·뷰어 공유 → 사용자 직접 전달 → **Song 11/3 14:57 KST [#38 댓글 6596608201](https://github.com/SongRoute/pitcheezy/issues/38#issuecomment-6596608201)로 수신·내용 검증 보고(Song 보고 기준: MANIFEST 270파일 크기·SHA 일치, 261/262, 제외 69:2, 메타 해시가 공개 영수증과 일치; ZIP 전체 SHA·verify 출력·재생·동기화는 미보고)**, Song 지정 검토 base·범위가 우리 대조로 review3와 동일, 모니터 1은 262구 발행기 재생 경로 사용 계획. 11/11 시각은 미확정.

### 다음 한 단위

- (갱신 2026-11-12: reply3는 끝내 게시하지 않았다. 내용은 [reply5](mail_drafts/EXHIBIT-song-reply5-20261112.md)에 합쳐 11/12 15:49 KST에 게시했고, 공동시험은 11/13(금) 21시로 확정됐다. 현재 상태는 CHECKLIST 맨 위를 따른다. 이 줄의 나머지는 원래 계획이다.) [reply3 초안](mail_drafts/EXHIBIT-song-reply3-20261103.md)을 사용자 "보내" 승인 뒤 #38에 1회 게시한다(시연 결과 한 줄은 게시 전에 채운다). 그 전에는 발신 0.
- 독립 작업: 11/11 공동시험 시각(→ 11/13 금 21시로 확정)·두 모니터·폰 공동 리허설 날짜 확정(리허설 날짜는 Song 제안 대기), 모니터 2 리허설(verify → serve → Chrome), 홈 소개 카드 그림 복원안(사용자가 "ㄱㄱ"하면 03 문구 수정·04 제외로 작성 → 다른 모델 검토 → 배포 전 설명).
- 사용자 결정 대기: 옛 Sites 기본 주소(docs/INTENT_DEMO_SITE.md 9행)가 옛 8페이지를 인증 없이 공개 중인 상태의 처리, SPOTV NOW VOD(id 249222, 베이직 ₩9,900 웹) 구매와 상영 허가.
- 11/3 16:30 교수님 시연은 접속 코드 유지·발표 기기 15:45 이후 사전 로그인·리허설 1회(사용자 결정). '연결 끊김' 칩은 60분 세션 만료 또는 네트워크 끊김 표시이며 새로고침 → 코드 재입력으로 복구한다.

### 이후 남은 일·경계

- 클립팩 v4는 Song 보고 기준 수신·내용 검증 완료(ZIP SHA·verify 출력 미보고). 남은 것은 Song 쪽 플레이어 재생 확인과 두 모니터·폰 공동 리허설. 두 화면은 같은 투구 ID로 수동 맞춤이며 자동 동기화로 설명하지 않는다.
- 형 전체 소스 검토 범위는 11/3 확정(base 61be7a8 → c47fe6c, apps/observer/** + scripts/publisher_replay.py = review3). 실제 검토 모델 ID·ZIP 밖 원증거 미대조는 양쪽 다 미완료 유지. 11/11 저녁(대안 11/12) 공동시험 시각·유한 원장·양측 GO는 별개다.
- 10/26미대조2건·옛host1꼬리·30/50명용량·요금·접근OFF·공개운영GO는 이번24요청으로 완료하지 않는다.
- 사용자 요청대로 형 작업 결과를 모아 회신초안을 보여 준다. 지금 #38발신·push·PR병합/닫기·비용·접근OFF·임시자원삭제는 하지 않는다.
- 팀원저장소/프로세스/배포 변경, 기존연구/페이지/worktree삭제, 새CV/경기추가 금지. 형 바이트 고정. 고정Wrangler4.151.0만, 설정파일routes/호스트와일드카드 금지, WebAnalytics Disabled.
- 11/20동결→11/21~23리허설→11/24전시. 매 단위 종료 시 완료기능·근거·남은조건·다음한단위를 CHECKLIST와 같은 커밋에 남긴다.

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
