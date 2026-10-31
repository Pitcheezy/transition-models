# Claude 전시 작업 인계 — 2026-11-01

## Claude 진행 기록 (이 절을 먼저 본다)

- 작업 폴더 `C:/Users/zpfh1/Projects/transition-models-exhibit-1101`, 브랜치 `claude/exhibit-host1-1101`(Codex `233ad17`에서 시작). Codex 폴더는 읽기만.
- 완료: ①② 독립 재검증(받은 ZIP SHA·인수 재현, Python57·Node29, 팩 v2 SHA·270파일, 261클립을 형 경기 파일·팩 등록부·CV-47 등록부와 타석·구·선수·구종·SHA 대조 0불일치, 브라우저 이어재생·제외구 정지). 독립 추출본 `D:/pitcheezy_exhibit_check/clips-v2-claude`.
- 완료: Codex 코드 Claude 교차 검토(확인 16건, CHECKLIST EXHIBIT-review2), 로컬 Worker 인수 `ops/public-host/rehearse-exhibit-host.mjs`(84/0, 접근 코드 92/0).
- 완료: EXHIBIT-clips2 — 검토 지적 16건 수정(Fable 5.1 수정, Opus 검토·재시작 포트 규칙 보정), 최종 팩 v4 `D:/pitcheezy_exhibit_check/pitcheezy-849843-clips-v4.zip`(SHA 32f4377e…), Chrome 19/19.
- 완료(11/1 밤): 홈 전용 폴더·정적 호스트 설정(6af1d54), [운영표](EXHIBIT_OPERATIONS_20261101.md), [CV 발표 문단](EXHIBIT_CV_PRESENTATION_NOTE_20261101.md), #38 회신 초안 갱신. 사용자 방향: Codex 없이 되는 일 먼저, 홈은 Cloudflare로 이전(Sites 대기 안 함).
- 진행 중: Fable 에이전트가 원격 검사 도구·배포 후보·토큰 도우미·업로드 계획 생성기·③ 명령 순서 문서 작성(ops/public-host). 끝나면 Opus 검토 → 커밋.
- 다음: 사용자 Cloudflare 로그인(`npx wrangler login`, wrangler 설치 필요) 뒤 ③ 실행. 사용자 결정 미수신 항목: 안내 문구, 클립팩 전달 방법, 모니터 2 노트북.
- 실행 전 설명: [docs/EXHIBIT_HOST_PLAN_20261101.md](EXHIBIT_HOST_PLAN_20261101.md). 형 회신 초안(미발신): [mail_drafts/EXHIBIT-song-reply-20261101.md](mail_drafts/EXHIBIT-song-reply-20261101.md).
- 중단되면: `git -C <작업 폴더> status`로 미커밋 파일을 확인하고, 위 두 문서와 CHECKLIST 맨 위를 읽은 뒤 남은 단위만 이어간다. 실제 배포·도메인·형 발신은 사용자 승인 전 금지.

먼저 PLAN.md와 CHECKLIST.md 상단을 읽는다. 현재 폴더는 codex/exhibition-intake-1101 전용 worktree이며 이전 site-first, Claude site-games2와 별개다. 기존 코드·연구·비공개 자료를 삭제하지 않는다. 팀원 저장소·Cloudflare·도메인을 변경하지 않는다.

현재 단계/합격 근거는 CHECKLIST.md가 정본이다. 아래는 재개 방법이다.

## 세션 확인

1. 실제 pwd, git status --short --branch, git log -1, git worktree list 확인. 다른 수정자가 작업 중이면 같은 파일을 수정하지 않는다.
2. 사용자 최신 지시는 받은 빌드 인수 →261클립팩/영상 전용 플레이어 →시험호스트 →도메인전환 →PR정리. 앞 두 단계만 지금 실행한다.
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

## 이번 종료 지점

제품 고정4cec0f8, 로컬검사 및 내부다른모델검토완료. 상세최신상태는CHECKLIST맨위에 있다. 최종비공개팩은 outputs/exhibition_1101/pitcheezy-849843-clips-v2.zip, 같은이름.receipt.json과 함께 전달한다. v1은최종전달대상이아니다.

입력ZIP·미디어등록부·클립DB·런타임절대경로는 outputs/exhibition_1101/local-inputs.private.json. 받은원본추출은 received/site, 실행가능팩은 clips-849843-v2. 출력이없는다른기기에서는 이비공개파일을받기전 임의재생성/다운로드하지 않는다.

다음은 EXHIBIT-host1의 로컬호스트적용계획이다. 정적4파일과v1자료24파일을분리해야 하며 received/site 전체를ASSETS나R2에단순복사하지 않는다. 날짜목록23개/실제5개차이를형에게확인할초안은준비가능하나새발신은별도승인. 실제배포/접근/도메인변경전 사용자설명이필요하다. 기존페이지/CV/PR86/다른worktree는보존하고재개발하지 않는다.

계정크레딧300잔여를AI가자동감지할수없다. 작업한단위마다기록하고사용자가중단을알리면CHECKLIST를갱신한다. Claude전송은이번고정코드의명시승인부재로자동검토에서거절됐으므로재시도하지말고, 현재인수문서·우리제품코드에서이어간다.
