# WS-stage2 — Cloudflare 계정 확인과 첫 시험 실행안

2026-10-15. 기준 main `a217a61db449f2b9bb8a33b3145b69bf317b0f6f`, 선점 `6daf0d478a47546c53ceedae4ed3b523bdb297d9`.
사용자가 계정 확인을 요청하고 Codex 브라우저에서 로그인 완료를 알린 뒤 **계정 화면을 읽기만 했다**.
[합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6191027629) · [영수증](results/ops/ws_stage2_20261015.json).
기존 [준비안](WS_PRIVATE_STAGE_PLAN_20261015.md)의 미조회/도구 미고정 상태는 이 기록으로 갱신한다.

## 1. 계정에서 확인한 사실

조회 근거는 인증된 Cloudflare 대시보드의 아래 화면이다. 계정/회원 ID, 주소, 레코드 값, 결제 정보,
다른 도메인 정보, 원시 화면 덤프는 공개 기록에 넣지 않는다. UI 현재값은 미래 사용량 보장이 아니다.

- **Workers & Pages / Workers plans:** Free가 Current plan. 프로젝트0개, 오늘 요청0/100,000.
  10/1~10/15 표시 기간 요청0·CPU0ms·observability events0·build minutes0. 실제 시험 CPU는 미측정이다.
- **R2 / plans:** Get started with R2 가입 화면. 현재 결제 표시 $0, 월 $0 + 추가 사용량.
  가입 버튼은 누르지 않았다. 아직 R2를 활성화하지 않았으며 버킷 생성/실제 용량 검사는 하지 않았다.
- **D1 SQLite Database:** DB0/10, 오늘 읽기0/500만·쓰기0/10만, 저장0/5GB. DB 생성하지 않았다.
- **Members / Permission policies:** Entire account에 Super Administrator - All Privileges.
  이는 로그인 사용자의 UI 권한이며 CLI 토큰/실제 API 쓰기 권한 검증은 아니다. 토큰 조회/발급 없음.
- **대상 도메인 Domains overview / Overview:** zone Active·Free, DNS Full, 등록 상태 Active,
  No Workers connected. 기존 DNS 전체4행은 root A2개·검증용 TXT2개이며 시험용 추가 이름/와일드카드는 없었다.
  기존 루트/검증 레코드는 변경하지 않았다. 이 사실만으로 기존 사이트 전체 운영 구성을 확정하지 않는다.

## 2. 계정에 맞춘 실행 후보

