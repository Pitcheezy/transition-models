# S service-game-v2 로컬 통합 준비

> 2026-10-10: 새 영상 연결과 portable v2 팩의 실행법은 [최신 안내](SERVICE_REVIEW_VIDEO_PACKAGE_20261010.md)를 따른다. 아래 수동 http.server 방식과 옛 출력은 당시 수신 검토 기록이며 그대로 보존한다.

## 2026-10-09 실제 수신 프로필·비공개 로컬 연결

I-service2는 사용자 제공 service-game-v2 ZIP의 원본 검사와 로컬 표시까지 완료했다.
경기849843 262투구/71타석, ready246·unsupported16·missing0,
셋업 estimated27·unavailable12·null223을 대조했다. missing 실제 응답은 이번 파일에 없다.
[수신 기록](SERVICE_GAME_V2_RECEIVED_20261009.md)과 [영수증](results/service_integration_20261009/s_export_receipt_v1.json)을 근거로 읽는다.
검사: 전체 Windows CPU 2120 passed/8 skipped/2 deselected(최종 크기 제한 검사 추가 전, 549.41초); 최종 관련 Python208 passed/1 skipped(25.96초)·Node16 passed; 실제262구 공개 전후 대조 및 로컬 브라우저 확인 완료. 선점 `2b11c06`; 완료는 같은 커밋, 수정 권한 반납.

기본 `teammate_status_20261007_provisional_v1`은 기존 합성 예제와 저장 보고서의 해석을 보존한다.
실제 새 계약은 **`--profile teammate_export_20261009_v1`을 명시**해 선택한다.

```text
uv run --frozen python scripts/inspect_service_game.py --input outputs/service_review_received_20261009/service-game-849843.json --source-kind provided_export --profile teammate_export_20261009_v1
```

새 프로필은 cutoff를 `{index, pitch_key}` 또는 null로 받는다. null은 경계 미상이며,
객체의 index는 공급된 스냅샷 안에서만 해석한다. 키가 있으면 같은 공급 행의 index와 일치해야 하고,
경계를 넘는 행은 거절한다. index는 스냅샷 사이의 안정 키가 아니므로 투구 연결에는 key를 쓴다.
이 경계는 학습 cutoff가 아니다. `game.date_kst`의 유효한 달력 날짜를 출력의 `game.kst_date`로 옮긴다.

`actual.catcher_setup`은 null 또는 명시적 `status/x_band/plate_x_feet` 객체다.
`estimated/unavailable`과 알려진 가로 구역을 검사하며, unavailable은 구역·좌표 모두 null이어야 한다.
좌표는 boolean이 아닌 유한수 또는 null이다. estimated여도 좌표가 null이면 그리지 않는다.
실제 결과를 공개한 뒤 estimated와 유효 좌표 조건을 모두 만족할 때만 가로 위치를 표시한다.
단위는 ft, 포수 시점 오른쪽이 +이며 검토 전 추정치다. 투수 의도나 검증된 최적 목표가 아니다.

`web/service-review`에는 화면 소스만 둔다. 원문·정규화 데이터와 화면 사본은 Git 제외 비공개 폴더에서
제공하며 현재 검토 주소는 `http://127.0.0.1:8794/`다. 새 사본은 이미 존재하지 않는 비공개 경로에 만든다.

```text
uv run --frozen python scripts/build_service_review.py --input outputs/service_review_received_20261009/service-game-849843.json --source-kind provided_export --out-dir outputs/service_review_private_new
uv run --frozen python -m http.server 8794 --bind 127.0.0.1 --directory outputs/service_review_private_new
```

공급 원문은 경기 후 as-of 재생이다. 추천 비중은 사건확률로 바꾸지 않으며,
SHA는 출처 인증이 아니다. 서버 접근·새 모델 추론·사전 가용성·누출 없음·정책 효용·런타임 커밋·
전체 경기 완전성은 검증하지 않았다. 표시 숨김도 접근 통제가 아니다.
**I-0·I-run1·I-release1은 미완료**다. 다음은 합의한 모델/API 실행 번들과 정본/버전 확인이며,
추가 사람 검토·새 기기·독립 영상 조건은 별도로 유지한다.
H-port5 기존54파일 ZIP에는 이 새 프로필과 화면 코드가 포함되지 않는다.
팀원 저장소/API와 공개 사이트는 변경하지 않았다.

