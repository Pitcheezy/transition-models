# 시험 호스트 ③ 실행 순서 — 운영자 명령 (2026-11-01 실행, 결과 포함)

[실행 전 설명](EXHIBIT_HOST_PLAN_20261101.md)의 ③을 **실제로 돌릴 때** 치는 명령이다. **2026-11-01 실행 완료 — 결과와 발견은 아래 "실행 결과" 절.** 명령은 ④ 뒤 재검사·되돌리기용으로 그대로 둔다.
전제: 사용자 결정(올릴 자료 24개 전부, 시험 단계 접근 코드 ON 유지)과 Cloudflare 로그인. 〔사용자만〕 표시는 Claude/Codex가 대신하지 않는 단계다(비밀·토큰·코드를 다루는 3·5·7단계 포함).
명령은 저장소 루트의 **Windows PowerShell 5.1** 기준이다(`&&` 없음, 순차 실행은 `;`). `<후보>`·`<비공개>`·`<site>`·`<receipt>`는 Git 밖 로컬 경로다.
`<시험호스트>`는 기존 시험 Worker에 이미 붙어 있는 시험용 하위 도메인의 https 출처이며 **이 문서 ③의 모든 명령(2·5·7단계)이 쓰는 대상**이다. `<앱호스트>`는 ④에서 정하는 공개 하위 도메인의 https 출처로 ④ 뒤에만 쓴다(7단계 재실행). 비밀값·버킷/DB 이름·출처는 문서·이슈·CHECKLIST에 쓰지 않는다.

## 실행 결과 — 2026-11-01 (KST 낮)

사용자가 로그인·비밀 등록·대시보드 변경을, Claude가 조회·설정 채움·배포·계획 생성·검사 실행을 맡았다. 호스트명·계정·버킷/DB·Worker 이름·코드·토큰은 적지 않는다.
비식별 기록 [host-deploy-20261101.json](results/exhibition_20261101/host-deploy-20261101.json), 검사 영수증 [host-remote-verify-20261101.json](results/exhibition_20261101/host-remote-verify-20261101.json).

| 단계 | 결과 | Worker 버전 |
|---|---|---|
| 1 | `whoami`·R2 1개·D1 1개 조회, 후보 4값 채움(세션 3600 = 기존 배포값 유지), 설정 검사 ok, 격리 프로필 dry-run 통과·원본 후보 불변 | V0(되돌리기 기준) `207c638d-5040-4ec3-ad92-0e2525f0272c` — 10/26 공동 합성 시험 뒤 상태(10/25 기록보다 뒤) |
| 2 | 배포(자료 읽기 ON·업로드 OFF·접근 ON). `/`·`/v1/*`·정적 모두 401 + `X-Pitcheezy-Access: required`·no-store | `46cf3edc-53a2-440f-b7ec-3baaae802e89` |
| 3 | 토큰 helper(파일 ACL 본인만) → 사용자 `secret put PUBLISH_TOKEN_SHA256` | `913b7f12-a7ac-4beb-a33d-ac8c2c1c0bd7` |
| 4 | `--var UPLOAD_ENABLED:true`. `/_publish` HEAD(토큰 없음) 401 = 창 열림 | `dbe8837c-61a2-4f96-8ee7-53ed6a2d6845` |
| 5a | HEAD 24: 없음 23, `v1/health.json` observed(10/16 합성 기록, ETag 확보) | — |
| 5b | PUT 24/24 `stored`·200·SHA 일치(health는 If-Match로 교체) | — |
| 6 | 덧씌움 없는 배포. `/_publish` 503, 게이트 401 유지. 토큰 파일은 사용자가 삭제(Claude가 `Test-Path`로 부재 확인) | `d4d707d7-47ec-4dfa-bc8b-af268bef40bc` |
| 7 | 1차 33/35 — `entry:root_is_index`·`entry:query_game_is_index` 실패(발견 1). 사용자 대시보드 조치 뒤 2차 **35/35**(영수증 SHA `3ebdafab…`) | 접속 코드 교체 `42e265fd-b7f9-4c3a-b569-0aeb9059c81e` |
| ③-6 | 안내 운영자 토큰 교체(helper → 사용자 `secret put NOTICE_TOKEN_SHA256`) → `notice-cli` GET(active false, revision 4) → **ON 12:59:29.6 KST** applied(revision 5, 감사 기록; 공개 manifest 503 + `X-Pitcheezy-Notice: maintenance` 12:59:59; iPhone Safari에 개발용 안내 문구 표시) → **OFF 13:03:52.9** applied(revision 6; 13:04:15 공개 manifest 401 게이트로 복귀) | 안내 토큰 digest `feed4fc1-949d-4672-98fb-35f4ab00fdc3`(현재 활성) |

