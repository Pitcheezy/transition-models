# 전시 첫 타석 재생 — 2026-10-28

목표·일정은 [PLAN](../PLAN.md), 현재 담당·다음 단위는 [CHECKLIST](../CHECKLIST.md)를 따른다.
이 문서는 이번 고정 구현의 근거다. 팀원 코드·Cloudflare·공개 사이트는 변경하지 않았다.

## 완료한 사용자 기능

기존 `web/service-review`에 투구 전 근거 이미지 패널과 같은 타석의 다음 투구 버튼을 추가했다.
추천 검토 → 공식 클립 재생 → 실제 결과와 근거 이미지 공개 → 다음 투구에서 다시 숨김 순서다.
그림은 별도 패널이며 실제 영상 위 추적점·제구 오차·검증된 의도로 표시하지 않는다.
기존 서비스 응답·IntentEstimate v1.1·공개 발행 계약은 변경하지 않았다.

현재 비공개 시연은 849843(현지 2026-09-29 CHC@SD, 한국 9/30)의 첫 타석이다.
Michael King 대 Pete Crow-Armstrong의 3구 모두 기존 저장 추천·실제 결과·클립이 있다.
원본 SHA `df606a11c6db465c054252ef8d331aeb23aa21565b4960bd586f3dcf8f62f6b7`,
정규화 보고서 SHA `154d9cd1cb166552db5975137e2ba431b9ab48f94fcfa6bdd05304f645427c80`는 v5와 불변이다.
추천은 당시 저장된 `ARM-B P3 (pitch type only), frozen <=2025` 재생이며 실행 runtime/가중치 버전은 미확인이다.
구종 비중을 사건확률로 바꾸지 않고 사건확률·기대가치는 미제공으로 표시한다.

## 영상 조사와 해석 범위

- 등록부는 읽기 전용 SQLite로 열었다. 첫5타석 목록만 조회하고 **영상은 PA1의 3구만** 디코딩했다.
- 3/3클립의 크기·SHA가 기존 등록부 및 v5 클립과 일치한다. 전체 디코딩 **1,234프레임**의 PTS를 확인했다.
- 명목 FPS를 사용하지 않았다. `ffprobe frame.pts`, time base `1/90000`, FFmpeg 디코딩 순번을 함께 기록했다.
- 약0.5초 간격으로 **45장**을 선택해 세 장의 시트와 원본 크기 이미지로 직접 AI 시각 확인했다.
  결과: 세 구 모두 투구 전 포수 장면이 있어 PA1을 유지한다. 쉬운 표본을 찾으려고 다음 타석으로 넘어가지 않는다.
- 3구는 투구 후 약5.019~5.520초 사이 타자 클로즈업으로 바뀐다. 표본에서 리플레이를 보지 못했지만
  0.5초보다 짧은 삽입 장면까지 부재를 확정하지 않는다. 정확한 컷·릴리스 프레임 측정은 미완료다.
- 근거 이미지는 세 구의 약2.0초 프레임이다. 약2.5초의 투구 팔 자세와 약3.0초 후속 프레임으로
  **AI가 관측한 릴리스 구간 하한**을 기록한다. 정밀 릴리스 검증이나 실제 방송 시계 대응이 아니다.
- **준비 장면 후보3, 확정 미트 점0, 점 판독 기권3, 독립 사람 검토0**이다.
  미트 중심·멈춤 순간·미트/맨손 구별은 다음 단위에서 검토한다. 사람 대비 정확도·제구 오차는 미측정이다.
- 기존3구째 미트 x 추정은 다른 프레임에서 만든 옛 자료다. 이번 사진에서 나온 좌표라고 연결하지 않는다.
- 평가 잠금849844 영상은 열지 않았다. 새 모델 학습·1,466클립 전수 AI 판독도 하지 않았다.

[고정 조사 기록·프레임 SHA·시각](results/exhibition_replay_20261028/feasibility_v1.json).
영상·PNG·시트·ZIP·로컬 서버 주소는 Git 제외 `outputs/exhibition_replay_*`에만 둔다.

## 내부 파일 계약과 검사

선택적 `review-evidence.json`은 `pitcheezy-service-review-evidence-v1`이다.
경기·원문 SHA와 각 행의 투구 key/play_id/클립 SHA를 기존 media manifest에 대조한다.
각 근거에는 이미지 SHA, 정수 PTS, 첫 프레임 PTS, time base, 클립 상대 초,
릴리스 구간 하한, `candidate` 또는 `abstained`, 이유가 있다. 좌표·실제 결과를 추가하지 않는다.

