# 의도 모듈 v0 — M3 평가 계획과 진행 기록

M3 완료 기준은 [작업 지시서](INTENT_V0_WORK_ORDER.md)에 있다.
- 다른 경기 2개 이상에서 사람이 찍은 라벨 50구 이상으로 픽셀·피트 오차와 기권률을 잰다.
- 개발 경기와 평가 경기를 분리하고, 결과를 `accuracy_report.json`에 담는다.

사전 등록 파일은 [intent_eval_plan_v0.json](results/mlb_p0/intent_eval_plan_v0.json)이다. 평가 경기의 프레임을 열기 전에 커밋했다.

## 경기 역할

| 역할 | 경기 | 방송 | 영상 | 이 경기로 만든 것 |
|---|---|---|---|---|
| 개발 | 747139 | SNY | 전체 경기 | M1 판독 규약, 홉 ① v1, 홉 ② 틸트 |
| 개발 | 849843 | NBC | 압축 경기 | 압축 경기 스캔·판독 프롬프트, 두 판독자 합의 규칙(15 px), 홉 ② 팬 항 |
| 평가 E1 | 849845 | NBC/Peacock | 압축 경기 18:33 | — |
| 평가 E2 | 823407 | FOX | 압축 경기 10:59 | — |

**선정 규칙:** 일정·콘텐츠 목록(경기 번호, 방송사, 압축 경기 제목·길이)만 보고 정했다.
- **E1:** 849843을 뺀 2026 와일드카드 1차전 중 압축 경기 MP4가 있는 가장 작은 gamePk.
- **E2:** SNY·NBC가 아닌 방송사의 경기. 정규시즌 마지막 주말(9/26–27) 경기 중 전국 중계가 있는 가장 늦은 경기.
- **보충:** 두 경기에서 사람이 찍은 투구가 50구 미만이면 849849, 849851을 같은 방법으로 더한다.

## 고정한 방법

평가 경기에는 이 커밋의 `intent/`를 그대로 쓴다.
- 압축 경기 처리는 `python -m intent.condensed`와 [스캔](../intent/workflows/condensed_scan.js)·[판독](../intent/workflows/condensed_read.js) 워크플로가 맡는다.
- 849843 때의 임시 스크립트를 일반화했다. 바뀐 점은 세 가지다.
  - 방송사별 화면 위치 힌트를 뺐다.
  - 투구 후 구종·구속 그래픽 판독을 넣었다.
  - 동점 후보를 그래픽 → 결과 순으로 자동으로 가른다.
- 운영자가 정해도 되는 것은 세 가지다.
  - 경기별 crop 상자: 판독 전에 한 프레임에서 정하고, 미트는 찍지 않는다.
  - 대응이 열린 스캔 검출의 배정·삭제: 이유를 적는다. Statcast 투구 위치와 미트는 쓰지 않는다.
  - 오류로 끝난 판독 에이전트의 같은 프롬프트 재실행.
- 사람 라벨링 팩은 그 경기의 출력이 모두 커밋된 뒤에 넘긴다. 경기의 모든 줄을 담고, 보조 판독 점·상태·투구 결과는 보여 주지 않는다.

## 지표

- **경기별 지표**
  - 출력 줄 수와 경기 전체 투구 대비 비율
  - 보조 판독 기권률, 사람 기권률, 가용성 표
  - 미트 픽셀 거리: 중앙값, 90분위
  - 출력 피트 오차: 공개한 `plate_feet` − 사람 미트를 사람 앞선과 홉 ② 행렬로 옮긴 값. 거리와 |x|·|z|의 중앙값·90분위
  - 포구 공 vs Statcast rms
- **합산:** 평가 경기만 묶는다. 사전 합격선은 두지 않았다.
- **명령:** 경기별로 `python -m intent.human_labels`를 돌린 뒤 `python -m intent.accuracy_report`를 실행하면 [intent_accuracy_report_v0.json](results/mlb_p0/intent_accuracy_report_v0.json)이 나온다.

