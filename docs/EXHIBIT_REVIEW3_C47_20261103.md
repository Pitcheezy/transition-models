# 팀원 빌드 c47 정적 교차 검토 (REVIEW3) — 2026-11-03

대상 저장소: `SongRoute/pitcheezy` · 대상 커밋 `c47fe6cb78479362e7250141da946814cc33bd31` · 기준 커밋 `61be7a86fdea108caed975cdde98d63296be50ad`.
산출물 식별: 전달받은 ZIP SHA-256 `3c3b8006b892872bfff3423e2bd6ba49ea3de17ee92fbecef07e0b076bc8da51` (웹 빌드 소스 c47, 공개 JSON 6개는 전달자 선언 기준 `cb1cfa8f759fd77adc75595316a389208c752dba`에서 생성).
영수증: [review3-c47-20261103.json](results/exhibition_20261101/review3-c47-20261103.json).

**검토 방식: GitHub compare `61be7a86…c47fe6cb`의 정적·읽기 전용 검토.** 팀원 코드를 복제·빌드·설치·실행하지 않았고, 팀원 저장소에 쓰지 않았다. 아래의 모든 동작 주장은 코드 읽기에서 나온 추론이며, 실행이 필요한 주장은 그렇게 표시했다. 심각도 기준은 팀원 검토 프롬프트와 같다 — P1 = 전시를 깨거나 전시 경로에서 관람자에게 틀린 정보를 보여줌, P2 = 틀리지만 전시 경로에서 보이지 않음, P3 = 사소한 지적.

전시 맥락: 2026-11-24 전시. 공개 빌드는 STATIC v1 모드(완료 경기 849843, 하루 2026-09-30, index.html + assets + JSON 6개를 접속 코드가 있는 우리 게이트웨이 뒤에서 제공, 폴링 기본 10 s, final=true, next=null). 모니터 1은 팀원 노트북의 로컬 라이브 재생(preview)을 돌릴 수 있다. 고정 모델 추천, 새 데이터 없음.

## 0. 요약

- P1 유지 0건. P2 유지 6건(SVC-4, PREV-1, PREV-2, PREV-3, COV-1, COV-3). 기각 1건(COV-2). P3(미검증) 15건.
- 공개 STATIC 전시 경로(완료 경기 849843을 정적 파일로 보는 폰)에서 관람자에게 틀린 정보를 보여주는 결함은 찾지 못했다.
- P2 6건은 각각 API 모드(SVC-4), 미리보기 재생 번들(PREV-1/2/3), 테스트 범위(COV-1/3)에 있다. 이 중 모니터 1에서 미리보기 재생을 관람자에게 보여줄 경우 PREV-1은 P1로 다뤄야 한다(아래 조건부 지적).
- 알려진 선행 관찰(API 모드에서 503 안내 → 자동 재시도 404 → 서버 복구 뒤 완료 경기 멈춤)은 줄 번호로 확인했고, 정적 모드에서는 폴링이 유지되어 영향이 없다는 판정도 확인했다(SVC-4).
- 판정: **PASS_WITH_NOTES**.

## 1. 발견

### P1 — 없음

전시 경로에 남은 P1은 없다.

### P2 — 유지 6건

각 항목의 "회의론자" 줄은 3명의 독립 회의론자 판정이다(기각 여부 / 권고 심각도). 다수결로 기각되지 않은 항목만 유지했다. 기록된 심각도는 분할 검토자의 값이며, 회의론자 권고가 다를 때는 함께 적었다.

#### SVC-4 (P2) — 선행 관찰 확인, API 모드 한정: 완료 경기가 503 안내 → 자동 재시도 404 → 서버 복구 뒤 안내 화면에 머무름

- 파일: `apps/observer/web/src/service/GameScreen.tsx:354`
- 코드:
  ```ts
  const firstLoadRetry = (detail === null || noticeHold) && error !== null && (error.status === 0 || error.status >= 500);
  ```
- 이유: API 모드에서 완료 경기는 332행에서 `pollMs = 0`(live 아님, waitingToStart 아님, static 아님)이라 333–337행의 인터벌이 돌지 않는다. 안내(503 `service_notice`)는 285행에서 `hold`를 세운다. 354행의 재시도는 status 0 또는 5xx에만 걸리므로, 한 번의 재시도가 404를 받으면 재시도가 멈춘다. `missing`(357행)은 정적 전용이다. 아무것도 다시 묻지 않고, 416행의 안내/오류 화면은 관람자가 425행의 "다시 시도"를 누를 때까지 남는다. `onVis`(387행)는 `pollMs`가 필요하고, `onOnline`(389행)은 `pollMs || detailRef.current === null`인데 안내는 `detail`을 비우지 않으므로 둘 다 발화하지 않는다.
  정적 모드(공개 전시 빌드)는 영향이 없다. 332행은 `detail !== null`인 동안 `pollMs = manifestMs ?? CADENCE.live`를 유지하고, 안내는 `detail`을 지우지 않는다(285행은 hold만 세움). `auto`는 false로 바뀌지 않으므로(유일한 setter는 552행 `setAuto(true)`) 335행 인터벌이 계속 `load()`를 부르고, 다음 읽기는 `requireBody = holdRef.current`(253행)로 게임 파일을 받아 같거나 새 순번의 본문이 적용되면 hold를 푼다(257행). 숨긴 탭은 멈추고(227, 335행) visibilitychange로 재개한다(387행). 정적 모드에서 detail이 없는 상태에서 hold가 시작되고 404가 뒤따르면 `missing` 백오프(369–380행)로 떨어지며, manifest의 live_dates에 2026-09-30이 없으면 "지금 볼 수 없어요"와 수동 버튼으로 조용히 끝난다 — 설계된 동작이며 루프가 아니다.
