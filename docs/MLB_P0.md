# MLB 우선 개발 — P0 실행 안내

최종 제품은 투구 전 중계 상황을 인식하고 구종·위치별 확률을 보여주는 시스템이다.
먼저 MLB로 완성하고 KBO로 확장한다. 이 문서는 **수동 입력 단계**의 실행·검증 범위를 설명한다.

## 현재 가능한 것

- 2024-09-30 NYM@ATL, 경기 ID **747139**, 322개 투구의 Statcast 키와 MLB `playId` 연결.
  투수·타자·구종도 대조했다. 목록 순서나 기존 영상 파일명을 정답으로 사용하지 않는다.
- MLB 공식 전체 경기 입력: 9,340.748초, 1280×720, 약 59.94fps.
  ffprobe 점검과 Chrome 실제 재생을 확인했다. 약 4.9GB 전체 파일은 내려받지 않았다.
- 첫 투구 클립은 6.594초이며 0·2초에 준비 동작, 3초에 투구 동작이 관찰된다.
  정확한 릴리스 시각은 아직 주석을 달지 않았다.
- 전체 경기는 **SNY/좌상단 점수판**, 확인한 투구 클립은 **Bally/하단 점수판**이다.
  같은 경기라도 방송사·화면 형식을 공유한다고 가정하지 않는다.
- 실제 저장된 운영 MLP 앙상블을 로드하는 수동 입력 웹 화면과 HTTP API.
- 스트라이크·볼·파울을 분리할 새 8종 정답과 투구 ID 기반 학습 준비 파일.
- 중계 재생 시각 주석 도구와 검증 CLI: 297개 시각 확인, 25개 판단 화면 확인 불가,
  0개 미검토(2026-09-27, 전 경기 검토 완료). 점수판 리뷰 297개 중 292개 전 필드 확인·5개 부분 판독.
  [주석 결과와 실행 방법](MLB_BROADCAST_TIMING.md).
- 서로 다른 확률 클래스의 이름·순서·의미를 검사하는 독립 모듈과 [계약 안내](OUTCOME_CLASS_CONTRACTS.md).
  동료 서비스 실연동·새 모델 검증을 완료한 것은 아니다.
- PA6의 선수 이름 평가 준비: 투구 전 6프레임·12역할 중 투수6/6, 타자5/6의 이름을 수동 확인했다.
  첫 투구의 타자 이름은 기권이다. [선수 식별 규약](PLAYER_IDENTITY_PROTOCOL.md)은 실제 화면 문자열과 최종 feed의
  기준 ID를 분리한다. [이름 OCR 기준선](PLAYER_IDENTITY_OCR.md)과 별도 예측/채점 경로도 추가했다.
  Windows OCR을 사용한 이 PA6 개발 결과이며 일반 선수 인식·실시간 선수 추적은 아직 검증하지 않았다.

## 시연 실행

저장소 루트에서, 기존 운영 데이터와 모델 파일이 있는 환경을 사용한다.

```bash
uv sync --frozen
uv run --frozen python scripts/59_serve_manual_demo.py --with-example-video
```

Chrome에서 `http://127.0.0.1:8770`을 연다. 기본 포트가 사용 중이면 `--port 8771`로 바꾼다.
이번 Windows 환경에서는 Codex 내장 브라우저가 동영상 재생 시 종료됐으므로 영상은 Chrome을 사용한다.
모델 계산 화면 자체는 내장 브라우저에서도 확인했다. 다른 브라우저/기기 재생은 미검증이다.

1. 예시 상황을 불러오거나 투구 전 상황을 직접 입력한다.
2. **이 상황으로 확률 계산**을 누른다.
3. 구종을 선택해 10종 결과 확률과 피안타 확률을 비교한다.
4. 입력을 바꾸면 이전 추천은 즉시 사라지며 다시 계산해야 한다.
5. 영상 재생은 수동 입력과 독립적이다. 자동 OCR·시각 동기화가 있는 것처럼 발표하지 않는다.