## 계획에서 벗어난 점

- **`intent/broadcast_windows.py`에 ffmpeg 재시도를 더했다.** 823407 창을 자를 때 MLB CDN이 범위 읽기를 중간에 끊어(`partial file`) 두 번 실패했다. 창마다 최대 4번 다시 시도한다.
  - 같은 seek는 같은 프레임을 내므로 출력은 바뀌지 않는다. 다시 자른 프레임의 sha256이 처음 것과 같았다.
  - 판독·보정·좌표 규칙은 바꾸지 않았다.
- **`intent/calibrate.py`의 `error_definition` 문구를 고쳤다.** "development game"과 몽타주 확인 문구가 모든 경기에 고정으로 찍히고 있었다.
  - 이제 경기 역할은 평가 계획에서 읽고, 몽타주 문구는 사람 확인이 있을 때만 붙인다.
  - 숫자는 바뀌지 않았다. 747139·849843 보정 파일은 이 문자열 한 줄만 달라졌다.
- **보고 도구를 보강했다 (2026-10-03, 측정 방법은 그대로).** 10/5 전달 요청에 맞춰 바꾼 것은 보고 쪽뿐이다.
  - `intent/accuracy_report.py`: 지표별 분모, 부호 있는 x·z와 절댓값, 미트 판독 오차·출력 오차·카메라 검사의 분리, 사람 기권 이유, 라벨 출처, 큰 차이와 가용성 불일치의 pitch_id, 한계 목록을 넣었다.
  - `intent/human_labels.py`: 라벨 내보낸 시각, 원본 파일 이름과 sha256을 기록한다.
  - 판독·합의 규칙·보정·좌표 변환은 바꾸지 않았다.
  - 합성 라벨(커밋하지 않음)로 끝까지 돌려 보다가 보고 도구가 per-frame 키 이름을 잘못 읽는 버그를 찾아 고쳤다. 같은 판 고정 피트 오차가 0건으로 나오던 문제다. 사람 라벨을 받기 전이다.

## 10/5 전달 묶음 (Song 요청 2026-10-03)

요청서의 체크리스트 순서대로 정리했다. 사람 라벨이 들어오면 이 절의 '상태'와 시연 요약을 채운다.

| 항목 | 상태 | 파일 |
|---|---|---|
| 사람 라벨 (평가 2경기, 표시 50구 이상) | **대기**: 라벨 팩 2개(86장)를 저장소 주인에게 넘겼다 | 팩 manifest: `game_849845_intent_label_pack_v0.json`(e3e7cac83f68ebf1), `game_823407_intent_label_pack_v0.json`(c72e8a15a8a67507) |
| 라벨 출처 | 가져오면 자동 기록 (라벨러 식별자, 내보낸 시각, 원본 sha256, 팩 ID, 프레임 해시) | `game_<경기>_intent_human_labels_v0.json`, `game_<경기>_intent_setup_check_v0.json` |
| 정확도 보고서 | 도구 준비, 라벨 대기 | `intent_accuracy_report_v0.json` |
| 보정과 해석의 한계 | 아래에 정리 | 이 문서, 보고서 `limits` |
| 재현·연동 정보 | 끝남 (재현 확인, 서비스 검사 통과) | 아래 |
| 시연용 짧은 요약 | 라벨 뒤 채움 | 이 절 끝 |

### 오차를 세 갈래로 나눈다

- **미트 판독 오차:** 같은 프레임에서 보조 판독 점과 사람 점의 차이다.
  - 픽셀로 잰다.
  - 피트로도 잰다. 두 점을 모두 사람이 찍은 앞선과 같은 홉 ② 행렬로 옮기므로 카메라 변환이 상쇄된다.
- **출력 오차:** 공개한 `plate_feet` − 사람 미트를 사람 앞선으로 옮긴 값이다. 미트 판독과 앞선 판독이 함께 들어간다.
- **카메라 검사:** 포구 공 vs Statcast다. 물리 좌표를 확인하는 유일한 검사이고, 사람 확인은 없다.
- 위 두 갈래(사람 vs 보조)는 같은 행렬을 양쪽에 쓰므로 `plate_feet`의 물리적 정확도를 증명하지 않는다.