발견·문서와 달랐던 점:

1. **Cloudflare Web Analytics 자동 설치가 HTML에 비콘을 끼워 넣었다.** 존 `pitcheezy.com`의 Web Analytics 사이트(한 달 전 생성, Automatic setup)가 하위 호스트의 `/`·`/?game=` 응답에 `static.cloudflareinsights.com/beacon.min.js`를 주입해 659→1026바이트가 됐다(`/index.html`은 307→`/`, 정적 JS/CSS·JSON은 무관). 홈 apex 응답에는 없었다. 사용자가 **Analytics & Logs → Web Analytics → `pitcheezy.com` Manage site → Disable → Update**로 끈 뒤 바이트 일치. ④ 홈 전환 뒤에도 이 설정이 Disable인지 다시 본다. 자료(`/v1`) 응답은 `no-store, no-transform`이지만 HTML·정적 응답은 `private, max-age=0`뿐이라 HTML은 지금 이 설정에만 의존한다.
2. **접속 코드 원문이 없었다.** 저장소·문서에는 digest만 있고 사용자도 보관본이 없어 새 16자 코드를 만들어(파일에만 저장·ACL 본인만·화면에는 digest) `ACCESS_CODE_SHA256`를 단일 digest로 교체했다. 옛 코드로 연 세션은 설계상(코드 태그 불일치) 무효가 된다 — 별도로 관측하지는 않았다. **안내 운영자 토큰(`NOTICE_TOKEN_SHA256`)도 같은 상태**라 같은 방식으로 교체한 뒤 ③-6(안내 ON/OFF)을 돌렸다. 두 원문 파일은 사용자 비공개 폴더에만 있다(전시 당일 안내 전환에 필요).
3. `wrangler login`은 승인 코드를 약 2분만 기다린다(첫 시도는 시간 초과 → 재실행). 저장소 루트가 아닌 상위 폴더에서 치면 상대 경로가 깨져 절대 경로로 안내했다.
4. `secret put`은 대화형 프롬프트 대신 PowerShell 파이프 `"<digest>" | node … secret put NAME --config …`로 넣었다(digest만, 토큰 원문 아님). Claude의 터미널 실행은 비밀 등록으로 차단되어 사용자가 직접 쳤다.
5. PowerShell 5.1에서 `--if-match 'v1/health.json=\"<etag>\"'`처럼 **`\"` 이스케이프**가 필요하다(그냥 `"`는 node에 닿기 전에 벗겨진다). 생성된 계획의 `condition.if_match`가 따옴표 포함 ETag인지 확인한 뒤 실행했다.
6. 5a·5b·7단계는 비공개 폴더의 `.ps1`(토큰·코드를 파일에서 읽고 `finally`로 환경 변수 제거)로 돌렸다. 영수증·계획·메모 원본은 Git 밖에 보관한다.
7. 2·4·6단계 뒤 `<후보>/host/.wrangler`를 지우고 설정 검사를 다시 통과시켰다(설정 SHA `eed14187…` 불변).

남은 ③ 꼬리: 8단계 비식별 로그 영수증(사용자가 보낸 대시보드 Observability 캡처에 요청 목록이 보였을 뿐 영수증은 미작성), 폰에서 경기 화면(`?game=849843`) 직접 확인(iPhone Safari 로그인·날짜 목록·안내 화면·다른 경기 화면은 확인됨), 형에게 주소·코드 비공개 전달.

## ④ 진행 — 2026-11-01 오후

