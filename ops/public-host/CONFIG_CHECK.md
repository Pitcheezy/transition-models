# 배포 후보 오프라인 설정 검사 — WS-ops4d

검사기는 **로컬 파일만 읽는다**. 계정 조회, 명령 실행, 압축 해제, 파일 수정, 배포는 하지 않는다.
[패키지 검사](RELEASE.md)에 이어 실제로 제공할 폴더의 바이트·경로·설정 일치를 확인한다.
어떤 모드에서도 `deployable=false`이며 실운영 합격이나 배포 승인을 의미하지 않는다.

## 고정 폴더 구조

~~~text
candidate/
  release-manifest.json
  host/
    worker.mjs ... (manifest의 운영 파일 12개, notice.mjs·access.mjs 포함)
    migrations/0001_telemetry.sql
    wrangler.deploy.json
  public/
    index.html ... (manifest의 공개 화면)
    collection-settings.json
~~~

manifest에 적힌 12개 운영 파일에는 migrations/0001_telemetry.sql·notice.mjs·access.mjs가 이미 포함된다.
추가 파일은 `host/wrangler.deploy.json`과 `public/collection-settings.json` 두 개만 허용한다.
manifest의 SHA/바이트를 재검사하며, 공개 폴더에 목록 밖 영상·메모 등이 하나라도 섞이면 거부한다.
검사한 폴더에 파일을 추가하거나 고치면 다시 검사해야 한다. 동시 파일 변경 방지나 서명 인증 도구는 아니다.

`wrangler.deploy.json`을 기준으로 main은 `worker.mjs`, assets는 **`../public`**이다.
기존 소스 예제의 `./public`을 그대로 복사하면 패키지에서는 다른 폴더를 가리키므로 거부한다.
운영자 설정은 host에 있고 공개 수집 안내 파일에는 불리언3개(`telemetryEnabled`·`feedbackEnabled`·`accessGate`)와 보관일만 들어간다.

## 실행

먼저 신뢰한 고정 커밋·공개 빌드로 새 ZIP을 만들고 RELEASE.md의 check를 통과시킨다.
그 ZIP을 별도의 새 폴더에 풀어 내용이 같은지 유지한다. 검사 도구가 ZIP을 직접 풀지는 않는다.
그다음 실제 배포에 사용할 설정 두 파일을 위 경로에 마련하고 저장소 루트에서 실행한다.

~~~text
python -B -S scripts/check_public_host_config.py PATH_TO_CANDIDATE
~~~

Python3.12 표준 라이브러리만 사용한다. 성공은 종료0, 입력 거부는 종료2이며 JSON을 출력한다.
입력 URL·경로·계정·비밀값을 오류에 반사하지 않는다. 성공 결과에는 설정의 SHA만 기록한다.
출력 저장이 필요하면 **후보 폴더 밖**에 저장한다. 폴더 안에 영수증을 추가하면 목록 밖 파일이다.

`examples/wrangler.offline.example.json`과 `examples/collection-settings.example.json`은
합성 검사 연습용이다. 가상 버킷·DB 식별자와 모든 기능 OFF를 담으며 실계정 존재를 주장하지 않는다.
이 예제가 통과해도 Cloudflare에서 실행할 수 있다는 뜻이 아니다. 기존 Sites 설정을 가져오지 않는다.

## 시험 발행 제한

선택적인 `PUBLISH_KEY_SCOPE`·`PUBLISH_EXPIRES_AT`는 동시에 지정해야 한다. [정확한 형식·옛 runtime 거부·한계](PUBLISH_SCOPE.md)를 따른다. 설정이 있으면 runtime 다섯 파일을 신뢰한 현재 체크아웃과 CRLF→LF 정규화 후 대조한다. 오프라인 검사는 실제 현재 시각의 만료 판단이나 배포/접속 승인이 아니다.

## 관측 로그 설정

`observability`는 선택 항목이다. 기존 생략 설정도 통과하지만, **로그 유지 확인을 뜻하지 않는다.**
고정 Wrangler4.151.0은 배포 설정에서 이 항목을 생략하면 실제 Worker의 observability를
`enabled:false`로 갱신한다(설치된 `wrangler-dist/cli.js`의 배포 후 설정 PATCH).
현재 저장 로그를 유지하려면 실제 배포할 설정에 명시하고, 그 파일의 SHA로 검사해야 한다.
검사 뒤 배포본에만 로그 설정을 덧붙이지 않는다.

지원하는 부분집합은 다음과 같다. 이는 설정의 형식 검사이며 로그 수집 정책을 자동으로 선택하지 않는다.

- 루트 `enabled`와 `logs.enabled`는 실제 JSON 불리언으로 반드시 지정하고 값이 같아야 한다.
  생략에 따른 기본값이나 서로 충돌하는 override는 받지 않는다.