### 알려진 한계

- **선정 편향:** 압축 경기는 대부분 타석 마지막 공만 보여 준다. 849845는 250구 중 57구(23%), 823407은 355구 중 29구(8%)다.
- **높이:** 두 평가 경기 모두 포수가 릴리스까지 글러브를 땅에 둔다. `plate_feet.z`는 목표 높이가 아니라 쉬는 글러브 높이다.
- **823407 카메라:** FOX 카메라가 낮아 러버가 가려졌다.
  - 팬은 미측정이라 규칙대로 0으로 두었다.
  - 포구 공 2구뿐이라 카메라 검사도 미측정(`null`)이다.
  - 셋업 − 실제 공 x 중앙값이 −0.75 ft로 치우쳐 있어, 이 경기 x는 카메라 기준으로 믿기 어렵다.
- **849845 카메라 검사:** 13구 rms 0.149 ft는 보조 판독만으로 잰 값이다.
- **판독 프레임:** 사람은 보조 판독이 고른 프레임에 라벨한다. 그 프레임이 맞는 셋업 프레임인지는 평가하지 않는다.
- **라벨러:** 1명이 한 번 찍는다. 사람 간 차이는 미측정이다.
- **실패 사례:** 보고서 `failure_cases`에 큰 차이 5건과 가용성 불일치 전부를 pitch_id로 남긴다.

### 재현·연동

- **기준 커밋:** 이 절을 넣은 커밋. 브랜치 `feature/intent-v0`.
- **환경:** Windows 11, Python 3.12.12(`uv run --frozen`), uv 0.10.4, Pillow 12.2.0, ffmpeg 8.0 (gyan.dev essentials).
- **영상 없이 커밋된 판독 원문에서 재현** (프레임 검증 `--verify-frames`만 로컬 프레임이 필요하다):

```bash
python -m intent.condensed map --game 849845 --scan docs/results/mlb_p0/game_849845_condensed_scan_reads_v0.json --resolve docs/results/mlb_p0/game_849845_condensed_resolutions_v0.json
python -m intent.condensed map --game 823407 --scan docs/results/mlb_p0/game_823407_condensed_scan_reads_v0.json
python -m intent.condensed assemble --game 849845 --reads docs/results/mlb_p0/game_849845_condensed_reads_v0.json
python -m intent.condensed assemble --game 823407 --reads docs/results/mlb_p0/game_823407_condensed_reads_v0.json
python -m intent.calibrate --game 849845
python -m intent.calibrate --game 823407
python -m intent.run --game 849845 --out docs/results/mlb_p0/game_849845_intent_v0.jsonl
python -m intent.run --game 823407 --out docs/results/mlb_p0/game_823407_intent_v0.jsonl
```

  - `map`과 `assemble`은 feed(`data/raw/mlb_video/<경기>/feed.json`, git 제외)가 필요하다. `python -m intent.condensed source --game <경기>`로 받는다.
  - 2026-10-03에 위 명령을 다시 돌렸다. 스캔·points·보정·JSONL이 커밋된 파일과 바이트 단위로 같았고, `run.json`의 실행 시간만 달랐다.
- **서비스 스키마 검사:** [intent_service_check_v0.json](results/mlb_p0/intent_service_check_v0.json). 서비스 저장소의 `intent.py`를 읽어서 돌리며, 이 저장소에 복사하지 않는다.
  - 검사기: SongRoute/pitcheezy `8771c06`, sha256 `52f46e9a…`. 10/3 기준 main·demo/ws-2026 모두 이 버전이다.
  - 결과: 849845 57/57, 823407 29/29, 849843 39/39, 747139 297/297.