| 단계 | 결과 |
|---|---|
| ④-a 앱 주소 | 대시보드의 Worker "Add Domain(custom domain)" 창이 하위 호스트명으로 존을 찾지 못해(새 존 등록·도메인 구매 흐름으로 빠짐) **DNS AAAA `app` → `100::` Proxied + Worker Route `app.pitcheezy.com/*`(fail closed)**로 연결했다. 설정 파일 `routes`는 설정 검사기가 `unsupported_or_missing_fields`로 거부하므로 도메인은 대시보드에서만 관리한다. 연결 뒤 `/`·`/v1/manifest.json`·정적 401 + `X-Pitcheezy-Access`. 검사기 **35/35**([영수증](results/exhibition_20261101/host-remote-verify-app-20261101.json), SHA `3853eaee…`). iPhone LTE: 접속 코드 → 경기 화면·추천·존 표시. 이 PC의 리졸버가 새 이름을 NXDOMAIN으로 부정 캐시해 검사기는 `dns.lookup`을 엣지 IP로 고정하는 검사 전용 preload로 돌렸다(운영 코드 아님). |
| ④-b 홈 Worker | `ops/public-home/wrangler.jsonc`로 `pitcheezy-home` 배포(정적 9파일, 도메인 없음) → 임시 호스트(AAAA `100::` + Route)에서 홈 200, `_headers` 적용(nosniff·DENY·referrer), 비콘 없음, "서비스 열기" 링크, `/nope` 404. 임시 라우트를 처음엔 앱 Worker에 붙이는 실수가 있었고 옮겼다. |
| ④-b 영상 | **Workers 정적 호스트는 Range 요청에 206이 아니라 200 전체(11.5MB)로 답하고 `Accept-Ranges`가 없다**(캐시 HIT에도 동일) → iPhone Safari 재생 불가 구조. 사용자 결정 A안: 전용 R2 버킷을 만들어 영상·포스터 2파일을 immutable 캐시로 올리고 R2 custom domain **`media.pitcheezy.com`**(TLS 최소 1.2, r2.dev 비활성)을 붙였다(초기화 중 약 10분간 403 `error code: 1014`). 이후 Range **206**·`Content-Range`·SHA 로컬 일치. `web/pitch-studio-home/index.html`의 `<source src>`만 media 호스트로 바꿔 재배포(`a4fe3d3f…`), 임시 호스트 HTML이 media 주소를 가리키는 것 확인, **iPhone Safari 영상 재생 확인(사용자)**. 포스터·정지 이미지·팀 로고는 정적 호스트에 그대로. |
| ④-b apex (1차 시도, 미완) | 사용자가 `pitcheezy.com` A 레코드 2개를 Proxied로 바꾸고 홈 Worker에 Route `pitcheezy.com/*`·`www.pitcheezy.com/*`(+ `www` AAAA `100::`)를 추가했다. **결과: `www`는 새 홈, apex는 여전히 OpenAI Sites 옛 홈**(CF-Cache HIT, OpenAI 존의 `__cf_bm` 쿠키, Worker 헤더 없음). 원인: apex가 OpenAI Sites의 **Cloudflare for SaaS custom hostname**(`_cf-custom-hostname` TXT)이라 Cloudflare가 SaaS 존 설정을 적용하고, 우리 존이 먼저 도는 O2O는 "SaaS 대상으로 가는 Proxied CNAME"일 때만 켜진다(A 레코드 Proxied는 해당 없음). 함께 들어간 와일드카드 Route(`*.pitcheezy.com/*`, `*home-test…`)가 `media.pitcheezy.com`까지 가로채 404를 냈고 삭제 뒤 복구(206). 현재 상태는 방문자에게 옛 홈이 정상 표시되는 상태라 되돌리지 않고 두었다. **마무리는 Codex 인계**: (c) 사용자가 OpenAI Sites에서 도메인 연결 해제 → 우리 존이 받음(되돌리기 = Sites 재연결 + Route 삭제), 또는 (b) OpenAI의 CNAME 대상이 있으면 apex를 Proxied CNAME으로. 전환 뒤 Web Analytics 자동 설치 Disable 재확인. |

## 0. 로컬에서 끝난 것 (2026-11-01)

