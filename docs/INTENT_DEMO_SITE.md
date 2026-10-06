# Pitcheezy 홈·최종 서비스 콘셉트 — 2026-10-05

사용자가 요청한 최종 제품의 화면을 홈과 분석 서비스로 나눠 구현했다.
기존 CV 관측과 M3 리포트는 별도 화면에 보존했다. 실제 영상·저장 관측과 설명용
추천·확률·선수/감독 평가를 구분하며, 모델 통합 완료나 완성률 95%를 주장하지 않는다.

## 실행·배포

- 공개 홈: https://pitcheezy-pitch-studio.sritone723.chatgpt.site
- 분석 서비스: 위 주소의 `/service.html`
- 실제 관측·검증: `/report.html#analysis`, `/report.html#validation`
- 배포 소스: `7cf49c756e07ecf6bd1a6f110cf70d49f3c2e574`, 배포 상태 `succeeded`.
- Sites project: `appgprj_6ac3665aa5048191ac2b5a012b2c7010` (기존 사이트 갱신).
- `web/pitch-studio/`는 배포 정적 파일 사본이다. CDN·외부 폰트·API·프레임워크가 필요 없다.
- 이전 `/#analysis` 링크는 서비스로, `/#validation`과 `/#story`는 기존 리포트로 이동한다.
- `pitcheezy.com`은 구매 확인, DNS/SSL 연결 대기다.

```bash
python -m http.server 8786 --bind 127.0.0.1 --directory web/pitch-studio
```

http://127.0.0.1:8786/ 을 연다. 서버 종료는 Ctrl+C. 로컬 index.html도 직접 열 수 있다.

## 시연 동선

1. 홈: 컵스 대 파드리스 실제 기록 리플레이로 시작한다. `미트 위치 보기`는 정확한
   판독 정지 장면으로 바꾸고 저장된 한 점을 표시한다. 재생 중에는 점을 숨긴다.
2. 분석 스튜디오: 투구 전 예측 → 투수 실행 → 타자 대응 → 교체 판단을 누른다.
   네 시나리오는 제구 이탈·좋은 타격·교체 검토·유리한 공을 놓친 타격이다.
   각 시나리오의 카운트·이닝은 설명용이며 배경 영상의 경기 상태와 별개다.
3. 예상 목표는 예시 표적, 실제 미트 관측은 저장 좌표다. 두 모드를 구분한다.
   좌타자의 몸쪽/바깥쪽은 포수 시점 격자이며 중계 영상과 좌우가 반대다.
   예시 표적의 화면 위치는 설명용 배치이지 영상으로 추정한 공간 좌표가 아니다.
4. 실제 관측 리포트: 39구 탐색·공개/숨김·27좌표/12기권과 기존 M3 근거를 보여준다.
5. 발표에서는 “우리가 만들려는 최종 사용자 흐름이며, 현재 검증한 부분은 영상의
   미트 관측과 사람 표시 비교입니다. 예측과 선수·벤치 평가는 연결할 화면입니다”라고 설명한다.

미트와 공의 측정 평면이 달라 두 x 차이를 제구 오차로 계산하지 않는다. 실시간 분석,
자동 추적·동기화, 투수 의도 검증, 책임 배분, 교체 실책의 인과 판단은 아직 완료되지 않았다.
실제 리허설의 Song 화면 6항목 확인도 별도 대기다.

## 실제 경기·영상 출처

로컬 frozen `data/raw/mlb_video/{gamePk}/feed.json`의 날짜·팀·구장·선수를 확인했다.

| 용도 | 경기 | 날짜·대회 | 구장 |
|---|---|---|---|
| 시연 849843 | Chicago Cubs @ San Diego Padres | 2026-09-29 NL Wild Card Game 1 | Petco Park |
| 평가 849845 | Philadelphia Phillies @ Atlanta Braves | 2026-09-29 NL Wild Card Game 1 | Truist Park |
| 평가 823407 | Tampa Bay Rays @ Philadelphia Phillies | 2026-09-26 정규시즌 | Citizens Bank Park |

대표 시연은 Michael King 대 Pete Crow-Armstrong. 평가 대표는 Chris Sale 대 Bryson Stott,
`849845:10:4` (2회 초). 내부 키는 유지하고 사용자에게 경기명을 먼저 보여준다.

