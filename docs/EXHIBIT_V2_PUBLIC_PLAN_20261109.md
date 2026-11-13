# 공개 앱을 v2(Pitcheezy 색)로 바꾸는 계획과 접속 코드 판단 — 2026-11-09

> **이후 경과(2026-11-12 저녁 기준).** 11/12 15:29 KST에 공개 앱을 Song c47 빌드 + 접속 코드 ON으로 되돌렸다(CHECKLIST `EXHIBIT-rollback1`). 15:49에 #38에 회신했고(댓글 6816876891), 16:49에 Song이 답했다(댓글 6817925715: 공동시험 11/13 21시, 색 테마 조건부 동의, 3D 타자 보류). 아래 본문은 작성 시점 기준이다. "현재", "미발신", "되돌린 적 없음", "미커밋" 같은 표현은 그 시점의 것이다.

사용자 요청(11/9 16시): "현재 배포된 버전 v0 저장해서 기록하고(→ [v0 스냅샷](EXHIBIT_V0_SNAPSHOT_20261109.md)), 공개 배포 버전 v2 pitcheezy 색깔로 바꾸자, 그리고 이제 접속 코드 안 써도 되지 않나 판단해 봐."
이 문서는 **배포 직전 설명·승인용**이다. 11/9 이 세션은 Cloudflare 로그인이 없고 wrangler를 실행하지 않았다. 아래 "실행" 절은 사용자(또는 로그인된 세션)가 승인 뒤 수행한다.

## 1. 지금 상태(기록 기준)

| 항목 | 값 |
|---|---|
| 공개 앱 | app.pitcheezy.com = Song 고정 빌드 c47fe6cb(v0)를 전시 Worker가 서비스. 적용 버전(11/2) `5999cf0d-4f18-4d43-bcd6-320e04860369` |
| 설정 | 접속 코드 ON(`ACCESS_GATE_ENABLED`), 자료 읽기 ON(`DATA_READ_ENABLED`), 업로드·수집·피드백 OFF, 안내 OFF |
| 자료 | 버킷에 849843 한 경기·2026-09-30 하루(6파일)만 — Song이 11/1에 요청한 공개 범위 그대로 |
| v0 스냅샷 | `D:/pitcheezy_exhibit_check/v0-snapshot-20261109/`(SNAPSHOT.json) + 문서 EXHIBIT_V0_SNAPSHOT_20261109.md |

## 2. 무엇을 올리나 — v2(Pitcheezy 색) 공개 후보

`relay/tools/build-public.mjs`(이번에 추가)가 relay v2를 정적 폴더로 모은다. 두 후보를 만들어 두었다(Git 밖).

| 후보 | 폴더 | 파일 | 크기 | 특징 |
|---|---|---|---|---|
| **A 사람형** | `D:/pitcheezy_exhibit_check/v2pz-candidate-20261109/public/v2/` | 13 | 6,391,224 B (6.10 MB) | 3D 타자 = `batter-ctl`(사람형 모델 변환본 3.2 MB) |
| **B 마네킹** | `D:/pitcheezy_exhibit_check/v2pz-candidate-20261109-mannequin/public/v2/` | 13 | 5,898,712 B (5.63 MB) | 3D 타자 = `batter-indexed`(Mixamo 마네킹, 2.7 MB) |

내용: `index.html`(v2.html에서 생성: Pitcheezy 색 기본·`?palette=song`이면 Song 색, 홈 링크 `https://pitcheezy.com/`, robots noindex 유지), `relay.js`(로딩 실패 안내문의 로컬 주소만 "잠시 뒤 새로고침" 문장으로), `relay-v2.css`, `batter3d-host.js`(기본 모델만 빌드 인자), `batter3d/`(모듈·three.js r187 vendor 5파일·모델 glb/meta), `data/849843.json`(버킷 `v1/game/849843.json`과 바이트 동일, SHA `056fcf13…`). 각 후보 상위 폴더의 `MANIFEST.json`에 SHA-256 전부.
로컬 검증(앱 안 Chromium 375px, `python -m http.server 8799`, launch `v2pz-candidate`): 요청 13건 전부 200·404 0, 콘솔 오류 0, 3D 연결(batter-ctl, 클립 6), 투구 262줄, Pitcheezy 색 적용.