- 재현(실행 안 함): API 빌드에서 완료 경기를 열고, 서비스 경로가 503 `{"error":"service_notice","notice":{"id":"maintenance"}}`를 반환하게 한 뒤, 4 s 자동 재시도에는 404, 그다음부터 200을 반환하게 한다. 페이지는 안내 또는 404 알림에 무기한 머문다. 정적 빌드로 반복하면 파일이 200을 답한 뒤 한 폴링(≤10 s) 안에 경기가 다시 그려진다.
- 최소 수정: hold가 선 동안 계속 묻게 한다. 예: `const firstLoadRetry = (detail === null || noticeHold) && error !== null && (error.status === 0 || error.status >= 500 || (noticeHold && error.status === 404));` 또는 API 모드에서 `hold`가 true인 동안 `pollMs`에 0이 아닌 주기를 준다.
- 전시 경로: 아님(공개 빌드는 정적; 모니터 1 미리보기는 live 경기를 재생하므로 `pollMs = 0` 분기가 아님).
- 회의론자: 3/3 기각 안 함, 3/3 P2, 줄 번호 3/3 확인.

#### PREV-1 (P2, 모니터 1에서 관람자에게 보여줄 경우 P1) — 재생이 경기 뒤(as-of) 추천을 "경기 중 기록"으로 재표기하고, 경기 뒤 시각을 그대로 보여줌

- 파일: `apps/observer/web/src/preview/replay/frames.ts:115`
- 코드:
  ```ts
  const rec = { ...clone(p!.rec), provenance: 'captured_live', policy: { name: 'ARM-B', identity: 'replay' } };
  ```
- 이유: 픽스처 game-849843.json의 65개 rec는 모두 provenance `asof_replay`, recorded_at `2026-09-30T08:48:53Z`(17:48 KST), policy `ARM-B P3 frozen <=2025`다. 경기 시작은 02:00Z(11:00 KST). 115행은 rec를 복사하며 provenance를 `captured_live`로 강제하지만 recorded_at은 그대로 둔다. 본문의 source.kind도 `live`(100행)라 normalizeDetail(api.ts:395, :415)이 live_source=true를 준다. 화면에서 다음 투구 시트는 "경기 중 투구 전에 기록한 추천 · 17:48 기록"(Sheets.tsx:108, :125, :149/:209)을 읽는데, 이는 거짓이고 재생 중인 "오늘" 경기에 속하지 않는 시각이다. 지난 투구는 제목이 "투구 전에 기록된 추천"(GameScreen.tsx:555–556)인데 그 시트는 "경기 뒤 … 계산한 추천"(원 provenance는 여전히 asof_replay)이라 한 화면이 자기모순이다. install.ts:33–35가 재생 경기를 오늘 날짜·현재 시작 시각으로 옮기므로 17:48은 보이는 경기와 무관하다. ReplayBar.tsx:13은 `useState(false)`로 시작해 20행의 "미리보기 전용" 안내가 기본으로 숨겨져 있다.
- 재현(정적): 위 115행과 픽스처 pitches[0].rec(provenance `asof_replay`, recorded_at `2026-09-30T08:48:53Z`)를 대조. 미리보기 빌드(`npx vite build --config vite.preview.config.ts --mode public`, 실행 안 함)를 열어 `?game=990003`에서 다음 투구의 추천 시트를 연다.
- 최소 수정: 픽스처의 provenance를 유지하고 경기 뒤 시각을 버린다. 예: `const rec = { ...clone(p!.rec), recorded_at: null };` (provenance `asof_replay` 유지). 관람자에게 재생을 보여줄 거면 bar가 닫혀 있어도 보이는 "재생" 표시를 화면에 둔다. 회의론자 보완: 지난 투구의 "투구 전에 기록된 추천" 제목은 live_source에서 오므로, 완전한 수정은 재생 전용 라벨이거나 제목을 rec.provenance에만 의존시키는 것이다.
- 전시 경로: 공개 정적 빌드에는 없음(main-replay.tsx는 "not a public bundle"). 모니터 1 미리보기를 관람자에게 보여주면 해당.
- 회의론자: 3/3 기각 안 함, 3/3 P2(조건부 P1 동의), 줄 번호 3/3 확인.

#### PREV-2 (P2 기록, 회의론자 다수 P3 권고) — 재생은 65구만 덮고 3회말 뒤 "경기 종료 0:8"로 건너뛴 뒤 반복하며, 투구 기준 시계가 없어 모니터 2 클립 체인과 보조를 맞출 수 없음

- 파일: `apps/observer/web/src/preview/replay/control.ts:41`
- 코드:
  ```ts
  if (now - last >= state.stepMs) { last = now; setReplay({ index: state.index + 1 >= STEPS.length ? 0 : state.index + 1 }); }
  ```
- 이유: game-849843.json은 tests/fixtures/service-849843.json(CONTRACT rev1 UI 픽스처)의 `final` 변형으로 `_note`를 빼면 바이트 동일하며, 65구·20타석, 849843:20:5(3회말, SD 2-0)에서 끝난다. 마지막 단계(frames.ts:28, :97, :104)는 그 투구 직후 실제 최종 점수 0:8과 linescore null을 보여주고, GameScreen.tsx:158은 이닝별 기록이 아직 준비 중이라고 말한다. control.ts:41은 이어서 0단계(경기 전)로 감긴다. 스크립트는 78단계(경기 전 1 + 투구 65 + 하프이닝 휴식 5(k=11,22,35,45,60) + 미확인 주입 6(k=4,15,26,37,48,59) + 종료 1)이고 단계 길이가 같아(stepMs 기본 4000 ms) 투구당 시간이 고르지 않다. 한 바퀴 312 s. `last = now`(`last += stepMs` 대신)는 단계마다 최대 250 ms 틱의 표류를 더한다. 슬라이스 안에 현재 투구 키를 페이지 밖으로 내보내는 것이 없고(BroadcastChannel/postMessage/공유 저장 없음), 재생 경기는 game_pk 990003이면서 키는 `849843:<pa>:<n>`이다.
  회의론자 정정: 종료 단계(index 77)는 약 308 s, 경기 전으로 감기는 시점은 312 s. 투구 64까지의 추가 단계는 12개(경기 전 1 + 휴식 5 + 미확인 6)다. 65구 절단과 최종 점수 건너뛰기는 frames.ts:96, :102–103 주석에 의도로 적혀 있다. 모니터 2 동기 요구는 우리 전시 요구이지 이 코드가 약속한 것이 아니다.
