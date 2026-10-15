# WS-stage1 — 본인 전용 Cloudflare 시험 준비안

2026-10-15. 우리 코드 기준 `c07dc942030e5ec4f100f638d572239524cd327e`, 문서 기준 `733ae750ff4c6511bf495a9dc6a75021f2c68238`.
**준비안이며 실행된 배포가 아니다.** 새 사용자 결정은 본인 Cloudflare·본인만 시험·월 $10 이내 준비·이용 기록/피드백 OFF다.
[사람 결정 기록](WS_HUMAN_DECISIONS.md) · [회신·산정·검사 영수증](results/ops/ws_stage1_20261015.json).

현재 계정/도구 후속 결과는 [WS-stage2](WS_ACCOUNT_READINESS_20261015.md)를 따른다. 아래 미조회·미고정은 WS-stage1 당시 기록이다.

## 1. 첫 시험에서 확인할 것

기존 사이트와 분리한 시험 환경에서 본인 로그인 → 고정 공개 JSON 읽기 → 추천/실제 결과 표시 → 발행 중단/복구 표시를 확인한다.
최초 자료는 합성 예제 또는 허용된 오프라인 공개용 파일이다. 실제 경기 연결·다른 관람자 초대·공개 사이트 전환은 별도다.
Song은 화면/모델/발행기를 유지하고 우리는 받은 고정 빌드와 공개 파일을 호스팅한다. 상대 소스·프로세스·배포를 다루지 않는다.
현재 승인된 것은 준비와 지정 회신 1회뿐이다. 실제 자원/권한/비용/접속 변경이 명시된 실행안을 준비한 뒤 그 실행 범위를 확인한다.

## 2. 필요한 자원과 잠정 설정

- 기존 사이트와 이름·경로가 겹치지 않는 Worker 1개, 비공개 R2 Standard 버킷 1개, 빈 비공개 D1 1개. 아직 만들지 않았다.
- R2 직접 공개 주소는 열지 않고 Worker를 통해서만 읽는다. 실제 private 여부와 계정 binding은 별도 확인한다.
- D1은 수집 OFF 런타임만 보면 생략 가능하지만, 현재 설정 검사기는 OFF여도 D1·마이그레이션·UTC 03:17 정리 cron을 요구한다.
  검증된 형식을 유지해 전용 빈 DB를 준비한다. 정리/관리 쿼리까지 모두 무료라는 뜻은 아니다.
- 업로드/수집 제한기 두 binding과 계정에서 충돌하지 않는 namespace가 필요하다. 예제의 이름/ID는 실계정 값이 아니다.
- 화면과 JSON은 같은 HTTPS 출처. `workers_dev: false`, `preview_urls: false`, `assets.run_worker_first: true`를 유지한다.
  별도 HTTPS 접속 경로는 아직 없다. 현재 검사기는 `routes` 항목을 받지 않으므로 도메인 연결은 별도 승인·기록·실제 경로 검사 대상이다.
  이 파일을 복사하는 것만으로 접속 가능한 배포가 되지 않으며 기존 사이트 DNS를 바꾸지 않는다.
- `host/worker.mjs`, `assets.directory: "../public"`, SPA fallback, `ASSETS`/`PUBLISH_BUCKET`/`TELEMETRY_DB` binding을 사용하는 패키지 구조다.

초기 잠정 설정(실계정에 적용하지 않음):

- `ACCESS_GATE_ENABLED="true"`; 공개 `collection-settings.json`의 `accessGate: true`.
- `TELEMETRY_ENABLED="false"`, `FEEDBACK_ENABLED="false"`; 공개 설정 두 값도 false.
- `DATA_READ_ENABLED="false"`, `UPLOAD_ENABLED="false"`로 준비하고, 나중에 승인된 시험 파일 읽기/업로드 단계에서만 각각 켠다. 이 초기값에서는 관전 데이터가 표시되지 않는다.
- `READ_ORIGIN=""`, `COLLECTION_ORIGIN=""`. 접근 문은 같은 출처 쿠키를 사용한다.
- 기존 예제의 세션 43,200초·보관일 30은 잠정값이다. 실제 세션 길이는 실행 후보에서 고정하며 30일을 향후 수집 ON 정책 승인으로 쓰지 않는다.
- 접근 비밀 이름은 `ACCESS_CODE_SHA256`, `ACCESS_SESSION_SECRET`; 업로드/안내는 별도 `PUBLISH_TOKEN_SHA256`, `NOTICE_TOKEN_SHA256`.
  값은 비공개 비밀 저장소에만 설치한다. 본인에게만 접근 코드를 전달할 계획이며 코드는 개인 신원 인증이나 재공유 방지 장치가 아니다.