| 항목 | 결과 |
|---|---|
| 배포 후보 ZIP | `scripts/build_public_host_release.py build --mode candidate`, host 커밋 `f50020b8aacf3bdd2ff47da80651b1d594c13098` + 형 정적 4파일(`fba6b2ff`). 16파일, ZIP SHA `790f3b8804bf00ade655d2c78935d212a2062171474cb985600ff1a847a6f537`(535,008바이트). `check` 통과. [영수증](results/exhibition_20261101/host-release-candidate.json) |
| 후보 폴더 | ZIP을 새 폴더에 풀고 `host/wrangler.deploy.json`·`public/collection-settings.json` 추가. 예제 대비 변경: `assets.directory ../public`, `DATA_READ_ENABLED true`, `UPLOAD_ENABLED false`, `ACCESS_GATE_ENABLED true`, **observability 명시**(Logs 100%·호출 기록·저장 ON, Traces/Issues OFF — 생략하면 고정 Wrangler 4.151.0이 10/25 켠 로그 저장을 꺼 버린다, [CONFIG_CHECK](../ops/public-host/CONFIG_CHECK.md)). |
| 설정 검사 | 자리표시자(`replace-…`) 그대로는 설계대로 `invalid_bucket_name` 거부. 같은 파일에 저장소의 **합성** 식별자를 넣은 구조 검사는 통과(`observability_config` 포함). [기록](results/exhibition_20261101/host-release-config-check.json) |
| 업로드 계획 | `exhibit-upload-plans.mjs`로 24계획+바이트 복사본 생성(자리표시자 출처). 비공개 폴더. 5단계에 쓰는 `--head`(HEAD 계획)·`--if-match`(기존 키 교체 조건)는 합성 빌드 검사만 했다. |
| 원격 검사기 | `verify-exhibit-remote.mjs` 작성, loopback 우리 gateway에 실제 24파일을 올려 35/35. Cloudflare 결과 아님. 세 도구는 `exhibit-site.mjs`만 거치므로 `ops/public-host/node_modules`(Miniflare) 없이도 돈다. |
| Wrangler dry-run | 고정 Wrangler 4.151.0을 로컬 npm 캐시에서 설치(네트워크 없음). 홈 설정(`ops/public-home/wrangler.jsonc`) dry-run: 정적 9파일 읽음·바인딩 없음·통과. 앱 후보(`wrangler.deploy.json`, 자리표시자 그대로) dry-run: 변수 11개 읽음·통과. 둘 다 로그인·업로드 없음. 앱 후보 dry-run은 원본 후보 폴더에서 돌려 `host/.wrangler/tmp`가 생겼고 같은 날 지웠다(설정 검사 재실행: `invalid_bucket_name` 거부 그대로). 다음부터는 1단계 절차(복사본)로만 돌린다. |
| R2 버킷 상태 | WS-stage4(10/16)가 넣은 **합성 22바이트 `v1/health.json`이 버킷에 남아 있다**([기록](results/ops/ws_stage4_20261016.json), `resources_retained`). 10/16 이후 버킷을 다시 조회하지 않았다. 5단계가 HEAD로 확인하고 If-Match로 교체한다. |

자리표시자(11/1에 채움, 값은 Git 밖 후보 폴더에만): Worker `name`(기존 시험 Worker 이름), `r2_buckets[0].bucket_name`, `d1_databases[0].database_name`·`database_id`. `ACCESS_SESSION_SECONDS`는 예제값 43200이었고 기존 배포값 3600으로 바꾼 뒤 재검사했다.

## 1. 후보 설정 채우기와 재검사 〔사용자만: 로그인·이름 조회〕

~~~text
Set-Location ops/public-host-tooling; npm ci --ignore-scripts --no-fund --no-audit; Set-Location ../..   # 고정 Wrangler 4.151.0 (lock), 네트워크
node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js login                                 # 〔사용자만〕 브라우저 OAuth
node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js whoami
node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js r2 bucket list                       # bucket_name
node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js d1 list                              # database_name, database_id
node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js deployments list --name <기존 Worker 이름>   # 현재 활성 버전 ID = V0(되돌리기 기준) 기록
~~~

`<후보>/host/wrangler.deploy.json`의 네 값을 채운다(파일은 Git 밖). 그다음 저장소 루트에서:

~~~text
python -B -S scripts/check_public_host_config.py <후보>          # ok:true, deployable:false 확인. 거부되면 배포하지 않는다
~~~

dry-run은 [고정 CLI README](../ops/public-host-tooling/README.md)의 절차 **그대로**: `<후보>`의 바이트 복사본 `<작업복사본>`을 따로 만들고, 새 빈 프로필 폴더(home/config/cache/temp/appdata/localappdata)와 README 2~4항의 환경 변수만 가진 자식 프로세스에서, **새 빈 env 파일**을 `--env-file`로 명시해 돌린다. 일반 로그인 터미널에서 원본 `<후보>`로 돌리지 않는다 — 4.151.0 dry-run은 `host/.wrangler/tmp`를 만들고, 그러면 설정 검사가 원본을 `invalid_path`로 거부한다.

~~~text
node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js deploy --dry-run --env-file <새빈파일> --config <작업복사본>/host/wrangler.deploy.json --outdir <비공개>/dry-run-app
python -B -S scripts/check_public_host_config.py <후보>          # 원본 재검사: 그대로 통과해야 한다. 복사본의 원래 16파일 SHA도 원본과 대조한다
~~~

