# 공개 앱 연결 교체 결과 — 2026-11-02

## 현재 판정

사용자가 기존 `app.pitcheezy.com/*` Route의 대상을 새 시험 인수 서버로 저장한 뒤, 공개 app에서 Song c47 빌드 원본과 일치하는 응답을 확인했다. **HTTP 검사 24/24·공개 앱 iPhone 두 브라우저 사용자 확인·저장 서버 로그 24/24 대조가 모두 통과해 공개 app 전환 인수를 완료했다**(11/2 밤, 아래 "저장 로그 대조 완료" 절). 10/26 미대조2건·11/1 8단계 로그·용량·접근 OFF·형 전체 소스 검토는 이 인수에 포함하지 않는다.

- 웹 소스: `c47fe6cb78479362e7250141da946814cc33bd31`
- 자료 생성 소스(전달자 선언): `cb1cfa8f759fd77adc75595316a389208c752dba`
- ZIP SHA-256: `3c3b8006b892872bfff3423e2bd6ba49ea3de17ee92fbecef07e0b076bc8da51`
- 기존 관리 버전: `6d652d4b-7d3c-4897-aefd-f37d0edce50c`
- 새 관리 버전: `5999cf0d-4f18-4d43-bcd6-320e04860369`

버전은 실행 전에 관리 조회로 고정한 기대값이다. 각 요청의 실제 서버 버전은 로그 대조 뒤에만 확정한다. 사용자 편집창 캡처·Save 완료 응답과 기대 바이트 확인이 현재 Route 전환 근거이며, Codex가 대시보드 저장을 수행한 것은 아니다.

## 수행과 근거

[사전 확인](results/exhibition_20261101/stage5-dashboard-preflight-20261102.json) → [실제15분 입력·dry-run](results/exhibition_20261101/stage5-ready-20261102.json) → [24요청 결과](results/exhibition_20261101/stage5-cutover-client-result-20261102.json).

| 항목 | 결과 |
| --- | --- |
| 실행 시각 | 11/2 22:21:54.576~22:22:01.417 KST, 6.841초 |
| 서비스 요청·판정 | 24요청·24/24판정, 재시도0, 복구0 |
| 비로그인 | 지정3경로401·접속제한 헤더 |
| 업로드 | OFF 확인 HEAD503 |
| 로그인 후 파일 | 형 정적4·자료6 및 보조설정1 원본바이트 일치 |
| 전시 범위 | 849843·2026-09-30, 지정 제외3주소404 |
| 종료 | 로그아웃204 |
| 요청 원장 | 24개 시작/완료·응답Ray 보존, 비공개 |
| 저장 로그 | 11/2 23:29 KST export 수신, 서버 HTTP 이벤트26 중 원장24건 전부 일치·추가2건 집계(아래 절) |
| 공개 app 실제 폰 | 사용자 “Safari·Chrome 모두 정상”, 상세 버전·정확 시각 미제공 |

실행 도구는 검토된 `7ec2e69733cfc651435a3ca10aeabf4a794e7475`의 `run-exhibit-stage5.mjs`이며 고정 SHA·입력SHA·15분 창을 실행 직전에 재대조했다. 코드 변경·추가 배포·안내 재시험·새 자격 생성은 없다. 로그100%/Invocation/Persist는 양쪽 사용자 현재 확인으로 기록하며 도구가 직접 읽었다고 쓰지 않는다. 공개 영수증은 별도 에이전트가 읽기 검토했고, 비공개 원장 재실행·독립 원격검사는 하지 않았다.

## 폰 확인 완료·남은 로그 대조

1. **완료(사용자 보고):** iPhone Safari/Chrome 기존 app 탭 새로고침/같은 코드 재로그인과 새 비공개 탭 홈→서비스 열기→코드→하루/추천/존/투구 이동 질문에 “Safari·Chrome 모두 정상” 응답. 이전 시험 주소 확인과 별개이며 도구 직접 관찰은 아니다. 상세 기기/OS/브라우저 버전·실제 관측 시각은 미제공이다.
2. 새 서버 Observability: **11/2 22:20~22:24 KST**를 JSON으로 비공개 내보내고, 기록한24요청과 Ray·방식·경로·status·시각·실제버전을 대조한다. 사용자 폰 등 추가 행은 별도 집계하며 자르거나 가까운 시각으로 대신 연결하지 않는다.

