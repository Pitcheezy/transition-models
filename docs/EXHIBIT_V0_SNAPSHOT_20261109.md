# v0 스냅샷 — 2026-11-09 현재 공개 배포본(app.pitcheezy.com)의 기록

> **이후 경과(2026-11-12 저녁 기준).** 11/12 15:29 KST에 공개 앱을 Song c47 빌드 + 접속 코드 ON으로 되돌렸다(CHECKLIST `EXHIBIT-rollback1`). 15:49에 #38에 회신했고(댓글 6816876891), 16:49에 Song이 답했다(댓글 6817925715: 공동시험 11/13 21시, 색 테마 조건부 동의, 3D 타자 보류). 아래 본문은 작성 시점 기준이다. "현재", "미발신", "되돌린 적 없음", "미커밋" 같은 표현은 그 시점의 것이다.

사용자 요청(2026-11-09 16시): "현재 배포된 버전 v0 저장해서 기록하고". v0 = 우리 안에서 부르는 이름(2026-11-09 09시 결정)으로, **Song 고정 빌드의 모바일 경기 화면이 우리 전시 Worker에서 서비스되는 지금의 공개 화면**이다.

## 무엇을 어디에 저장했나

Git 밖 `D:/pitcheezy_exhibit_check/v0-snapshot-20261109/` (25파일, 4.5 MB). 목록과 SHA-256은 그 폴더의 `SNAPSHOT.json`.

| 폴더 | 내용 | 근거 |
|---|---|---|
| `public/` | Song 고정 빌드 정적 4파일: `index.html` 659 B `85616c4b…`, `assets/index-X1sSTTQ4.js` 300,041 B `e46d431a…`, `assets/index-ks_hu7Ji.css` 118,449 B `292dd392…`, `favicon.svg` 249 B `bbfd72e5…` | 웹 commit `c47fe6cb78479362e7250141da946814cc33bd31`(Song 11/1 요청 묶음) |
| `data-v1/` | 공개 자료 6파일: `manifest.json`, `dates.json`, `health.json`, `games/2026-09-30.json`, `setup/849843.json`, `game/849843.json` 726,729 B `056fcf13…` | 자료 commit `cb1cfa8f…`; `game/849843.json`은 relay 데모가 쓰는 `relay/data/849843.json`과 바이트 동일 |
| `release/` | 11/1 호스트 release 후보 `release.zip` 535,848 B(번들 SHA `14106af1…`, 호스트 `aa6f7ab7…` + 위 정적 4) + `receipt.json` + `provenance.json` | EXHIBIT-host2 단계2 배포 입력 |
| `screens/` | 로컬 재생 화면 5장(`f00000~4.jpg`: 1구 Crow-Armstrong → Busch 1~3구 → Tatis 홈런)과 11/1 로컬 Worker 리허설 캡처 7장(게임·안내·복원, 390×844·1440×900) | 11/9 GIF 작업의 v0 칸 프레임, host1-local-browser |

## 이 스냅샷이 "배포본"과 같다고 보는 근거

- 배포 서버에서 내려받은 것이 아니다(접속 코드 뒤라 자동 수집을 하지 않았다). 대신 **우리가 올린 바이트**다: 11/2 단계5 전환 검사(CHECKLIST `EXHIBIT-switch2`, 24요청/24판정)에서 app.pitcheezy.com의 정적 4·자료 6·보조 1이 이 release 후보·자료 파일과 원본 바이트 일치함을 확인했다.
- 그 뒤 app Worker에 새 배포는 기록에 없다(11/3 maintenance·접속 문구 후보 `94afc1d`는 미배포). 적용 버전(11/2 기록) `5999cf0d-4f18-4d43-bcd6-320e04860369`, 접속 코드 ON, 자료 읽기 ON, 업로드·수집·피드백 OFF.
- 다음에 배포를 바꾸기 전에 **대시보드에서 현재 적용 버전 id가 위와 같은지 한 번 확인**하면 이 스냅샷이 곧 되돌릴 기준이 된다(wrangler rollback 대상 = 이 버전 id, 또는 `release/release.zip`의 public/ + 자료로 재배포).

## 로컬에서 v0 그대로 띄우기(검증·GIF 제작에 쓴 방법)

`public/` + `data-v1/`를 `v1/`이라는 이름으로 한 폴더에 두고(`public/v1/...`) 정적 서버로 서빙하면 된다(빌드의 자료 기준 경로 `VITE_PUBLISH_BASE="."` → `./v1/game/849843.json`). 주소 `/?game=849843`. 종료 경기는 1구에서 시작하고, 타석 목록의 투구를 누르면 아래 시트의 ‹ ›로 한 공씩 이동한다. launch.json `v0-song-static`(8798)이 이 구성이다(폴더는 세션 임시 폴더였으므로 다시 만들 때는 이 스냅샷에서 복사).

## 한계

- Worker 쪽(게이트·안내·텔레메트리 코드)은 `release/release.zip`의 `host/` 그대로이지만, 실제 배포 설정(이름·바인딩·비밀)은 비공개 폴더에만 있고 여기엔 없다.
- 화면 캡처는 로컬 재생이라 Worker가 끼우는 요소(이용 안내 위젯 등)는 없다.
