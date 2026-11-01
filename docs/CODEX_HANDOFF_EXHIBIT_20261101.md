# Codex 인계 — 전시 호스트·도메인·PR 정리 (2026-11-01, Claude 작성 · 11/1 14:40 KST 최종)

**2026-11-01 사용자 재개 지시로 Codex가 이어받았다.** 11/4까지 기다린다는 문구는 작성 당시의 한도 기록이다. 사용자 결정(11/1 14:3x): **apex 전환(2번)부터 Codex에 넘긴다.** 상태 정본은 [CHECKLIST.md](../CHECKLIST.md) 맨 위, 형 요구 5항목의 실행 계획은 [EXHIBIT_SONG_REQ_PLAN_20261101.md](EXHIBIT_SONG_REQ_PLAN_20261101.md), 호스트 실행 결과·발견은 [EXHIBIT_HOST_DEPLOY_STEPS_20261101.md](EXHIBIT_HOST_DEPLOY_STEPS_20261101.md)("실행 결과"·"④ 진행")다. 맨 아래 5절이 **Codex 채팅에 붙여 넣을 프롬프트**다.

## 검토 후 재개 주의 — 2026-11-01

**11/1 17:22 KST 후속:** 사용자 직접 Sites 도메인 해제 뒤 apex 전환을 실제 확인했다. 아래 14:34 상태·5절 붙여넣기 프롬프트는 인계 당시 기록이며 apex 전환을 다시 실행하지 않는다. [전환 증거](EXHIBIT_HANDOFF_REVIEW_20261101.md#apex-전환-완료--2026-11-01-1722-kst)와 CHECKLIST 맨 위가 현재 재개 기준이다. 추가 배포·발신·PR 병합/닫기는 각각 기존 승인 경계를 유지한다.

[Codex 인계 리뷰](EXHIBIT_HANDOFF_REVIEW_20261101.md)에서 오래된 활성 버전·자격 교체 전 복구 지시·폰 복원 시간 과장을 정정했다. CHECKLIST가 현재 상태의 정본이다. 최초 리뷰 당시의 apex 승인 대기는 이후 사용자 승인·전환 검증으로 해소됐다. Sites 재연결의 즉시 복구는 여전히 미검증이며 앱 Worker의 과거 버전 롤백을 apex 복구와 섞지 않는다. 아래 날짜별 실행 결과는 당시 관측이다.

## 1. 지금 상태 (11/1 14:34 KST 실측)

| 주소/항목 | 상태 |
|---|---|
| 작업 폴더·브랜치 | `C:/Users/zpfh1/Projects/transition-models-exhibit-1101`, `claude/exhibit-host1-1101`(origin에 push, 마지막 커밋은 이 문서 포함). Codex 폴더 `C:/Users/zpfh1/.codex/worktrees/exhibition-intake-1101`은 233ad17 그대로, 읽기만 |
| ① 받은 빌드 인수 | 완료. ZIP SHA `af10293d…`, 형 소스 `fba6b2ff` |
| ② 클립팩·영상 전용 플레이어 | 완료. 최종 팩 **v4** `D:/pitcheezy_exhibit_check/pitcheezy-849843-clips-v4.zip`(SHA `32f4377e…`, 261클립). 전달 방법 결정: 비공개 클라우드 링크(링크 보유자만·기한) + SHA, 전시 당일 USB 백업. 업로드는 사용자 계정에서 |
| ③ 시험 호스트 | 완료. 시험 호스트명(비공개)과 **`app.pitcheezy.com`** 둘 다 원격 검사 35/35, iPhone LTE 확인. 접근 코드 ON(11/21 OFF 예정), 업로드 OFF, 안내 OFF. 접속 코드·발행 토큰·안내 운영자 토큰 모두 11/1 교체. 안내 ON/OFF 시험 완료 |
| `app.pitcheezy.com` | 앱 Worker에 **Route `app.pitcheezy.com/*`**(DNS AAAA `100::` Proxied). 대시보드 "Add Domain(custom domain)" 창이 하위 호스트의 존을 못 찾아 Route 방식으로 붙였다. 정상 |
| `www.pitcheezy.com`, 임시 홈 호스트 | **홈 Worker `pitcheezy-home`**(정적 9파일, 영상만 R2) — 새 홈이 이미 나온다. Route `www.pitcheezy.com/*`·임시 호스트 Route. 와일드카드 라우트는 11/1 삭제함(다시 넣지 않는다) |
| `media.pitcheezy.com` | 전용 R2 버킷의 custom domain(TLS 1.2, r2.dev 비활성). 홈 영상 mp4·포스터 jpg, immutable 캐시, Range 206. 정적 호스트는 Range를 지원하지 않아 분리했다 |
| **`pitcheezy.com`(apex)** | **아직 OpenAI Sites의 옛 홈.** DNS A 레코드 2개는 Proxied로 바꿨고 홈 Worker에 Route `pitcheezy.com/*`도 있지만, apex가 OpenAI Sites의 **Cloudflare for SaaS custom hostname**(DNS의 `_cf-custom-hostname` TXT)이라 Cloudflare가 OpenAI 쪽 설정을 먼저 적용해 우리 Worker가 돌지 않는다(문서: O2O는 SaaS 대상으로 가는 Proxied **CNAME**일 때만). 방문자는 옛 홈을 정상적으로 본다(장애 아님). **→ Codex 첫 단위** |
| 홈 1페이지(형 요구 1) | 파일 `web/pitch-studio-home/`(영상 src만 media 호스트). apex 전환이 끝나야 공개 반영 |
| CV(형 요구 3) | 새 개발 없음. 발표 문단 [EXHIBIT_CV_PRESENTATION_NOTE_20261101.md](EXHIBIT_CV_PRESENTATION_NOTE_20261101.md) |
| PR 정리(형 요구 4) | 미실행. 분류안은 계획 문서 (4)절: 병합 #66, #68, #76→#75, #83 + 이 브랜치 PR 신규; 닫기 16(CV #67, #69~#74, #77~#82; 사이트 #84, #85, #86). 건별 사용자 승인 |
| #38 회신 | [초안](mail_drafts/EXHIBIT-song-reply-20261101.md) "## 회신" 절이 최종 문안(③·④-a 결과 반영). **미발신.** 사용자 "보내" 뒤 `gh issue comment`로 SongRoute/pitcheezy#38에 올린다. apex가 끝났으면 "옮기는 중"을 "옮겼어"로 바꾼다 |
| 안내 문구 | 결정됨: **"잠시 자료를 확인하고 있어요. 곧 다시 보여 드릴게요."** 아직 코드는 개발용 문구. 코드 변경 + 다른 모델 검토 + 재배포 필요(11/20 전) |
| 운영표·모니터 2 | [EXHIBIT_OPERATIONS_20261101.md](EXHIBIT_OPERATIONS_20261101.md). 모니터 2 = 이 Windows 노트북 |

## 2. 비공개 위치 (Git 밖, 이 문서에는 값 없음)

- 시험 호스트명·Worker·버킷·DB 이름, 버전 ID·시각·단계별 메모: `D:/pitcheezy_exhibit_check/host-1101/deploy-private-notes.json`.
- 배포 후보 폴더(채워진 `host/wrangler.deploy.json`): `D:/pitcheezy_exhibit_check/host-1101/candidate/`. 앱 Worker 재배포·롤백은 이 설정으로. 되돌리기 기준 버전 ID도 메모에 있다.
- 업로드 계획·HEAD/PUT 영수증·검사 영수증·안내 스냅샷·단계 스크립트(step5a/5b/7·verify-origin·notice-run·probe-root `.ps1`), 검사 전용 `dns-preload.mjs`: `D:/pitcheezy_exhibit_check/host-1101/trial-host/`. **스크립트 안의 경로는 Claude 임시 폴더 기준이라 D: 사본을 쓰려면 경로를 바꾼다.**
- 형 빌드 추출본·인수 영수증: `D:/pitcheezy_exhibit_check/host-1101/intake-claude/`.
- 관람 접속 코드 `access-code.txt`, 안내 운영자 토큰 `notice-token.txt`: 사용자 비공개 폴더(Projects·TEMP 밖, 위치는 사용자가 안다; ACL 사용자만). 발행 토큰 파일은 삭제됨(필요하면 `ops/public-host/exhibit-token-helper.mjs`로 새로 만들고 사용자가 `secret put PUBLISH_TOKEN_SHA256`).
- Cloudflare 로그인은 사용자 본인(`node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js login`, 브라우저 승인은 **2분 안에**; 저장소 루트에서 실행). `whoami`로 확인. `secret put`은 사용자가 친다(PowerShell 파이프 `"<digest>" | node … secret put NAME --config <후보>/host/wrangler.deploy.json`).

## 3. 규칙 (바뀐 것 없음)

- 팀원(Song) 저장소·프로세스·배포는 읽기만. 형 빌드 바이트는 바꾸지 않는다.
- 비밀값·시험 호스트명·버킷/DB·계정은 Git·이슈·CHECKLIST에 쓰지 않는다(공개 호스트명 `pitcheezy.com`·`app.`·`www.`·`media.`는 써도 된다). 공개 기록은 버전 ID·SHA·pass/fail만.
- 실제 배포·DNS·Sites·형에게 발신·PR 병합/닫기는 사용자에게 적용 범위와 되돌리기를 설명하고 승인받은 뒤. 롤백은 항상 버전 ID 명시, 토큰·코드 교체 이전 버전으로는 돌리지 않는다.
- Wrangler는 고정 4.151.0(`ops/public-host-tooling`)만. `npx wrangler`·다른 버전 금지. 설정 파일에 `routes`를 넣지 않는다(설정 검사기가 거부) — 도메인은 대시보드 Route로만.
- 와일드카드 Route(`*.pitcheezy.com/*`) 금지 — 11/1에 media 호스트까지 가로채 404를 냈다.
- 존 `pitcheezy.com`의 Web Analytics 자동 설치는 **Disable 유지**(켜지면 형 HTML에 비콘이 끼어 바이트 불일치). 홈 전환 뒤 다시 확인.
- 기존 파일·worktree·PR·연구는 삭제하지 않는다. CV·추가 경기 개발 없음. 11/20 동결. 운영 코드 변경은 다른 모델이 검토. 한 파일 한 수정자, CHECKLIST는 작업과 같은 커밋에 갱신.

## 4. Codex가 이어서 할 단위 (권장 순서)

1. **apex 전환 마무리(④-b, 형 요구 1·2)** — 사용자 승인 뒤 **(c) 방식**: 사용자가 OpenAI Sites 대시보드에서 `pitcheezy.com` 도메인 연결을 해제(custom hostname 등록 삭제) → 우리 존으로 전환되는지 실제 응답으로 확인한다(반영 시간 미측정). 확인: `curl.exe -s -D - -o NUL https://pitcheezy.com/`가 200 + `x-frame-options: DENY`·`x-content-type-options: nosniff`, 본문에 `https://media.pitcheezy.com/hero-849843-four-pitches-v1.mp4`와 `app.pitcheezy.com/?game=849843`가 있고 `cloudflareinsights` 없음; `http://pitcheezy.com/` → https 리다이렉트; `curl.exe -s -D - -o NUL -H "Range: bytes=0-1" https://media.pitcheezy.com/hero-849843-four-pitches-v1.mp4` → 206; `https://app.pitcheezy.com/v1/manifest.json` → 401 + `X-Pitcheezy-Access: required`. 폰(iPhone·Android) QR 흐름(홈 → 서비스 열기 → 앱). 복구안: Sites 도메인 재연결·검증/TLS 활성 상태 확인 후 홈 Worker의 정확한 Route `pitcheezy.com/*`만 해제(재연결은 재검증·전파가 필요할 수 있어 즉시 복구를 보장하지 않음)(A 레코드는 Proxied여도 SaaS 쪽이 받는다). 대안 (b): OpenAI가 준 CNAME 대상이 있으면 apex를 그 대상으로 Proxied CNAME(플래트닝)으로 바꾸면 O2O로 우리 Worker가 먼저 돈다. 끝나면 CHECKLIST 맨 위 "공개 버전" 줄과 EXHIBIT-host1을 갱신하고, `pitcheezy.com` 응답에 비콘이 없는지(Web Analytics Disable) 다시 본다.
2. **#38 회신 발신** — 초안 "## 회신" 절을 사용자에게 보여 주고 "보내" 뒤 `gh issue comment 38 --repo SongRoute/pitcheezy --body-file <문안파일>`(gh는 이 PC에 로그인돼 있음). 시험 호스트명·코드는 절대 넣지 않는다. 발신 뒤 사용자가 접속 코드를 비공개 채널로 형에게 보낸다. 이후 PR 정리 결과는 짧은 후속 댓글.
3. **PR 정리(⑤, 형 요구 4)** — 계획 (4)절 분류대로 건별 승인 후 병합 5·닫기 16. 이 브랜치는 PR을 열고(제목 "exhibit: host1 — 시험 호스트·app/홈 도메인·운영 문서") 다른 모델 검토 뒤 병합. 병합 뒤 CHECKLIST "공개 버전·소스 커밋" 줄을 main 기준으로.
4. **안내 문구 코드 변경** — `ops/public-host/notice.mjs`의 `NOTICE_MESSAGES.maintenance`(현재 "개발용 안내 문구(승인 전): …")를 결정 문구로, 안내 HTML의 "개발용 안내 화면입니다…" 설명도 제거/수정, 관련 테스트 갱신 → 다른 모델 검토 → `scripts/build_public_host_release.py`로 새 후보 → 설정 검사 → 배포(새 버전 ID 기록) → `notice-run`과 같은 절차로 ON/OFF 1회 재확인. 11/20 전.
5. **③ 꼬리** — 8단계 비식별 로그 영수증(Workers Logs를 버전 ID로 걸러 시각·method·path·status·version 5필드), 폰 경기 화면(`?game=849843`) 확인 기록.
6. **형 빌드 Codex 교차검토** — 형이 `review/PROMPT.md`를 비공개로 주면 Codex 앱에서 실행, 결과는 #38 요약.
7. **11/11 공동시험 지원** — 접근 코드 ON 유지, 당일 로그 대조, 요청량 확인(화면당 약 480요청/시간, Free 하루 100,000).
8. **클립팩 v4 전달·모니터 2 리허설(11/21~23)** — 운영표 체크 항목대로.
9. **전시 뒤** — Sites 정리(도메인 해제 뒤 사이트 삭제 여부는 사용자 결정), 접근 코드·토큰 정리, 기록.

## 5. Codex 채팅에 붙여 넣을 프롬프트

~~~text
Pitcheezy/transition-models 전시(2026-11-24) 준비를 Claude에게서 이어받는다. Claude는 2026-11-01에 ①빌드 인수 재검증, ②클립팩 v4, ③시험 호스트 연결(검사 35/35·안내 ON/OFF), ④-a app.pitcheezy.com 연결, ④-b 홈 Worker·영상 R2 분리까지 끝냈고, apex 전환부터 네가 맡는다.

작업 폴더: C:/Users/zpfh1/Projects/transition-models-exhibit-1101 (브랜치 claude/exhibit-host1-1101, origin에 push됨). 이 폴더에서 작업한다. 다른 worktree·팀원 저장소는 읽기만.
먼저 읽을 것(순서): PLAN.md → CHECKLIST.md 맨 위 절 → docs/CODEX_HANDOFF_EXHIBIT_20261101.md(이 문서) → docs/EXHIBIT_SONG_REQ_PLAN_20261101.md → docs/EXHIBIT_HOST_DEPLOY_STEPS_20261101.md의 "실행 결과"와 "④ 진행" → docs/EXHIBIT_OPERATIONS_20261101.md → ops/public-home/README.md.

현재 공개 상태(11/1 14:34 KST): app.pitcheezy.com = 형 고정 빌드 fba6b2ff가 우리 Worker에서 서비스(접근 코드 ON, 11/21 OFF 예정). www.pitcheezy.com = 새 홈 한 페이지(홈 Worker pitcheezy-home, 영상은 media.pitcheezy.com R2에서 206). pitcheezy.com(apex) = 아직 OpenAI Sites의 옛 홈 — DNS A 레코드는 Proxied이고 홈 Worker에 Route pitcheezy.com/*도 있지만, apex가 OpenAI Sites의 Cloudflare for SaaS custom hostname이라 우리 Worker가 돌지 않는다(O2O는 Proxied CNAME일 때만). 비공개 값(시험 호스트명·Worker·버킷·DB·버전 ID·코드)은 D:/pitcheezy_exhibit_check/host-1101/deploy-private-notes.json과 사용자 비공개 폴더에만 있다. 채팅·문서·이슈에 옮기지 않는다.

규칙: 팀원 저장소·프로세스·배포는 읽기만. 형 빌드 바이트 불변. 비밀값·시험 호스트명·버킷/DB·계정은 Git·이슈·CHECKLIST에 쓰지 않는다(버전 ID·SHA·pass/fail만; pitcheezy.com/app./www./media.는 공개 호스트명이라 써도 됨). 실제 배포·DNS·Sites·형에게 발신·PR 병합/닫기는 사용자에게 적용 범위와 되돌리기를 설명하고 승인받은 뒤에만. Wrangler는 ops/public-host-tooling의 고정 4.151.0만(npx wrangler 금지), 설정 파일에 routes 금지(검사기가 거부), 도메인은 대시보드 Route로만, 와일드카드 Route 금지. 존 pitcheezy.com의 Web Analytics 자동 설치는 Disable 유지. Cloudflare 로그인·secret put은 사용자가 직접(로그인 승인은 2분 안). 기존 파일·worktree·PR·연구 삭제 금지. CV·추가 경기 개발 없음. 11/20 동결. 운영 코드를 바꾸면 다른 모델이 검토한다. 한 파일 한 수정자, CHECKLIST는 작업과 같은 커밋에 갱신, 각 단위 시작 전 CHECKLIST에 합격 기준을 적고 선점한다.

해야 할 단위(권장 순서): (1) apex 전환 마무리 — 사용자 승인 뒤 (c) 방식: 사용자가 OpenAI Sites에서 pitcheezy.com 도메인 연결을 해제하면 우리 존이 받는다. 확인: https://pitcheezy.com/ 200 + x-frame-options DENY + 본문에 media.pitcheezy.com 영상 주소와 app.pitcheezy.com/?game=849843 링크, cloudflareinsights 없음; http→https; media Range 206; app 401 X-Pitcheezy-Access; 폰 QR 흐름. 복구안: Sites 도메인 재연결·검증/TLS 활성 확인 뒤 홈 Worker의 정확한 apex Route pitcheezy.com/*만 해제. 재검증·전파 시간은 미측정이며 즉시 복구를 보장하지 않는다. 앱 Worker의 과거 버전 롤백은 하지 않는다. 대안 (b): OpenAI가 준 CNAME 대상으로 apex를 Proxied CNAME. 끝나면 CHECKLIST 공개 버전 줄·EXHIBIT-host1 갱신. (2) #38 회신 — docs/mail_drafts/EXHIBIT-song-reply-20261101.md "## 회신" 절을 사용자에게 보여 주고 "보내" 뒤 gh issue comment로 SongRoute/pitcheezy#38에 게시(apex가 끝났으면 "옮기는 중"→"옮겼어"). 시험 호스트명·코드 금지. 발신 뒤 사용자가 접속 코드를 비공개로 형에게 전달. (3) 열린 PR 정리 — docs/EXHIBIT_SONG_REQ_PLAN_20261101.md (4)절 분류대로 건별 승인 후 병합 5·닫기 16, 이 브랜치의 PR 생성·다른 모델 검토·병합, 병합 뒤 CHECKLIST 공개 버전 줄 갱신. (4) 안내 문구 코드 변경 — ops/public-host/notice.mjs NOTICE_MESSAGES.maintenance를 "잠시 자료를 확인하고 있어요. 곧 다시 보여 드릴게요."로, 안내 HTML의 개발용 설명 제거, 테스트 갱신, 다른 모델 검토, scripts/build_public_host_release.py 새 후보·설정 검사·배포(버전 ID 기록)·안내 ON/OFF 재확인(D:/…/trial-host/notice-run.ps1 참고, 경로 수정 필요). 11/20 전. (5) ③ 꼬리 — 8단계 비식별 로그 영수증, 폰 경기 화면(?game=849843) 확인 기록. (6) 형이 review/PROMPT.md를 주면 형 빌드 교차검토. (7) 11/11 공동시험 지원·요청량 확인. (8) 클립팩 v4 비공개 클라우드 링크 전달(사용자 업로드)·모니터 2 리허설(11/21~23, 이 Windows 노트북). (9) 전시 뒤 Sites 정리.

하지 말 것: 비밀 조회·출력, 접근 코드/토큰 교체 이전 버전으로 롤백, 형 저장소 변경, Web Analytics 재활성화, 와일드카드 Route, 설정 파일 routes, 새 기능·새 경기 추가, 시험 호스트명을 이슈·문서에 적기.

시작하면 실제 pwd·git status·git log -1을 확인하고(미커밋 변경이 있으면 보고만), 위 문서를 읽은 뒤 첫 단위(apex 전환)의 합격 기준과 사용자가 해야 할 클릭(OpenAI Sites 도메인 해제)을 한 번에 설명하고 승인을 받아라.
~~~