```bash
python -m intent.service_check --validator <pitcheezy>/apps/observer/backend/observer_app/intent.py docs/results/mlb_p0/game_849845_intent_v0.jsonl docs/results/mlb_p0/game_823407_intent_v0.jsonl --out docs/results/mlb_p0/intent_service_check_v0.json
```

- **라벨 받은 뒤:**

```bash
python -m intent.human_labels --game 849845 --labels <내려받은 JSON>
python -m intent.human_labels --game 823407 --labels <내려받은 JSON>
python -m intent.accuracy_report
```

- **git 제외 자료** (영상, 프레임, 라벨링 HTML)는 공개 저장소에 넣지 않는다. MLB 공식 압축 경기에서 다시 만들고 해시로 대조한다.
  - 다시 만드는 명령: `source` → `sheets` → `broadcast_windows`(경기별 상자는 위 '진행'에 있음) → `label_pack`.
  - 프레임 sha256은 points와 팩 manifest에 있다. ffmpeg 버전이 다르면 JPEG 바이트가 달라질 수 있다. 프레임 번호는 정확하므로 좌표는 그대로 쓸 수 있다.
- **처음부터 다시 돌리기:** 스캔·판독 워크플로(`intent/workflows/*.js`)는 Claude Code 에이전트 판독이라 다시 돌리면 같은 결과가 나오지 않는다. 그래서 재현의 기준은 커밋된 판독 원문이다.

### 시연용 짧은 요약

(사람 라벨을 가져온 뒤 채운다.)

## 진행

- 2026-10-02: 계획과 도구를 커밋했다(`784db6e`, 평가 경기 프레임은 아직 열지 않음).
- 2026-10-02: 두 평가 경기의 원본 정보와 2 fps 접촉 시트를 만들고 스캔 워크플로를 돌렸다.
  - 849845: 18:33, feed 250구, 시트 140장, 범위 14개.
  - 823407: 10:59, feed 355구, 시트 83장, 범위 9개.
- **운영자 crop 상자:** 판독 전에 중앙 카메라 프레임 하나씩만 보고 정했다. 미트는 찍지 않았다.
  - 849845 (NBC 높은 중앙 카메라, 플레이트 y≈357): `400,140,880,460`
  - 823407 (FOX 비켜 선 중앙 카메라, 점수판 오른쪽 아래): `300,180,960,500`
- **스캔과 feed 대응** ([849845](results/mlb_p0/game_849845_condensed_scan_v0.json), [823407](results/mlb_p0/game_823407_condensed_scan_v0.json))
  - 823407: 검출 30건 중 29건을 썼다. 1건은 두 스캔 범위 경계(t≈560)에서 같은 투구를 두 번 잡은 것이라 대응 후보가 없어 빠졌다. 투구 후 구종·구속 그래픽은 29건 모두 feed와 맞았다.
  - 849845: 검출 58건 중 57건을 썼다. 자동 규칙이 남긴 3건은 [운영자 결정 파일](results/mlb_p0/game_849845_condensed_resolutions_v0.json)에 이유와 함께 적었다.
    - t=331은 견제구였다(점수판이 이미 0-1, P:43; feed는 견제 도루사로 타석 종료). 그래서 뺐다.
    - t=547은 같은 1-2 스위퍼 두 개 중 P:65로 37:5를 골랐다.
    - t=610.75는 P:76으로 42:3을 확인했다. 그래픽은 FOUR SEAM, Statcast는 SI였다.
  - **독립 확인:** 점수판의 투수 투구 수 `P:NN`은 그 투구 전까지 던진 공 수와 같다. 쓴 투구 전부에서 맞았다(823407 29/29, 849845 56/56, 1건은 P 미판독). 이 확인은 대응 규칙에 쓰지 않았고, 위 운영자 결정 2건에만 근거로 썼다.