- 루트 선택 필드: `head_sampling_rate`, 불리언 `redact_query_string`, `traces`, `issues`.
- `logs` 선택 필드: `head_sampling_rate`, 불리언 `invocation_logs`·`persist`.
- `traces`가 있으면 불리언 `enabled`가 필수이고 `head_sampling_rate`·불리언 `persist`는 선택이다.
- `issues`가 있으면 불리언 `enabled`만 허용한다.
- 샘플링은 0~1의 유한 JSON 숫자만 받는다. 문자열·불리언·NaN·무한대는 거부한다.
  알 수 없는 키와 모든 `destinations` 설정은 거부하며 외부 로그 전송을 이 검사에 포함하지 않는다.

Logs100%·호출 기록/저장 ON·Traces/Issues OFF를 명시하려면 다음 항목을 사용한다.
이는 현재 기본값을 바꾸는 예제가 아니라 운영자가 선택한 후보에 붙일 설정 구조다.

```json
{
  "observability": {
    "enabled": true,
    "head_sampling_rate": 1,
    "logs": {
      "enabled": true,
      "head_sampling_rate": 1,
      "invocation_logs": true,
      "persist": true
    },
    "traces": {"enabled": false},
    "issues": {"enabled": false}
  }
}
```

통과 결과에는 `observability_config`만 추가된다. `deployable:false`는 유지하며,
실제 배포 후 활성 설정·요청 로그 저장 여부·비용/보관 정책은 따로 확인해야 한다.
서버 로그는 우리 화면의 이용 기록/피드백 토글과 별도다. 로그 설정이 있더라도
운영 코드에서 비밀·개인정보를 기록하지 않는지 검토하는 일을 대신하지 않는다.

## 지원 범위

- JSONC/TOML이 아닌 엄격한 JSON만 지원한다. 중복 키·주석·각64KiB 초과를 거부한다.
- 한 환경의 설정만 받는다. env 오버라이드와 임의 top-level 필드·routes 등은 지원하지 않는다.
  도메인 라우팅은 별도 계정 작업이며 이 제한형 검사를 일반 Wrangler 검증기처럼 사용하지 않는다.
- 테스트한 compatibility_date, Worker 우선 처리, ASSETS, SPA fallback, 기본 공개 엔드포인트 비활성 확인.
- private R2와 D1의 **binding 이름/형식** 확인. 실제 private 여부·계정·DB 존재는 확인하지 못한다.
- 업로드/수집 limiter 이름·주기·서로 다른 namespace 확인. 다른 Worker와의 충돌은 계정에서 별도 확인.
- 다섯 서버 토글(읽기·업로드·통계·피드백·접근 문)은 문자열 true/false만, 공개 수집 설정은 정확한 불리언3개·정수 보관일1개만 허용한다.
  공개 설정 `accessGate`는 `ACCESS_GATE_ENABLED`와 같아야 한다(WS-access3: 게이트가 수집 경로도 보호하므로 그때만 같은 출처 쿠키를 보낸다).
  접근 문 세션 길이 ACCESS_SESSION_SECONDS는 1~604800이며, 접근 문이 켜진 설정은 READ_ORIGIN이 비어 있어야 한다(같은 출처 쿠키).
  공개 설정과 서버 통계/피드백/보관일이 같아야 한다. 이전 enabled만으로 켜는 설정은 수용하지 않는다.
- 수집 OFF여도 기존 행은 만료되어야 하므로 UTC03:17 정리 cron을 반드시 요구한다.
- origin은 정규화된 HTTPS DNS/IPv4/IPv6의 제한된 형식만 받는다. 경로·사용자 정보·쿼리·fragment,
  대문자·명시적 기본443포트·IPv6 zone ID·xn-- IDNA 라벨은 지원하지 않는다.
  비기본 포트1~65535는 허용한다. DNS 등록·TLS·접속 가능 여부는 별도다.
- 비밀 변수는 설정 파일에 넣지 않는다. PUBLISH_TOKEN_SHA256·TELEMETRY_RATE_SECRET·NOTICE_TOKEN_SHA256·
  ACCESS_CODE_SHA256·ACCESS_SESSION_SECRET은 별도 비밀 저장소에서 설치할 이름이며 설치 여부는 검사하지 못한다. 값은 문서/로그/이슈에 쓰지 않는다.

실제 화면이 collection-settings.json을 읽어 UI에 넘기는지, 실제 배포가 검사한 설정/바이트를
사용하는지는 **미검증**이다. 환경 변수나 배포 인자로 나중에 덮어쓰면 이 검사 결과의 범위 밖이다.
D1 migration·백업·cron 실행, 실제 CDN·브라우저·부하, Song 계약·공개 권리도 별도 확인한다.

## 확인 결과

~~~text
python -m pytest tests/test_public_host_release.py tests/test_public_host_config.py -q
~~~

신규 설정 검사66건 및 기존 패키지58건을 포함한다. 독립 Codex는 수정 전64건을 통과시킨 뒤
Python과 Node URL 파서가 다르게 처리하는 zone ID·잘못된 punycode 두 사례를 발견했다.
두 형식을 제한형 정책에서 거부하고 회귀2건을 추가했다. 사람 검토·Claude 검증으로 부르지 않는다.
합성 CLI 영수증은 `docs/results/ops/ws_config_check_20261012.json`에 별도로 기록한다.
