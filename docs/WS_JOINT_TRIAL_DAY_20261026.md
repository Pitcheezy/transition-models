# 공동시험 당일 우리 측 준비 — 2026-10-26 (WS-trial2)

2026-10-26 20:35 KST 작성. 기준 main `4e6aba71487ffe0c2ce9dd6df658ca9db9da9953`, 브랜치 `claude/ws-trial-prep-1026`(문서만). [착수 기록](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6414981761).
**준비 문서이며 합의·배포·자격 등록·접속 허용·실행 기록이 아니다.** 우리 Cloudflare 설정·배포·자격, Song 코드·프로세스·배포, CV 연구 브랜치·폴더는 이번에 바꾸지 않았다. 형에게 새 발신은 없고 [초안](mail_drafts/COLLAB-001-joint-trial-day-20261026.md)만 있다.

사용자 보고: 2026-10-26 21:00 KST에 Song과 공동시험 예정. 최신 ZIP 미수신. 합성 파일 시험(A)과 실제 경기 화면 연결(B)을 모두 시도할 생각이나 세부 범위·종료 시각 미확정. 이 문서는 어느 창이든 그대로 쓰도록 조건만 모은다.

## 1. 현재 상태 — 출처를 구분해 기록

### 1a. Codex 세션 관측 보고 (2026-10-26 19:59~20:04 KST) — Claude 재실행 아님

- 관리 API 조회 성공. 시험 Worker `pitcheezy-ws-stage`, 활성 버전 `d714e7fb-20d4-4a80-9f29-695e44130955` 비중 100%.
- 원격 worker.js 54,114 bytes SHA-256 `3312fbff2dac2a22b32e474392ee7eb107663c79e9749781810a681e5ee07cfd` = 기존 검토 번들과 일치(runtime `e9b362b`).
- 접근문 ON, 업로드·자료읽기·이용기록·피드백 OFF. **기존 `PUBLISH_EXPIRES_AT`는 이미 만료**.
- Cloudflare 설정 화면: Logs ON·Invocation logs ON·Persist ON·Sampling 100%. API는 상위 `observability.enabled=false`와 하위 `logs.enabled=true`를 함께 반환 — 이 조합만으로 고장 판정이나 설정 변경을 하지 않는다.
- 20:04 무인증 `GET /` 1회 → 401. 서버 저장 이벤트 `2026-10-26T11:04:09.180Z`, 클라이언트/서버의 요청 식별자·method·path·status·배포 버전 일치. **오늘 표본 1건의 실제 로그 저장 확인.** 공동시험 전체 로그·만료 403·발행회수 401은 미확인.
- 과거 안내 시험 저장 로그 12/13은 그대로다. 오늘 로그로 옛 누락 1건을 채웠다고 쓰지 않는다. 설정·배포·팀원 코드 변경 없음. Codex 브라우저의 로그인이 Claude 세션의 자격을 뜻하지 않는다(이 세션에서 Cloudflare 자격 파일·로그인 확인: 없음).

### 1b. 10/25 고정 증거 (main)

관람 200→회수 401(로그 4건), 발행 HEAD 404→401→업로드OFF 503(로그 3건), 안내 ON/OFF 13요청(로그 12/13, OFF PUT 1건 미확인 HOLD). [발행](WS_PUBLISHER_REVOCATION_20261025.md)·[관람](WS_VIEWER_REVOCATION_20261025.md)·[안내](WS_NOTICE_TRIAL_20261025.md)·[사전 조회](WS_HOST_PREFLIGHT_20261025.md). 실제 파일 PUT/DELETE·만료 403·Song 실행본의 동일 대상 증거는 없다.

### 1c. 양쪽 board·mail (2026-10-26 20:30 KST 조회)

- Song board #35 [18:45 KST 댓글](https://github.com/SongRoute/pitcheezy/issues/35#issuecomment-6412929588): 라이브 발행 worktree를 `df2f41fa`→`e53b89a7`로 교체, "운영 결함 3건 수정(감시기 입력 격리, 업로드 자격 env/파일, 한 키 후속 검사 결합)", 발행 계약·화면·지연 15초 불변, 업로드 꺼짐 유지, 시스템 파이썬 dry-run exit 0, "공동시험은 10/27 14:00~17:00 제안(#38 회신 Song 게시)". 2차전(10/25) 로컬 발행 341구·추천 0구(메모리 문턱). **모두 Song 보고**이며 우리 수신·검증·수용이 아니다. 세 결함 명칭(OPS-ALERT-JSON01·OPS-CRED-01·ONEKEY-PROBE-01)과의 대응은 설명상 추정이므로 수신 뒤 확인한다.
- Song mail #38: 마지막 댓글은 우리 10/25 17:28 UTC 일정 안내. **10/27 제안 회신은 아직 없다.** 우리 #18: 10/18 이후 없음. 우리 #3: CV 기록과 이 착수 기록.
- D181(10/25): 이번 시리즈 비공개 라이브(로컬 발행+RS 그림자), 3차전 전 공동시험 1회, 공개 배포 없음. "형이 final2로 공개 운영했다"는 추정은 쓰지 않는다.