- 재현(정적): frames.ts:21–30의 STEPS를 픽스처로 세면 78. 기본 4 s로 두면 약 308 s에 "경기 종료 CHC 0 : 8 SD"와 3회말에서 끝나는 투구 기록, 약 4 s 뒤 "경기 전". 같은 순간 시작한 투구당 고정 주기의 모니터 2 체인은 투구 64에서 약 48 s(12단계 × 4 s) 어긋난다.
- 최소 수정: 끝 상태를 명시하고 멈춘다. control.ts:41을 `setReplay(state.index + 1 >= STEPS.length ? { playing: false } : { index: state.index + 1 })`, `last += state.stepMs`로. 모니터 2가 따라와야 하면 현재 단계의 투구 키를 내보낸다(예: setReplay에서 `new BroadcastChannel('pz-replay').postMessage(P[k].key)`) 또는 두 모니터를 하나의 투구 기준 일정으로 구동한다. 재생이 전시 경기를 비추려면 65구 픽스처를 공개 849843 전체 파일로 바꾼다.
- 전시 경로: 공개 정적 빌드에는 없음. 모니터 1 미리보기 운영 시 관람자가 3회말 0:2 → 경기 종료 0:8 → 경기 전을 본다.
- 회의론자: 1/3 기각(의도된 문서화 동작·존재하지 않는 동기 요구), 2/3 기각 안 함; 권고 심각도 P3·P3·P2. 다수결로 유지, 심각도는 P3 권고가 다수. 줄 번호 3/3 확인.

#### PREV-3 (P2 기록, 회의론자 1/3 P3 권고) — 미리보기의 "지난 경기" 849843은 final로 표시된 65구 픽스처이지 공개 849843 경기 파일이 아님

- 파일: `apps/observer/web/src/preview/replay/install.ts:54`
- 코드:
  ```ts
  if (game && Number(game[1]) === ARCHIVE_PK) return json(stamp(FINAL_FILE, { seq: 1, at: ARCHIVE_AT }, true));
  ```
- 이유: 미리보기에서 `?game=849843`("지난 경기" 링크 ReplayBar.tsx:32, 2026-09-30 목록 install.ts:45/:49)은 FINAL_FILE(frames.ts:6–12, 원 픽스처 그대로)을 publish {sequence:1, final:true}로 답한다. status final·점수 0:8이지만 투구 0..64만(cutoff 849843:20:5), linescore·display_state·receipts 없음, `_note` 키 추가. next=null·final=true 의미는 공개 파일과 같지만 내용은 다르다. 한 회의론자가 우리 쪽 전시 점검 사본의 공개 v1/game/849843.json(읽기 전용)과 대조했다: 262구, cutoff 849843:71:6, final 0:8, linescore·pregame·features·publish 있음. GameScreen.tsx:627은 완료 경기에 detail.linescore_asof를 쓰므로 이닝별 기록이 비게 된다.
- 재현(정적, 픽스처 JSON만 읽음): `python -I -c "import json;d=json.load(open('game-849843.json',encoding='utf-8'));print(len(d['pitches']),d['cutoff'],d['game']['status'],d['game']['away_score'],d['game']['home_score'],'linescore' in d)"` → `65 {'index': 64, 'pitch_key': '849843:20:5'} final 0 8 False`.
- 최소 수정: ARCHIVE_PK에 전시 정적 세트의 실제 v1/game/849843.json을 바이트 그대로 제공한다. 65구 절단만 원하면 미리보기의 "지난 경기" 경로를 뺀다(install.ts:54 → `notFound()`, ReplayBar.tsx:32 링크 제거).
- 전시 경로: 아님(install.ts:1 "Preview builds only (`__PZ_REPLAY__`)"; ReplayBar.tsx:20이 "첫 65구"임을 운영자에게 알림; 모니터 1은 990003으로 열리고 849843은 운영 bar나 날짜 목록을 거쳐야 도달).
- 회의론자: 3/3 기각 안 함; 권고 심각도 P2·P2·P3. 줄 번호 3/3 확인.

#### COV-1 (P2 기록, 회의론자 3/3 P3 권고) — 안내 → 네트워크 오류/404 → 계속 숨김("재노출 없음" 주장)에 대한 테스트 없음

- 파일: `apps/observer/web/tests/notice-hide-smoke.mjs:150` (인용 블록은 150–155행)
- 코드:
  ```js
  host.mode = 'maintenance';
  await noticeShown(page, tag, 'maintenance', width, height, errors);
  host.mode = 'data_hold';
  await noticeShown(page, tag, 'data_hold', width, height, errors);
  host.mode = 'ok';
  await gameShown(page, tag, 'after');
  ```
- 이유: 안내 뒤 일반 오류가 옛 추천을 다시 보여주면 안 된다는 것이 핵심 주장이고, 이를 구현하는 코드는 GameScreen.tsx:176–179와 :285의 sticky hold다(fba6b2ff P2-1). notice-hide-smoke는 maintenance → data_hold → ok만 돌린다(가짜 호스트 27행은 'ok'|'maintenance'|'data_hold'만 앎). 135행의 "재노출 없음" 검사(`!innerText.includes('이전:')`)는 복구 뒤 변경 메모만 본다. static-publish-smoke의 game-notice 블록(1431–1471)은 hold 중 304(1444)와 낮은 순번(1447)을 시도하지만, 'abort'는 내용이 이미 복원된 뒤(1452)에만 보낸다. 다른 테스트 10여 개(service-ui, display-state, game-reconnect, public-viewer-e2e, final-integration, full-rehearsal, game-hang, game-timeout, demo-recovery, ws-host-errors)에는 안내 뒤 오류 시나리오가 없다. 자동화 테스트가 이 주장을 덮지 않으며, 근거는 우리 쪽 수동 Chrome 확인뿐이다.
  회의론자 정정: 코드 자체는 읽기로는 올바르다(285행 `if (notice) { holdRef.current = true; setHold(true); }`, 257/281행만 hold 해제, 240행 `if (!holdRef.current) setError(null)`, 351행 `noticeHold = hold || error?.notice === true`, 416행 조기 반환). 따라서 잘못된 동작이 아니라 회귀 방지 테스트의 부재이며, 규칙상 P3다. "Issue #38이 정확히 이것을 요구했다"는 확인되지 않았고, f11de37f 커밋 메시지의 "과거 추천 재노출 없음"은 정상 응답 뒤를 뜻하므로 과장된 인용이다. 제안 단언 중 `.sv-alert` count === 1은 abort 뒤 오류 문구가 바뀌어도 성립하나, 더 안전한 단언은 LIVE_PARTS 모두 0 또는 `.sv-zone` count === 0이다.
