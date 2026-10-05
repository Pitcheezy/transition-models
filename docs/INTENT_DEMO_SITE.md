# Pitcheezy 투구 관측 스튜디오 — 2026-10-05

사용자 요청으로 만든 독립 CV 발표 사이트다. Song의 실제 관전 UI를 대체하거나
그 화면의 리허설을 완료한 것으로 처리하지 않는다.

## 실행과 배포

- 공개 데모: https://pitcheezy-pitch-studio.sritone723.chatgpt.site
- Sites 배포 성공: 2026-10-05, 소스 `febbcf003fd76a4501b75810f4c86bfd3dbb7ed3`.
- Sites project: `appgprj_6ac3665aa5048191ac2b5a012b2c7010`.
- 사용자 추가 요청에 따라 public으로 전환했다. 중계 영상·이미지·사람 원본 라벨은 포함하지 않는다.
- `pitcheezy.com` 연결 요청은 생성했으나, 도메인 구매·Cloudflare 네임서버는 확인됐고 DNS 설정은 대기다.
- 저장소의 `web/pitch-studio/`는 배포된 정적 파일 4개의 동일한 사본이다.

인터넷 없는 발표에서는 `web/pitch-studio/index.html`을 브라우저로 직접 열 수 있다.
HTTP 방식은 저장소 루트에서 다음을 실행한다(Python 3, Windows/macOS 동일).

```bash
python -m http.server 8786 --bind 127.0.0.1 --directory web/pitch-studio
```

브라우저에서 http://127.0.0.1:8786/ 을 연다. 서버 종료는 해당 터미널에서 Ctrl+C.
외부 CDN, 폰트, API, 프레임워크 설치 없이 HTML/CSS/JS만으로 동작한다.

## 화면과 발표 동선

1. **투구 관측:** 투구 선택 → 공개 → 미트/공의 가로 관측값 확인. 첫 사례는 `849843:1:3`.
2. **기권:** `849843:2:5`를 공개해 미트 좌표가 없고 이전 점도 남지 않음을 보인다.
3. **검증 리포트:** 별도 두 경기 M3의 86장/출력58/기권28, 공동 표시58구의 2.5px/~1.1in을 설명한다.
4. **프로젝트 방향:** 관측 → 요구 위치 확인 → 동일 기준 비교의 순서로 다음 검증을 설명한다.
5. 로컬 대표 비교 그림 `849845:10:4`는 이미 전달한 ZIP의 index.html에서 별도로 연다.

발표용 표현:

> 최종 목적은 포수가 요구한 위치와 실제 투구 수행을 비교하는 것입니다.
> 제가 맡은 부분은 영상에서 미트 위치를 읽어 좌표로 전달하고 사람 표시와 비교하는 관측 모듈입니다.
> 오늘은 실제 저장 기록의 탐색·기권 처리·위치 표시와 평가 결과를 연결해 보여드립니다.

완성률 95%는 산정하지 않는다. 현재 사이트는 사전 처리 기록의 시연이며 실시간 판독이 아니다.
셋업 미트가 실제 요구 위치였는지는 별도 검증 대상이다. 공 좌표는 Statcast 홈플레이트 통과
위치이고 미트는 플레이트 뒤의 위치라 두 값의 단순 차이를 제구 오차로 계산하지 않는다.
미트 높이·9구역·투수 의도·결과 확률·추천·영상 자동 동기화는 제공하지 않는다.

## 데이터와 유지보수

시연은 경기849843의 선택된39구(미트27/기권12)다. 전체262구나 새로운 독립 평가가 아니다.
`data.js`의 `sources`는 원본 4파일의 SHA256이며, 키로 연결한 투구 데이터와 정확한 M3 수치를 보존한다.
공 좌표39개는 calibration_readings의 statcast_front.pX이며 로컬 frozen feed와39/39 일치를 확인했다.
타순·영상 배열 순서를 사용하지 않는다. 공개 버튼은 표시 상태만 조작하며 실제 경기 진행과 연결되지 않는다.

원본 대조(기본값은 읽기 전용, Python + Node 필요):

```bash
uv run --frozen python scripts/export_pitch_studio.py
node --check web/pitch-studio/app.js
node --check web/pitch-studio/data.js
```

의도적인 원본 변경 후에는 먼저 평가 설명·고정 숫자의 변경 범위를 검토한 뒤
`uv run --frozen python scripts/export_pitch_studio.py --write`로 파생 파일을 갱신한다.
이 도구는 중복키·키 불일치·39/27 계약 위반을 거절한다. 임의로 기존 M3를 재측정하지 않는다.

- `index.html`: 기본 화면 구조
- `styles.css`: 반응형 스타일
- `app.js`: 화면 상태·조작·검증 설명·WebMCP
- `data.js`: 고정 자료에서 만든 파생 스냅샷

Sites 재배포는 같은 project_id와 기존 checkout을 열어 수행한다. 새 Site를 만들지 않는다.
현재 로컬 Site checkout은 주 저장소의 `outputs/cv_followup_20261005/pitcheezy-demo-site`이며 Git 추적 제외다.
Sites 소스와 이 저장소의 web 사본을 함께 맞추고, native 배포 성공을 확인한 뒤 링크를 전달한다.
Windows의 bundled workflow는 Git Bash, `TAR_OPTIONS=--force-local`, forward-slash archive 경로가 필요했다.
샌드박스 소유권 차이는 해당 checkout만 실행 범위의 safe.directory로 지정했다. 전역 설정은 변경하지 않았다.
인증 토큰은 저장하지 않는다.

## 실제 확인 결과

- JavaScript 두 파일 문법 검사 통과, Prettier 정리 완료.
- 원본 대조:39키/27좌표/12기권 및 M3·출처 해시 일치.
- 브라우저: 선택 시 공개 상태 초기화, 기권 시 null 유지, ft/in 변환, 다음 투구 초기화,
  화면 전환·발표 가이드, 접근성 설명의 이전 좌표 제거, 잘못된 키(`__proto__` 포함) 거절 확인.
- 390px 모바일 viewport에서 document scrollWidth=clientWidth=375px(스크롤바 제외), 가로 넘침 없음.
- 사이트 배포 succeeded, public 접근 설정 확인. Song의 실제 UI 6항목 검증은 여전히 대기.
- 기존 JSONL·M3 보고서·PPTX·PNG·리허설 문서·팀원 저장소는 변경하지 않았다.

## pitcheezy.com 연결 대기

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
