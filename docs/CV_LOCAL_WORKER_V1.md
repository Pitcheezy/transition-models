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

## 실제 10시각 결과

사전 등록 `0f292da`를 푸시한 뒤 실행했다. 10/10수락, 오류/미시도0,
단일후보4·복수2·후보없음4이며 확정 미트 좌표는0이다. 입력10SHA가 규약과 일치하고
실행 전후 코드 바이트 결속을 통과했다. worker 하나·engine 하나를 만들었고 9회 재사용했다.
10요청 완료 후 exitcode0과 실제 종료를 확인했다. 개별 요청의 exit_confirmed=false는
요청 사이 프로세스가 살아 있었다는 뜻이며 마지막 lifecycle의 true와 구분한다.

| 지표 | CV-14 매번 새 모델 | CV-17 재사용 |
|---|---:|---:|
| 같은 10시각 루프 전체 | 233.562초 | 72.766초 |
| 예정 시점→검증 후 발행 중앙 | 104.961초 | 26.664초 |
| 예정 시점→발행 범위 | 23.859–188.562초 | 26.250–27.766초 |
| 발행≤5초 / 계획10개 | 0/10 | 0/10 |
| 어댑터 처리 중앙 | 17.042초 | 0.712초 |
| 모델 초기화 중앙 | 15.041초 | 0.000033초 |

첫 worker 요청은 24.953초이며, 재사용9개의 worker 구간 중앙은1.219초다.
첫 실제 모델 초기화20.275초는 위의 거의0인 중앙값으로 감추지 않는다.
워커 구간은 부모 결속/발행을 포함하지만 바깥 영상 추출·최종검증은 포함하지 않는다.
실행 순서와 장비 상태가 다른 각1회 비교이므로 보편적인 속도배수나 신뢰구간을 주장하지 않는다.

지연 증가를 줄였지만 시작 지연을 따라잡지 못했다. **5초 목표는 여전히 미충족**이며
실시간 완료·미트 정확도 개선·서비스 채택이 아니다. 후속은 입력 전에 모델 준비를 끝내는
별도 단계다. 그 준비 시간을 명시하고 warm 구간만의 지연을 콜드 전체시간과 구분해야 한다.

[수치 보고서](results/cv_local_20261007/worker_report_v1.json),
[입력·프로세스 결속 기록](results/cv_local_20261007/worker_run_audit_v1.json).
28합성 테스트와 Ruff, 기존 loop/report 성공·timeout 통합 검증을 통과했다.