### 배치 방식 두 가지(사용자 결정 ①)

| 방식 | 내용 | 장점 | 단점 |
|---|---|---|---|
| **(가) `/v2/` 덧붙이기(권장 1단계)** | Worker의 정적 자산 폴더 = Song public 4파일 **+ `v2/` 13파일**. 루트 `/`는 그대로 Song 화면, `/v2/`가 우리 화면. Worker 코드·설정·비밀 변경 없음(자산 폴더만 커짐) | Song 화면과 11/11 공동시험 경로를 건드리지 않음. QR·링크를 `/v2/`로 주면 그걸로 "공개 버전 v2"가 됨. 되돌리기 = v0 스냅샷 public으로 재배포 | 주소에 `/v2/`가 붙음 |
| **(나) 루트 교체** | 루트 `index.html`을 우리 v2로 바꾸고 Song 빌드는 내림(또는 `/v0/`로 옮김 — 단, Song 빌드는 자료를 `./v1/…`로 읽어 하위 폴더에선 Worker 경로 수정이 필요) | 주소가 깔끔 | **Song의 관전 화면을 공개에서 내리는 결정** — 협업 규약상 관전 화면은 Song 담당이라 Song 동의가 먼저. 11/11 공동시험(Song 빌드 기준)과 충돌 |

권장: (가)로 먼저 올리고, Song과 합의되면 (나). (가)는 "공개 배포 버전을 v2로 바꾸자"를 **링크 기준**으로 충족한다.

### 결정 ②: 사람형(A) vs 마네킹(B)

후보 A와 B 가운데 무엇을 쓸지는 3D 모델 선택 문제다(세부는 비공개 기록에서 관리). 후보 선택은 사용자 결정. 전시 11/24에는 어느 쪽이든 동작 동일(hit·take·miss 클립은 A에만 있음 — B는 contact/miss만).

## 3. 접속 코드, 이제 안 써도 되나 — 판단

**근거가 되는 기록**

- 코드는 "시험 단계(우리·형만) 보호"로 11/1에 넣었다(EXHIBIT_HOST_PLAN "이 단계는 접근 코드 ON 유지", 결정 2 "관람객 폰 QR이면 접근 코드를 꺼야 한다 = 일반 공개"). 운영 문서는 "**공개 전환 승인 전에는 ON 유지**"(EXHIBIT_OPERATIONS 42·57행), Codex 인계는 "11/11 공동시험 지원 — 접근 코드 ON 유지, **11/21 OFF 예정**".
- 즉 코드는 **공개 승인 전까지의 자물쇠**이지 기술적 필요물이 아니다.

**코드를 끄면 달라지는 것(사실 확인)**

| 걱정 | 확인 | 판단 |
|---|---|---|
| 자료 노출 | 새 Worker의 버킷에는 Song이 요청한 공개 범위(849843·2026-09-30, 6파일)만 있다 | 끄더라도 Song 합의 범위 밖 노출 없음 |
| 요청량(Workers Free 하루 100,000, 계정 전체) | Song 화면은 폴링 때문에 **열린 화면당 약 480요청/시간**(11/1 로컬 측정). v2는 폴링 없음: 첫 방문 13요청(6.1 MB), 그 뒤 0 | v2로 바꾸면 요청량 걱정이 크게 준다. 10만/일이면 v2 약 7,000방문/일. 봇·크롤러 대비는 Cloudflare 대시보드의 Rate limiting 규칙 1개(무료)로 보완 가능(사용자 조작) |
| D1 쓰기(무료 하루 10만 행) | gateway는 `/_telemetry`에서만 D1에 쓰고(`telemetry.mjs` usage_sessions/feedback, 예산 표), 수집은 OFF | 코드 OFF로 늘어나는 D1 쓰기 없음 |
| 3D 모델 선택(A/B) | 후보 A는 사람형 모델 포함 | 결정 ②와 묶임 |
| 로그인 화면 문구("개발용 입력 화면") 승인 문제 | 코드 OFF면 화면 자체가 안 나옴 | 해소 |
| 11/11 공동시험 | 시험 트래픽과 공개 트래픽이 섞이고, Song 빌드 경로가 공개됨 | 공동시험 **뒤**에 끄는 것이 깔끔(계획대로 11/21, 또는 Song과 합의하면 더 일찍) |
| 전시 당일 | 관람객 QR → 코드 입력은 큰 마찰 | 전시 전에는 반드시 OFF |

