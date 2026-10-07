# 로컬 미트 관측 후보 개발 비교 — 2026-10-07

CV-12에서 기존 86장의 원본·사람 라벨 연결을 검증하고 로컬 관측 후보를 준비했다.
실제 개발 비교는 CV-13으로 구분한다. 팀원 모델/API·사이트·기존 M3·JSONL은 고정한다.
잔여 사용량 20% 하한을 유지한다.

## 데이터와 비교 의미

823407의 29장(표시 28·기권 1), 849845의 57장(표시 56·기권 1), 원본 SHA 86/86과
pack ID·raw/imported 라벨 연결이 일치한다. 모두 1280×720 JPEG이고 84점은 원본 좌표다.
기존 기권은 not_centre_field/not_in_setup으로, 현행 미트 부재 음성이 아니다.
기존 UI/추가 채팅 지시와 현행 미트 몸체 정의가 완전히 같다는 보장이 없다.
따라서 단일 라벨러의 기존 기준점과 조건부 위치 차이를 비교하며 새 정확도라고 하지 않는다.

같은 86장에 두 후보를 각각 전체 화면과 기존 고정 crop으로 적용한다.
SSDLite320 MobileNetV3와 고해상도 Faster R-CNN MobileNetV3의 공식 COCO_V1 가중치를
전체 SHA로 고정했다. 클래스 40은 baseball glove다. 투수 글러브와 포수 미트를 식별한 결과가 아니다.
점은 검출 상자의 중심 대리값이고 crop은 사람이 정한 카메라 영역이다.
0.5 이상 후보가 정확히 하나일 때만 좌표를 만들며, 여러 개면 기권한다.
사람 점과 가까운 후보를 고르지 않는다. 임계값·crop을 결과를 보고 바꾸지 않는다.

GPU 네 조건을 순서대로 각 3회, 미리 정한 Faster R-CNN crop CPU 조건을 1회 실행한다.
각 조건 첫 회만 위치 비교에 사용한다. 나머지는 반복 처리시간이며 추가 독립 표본이 아니다.
사전 통합 점검은 모델별 검은 이미지 1장, 총 2회였고 두 모델 모두 GPU에서 기권을 반환했다.
실제 86장의 영상 내용은 사전 통합 점검에 사용하지 않았다.

[입력 감사](results/cv_local_20261007/dataset_audit_v1.json),
[호출 전 고정 규약](results/cv_local_20261007/detector_preregister_v1.json).
이 문서 최초 커밋은 실제 86장 모델 호출 전이다.

## 재현과 유지보수

`uv sync --frozen --extra local-cv`로 선택 의존성을 설치한다. 기존 torch 버전은 유지한다.
Windows/Linux는 torch 2.6.0/torchvision 0.21.0, Mac은 2.8.0/0.23.0을 고정한다.
Mac 실제 실행 성능을 이번 Windows 결과로 대신하지 않는다.

`python -m intent.local_detector_data --results-dir docs/results/mlb_p0 --frames-root . --out outputs/cv_local_dataset_NEW`

위 명령은 검증된 전체 이미지 목록과 사람 기준점을 별도 파일로 만든다.
추론기는 manifest만 읽으며 사람 기준점은 평가 도구만 읽는다.
가중치는 공식 URL에서 따로 받아 SHA를 확인하고 로컬 경로로 제공한다. 추론 중 다운로드·장치 대체는 없다.
Torchvision 코드의 BSD-3 라이선스와 사전학습 가중치/원데이터의 조건을 동일하게 단정하지 않는다.

`python -m intent.local_glove_benchmark --plan PLAN.json --out outputs/cv_local_run_NEW`

`python -m intent.local_glove_report --manifest MANIFEST.json --references REFERENCES.json --predictions PREDICTIONS.json --out NEW_REPORT.json`

재실행은 새 경로를 사용한다. 원본 이미지·기기별 계획·가중치·개별 실행 파일은Git 제외다.
보고서는 원본을 재검증한 입력 감사와 저장 JSON 결속 검사 범위를 구별한다.
상세 모델 처리와 전체 서비스 시간, 초기 모델 로딩을 분리하고 개별 실패·미시도도 분모에 남긴다.

실행시간은 고정 정지화면을 미리 준비한 로컬 실험이다. 영상 수신·자동동기화·투구 연결·실시간
중계 가용성은 측정하지 않는다. CV-5a4/6/7의 전체 타석·추가 사람·미열람 독립 검증은 별도로 남긴다.

## 준비 검증

실제 연구 프레임 호출 전 검사: 관련 212 passed, 전체 CPU 검사 1,331 passed / 5 skipped / 2 deselected.
Ruff 121경로 통과. 별도 읽기 전용 검토에서 다섯 계획과 코드·가중치·원본 86장 해시, 분모와
공개 문서의 경로 노출 여부를 재확인했다. 이 단계의 연구 프레임 모델 호출은 0회다.
