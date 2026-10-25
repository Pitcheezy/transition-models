# CV-34a — 검토 입력과 프레임 범위 수정 (2026-10-26)

사용자가 Codex의 두 결함 수정을 승인했다. PR67의 고정 `5e90c19343785cea917c94bc5aaf9374406f1581`을 기반으로 별도 `codex/cv-review-repair-1026`에서 작업했다. [선점·합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6401045906). 원래 Claude 폴더·브랜치와 기존 팩/판독/사람 응답은 보존한다. 이 수정은 PR67에 의존하는 연구 코드이며 운영 배포가 아니다.

## 발견과 수정

1. `intent/mitt_pilot.py`는 좌표를 숫자로 바꾸는 단계가 예외 처리 밖에 있어 `[null, 250]`은 TypeError, `["bad", 250]`은 ValueError로 평가 전체를 중단시켰다. 숫자 2개의 유한한 좌표만 수용하고 bool·문자·null 성분·잘못된 앞변 좌표를 해당 행의 `schema` 오류로 분리한다. 정상 숫자는 기존과 같이 처리한다. 이는 좌표 행의 방어이며 임의로 망가진 JSON 파일 전체를 모두 복구한다는 뜻은 아니다.
2. `intent/sequence_review.py`는 눈가림을 위해 앞뒤 격자를 임의 삭제했다. 실제 `747139:4:1`에서 후보 순간이 검토팩 시작보다 약 0.20초 앞에 있어 검토자가 볼 수 없었다. 이제 **원래 릴리스 최근접 기준까지의 모든 격자 프레임**을 보존한다. 후보 결과를 입력받아 창을 맞추지 않는다. crop·불투명 ID·콘텐츠 주소·고정 시각·비공개 대응표는 유지한다. seed는 이중 검토 표본에만 사용한다.

프레임 수로 공개 타이밍과 다시 연결할 수 있는 한계가 있다. 공개 타이밍/AI 결과를 보지 않는 검토자에게만 눈가림이며 완전 익명성을 주장하지 않는다. 원래 저장 영상 앞에 없는 장면을 복구한 것은 아니다. 창 밖 후보/맥락은 비교 불가이며 잘못된 순간으로 채점하지 않는다.

## 검증과 보존

- 관련 Python/JavaScript 회귀와 체크리스트 **51개 통과**. 초반 멈춤 구간·마지막 포함 격자·릴리스 기준 밖 제외·기존 manifest 응답 거부를 확인했다.
- 최초 실행의 Windows 하위 프로세스 문자열 처리 경고 1건은 UTF-8 환경으로 체크리스트 8개를 재실행하여 경고 없이 통과했다. 코드 변경을 추가하지 않았다. Ruff 검사/포맷 통과.
- 기존 325개 저장 판독의 재평가 JSON은 이전 결과와 바이트 단위로 같았다. 새 10구 팩은 625프레임, 39구 팩은 2,366프레임이다. 각 프레임 SHA, 원본 격자와 1:1 대응, 문제 투구의 구간 시작/후보 출력 포함, 옛 응답의 새 manifest 거부를 확인했다. 원본·기존 팩 등 46개 파일의 SHA도 불변이다. 실제 결과·SHA는 [검증 영수증](results/cv_review_repair_20261026/verification.json)에 기록했다.
- 새 모델 호출·새 영상 다운로드·사람 검토·새 정확도 측정은 없다. 기존 개발 평가 결과를 성능 향상으로 다시 보고하지 않는다. 원본 M3·JSONL·timing은 불변이다.
- 별도 동일 모델 에이전트의 변경 코드 읽기 검토에서 추가 P1/P2 없음. 실제 운영용 다른 모델 검토 조건을 대신하지 않는다.

## 새 검토팩

이번 수정 작업 폴더 안의 비공개 출력이다. Git에 프레임을 넣지 않는다.

- `outputs/cv_review_repair_20261026_v2/pilot10_pack/index.html`: 10구.
- `outputs/cv_review_repair_20261026_v2/all39_pack/index.html`: 39구.
- 대응표는 각각 `pilot10_private/private_map.json`, `all39_private/private_map.json`이며 검토자 팩 밖이다.
- 이전 `outputs/cv_mitt_review_seq_20261025/`는 과거 팩으로 보존한다. 기존 응답을 새 팩으로 자동 변환하거나 재검토가 끝난 것으로 처리하지 않는다.

## 재현

저장된 개발 묶음·판독 파일이 있어야 한다. `<saved-bundle>`은 기존 `bundle_v1`, `<saved-pilot>`은 기존 `pilot_v1`의 경로다. 읽기 입력은 기존 자료, 쓰기 출력은 새로운 폴더로 지정한다. 저장 자료가 없으면 새로 모델을 호출하지 말고 인계를 요청한다.

```text
uv run --frozen python -m pytest -q tests/test_mitt_inventory.py tests/test_mitt_dev_bundle.py tests/test_mitt_temporal.py tests/test_mitt_pilot.py tests/test_sequence_review.py tests/test_checklist_model.py
uv run --frozen python -m intent.mitt_pilot evaluate --pilot <saved-pilot> --delivery <saved-pilot>/delivery_start_v1.json --out outputs/pilot_replayed_new.json
uv run --frozen python -m intent.sequence_review build --bundle <saved-bundle> --pack outputs/new_review/all39_pack --private outputs/new_review/all39_private --crop 330,100,950,600
```

10구는 같은 build 명령에 다음 `--pitch`를 추가하고 pack/private 이름을 각각 새 pilot10 경로로 바꾼다.

```text
--pitch 747139:3:1 --pitch 747139:3:2 --pitch 747139:3:3 --pitch 747139:4:1 --pitch 747139:4:2 --pitch 747139:5:1 --pitch 747139:5:2 --pitch 747139:5:3 --pitch 747139:5:4 --pitch 747139:5:6
```

`pilot_replayed_new.json`은 `docs/results/cv_mitt_20261025/pilot_v1.json`과 SHA를 대조한다. 각 새 비공개 대응표의 `frame_indices`는 원본 manifest의 grid 중 `index <= release_index`인 목록과 같아야 한다. manifest의 각 frame SHA와 실제 파일 SHA도 대조한다. 새 응답은 `python -m intent.sequence_review check --pack <new-pack> --response <response.json>`으로 확인한다.

## 다음 일

이번 기술 수리는 사람 응답 없이 완료했다. CV-35의 실제 사람 평가나 독립 평가 완료를 뜻하지 않는다. 반복 판독의 위치 안정성·후보 시각 민감도는 여전히 개선/검증 대상이며, AI끼리 교차 확인할 때는 AI 개발 검증으로 기록한다. Song 공동시험은 고정 절차·시각·준비/양측 GO를 맞춘 뒤 별도로 수행한다. 전시회는 사용자 확정 11/24이며, 요금제·실제30~50명 부하 시험은 11월로 유지한다.
