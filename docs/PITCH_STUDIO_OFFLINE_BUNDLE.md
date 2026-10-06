# 우리 CV 오프라인 시연 묶음 — 2026-10-06

실제 timeline/reveal 응답은 로컬 대상 폴더에서 찾지 못했다. 팀원 API/모델/관전 UI를
변경하거나 새로 구현하지 않고, 사용자가 바로 가져갈 수 있는 우리 발표 묶음을 준비했다.
E-site5 실제 응답 연결과 E-demo2 Song 화면 리허설은 계속 대기다.

## 산출물과 실행

- ZIP: `outputs/demo_delivery/pitcheezy_offline_demo_20261006_v3.zip`
- 압축 푼 폴더: 같은 위치의 `pitcheezy_offline_demo_20261006_v3/`
- 시작 파일: `START_HERE.html`
- 크기: 4,563,043바이트 (약 4.56MB)
- ZIP SHA256: `6afeb490264aca99ff92fa95e5f3f3ea43879af933ad973804d29ee0ca58f6cb`
- 내용 파일 29개 + bundle_manifest.json 1개. ZIP 전체를 옮겨 압축 해제한 뒤 시작 파일을 연다.
- v1/v2 폴더와 ZIP은 덮어쓰지 않고 보존했다. 새로 전달한다면 위 v3를 사용한다.

포함: 우리 정적 사이트 21파일(영상·포스터 포함), 기존 CV 장표 PNG/PPTX 2파일,
기존 private 비교 HTML/README/manifest 3파일, 시작 안내·대본·실행 안내 3파일.
원본 라벨·모델·private 관측 세션·전체 영상·인증정보는 포함하지 않았다.

홈 → 제품 콘셉트 → 실제 관측 → 기존 장표 → 대표 비교 → 다음 단계 순서다.
[새 사이트 포함 발표 대본](PITCH_STUDIO_DEMO_RUNBOOK.md)은 목표 2분이며 실제 낭독은 미측정이다.
기존 60–90초 M3 전용 대본과 장표를 덮어쓰지 않았다.

패키지는 비공개 현장·지정 팀원 파일 전달용이다. 기존 comparison/에는 MLB 비교 그림이
포함되므로 이 ZIP 전체를 공개 사이트/GitHub에 올리지 않는다. 이 ZIP을 공개 배포하거나
팀원에게 전송하지 않았다. 공개 사이트 자체는 별도로 v4로 갱신했다. 홈페이지의 이미 승인된 영상 공개 범위는 그대로다.

## 재생성·확인

저장소 루트에서 Python 3만 있으면 패키지 도구를 실행할 수 있다.

```bash
python scripts/build_pitch_demo_bundle.py build --comparison outputs/intent_label/delivery_20261005/intent_comparison_local --out outputs/demo_delivery/pitcheezy_offline_demo_new
python scripts/build_pitch_demo_bundle.py check outputs/demo_delivery/pitcheezy_offline_demo_new
```

기존 출력 폴더나 ZIP이 있으면 거절한다. 다른 출력 이름을 쓰며 이전 파일은 삭제하지 않는다.
개별 파일 수정 뒤 무조건 검사를 통과시키도록 해시를 바꾸지 않는다. 새로 빌드해 원본과 대조한다.

빌드 허용 목록은 scripts/build_pitch_demo_bundle.py의 SITE_FILES/SLIDES/COMPARISON_FILES다.
공개 사이트에 새 파일이 생기면 이 목록도 검토해야 한다. 원본 비교자료 폴더는 Git 제외이며,
다른 컴퓨터에서는 기존 비공개 자료를 받아 같은 저장소 아래에 두거나 완성 ZIP 자체를 옮긴다.

홈 링크 `href="./"`는 file URL에서 폴더 목록이 될 수 있으므로 **패키지의 사이트 HTML
사본에서만** `href="index.html"`로 바꾼다. 원본 HTML의 홈 링크는 바꾸지 않았다. v3는 재생 복구·투구 바로가기가 반영된 Site v4와 같다.
manifest는 source_sha256과 출력 sha256, 이 변환의 이름을 각각 기록한다.
장표·비교 HTML/JPEG·영상·JS·CSS는 원본 바이트 그대로다.

## 확인한 것

- 29개 파일의 원본 SHA·출력 SHA·바이트 일치 또는 명시한 홈 링크 변환을 확인했다.
- 기존 비교 HTML과 원본 M3 보고서, 내장 JPEG 5장의 해시가 기존 manifest와 일치한다.
- 패키지 내부 HTML href/src/poster의 상대 파일 경로·존재·범위 확인 통과.
- 이 링크 검사기는 CSS/JavaScript의 모든 동적 네트워크 요청을 증명하는 보안 검사가 아니다.
  이번 소스의 별도 읽기 감사에서 외부 CSS/JS 로드 의존성은 발견하지 않았다.
- ZIP에서 읽은 모든 내용이 생성 폴더와 바이트 단위로 일치한다.
- 같은 출력으로 빌드하면 FileExistsError로 거절되어 이전 묶음을 보존한다.
- Ruff check/format, 체크리스트 가드 4 passed(PYTHONUTF8=1). 재생 6·수신 34 Node 검사 통과. 공개 사이트는 재생 복구·투구 바로가기 변경만 별도 v4로 배포했다.
- 기존 M3·JSONL·장표·비교자료와 팀원 저장소는 수정하지 않았다.

## v3 변경 범위

홈 재생/일시정지·자동재생 차단 안내·파일 오류 정지 폴백, 정상/기권 바로가기,
2분 목표 안내와 30초 대체 대사가 추가됐다. 모델 호출이나 새 측정은 없다.
본 발표의 정상/기권 사례는 여전히 849843:1:3 / 849843:2:5이며 대표 비교는 849845:10:4다.
Windows 브라우저의 공개 사이트용 로컬 미리보기에서 재생·표시·정상/기권·390px 폭을
검수했다. 아래 file URL 제한을 우회해 비공개 패키지를 브라우저로 검사한 것은 아니다.

## 직접 실행 확인의 한계

Codex 앱 브라우저의 URL 보안 정책이 file:// 프로토콜을 차단해 시작 파일을 직접 여는
시도는 거절됐다. 다른 경로로 우회하지 않았다. 따라서 이 패키지의 file URL 렌더링,
Safari/Mac/iPhone에서의 재생, 실제 발표 낭독 시간은 **미확인**이다.
이전 작업의 공개 사이트 브라우저 검수와 이번 파일·해시 검증을 현장 리허설로 바꾸지 않는다.

다음은 사용자가 실제 발표 기기에서 START_HERE.html을 열고 네 항목(재생, 공개·기권,
글자·범례, 낭독 시간)을 확인하는 것이다. 기존 README에는 일반 로컬 HTTP 실행 방법도
있지만 이번 제한을 우회하기 위해 도구로 실행하거나 확인하지 않았다.
Song의 영상 대응·좌우·공개 시점·기기 확인은 별도 E-demo2다.