기존 `correlate_exhibit_stage34_logs.py`의 `Sources`, `journals`, `correlate`는 일치 판정 재사용이 가능하다. CLI는 단계5 옵션이 없으므로 단계4 폴더로 가장하지 않는다. 현재 단계5 `cutover/requests`를 `journals`로 읽고24행·고정 버전/실행 결과를 대조한 뒤 같은 고유Ray 규칙을 적용한다. 자료·원본 로그는 Git에 넣지 않는다.

남은 로그 대조가 끝나기 전 최종 전환 인수 완료로 쓰지 않는다. 기존133/133·10/26 미대조2건·30/50명 용량·형 전체 소스 검토·클립 수신·발신/PR 정리는 별개다. 현재 앱은 코드ON을 유지하며 기존 서버·자료·시험주소를 보존한다. 같은24요청 실행을 반복하지 않는다.

## 저장 로그 대조 준비 — 2026-11-02 밤 (Claude)

사용자 지시로 Claude가 Codex 인계를 이어받았다. 기준 커밋 `e335974`. 원격 요청·Cloudflare·자격·기존 자료·팀원 저장소 변경은 0이다.

**export 미수신.** 이 PC의 Downloads·Desktop·Documents·OneDrive와 D: 비공개 검사 폴더에서 2026-11-02 22:24 KST 이후 생성된 `logs-*.json`·Observability export를 찾지 못했고, 회차의 `server-log-exports/`는 비어 있다. 11/2 17:26·17:27 KST에 받은 두 파일은 이미 133/133 대조를 마친 단계3/4 export다. 따라서 **24건 실제 대조는 수행하지 않았다.** 다른 기기에서 내보냈다면 그 파일을 회차 `server-log-exports/`에 넣고 이름을 알려 주면 된다(원본 보존, 복사 전후 SHA 확인).

**원장 사전 검증(오프라인, 서버 증거 아님).** `cutover/requests`를 phase `stage5-cutover`로 읽어 24개 시작/완료 쌍·연속 시퀀스·완료 24·고유 응답 Ray 24·버전 핀 `5999cf0d-4f18-4d43-bcd6-320e04860369` 단일, `cutover/result.private.json`의 passed·service_requests 24·version_pin·input_sha256이 `cycle.private.json`과 일치함을 확인했다. 창 13:21:54.576Z~13:22:01.417Z, GET20/HEAD2/POST1/DELETE1, 상태 200×14·204×1·307×1·401×3·404×4·503×1, 경로 18종. [사전 검증 영수증](results/exhibition_20261101/stage5-ledger-precheck-20261102.json)(8,965bytes, SHA `f68ff257a9fe5310ae4830a9c3d67b4069fa64aa5077c9b35a17ffa58430e6fe`)에는 집계·버전·입력 파일 SHA만 있고 호스트·Ray·경로·로컬 경로는 없다.

**실행기.** `scripts/correlate_exhibit_stage5_logs.py`(137줄, SHA `9bc5a771c70c65570d0b5852ed520b303bce2ff3191bfc951938967419e3db68`)는 기존 `correlate_exhibit_stage34_logs.py`의 `Sources`·`journals`·`correlate`·`inside_private`를 그대로 가져와 쓴다. 고유 응답 Ray만으로 연결하고 허용오차 기본 0, 시간·경로 대체 연결 없음, 사용자 폰 등 추가 서버 행은 `server_unmatched_events`/`extra_server_events_not_reassigned`로 집계만 하며 자르거나 재배정하지 않는다. `--ledger-only`는 위 사전 검증 영수증을, 전체 모드는 schema `pitcheezy-stage5-server-log-correlation-v1` 영수증을 쓴다. 출력 파일이 이미 있으면 거부한다. `tests/test_exhibit_stage5_logs.py`(SHA `ae92a1cc07b8ab7a7ebd1e45a6edd42e921fc7de72b303051146103977fc8a91`) 13 통과, 기존 stage34 테스트 27·체크리스트 8·ruff 통과. 시스템 `python -I`에는 pytest가 없어 테스트는 `.venv/Scripts/python.exe -I -B -m pytest …`로 돌렸고 실행기 자체는 표준 라이브러리만 쓴다.

