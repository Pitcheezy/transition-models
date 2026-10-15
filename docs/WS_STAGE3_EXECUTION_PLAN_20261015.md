# WS-stage3 — 본인 전용 Cloudflare 시험 실행 준비

2026-10-15. 기준 main `928b2671cf6605dc7f83d2801d56fcf5adc39c7a`, 선점 `93d4c7b`.
[합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6191683745) · [검증 영수증](results/ops/ws_stage3_20261015.json).
**시험 실행안·합성 후보·다른 모델 검토를 완료했다. 실제 자원·API 토큰·비밀·배포·DNS 연결은 아직 실행하지 않았다.**
기존 R2 가입 완료와 이번 실행 권한을 구분한다. 실제 자원 실행은 WS-stage4로 기록한다.

## 1. 정한 시험 범위

본인 Cloudflare에서 본인 한 명이 합성 자료로 접속 제한·파일 발행·철회·복구를 확인한다.
전용 Worker1개 + private R2 Standard1개 + 빈 D1 1개 + 별도 Custom Domain1개다.
정확한 이름·호스트명·계정 ID는 Git 제외 비공개 실행안에만 보관한다. 기존 root DNS/사이트는 변경하지 않는다.
첫 시험 계획은 합성 입력 최대5MiB·시험 요청 최대200회·활성 확인 약30분이다.
이는 시험 실행 계획의 제한이며 전체 인터넷 요청/계정 과금의 강제 상한이 아니다.

- Workers Free 유지. 유료 Workers 전환은 포함하지 않는다. 월$10는 준비 예산이며 자동 청구 상한이 아니다.
- 접근 문 ON, 세션3600초. 이용 기록·피드백은 서버/화면 양쪽 OFF다.
- 첫 배포에는 자료 읽기/업로드도 OFF. 접근 문 검증 뒤 승인된 합성 시험 동안만 켠다.
- R2의 개발용 공개 URL과 공개 도메인을 OFF로 유지한다. 영상·실경기·사람 검토 자료는 올리지 않는다.
- D1은 현재 검증된 구성의 바인딩/정리 작업 확인용이다. 이용 기록을 수집하지 않는다.
- Song 최종 관전 화면·실제 발행기는 연결하지 않는다. 현재 화면은 저장소의 최소 합성 예제다.

## 2. 인증 초안과 제한

Cloudflare UI에서 custom token 발급 전 요약까지만 작성했다. `Create Token`은 누르지 않았다.
계정은 본인 계정 하나이며 다음 실제 UI 권한만 선택했다.

- Account / Workers Scripts / Edit
- Account / Workers R2 Storage / Edit
- Account / D1 / Edit

계정 전체의 해당 제품에 적용되는 권한이며, 앞으로 만들 자원 세 개로 토큰 자체가 제한되는 것은 아니다.
실행은 비공개 계획에 고정한 신규 시험 자원으로만 제한한다. 기존 토큰·다른 자원은 사용하거나 수정하지 않는다.
TTL 입력은 10/16 21:00 KST, 요약은 End Date October16을 표시했다. 발급 후 실제 만료 시각을 다시 확인한다.
이 시각이 지나면 초안을 그대로 제출하지 말고 새 짧은 기간을 사용자에게 제시한다.
IP 제한은 설정하지 않았다. 토큰 값/계정 식별값/주소는 공개 기록·로그·명령 인수에 넣지 않는다.

