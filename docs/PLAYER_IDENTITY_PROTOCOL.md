# 투수·타자 식별 규약과 개발 평가 준비 — F-4a

**한 타석의 화면 판독과 출처 분리를 준비한 단계다.** 자동 선수 이름 OCR, 실시간 선수 추적,
선수 교체 인식 성능 또는 F-4a 전체 완료를 뜻하지 않는다. 기존 점수판 숫자 OCR과도 별개다.

경기 747139의 PA6, 6개 판단 프레임에서 투수·타자 역할을 각각 기록했다. 2026-09-27 Codex 세션이
이미 알려진 경기 자료를 보며 직접 판독한 **AI-assisted, 비블라인드 개발 자료**다.
사람 간 독립 일치도나 새 홀드아웃 정확도로 보고하지 않는다.

## 기준값과 관찰값은 다른 자료다

| 자료 | 역할 | 사용하면 안 되는 해석 |
|---|---|---|
| 공식 최종 feed의 PA matchup | 재생 평가에서 투수·타자 ID와 이름을 대조하는 기준값 | 당시 실시간으로 수신한 입력, 화면에서 인식한 ID |
| 경기 boxscore의 선수 목록 | 화면 문자열을 대조할 경기 전체 이름 사전 | 특정 프레임의 선수나 초기 라인업을 자동 확정하는 정답 |
| 판단 프레임에서 읽은 문자열 | `name_text`, 역할, 타순 등 실제 보인 값 | feed ID를 복사한 관찰값 |
| 고정된 투구 timing | 수동으로 맞춘 재생 초와 투구 키 | 자동 중계 동기화, feed UTC의 보간값 |

화면 기록에는 `MEGILL`, `OZUNA`처럼 실제 읽은 문자열을 넣고 보이지 않은 필드는 null로 둔다.
선수 ID는 화면 판독값에 넣지 않는다. 화면에서 읽은 타순 3과 feed 기준 ID가 일치하더라도
타순에서 ID를 직접 읽었다고 표현하지 않는다.

### 고정 출처

- feed: `data/raw/mlb_video/747139/feed.json` — Git 제외 원본.
- 원본 URL: `https://statsapi.mlb.com/api/v1.1/game/747139/feed/live`.
- feed 바이트 SHA256:
  `cd12bf34bbabd57f8db6073294fc1d8938f47c127043e128e0ea7bbb18bebd59`.
  [manifest](results/mlb_p0/game_747139_manifest.json)의 `feed_sha256`와 일치한다.
- manifest canonical SHA256:
  `4d036f94f5b5bddc682e846960dbc40de5ae35c4e023581efa12167475e062da`.
- timing canonical SHA256:
  `820d18012f418e35699ebe8187be3a9fe891644f4966707ae4489d0538e997a1`.
- 실제 화면 판독 원문: [PA6 review](results/mlb_p0/game_747139_player_identity_review_pa6.json).
  각 기록의 원본 영상 URL·재생 초·이미지 해시·증거 경로를 보존한다.

이 feed는 `status=Final`, `metaData.timeStamp=20240930_200937`인 최종 경기 기록이다.
이 값은 수신 시각이나 영상 재생 초가 아니다. 과거 시점에 실제 도착한 feed 스냅샷이 없으므로
여기서 실시간 가용성·지연·사전 예측 입력의 적법한 시점을 검증하지 않는다.
이름 사전도 최종 경기 명단에서 고정한 replay 자료다. 실시간 경로에는 당시 확보한 명단과
교체 이벤트의 수신 시점을 별도로 검증해야 한다.

## PA6 기준과 직접 읽은 범위

공식 feed의 `/liveData/plays/allPlays/5`는 `about.atBatIndex=5`, 즉 PA6이다.
투수는 **Tylor Megill 656731**(NYM, 원정), 타자는 **Marcell Ozuna 542303**(ATL, 홈)이며
우투·우타다. 1회말이고 Ozuna의 경기 boxscore 타순은 `300`, 즉 3번이다.
PA6에는 6개 투구와 견제 이벤트 1개가 있고 선수 교체는 없다.

[mlb_video.py](../src/data/mlb_video.py)의 투구 키·`play_id` 대조로 6개 투구의 투수·타자 ID가
manifest와 일치함을 확인했다. `playEvents`에는 견제가 끼므로 목록 위치를 투구 번호로 사용하지 않는다.
평가 행의 증거 시각은 해당 판단 프레임과 정확히 일치해야 한다. 더 이른 프레임을 새 직접 관찰로
기록하지 않고, 과거 값의 유지는 별도 연속성·신선도 규칙을 통과한 `held`로만 다룬다.

