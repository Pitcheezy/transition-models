# WS-ops2 첫 연결 자료 실제 검증 — 2026-10-13

[mail #18](https://github.com/Pitcheezy/transition-models/issues/18)의 첫 연결 안내(Song / Claude PM, 2026-10-12)를 **우리 환경에서 실제 파일로** 검증한 기록이다.
상대 저장소는 고정 커밋을 읽기만 했고(변경·push·배포·발행기 실행 없음), 모든 결과는 **합성 예시·임시 로컬 Worker·읽기 전용 화면 빌드**에서 나왔다.
실제 발행기 업로드·실계정 호스팅·실경기·MLB 이용 허가는 이 기록의 범위 밖이다.

## 1. 받은 것과 대조 결과

| 항목 | 값 |
|---|---|
| 발행기·계약 | `SongRoute/pitcheezy` `svc/ws-publisher` `d5a1dd98003672235cc50509391fd4c41b28be32`, `apps/observer/publish_contract/v1/` |
| 공개 화면 | `svc/ws-static-web` `ef4e4df2f0547331459f9d952c5d76e1090f11e8`, `apps/observer/web` `npm run build:public` |
| 문서 | `collab/ws-2026` `c0e2e28` `docs/pm/transfers/COLLAB-001-first-connection-pack.md` |
| 계약 버전 | 공개 파일 v1(문서 초안 v0 표기 유지) |

- 예시 13개·스키마 6개를 고정 커밋에서 받아 문서의 SHA-256과 대조: **19/19 일치**.
- JSON Schema(draft 2020-12) 검증: 13개 예시 모두 **오류 0**. 모든 파일에 `publish{contract:"v1",sequence,published_at}`, 경기·셋업에만 `final`.
- 호스트 제약: 대상 경로가 모두 우리 허용 목록(`v1/manifest|health|dates|games/<날짜>|game/<id>|setup/<id>`)에 맞고 최대 34,668바이트(5 MiB 상한 안).
- 관측된 화면 상태: `pregame`·`recommended`·`unconfirmed`·`disconnected`·`waiting`·`final`. **`unsupported` 예시는 없음**(문서가 밝힌 공백, Song 후속).
- 추천 후보 `detail.probability`·`target` 스키마 2곳 수정 예고는 d5a1dd9에 아직 반영되지 않았다(세 브랜치 head가 2026-10-12 이후 그대로).
- 영수증: [collab001_contract_verification_20261013.json](results/ops/collab001_contract_verification_20261013.json)
  (`uv run --frozen python scripts/verify_publish_contract.py --received <받은 폴더> --expected ops/public-host/examples/collab001-expected-files.json`).

## 2. 호스팅 조건 1-1 대조 (로컬 Worker)

[rehearse-first-connection.mjs](../ops/public-host/rehearse-first-connection.mjs)가 문서 6절 절차(manifest·dates → 목록 2개 → `game/900200` 6단계 교체 → `game/900101`·`setup/900101` → health 마지막)대로
원본 바이트를 올리고 되읽었다. [영수증](results/ops/ws_first_connection_rehearsal_20261013.json).

| 조건 | 결과 |
|---|---|
| 매번 원본 재확인 | 모든 JSON `Cache-Control: no-store`(문서의 no-cache/짧은 max-age보다 강함). 종료 파일 장기 캐시는 미구현 |
| `Date`·`Age` | 매 응답 `Date` + `Age: 0`(R2 직접 읽기). 실제 CDN의 Age 동작은 미검증 |
| 다른 출처 헤더 | `READ_ORIGIN`과 같은 Origin에만 `Access-Control-Allow-Origin` + `Expose-Headers: Date, Age, ETag`; 다른 출처에는 없음 |
| 없는 파일 404 | JSON 404, index.html 대체 없음 |
| 삭제 반영 | 인증 DELETE(If-Match) 직후 GET/HEAD 404; 복원은 새 ETag |
| 통째 교체 | 조건부 PUT(If-Match)으로 6개 스냅샷 교체, ETag 6개 모두 다름, 마지막 본문 = game-final |
| **GET `If-None-Match` → 304** | 이번에 구현(`gateway.mjs::etagMatches`). 현재 강한 ETag만 304, 약한 태그·`*`·교체/삭제 후는 200/404. 업로드 조건부 ETag와 별개 |

## 3. 공개 화면 첫 연결 (Chromium, 로컬)

고정 커밋을 sparse clone해 `npm ci` 후 `VITE_PUBLISH_BASE=. npm run build:public`로 만든 `dist-public/`(index.html SHA-256
`0fcdd63e0d42598b258ec6525e4d4a8659bfe9e8c5afe035e528d3578ae6b43a`, 4파일 352,514바이트)을 같은 Worker의 ASSETS로 제공했다.
[영수증](results/ops/ws_first_connection_screen_20261013.json) ([first-connection.test.cjs](../tests/browser/first-connection.test.cjs), 환경 변수 없으면 건너뜀).

- **A. 원본 그대로:** `?date=2026-10-05` 목록에 LIVE 카드, `?date=2026-09-30`에 종료 카드. `/v1/dates·manifest·games/<날짜>·health·game/900200`만 요청, `/api/**` 0건.
  발행 시각이 2026-10-05라 문서 예상대로 **"갱신 지연"** 이 함께 표시됨(발행 중단 구별 확인). 경기 전 예시는 "예정"+갱신 지연.
- **B. 시각만 현재로 바꾼 사본(별도 산출물, 원본 SHA와 다름 — 영수증에 12건 기록):** 경기 전 → 다음 공 추천(첫 표시 10.1 s, 목록/health 10 s 주기) → 확인 중(2.0 s)
  → 연결 끊김(1.9 s) → 공수 교대(1.9 s). 여기서 갱신을 멈추자 **28 s 뒤 "갱신 지연"** (잠정 기준 30 s, 문서대로 미측정 값). 이어 종료본을 올리면 "경기가 끝났어요"(1.9 s),
  종료 뒤에는 갱신 지연 표시 없음(관측). 375 px 폭 수평 스크롤 없음.
- **C.** 보관 종료 경기 `?game=900101`에 "종료" 표시, `v1/setup/…` 요청 없음(문서와 일치), 철회 뒤 화면 fetch 404.
- 미확인: `unsupported` 화면 상태(예시 없음), 실제 Safari/모바일, 실제 CDN 지연, Song 발행기의 실제 업로드.

## 4. 배포 목록 (현재 고정값)

| 항목 | 값 |
|---|---|
| Song 발행기 커밋 | `d5a1dd98003672235cc50509391fd4c41b28be32` |
| Song 화면 커밋 | `ef4e4df2f0547331459f9d952c5d76e1090f11e8` (dist-public index.html SHA 위 참조) |
| 우리 호스트 커밋 | 이 기록을 담은 PR #24의 완료 커밋(CHECKLIST·board 참조) |
| 계약 | 공개 파일 v1; 예시 manifest의 `commit`은 합성값(0…0)이라 식별자로 쓰지 않음 |
| 파일 SHA | 1절 영수증의 19개 |

## 5. 알게 된 것 / Song에게 알릴 것 (회신 초안 참조)

- 화면 빌드의 `vite.config.ts`는 `.env.public` 위치를 `new URL('.', import.meta.url).pathname`으로 잡아 **Windows에서는 `.env.public`이 읽히지 않고 API 방식 번들이 나온다**
  (`__PZ_STATIC__=false`, `/api/service/...` 요청). 셸 변수 `VITE_PUBLISH_BASE=.`로 빌드하면 정상이다. macOS/Linux 빌드에는 영향이 없을 것으로 보이나 재현 안내에 적는 편이 안전하다.
- 공개 GET `If-None-Match` → 304를 우리 쪽에서 준비했다. health를 먼저 읽고 바뀐 파일만 받는 변경과 맞물린다.
- 접근 문(WS-access1)을 켜면 화면 fetch가 `credentials: "same-origin"`이어야 하고 호스트와 같은 출처여야 한다(별도 요청 초안).
- 안내 스위치(WS-safe1)가 켜지면 공개 JSON이 503 `service_notice`로 바뀐다(별도 요청 초안).

## 6. 남은 것

- Song: `unsupported` 예시·SHA 추가, 추천 후보 스키마 2곳 수정, 업로드 도구(HTTP PUT/DELETE+토큰)와 우리 `/_publish/v1/...` 계약 맞춤.
- 사람: 호스팅 계정·도메인·토큰 전달·공개 범위(WS-ops4/WS-human1), 회신 발신 승인([초안](mail_drafts/COLLAB-001-reply-draft-20261013.md)).
- 우리: 실제 발행기 연결 리허설(계정 뒤), 종료 파일 장기 캐시(선택), WS-review1 다른 모델 검토.

## 7. 재현

~~~text
uv run --frozen python -m pytest tests/test_publish_contract_verify.py -q
uv run --frozen python scripts/verify_publish_contract.py --received <examples,schema 폴더> --expected ops/public-host/examples/collab001-expected-files.json
node ops/public-host/rehearse-first-connection.mjs --examples <폴더> --dist <dist-public> --output .cache/first-connection-new.json
cd tests/browser && PZ_FIRST_CONNECTION_EXAMPLES=<폴더> PZ_FIRST_CONNECTION_DIST=<dist-public> BROWSER_ENGINE=chromium node --test first-connection.test.cjs
~~~

받은 파일과 화면 빌드는 저장소에 넣지 않았다(Song 산출물). 해시와 영수증만 보존한다.