서버는 안전한 상대 경로·이미지 SHA·PTS 관계를 검사하고 허용 파일만 제공한다.
브라우저는 공개 전 근거 경로·시각·이유를 뷰로 내보내지 않는다. 공개 버튼은 표시 순서이며 접근 통제가 아니다.
명세가 없거나 틀리면 근거만 미제공으로 남기고 기존 추천·영상은 계속 쓸 수 있다.
v5의 선택적 sidecar 없는 형식도 계속 수용한다. 근거 PNG는 장당5MiB, 현재 time base는 측정된1/90000만 지원하며 다른 시간 기준은 거부한다.

## CV47r에서 수정한 것

고정 `c99166c`의 Codex 재검토에서 두 결함을 합성 재현했다.

1. 중복 투구 등 manifest 검증 전에 원본을 저장해 정상 재시도를 막음.
   모든 행·메타데이터·SQLite 제약 검사 후 확정 저장하고 충돌도 전체 사전 확인한다.
   파일 시스템과 SQLite를 아우르는 전원 중단 원자성까지 보장하지는 않는다.
2. 작은따옴표로 나열된 MP4 URL 두 개를 한 후보로 합침.
   따옴표 문맥별로 분리하며 경로의 아포스트로피 지원을 보존한다.

수정 `a1b70e3267d7c0c17a76746f0536be6ed74f1261`, 관련49검사 통과.
핵심 새 회귀8개는 이전c99166c에서7실패/1통과였다.
Claude Code2.1.310, 실제 응답 `modelUsage`의 **claude-fable-5-1** 읽기 검토는 approve다.
검토자는 테스트를 실행하지 않았다. [영수증](results/exhibition_replay_20261028/cv47r_review_v1.json).
Codex 작성 모델의 정확한 런타임 ID는 이 환경에 노출되지 않아 GPT-6 계열/미확인으로 기록했다.
이 로컬 개발 검토를 운영 출시 승인으로 쓰지 않는다.

## 실행·재현

기존 노트북 Python 환경과 FFmpeg/ffprobe가 필요하다. `<CLIP_ROOT>`는 비공개 SSD 등록부,
`<RAW>`는 기존 S 원문, `<V5>`는 보존한 v5 영상팩 폴더다. 기존 출력을 덮어쓰지 않는다.

```sh
python scripts/76_audit_replay_clips.py --root <CLIP_ROOT> --out outputs/exhibition_replay_audit_new --through-pa 1
python scripts/prepare_replay_evidence.py --audit-dir outputs/exhibition_replay_audit_new --decisions docs/results/exhibition_replay_20261028/feasibility_v1.json --out-dir outputs/exhibition_replay_evidence_new
python scripts/build_service_review.py --input <RAW> --source-kind provided_export --include-first-pa-video --media-dir <V5> --evidence-dir outputs/exhibition_replay_evidence_new --out-dir outputs/exhibition_replay_pack_new --zip outputs/exhibition_replay_pack_new.zip
python outputs/exhibition_replay_pack_new/launch_review.py --check
python outputs/exhibition_replay_pack_new/launch_review.py --open
```

다른 디코더/등록부 버전 때문에 audit SHA가 달라지면 두 번째 명령은 거부한다.
그때 기존 결정을 억지로 재사용하지 말고 디코딩 근거를 대조한 뒤 새 결정 기록을 만든다.
검토팩 자체는 Python3.10+ 표준 라이브러리만 필요하고 Windows/Mac 실행기가 포함된다.
이번 실물 사용 검사는 Windows이며 Mac 실제 사용 완료를 뜻하지 않는다.

## 검증 근거와 남은 장애물

- 로컬 Python: 최종 관련 **208검사 통과**(등록부·디코딩·서버·팩·재현·체크리스트, 32.95초). 체크리스트 첫 실행의 Windows
  subprocess 인코딩 경고는 PYTHONUTF8=1로 재실행해 없음을 확인했다.
- Node: 기존·신규 UI55 통과.
- Chrome155 합성 회귀17 통과. 실제 비공개3구 원속도 재생·근거 표시·전환·파일 오류/복구10항목 통과.
  실제 브라우저의 비loopback 요청0, 페이지 오류0. 캡처는 비공개로 보존한다.
- 전시 전체 완료가 아니다. 미트 중심·안정 순간, 좌표 비교 타당성, 채택 화면 연결, 실기기·전시 규모 시험이 남는다.
- 다음 한 단위: **CV48b — 같은3구의 투구 전 구간을 좁혀 미트/맨손 문맥과 준비 순간을 교차판독**한다.
  새 근거가 없는 좌표·기대가치를 만들지 않는다. 결과에 따라 후보 점 또는 기권을 기존 화면에 연결한다.

새 재생 코드도 고정 e9948b9의 Claude Fable 검토와 후속973e901 집중 재검토 APPROVE를 받았다.
[검토 결과와 지적 처리](results/exhibition_replay_20261028/replay_review_v1.json) · [브라우저·ZIP 영수증](results/exhibition_replay_20261028/checks_v1.json).