| 투구 | 판단 재생 초 | 투수 문자열 | 타자 문자열 / 타순 |
|---|---:|---|---|
| 6/1 | 481.00 | `MEGILL` | 배너 없음: null / null |
| 6/2 | 525.50 | `MEGILL` | `OZUNA` / 3 |
| 6/3 | 548.95 | `MEGILL` | `OZUNA` / 3 |
| 6/4 | 576.50 | `MEGILL` | `OZUNA` / 3 |
| 6/5 | 611.45 | `MEGILL` | `OZUNA` / 3 |
| 6/6 | 663.50 | `MEGILL` | `OZUNA` / 3 |

6프레임 × 2역할의 **12개 기록 중 11개 이름을 직접 읽었고, 1개는 타자 배너가 없었다.**
배너가 없는 기록은 현재 스키마에서 `readability=unreadable`, `name_text=null`로 저장하고
note에 부재 이유를 명시한다. 11/12는 이 선택 자료에서 이름이 보인 범위이며 자동 인식 정확도가 아니다.
다섯 타자 배너의 전체 문구 `3.OZUNA .304`에서 이름과 타순을 분리해 기록했다.
팀은 이 이름 배너에서 별도로 읽지 않아 모든 화면 기록의 `team`을 null로 두었다.

470초의 타자 소개 그래픽에는 `OZUN…`까지만 확인됐다. 대각선 그래픽이 이름 일부를 가려
`partial`인 **문맥 기록**으로만 보존한다. 판단 프레임의 이름 정답이나 이전 확정값의 출처로 쓰지 않는다.
481초에 없는 타자 이름을 470초의 불완전한 글자나 이후 525.50초의 완전한 이름으로 채우지 않는다.

## 읽기 상태, 이름 대응과 기권

원문 `readability`와 이름 대응 결과를 분리한다. `readable`은 글자가 읽힌다는 뜻이지
선수 ID까지 확정됐다는 뜻이 아니다.

- 완전하게 읽힌 이름만 경기 **전체** 선수 목록의 이름/별칭과 대응한다. 대소문자·악센트·공백을 정규화한
  정확한 이름 일치만 허용한다. 후보가 하나일 때만 이름 기반 ID 대응을 허용한다.
  정답 matchup ID나 기대 역할에 맞춰 후보를 줄이지 않는다.
- `partial`은 읽힌 부분을 그대로 남긴다. 접두사·오타 보정·희망하는 정답으로 완성하지 않는다.
- 같은 이름의 후보가 여러 명이면 `ambiguous` 원인으로 기권한다. 예를 들어 이 경기 PA60의
  투수 Raisel Iglesias와 타자 Jose Iglesias는 모두 `IGLESIAS`가 될 수 있다.
- 읽힌 이름이 사전에 없거나 의미가 불분명하면 기권한다. 다른 역할·타석의 정답 ID로 대체하지 않는다.
- `team`은 화면에서 실제 읽었을 때만 전체 명단의 팀과 대조해 후보를 제한한다. feed의 기대 팀을
  관찰값으로 채우지 않는다. `lineup_order`는 화면에서 읽은 부가 정보로 보존하며 ID 추론에 쓰지 않는다.
  최종 boxscore의 타순으로 현재 화면의 선수를 좁히거나 타순을 자동 채우지 않는다.

파생 상태는 `observed`(해당 프레임의 직접 판독), `held`(이전 확정값 유지), `abstain`(기권)을 구분한다.
기권 이유, 이전 확인 시각, `age_seconds`, 신선도와 근거를 함께 남긴다. held는 새 직접 판독이 아니다.
원문·이름 대응·최종 feed 기준을 따로 보존해야 오판독과 이름 모호성을 구분할 수 있다.

## 교체와 신선도

이 준비 단계의 신선도 기준 **30초는 개발용 정책값이며 검증된 성능 기준이 아니다.**
시간이 짧다는 이유만으로 동일 선수가 계속 있다고 가정하지 않는다.

- `continuity=confirmed`는 해당 역할의 이전 확인부터 현재까지 교체·역할 변화가 없음을 확인했다는
  명시적 근거가 필요하다. 선택한 두 정지 화면의 이름이 같다는 사실만으로 만들지 않는다.
- `changed`나 `unknown`, 오래된 값, 모호하거나 모순된 관찰에서는 과거 ID를 현재 확인값으로 승격하지 않는다.
  이름을 읽지 못해도 현재 화면에서 읽은 팀이 이전 선수의 팀과 다르면 유지하지 않고 기권한다.
- 타석이 바뀌면 이전 상태를 넘기지 않는다. 같은 투수가 계속 던져도 새 타석의 관찰부터 다시 시작한다.
- 투수 교체, 대타, 대주자, 수비 위치 변경을 구분한다. 이 경기의 PA58 대타 Marte는 타자 교체지만
  PA65 대주자 Acuña는 현재 타자 Taylor의 교체가 아니다. PA71의 대주자 Merrifield도 타자 Harris를 바꾸지 않는다.

