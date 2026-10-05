# 10/6 교수 시연 — CV 발표 대본

2026-10-05 작성. 본문 낭독 목표 60–90초이며 실제 낭독 시간은 리허설에서 확인한다. 아래 대사는 기존 M3 결과 설명용이다. 고정 JSONL·M3 측정·발표 PPTX를 수정하거나 화면 연결 완료를 확인한 문서가 아니다.

## 읽을 대사

저는 영상 속 포수 미트의 AI 판독 결과를 좌표로 바꾸고, 사람 표시와 비교하는 CV 부분을 맡았습니다. Song은 확률·추천과 서비스 화면 연결을 맡습니다.

오늘 ‘포수 미트 위치 추정’은 개발 경기 849843의 사전 처리 결과를 재생하는 시연입니다. 39구 중 좌표가 있는 27구에서 실제 투구 공개 후 가로 위치만 표시합니다.

평가는 별도 경기 849845와 823407에서 했습니다. 전체 86장 중 AI 출력 58장, 기권 28장입니다. 사람은 84장을 표시하고 2장은 기권했습니다. 지금 그림은 보고서가 중앙값에 가장 가깝게 고른 대표 사례입니다.

평가 2경기에서 AI와 사람이 모두 표시한 58구의 미트 점 차이 중앙값은 2.5px입니다. 같은 변환 기준의 좌표 차이는 중앙값 약 1.1인치이며, 물리 정확도나 투수 의도를 검증한 값은 아닙니다.

현재는 오프라인 처리이며 실시간 성능은 검증하지 않았습니다. 다음은 연속 한 타석에서 실제 판독과 처리 시간을 측정하고, 이후 새 영상과 독립 라벨러로 검증하는 것입니다.

## 화면 전환 큐 — 읽지 않는 메모

| 대사 위치 | 보여 줄 것과 확인할 내용 |
|---|---|
| 역할·시연 소개 | 기존 화면 제목 **포수 미트 위치 추정**. 849843은 개발·시연 경기다. 좌표 있는 27구의 x만 실제 투구 공개 후 표시하는 확정 범위를 설명한다. 높이·9구역·투수 의도 표시를 추가하지 않는다. |
| “평가는 별도 경기…” | 기존 CV 요약 장표의 **전체 86장 중 AI 출력 58장 / 기권 28장**을 가리킨다. 사람 표시 84장 / 기권 2장과, AI·사람 좌표 비교 58구의 분모를 구분한다. |
| “지금 그림은…” | 이미 전달한 `intent_comparison_local_20261005.zip`을 풀어 안의 `index.html`을 로컬에서 연다. 처음부터 펼쳐진 **대표 · 849845:10:4**만 본 설명에 사용한다. 이 예시는 849843 시연 타임라인에 없다. |
| 대표 그림 범례 | 전달용 로컬 HTML에서 확인한 범례: **초록 원 = AI 미트 점, 초록 선 = AI 플레이트 앞선, 빨간 십자 = 사람 미트 점, 빨간 선 = 사람 플레이트 앞선.** 필요할 때 “초록 원이 AI, 빨간 십자가 사람 표시입니다”라고 짧게 덧붙인다. |
| 확정 검증 문구 | 본문 네 번째 문단은 리허설 문서의 확정 문구 그대로다. **1.1인치는 평가 58구의 x·z 좌표 거리 차이**이며, 시연 화면의 가로 위치만의 오차가 아니다. 이 문구를 줄이거나 “물리 정확도 1인치”로 바꾸지 않는다. |
| 이후 질문 | 나머지 비교 그림은 질문이 있을 때만 펼친다. 대표 선정은 출력 좌표 거리가 합산 중앙값에 가장 가까운 사례를 코드로 고른 결과다. 성공 사례를 손으로 골라 일반 성능으로 설명하지 않는다. |

로컬 비교 HTML에는 MLB 이미지가 들어 있으므로 기존 비공개 현장 자료로만 사용한다. 별도 공개 업로드나 재전달은 이 대본의 작업 범위에 없다. 화면 연결·맥북·아이폰·전체 시연 동선은 Song 담당이며 실제 화면 확인은 별도 리허설 항목이다.