### 1d. 전달본 해석 (정정)

final2/v4.4(`000e4ba0`)는 10/21 수신·검증한 과거 후보다. v7/v4.5는 미수신이며 화면 수정·핀 갱신의 예고다. **"v7 ZIP이 없으면 시험 불가"가 아니다**: Song이 대체 고정 실행 절차(예: `e53b89a7` 기반)를 실행 파일·명령·등록/전체 SHA·검토 근거·결함 처리와 함께 제시하고 양쪽이 수용하면 A 전송시험을 먼저 할 수 있다. 반대로 형의 내부 권고만 보고 final2나 임의 명령을 실행하지 않는다. Windows에서 Song의 fcntl 실행기를 이식하지 않는다. Song 단일 writer, 우리는 호스팅·관측·회수.

### 1e. Git·작업 경계

worktree 7개 확인. CV 폴더(`claude/cv-ocr-view-1026` f15d314, `claude/cv-track-reacquire-1026` 0112f01, `claude/cv-mitt-temporal-1025` 5e90c19)와 Codex `cv-frame-view-1026`(360d3c4, 깨끗함)·`cv-stationary-candidate-1026`(c3f226f) 불변. `integrate-main` 폴더는 `codex/ws-trial-readiness-1026`(c45ec1c, PR68 미병합, 오늘 02:14 작성)에 있다. 운영 배포 기준은 main 4e6aba7(runtime e9b362b)이며 CV 브랜치를 배포 기준으로 쓰지 않는다.

## 2. 사람이 확정할 창·범위 (AI가 추정하지 않음)

| 항목 | 현재 기록 | 필요한 결정 |
|---|---|---|
| 날짜·시작·종료 | 사용자: 오늘 21:00. Song board: 10/27 14:00~17:00 제안(회신 미게시) | 양측이 같은 창을 보고 있는지, 종료 시각(KST/UTC) |
| 범위 | A·B 모두 시도 의향 | A만 / A+B. B는 자료가 있어야 함 |
| 접속 허용 | 본인 계정·본인 시험만 승인됨 | Song 발행 자격 1개 허용 여부, (B면) Song 관람 코드 허용 여부 |
| 중단 연락 | 비공개 채널 미기록 | 양쪽 담당·즉시 연락 수단·응답 시간 |
| 결함 처리 | 3결함: Song은 e53b89a7 수정 보고(미검증), ASTRA 차단 2건 ACK 없음 | 미검증 상태로 제한 전송시험을 수용할지 |

## 3. A — 합성 파일 전송·회수 시험

### 3.1 완료 기준 (착수 전 고정)

1. 실제 사용할 고정 실행 절차와 파일 SHA를 수신·대조했다(새 ZIP 또는 대체 절차; §5 인수 통과).
2. 새 시험 키 1개·정확한 허용 경로·절대 UTC 만료·요청 예산을 비공개 원장에 고정했고 양쪽이 확인했다.
3. 쓰기(PUT/DELETE)는 Song 실행본만 수행했다. 우리는 HEAD/probe·관측·회수만 했다.
4. 모든 실제 요청을 서버 저장 로그(시각·method·path·status·버전)와 1:1 대조했고, 창 전후 배포 버전·설정 이력이 같았다(변경 시 회차 무효).
5. 합의된 만료 403, 발행 자격 회수 401, 종료 후 업로드OFF 503을 확인했다.
6. 예상 밖 실패·시간초과·결과 불명확이면 그 창에서 중단했고 임의 재시도가 없었다.

증거 필요조건: Song 실행본의 종료코드 0 + wrapper-log `PASS_SYNTHETIC_HTTPS`(PUBLIC-SUMMARY PASS만으로 불인정), 우리 로그 대조 영수증(허용 필드만 공개), 관리 API 조회 횟수 별도 원장. 합성 자료이며 실경기·화면 합격이 아니다.

### 3.2 실행 절차 확정 — 형에게서 받을 것

