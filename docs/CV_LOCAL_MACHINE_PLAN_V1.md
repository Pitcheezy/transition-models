# CV21 — 기기별 새 실행 계획 준비

기존 절대경로 계획을 수동 수정하지 않고, 현재 컴퓨터의 검증된 캡처·설정·실행기로
새 `plan.json`과 `validation_receipt.json`을 만든다. 원본 계획과 기존 실험은 보존한다.
준비 단계에서는 영상 추출·디코더 실행·torch import·모델 호출을 하지 않는다.

## 준비 조건

- 현재 기기에 이미 유효한 capture receipt와 원본/클립/시간표가 있어야 한다.
  예전 Windows capture receipt를 Mac에 복사해 경로만 바꾸는 도구가 아니다.
- 해당 기기의 가중치 절대경로와 SHA를 가진 새 strict config를 준비한다.
  기존 config를 덮어쓰지 않는다. Mac에서는 현재 지원되는 `cpu`를 사용한다.
  MPS는 이 관측기의 지원 장치가 아니며 Windows CUDA 결과를 Mac 속도로 해석하지 않는다.
- cutoff는 엄격히 증가하는 원본 PTS의 정수·분수·정확한 문자열이다.
  JSON 소수 숫자는 거절한다. 영상 UTC로 재생초를 추정하지 않는다.
- output의 부모는 존재해야 하며 bundle은 새 폴더여야 한다.

## 사용

아래 명령은 저장소 루트, 활성화한 프로젝트 가상환경에서 실행한다. 대문자 경로는
그 컴퓨터에서 이미 검증한 파일로 대체한다. 한 줄은 Windows PowerShell/Mac shell 공통이다.

```text
python -m intent.local_glove_plan --capture-dir LOCAL_CAPTURE --config LOCAL_CONFIG.json --cutoffs-json EXACT_CUTOFFS.json --ffmpeg LOCAL_FFMPEG --out-directory outputs/new_machine_plan_v1 --observer-timeout-seconds 60 --extract-timeout-seconds 120
```

`--cutoffs-json` 대신 `--cutoff 2703701/15000 --cutoff 2778701/15000`처럼 반복 지정할 수 있다.
ffmpeg는 실행하지 않고 설치된 실제 파일로 해석한다. Homebrew 실행기 링크만 해석하며
영상·config·가중치의 링크 검사는 완화하지 않는다. Python은 venv launcher 경로를 유지한다.

성공 receipt의 `status=validated`는 파일/SHA/PTS 준비 검사 성공이다. 장치·디코더·모델의
실제 동작 성공은 아니다. 이 단계 후 `run/`, `run.startup/`은 아직 없어야 한다.
오류가 나면 실패 receipt와 중간 plan을 보존하며, 고친 뒤 **다른 새 bundle**을 사용한다.
생성 중 가중치·config·계획이 변하면 거절한다. receipt는 기존 파일을 덮어쓰지 않는다.

실제 호출은 별도 연구 규약·코드 해시를 고정하고 기록한 후 실행한다.

```text
python -m intent.local_glove_ready --plan outputs/new_machine_plan_v1/plan.json --out outputs/new_machine_plan_v1/run --startup-timeout 60
```

이 명령은 실제 모델을 불러온다. CPU 준비가 60초를 넘으면 실패를 기록하며 임의 재시도하지 않는다.
준비된 generic glove 후보는 계속 확정 미트/투수 의도가 아니다. 표준 응답 `mitt=null`을 유지한다.

## 실제 준비 확인

Windows에서 기존 CV20의 10개 cutoff와 원 config로 새 bundle을 한 번 만들었다.
계획·설정 원본 SHA 불변, 상태 validated, 모델/디코더/준비 subprocess 호출0,
run/startup 폴더 없음 확인. 전체 경로 receipt는 로컬에 보존한다.
[경로를 제외한 준비 근거](results/cv_local_20261007/machine_plan_validation_v1.json).
합성 검사45개와 독립 읽기 검토를 통과했다. 관련 준비/worker 검사는 인계 기록 참조.
프로젝트 Ruff142경로 통과. Mac 실기기 실행은 아직 검증하지 않았다.

CV22 속도 반복은 이 도구가 생성한 짧은 manifest를 쓰지 않고 CV20 원본 계획 바이트의
복사본을 사용한다. 검사 파일 수 차이가 이전과의 속도 비교에 섞이지 않게 하기 위해서다.
