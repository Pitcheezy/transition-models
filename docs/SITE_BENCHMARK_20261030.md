# Pitcheezy 관전 서비스 비교 조사

2026-10-30 사용자 요청: 홈의 분위기는 유지하되 나머지 페이지를 실제 관전 서비스로 개선한다.
공식 제품·도움말·현재 공개 페이지를 조사했다. 전 세계 서비스의 전수 목록은 아니며,
기존 야구 데이터 서비스와 AI/영상 분석 제품을 함께 비교했다. 업체 성능 주장을 독립 검증하거나
유료 제품을 직접 사용한 조사가 아니다. 가격은 이번 조사에서 비교하지 않았다.

## 결론

현재 부족한 것은 모델 기능의 수보다 관람자가 한 공의 맥락을 이해하는 동선이다.
홈은 영상·브랜드·짧은 목적이 잘 연결되지만, 내부 화면은 자료 설명과 조작이 길고 분산돼 있다.
`watch`와 `receiver`의 역할이 겹쳐 신규 사용자가 어느 화면에서 시작해야 할지 혼동했다.
이번 SITE-audit1은 동선과 결과 초기화 결함을 고쳤으며, 아래 구성 개선까지 완료한 것은 아니다.

좋은 방향은 **경기 선택 → 한 화면 관전 → 필요할 때 상세 근거**이다.
추천을 만들었다는 사실보다, 같은 공의 영상·당시 추천·실제 결과가 정확하게 연결돼 보이는
경험을 핵심으로 한다. 검증되지 않은 책임 점수·확률·선수 의도는 추가하지 않는다.

## 공식 참고 자료와 확인 범위

