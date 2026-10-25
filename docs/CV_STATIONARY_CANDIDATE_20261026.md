# CV-38 — 현재 추적과 과거 멈춤 후보의 분리

## 착수 기준 (실행 전 고정)

2026-10-26, 우리 `73bbce75e12d1e8f28ef2c98085d486112396249`의 CV37 v3에 의존하는 별도 연구 브랜치 `codex/cv-stationary-candidate-1026`이다. 구현 Codex, 고정 소스의 별도 Claude Fable 검토를 받는다. 기존 `mitt_temporal.run`은 마지막 후보를 현재 후보 필드에 계속 보존하므로 이를 새 추적 경로에 재사용하지 않는다. 기존 보고·판독·평가 결과는 수정하지 않는다.

합격 기준:

1. 저장된 PatchTracker 행만 받는 인과적 선택기. 단일 투구·증가하는 시각/프레임·유한 좌표·추적 상태를 검사하고 잘못된 입력은 상태 변경 전에 거부한다.
2. `current_track_point_px`, 현재 연속 구간의 `current_candidate`, 과거 발생 기록 `last_historical_candidate`를 분리한다. 움직임/가림/추적 소실/간격 단절에서 현재 후보를 즉시 비우고 과거의 발생 시각·좌표를 보존한다.
3. 사전 고정 개발값: **0.30초 이상, 관측 4개 이상, patch_continuity 2개 이상, 간격 최대 0.25초, 구간 전체 축 정렬 경계상자의 대각선 최대 8px**. 720p 원본 픽셀 기준이며 다른 해상도로 자동 적용하지 않는다. 반경 8px와 다르다. 범위를 넘으면 현재 점부터 새 구간을 시작한다. 원점을 누적 이동시키지 않는다.
4. 한 구간에서 최초 조건 충족 때 사건을 한 번 기록한다. 현재 후보는 현재 행의 위치/시각을 사용하고, 과거 사건은 최초 발생 당시 값으로 고정한다. 잃은 추적의 자동 재획득은 하지 않는다. 새 선택기/새 tracker 쌍으로만 재시작한다.
5. 고정 CV37 v3 CPU/CUDA 각625행·10구를 같은 파라미터로 각각 재생한다. 입력 SHA·불변성, 출력 일치, 현재/과거 분리와 마지막 소실 상태를 확인한다. 후보 수가 많아지는 것은 합격 기준이 아니며 결과를 보고 문턱을 조정하지 않는다.
6. 경계·거부·부분 상태 변경·prefix 불변·누적 drift·반대 방향 진동 검사를 수행하고 실제 다른 모델의 고정 소스 검토와 지적 처리를 기록한다.

좌표는 **추적한 패치의 기하학적 멈춤 후보**다. 미트 식별·포수 목표 자세·투수 의도·물리 정확도·독립 사람 평가가 아니다. 잘못된 초기 점도 안정적으로 추적되면 후보가 생길 수 있다. 원래 관측은 수정하지 않으며 릴리스 시각·실제 결과·향후 영상은 선택기에 넣지 않는다. 공개 계약·팀원 레포/프로세스·운영 배포·옛 질문 발신·삭제 작업은 범위 밖이다.

## 실행 결과

고정 v3의 CPU/CUDA 각625행·10구를 새 파라미터로 재생했다. 5구에서 사건6개, 현재 후보92행, 과거 후보만 남은197행, 아직 지지 부족31행, 추적 불가502행이다. 10구 모두 마지막에는 lost이며 현재 후보0개다. CPU/CUDA 입력에서 선택 결과625행이 모두 같았고, 입력3파일 SHA가 전후 같았다. 새 보고와 행은 `outputs/cv_mitt_stationary_20261026_v1/`, 공유 가능한 집계는 [report_v1.json](results/cv_stationary_20261026/report_v1.json)에 있다.

현재 후보를 관찰한 구간 길이는 마지막 유효 표본까지만 계산한다. 후보6개의 관측 길이는0.5005~2.6026초다. 다음 프레임까지 유지됐다고 보간하지 않는다. 선택기 자체는 표준 Python이며 CPU/CUDA는 기존 입력을 만든 장치 이름이다. 이 재생에는 새 의미/자세/view gate를 추가하지 않았다. `usable=False` 입력의 즉시 해제는 합성 경계 검사로만 확인했다.

신규79검사와 기존 추적/체크리스트38검사를 합친 **117 passed (17.44초)**, 신규4파일 Ruff 통과. 최초 기본 임시 폴더 권한 오류15건은 새 작업용 임시 폴더로 재실행해 해소했다. 실제 Claude 고정 소스 검토는 다음 단계이며 아직 수신 전이다.

재현 (저장 자료는 비공개 Git 제외 경로):

```sh
python -m intent.mitt_stationary_pilot --tracking-report docs/results/cv_tracking_20261026/report_v3.json --report-sha256 6979e4b921afe2f978fd83e89755ec65fea9e74db6a1c794606fa942e80002b3 --cpu outputs/cv_mitt_tracking_20261026_v3/records_cpu.json --cuda outputs/cv_mitt_tracking_20261026_v3/records_cuda.json --out <새 출력 폴더>
python -m pytest -q tests/test_mitt_stationary.py tests/test_mitt_stationary_pilot.py tests/test_mitt_tracking.py tests/test_mitt_tracking_pilot.py tests/test_checklist_model.py
```

현재/과거 계약: `current_track_point_px`는 해당 행의 유효 위치, `current_candidate`는 현재 안정 구간의 **현재 시각·현재 좌표**, `event`는 처음 충족한 순간에만 발생, `last_historical_candidate`는 마지막 사건 당시의 스냅샷이다. `available_seconds`보다 이전에 알려졌다고 표시하지 않는다. UI는 역사 필드를 현재 마커로 사용하면 안 된다. `usable=False`는 호출자가 현재 프레임의 가림/뷰 부적합을 알려주는 옵션이며 추적 lost를 되살리지 않는다.
