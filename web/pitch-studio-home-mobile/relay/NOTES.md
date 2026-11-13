# 관전 화면 시안 A(relay) — 작업 노트 (2026-11-03)

> **이후 경과(2026-11-12 저녁 기준).** 11/12 15:29 KST에 공개 앱을 Song c47 빌드 + 접속 코드 ON으로 되돌렸다(CHECKLIST `EXHIBIT-rollback1`). 15:49에 #38에 회신했고(댓글 6816876891), 16:49에 Song이 답했다(댓글 6817925715: 공동시험 11/13 21시, 색 테마 조건부 동의, 3D 타자 보류). 아래 본문은 작성 시점 기준이다. "현재", "미발신", "되돌린 적 없음", "미커밋" 같은 표현은 그 시점의 것이다. 저장소에는 `relay/data/`, `captures-20261108/`·`captures-20261109/`, GPT 프롬프트 메모, 3D 모델 파일을 넣지 않았다(저장소 밖 보관). 화면을 열려면 Song 발행 `849843.json`(SHA-256 `056fcf13a08c1831a92383e0cf8e1782d201eae9b61e159e65d2c847b78c2ab6`)을 `relay/data/`에 둔다.

로컬 데모 전용 하루짜리 시안. 공개 배포·Song 전달 아님. 열어 보는 주소: `http://localhost:8790/relay/` (서버 루트 = `web/pitch-studio-home-mobile/`).
완료 경기 849843(CHC @ SD, 2026-09-30 KST, 최종 0:8)의 262구를 Song 발행 파일(c47fe6cb 묶음, schema `pitcheezy-service-game-v2`)로 **저장 재생**한다. 화면 어디에도 "LIVE"라고 쓰지 않았다.

## 파일
| 파일 | 역할 |
|---|---|
| `index.html` | 뼈대(헤더·상단 탭·자동 진행·점수 띠·존 그림 틀·투구 패널·이닝 탭·타석 목록·라인업·기록·하단 안내). 외부 자원 0, 인라인 SVG 파비콘·실루엣 |
| `relay.css` | 테마 토큰(`--bg #091811 --panel #11241b --ink #f2f4e9 --muted #a5b6a8 --line #304438 --lime #ceff78 --orange #ffb782`), "Segoe UI"/"Malgun Gothic", 390 기준 320~430 대응, 터치 44px, 본문 16px, 431px 이상은 430px 열 가운데 정렬 |
| `relay.js` | `fetch('./data/849843.json')` → 렌더. 순수 함수(좌표 변환·결과 분류·득점 타석·타순 도출)는 `module.exports`로도 내보내 node 검증에 썼다 |
| `data/849843.json` | 읽기 전용(Song 발행). `data/849843-setup.json`은 **쓰지 않았다**(검토 전 추정) |

## 네이버 중계 탭에서 참고한 것 / 우리가 새로 만든 것
| 참고한 것(구성·흐름만) | 우리가 새로 그린 것 |
|---|---|
| 세로 배치 순서: 점수 띠 → 메인 그림 → 이닝 탭 → 타석 카드 목록 | 모든 색·간격·글꼴(테마), 존 SVG(격자·표식·화살), 타자 실루엣(인라인 SVG 직접 작도, 좌타는 CSS `scaleX(-1)`), 주자 다이아몬드, B/S/O 점, 스위치, 칩·배지 |
| "자동 업데이트 · N초 후" 개념 → "저장 경기 재생 · 자동 진행 · N초 후 다음 투구" | 문구는 전부 데이터 값으로 생성, 없는 값은 '자료 없음' |
| 이닝 탭에 '득점' 탭을 두는 흐름, 타석 카드에 투구 줄을 펼치는 흐름 | 네이버의 3D 그라운드·아이콘·애니메이션·문구·이미지는 **하나도 복사하지 않았다** |
| 상단 탭(중계/라인업/기록) — 전력·뉴스·영상 탭은 자료가 없어 만들지 않음 | 라인업·기록 탭 내용은 pas/linescore에서 도출 |

## 데이터 매핑
| 화면 | JSON 경로 | 변환 / 없을 때 |
|---|---|---|
| 점수 띠 점수·이닝·B/S/O·주자 | `pitches[i].situation_before.{away_score,home_score,inning,half,balls,strikes,outs,runners}` | half `Top`→초, `Bot`→말. 띠에 "이 공 던지기 전" 알약 표기 |
| 투수·타자 | `pitches[i].pitcher/batter {name,jersey,hand/side}` | `이름 (등번호) · 우투/좌투/우타/좌타/양타`, 없으면 '자료 없음' |
| 누적 기록 한 줄 | `pitches[i].context_before.batter{at_bats,hits}`, `.pitcher{pitches,strikeouts,earned_runs}` | 값 그대로 |
| 존 그림 — 타석 투구 원 | `pas[j].first_index..last_index` 의 `pitches[].actual.{x,z,description,pitch_label}` | 번호 = `pitch_number`; 색 = description 분류(아래) |
| 존 그림 — 추천 네모 | `pitches[i].rec.candidates[].{rank,target{x,z}}` (status `ready`일 때만) | 같은 target(.05 ft 이내)은 '1·3'처럼 한 네모 |
| 존 범위 | `zone_bounds {bottom 1.6, top 3.3899}` + 가로 ±0.83 ft | 창 = 존 ± (x .42, z .45) ft = Song **상세 시트(fullWindow)** 창 여백(라이브 메인 창 .12/.24보다 넓음), 창 밖 표식은 점선+화살로 가장자리에 |
| 추천 칩 | `rec.candidates[].{rank,pitch_label,zone_label,detail.probability}` | `% = round(p×100)`; 아래 줄에 "위치 이름의 왼쪽·오른쪽은 포수 기준(그림은 투수 시점이라 좌우 반대)", `rec.recorded_at`, `rec.policy.name` |
| zone_label의 좌우 | `rec.candidates[].zone_label`, `actual.zone_label` | **포수 기준**이다(1구 후보 3 `high_left` '높은 왼쪽' target.x = −0.553 / 실제 1구 '가운데 높이 오른쪽' x = +0.502). 그림은 투수 시점(VIEW_X = −1)이라 '왼쪽' 네모가 화면 오른쪽(+55)에 그려진다. 라벨은 바꾸지 않고 칩 아래 줄·'위치' 행 "(포수 기준)"·범례 한 줄로 기준을 적는다. Song 화면도 zone_label을 그대로 쓴다 |
| 추천 미지원 | `rec.status ≠ ready` → `rec.reason` | "추천 미지원 (unsupported) · 사유" (16구, 투수 Ryan Rolison) |
| 실제 투구 표 | `actual.{pitch_label,pitch_type,speed_mph,call_label,result_label,zone_label,x,z}`, `actual.tracking.{spin_rate_rpm,extension_feet,exit_velocity_mph,launch_angle_deg,distance_feet}` | km/h = round(mph×1.609344); 익스텐션 소수 1자리; 타구 3값 null이면 '자료 없음'(215구); 비거리 m = round(ft×0.3048) |
| 타석 결과 | `pas[j].{event,event_label,result_text,pitch_count,batting_order}` | 배지 문구 = event_label, 배지 색 분류는 event 코드로 |
| 투구 줄 | `pitch_number · actual.pitch_label · km/h · actual.result_label` | |
| 득점 탭 | 타석 첫 투구의 `situation_before` 점수 vs 다음 타석 첫 투구의 점수(마지막 타석은 `game.away_score/home_score`) | 바뀐 타석 7개. **득점 시점**도 구분: 타석 안 투구 사이에서 `situation_before` 점수가 바뀐 첫 투구가 있으면 "N구 전(타석 중)", 마지막 투구 전 점수와 타석 뒤 점수가 다르면 "타석 결과"(둘 다면 '+'). 5회 말 Austin Hays(삼진)는 2구 전(index 141→142, 0:6→0:7), 7회 말 Dustin Harris(1루타)는 5구 전(200→201, 0:7→0:8)에 점수가 났고 나머지 5타석은 타석 결과. 카드·기록 탭 목록에 적고, '그 타석 보기'는 타석 중 득점이면 그 투구(2구/5구)로 간다 |
| 라인업 | `pas[].batting_order`·`batter` (공격 half별 첫 등장 = 선발, 이후 = 교체), 투수는 상대 half의 `pitcher` 등장 순, `game.probable_pitchers` | CHC 8번 Carson Kelly → 교체 Michael Conforto, SD 2번 Samad Taylor → 교체 Dustin Harris |
| 기록 | `linescore.innings[]`, `linescore.teams.{runs,hits,errors,bb_hbp}`, `linescore.basis/provenance`, `game.{status,date_kst,venue}` | 9회 home null → '–' + "9회 말 공격 없음" 설명 |
| 하단 메타 | `schema`, `publish.published_at`, 투구·타석 수, `rec.policy.name`, 미지원 수 | |

## 존 좌표 변환 근거 (Song 고정 빌드 c47fe6cb)
- Song 고정 빌드(c47fe6cb)의 존 그림은 투수 시점이다(가로 좌표를 뒤집어 그린다). 창 밖 표식을 그리는 규칙과, 같은 목표를 한 네모로 묶는 규칙도 Song 화면과 같게 맞췄다.
- 창 여백 x .42, z .45 + pad .16은 Song 상세 시트 창의 값이다. Song 라이브 메인 창은 x .12, z .24 + pad .08로 더 좁다. 이 시안은 넓은 쪽을 쓰되 선택 투구에 맞춰 창을 넓히지는 않는다.
- Song 화면에서 우타자 실루엣은 화면 오른쪽, 좌타자는 왼쪽이다.
- 따라서 relay.js도 `VIEW_X = -1`, `ux = -x·100`, `uz = -z·100`으로 그린다. 원본 좌표(포수 기준 plate_x, 오른쪽 +)는 바꾸지 않고 화면에 그릴 때만 좌우를 뒤집는다. 1회 초 1구 actual.x = +0.502(포수 기준 오른쪽) → 화면 x = −50.2(왼쪽). 실루엣은 side `R` → 화면 오른쪽, `L` → 왼쪽, 범례는 "투수 시점 · 우타자(화면 오른쪽)".
- **주의(과제 문구와의 차이)**: 과제 지시문에는 "같은 방향(포수 시점)"이라 적혀 있으나 Song 화면은 위와 같이 **투수 시점**(VIEW_X = −1)으로 그린다. "Song과 같은 방향"을 우선해 투수 시점으로 맞췄고 화면에도 "투수 시점"이라 적었다. 포수 시점으로 바꾸려면 relay.js의 `VIEW_X`를 `1`로, 실루엣 좌우를 반대로, 범례 문구를 바꾸면 된다(한 줄 + 두 줄).

## 실제 투구 색 분류 (`actual.description` → 범례)
`ball`, `blocked_ball` → 볼(테두리만) · `called_strike`, `swinging_strike`, `swinging_strike_blocked`, `foul`, `foul_tip` → 스트라이크·파울(회녹색 채움) · `hit_into_play` → 타격(주황) · 그 밖 → 결과 미확인(이 경기엔 없음). 선택 투구는 라임 링. 추천 네모는 1순위 라임 채움, 2순위 반투명, 3순위 테두리.

## 미측정 · 쓰지 않은 자료
- 포수 셋업 추정(`actual.catcher_setup` 39구, `data/849843-setup.json`)은 검토 전이라 **표시하지 않았다**.
- 실기기(iOS/Android) 표시·터치 확인 **미측정**. PC의 미리보기 창(375×812 에뮬레이션과 550px 데스크톱 폭)에서만 확인했다(아래 검증 결과).
- 소요 토큰은 이 세션에서 재지 않았다(오케스트레이터 측정). 이 노트에서 "추정"이라 적지 않은 수치는 전부 데이터·스크립트 출력값이다.