Wrangler4.151.0 기본 OAuth는 이번에 필요한 범위보다 넓고 R2 생성 범위가 기본 목록에서 확인되지 않았다.
그래서 위 custom token을 제안했다. 이 세 권한으로 실제 API가 모두 성공하는지는 아직 미검증이다.
권한 오류가 나면 원인을 조회하고, 승인 없이 권한을 넓히지 않는다. Custom Domain은 Dashboard에서 별도 연결한다.
[공식 토큰 생성](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/),
[고정 버전 OAuth 범위](https://github.com/cloudflare/workers-sdk/blob/wrangler%404.151.0/packages/workers-auth/src/core/scopes.ts).

## 3. 실제 완료한 검증

고정 host `c07dc942030e5ec4f100f638d572239524cd327e`와 기존 합성 화면/출처 예제로 패키지를 만들었다.
release ZIP13파일·108,993bytes, 설정을 더한 검증 원본16파일·113,578bytes다.
화면 출처111…은 합성 값이다. Song 화면 수신이나 실제 배포 합격 근거가 아니다.
설정의 D1 ID도 의도적인 placeholder이므로 그대로 실배포하지 않는다.

Wrangler4.151.0/Node24.1.0에서 새 프로필·명시적 빈 env·키체인/지표/오류전송 OFF로 dry-run1회 종료0.
검증 원본은 보존하고 동일 바이트의 도구 복사본만 실행했다. 원본 설정 검사 전후 통과,
원래16파일의 SHA와 복사본 SHA가 모두 일치했다. 생성된 Worker bundle은52,728bytes다.
2.148초는 로컬 번들 시간이며 서비스 응답 속도/Cloudflare CPU가 아니다. 외부 통신0건도 주장하지 않는다.

작성 계열과 다른 실제 모델 `gpt-5.6-sol`이 전체 고정 host와 이번 후보를 읽어 **P1/P2 없음**으로 검토했다.
12개 host 파일이 manifest·고정 Git blob과 바이트 단위로 일치하며 JS7개 구문 검사를 통과했다.
집중 Node82개 중79개 통과·3개는 localhost 연결 EACCES로 실패했다. Python은39개 통과·95개가 임시 폴더 생성 권한 때문에 setup 오류였다. 환경 오류 항목을 통과로 세지 않았다.
실계정 실행 전체 승인이나 보안 보증은 아니다. 주요 확인은 다음과 같다.

- 정적 자산/API가 Worker-first 경로와 접근 검사를 거친다. 인코딩 API 우회와 비공개 경로의 SPA fallback을 차단한다.
- 업로드는 viewer gate와 별도로 업로드 토글·bearer·limiter를 확인한다.
- gate=true일 때 접근 비밀이 없거나 잘못되면503. 수집/피드백OFF는 DB 접근 전 거부한다.
- `ACCESS_GATE_ENABLED` 누락/오타는 gate OFF로 해석된다. **hostname 연결 전 실제 배포 변수 `true`를 확인해야 한다.**

## 4. 승인 후 실행 순서와 중단 조건

아래 전체는 실행안이다. 이번 기록 시점에는 자원/API 권한/비밀/배포/DNS가 미승인·미실행이다.
비밀 생성·설치와 짧은 API 토큰 발급, 새 시험 경로 연결을 포함한 구체 범위를 사용자에게 함께 제시했다.

1. 짧은 API 토큰 발급·만료/세 권한 확인. 자식 프로필에만 전달하고 기존 개인 자격증명은 읽지 않는다.
2. 새 private R2와 빈 D1을 만든다. 같은 이름의 기존 자원이 있으면 덮어쓰지 말고 소유/내용을 확인한다.
3. R2 public dev URL/domain OFF 확인. D1의 실제 ID로 **새 후보**를 만들고 설정 검사를 다시 한다.
4. `0001_telemetry.sql`을 원격 D1에 먼저 적용한다. 수집OFF여도 Worker cron은 만료 행 정리를 호출한다.
5. workers_dev=false, preview_urls=false, route/routes 없음으로 Worker를 올린다. 아직 외부 진입점은 연결하지 않는다.
6. 접근 코드 SHA·세션 서명 비밀·서로 다른 발행/안내 토큰 SHA를 등록한다. 값은 비공개로만 보관한다.
   secret 명령도 원격 새 버전 배포다. 실제 버전/vars/bindings/secret 이름·limiter namespace를 조회한다.
7. 접근 문 true·필수 비밀·수집OFF·R2 비공개를 확인한 뒤 별도 시험 Custom Domain만 연결한다.
8. HTTPS에서 미인증 asset/JSON 거부, 접근/로그아웃/만료·직접 경로, 수집OFF를 검사한다.
9. 합성 자료만 읽기/업로드를 켜 304/조건부 갱신 충돌/철회/복구·안내 전환을 확인한다.
10. 결과와 실제 요청/CPU/저장 사용량을 기록한다. 실제 값이 준비 예산/Free 범위와 맞지 않으면 중단·원인 확인한다.

권한 확대·유료 전환·기존 사이트 전환·실경기·외부 발송은 이 범위가 아니다.
실제 gate/바인딩/비밀 확인 실패 시 도메인을 연결하지 않는다. 연결 후 접근 제한 문제가 있으면 시험 경로를 해제한다.
실험 종료 뒤 자료/업로드 토글은 OFF로 돌리고 시험 자원을 보존한다. 자원 삭제를 완료로 가정하지 않는다.

## 5. 재현 명령과 산출물

[stage2 실행안](WS_ACCOUNT_READINESS_20261015.md)과 [고정 도구의 격리 지침](../ops/public-host-tooling/README.md)을 따른다.
비공개 검증 원본·작업 복사본·실행 계획·로그는 `.cache/ws-stage3-private/`에 있다. Git에는 비식별 영수증만 넣는다.

```text
python -B -S scripts/build_public_host_release.py build --frontend ops/public-host/examples/synthetic-dist --provenance ops/public-host/examples/synthetic-provenance.json --host-commit c07dc942030e5ec4f100f638d572239524cd327e --mode synthetic --output <새 출력>
python -B -S scripts/build_public_host_release.py check <새 출력>/release.zip
python -B -S scripts/check_public_host_config.py <검증 원본>
node <고정 Wrangler> deploy --dry-run --env-file <새 빈 env> --config <도구 복사본>/host/wrangler.deploy.json --outdir <후보 밖 출력>
```

패키지·설정의 `deployable=false`는 유지한다. 승인 후 본인 한정 합성 시험과 일반 공개 운영 합격은 별개다.
실제 R2/D1/cron/비밀/Custom Domain/브라우저/CPU/비용은 미검증이다. [현재 인계](WS_OPERATIONS_HANDOFF.md)의
Song 후속 자료·실기기·사람 검토 대기 상태는 이 준비로 해제되지 않는다.