**판단:** 기술적으로는 지금 꺼도 된다(자료 범위·D1·요청량 모두 문제 없음). 남는 건 세 가지 합의·결정뿐 — ① Song에게 "공개 전환"을 알리고 동의(우리 화면을 `/v2/`로 올리는 것도 함께), ② 11/11 공동시험 전/후 어느 쪽에 끌지, ③ 3D 모델 선택(A/B). **권장 순서:** (1) 코드 ON인 채로 `/v2/`(후보 A)를 올려 폰에서 확인 → (2) Song 동의 → (3) 11/11 뒤 코드 OFF(`ACCESS_GATE_ENABLED` 값 변경 + 재배포 1회; 그때 A를 유지할지 B로 바꿀지 결정). 전시 전에 꼭 OFF.

## 4. 실행 절차(승인 뒤, 로그인된 창에서) — 이 세션은 실행하지 않음

0. 대시보드에서 현재 적용 버전 id가 `5999cf0d…`인지 확인(다르면 멈추고 기록).
1. 배포용 자산 폴더 만들기: v0 스냅샷 `public/`(4파일) 복사 + 후보 `public/v2/`(13파일) 복사 → 바이트 대조(SNAPSHOT.json·MANIFEST.json SHA).
2. 기존 stage2 설정(비공개 폴더의 wrangler 설정, 비밀 4개 유지=keepSecrets)으로 **배포 1회**(`wrangler deploy --config <설정>`; 11/1 절차 문서 EXHIBIT_HOST_DEPLOY_STEPS 2~6단계와 같은 방식). 코드 변경 0, 설정 변경 0(자산만).
3. 확인(접속 코드 뒤, 사용자 폰·노트북): `/`가 그대로 Song 화면, `/v2/`가 Pitcheezy 색 v2 + 3D, `/v2/data/849843.json` 200, `/v1/game/849843.json`과 SHA 동일. 요청 13건 200.
4. 기록: CHECKLIST에 새 버전 id·시각·검사 결과, v0 스냅샷 문서에 "되돌리기 기준 유지" 한 줄.
5. 되돌리기: `wrangler rollback <5999cf0d…>` 또는 v0 스냅샷 public만으로 재배포.
6. (별도 승인) 코드 OFF: `ACCESS_GATE_ENABLED`을 끄는 값으로 바꾼 설정으로 재배포 1회 → `/` 200(로그인 화면 아님)·`/v1/manifest.json` 200 확인 → 기록. 되돌리기는 ON 값으로 재배포.

## 5. 하지 않은 것·주의

- 배포·설정 변경·비밀 조회는 하지 않았다. Worker 코드도 그대로다(`release.zip`의 host/).
- 후보 A/B 선택, (가)/(나), 코드 OFF 시점은 사용자 결정이며 Song 동의가 필요한 항목(관전 화면·공개 전환)은 발신도 사용자 승인 뒤.
- 후보는 데스크톱에서도 열리지만 폰 틀(390px)이 가운데 놓이는 v2 그대로다. Safari 실기기는 미측정.