이번 홈의 MLB 영상 공개는 사용자가 명시적으로 승인했다. 기존 공개 자료에서 MLB 화면을
제외했던 지침은 이번 추가 홈페이지 미디어에 한해 변경됐다. 기존 발표 장표는 그대로다.
새 다운로드 없이 이미 추출한 원본 JPEG 각 61장으로 두 개의 약 3.053초 무음 MP4를 만들었다.
H.264/yuv420p/faststart, 1280×720, 20000/1001fps. 자르기·리사이즈·원본 시간 간격 변경 없음.
원본 122장 모두 창 manifest의 SHA256과 일치했다. 포스터는 원본 바이트 복사다.

[미디어 출처·SHA256](results/mlb_p0/pitch_studio_media_provenance_v1.json)에 원본 URL,
프레임 인덱스·시각·점·인코딩·모든 입력 해시를 기록했다. 홈/서비스는 `849843:1:3`을 사용한다.
`849843:2:5` 기권 클립은 재사용 자산으로만 보존하며 현재 화면에서 재생하지 않는다.
실제 점 (571, 372.5)은 1280×720 판독 프레임 3084에서만 표시한다. 시각 51.4514초는
원본 영상의 프레임 시각이며 사이트의 공개 시점 정책을 대신하지 않는다.

## 우리 쪽 파일 수신 준비

[응답 수신 도구](PITCH_STUDIO_RECEIVER.md)를 추가했다. `/receiver.html`에서
전달 파일을 열거나 합성 연결 검사를 할 수 있다. 실제 서버 호출·자동 업로드는 없다.
34 Node 테스트를 기존 사이트 검사 명령에 포함했다. 실제 팀원 응답과 영상 대응 확인은 대기다.

## 실제 서비스 연결 계약

동료 저장소는 읽기 전용으로 확인했다.

- `SongRoute/pitcheezy`, `demo/ws-2026@9c3018913780cde2d12db522c2a420a6e283db7c`.
- 구형 Observer 비교 기준 `main@70aa5499eb261e57c85c5c54e84ea27f869dae50`.
- 근거: `watch_along.py`, `WatchAlong.tsx`, `demo_precompute.py`,
  `docs/contracts/event-analysis-v1.md`, `inning-decision-api-v1.md`, `inning-result-v1.md`.

| 화면 | 실제 연결 대상 | 현재 한계 |
|---|---|---|
| 경기·선수·투구 전 추천 | GET `/api/watch/games`, `/api/watch/{game_pk}` | `pre.recommendation.candidates[].detail.probability`는 구종 선택 비율 |
| 투구 후 공개 | GET `/api/watch/{game_pk}/reveal/{index}` | 실제 결과·위치·WE 변화, 책임 판정 아님 |
| 결과 확률 | 별도 결과 확률 계약 필요 | `/watch`에는 없음. 구형 Observer 확률을 혼합하지 않음 |
| 투수·타자 분석 | `event-analysis-v1` | 의도 근거가 없으면 전략·실행 null. 결과 잔차는 타자 실력/책임 아님 |
| 유지·교체 | POST `/api/inning-decisions/{id}/resolve`, `inning-result-v1` | 조건부 유지 전망. replacement unavailable, value_pp null |
| 미트 관측 | 우리 `IntentEstimate v1` | 투구 키로 연결, null을 0으로 바꾸지 않음 |

구형 Observer의 10종은 ball/strike/foul/out/single/double/triple/home_run/hbp/double_play다.
우리 구형 ten-class의 Strike에는 foul이 포함되므로 독립 파울 확률로 변환하지 않는다.
`preview-data.js`는 10종을 갖춘 **합성 설명용 분포**이며 `source_kind=illustrative`,
`model_connected=false`, `causal_attribution=false`다. 어떤 기존 모델 출력도 가장하지 않는다.
교체 수치도 수비 팀의 승리 전망을 가정한 예시이며 동료의 조건부 유지 전망과 의미가 같지 않다.

다음 한 작업 단위: 동료의 849843 한 타석 watch/reveal 실제 응답, 모델 식별자·생성 시점·SHA256을
확보한다. 투구 키와 CV 연결, 공개 전후 정보 분리, 누락 처리를 검증한 뒤 그 타석만 실제 모델
모드로 바꾼다. 결과 확률과 책임 판정은 별도 검증된 응답이 있어야 연결한다.

## 유지보수·확인 결과

```bash
uv run --frozen python scripts/export_pitch_studio.py
uv run --frozen python scripts/check_pitch_studio.py
uv run --frozen python -m pytest tests/test_checklist_model.py -q
```