- 선택 1: 새 고정본 ZIP(v7/v4.5 또는 대체 이름) + 전체 SHA + manifest + 고정 소스/빌드 커밋 + 작성/검토 모델 ID·검토 해시 + 변경 목록.
- 선택 2: `e53b89a7` 기반 대체 절차 — 실제 실행할 파일 목록과 SHA, 명령, 등록서, 검토 근거, 미수정 결함을 어떻게 제한할지.
- 공통: 시험 game key(허용목록 안의 정확한 저장키 1개, 예: `v1/game/<키>.json`), 실행본의 요청 순서와 횟수(HEAD/PUT/DELETE 각각), 시간 예산, Song 측 중단 연락. **기존 GATE-06 32회 원장은 final2 절차 기준**이므로 대체 절차면 실제 요청 수를 다시 계산해 합의한다.

### 3.3 오늘용 호스트 설정안 (적용은 승인된 배포 절차로 별도)

대상은 시험 Worker `pitcheezy-ws-stage`의 현재 버전 `d714e7fb`(runtime e9b362b) **그대로**, 설정/비밀만 창 동안 바꾼다. 코드 재배포 없음.

| 항목 | 창 전(현재) | 창 중 | 창 후 |
|---|---|---|---|
| `ACCESS_GATE_ENABLED` | true | true | true |
| `UPLOAD_ENABLED` | false | **true**(시작 직전) | **false**(가장 먼저) |
| `DATA_READ_ENABLED` | false | A만이면 false 유지. 실행본이 공개 GET으로 검증하면 true(원장에 포함) | false |
| `TELEMETRY_ENABLED`·`FEEDBACK_ENABLED` | false | false | false |
| `PUBLISH_KEY_SCOPE` | (만료된 옛 값) | 합의한 **정확한 키 1개**(선행 `/` 없음, prefix·목록 불가) | 정리(회수 뒤) |
| `PUBLISH_EXPIRES_AT` | 만료됨 | `YYYY-MM-DDTHH:mm:ss.sssZ` 절대 UTC. 계획 시작+약 5분(Song 제안)을 기본으로 하되 시작 시점에 **만료 여유 ≥180초**가 없으면 HOLD. 첫 요청 뒤 연장·덮어쓰기 금지 | 정리 |
| 비밀 `PUBLISH_TOKEN_SHA256` | 옛 digest(회수됨) | **새 시험 토큰 digest 1개** | 새 폐기용 digest로 교체 → 옛 bearer HEAD 401 확인 |
| 비밀 `ACCESS_CODE_SHA256` | 본인 복구 코드 digest | A만이면 변경 없음. B면 Song 관람 코드 digest 추가(사람 승인) | B면 Song digest 제거 → 옛 세션 401 확인 |
| 비밀 `NOTICE_TOKEN_SHA256`·`ACCESS_SESSION_SECRET` | 유지 | 유지 | 유지 |
| Logs/Invocation/Persist 100% | ON | ON(건드리지 않음) | ON |

규칙: 둘 중 하나만 있으면 발행 거부(503)이므로 scope·expiry는 **함께** 넣고 함께 정리한다. 설정 변경 전후 `settings`/`deployments` 조회 스냅샷을 비공개 보관하고 버전 ID가 같은지 확인한다. 안내 스위치가 이미 ON이면 사람 결정 없이 끄지 않는다.

적용 수단(사람/Codex 세션): 이 Claude 세션에는 Cloudflare 자격이 없다. 대시보드(Codex 세션 로그인) 또는 고정 Wrangler 4.151.0 + 유효한 최소 범위 토큰으로 사람이 적용한다. 토큰·코드 원문은 채팅·이슈·명령 인수에 쓰지 않는다.

### 3.4 새 자격 준비 순서 (비밀은 비공개 폴더에만)

1. 사람이 비공개 폴더에서 새 발행 시험 토큰을 만든다(32바이트 난수, base64url). 예: `node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))" > <비공개>/publish_token_YYYYMMDD.txt`.
2. digest만 계산해 등록한다: `node -e "const fs=require('fs');console.log(require('crypto').createHash('sha256').update(fs.readFileSync(process.argv[1],'utf8').trim()).digest('hex'))" <비공개>/publish_token_YYYYMMDD.txt`. 출력은 digest이며 토큰이 아니다.
3. 원문 토큰은 **기존 사람 간 비공개 채널**로 Song에게 전달한다. 공개 이슈·ZIP·채팅 금지. 이전 시험 토큰은 재사용하지 않는다.
4. 폐기용 digest(시험 뒤 교체용)도 미리 만들어 둔다. 폐기용 원문은 아무에게도 전달하지 않는다.
5. B가 있으면 Song 관람 코드도 같은 방식(8~128자, digest만 등록, 원문 비공개 전달). 본인 복구 코드 digest는 유지한다.
6. 등록 뒤 확인(우리 원장에 기록): 옛 bearer `HEAD /_publish/<키>` → 401, 새 bearer `HEAD` 범위 밖 키 → 403, 범위 안 키 미사용 → 404.

