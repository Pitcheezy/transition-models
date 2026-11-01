# Claude 전시 작업 인계 — 2026-11-01

**새 전시 범위 재개 — 11/1 후속:** PLAN → CHECKLIST 상단 → COLLABORATION_PROTOCOL → [전시 호스트 분리 감사](EXHIBIT_HANDOFF_REVIEW_20261101.md#전시-전용-호스트-분리-인계-재검토--2026-11-01) → [미발신 reply2](mail_drafts/EXHIBIT-song-reply2-20261101.md). 현재 단계/담당은 CHECKLIST만 정본이다. 아래 인계 프롬프트와24자료 실행서는 당시 이력이며 그대로 재실행하지 않는다. 실제 신규 자원·배포·발행·안내·앱Route·발신은 각각 승인 뒤다. 새 ZIP은 받기 전 형식/검사 합격을 추정하지 않는다. 버전ID·SHA는 공유 가능하지만 자원명·시험주소·계정·자격값은 공개하지 않는다. 사용자가 규칙 수정·커밋과 host 후보 aa6f7ab 채택을 승인했다. 신규 이름은 지정 비공개 메모/계획에 준비했으며 자원 생성·배포는 별도 승인이다. 옛 시험 Route는 코드ON 유지. #38 초안은 ZIP 검증 뒤 결과를 넣어 다시 보여 주고 발신 전 재확인한다. 실제 다음 단위·검증은 CHECKLIST 상단을 따른다.

**11/1 후속 재개 안내:** apex 전환·승인된 #38 회신·안내 문구 배포를 완료했다. 아래 날짜별 프롬프트는 과거 인계 기록이다. [CHECKLIST 상단](../CHECKLIST.md)과 [실제 배포·QR·리뷰 증거](EXHIBIT_NOTICE_DEPLOY_20261101.md)에서 남은 항목만 확인하며, 완료된 발신·배포·도메인 전환을 반복하지 않는다. iPhone Safari·Chrome 홈/접속 화면은 사용자 확인됐고 인증 뒤 경기까지의 전체 동선은 미확인이다.

## 현재 재개 위치

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