- 재현(정적): `grep -n "host.mode" tests/notice-hide-smoke.mjs` → ok/maintenance/data_hold만. static-publish-smoke.mjs 1441–1455행에서 첫 fileMode='abort'/'404'가 "accepted current body restores content" 단언 뒤에 온다. 실행 안 함.
- 최소 수정: game-notice 블록에서 1442행의 안내 단언 바로 뒤에 `state.fileMode='abort'; await advance(page,10000); ok(await page.locator('.sv-zone').count()===0 && …)`를 넣고 `state.fileMode='404'`로 반복(final·live 둘 다). 선택적으로 notice-hide-smoke의 data_hold와 ok 사이에 host.mode 'down'(route.abort)과 '404' 단계를 넣어 LIVE_PARTS가 모두 0임을 단언한다.
- 전시 경로: 테스트 파일이라 관람자에게 보이지 않음(기록은 true였으나 회의론자 판단은 커버리지 공백).
- 회의론자: 3/3 기각 안 함, 3/3 P3 권고, 줄 번호 3/3 확인.

#### COV-3 (P2 기록, 회의론자 3/3 P3 권고) — 섹션 1–3은 폴링 2 s의 소스 재빌드를 시험하고 전달된 공개 번들이 아니며, 섹션 1(파일에서 여는 완료 경기)은 375x553에서만 돈다

- 파일: `apps/observer/web/tests/static-publish-smoke.mjs:131`
- 코드:
  ```js
  const distRegression = variant('regression', { VITE_PUBLISH_POLL_MS: '2000' });
  ```
- 이유: open()은 dist = distRegression이 기본(138행)이고, 이는 작업 트리에서 VITE_PUBLISH_POLL_MS=2000으로 새로 `vite build --mode public`한 것이다(variant, 194–198행). 섹션 1–3(261, 297, 316, 329행)은 모두 기본을 쓴다. 따라서 PZ_WEB_DIST_PUBLIC에 풀어 놓은 ZIP을 지정해도 완료 경기 849843을 파일에서 여는 검사는 전달된 바이트나 10 s 기본을 쓰지 않는다. distPublic은 protocolScreen(1225), withServer(888), 1476/1516, R13(1540), 번들 텍스트 검사(318)만 쓴다. 섹션 1은 파일의 849843을 keyOnFirstScreen으로 확인하는 유일한 곳이고 375x553에서만 돈다(261, 279행); 섹션 2의 320/360/390 폭은 live 경기 990003이다.
  회의론자 정정: (1) 130행 주석이 의도를 밝힌다("regression scenarios at their original test cadence; protocol scenarios below use the real public defaults"). (2) "완료 경기를 파일에서 여는 유일한 정적 테스트"는 과장 — protocolScreen({final:true})(1349행)과 1433행의 final 루프가 distPublic·10 s 기본으로 완료 본문을 그린다(다만 990003으로 재표기, 390x664, 목록→경기 경로·디스크 파일·keyOnFirstScreen 없음). (3) 섹션 1의 유일한 주기 검사(2.5 s에 게임 읽기 ≤2)는 10 s 기본에서도 통과하므로, 두 번들의 차이는 빌드 시 폴링 변수뿐이다. (4) 비프로토콜 open()은 162–165행에서 manifest의 publish_interval_s를 지우므로 dist: distPublic로 바꿔도 번들 내장 기본만 시험한다. 잘못된 동작이 아니라 커버리지 공백이라 P3.
- 재현(정적): `grep -n "distRegression\|distPublic" tests/static-publish-smoke.mjs`. 261, 297, 329행의 open()에 `dist`가 없다. 실행 안 함.
- 최소 수정: 섹션 1에 명시적 `dist: distPublic`(또는 [distPublic, distRegression] 루프)을 주고 [[320,568],[390,844],[375,553]]에서 keyOnFirstScreen으로 돌린다. 그러면 PZ_WEB_DIST_PUBLIC=<풀어 놓은 ZIP> 실행이 전달 번들의 완료 경기를 폰 폭에서 실제로 검사한다.
- 전시 경로: 테스트 하네스이며 배포되지 않음(기록은 true였으나 회의론자 판단은 커버리지 공백).
- 회의론자: 2/3 기각 안 함, 1/3 기각(과장·심각도), 3/3 P3 권고, 줄 번호 3/3 확인(329행은 원 기록의 327행 정정).

### P3 — 미검증 목록 (15건)

분할 검토자의 지적이며 회의론자 검증을 거치지 않았다. 모두 정적 읽기.