**Workers Free를 유지한 작은 본인 시험을 우선 제안한다. 유료 Workers 전환은 지금 필요하다고 확인되지 않았다.**
무료 Worker의 호출당 CPU10ms 안에서 우리 접근 검증/JSON 처리가 동작하는지는 실계정에서 측정해야 한다.
한도를 넘으면 우선 작업량/설정을 검토하고 유료 전환은 다시 제시한다. 무료 보장은 하지 않는다.
이전 $5/$9.90 산정은 Paid 모델 가정이며 현재 계정 청구액이 아니다. 월 $10 준비 예산·수집/피드백 OFF는 유지한다.
R2 가입은 무료 포함량이 있어도 초과 과금·자동 갱신·약관 동의를 수반한다. 실제 가입은 사용자 확인 후 한다.
[공식 Workers 요금](https://developers.cloudflare.com/workers/platform/pricing/), [R2 요금](https://developers.cloudflare.com/r2/pricing/).

실제 변경 후보는 전용 Worker1개 + private R2 Standard1개 + 빈 D1 1개 + 별도 시험 호스트명1개다.
실제 이름/ID/주소는 비공개 실행 기록에서 정한다. 초기에는 workers_dev/preview_urls를 모두 false로 두고
공개 경로 없이 배포한 다음, 비밀/접근 토글 검사가 끝난 뒤 시험 호스트명만 연결하는 순서다.
D1은 수집 OFF여도 현재 검증된 설정 형식을 유지하기 위한 자원이며 migration/정리 cron을 함께 확인한다.

**경로 방안:** 설정의 route/routes를 모두 생략하고 workers_dev:false를 유지하면 Dashboard에서만 경로를
관리할 수 있다. 별도 Custom Domain을 연결하면 Cloudflare가 해당 이름의 DNS/인증서를 만든다.
따라서 경로 연결은 실제 변경 승인 대상이며 기존 root/검증 레코드 변경을 포함하지 않는다.
[Wrangler 설정 기준](https://developers.cloudflare.com/workers/wrangler/configuration/#source-of-truth),
[Custom Domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/).
현재 코드의 routes 거부 규칙을 바꿀 필요는 없다. Dashboard 경로는 설정 검사 대상 밖이므로 실제 연결 후 따로 검증한다.
vars는 파일이 기준이므로 Dashboard에서 바꾼 토글을 다음 배포가 덮어쓰지 않도록 후보 설정도 함께 갱신한다.

## 3. 실제 완료한 로컬 준비

- 별도 [도구 폴더](../ops/public-host-tooling/README.md)에 Wrangler4.151.0과 전이 의존성 lock을 고정했다.
  기존 호스팅 Miniflare 패키지/lock·운영 코드는 변경하지 않았다. Windows Node24.1.0/npm11.3.0.
- 공식 npm 설치91패키지, CLI 버전4.151.0 확인, 같은 날짜 npm audit의 알려진 취약점0.
- 우리 host `c07dc942030e5ec4f100f638d572239524cd327e` + 합성 화면 패키지13파일/108,993bytes 생성·검사.
  예시 화면의 111… 커밋은 가상값이며 Song 최종 화면 수신 증거가 아니다.
- 접근 문 ON, 수집/피드백 OFF, 업로드/자료읽기 OFF 설정 검사 통과.
- 빈 자식 프로필·빈 env 파일·keyring OFF·지표/오류 전송 OFF로 `deploy --dry-run` 종료0.
  도구가 표시한 51.49KiB(gzip12.55KiB)는 로컬 번들 크기이며 실제 업로드량이 아니다.
- dry-run이 host/.wrangler/tmp를 만들어 원본 설정 재검사에서 invalid_path가 발생했다.
  새 검증 원본과 도구 복사본을 분리하고 재실행했다. 원본 전후 검사 통과·원래16파일 SHA 일치.
  검사기를 완화하거나 임시 폴더를 배포 목록에 넣지 않았다.

자격증명/계정 자원 없이 실행했다. 패킷 차단이나 외부 통신0건은 검증하지 않았다.
이것은 합성 자료의 로컬 빌드 검사다. Cloudflare 배포·실행·CPU/응답시간·실제 브라우저 성공은 미측정이다.
패키지/설정 검사기의 deployable=false를 유지한다. 실제 운영 전체의 다른 모델 검토 조건도 별도다.

## 4. 재현 명령

Python3.12, 저장소 루트. 새 출력 이름을 사용하고 부모 .cache만 미리 만든다.

```text
python -B -S scripts/build_public_host_release.py build --frontend ops/public-host/examples/synthetic-dist --provenance ops/public-host/examples/synthetic-provenance.json --host-commit c07dc942030e5ec4f100f638d572239524cd327e --mode synthetic --output .cache/ws-stage2-synthetic-new
python -B -S scripts/build_public_host_release.py check .cache/ws-stage2-synthetic-new/release.zip
python -B -S scripts/check_public_host_config.py <검증원본>
```

ZIP은 새 검증원본에 풀고 `examples/wrangler.offline.example.json`을 host/wrangler.deploy.json으로,
`examples/collection-settings.example.json`을 public/collection-settings.json으로 복사한다(examples는 ops/public-host 아래).
접근 문만 각각 문자열 true/불리언 true로 맞추고 다른 기본 토글은 OFF를 유지한다.
복사/설정 후 검증원본을 검사하고 새 도구복사본에 바이트 그대로 복사한다.
그다음 [도구 README](../ops/public-host-tooling/README.md)의 격리 환경·빈 env·dry-run을 실행한다.
원본 재검사와 두 폴더 원래 파일의 SHA 일치를 확인한다. 실제 바인딩으로 교체하면 새 검사 기록이 필요하다.

## 5. 승인 후 진행할 한 단위와 종료 기준

1. **R2 가입:** 표시된 무료 포함량/추가 사용 과금과 약관을 확인하고 사용자 승인 또는 직접 조작으로 활성화한다.
   현재 로그인 완료나 $10 준비 예산을 가입 승인으로 확대하지 않는다.
2. **실자원 실행안 확정:** 별도 자원 이름/호스트명·사용자만 접근·실제 토큰 범위·월 비용 가정을 비공개로 고정한다.
   자원 생성, D1 migration/cron, Worker 업로드, 비밀 설치와 시험 경로 연결을 하나의 구체적인 실행안으로 제시한다.
   일반 공개·기존 사이트 교체·실경기 연결·실제 이메일 발송은 이 범위에 넣지 않는다.
3. **승인된 실제 시험:** 전용 private 자원 → 경로 없는 Worker → 접근 비밀/설정 확인 → 전용 HTTPS 경로 순서다.
   미인증·직접 asset/JSON 거부, 로그인/로그아웃·만료, 수집 OFF를 확인한 뒤 승인된 합성 파일로 읽기/업로드를 켠다.
   304/412/삭제/복구·발행 중단/안내·실제 CPU/사용량을 기록한다. 비밀의 CLI 설정도 원격 변경이다.
4. **완료 기준:** 기존 사이트 영향 없이 본인만 접근, 수집/피드백 없음, 합성 업로드→읽기→철회→복구,
   실제 배포 버전/설정/파일 SHA와 사용량 증거가 있어야 실제 시험 완료다. 이번 WS-stage2에는 해당하지 않는다.

R2 가입만으로 다음3단계를 자동 승인하지 않는다. 고정 도구 명령은 준비됐지만 실계정 설정·경로가 아직 없어
실제 배포 명령을 실행하지 않았다. 받은 첫 팩은 이전 개발 연결 근거로 유지하며 mail #18의 최종 공개 화면·
unsupported 예시·스키마2항목·발행 규칙/업로더는 별도 수신 대기다. 계정 시험 준비에 Song 답변은 필요하지 않다.
팀원 코드/프로세스/배포 접근, 기존 Sites/영상팩 변경, 외부 회신/메일 발송은 하지 않았다.
