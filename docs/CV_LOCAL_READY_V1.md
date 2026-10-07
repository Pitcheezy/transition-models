# 입력 전 준비를 구분한 영상 처리 — CV-18

CV-17에서 매번 로드하던 비용은 줄었으나 최초24.953초 지연이 남아 5초 발행은0/10이었다.
모델 준비를 입력 일정 시작 전에 완료하는 별도 개발 실행을 고정한다. 시작 비용을 숨기지 않고
preflight, startup, warm loop, 사용자가 처음 실행한 시점부터의 cold 전체 시간을 각각 기록한다.
wrapper의 cold_user_elapsed는 Python실행/import와 마지막 요약 저장을 제외한다.
별도 부모 perf_counter로 명령 시작→프로세스 종료 전체 시간을 재어 이 비용도 기록한다.

같은 Faster 전체/GPU/threshold0.5/4threads와 같은10시각을 사용한다. 단일worker를 한 번
준비하며 synthetic RGB검정1280×720 5회만 warmup한다. 이 수는 실제 결과 전에 고정했다.
study 프레임은 READY 이후에만 제공한다. READY timeout은60초다. 실패 시 원예외·종료 영수증,
계획10개/미시도10개를 남긴다. 자동 retry나 restart는 없다. 성공 후 기존 loop의 입력일정을 시작한다.

원본·설정·모델·응답 결속, shadow응답 항상mitt=null, 모호함/후보없음/오류 분리는 유지한다.
기존 CV-17 기본 lazy 동작은 그대로이며 optional prepare를 호출한 실행만 새모드다.
기존 CV-17 재현에는 해당 실행 커밋의 worker 코드를 쓴다. 과거 기록의 SHA를 새코드값으로 고치지 않는다.
이번 loop에는 CV-19의 맥/리눅스 가상환경 실행파일 결속 수정도 포함한다. 동일 일정/입력과
추출 방식은 유지하지만 코드가 완전히 동일한 단일요인 무작위 비교로 설명하지 않는다.

[사전 규약](results/cv_local_20261007/ready_preregister_v1.json).
아래 명령은 해당실행 계획에 ready/worker/observer/detector/report 코드파일이 결속되어야 한다.

```bash
python -m intent.local_glove_ready --plan PLAN.json --out outputs/cv_local_ready_run_NEW --startup-timeout 60
python -m intent.local_glove_observer_report --run outputs/cv_local_ready_run_NEW --out REPORT.json
```

startup 자료는 출력의 `.startup` 형제폴더에 보존한다. 두경로가 이미 있으면 시작하지 않는다.
성공한 warm-loop의 5초 비율도 콜드 시작·릴리스 전 성공·실시간 중계 검증과 다르다.
이 기술 비교로 기존 범용모델의 미트 판독 채택보류 결정을 바꾸지 않는다.

실제 모델 실행 전 전체Windows CPU검사:1563 passed·5 skipped·2 deselected,401.33초.
Ruff139경로통과. 기존Pillow deprecation경고2건, 새로운 실패0.