| ID | 파일:행 | 내용 | 최소 수정 | 전시 경로 |
| --- | --- | --- | --- | --- |
| SVC-1 | `web/src/service/GameScreen.tsx:724` | 완료 경기에서 헤더는 최종 점수·최종 linescore(543–545, 627행)를 보이지만, 헤더 LineScore 탭(654행)이 여는 BoxSheet는 선택 투구(기본 첫 투구, 401행)의 `linescore_before`라 거의 '–'와 R 0:0인 표에 "아직 오지 않은 이닝은 –로 표시해요"(159행)가 붙는다. 값은 as-of 기준으로 맞으나 헤더와 모순. 코드: `{sheet === 'box' && <BoxSheet ls={latest ? detail.linescore_asof : pitch!.line ?? null} game={game} at={situation} onClose={closeSheet} />}` | `ls={latest \|\| game.status === 'final' ? detail.linescore_asof : pitch!.line ?? null}`, `at={game.status === 'final' ? null : situation}` 또는 `!latest`일 때 시트 제목에 as-of 기준 표기 | 예(공개 정적 849843에서 재현 가능: 첫 투구 선택 → 헤더 linescore 탭) |
| SVC-2 | `web/src/service/GameScreen.tsx:754` | 투수 시트 합계는 '오늘 · 이 공 전'(753행, `context_before`)인데 바로 아래 MixTable은 같은 asOfIndex로 `p.index <= asOfIndex`(LivePanels.tsx:11)라 선택 투구를 포함, '오늘 구종 · N구'(LivePanels.tsx:63)와 1구 차이. 완료 경기 기본 화면에서 '0구 · 0삼진 · 0자책' 옆에 '오늘 구종 · 1구'. | 선수 시트에 배타 절단(`asOfIndex === null ? null : asOfIndex - 1`) 또는 `upTo`에 `exclusive` 플래그, 또는 제목을 '이 공까지 N구'로 | 예(공개 정적 849843: 선수 → 투수 탭) |
| SVC-3 | `web/src/service/GameScreen.tsx:604` | 정적 모드에서 health.json 401은 삼켜지고(236행) 게임 파일 401은 hold 없이 오류만 세워 페이지가 그대로 남고, 칩은 '연결 끊김'(604행)이며 실제 지시문 '접근 확인이 필요해요…'(api.ts:22)는 칩을 눌러야 보이고 '다시 확인'(615행)은 같은 401을 반복. 데이터는 여전히 올바른 완료 경기라 틀린 정보는 아님. 코드: `if (error \|\| feedDown \|\| clientStale \|\| disp?.state === 'disconnected') return { label: '연결 끊김', tone: 'lost', state: 'disconnected', lines: [error?.text ?? CLIENT_LOST.message] };` | 604행 앞에 `if (error?.status === 401) return { label: '접근 확인', tone: 'lost', state: 'disconnected', lines: [error.text] };`, 401에는 canRetry false(또는 새로고침 링크) | 예(세션 만료 시 게이트웨이 뒤에서 발생 가능; 1시간 고정 세션) |
| PREV-4 | `web/src/preview/replay/frames.ts:90` | 타석 시작 off-by-one: `fx.pas.filter(pa => pa.first_index < k)`가 P[k]가 첫 투구인 타석을 떨어뜨려, 20개 '타석 첫 투구' 프레임에서 current.pa_key가 가리키는 타자의 '타석 진행 중' 행이 없음. 실제 발행기는 pitch_count 0·null 인덱스로 포함(publish-ws-moments 849803 first-rec/last-rec). | kind==='pitch'일 때 `pa.pa_key === P[k].pa_key`도 포함하고 first_index === k면 complete:false·pitch_count:0·null 인덱스로 내보냄 | 아님 |
| PREV-5 | `web/src/preview/replay/install.ts:26` | published_at = t0 + n*C가 지금보다 최대 한 주기 앞이라 publishLag가 모든 재생 파일을 'ahead'로 보고 발행기 시계 비교를 건너뜀. 표시에는 무해하나 지연 버그를 숨김. | `return { seq: n, at: new Date(t0 + (n - 1) * CYCLE_MS).toISOString().replace(/\.\d+Z$/, 'Z') };` | 아님 |
| PREV-6 | `web/src/preview/ReplayBar.tsx:30` | `jumps.slice(0, 14)`가 17개 바로 가기를 자르므로 종료 단계(final=true, next=null)·k=59 확인 중·k=60 휴식으로 건너뛸 수 없음. | slice 제거 또는 `[...jumps.slice(0, 13), jumps[jumps.length - 1]]` | 아님 |
| PREV-7 | `web/vite.preview.config.ts:13` | outDir 'dist-preview-classic'이 web/.gitignore('dist-public/', 'dist-public-*/')와 루트 .gitignore('dist/') 어디에도 없어 `git add -A`가 번들을 커밋할 수 있음. dist-public에는 닿지 않음(build:public은 vite.config.ts·/src/main.tsx). | web/.gitignore에 `dist-preview-*/` 추가 | 아님 |
| BE-1 | `publish_contract/v1/schema/setup.schema.json:87` | 기존 필수 필드 6곳의 타입 확장(setup plate_x_feet number→number\|null 87행, x_band string→string\|null 105행, unavailable_reason null→string\|null 99행; game catcher_setup plate_x_feet/x_band 1541/1550행; games venue null→string\|null 220행). 빌더가 이미 이 모양을 내므로 기준 스키마가 좁았던 것을 c47이 고친 호환 확장. 게이트웨이(경로·크기만)와 기존 클라이언트는 영향 없음. 다만 계약 문서 공지가 없음(docs/pm/contracts.md의 +2는 무관한 연구 메모). 기준 스키마를 고정한 소비자는 전시 파일을 거부함(setup 39구 중 12구 null, venue 4개 모두 문자열). | 코드 변경 없음. 계약 문서/v1 변경 기록에 6개 경로의 호환 확장 한 줄 공지. 호스트 측 도구는 c47 스키마를 고정 | 아님 |
| BE-2 | `ops/ws_alert.py:548` | ops_armb_off가 운영자가 의도적으로 armb='0'으로 끈 경우(ws_operate.py:30–31 → 1077행 self.armb=False)에도 CRITICAL을 내고 900 s마다 재알림(62행). 발행기 블록(813행)은 불리언만 가짐. 운영 라인 소음만, 공개 화면 무관. 코드: `if ops_state == 'running' and 'armb' in pub: conds.append(_cond('ops_armb_off', CRITICAL, pub.get('running', True) is not False and pub['armb'] is False, …` | ws_operate가 publisher 블록에 'armb_mode'를 넣고 ws_alert가 mode != '0'일 때만 평가, 또는 강제 off는 WARN으로 | 아님 |
| COV-4 | `web/tests/static-publish-smoke.mjs:249` | screenKind가 data-state 'disconnected'를 모두 'client'로 매핑해 피드 실패와 클라이언트 실패를 구분하지 못하고(1364행 완료 경기 실패 표시 검사 포함), `data-publish-clock` 호스트/발행기/경과 단언이 전부 제거되어 publishLag 단위 검사(88–91행)만 남음. 완료 경기 실패 표시 자체는 final=true 본문으로 여전히 검사됨. | screenKind가 피드 실패 시 'feed'를 돌려주게(또는 .sv-hd-status에 data-reason) 하고 1333/1364행에서 'feed' 단언; 시계 출처 브라우저 단언 하나 복원 | 아님 |
| COV-5 | `web/tests/ws-launch-layout-check.mjs:169` | `.sv-notice`, `.sv-chip`, `.sv-limit-line`, `.sv-rec-summary`, `.sv-duel`, `.sv-board`, `.sv-head-score`는 c47 service/preview TSX에 없어 `count() === 0` 검사가 항상 통과(110/169행, notice-hide-smoke LIVE_PARTS 5개(98행), compact-rev3-fit:151 `limitText`). GameScreen.tsx:416의 전체 교체와 live `.sv-zone`/`.sv-reclist`/`.sv-pitch-row` 검사로 완화됨. | 살아 있는 선택자('.sv-hd-score', '.sv-mu', '.sv-hd-status')로 교체, `.sv-limit-line` 검사는 본문 텍스트 검사(`!/검증 전 실험/.test(mainText)`)로 | 아님 |
| COV-6 | `web/tests/ws-gaps-smoke.mjs:63` | '#9' 검사가 픽스처 JSON 값만 단언하고 page를 쓰지 않아 항상 ok로 '15 pass'에 포함; 실제 화면 검사는 66행 SKIP. WS 재생 픽스처에만 해당. | 픽스처 전용 검사를 빼거나 전제조건으로 표기(ok 집계 제외) | 아님 |
| COV-7 | `web/tests/display-state-smoke.mjs:938` | 이닝 휴식 진입 레이아웃 안정성 검사가 전체 화면(상태줄·보드·존·상태 슬롯·카드·선수)에서 헤더('.sv-hd-1'/'.sv-hd-2', 938·289행)로 좁아져 존/추천 행의 점프를 놓침. 완료 경기에는 휴식이 없음. | UI-1026 전체 세트('.sv-hd-1', '.sv-hd-2', '.sv-zrow', '.sv-rec-sec', '.sv-atbat-head')의 boxes 비교, '.sv-mu'만 제외 | 아님 |
| COV-8 | `web/tests/compact-rev3-fit.mjs:197` | 약화된 검사: 기준은 글자 크기와 무관하게 카드 높이 불일치·한 줄 아님이면 hard fail이었는데, 큰 글자(big=true)에서는 `soft`(166행)로 가 INFO만 남기고 실패하지 않음. 속도 캡션 정규식도 빈 속도를 허용(기준은 '–' 필수). API 번들 한정. 코드: `(big ? soft : ok)(L.n > 0 && L.cardsEqual && L.cardsStacked, …)` | `L.n > 0 && L.cardsStacked`는 `ok`로 유지하고 큰 글자에서는 높이 동일 검사만 soft로 | 아님 |
| COV-9 | `web/tests/display-state-smoke.mjs:596` | API 모드 완료 경기의 안내 멈춤 경로(SVC-4)에 테스트가 없고, 기존 테스트는 그 두 전제만 각각 고정함: 596행 'final: polling stops'(pollMs 0)와 465행(404 미재시도). notice-hide-smoke의 API 케이스는 live 본문이라 503→404→200 조합은 시험되지 않음. 정적 모드는 detail이 있는 동안 폴링이 유지되어 전시 차단 아님. 코드: `ok(asks.length === stop, 'final: polling stops');` | notice-hide-smoke에 API final 본문 케이스(503 → 404 → 200)를 추가해 복원을 단언하거나, API 모드에서 복원이 의도가 아니면 문서화된 멈춤 상태를 단언 | 아님 |