### 3.5 요청 원장 — 템플릿 [ws_trial_day_ledger_template_20261026.json](results/ops/ws_trial_day_ledger_template_20261026.json)

- **서비스 원장(A)**: 사전 HEAD(우리, 범위 밖 403·범위 안 404 각 1) → Song 실행본 N회(절차 확정 뒤 기입; final2 기준이면 HEAD1+runner17=18) → 후속 probe 최대 3(만료 403·회수 401·업로드OFF 503). B/안내가 있으면 관람 2·안내 9를 별도 열로 추가.
- **관리 원장**: 설정/비밀 변경 PATCH·PUT, settings/deployments GET, 로그 조회 — 실제 횟수·시각만 기록, 비밀 없음.
- **실패·정리 원장**: 예상 밖 상태·시간초과·중단 사유·정리 요청. 의도한 낡은 DELETE 412는 정상 항목.
- 각 행: 순번·소유자(Song/우리)·method·경로 템플릿·기대 상태·실제 상태·클라이언트 요청 식별자·서버 이벤트 시각·배포 버전. 끝난 뒤 저장 로그와 1:1 결합, 누락은 누락으로 남긴다.
- 합계는 그 창의 상한이지 전체 비용 합의가 아니다. 브라우저 자동 갱신·주기 감시를 본 실행에 섞지 않는다.

### 3.6 정상 종료 순서

1. Song 실행본의 정리/삭제표식과 만료 확인이 끝났는지 양쪽 확인. 2. `UPLOAD_ENABLED=false`. 3. `PUBLISH_TOKEN_SHA256`를 **폐기용 유효 digest로 교체**(digest 전부 삭제 시 503이라 401 증거가 안 됨) → 옛 bearer HEAD 401 확인, 적용 버전·설정 증거 보존. 4. B를 했다면 Song 관람 digest 제거 → 옛 세션 `GET /` 401(접근문 ON·안내 OFF·다른 digest ≥1 유지일 때) 확인. 5. scope/expiry 정리. 6. 설정 스냅샷·로그 조회 → 원장 결합 → 공개 영수증은 허용 필드(시각·method·path·status·version)만. 잔여 객체·삭제표식은 보존(물리 삭제 없음).

### 3.7 긴급 차단 순서

1. 즉시 `UPLOAD_ENABLED=false`. 2. 필요 시 안내 ON(`maintenance`/`data_hold` 고정 문구, 현재 ETag 조건부 PUT, 감사 기록) 및 `DATA_READ_ENABLED=false`. 3. 발행 digest 교체/제거와 적용 버전을 함께 기록. 4. 401 확인은 미완료로 남기거나 별도 창으로 넘긴다(401을 얻으려고 업로드를 다시 켜지 않음). 5. 사유·시각·영향을 비공개 원장에 적고 공개 이슈에는 상태만.

### 3.8 중단 규칙

첫 요청 전 거부·키 미소모면 창 안 재준비 1회 제안 가능. 한 번이라도 요청이 나간 뒤 unknown·5xx·429·예상 밖 412·시간/예산 초과·중단이면 그 창에서 추가 실행 없이 HOLD. 새 실행은 새 키/run_id/승인이며 후속은 최대 3회. 만료 −3분을 넘긴 시작은 하지 않는다.

## 4. B — 실제 경기 자료·관전 화면 연결 (A와 별도 판정)

### 4.1 입력 (형)

배포용 최신 화면 묶음(public build)·경기 자료(game/health/setup 실제 JSON 또는 기록 재생본)·기준 커밋·파일 SHA·manifest. UI 후보 `687e206`은 Song board 보고일 뿐 수신본이 아니다. **자료가 없으면 B는 대기**이며 A 결과와 섞지 않는다.

### 4.2 완료 기준·로컬 검사 (loopback, 실제 계정 아님)

