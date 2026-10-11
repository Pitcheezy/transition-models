# 실제 PTS 프레임 추출·AI 관측 연결 — 2026-10-06

CV-5a2를 완료했다. 원본/클립 체크섬과 영상 파일을 다시 확인한 뒤, 지정한 시각보다
뒤의 화면을 사용하지 않는 프레임 추출과 실제 AI 응답 수신을 연결했다. 기존 M3와
시연 결과를 다시 측정하거나 바꾸지 않았다.

## 실제 동작 확인

기존 개발 경기 747139에서 **180·185·190초의 5초 간격 세 요청**을 AI 응답 전에
고정했다. 세 관측기는 이전 대화를 물려받지 않은 별도 Codex 에이전트이며, 각자
익명 이미지와 요청 JSON만 받았다. 앞뒤 프레임·투구 ID·릴리스 시각·정답을 전달하지
않았다. 이는 접근을 제한한 작업 지시이며 에이전트를 보안 샌드박스로 인증한 것은 아니다.

| 요청 상한(초) | 실제 프레임(초) | AI 응답 | 미트 픽셀 | 요청→수신(초) |
|---:|---:|---|---|---:|
| 180 | 179.9964833 | unavailable | None | 69.062 |
| 185 | 184.9848000 | marked | [665, 270] | 69.156 |
| 190 | 189.9898000 | unavailable | None | 69.172 |

표의 좌표는 **새 AI 관측값**이다. 사람 정답과 대조하지 않았으므로 정확도·개선량을
계산하지 않았다. 기존 185초 seek 샘플과 새 185초 cutoff 샘플은 실제 선택 프레임이
다르다. 이 둘의 좌표 차이를 모델 정확성이나 일관성 수치로 해석하지 않는다.

경과 시간은 요청 발행부터 원응답 파일 수신까지다. 에이전트 생성·도구/승인·큐·컨트롤러
대기를 포함하며 모델 단독 추론 시간이 아니다. 이미 준비된 이미지로 실험했으므로
중계 수신부터 출력까지의 지연이나 투구 전 성공률을 측정한 것도 아니다.
원응답과 파일 해시는 [공유 실행 기록](results/cv_followup_20261006/mapped_observation_v1.json)에 있다.

## 재현 경로

먼저 [시간축 캡처](CV_CLIP_CLOCK_V1.md)를 새 폴더에 실행한다. 아래 경로는 예시이며
모든 출력 폴더는 새 이름을 사용한다.

```bash
python -m intent.clip_frames --capture-dir outputs/cv_clip_clock_new --source-seconds 185 --out outputs/cv_clip_frame_new
python -m intent.observation_session begin-mapped --mapped-frame outputs/cv_clip_frame_new --out outputs/cv_observation_new
# 실제 관측기에 outputs/cv_observation_new/request/만 제공해 응답 JSON을 받는다.
python -m intent.observation_session finish --session outputs/cv_observation_new --response path/to/actual_response.json
uv run --frozen python scripts/check_project.py --cpu-only
```

`clip_frames`는 receipt가 결속한 영상·체크섬의 SHA를 확인하고 매핑을 새로 계산한다.
그 결과의 **디코딩 순번**으로 FFmpeg에서 화면을 고른 뒤, 선택된 원시 픽셀 MD5와
PTS·시간 단위·크기·duration을 대조한다. JPEG 형식·크기·전체 디코딩도 검사한다.
입력 파일은 실행 후 다시 확인한다. 단순 seek, 평균 fps, 임의로 편집된 매핑 JSON에
의존하지 않는다. 시작 전·누락 구간·종료 후 세 요청은 출력 폴더 생성 전에 거절됐다.

새 `intent_mapped_frame_v1` 영수증에는 요청 상한과 실제 source/clip 시각을 각각
유리수로 기록한다. `load_verified_frame`은 원본 캡처부터 다시 검사하며, 변조·중단·
손상 JPEG·불일치 시 성공으로 처리하지 않는다. 캡처/추출의 산출물 해시 수집은 공통
함수로 관리한다. 저장 장치 자체에 쓸 수 없거나 프로세스가 강제 종료되면 부분
폴더가 남을 수 있으므로 기존 출력은 덮어쓰지 않고 새 실행으로 재개한다.

관측 `begin-mapped`는 이 새 영수증만 받는다. v2 요청/세션/결과에는
`source_time_basis=decoded_pts`, `source_time_seconds_exact`,
`requested_cutoff_seconds_exact`를 남긴다. 완료 시 이미지·요청·원본·검증 코드 3개·
호스트와 시계까지 다시 검사한다. AI 응답의 픽셀 판독 형식은 기존 v1을 재사용한다.
기존 `begin`과 과거 v1 요청 시각 영수증·결과는 유지하며 조용히 의미를 바꾸지 않는다.

CLI는 모델을 자체 호출하지 않는다. 이번 실제 호출은 Codex가 새 에이전트 세 개에
요청을 전달하고 응답을 수집한 것이다. 같은 모델/같은 좌표 재현을 보장하지 않는다.
`request/` 외 private 세션에는 로컬 경로가 있으므로 관측기/공개 배포에 포함하지 않는다.

## 검사와 다음 작업

관련 180 tests 통과, 전체 **987 passed / 5 skipped / 2 deselected**, Ruff 107경로 통과.
동결 자료 186개와 웹 파일 21개, 총 207개 SHA 불변. 팀원 코드와 공개 사이트를
변경하거나 새 배포하지 않았다. 기존 오프라인 ZIP도 그대로 사용할 수 있다.

CV-5a 전체는 아직 완료가 아니다. 다음 개발 단위는 실제 모델 어댑터의 자동 호출을
시간순 공급기에 연결하고, 한 연속 타석의 입력 도착·결과 발행을 계측하는 것이다.
그전에 타석 입장·종료 범위와 모델 호출 수단·시간 기준을 확정한다. 실제 사람 검토와
새 미열람 영상의 독립 평가는 별도다. E-site5 실제 응답과 E-demo2 현장 확인도 대기다.