- **823407 보조 판독 결과** ([JSONL](results/mlb_p0/game_823407_intent_v0.jsonl), 서비스 검사 29/29 통과)
  - 29구 중 추정 15, 기권 14.
  - 기권 이유: 한 판독자만 셋업 찾음 7, 중앙 카메라 아님 3, 판독자 불일치 3, 릴리스 뒤 컷 1.
  - **카메라:** 틸트 3.3°(타자석 판독 18건). FOX 카메라가 낮아 러버가 마운드 뒤에 가려졌다. 그래서 팬은 잴 수 없었고, 규칙대로 0으로 두었다.
  - **포구 공 vs Statcast:** 인플레이가 많아 쓸 수 있는 공이 2구뿐이다. 최소 10구에 못 미쳐 `rms_error_feet = null`(미측정)로 두었다.
  - **참고(평가 지표 아님):** 셋업 − 실제 공의 x 중앙값이 −0.75 ft(15구)로 한쪽에 치우쳐 있다.
    - 잴 수 없었던 팬 때문일 가능성이 크다. 이 경기의 x는 카메라 기준으로 믿기 어렵다.
    - 사람 라벨과의 비교는 같은 행렬을 양쪽에 쓰므로 이 편향의 영향을 받지 않는다. 그 비교는 판독만 잰다.
  - 셋업 높이 중앙값은 0.51 ft다. 포수가 릴리스까지 글러브를 땅에 두는 것은 849843과 같다. 프레임 4장을 직접 그려 확인했고, 점은 글러브 위에 있었다.
- **849845 보조 판독 결과** ([JSONL](results/mlb_p0/game_849845_intent_v0.jsonl), 서비스 검사 57/57 통과)
  - 57구 중 추정 43, 기권 14.
  - 기권 이유: 한 판독자만 셋업 찾음 8, 판독자 불일치 6.
    - '한 판독자만'의 대부분은 판독자 B가 "글러브가 땅에 놓여 있어 목표로 내민 것이 아님"이라며 기권한 경우다. A는 같은 글러브를 찍었다.
    - 고정된 규칙대로 기권으로 처리했다.
  - **카메라:** 틸트 5.7°(타자석 판독 129건), 팬 −0.7°(러버 판독 42건, SD 0.002).
  - **포구 공 vs Statcast (13구):** rms 0.149 ft, x 편향 +0.01 ± 0.03 ft, z 편향 +0.06 ± 0.02 ft. 보조 판독만으로 잰 값이고 사람 확인은 0구다.
  - **참고(평가 지표 아님):** 셋업 − 실제 공은 x 중앙값 −0.34 ft(|x| 0.51), z 중앙값 −1.15 ft다. 셋업 높이 중앙값은 0.65 ft로, 이 경기 포수들도 글러브를 땅에 둔다. 프레임 4장을 직접 그려 확인했다.
- **사람 라벨링 팩** (두 경기의 출력을 커밋한 뒤에 만들었다)
  - 823407: [manifest](results/mlb_p0/game_823407_intent_label_pack_v0.json) 29장, pack `c72e8a15a8a67507`
    - 미트 상자 `480,200,960,460`, 플레이트 상자 `580,405,880,465`
  - 849845: [manifest](results/mlb_p0/game_849845_intent_label_pack_v0.json) 57장, pack `e3e7cac83f68ebf1`
    - 미트 상자 `480,170,880,400`, 플레이트 상자 `540,330,780,395`
  - 페이지는 로컬 `outputs/intent_label/game_<경기>_pack.html`에만 있다(MLB 프레임 포함, git 제외).
  - 페이지에 보조 판독 점·상태가 없는 것을 페이지 데이터에서 확인했다.
- **라벨러에게 준 지시** (라벨을 받기 전에 기록)
  - 판독 프롬프트의 셋업 정의를 따른다: 포수가 자리를 잡았고 글러브가 보이면, 글러브가 땅에 놓여 있어도 그 중심을 찍는다.
  - 글러브가 가려졌거나 포수가 아직 앉지 않았거나 중앙 카메라가 아닐 때만 버튼으로 표시한다.
  - 플레이트 앞선은 투수 쪽 가장 아래 직선 모서리의 두 끝을 찍는다.
