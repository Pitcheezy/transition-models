# 849843 전체 영상 조사와 원형 추천 표시

사용자 요청: 전체 중계 원본을 찾아 Song의 구현도 읽기 전용으로 확인한다. 조사일 2026-10-30.
현재 진행·배포 여부는 CHECKLIST와 `results/site_fullgame_20261030/round-markers-receipt.json`에 기록한다.

## 확인한 영상과 방식

- 우리 공개 관전은 71타석·262구 자료와 개별 공식 클립261개를 연결한다. 1구는 신원 불일치로 영상 제외. 경기 탐색바는 투구 순서이며 전체 중계의 초 단위 타임라인이 아니다.
- Song 공개 분기 `ws/rs01-tfinal-fix-1029`, 고정 커밋 `7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8`에서 확인한 영상은 MLB 압축 영상39구다. 우리에게 이미 있는 약13분51초 압축 영상과 같은 URL이며 새로운 전체 원본을 확보한 것이 아니다.
- [showcase-scenes.json](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/src/showcase-scenes.json#L2)은 `pitchId`와 `releaseSeconds`를 연결한다. 전체262구의 준비·도착·결과 시각표는 없다.
- [Showcase.tsx](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/src/Showcase.tsx#L72)는 릴리스3초 전~4초 후를 재생한다. [화면 설명](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/src/Showcase.tsx#L151)도 압축 영상39구·AI판독·사람미검토를 명시한다.
- [offline README](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/offline/README-ko.md#L16)의 전체262구는 공개 결과·경기 흐름 응답을 뜻한다. 영상 사본은 별도 압축 영상이다.
- [SyncSheet.tsx](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/src/service/SyncSheet.tsx#L56)의 ‘중계 맞추기’는 외부 TV를 보며 미트 순간에 탭해 기록 표시 지연을 조절한다. 외부 영상의 재생 시각을 제어하는 기능이 아니다.

## 공식 전체 다시보기 후보

[Peacock Game 1: Cubs at Padres](https://www.peacocktv.com/sports/game-1-cubs-at-padres/0a6dbfb3-dfe6-34ec-9beb-d228d4dba9af)에 NL Wild Card Game1, September30, 2h41m 다시보기가 표시된다. ‘Watch Replay’는 가입/요금제 화면으로 연결된다. 이번 조회에서는 실제 재생·한국 접속 가능 여부·다운로드 가능한 원본·외부 플레이어 삽입 경로를 확인하지 못했다. 가입·결제·영상 다운로드·공개 재업로드를 수행하지 않았다.

[MLB 경기 영상 목록](https://www.mlb.com/video/game/849843)은 해당 경기의 공식 하이라이트 경로다. 검색의 ‘Full Game Highlights’라는 제목만으로 무편집 전체 중계로 분류하지 않았다.

조사 범위는 Song 공개 main/demo/ws-2026/svc/ws-static-web 및 위 최신 고정 분기의 관련 트리, 우리 기존 영상 기록, 공식 웹 검색이다. Song의 비공개 로컬 보관 파일은 미확인이다. 팀원 파일·프로세스·배포는 변경하지 않았다.

## 다음에 필요한 것

전체 중계에 싱크를 맞추려면 실제 재생 가능한 같은 원본과 투구ID별 준비·도착·결과 경계가 필요하다. 방송사/광고/리플레이 편집이 다르면 시각표도 달라지므로 파일 식별을 먼저 고정한다. 현재 클립 길이를 더하거나 릴리스+고정초를 정확한 도착 시각으로 사용하지 않는다.

지금 가능한 축약 영상39장면 재생은 별도 선택지이며, 사용자 요청의 전체262구 중계 완성으로 표시하지 않는다. 새 모델 가중치를 받는 것으로 영상 원본과 시각표의 부재가 해결되지는 않는다.

## 이번 원형 표시 변경

관전·상세 분석의 추천 표시를 기존 좌표 중심의 원으로 변경한다. 같은 위치의 순위는 `1·3`처럼 묶고 숫자 전체 목록을 유지한다. 실제 위치·공개 시점·추천 자료는 변경하지 않는다. 범례와 홈/안내의 개념도도 원형으로 맞춘다. 미트 추정의 검증 수준이나 추천 효과를 높여 표현하지 않는다.

## 검증과 공개 결과

- 제품 `22723982723f5c83dbcffde4cc963105093fb879`, PR85, main 미통합.
- 기존 Node257 통과, 사이트 정적/미디어 무결성 통과, checklist8 통과(기존 Windows 출력 인코딩 경고1).
- 실제 Claude Fable5.1 고정 변경분 검토70.31초, APPROVE. 범례의 색 외 구분과 큰 순위 그룹 크기는 비차단 제안으로 기록했다.
- Chrome 관전/상세에서 원 중심과 겹친 `1·3`/`2` 유지, 재생 종료 실제 위치/결과 공개, 되감기 숨김, 390px 가로 넘침 없음 확인. 실제 휴대폰 검사와 다르다.
- Sites v20 공개 성공, 소스 `af4ce5057ba25bb4d3f7c3732a81da32e27c8a12`. 공개 도메인의 원형 마커와 영상 종료 실제 공 표시도 확인했다.
- 기존 로고5·설명그림4·주동선에서 연구미트분리 등은 v19에서 완료된 범위다. 원형 표시는 이번 v20이다.
- 전체 중계 동기화는 미완료. 팀원 저장소와 별도 Cloudflare 시험 설정은 불변이다.