P3 목록은 분할 검토 기록 전체(SVC 3·PREV 4·BE 2·COV 6)를 옮긴 것이다. 작성 단계에 전달된 기록이 COV-8 중간에서 절단되어 있어, COV-8 전문과 COV-9는 오케스트레이터가 분할 검토 원본 기록에서 보완했다.

## 2. 기각된 발견

- **COV-2** (`web/tests/notice-hide-smoke.mjs:143`, "공개 모드 안내 숨김/복원이 390/320에서 live 경기만 돌고 final=true 경기는 안 돔"): 3/3 기각. 줄과 픽스처 사실(990003 live, 849843 final)은 맞지만, 안내 화면은 GameScreen.tsx:416의 조기 반환이라 경기 상태와 무관한 같은 DOM이고(352행 시트 닫기도 상태 무관), 정적 빌드에서 332행의 pollMs는 live와 final(detail !== null)이 같은 값이며, static-publish-smoke game-notice(1432행 `for (const final of [false, true])`)가 final=true 안내·숨김·304/낮은 순번 거부·복원을 이미 검사한다. 남는 것은 320 px·시트 열림의 중복 커버리지 nit(P3 이하)이며 잘못된 동작이 없다.

## 3. WS 운영 라인(ws_operate/ws_alert)의 조용한 동작 변경 — 새 ops_armb_off 규칙 외