## 2026-10-07 잠정 프로필 이력

아래 cutoff 정수·셋업 구조 미확인·실제 원문 미수신 설명은 **옛 기본 프로필의 당시 범위**다.
새 수신 프로필은 위 절을 적용하며, 아래 기록을 삭제하거나 실제 새 수신 결과로 소급하지 않는다.

작성일: 2026-10-07. 이 문서는 우리 저장소의 로컬 JSON 검토 도구를 설명한다.
근거는 전달받은 팀원 **2026-10-07 STATUS 4.3·4.4절**이다.
팀원 S의 실제 응답 원문·현재 서버·현재 코드를 이번 작업에서 검증하지 않았다.

## 현재 범위와 계약 이름

[정규화기](../src/integration/service_game.py)는 공급된 스냅샷의 식별과 값 범위를 검사한다.
[검사 CLI](../scripts/inspect_service_game.py)는 지정한 로컬 JSON 파일만 읽는다.
모델 호출·네트워크 요청·학습·팀원 저장소 수정은 수행하지 않는다.

| 구분 | 이름과 의미 |
|---|---|
| 입력 | `pitcheezy-service-game-v2`: STATUS에 기술된 S 응답 형태 |
| 로컬 출력 | `pitcheezy-service-review-v1`: 우리 검토에 필요한 필드의 투영 |
| 적용 프로필 | `teammate_status_20261007_provisional_v1`: 잠정 허용 규칙 |
| 한 투구 표시 | `pitcheezy-service-pitch-view-v1`: 공개 여부를 적용한 표시 자료 |

출력은 기존 `pitcheezy-receiver-v1` 패킷이나 실시간 프런트 연결 결과가 아니다.
구형 watch/reveal 엔드포인트를 만들거나 WE를 채워 넣는 변환은 없다.
이전에 받은 849843 첫 타석 watch/reveal ZIP은 새 S service-game-v2의 실제 수신 증거로 사용하지 않는다.
기존 사이트와 [M3 평가](INTENT_V0_M3_EVAL.md)는 이번 변경으로 바뀌지 않는다.
공개 화면의 기존 흐름은 [시연 사이트 문서](INTENT_DEMO_SITE.md)를 참고한다.

## 실행 방법

저장소 루트에서 합성 예제를 검사한다. 실제 S 수신 성공을 재현하는 명령은 아니다.

```text
uv run --frozen python scripts/inspect_service_game.py --input docs/examples/service_game_v2_synthetic.json --source-kind synthetic
```

전체 정규화 결과를 새 파일로 남기려면 다음과 같이 실행한다.
`outputs` 폴더가 이미 있어야 하며 `outputs/new.json` 파일은 없어야 한다.

```text
uv run --frozen python scripts/inspect_service_game.py --input docs/examples/service_game_v2_synthetic.json --source-kind synthetic --out outputs/new.json
```

`--out`을 생략하면 파일을 만들지 않고 SHA·집계·경고만 표준 출력에 쓴다.
출력 파일을 지정해도 원문·전체 정규화 자료를 터미널에 출력하지 않는다.
입력 덮어쓰기, 기존 출력 파일 덮어쓰기, 출력 폴더 자동 생성은 허용하지 않는다.
검사 성공은 종료 코드 0, 입력·계약·파일 오류는 종료 코드 2로 구분한다.

실제로 전달받은 로컬 응답에는 `--source-kind provided_export`를 사용한다.
선택 사항인 `--source-revision`에는 전달자가 알려준 7–40자리 16진 revision을 넣는다.
확인하지 않은 revision을 현재 실행 서버의 커밋처럼 기입하지 않는다.

## 출처와 메타데이터