1. 패키지/설정 검사: `python -B -S scripts/build_public_host_release.py check <새 release.zip>`, `python -B -S scripts/check_public_host_config.py <후보 폴더>`(runtime 5파일은 신뢰한 체크아웃과 CRLF→LF 정규화 후 동일해야 함).
2. 로컬 Worker+화면에서 로그인(접근문 ON) → 자료 읽기 → `file_sequence`/health 갱신 재조회 → `unsupported`/참고통계 표시 → 로그아웃.
3. **열린 화면 안내 검사**: 정상 추천 표시 → 안내 ON(`maintenance`, `data_hold` 각각) → 추천 카드·존이 **전부** 숨겨짐 → 안내 뒤 일반 오류(네트워크/5xx/404)에서 과거 추천 **미재노출** → 안내 OFF + 유효 정상 응답에서 의도한 방식으로 복구. final2/v4.4는 "12초 뒤 안내와 마지막 추천 공존"으로 실패했으므로 이 항목이 새 화면의 핵심이다. 도구: `node ops/public-host/rehearse-notice.mjs --output <새 영수증>` + 기존 private harness(`outputs/partner_final_20261021/integration-accepted/combined-review.mjs`, integrate-main 폴더에 보존; 새 빌드 구조가 다르면 수정 전 help/계약 확인).
4. 390px 가로 넘침 없음. 실제 Mac/Safari/휴대폰은 미실행으로 남긴다.
5. 증거 종류를 행마다 표기: 합성 자료 / 오프라인 재생 / 실경기 / 일반 공개(없음).

B 통과는 화면 인수이지 공개 운영 합격·실경기 연결 승인이 아니다.

## 5. 새 ZIP 인수 순서 (받는 즉시)

1. 원본을 별도 비공개 폴더에 보존(덮어쓰기 금지). ZIP 전체 SHA-256·크기, 경로이탈·중복·대소문자 충돌·링크·암호화·CRC·manifest 대조. 불일치면 중단.
2. 등록/실행본/manifest와 source/build·검토 대상이 **같은 최종 커밋**을 가리키는지, runtime5 원본/CR제거 SHA가 우리 고정본과 같은지, 작성·검토 모델 ID·검토 해시·남은 조건.
3. 기존 전달본 대비 변경 목록. "화면/핀만"과 다르면 범위 재확인. 3결함·차단 2건의 수정 주장은 B/§3.2 증거로만 인정.
4. 필요한 로컬 검사만(§4.2). 원본 Windows `verify_offline.py`의 fcntl 실패를 반복·shim하지 않는다. 대규모 검사·영상 분석·전달팩 재포장은 새 결함이 없으면 반복하지 않는다.
5. 통과 뒤에만 우리 후보를 새 폴더로 구성. 실제 배포는 이 절차에 없다.

## 6. 형에게 받아야 할 최소 자료

① 실행 절차 선택(새 ZIP 또는 e53b89a7 절차)과 파일·SHA·명령·검토 근거 ② 시험 키·요청 순서/횟수·시간 예산 ③ 창 확정(21:00 오늘 vs 10/27 14:00~17:00)·종료 시각·중단 연락 ④ (B) 화면 묶음·경기 자료·커밋·SHA ⑤ 실행 후 종료코드·wrapper-log·클라이언트 원장.

## 7. 사용자가 결정할 최소 항목

① 창·범위(§2) ② 새 발행 토큰(및 B면 관람 코드) 생성·비공개 전달·digest 등록을 누가 어떤 수단으로 할지(이 세션은 자격 없음) ③ Song 접속 허용 범위 ④ 결함 미검증 상태의 제한 전송시험 수용 여부 ⑤ 시작 직전 양측 GO.

## 8. 21:00 판단 (20:35 기준)

- A: §3.2 실행 절차·§3.4 새 자격·§3.3 scope/expiry 등록·§3.5 원장 합의가 21:00 전에 끝나야 시작 가능. 지금은 네 가지 모두 미확정이라 **HOLD**. 형이 e53b89a7 절차와 파일/SHA를 보내고 사용자가 자격을 등록하면 같은 문서로 즉시 진행한다.
- B: 자료 미수신으로 **대기**.
- 창이 10/27 14:00~17:00로 확정돼도 이 문서는 그대로 쓴다(시각만 바꿈).

## 9. 이번에 실행한 것 / 실행하지 않은 것

실행: 최신 main·규약·인계·실행계획·양쪽 board/mail 조회, 고정 Wrangler/CLI/검사기 존재 확인, 자격 파일 부재 확인, 새 worktree 생성, 문서·초안·원장 템플릿·영수증 작성, 체크리스트 검사.
미실행: Cloudflare 조회/설정/배포/자격 변경, 서비스 요청, 로그 조회, 형 코드/프로세스 접근, 발신, 운영 코드 변경(따라서 다른 모델 교차검토 대상 없음), 동일 시험·권한 회수 반복, 30~50명 부하, 요금제.

## 10. 검사

`python -m pytest -q tests/test_checklist_model.py`, 문서 상대 링크·비밀/주소 포함 여부, JSON 구문. 결과는 [영수증](results/ops/ws_trial_day_20261026.json)에 있다.