**다른 모델 검토.** 작성 Claude Fable 5.1, 검토는 다른 Claude 모델(opus 지정 에이전트)이 적대 입력으로 수행해 **APPROVE, P1/P2 0건**. 중복 Ray·겹친 export 2개·같은 export 2회·객체형 export·시퀀스 공백·service_requests 25·허용오차 5001/-1·±1ms 경계·completed 저널 누락·provider id 중복·NaN·누락 파일을 모두 거부했고, 합성·실제 출력에서 호스트·Ray·경로·IP 0건을 확인했다. 남긴 P3 6건은 수정하지 않고 기록한다: ① 비정상 timestamp의 OverflowError·깊은 중첩 JSON의 RecursionError는 traceback으로 exit 1(거짓 합격 아님, exit 코드 계약만 어긋남) ② cycle/result의 schema·phase 값 미검사(핀·입력SHA 일치는 검사) ③ `cutover/requests/started.private.json` 헤더(request_limit·expected_deployment_version) 미대조 ④ 실제 저널 형태(top-level finished_utc/status/ray)는 실제 dry-run으로만 검증·테스트 미포함 ⑤ `--ledger-only`에서 허용오차 값 미검증·`--output` 위치 무제한 ⑥ 상속된 `inside_private`의 심링크 해석. 코드를 바꾸면 다른 모델 재검토가 필요하다.

**export 도착 후 명령(원격 요청 0, 1회만).**

```text
python -I -B scripts/correlate_exhibit_stage5_logs.py --private-root D:/pitcheezy_exhibit_check --round "<회차 폴더>" --logs "<회차 폴더>/server-log-exports/<export>.json" --output docs/results/exhibition_20261101/stage5-server-log-correlation-20261102.json
```

exit 0이면 24/24 matched·malformed 0이다. exit 1이면 영수증의 `requests[].result`/`problems`를 그대로 보고하고 원인 추정으로 메우지 않는다. 원본 export·비공개 연결 기록은 Git 밖에 두고, 영수증은 집계·버전·파일 SHA만 담는다. 합격 뒤 CHECKLIST 공개 버전 줄·이 문서·인계·미발신 reply2를 갱신한다.

## 저장 로그 대조 완료 — 2026-11-02 밤 (Claude)

사용자가 새 전시 Worker Observability를 JSON으로 내보냈다(파일 생성 2026-11-02T14:29:00Z = 23:29 KST, 131,330bytes, SHA-256 `4d767bbaf0a0e30e4c4241f4915ae7772fea1a950c273c9f5b3049d700feaf89`). 원본은 사용자 업로드 위치에 두고 회차 `server-log-exports/`에 복사해 전후 SHA 일치를 확인했다. 위 명령을 그대로 1회 실행했고 원격 요청은 없다.

| 항목 | 결과 |
| --- | --- |
| 서버 레코드 | 26, 전부 HTTP, malformed 0, 비HTTP 0 |
| 서버 버전 | 26건 모두 `5999cf0d-4f18-4d43-bcd6-320e04860369` |
| 원장24건 | **24/24 matched**: Ray 헤더·메타 일치, provider id 고유, 방식·경로·쿼리·상태 일치, 시각이 클라이언트 구간 안(허용오차 0), outcome ok, 잘림 없음 |
| 누락·중복·불일치 | 0 / 중복 Ray 그룹 0 / 중복 provider id 그룹 0 |
| 추가 서버 이벤트 | 2건, 재배정 없음. 자동 원장 종료 뒤 13:22:54.778Z·13:23:34.098Z의 모바일 UA 정적 경로 GET 401(코드 화면). 사용자 폰 확인 시각과 부합하며 공개 영수증에는 개수만 둔다 |
| 서버 로그 시각 범위 | 13:21:55.224Z~13:23:34.098Z |

[대조 영수증](results/exhibition_20261101/stage5-server-log-correlation-20261102.json)(24,559bytes, SHA `960458c4b99b5831a4f9f602a94a96afce1ba65b7331cf88981d1d78ad07766e`)은 schema `pitcheezy-stage5-server-log-correlation-v1`이며 호스트·Ray·provider id·경로·로컬 경로를 담지 않는다. 입력 무결성은 원장 저널48·cycle·result·export의 바이트/SHA로 기록했다.

이로써 단계5의 세 조건(HTTP 24/24, 공개 app 실기기 사용자 확인, 요청별 저장 로그)이 모두 충족되어 **공개 app 전환 인수를 완료**로 기록한다. 관리 핀이던 새 버전은 24건 전부에서 실제 서버 버전으로 확인됐다. HTTP→HTTPS 301은 이번 원장에 없고(307 1건은 Worker 응답으로 일치), 카메라 QR 스캔 동선·접근 코드 OFF·10/26 미대조2건·11/1 8단계 로그·30/50명 용량·형 전체 소스 검토는 이 인수에 포함하지 않는다.

## 11/3 교수님 시연 — 접속 코드 단계 판단 (사용자 결정 대기)

질문: 내일 교수님께 데모를 보일 때 "서비스 열기 → 접속 코드" 단계를 지우는 편이 나은가. **권장: 지우지 않는다.** 설정·배포·Cloudflare는 바꾸지 않았다.