## 6. 추가(11/9 17시): V3 = Song 배포 화면 + Pitcheezy 색 + 3D 타자 — 루트 교체 후보

사용자가 V3를 "지금 공개 배포 화면 그대로에 색 테마와 우리 캐릭터만 입힌 것"으로 정의했다(위 2절의 relay v2 후보와는 다른 물건). 이 후보는 **Song 화면·동작을 그대로 두므로 (나) 루트 교체에 어울린다**(Song의 관전 화면을 내리는 것이 아니라 덧입히는 것; 그래도 Song 동의는 필요).

| 항목 | 값 |
|---|---|
| 폴더 | `D:/pitcheezy_exhibit_check/v3-songskin-20261109/public/` (14파일, 5,995,100 B; 마네킹 판 5,502,630 B; `MANIFEST.json` 상위 폴더) |
| Song 파일 | `assets/*.js`·`*.css`·`favicon.svg` = v0 스냅샷과 바이트 동일. `index.html`만 태그 3개(import map, `pz/pz-theme.css`, `pz/pz-batter.js`) + theme-color |
| 우리 파일 | `pz/` 10파일: 테마 CSS 3.8 KB, 호스트 JS 9.5 KB, 3D 모듈·three vendor 2.3 MB, 모델 glb 3.2 MB + 메타(사람형 batter-ctl; `--model batter-indexed`로 마네킹 판 가능) |
| 자료 | 바꾸지 않음. Song 앱이 전처럼 `/v1/…`(버킷)을 읽는다 — 그래서 **배포 폴더에 자료 복사는 없다**(local-serve에만 있음) |
| 확인 | 로컬 8800: 콘솔 오류 0, 3D 연결, 테마, 투구 전환 반응, 목록 화면 정상. 헤드리스 녹화 `relay/captures-20261109/pitcheezy-v0-v3.gif` |

### 어느 PC에서 하나 — **노트북(Windows, 이 세션의 PC)**

배포에 필요한 것이 모두 노트북에만 있다: 고정 Wrangler 4.151.0(`ops/public-host-tooling/node_modules`), 11/1~11/2에 채운 비공개 배포 설정(`<후보>/host/wrangler.deploy.json`, Git 밖 D: 폴더), 접속 코드·안내 토큰 파일(사용자 비공개 폴더), 설정 검사 스크립트(`scripts/check_public_host_config.py`), 그리고 v0 스냅샷·V3 후보 폴더(D:). Mac에는 Codex 작업 폴더(읽기 전용)뿐이고 Cloudflare 로그인도 노트북 브라우저에서 했다. Mac에서 하려면 wrangler 설치·로그인·비공개 설정 복사가 다시 필요하므로 권하지 않는다.

### 노트북에서 할 일(승인 뒤, 순서대로; 4절과 같은 방식)

0. 대시보드(Workers → 전시 Worker → Deployments)에서 현재 적용 버전이 `5999cf0d…`인지 확인. 다르면 멈추고 기록.
1. 새 후보 폴더 만들기(Git 밖): 11/2 단계2 후보 폴더를 통째로 복사 → 그 안의 `public/`을 **V3 `public/` 14파일로 교체**(`host/`·`wrangler.deploy.json`은 그대로; 코드·설정·비밀 변경 0). SHA 대조: `MANIFEST.json`(V3)과 v0 스냅샷 `SNAPSHOT.json`(assets 3파일 동일해야 함).
2. 저장소 루트에서 `python -B -S scripts/check_public_host_config.py <새후보>` → ok 확인. (선택) 1절 방식의 dry-run.
3. 배포 1회: `node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js deploy --config <새후보>/host/wrangler.deploy.json` → 출력의 새 버전 ID 기록(CHECKLIST 맨 위). 비밀 4개는 keepSecrets로 유지.
4. 확인(폰·노트북, 접속 코드 입력 뒤): `/?game=849843`에서 진녹 헤더·라임 1순위·3D 타자, 투구 시트 ‹ ›에서 반응; `/`(목록) 정상; `/pz/pz-theme.css` 200; 개발자 도구 콘솔 오류 0. 요청 수: 첫 방문 Song 요청 + pz/ 10개.
5. 되돌리기: `wrangler rollback <5999cf0d…> --config <새후보>/host/wrangler.deploy.json`(4절 5항 주의 그대로) 또는 v0 스냅샷 `public/`으로 재배포.
6. (별도 승인) 접속 코드 OFF: 3절 판단대로 — `ACCESS_GATE_ENABLED`을 끈 설정으로 재배포 1회, `/`가 로그인 화면 없이 열리는지 확인. 3D 모델 선택(A/B)은 이때 결정.

