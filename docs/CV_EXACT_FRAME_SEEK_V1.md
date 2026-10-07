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
