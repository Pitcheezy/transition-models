# 결과 클래스 의미 계약 — I-6

이 계약은 서로 다른 결과 확률을 같은 것으로 오인하지 않도록 이름·순서·의미와 입력 검증을 고정한다.
**세 분포를 이름만 바꾸거나 인덱스만 재배열해 변환할 수 없다.**
동료 서비스 호출, 새 모델 학습, 확률 보정, 정책 구현은 이 작업에 포함하지 않는다.

## 검토 기준과 증거

- 우리 기준: [10종 라벨과 매핑](../src/data/features.py),
  [8종 관찰 정답](../src/data/pitch_observation.py), [투구 전 표시 계약](PREPITCH_CONTRACT.md).
- 동료 기준: `SongRoute/pitcheezy`의
  **`9d096940b6fe065051979cd7ef4dbfde006e35c6`**. 2026-09-22 검토 당시 코드다.
  2026-09-27 현재 원격 최신 상태라는 뜻은 아니다.
- 로컬에 남은 Git clone과 추출본의 아래 5개 파일을 비교했다. 줄바꿈을 LF로 통일하면
  Git blob과 모두 일치한다. 동료 코드를 실행하거나 원격에 접속하지 않았다.
- 동료 실제 `/metadata`, 서비스 응답, 모델 번들은 이 계약 검증의 입력이 아니다.
  기존 [팀원 검토 문서](TEAMMATE_PITCHEEZY_2026-09-22.md) §9의 수신 대기는 유지한다.