영상 없이 실행하려면 `--with-example-video`를 생략한다. 다른 입력은 `--video-url URL`로 지정한다.
로컬 서버는 127.0.0.1에만 바인딩하며 원격 공개 서버로 운영하는 구성은 아니다.
연결마다 독립 처리하고 읽기 제한은 5초다. 모델 계산은 한 번에 하나만 실행하며,
계산 중에도 health 조회와 화면 파일 요청은 응답한다.

## 필요한 로컬 파일

Git에 새 모델·원본 영상·대용량 데이터는 넣지 않는다. 다른 컴퓨터에서는 아래 아티팩트를
옮기거나 [운영 검증 가이드](OPERATIONAL_VALIDATION_2026-09-21.md)의 명령으로 재생성한다.

- `data/operational_20260921_v2/`: `feature_builder.pkl`, `dataset_manifest.json`, `run_value_model.npz`
- `outputs/operational_20260921/evaluation/`: `probability_report.json`, `empirical.pkl`
- `outputs/operational_20260921/mlp135_seed42/`, `mlp135_seed43/`, `mlp135_seed44/`:
  각 폴더의 `manifest.json`, `best.pt`
- `outputs/operational_20260921/policy_nuisance_v2/`: `manifest.json`, `propensity.txt`

경로가 다르면 `--data-dir`, `--evaluation-dir`, `--nuisance-dir`, `--runs-dir`를 지정한다.
구형 `model_b3_focal_135dim_10cls_best.pt`를 이 서비스에 넣어 대체하면 안 된다.

## 영상 자료 점검 재현

원본 `data/raw/2024/statcast_2024.parquet`와 인터넷 연결이 필요하다.
`--probe`에는 PATH에 설치된 FFmpeg의 `ffprobe`가 필요하다. 설치하지 않았다면 옵션을 생략한다.

```bash
uv run --frozen python scripts/60_prepare_mlb_demo_sources.py --probe
```

`data/raw/mlb_video/747139/`에 공식 feed, 페이지 스냅샷, ID manifest, 입력 점검 결과를 저장한다.
캐시를 새로 받으려면 `--refresh`를 사용한다. 전체 영상이나 모든 클립을 자동 다운로드하지 않는다.

네트워크 없이 기존 스냅샷으로 ID 검증만 다시 수행:

```bash
uv run --frozen python scripts/58_build_mlb_video_manifest.py --statcast data/raw/2024/statcast_2024.parquet --feed data/raw/mlb_video/747139/feed.json --output data/raw/mlb_video/747139/manifest.json
```

확인된 결과는 [game_747139_manifest.json](results/mlb_p0/game_747139_manifest.json)과
[media_inspection.json](results/mlb_p0/media_inspection.json)에 있다.
`event_start_utc`는 경기 feed의 시각이며 방송 영상의 재생 초나 릴리스 시각이 아니다.
원본 ID manifest의 `broadcast_offset_seconds`는 null로 유지한다. 확인한 재생 시각은
출처·manifest 해시를 묶은 별도 [주석 파일](results/mlb_p0/game_747139_timing.json)에 보관한다.
322개 전부의 영상 존재·길이·연속성까지 검증한 것은 아니다.

## 새 정답 정의

```bash
uv run --frozen python scripts/61_audit_pitch_observations.py --output outputs/pitch_observation_audit.json --targets-dir data/processed/pitch_observation_v1
```

`pitch_observation_v1`의 8종: 볼, 루킹 스트라이크, 헛스윙 스트라이크, 일반 파울/번트 파울,
잡힌 파울팁, 안타, 인플레이 비안타, 몸에 맞는 공.
삼진·볼넷 등의 타석 종료 사건은 별도 `pa_event`로 보존한다.
2스트라이크 번트 파울을 일반 파울과 같은 상태 전이로 처리하면 안 된다.
향후 표시용 스트라이크는 루킹+헛스윙+잡힌 파울팁의 합으로 정의하고 일반 파울은 분리한다.
인플레이 비안타에는 실책·야수선택 등이 있어 반드시 아웃이라는 뜻은 아니다.

2022–2024 정규시즌 **2,142,792행**을 점검해 **2,135,726행**에 정답을 부여했다.
자동 볼·스트라이크 6,796행과 포수 방해 270행은 사유를 남겨 제외했다.
이것은 정답 정의·전처리 검증이며 새 모델의 성능 결과가 아니다.
기존 10종 체크포인트를 8종으로 이름만 바꿔 사용하지 않는다.
[전체 집계](results/mlb_p0/observation_audit.json), [입출력 규약](PREPITCH_CONTRACT.md).

