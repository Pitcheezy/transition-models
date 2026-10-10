# 우리 프로토타입 소스 이관 안내 — H-port7

갱신일: 2026-10-10. 내부 통합 검토용 **64파일**(기존 54 + 최신 서비스 경로 10)이다.
기준은 `bundle_manifest.json`의 `source_commit`이다. 모든 파일은 그 커밋의 Git blob이며,
원래 저장소·비공개 영상·가중치가 없는 폴더에서도 아래 계약 검사와 영상 없는 화면 생성을 할 수 있다.
**모델 실행 번들 또는 공개 배포 사이트는 아니다.** 팀원 저장소는 변경하지 않았다.

## 먼저 어떤 묶음인지 구분하기

| 묶음 | 목적 | 포함 / 제외 |
|---|---|---|
| 이 소스 ZIP v4 | 우리 코드를 다른 프로토타입에 옮길 때 검토·테스트 | 소스·합성 예제·선택된 보정 및 연결 메타데이터. 실제 S 원문·영상·가중치 없음 |
| 별도 비공개 검토팩 v4 | 전달된 849843 결과와 첫 타석 3클립을 바로 보기 | 정규화 보고서·영상·단독 실행기. 개발용 소스 ZIP과 별개 |
| 기존 운영 모델 ZIP | 우리 예전 운영 모델 재현 | 별도 14개 프로필·가중치·보정 자료. 전체 소스 필요; 팀원 모델 아님 |

소스 ZIP은 웹 루트에 통째로 올리지 않는다. 같은 v4 표기라도 소스팩과 검토팩은 다른 파일이다.
실제 원문·사람 응답·비공개 자료·계정은 이 팩에 들어 있지 않다. 해시는 바이트 변경 검사이며
저자 인증, 권리 증명 또는 모델의 출처 검증이 아니다.

## 무엇을 가져갈 수 있는가

| 계층 | 파일 | 범위 |
|---|---|---|
| S 정규화 | `src/integration/service_game.py`, `scripts/inspect_service_game.py` | 새 수신 프로필과 옛 잠정 프로필을 분리. 키·cutoff·단위·null·공개 전후 검사 |
| 새 S 화면 | `web/service-review/{index.html,review.js,style.css}` | 정규화 보고서 → 추천 → 실제 결과 공개 → 조건을 만족하는 미트 가로 표시. 파일 교체 시 식별자 검사·표시 초기화 |
| 검토팩 생성·실행 | `scripts/build_service_review.py`, `src/integration/service_review_server.py` | 새 폴더/ZIP 생성; SHA 검사, localhost, 허용 파일만 제공, 영상 Range 및 연결 중단 처리 |
| 미트 계약·변환 | `intent/{schema,geometry,plate_feet,run}.py` | 저장 관측 변환·직렬화·근거 검사. `intent.run`은 영상에서 자동 검출하지 않음 |
| 관측 세션 | `intent/{observation_session,replay}.py`, `src/vision/frames.py` | 이미지 SHA·가시성·기권 결속. 전체 영상 루프·제공자는 이 부분집합 밖 |
| 기존 화면 | `web/pitch-studio/` | 이전 홈·서비스 콘셉트·첫 타석 수신기·검증 리포트 소스. 자동 통합/채택을 뜻하지 않음 |
| 회귀 검사 | 선택된 `tests/`, `web/*/*.test.cjs` | 수신·표시·서버·이관·좌표 규약 검사. 정확도나 실기기 사용 시험이 아님 |

기존 `receiver-v1` 화면과 새 `service-review-v1` 화면은 별도다. 새 S 자료는 새 화면을 사용한다.
이 ZIP에서 선택한 기존 `data.js`·`receiver-demo-849843.js`는 이미 관리하던 표시용 자료이며,
`preview-data.js`·`receiver-sample.js`와 새 예제는 합성/설명 자료다. raw export를 복사한 것이 아니다.
`first_pa_media_binding_v1.json`은 기존 3클립의 투구 키·SHA 메타데이터만 포함한다.
영상 파일은 없으며 새 S 응답 자체에 play ID가 있다는 의미도 아니다.

## 1. 소스 무결성 확인

빈 폴더에 압축을 풀고 생성된 최상위 폴더로 이동한다. Python 3.12와 Node가 기준이다.
Windows는 `python` 또는 `py -3`, Mac은 필요하면 `python3`를 쓴다.

```text
python -B -S scripts/build_integration_handoff.py check .
```

