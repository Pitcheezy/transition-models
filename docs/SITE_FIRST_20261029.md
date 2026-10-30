# 사이트 우선 연결과 형 서비스 코드 확인 — 2026-10-29

사용자가 사이트 완성을 CV보다 먼저 진행하도록 우선순위를 바꿨다. 같은 날 Song 저장소를 읽어 시연의 데이터 입력 방식을 확인하도록 명시적으로 승인했다. 이번 범위는 **우리 로컬 사이트 동선과 상대 코드의 읽기 전용 조사**다. 상대 파일·프로세스·배포, 우리 Cloudflare와 공개 Site는 변경하지 않는다. 목표와 현재 담당은 [PLAN](../PLAN.md)과 [CHECKLIST](../CHECKLIST.md)를 따른다.

## 확인한 소스와 결론

GitHub 연결 도구로 다음 참조를 고정해 읽었다. 저장소의 코드 존재와 실제 실행 중인 버전은 다르다.

| 참조 | 확인한 전체 커밋 | 해석 |
| --- | --- | --- |
| Song `main` | `70aa5499eb261e57c85c5c54e84ea27f869dae50` | 9/23 기준이며 최신 서비스 전체를 대표하지 않는다. |
| Song `rc/ws-2026` | `e39bb41a10901a06b50b54121b70866cdc2e0610` | 자동 피드·ARM-B·재생 경로를 확인한 RC 소스다. |
| Song `ws/rs01-tfinal-fix-1029` | `7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8` | 10/29 공개 브랜치에서 같은 핵심 경로를 다시 확인했다. 운영 채택이나 배포를 뜻하지 않는다. |

**형 서비스에는 경기 데이터를 자동으로 받아 로컬 모델로 추천을 계산하는 코드가 있다.** 매 공의 카운트나 결과를 사용자가 직접 입력해야 하는 구조는 아니다. 아래 링크는 모두 마지막 표의 10/29 커밋에 고정했다.