## 짧은 Q&A 5개

1. **물리 정확도가 1.1인치라는 뜻인가요?**

   아닙니다. 같은 변환 행렬을 쓴 AI·사람 좌표의 차이입니다. 별도 포구 공 대 Statcast 검사는 849845의 13구에서 RMS 0.149ft였지만 사람 확인은 0구입니다. 823407은 2구뿐이라 최소 10구 조건에 못 미쳐 미측정입니다. 물리 정확도는 아직 확정할 수 없습니다.

2. **압축 영상이면 결과가 편향되지 않나요?**

   맞습니다. 재현 가능한 공식 압축 MP4를 사용했지만 타석 마지막 공 위주입니다. 평가 출력은 각각 전체 250구 중 57구, 355구 중 29구이며 무작위 표본이 아닙니다. 이 결과를 전체 투구나 연속 중계의 성능으로 일반화하지 않습니다.

3. **사람 라벨러가 왜 한 명인가요?**

   현재 확보한 검토는 저장소 주인 한 명이 한 번 표시한 자료입니다. AI 점은 숨겼지만 AI가 고른 프레임에 표시했습니다. 사람 간 일치도, 반복 표시의 신뢰도, 프레임 선정의 정확도는 측정하지 못했습니다.

4. **AI 기권은 안전하게 판단을 보류했다는 뜻인가요?**

   그렇게만 설명할 수 없습니다. AI 기권 28구 중 26구를 사람은 표시했습니다. 두 AI 판독자의 합의 규칙과 목표 미트의 해석 차이가 섞여 있습니다. ‘땅에 놓인 글러브도 찍는다’는 사람 지시는 AI 출력을 본 뒤, 사람 라벨을 받기 전에 추가한 해석이며 사전 등록되지 않았습니다.

5. **실시간으로 작동하나요? 다음 단계는 무엇인가요?**

   현재 시연은 사전 처리한 결과를 재생합니다. 기존 절차는 릴리스 주변 영상 창과 투구 후 그래픽도 사용하므로 투구 전 입력만으로 정해진 지연 안에 출력한다고 검증하지 않았습니다. CV-5a에서 연속 한 타석의 실제 관측과 입출력 시간을 계측하고, CV-7에서 미열람 연속 영상·독립 라벨러·평가 manifest를 확보해 새 검증을 진행합니다.

## 수치 근거 — 낭독하지 않는 확인표

모든 키는 저장소의 `docs/results/mlb_p0/intent_accuracy_report_v0.json` 기준이다. 배열 인덱스는 0부터 센다. 보고서 `code_commit`은 `6245038`이며, 이 문서는 보고서를 재생성하지 않았다.

