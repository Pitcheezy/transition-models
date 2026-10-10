# 경기 검토 화면 좌표 표시 개선 — 2026-10-10

I-service5 완료. 사용자가 `관측 위치 -0.41 / 2.97 ft`의 의미를 물은 데 따라,
비공개 검토 화면에 가로 방향·높이·cm 환산을 추가했다. 선점 `6ecedbf`; 구현은 이 문서와 같은 커밋이다.

## 바뀐 표시와 근거

- 실제 투구 카드: `실제 공 위치` 아래 가로 방향과 높이를 표시하고 기존 x/z ft 값도 유지한다.
- 추천 후보: 같은 단위 설명을 적용한다. 구종 선택 비중·추천 순위·실제 좌표는 바꾸지 않았다.
- 비교 그래프: 눈금은 ft로 유지하고, 포수가 투수를 바라보는 방향에서 왼쪽 음수/오른쪽 양수와 지면 기준 높이를 설명한다.
- 미트: 결과 공개 후 별도 가로 축에 표시한다. 높이 정보 미제공·미검토 추정·투수 의도 아님을 유지한다.

좌표 방향과 높이는 이미 전달받아 보존한 로컬 `CONTRACT.md` §5의 정의다.
홈플레이트 기준 좌우이지 중계 화면 좌우나 타자 몸쪽/바깥쪽의 자동 판정이 아니다.
3구 `849843:1:3`은 원래 실수 좌표를 환산하면 가로 왼쪽 약12.6cm, 높이 약90.4cm다.
기존 두 자리 표시(-0.41/2.97ft)를 먼저 환산하면12.5/90.5cm가 되므로 **원래 값×30.48 후 반올림**한다.
미트 x는 왼쪽 약1.6cm다. 두 값을 제구 오차나 의도 정확도로 해석하지 않는다.
cm 표시는 단위 변환이며 정확도가 개선됐다는 의미가 아니다. 서비스의 고정 비교 구역을 타자별 실제 스트라이크존으로 주장하지 않는다.

## 검증

Node36passed, 관련 Python95passed(24.74초), 실제 Chrome headless154.0.8037.58에서9시나리오 통과.
3구 실제 영상 종료 후 공개, 공개 전 DOM/툴팁 숨김, 원 실수 기반 환산, 후보/미트 구분,
탐색 시 숨김,390px 화면 넘침 없음, 합성 영점/결측/미세값/음수 높이를 확인했다.
브라우저 예외·외부 요청·GET 이외 요청은0건이다. 최종 체크리스트7검사·Ruff167경로·JS 구문·diff 검사도 통과했다. 미트 높이 문구를 독립 코드 검토 피드백에 따라
“높이 정보는 제공되지 않습니다”로 수정한 최종 팩으로 브라우저 검사를 수행했다.

비공개 캡처는 `outputs/service_review_coordinates_20261010_v1/`에만 있다.
데스크톱 후보/그래프와 모바일 좌표/실제 투구 캡처를 직접 열어 확인했다.
[기계 판독 기록](results/service_integration_20261010/coordinate_ui_verification_v1.json)에 검사와 파일 식별 정보를 남겼다.

## 현재 실행·전달본

- 폴더: `outputs/service_review_video_20261010_v3/`
- ZIP: `outputs/service_review_video_20261010_v3.zip`
- 16파일,13,571,442bytes. SHA256: `c185473271ecee60fa99fa2c3689b854b1bfe071f587024ba04291555dc86cfa`
- 압축 해제16파일 바이트 일치·CRC·격리 Python `launch_review.py --check` 통과.
- v2 대비 변경은 `index.html`, `review.js`, `style.css`, `receipt.json`4파일뿐이다.
- 원본 응답 SHA `df606a11c6db465c054252ef8d331aeb23aa21565b4960bd586f3dcf8f62f6b7`과
  정규화 보고서 SHA `154d9cd1cb166552db5975137e2ba431b9ab48f94fcfa6bdd05304f645427c80`는 그대로다.
- Windows `START_WINDOWS.cmd`, Mac `START_MAC.command`; Python3.10 이상 필요. 주소는 실행한 컴퓨터에서만 열린다.
- 이 세션의 새 주소는 `http://127.0.0.1:59152/`다. 이전59151은 v2 사용자 확인 기록으로 보존한다.

재현 명령(저장소 루트, 출력 경로는 존재하지 않는 새 경로 사용):

```powershell
.venv/Scripts/python.exe -B scripts/build_service_review.py --input outputs/service_review_received_20261009/service-game-849843.json --source-kind provided_export --include-first-pa-video --out-dir outputs/service_review_video_20261010_v3 --zip outputs/service_review_video_20261010_v3.zip
.venv/Scripts/python.exe -I -S -B -X utf8 outputs/service_review_video_20261010_v3/launch_review.py --check
node --test web/service-review/review.test.cjs
.venv/Scripts/python.exe -B -m pytest -q tests/test_service_review_package.py tests/test_service_review_server.py tests/test_checklist_model.py
```

## 범위와 다음 조건

팀원 저장소·공개 Site·모델·영상·사람 응답은 변경하지 않았다. 기존 v1/v2 팩은 보존한다.
I-device1의 사용자 정상 확인은 v2에 대한 기록이다. v3의 자동 검사를 새 사용자 확인으로 옮기지 않는다.
Mac/아이폰 실기기, CV-6 추가 사람 응답, A-y 실제 timing 응답, CV-5a 시작 정의, CV-7 미열람 영상,
I-0/I-run1/I-release1의 모델 실행·합의·공개 조건은 그대로 남는다. 수정 권한 반납.