CLI는 **읽은 원본 바이트 전체의 SHA256**을 계산하여 `source.sha256`에 보존한다.
공백·줄바꿈·UTF-8 BOM이 달라져도 바이트가 달라지므로 SHA가 달라진다.
이는 입력 파일 식별자이며 서버나 공급자의 신원을 인증하는 서명이 아니다.
정규화기를 직접 호출할 때는 호출자가 원본 바이트의 SHA를 공급해야 한다.

- `source.input_kind`: CLI의 `synthetic` 또는 `provided_export` 선언.
- `source.reported_revision`: 전달자가 알려준 revision 또는 null.
- `source.upstream_kind`: 응답의 `source.kind`, 즉 `archive`·`live`·`demo`.
- 추천별 `provenance`, `recorded_at`, `policy.name/identity`: 원문에 있는 값만 보존.

`input_kind`와 revision은 **신고된 정보**다. 독립 확인된 출처로 승격하지 않는다.
`game`은 `game_pk`, `start`, `kst_date`, 원정·홈 팀 이름을 투영한다.
`start`가 있으면 시간대를 포함한 ISO 시각을 검사하며, 날짜나 영상 시점을 추정하지 않는다.
`feed.as_of/ok/stale_s`는 보존하지만 신선도나 사전 가용성 인증으로 사용하지 않는다.
`cutoff`는 signed 32-bit 정수 또는 null을 그대로 보존하는 해석 미확정 값이다.
음수도 허용하며 이를 재생초·투구 index로 단정하거나 행 필터에 사용하지 않는다.

## 투구 식별과 사전상황

`key`는 `game_pk:at_bat_number:pitch_number`, `pa_key`는 `game_pk:at_bat_number`와 일치해야 한다.
중복 key·index, 다른 경기 식별자, 원래 index와 타석/투구 순서의 충돌은 거절한다.
입력 배열은 뒤섞여도 되며, 출력은 원래 index로 정렬하고 번호를 새로 부여하지 않는다.
index·타석 번호·투구 번호의 간격은 허용한다. 전체 경기를 빠짐없이 받았다는 뜻은 아니다.

사전상황은 `situation_before`에서만 얻고 최종 점수나 실제 결과로 보충하지 않는다.
행에 반복된 `inning/half`가 있으면 사전상황과 일치해야 한다.
`runners`가 있으면 각 값은 boolean이고 `bases` 비트마스크와 일치해야 한다.
비트는 1루=1, 2루=2, 3루=4다. 문자열·정수로 된 점유 값을 자동 변환하지 않는다.
투수 hand는 L/R/null, 타자 side는 L/R/S/null을 허용하며 이름으로 좌우를 추정하지 않는다.

## 추천 상태·선택 비중·위치

| 상태 | 잠정 처리 규칙 |
|---|---|
| `ready` | 비어 있지 않은 후보 목록을 요구한다. |
| `unsupported` | 후보는 빈 목록이고 전달된 미지원 사유를 보존한다. |
| `missing` | 후보는 빈 목록이며 추천값을 보충하지 않는다. |

`missing`, `absent`, 확률 null은 STATUS의 화면 타입을 참고한 잠정 허용 범위다.
실제 백엔드 응답에서 모든 조합을 확인했다는 뜻은 아니다.
구종 추천 지원과 위치 지원은 독립이다. `ready` 후보도 `target=null`일 수 있다.
좌표가 있는 target은 명시된 지원 구역 이름이 필요하며, 구역 정수를 임의 변환하지 않는다.

`detail.probability`는 `selection_probability`로 옮기는 **구종 정책 선택 비중**이다.
명시적인 null은 미상으로 유지하고 0이나 균등분포로 바꾸지 않는다.
후보는 rank로 정렬하며 중복 순위·구종을 거절하고 상위 3개로 잘라내지 않는다.
알려진 비중 합이 1을 넘으면 수치 허용오차 범위 밖에서 거절한다.
합이 0.8이면 그대로 0.8이다. 합을 1 또는 100%로 다시 맞추지 않는다.
`known_selection_mass`는 알려진 비중의 합이며 전체 분포 확보 여부는 미확정이다.