1. **MLB 경기 데이터 → 현재 상황:** [live_feed.py](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/backend/observer_app/live_feed.py#L361)는 일정과 경기별 `feed/live`를 조회한다. [설정](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/live_config.json#L4)의 조회 간격은 기본 10초, 조건부 5초다. 영상 OCR이 아니라 경기 데이터에서 투수·타자·카운트·주자·점수를 읽는다.
2. **현재 상황 → ARM-B 추천:** [live_armb.py](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/backend/observer_app/live_armb.py#L246)의 작업 스레드가 `self.policy(feed)`를 실행한다. [LivePolicy](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/scripts/demo_precompute.py#L907)는 현재까지의 기록과 다음 공 자리표시 행을 사용한다. [투구 전 호출](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/scripts/demo_precompute.py#L806)은 실제 선택 행동을 제거한 뒤 평가한다. 동결된 ≤2025 ARM-B 정책 식별자 `a6dffaea70976368a9cdc9f1a8bff4267b1c138162ee48aafda00e81e989109c`와 등록 부품을 검사하며, 가중치·자료는 로컬 저장장치에 의존한다.
3. **추천 → 발행 파일:** [publisher.py](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/backend/observer_app/publisher.py#L1)는 관람자 요청 없이 같은 서비스 builder를 주기적으로 호출한다. 이 호출이 피드 조회를 진행시키고 `v1/manifest.json`, `health.json`, 날짜·경기 목록과 경기 JSON을 만든다. HTTP 업로드는 선택 기능이며 [저장소 기본 설정](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/publish_config.json#L29)은 OFF다.
4. **발행 파일 → 관전 화면:** [공개 빌드](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/package.json#L9)는 `dist-public`을 만든다. [화면 수신기](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/src/service/api.ts#L341)는 공개 모드에서 정적 JSON, 일반 모드에서 로컬 서비스 API를 읽는다. 우리 호스트는 이 공개 파일과 업로드 계약을 받으며 모델을 대신 실행하지 않는다.

## 라이브·재생·지원 범위

| 모드 | 자료와 계산 | 의미 |
| --- | --- | --- |
| 진행 경기 라이브 | MLB 피드를 자동 조회하고 ARM-B로 새 상황을 계산 | 코드 경로 확인. 현재 실행·실제 지연·투구 전 도달률은 별도 확인이 필요하다. |
| 종료 경기 시간순 재생 | 저장된 최종 피드나 녹화본을 같은 경로에 시간순으로 공급 | 자동 진행돼 보여도 실제 진행 중 경기라는 뜻은 아니다. |
| 저장 경기·시연 | 저장된 추천과 실제 결과를 선택한 순서로 공개 | 우리 첫 타석 3구 데모가 여기에 해당한다. |

[main.py의 transport 선택](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/backend/observer_app/main.py#L304)은 재생 폴더 설정이 없으면 HTTP, 있으면 녹화본을 사용한다. [라이브 화면의 `replay` 분기](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/backend/observer_app/main.py#L558)도 별도로 있다. 사용자가 본 시연의 모드는 코드만으로 확정하지 않았다.

**모든 MLB 경기의 모든 투구에 추천을 제공하는 것은 아니다.** 일정의 경기 유형 허용과 모델의 지원 범위는 다르다. [runtime](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/experiments/pitchmdp/pitchmdp/policy_runtime.py#L315)은 학습 기록 없는 투수의 리그 평균 대체를 거부하고, 지원 구종 없음·이력 불일치 등에서 기권한다. 옛 6투수 번들의 제한을 현 ARM-B 서비스에 그대로 적용하지 않는다. 정확한 지원 명단·실행 가중치와 시연 당시 커밋은 별도 확인 사항이다.

공급자 README의 시간 수치나 포스터의 성능 수치는 실행 원장까지 재측정하지 않았다. 후속 [포스터 대조](POSTER_REPO_AUDIT_20261029.md)에서 고정 집계와 공급자 운영 보고를 구분했다. 우리 실측이나 전경기 성능으로 표시하지 않는다. 저장 응답의 구종 선택 비중도 스트라이크·안타 사건확률이나 실제 승리확률 개선으로 바꾸지 않는다.

## 서로 다른 세 화면의 상태

- **기존 공개 Site:** 이번 세션에서 Sites 메타데이터의 공개 버전9와 브라우저의 홈→첫 타석을 실제 조회했다. 저장된 실제 첫 타석 3구와 추천·결과 비교이며 화면에도 실시간 모델 추론이 아니라고 표시한다. [기존 사이트 기록](INTENT_DEMO_SITE.md)과 [수신 화면 기록](PITCH_STUDIO_RECEIVER.md)을 참고한다. 형의 최신 라이브 서비스가 연결됐다는 근거로 사용하지 않는다.
- **10/26 별도 시험 호스트:** Song final2/v4.4 `000e4ba0d83bb81fee8db82539e67c7ab0e7d0b3`와 우리 호스트로 실제 클라우드에서 합성 전송시험을 실행했다. 전체 판정은 **STOPPED/미완**이다. 두 요청의 로그 대조와 당일 회수 응답 확인이 남았다. [고정 종료 보고](https://github.com/Pitcheezy/transition-models/blob/77b958dbf3424c8c69259127cc7f2b93511c42ee/docs/WS_JOINT_TRIAL_CLOSEOUT_20261026.md)를 따른다. 실제 경기 공개 서비스나 새 UI 채택과 구분한다.
- **최신 Song UI 후보:** 10/27 운영 기록의 `d0d25eda` 등은 상대 보고 후보다. 우리 채택·인수·배포는 확인되지 않았다. [고정 비CV 현황](https://github.com/Pitcheezy/transition-models/blob/77b958dbf3424c8c69259127cc7f2b93511c42ee/docs/WS_NON_CV_STATUS_20261027.md)과 기존 [Song #38 요청](https://github.com/SongRoute/pitcheezy/issues/38#issuecomment-6434440631)의 인수 기준을 유지한다.

## SITE-1 로컬 동선과 다음 SITE-2

**현재 변경:** 아래 SITE-1의 새 홈은 비교용 후보로 보존한다. 후속 SITE-1c에서는 사용자 요청대로 기존 `index.html`의 디자인·영상을 유지하며 문구·수치와 실제 재생 동선을 정정했다. 로컬 메뉴는 기존 홈으로 통일했다. 공개 사이트 교체는 하지 않았다.

SITE-1은 `codex/site-first-1029`에서 준비하는 **로컬 초안**이다. 새 진입 페이지를 만들고 기존 수신 화면의 이동 메뉴를 연결한다. 공개 홈 교체·새 Sites 프로젝트·실시간 서버 연결은 포함하지 않는다.

| 페이지 | SITE-1의 역할 | 후속 연결 원칙 |
| --- | --- | --- |
| [exhibition.html](../web/pitch-studio/exhibition.html) | 홈, 추천을 먼저 보고 실제 결과를 확인하는 순서와 첫 타석 진입 | 비교용 홈 후보다. 기존 공개 홈의 디자인·영상을 보존하고 채택할 요소를 연결한다. |
| [games.html](../web/pitch-studio/games.html) | 저장된 849843 첫 타석 3구와 준비 중인 실시간 관전을 구분 | 채택된 Song 경기 목록·관전 화면으로 연결한다. |
| [guide.html](../web/pitch-studio/guide.html) | 추천 비중·근사 위치·저장/라이브 차이·미트 근거의 한계 설명 | 채택 화면의 실제 지원 범위에 맞춰 갱신한다. |
| [receiver.html](../web/pitch-studio/receiver.html) | 기존 저장 데모와 결과 공개 기능, 홈·경기·안내 이동 | 저장 데모를 보존하고 Song 라이브 관전 본체를 중복 구현하지 않는다. |
| [report.html](../web/pitch-studio/report.html) | 기존 관측·검증 기록으로 연결 | CV는 결과 공개 뒤 근거가 있을 때 추가한다. 기본 관전의 선행 조건으로 삼지 않는다. |

다음 **SITE-2**는 기존 #38 흐름에서 채택할 Song 화면을 정하고, 전체 커밋·원본 빌드/manifest/ZIP SHA·작성/검토 근거를 받아 로컬에 연결하는 단위다. 정상 추천, 미지원, 확인 중, 연결 끊김, 안내 ON에서 추천 숨김, 오류 뒤 과거 추천 재노출 방지와 복구를 확인한다. 형 모델·발행기·관전 본체는 재사용하고 우리 진입 동선과 호스트를 연결한다. 새 요청 발신·상대 수정·배포는 이번 단위에서 하지 않는다.

## 로컬 검사와 관찰

- SITE-1의 `python scripts/check_pitch_studio.py`: 모든 HTML 상대 링크·JS 구문, 실제 3구 playId/영상/포스터 SHA, 기존 4투구 reel SHA, 기존 home/receiver Node 회귀 통과. 합성 예시와 실제 응답의 구분 유지. 이 최초 단계에서는 기존 영상 바이트·모델 결과·수신 JS를 변경하지 않았다. 후속 SITE-1b는 아래처럼 수신 JS의 표시 부분을 확장했다.
- 실제 IAB Chrome: 홈→경기→안내→첫 타석 경로, 1구 영상 실제 재생 종료 뒤 결과 공개, 2구 이동 뒤 이전 결과 숨김을 확인했다.
- 1280px와 390px 크기 설정에서 신규 페이지를 확인했다. 최초 390px 검사 당시 `innerWidth=390`, 문서 `clientWidth=scrollWidth=375`로 15px는 세로 스크롤바 차이였다. 현재 IAB의 확대율에 따라 설정 폭과 실제 CSS 폭이 다를 수 있어 SITE-1b에서는 실제 측정값도 아래에 남겼다. 브라우저 크기 모사이며 iPhone 실기기 검사는 아니다.
- 새 홈은 `exhibition.html`이라는 후보 진입점이다. 기존 공개 `index.html`은 교체하지 않았다. 공개 사이트·Cloudflare·팀원 코드·실행 프로세스 변경 없음.
- 체크리스트 형식 검사 `python -m pytest tests/test_checklist_model.py -q`: 8 passed.
- 고정 `0be7fdd7e8d4f1e2a25f2edb9577424c2f682ee1`의 사이트 변경분은 사용자 구체 승인 후 `claude-fable-5-1`에 한 번 읽기 검토받았다. 아래 검토 기록을 따른다. 최종 배포 승인이나 후속 새 코드의 검토로 확대하지 않는다.

로컬 재현: 저장소 루트에서 `python -m http.server 0 --bind 127.0.0.1 --directory web/pitch-studio`를 실행하고 출력된 주소에 `/exhibition.html`을 붙인다. 서버가 실행되는 같은 컴퓨터에서만 열린다.

## SITE-1 다른 모델 검토와 조치

- 작성: Codex. 검토: 실제 Claude Code `claude-fable-5-1`, 고정 0be7fdd의 7파일 변경분만, 실행 도구 없음·정적 검토. 실제 호출 종료0, 경과117.547초, `request_changes`, 중간1·낮음9. 검토 모델은 테스트를 실행하지 않았다.
- 실행 옵션: `claude --print --model claude-fable-5-1 --effort medium --permission-mode plan --restricted --strict-mcp-config --tools '' --no-session-persistence --output-format json`. 격리된 임시 작업 폴더에서 승인된 변경분만 전달했다. 전체 원응답·프롬프트는 Git 제외 outputs에 보존한다.
- `0c859fa645b5452551bd74b6a7d95cb292809e51`: 가이드의 현재 3구 범위, 홈 링크/장식문자 접근성, 제목·탐색·푸터 일관성, 경기 제목의 대비, 모바일 최소44px 링크, 미사용 CSS 및 클릭처럼 보이는 장식 화살표를 수정했다.
- 미지원 표시 자체는 기존 `receiver.js`의 `view.pre.status` 분기와 계약 검사에 존재한다. 그러나 현재 실제 첫 타석 3구 모두 추천이 있으므로 가이드도 그 범위로 좁혔다. 추천 위치의 과거 분포 근사는 기존 receiver의 과학 설명 및 공급자 설명과 대조해 유지했다.
- 폭 기록의 15px 차이는 스크롤바 구분으로 보완했다. 수정 후 기존 검사와 브라우저 경로를 확인했다. **수정 후 Fable 재검토는 미실행**이며 최초 `request_changes`를 `approve`로 바꾸지 않는다.

## SITE-1b: 영상 옆 추천·실제 좌표 비교

같은 저장 응답을 사용하는 반응형 도표를 기존 `receiver.html`에 추가했다. PC는 영상 옆, 좁은 화면은 영상 아래다. 형의 관전 본체나 모델을 복제하지 않고 기존 3구 데모의 표시만 확장한다.

- 녹색 숫자는 추천 순위, 주황색 원은 결과 공개 뒤의 실제 공 위치다. 같은 추천 좌표는 `1·3`처럼 순위를 함께 적고 모든 수치 행을 유지한다. 표시를 위해 좌표를 밀거나 도표 안으로 잘라 넣지 않는다.
- 고정 축 x −2~2ft, z 0~5ft, 같은 단위의 가로·세로 눈금. **타자별 스트라이크존이 아니다.** x는 제공 응답의 포수 시점, z는 지면 높이다. 실제 값은 플레이트 통과 위치이며 포구 지점이 아니다. 미트 높이나 제구 오차를 계산하지 않는다.
- `receiver-location.js`는 현재 `session.view()`만 받는 순수 표시 모델이다. 결과 공개 전 `post`를 읽지 않고, 누락·비유한 값·도표 밖 좌표는 점으로 만들지 않는다. 다음/이전 투구·숨김·자료 초기화 때 기존 도형과 접근성 설명을 지운다.
- 기존 모델 응답·영상·미디어 등록부·계약 버전은 불변이다. receiver JS/CSS의 URL 버전을9, 후속 검토 수정에서10으로 바꿔 오래된 캐시 파일과 새 HTML의 혼합을 방지했다.

### 실행한 검사

- `node --test tests/js/pitch_receiver_location.test.cjs tests/js/pitch_receiver.test.cjs`: 새13+기존37=50통과. 투구 ID/키 연결, 결과 누출 방지, 누락·범위 밖 값, 중복 위치, 전환·초기화, 입력 불변을 검사했다.
- 최종 `python scripts/check_pitch_studio.py`: 새 위치 검사와 기존 5개 Node 검사 파일, HTML 상대 링크·JS 구문, 실제3구/4투구reel SHA 통과.
- `python -m pytest tests/test_checklist_model.py -q`: 8통과. `git diff --check` 통과.
- 실제 Windows IAB Chrome: 1구 공개 전 추천3·실제0 → 공개 후 실제1, 2구 전환 실제0·공유좌표 `1·3`, 2구 공개 `(1.28,1.48)`, 3구 전환 실제0 → 공개 `(-0.41,2.97)`, 숨김 뒤 실제0·접근성 설명에서도 제거, 3구 영상 실제 재생 종료→결과 자동 공개, 자료 비우기→모든 점·수치 제거를 확인했다. 1구 실제 값 표시는 `(0.50,2.40)ft`다. 소수 둘째 자리의 표시는 원좌표 변경이 아니다.
- 데스크톱 설정1280에서 실제 CSS `clientWidth=scrollWidth=1150`; 모바일 설정390에서 `innerWidth=355`, `clientWidth=scrollWidth=341`. 모바일 도표는 영상 아래이며 가로 넘침이 없었다. 임시 화면 크기 설정은 검사 뒤 해제했다. 실제 iPhone/Mac 검사는 아니다.
- 포스터 원본은 수정하지 않고 [대조·권장 문구](POSTER_REPO_AUDIT_20261029.md)를 작성했다. 기능과 운영 보고·평가 수치의 범위를 구분한다.

### SITE-1b 고정 검토와 수정

사용자는 새 고정 `eedf2f2e8ef8d6682c6412c7908742870a97d553`의 사이트 코드8개·좌표검사1개·이 요약을 Claude에 한 번 읽기 검토하도록 추가 승인했다. 실제 `claude-fable-5-1`, 종료0·179.860초·도구 없음·`request_changes`. 중간2·낮음3·선택3이며, SITE-1의 앞선 지적은 제공 소스에서 해결됐다고 확인했다. 원문은 Git 제외 outputs에 보존한다. 모델은 직접 검사나 브라우저를 실행하지 않았다.

수정한 항목:

- SVG 접근성 설명의 수치 행이 `ft2`처럼 붙는 현상: 행 사이에 `; `를 넣어 구분했다.
- 고정24px 상자에서 겹친 순위 글자가 넘는 현상: 글자 길이에 맞춰 상자 폭을 정하고, 7글자보다 긴 순위는 `1+29`처럼 축약한다. 전체30행·원좌표는 그대로 남기는 새 회귀1개를 추가했다.
- 잘못된 표시 모델이 예외를 내는 경로: 기존 `reportError`로 전체 자료와 표시를 비운다. 정상 계약 검사를 통과한 현재 입력에서는 예외가 재현되지 않았으며 방어 경로를 보완한 것이다.
- 고정 `1–3` 범례를 제거하고 동일 위치 묶음·축약 읽는 법을 화면에 추가했다. 경계 눈금 여백과 중복 live-region 알림도 보완했다.
- 홈의 밝은 배경 경기 구분자 대비를 어둡게 했다. 기존 receiver의 제품 메뉴는 보존하며, SITE-2 관전 본체 연결 때 메뉴를 통일한다.

수정 후 `check_pitch_studio.py` 전체 통과, 위치 신규14+기존37=51검사. 실제 브라우저에서 공개 전 실제0·공개 후 실제1, 행 구분자를 포함한 접근성 설명, 범례·화면을 확인했다. 이전 미디어 SHA는 동일하다. **이 수정 후의 추가 Fable 재검토는 하지 않았으며 최종 approve로 기록하지 않는다.** [PR85](https://github.com/Pitcheezy/transition-models/pull/85)는 PR84 위의 로컬 후보이며 공개 배포·최신 Song 화면 채택과 별도다.

## SITE-1c: 제품 예시 제거·실제 모델 근거 인용

사용자10/29 후속 지시로 기존 예시 숫자를 실제 모델 근거에 맞췄다. 기준 `3f7c337d5bd2350d4bd11fea92a5fa238917c3ce`, [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6491866436). 기존 커밋의 Ubuntu/macOS CI 2건 성공은 확인했지만 이번 후속 변경의 CI 결과로 인용하지 않는다.

- 기존 `index.html`의 영상·레이아웃을 유지하고 포스터의 “다음 공, 무엇이 최선일까?”와 팬을 위한 관전 보조 문구를 반영했다. 소개는 경기 선택→저장 추천→실제 결과→근거 확인이다. 미구현 제구/타격 점수·교체 효과의 광고를 제거했다.
- `service.html`은 더 이상 예시 확률·점수를 불러오지 않는다. 옛 `?phase=manager` 같은 링크도 실제 재생 진입 화면을 보여준다. `preview-data.js`·`studio.js`는 기존 이력과 검사 자료로 보존하지만 모든 제품 HTML에서 연결을 금지한다. `home.js`의 옛 `#analysis` 링크도 이 진입 화면으로 이어진다.
- 홈에는 개발 평가 NLL 감소0.0137과 **별도** 리허설 계산 중앙값0.13초를 출처 바로가기에 붙였다. `guide.html#model-evidence`에는 분모311,721구, 비공개 수집263구/지원185구 중 추천180구, 구종만 바꾼 정책의 승리확률 차이 경계−0.12~+0.09%p를 설명했다. +0.09를 향상으로 표현하지 않으며 모든 인용은 [포스터 대조](POSTER_REPO_AUDIT_20261029.md)의 고정 원문에 근거한다. 새 추론·재평가가 아니다.
- 실제 CV86장/58출력/28기권 기록은 `report.html`·`data.js`에 보존했다. 실제 저장 추천·좌표·미디어·계약 원자료도 변경하지 않았다. 미트 연구 표시와 모델 평가를 구분한다.
- `build_pitch_demo_bundle.py`의 자산 목록에 신규 페이지/CSS/좌표JS를 포함하고 예시 전용3자산을 제외했다. 기존 ZIP·발표 자료·비공개 비교 이미지는 수정하지 않았다. 전체 발표팩을 새로 발행하거나 전달한 것은 아니다.
- 브라우저가 이전 모바일70px 스타일을 사용한 것을 확인해 `product.css?v=11`·`exhibition.css?v=2`로 버전을 명시했다. 모바일 NLL 숫자는 약31.9px로 렌더링되며 넘침이 없다.

검증:

- `python scripts/check_pitch_studio.py`: 제품 HTML의 예시 자산 참조0, JS/상대링크·실제3구/4구reel SHA·기존6개 Node 검사 파일 통과. `python -m pytest tests/test_checklist_model.py -q`:8통과.
- 로컬 사이트 자산33개를 새 폴더에 복사하고 ZIP CRC·해제 바이트·내부 링크/앵커를 확인했다. 검사용 최초 네이티브 앵커 가정은 기존 report의 hash routing과 맞지 않아 실패했으며, `data-view`/`view-*` 라우팅을 확인해 검사를 정정했다. 최종 사이트 부분팩 검사 통과; 전체 발표팩/실기기/공개 배포 검사는 아니다. 세부 영수증은 Git 제외 `outputs/site1c_site_assets_20261029_final/receipt.json`.
- Windows IAB: 기존 홈→모델 근거→경기→첫타석, 실제1구 공개 전/후 좌표, 옛service query의 새화면과 스크립트 없음, 홈 돌아가기 확인. 데스크톱 설정1280의 CSS폭1150, 모바일 설정390의 CSS폭341에서 가로 넘침 없음. 모바일 실기기와 구분한다.
- 같은 모델의 보조 에이전트가 예시/실제 자료 구분과 문구·출처를 정적 대조했다. 다른 모델 검토를 대체하지 않는다. SITE-1c를 Claude에 새로 전송하지 않았으며 고정0be7fdd/eedf2f2의 사용자 승인 범위를 확대하지 않았다. **최종 교차검토·main 통합·공개 배포는 미완료**다.

다음: 고정 수정본의 교차검토 후, SITE-2 채택된 Song 관전 빌드를 기존 파일 계약으로 연결한다. 팀원 코드·Cloudflare·평가 잠금 원자료·보류한 사람 검토·기존 팩은 보존했다.
