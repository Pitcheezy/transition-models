# 모델 재사용 영상 처리 — CV-17

CV-14의 초기화 중앙15.041초를 줄일 수 있는지 같은 10개 개발 시각으로 확인한다.
Faster R-CNN 전체 화면·GPU·임계값0.5·4threads 및 설정 원바이트는 그대로 고정한다.
범용 모델의 미트 판독 채택 보류도 유지한다. 확정 응답 좌표는 항상 null이다.

첫 요청에서 별도 spawn 프로세스 하나를 만들고 모델을 한 번 로드한다. warmup은 없다.
부모는 요청/이미지/설정/응답 해시와 ID를 대조하고 검증한 파일만 response 마지막 순서로
독점 발행한다. 요청 하나가 끝나야 다음 요청을 보낸다. worker의 지연 출력이 그대로
서비스 파일에 쓰이지 않도록 private 공간에서 받고 원바이트를 부모가 검증한다.

60초 관측 제한을 넘기거나 통신/결속이 실패하면 worker를 종료하고 종료 여부를 확인한다.
그 실행은 영구 실패하며 자동 재시작하지 않는다. 이후 계획 항목도 분모에 남긴다.
최종 외부 루프 검증·발행까지 60초 hard deadline이라는 주장은 하지 않는다.
응답 회수 실패에도 finally에서 종료하고, 이미 존재하는 출력 폴더는 변경 전에 거절한다.

[실행 전 규약](results/cv_local_20261007/worker_preregister_v1.json).
합성28개 테스트(기존 loop/strict reporter 성공·timeout 통합 포함) 및 Ruff 통과.
실제 모델 호출 전 커밋·푸시한다. 새 사람 검토·전체 타석·독립 실시간 성능은 미완료다.

```bash
python -m intent.local_glove_worker --plan PLAN.json --out outputs/cv_local_worker_run_NEW
python -m intent.local_glove_observer_report --run outputs/cv_local_worker_run_NEW --out REPORT.json
```

원래 CLI 표기가 실행 방식으로 오해되지 않도록 worker_private의 execution/lifecycle/request
영수증에서 persistent_spawn_worker를 명시한다. raw worker 파일은 Git 제외다.
코드 파일 결속에 worker/observer/detector/observer_report가 빠지면 시작하지 않는다.