| 서비스 | 확인한 기능 / 참고점 | 확인 한계 |
|---|---|---|
| [Baseball Savant Search](https://baseballsavant.mlb.com/statcast_search) | 구종·카운트·이닝·주자·좌우 조건 검색, 위치·구속 열 선택 | 검색 화면 확인, 전체 조건 조합 미실행 |
| [Savant Pitch Arsenal](https://baseballsavant.mlb.com/pitchmix) | 구종 빈도·구속·움직임·리그 평균 | 현재 화면 선택 항목 확인 |
| [Savant Gamefeed](https://baseballsavant.mlb.com/gamefeed) | 경기 선택·지표 범례·구종 분류 수정 가능성 안내 | 동적 차트 조작 미실행 |
| [MLB Gameday 3D](https://www.mlb.com/news/mlb-gameday-3d-guide) | 3D 재구성·시점 전환·다시보기 | 공식 설명, 우리 자료로 구현 가능한 기능이라는 뜻 아님 |
| [MLB Film Room](https://www.mlb.com/video) | 클립 탐색·모음·공유 | [출시 안내](https://www.mlb.com/news/mlb-film-room-launch)는 2020년 기록 |
| [FanGraphs](https://www.fangraphs.com/scores) | 날짜·점수·WE·LI, Box Score / Game Graphs / Game Stats / Play Log | 현재 메뉴 확인; [세부 도움말](https://library.fangraphs.com/features/live-scoreboard/)은 2016년 문서 |
| [Baseball Reference](https://faq.sports-reference.com/portal/en/kb/articles/box-score-tips-and-tricks) | 투구별 기록 펼치기·용어·주자 도식·승리확률 변화 | 공식 도움말 확인; 실제 경기 페이지는 조회403 |
| [BaseballCloud](https://www.seemagnus.com/baseballcloud) | BallR/Analyzr/PitchR, 여러 투구·위치·구종·2D/3D 비교 | 전용 측정 자료/연결 데이터 필요 |
| [WIN SmartPark](https://winreality.com/smartpark/players-fans-coaches/) | 경기 중/뒤 선수·팬·코치 데이터 화면 | [광학 카메라 시스템](https://winreality.com/blog/what-is-optical-pitch-tracking-in-baseball/) 전제 |
| [TrackMan](https://www.trackman.com/baseball/V3-Game-Tracking/what-we-track) | 릴리스·비행·존·타구 분석 | [레이더/광학 장비](https://www.trackman.com/baseball/V3-Game-Tracking/tech-specs) 의존 |
| [Rapsodo](https://rapsodo.com/pages/baseball-frequently-asked-questions-faq) | 영상과 투구/타격 측정, 선수 기록·기간 조회 | PRO 장치·앱·보정 등 전제 |
| [WIN SwingAI](https://winreality.com/quick-start-guide/swing-ai-start-training/) | 원영상·3D·나란히 비교, 설명과 과거 분석 | [촬영 조건](https://winreality.com/quick-start-guide/swing-ai-uploading-swings/) 최소60fps·전신·배트·전체 스윙 |
| [Pelotero](https://support.pelotero.com/support/solutions/articles/158000433598-frequently-asked-questions) | 영상·센서·경기 기록 구분, 자료 누락/오래됨 표시 | 업체 고유 점수와 실제 성능 검증은 구분 |
| [KBO 게임센터](https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx) | 일정·게임센터·스코어보드·선수 기록 분리 | 동적 상세 경기 조작 미실행 |
| [NAVER AI 하이라이트 공식 발표](https://www.navercorp.com/media/pressReleasesDetail?seq=30010) | 중계 화면·기록을 대조한 장면 탐색 | 과거 발표 사례이며 현행 동일 기능 운영 확인 아님 |
| [SOOP 공식 발표](https://corp.sooplive.co.kr/media.php?bNo=3756&page=news_view) | 스포츠 시청·다국어·AI 번역/자막 | 현재 Pitcheezy 우선 범위와 거리가 있음 |

STATIZ는 조회502로 현행 화면을 확인하지 못했다. 없는 서비스/기능으로 처리하지 않으며
사용 가능하다고 단정하지도 않는다. 위 목록을 모두 AI 붐 이후 새로 생긴 서비스라고 부르지 않는다.

## 우리 서비스에 넣을 우선순위

### 교수 시연 전에 우선할 화면 구성

1. **한 타석 투구 리본**: 1구→2구→3구, 현재 공 강조, 클릭 시 영상·추천·결과 함께 이동.
   미래 공의 실제 구종/결과를 미리 표시하지 않고, 재생/공개한 공만 결과색을 붙인다.
2. **영상 옆 비교 카드**: ‘당시 추천’과 ‘실제 선택’을 같은 크기로 보여준다. 존을 주 그림으로,
   구종·구속·결과는 짧게. 좌표 상세값·파일/검증 설명은 펼쳐 보기에 둔다.
3. **현재 상황 한 줄**: 이닝·카운트·아웃·주자와 투수/타자. 예를 들어 ‘1회 초, 0볼 1스트라이크’.
   ‘왜 이 추천인가’는 실제 입력·받은 출력까지만 설명하고 모델 내부 인과를 생성하지 않는다.
4. **3단계 시연 진입**: 첫 타석 → 다른 타석 → 근거. SITE-audit1은 안내 링크까지 반영했다.
5. **PC/모바일 공통 위계**: PC는 영상 왼쪽·비교 오른쪽·투구 리본 아래. 모바일은 영상→핵심 비교→
   리본 순서로, 큰 표와 긴 문서는 뒤로 보낸다. 별도 사이트 두 개를 만들지 않는다.

### 현재 받은 경기 자료로 다음에 가능한 기능

- 투수·타자·카운트 필터. 실제 구종/결과 조건은 사후 분석 모드로 분리한다.
- 현재 공 이전의 구종 빈도·평균 구속·표본N. 모델 선택 비중과 실제 사용 빈도는 다른 색/이름으로 구분.
- 공개된 공의 번호 있는 실제 위치 누적. 점들을 궤적처럼 선으로 연결하지 않는다.
- 같은 투구 링크 복사와 제한된 시연 클립 목록. 공개 범위를 바꾸는 새 영상 업로드는 별도다.
- 미트 근거 토글. 같은 투구의 적합한 관측이 없으면 미제공, 보정이 없으면 거리 계산 없이 이미지.

### 추가 자료/검증 없이는 넣지 않을 기능

- 사건확률, 기대가치/WPA/승리확률 변화: 현재 선택 비중으로 대체 불가. 해당 모델 출력·정의·버전 필요.
- 포수/투수/감독 책임 점수: 현재 자료로 인과 책임을 계산할 수 없다.
- 3D 공 궤적·회전·신체 역학: 위치 한 점과 중계 영상은 전용 센서 자료를 대체하지 않는다.
- 무제한 AI 해설/챗봇·커뮤니티·VR: 한 공 설명과 시연 안정화 이후 검토한다.
- 연속 중계의 초 단위 경기 전체 탐색: 연속 영상과 투구별 시간 매핑이 필요하다. 현재261개 클립과 다르다.

## 제안하는 페이지 구조

```text
홈 (기존 디자인 유지)
├─ 경기 선택
│  └─ 관전: 영상 + 현재 상황 + 추천/실제 + 투구 리본
│     └─ 상세 분석: 좌표·받은 모델 정보·CV 근거
└─ 소개/근거: 사용 방법 + 모델 수치 + 연구 한계
```

CV 연구 기록은 보조 메뉴, service는 이동 안내, exhibition은 홈 비교 후보로 둔다.
별도 화면을 계속 늘리지 않는다. 이 문서는 기능/구조 제안이며 신규 기능 전체 구현 완료나
Song 관전 본체 채택 합의를 뜻하지 않는다. 팀원 코드·배포·공개 계약은 변경하지 않았다.
