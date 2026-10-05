# 원본·클립 프레임 시간축 검증 — 2026-10-06

CV-5a의 시간축 단위를 완료했다. 기존 개발 경기 747139의 로컬 후보 클립과 원본 URL의
제한된 구간을 새로 디코딩해, 보존된 3,298장 모두를 고유한 픽셀 체크섬으로 연결했다.
기존 M3·시연 JSONL·장표·사이트는 변경하지 않았다. 새 정확도나 실시간 성능 실험이 아니다.

## 확인 결과

| 항목 | 결과 |
|---|---|
| 원본 구간 / 로컬 클립 디코딩 행 | 3,717 / 3,298 |
| 고유하게 대응된 클립 행 | 3,298 / 3,298 |
| 새 양쪽 체크섬 시간 단위 | 1/60000초 |
| 원본 PTS − 클립 PTS | 10,500,490 ticks = 175.0081667초 |
| 마지막 디코딩 순번 / 클립 PTS | 3297 / 3301298 |
| 클립에서 누락된 구간 | PTS 3300297부터 3301298 이전까지, 1001 ticks |
| 185초까지 허용한 화면 | 원본 PTS 11099088 = 184.9848초 |

185초를 seek 요청했을 때 FFmpeg가 고르는 185.0014833초 화면은 **185초 cutoff에서는
미래 프레임**이다. 요청 시각·실제 PTS·디코딩 순번을 별도 값으로 보관한다. 단순히
원본 시각에서 175를 빼거나 순번에 평균 프레임 간격을 곱하지 않는다.

Claude의 기존 `source_pts = clip_pts + 10490` 계산도 저장 체크섬으로 재현했다.
다만 그 파일의 기본 출력 시간 단위는 1001/60000초다. 새 캡처는 `-enc_time_base -1`과
`-copyts`, `-fps_mode passthrough`로 입력 시간 단위를 보존했다. 모든 디코딩 이미지
체크섬은 이전과 같다. 원본의 프레임 시각은 기존 기본 인코더 시간축에서 반올림될 수
있으므로 그때의 프레임 번호를 실제 원본 PTS와 혼용하지 않는다.

## 재현

Python과 FFmpeg가 있는 저장소 루트에서 새 출력 폴더를 사용한다.
CLIP에는 로컬 `pa2_source_candidate.mp4` 경로를 넣는다. 이 파일은 Git에 없다.
소스 URL은 아래 JSON 보고서에 있으며, 영상 전체를 저장하지 않고 제한 구간의
디코딩 체크섬만 만든다.

```bash
python -m intent.clip_capture --source URL --source-start 172 --source-duration 62 --clip CLIP --out outputs/cv_clip_clock_new --timeout 120
python -m intent.clip_clock audit --source-frames outputs/cv_clip_clock_new/source.framemd5 --clip-frames outputs/cv_clip_clock_new/clip.framemd5 --out outputs/cv_clip_clock_new/mapping.json
uv run --frozen python scripts/check_project.py --cpu-only
```

`clip_capture`는 명령·FFmpeg 버전·실행 시간·영상 전후 SHA·체크섬 SHA를 private
receipt에 기록한다. 빈 디코딩, 명령 실패·중단·시간 초과는 성공으로 표시하지 않으며
부분 산출물을 보존한다. 기존 폴더를 덮어쓰지 않는다. receipt에는 로컬 경로가 있어
그대로 공개하지 않는다. 실행 시간은 체크섬 생성 시간이며 미트 모델 지연이 아니다.

`clip_clock`은 단일 rawvideo 스트림·유리수 시간 단위·크기·PTS 순서와 고유 체크섬을
검사한다. 중복 이미지로 시각 대응이 모호하거나 연결이 누락·역행하면 거절한다.
다른 영상에서 행별 오프셋이 달라질 수 있으므로 전체 평균 보정을 적용하지 않는다.
`latest_mapped_frame`에는 입력 체크섬에서 방금 계산한 보고서를 전달한다. 이 함수
자체는 임의로 편집된 JSON을 인증하는 검증기가 아니다. 누락 구간과 범위 밖 조회는
거절하며 미래 프레임을 반환하지 않는다.

공유 가능한 수치·해시·경계 검사는 [JSON 보고서](results/cv_followup_20261006/clip_clock_v1.json)에 있다.
입력 파일 두 개와 로컬 영상의 해시로 정확한 실행 자료를 구별한다. 해시는
영상의 경기 식별이나 외부 제공자의 정직성을 인증하지 않는다.

## 남은 것

누락 프레임의 원인은 확정하지 않았다. 클립에 세 투구의 기존 주석 시각이 들어 있다는
것과 전체 타석의 입장·결과·퇴장을 포함한다는 것은 다르다. 전체 타석 범위 확인,
실제 관측기 자동 호출, 결과 발행 시각·방송 지연 계측은 남아 있다.
다음 단위는 이 매핑과 영상 해시를 재확인한 뒤 디코딩 순번으로 정확한 프레임을
꺼내고, 새 영수증에 실제 PTS를 남기는 것이다. 과거 세 관측의 요청 시각을 실제
프레임 시각으로 소급 변경하지 않는다. E-site5·E-demo2는 실제 응답/현장 확인 대기다.

검사: 906 passed / 5 skipped / 2 deselected, Ruff 104 paths. 기존 동결 파일 186개와 우리 웹 파일 21개, 총 207개 SHA 불변.
