# 전시 첫 타석 재생 — 2026-10-28

목표·일정은 [PLAN](../PLAN.md), 현재 담당·다음 단위는 [CHECKLIST](../CHECKLIST.md)를 따른다.
이 문서는 이번 고정 구현의 근거다. 팀원 코드·Cloudflare·공개 사이트는 변경하지 않았다.

## CV48c — 고정 구간 80프레임 조사와 객체 지목 불일치

CV48b에서 정한 같은3구의 짧은 후보 구간을 **24+25+31=80개 실제 디코딩 프레임**으로 확인했다.
1구0.4015초·2구0.4004초·3구0.5005초는 양 끝 PTS 차이이며 전체 준비 동작의 길이가 아니다.
각 프레임의 투구 key/play_id/클립 SHA/정수 PTS/이미지 SHA를 연결했다. FFmpeg showinfo80개는
ffprobe 선택과 일치하고, 기존 대표 이미지3개 SHA도 동일했다. 1구의 최대 PTS 간격34.4667ms를
그대로 보존했으며 FPS 보간·누락 프레임 생성·원중계 완전성 주장은 하지 않았다.

Codex는 전체/크롭16시트의80장을 보고 최초 판독을 먼저 저장했다. Fable 최초3회는 정상 종료했고
같은16이미지 Read를 확인했다. 그러나 **라벨이 같아도 같은 물체를 본 것은 아니었다.**

- 1·2구의 최초 Fable 설명은 미트를 정강이 보호대 옆에 있다고 하거나 고정 크롭이 움직였다고 적었다.
  이 설명을 채택하지 않았다. 크롭은 전 프레임에서 동일한 `[450,240,660,470]`이다.
- 1구 후속은 위쪽 미트의 넓은 영역을 다시 지목했다. 정밀 중심·오른쪽 부속물의 정체까지 확정하지 않고
  24프레임을 정성적인 개발 후보로만 남겼다. 완성 응답은239.239초에 왔지만 프로세스는240초 제한으로
  중단돼, **내용 수신과 CLI 정상 종료를 구분**했다.
- 2구 후속은 정강이 보호대 혼동을 인정했지만 새 경계상자도 미트 중심부 대신 오른쪽 소매/몸통/배경 쪽을
  지목했다. 원본 크롭을 다시 확인하여 **25프레임의 객체 교차판독을 미해결**로 남겼다.
  최초 응답의25행에 `point_xy` 필드가 없던 것도 보존했고 누락을 null로 간주하지 않았다.
- 3구는 최초 판독에서 끝3프레임(ordinal134~136)의 자세가 갈렸다. 후속은240초 내 완성 응답이 없어
  추가 판독을 채택하지 않았다. 앞28프레임은 개발 후보, 끝3프레임은 자세 판단 미해결이다.

결과: **80프레임 중 개발 후보52 / 객체 지목 미해결25 / 자세 미해결3**. 이는 개발 검토 상태이며
정확도·독립 AI 일치율이 아니다. 이번 단위는 정성 판독이므로 **새 좌표 출력0**, 픽셀 이동량·정지 임계값·
물리 거리·제구 오차·투수 의도·사람 대비 정확도는 미측정이다. 이전 CV48b의 정지 이미지 후보점3개를
연속 구간으로 늘려 표시하지 않았다. 기존 v2 화면·실행팩·원본·사람 응답·평가 잠금 자료는 보존했다.
[프레임별 원판독·불일치·채택/보류·SHA](results/exhibition_replay_20261028/interval_review_v1.json).

추출 코드는4b41470이며 읽기 검토에서 고정 구간과 원본 결속 누락을 찾았다. 2536ee9는 기존 CV48b의
play_id·영상 SHA까지 고정한다. 등록부와 새 파일이 서로 일치하더라도 옛 영상과 다르면 출력 생성 전에
거부한다. 실제3원본의 고정값을 재대조했고 선택·이미지 생성은 바뀌지 않아 추출을 반복하지 않았다.
관련 검사와 다른 모델의 고정 검토 결과는 [검토 영수증](results/exhibition_replay_20261028/interval_code_review_v1.json)에 남긴다.
최종 관련 Python59(새 구간 검사27 포함)·린트/포맷180경로 통과. 8e9e4eb의 Fable 검토는 승인이고
남긴 커밋 추적 필드 요청도 반영했다. 코드 검토자는 실제 검사를 실행하지 않았다. UI 코드를 바꾸지 않아
기존 브라우저 검사를 반복하지 않았고, v2 ZIP SHA 불변을 확인했다. 원격CI는 PR84의 최종head 기준으로 확인한다.

재현: `python scripts/78_build_replay_interval.py --root <CLIP_ROOT> --out <NEW_PRIVATE_OUTPUT_DIR> --ffprobe <FFPROBE> --ffmpeg <FFMPEG>`.
현재 원본 추출물은 Git 제외 `outputs/exhibition_replay_interval_20261028_v1`이다. 이미지·시트·Claude 원문
이벤트(이미지 포함)는 비공개로 유지한다. 중간 실패는 부분 폴더를 보존하고 audit.json을 쓰지 않는다.
그 폴더를 완료본으로 쓰거나 재사용하지 말고 새 출력 경로로 재개한다. 실패 자료를 자동 삭제하지 않는다.

다음 단위는 기존 재생 화면에서 **준비 구간의 근거와 교차판독 미해결 사례를 구분해 보여주는 것**이다.
특히2구를 검증된 연속 미트 추적으로 표시하지 않는다. 같은80장을 라벨만 맞을 때까지 반복 판독하지 않는다.