## 알려진 한계
1. 존 SVG는 viewBox 고정이라 표식 크기가 화면 폭에 비례한다(Song은 ResizeObserver로 픽셀 크기를 고정). 320px에서는 약 20% 작아진다(존 폭 216px vs 390px에서 270px, 에뮬레이션 실측; 실기기 미측정).
2. 표식끼리 겹칠 때 숫자를 옮겨 쓰는 처리(Song의 lifted/badge 배치)는 없다. 추천 네모 위에 선택 투구가 겹치면 선택 투구가 위에 그려진다.
3. 같은 좌표에 두 투구가 있을 때의 쪼개기(stacked)는 구현하지 않았다. 이 경기 데이터에는 같은 좌표 쌍이 0건이라 화면에 영향이 없다.
4. 창(존 ± 여백) 밖 투구 60/262구는 가장자리에 점선 원+화살로 표시하고 실제 좌표는 title(길게 누르기/마우스 올림)과 아래 표에 적는다. 창은 Song **상세 시트(fullWindow)** 여백(.42/.45, pad .16)을 쓰되 선택 투구에 맞춰 넓히지는 않는다. Song 라이브 메인 창(.12/.24)보다 넓으므로 "창 밖 60구"는 Song 메인 화면의 수치와 다르다(메인 창 기준이면 더 많다).
5. 정책 선택 비중은 상위 3후보만 보이므로 합이 100%가 아니다(예: 1구 27+26+26 = 79%). 면책 문구로 "성공·적중 확률이 아님"을 적었다.
6. 라인업의 '교체'는 타석 기록상 같은 타순에 나중에 나온 선수를 뜻하며 대수비·대주자는 알 수 없다. 공식 라인업 카드가 아니다(화면에도 적음).
7. 선수 이름은 발행 파일의 영문 그대로다(한글 표기 자료 없음).
8. 자동 진행은 브라우저 탭이 가려지거나 상단 탭이 라인업·기록이면 멈추고("다른 화면 · 일시정지") 중계 탭으로 돌아오면 이어간다. 마지막 262구에 닿으면 꺼진다. stopAuto가 남긴 안내("마지막 투구 · …")는 다른 투구를 고르면 지워진다.
9. 점수 띠는 선택 투구 **직전** 상황이므로 홈런 투구를 골라도 점수는 아직 오르지 않는다. 띠에 "이 공 던지기 전" 알약을 두고, 바뀐 점수는 득점 탭·카드의 "득점 · 0:1 → 0:2 · 득점 시점 …" 줄에서 보여 준다. 타석 중 득점(와일드피치·도루 등)의 **원인**은 발행 파일에 없어 적지 않는다("N구 전(타석 중)"까지만).
10. 선택 줄로의 자동 스크롤은 타석 목록이 이미 화면에 보일 때만 한다. 처음 화면(존·점수 띠·이전/다음 버튼이 보이는 상태)에서 '다음'을 누르거나 자동 진행이 돌아도 페이지는 내려가지 않는다. 목록을 읽는 중(목록이 화면에 들어온 상태)이면 선택 줄을 따라간다. 기록 탭 '그 타석 보기'만 그 타석 카드 머리로 이동한다.
11. 접근성: 매초 바뀌는 카운트다운은 `aria-hidden`이고 켜짐·꺼짐·일시정지·종료만 `role=status`(sr-only)로 한 번씩 알린다. B/S/O 줄은 `role=img` + "볼 1"식 이름. 이닝 탭은 `aria-controls="pa-panel"`(목록을 `role=tabpanel`로 감쌈). 타격 원은 주황 채움에 짙은 굵은 테두리(#3a1f0a, 3)로 스트라이크·파울(회녹색 채움)과 모양으로도 구분된다. 스크린리더 실기 확인은 **미측정**.

## 로컬 검증 결과 (2026-11-03)
- `node --check relay.js` → OK.
- 순수 함수 스모크(node, 262구): 창 {x ±1.25, z 1.15~3.84} 안 202구·밖 60구, 추천 묶음 673(한 투구에 같은 target이 있는 63구는 네모가 2개 이하), 추천 창 밖 0, 득점 타석 7(`849843:4, 6, 23, 31, 41, 42, 55`), 타순 양 팀 1~9 + 교체 2, kmh(96.3) = 155.
- HTML 파싱(python html.parser): 태그 107개, 미닫힘 0, 짝 오류 0, 중복 id 0, 외부 src/href 0, `lang="ko"`·UTF-8, 본문에 'LIVE' 없음. CSS·JS의 http(s) 문자열은 SVG 네임스페이스 상수와 오류 안내 문구의 localhost 주소뿐(네트워크 요청 아님).
- 브라우저(기존 8790 서버, 미리보기 창 375×812 에뮬레이션 → 550px 데스크톱): 콘솔 오류 0 · 처음 열면 1회 탭·1구 선택·scrollY 0 · 3구 클릭 시 패널 "3구 · 던지기 전 추천"/B·S 점 2개/라임 링 1개 · 득점 탭 카드 7개 · 득점 탭에서 2회 투구를 고르면 2회 탭으로 자동 전환 · 자동 진행 켜고 12초 뒤 다음 투구(41번)로 이동, 카운트다운 표시 · 미지원 투구(Ryan Rolison)에서 "추천 미지원 (unsupported) · 사유" 표시, 존에 추천 네모 0개 · 라인업·기록 탭 렌더 · 데스크톱 폭에서 430px 열 가운데 정렬. 처음 구현에서 이닝 탭의 `scrollIntoView`가 페이지를 세로로 489px 내리던 문제를 발견해 탭 줄 안 가로 스크롤로 바꿨다.
- 262구 필드 집계(python): actual·x·z·speed·pitch_label·result_label·call_label·zone_label 262/262, spin·extension 262/262, 타구 3값 47/262(나머지 215구 '자료 없음'), rec 262/262(ready 246, unsupported 16 — 사유 "2025년까지 학습 기록이 없는 투수라 추천하지 않습니다."), 후보 target·probability 738/738, situation_before·context_before 262/262, index 연속·PA first/last 일치·pitch_count 합 262, PA event_label·result_text·batting_order 71/71, half 값 `Top` 130 / `Bot` 132, linescore 9이닝·9회 home null.

## 검토 반영 (2026-11-03, 2차) — 지적 F1~F8
| 지적 | 반영 |
|---|---|
| F1 (P1) 이전/다음·자동 진행이 페이지를 아래로 내려 존·점수 띠·버튼이 사라짐 | `scrollToRow`: 타석 목록(`#pa-list`)이 화면에 보일 때만 `scrollIntoView(nearest)`. 처음 화면에서는 스크롤 0. 기록 탭 '그 타석 보기'만 `force`로 카드 머리로 이동 |
| F2 (P2) 320px 헤더 가로 넘침 | `.r-tag` min-width 0 + ellipsis(안전망), ≤389px에서는 줄바꿈 허용·팀 부분(`.r-tag-game`)은 한 덩어리로 둘째 줄, ≤359px 11px/자간 0, 기본 자간 1.2→0.8px, 워드마크 flex none |
| F3 (P2) 추천 칩 zone_label 잘림 | 390px 이상: `small` 두 줄 허용(nowrap 제거). ≤389px: `.chips` 1열, 한 줄에 순위 · 구종 · 위치 · 비중(min-height 44px) |
| F4 (P2) zone_label 좌우는 포수 기준인데 그림은 투수 시점 | 라벨은 그대로. 칩 아래 줄·'위치' 행 "(포수 기준)"·범례 한 줄 추가, relay.js 머리 주석·이 노트 매핑 표에 근거 기록 |
| F5 (P3) 타석 중 득점이 타석 결과처럼 읽힘 | `scoreChanges`에 `mid`(타석 중 점수가 바뀐 첫 투구)·`atResult` 추가, `scoreWhen` 문구 "2구 전(타석 중)" / "타석 결과"를 카드·기록 목록에 표기 |
| F6 (P3) 접근성 4건 | (a) 카운트다운 `aria-hidden` + sr-only `role=status`는 상태 변화 때만 (b) `.c-row` `role=img` "볼 1", `.count` `role=group` (c) 이닝 탭 `id`·`aria-controls="pa-panel"`, 목록을 `role=tabpanel`로 감싸고 `aria-labelledby` 갱신 (d) 타격 원·범례·줄 표식에 짙은 굵은 테두리 |
| F7 (P3) 라인업·기록 탭에서도 자동 진행, 종료 문구 잔존 | 중계 탭이 아니면 일시정지(`autoPaused`), 돌아오면 재개. `selectPitch` 끝에서 항상 `renderAuto()`, `S.note`로 stopAuto 문구 관리 |
| F8 (P3) 근거 서술 2곳 | (a) 창 여백은 Song 상세 시트(fullWindow) 값이라고 고침(relay.js 주석·매핑 표·한계 4) (b) 320px 축소 약 20%(216 vs 270px, 실측)로 고침 |

재검증(2026-11-03 2차): `node --check relay.js` OK · 순수 함수 스모크(node): 득점 타석 7, 합계 0:8 = game, `mid` 2건(849843:42 2구 idx142, 849843:55 5구 idx201), 나머지 5건 atResult · HTML 파싱: 태그 110, 미닫힘 0, 중복 id 0, 외부 src/href 0, 주석 밖 'LIVE' 없음 · CSS 중괄호 204/204.
브라우저(기존 8790 서버, 중계 탭을 앞으로 가져와 에뮬레이션): 390×844 처음 화면에서 '다음' 3회 → scrollY 0, 다음 버튼 top 744, 존 top 344 그대로 · 목록이 보이는 위치(scrollY≈1200)에서 '다음' → 선택 줄 화면 안 · 자동 진행 중 라인업 탭 → "다른 화면 · 일시정지"·선택 투구 유지, 중계 복귀 → "8초 후 다음 투구" 재개 · 기록 탭 '그 타석 보기'(Austin Hays) → 142번(2구) 선택·5회 탭·카드 "득점 시점 2구 전(타석 중)" · 폭별(가장 긴 라벨 조합 7번 투구: 싱커/가운데 높이 오른쪽, 체인지업) 320: scrollWidth 320, 태그 두 줄(h 28, 오른쪽 끝 304), 칩 1열 44px 잘림 0 / 360: scrollWidth 360, 태그 끝 344, 잘림 0 / 390: 태그 끝 374, 3열 두 줄 잘림 0 / 430: 잘림 0 · 콘솔 오류 0. 실기기·스크린리더는 미측정.

## 2차 시안 (2026-11-06) — 라이트 모드·결과별 애니메이션·디자인 패스

로컬 데모에만 반영(공개 배포·Song 전달·Git 커밋 아님). 고친 파일은 `index.html`(158→180줄), `relay.css`(287→363줄), `relay.js`(508→692줄), 이 노트(11/6 검토 반영 뒤 수치). `data/`는 읽기만 했다. 외부 스크립트·폰트·CDN·라이브러리 0, 네트워크 요청 0. 위 절들은 1차 기록이라 그대로 두었고, 이 절의 수치는 전부 아래 '검증' 스크립트 출력값이다(브라우저·실기기·스크린리더는 **미측정**, 오케스트레이터가 확인한다).

### 쓴 디자인 도구와 적용한 규칙
| 도구 (GitHub star, 11/6 실측은 브리프 기준) | 적용한 규칙 | 바꾼 것 |
|---|---|---|
| anthropics/skills `frontend-design` SKILL.md | "AI tells" 5번(가운뎃점 메타 문자열 'A · B · C', 링크 글자에 붙은 '→', 스페이스 em dash, 트래킹된 라벨) | 가운뎃점 이어붙임 전부 문장·쉼표·줄바꿈·`<dl>`로, '← 홈으로'→'홈 화면으로', `<title>` em dash 제거, 라벨 자간 제거 |
| 같은 문서 "spend your boldness in one place" / "writing" | 과감함은 한 곳(점수 띠 숫자 30→34px, 디스플레이 글꼴은 점수 띠·워드마크에만), 능동·사용자 관점 문구 | 카드 그림자 0·그라데이션 0, 반지름 단계 카드 14 / 칩·버튼 10 / 알약 999(`--r-card/--r-ctrl/--r-pill`), "추천 미지원 (unsupported) · 사유"→"이 투수는 추천이 없습니다. 사유: … (상태 unsupported)" |
| Nutlope/hallmark `gates.md` §4 | **63 Floor**(가운뎃점 2개 이상·글자에 붙은 화살표) · **67 Floor**(15px 이하 라벨 자간 0.03em 초과) · **48 Floor**(토큰 블록 밖 색·`font-family` 리터럴 0) · **7a/7b**(순흑·순백 금지) · **10a Floor**(`transition: left`) · **34 Floor**(`overflow-x: clip`을 html, body 둘 다) · **27 Floor**(keyframes에 reduced-motion 폴백) · **33 Floor**(장식 SVG 그룹 `aria-hidden`) · **40/41 Floor**(본문 4.5:1, 링 3:1, 채움 위 글자는 짝 토큰) · **26a**(포커스 링 3:1) · **4**(카드 안 카드 없음, 유지) | 자간: `.auto-label .4px`, `.r-tag .8px`, `.half-head 1.2px`, `.pill .4px`, `.score-who small .6px`, `.score-main .team .5px` 제거(워드마크 −1px, 제목 −0.2px은 음수 트래킹이라 유지). 색 리터럴 22종→토큰 25개. `.switch .knob` `left`→`transform: translateX(24px)`. `--on-accent/--on-strike/--on-orange/--accent-ink/--orange-ink` 짝 토큰 |
| hallmark `dark-mode.md` | "반전이 아니라 재도출, hue는 움직이지 않음", 두 모드 모두 대비 수치 확인, 첫 페인트 전 인라인 스크립트, `localStorage` 저장 | `:root` = 라이트, `[data-theme="dark"]` = 재도출 다크(1차 값 그대로). `@media (prefers-color-scheme)` 자동 전환은 브리프대로 넣지 않음 |
| hallmark `craft.md` §1 Type | 가족 2개 이하 + 아웃라이어 1(표시용 "Arial Black"은 점수 띠·워드마크 한 역할), `tabular-nums`, 라벨은 본문 글꼴 한 단계 작게·문장형·무자간 | `--font-body: "Apple SD Gothic Neo", "Malgun Gothic", "Segoe UI", system-ui, sans-serif`(의도적 시스템 한글 산세리프), `--font-display: "Arial Black"`, `body { font-variant-numeric: tabular-nums }`(전체 숫자), `.half-head`는 라임 소제목→`--ink` 14px 굵게 + 위 여백 12px |
| craft.md §2 Colour | 알파를 색 정의로 쓰지 않음(오버레이 제외), 짝 ink 토큰, 종이는 순백 금지 | `--accent-soft` 라이트 `#e4f7c0`·다크 `#4d6a38`(1차 `#ceff7855` 알파를 불투명으로), `--tap`만 알파(탭 하이라이트 오버레이) |
| craft.md §5 Motion, ui-ux-pro-max `motion.csv` 원칙 | transform/opacity만, reduced-motion이면 최종 상태 즉시, 루프는 한 번에 하나 | 스윙은 CSS `transform: rotate`, 공은 SVG 속성(cx·cy·r·opacity)이라 rAF 직접 갱신(WAAPI 불가), `prefers-reduced-motion`이면 `animation: none` + 자막만, 탭 숨김(`document.hidden`)이면 최종 상태 |

생성물 티가 **아니라서 유지한 것**(브리프 B-10): 순위 숫자 1·2·3(실제 순서), 범례, '이 공 던지기 전' 알약(상태 칩), 워드마크의 라임 점(글자라 `--accent-ink`, 다크에서는 같은 라임), 범례의 "스트라이크·파울"과 추천 네모 안 "1·3"(한 줄에 점 1개, 데이터 라벨).

### 문구 전/후 (가운뎃점·화살표·em dash)
| 위치 | 전 | 후 |
|---|---|---|
| `<title>` | Pitcheezy 중계 — 저장 경기 재생 849843 | Pitcheezy 중계, 저장 경기 849843 재생 |
| `#hdr-tag` | 저장 경기 재생 · CHC @ SD | "저장 경기 재생" / 둘째 줄 "CHC @ SD"(`.r-tag-game` block, 항상 두 줄) |
| `.auto-label` | 저장 경기 재생 · 자동 진행 | 자동 진행 (헤더에 이미 '저장 경기 재생') |
| `#s-count` aria-label | 볼 · 스트라이크 · 아웃 (이 공 던지기 전) | 볼, 스트라이크, 아웃 (이 공 던지기 전) |
| `#w-ctx` | 타자 오늘 3타수 1안타 · 투수 45구 · 탈삼진 3 · 자책 0 | 두 줄 `<span>`: "타자 오늘 3타수 1안타" / "투수 45구, 탈삼진 3, 자책 0" |
| 주자 `<title>` | 주자 1루·3루 | 주자 1루, 3루 |
| `who()` | Michael King (34) · 우투 | Michael King (34) 우투 |
| `#legend-view` | 투수 시점 · 우타자(화면 오른쪽) | 투수 시점, 우타자는 화면 오른쪽 |
| `.legend-note` | 위치 이름(칩·위치 행)의 왼쪽·오른쪽은 포수 기준 · 그림은 투수 시점이라 좌우가 반대 | 칩과 위치 행의 왼쪽, 오른쪽은 포수 기준입니다. 그림은 투수 시점이라 좌우가 반대입니다. |
| 존 title(툴팁) | 3구 · 포심 · 볼 · 가로 0.50 ft · 높이 2.10 ft (포수 기준) · 화면 밖 | 3구 포심, 볼, 가로 0.50 ft, 높이 2.10 ft, 포수 기준, 화면 밖 |
| 존 aria-label | … · 이번 타석 3개 투구 · 선택 2구 | …. 이번 타석 투구 3개, 선택 2구 |
| `#pp-title` | 3구 · 던지기 전 추천 | 3구를 던지기 전 추천 |
| `#pp-disc` | 그 공을 던지기 전 정보만으로 계산한 추천 · 정책 선택 비중은 성공·적중 확률이 아님 · 위치는 … (참고) | 세 문장: "…계산한 추천입니다." "정책 선택 비중은 성공 확률이 아닙니다." "위치는 과거 투구 분포의 대략 위치라 참고용입니다." |
| `.rec-meta` | 위치 이름의 왼쪽·오른쪽은 포수 기준(…) · 정책 선택 비중(%) · 기록 … · 정책명 | "위치 이름의 왼쪽, 오른쪽은 포수 기준입니다(…). 숫자는 정책 선택 비중(%)입니다. 기록 …, 정책 …." |
| `.rec-none` | 추천 미지원 (unsupported) · 사유 | **이 투수는 추천이 없습니다.** 사유: … (상태 unsupported) |
| '판정·결과' 행 | 판정·결과: 볼 → 볼넷 | 판정과 결과: 판정 볼, 결과 볼넷 (같으면 한 단어) |
| '위치' 행 | … (포수 기준) · 가로 x ft · 높이 z ft (포수 기준 원본 좌표) | … (포수 기준), 가로 x ft, 높이 z ft |
| '타구' 행 | 타구 속도 … · 발사각 … · 비거리 … | 쉼표 |
| '타석 결과' 행 | 삼진 · 헛스윙 삼진 | 삼진, 헛스윙 삼진 |
| `.half-head` | 2회 초 · CHC 공격 | 2회 초, CHC 공격 |
| `.pa-result` | 2회 초 · 파울팁 삼진 · 5구 · 투수 이름 | 2회 초, 파울팁 삼진, 5구, 투수 이름 |
| `.pa-score` | 득점 · CHC 0 : 1 SD → 0 : 2 · 득점 시점 … | 득점 CHC 0 : 1 SD → 0 : 2, 득점 시점 … (점수 변화 화살표 한 번은 유지) |
| 자동 진행 안내 | 자동 진행 꺼짐 · …, 다른 화면 · 일시정지, 마지막 투구 · 자동 진행 종료 | "자동 진행 꺼짐. …", "다른 화면, 일시정지", "마지막 투구, 자동 진행 종료" |
| 라인업 `.sub` | 교체 → 이름 | 교체: 이름 |
| 라인업 투수 | A → B → C · 예고 선발 X | "A, B, C." 다음 줄 "예고 선발은 X." |
| 기록 `.game-meta` | 경기 종료 · 날짜 (KST) · 구장 · 팀 0 : 8 팀 | 첫 줄 굵게 "Chicago Cubs 0 : 8 San Diego Padres" / "경기 종료, 2026-09-30 (KST), Petco Park" |
| 기록 caption | 이닝별 득점 · R 득점 · H 안타 · E 실책 · BB 볼넷+사구 | 이닝별 득점. R 득점, H 안타, E 실책, BB 볼넷과 사구. |
| 기록 `.panel-note` | 9회 말 공격 없음(…) → '–' · 집계 기준 … · 출처 … | "9회 말은 공격 없음(…)이라 '–'로 표시합니다. 집계 기준은 …. 출처는 …." |
| 득점 목록 | 이름 · 결과 · 설명 · 득점 시점 … → 점수 | 이름, 결과, 설명, 득점 시점 … → 점수 |
| 푸터 1문단 | Song 발행 파일(c47) 기반 저장 경기 재생 · 추천은 … · 위치는 참고 · 정책 선택 비중 ≠ 성공 확률 | 세 `<p>`: "Song 발행 파일(c47)로 완료 경기를 다시 재생합니다." "추천은 그 공을 던지기 전 정보만으로 계산했고, 위치는 참고용입니다." "정책 선택 비중은 성공 확률이 아닙니다." |
| `#foot-meta` | schema … · 발행 … · 투구 262구 · … | `<dl>` 6행(schema / 발행 / 투구 / 타석 / 추천 정책 / 추천 없음) |
| `.footer-link` | ← 홈으로 | 홈 화면으로 |
| 로딩 실패 문구 | … (오류) · 로컬 서버(…)에서 열어 주세요 | … (오류). 로컬 서버(…)에서 열어 주세요. |

### 토큰 (라이트 = `:root` 기본, 다크 = `[data-theme="dark"]`)
브리프 표의 출발값에서 대비 때문에 바꾼 것 2개: `--strike` 라이트 `#52685a`→`#485d4f`(비선택 원 .78 불투명도에서 숫자 실효 대비 3.57:1 → 색을 짙게 하고 불투명도 .9로 올려 5.23:1), `--switch-on` 라이트 `#dff5b0`→`#4e7d22`(라임 손잡이가 트랙과 1.02:1로 안 보임 → 4.25:1). hue는 둘 다 유지. 다크 `--accent-soft`는 알파 `#ceff7855`를 같은 보임새의 불투명 `#4d6a38`로.

| 토큰 | 라이트 | 다크 | 쓰는 곳 |
|---|---|---|---|
| `--bg` | `#f4f7ef` | `#091811` | 페이지, 자막 배경 |
| `--panel` | `#e8eee0` | `#11241b` | 자동 진행 줄, 존 그림 배경, 칩, 카드, 버튼 |
| `--ink` | `#0f2217` | `#f2f4e9` | 본문, 존 테두리, 소제목 |
| `--muted` | `#4f6457` | `#a5b6a8` | 보조 글자, 볼 원 테두리, 꺼진 스위치 손잡이, 꺼진 스위치 트랙 테두리와 3순위 네모·칩 테두리(11/6 D-F6, D-F7) |
| `--line` | `#c5d2c0` | `#304438` | 헤어라인 |
| `--accent` | `#ceff78` | `#ceff78` | 채움만: 선택 이닝 탭, 1순위 네모, 스위치 손잡이, 현재 카드 타순 알약 (B/S/O 켜진 점과 주자 베이스는 11/6 D-F1로 `--accent-ink`로 옮김: 라이트에서 라임은 종이와 1.07:1라 켜짐이 안 보였다) |
| `--accent-ink` | `#2f6b12` | `#ceff78` | 글자·테두리·링: 선택 상단 탭, 포커스 링, 선택 링, 비중 %, 득점 글, 링크, 워드마크 점, 켜진 B/S/O 점과 주자 있는 베이스 채움(다크에서는 같은 라임이라 보임새 그대로) |
| `--on-accent` | `#0f2217` | `#091811` | `--accent` 채움 위 글자 |
| `--accent-soft` | `#e4f7c0` | `#4d6a38` | 2순위 네모, 온베이스 배지 |
| `--orange` | `#ffb782` | `#ffb782` | 타격 원·배지 채움 |
| `--orange-ink` | `#9a4a0f` | `#ffb782` | 주황 글자(추천 없음 강조, 교체 표시) |
| `--on-orange` | `#2b1a0d` | `#2b1a0d` | 주황 채움 위 글자·굵은 테두리(1차 `#3a1f0a`/`#2b1a0d` 통일) |
| `--strike` | `#485d4f` | `#a5b6a8` | 스트라이크·파울 원 |
| `--on-strike` | `#f4f7ef` | `#091811` | 그 위 숫자 |
| `--ball-fill` | `#fbfcf8` | `#0c1c14` | 볼 원, 3순위 네모 바탕, 연출 공 |
| `--z-outside` | `#dfe8d6` | `#0c1c14` | 존 창 바깥 면 |
| `--z-grid` | `#b4c4ad` | `#3f5a48` | 3×3 격자 |
| `--batter-fill` / `--batter-stroke` | `#c9d6c2` / `#5c7263` | `#2a4433` / `#6f8a76` | 타자 실루엣 |
| `--diamond-off` | `#d7e1d1` | `#1b3024` | 빈 베이스 |
| `--switch-off` / `--switch-on` | `#cdd8c7` / `#4e7d22` | `#22382b` / `#3a5a2a` | 스위치 트랙 |
| `--sticky-bg` | `#f4f7eff2` | `#0b1d14f2` | 상단 탭·이닝 탭 바(블러) |
| `--row-sel` | `#e3efd0` | `#1a3022` | 선택 투구 줄 |
| `--tap` | `#ceff7855` | `#ceff7833` | 탭 하이라이트(오버레이라 알파) |
| `--font-body` / `--font-display` | 위 §Type | 같음 | 글꼴 토큰(Hallmark 48: `font-family` 리터럴도 토큰 블록에만) |

예외(브리프대로): 파비콘 data-URI의 `%23ceff78`/`%23091811`, `<meta name="theme-color">` 초기값 `#f4f7ef`(JS가 테마 전환 때 `--bg` 계산값으로 바꾼다).

### 대비 (WCAG 2.x 비율, python -I 계산, 두 모드 모두 통과 — 38쌍 전부. 11/6 검토 뒤 상태 쌍 7개 추가)
| 쌍 | 라이트 | 다크 | 기준 |
|---|---|---|---|
| `--ink` / `--bg` (본문, 자막) | 15.38 | 16.42 | 4.5 |
| `--ink` / `--panel` | 14.06 | 14.62 | 4.5 |
| `--muted` / `--bg` | 5.89 | 8.57 | 4.5 |
| `--muted` / `--panel` | 5.39 | 7.63 | 4.5 |
| `--accent-ink` / `--bg` (링크, 선택 탭) | 6.00 | 15.82 | 4.5 |
| `--accent-ink` / `--panel` (비중 %, 득점 글) | 5.49 | 14.09 | 4.5 |
| `--on-accent` / `--accent` (선택 이닝 탭 글자, 1순위 숫자) | 14.43 | 15.82 | 4.5 |
| `--on-strike` / `--strike` (스트라이크 원 숫자 13px 굵게) | 6.57 | 8.57 | 4.5 |
| `--on-orange` / `--orange` (타격 원 숫자, 안타 배지) | 9.83 | 9.83 | 4.5 |
| `--orange-ink` / `--bg` | 5.77 | 10.73 | 4.5 |
| `--orange-ink` / `--panel` (추천 없음 강조, 교체) | 5.28 | 9.56 | 4.5 |
| `--accent-ink` / `--accent-soft` (온베이스 배지, 2순위 숫자) | 5.68 | 5.30 | 4.5 |
| `--bg` / `--muted` (타순 알약 글자) | 5.89 | 8.57 | 4.5 |
| `--ink` / `--ball-fill` (볼 원 숫자) | 16.16 | 15.85 | 4.5 |
| `--accent-ink` / `--ball-fill` (3순위 숫자) | 6.30 | 15.27 | 4.5 |
| `--ink` / `--line` (결과 미확인 원, 이 경기엔 없음) | 10.59 | 9.40 | 4.5 |
| `--ink` / `--row-sel` (선택 줄) | 13.89 | 12.68 | 4.5 |
| `--muted` / `--row-sel` | 5.32 | 6.62 | 4.5 |
| `--accent-ink` / `--row-sel` | 5.42 | 12.22 | 4.5 |
| `--muted` / `--sticky-bg` (탭 바 글자) | 5.89 | 8.21 | 4.5 |
| `--accent-ink` / `--sticky-bg` | 6.00 | 15.17 | 4.5 |
| 포커스 링 `--accent-ink` / `--bg` | 6.00 | 15.82 | 3.0 |
| 포커스 링 / `--panel` | 5.49 | 14.09 | 3.0 |
| 포커스·선택 링 / `--z-outside` | 5.15 | 15.27 | 3.0 |
| 스위치 손잡이(꺼짐) `--muted` / `--switch-off` | 4.33 | 5.91 | 3.0 |
| 스위치 손잡이(켜짐) `--accent` / `--switch-on` | 4.25 | 6.80 | 3.0 |
| 볼 원 테두리 `--muted` / `--z-outside` | 5.06 | 8.27 | 3.0 |
| 참고(기준 없음) 헤어라인 `--line`/`--bg` | 1.45 | 1.75 | — |
| 참고 격자 `--z-grid`/`--z-outside` | 1.46 | 2.32 | — |
| 참고 실루엣 테두리/채움 | 3.43 | 2.82 | — |
| 비선택 원(불투명도 .9) 실효: 스트라이크 / 볼 / 타격 숫자 | 5.23 / 12.21 / 7.81 | 7.20 / 12.93 / 8.25 | 4.5 |
| 켜진 B/S/O 점 `--accent-ink` / `--bg` (상태 구분, 11/6 D-F1; 전에는 `--accent`로 1.07) | 6.00 | 15.82 | 3.0 |
| 주자 있는 베이스 `--accent-ink` / 빈 베이스 `--diamond-off` (전에는 1.17) | 4.82 | 12.17 | 3.0 |
| 빈 베이스 테두리 `--muted` / `--diamond-off` | 4.73 | 6.59 | 3.0 |
| 꺼진 스위치 트랙 테두리 `--muted` / `--panel` (11/6 D-F7; 전에는 `--line` 1.33) | 5.39 | 7.63 | 3.0 |
| 3순위 네모 테두리 `--muted` / `--z-outside` (11/6 D-F6) | 5.06 | 8.27 | 3.0 |
| 3순위 칩 테두리 `--muted` / `--panel` | 5.39 | 7.63 | 3.0 |
| 자막 작은 글자 `--muted` / `--bg` | 5.89 | 8.57 | 4.5 |
| 참고 자막 흐림(.6, 여섯 자리 전부 겹칠 때만, 이 경기 0회) 실효 글자/rect | 4.50 | 6.51 | — |

### 테마 전환
`<head>` 인라인 스크립트가 첫 페인트 전에 `localStorage['pz-relay-theme']`(light/dark)를 읽어 `document.documentElement.dataset.theme`을 세팅(없거나 접근 실패 → light). 헤더 오른쪽 `#theme-switch`(44px, 라이트일 때 "어둡게", 다크일 때 "밝게", `aria-label` "어둡게, 지금은 밝은 화면" / "밝게, 지금은 어두운 화면": 보이는 글자로 시작해 음성 조작으로 누를 수 있다(WCAG 2.5.3, 11/6 C-F2·D-F2)). 전환 때 `meta[name=theme-color]`를 `getComputedStyle(--bg)` 값으로 갱신. `color-scheme`은 `:root light`, `[data-theme=dark] dark`. 헤더 태그는 항상 두 줄(≤359px에서 11px)이라 320px에서 버튼이 들어가도 넘치지 않도록 설계했다(브라우저 폭 확인은 미측정).

### 결과별 공·스윙 연출 (`actual.description` 8종, 분기는 순수 함수 `Relay.animPlan`)
| description (이 경기 수) | 스윙 | 공(도착 뒤) | 자막(`result_label`, 다르면 작은 글자로 `call_label`) |
|---|---|---|---|
| `ball` 89, `called_strike` 43 → take 132 | 없음 | 도착 뒤 0.2초 페이드(번호 원이 그 자리에 이미 있음) | 볼 / 루킹 스트라이크, 타석 끝이면 "볼넷 +볼" 6, "삼진 +루킹 스트라이크" 2 |
| `blocked_ball` 2 → block | 없음 | 아래로 34단위 `sin` 튀고 0.38초 페이드 | 볼 |
| `swinging_strike` 32, `swinging_strike_blocked` 1 → miss 33 | 도착 0.14초 전 시작 | 맞지 않고 도착, 0.2초 페이드 | 헛스윙 18, "삼진 +헛스윙" 15(자료에 `call_label`이 이미 '헛스윙'이라 중복 없을 때만 작은 글자) |
| `foul` 45 → foul | 스윙 | 타자 쪽(좌타 화면 왼쪽, 우타 오른쪽) 뒤 위로, 커지며(R 11→28.6) 0.5초 페이드. 공 색 `--strike` | 파울 45 |
| `foul_tip` 3 → tip (11/6 D-F4, 브리프의 foul 분기에서 분리) | 스윙 | 방망이를 스치고 포수 앞으로 40단위 떨어지며 0.32초 페이드. 뒤로 날아가지 않는다(파울팁은 포수가 잡은 공). 공 색 `--strike` | 파울팁 2, "삼진 +파울팁" 1 |
| `hit_into_play` 47 → inplay | 스윙 | 시청자 쪽으로 커지며(R 11→28.6, 홈런급 33) 날아감. 세로: `launch_angle_deg` >25 위로 0.9H(20구) / 10~25 위로 0.4H(8구) / <10 아래로 0.1H(19구). 시간: `exit_velocity_mph` 30→800ms, 108→450ms(이 경기 450~799ms). 화면 위로 완전히 나가는 것(R 33, viewBox 위)은 실제 결과 `event === "home_run"`(3구)만(11/6 D-F4; 브리프의 "300 ft 이상"이면 353·348 ft 뜬공 아웃과 399 ft 2루타 7구도 홈런처럼 나갔다). 300 ft 이상 아웃·2루타 7구는 발사각 구간대로 창 안에서 커지며 페이드(`plan.deep`은 참고 값). **좌우는 자료 없음 → 똑바로**. 공 색 `--orange` | `event_label`: 타구 아웃 28, 안타 12, 홈런 3, 병살타 2, 2루타 1, Field Error 1 |
| 그 밖(이 경기 0) | 없음 | take와 같음 | `result_label`, 없으면 '자료 없음' |

공통: 출발 존 창 위 가운데(`ux(0)`, `uz(zHi)+24.2`), 반지름 24.2, 불투명도 .5 → 도착 `inset(place(actual))` 표식 자리, 반지름 11, .95. ease-in(t²). 비행 `D = clamp(560 + (97.6 − speed_mph)×10, 560, 900)`ms, 이 경기 560~823ms, speed 없으면 700. 스윙 keyframes `rotate 0 → −105° (30%, 144ms = 공 도착 순간, 방망이 끝이 플레이트 쪽으로 수평) → −120° (45%) → −120° (65%) → 0 (100%)`, 480ms `both`, `transform-box: view-box; transform-origin: 34px 31px`, 500ms 뒤 클래스 제거(11/6 D-F3: 전에는 −150°에서 끝이 몸통 안으로 들어가고 400ms에 0°로 점프했다. 되돌아오는 구간을 keyframes 안에 넣어 점프 컷이 없다). 좌타 실루엣은 기존 `scaleX(−1)`이라 같은 keyframes로 존 쪽으로 돈다. 자막 자리는 순수 함수 `captionSpot`이 창 안 여섯 자리(아래 가운데·왼쪽·오른쪽, 위 가운데·왼쪽·오른쪽) 중 이번 타석 번호 원과 추천 네모와 겹치지 않는 첫 자리를 고른다(11/6 C-F1: 전에는 선택 표식만 피해 262구 중 31구에서 같은 타석의 다른 원을 덮었다. 지금은 262구 전부 겹침 0, 아래 가운데 210 / 아래 왼쪽 31 / 아래 오른쪽 14 / 위 7). `--bg` 불투명 둥근 rect(높이 30) + `--ink` 18 단위 굵게, 작은 글자 15 단위(11/6 D-F5: 320px 폭에서 13.8 / 11.5px, 390px에서 17.2 / 14.4px), 다음 투구까지 유지. 여섯 자리가 전부 겹치면 가장 적게 겹치는 자리에 두고 1.2초 뒤 불투명도 .6(이 경기 0회). 오버레이 `.z-anim`은 `pointer-events: none`이라 아래 표식의 title 툴팁이 살아 있다. 새 투구를 고르면 `cancelAnim()`(rAF 취소·타이머 정리·swing 클래스 제거) 뒤 SVG를 다시 그린다. `document.hidden`이면 각 구간이 바로 최종 상태. 자료가 없을 때 기본값: 비행 700ms, 발사각 없으면 '조금 위', 타구 속도 없으면 650ms, 비거리 없으면 홈런급 아님(이 경기엔 해당 없음, `animPlan` 폴백으로 확인). 스위치 `#anim-switch`(`.auto-row` 둘째 줄, `role=switch`, `localStorage['pz-relay-anim']` on/off): 기본 켜짐, `prefers-reduced-motion: reduce`면 기본 꺼짐이고 켜도 자막만("켜짐, 감속 모션 설정이라 결과 자막만" 표시). 켜고 끌 때 현재 투구를 다시 그려 바로 반응한다. 화면이 열린 채 OS 감속 모션 설정이 바뀌면 저장값이 없을 때 기본값을 다시 읽고 라벨과 지금 투구를 함께 다시 그린다(11/6 C-F5). 오버레이 `<g class="z-anim" aria-hidden="true">`, 투구마다 라이브 안내 없음. 범례에 한 줄 추가: "공의 움직임은 도착 위치와 결과로 만든 연출이고, 실제 궤적 자료가 아닙니다. 타구의 좌우 방향은 자료에 없어 똑바로 그리고, 파울은 타자 쪽 뒤로 보내는 연출입니다."(11/6 C-F3: 파울의 좌우 이동도 연출이라 화면에 적음)

**연출의 한계(정직 표기)**: 발행 파일에 릴리스 포인트·궤적(vx0 등)·타구 방향(스프레이)·체공 시간이 없다. 공의 경로·크기 변화·파울의 '타자 쪽 뒤'·파울팁의 '포수 앞'·타구의 발사각 구간·시간은 모두 **도착 위치와 결과 라벨·3개 타구 값으로 만든 연출**이며 실제 궤적이 아니다. Statcast의 release/velocity 필드가 있어야 궤적을 그릴 수 있다.

### 검증 (2026-11-06, 스크립트 출력값)
- `node --check relay.js` OK. `require('./relay.js')` 스모크: `Relay` export 26개(기존 22 + `animPlan`, `ANIM_OF`, `captionSpot`, `textWidthGuess`), `kmh(96.3) = 155`, 득점 타석 7(`849843:4, 6, 23, 31, 41, 42, 55`), `mid` 2, 타순 양 팀 9 + 교체 1씩, 창 안 202 / 밖 60, `who()` 샘플 "Michael King (34) 우투". `animPlan` 262구: take 132, miss 33, foul 45, tip 3, inplay 47, block 2, 미분류 0, 스윙 128, 비행 560~823ms, 타구 450.0~799.1ms, 발사각 구간 high 20 / mid 8 / flat 19, 화면 밖(홈런) 3, 300 ft 이상 10(그중 아웃·2루타 7은 창 안), 자막 분포는 위 표와 같음. `captionSpot` 262구: 표식과 겹침 0(가장 넓은 자막 rect 172 단위 "삼진 +루킹 스트라이크", 창 폭 250, 전부 창 안), 여섯 자리 전부 막힌 가상 입력은 최소 겹침 자리 반환.
- HTML(python -I html.parser): 태그 121, 미닫힘 0, 짝 오류 0, 중복 id 0(id 44), 외부 src/href 0(스크립트는 `relay.js` + 테마 인라인 1개), 주석 밖 'LIVE' 0, `lang="ko"`, UTF-8. relay.js가 쓰는 id 전부 존재(JS 참조 id 중 HTML에 없는 것 0). 로딩 전 자리표시 5개(`s-away-abbr`, `s-home-abbr`, `s-inning`, `w-pitcher`, `w-batter`)는 비어 있고 init이 채운다.
- CSS: 중괄호 228/228, **토큰 블록(`:root`, `[data-theme="dark"]`) 밖 색 리터럴 0**(`#…`, `rgb/hsl/oklch` 모두 0), `font-family` 리터럴 0, 토큰 라이트 32개(색 25 + 글꼴 2 + 치수 5)·다크 25개, `transition`에 left/top/width/height/all 0, `html, body { overflow-x: clip }`, `tabular-nums` body, `prefers-reduced-motion` 블록에 `animation: none`, `.z-anim { pointer-events: none }` 1곳.
- 가운뎃점 2개 이상 문자열: HTML 텍스트·속성 0, HTML 주석 0, JS 문자열 리터럴 0(627개 검사), JS 주석 0, CSS 0. 점 1개(허용): "스트라이크·파울"(범례·KIND_WORD), 추천 네모 "1·3" 결합. 글자에 붙은 화살표 0(남은 `→` 2개는 점수 변화 "0 : 1 → 0 : 2"뿐). em dash: HTML 0(화면 글자 0, 로딩 전 자리표시 '—' 5개도 비움: 11/6 C-F4·D-F8), CSS 0, relay.js 주석 5개(1차 코드 주석, 화면에 보이지 않음). 남은 `letter-spacing`은 워드마크 −1px, 패널 제목 −0.2px(음수).
- 대비: 위 표 38쌍 두 모드 전부 기준 이상(ALL PASS).

### 미측정·하지 않은 것
- 브라우저 표시(라이트·다크 전환, 320~430 폭, 애니메이션 실제 재생, 자막 위치와 여섯 자리 선택, 스윙 되돌아옴, 파울팁 연출, 라이트 B/S/O 점·베이스 켜짐 보임새, 콘솔 오류), 실기기, 스크린리더: **미측정**(이 빌드 단계는 브라우저 도구를 쓰지 않음, 오케스트레이터가 `http://localhost:8790/relay/`에서 확인).
- 네이버식 3D 그라운드·실제 궤적·타구 방향: 자료 없음(위 '연출의 한계'). Statcast release/velocity 필드가 있어야 가능.
- `@media (prefers-color-scheme: dark)` 자동 전환: 브리프대로 넣지 않음(기본 항상 라이트, 저장값만 따름).
- Hallmark `dark-mode.md`의 "다크에서 본문 굵기 −50"은 시스템 글꼴에 350 굵기가 없어 적용하지 않았다. Hallmark 스탬프 주석(gate 20)·sloplint 실행은 하지 않았다(규칙을 손으로 적용·점검).
- 비선택 투구 원 불투명도 .78→.9, `--strike`·`--switch-on` 라이트 값은 대비 때문에 브리프 출발값과 다르다(위 토큰 절).

### 검토 반영 (2026-11-06) — 다른 모델 검토 C-F1~F5, D-F1~F8
검토자의 지적은 전부 현재 파일에서 다시 확인했다(틀린 지적 없음). P1·P2는 모두 고쳤고 P3도 변경이 작아 전부 반영했다. 브리프에서 벗어난 것 두 가지(D-F4)는 아래에 적는다.

| 지적 | 우선 | 처리 | 바꾼 것 |
|---|---|---|---|
| C-F1 자막이 같은 타석의 다른 번호 원을 덮음(31/262), 오버레이가 툴팁을 막음 | P2 | 고침 | `renderZone`이 번호 원·추천 네모 자리(obs)를 모아 `drawCaption`에 넘기고, 순수 함수 `captionSpot`이 창 안 여섯 자리 중 겹치지 않는 첫 자리를 고른다(262구 겹침 0). 전부 겹치면 최소 겹침 자리 + 1.2초 뒤 `.dim`(.6). `.z-anim { pointer-events: none }` |
| C-F2 / D-F2 테마 버튼 접근성 이름에 보이는 글자가 없음(WCAG 2.5.3) | P2 | 고침 | `aria-label` "어둡게, 지금은 밝은 화면" / "밝게, 지금은 어두운 화면"(index.html 초기값, relay.js `setTheme`) |
| C-F3 파울의 좌우 이동도 연출인데 화면 문구가 타구만 다룸 | P3 | 고침 | 범례 문구에 "파울은 타자 쪽 뒤로 보내는 연출입니다" 추가 |
| C-F4 / D-F8(b) "em dash 0"인데 로딩 전 자리표시 '—' 5개 | P3 | 고침 | 자리표시 5개를 비움(init이 채움). 검증 문구를 실제 수치로 고침 |
| C-F5 OS 감속 모션 설정이 바뀌면 라벨만 갱신 | P3 | 고침 | `storedAnimPref()` 분리, change 핸들러가 저장값 없을 때 기본값 재계산 + `renderAnimSwitch` + 지금 투구 `renderZone` |
| D-F1 라이트에서 B/S/O 점·주자 베이스 켜짐/꺼짐이 안 갈림(1.07 / 1.02 / 1.17) | P1 | 고침 | `.c-row i.on`, `.diamond path.on` 채움을 `--accent-ink`로(라이트 6.00 / 4.82, 다크는 같은 라임). 대비 표에 상태 쌍 추가 |
| D-F3 스윙이 −150°로 몸통 안까지 가고 400ms에 0°로 점프 | P3 | 고침 | keyframes 0 → −105°(30%) → −120°(45~65%) → 0(100%), 480ms `both`, 500ms 뒤 클래스 제거 |
| D-F4 300 ft 이상 아웃·2루타 7구가 홈런처럼 화면 밖으로, 파울팁이 뒤로 날아감 | P3 | 고침(브리프와 다름) | `plan.out = event === "home_run"`(3구), `foul_tip` → 새 분기 `tip`(포수 앞으로 40단위 떨어지며 사라짐). 브리프 표의 "≥300 ft 화면 밖", "foul_tip = foul"에서 벗어남: 실제 결과(event)와 어긋나는 연출을 피하기 위해 |
| D-F5 자막 글자가 320px에서 11.5 / 9px | P3 | 고침 | `.z-caption text` 18, `.z-cap-sub` 15 단위(320px 13.8 / 11.5px, 390px 17.2 / 14.4px, 430px 19.1 / 15.9px), rect 높이 30. JS 배율 보정 대신 고정 단위 |
| D-F6 라이트에서 추천 1·2·3 네모 위계가 톤으로 안 갈림(1.01~1.12) | P3 | 고침 | 테두리 굵기 2.5 / 2 / 1.5, 3순위 테두리 `--muted`(존 네모·범례·칩 동일). 점선은 이미 '화면 밖' 표식(`.out`)에 쓰여 쓰지 않았다 |
| D-F7 꺼진 스위치 트랙이 거의 안 보임(1.25 / 1.33) | P3 | 고침 | `.switch { border: 1px solid var(--muted) }`(라이트 5.39, 다크 7.63). 켜짐은 기존 `--accent-ink` |
| D-F8(a) 대비 표에 상태 쌍이 없음 | P3 | 고침 | 위 대비 표에 7쌍 추가(38쌍) |

브리프 대비 달라진 값(이번 검토로): 자막 글자 15 → 18 단위(작은 글자 12 → 15), 스윙 260ms(−150°) → 480ms(−120°, 되돌아옴 포함), 홈런 판정 비거리 → `event`, 파울팁 분기 분리, B/S/O 점·베이스 켜짐 채움 `--accent` → `--accent-ink`. 브라우저에서의 실제 보임새는 **미측정**(오케스트레이터 확인).

## 3D 타자 요청 (2026-11-08)

- 사용자 요청: 막대 스윙이 아니라 네이버 스포츠처럼 사람 같은 3D 타자 애니메이션. GPT에게 시킬 프롬프트를 `GPT_PROMPT_batter3d.md`(저장소 밖 보관)로 작성했다.
- 분리 원칙: GPT 산출물은 `batter3d/` 새 폴더에만 받는다(three.js vendor, glb, demo.html). 기존 index.html, relay.css, relay.js는 수정하지 않고, 연결(playAnim 분기에서 호출)은 이 세션이 따로 한다.
- 한계: 3D 소재(캐릭터, 스윙 클립)는 GPT가 만들지 못한다. Mixamo 내려받기와 Blender 변환은 사람이 한다. 야구 클립 이름은 미확인. 모듈을 붙이면 "외부 자원 0" 원칙이 바뀌므로 공개 배포 포함 여부는 사용자 결정.
- 11/8 확인: 데모 서버가 11/6에 앱에 의해 멈춰 있어 다시 켰다. 브라우저 창이 보이는 상태에서는 rAF가 정상 동작(0.3초에 20프레임)하고 콘솔 오류 0.


## 3차 시안 (2026-11-09) — 디자인 다시 그리기: 카드(벤토)·떠 있는 알약 탭·점수판 타일·데스크톱(Mac) 2열

사용자 요청(11/9): 캐릭터 교체(EXHIBIT-batter3d-4)는 일단 보류하고, 마네킹(3D 더미)은 그대로 둔 채 "요즘 유행하는 디자인으로 깔끔하고 예쁘게", 썸네일을 Mac에서도 볼 수 있게. 배포 서버 반영 없음(로컬만). 수정 파일은 `relay.css`(전면 재작성, 35,895 B, SHA `b20c599e…`)와 `index.html`(11,715 B, SHA `f3ad7b62…`: `.stage`/`.controls`/`.feed` 묶음 div 3개, `relay.css?v=3`, `?theme=dark|light` 검증용 매개변수, theme-color 초기값) 둘뿐이다. `relay.js`(SHA `ae512da1…`)·`batter3d-host.js`(`82d4e783…`)·`batter3d/` 모듈·`data/`는 손대지 않았다.

### 바뀐 것

| 영역 | 2차(11/6) | 3차(11/9) |
|---|---|---|
| 바탕 | 단색 종이 | 종이 위 왼쪽 위 라임 빛·오른쪽 아래 흰 빛(다크: 짙은 녹색 빛) 라디얼 그라데이션, `background-attachment: fixed` |
| 면 | 1px 선으로 나눈 띠 | 흰 카드(라운드 20px, 머리카락 테두리 `--hair`, 부드러운 그림자 `--shadow-card`). 카드 사이 10px |
| 상단 탭(중계/라인업/기록) | 밑줄 탭, 고정 띠 | 떠 있는 알약(유리 blur 14px, 그림자) `position: sticky; top: 8px`. 선택 탭은 잉크색 알약(다크: 라임 알약) |
| 스위치 두 개 | 전체 폭 띠 2줄 | 작은 카드 2장 나란히(359px 이하 1열). iOS식 흰 손잡이 |
| 점수판 | 종이색 띠 | 라이트에서도 짙은 녹색 타일(그라데이션 + 라임 빛). 안에서만 토큰을 바꿔(`--ink`·`--muted`·`--line`·`--accent-ink`·`--diamond-off`) 아래 규칙은 그대로 재사용. 팀 약어는 알약, 숫자 40px, 이닝 알약 |
| 존 그림 | 패널색 띠 | 폭 전체를 쓰는 무대(카드 아님: 3D 캔버스가 양옆으로 넘칠 공간). 존 바깥 사각형 `rx 14`, 존 상자 카드색 채움, SVG 전체 `drop-shadow`. 데스크톱에서는 카드 |
| 추천 칩 | 같은 패널색 3장 | 1순위만 라임 그라데이션 카드(`--chip1-a/b/line`), 2·3순위 흰 카드. 이전/다음은 44px 원형 버튼 |
| 이닝 탭 | 알약(패널색) | 흰 알약 카드 + 그림자, 선택은 잉크색(다크: 라임). 유리 띠 `top: var(--top-h)` |
| 타석 카드 | 패널색, 선택 카드 안쪽 1px | 흰 카드, 현재 카드 1.5px 라임잉크 링, 투구 행 hover 패널색, 12px 라운드 |
| 글꼴 | Apple SD Gothic Neo/Malgun/Segoe | `-apple-system, BlinkMacSystemFont, Apple SD Gothic Neo, Pretendard, Segoe UI Variable, Segoe UI, Malgun Gothic` (Mac은 시스템 글꼴). 워드마크만 Arial Black 유지(홈 데모와 같게) |
| 데스크톱(Mac) | 430px 열 가운데 정렬(큰 화면에서 "썸네일"처럼 보임) | 600px 이상 560px 열, **960px 이상 2열**: 왼쪽 `.stage`(조작·점수판·존·추천, 380~460px) + 오른쪽 `.feed`(이닝 탭·타석 목록). 헤더가 유리 띠로 고정(64px)되고 탭 알약이 그 가운데 겹쳐 뜬다(`margin-top: -56px`, 알약 밖은 `pointer-events: none`). 왼쪽 열은 `position: sticky; bottom: 16px`라 목록을 길게 내려도 존·추천이 화면에 남는다(목록이 왼쪽 열보다 길 때만) |

색 리터럴은 여전히 `:root`와 `[data-theme="dark"]` 두 토큰 블록에만 있다(새 토큰: `--bg-glow(2)`, `--card`, `--hair`, `--knob`, `--glass`, `--glass-line`, `--board-a/b/ink/muted/line/off`, `--chip1-a/b/line`, `--tab-on`, `--on-tab`, `--shadow-card/float`, `--page-max`, `--top-h`). `--muted`는 라이트에서 `#4f6457`→`#566b5d`, `--bg` `#f4f7ef`→`#eef3e8`, `--line` `#c5d2c0`→`#d9e3d3`.

### 3D 타자(더미) 기하 — 바뀌지 않음(측정, Chromium 창 폭별 `clientWidth/Height`)

| 폭 | `.zone-row` | 3D 캔버스 | 비고 |
|---|---|---|---|
| 320 | 288×209 | 218×209 | `--wide3d 84px`(2차와 같음) |
| 390 | 358×267 | 260×267 | 2차 측정값과 동일 |
| 1280 | 398×310 | 260×310 | `.zone-row max-width: 398px` = 2차의 430px 열 최대값. 이보다 커지지 않는다 |

호스트 어댑터·카메라(zoom 0.8)·클립 구간 변경 없음. 데스크톱 2열 뒤에도 `PZRelay.state3D()` attached·webgl, 다음 투구 2회에서 contact_hit1 재생(k 0.724로 끝 자세 유지)·자막 "삼진 파울팁" 확인.

### 대비 (WCAG 2.x, python -I 계산) — 24쌍 전부 4.5:1 이상

라이트: muted/card 5.74, muted/bg 5.09, muted/panel 5.20, accent-ink/card 6.50, accent-ink/bg 5.76, ink/card 16.65, on-tab/tab-on 15.38, chip1 ink/chip1-b 13.43, orange-ink/card 6.25. 점수판 타일: ink 16.59, muted 8.47~9.74, 라임 13.54. 다크: muted/card 8.02, 라임/card 14.81, on-tab/tab-on 15.82, 라임/chip1-b 12.88, orange-ink/card 10.05, on-orange/orange 9.83.

### 검증 (2026-11-09, 앱 안 Chromium + 헤드리스 Chrome)

- 폭 320·360·375·390·768·1280에서 가로 스크롤 0(`scrollWidth` = 폭). 처음 만든 `.feed` 격자가 이닝 탭 줄(가로 스크롤)의 내용 폭 때문에 열을 넓혀 타석 카드가 잘렸던 것을 `grid-template-columns: minmax(0, 1fr)`로 고쳤다(390px 카드 365px 확인).
- 점수판 윗줄: 390px에서 점수 156px + 상황 160px = 330px로 여유 0이라 배율 2 헤드리스 캡처에서 이닝 알약이 SD 알약에 닿았다 → 429px 이하 숫자 36px·간격 6/10px(390px 재측정: 점수 143px, 상황 칸 173px 안에 내용 전부). 360px(상황 칸 130px)·320px에서는 이닝 알약이 숫자 위로 겹쳤다 → 389px 이하에서 상황 줄을 점수 아래로 내림(320px 상황 줄 260/260px).
- 헤더: 320px에서 태그가 세 줄(43px 폭)이던 것을 워드마크 17px·도장 26px·테마 버튼 아이콘 생략으로 두 줄(72px)로.
- 라이트/다크 × 폰/Mac, 라인업·기록 탭(데스크톱 760px 열, 라인업 2열) 캡처. 테마 전환·스위치·이전/다음·이닝 탭 동작 그대로.
- 캡처: `captures-20261109/hd-*.png`(헤드리스 Chrome + SwiftShader, 배율 2: Mac 1440×900 라이트·다크, 폰 390×844 다크 — 폰은 Chrome 최소 창 폭 때문에 같은 출처 iframe 래퍼 `phone-frame.html`로 찍어 잘라냄), `pane-*.jpg`(앱 안 브라우저 화면 그대로, 1.2배), `thumb-design3.png`(Mac 라이트·다크 + 폰 라이트·다크 모음 썸네일, 2400×1500). **폰 라이트 배율 2 캡처는 없다**: 헤드리스 SwiftShader에서 라이트 테마 로딩은 3D 타자가 붙지 않고 SVG 대체로 끝나는 일이 잦았다(직접 로딩 5회 중 2회만 3D, iframe 래퍼 13회 전부 SVG; 다크는 전부 3D). 앱 안 브라우저(실제 GPU)에서는 라이트·다크 모두 매번 3D가 붙어 캡처 환경 문제로 보지만 원인은 **미확인**(다른 모델 검토 때 함께 볼 것: 느린 GPU에서 초기화 경쟁 가능성). 썸네일의 폰 라이트 칸은 앱 안 브라우저 캡처(`pane-phone390-light-top.jpg`)를 썼다.

### 미측정·하지 않은 것

- 실제 Mac Safari(`backdrop-filter`·`-apple-system` 글꼴·`overflow: clip`)와 iPhone 실기기는 **미측정**(Chromium만). Safari 16 이상이면 쓴 속성은 모두 지원 범위(추정).
- 감속 모션 설정은 전환·애니메이션을 끄는 규칙만 있고 미측정.
- 상단 알약 위 8px 틈으로 스크롤 내용이 비친다(의도한 "섬" 모양이나 글이 지나갈 때 어수선해 보일 수 있음). 다른 모델 검토 전.
- 배포·커밋·push 없음. 단위 3(3D 호스트 연결)과 함께 **미커밋**.


## v1 기록과 v2 시안 (2026-11-09 03:xx) — Song 틀 + 3D 타자

사용자 전달(11/9): 현재 각도(−22°)는 좋다. 배포는 하지 않는다. Song의 요청은 **틀·비율 유지**다. 그래서 지금 화면을 **v1**로 기록하고, Song 틀에 맞춘 **v2**를 로컬로 만들었다.

| 버전 | 파일 | 무엇 |
|---|---|---|
| **v1** | `index.html`(11,715 B, SHA `f3ad7b62`), `relay.css`(35,895 B, `b20c599e`) | 디자인 3차(카드·알약 탭·점수판 타일·Mac 2열) + 3D 타자(`?batter3d=batter-ctl`). 기본 모델은 마네킹 그대로 |
| **v2** | `v2.html`(10,740 B, `4e82b461`), `relay-v2.css`(21,892 B, `e7bb44cd`) | Song 고정 빌드(c47fe6cb) 경기 화면의 틀(`songapp-mock/mock.css` 측정값) + 실루엣 자리에 3D 타자. 열기: `relay/v2.html?batter3d=batter-ctl` |
| 공용 | `relay.js`(56,987 B, `a4ec1484`), `batter3d-host.js`(`940d9691`), `batter3d/batter3d.js`(`e9b8b187`), `data/`, `batter3d/assets/` | 두 버전이 같은 스크립트·자료를 쓴다. relay.js의 v2 분기는 `document.documentElement.dataset.v2`(v2.html이 세팅)로만 켜진다: 존 창 여백을 Song 라이브 메인 창(x .12, z .24, pad .08)으로 |

### v2에서 그대로 둔 Song 틀(측정값 → v2)

헤더 1행 44px(1fr auto 1fr, padding 0 12 0 6) · 2행 60px(auto 1fr, padding 6 12 7 14) · 카드 바깥 여백 12px · 흰 카드 padding 14px 12px 4px, radius 0, 섹션 gap 10px · 존 행 **216px**, 열 28px | 1fr | 28px(존 그림 폭 286px = Song viewBox 폭) · 범례 13px · 추천: border-top, padding-top 12, 제목 16px, 3칸 min-height 52px/padding 4 0 8/17px · 실제 투구 줄 13px 라벨 + 16px · 이번 타석: border-top, 머리 44px, 행 44px(g1 22px) · 하단 탭 바 padding 6px 8px, 버튼 52px, 13px 600, 아이콘 24px stroke 1.8 · 폭 390px 고정(넓은 화면은 가운데 정렬). 섹션 순서 헤더 → 존 → 범례 → 추천 → 실제 투구 → 이번 타석 → 하단 탭.

### v2에서 우리 것

- 3D 타자: Song 실루엣 자리(`.batband` absolute, left/right 4px)에 **absolute 140×210px** 캔버스. `has3d`여도 열 폭 28px 그대로라 어떤 요소도 안 움직인다(v1은 열을 100px로 넓혔다). 카메라는 모델 메타(−22°, 10°, targetY .55)와 호스트 zoom .8 → 폭 제약으로 타자 키 약 134px(Song 실루엣 124px과 비슷). 좌타자는 왼쪽, 우타자는 오른쪽(거울).
- relay.js가 만드는 DOM을 CSS로만 Song 틀에 맞췄다. Song 메인에 없는 정보는 숨김: 추천 칩의 위치 글·비중, 면책 2문단, 범례 설명 2줄, 실제 투구의 위치·회전수·익스텐션·타구 행, 이닝 탭, 현재 타석 외 카드·반이닝 머리, 투수/타자 누적 줄. 두 스위치(자동 진행·애니메이션)는 카드 **아래** 작은 줄로(틀 밖).
- 색·굵기는 11/3 시각 제안(P1·P2) 값. 밝은 화면만(Song과 같음).

### 측정(앱 안 Chromium, 390px)

헤더 44/60px, 존 행 216px, 존 그림 286×216px, 3D 캔버스 140×210, 카드 폭 366px, 가로 스크롤 0. 존 상자는 **119×128px**(Song 150×160): 우리 존 SVG는 결과 자막 자리를 같은 viewBox 안에 두어 상자가 Song보다 작다(relay.js 그리기, v1과 공유라 v2에서 바꾸지 않음). 헛스윙 재생·대기 복귀·하단 탭 전환 정상. 캡처 `captures-20261109/v2-*.jpg`.

### 한계

- 틀은 mock.css의 측정값이지 Song 빌드 CSS를 직접 읽은 것이 아니다(mock은 11/3에 빌드 CSS와 대조해 만든 것). Song 앱의 라인스코어·뒤로 가기·"자세히"·"접기"·상세 시트는 없다(우리 데이터 흐름에 없음).
- 실제 투구 줄의 "(SI)"·"(96.3 mph)"는 relay.js 문구 그대로(Song은 "싱커 155km/h").
- v1·v2 모두 미커밋·미배포. 어느 쪽을 쓸지, Song에게 v2를 보여 줄지는 사용자 결정.

### 비교 페이지 `compare.html` (2026-11-09 03:4x)

사용자 결정 "둘 다 보여주자" → `relay/compare.html`: v1(index.html)과 v2(v2.html)를 같은 출처 iframe 390×844로 나란히 띄우고, 위 버튼(이전/다음 투구/처음으로)으로 두 화면을 함께 넘긴다(각 iframe의 `#btn-prev/#btn-next` 클릭). 열기 `http://localhost:8790/relay/compare.html`. 두 iframe 모두 3D 붙음·대기 반복 확인(900px 창). 캡처 `captures-20261109/cmp-*.jpg`, 스윙 GIF `cmp-swing.gif`. Song에게는 캡처·GIF를 사용자가 전달한다(배포 없음, 외부 구매 모델 변환본은 보내지 않음).



### 단일 파일 데모·색 변형 (2026-11-09 04:xx)

사용자 요청 둘: "형에게 데모 버전도 HTML 파일로 보낼 수 있나(디자인만 보여주는 느낌)" · "형 틀에 맞춘 v2에서 틀·디자인은 두고 색만 바꿔 볼래?"

**단일 파일 데모** — `tools/bundle-demo.mjs`(6,818 B, SHA `af6f718c`): `node tools/bundle-demo.mjs v1|v2 <출력 폴더>`. HTML에 CSS·relay.js·경기 자료 JSON·3D 모듈/어댑터·three.js(vendor)·`batter-ctl.glb`(base64)·메타를 전부 넣는다. 서버 없이 더블클릭으로 열린다. 방법: fetch 가로채기(`data/849843.json`, `batter3d/assets/*` → 내장 문자열 또는 `data:` URL; GLTFLoader의 FileLoader도 fetch라 같이 잡힘), ES 모듈은 소스를 문자열로 넣고 실행 때 Blob URL을 만들어 import 지정자를 바꿔 끼운 뒤 어댑터를 `import()`(import map 없음), 기본 모델 `batter-ctl` 고정. 출력은 저장소 밖 `D:/pitcheezy_assets/build/demo/`: `pitcheezy-relay-v1-demo.html` 7,476,082 B(SHA `293d439b`), `pitcheezy-relay-v2-demo.html` 7,463,691 B(SHA `ebe4a24e`). 검증: 앱 안 Chromium(http, 임시 복사본)에서 두 파일 모두 자료 로딩·3D 연결·대기 반복 정상; 헤드리스 Chrome `file://`에서 스크립트 오류 0(첫 빌드에 있던 `String.replace`의 `$'` 패턴 사고 — three.js 소스에 `$'`가 있어 치환 문자열 안에 `</html>`이 끼어든 것 — 함수형 치환으로 수정). **주의:** 외부 구매 모델 변환본이 파일 안에 들어 있으므로 팀 내부(Song)에게만 비공개로 전달하고 공개 게시·공개 버킷 업로드는 하지 않는다. Mac Safari에서의 동작은 미측정(Blob 모듈·WebP 텍스처·WebGL은 Safari 15 이상이면 지원 범위, 추정).

**v2 색 변형 'pz'** — `relay-v2.css`(23,511 B, `16c32e88`)에 토큰 4개 추가(`--s-rec1`, `--s-on-rec1`, `--s-on-play`, `--s-nav-on`)하고 `:root[data-palette="pz"]`에서 Song 색 토큰을 Pitcheezy 색(헤더 #091811, 강조 글자·테두리 #2f6b12, 1순위 채움 라임 #ceff78, 2순위 #e7f8c6, 타격 #ffb782, 종이 #eef3e8)으로 덮어쓴다. 기하·글자 크기·간격 규칙은 한 줄도 바꾸지 않았다. `v2.html`(11,711 B, `bd3bb1bc`): `?palette=pz` 또는 카드 아래 '색' 선택(Song 색 / Pitcheezy 색; 틀 밖). 기본은 Song 색. 캡처 `captures-20261109/v2-palette-*.jpg`.


## 버전 이름 정리(v0·v1·v2)와 Codex '단위 3' 지시 대조 (2026-11-09 09:2x)

사용자 결정(11/9 09시): **지금 배포되어 있는 화면 = v0**로 부른다(우리 안에서도 같은 이름). 형(Song)에게도 v0으로 설명한다.

| 이름 | 무엇 | 어디 |
|---|---|---|
| **v0** | 현재 배포본. Song 고정 빌드(c47fe6cb)의 모바일 경기 화면, 터치까지 계산된 틀. 우리가 손대지 않음 | 배포 서버(이 저장소에 없음) |
| **v1** | 우리 디자인 3차(카드·알약 탭·점수판 타일·Mac 2열) + 3D 타자 | `index.html` + `relay.css` |
| **v2** | v0의 틀·비율 그대로 + 실루엣 자리에만 3D 타자, 색은 Song 색 기본·`?palette=pz`로 Pitcheezy 색 | `v2.html` + `relay-v2.css` |
| **v2-tabs** | (처음 이름 v3, 11/9 15~17시) v2 틀 + Pitcheezy 색 기본 + 조작 세 줄을 v0 선수 시트 탭 양식으로 | `v2-tabs.html` + `relay-v2.css` + `relay-v2-tabs.css` |
| **V3** | **Song 배포 빌드(c47fe6cb) 그대로 + Pitcheezy 색 테마 + 우리 3D 타자**(11/9 17시 사용자 정의). Song JS·CSS 바이트 불변, index.html에 태그 3개만 삽입 | 빌드 `tools/build-songskin.mjs` → `D:/pitcheezy_exhibit_check/v3-songskin-20261109/`; 소스 `tools/songskin/pz-theme.css`·`pz-batter.js` |
| **V4** | v2 공 연출·‹ › + V3식 머리(보고 있는 공 직전 시점) + 아래 메뉴 추천·선수·구종·기록(Song 시트 사양) + 라인업 화면 + 고정 스위치 줄 + 유니폼 팀 색 + 나가기 동작(출루 달리기·아웃 옆걸음), 11/9 21~23시 로컬 | `v4.html` + `relay-v4.css` + `relay-v4.js`, 모델 `batter3d/assets/batter-ctl-v4.glb` |

사용자가 붙여 준 Codex 채팅 답변(우리 작업 폴더를 읽지 않은 채팅)은 **단위 3 '호스트 최소 연결' 지시 5항목**과 같은 글이다. 이 다섯 항목은 2026-11-08 20:1x~21:xx에 이미 그대로 수행해 CHECKLIST `EXHIBIT-batter3d-3`와 `batter3d/README.md` 9절에 기록되어 있다(정점 속성 보존 `tools/verify-glb-attrs.mjs` 바이트 대조 일치, 로컬 체크포인트 커밋 `5191357`(모델 파일 포함, push하지 않음), SVG 대체 경로 보존 연결, 클립 비교 contact_hit1 0→2.10 s 선택, 호스트 검증·누적 검사). 지시가 가리키는 `batter-indexed`·`contact_hit1/2`는 마네킹 시절 이름이고, 단위 4에서 캐릭터가 `batter-ctl`(자체 contact/miss 클립, `meta.play` 구간 end 1.85/3.33 s)로 바뀌었다. 단위 4에서 다시 확인하지 않았던 한 항목 — 화면 진입·이탈 반복 뒤 자원 누적 — 을 batter-ctl(대기 반복 rAF가 새로 생김)로 오늘 재측정했다.

### batter-ctl 누적 검사(앱 안 Chromium, 앞 탭, `v2.html?batter3d=batter-ctl`, 2026-11-09 09:1x)

| 검사 | 결과 |
|---|---|
| 시작 상태 | attached, idleLoop true, idleRendered 554, gpu geometries 8·programs 4·textures 14, 캔버스 1 |
| 화면 진입·이탈 20회(라인업↔중계) | 띠 폭 0↔140 px 20쌍 전부 같음, attached 유지, gpu 8/4/14 불변 |
| 연속 재생 30회(120 ms 간격, 스윙 중 끊기) → 4 s 뒤 | kind null·k 0(대기 복귀), idleLoop true, 대기 프레임 30/s, gpu 8/4/14 불변 |
| 해제·재연결 10회(`PZRelay.detach3D` → `PZBatter3D.init`) | 10/10 재연결(init 203~557 ms, 합계 8.1 s), 캔버스 1·상자 1, idleLoop true 30/s, gpu 8/4/14 불변 |
| 전체 뒤 | 미해결 rAF **1**(대기 반복의 다음 프레임 1건, 정상), 리스너 순증 0(검사 코드 자신의 1건 제외), status "연결됨" |

Codex 지시와 지금 상태 사이에 충돌은 없다. 지시의 2번(체크포인트 커밋)에 해당하는 **단위 3·4·디자인 3차·v2 변경분은 아직 미커밋**이며, 커밋 여부는 사용자 결정(이 세션은 커밋하지 않음).


## 안 치는 공 반응 'take' (2026-11-09 09:3x~10:3x) — 볼·루킹 스트라이크·블록 뒤 한 발 물러나기

사용자 요청(11/9 09시, Mixamo `Baseball_Step_Out.fbx` 다시 첨부): "공이 스트라이크나 볼일 때는 이모션이 들어갔으면 좋겠는데 v1 v2 다시 수정해줘". 캐릭터 패키지(외부 구매)에는 반응용 클립이 없어(달리기·점프·슬라이드·걷기뿐) Mixamo 클립을 이 캐릭터 뼈대로 옮겼다. 02시의 자동 재대상(SkeletonUtils.retargetClip)은 발이 53~95 cm 떠서 실패했었고, 이번엔 방법을 바꿨다.

### 옮기기(`batter3d/tools/retarget-mixamo.mjs`, Node)

- 두 뼈대의 **휴식 자세**(대상 = 스킨 바인드 A-pose, 원본 = 노드 T-pose; 둘 다 Y 위·정면 +z·왼쪽 +x로 측정됨)를 기준으로 뼈마다 (1) 부모→자식 방향이 같아지게 대상 휴식 회전을 돌려 맞추고(어깨·팔 42~55°, 다리 7~11°, 손가락 47~63°), (2) 프레임마다 원본 뼈의 **월드 회전 변화량**(현재×휴식⁻¹)을 그 위에 곱해 대상 월드 회전으로 삼은 뒤, (3) 위에서 아래로 부모 회전을 나눠 로컬 트랙을 만든다. 골반 위치는 다리 길이 비율 1.6327(대상 83.0 / 원본 50.8 cm)로.
- 뼈 축 규약이 달라(Mixamo Y축, UE계 X축) 로컬 회전 복사는 쓰지 않는다. 같은 이름이 둘인 spine_03·neck_01은 자식이 있는 쪽을 쓰고 트랙 이름은 뼈 이름 그대로(원본 클립들과 같은 방식).
- 첫 실행은 다리가 위로 솟았다(발목 82~160 cm): 부모의 저장된 월드 회전을 제자리에서 `invert()`해 다음 형제부터 깨진 것 → clone 뒤 뒤집기로 수정. 디버그 모드(`RETARGET_DEBUG=1`)는 정렬 휴식 자세만 적용해 T-pose 재구성을 확인한다.
- 결과(52쌍 뼈, 94키 30 fps, 3.1 s): 발목 높이 8.2~19.5 cm(바인드 9.3), 발끝 최저 -2.9 cm, 머리 143.4~152.4 cm(대기 149), 시작 자세와 대기 자세 차이 손 17.9/18.3·발 18.7/6.3·머리 15.1 cm(→ 모듈 섞기 0.3 s로 가림). 보고서 `D:/pitcheezy_assets/build/retarget-take-report.json`, 클립 `D:/pitcheezy_assets/(ctl 입력 폴더)/take.clip.json`(492,131 B, SHA `832c43db`).
- Node에서 vendor three.js를 `three`/`three/addons/`로 쓰는 로더 `tools/node-three.mjs`(+`node-three-hooks.mjs`) 추가. 실행: `node --import ./node-three.mjs retarget-mixamo.mjs <ANIM_Idle.fbx> <Step_Out.fbx> <out.json> take <report.json>`.

### 변환기·모델

- `fbx-to-glb.html` 'ctl' 프로필: `extraClips`(take.clip.json → 'take'), `playEnd.take 2.6`, `playCue.take 0.3`, meta `clips.take.source`·`play.take`. **빌드 4** `batter-ctl.glb` 3,089,640 B, SHA `c34da227`(빌드 3 2,979,472 B + 클립 약 110 KB; primitive·텍스처 변화 없음), 저장 뒤 다시 읽어 SHA 일치. 메타는 기존 데모 측정값(contact/miss cue·view·bat)을 두고 take·output·source만 합쳤다(11,138 B, SHA `10ee9acd`). 빌드 3 원본은 `D:/pitcheezy_assets/build/prev-build3/`에 보존.

### 모듈·어댑터·호스트

- `batter3d.js`: `SWING_KINDS`에 take. 대기 반복 → 클립 **0.3 s 섞기**(`BLEND_IN`), 클립 끝 → 대기 0.35 s(take는 0.6 s). 섞기는 모듈이 직접 가중치를 선형으로 옮긴다(`startBlend/stepBlend`: 지금 값에서 시작, 합 1 유지, 0이 된 액션 stop) — three.js fadeIn/fadeOut은 항상 0/1에서 다시 시작해 섞기 도중 끊기면 튀고, 이전 `reset()`의 crossFadeTo는 paused 액션에서 isRunning()이 false라 실제로는 컷이었다. `reset({still})`: 호스트가 정지 자세를 원하거나 OS 감속 모션이면 반복 없이 시각 0. `sample()`은 섞기를 즉시 끝내 요청 클립만의 자세. `getState().weights/blending` 추가(검증용). `activate()` 제거.
- `batter3d-host.js`: `resolvePlay`가 선택 항목 take를 받고, init에서 glb와 안 맞는 take는 빼기만 한다(contact·miss는 그대로 치명). `api.react(leadMs)` — 공 도착 + **250 ms** 뒤 take 0.3→2.6 s 원속도, 그 전엔 대기 반복 유지(첫 프레임에 reset 한 번: 끊긴 자세였다면 대기로). `reset(o)` 전달. 마네킹은 null.
- `relay.js`: `playAnim`에 `plan.kind` take|block 분기(side·3D 연결·`react` 있을 때만, 끝나면 `reset`). `b3Still()` = 애니메이션 스위치 끔·감속 모션·중계 탭 아님 → cancelAnim·b3Show·연출 끝·탭 전환에서 `reset(b3Still())`(다른 탭의 숨은 캔버스에 30 fps로 그리지 않음). SVG 타자·마네킹·판정·자막은 그대로. v1·v2 공용이라 둘 다 바뀐다.
- `demo.html` 종류 선택에 take.

### 측정(앱 안 Chromium, 앞 탭)

| 항목 | 결과 |
|---|---|
| v2 볼(Bregman 우타) | 자막 "볼" 770 ms → take 시작 926 ms(k 0.10), 섞기 0→0.55→1(0.3 s), k 0.79에서 끝 3.07 s → 대기 섞기 0.38→0.86→1(0.35 s) |
| v2 루킹 스트라이크(Crow-Armstrong 좌타, 거울) | 자막 767 ms → take 923 ms, 같은 진행, 왼쪽으로 물러남 |
| v1(데스크톱 2열) 볼 | take 1,076 ms에 가중치 0.55, 진행 동일 |
| 헛스윙(miss) 회귀 | 섞기 0.49→0.99(0.3 s), k 진행 전과 같음, 끝→대기 섞기 0.1→0.48→0.95→1 |
| 섞기 도중 끊기(검토 반영 뒤, rAF마다 가중치 기록) | 첫 헛스윙 섞기 200 ms에 타격으로 / 첫 반응 섞기 1.0 s에 다음 볼로 / 반응 1.3 s에 타격으로: 프레임당 변화 최대 0.058(=1/60/0.3), active+idle 합 최대 1.000, 끝 대기 1 |
| 정지 조건 | 애니메이션 스위치 끔 → 대기 반복 정지(정지 자세), 켬 → 재개; 라인업·기록 탭 → 정지, 중계 복귀 → 재개 |
| 누적 | 연속 24회(120 ms, 반응·스윙 섞여 끊김) + 완주 5회 + 앞선 진입·이탈 20회·재연결 10회: 캔버스 1, geometries 8·programs 4·textures 14 불변, 미해결 rAF 1(대기분), 리스너 순증 0, 대기 30 fps |
| 단일 파일 데모 재생성 | v1 7,633,045 B, SHA `87638ffd`, v2 7,620,654 B, SHA `923d2bd7` — 둘 다 클립 5개·play.take 확인(서버 복사본으로 열어 확인 뒤 삭제) |

캡처 `captures-20261109/take-demo-k*.png`(데모 k 0.10~0.84), `take-v2-R-*.png`(우타 볼 1~4 s), `take-v2-L-*.png`(좌타 루킹), `take-v1-desktop-2s.jpg`.

### 독립 검토(같은 모델 Workflow; GPT 검토 대체 아님)

Workflow 29 에이전트(관점 3 × 읽기 검토 → 지적마다 반박 2, 350만 토큰, 30분). 지적 13건 중 확정 12(중복 포함)·기각 1(같은 이름 뼈 트랙 바인딩 — 원본 클립과 같은 방식이라 문제 아님). 확정 지적과 반영:
- (중) three.js crossFadeFrom/To는 가중치를 항상 0/1에서 다시 시작해, 섞기 도중 다음 투구로 끊기면 자세가 한 프레임에 튀고 세 액션이 겹친다 → 모듈이 직접 가중치를 옮기는 `startBlend/stepBlend`(지금 값에서 선형, 합 1 유지, 0이 된 액션 stop)로 교체. 측정(rAF마다 가중치 기록): 첫 헛스윙 섞기 도중 타격으로 끊기, 첫 반응 섞기 도중 다음 볼로 끊기, 반응 중 타격으로 끊기 — 프레임당 가중치 변화 최대 0.058(=1/60/0.3), active+idle 합 최대 1.000, 끝은 항상 대기 1. 첫 구현에서 처음 쓰는 액션을 가중치 읽기 전에 play()해 1에서 시작하던 것도 측정으로 잡아 고침.
- (중) 데모 측정용 `sample()`이 섞기 때문에 결정적이지 않음 → sample 안에서 섞기를 즉시 끝내고 요청 클립만의 자세로.
- (하) meta.play.take가 glb와 안 맞으면 모델 전체가 SVG로 떨어짐 → 어댑터 init에서 take만 빼도록(contact·miss 검사는 그대로 치명).
- (중) 대기 반복이 감속 모션·애니메이션 끔·다른 탭(숨은 캔버스)에서도 30 fps로 돎 → 모듈 `reset({still})` + 감속 모션 자체 확인, 호스트 `b3Still()`(스위치 끔·감속·중계 탭 아님)을 cancelAnim·b3Show·연출 끝·탭 전환에서 전달. 측정: 스위치 끔 → 반복 정지(정지 자세), 켬 → 재개, 라인업/기록 탭 → 정지, 중계 복귀 → 재개.
- (하) 재대상 도구가 스케일 섞인 행렬·정면 불일치를 확인하지 않음 → 회전을 decompose로 뽑고(스케일 카운트 보고), 정면·좌우·위 방향이 다르면 파일을 쓰지 않고 종료 1. 같은 입력에서 다시 돌린 결과는 값 차 6e-8(부동소수)로 같음 — glb에 든 클립(SHA 832c43db)은 그대로 둠.
- (하) 데모의 '연출 기준 시점 추정'이 take에도 cue를 덮어씀 → take는 추정하지 않음, 모델에 없는 클립을 고르면 안내.
- (하) react 없는 옛 어댑터(캐시)와 새 relay.js 조합에서 예외 → `typeof react` 확인.
- (하) 문서 불일치(README 11.8 '보류', 모듈 머리글 '상시 루프 없음', 어댑터 '끝 자세 유지') → 각각 갱신.
반영 뒤 재측정: 연속 24회(끊김 포함) 뒤 캔버스 1, gpu 8/4/14 불변, 미해결 rAF 1(대기분), 리스너 순증 0. 같은 모델 검토라 GPT(다른 모델) 검토를 대체하지 않는다.

### 한계·미측정

- 반응은 한 종류(물러나기)라 볼과 스트라이크의 표정 차이는 없다(클립이 하나). 블록(원바운드)도 같은 반응.
- 물러난 뒤 대기로 섞일 때 25 cm쯤 제자리로 미끄러져 돌아온다(0.35 s). 걸어 돌아오는 동작은 없다.
- 배트는 오른손에 붙어 있어 Mixamo 동작의 손 위치를 따라간다(끝 자세는 오른손에 배트를 늘어뜨린 모양, 데모 캡처 k 0.84).
- 실기기·Safari 미측정. 커밋·push·배포 없음.


## 안타·홈런 타격 'hit' — 치고 1루 쪽으로 달려 나가기 (2026-11-09 13:1x~14:xx)

사용자 요청(11/9 13시, Mixamo `Baseball_Hit_5.fbx` 첨부, 592,912 B SHA `36f15196`): "유효한 타격을 했을 때, 진루 상황이나 홈런 상황에 이걸 하면 좋을 것 같은데 … 치고 나가는 듯한 모션 … 맞는 상황만 바꾸자". 그래서 **인플레이이고 자료의 타석 결과(`actual.event`)가 single·double·triple·home_run일 때만** 이 클립을 쓰고, 아웃(field_out·병살)·실책 출루·파울·파울팁은 전과 같은 contact(팔로스루에서 멈춤)이다. 이 경기(849843) 262구 중 해당 투구는 16개(단타 12·2루타 1·홈런 3; 좌타 4).

### 옮기기(`tools/retarget-mixamo.mjs`, take와 같은 방법)

- `node --import ./node-three.mjs retarget-mixamo.mjs <ANIM_Idle.fbx> <Baseball_Hit_5.fbx> hit.clip.json hit <report>`(대상은 스킨이 있는 ANIM_Idle — A-pose 파일(SM_A-Pose)은 클립이 없어 대기 자세 대조에 못 쓴다; 첫 실행에서 그걸로 돌려 실패). 원본 2.9 s/53트랙 → 결과 2.9 s, 88키 30 fps, 뼈 52쌍(빠진 뼈 없음, 스케일 섞인 행렬 0). 클립 `D:/pitcheezy_assets/(ctl 입력 폴더)/hit.clip.json`(460,347 B, SHA `b2832560`), 보고서 `D:/pitcheezy_assets/build/retarget-hit-report.json`.
- 결과 자세: 발목 6.8~35.3 cm(달릴 때 들림), 발끝 최저 -4.5 cm, 머리 118.3~146.6 cm. 시작 자세와 대기 자세 차이 손 17.9/18.4·발 18.7/6.3·머리 15.1 cm → 모듈 0.3 s 섞기로 가림(take와 같은 크기).
- **골반 이동**(보고서 0.25 s 표본): 2.0 s x −26.7, 2.5 s −44.9, 2.9 s −133.5 cm — 타격 뒤 −x(이 캐릭터의 가슴 쪽 = 호스트 틀의 존 쪽)로 달려 나간다. 우타자(오른쪽 띠)는 화면 왼쪽(투수 시점의 1루 방향)으로, 좌타자(거울)는 화면 오른쪽으로 나간다(아래 한계).

### 변환기·모델(빌드 5)

- `fbx-to-glb.html` 'ctl' 프로필: `extraClips`에 hit.clip.json → 'hit'(각 항목에 `retargeted` 출처 문구; 클립별 `source.note`도 이 값으로 — 처음엔 take 문구가 hit에도 붙어 검토에서 지적, 작업본 메타는 손으로 고침), `playEnd.hit 2.9`(클립 끝), `playCue.hit 1.7`(임시값), meta `play.hit`. 변환기 페이지(앞 탭, 자산 서버 127.0.0.1:8794)에서 검사 → 만들기·저장 → 다시 읽어 SHA 일치. **빌드 5** `assets/batter-ctl.glb` 3,212,124 B, SHA `c56571c4`(클립 6: contact·miss·idle·prepare·take·hit; 빌드 4 3,089,640 B + 약 120 KB). 빌드 4는 `D:/pitcheezy_assets/build/prev-build4/`(변환기 출력)·`prev-build4-assets/`(작업본)에 보존.
- 메타(12,860 B, SHA `804cceda`): 기존(contact/miss 데모 측정 cue·take·view·bat) 유지 + hit 합침. **hit cue = 1.443958 s**(데모 `연출 기준 시점 추정`: 배트 끝 속도 최대 k 0.497917, 240표본 구간 중점, 상대 속도 72.2 m/클립; `clips.hit.contactTime/contactFrac/contactBy`도 데모가 쓰는 대로 채움) — 처음 변환기 임시값 1.7로 빌드한 뒤 이 값으로 바꿨고, 검토 2차 지적에 따라 변환기 프로필 `playCue.hit`도 같은 값으로 맞춰 다시 빌드해도 같은 cue가 나온다(생성값 = 배포값). end 2.9 s.

### 모듈·어댑터·호스트

- `batter3d.js`: `SWING_KINDS`에 hit, `FADE_BACK_HIT = 0` — hit 끝 자세는 타자가 틀 밖(골반 −134 cm)이라 대기로 '섞으면' 틀을 가로질러 미끄러져 돌아오므로 컷. 단 **k ≥ 0.65(골반 이동 시작 전후)일 때만** 컷이고, 그 전에 끊기면(다음 투구) 아직 틀 안의 타격 자세라 다른 클립처럼 0.35 s 섞는다(독립 검토 반영).
- `batter3d-host.js`: `resolvePlay` 선택 항목 hit(take와 같이 glb와 안 맞으면 hit만 뺌), `swing("hit")`은 메타에 hit가 있으면 hit, 없으면 contact. 돌려주는 객체에 실제로 고른 항목 `kind`를 넣는다(호스트의 투명 처리는 클립 이름이 아니라 이 값으로 판단; 독립 검토 반영). 마네킹(batter-indexed)은 메타에 hit가 없어 전과 같다.
- `relay.js`(v1·v2 공용): `swingKind` = miss / (inplay ∧ `BADGE_OF[actual.event] === "hit"` → hit) / contact. hit일 때만 진행률 0.86~1(약 마지막 0.3 s)에 3D 상자 투명도 1→0(`b3Opacity`), 끝나면 `reset` + 0.35 s 전환으로 대기 자세가 나타난다 — 끝 자세→대기 컷에서 상자 가장자리에 남은 다리가 튀어 보이는 것을 가림(첫 중계 캡처에서 확인). `cancelAnim`은 투명도를 즉시 1로 되돌린 뒤 reset(연출 도중 다음 투구). SVG 타자·판정·자막·공 연출은 그대로.
- `demo.html` 종류 선택에 hit(연출 기준 시점 추정 가능; take만 제외).

### 측정(앱 안 Chromium, 폰 375×812 에뮬레이션)

| 항목 | 결과 |
|---|---|
| v2 홈런(11번째 공, Tatis Jr. 우타, 83.4 mph → 비행 702 ms, 전체 2,158 ms) | 0.8 s 타격 준비 → 1.4 s 접촉 자세 → 1.75 s(k 0.86) 달리기 시작 → 1.9 s(k 0.91) 투명도 0.88, 몸이 왼쪽(존 쪽) 가장자리로 → 2.45 s 대기 반복 복귀(투명도 0.98→1) |
| v2 단타(93번째 공, Merrill 좌타 거울, 91.8 mph → 비행 618 ms) | 1.1 s(k 0.67) 오른쪽(존 쪽)으로 달림 → 1.5 s(k 0.80) → 2.46 s 대기 복귀, 투명도 1 |
| 아웃 인플레이(10번째 공, field_out) | contact 그대로(회귀 없음, 같은 세션에서 11번째로 넘어가기 전 재생) |
| 연출 도중 다음 투구(검토 반영 뒤) | k 0.61(타격 직후, 틀 안)에서 끊음 → 0.35 s 섞기(blending true, 컷 아님); k 0.96(달려 나가는 중, 투명도 0.41)에서 끊음 → 즉시 컷(idle 가중치 1)·투명도 즉시 1 → 2.5 s 뒤 대기 반복·투명도 1 |
| 단일 파일 데모 재생성 | v1 7,801,541 B, SHA `02507d06`, v2 7,789,150 B, SHA `f8a9d4e7` — 서버 복사본(demo-test, git 무시)으로 열어 클립 6·play.hit·홈런 재생 확인 |
| 폰 화면 확인(이 단위와 별개, 13시) | 단일 파일 데모를 375 px 에뮬레이션과 headless Chrome(file:// 포함)으로 열어 3D 타자까지 표시됨 — 팀원 폰에서 안 보인 것은 파일을 여는 뷰어(JS 미실행) 문제로 판단(아래 참고) |

캡처 `captures-20261109/hit-v2-R-*.png`(우타 홈런 0.8~2.4 s), `hit-v2-L-*.jpg`(좌타 단타), `hit-demo-k050-contact.jpg`(데모 접촉 자세), `v2-demo-palette-sheet.png`(색 변형 비교).

### 독립 검토(다른 세션 에이전트 읽기 검토; GPT 검토 대체 아님)

1차: 다른 세션 에이전트(일반 목적, 읽기 전용) 1명 — 지적 3건(모두 경미) 전부 반영. (1) 변환기 메타의 클립별 `source.note`가 take 문구로 고정돼 hit에도 "Baseball Step Out … play.take"가 붙음 → 항목별 `retargeted`·길이·이름으로 템플릿화, 작업본 메타의 hit·take note 수정(런타임엔 읽지 않는 값). (2) 모듈 `reset()`이 hit 뒤엔 진행률과 무관하게 컷 → 타격 직후(틀 안, k < 0.65) 끊기면 다른 클립처럼 0.35 s 섞고, 달려 나간 뒤(k ≥ 0.65)만 컷. 측정: k 0.61 끊음 → 섞기, k 0.96 끊음 → 컷. (3) 호스트의 투명 처리가 클립 이름(`sw.clip === "hit"`)에 묶여 메타의 clip 이름이 다르면 조용히 빠짐 → 어댑터가 실제 고른 항목 `kind`를 돌려주고 호스트는 `sw.kind === "hit"`로 판단. 질문 7개는 모두 "문제 없음"으로 확인(actual null 안전, detach 뒤 상자 재사용 없음, cancelAnim 순서, 거울·먼 골반 위치에 의존하는 코드 없음(바닥 그림자 원반은 원점 고정), 0초 섞기의 NaN 없음·idle 처음부터, 마네킹은 contact 대체, demo take 비교만). 미검증: 실제 렌더 결과(검토자는 브라우저 미실행).
2차(1차 반영 뒤): Workflow 7 에이전트(관점 3: 호스트·모듈/어댑터·도구/자료 × 지적마다 반박 1, 같은 모델, 87만 토큰, 14분) — 지적 4건 중 확정 3(모두 경미)·기각 1(중복). 확정과 반영: (1) `relay.js` 20행 `V2 = !!document…`가 IIFE 맨 위에서 document를 읽어 node `require('./relay.js')` 스모크가 ReferenceError(11/9 오전 v2 단위에서 들어온 줄; 브라우저 영향 없음) → `typeof document !== "undefined" &&` 가드, 스모크 통과(export 26개). (2) 손으로 합친 메타의 `clips.hit`에 contactTime/contactFrac/contactBy가 null인데 `play.hit.cueSource`는 데모 측정이라 함(데모의 '연출 기준 시점으로' 단추가 0.5로 떨어짐) → 데모가 쓰는 대로 contactFrac 0.497917·contactTime 1.443958·batTipSpeed·note 채우고 cue도 반올림 전 값 1.443958로. (3) 변환기 프로필 `playCue.hit 1.7`(임시값)이 배포 메타 1.444와 달라 다시 빌드하면 조용히 되돌아감(호스트는 cue < end만 검사) → 프로필을 1.443958로(생성값 = 배포값). 기각 1: (2)와 같은 내용의 중복 지적. 관점별 확인: 262구 전부 animPlan+BADGE_OF로 돌려 hit 16·contact 76·miss 33, actual.event는 타석 마지막 공에만 있고 pas[].event와 0건 불일치; 투명 처리는 비행 560~900 ms에서 클립 2.57~2.62 s부터 282~330 ms; 0초 섞기 NaN 없음·stop() 뒤 원래 자세 복원 왕복; 번들러 치환 전부 유효·glb와 메타 SHA/클립 6개 일치. 두 차례 모두 같은 모델 계열이라 GPT(다른 모델) 검토를 대체하지 않는다.

### 한계·미측정

- 안타 종류(단타·2루타·홈런)에 관계없이 같은 '치고 달려 나가기' 한 클립이다(홈런 트롯 없음). 실책 출루·희생타·내야 안타성 아웃은 contact 그대로(자료의 event 기준).
- 좌타자는 거울 반전이라 화면 오른쪽(존 쪽)으로 달려 나간다 — 실제 1루 방향(투수 시점 왼쪽)과 반대다. 작은 틀 안에서 '달려 나감'만 읽히도록 둔 연출이며, 정확한 주루 방향은 별도 클립·비반전 처리 없이는 못 만든다(사용자 판단 대기).
- 끝에서 상자 투명도로 가리므로 상자 밖까지 완주하는 그림은 아니다(클립 2.9 s에 골반 −134 cm, 틀 폭의 약 절반을 넘는 지점).
- 헤드리스 Chrome의 iframe 래퍼 캡처에선 단일 파일 데모의 3D가 붙지 않았다(직접 열기에선 붙음; 원인 미확인) → 폰 크기 캡처는 앱 안 에뮬레이션 화면으로 대신했다.
- 실기기·Safari 미측정. 커밋·push·배포 없음.

### 참고: 단일 파일 데모를 폰에서 열 때(13시 질문)

페이지 자체는 폰 크기에서 동작한다(위 측정). 메신저에서 받은 .html을 폰이 '미리보기'(iOS 파일 앱 Quick Look, Android 'HTML 뷰어' 등)로 열면 자바스크립트가 돌지 않아 빈 틀만 보인다. Android는 Chrome 주소창에 `chrome://downloads`를 열어 파일을 누르면(file://) 동작하고, iPhone은 Safari가 로컬 html을 열지 못해 JS를 지원하는 뷰어 앱이 필요하다. 확실한 방법은 http(s)로 서빙해서 여는 것(같은 Wi-Fi의 PC 로컬 서버, 또는 비공개 호스팅) — 3D 모델이 들어 있어 공개 호스팅은 하지 않는다.


## 세 버전 동시 비교 GIF — v0·v1·v2 (2026-11-09 15:xx)

사용자 요청: "그냥 우리가 세 버전 한꺼번에 보이는 gif 만들어 보여주자" (폰에서 html 데모가 안 열리는 문제의 대안 — GIF는 메신저가 바로 재생한다).

### 만든 것

| 파일 | 크기 | SHA-256 앞 8 | 내용 |
|---|---|---|---|
| `captures-20261109/pitcheezy-v0-v1-v2.gif` | 3,284,158 B | `4d6ce62e` | v0(Song 배포본) · v1 · v2(Song 색) 세 폰 화면 나란히, 1076×860, 12 fps, 16.6 s, 201 프레임 |
| `captures-20261109/pitcheezy-v0-v1-v2.mp4` | 500,064 B | `bd6d3f73` | 같은 내용 H.264(용량 1/6, 메신저 영상으로 보낼 때) |
| `captures-20261109/pitcheezy-v0-v1-v2pz.gif` | 3,266,753 B | `185343bd` | v2를 Pitcheezy 색(`?palette=pz`)으로 바꾼 변형 |
| `captures-20261109/pitcheezy-v0-v1-v2pz.mp4` | 501,159 B | `7d8a43bd` | 위의 mp4 |

같은 파일을 `D:/pitcheezy_assets/build/demo/`에도 복사했다. 세 화면 모두 **같은 경기(849843) 같은 네 공**을 같은 시각에 넘긴다: 1회 초 Michael Busch 1구 볼(안 치는 공 → v1·v2는 take) → 2구 헛스윙(miss) → 3구 타구 아웃(contact) → 1회 말 Fernando Tatis Jr. 1구 홈런(hit, 치고 달려 나감). 투구 전환 시각 0.6 / 4.6 / 8.6 / 12.6 s, 끝 16.6 s. 아래 자막은 자료의 이닝·타자·구 번호·결과 문구만 쓴다.

### 방법(스크립트 `tools/gif3/`, 원본은 세션 scratchpad `gif3/`)

- **v0 = Song 고정 빌드를 로컬에서 띄운 것**. `D:/pitcheezy_exhibit_check/scope2-c47fe6cb-20261101/frontend/`(c47fe6cb 빌드, `VITE_PUBLISH_BASE="."`) + `upload-put-plans/v1/`(c47 자료 6파일; `game/849843.json`은 relay `data/849843.json`과 SHA `056fcf13` 동일)를 한 폴더에 모아 `python -m http.server 8798`(launch.json `v0-song-static`, 폴더는 scratchpad `gif3/v0site`)로 서빙, 주소 `/?game=849843`. 배포 서버·접속 코드는 건드리지 않았다. 종료 경기 화면은 1구에서 시작하며, 타석 목록의 투구를 누르면 아래 시트가 열리고 시트의 ‹ ›(이전 공·다음 공)가 타석 경계를 넘어 한 공씩 이동한다. 시트를 닫아도 본 화면은 고른 공을 유지한다. 녹화 때는 "눌린 줄 클릭 → › → 닫기"를 React 동기 갱신(마이크로태스크) 사이에 몰아 넣어 시트가 한 프레임도 그려지지 않게 했다(v0 프레임 5장 = 처음 1 + 전환 4, 깜빡임 0).
- **v1·v2 = 단일 파일 데모**(`batter3d/assets/demo-test/pitcheezy-relay-v{1,2}-demo.html`, 11/9 14시 빌드, hit 포함)를 `.prow[data-index=N]` 클릭(`selectPitch(N, {scroll:false})`)으로 넘김. 준비 상태는 `PZRelay.state3D().attached && idleLoop`, 7번째 공(idx 7)을 먼저 골라 4.2 s 기다린 뒤 녹화.
- **녹화기 `capture-cdp.mjs`**(Node 24, npm 의존 0): 헤드리스 Chrome(`--headless=new --use-angle=swiftshader --enable-unsafe-swiftshader`)을 원격 디버깅 포트로 띄우고 CDP로 `Emulation.setDeviceMetricsOverride`(375×812, dpr 2, mobile) → `Page.startScreencast`(JPEG 85)로 프레임을 받아 수신 시각과 함께 저장, 계획된 시각에 `Runtime.evaluate`로 투구 전환. 실측: v1 604 프레임·v2 725 프레임(약 36~44 fps), 전환 시각 오차 ≤ 15 ms. 이전의 `--screenshot` 방식(최소 창 폭 문제)과 iframe 래퍼(3D 미로딩) 문제를 피한다.
- **합성 `compose.py`**(Pillow): 12 fps 격자 시각마다 각 버전의 "그 시각 이하 마지막 프레임"을 골라 폰 3장(각 340×736)을 나란히 놓고, 위 라벨·아래 자막(투구 전환 시각 기준)·우하단 "n.n s · 로컬 데모 녹화"를 붙여 PNG 열 → ffmpeg 8.0 `palettegen(max_colors 160, stats_mode diff) + paletteuse(bayer 3, diff_mode rectangle)`로 GIF, libx264 crf 22로 mp4.

### 확인(합성 프레임 직접 봄)

| 시각 | v0 | v1·v2 |
|---|---|---|
| 1.9 s | Busch 1구 볼, 좌타 실루엣 왼쪽 | 공 도착 뒤 한 발 물러나는 take |
| 5.6 s | 2구 헛스윙 | 헛스윙 팔로스루 |
| 9.5 s | 3구 1루수 땅볼 아웃 | contact 팔로스루 |
| 14.4 s | Tatis 1구 중견수 방면 홈런, 우타 실루엣 오른쪽 | 치고 달려 나가는 hit(v1은 상자 오른쪽 가장자리, v2는 존 옆) |
| 16.6 s | 그대로 | 대기 자세 복귀 |

### 한계·주의

- v0는 Song 빌드의 **로컬 사본**(같은 commit·같은 자료)이지 배포 서버 화면 녹화가 아니다(접속 코드 뒤 화면을 자동으로 열지 않기 위해). 글꼴·배치는 같은 빌드라 같지만 Worker가 끼우는 요소(사용 위젯 등)는 없다.
- v0에는 투구 애니메이션이 없어 v0 칸은 공이 바뀔 때만 바뀐다(실제 v0 동작 그대로).
- 헤드리스 SwiftShader(소프트웨어 GL) 렌더링이라 실기기보다 매끄러움·그림자 품질이 다를 수 있다. 실기기 미측정.
- GIF는 160색 팔레트라 3D 음영에 약한 밴딩이 있다. 원본 품질이 필요하면 mp4.
- GIF·mp4에는 외부 구매 모델의 렌더 이미지가 들어 있다. 팀 내부(Song) 공유용이며 공개 게시 여부는 사용자 결정.
- 서버 `v0-song-static`(8798)은 launch.json에 추가됨. 폴더가 세션 scratchpad라 세션이 끝나면 다시 만들어야 한다(`tools/gif3/README` 참고 없음 — 이 절이 설명).

## v2-tabs(처음 이름 v3) — v2 + Pitcheezy 색 기본 + 토글을 v0 탭 양식으로 (2026-11-09 15:3x~17:xx)

> 이름 변경(17:xx): 사용자가 "V3 = Song 배포 화면 그대로 + 색 + 캐릭터"라고 정의해 이 절의 결과물은 `v2-tabs.html`·`relay-v2-tabs.css`·데모 `pitcheezy-relay-v2t-demo.html`·그림 `v2tabs-*.{png,jpg}`로 이름만 바꿨다(내용 동일). 아래 본문의 v3.html·relay-v3.css는 그 옛 이름이다.

사용자 요청: "v2에 토글 스위치를 v0 버전과 똑같이 맞춘 V3 만들어봐, 색깔 반영한". 확인 질문엔 답이 없어("이어서 ㄱㄱ") 다음 해석으로 진행했다: v2의 세 조작(자동 진행·투구 애니메이션·색 선택)의 **모양을 v0에 맞추고** Pitcheezy 색을 기본으로 켠다.

### v0에서 '토글'로 볼 수 있는 것

Song 고정 빌드(c47fe6cb) 번들을 읽은 결과, 공개 화면에 켜고 끄는 스위치(`role=switch`·checkbox)는 없다. 토글처럼 쓰이는 것은 **선수 시트의 '타자 | 투수' 탭(`.sv-tabs`)** 하나(하단 4칸 탭 바는 화면 전환). 번들 CSS에는 알약 분할 버튼(`.chart-tabs`)도 있지만 공개 화면 JS에서 그리지 않는 죽은 규칙이라 기본으로 쓰지 않았다(`?toggle=pill` 대안으로만).

측정값(라이브 계산 스타일 + CSS): 묶음 아래 1px 선(`--sv-line` #dce5e8), 칸 min-height 46px, padding 0 16px, 글자 16px 700, 안 고른 칸 `--sv-muted` #60727a, 고른 칸 잉크 #192e38 + 아래 3px 밑줄(잉크).

### 만든 것

- `v3.html`(14,989 B, SHA `dca541d6`): v2.html과 같은 틀. 머리 스크립트가 `data-palette="pz"` 기본(`?palette=song`이면 Song 색, `?toggle=pill`이면 알약 대안). 카드 아래 `.controls.settings` 한 장에 세 줄(자동 진행 / 투구 애니메이션 / 색). `#auto-switch`·`#anim-switch`는 v1·v2와 같은 `role=switch` 버튼이라 **relay.js 변경 0**. 색 선택은 `role=radiogroup` 버튼 둘(Song 색 | Pitcheezy 색, 화살표 키·roving tabindex, 저장 안 함). 인라인 스크립트 하나 더: 탭 모양이라 **이미 고른 칸을 다시 누르면 아무 일도 없어야** 하므로 문서 캡처 단계에서 '고른 쪽 절반' 클릭만 삼킨다(키보드 Space/Enter는 그대로 뒤집힘).
- `relay-v3.css`(6,906 B, SHA `916a6d94`): relay-v2.css 뒤에 읽는 덮어쓰기만. `.switch.seg2`는 `::before`/`::after`를 '꺼짐'·'켜짐' 칸으로 그리고 `.knob`은 숨김. 탭은 줄 바닥에 붙여 3px 밑줄이 줄 구분선 바로 위에 놓인다(v0처럼 선 하나). 줄 56px(Song `.sv-pa-item`/`.sv-cand` 값). pz 팔레트에선 밑줄만 진녹 #2f6b12. Song 틀 요소(`.stage`·헤더·하단 탭) 규칙은 0건.
- 단일 파일 데모 `D:/pitcheezy_assets/build/demo/pitcheezy-relay-v3-demo.html`(7,799,302 B, SHA `34bdd53f`; `tools/bundle-demo.mjs`에 v3 추가 — 스타일시트 둘을 차례로 인라인). 외부 구매 모델 포함 → 비공개 전달만.
- 그림 `captures-20261109/v3-sheet.png`(폰 화면 2장 + v0 탭·v3 토글 확대 비교), `v3-phone-top.jpg`, `v3-phone-controls.jpg`, `v0-player-sheet-tabs-zoom.png`, `v3-controls-zoom.png`.

### 확인

앱 안 Chromium 375px·320px: 넘침 0, 3D 연결, 색 전환(Song/Pitcheezy) 동작, 스위치 — 고른 칸 클릭 → 상태 유지, 반대 칸 클릭 → 뒤집힘, 키보드(detail 0) → 뒤집힘. 탭 묶음 바닥과 줄 바닥 간격 4px, 묶음 자체 선 0px. 단일 파일 데모: 스타일 2개·팔레트 pz·클립 6.

### 검토(같은 모델 Workflow, 에이전트 48 = 관점 3 + 지적 15건 × 반박 3, 362만 토큰, 16분)

확정 7(P2 1·P3 6) 전부 반영, 기각 8. 확정: (1) **P2** 탭 두 칸으로 그린 `role=switch` 하나라 고른 칸을 눌러도 뒤집힘 → 캡처 리스너로 고른 쪽 절반 클릭 무시; (2) 알약 대안 고른 칸 글자색은 Song `.chart-tabs`가 읽는 `--teal` #17695b(`--sv-teal` #06776f 아님) → 수정; (3) 탭 묶음 선 + 줄 구분선이 6px 간격으로 두 줄 → 묶음 선 제거·탭을 줄 바닥에; (4) reduced-motion 규칙이 알약 가상요소 전환에 특이도로 짐 → `!important`; (5)(6) 줄 높이 주석(48/56/실제 59)이 서로 달랐음 → 56px로 맞추고 주석 수정; (7) 머리선 색이 v0 값이라는 주석 과장 → 사실대로(v2 제안 값 `--s-line` #cfdadf). 기각 8은 pz 밑줄 색·상태 글 중복·번들러 주석 표현·theme-color 등. 같은 모델 계열이라 GPT 검토를 대신하지 않는다.

### 한계·결정 대기

- "v0 토글"이 하단 4칸 탭 바(추천·선수·구종·기록)를 뜻한 것이면 다른 작업이다(v3의 하단 탭은 v2 그대로 중계·라인업·기록). 스위치를 카드 위쪽으로 옮기는 것도 안 했다(v0 틀 유지).
- v1/v2/v3 중 무엇을 Song에게 보여줄지, 공개 후보에 v3 토글을 넣을지는 사용자 결정(공개 후보는 v2 기준으로 만들었다).


## v0 스냅샷·공개 후보 v2(Pitcheezy 색)·접속 코드 판단 (2026-11-09 16:xx~17:xx)

사용자 요청: "현재 배포된 버전 v0 저장해서 기록하고, 공개 배포 버전 v2 pitcheezy 색깔로 바꾸자, 접속 코드 안 써도 되지 않나 판단해 봐". 배포·설정 변경은 하지 않았다(승인·로그인 필요). 상세는 저장소 문서 `docs/EXHIBIT_V0_SNAPSHOT_20261109.md`, `docs/EXHIBIT_V2_PUBLIC_PLAN_20261109.md`.

- **v0 스냅샷**: `D:/pitcheezy_exhibit_check/v0-snapshot-20261109/`(Song 정적 4 + 자료 6 + 11/1 release.zip·영수증 + 화면 12장, SNAPSHOT.json에 SHA-256). 배포본과 같다는 근거는 11/2 단계5 검사(정적4·자료6 바이트 일치)와 그 뒤 재배포 기록 없음; 적용 버전 `5999cf0d…`.
- **공개 후보**(`tools/build-public.mjs`, 이번 추가): v2.html → index.html(Pitcheezy 색 기본, 홈 링크 pitcheezy.com, noindex 유지), relay.js(로딩 실패 문구의 로컬 주소만 교체), CSS, 3D 모듈·vendor·모델, 자료 JSON(버킷 파일과 SHA 동일). A 사람형 `v2pz-candidate-20261109/public/v2/` 13파일 6,391,224 B, B 마네킹 `…-mannequin/` 5,898,712 B. 로컬 8799에서 13요청 200·오류 0·3D·pz 확인. 첫 빌드의 두 실수(robots 검사 치환이 무변경 예외, 머리 스크립트에 줄 주석을 넣어 `} catch` 가 주석 처리됨 → 블록 주석)는 검증에서 잡아 고쳤다.
- **배치 권장**: (가) `/v2/` 덧붙이기(Worker 코드·설정 변경 0, Song 루트 화면 유지) → Song 동의 뒤 (나) 루트 교체. 사람형 모델 선택(A/B)은 사용자 결정.
- **접속 코드 판단**: 기록상 코드는 "공개 승인 전 자물쇠"(11/21 OFF 예정). 끄면 자료 노출은 Song 합의 범위(6파일)뿐, D1 쓰기는 `/_telemetry`에서만(수집 OFF), 요청량은 v2가 폴링이 없어 방문당 13요청(Song 화면은 시간당 약 480). 기술적으로는 지금 꺼도 되고, 남는 건 Song 동의·11/11 공동시험 전후·모델 선택(A/B) 세 결정. 권장: 코드 ON인 채 `/v2/` 올려 폰 확인 → Song 동의 → 11/11 뒤 OFF(`ACCESS_GATE_ENABLED` 재배포). 전시 전에는 반드시 OFF.

## V3 — Song 배포 화면 그대로 + Pitcheezy 색 테마 + 3D 타자 (2026-11-09 17:xx~18:xx)

사용자 정의(17시, 배포 화면 캡처 2장 첨부): "실행 화면에서 펼치기를 한 첫 화면과 자세히를 누르면 나오는 화면이 현재 공개 배포 사이트 버전인데, 여기에 색 테마와 우리 캐릭터만 적용시킨 버전이 V3." → relay 틀이 아니라 **Song 고정 빌드(c47fe6cb) 자체**에 덧입힌다.

### 방법(소스 `tools/songskin/`, 빌드 `tools/build-songskin.mjs`)

- **Song 파일 불변**: `assets/index-X1sSTTQ4.js`·`assets/index-ks_hu7Ji.css`·`favicon.svg`는 v0 스냅샷 바이트 그대로. `index.html`에만 태그 3개(import map → Song 모듈 앞, `pz/pz-theme.css` 링크 → Song CSS 뒤, `pz/pz-batter.js` 모듈)와 `theme-color` 한 값(#f5f7f8 → #091811)을 넣는다.
- **색 테마 `pz-theme.css`**(3.8 KB): Song이 토큰(`--sv-*`)을 읽는 곳은 토큰만 바꾼다 — `.sv-page.sv-game`, `:root`, 그리고 Song이 시트 안에서 토큰을 다시 정의하는 `.sv-sheet.frame-c` 세 곳. 값은 relay-v2 'pz' 색 변형과 같다(헤더 #091811, 강조 #2f6b12, 1순위 라임 #ceff78 + 짙은 글자, 2순위 #e7f8c6, 타격 #ffb782 + 짙은 글자, 종이 #eef3e8, 잉크 #0f2217). 리터럴 색을 쓰는 Song 규칙(1순위 네모 `.sv-rk.r1`, 타격 원 `.sv-g1.inplay`, 존 안 번호 fill, 헤더 '경기 종료' 칩 #5fd0bd, 존 격자, 선택 행 배경 #eaf3ef 등)은 **같은 선택자**로 뒤에서 덮어쓴다. 기하는 한 줄도 바꾸지 않는다.
- **3D 타자 `pz-batter.js`**(9.5 KB, ES 모듈, batter3d 모듈·three r187 vendor를 `pz/batter3d/`에 복사): Song React가 그린 DOM을 MutationObserver로 보고, 경기 화면의 존 행(`.sv-zrow`)이 나타나면 상자 `.pz-bat3d`(140×210px, 띠 바깥 22px — v2의 `.zone-row.has3d .batband`와 같은 틀)를 넣고 `createBatter3D`로 띄운다. 실루엣 svg는 CSS(`.pz-has3d`)와 인라인 style 둘로 숨긴다(React가 `.sv-zrow` className을 통째로 다시 써서 우리 클래스가 지워지는 일이 있어 틱마다 되살림; 처음 빌드에서 우타자로 바뀐 뒤 실루엣이 비쳐 보였던 것을 고침). 타석 방향은 `bat-l`/`bat-r` 클래스. **반응 재생은 '실제 투구' 줄(`.sv-actual-line`) 글이 바뀔 때**: 표식 원 분류(ball/strike/inplay) + 결과 낱말로 take(볼·루킹·몸에 맞는 공) / miss(헛스윙) / contact(파울·파울팁·아웃·실책) / hit(안타·2루타·3루타·홈런)을 고른다. Song 화면엔 공 비행이 없으므로 와인드업 520 ms 뒤 접촉(상대 호스트와 같은 cue/end 규칙, take는 +250 ms, hit 끝 0.3 s 투명). 존 행이 사라지면(목록 화면) 해제, 로딩·WebGL 실패 시 실루엣 그대로(최대 3회 시도). 감속 모션이면 정지 자세. 검증용 `window.PZSongSkin.status()`.
- **출력** `D:/pitcheezy_exhibit_check/v3-songskin-20261109/`: `public/`(배포용 14파일 5,995,100 B = Song 4 + pz/ 10, glb 3.2 MB 포함), `local-serve/`(public + `v1/` 자료 6; launch `v3-songskin` 8800), `MANIFEST.json`. `--model batter-indexed`로 마네킹 판도 만들 수 있다.

### 확인

- 앱 안 Chromium 375px(8800, `/?game=849843`): 콘솔 오류 0, 3D 연결(클립 6), 테마 적용(헤더 rgb(9,24,17), 1순위 라임), 실루엣 숨김, 투구 시트 ‹ ›로 넘길 때 miss/take/hit 재생·좌↔우 전환, 목록 화면 `/`은 테마만 적용되고 3D는 대기(attached false). 320px 넘침 0.
- 브라우저 팬이 숨겨진 상태에서는 rAF가 약 1 Hz라 팬 안 측정값이 튀었고(교훈), 헤드리스 Chrome도 같은 시각에 프레임이 1/10로 떨어져(기계 부하와 무관, 원인 미확인) 녹화기를 **가상 시계 방식**으로 바꿨다(`tools/gif3/capture-cdp.mjs` virtual: 페이지의 rAF·setTimeout·performance.now·Date.now를 바꿔 치고 프레임마다 33.3 ms씩 진행시켜 captureScreenshot — 기계 속도와 무관한 결정적 30 fps). 동작 확인은 그 녹화로 했다(v0·V3 각 499프레임, 전환 시각 오차 0): `captures-20261109/pitcheezy-v0-v3.{gif,mp4}`(v0 | V3 두 칸, 같은 네 공 — 볼 take, 헛스윙 miss, 타구 아웃 contact, 홈런 hit·투명 처리·대기 복귀), 정지 화면 `v3-songskin-game.jpg`·`v3-songskin-detail-sheet.jpg`·`v3-songskin-list.jpg`·`v3-songskin-sheet.png`.
- 검토(같은 모델 Workflow, 관점 3 + 지적마다 반박 3): 확정 16건 전부 반영, 기각 5건. 확정: P2 pz-batter.js:48 Singles never trigger the hit clip: Song labels a single "1루타", which the hit regex does not match; P2 pz-batter.js:134 Hiding the tab mid-reaction cancels the rAF loop without reset(), leaving the batter frozen in a mid-swing pose; P3 pz-batter.js:51 Pitch-change key is the whole actual-line text, so toggling the speed unit or the arrival of the "정정됨" tag replays the reaction for the same pitch; P3 pz-batter.js:119 A 3D batter is mounted even when Song intentionally renders no batter (unknown side: .sv-zrow has bat-r but no .sv-batband); P3 pz-batter.js:95 When the row is replaced while the glb is loading, mount() gives up without scheduling a retry, so the batter does not appear until some unrelated DOM mutation; P3 pz-batter.js:99 WebGL context loss triggers unmount → immediate remount with no cap, so a GPU that keeps dropping contexts re-downloads/re-parses the glb in a loop; P3 pz-theme.css:40 Fallback silhouette keeps Song's literal blue-grey stroke (#9fb0b7) on the new green fill; P2 pz-theme.css:26 Rank-1 colour split: chip is lime but the zone box, lift label and legend swatch stay dark green; P3 pz-theme.css:26 r1 chip border set to lime: edge against white is 1.15:1, reference keeps the green border; P3 pz-theme.css:35 Selected pitch row keeps Song's mint #f0f7f5; the override targets a class this bundle never emits; P3 pz-theme.css:37 Section headings '추천' / '이번 타석 · N구 던짐' keep Song's blue-grey #4f5f66; P3 pz-theme.css:16 Silhouette stroke stays blue-grey #9fb0b7 while its fill becomes green-grey; --sv-figure-line token is never read; P3 pz-theme.css:28 Zone in-play dot becomes a pale orange disc with an invisible white stroke (edge 1.7:1); P3 pz-theme.css:37 Remaining Song cool-grey literals in header strip, sheet and backdrop not recoloured; P3 pz-theme.css:2 머리말의 색 설명이 relay-v2.css pz 변형과 어긋남: '종이 #eef3e8'은 배경색이고, --sv-chip-line·--sv-past는 pz 변형에 없는 새 값; P3 pz-theme.css:40 3D 실패 시 남는 실루엣의 stroke가 Song 리터럴 #9fb0b7(청회색)로 남아 새 채움색 #c9d6c2(녹회색)와 어긋남. 기각(제목): three.js vendor graph (~2.2 MB) is fetched and evaluated on every page; Status popover for the 'fixed' tone keeps a teal dot (#1f9e8b) and blu; Fixed 140x210 batter box overflows the 174px zone row on short viewpor; batter-ctl 빌드의 MANIFEST 표기 1건; 출력 폴더가 --song 스냅샷 폴더와 같으면 rmSync가 Song 스냅샷 public/을 먼저 지운다. 같은 모델 계열이라 GPT 검토를 대신하지 않는다.

### 한계·주의

- Song 화면의 공개 경로 `/?game=`는 그대로이고, 우리 파일은 `./pz/` 상대 경로(Song 자산 `./assets/`와 같은 방식)다. 하위 경로 라우트(`/game/849843`)에서는 Song 자산도 우리 자산도 같은 이유로 못 찾는다(배포 시 Worker의 SPA 처리에 의존).
- 반응 종류는 Song이 화면에 쓴 결과 글을 읽어 정한다(자료 접근 없음). 글이 바뀌면(예: 새 결과 표현) take/contact로 떨어진다.
- 사람형 모델 glb가 `pz/`에 들어 있다 → 모델 선택은 사용자 결정(마네킹 판 대안). GPT(다른 모델) 검토 전.


## V4 — v2 연출 + V3 머리·아래 메뉴·시트 + 라인업 + 유니폼 팀 색 + 나가기 동작 (2026-11-09 21:xx~23:xx, 로컬 시안, 미배포·미커밋)

사용자 요청(11/9 21시, V3 시트 캡처 3장 첨부): "내가 원하는 조합과 유니폼 색 추가해서 v4 만들자. v4에 현재 공개 버전인 v3의 (이미지 포함) 아래 하단의 추천·선수·구종·기록 메뉴는 그대로 들고 가자. 라인업도 추가해서 V4 로컬로 보여줘." 앞선 대화의 '원하는 조합' = v2의 공 비행·결과 자막·다음 구 버튼 + V3처럼 위에 몇 회·몇 점 + 투구 애니메이션·자동 진행 스위치는 맨 아래. 유니폼: "팀 테마 색상에 맞춰서 … 너무 완전 빨갛고 파랗고 말고 자연스럽게". 작업 중 추가(Mixamo `Fast_Run_1`·`Left_Strafe_Walking`·`Right_Strafe_Walking` 첨부): "출루 상황일 때 스윙 후에 타자가 Fast Run을 하고, 아웃 상황에선 좌타·우타가 상황에 맞게 strafe walking을 스윙이나 스트라이크 몸동작 후에 했으면 … V4에 추가".

| 파일 | 무엇 |
|---|---|
| `v4.html` | v2.html을 바탕으로 새로 씀. 머리(뒤로·점수 / 이닝·볼카운트·주자 버튼 + 작은 이닝별 점수 버튼), 추천 화면(존·범례·추천 칸·자세히·‹ ›·실제 투구 한 줄·이번 타석 접기), 라인업 화면, 고정 스위치 줄, 아래 메뉴 5칸(추천·선수·구종·기록·라인업), 시트 자리. Pitcheezy 색 고정(`data-palette` 없음, 색 선택 없앰), `data-batter3d-model="batter-ctl-v4"` |
| `relay-v4.css` | relay-v2.css 복사 → pz 색을 기본 토큰으로, 머리·시트(Song frame-c 값: 반 높이 max(50dvh, min(400px, 100dvh−56px)), 머리 52px, 본문 12px 16px 20px)·스위치 줄·5칸 메뉴 추가. 320px 넘침 0 |
| `relay-v4.js` | relay.js 복사본(v1·v2는 relay.js 그대로). 바뀐 곳은 머리말에 정리: 머리 렌더(이 공 던지기 전 값, `linescore_before`), 이닝 탭·기록 화면 제거, 아래 메뉴, 시트 6종, 추천 칸 → 자세히, 실제 투구 한 줄(Song 형식), 자동 진행은 시트가 열려 있으면 멈춤, 유니폼 색, 나가기 동작 |

### 아래 메뉴·시트 — Song 고정 빌드(c47fe6cb) 사양 그대로

사양은 Song 번들(index-X1sSTTQ4.js)을 읽고 V3 로컬(8800)과 대조한 에이전트 4개 결과(스크래치 `v4/spec_detail.md`·`spec_player.md`·`spec_record.md`·`spec_header.md`; 자세히 시트는 262구 전부 실제 화면과 해시 일치 확인). 문구·숫자 형식·순서·반올림·없는 값('—')·강조·누르기 동작을 따랐다.

- **추천**(메뉴): 추천 화면으로(시트 닫힘). Song은 이 메뉴가 자세히 시트를 연다 — v4는 화면이 하나 더 있어(라인업) 화면 전환으로 둠.
- **선수**(시트, 타자 탭부터): 제목 = 고른 탭 선수 이름, "이름 팀 · 좌타/우투", 등번호 `#n`, 시즌 `AVG — · OPS —`/`ERA —`(발행 파일에 경기 전 시즌 기록 없음), "오늘 · 이 공 전" = `context_before`(없으면 '타수 —' 형식), 투수 탭은 "오늘 구종 · N구" 표 + 같은 안내문. 팀 이름 = Song 표(컵스·샌디에이고만 확인값, 그 밖은 영문 마지막 낱말 — Song과 같은 규칙).
- **구종**(시트): 제목 "King 오늘 구종"(Jr. 같은 꼬리는 두 낱말), "받은 기록 중 구종이 확인된 N구 기준 · 고른 공(1회 초 · Alex Bregman · 2구)까지", 표 = 경기 첫 공부터 고른 공까지(포함)·같은 투수·구종 코드별, 많은 순(같으면 먼저 던진 순), 비율 반올림, 평균 구속 = mph 평균 × 1.609344 반올림. 크게 보면 "오늘 던진 위치" 그림(줄임말+번호).
- **기록**(시트): 문자 로그(고른 공까지 시작한 타석, 최근 것부터, 진행 중이면 "타석 진행 중 · n구", 누르면 그 타석 첫 공 + 자세히) · 라인업·박스(발행본 `current.context.lineups/boxscore` 그대로 — 자책은 공개된 플레이로 다시 셀 수 없어 자료 값) · 분석(준비 중). 열 때마다 문자 로그부터.
- **자세히**(추천 칸·'자세히'): 제목 "1회 초 · 1구 · 이름" + ‹ ›(경기 전체 공, 끝에서 비활성, 시트 열린 채 크기·스크롤 유지), 결과 줄, 작은 존(Song 상세 창: 반폭 1.25 ft, 실제 공이 밖이면 넓힘, 미트 점선), 판정·원본 좌표·추적값(없는 값은 "…은/는 이 공 자료에 없어요"), 타석 결과·원본 기록, 추천 표(위치 이름은 Song 규칙: 좌우를 투수 시점으로, '가운데 높이 중앙' → '한가운데'), 추천 없는 공은 사유 문장.
- **타석 선택**(머리 왼쪽): 반 이닝 고르기(기본 = 고른 공의 반 이닝) + 그 반 이닝 모든 타석(최종 결과·투구 수, '보는 중'), 누르면 그 타석 첫 공 + 자세히. '박스스코어' → 이닝별 기록.
- **이닝별 기록**(머리 오른쪽): 고른 공 던지기 전까지 공개된 플레이(`linescore_before`), 아직 안 온 이닝 '–', 지금 반 이닝 칸 강조(공격 팀 cur, 다른 팀 curcol).
- **라인업**(메뉴, 화면): v2 라인업(타순·교체·투수 등판 순) 그대로.
- 시트 공통: 배경 누르기·Esc·닫기로 닫힘, Tab 갇힘(실제로 Tab이 가는 요소만), 닫으면 연 버튼으로 포커스, 손잡이 누르기로 크게/작게, 반 높이에서 본문을 내리면 크게, 손잡이·머리 끌기(위 40px → 크게, 아래 60px → 반/닫기, 8px 넘게 끌면 누르기 무시) — 전부 Song과 같다. 투수 탭·구종은 반 높이 56dvh/420px. 열려 있는 동안 페이지 스크롤 잠금은 html에(머리 sticky 유지).

### 머리·추천 화면 — v4에서 정한 것

- 머리 점수·이닝·볼카운트·주자·작은 이닝별 점수는 **보고 있는 공 던지기 전** 값. Song은 끝난 경기면 최종 점수(1구를 볼 때도 0:8)라 결과가 미리 보인다 — 재생 화면이라 v4는 진행형으로(사용자에게 권한 안, "내가 원하는 조합"으로 승인).
- 추천 제목 "이 공 던지기 전 추천 · N구", 추천 칸은 Song처럼 세 칸 버튼(누르면 자세히, 추천 없으면 '— — —'), 그 옆에 '자세히'와 v2의 ‹ ›. 실제 투구는 Song 한 줄("실제 투구 · 1구 · 이름 / ① 싱커 155km/h · 루킹 스트라이크", 타석이 끝난 공이면 타석 결과 글). 범례 "투수 시점 · 좌타자". 이번 타석은 Song 목록(최근 공부터, 타석이 끝난 공이면 맨 위 결과 줄, 누르면 그 공 + 자세히, 속도 '152km/h'), 접기/펼치기는 기본 **펼침**(사용자가 기준으로 든 화면이 펼친 상태 — Song 기본은 접힘). 머리 이닝 글은 Song 라이브 형식 "5회말 ▾", 작은 이닝별 점수는 지금 이닝 칸(머리·두 팀)을 강조하고 공격 팀 칸 글자는 라임.
- 두 스위치(투구 애니메이션·자동 진행)는 아래 메뉴 바로 위 고정 줄(48px, 추천 화면에서만). 상태 글은 짧게("10초 뒤 다음", "멈춤", "켜짐(자막만)", 두 줄까지), 긴 문장은 보조기기 안내로. 자동 진행은 시트가 열려 있거나 라인업 화면이면 멈춤. 공을 넘겨도 페이지가 스크롤되지 않는다(고정 줄 아래로 숨지 않게).

### 유니폼 팀 색(3D)

- `batter3d.js` `setUniform(spec)`: 사람형 모델의 재질 `M_Clothes`(상의·바지·소매·양말·벨트·신발·장갑이 한 장)·`M_Helmet`에만. 텍스처 실측(밝기: 흰 천 0.85~0.90, 줄무늬 0.75~0.85, 검은 부분 0.10~0.15, 헬멧 0.05~0.10/0.30~0.40)에 맞춰 **원래 명암을 살린 채 색만 옮긴다**(`recolorPixels`): 흰 천 → 바탕색 × 밝기, 줄무늬 → 줄무늬 색 쪽으로, 검은 부분 → 팀 색 × 밝기, 헬멧 전체 → 팀 색. 채도 있는 작은 부분(단추)은 그대로. 같은 색은 캐시, dispose 때 원래 텍스처로 되돌리고 해제. glb 파일은 바꾸지 않는다. 마네킹 모델은 해당 재질이 없어 무동작.
- `relay-v4.js` `uniformFor`: 공격 팀 기준. 홈 = 흰 유니폼(#f3efe7) + 팀 줄무늬, 원정 = 회색 원정 유니폼(#b9bdc0). 팀 색은 채도를 낮춰 소매·양말·벨트·헬멧·줄무늬에만 — SD 짙은 갈색 #3d2d23(줄무늬 #8c7a66), CHC 짙은 남청 #24396b(원색 파랑 #0E3386보다 어둡고 탁하게). 로고·글자 없음(구단 상표). 목록 밖 팀은 중립 남색.
- 3D 모델 관련 확인은 비공개 기록에서 관리한다(색은 파일을 그대로 두고 화면에서만 바꿈).

### 나가기 동작 — 출루 = 달리기, 아웃 = 옆걸음

- 언제: 이 공으로 타석이 끝날 때만(`pas`: complete·last_index·event). 타자가 베이스에 나가는 결과(안타·2루타·3루타·홈런·볼넷·고의4구·몸에 맞는 공·실책 출루·야수 선택·포스 아웃·타격 방해) → 스윙(인플레이면 contact, 기준 시점 뒤 0.85 s까지) 또는 볼넷 반응(take 0.8 s) 뒤 **달리기**. 아웃(삼진·타구 아웃·병살·희생타 등) → 헛스윙(0.9 s)·contact·루킹 삼진 반응 뒤 **옆걸음**. 모델에 나가기 클립이 없으면(?batter3d=batter-ctl 등) 전과 같이 안타는 hit 클립. 나가기가 있으면 안타도 이전의 hit 클립 대신 contact 스윙 뒤 달리기(사용자 "스윙 후에 Fast Run"). 이 경기 71타석 중 출루 23·아웃 48.
- 방향: 달리기는 1루 쪽(투수 시점 화면 왼쪽) — 우타자는 존 쪽으로, 좌타자는 바깥쪽으로. 옆걸음은 타석 바깥쪽 — 우타자 화면 오른쪽, 좌타자 화면 왼쪽. 좌타자는 화면에서 거울로 그려지므로 `Right_Strafe_Walking`을 데이터에서 미리 좌우 거울로 옮겨(`strafe_l`) 원본 오른쪽 옆걸음 모습 그대로 바깥쪽으로 걷게 했다. 우타자는 `Left_Strafe_Walking` 그대로(`strafe_r`).
- 옮기기: `tools/retarget-mixamo.mjs`에 선택 옵션 5개 — `RETARGET_YAW_DEG`(세로축 돌림, 달리기 −90°/+90°), `RETARGET_MIRROR=1`(반대쪽 뼈의 월드 회전 변화량을 x 반사), `RETARGET_LOOPS`, `RETARGET_ROOT_SCALE`(골반 수평 이동 배율), `RETARGET_TIME_SCALE`(시간 늘이기). 값이 잘못되면 중단. **골반 위치 트랙은 부모(Root) 로컬이라 축이 돌아가 있어**(측정: 월드 −x 이동이 로컬 x·y·z에 나뉨) 반복·배율은 월드에서 적용한 뒤 로컬로 옮긴다 — 첫 시도(로컬 x·z만 바꿈)는 두 번째 주기에서 타자가 뒤로 튀었다. 이동 배율만 줄이면 발이 미끄러져(검토: 0.3배에서 디딤발 4 m/s) 시간 늘이기와 섞었다. 결과: 달리기 3주기·시간 × 1.5·이동 × 0.7(몸 ≈2.5 m/s, 미끄러짐 약 30 %), 옆걸음 2주기·× 1.2·× 0.8(≈1.1 m/s, 약 20 %), 뼈 52쌍 빠짐 0.
- 모델: `tools/append-clips.mjs`(새, 의존 없음)로 `batter-ctl.glb`(빌드 5, 불변, SHA `c56571c4`)에 클립 4개를 덧붙인 **`batter-ctl-v4.glb`**(3,450,628 B, SHA `90762a42`; 메타 `play.run_r/run_l/strafe_r/strafe_l` 달리기 end 1.0 s·옆걸음 1.3 s, `output`은 v4 파일, 클립 출처는 클립 JSON 이름·SHA + fbx 따로). 기존 BIN 바이트 일치 확인. 노드 번호는 같은 도구로 옮긴 take 클립 채널에서. 반복·배율은 이 도구에서 받지 않는다(Root 로컬 축 문제 — retarget에서만).
- 모듈·어댑터(공용, v1·v2는 새 옵션을 안 씀): `batter3d.js` EXIT_KINDS·`setSwing(kind, k, {blendIn})`(스윙 끝 자세 → 나가기 0.25 s 섞기)·나가기 중 접지 원이 시작 자리부터 움직인 만큼 골반을 따라감·나가기에서 대기로는 언제나 컷. `batter3d-host.js` `exit(kind, side)`, `swing/react(…, {follow})`, 페이지 기본 모델(`data-batter3d-model`), 모듈 주소에 `?v=4`(캐시에 남은 이전 판과 섞이지 않게; v4.html도 어댑터를 `?v=4`로). 호스트는 나가기 진행률 구간에서 상자를 부드럽게 투명하게(우타 달리기 0.12→0.42 — 존 쪽 틀 가장자리 닿기 전, 좌타 달리기 0.3→0.75, 옆걸음 0.35→0.8)하고, 나가는 동안 상자 안쪽 가장자리에 마스크를 건다. 끝나면 대기 자세가 0.35 s에 나타난다.

### 독립 검토(같은 모델 Workflow; GPT 검토 대체 아님)

관점 4(Song 시트 사양 대조 · 화면 동작 · 3D 모듈·어댑터 · 클립 도구·glb 구조) × 지적마다 반박 3, 에이전트 100. **확정 26건(P2 9·P3 17) 전부 반영**, 기각 6건(그중 5건 — 추천 제목·이닝 칸 강조·없는 값 낱말·비중 우선순위·출루/아웃 표 — 도 Song에 맞춰 같이 고쳤다; 이번 타석 기본 펼침만 의도로 유지). 주요 확정: 자세히 존 기호가 Song의 60 % 크기 · 시트 끌기 없음 · 우타 달리기가 틀 가장자리에서 잘림 · 이동 배율 때문에 발 미끄러짐 · Tab 갇힘 새는 곳 · 시트를 열면 sticky 머리가 밀림 · 360px에서 'CHC' 줄바꿈 · ‹ ›·자동 진행 때 선택 줄이 고정 줄 아래로 · 나가기 도중 끊기면 미끄러져 돌아옴 · 그림자 첫 프레임 튐 · 캐시에 남은 이전 판 모듈 · append-clips의 Root 로컬 축 · 메타 출처·출력 · 보고서 키 수 · 환경 값 검사.

### 확인

- 앱 안 Chromium 375×812·320×640: 시트 6종 문구·숫자가 사양 값과 일치(1구·Bregman 2구·Merrill 5회 말 1구(추천 없음 사유)·Tatis 홈런(미트·추적값 전부)·140구 이닝별 기록 강조·문자 로그 41줄·박스 21+8줄·라인업), 자세히 작은 존 네모 24 px·공 20 px(Song 22·18 + 테두리), 겹침 시 번호 밖으로·순위 글자 위로, 시트 끌기(아래 → 닫힘, 위 → 크게), 시트 열 때 머리 제자리, 콘솔 오류 0, 가로 넘침 0. v2(`v2.html?batter3d=batter-ctl`) 3D·홈런 연출 정상(공용 파일 회귀 없음).
- 가상 시계 녹화(`tools/gif3/capture-cdp.mjs`, 20 fps) 7타석: 우타 헛스윙 삼진·땅볼 아웃 → 오른쪽 옆걸음, 좌타 삼진(헛스윙·루킹) → 왼쪽 옆걸음, 우타 홈런·볼넷 → 왼쪽(1루) 달리기, 좌타 안타 → 왼쪽 달리기, 끝나고 대기 복귀. 캡처 `captures-20261109/v4-*.png`, 데모 `pitcheezy-v4-demo.{gif,mp4}`.
- 단일 파일 데모 `tools/bundle-demo.mjs v4` → `D:/pitcheezy_assets/build/demo/pitcheezy-relay-v4-demo.html`(외부 구매 모델 포함 — 팀 내부만).

### 한계·미측정

- 실기기(iPhone Safari) 미확인. 자세히 존의 겹침 처리는 Song 규칙을 단순화(번호는 위·아래·오른쪽·왼쪽 중 빈 자리, 네모끼리 겹칠 때 글자 옮기기는 없음). → **11/10에 Song dl·Vt·xe 규칙으로 바꿈**(262구 전부 V3와 같음, 아래 11/10 절; 남은 차이 = 미트 글자는 옮기지 않음, 130구 네모 글자 '2'·'1·3' 겹침은 Song이 '2'를 아래로 옮기고 V4는 안에 둠). 이번 타석 기본 펼침은 Song(접힘)과 다르다(의도).
- 달리기·옆걸음은 화면 안에 조금 더 보이게 느리게 했지만 발이 약 20~30 % 미끄러진다. 우타자 달리기는 존 쪽(안쪽) 3D 틀 가장자리에 닿기 전에 흐려져 실제로 보이는 달리기는 0.3 s 남짓이다.
- 유니폼 색은 연출(실제 유니폼 아님, 화면 바닥 안내에 적음). 3D 모델 관련 확인은 비공개 기록.
- 공용 파일(batter3d.js·batter3d-host.js·retarget-mixamo.mjs·bundle-demo.mjs)을 고쳤다(바꾸기 전 백업 `D:/pitcheezy_exhibit_check/backup-v4-20261109/`). 배포된 V3는 자기 복사본을 써서 영향 없음. 미커밋·미배포, GPT(다른 모델) 검토 전.

### 11/10 총점검·재점검(1~6차) — 로컬 시안 `?v=9`, 미배포·미커밋

사용자 요청(11/10, V4 2회초 Suzuki 5구 캡처에 'Field Error'): "필드 에러는 뭐지 다시 총점검 해줘 애니메이션 오류는 없다 잘만들었네". 애니메이션(공 비행·스윙·나가기)은 사용자 승인대로 두고, 결과가 나타나는 때만 다듬었다.

- **Field Error**: Song 발행 파일이 event `field_error`의 `result_label`·`event_label`을 영어 'Field Error'로 남긴다(`result_text`는 '유격수 실책 출루', Song 앱 Vy 표는 '실책 출루'). 이 공은 Suzuki 유격수 땅볼 → Bogaerts 송구 실책으로 출루·2루까지(안타 아님, 타수에 들어감, 실책은 SD). V4는 `EVENT_KO`·`koLabel`·`resultWord`로 한국어 낱말을 쓴다. **V3·v1·v2는 여전히 'Field Error'**(Song 발행기 쪽, 이번 범위 밖).
- 방법: 같은 모델 Workflow — 영역별 점검(각 에이전트가 자기 headless Chrome·CDP, 공유 브라우저 창 안 씀) → 지적마다 반박 검증 → 고치고 다음 차에서 고친 것 + 회귀를 다시 확인. **GPT(다른 모델) 검토 대체 아님.**

| 차 | 에이전트 | 확정(보고 수, 중복 포함) | 고친 것(코드 꼬리표 `11/10 총점검`·`재점검`·`3차`~`5차`) |
|---|---|---|---|
| 1 총점검 | 56 | 약 49(P2 15·P3 34) + 비평 3, 고유 약 20 | 존·이번 타석 목록은 고른 공까지만(뒤 공·결과 미리 보기 없음) · 자막도 '루킹 삼진'·'볼넷' 등 같은 낱말 · 작은 존 화살 px 배율(3px로 잘림)·가장자리 표식 안쪽으로 · 시트 끌기 따라 움직임·연 직후 두 번째 누르기로 닫히지 않게 · 이닝별 점수 R·H·E 오른쪽 고정 · 3D 문맥을 잃으면 다시 붙이기(최대 3번) · 애니메이션 설정 저장을 v1·v2와 분리 · 포커스가 body로 떨어지면 같은 자리로 · Chrome 자동 어둡게 방지·대비 3.3:1·누르는 자리 44px · 320px 3D 타자 작게 · 가로 화면 머리·스위치 줄 고정 안 함 · '초예요'·'말이에요' · 구종 시트 수 차이 설명 · 보이는 글자로 시작하는 읽기 이름(WCAG 2.5.3) |
| 2 재점검 | 30 | 22(P2 1·P3 21) | 공이 닿을 때까지 결과 글 가림 · 방문객 문구(빈 점수 '–', 개발 문자열 빼기) · 자막 테두리 여유 · 시트 포커스(무시한 두 번째 누르기·끌기 직후 클릭·닫은 뒤 'chips'·'row' 표지) · 360~389·375~389·≤359 이닝 표 칸·합계 고정·지금 이닝 숨김 방지 · Tab이 머리 버튼에서 페이지를 끌어올리지 않게 · 좁은 화면 구종 이름 줄바꿈(Song 값) |
| 3 | 27 | 19(P2 4·P3 15), 기각 2 | 결과 색도 닿을 때까지 회색·비행 중 읽기 이름도 결과 없이 · 발 밑 '자료 정보' 접기(개발용 문자열·KST 시각) · 3D 실패 시 3초·8초 뒤 재시도 · 시트 연 직후 두 번째 누르기가 다른 타석으로 가지 않게 · 끝에서 비활성 화살표는 반대쪽으로 · 자세히 존 Song dl(번호 자리)·표식 여백 통일 · 구종 위치 그림 던진 순서·글꼴 12/11px · 행이 보이던 때만 다시 밀기(자동 진행이 페이지를 끌어오지 않게) · 320 이닝 표 팀 칸 고정 |
| 4 | 20 | 15(P2 2·P3 13) ≈ 고유 10, 기각 1 | 자세히 존 Song Vt(순위 글자 들어올림·원래 글자 숨김)·xe(보이는 상자) · 불러오기 실패 화면 빈 점수·'저장 경기' 숨김, 빈·순서 깨진 투구 목록도 실패로 · '보이는 행'은 고정 머리·아래 줄 안쪽만 · 목록을 다시 그리지 않는 재연출에서도 결과 읽기 이름 빼기 · 3D 재시도 예약은 늘 하나 · 포커스 링(summary·뒤로·320 머리·가로 Shift+Tab 6px) · '자료 정보' ▸/▾ |
| 5 | 6 | 2(P3) | 기다리는 3D 재시도(1.5·3·8초)를 앱 전환이 앞당기지 않음(7~10초 끊김 뒤에도 돌아옴) · 가로 화면 `scroll-padding-bottom`에 홈 표시줄 safe-area |
| 6 최종 확인 | 4 | 화면 결함 0 · 위생 1 | 점검기가 남긴 로그 4개(`a3d-*.out`, 로컬 경로 포함, 미추적)를 relay 폴더에서 스크래치(`check1110/stray-from-relay/`)로 옮김 · 낡은 주석 2개(닫은 뒤 포커스, 가로 규칙 꼬리표) — 동작 변화 없음, `?v=9` 유지 |

- **확인 값(측정)**: 자세히 존 262구 × 375·320·414·667에서 V3와 번호 옮김 여부·자리·간격·들어올림(74개/67구)·숨긴 글자·색 일치(4차). 비행 중 읽기 이름 933 스냅샷·144 시험 실패 0(4차). 3D 다시 붙이기 시나리오 19개 + 새 5개(앱 전환 깜빡임 10번·숨김 중 실패·발사 직전 보이기 등) 전부 예약 1개 이하·재시도 3번 이하·회복(6차 점검). 가로 812×375·844×390(safe-area 아래 21 좌우 47)·667×375·568×320·세로 375×812(아래 34)에서 '보이는 행' 65경우·실제 10초 자동 진행·실제 Tab 통과, 이전 CSS로는 실패 재현(A/B). 375×812·320×568 애니메이션 끔·켬 262구 전체·시트 전부 콘솔 오류·경고 0. 하루 전체 diff에서 꼬리표 없는 실수 변경 없음.
- **단일 파일 데모** 재빌드 `D:/pitcheezy_assets/build/demo/pitcheezy-relay-v4-demo.html`(8,188,154 B) + `batter3d/assets/demo-test/` 사본(git 무시): 네트워크 요청 data:·blob:만, 262구·71타석, 3D 붙음, 콘솔 0, 서버 화면과 글자·읽기 이름 일치(제목 꼬리만 다름). **외부 구매 모델 포함 — 팀 내부만.**
- 백업 `D:/pitcheezy_exhibit_check/backup-v4-20261110/`: 루트 = 오늘 전, `after-check1`~`after-check5` = 각 차 고치기 전(5에는 NOTES·CHECKLIST·이전 데모도), `demo-before/` = 11/9 데모. 점검 기록·재현 스크립트는 세션 스크래치 `v4/check1110/`(recheck*.json).
- **남은 한계**: 320에서 3D 타자가 표식 몇 개를 조금 덮음 · 320×568에서 추천 칸이 첫 화면 아래 · 미트 글자는 Song처럼 옮기지 않음 · 130구 네모 글자 겹침(위) · V3·v1·v2 'Field Error' · 달리기·옆걸음 발 미끄러짐(위) · `mixMap`의 `m.sel` 계산은 남았지만 그리지 않음(Song '오늘 던진 위치'도 선택 표시 없음 — 의도).
- **사용자 결정 대기**: 머리 '뒤로(←)'가 갈 곳 · 실기기(iPhone Safari) 확인 · GPT 검토 · 3D 모델 관련 확인(비공개 기록) · 커밋·배포.

### 11/10 공개 배포 — app.pitcheezy.com = V4 (버전 `e28b0617`)

사용자 승인(11/10 채팅 "v4로 배포버전 바꾸자"). 이전 공개는 V3(`c222a454`). 기록 `docs/results/exhibition_20261101/v4-deploy-20261110.json`.

- **빌드** `tools/build-public-v4.mjs <후보 폴더> [--replace]`(새, 배포는 안 함): 공개 13파일 = index.html(v4.html에서 제목 'Pitcheezy 중계'·방문객 설명·뒤로(←)는 `visibility: hidden`·`aria-hidden`·`tabindex -1` 자리만 — 공개 경기가 하나라 갈 곳이 없음) + relay-v4.js(자료 주소만 `./v1/game/849843.json`) + relay-v4.css·batter3d-host.js·batter3d.js·three vendor 5·batter-ctl-v4.glb/meta(원본 바이트) + collection-settings.json(호스트 설정 짝, V3와 같음). 임시 폴더에 만든 뒤 검사 통과 시에만 public/ 교체, git 작업 트리 안 출력 거부, 조립된 후보는 `--replace`일 때만.
- **자료를 /v1에서 읽는 이유**: 처음 후보는 data/849843.json 정적 사본이었는데, 배포 전 점검에서 그러면 호스트 자료 스위치(DATA_READ_ENABLED·삭제 표시)가 화면에 안 먹는다는 지적(V3는 /v1을 읽어 먹었음) → /v1로 바꿈. 바이트는 같다(056fcf13). /v1 응답은 `no-transform`이라 압축 없이 727 kB(V3도 같음).
- **후보** `D:/pitcheezy_exhibit_check/v4-deploy-20261110/C-v4/`(host/ = V3 후보 그대로, 설정 SHA d85b6997…), 배포한 원본 사본 `…/source/`(V4 파일 미커밋이라 보존), 비공개 배포 로그 `deploy-C.private.log`. 검사기 `check_public_host_config` ok(이번 실행에서만 .glb·프런트엔드 선언 Pitcheezy/transition-models 허용).
- **배포 전 점검**(같은 모델 Workflow 9 에이전트, GPT 검토 대체 아님): 로컬 정적 서버·로컬 Worker(`wrangler dev --local`, 계정 접촉 없음)에서 262구×시트 전부 개발 화면과 텍스트·읽기 이름 같음(제목·뒤로만 다름), 375/320/812 콘솔 0, 요청 전부 200, `/?game=849843`도 V4. 지적 반영 2(자료 경로, 빌드 도구 안전). 남긴 것: 깊은 경로(/foo/bar)는 상대 주소라 깨짐(V3와 같음), 느린 망에서 자료(727 kB)가 3D 내려받기와 겹침.
- **배포 뒤 확인**: 공개 파일 라이브 바이트 13/13, `/`·`/?game=849843` = V4 index.html, `/v1/*` 200, 업로드 HEAD 503, 앱 안 Chromium 375×812 실주소에서 262구·3D batter-ctl-v4·'실책 출루'·콘솔 0.
- **되돌리기**: `node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js rollback c222a454-c36d-4406-b411-1f7f06b0d5dc --config D:/pitcheezy_exhibit_check/v4-deploy-20261110/C-v4/host/wrangler.deploy.json --message "back to V3"`.
- 남은 일(사용자): Song 알림, 실기기(iPhone Safari), GPT(다른 모델) 검토, 3D 모델 관련 확인(비공개 기록), V4 원본 커밋.
