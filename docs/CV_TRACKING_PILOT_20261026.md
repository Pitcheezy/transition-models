# CV-37 — 시간순 국소 추적 개발 (2026-10-26)

사용자는 CV 고도화의 즉시 착수와 내부 일정 단축을 요청했다. [착수 전 합격 기준·고정 후보](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6401534435). 기준 PR69 `c41eb74782d585cce47d2f1d99b4417ea2f4623e`, 작업 `codex/cv-track-pilot-1026`. PR67/69 연구에 의존하며 main 병합·운영 배포·Song 코드 변경은 포함하지 않는다. 원래 Claude 폴더/자료는 읽기만 한다.

## 목표와 한계

초기 AI 점에서 같은 영상 패치가 이어지는지 계산한다. **추적 성공은 미트 식별 성공이 아니다.** 정지한 잘못된 물체도 통과할 수 있다. 사람 정확도·투수 의도·실시간 서비스 지연은 미측정이다. 기존의 미트 좌표, M3, timing, IntentEstimate와 사람 응답은 고정한다.

`intent/mitt_tracking.py`는 현재 프레임까지의 uint8 단색 영상만 사용한다. 원본 좌표와 crop 원점을 분리하며 배율 변경은 하지 않는다. 초기화는 원본 점을 반올림(0.5 올림)한 정수 위치이고 요청 점도 보존한다. NCC는 각 후보 패치의 분산으로 정규화한다. 고정 초기 템플릿을 사용해 임의 적응을 막는다. 현재 후보 패치를 이전 프레임으로 되찾는 왕복 검사, 저질감·낮은 유사도·서로 떨어진 유사 봉우리·검색 경계·큰 화면 변화·시간 공백으로 기권한다. 큰 화면 변화는 휴리스틱이며 검증된 장면 분류기가 아니다.

상태는 unseeded → tracking → lost다. lost는 현재 점 null이며 자동 재초기화하지 않는다. 새로운 외부 seed는 새 인스턴스를 사용한다. 서로 다른 투구/역순 프레임/NaN 시각을 거부한다. 미래 프레임이 과거 출력에 영향을 주지 않아야 한다.

## 실행 전에 고정한 개발 비교

- 기존 CV33 첫10구를 유지한다. 기존 sequence 판독315행을 사용하고 v0_reread10장은 제외한다.
- 구별 최초의 적격 기존 AI 점 하나로만 초기화한다. 이후 AI 점은 비교 자료이며 재탐색/정답으로 사용하지 않는다. 결과를 보고 seed를 바꾸지 않는다.
- 모든 원래 grid 프레임 중 기존 release-nearest index 이하를 시간순 처리한다. 릴리스는 평가 창에만 쓰며 추적기는 받지 않는다.
- 원본 `frame_*.jpg`의 SHA/크기/1280×720/PTS를 확인한다. 노란 좌표 격자가 있는 `crop_*.jpg`는 절대 추적 입력으로 사용하지 않는다. 무표식 crop330,100,950,600만 적용한다.
- 템플릿21px·검색반경24px·NCC0.65·봉우리차0.05(주변4px 제외)·왕복오차3px·질감0.03·화면차0.22·간격0.25초. 변경하면 별도 후보/새 결과로 기록하고 기존 실행을 보존한다.
- 새 모델 호출, 재학습, 새 영상, 유료 클라우드 자원 없이 진행한다.

## GPU와 측정 범위

실제 노트북 확인: RTX4070 Laptop GPU, 8188MiB VRAM, PyTorch2.6.0+cu124, CUDA runtime12.4, CUDA 사용 가능. 기존 환경을 사용하며 드라이버·전력 설정·의존성을 바꾸지 않았다.

CPU4스레드, float32, TF32 OFF, cuDNN benchmark OFF/deterministic ON으로 비교한다. CUDA 타이머 전후 synchronize, 첫 합성 연속16프레임은 워밍업, 이후 동일16프레임 3반복에서 초기화와 추적을 분리한다. 합성 sustained 추적 시간은 이미 디코딩된 픽셀의 전송/연산/CPU 결과 회수를 포함한다. 실제 개발 재생은 JPEG 읽기·SHA·디코딩·crop과 추적 처리 시간을 나눠 적는다. CPU 후 GPU 실행 순서/파일 캐시 영향이 있어 디코딩 속도차를 GPU 효과라고 주장하지 않는다. 실제 재생은 실패 후 빠른 lost 행이 많을 수 있으므로 active attempt와 전체 시간을 구별한다.

```text
python -m intent.mitt_tracking_pilot --bundle <saved-bundle> --pilot <saved-pilot> --out outputs/cv_mitt_tracking_20261026_v1 --devices cpu cuda
python -m pytest -q tests/test_mitt_tracking.py tests/test_mitt_tracking_pilot.py tests/test_mitt_temporal.py tests/test_mitt_pilot.py tests/test_checklist_model.py
```

입력은 기존 Claude 개발 폴더의 bundle_v1/pilot_v1이고 출력은 이 연구 작업 폴더의 새 경로다. 원본 SHA/PTS와 frame별 원 AI 점, 현재 추적 점, 기권 이유를 함께 보존한다. 새 records는 비공개 출력이며 집계 report만 공개 기록에 넣는다. AI와의 거리 차이는 정확도가 아니다.

## 앞당긴 내부 일정

-10/28 CV37 추적·기권·CPU/GPU 비교.
-11/1 CV38 유효 구간에서 멈춤 후보·현재/과거 표시 분리.
-11/5 CV39 PTS/투구 연결·OCR 연속성·로컬 한 타석 통합.
-11/9~12 CV40 고정판 새 경기 평가. 새 영상·검토 기준·호출 비용 조건 필요.
-11/15 CV41 연구 기능 동결 목표,11/16~23 리허설/수리,11/24 전시. 기존11/20 최종 동결선은 여유.

이는 우리 내부 목표이며 Song의 약속/일정 변경이 아니다. 실제 공동시험·접근/배포·11월 비용/실부하는 별도 조건이다. CV35/36 사람 평가를 AI 합의로 완료하지 않는다. 판단 불가는 음성 정답과 구별한다. 실제 GPT/Claude 검토 모델·커밋·결과를 기록하고 같은 모델의 다른 에이전트만으로 다른 모델 검토 완료라고 하지 않는다.