다른 Wrangler 버전(`npx wrangler` 포함)은 observability 처리가 달라질 수 있으니 쓰지 않는다.

## 2. 배포 (업로드 OFF 상태) 〔사용자만〕

~~~text
node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js deploy --config <후보>/host/wrangler.deploy.json
~~~

- 출력의 **버전 ID(V2)** 를 기록한다(CHECKLIST 맨 위 줄·#38 기록용. 호스트명·계정은 쓰지 않는다). 2·4·6단계는 `<후보>/host/.wrangler`를 다시 만들 수 있다 — 배포 뒤 지운다.
- 기존 비밀 4개(`ACCESS_CODE_SHA256`, `ACCESS_SESSION_SECRET`, `NOTICE_TOKEN_SHA256`, `PUBLISH_TOKEN_SHA256`)는 배포가 유지한다(Wrangler keepSecrets). 새로 넣지 않는다.
- 현재 재사용할 때 V0로 되돌리지 않는다. V0는 11/1 자격 교체 전의 과거 기록이다. 복구는 9절의 자격 교체 이후 후보 확인·사용자 승인 절차를 따른다.
- 배포 직후 확인(접근 코드 없이, 토큰·코드를 환경에 넣기 전): `<시험호스트>/` → 401 입력 화면, `<시험호스트>/v1/manifest.json` → 401 + `X-Pitcheezy-Access: required`(게이트 ON. manifest는 아직 없다). 이 응답이 우리 gateway임을 확인한 출처만 5·7단계에 쓴다. 대시보드 Settings에서 Logs가 켜져 있는지 본다.
- **버킷에는 WS-stage4 합성 22바이트 `v1/health.json`이 남아 있다.** 이 시점부터 5단계 교체 전까지 접근 코드로 로그인한 사람(우리만)은 `<시험호스트>/v1/health.json`에서 그 합성 파일을 읽는다. 형 앱 자료가 아니다.

## 3. 발행 토큰 〔사용자만〕

~~~text
node ops/public-host/exhibit-token-helper.mjs --out <비공개토큰폴더>/publish-token.txt --config <후보>/host/wrangler.deploy.json
node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js secret put PUBLISH_TOKEN_SHA256 --config <후보>/host/wrangler.deploy.json
~~~

- helper가 찍은 64자 hex를 `secret put` 프롬프트에 붙인다(토큰 원문이 아니다). 기존 digest는 이 순간 교체되어 옛 토큰은 무효가 된다. `secret put`도 새 배포(V3)다.
- **토큰 파일의 비공개성은 폴더·파일 ACL에서 온다**(mode 0600은 Windows에서 무시된다). `<비공개토큰폴더>`는 Projects·`%TEMP%`·Documents·Downloads·Desktop·AppData·exFAT `D:` **밖의 새 폴더**(예: `C:\Users\<사용자>\` 바로 아래 — 상속 ACE가 SYSTEM·Administrators·본인만)이며, 계획·영수증·검사 영수증이 있는 `<비공개>`와 다른 곳이다. helper는 Windows에서 파일 ACL을 현재 사용자(`DOMAIN\USER`)만으로 제한하고(상속 제거) 실패하면 파일을 지우고 `acl_restrict_failed`(종료 2)로 끝낸다.
- 토큰 파일은 **6단계(업로드 OFF) 확인 뒤 지운다.** 9절 회수에 토큰이 다시 필요하면 helper를 다시 실행해 새 토큰·새 digest를 만든다. 접근 코드·안내 토큰은 바꾸지 않는다(형 전달용 새 접근 코드는 별도 결정).

## 4. 업로드 창 열기 (설정) 〔사용자만〕

~~~text
node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js deploy --config <후보>/host/wrangler.deploy.json --var UPLOAD_ENABLED:true
~~~

같은 코드에 변수 하나만 바꾼 새 버전(V4)이다(버전 ID·시각 기록). 설정 검사는 파일만 보므로 이 덧씌움은 검사 범위 밖이며, 6단계에서 덧씌움 없는 배포로 닫는다. HEAD·PUT 모두 이 창이 열려 있어야 한다.

## 5. 자료 24개 업로드 〔사용자만〕

출처는 `<시험호스트>`다. 계획 파일에는 출처가 들어가므로 다른 호스트에 재사용하지 않는다(필요하면 새로 생성). `--out`은 **새 폴더**만 받는다.

**5a. 키 상태 확인(HEAD 계획, 자료 바이트 없음).** 버킷에 남은 합성 `v1/health.json` 때문에 첫 생성 조건(`If-None-Match: *`)만으로는 health가 412가 난다.

~~~text
node ops/public-host/exhibit-upload-plans.mjs --site <site> --receipt <receipt> --out <비공개>/head-plans --origin <시험호스트> --head
Get-ChildItem <비공개>/head-plans/head-*.json | Sort-Object Name | ForEach-Object { node ops/public-host/publisher-cli.mjs --plan $_.FullName }   # 24개 모두 dry_run(토큰 불필요)
New-Item -ItemType Directory -Force <비공개>/upload-receipts | Out-Null
$env:PITCHEEZY_PUBLISH_TOKEN = (Get-Content -Raw "<비공개토큰폴더>/publish-token.txt").Trim()
try {
  Get-ChildItem <비공개>/head-plans/head-*.json | Sort-Object Name | ForEach-Object {
    node ops/public-host/publisher-cli.mjs --plan $_.FullName --execute | Tee-Object -FilePath (Join-Path "<비공개>/upload-receipts" ($_.BaseName + ".json"))
    if ($LASTEXITCODE -ne 0) { throw "stop at $($_.Name)" } }
} finally { Remove-Item Env:PITCHEEZY_PUBLISH_TOKEN -ErrorAction SilentlyContinue }
~~~

- 영수증의 `outcome`: `missing` = 키 없음(23개 예상, 종료 0), `observed` = 키 있음(`v1/health.json` 예상, 종료 0; `etag`·`current_sha256`·`deleted` 기록). health 외 키가 `observed`이거나 `unavailable`(종료 3)·`invalid_response`(종료 1)로 루프가 멈추면 사람이 판단한다.

**5b. PUT 계획 생성과 실행.** `observed`인 키마다 `--if-match '<키>="<HEAD 영수증의 etag 32자리 hex>"'`(따옴표 포함, 반복 가능)를 붙인다. 그 키는 `{"if_match": ETag}`로 기존 기록을 교체하고, 나머지 23개는 첫 생성 조건 그대로다. 생성기는 형식이 틀린 ETag·site에 없는 키·중복 키를 거부한다.

~~~text
node ops/public-host/exhibit-upload-plans.mjs --site <site> --receipt <receipt> --out <비공개>/upload-plans --origin <시험호스트> --if-match 'v1/health.json="<etag>"'
Get-ChildItem <비공개>/upload-plans/plan-*.json | Sort-Object Name | ForEach-Object { node ops/public-host/publisher-cli.mjs --plan $_.FullName }   # 24개 모두 dry_run(토큰 불필요)
$env:PITCHEEZY_PUBLISH_TOKEN = (Get-Content -Raw "<비공개토큰폴더>/publish-token.txt").Trim()
try {
  Get-ChildItem <비공개>/upload-plans/plan-*.json | Sort-Object Name | ForEach-Object {
    node ops/public-host/publisher-cli.mjs --plan $_.FullName --execute | Tee-Object -FilePath (Join-Path "<비공개>/upload-receipts" ($_.BaseName + ".json"))
    if ($LASTEXITCODE -ne 0) { throw "stop at $($_.Name)" } }
} finally { Remove-Item Env:PITCHEEZY_PUBLISH_TOKEN -ErrorAction SilentlyContinue }
~~~

- **plan-01부터 순서대로 하나씩**(setup → game 15개 → games 5개 → dates → manifest → health). 제한 60회/60초 안의 24요청이지만 병렬로 돌리지 않는다. 토큰은 실행 직전에만 파일에서 읽고(helper 출력 2번) `finally`가 변수를 지운다 — 블록이 중간에 멈춰도 지워진다.
- 각 출력의 `outcome`이 `stored`여야 한다. `conflict`(412)는 조건이 맞지 않는다는 뜻(첫 생성 키가 이미 있음, 또는 If-Match 키의 ETag가 HEAD 뒤 바뀜) — 덮어쓰지 말고 5a HEAD 계획으로 현재 ETag·SHA를 다시 보고 사람이 판단한다. `unknown`은 저장됐을 수 있으니 재전송 전에 HEAD로 확인한다. 종료0만 보고 성공으로 읽지 않는다([PUBLISHER](../ops/public-host/PUBLISHER.md)).
- stdout 영수증(HEAD 24 + PUT 24)은 `Tee-Object`가 `<비공개>/upload-receipts/<계획이름>.json`에 남긴다(출처·토큰 없음; PowerShell 5.1의 Tee-Object는 UTF-16으로 저장한다).

## 6. 업로드 OFF 〔사용자만〕

~~~text
node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js deploy --config <후보>/host/wrangler.deploy.json
~~~

덧씌움 없는 배포 = 1단계에서 검사한 설정 그대로(업로드 OFF). 버전 ID(V6) 기록. 이후 `/_publish` PUT은 503이어야 한다. 확인되면 **토큰 파일을 지운다**(3단계).

## 7. 검사 (읽기 전용) 〔사용자만〕

접근 코드는 프롬프트에 직접 치지 않는다(PSReadLine이 입력 줄을 `ConsoleHost_history.txt`에 그대로 저장한다). 코드를 `<비공개토큰폴더>/access-code.txt`(토큰과 같은 ACL 제한 폴더, 손으로 만든 한 줄)에 두고 파일에서 읽는다. 검사기는 앞뒤 공백·CR/LF를 지우고 받는다.

~~~text
$env:PITCHEEZY_ACCESS_CODE = (Get-Content -Raw "<비공개토큰폴더>/access-code.txt").Trim()
try {
  node ops/public-host/verify-exhibit-remote.mjs --origin <시험호스트> --site <site> --receipt <receipt> --out <비공개>/verify-<날짜>.json --notice-check
} finally { Remove-Item Env:PITCHEEZY_ACCESS_CODE -ErrorAction SilentlyContinue }
~~~

- 종료0 = 로그인 1회·자료 24개 바이트 일치·정적 4개·`/`·`/?game=849843`·404 2건·HEAD 통과(35/35). 영수증에는 출처·코드·쿠키가 없으므로 pass/fail 수와 SHA는 CHECKLIST/#38에 옮길 수 있다.
- 브라우저 확인 〔사용자〕: 폰·PC에서 `<시험호스트>/?game=849843` → 접속 코드 → 첫 투구 "실제 투구 · 1구 · Pete Crow-Armstrong".
- 안내 ON→OFF 1회(계획 ③-6): `notice-cli.mjs`를 운영자 토큰(`PITCHEEZY_NOTICE_TOKEN`, 사용자 보관)으로 ON → 앱이 "자료를 확인하고 있어요" → OFF → 복원. 전환 시각 2개 기록. [NOTICE](../ops/public-host/NOTICE.md).
- ④ 뒤에는 같은 7단계(검사기·브라우저)를 `--origin <앱호스트>`로 다시 실행한다.

## 8. 저장 로그 대조 〔사용자만: 대시보드〕

Workers Logs(저장 ON)에서 버전 ID로 거르고 다음을 확인해 10/25 방식의 비식별 영수증(시각·method·path·status·version 5필드)으로 남긴다. 5단계 요청은 4단계 버전(V4 `dbe8837c…`) 아래, 7단계 요청은 **접속 코드 교체 버전(`42e265fd…`)** 아래 있다 — 11/1에는 교체가 7단계보다 먼저였고, 6단계 버전(`d4d707d7…`) 아래에는 `/_publish` 503 확인 1~2건만 있다. 안내 토큰 교체 뒤의 요청(안내 ON/OFF 시험)은 그다음 버전 아래다.

- 5단계(V4) `/_publish/v1/...`: HEAD 200 ×1(`v1/health.json`)·HEAD 404 ×23, PUT 200 ×24(health는 If-Match). 그 외 `/_publish` 요청 없음.
- 7단계 검사기 1회분(접근 코드 ON·`--notice-check`) **35건** — 11/1에는 검사기를 1차·2차 두 번 돌렸고 그 사이 본문 확인(로그인·`/`·`/?game=`·`/index.html`·로그아웃) 5건이 더 있다: POST `/_access/v1/session` 200 ×1, GET `/v1/manifest.json` 200 ×2(하나는 `--notice-check`), 그 외 자료 GET 200 ×23, GET `/favicon.svg`·`/assets/*.js`·`/assets/*.css` 200 ×3, GET `/index.html` 307(→`/`) 또는 200 ×1, GET `/` 200 ×2(하나는 `?game=849843`), 404 ×2(`/v1/game/999999.json`·목록에만 있는 날짜), HEAD `/v1/manifest.json` 200 ×1. `--notice-check` 없이는 34건.
- 7단계 폰·PC 브라우저 확인(로그인·`/`·자료 폴링)과 안내 ON/OFF(`/_notice` PUT 2건)는 시각으로 구분한다. 접근 코드 없는 401이 있으면 누구 요청인지 기록한다. 원시 로그(IP·헤더)는 Git·이슈에 넣지 않는다.

## 9. 되돌리기

| 상황 | 조치 |
|---|---|
| 새 버전이 잘못됨 | `node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js rollback <버전 ID> --config <후보>/host/wrangler.deploy.json` — 현재 관리 화면에서 마지막 배포와 자격 교체 이력을 확인하고 **모든 자격 교체 이후이며 업로드 OFF인 승인된 후보 ID만** 명시한다. 이 문서의 V0·2·6단계 버전은 후속 자격 교체보다 앞서므로 복구 대상으로 사용하지 않는다. 적합한 후보가 없으면 현 자격을 보존한 수리 배포안을 준비하고 승인을 받는다. 3단계(`secret put`) 뒤에는 인자 없는 `rollback`을 쓰지 않는다: 직전 배포(예: 4단계 업로드 ON 버전)로 가서 업로드 창을 다시 열 수 있다. 프롬프트의 버전 ID가 적어 둔 것과 같은지 보고 확인한다. R2·D1 내용은 그대로지만 **롤백은 그 버전의 비밀·변수를 되살린다**(비밀이 바뀌었으면 Wrangler가 확인을 묻는다). 복구 뒤 업로드 OFF·접근 ON 설정과 승인된 유한 검사 결과를 확인한다. 비밀 원문을 조회·출력하지 않는다. `PUBLISH_TOKEN_SHA256`·`ACCESS_CODE_SHA256`·`NOTICE_TOKEN_SHA256`의 교체 이력을 대조하고, 토큰·코드 회전 **이전** 버전으로는 되돌리지 않는다(옛 토큰·코드가 살아난다). |
| 자료를 숨겨야 함(긴급) | 안내 스위치 ON(`notice-cli`, 운영자 토큰) — 화면·자료 503. 또는 `DATA_READ_ENABLED:false`로 재배포. |
| 올린 파일 회수 | 키별 HEAD 계획(`--head`)으로 현재 ETag → DELETE 계획(`if_match`) `--execute`(묘비 기록, 물리 삭제 아님). 업로드 창(4단계)이 열려 있어야 하고, 토큰 파일을 이미 지웠으면 3단계를 다시 해 새 토큰을 만든다. |
| 토큰 회수 | 새 helper 실행 → `secret put PUBLISH_TOKEN_SHA256`(옛 토큰 즉시 무효) 또는 업로드 OFF 유지. 토큰 파일 폐기. |
| 접근 코드 유출 의심 | `ACCESS_CODE_SHA256`에 새 digest 추가·옛 digest 제거([ACCESS](../ops/public-host/ACCESS.md)). |

## 10. 기록

- CHECKLIST 맨 위 한 줄: Worker 버전 ID / host 커밋 `f50020b` / 형 빌드 `fba6b2ff` / ZIP SHA `790f3b88…` / 검사 pass·fail. 호스트명·버킷·DB·코드·토큰은 쓰지 않는다.
- #38 회신은 [회신 초안](mail_drafts/EXHIBIT-song-reply-20261101.md)에 결과를 채운 뒤 **사용자 승인으로만** 발신. 초안에도 호스트명·코드·토큰은 쓰지 않는다. 포스터 QR은 `pitcheezy.com` 홈 → "서비스 열기" → 앱이 기준이다(앱 직행 QR은 형이 원할 때 최종 포스터에).
- ④ 도메인 연결(`<앱호스트>` custom domain)은 별도 승인 단계이며 이 문서의 ③은 그 전까지 `<시험호스트>`에서 끝낸다. ④ 뒤 7단계를 `<앱호스트>`로 다시 실행한다.

## 하지 않은 것 (2026-11-01 실행 뒤 기준)

④-a 앱 Route·④-b 홈 Worker/www·media R2는 위 오후 기록대로 실행됐다. apex의 Sites 연결 해제·전환은 미실행이다. 8단계 비식별 로그 영수증과 폰에서 849843 지정 경기/QR 전체 동선 기록은 남는다. iPhone 경기/추천과 홈 영상 확인은 사용자 보고가 있으나 지정 경기 ID·복원 지연 측정과 구분한다. 후보 폴더·ZIP·계획·영수증·메모는 Git 밖, 토큰 파일은 삭제했고 접속 코드 파일은 사용자 보관.