이번 PA6 원문 12개 기록의 `continuity`는 모두 **`unknown`**이다. 프레임 사이 연속 관찰을 수행하지 않았으므로
이 자료는 held의 실제 성공률이나 교체 감지 성능을 입증하지 않는다. 현재 기록은 직접 관찰 11개와 기권 1개다.

## feed의 역할·라인업 함정

일반 선수 프로필과 해당 경기 기록을 혼동하지 않는다. 같은 고정 feed 안에서도 아래 값이 다르다.

| 선수 | `gameData.players.primaryNumber` | 해당 경기 boxscore `jerseyNumber` |
|---|---:|---:|
| Tylor Megill | 58 | 38 |
| Marcell Ozuna | 24 | 20 |

일반 프로필에는 2026년 기준 나이처럼 경기 이후 갱신된 정보도 있다. 이 필드로 2024년 영상의
유니폼 번호·당시 소속을 판정하지 않는다. 위 번호는 출처 차이를 설명할 뿐 이번 이름 대응에 사용하지 않는다.

최종 boxscore의 `battingOrder` 배열은 교체 선수를 반영한다. 이를 초기 라인업이나 매 타석의 선수 목록으로
역투영하지 않는다. PA6 Ozuna의 3번 타순은 개별 경기 기록과 해당 PA matchup을 대조한 replay 기준이다.
또한 `matchup.postOnFirst` 등 사후 상태나 타석 완료 결과를 투구 전 관찰값으로 사용하지 않는다.

기존 `feed_pitch_index`는 PA matchup을 그 타석의 각 투구에 붙인다. PA6처럼 교체가 없는 타석에서는
대조 근거가 있지만, 일반적인 타석 도중 투수·타자 교체까지 재구성하는 함수는 아니다.
그런 타석을 추가할 때는 이벤트 순서를 확인하고 투구별 ID 기준이 불확실하면 보류한다.
이번 평가셋 생성기는 대상 타석에 교체 또는 수비 위치 변경 이벤트가 있으면 보수적으로 거부한다.

## 재현과 다음 범위

구현은 [player_identity.py](../src/data/player_identity.py), CLI는
[73_build_player_identity_evalset.py](../scripts/73_build_player_identity_evalset.py)다.
저장소 루트에서 다음 명령을 실행한다.

```bash
uv run --frozen python scripts/73_build_player_identity_evalset.py build --verify-frames
uv run --frozen python scripts/73_build_player_identity_evalset.py check --verify-frames
uv run --frozen python scripts/73_build_player_identity_evalset.py summary
```

기본 출력은 [PA6 평가 자료](results/mlb_p0/game_747139_player_identity_evalset_pa6.json)다.
`--manifest`, `--timing`, `--feed`, `--review`, `--output`으로 명시적 경로를 지정할 수 있다.
사용자 입력으로 build할 때는 별도 `--output`을 지정해야 하며 기본 PA6 평가셋에 덮어쓸 수 없다.
출력 경로가 현재 입력 또는 기본 입력 파일과 같으면 거부한다.
build에는 고정 원본 feed가 필요하며 없으면 실패한다. 자동 다운로드하거나 임의의 명단으로 대체하지 않는다.

check는 원본 feed가 있으면 전체 재생성을 대조해 `validation_level=full_input_rebuild`,
`feed_bytes_reverified=true`를 보고한다. 원본이 없으면 커밋된 입력 해시와 동결된 이름 사전·기준·관찰에서
다시 계산한 `frozen_snapshot_recomputed`이며 `feed_bytes_reverified=false`다.
summary 역시 동결 자료를 다시 계산하지만 원본 feed의 바이트 검증을 대신하지 않는다.

`--verify-frames`는 지정한 로컬 이미지 자체의 바이트와 영상 출처·시각의 캐시 근거까지 확인한다.
같은 출처·시각의 다른 캡처가 존재해도 지정한 이미지의 유효한 근거를 대신 선택하지 않는다.
이 옵션 없이 통과한 구조 검사를 이미지 파일까지 확인한 결과라고 보고하지 않는다.
구현·CLI의 build/check/summary는 원문과 feed 기준을 분리한 평가 자료를 생성·검사한다.
이미지 해시는 동일한 증거 파일인지 확인할 뿐 내용이 올바르게 판독됐음을 자동 증명하지 않는다.
원본 feed 없이 수행하는 구조 검사는 feed 원본을 읽고 전체 자료를 재생성한 검증과 구분한다.

다음 확장에는 실제 이름 인식 경로와 역할/모호성/교체/신선도 사례의 검증이 필요하다.
이 경기에서 만든 규칙의 새 독립 성능에는 미검토 영상이 필요하다. feed ID 자동 입력만으로
화면 선수 인식 완료를 표시하거나 현재 UI의 미지원 기능을 켜지 않는다.
