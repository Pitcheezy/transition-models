# 사람 미트 검토 입력 화면 v1

2026-10-05. CV-6의 기존 26장 개발 재검토를 쉽게 입력하기 위한 로컬 도구다.
실제 사람 판정은 **완료 0 / 미검토 26**으로 남아 있으며 AI 추론은 하지 않았다.

## 사용 순서

1. `outputs/cv_review_20261005_ui_v1/reviewer/index.html`을 브라우저로 연다.
   HTML만 옮기지 말고 `reviewer/` 폴더 전체(원본 images·JS 포함)를 함께 보관한다.
2. 검토자 ID를 입력한다. 이전/다음 또는 프레임 번호로 원본을 이동한다.
3. 미트 중심을 클릭하면 원본 전체 프레임의 픽셀 좌표가 기록된다.
   가시성 full/partial과 자세는 사람이 따로 선택한다. resting은 기권 사유가 아니다.
4. 읽을 수 없으면 unavailable, 판정이 불확실하면 unknown을 선택하고 이유를 적는다.
   해당 상태에서는 점이 지워진다. unreviewed를 선택하면 그 행을 미검토로 초기화한다.
5. **JSON 내보내기**로 파일을 저장한다. 미검토 행을 남긴 중간 저장도 가능하다.
   자동 저장은 없으므로 닫기 전 다운로드 파일을 확인한다.
6. 다음에 **저장한 응답 불러오기**로 이어서 검토한다. 다른 자료·누락·중복·범위 밖 좌표는
   거부하고 기존 입력을 유지한다. 유효한 파일로 현재 입력을 교체할 때는 확인창이 나온다.

아래 명령으로 실제 응답을 검사한다. `path/to/response.json`은 내려받은 응답 경로로 바꾼다.

```bash
python -m intent.review_queue check-response --package outputs/cv_review_20261005_ui_v1 --response path/to/response.json
```

원본 응답과 검토자별 파일을 각각 보존한다. 검토자에게 `reviewer/`만 제공하고 상위의
`private_selection.json`은 제공하지 않는다. MLB 원본 화면은 공개 저장소·공개 링크에 올리지 않는다.

## 재생성과 유지보수

기존 Python 환경에서 새 패키지를 만들면 UI도 함께 생성된다.

```bash
python -m intent.review_queue prepare --report docs/results/cv_followup_20261005/quality_audit_v1.json --out outputs/cv_review_new_ui
```

기존 static 패키지와 빈 양식은 보존했다. UI는 `intent/reviewer_ui.py`와 `intent/review_ui.js`,
준비/최종 검사는 기존 `intent/review_queue.py`가 담당한다. 응답 스키마는 그대로다.
JS는 브라우저 기본 기능만 쓰며 네트워크 호출·localStorage·외부 AI 연결이 없다.
Python 테스트는 Node가 있으면 JS 로직과 합성 응답의 Python 검사 왕복도 확인한다.
Node가 없는 환경에서는 해당 JS 검사가 skip되므로 별도 Node 환경에서 확인해야 한다.

## 검증 범위와 남은 일

축소 화면 클릭의 원본 좌표 변환·명시적 가시성·상태 변경·잘못된 응답 거절·내보내기와
Python 응답 검사 연결을 합성 자료로 검사했다. 실제 패키지는 26장 이미지 SHA와 공개 데이터 연결,
빈 응답을 검사했으며 실제 사람 응답으로 합성 결과를 섞지 않았다.
브라우저 렌더링은 미검증이다. 앞선 앱 브라우저의 file URL 보안 거절을 우회하지 않았고
HTML 정적 검사와 Node 로직 검사만 수행했다.

이 자료는 이미 읽은 두 경기의 불일치 표본이므로 새 독립 평가가 아니다. CV-6은 실제 사람
응답과 원인 판정이 있어야 끝난다. CV-5a는 연속 영상과 실제 자동 관측기·발행 시각 계측이 필요하다.
기존 `intent.run`은 저장된 주석 변환기이며, 과거 Claude 판독 workflow는 릴리스/포구 뒤
화면을 함께 제공하므로 그대로 투구 전 관측기로 사용할 수 없다. CV-7 새 영상 독립 평가도 남아 있다.

[실행 기록](results/cv_followup_20261005/review_ui_v1.json) · [검토 규약](CV_OBSERVATION_PROTOCOL_V1.md)

검사: **794 passed / 5 skipped / 2 deselected**, Ruff 96경로 통과. 기존 Pillow 경고 2건. frozen 파일 186개와 이전 검토 패키지 불변.

## 2026-10-07 브라우저 확인

기존 reviewer 폴더만 `127.0.0.1:8788`에 로컬 제공하고 앱 브라우저에서 원본 이미지,
26장 분모, 미검토 상태와 입력 도구 렌더링을 확인했다. 검토자ID와 판정은 입력하지 않았고
응답0/미검토26을 유지한다. 앞선 file URL 제한을 우회한 것이 아니라 별도 로컬 HTTP 제공이다.
서버가 종료되면 저장소 루트에서 다음 명령으로 다시 열 수 있다.

```text
python -m http.server 8788 --bind 127.0.0.1 --directory outputs/cv_review_20261005_ui_v1/reviewer
```

원본 검토 결과를 저장할 때에는 브라우저의 **JSON 내보내기**를 사용한다. 서버는 입력을 저장하지 않는다.