Song 동의: 루트의 화면을 바꾸는 것이므로 배포 전에 Song에게 V3(GIF·정지 화면)를 보여 주고 동의를 받는 것을 권한다(발신은 사용자).

## 7. 실행 결과 — 2026-11-09 18:00~18:01 KST (사용자 승인: "배포 v3로 하자 … 코드 off 시키자")

노트북의 고정 Wrangler 4.151.0이 11/1 OAuth 로그인을 유지하고 있어 사용자 조작 없이 진행했다. 두 번에 나눠 배포해 단계마다 코드 없이 확인하고 되돌릴 지점을 둘로 만들었다. 기록 [v3-deploy-20261109.json](results/exhibition_20261101/v3-deploy-20261109.json)(비식별).

| 단계 | 내용 | 새 버전 | 확인 |
|---|---|---|---|
| 0 | 배포 목록 조회: 적용 버전 `5999cf0d…` = 기록과 같음 | — | — |
| A | 화면 그대로, 접속 코드 OFF(`ACCESS_GATE_ENABLED` false + `collection-settings.json` accessGate false) | `55087f55-688f-4fd8-a59a-fa45ebeaaaf2` | 쿠키 없이 `/`·`/?game=849843`·`/v1/*` 200, 바이트 = v0 스냅샷 |
| B | V3 화면(공개 15파일) | `c222a454-c36d-4406-b411-1f7f06b0d5dc` | 15/15 라이브 바이트 일치, `/v1/*` 200, 업로드 503, 헤드리스 375px 실주소: 3D·네 공 반응·콘솔 0 |

- 설정 검사기: A 통과. B는 공개 확장자 목록에 `.glb`가 없어 막혔고, 이번 검사에서만 `.glb`를 더해 나머지 검사를 모두 통과시켰다(저장소 코드는 그대로; 목록 갱신은 별도 검토 단위).
- 되돌리기: V3만 내리기 = `wrangler rollback 55087f55…`(코드 OFF·Song 원래 화면), 전부 되돌리기 = `wrangler rollback 5999cf0d…`(코드 ON). 둘 다 `--config <B-v3 후보>/host/wrangler.deploy.json`.
  Wrangler는 이 저장소 폴더 안에만 있으므로 PowerShell 어느 위치에서든 아래처럼 **절대 경로**로 실행한다(11/9 사용자가 `C:\Users\zpfh1\Projects`에서 상대 경로로 실행해 MODULE_NOT_FOUND — 아무것도 바뀌지 않았음을 라이브 SHA로 확인). 확인 질문이 나오면 y.
  ```powershell
  node C:\Users\zpfh1\Projects\transition-models-exhibit-1101\ops\public-host-tooling\node_modules\wrangler\bin\wrangler.js rollback 55087f55-688f-4fd8-a59a-fa45ebeaaaf2 --config D:\pitcheezy_exhibit_check\v3-deploy-20261109\B-v3\host\wrangler.deploy.json --message "V3 down, keep gate off"
  ```
- 남은 것: Song 알림·동의, 실기기 확인, GPT 검토, 홈 화면 안내 문구(코드 입력 안내가 남아 있다면) 점검.