접근 문은 토글이 정확히 문자열 `"true"`일 때 비밀 누락/형식 오류를 503, 세션 없음을 401로 막는다.
**토글 자체 누락·오타는 런타임에서 OFF 취급하므로 모든 오설정이 차단되는 것은 아니다.** 설정 검사와 실제 적용 토글/경로·직접 asset 검사가 필요하다.
근거: [설정 검사](../ops/public-host/CONFIG_CHECK.md), [검사 코드](../src/operations/host_config.py), [접근 코드](../ops/public-host/access.mjs), [수집 코드](../ops/public-host/telemetry.mjs).

## 3. 월 $10 준비 예산 안에서 확인할 것

Workers 유료 기본요금은 월 $5이며 포함량 초과 사용료가 붙는다. 별도 상품·계정 잔여 포함량·세금은 확인 전이다.
[Workers](https://developers.cloudflare.com/workers/platform/pricing/) · [R2](https://developers.cloudflare.com/r2/pricing/) · [D1](https://developers.cloudflare.com/d1/platform/pricing/) 공식 가격을 10/15 다시 확인했다.

기존 산정기에 **본인 1명·총 21시간·5초마다 JSON 2개·요청당 CPU 5ms** 가정을 넣었다. CPU·빈도·처리량은 모두 미측정이다.
추가 Worker 1,000회, PUT 7,560회·DELETE 10회·HEAD 7,570회, 안내/감시 등을 위한 추가 R2 읽기 50,000회,
R2 0.1GB-month·D1 0.01GB-month·관리/정리용 D1 읽기 10,000행/쓰기 1,000행도 산정 가정이다. 방문자 행동 수집량이 아니다.

- 결과: Worker 46,380회. 포함량이 남은 조건에서 소계 **$5.00**, 이미 소진된 조건의 민감도 소계 **$9.90**.
- 이는 두 조건의 계산이지 실제 비용의 범위/상한이 아니다. 두 값 모두 기본요금 $5를 포함하며 기존 계정 전체 청구/증분 금액이 아니다.
- 세금·도메인·별도 상품·로그/메일·가정 밖 재시도/봇·다른 계정 사용량은 제외된다. $9.90 조건은 $10 이내 실행 가능 근거가 되지 않는다.
- 시작 전 계정 포함량과 별도 청구를 확인한다. 총 예상이 $10 안인지 불명확하면 유료 자원을 만들지 않고 무료 범위 시험 또는 더 작은 계획으로 다시 제시한다.
- 제안 운영 기준: 매 시험 전후 비용/요청량 확인, 월 예상 $8 도달 시 검토, $10 초과 전망이면 확대 중지와 사람 결정을 요청한다. 아직 경보·차단 장치를 설치하지 않았다.
- 접근 코드, 일일 쓰기 상한, 요청당 CPU 제한은 **월간 청구 상한이 아니다**. 안내 화면으로 바꾸어도 요청/기본요금이 없어지지 않는다. CPU 제한값은 실측 전 미정이다.

재현:

```text
python -B -S scripts/estimate_public_host_cost.py docs/results/ops/ws_stage1_cost_input_20261015.json
```

출력의 `measurement:false`, `budget_approved:false`는 산정 도구 자체가 승인/실측을 하지 않는다는 뜻이다.
사용자가 정한 준비 예산은 별도 결정 기록에 보존하며 산정기의 고정 결과를 고쳐 승인 증거로 만들지 않는다.
10/12 가격 스냅샷 산정과 10/15 공식 재조회 날짜도 구별한다. 기존 [산정 한계](../ops/public-host/COST_PLAN.md)를 유지한다.

## 4. 실행안을 구체화하는 순서

1. **우리만 가능한 준비:** 계정의 상품/포함량/권한을 읽기 전용으로 확인할 수단을 마련하고, 전용 자원·같은 출처 HTTPS 경로·비밀 설치 방식·고정 Wrangler 버전과 실행 경로를 정한다.
   이번에는 계정 조회/로그인/설치도 하지 않았다. 로컬 조회 결과 Node 24.1.0, Python 3.12.12, 저장소 로컬 Wrangler 미설치다.
2. **후보 고정:** 받은 최종 공개 빌드·출처·SHA와 우리 검토한 고정 커밋을 묶는다. 기존 첫 팩은 개발 연결 증거이며 최신 최종본으로 바꾸어 부르지 않는다.
   `unsupported` 예시·두 스키마 수정·발행 규칙/업로더는 mail #18 후속 수신 대상이다. 전부 도착할 때까지 1번을 미룰 필요는 없다.
3. **오프라인 후보 검사:** 아래 명령의 입력을 실제 고정 파일로 채워 실행한다. 후보 출력 디렉터리는 새 경로, 검사 결과는 후보 밖에 저장한다.
4. **실행 전 검토:** 실제 적용 설정·버전·권한·비용·접속 경로를 포함한 한 실행안을 사용자에게 제시한다. 이번 준비 승인을 실제 가입/배포 승인으로 확대하지 않는다.
5. **실계정 시험(승인 후):** 외부 경로를 열기 전에 비밀/토글·private binding을 확인하고, 실제 HTTPS에서 미로그인·로그인·직접 JSON/asset·로그아웃·세션 만료·수집 OFF를 검사한다.
   승인된 시험 파일 업로드/읽기를 켠 뒤 ETag/304·412 충돌·삭제/복원·발행 중단·안내/접근 문·수집 미생성을 확인한다. CDN/비용/지연은 그때 측정한다.

```text
python -B -S scripts/build_public_host_release.py build --frontend <고정공개빌드폴더> --provenance <고정출처JSON> --host-commit <검토한40자리커밋> --mode candidate --output <존재하지않는출력폴더>
python -B -S scripts/build_public_host_release.py check <출력폴더>/release.zip
python -B -S scripts/check_public_host_config.py <별도설정을준비한압축해제후보폴더>
```

위 명령은 절차의 틀이며 이번에 실제 후보로 실행하지 않았다. 패키지/설정 검사 자체도 항상 `deployable=false`다.
정확한 배포 명령은 Wrangler 버전·계정·라우팅·고정 후보가 준비될 때 작성한다. 실제 주소·자원 ID·비밀을 공개 문서에 채우지 않는다.

## 5. 이번 완료와 남은 조건

완료: 지정 회신 1회 게시·원격 본문 일치, 새 선택 기록, 현재 구현 기반의 자원/설정/비용 가정/시험 절차 준비.
[게시된 회신](https://github.com/Pitcheezy/transition-models/issues/18#issuecomment-6190443556)의 문안은 바꾸지 않았으며 mail은 OPEN이다.
최종 문서 검사·독립 대조의 실제 결과는 영수증과 CHECKLIST에 기록한다. 운영 코드는 변경하지 않았다.

남음: 실제 계정/도구·자원/경로, Song 후속 자료, 배포 승인, 실제 기기·클라우드 검증, 이메일 제공자/양쪽 수신/실제 발송, 자료 이용 범위와 전체 출시 근거.
개인 수신 주소는 기록하지 않는다. 이메일 선택을 발송 제공자 확정으로 쓰지 않으며 실제 메일은 보내지 않았다.
A-y/F-4i 보류·CV/실기기의 독립 조건을 그대로 유지한다. 10/20 연락/응답 시간 결정·10/21 이후 고장 수리만이라는 규칙도 유지한다.