## 검증과 남은 작업

```bash
uv run --frozen python scripts/check_project.py --cpu-only
node --check src/web/static/app.js
```

2026-09-22 Windows CPU 검사: **264 passed, 2 deselected**, Ruff 47개 경로 통과.
2개 제외 항목은 MPS 하드웨어 테스트다. GitHub의 Linux/macOS CPU CI 결과는 커밋별로 확인한다.

실제 모델 예시: 슬라이더 추천, 해당 구종의 다음 투구 피안타 확률 약 7.12%.
브라우저에서 관찰한 서버 계산 시간 약 92–113ms는 소수 수동 실행 결과다.
영상 인식이나 전체 처리 지연의 벤치마크로 일반화하지 않는다.

59번 서버를 실행한 상태에서, 다른 터미널에서 경기의 322개 기록 상태를 모두 실제 HTTP API에
입력하는 점검을 실행한다. 포트를 바꿨다면 `--server-url http://127.0.0.1:8771`을 지정한다.

```bash
uv run --frozen python scripts/62_check_game_service.py --output outputs/game_service_smoke.json
```

322개 모두 확률 계산과 유효성 검사를 통과했다. **188개 추천, 134개 보류**다.
보류는 과거 구종 자료가 부족한 투수의 94개와 정책 평가 범위 밖인 9회 이후 40개다.
한 경기만으로 운영 전체의 추천 가능 비율을 추정하지 않는다.
[결과와 계산 시간 범위](results/mlb_p0/game_service_smoke.json)를 보존했다.
이 점검은 기록된 투구 전 상태를 쓰며 영상 OCR이나 새로운 예측 정확도 검증은 아니다.

검사 도구는 표준 라이브러리만 사용하며 실제 브라우저와 같은 API를 호출한다.
별도 프로세스에서 모델을 직접 중복 로드한 진단에서는 첫 Arrow 문자열 변환이 멈추는 현상도
관찰했다. 선행 pandas 초기화로 끝까지 실행된 경우가 있었지만 근본 원인은 확정하지 못했다.
지원하는 59번 서버 시작·실제 API 경로는 검증했으며 직접 임베딩할 때의 초기화 문제는 추가 조사한다.

미완료(전체 목록과 진행 상태는 [../CHECKLIST.md](../CHECKLIST.md)):

- 기존 오타니 영상 원본 전체의 ID 재검증(이번에는 저장소 코드와 새 경기 ID 연결을 확인).
- 경기 시점 이전 자료만으로 투수 프로필 갱신 및 신규 투수 처리(고정 2022 프로필의 한계).
- 전체 경기 재생 시간 ↔ 투구 시각 주석 확대(68개 확인, 4개 확인 불가, 250개 미검토; 2026-09-24).
- 새 8종 모델 학습·보정. 현재 화면의 독립 스트라이크·볼·파울은 미지원(null).
- 타자 세부 특성, 목표 위치와 제구 오차, 자동 점수판·선수 인식, 실시간 상태 추적.
- 실제 추천이 실점을 줄이는지 검증. 현재 구종 정책의 개선 효과는 미입증.

## Codex / Claude 교대

[MLB_P0_HANDOFF.md](MLB_P0_HANDOFF.md)를 공통 작업 기록으로 사용한다.
한 번에 한 도구만 파일을 수정하고, 검증한 단위마다 커밋·푸시한다.
현재 교대 시작점은 [CODEX_RESUME_PROMPT.md](CODEX_RESUME_PROMPT.md)와 CHECKLIST의 수정 권한·다음 단위다.
Claude도 같은 재개 절차를 따르되 작업자 이름과 CHECKLIST의 Claude 모델 배정을 적용한다.
초기 인증·자동 승인 제한은 2026-09-22의 기록이며 현재 승인 대기 상태를 뜻하지 않는다.
[초기 Codex 로컬 검토 기록](MLB_P0_REVIEW_2026-09-22.md)과 이후 실제 교대 결과는 공통 인계 문서를 참조한다.
