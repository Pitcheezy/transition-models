# CV-31 — 노트북 관측 재생과 브라우저 회귀

2026-10-11, 기준6792ca3·선점c8f9fe8. 사용자 요청에 따라 Windows에서 독립적으로 진행했다. 팀원 저장소 접근·수정·메시지 전송·공개 Site 배포는 하지 않았다.

## 발견과 수정

1. 구간 끝은 원본 파일의 끝과 다르다. 기존 코드는 별도 재생 버튼에서만 처음으로 돌려서, 영상 자체 재생/키보드 Space는 즉시 다시 멈췄다. 실제 개발 영상에서 재현했고, 수정 전 소스를 합성 팩에 주입한 회귀도 실패했다. 이제 공통 `play` 이벤트가 재시작을 처리한다.
2. Windows WebKit에서는 최초 탐색이 요청한 구간 시작보다 앞에서 완료되었다. 최초 이동을 `loadeddata`에서 한 번 실행하고 `seeked`에서도 경계를 확인한다. 단순히 이벤트만 추가하면 디코더의 수ms~한 프레임 차이로 같은 위치를 반복 탐색하는 문제가 있어, 재생 제어에만100ms의 정착 여유를 둔다. 15fps 합성 영상의 시험 허용치는 한 프레임+25ms이며 탐색 완료도 확인한다.

이 여유는 과학적 허용 오차가 아니다. 원본 분수 시각·발행/마감 비교·`stateAt`·관측 요약은 바꾸지 않았다. 표시 시계는 실제 `video.currentTime`을 사용하며 값을 맞춰 꾸미지 않는다. 프레임 단위 정확한 정지, 동기화 정확도100ms, 실제 Mac/iPhone 검증을 주장하지 않는다.

## 비공개 자료 없이 검사하기

`tests/browser/observation-playback.test.cjs`가 원본 색상/도형 합성 영상과 가상 기록으로 실제 검토 서버를 실행한다. fixture는 직접 생성한8초·15fps MP4와 JPEG2장이다. MLB 영상·모델·사람 응답은 쓰지 않는다. 새9검사와 기존 서비스13검사를 Chromium/WebKit에서 함께 실행하도록 기존 CI에 연결했다.

```text
cd tests/browser
npm ci --ignore-scripts
npx playwright install chromium webkit
npm test
```

Linux에서 브라우저 시스템 의존성도 필요하면 `npx playwright install --with-deps chromium webkit`를 사용한다. `BROWSER_ENGINE=webkit`으로 WebKit을 선택한다(기본 chromium). Windows PowerShell은 `$env:BROWSER_ENGINE='webkit'` 형식이다. `PYTHON_BIN`은 Python3.12 실행 경로, `BROWSER_EXECUTABLE`은 Chromium에서만 선택하는 실행 파일이다. 실제 Mac에서의 확인과는 별개다.

검사 범위: 기본 재생 경로 재시작, 실제 영상 디코딩·Range 탐색, 발행 전/뒤로 이동 숨김, 이미지 교체 중 이전 이미지 숨김, 구간 종료·재생·투구 탐색, 자료/영상/이미지 오류 표시, 좁은 화면과 기권/오류 의미 보존. 외부 요청·업로드는 거절하고 자체 임시 폴더와 테스트 서버만 정리한다.

## 실제 확인 결과

- Windows Chrome154.0.8037.58: 합성22/22 통과(35.84초).
- Windows WebKit26.5: 합성22/22 통과(56.82초). 실제 Safari/Mac/iPhone 사용자 검수는 아니다.
- 실제 개발 영상 Chrome:16/16 통과, JavaScript 오류0. 원래15검사에 영상 키보드 Space 재시작을 추가했다. 기존 개발 자료의 재생 회귀이며 새 정확도 평가가 아니다.
- Node 발행·마감 계약26검사 통과. 관련 Python58검사 통과; 최초 실행은 자식 프로세스의 Windows 인코딩 경고1건이 있었다. 문서상 `PYTHONUTF8=1` 설정 후 체크리스트7검사를 경고 없이 재확인했다.
- 기존 v4와 새 v9 팩의 원문/영상/입력 근거/재생 데이터는 동일하다. 자산 중 `playback.js`와 이를 기록하는 manifest만 바뀌었다. 전체 파일 크기·SHA 검사를 통과했다.

새 비공개 관측팩 `outputs/cv_replay_view_20261011_v9`:21파일·52,900,379bytes. manifest SHA256 `766b8d723679f89ccab701a83998f0fb90c90e1111f0da73b7ebc104b85aced3`.
노트북 주소는 `http://127.0.0.1:59158/`이며 서버가 실행 중인 이 컴퓨터에서만 열린다. 기존 탭은 새로고침한다. 종료 후 재실행:

```text
.venv/Scripts/python.exe -B -S -X utf8 -m intent.observation_playback_server --directory outputs/cv_replay_view_20261011_v9 --port 59158
```

이 관측팩은 팀원 서비스 검토용 v5 ZIP과 별개다. v5 소스/영상 ZIP은 변경하지 않았고 CV-31을 포함하지 않는다. [세 ZIP의 내용과 팀원 전달 문안](handoff/FILE_GUIDE_20261011.md).
Mac I-device2는 나중에 해당 기기에서 재개하며 노트북 개발의 선행 조건이 아니다. A-y 사용자 보류, CV-6/CV-7 독립 입력, I-run1 모델 실행 자료 대기를 유지한다.
