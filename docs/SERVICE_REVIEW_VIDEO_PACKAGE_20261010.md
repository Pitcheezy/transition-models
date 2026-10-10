# S 응답·공식 클립 연결과 간편 실행팩 — 2026-10-10

사용자가 승인한 I-service3(영상 연결)와 H-port6(간편 실행팩)이다.
팀원 저장소·모델·API를 조회하거나 수정하지 않았다. 기존 공개 Site도 변경하지 않았다.
원문 응답과 기존 영상·미트/M3/사람 판독은 보존하며, 새 자료를 수집하거나 정확도를 다시 측정하지 않았다.

## 한 화면에서 가능한 것

262구 저장 응답에서 타석·투구를 고르고 추천을 확인한다. 첫 타석 3구에는 기존 공식 클립을 연결했다.
클립을 재생하면 끝날 때 현재 투구의 실제 결과·도착점과, 있는 경우 미트 가로 추정을 공개한다.
영상이 없는 나머지 투구도 추천 검토와 수동 결과 공개가 가능하다.
다른 투구·타석·보고서로 바꾸면 재생을 중단하고 결과를 다시 숨긴다.
늦게 끝난 이전 영상이나 파일 읽기가 현재 화면을 덮어쓰지 않는다. 영상 오류 시 다시 불러올 수 있다.

미트는 별도 가로축이다. 공식 클립의 프레임 시각이나 픽셀 위치로 변환·오버레이하지 않는다.
연속 중계·실시간 모델 추론·투수 의도·정책 효과 검증은 이 작업의 결과가 아니다.

## 영상 식별 근거

[고정 연결표](results/service_integration_20261010/first_pa_media_binding_v1.json)는
원문 SHA `df606a11c6db465c054252ef8d331aeb23aa21565b4960bd586f3dcf8f62f6b7`와
`849843:1:1–3`에만 적용한다. 다른 응답 파일에 같은 키가 있어도 출처 해시가 다르면 자동 연결하지 않는다.

- MP4 3개·포스터 3개의 바이트/SHA가 기존 공식 영상 근거·연결 코드와 일치한다.
- 이전 응답과 새 S의 공통 실제 결과 8필드, 투구 전 상황, 투수·타자 ID가 일치한다.
- 새 S 응답에는 playId가 없다. 기존 공식 피드/영상의 **투구 키↔playId 근거를 재사용**했다.
  S가 준 playId를 직접 검증했다고 표현하지 않는다.
- 기존 별도 미트 판독 프레임은 새 팩에 넣지 않았다. 공식 클립과 그 프레임의 시각을 추정 대응하지 않는다.

## 간편 실행과 생성

전달용 ZIP은 `outputs/service_review_video_20261010_v1.zip`이며 Git 제외 비공개 자료다.
압축을 전부 풀고 Windows에서는 `START_WINDOWS.cmd`, Mac에서는 `START_MAC.command`를 연다.
**Python 3.10 이상이 필요**하다. Python이 없는 기기에 자동 설치하는 프로그램은 아니다.
Mac에서 실행 권한/파일 연결 문제가 있으면 해당 폴더에서 `python3 launch_review.py --open`을 사용한다.
Windows 명령 대안은 `py -3 launch_review.py --open`이다.

실행 시 해시·보고서·영상 연결을 확인하고 빈 포트를 자동 선택한다. 안내되는 주소는 실행한 컴퓨터에서만 열린다.
저장소 전체·가중치·PyTorch·인터넷은 실행에 필요 없다. 서버 종료는 Ctrl+C다.
서버는 검증한 UI·보고서·영상만 제공하며 원문·영수증·실행 파일·디렉터리 목록은 제공하지 않는다.
MP4 단일 구간 요청(206/416)과 HEAD를 지원한다. 검증 후에는 고정한 바이트를 제공한다.

새 폴더/ZIP 이름으로 재생성한다. 기존 출력은 덮어쓰지 않는다.

```text
uv run --frozen python scripts/build_service_review.py --input outputs/service_review_received_20261009/service-game-849843.json --source-kind provided_export --include-first-pa-video --out-dir outputs/service_review_video_new --zip outputs/service_review_video_new.zip
python outputs/service_review_video_new/launch_review.py --check
python outputs/service_review_video_new/launch_review.py --open
```

영상 옵션을 생략하면 빈 영상 목록을 가진 새 v2 팩을 만든다. 옛 v1 팩을 덮어쓰거나 소급 변환하지 않는다.
이 팩의 숨김 기능은 표시 순서 제어이며 접근 통제가 아니다. 전체 보고서에는 사후 자료가 있다.
SHA는 파일 변경 탐지이며 제공자 신원/자료 재배포 권리의 인증이 아니다. 공개 배포 대상이 아니다.

## 검증

검사 결과와 ZIP 식별자는 [검증 기록](results/service_integration_20261010/video_package_verification_v1.json)에 기록한다.
- Windows CPU 전체: **2202 passed, 8 skipped, 2 deselected**, 2 warnings, 566.80초. Ruff167경로 통과.
- 관련 Python289passed/1skipped(최종 JS 일시정지 수정 전); 최종 Node29passed. 전체 검사에는 최종 JS 검사도 포함됐다.
- ZIP 13,570,764bytes, SHA `9f6362ffe048509b59265a99645bbaa125db1445f1c32b89bfc31fd2f7b30f75`; CRC 정상.
- 한글·공백 경로에 실제 압축 해제한16파일이 원본과 같고, 저장소 없는 격리 Python의 --check가 통과했다.
- 실제 HTTP에서 영상 구간206/128bytes를 확인하고 원문·영수증·실행기·폴더 목록은404임을 확인했다.
- Windows 브라우저에서3클립 종료→현재구 공개, 재생 중 탐색 초기화,3구 미트 가로 추정 공개를 확인했다.
- 390px 창에서 가로 넘침 없음(영상 폭309.6px)을 확인했다. 실제 모바일/Safari 검증은 아니다.
- 실제 파일 선택기 오류 검수와 최종 화면 캡처는 브라우저 도구의 실행 환경 갱신 오류로 완료하지 못했다.
  파일 오류·교체·늦은 응답의 상태 제어는 Node 회귀 검사에서 확인했다.
- 정상 일시정지 AbortError를 실패로 고정하던 문제를 수정했고, 독립 재검토에서도 해당 수정과 원자료 보존을 확인했다.

## 다음 조건

두 단위는 우리 로컬 연결과 전달 편의를 완성한다. I-0 정본·역할 합의, I-run1 팀원 모델 실행,
I-release1 공개 운영/실기기, CV-6/A-y 독립 사람 검토, CV-7 독립 영상 평가를 완료로 바꾸지 않는다.
새 실행팩을 실제 Mac·아이폰에서 사용한 기록은 아직 없다. Python이 설치된 Windows의 압축 해제본을 검증했다.
