# Claude 전시 인계 검토 — 2026-11-01 · Codex

검토 기준: `claude/exhibit-host1-1101`의 `8db9a25dbec12188a627c8000c2503d2b691c144`. 지정 폴더와 origin 추적 커밋이 일치하고 시작 시 미커밋 변경이 없었다. 현재 상태는 CHECKLIST 상단을 따른다.

## 방향 판정

사용자가 채택한 [Song 회신 3](https://github.com/SongRoute/pitcheezy/issues/38#issuecomment-6541685530)·[회신 4](https://github.com/SongRoute/pitcheezy/issues/38#issuecomment-6543742838) 및 PLAN의 순서와 맞는다. 관전 본체는 Song 고정 빌드 fba6b2ff, 우리는 홈·호스팅·업로드 수신·영상 261클립과 영상 전용 플레이어를 맡는다. 기존 페이지는 배포 대상에서 제외하고 Git에 보존한다. CV/추가 경기 개발은 재개하지 않는다. 두 모니터 수동 맞춤, 풀 중계 미확보, 클립팩 미발신도 구분한다.

① 인수·② 클립팩·③ 시험 호스트·④ 앱/홈/영상 분리까지 진행했지만 **apex 전환·공동시험·최종 전시 합격은 아직 아니다.** #38의 마지막 회신은 고정 빌드 전달이며, 새로운 전시 요구나 새 빌드는 이번 조회에서 확인되지 않았다. Song 상황판의 새 연구 보고는 전시 빌드 변경으로 취급하지 않는다.

## 확인된 지적과 정정

1. **복구 지시:** 배포 절차가 자격 교체 전 V0와 2·6단계 버전을 가리키면서 동시에 옛 자격 복원을 금지했다. 과거 버전은 이력으로만 남기고 복구 대상으로 금지했다. 실제 앱 복구는 모든 자격 교체 이후 후보·업로드 OFF·현재 관리 상태를 확인해 승인받는다. apex 복구에 앱 Worker 롤백을 끼워 넣지 않는다.
2. **활성 버전:** CHECKLIST의 `42e265fd…`는 후속 안내 토큰 교체보다 앞선 값이었다. 원본 배포 영수증의 마지막 관리 조회 버전 `feed4fc1-949d-4672-98fb-35f4ab00fdc3`로 정정하되, 이번 관리 API 재조회는 하지 않았다고 표시했다.
3. **검증 주장:** 미발신 회신의 “폰에서 4초 안에 복원”을 삭제했다. 로컬 Chrome 3~4초, 실제 폰 안내 ON 사용자 확인, 실제 OFF 뒤 인증 없는 요청의 401 복귀는 서로 다른 증거다. 실제 폰의 추천 복원 지연은 미측정이다.
4. **영상 검사:** 이미 200 전체 응답으로 판정했던 홈의 옛 `/media` 경로를 재검사하도록 한 지시를 실제 media 호스트 주소로 바꿨다.
5. **운영 범위:** 공개 앱을 모니터1로 쓰면서도 호스트 장애와 무관하게 계속 돈다는 단정을 수정했다. Song 로컬 재생을 준비한 경우에만 독립 운영 가능하다. iPhone 확인 보고와 지정 경기 849843/QR 전체 동선 완료도 구분했다.
6. **이전 상태 중복:** 미완료 app 연결·홈 미배포·11/4까지 대기·이미 정해진 문구/PC를 다시 묻는 내용을 정리했다. 과거 영수증과 Git 이력은 변경하지 않았다. 발신 초안은 여전히 미발신이다.

## 독립 확인한 근거

- 우리 코드/문서 읽기 검토를 두 에이전트가 병행했고 root가 지적 근거를 대조했다. 같은 모델 보조 검토를 “다른 모델” 검토로 세지 않는다. 이번에 운영 코드는 수정하지 않았다.
- 관련 작업 파일 14개의 Git blob 일치, JS 구문 5개 및 import 검사 2개는 하위 에이전트 실행 결과다. 홈 HTML/JS/설정에서 전환을 막는 코드 결함은 발견하지 못했다.
- 저장 원격 영수증 두 개의 SHA와 35/35 결과, 28파일 크기·해시가 인수 기록과 일치한다. **35/35는 HTTP 읽기 검사이며 브라우저 렌더링·안내 복원·저장 로그 대조까지 뜻하지 않는다.** 이번에 인증 검사를 재실행하지 않았다.
- 클립팩 v4 전체 파일을 이번에 직접 SHA-256으로 재검사했다. `32f4377e9cf4e003efa54f49f7584ca2eb72eb362edd8e32c77e7f9a2d526f1c`로 전달 기록과 일치한다. 이번에는 재압축·새 클립 판독·261개 재생을 하지 않았다.
- 원본 `host-deploy-20261101.json`·`host-remote-verify-*.json`은 보존한다. Claude/Opus 검토와 iPhone 실기기 확인은 원 기록/사용자 보고로 인용하며 이번 직접 실행으로 쓰지 않는다.

## 현재 공개 응답 — 이번 직접 조회

인증 없는 유한 조회 총 9회. 첫 기본 Python 클라이언트의 HTTPS 4건은 403, HTTP 1건은 HTTPS로 302였다. 같은 공개 URL 4개를 일반 브라우저 User-Agent로 조회해 아래를 확인했다. 이 차이를 서비스 전체 장애 또는 보안 예외 승인으로 해석하지 않는다.

- apex: 200, 11,657bytes. 새 홈과 불일치, media/app 링크 없음. 기존 Sites 연결 목록에서도 apex 연결 active를 확인했다.
- www: 200, 6,133bytes, SHA `8fce362e133ee737b341b6ad4c436ebc3c82f2054588f28c2bc5cc237446c883`. 로컬 홈 HTML과 바이트 일치, DENY/nosniff, media/app 링크 있음, cloudflareinsights 없음.
- app의 `/v1/manifest.json`: 401 + `X-Pitcheezy-Access: required`. 접속 코드·쿠키는 사용하지 않았다.
- media MP4: `Range: bytes=0-1` → 206, `Content-Range: bytes 0-1/11571137`.

조회는 Python urllib GET, 제한된 본문 읽기와 헤더 허용목록 출력으로 수행했다. 비밀·계정·시험 호스트·버킷·DB·쿠키·DNS 검증값은 이 기록에 포함하지 않는다. 이번 새 브라우저/실기기/QR 검사는 미실행이다.

## 다음 단위 — apex 전환 (승인 대기)

Cloudflare 공식 [O2O 설명](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/saas-customers/how-it-works/)은 proxied CNAME 기반이며 SaaS apex A 레코드에는 적용되지 않는다고 명시한다. 실제 Sites의 활성 apex 연결과 공개 응답은 Claude의 원인 설명에 부합한다. 현재 Chrome의 Cloudflare 탭은 로그인 화면이다. 사용자 로그인 완료를 요청했고 DNS/Route 관리 설정은 아직 재조회하지 못했으므로, 실행 직전에 정확한 apex Route 대상·Proxied·TLS 상태를 확인한다.

변경안은 **기존 Sites 사이트/배포를 보존하고 pitcheezy.com 도메인 연결만 해제**하는 것이다. 앱의 자격·업로드·자료·영상·비용 설정은 이 전환 대상이 아니다. 합격은 apex 200·새 홈 바이트/보안 헤더·app/media 링크·비콘 없음, HTTP→HTTPS, media 206, app 접근 문 401, 지정 경기/폰 QR 동선으로 나누어 기록한다.

복구안은 Sites 도메인 재연결·검증/TLS 활성 확인 후 홈의 정확한 apex Route만 해제하는 것이다. 재검증·전파가 필요할 수 있어 즉시 복구를 보장하지 않는다. 실패 시 새 변경을 연쇄 실행하지 않고 www 홈/app 유지 상태를 알리고 복구 승인을 따른다. 대안 CNAME 변경은 별도 승인이 필요하다.

이번 작업에서 Cloudflare·DNS·Sites·형 저장소·이슈·PR 변경과 발신은 하지 않았다. 확인된 로컬 문서 정정만 수행했다.

## 문서 정정 검증

`python -B -m pytest tests/test_checklist_model.py -q -p no:cacheprovider`: 8 passed. `git diff --check` 통과. 변경 문서 10개에서 기준 커밋 대비 새로 생긴 상대 링크 오류 0. 과거 CHECKLIST의 기존 비정상 링크는 이번 범위에서 보존했다. 읽기 전용 보조 검토의 최종 delta 판정 PASS; 운영 코드 변경·새 배포·사용자 기기 검사로 확대하지 않는다.

## apex 전환 사전 실측 — 2026-11-01 17:04 KST

사용자가 전환을 승인했고, 연결 규칙·HTTPS 확인 뒤 Sites 도메인 연결은 직접 해제하기로 했다. 기준 HEAD `3bedef222cf1ff5ad8911d7e12376b68a75f8da8`, 시작 트리 clean. 이번 조회에서는 로그인된 채팅 내 브라우저의 대시보드를 사용했다. 앞 절의 로그인/승인 대기는 당시 상태다.

- Workers Routes: `pitcheezy.com/*` 및 `www.pitcheezy.com/*`가 홈 Worker를 가리킨다. `*.pitcheezy.com/*`는 없다. 앱 Route는 별도로 유지되어 있다.
- DNS: apex A 두 레코드와 www 레코드가 Proxied다. 값을 변경하지 않았다.
- Edge Certificates: `pitcheezy.com`과 `*.pitcheezy.com`을 포함한 Universal 인증서 Active, 만료 표시 2027-01-03. TLS 1.3 ON. **Always Use HTTPS OFF**를 확인했다.
- Sites 연결 목록: apex custom domain active·SSL active. 사이트/버전 21을 보존한다.
- 인증 없는 유한 HTTP 조회 5회(urllib, 브라우저 User-Agent, 리다이렉트 자동 추적 안 함): `http://www.pitcheezy.com/` 200, 이동 없음; `http://pitcheezy.com/` 302→HTTPS; `https://www.pitcheezy.com/` 200·6133bytes·기존 새 홈 SHA 일치·DENY·app/media 링크 있음·비콘 없음; 앱 manifest401+접근문 required; media Range206(`bytes 0-1/11571137`).

**판정:** 라우트와 인증서는 준비됐으나, 기존 apex의 HTTPS 리다이렉트는 Sites 동작일 수 있다. 새 www 호스트의 HTTP 200은 HTTPS 강제 이동이 아직 없다는 직접 근거다. Sites를 해제하기 전에 우리 존의 HTTPS 이동을 보완한다. 도메인 전체 Always Use HTTPS를 ON으로 하면 app/media를 포함한 같은 존의 HTTP 요청도 HTTPS로 이동하므로, 이 추가 설정 범위를 설명하고 승인을 받는다. 접근 코드/업로드/요금/인증서는 변경 대상이 아니다. 승인 전 설정 변경·Sites 해제는 미실행이다.

설정 적용 뒤 HTTP→HTTPS와 HTTPS 정상 응답을 확인하고 사용자에게 Sites 연결만 해제하도록 안내한다. 최종 새 apex SHA 및 보안 헤더까지 확인하기 전 전환 완료로 기록하지 않는다. 보조 에이전트의 읽기 검토도 우리 존 인증서/HTTPS 이동 확인과 기존 복구안 유지를 지지했다. 같은 모델 추가 검토이며 코드 변경은 없다.

기록 검사: diff 공백 검사 통과. 체크리스트 검사 첫 실행 8 passed/Windows 자식 프로세스 디코딩 경고 1; `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`로 재실행 8 passed(경고 없음). 동작 코드 수정 없음.

## HTTPS 보완 적용 — 2026-11-01 17:09 KST

사용자가 `HTTPS 자동 전환 ON 승인`으로 도메인 전체 HTTP 이동 설정을 승인했다. 로그인된 Cloudflare의 `Always Use HTTPS` 한 항목만 OFF→ON으로 바꾸고, 스위치 ON과 저장 시각 표시를 확인했다. DNS·인증서·앱 자격·업로드·요금·Sites 연결은 변경하지 않았다.

인증 없는 GET 7회(08:09:10~11 UTC, 자동 리다이렉트 미추적):

- HTTP www/app/media → 각 301, 같은 경로의 HTTPS Location.
- HTTP apex →302 HTTPS(아직 기존 Sites 경로; 새 홈 전환 합격 근거가 아님).
- HTTPS www →200, 6133bytes, SHA `8fce362e133ee737b341b6ad4c436ebc3c82f2054588f28c2bc5cc237446c883`, DENY, app/media 링크 있음·비콘 없음.
- HTTPS 앱 manifest →401, `X-Pitcheezy-Access: required`.
- HTTPS media `Range: bytes=0-1` →206, `Content-Range: bytes 0-1/11571137`.

사용자가 직접 Sites의 **pitcheezy.com 연결만 해제**하는 단계로 인계했다. 사이트·배포·DNS 삭제가 아니다. 해제 후 apex 본문 SHA까지 대조하기 전 전체 전환 완료로 기록하지 않는다. 변경 화면은 Git 밖의 로컬 캡처로 남겼으며 관리 API 감사 로그를 확보했다는 뜻은 아니다. 문제가 확인되면 이번 HTTPS 스위치를 원래 OFF로 되돌리는 범위이며, 앱의 과거 버전 롤백은 금지한다.

## apex 전환 완료 — 2026-11-01 17:22 KST

사용자가 맞춤 도메인 연결만 해제했다고 알렸다. Sites 연결 목록 실제 조회는 `items: []`였으며 추가 삭제 도구는 실행하지 않았다. 기존 사이트 자체와 배포 버전은 보존했다. 이 단위에서 DNS·Route·앱 설정·업로드·인증 자격을 바꾸지 않았다.

인증 없는 GET 11회(08:22:09.959~12.921 UTC, urllib 브라우저 User-Agent, 자동 리다이렉트 미추적):

- apex와 www: 200, 각각 6,133bytes. SHA-256 `8fce362e133ee737b341b6ad4c436ebc3c82f2054588f28c2bc5cc237446c883`, 로컬 `web/pitch-studio-home/index.html` 원본 바이트와 일치. 홈 HTML 마지막 변경 커밋 `986c6203f0820e0cb97ab9aa1b17181142e38206`.
- 두 홈 모두 `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, 앱 지정 경기 링크와 media 영상 링크 있음, `cloudflareinsights` 없음.
- HTTP apex: 301 → 같은 주소 HTTPS.
- 앱 `/?game=849843`와 `/v1/manifest.json`: 모두 401, `X-Pitcheezy-Access: required`, `Cache-Control: no-store`. 접근 제한은 유지됐다. 인증 후 자료 바이트 검사는 Claude의 앞선 35/35 기록과 구별하며 이번에 반복하지 않았다.
- media의 `Range: bytes=0-1`: 206, 실제 읽기2bytes, `Content-Range: bytes 0-1/11571137`, video/mp4.
- 사용 보류한 watch.html·receiver.html·games.html·guide.html·report.html: 각404. 저장소의 원본 코드·연구·Sites 기존 배포 삭제를 뜻하지 않는다.

별도 실제 브라우저에서 새 apex를 열었다. 제목·홈 한 페이지·서비스 링크를 확인했고, 영상은 media 주소, readyState4, paused=false, currentTime3.8782초/전체23.833333초, 오류 없음이었다. 화면 캡처는 Git 밖에 보존했다. 이는 PC 브라우저 확인이며 실제 폰 QR 전체 동선·261클립 전체 재생·두 모니터 자동 동기화·관리 API 감사 로그 확보를 의미하지 않는다.

**판정:** apex의 새 홈 전환은 완료. 다음은 정정한 #38 초안의 발신 결정, 안내 문구 로컬 수정·검토, 잔여 로그 영수증·폰 QR 확인, PR 정리다. 형 저장소는 변경하지 않고 새 메시지도 발신하지 않았다. 같은 날 양쪽 board/mail 조회는 성공했고 새 운영 빌드 전달은 없었다. 우리 board 기록은 뒤처져 있어 [착수 댓글](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6555496140)로 현 단위를 추적했다(연결 도구 댓글쓰기403 뒤 인증된 gh로 성공).

## 다음 로컬 단위 — EXHIBIT-notice-copy1

11/1 채택한 maintenance 문구를 `잠시 자료를 확인하고 있어요. 곧 다시 보여 드릴게요.`로 반영하고 공통 HTML의 개발용 설명을 제거했다. 메시지 ID·JSON 구조·HTTP 상태/헤더·인증·캐시·스위치 처리 로직은 변경하지 않았다. `data_hold` 별도 문구는 아직 승인 전 초안이므로 변경하지 않았고 이번 배포 대상 안내 운영은 maintenance 기준이다. 운영 코드 원본은 Codex 작성, 제품 커밋 `0885a5a7836b08e14e5ac01a37ce0725223e9300`. 실제 서버에는 배포하지 않았다.

검사:

- `node --test --test-reporter=spec tests/notice.test.mjs tests/access.test.mjs tests/notice-client.test.mjs tests/notice-cli.test.mjs tests/publish-scope.test.mjs` (`ops/public-host`): 53 passed. 로컬 workerd의 Windows 연결 종료 진단(WSARecv #64) 한 건이 출력됐지만 테스트 실패는0·종료0이었다. 운영 서버 오류로 해석하지 않는다.
- `BROWSER_CHANNEL=chrome node --test --test-reporter=spec public-host-notice.test.cjs` (`tests/browser`): 2 passed. 열린 합성 화면→안내→뒤로/앞으로→복원, 직접 HTML/JSON/HEAD, 작은 화면 폭·스크립트 없음·자격 비노출을 확인했다. 최초 실행은 이 작업 폴더의 Playwright 미설치로 실패했고, 기존 lockfile에 맞춰 `npm ci --ignore-scripts --no-audit --no-fund` 후 설치된 Chrome에서 통과했다.
- `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 python -B -m pytest tests/test_checklist_model.py -q -p no:cacheprovider`: 8 passed. `git diff --check` 통과.

시험은 모두 로컬 합성 자료이며 실제 Cloudflare 안내 ON/OFF 재실행이 아니다. 코드 검토·후보 구성 뒤 실제 배포에는 적용 범위·복구 설명과 사용자 승인이 필요하다. #38 초안은 미발신이며 PR 병합/닫기, 앱 공개 확대, 새 경기/CV는 수행하지 않았다.

### 고정 검토와 오프라인 후보 완료

다른 모델 `gpt-6.1-terra`가 기준 `e8efc7f4de44614b0bdf7d8456dc651e605ecdce`부터 제품 `0885a5a`까지 읽기 검토했다. 운영 코드 회귀는 발견하지 못했고, CHECKLIST와 인계 문서에 과거 apex 대기 문구가 현재 지시처럼 남은 P2를 제기했다. 문서 수정 `c47643ace740d45898300b1f9f0d6e4184d8bd82`를 재검토해 APPROVE. 검토자는 실제 Cloudflare 배포/로그를 독립 실행한 것이 아니다.

`scripts/build_public_host_release.py build --mode candidate --host-commit c47643ace740d45898300b1f9f0d6e4184d8bd82 --frontend <기존 비공개 정적4파일 폴더> --provenance <기존 메타데이터 JSON> --output <새 후보 폴더>`와 `check <후보 폴더>/release.zip`을 실행했다. 원본·기존 후보를 덮어쓰지 않았다.

- ZIP `release.zip`: 실제 파일 **535,003bytes**, SHA-256 `01b486601d5d5beb80806e555f0d5e41902ee0877caf5681fab9c8f40c5815ff`.
- payload 16파일 **529,534bytes**, manifest 포함 ZIP 항목17개. payload 합과 압축 파일 크기를 구분한다.
- manifest SHA-256 `2f3cc83d1f88e370146d83a2e283d9cf970c1a9bbf633e2d33e0bce4dea25a5c`.
- 형 고정 빌드 `fba6b2ff846dcfa9afad9ea5df4204007e0604c1`의 정적4파일은 받은 원본과 바이트/SHA 모두 일치. `index.html` SHA `248860bda9fd9bc780ee9ab1598ccab58bbc9cff000c17ec5a31b22efe8d6c67`.
- 기존 배포 소스 `f50020b` 대비 host payload 차이는 `notice.mjs`와 `package.json` 두 개다. 후자는 기존 Claude 작업의 `scripts.check`에 전시 도구4개의 구문 검사 명령을 더한 것으로 이번 변경이 아니다. 의존성·버전·실행 진입점 변경은 없다. 같은 다른 모델이 이 추가 baseline 대조도 읽기 확인해 APPROVE했으며 배포 검증/승인을 뜻하지 않는다.
- **deployable=false**: 오프라인 바이트/manifest 검사만 통과했다. 실제 설정 채움·설정 검사·dry-run·배포 승인·원격 안내 재검사는 남는다. 기존 서버 설정과 자격을 조회/복사하거나 옛 자격 버전으로 롤백하지 않았다.

다음 작업자는 CHECKLIST 상단부터 읽는다. 이 후보는 서버에 반영된 버전이 아니므로 공개 버전 한 줄을 후보 커밋으로 바꾸지 않는다. 미발신 #38 회신은 사용자 발신 결정 후, 실제 안내 배포는 적용 범위·복구 설명 후에 각각 진행한다.

최종 기록 갱신 뒤 체크리스트8검사와 diff 공백 검사를 통과했다. 제품 코드는 고정 검토 이후 변경하지 않았다. 후보는 Git 밖 `D:/pitcheezy_exhibit_check/notice-copy-20261101/release.zip`에 보존했다. 이 로컬 경로에는 자격이 없으며 실제 배포용 설정/비밀은 포함하지 않는다.