**없음.** 기준과 c47의 ws_alert.py 전체 diff는 542–550행의 9행 삽입뿐이고(`541a542,550`), ws_operate.py와 그 밖의 apps/observer/ops/*.py는 compare에 없다(173파일 목록 확인). 새 규칙은 거짓 복구를 보내지 못한다: 'armb' 키는 proc가 있는 running 세그먼트에서만 publisher 블록에 있고(ws_operate.py:809–813, running=True), 세그먼트 사이에는 키가 없어 엔진(process(), 601–660행)이 알림을 조용히 닫는다. 유일한 지적은 BE-2(의도적 armb='0'도 CRITICAL).

운영 라인 밖의 인접 변경(참고, 운영 동작 아님):
- ops 테스트 리그: test_ws_ops_alert_integration.py ~87행이 `self.wcfg['schedule'] = []`를 강제해 기본/실제 schedule 설정을 더 이상 읽지 않음(호스트 상태로부터 격리되지만 schedule 로딩 회귀는 여기서 안 보임). ~540행 try/finally로 stop 보장, supervisor 종료 단언은 `if sup is not None`일 때만(시작 단언이 먼저 실패하므로 통과 경우의 손실은 없음). test_ws_alert.py는 armb 테스트 추가만.
- 웹 클라이언트 정적 모드(전시 공개 빌드)의 요청 예산 변화: GameScreen.tsx:250 — health.json game_checks가 적용 순번과 맞으면 영원히 건너뛰던 게임 파일을 보이는 탭에서 60 s에 최대 1회 조건부 재읽기. 유효 game_checks가 있는 849843 탭당 약 health 6회/분(대부분 304) + 게임 1회/분 + manifest 1회/분(204행), 없으면 10 s마다 게임 읽기. 숨긴 탭은 0회(200, 227, 237, 335, 358행). 236행: health.json의 503 service_notice는 이제 전파되어 hold를 시작하고 그 밖의 health 실패(401 포함)는 여전히 삼킴. 416행: 안내가 전체 페이지를 교체하고 시트·버블을 닫음(352행), 복구는 새 본문 필요(api.ts:73/83/112가 hold 중 If-None-Match 생략, 304·낮은 순번 거부). 240행: hold 중 정상 health가 오류를 지우지 않음. 543–545·627행: 완료 경기 헤더가 항상 최종 점수·linescore. api.ts:414 + 624행: 쓸 수 없는 win_expectancy 슬롯이 'unavailable'로 정규화되어 승리확률 링크(완료 경기에서는 항상 '정보 없음')를 보일 수 있음 — 발행기 픽스처에는 키가 없어 849843에는 링크가 없을 가능성이 큼. model.ts:44 + 579/695행: receipt.reason 'held_last_accepted'는 정정됨 태그를 숨기고 기록 시트 한 줄로 집계(LivePanels.tsx:50). WatchList.tsx(옛 136행 hunk): 목록 재읽기의 안내가 화면의 목록을 비움.

## 4. 수행한 검사

- **정적·읽기 전용 검토**: GitHub compare `61be7a86fdea108caed975cdde98d63296be50ad...c47fe6cb78479362e7250141da946814cc33bd31`. compare는 87커밋·173파일이며, 범위(`apps/observer/**` + `scripts/publisher_replay.py`)는 91파일(added 66, modified 25; +4,856/−1,506). 범위 밖 82파일은 보지 않았다(단, backend-ops 슬라이스가 compare 목록으로 ops 모듈의 부재를 확인하면서 scripts/demo_precompute.py와 문서 2개도 0/0·패치 없음으로 나열됨을 참고로 적었다).
- **팀원 코드는 실행하지 않았다.** 빌드·설치·테스트·브라우저 렌더링 없음. 팀원 저장소에 쓰기 없음. 네트워크는 읽기 전용 GitHub API(compare, contents, issue #38 본문·댓글, PR #45/#50/#65 본문)만 사용. 픽스처 JSON 읽기(`python -I`)와 로컬 diff/grep은 데이터 검사이지 팀원 코드 실행이 아니다.
- **API 패치가 없는 범위 파일 8개와 읽은 방법**:
  1. `apps/observer/web/src/preview/replay/game-849843.json` (added, 1행) — 대상 커밋 전체 파일을 받아 `python -I`로 구조 분석(120,744바이트 1행, 65구·20타석, 키 연속성, 하프이닝 경계, rec provenance/recorded_at, tests/fixtures/service-849843.json `final` 변형과의 바이트 비교).
  2–4. `apps/observer/web/tests/fixtures/publish-ws-moments/849803/{last-rec,mid-rec,reference-card}/v1/game/849803.json` (added, 각 1행) — 읽기 전용 contents API로 first/mid/last-rec 게임 파일을 받아 실제 발행기 PA 모양(pitch_count 0·null 인덱스)·linescore_before·context_before·game_checks·display_state·win_expectancy 부재를 확인. reference-card 게임 파일은 compare 목록의 존재·1행 added만 확인하고 따로 열지 않았다.
  5–7. `apps/observer/web/tests/fixtures/publish-ws/{2026-10-24,2026-10-27,2026-10-28}/v1/game/{849805,849804,849803}.json` (added, 각 1행) — compare 목록의 존재·상태만 확인. 내용은 ws-gaps-smoke의 픽스처 전용 단언(COV-6)을 읽는 범위에서만 간접 참조했고 파일 자체를 따로 분석하지 않았다.
  8. `scripts/publisher_replay.py` (modified, API 0/0) — 기준·대상 전체 파일을 받아 로컬 diff. mode 100644 양쪽 동일(이름 변경 아님), blob `8520322b`(71,357 B) → `620d2668`(79,299 B). 변경: `--policy ledger`, `--ledger-*` 입력과 sha256/작업 폴더 검사, `--keep-moments` gzip 사본, summary/RUN.json 필드. 기본 armb/off 경로는 새 summary 키와 'moment' 열 외 변화 없음. gzip/hashlib import(43–44행), `from observer_app import ledger_policy`가 1168행 guard(observer_app.settings/main만 검사)에 걸리지 않음을 확인.
- **슬라이스별 검사(4 슬라이스, 읽은 파일 합계 약 70)**:
  - service-ui: GameScreen.tsx, api.ts, LivePanels.tsx, Sheets.tsx, model.ts 전체와 Zone.tsx 앞부분, 슬라이스 diff 전체. 기준 GameScreen.tsx 160–420행과 대상 diff로 load/hold/polling 변경 분리. 정적 모드 안내 처리 끝까지 추적(getPublished 503 본문 → isServiceNotice → 236 rethrow → 285 hold → 416 render gate → 354 retry → 332–337 interval → 253 requireBody → 257 해제). 401 추적. 완료 정적 경기의 요청 예산과 모든 타이머의 숨긴 탭 gate·무한 루프 검사(firstLoadRetry 오류당 4 s, missing 백오프 60 s 상한, 단일 비행). setAuto(false) 부재 grep. 완료 경기의 rec/actual/zone/sheet 선택 경로에서 추천이 다른 투구·타석과 짝지어지는 경로 없음. '과거 투구 기준' 문자열 부재(Sheets.tsx:123만 유사). CSS 분할: service-base.css가 기준 service.css 1–651행과 동일, 꼬리 51행은 service-layout.css로 대체, 규칙 없는 클래스는 id·측정 훅뿐, 존 행 높이 규칙 특이도 동일·뒤 규칙 우선, ≤359/360–399 px 미디어 블록 확인. 390/320 px 렌더링은 안 함. 발행기 픽스처(849803 game/health/manifest)와 publish.ts를 contents API로 읽음.
  - preview-replay: 슬라이스 7파일 전체 + vite.config.ts, index.html, package.json, src/main.tsx, publish.ts, tsconfig.json, .gitignore(web/루트), service-849843.json, 849803 moment 픽스처. 누출 검사: build:public = `tsc -b && vite build --mode public --outDir dist-public`(기본 config) → index.html:11 → /src/main.tsx가 src/preview를 import하지 않음(demo-operator import.meta.glob은 정적에서 제거) → 미리보기는 dist-public에 안 들어감. 남은 결합: `tsc -b`가 tsconfig include "src"를 덮으므로 src/preview의 타입 오류는 공개 빌드를 깨뜨림(읽기로는 없음, 확인은 tsc 실행 필요). 78단계 계산·투구당 체류·루프 산술. 미리보기 manifest publish_interval_s=2 → 정적 화면이 2 s 폴링(공개 10 s와 다름). provenance/live_source → 화면 문구 추적.
  - backend-ops-contract: ws_alert.py 전체 diff(9행 삽입만), ws_operate.py 대상 읽기, ws_alert process() 601–660행, publisher_replay.py 로컬 diff, ledger_policy.py vs live_ledger.admit/live_store.append_recommendation(결정 = (game, state_sha, policy_identity); 'first' 행만 표시, 단일 identity 요구, 중복 state 거부, pending_key 불일치 시 fail-closed, 읽기 전용 mode=ro&immutable=1·query_only; 두 nit: '-wal'만 검사하고 immutable=1이 hot '-journal'을 무시, 투구 단위 거부 문구가 일반 NO_ROW_REASON이 됨(문서화됨)). main.armb_view/display_state.view의 LEDGER_* 매핑. 전달받은 전시 game/849843.json의 262 rec 블록 전부 provenance 'asof_replay'(identity a6dffaea)라 ledger_policy는 전시 경로 밖. publish_schema.py CONTRACT_TYPES(157–169)와 스키마 diff 3개 대조, infer() → _add_types 리팩터는 동작 동등. 전달받은 setup/games/game JSON으로 기준 스키마 거부 확인. 스키마 재생성 테스트는 실행 안 함.
  - test-coverage: issue #38 본문·댓글, compare 커밋 메시지(dfdd40a4, f11de37f, fba6b2ff, 790f1fbe/5e44e69e), PR #45/#50/#65 본문 읽기. c47·기준 테스트 파일 11개 전체를 받아 diff(display-state-smoke, static-publish-smoke, ws-launch-layout-check, compact-rev3-fit, studio-layout-check, zone-geometry-check, zone-label-clip-check, ui-preview, ws-gaps-smoke, ui-review-followups-check; notice-hide-smoke는 new-file 패치에서 재구성 후 contents API 사본과 대조). 픽스처 990003(live, final:false)·849843(final, final:true) 확인. 모든 service/preview TSX(HostSlot/Reference/SyncSheet 포함)에서 단언 클래스명 grep으로 항진 선택자 식별. 주장↔테스트 매핑(안내 숨김/복원, 재노출 없음, 완료 경기 실패 표시, 과거 투구 문구, 60 s 재검증 예산).
- **선행 관찰 재확인**: GameScreen.tsx:332(API 모드 완료 경기 pollMs 0), :354(재시도 0/5xx만), :357(404 재시도는 `__PZ_STATIC__`만) — 확인. 정적 모드는 detail !== null인 동안 폴링 유지 — 확인. SVC-4로 기록.
- **회의론자 단계**: 유지 후보 7건 각각을 3명의 독립 회의론자가 줄 번호·코드 인용·시나리오로 재검토(위 각 항목의 판정 요약). 모두 정적 읽기이며 회의론자도 실행하지 않았다.

## 5. 검토 모델과 규칙

- 분할 검토자(4 슬라이스: service-ui, preview-replay, backend-ops-contract, test-coverage)와 회의론자(후보당 3명)는 'opus' 모델 옵션으로 선택한 Claude 에이전트다. 오케스트레이터는 Claude Fable 5.1(이 문서 작성 포함). 에이전트들의 정확한 모델 ID는 이 기록으로 증명되지 않는다. 같은 계열 모델의 보조 검토를 "다른 모델 검토"로 세지 않는다.
- 유지 규칙: 후보마다 회의론자 3명의 다수결. 2명 이상이 기각하면 기각, 아니면 유지. 심각도는 분할 검토자의 기록값을 두고 회의론자 권고를 병기했다(PREV-2는 2/3, COV-1·COV-3는 3/3이 P3 권고; PREV-3는 1/3).
- 이 문서는 전달받은 유지/기각/P3 기록을 옮긴 것이며 작성 단계에서 새 코드 검토를 추가하지 않았다. 작성 단계에 전달된 P3 기록이 COV-8에서 절단되어 COV-8 전문·COV-9는 오케스트레이터(Claude Fable 5.1)가 분할 검토 원본 기록에서 그대로 보완했다.

## 6. 한계

- 정적 검토다. 런타임·실제 폰·호스트 검증을 하지 않았고 테스트 스위트를 실행하지 않았다. 390/320 px 렌더링, 존 라벨 잘림, 안내 복원 지연, `tsc -b` 통과 여부는 실행 없이는 확인할 수 없다.
- 팀원 자신의 테스트 결과(PR #50/#65의 411/1·416 보고 등)를 대체하지 않으며, 우리 쪽 호스트 인수(24/24 HTTP·iPhone 사용자 확인·저장 로그 대조)를 대체하지도 않는다.
- 공개 849843 전체 파일은 이 compare 범위에 없어 PREV-3의 비교는 우리 쪽 전시 점검 사본(읽기 전용)으로만 했다. 전시 JSON은 c47이 아닌 cb1cfa8에서 생성되었다는 전달자 선언을 그대로 둔다.
- 전시 health.json의 두 데이터 전제(참고): game_checks['849843']가 있지만 형식이 틀리면 maskPublished(433행)가 추천을 '확인 중'으로 영구히 가리고, 완료 경기에서 '갱신 지연'이 뜨지 않으려면 게임 파일의 publish.final이 true여야 한다(484행 timeWarnings). 전달받은 파일은 final=true·next=null로 알려져 있으나 이 검토에서 health.json의 game_checks 형식을 재검증하지는 않았다.
- 범위 밖 82파일과 scripts/demo_precompute.py(약 11행 변경, 리허설 metaData.timeStamp가 날짜 기반 스탬프; state_key는 metaData를 읽지 않아 추천 state 무관)는 이번 판정에 포함하지 않았다.

## 7. 판정

**PASS_WITH_NOTES** — 공개 정적 전시 경로에 남은 P1은 없고, 유지된 P2 6건은 API 모드·미리보기 재생·테스트 범위에 있으며, 모니터 1에서 미리보기 재생을 관람자에게 보여줄 계획이라면 PREV-1(거짓 출처 표기)과 PREV-2/3(65구 절단·루프)을 먼저 처리하거나 재생을 운영자 전용으로 둔다.