| 동료 소스 | 확인한 내용 |
|---|---|
| [model.py:18–48](https://github.com/SongRoute/pitcheezy/blob/9d096940b6fe065051979cd7ef4dbfde006e35c6/experiments/pitchmdp/pitchmdp/model.py#L18-L48) | 서비스 10종 순서, 설명/사건 기반 라벨, 지원 행 조건 |
| [planner.py:13–17](https://github.com/SongRoute/pitcheezy/blob/9d096940b6fe065051979cd7ef4dbfde006e35c6/experiments/pitchmdp/pitchmdp/planner.py#L13-L17), [99–110](https://github.com/SongRoute/pitcheezy/blob/9d096940b6fe065051979cd7ef4dbfde006e35c6/experiments/pitchmdp/pitchmdp/planner.py#L99-L110) | 서비스 10종 순서, 카운트에 따른 볼넷·삼진 및 2스트라이크 파울 처리 |
| [outcomes.py:29–87](https://github.com/SongRoute/pitcheezy/blob/9d096940b6fe065051979cd7ef4dbfde006e35c6/src/pitcheezy/interfaces/outcomes.py#L29-L87) | 연구 11종 순서, 종결 우선 매핑, 인플레이 통합 범위 |
| [data.py:214–285](https://github.com/SongRoute/pitcheezy/blob/9d096940b6fe065051979cd7ef4dbfde006e35c6/experiments/pitchmdp/pitchmdp/data.py#L214-L285) | 서비스 학습/평가의 지원 타석 필터; 모델 라벨 함수보다 좁은 범위 |
| [minimal_pitch_service.py:259–264](https://github.com/SongRoute/pitcheezy/blob/9d096940b6fe065051979cd7ef4dbfde006e35c6/experiments/pitchmdp/scripts/minimal_pitch_service.py#L259-L264) | `OUTCOMES` 이름으로 응답 확률 생성, 확률 종류와 정책 목적 구분 |

## 이름과 배열 순서

대소문자와 철자도 계약의 일부다. 이름이 있는 객체는 키로 대응한다.
위치만 있는 배열은 아래 순서를 명시해야 하며 길이가 10이라는 이유로 계약을 추정하지 않는다.

| 인덱스 | 우리 legacy10 | 동료 service10 | 동료 research11 |
|---:|---|---|---|
| 0 | `Ball` | `ball` | `ball` |
| 1 | `Strike` | `strike` | `strike` |
| 2 | `Single` | `foul` | `foul` |
| 3 | `Double` | `out` | `K` |
| 4 | `Triple` | `single` | `BB` |
| 5 | `HomeRun` | `double` | `HBP` |
| 6 | `FieldOut` | `triple` | `1B` |
| 7 | `Strikeout` | `home_run` | `2B` |
| 8 | `Walk` | `hbp` | `3B` |
| 9 | `HitByPitch` | `double_play` | `HR` |
| 10 | — | — | `in_play_out` |

우리 관찰8의 순서는 `ball, called_strike, swinging_strike, foul, caught_foul_tip,
hit, in_play_no_hit, hit_by_pitch`다. 이는 [관찰 정답 정의](../src/data/pitch_observation.py)이며,
이 이름의 예측 모델이 학습·검증됐다는 뜻은 아니다.

## 같은 이름으로 묶으면 놓치는 차이

| 주제 | 우리 legacy10 | 동료 service10 | 동료 research11 |
|---|---|---|---|
| 볼과 볼넷 | 종결 `Walk`와 비종결 `Ball` 분리. `Walk`에는 포수 타격 방해도 포함 | `ball` 확률을 출력하고 planner가 3볼에서 볼넷으로 처리 | `ball`과 `BB` 분리; 규칙 마스크는 3볼에서 `ball`을 금지 |
| 스트라이크와 삼진 | `Strike`에 비종결 파울도 포함; 삼진은 `Strikeout` | `strike`와 `foul` 분리; `strike`는 2스트라이크에서 삼진으로 처리 | `strike`, `foul`, `K` 분리 |
| 파울 번트 삼진 | `events=strikeout`이면 `Strikeout` 우선 | 모델 라벨 함수가 `foul_bunt` + 2스트라이크를 `strike`로 분류 | `events=strikeout`이면 `K` 우선 |
| 인플레이 비안타 | `FieldOut`에 실책·야수선택 출루·병살·삼중살 등 포함 | `out`과 `double_play` 분리. 허용된 사건과 타석만 지원 | `hit_into_play`의 안타 이외 모든 사건을 `in_play_out`으로 통합 |
| 행정 콜 | `automatic_ball`, `automatic_strike` 포함 | 해당 모델 라벨 함수에서는 미지원 | 포함; 관찰8과 다름 |

연구11의 `in_play_out`은 `hit_into_play`이면 알 수 없는 사건이나 `events=None`도 받아들인다.
따라서 `FieldOut`과 `in_play_out`을 실제 아웃 발생 확률이라고 표시하지 않는다.
연구의 [카운트 규칙](https://github.com/SongRoute/pitcheezy/blob/9d096940b6fe065051979cd7ef4dbfde006e35c6/src/pitcheezy/interfaces/outcomes.py#L105-L136)은
볼/볼넷 및 스트라이크/삼진의 허용 카운트를 구분한다. 이런 전이 규칙을 확률 이름 검사와 혼동하거나,
우리 legacy 모델에 그대로 적용해 확률을 지우고 재정규화하지 않는다.

서비스 `model.outcome_labels`에서 라벨이 나온다는 것만으로 실제 서비스 지원 타석이 되는 것은 아니다.
`supported_pa`는 별도 준비 단계에서 타석 중 주자·점수·아웃 변화, 지원 종결 사건, 관측된 카운트 경로,
이닝 범위 등을 검사한다. 실제 배포 지원 범위는 모델 번들과 metadata 확인이 추가로 필요하다.

## 단순 변환을 깨는 코드상 반례

아래는 소스 매핑을 대조한 사례다. 실제 서비스 호출 결과나 새로운 평가 표본이 아니다.
service10 열은 `model.outcome_labels`의 결과이며, 별도 지원 타석 필터 통과를 뜻하지 않는다.

| `description` / `events` | 조건 | legacy10 | service10 라벨 | research11 | 우리 관찰8 |
|---|---|---|---|---|---|
| `foul` / 없음 | 2스트라이크 | `Strike` | `foul` | `foul` | `foul` |
| `foul_bunt` / `strikeout` | 2스트라이크 | `Strikeout` | `strike` | `K` | `foul` |
| `hit_into_play` / `catcher_interf` | — | `Walk` | 미지원 | `in_play_out` | 타격 방해로 제외 |
| `hit_into_play` / `field_error` | — | `FieldOut` | 미지원 | `in_play_out` | `in_play_no_hit` |
| `hit_into_play` / 없음 | — | 미지원 | 미지원 | `in_play_out` | 미지 인플레이 사건으로 제외 |
| `automatic_ball` / 없음 | 비종결 | `Ball` | 미지원 | `ball` | 실제 투구 없는 행정 콜로 제외 |

추가로 우리10은 `events`가 있으면 이를 우선하고 미지 사건에서는 description으로 되돌아가지 않는다.
연구11은 알려진 K/BB 사건 외에는 description을 계속 검사한다. 포수 타격 방해뿐 아니라 주자 사건과
미지 사건의 처리 범위도 같지 않다. 반대로 우리 `Strikeout`만으로 루킹·헛스윙·파울팁·번트 파울의
비중을 복원할 수도 없다.

## 허용 범위와 변환 거부

1. **동일 계약의 검증·표현 이동**은 가능하다. 이름이 있는 확률 객체와 명시적인 순서의 배열은
   같은 계약 안에서 값의 의미를 유지한다.
2. **동일 계약 안의 집계**는 별도 표시 목적일 수 있다. 예를 들어 각 계약의 단타·2루타·3루타·홈런
   확률 합은 그 계약의 다음 투구 안타 확률이다. 접촉했을 때의 안타 확률로 바뀌지 않으며,
   다른 모델과 모집단·학습 범위가 같다는 뜻도 아니다. 이 모듈은 새 집계 API를 추가하지 않는다.
3. **다른 계약 전체로의 자동 변환은 거부한다.** `strike+foul`, `out+double_play`와 같은 합산은
   세부 정보를 버린다. 카운트를 추가해도 포수 타격 방해·행정 콜·미지원 사건·관찰 정의의 차이가 남는다.
   제한된 서비스 사건 집합의 재표현을 연구11 전체나 우리10 전체의 동등한 확률로 인증하지 않는다.
4. **8종과 카운트만으로 10/11종을 복원하지 않는다.** 관찰8의 `hit`에는 안타 종류가 없고,
   `in_play_no_hit`에는 병살 분리 정보가 없다. 기존10/11종에서는 관찰8의 루킹·헛스윙·파울팁을 복원할 수 없다.

## 코드 사용

구현은 [outcome_contracts.py](../src/inference/outcome_contracts.py), 검사는
[test_outcome_contracts.py](../tests/test_outcome_contracts.py)에서 관리한다.

| 상수 | schema ID |
|---|---|
| `LEGACY10_SCHEMA` | `transition_models_legacy10_v1` |
| `SERVICE10_SCHEMA` | `pitcheezy_pitchmdp10_9d09694_v1` |
| `RESEARCH11_SCHEMA` | `pitcheezy_research11_9d09694_v1` |
| `OBSERVATION8_SCHEMA` | `pitch_observation_v1` |

```python
from src.inference.outcome_contracts import (
    SERVICE10_SCHEMA,
    get_contract,
    validate_probabilities,
)

# 합성 입력: 실제 모델 응답이나 성능 결과가 아니다.
contract = get_contract(SERVICE10_SCHEMA)
checked = validate_probabilities(
    SERVICE10_SCHEMA,
    [0.1] * 10,
    class_names=contract.class_names,
)
assert checked["foul"] == 0.1
```

`validate_probabilities`는 이름이 있는 객체를 키로 확인하고 계약 순서의 객체를 반환한다.
배열은 정확한 `class_names`가 필요하다. 누락·추가 이름이나 잘못된 확률을 보정해서 통과시키지 않는다.
`convert_probabilities`는 같은 schema에만 허용되며 다른 schema 요청은 `ValueError`다.
`CORRESPONDENCES`는 문서상 의미 대응을 설명하는 메타데이터이며 변환 행렬이 아니다.
투구별 자료 대응은 `align_pitch_rows`의 키·`play_id` 검사로 수행하고 리스트 위치로 연결하지 않는다.

이 검증은 합성 입력과 고정된 소스 정의의 계약 검사다. 실제 동료 응답 수신·모델 정확도·보정 품질·
정책 효용 검증을 대신하지 않는다. 독립 스트라이크/볼/파울 표시와 목표 위치 추천의 현재 미지원 상태도
이 계약만으로 해제하지 않는다. I-0/I-5의 인터페이스·경기·번들 수신 이후 실제 응답 회귀 검증을 추가한다.
