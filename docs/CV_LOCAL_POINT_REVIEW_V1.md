# 84장 전체 로컬 점 비교 — CV-16

CV-15의 기존 표시 84장 모두를 원본 JPEG, 기존 사람점, 선택 seed 모델점, crop 중심,
학습 경기 평균과 함께 탐색한다. 좋은 사례만 선별하지 않으며 기본 seed는 42다.
경기/프레임/seed 선택, 앞뒤 이동, 각 표시 끄기, 원본만 보기를 제공한다.
프레임 원본 픽셀 좌표로 겹쳐 보여주고 모델이 학습한 반대 경기와 거리 단위를 표시한다.

로컬 파일: `outputs/cv_local_point_review_v2/index.html`.
v1은 키보드 보조키 수정 전 파일로 보존한다. 새 v2는 학습/예측 결과를 바꾸지 않았다.
원본 JPEG 바이트를 HTML에 내장하며 외부 요청·모델 호출·라벨 저장 기능은 없다.
Git 및 공개 사이트에 MLB 이미지가 포함된 이 HTML을 올리지 않는다.

```bash
python -m intent.local_point_review --manifest outputs/cv_local_dataset_v1/manifest.json --references outputs/cv_local_dataset_v1/references.json --report outputs/cv_local_point_run_v1/report.json --out outputs/cv_local_point_review_NEW
python -m http.server 8786 --bind 127.0.0.1 --directory outputs/cv_local_point_review_v2
```

브라우저에서 `http://127.0.0.1:8786/`를 연다. 생성에는 private 실행 report와 그 옆의
plan/ledger/training/evaluation 해시 결속 파일 및 원본 이미지가 필요하다.
공개 보고서 JSON만 복사해서 생성할 수는 없다. 이미 만든 단일 HTML은 원본 파일 경로에
의존하지 않지만 다른 기기의 브라우저 동작은 이번에 검사하지 않았다.

합성 검사 28 passed·Ruff·JavaScript 구문 검사, 실제 84장 생성 성공(추가 모델 호출 0).
Windows 로컬 브라우저에서 그림/범례, 경기·seed 선택, 원본 보기, 프레임 이동을 확인했다.
`823407:1:3`, `823407:4:2`, `849845:10:4`는 화면 동작 확인 예시이며 별도 사람 라벨이 아니다.
모바일은 미검사. 직접 file URL은 브라우저 도구의 프로토콜 정책으로 검사하지 못했다.
우회하지 않았으며 확인된 실행 방식은 위의 localhost다.

[바이트·검수 기록](results/cv_local_20261007/point_review_receipt_v1.json),
[모델 결과](CV_LOCAL_POINT_MODEL_V1.md). 사람 표시 자체가 현재 관측 규약의 확정 정답이라는 뜻은 아니다.