Windows 체크리스트 테스트는 `PYTHONUTF8=1`로 실행한다.
`export_pitch_studio.py` 기본 동작은 읽기 전용 원본 대조다. `--write`는 의도적으로
고정 원본을 바꾼 경우에만 사용한다. M3 재측정이나 JSONL 재생성은 이번에 하지 않았다.

- 홈 `index.html/home.js/product.css`; 서비스 `service.html/studio.js/studio.css/preview-data.js`.
- 실제 관측 `report.html/app.js/styles.css/report-theme.css/data.js`.
- 39고유키/27좌표/12기권·M3·4개 원본 해시 대조 통과. 예시 4개 분포 합 1, 구종 비율 합 100.
- JavaScript 문법·HTML 내부 파일 링크·미디어와 원본 manifest 해시 검사 통과.
- 브라우저: 시나리오·분석 단계·실제 좌표/예시 목표·재생 시 표식 숨김·계약 안내 확인.
- 390×844 모바일 홈/서비스/리포트의 scrollWidth=clientWidth=375, 가로 넘침 없음.
- 개발 콘솔 오류 없음. 체크리스트 가드 결과 `4 passed`.
- 팀원 저장소·고정 M3·원본 JSONL·발표 PPTX/PNG·기존 리허설 문서는 수정하지 않았다.

Site 재배포는 같은 project_id와 기존 checkout을 열어 수행한다. 새 Site를 만들지 않는다.
소스는 주 저장소의 ignored `outputs/cv_followup_20261005/pitcheezy-demo-site`다.
원본 Site 파일과 `web/pitch-studio/` 사본을 맞추고 정확한 소스 커밋의 배포 성공을 확인한다.
Windows bundled workflow: Git Bash, TAR_OPTIONS=--force-local, forward-slash archive 경로.
safe.directory는 해당 checkout에만 실행 범위로 적용하고 토큰을 파일에 저장하지 않는다.

## pitcheezy.com 연결 대기

## 2026-10-06 접속 장애 진단

Sites의 기존 공개 배포는 active이며 v3다. `pitcheezy.com` custom domain은
pending / provider pending / ssl pending_validation이다. Google 공개 DNS 조회에서
apex A는 NOERROR·Answer 없음, 두 인증 TXT 이름은 NXDOMAIN이었다. 필요한 A/TXT를
아직 등록하지 않은 상태로 판단했다. 단순 SSL 전파 완료를 기다리는 상태가 아니다.

Cloudflare 관리 탭이 로그인 화면으로 이동해 DNS 수정은 수행하지 못했다. 사용자 로그인
요청을 남겼다. 로그인 후 아래 기존 네 레코드를 추가하고 Sites refresh에서 active 및
SSL active를 확인한다. 기존 레코드를 먼저 읽고 다른 서비스를 보존한다. 아직 해결 완료가 아니다.


사용자가 구매 완료를 알렸으며 공식 RDAP에서 PITCHEEZY.COM 등록과 Cloudflare 네임서버를 확인했다. 이메일 인증 여부는 미확인이다. DNS에
아래 서버 반환 값을 추가한다. 기존 DNS가 있다면 충돌 레코드만 검토하고 다른 서비스 기록을 보존한다.
Cloudflare에서는 A 레코드 프록시를 DNS only로 두고 TTL은 Auto를 사용할 수 있다.

| 유형 | 이름 | 값 |
|---|---|---|
| A | @ | 162.159.143.30 |
| A | @ | 172.66.3.26 |
| TXT | _openai-site-verification | openai-site-verification=Ri42X02gL2W0q1VQ1Yf6kgVnnImINnyocTQRyW-KBqE |
| TXT | _cf-custom-hostname | c553d001-7861-4f68-aa19-e90456e7e7aa |

custom domain ID: `appgdom_6ac36b64dbe8819192e28f67024aa9f5`.
설정 후 같은 ID의 Sites refresh_custom_domain_status로 소유권·SSL·active 상태를 확인한다.
active 전에 pitcheezy.com 연결 완료라고 보고하지 않는다. www는 이번에 등록하지 않았다.
구매 가능 여부·최종 금액·자동 갱신 설정·연락처·결제·약관은 사용자가 구매 화면에서 확인한다.

공식 절차: https://developers.cloudflare.com/registrar/get-started/register-domain/
공식 가격표: https://pricing.registrar.cloudflare.com/
2026-10-05 조회 기본 .com 등록·갱신 US$10.46/년, 실제 결제 화면 금액 우선.