## CV48b — 미트 개발 후보와 같은 프레임 표시 완료

첫3구의0~2.5초 구간을 실제 PTS로 약0.1초 간격 선택하여78장과 포수 문맥 크롭을 보존했다.
`77_build_replay_context.py`는 정확히849843 PA1의3구만 수용하며 새 비공개 출력 경로를 요구한다.
두 AI가 고른 시각·점은 같다고 가정하지 않는다. 최초 독립 판독과 동일 프레임 후속 확인을 구분한다.
내부 sidecar v2는 원본 이미지 크기·nullable pixel point·context_crop을 추가한다. 공개 계약은 그대로다.
점은 결과 공개 후 해당 정지 이미지에만 표시하며, 영상·plate 좌표에 옮기거나 제구 오차로 계산하지 않는다.
v1 자료는 이전과 같이 수용한다. 서버의 PNG IHDR 크기/CRC와 브라우저 실제 이미지 크기를 대조하고,
기권 점·잘못된 크기/범위는 거부한다. 같은 이미지의 SVG viewBox로 문맥 확대를 표시한다.
결과는 **3구 / 78시각표본 / 개발 후보점3 / 기권0 / 확정목표0 / 독립 사람검토0**이다.
두 AI의 최초 프레임·점은 일치하지 않았으며 그대로 기록했다. 이후 동일 프레임에 제안한 점3개를
Fable이 확인한 것은 정보를 공유한 후보 검토다. 독립 점 일치도나 사람 대비 정확도로 계산하지 않는다.
낮은 자세·올리는 중인 장면을 준비 위치로 채택하지 않았으며, 표본 사이 전체 프레임의 정지를 확인한 것은 아니다.
선택 시점에는 투수 동작이 이미 시작돼 있다. 추천 시점의 사전 가용성을 입증하지 않는다.

초기18시트 일괄 검토는360초 제한으로 끝났으며 성공으로 기록하지 않았다. 이어 투구별4시트씩
3회 제한 검토가 정상 종료됐고, 실제 `Read` 이미지12건과 동일프레임 후속3건을 로그에서 확인했다.
작성은 Codex(GPT-6 계열, 정확한 런타임 ID 미노출), 실제 검토 모델은 `claude-fable-5-1`이다.
1구 응답의 JSON 구문 오류는 원문을 보존하고 필요한 항목을 수동 전사했다고 기록했다.
[판독·불일치·시각·이미지 SHA](results/exhibition_replay_20261028/context_review_v1.json).

고정92a703e 코드 검토의 경로 정규화 우회 지적은 경로를 정규화하지 않고 거부하는 코드로 반증했고,
검토 모델도 오탐을 인정했다. PTS 결속 지적은041f854에서 `-copyts` + `showinfo`로 보강했다.
실제 추출시각78개가 ffprobe와 모두 일치하고 기존78이미지 바이트도 동일했다. Fable 후속 검토는
**approve / 남은 차단0**이다. [검토 영수증](results/exhibition_replay_20261028/context_code_review_v1.json).

검사: Python 관련189통과 후 추출기 수정24통과(기존19 재실행+새5, 합산213고유검사가 아님),
Node59·Chrome 합성19·실제3구 원속도 재생 및 모바일14항목 통과. 페이지오류0·외부요청0.
실행팩20파일 / 16,945,651bytes / SHA256 `f269ac511491ddd948d8e6872ebb57bf39348e1d885538f65db33e1cbe6b7b08`.
CRC·폴더와ZIP 전바이트·동봉런타임·표준라이브러리 `--check` 통과. 비공개
`outputs/exhibition_replay_pack_20261028_v2.zip`이며 이전v1팩은 보존했다.
[브라우저·실행팩 영수증](results/exhibition_replay_20261028/checks_v2.json).

원격CI 후속: fa2794d는 Linux·Chromium·WebKit 통과, macOS는180초 제한으로2회 종료됐다.
2회차는2850 passed/8 skipped/2 deselected/177.46초를 출력한 뒤 프로세스 종료 정리에서 제한에 걸렸다.
021514b는 macOS만300초로 보강하며 Ubuntu180초·전체job25분·테스트 선택은 그대로다.
Fable 고정021514b 검토APPROVE. 새 head 실제 종료 결과는 PR84 checks와 board 종료 댓글로 확인한다.
시간 제한 실패를 테스트 성공/실제 Mac 사용 확인으로 바꾸지 않는다.

재현: `77_build_replay_context.py --root <CLIP_ROOT> --out <NEW_PRIVATE_DIR> --ffprobe <FFPROBE> --ffmpeg <FFMPEG>`.
이번 고정 audit는 `outputs/exhibition_replay_context_20261028_pts_v2`에 있고, 아래 prepare 명령의
decisions를 `context_review_v1.json`으로 바꾼다. 나머지 빌드/실행 명령은 동일하다.
showinfo 원문은 경로·프로세스별 포인터를 포함하여 비공개이며 로그 SHA와 audit SHA는 재실행마다
달라질 수 있다. 새 추출물을 기존 결정에 억지로 연결하지 않고 PTS·이미지 SHA부터 대조한다.

당시 다음 단위였던 CV48c의 결과는 위 절에 있다. 미트 식별의 일반화·
물리 좌표 보정·선택 기대가치 비교는 아직 완료되지 않았다.
이후 절의0점/3기권·20파일팩은 **이전 EX-replay1의 고정 결과**이며 CV48b 결과로 덮어쓰지 않는다.

## 이전 EX-replay1 — 완료한 사용자 기능

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
