# Codex 인계 — 전시 호스트·도메인·PR 정리 (2026-11-01, Claude 작성)

Codex 사용 한도가 풀리는 **2026-11-04 16:04** 이후 Codex가 이어받을 때의 진입 문서다. 상태 정본은 [CHECKLIST.md](../CHECKLIST.md) 맨 위, 형 요구 5항목의 실행 계획은 [EXHIBIT_SONG_REQ_PLAN_20261101.md](EXHIBIT_SONG_REQ_PLAN_20261101.md), 호스트 실행 결과는 [EXHIBIT_HOST_DEPLOY_STEPS_20261101.md](EXHIBIT_HOST_DEPLOY_STEPS_20261101.md)다. 맨 아래에 **Codex 채팅에 붙여 넣을 프롬프트**가 있다. 이 문서는 Claude가 작업을 더 진행하면 갱신한다(마지막 갱신: 11/1 낮, ③ 완료 직후).

## 1. 지금 상태 (11/1 낮)

| 항목 | 상태 |
|---|---|
| 작업 폴더·브랜치 | `C:/Users/zpfh1/Projects/transition-models-exhibit-1101`, `claude/exhibit-host1-1101`(origin에 push). Codex 폴더 `C:/Users/zpfh1/.codex/worktrees/exhibition-intake-1101`은 233ad17 그대로, 읽기만 |
| ① 받은 빌드 인수 | 완료(Codex 233ad17 + Claude 독립 재검증). ZIP SHA `af10293d…`, 형 소스 `fba6b2ff` |
| ② 클립팩·영상 전용 플레이어 | 완료. 최종 팩 **v4** `D:/pitcheezy_exhibit_check/pitcheezy-849843-clips-v4.zip`(SHA `32f4377e…`, 261클립, 69:2 제외, 기본 주소 127.0.0.1:8741). 전달 방법·모니터 2 노트북은 사용자 결정 대기 |
| ③ 시험 호스트 연결 | **완료.** 우리 Cloudflare 시험 Worker에 host `f50020b` + 형 정적 4파일 배포, v1 자료 24개 업로드(바이트 일치), 접근 코드 ON, 업로드 OFF, 원격 검사 35/35. 버전 ID·발견 7건은 ③ 문서 "실행 결과". 안내 운영자 토큰 교체·안내 ON/OFF 시험(③-6)도 11/1 완료(iPhone에 안내 표시, 복귀 확인). 꼬리: 8단계 로그 영수증, 폰 경기 화면(`?game=849843`) 직접 확인, 형에게 주소·코드 비공개 전달 |
| ④ 도메인 전환 | 미실행. 계획: `app.pitcheezy.com` → 시험 Worker custom domain + 검사기 재실행; 홈은 `ops/public-home`(`pitcheezy-home` Worker, 정적만) 배포 → 임시 주소에서 iPhone Safari 영상 206 확인 → apex `pitcheezy.com` 전환(DNS 백업, Sites는 전시 뒤까지 유지). 사용자 설명·승인 뒤 |
| 홈 1페이지(형 요구 1) | `web/pitch-studio-home/` 준비 완료(로컬 확인). 배포는 ④ |
| CV(형 요구 3) | 새 개발 없음. 발표 문단 [EXHIBIT_CV_PRESENTATION_NOTE_20261101.md](EXHIBIT_CV_PRESENTATION_NOTE_20261101.md) |
| PR 정리(형 요구 4) | 미실행. 분류안은 계획 문서 (4)절: 병합 #66, #68, #76→#75, #83 + 이 브랜치 PR 신규; 닫기 16(CV #67, #69~#74, #77~#82; 사이트 #84, #85, #86). 건별 사용자 승인 |
| #38 회신 | [초안](mail_drafts/EXHIBIT-song-reply-20261101.md) 미발신. 사용자 승인으로만 발신 |
| 운영표 | [EXHIBIT_OPERATIONS_20261101.md](EXHIBIT_OPERATIONS_20261101.md) |

## 2. 비공개 위치 (Git 밖, 이 문서에는 값 없음)