표준 라이브러리만 사용한다. 원본 소스팩 안에 `.venv`, `__pycache__`, 테스트 캐시나 출력물을 만들면
추가 파일로 거절한다. 생성물과 개발 사본은 **팩 밖**에 둔다. 삭제·덮어쓰기로 검사를 통과시키지 않는다.

## 2. 새 형식의 합성 자료로 바로 실행

```text
python -B -S scripts/inspect_service_game.py --input docs/examples/service_game_v2_export_synthetic.json --source-kind synthetic --profile teammate_export_20261009_v1
python -B -S scripts/build_service_review.py --input docs/examples/service_game_v2_export_synthetic.json --source-kind synthetic --out-dir ../synthetic-review-new --zip ../synthetic-review-new.zip
python -B -S ../synthetic-review-new/launch_review.py --check
python -B -S ../synthetic-review-new/launch_review.py --open
```

출력 폴더·ZIP은 새 이름이어야 하며 부모 폴더는 있어야 한다. 생성팩은 Python 3.10 이상 표준
라이브러리로 실행된다. 터미널에 표시된 `127.0.0.1` 주소는 그 컴퓨터에서만 열린다. 종료는 Ctrl+C.

합성 3구는 ready/unsupported/missing 각 1개다. 존재하는 ready 행을 선택해 실제 결과를 공개하면
가상의 미트 가로값 0도 볼 수 있다. 영상은 없고 실제 서비스 응답·정확도·사람 검토 결과가 아니다.
옛 `service_game_v2_synthetic.json`은 옛 잠정 프로필 검사 용도로 보존했다. 새 빌더에는 새 예제를 쓴다.

## 3. 별도 전달받은 실제 S JSON 연결

실제 원문은 이 ZIP에 없다. 받은 원문을 별도 비공개 폴더에 보존한 뒤 경로를 넣는다.

```text
python -B -S scripts/inspect_service_game.py --input ../private-input/service-game-849843.json --source-kind provided_export --profile teammate_export_20261009_v1
python -B -S scripts/build_service_review.py --input ../private-input/service-game-849843.json --source-kind provided_export --out-dir ../private-review-new --zip ../private-review-new.zip
python -B -S ../private-review-new/launch_review.py --check
python -B -S ../private-review-new/launch_review.py --open
```

원문을 변경하지 않고 별도 정규화 자료를 만든다. 출력은 비공개로 보관한다.
`--include-first-pa-video`는 이 소스팩만으로 사용할 수 없다. 별도 허용된 정확한 6개 미디어 파일이
`web/pitch-studio/media/`의 지정 경로에 있어야 하며, 원문 SHA와 각 영상/포스터 SHA가 기존 바인딩과
일치해야 한다. 경로·해시를 바꿔 임의 경기와 연결하지 않는다. 미디어를 추가한 개발 사본은 원본
소스 ZIP과 구분한다. 이미 생성된 비공개 영상 검토팩을 보는 것과 소스팩 개발은 별개다.

실제 수신 원문은 경기849843의 262구/71타석, ready246·unsupported16·missing0이다.
미트는 estimated27·unavailable12·null223이다. 원문은 경기 후 as-of 재생이며 런타임 커밋·
사전 가용성·누출 없음·정책 효용·경기 전체 완전성을 검증하지 않았다. 실제 missing 사례는 없다.
이 숫자는 기존 수신 검사 결과이고 이 팩의 합성 3구 결과가 아니다.

## 4. 압축 해제본에서 테스트

새 서비스 경로만 검사:

```text
python -B -m pytest -q -p no:cacheprovider tests/test_service_game_contract.py tests/test_service_game_cli.py tests/test_service_review_package.py tests/test_service_review_server.py
node --test web/service-review/review.test.cjs
```

기존 CV·구형 화면과 전달 도구도 검사:

```text
python -B -m pytest -q -p no:cacheprovider tests/test_integration_handoff.py tests/test_intent_v0.py tests/test_intent_m2.py tests/test_intent_observation_session.py
node --test tests/js/pitch_receiver.test.cjs tests/js/pitch_home.test.cjs web/pitch-studio-tests/receiver-intake.test.cjs web/pitch-studio-tests/receiver-first-pa.test.cjs
python -B -S scripts/build_integration_handoff.py check .
```