| 대사·답변의 수치 | JSON 키 | 값과 해석 |
|---|---|---|
| 시연 개발 경기 | `development_games[1].game_pk` | `849843` |
| 시연 출력 39구, 좌표 27구 | `development_games[1].pitches_in_output`, `.assistant.estimated`, `.assistant.unavailable` | `39`, `27`, `12`; 사람이 비교한 M3 평가 수치와 별도 |
| M3 평가 두 경기 | `evaluation_pooled.games` | `[849845, 823407]`; 개발 경기는 합산 제외 |
| AI 86 / 58 / 28 | `evaluation_pooled.lines_in_output`, `.assistant.estimated`, `.assistant.unavailable` | 출력 86행 중 좌표 58행, 기권 28행 |
| 사람 86 / 84 / 2 | `evaluation_pooled.frames_decided_by_person`, `.person_marked`, `.person_abstained` | 판단 86장 중 표시 84장, 기권 2장 |
| 오차 비교 분모 58 | `evaluation_pooled.availability.both_marked`, `.mitt_reading_pixels.distance.n`, `.output_vs_person_feet.distance.n` | 모두 `58`; 사람 표시 84장 전체의 오차가 아님 |
| 미트 점 중앙값 2.5px | `evaluation_pooled.mitt_reading_pixels.distance.median` | `2.5298221281347035`px → 2.5px |
| 좌표 차이 중앙값 약 1.1인치 | `evaluation_pooled.output_vs_person_feet.distance.median` | `0.09236584866713454`ft × 12 = 약 `1.10839`in; x·z 거리 차이 |
| AI 기권 28구 중 사람이 표시한 26구 | `evaluation_pooled.assistant.unavailable`, `.availability.person_only`, `.availability.both_abstained` | `28`, `26`, `2`; 26구는 AI 좌표가 없어 거리 비교에서 제외 |
| 합산 대표 849845:10:4 | `evaluation_pooled.example_cases.cases[0].pitch_id`, `.value`; `evaluation_pooled.example_cases.rule` | `849845:10:4`, `0.0924`ft; 합산 중앙값에 가장 가까운 사례, 동률은 pitch_id 순 |
| 849845 전체 250구 중 출력 57구 | `evaluation_games[0].game_pk`, `.coverage.feed_pitches`, `.pitches_in_output`, `.coverage.selection` | `849845`, `250`, `57`; 압축 영상에 나타난 투구 위주 |
| 823407 전체 355구 중 출력 29구 | `evaluation_games[1].game_pk`, `.coverage.feed_pitches`, `.pitches_in_output`, `.coverage.selection` | `823407`, `355`, `29`; 압축 영상에 나타난 투구 위주 |
| 라벨러 owner | `evaluation_games[0].person.provenance.labeler`, `evaluation_games[1].person.provenance.labeler`; `limits` | 양쪽 `owner`; 한 명·한 번의 검토라는 제한은 `limits`와 M3 문서에 명시 |
| E1 포구 공 검사 13구, RMS 0.149ft, 사람 확인 0구 | `evaluation_games[0].camera_check_catch_vs_statcast.{pitches_used,rms_error_feet,human_verified_count}` | `13`, `0.1488494360600154`, `0`; AI·사람 판독 비교와 별도 검사 |
| E2 포구 공 2구, 최소 10구, 미측정 | `evaluation_games[1].camera_check_catch_vs_statcast.{pitches_used,min_pitches,rms_error_feet}` | `2`, `10`, `null`; 물리 오차 0이라는 뜻이 아님 |
| M3 조건 충족의 의미 | `m3_requirement.{met,person_marked,games_with_person_marks}`, `no_threshold` | `true`, `84`, `2`; 경기·라벨 수 조건 충족. 사전 정확도 합격선은 없음 |

픽셀·좌표 거리의 중앙값은 기존 보고서의 nearest-rank 규약이다. 보고서의 판독 일치도·표본 수를 모델 정확도, 의도 검증, 추천 효과 또는 실점 감소의 증거로 바꾸지 않는다.

## 비수치 근거와 준비 상태

- `docs/INTENT_V0_DEMO_REHEARSAL.md`: 확정 검증 문구, 849843 화면 범위, Song의 화면·기기·동선 담당, 미완료 리허설 항목.
- `docs/INTENT_V0_M3_EVAL.md`: 한 명·한 번의 라벨, AI 선정 프레임, 압축 영상 편향, 사후 라벨 지시 해석, 릴리스 주변 창·투구 후 그래픽 사용, 물리 확인 한계.
- `docs/CV_FOLLOWUP_2026-10-05.md`의 담당 표: 본인 CV와 팀원의 확률·프로필·정책·피드·서비스·UI 범위 구분.
- `AGENTS.md` 상단 및 `CHECKLIST.md` CV-5a·CV-7: 다음은 연속 한 타석의 실제 관측기와 시간 계측, 이후 미열람 영상·독립 라벨러 검증. CV-5a의 소수 프레임 호출을 자동 전체 타석·실시간 완료로 설명하지 않는다.
- `outputs/intent_label/delivery_20261005/intent_comparison_local/index.html`과 `README.txt`: 대표 사례, 실제 AI·사람 색·도형 범례, 오프라인 열람 경로 확인. 전달 ZIP의 `manifest.json`은 대표 그림을 `evaluation_pooled.example_cases.cases[0]`에 연결한다.

문서 작성 시 확인한 것은 저장소 문서·JSON·로컬 HTML이다. ZIP 수신 여부, 현장 브라우저 표시, Song 화면 연결 상태와 실제 낭독 시간은 이 확인으로 입증되지 않는다. 기존 전달 사실은 사용자 확인을 따른다.