- 시험 호스트명·Worker·버킷·DB 이름: Cloudflare 대시보드(사용자 계정) 또는 `D:/pitcheezy_exhibit_check/host-1101/deploy-private-notes.json`.
- 배포 후보 폴더(채워진 `host/wrangler.deploy.json` 포함): `D:/pitcheezy_exhibit_check/host-1101/candidate/`. 재배포·롤백은 이 설정으로.
- 업로드 계획·HEAD/PUT 영수증·검사 영수증·단계 스크립트(step5a/5b/7·notice-run `.ps1`): `D:/pitcheezy_exhibit_check/host-1101/trial-host/`. 스크립트 안의 경로는 Claude 작업 폴더 기준이라 D: 사본을 쓰려면 경로를 바꿔야 한다.
- 형 빌드 추출본·인수 영수증: `D:/pitcheezy_exhibit_check/host-1101/intake-claude/`.
- 관람 접속 코드: 사용자 비공개 폴더(Projects·TEMP 밖, 사용자가 위치를 안다)의 `access-code.txt`(ACL 사용자만 읽기). 발행 토큰 파일은 삭제됨(필요하면 helper로 새로 만들고 digest 재등록). 안내 운영자 토큰은 11/1 교체해 같은 비공개 폴더의 `notice-token.txt`에 있다(전시 당일 `notice-cli` 실행에 필요, `PITCHEEZY_NOTICE_TOKEN`으로만 읽음).
- Cloudflare 로그인은 사용자 본인(`node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js login`, 승인 2분 안). 비밀 등록(`secret put`)은 사용자가 친다.

## 3. 규칙 (바뀐 것 없음)

- 팀원(Song) 저장소·프로세스·배포는 읽기만. 형 빌드 바이트는 바꾸지 않는다.
- 비밀값·호스트명·버킷/DB·계정은 Git·이슈·CHECKLIST에 쓰지 않는다. 공개 기록은 버전 ID·SHA·pass/fail만.
- 실제 배포·DNS·Sites·형에게 발신·PR 병합/닫기는 사용자 설명·승인 뒤. 되돌리기는 항상 버전 ID 명시(`rollback <id> --config <후보>/host/wrangler.deploy.json`), 토큰·코드 교체 이전 버전으로는 되돌리지 않는다.
- Wrangler는 고정 4.151.0(`ops/public-host-tooling`)만. `npx wrangler`·다른 버전 금지(observability 처리 차이).
- 기존 파일·worktree·PR·연구는 삭제하지 않는다. CV·추가 경기 개발 중단. 11/20 동결.
- 운영 코드 변경은 작성 AI와 다른 모델이 검토한다. 이번 ③은 코드 변경 없음(문서·영수증만).
- Web Analytics: 존 `pitcheezy.com`의 자동 설치는 11/1에 사용자가 Disable했다. 홈 전환 뒤 다시 켜지지 않았는지 확인한다(켜지면 형 HTML에 비콘이 끼어 바이트 불일치).

## 4. Codex가 이어서 할 단위 (권장 순서)

1. **PR 정리(⑤)** — 계획 문서 (4)절의 분류대로 건별 승인 받아 병합 5·닫기 16. 이 브랜치는 PR을 열고(제목 "exhibit: host1 — 시험 호스트 연결·홈 1페이지·운영 문서") 다른 모델 검토 뒤 병합. 병합 뒤 CHECKLIST 맨 위 "공개 버전·소스 커밋" 줄을 main 기준으로 갱신.
2. **④가 아직이면 ④** — 사용자 설명·승인 → `app.pitcheezy.com` custom domain(대시보드, 사용자) → `verify-exhibit-remote.mjs --origin https://app.pitcheezy.com …` 35/35 → `ops/public-home` 배포(`wrangler deploy --config ops/public-home/wrangler.jsonc`) → 임시 주소 iPhone 영상 → apex 전환 → 홈 검사. 절차는 [ops/public-home/README.md](../ops/public-home/README.md) 5·6단계.
3. **③ 꼬리** — 8단계 비식별 로그 영수증(Workers Logs를 버전 ID로 걸러 시각·method·path·status·version 5필드만), 폰에서 경기 화면(`?game=849843`) 확인 기록. 안내 ON/OFF 절차는 [NOTICE.md](../ops/public-host/NOTICE.md)와 `D:/pitcheezy_exhibit_check/host-1101/trial-host/notice-run.ps1`(11/1 실제 사용) 참조.
4. **형 빌드 Codex 교차검토** — 형이 `review/PROMPT.md`를 비공개로 주면 Codex 앱에서 실행, 결과는 #38에 요약.
5. **11/11 공동시험 지원** — 접근 코드 ON 유지, 당일 8단계 로그 대조 영수증(시각·method·path·status·version 5필드), 요청량 확인.
6. **클립팩 v4 전달·모니터 2 리허설(11/21~23)** — 전달 방법·노트북은 사용자 결정. 운영표 체크 항목대로.
7. **전시 뒤** — Sites 내리기(Codex 담당), 접근 코드·토큰 정리, 기록.