Python 테스트는 팩 밖의 pytest 환경을 사용한다. CV 검사에는 numpy·Pillow가 추가로 필요하고,
Git 바이트 이관 검사에는 Git이 필요하다. 기존 개발 환경 기준 Python3.12, pytest9.0.3,
numpy2.4.4, Pillow12.2.0이다. Node 검사는 추가 npm 설치가 없다. 이 팩에는 전체 학습 의존성/lock이
없어 `uv sync`나 전체 프로젝트 검사를 실행하지 않는다. 전체 재현은 같은 source_commit의 전체
저장소·`uv.lock`·`docs/MAINTENANCE.md`를 사용한다. 실제 Mac/아이폰 사용 확인과 자동 검사는 다르다.

## 수치·좌표·기능을 옮길 때 유지할 의미

- `detail.probability` / `selection_probability`는 구종 선택 비중이다. 스트라이크·안타 사건확률이 아니다.
- 후보 위치는 과거 도착 분포의 근사다. 검증된 최적 목표 또는 투수 의도로 표시하지 않는다.
- actual의 x는 홈플레이트 중심 기준 가로(ft), 포수 시점 오른쪽이 +다. z는 지면 기준 높이(ft).
  cm 표시는 원 실수에 30.48을 곱한다. 화면/카메라 좌우나 타자 몸쪽/바깥쪽과 같다고 하지 않는다.
- 새 프로필의 미트는 `estimated`이며 유한 x가 있을 때 **결과 공개 후 가로만** 표시한다.
  `unavailable` 또는 null은 그리지 않는다. 미트 높이·제구 책임·물리 오차를 계산하지 않는다.
- 셋업과 실제 도착점은 동일 물리 평면의 정답 쌍으로 검증되지 않았다. 두 값을 빼서 제구 오차라고 하지 않는다.
- 표시 숨김은 사용자 동선이지 접근 통제/투구 전 추론 증거가 아니다. 자료는 이미 브라우저에 있다.
- M3는 2경기86프레임, AI58출력·28기권, 함께 표시한58개에서 중앙값2.53px·90분위6.51px.
  사람1명 판독과의 차이이며 물리 정확도/독립 실시간 정확도가 아니다. 새 모델 성능 주장에 합치지 않는다.

## 남은 통합 조건과 소유권

우리 담당은 CV/좌표 근거·자료 결속·계약 검사·화면의 보존/이식이다. 팀원 모델·API·백엔드는 수정하지 않는다.
최종 화면/백엔드/기준 브랜치 채택은 미합의다. 모델/API 실행 번들·의존성·정본 버전이 있어야
I-run1을 시작한다. 실제 기기·공개 권한·운영 검증은 I-release1 조건으로 남는다.
A-y44구 사람 검토는 사용자가 보류했으며 서비스 마무리 선행 조건이 아니다. 재배정하지 않는다.
CV-6 추가 독립 검토·CV-7 새 영상 평가는 별도 연구 조건이고 이 소스팩 작업으로 완료되지 않는다.
추가 의존 목록 `external_artifacts_v1.json`은 10/7 조사 스냅샷이며 최신 원문/모든 산출물 목록이 아니다.
`LEGACY_PROJECT`는 옛 transition-models, `INTENT_PROJECT`는 현재 feature/intent-v0 경로 별칭이다.
계정·DNS·API 키를 전달하지 않으며 영상의 기존 공개 결정은 다른 자료의 일반 재배포 권한이 아니다.

## 다시 생성하기와 이전 이력

전체 저장소에서 목록·소스를 커밋한 뒤 명시적인 커밋 SHA로 새 폴더/ZIP을 만든다.

```text
python -B scripts/build_integration_handoff.py build --source-ref FULL_COMMIT_SHA --out outputs/service_review_source_new
python -B -S scripts/build_integration_handoff.py check outputs/service_review_source_new
```

명시 목록의 Git blob만 담는다. 미커밋 파일·LFS 포인터·영상·가중치를 복사하지 않는다.
이번 전달 식별·압축 해제 검사 결과는 전체 저장소의 `docs/handoff/delivery_v4.json`, 파일별 근거는
`docs/handoff/source_manifest_v4.json`에 기록한다. 두 기록은 자기 포장 순환을 피하려고 ZIP 밖에 둔다.
이전 v1/v2/v3 ZIP·manifest·receipt는 변경하지 않는다. v3(54파일)는 소스47ddc8f의 고정 전달물이며
새 S 화면은 없었다. v4는 기존 H-7/H-9/H-10/H-12/H-13 수정과 I-service2~6을 포함한다.
사람 검토 UI·전체 관측 루프·모델 제공자·운영 학습/추론은 부분집합 밖이다.