선택 비중은 스트라이크·안타 등 사건확률이나 성공확률·승리확률이 아니다.
`event_probabilities`는 null이며 [결과 클래스 계약](OUTCOME_CLASS_CONTRACTS.md)을 자동 변환하지 않는다.
target x/z는 ft, 실제 공 x/z는 ft, 구속은 mph로 보존한다.
STATUS가 설명한 위치는 과거 도착 분포의 근사다. 검증된 최적 목표로 표시하면 안 된다.

## 결과 공개와 포수 셋업

정규화 출력은 각 투구의 `pre`와 `post.actual`을 분리한다.
사전상황·선수·추천 안에 중첩된 actual/we/post/result/catcher_setup 필드는 거절한다.
`build_pitch_view(report, pitch_key)`는 정확한 key를 선택하고 기본적으로 `actual=null`을 반환한다.
`revealed=True`를 명시해야 실제 결과가 표시 자료에 포함되며, 원본·출력 객체는 서로 분리된다.
원문과 전체 검토 파일에는 이미 결과가 있다. 표시 숨김은 접근 통제나 사전 추론의 증명이 아니다.

`actual.catcher_setup`의 비null 구조는 아직 확인되지 않았다.
`has_setup_estimate`는 **비null 원자료가 존재한다**는 뜻뿐이며 빈 객체도 해당한다.
`setup_x_ft`는 항상 null이고 원래 셋업 값은 복사하거나 좌표로 해석하지 않는다.
키 이름이 x·setup_x처럼 보여도 단위·방향·검토 여부를 추정하지 않는다.
미트 의도, 제구 오차, 투수/타자 책임 또는 선택의 효과를 이 자료로 판정하면 안 된다.

## 입력 제한과 검증 범위

CLI는 로컬 일반 파일의 UTF-8 JSON을 받으며 입력 상한은 **5 MiB**다.
중복 JSON 키, NaN/Infinity, 비유한수 변환, URL·UNC·장치 경로는 거절한다.
경기당 최대 **2,000투구**, 추천당 최대 **30후보**를 허용한다.
index 0–100000, 타석 1–999, 투구 1–100 등 값 범위는 보수적인 로컬 제한이다.
이 제한과 null 처리 조합은 **공식 S 스키마가 아니다**. 실제 응답 확인 후 버전 관리하며 조정한다.
`current/next/pas/linescore/pregame`은 존재 여부를 기록하되 내용을 정규화 결과에 복사하지 않는다.
그 밖의 알 수 없는 필드도 생략하므로 출력은 원본의 완전한 보존 형식이 아니다.

[계약 테스트](../tests/test_service_game_contract.py)와 [예제](examples/service_game_v2_synthetic.json)는 합성 자료다.
테스트 통과는 로컬 규칙의 동작 근거이며 실제 API 호환성·실시간 연결·정책 성능 근거가 아니다.
실제 응답 대조, 서버 호출, 팀원 코드 검증, 기존 사이트 연결 또는 새 M3 평가는 완료하지 않았다.

## 다음에 받아야 할 자료

1. `ready/unsupported/missing` 실제 JSON 각각과 생성 버전·원본 SHA256. null/누락 조합도 포함한다.
2. null 및 비null `catcher_setup` 실제 형태와 필드 정의, 단위, 좌표 방향, 출처·검토 상태.
3. STATUS의 서빙 `a6dffaea…`, OPE `c13cc989…`, S6-v3 `6eb85ba7…` 정책 식별자 대응 확인.
   코드 재인증이라는 설명만으로 추천값 동등성이나 평가와 서빙의 일치를 확정하지 않는다.
4. 실제 추천 계산·기록·피드 수신·영상 표시 시점과 cutoff 의미를 연결할 근거.
   `captured_live` 표기나 feed UTC만으로 투구 전 가용성·영상 동기화를 주장하지 않는다.

후속 작업과 완료 조건은 [CHECKLIST](../CHECKLIST.md)에 함께 기록한다.
2026-10-07 STATUS 비교 뒤 CV 후속은 보류/응답 대기로 정리했다. 자동 `--next`는 지금 가능한 H-port1을 선택한다.
실제 원문이 도착해 이 통합을 재개할 때는 `scripts/checklist_model.py I-service2`처럼 항목을 명시한다.
