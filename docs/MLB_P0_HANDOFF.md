# MLB P0 — Codex / Claude 인계 기록

현재 범위는 MLB 우선 개발이다. KBO는 최종 확장 목표로 유지한다.
2026-09-22 Codex가 아래 코드를 구현·검증했다. Claude의 첫 호출은 OAuth 만료(401)로
실행되지 않았으며, 사용자 재로그인 확인 전에는 Claude 리뷰 완료로 기록하지 않는다.

## 교대 원칙

- 한 번에 한 도구만 코드를 수정한다. 다른 도구는 명시한 커밋을 읽고 리뷰한다.
- AGENTS.md, docs/MLB_P0.md, docs/PREPITCH_CONTRACT.md,
  docs/OPERATIONAL_VALIDATION_2026-09-21.md를 먼저 읽는다.
- 브랜치는 `codex/fix-point-label-alignment`. 검증한 단위마다 커밋·푸시한다.
- 원본 영상, 데이터, 모델 캐시, 로그인 정보는 새로 Git에 넣지 않는다.
- 독립 스트라이크·볼·파울 확률과 목표 위치는 현재 미지원이다. 0으로 대체하지 않는다.

## 완료한 체크포인트

1. `6fe5fbc`: 경기 747139의 322개 투구를 공식 feed와 Statcast ID로 연결했다.
   투수·타자·구종을 대조하며 중복/누락/충돌은 성공으로 처리하지 않는다.
2. `bb4fa75`: 엄격한 투구 전 상태 규약과 CLI/웹 공통 추천 서비스를 구현했다.
   기존 Strike에 파울이 포함되는 의미 문제를 드러내고 지원 범위 밖 추천을 보류한다.
3. 수동 웹 시연: 실제 운영 MLP 앙상블 → 구종 후보별 확률 → 추천 → 화면까지 연결했다.
   예시 SL 추천 / 피안타 약 7.12%. 입력 변경 시 기존 결과를 지운다.
4. 공식 MLB 전체 경기 입력과 첫 투구 클립을 점검했다. Chrome 실제 영상 재생 확인.
   전체 파일은 저장하지 않았으며 Codex 내장 브라우저 영상 재생은 실패했다.
5. 자료 점검 재현 CLI와 별도 8종 투구 관찰 정답 생성기를 추가했다.
   정규시즌 2,142,792행 중 2,135,726행 정답 생성, 자동 판정 6,796행 및 포수 방해
   270행 제외, 알 수 없는 유형 0행. 기존 10종 모델을 수정하거나 재학습한 결과는 아니다.

이 문서와 함께 추가되는 후속 커밋의 해시는 `git log -6 --oneline`으로 확인한다.
전체 Windows CPU 검사: **235 passed, 2 deselected**, Ruff 43개 경로 통과.
JavaScript 구문 검사 및 Chrome 수동 입력·실제 추론·9회 이후 추천 보류 확인.
GitHub CI 결과는 해당 커밋의 validation 워크플로에서 따로 확인한다.

## 바로 실행하기

기존 운영 아티팩트가 있는 저장소 루트에서:

```bash
uv run --frozen python scripts/59_serve_manual_demo.py --with-example-video
uv run --frozen python scripts/check_project.py --cpu-only
node --check src/web/static/app.js
```

Chrome에서 `http://127.0.0.1:8770`을 연다. 포트 충돌 시 `--port 8771`.
필수 모델/데이터 경로와 Mac 이관은 docs/MLB_P0.md를 따른다.

## Claude 재로그인 후 첫 작업

우선 읽기 전용 리뷰를 맡긴다. 기존 입력 규약을 새로 만들라는 오래된 지시는 사용하지 않는다.
아래 내용을 Claude Code에 전달할 수 있다.

> 현재 브랜치의 6fe5fbc부터 HEAD까지 MLB P0 변경을 읽기 전용으로 리뷰해라.
> AGENTS.md와 docs/MLB_P0_HANDOFF.md, docs/PREPITCH_CONTRACT.md부터 읽어라.
> 투구 ID 대응, 미래 정보 누수, 레거시 확률 의미, 추천 지원 범위,
> HTTP 입력 검증과 UI의 오래된 결과 표시, 새 8종 정답의 타석 종료 사건 구분을 집중 점검해라.
> src/data/mlb_video.py, mlb_sources.py, pitch_observation.py,
> src/inference/prepitch_contract.py, recommendation.py, src/web 및 관련 tests가 범위다.
> 파일을 수정하거나 커밋하지 말고, 재현 가능한 결함을 경로·행·영향과 함께 보고해라.
> 실제 결함이 없다면 없다고 쓰고 검토 한계를 밝혀라. 이후 Codex가 확인하고 수정한다.

## 남은 순서

1. **영상 시간 주석**: feed UTC 시각을 재생 시간으로 쓰지 말고, SNY 전체 경기에서
   최소 연속 한 타석의 투구 전 판단 시각과 릴리스 시각을 투구 ID별로 표시한다.
   이후 322개 투구로 확대하고 실제 영상 누락 여부도 검사한다.
2. **기존 영상 재검증**: 옛 오타니 수집기는 CSV `iloc[i]`를 사용했다.
   기존 영상 파일명은 재확인 전 정답이 아니다. 원본 확보 후 playId로 재대조한다.
3. **새 확률 모델**: 8종 정답을 기존 특징에 투구 ID로 연결하고 시간 분할을 유지한다.
   학습·독립 보정·CE/Brier 검증을 거친 뒤에만 UI의 미지원 확률을 활성화한다.
4. **위치/인식**: 목표 위치와 제구 오차, 타자 특성, 점수판 OCR, 선수·상태 추적을 순차 구현한다.
5. **효용 검증**: 기존 정책 실점 차이 CI는 0을 포함한다. 실제 실점 개선 입증으로 발표하지 않는다.

경기 747139는 이미 기존 test cohort에 포함되어 있다. 개발·시연용이며,
이 경기를 보고 튜닝한 뒤 새로운 독립 검증 성능으로 보고하지 않는다.