## 5. Codex 채팅에 붙여 넣을 프롬프트

~~~text
Pitcheezy/transition-models 전시(2026-11-24) 준비를 Claude에게서 이어받는다.

작업 폴더: C:/Users/zpfh1/Projects/transition-models-exhibit-1101 (브랜치 claude/exhibit-host1-1101, origin에 push됨). 이 폴더에서 작업한다. 다른 worktree·팀원 저장소는 읽기만.
먼저 읽을 것(순서): PLAN.md → CHECKLIST.md 맨 위 절 → docs/CODEX_HANDOFF_EXHIBIT_20261101.md → docs/EXHIBIT_SONG_REQ_PLAN_20261101.md → docs/EXHIBIT_HOST_DEPLOY_STEPS_20261101.md의 "실행 결과" 절 → docs/EXHIBIT_OPERATIONS_20261101.md.

현재 상태: ① 형 고정 빌드 fba6b2ff 인수 완료, ② 261클립 팩 v4 완료(D:/pitcheezy_exhibit_check/pitcheezy-849843-clips-v4.zip), ③ 우리 Cloudflare 시험 호스트에 형 빌드·자료 24개 배포·원격 검사 35/35·안내 ON/OFF 시험 완료(접근 코드 ON, 업로드 OFF, 접속 코드·발행 토큰·안내 토큰 모두 11/1 교체), ④ 도메인 전환 미실행, ⑤ PR 정리 미실행, #38 회신 초안 미발신. 비공개 값(호스트명·Worker·버킷·DB·코드)은 Git 밖 D:/pitcheezy_exhibit_check/host-1101/ 과 사용자 파일에만 있다. 채팅·문서·이슈에 옮기지 않는다.

규칙: 팀원 저장소·프로세스·배포는 읽기만. 형 빌드 바이트 불변. 비밀값·호스트명은 Git·이슈·CHECKLIST에 쓰지 않는다(버전 ID·SHA·pass/fail만). 실제 배포·DNS·Sites·형에게 발신·PR 병합/닫기는 사용자에게 적용 범위와 되돌리기를 설명하고 승인받은 뒤에만. Wrangler는 ops/public-host-tooling의 고정 4.151.0만 쓴다(npx wrangler 금지). Cloudflare 로그인과 secret put은 사용자가 직접 한다. 기존 파일·worktree·PR·연구를 삭제하지 않는다. CV·추가 경기 개발은 없다. 11/20 동결. 운영 코드를 바꾸면 다른 모델이 검토한다. 한 파일 한 수정자, CHECKLIST는 작업과 같은 커밋에 갱신한다.

해야 할 단위(권장 순서, 각 단위 시작 전 CHECKLIST에 합격 기준을 적고 선점): (1) 열린 PR 정리 — docs/EXHIBIT_SONG_REQ_PLAN_20261101.md (4)절 분류대로 건별 승인 후 병합 5·닫기 16, 이 브랜치의 PR 생성·다른 모델 검토·병합, 병합 뒤 CHECKLIST "공개 버전·소스 커밋" 줄 갱신. (2) ④가 미완이면 ④ — app 하위 도메인 연결·검사기 재실행, ops/public-home 배포·iPhone 영상 확인·apex 전환(ops/public-home/README.md 5·6단계), Sites는 전시 뒤까지 유지. (3) ③ 꼬리 — 8단계 비식별 로그 영수증, 폰 경기 화면(?game=849843) 확인 기록(안내 ON/OFF 시험은 11/1 완료). (4) 형이 review/PROMPT.md를 주면 형 빌드 교차검토. (5) 11/11 공동시험 지원, 요청량 확인. (6) 클립팩 v4 전달·모니터 2 리허설(11/21~23). (7) 전시 뒤 Sites 내리기.

하지 말 것: 비밀 조회·출력, 접근 코드/토큰 교체 이전 버전으로 롤백, 형 저장소 변경, Web Analytics 자동 설치 재활성화, 새 기능·새 경기 추가.

시작하면 실제 pwd·git status·git log -1을 확인하고, 위 문서를 읽은 뒤 첫 단위의 합격 기준과 필요한 사용자 결정을 한 번에 물어라.
~~~
