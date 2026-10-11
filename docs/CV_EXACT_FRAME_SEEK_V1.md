# CV24 — 정확한 프레임 추출 최적화

우리 CV 저장소의 반복 디코딩 비용만 개선한다. 팀원 모델/API·공개 사이트·M3·기존 JSONL은 고정한다.

## 변경과 검증 기준

기존 방식은 매 요청마다 클립 처음부터 디코딩한 뒤 순번으로 선택했다. 새 기본 방식은
검증된 목표 프레임보다 최소 2초 앞의 정수 시각으로 탐색한 후 **정확한 PTS**로 선택한다.
요청 시각 이전 프레임만 선택하는 기존 매핑과 체크섬 검증은 그대로다. 초기·음수·큰 PTS는
실행 전에 기존 순번 방식으로 분기한다. 추출 실패 뒤 다른 프레임이나 방식으로 재시도하지 않는다.

이전 영수증도 계속 검증할 수 있고, 새 영수증은 요청 방식과 실제 방식을 따로 기록한다.
`--extraction-mode ordinal`은 기존 방식의 명시적 비교 경로다.

[FFmpeg 공식 옵션](https://ffmpeg.org/ffmpeg.html)의 `seek_timestamp`, `copyts`,
`noaccurate_seek`를 사용한다. 탐색 자체가 정확성을 보장하는 것은 아니므로 최종 PTS·duration·size·MD5,
time base와 크기가 기존 매핑과 다르면 실패로 남긴다. 새 영상의 자동 지원을 보장하지 않는다.

## 실행 전 고정

[기계 판독 규약](results/cv_local_20261007/exact_seek_preregister_v1.json)에 코드·입력·모델 해시,
14개 시각, 비교 순서와 실패 보존을 기록했다. 이전 개발 자료 3장으로 구현 탐색을 했으며
이후 비교는 독립 정확도 평가가 아니다. 14장 각각 기존/새 방식 순서를 교대로 한 번 비교하고,
고정5초 간격 관측 루프도 한 번 실행한다. 실패·기권·지연 초과를 삭제하지 않는다.

## 재현

기존 로컬 CV23 capture 자료와 가중치가 필요하다. 경로는 비공개 로컬 자료이며 Git에 영상을 넣지 않는다.
새 출력 폴더를 지정한다. 기존 실행 결과는 덮어쓰지 않는다.

```text
python -m intent.clip_frames --capture-dir CAPTURE --source-seconds RATIONAL --out NEW_FRAME --ffmpeg FFMPEG --extraction-mode seek_pts
python -m intent.clip_frames --capture-dir CAPTURE --source-seconds RATIONAL --out NEW_REFERENCE --ffmpeg FFMPEG --extraction-mode ordinal
python -m intent.local_glove_ready --plan NEW_PLAN --out NEW_RUN --startup-timeout 60
python -m intent.local_glove_observer_report --run NEW_RUN --out NEW_REPORT
```

기기별 계획은 `intent.local_glove_plan`으로 새로 만든다. 이번 추출 구현 변경으로 코드 해시가 바뀌므로
이전 계획의 검사 기록을 새 실행에 재사용하지 않는다. CV6의 26장 실제 사람 검토와
CV7 미열람 독립 검증은 별도다. 범용 글러브 후보를 확정 미트로 승격하지 않는다.

새 회귀 19건(실제 FFmpeg 합성 영상 2건 포함)과 기존 계약/체크리스트를 합쳐 140 passed.
실제 디코더 검사는 `INTENT_TEST_FFMPEG`에 FFmpeg 실행 경로를 설정하면 활성화되며,
추가 다운로드 없이 임시 합성 영상을 만든다. 환경변수가 없으면 해당 2건만 건너뛴다.

## 실제 결과 — 2026-10-07

규약과 구현을 `d1e2c4f`로 커밋·푸시한 뒤 실행했다. 14장 각각 두 방식으로 한 번씩 추출했고,
모델 관측 루프는 새 방식으로 한 번 실행했다. 비교 중 별도 모델/테스트 작업은 실행하지 않았다.

| 항목 | 기존 | 개선 후 | 범위 |
|---|---:|---:|---|
| 같은14장 추출 시간 중앙 | 2.185초 | 0.848초 | 입력·출력 해시 검사 포함, 순서를 교대한 쌍별 비교 |
| 예정→검증 발행 중앙 | 5.375초 | 3.883초 | CV23 저장 실행과 같은 입력·모델의 새 실행 비교 |
| 예정→검증 발행 최대 | 9.859초 | 4.047초 | 모델 연산 단독 시간이 아님 |
| 5초 이내 발행 | 5/14 | 14/14 | 로컬 개발 일정 기준, 실제 중계 보장 아님 |
| 입력 전 준비 | 20.359초 | 18.563초 | 합성 입력5회 포함 |
| 전체 명령 | 99.922초 | 92.192초 | 65초 입력 일정·준비·정리 포함 |

추출 중앙값은 61.2% 줄었다. 14/14 프레임의 PTS·duration·size·MD5와 JPEG SHA가
서로, 그리고 CV23 저장 원본과 일치했다. 구간별 시간으로도 추출 비용 감소를 확인했다.
표의 루프 지연 비교는 실행 시점이 다른 과거 결과와의 비교이며, 무작위 교차 반복 실험이나
새 기기의 성능 보장은 아니다.

새 루프는 수락14/14·오류0·미시도0다.
단일 후보5·복수1·후보 없음8과
후보 좌표는 기존14개 모두 동일했다. 확정 미트는 **0**으로 그대로이며
속도 개선을 판독 정확도나 운영 채택으로 해석하지 않는다. 방송 구간 종료 뒤 발행된
응답 1개도 기록에서 유지했다. worker 정상 종료.

관련140tests와 전체 CPU **1667 passed, 5 skipped, 2 deselected, 2 warnings in 407.57s (0:06:47)**, Ruff145경로 통과. 전체 검사에는 별도 환경변수로
실제 FFmpeg 합성 영상2건을 포함했다. 모델·MLB 원본 다운로드는 하지 않았다.
동일 구현 `d1e2c4f`의 [원격 Linux/macOS 검사](https://github.com/Pitcheezy/transition-models/actions/runs/37588484216)도
각각1664 passed·8 skipped·2 deselected로 통과했다. 원격검사의8 skipped에는 위 디코더2건이
포함되므로 실제 디코더 검증은 Windows 결과다. macOS CI는 맥미니 실기기 모델 성능과 구분한다.
M3 고정 입력25개 SHA 불변. 팀원 저장소·API·사이트·기존 JSONL 변경 없음.

[쌍별 추출 결과](results/cv_local_20261007/exact_seek_comparison_v1.json) ·
[모델 루프](results/cv_local_20261007/exact_seek_model_report_v1.json) ·
[실행 감사](results/cv_local_20261007/exact_seek_run_audit_v1.json) ·
[요약](results/cv_local_20261007/exact_seek_summary_v1.json) ·
[검사 기록](results/cv_local_20261007/exact_seek_validation_v1.json)

## 남은 우리 작업

1. **CV6 실제 사람 판정:** 준비된26장 검토 응답을 받아 검사·집계한다. 기존86장 평가의
   일부를 새 기준으로 다시 보는 것이므로 표본이26장 늘어나는 것은 아니다.
2. **CV5a 미트 판독 품질:** 새 중심점·가시성·자세·기권 라벨로 포수 미트 전용 모델의
   개발 기준을 고정한다. 현재 범용 탐지기와 작은 점 예측기는 채택하지 않는다.
3. **CV7 독립 평가:** 개발에 쓰지 않은 연속 영상과 독립 사람 라벨을 확보한다.

CV6 응답은 원본SHA와 픽셀 좌표로 다시 연결할 수 있으므로 점 기반 학습을 위해 같은
중심을 다시 클릭할 필요는 없다. 옛/새 판정은 따로 보존한다. unknown/unreviewed는 학습
정답에서 제외하고 unavailable은 미트 부재가 아니라 중심을 판독할 수 없다는 뜻으로 유지한다.
현재 라벨에는 박스·마스크가 없으므로 중심점으로 정답 박스를 만들어서는 안 된다.
추가 속도 반복 대신 이 품질 단계에 집중한다.