- **지우려면 재배포다.** 게이트는 `ACCESS_GATE_ENABLED`가 "true"일 때만 켜지고(access.mjs:34) 실행 중 끄는 스위치가 없다(R2 안내 상태는 503 안내만 켠다). vars를 바꾸면 보조 정적 `collection-settings.json`의 accessGate도 맞춰야 설정 검사를 통과하므로(host_config.py:356) 설정 SHA와 클라이언트 설정 SHA가 모두 바뀌는 새 버전이 되고, 되돌릴 때 또 한 번 배포가 든다. PLAN.md "접근 코드 OFF는 별도 공개 결정"·"접근 제한 OFF는 승인되지 않았다", 실행 계획 "11/21 코드 없는 관람은 별도 공개 승인과 인증 없는 QR 동선 확인 후에만"과 충돌한다. 방금 24/24로 인수한 `5999cf0d` 위에 미검증 버전 2개(OFF·복귀)를 얹게 되고 아직 남은 저장 로그 대조의 기준 버전과도 어긋난다.
- **노출.** OFF면 URL만 알면 HTML·JS·`/v1` 자료 JSON이 누구에게나 열린다(DATA_READ_ENABLED true). 받은 빌드 index.html에 robots meta가 없고 robots.txt도 없으며 게이트 OFF 자산엔 noindex 헤더가 붙지 않아(gateway.mjs:345) 색인·크롤러·Free 플랜 하루 100,000요청 한도에 노출된다.
- **배포 없이 같은 효과.** 발표 기기의 일반(비시크릿) 브라우저 탭에서 시연 전 60분 이내(권장 10분 이내)에 `https://app.pitcheezy.com/?game=849843`을 열어 코드를 입력하면 쿠키 `__Host-pz_viewer`(Path=/, Max-Age=3600, HttpOnly, SameSite=Strict, Secure; access.mjs:47,104)가 발급된다. pitcheezy.com 홈의 "서비스 열기"는 target 없는 일반 링크이고 pitcheezy.com→app.pitcheezy.com은 등록 가능 도메인이 같은 https 최상위 이동이라 Strict 쿠키가 전송되어 **코드 화면 없이 `?game=849843` 경기 화면으로 들어간다.**
- **세션 수명.** 로그인 시각+3600초로 고정되며 활동으로 연장되지 않는다(access.mjs:61,93). 만료 뒤 10초 폴링이 401을 받으면 형 앱은 "접근 확인이 필요해요. 페이지를 새로고침해 다시 접속해 주세요." 알림을 띄우고 자동 복귀하지 않는다(받은 번들 판독: 자동 reload·리다이렉트·/_access 호출 없음). 복귀는 새로고침 → 코드 입력 → 303 "/" 목록 → 849843 선택으로 수 초다. 시연이 50분을 넘길 것 같으면 쉬는 시점에 미리 새로고침·재로그인한다.
- **주의.** 시크릿 탭·다른 브라우저·교수님 본인 폰의 QR은 쿠키가 없어 코드 화면이 뜬다(코드를 알려 주면 통과, 입력 뒤 "/" 목록이라 경기를 한 번 더 누른다). 로그인 POST는 IP별 일일 제한이 있어 반복 재로그인 시 429가 날 수 있다(한도 값 미확인). **사전 로그인 뒤 홈→서비스 열기의 무코드 진입 경로는 아직 아무도 실기기로 관측하지 않았다**(11/2 사용자 확인은 새 비공개 탭에서 코드를 입력한 경로). 시연 전 발표 기기에서 리허설 1회가 필요하다.
- **대안.** `ACCESS_SESSION_SECONDS` 상향(상한 604800) 재배포도 같은 승인 등급이며 짧은 시연엔 불필요하다. 현장 인터넷이 없으면 폰 핫스팟이 1차 대안이고, 로컬 리허설 도구 `rehearse-exhibit-host.mjs`는 검사 뒤 서버를 정리하는 자동 검사용이라 상시 시연 서버가 아니다. 오늘 밤 공개 앱에서 홈→서비스 열기→코드→9/30 하루→추천/존→투구 이동 화면을 녹화·캡처해 두는 편이 현실적이다.
- 다른 Claude 모델(opus 지정 에이전트)이 위 근거를 파일 줄 단위로 재확인해 반박을 시도했고 결론은 유지됐다. 정정 2건(무코드 진입 경로 미관측, accessGate 일치는 오프라인 검사기 조건)을 위에 반영했다.
