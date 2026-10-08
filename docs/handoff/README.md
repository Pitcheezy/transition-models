# 우리 프로토타입 최소 이관 묶음 — H-port4

갱신일: 2026-10-08. `Pitcheezy/transition-models`, `feature/intent-v0`의 내부 팀 검토용 소스49개 부분집합이다.
정확한 기준 커밋은 함께 받은 `bundle_manifest.json`의 `source_commit`이다.
파일 목록은 `docs/handoff/source_files_v1.json`, 별도 자료 목록은 `external_artifacts_v1.json`이다.
모든 파일의 출처는 같은 기준 커밋의 Git blob이다. Windows 체크아웃의 줄바꿈 변환은 적용하지 않는다.
해시는 전달 중 변경을 탐지하는 식별자이며 저자 인증 서명이나 재배포 권한 증명이 아니다.

## 이번 새 묶음에 반영한 수정

- H-7: 수신기의 존재하지 않는 Gregorian 날짜를 거부한다. 정상 시간대·소수초·생성 시각 원문은 보존한다.
- H-9: 좌표 변환에서 요청 경기와 timing·points·calibration의 경기 식별자를 대조한다.
- H-10: 명시적으로 지정한 보정 경로가 잘못되면 출력 전에 거부한다. 보정 옵션을 생략한 경우의 기존 기본 동작은 유지한다.
- CV-28: 새 AI `marked/partial` 응답은 부분 가림의 비어 있지 않은 이유가 필요하다. 요청 문구와 수신 검사가 이를 명시한다.

좌표 변환의 회귀 검사 `tests/test_intent_m2.py`를 추가했다. 나머지는 기존48개 소스 범위를 유지한다.
2026-10-07의 H-port1 원본 ZIP·전달 기록·파일 manifest는 보존하며 이 새 ZIP으로 덮어쓰지 않는다.
표시된 수정은 입력·도구의 동작 수정이며 새 모델 정확도나 팀원 서비스 연결을 의미하지 않는다.

H-8의 `intent/review_ui.js`는 이 부분집합에 없다. 사람 검토 UI를 쓰려면 전체 저장소나
별도 `outputs/cv_review_20261008_ui_v2/reviewer` 팩을 사용한다. 그 팩의 이미지·사람 응답은 이 ZIP에 넣지 않는다.
H-10의 반복 판독 RMS 0 보존 수정은 별도 보정 생성기 `intent/calibrate.py`에 있으며 이 부분집합에는 없다.
보정 생성기와 전체 관측 루프·모델 제공자·과거 관측 보고서는 기준 커밋의 전체 저장소에서 사용한다.

## 무엇을 바로 가져갈 수 있는가

| 부분 | 경로 | 이 묶음에서 확인하는 범위 |
|---|---|---|
| S 응답 검사 | `src/integration/service_game.py`, `scripts/inspect_service_game.py` | 투구 키·단위·null·선택 비중·공개 전후 분리. STATUS를 바탕으로 한 잠정 규약이며 실제 새 S 원문 미수신 |
| 미트 계약 | `intent/schema.py` | IntentEstimate v1의 상태·출처·좌표 변환 근거 검사. 검출 모델이 아님 |
| 이미지 관측 계약 | `intent/observation_session.py`, `intent/replay.py`, `src/vision/frames.py` | 이미지 SHA·픽셀·가시성·기권을 갖는 별도 `intent_visual_observation_v1`의 begin/finish. mapped 경로와 전체 루프는 전체 저장소 필요 |
| 좌표 변환 | `intent/geometry.py`, `intent/plate_feet.py`, `intent/run.py` | 저장 주석을 변환·직렬화. `intent.run`은 영상에서 미트를 자동 검출하지 않음 |
| 화면 | `web/pitch-studio/`의 HTML/CSS/JS | 홈·서비스 콘셉트·첫 타석 수신기·검증 리포트의 기존 소스. 현재 공개 영상 파일은 제외 |
| 회귀 검사 | `tests/`, `web/pitch-studio-tests/`에 선택한 파일 | 합성 계약 검사와 저장 응답/화면 로직 검사. 실제 API·실기기·모델 성능 검사가 아님 |

기존 화면은 구형 watch/reveal을 받은 `pitcheezy-receiver-v1` 경로를 사용한다.
새 S `service-game-v2` 검사 출력과 자동 연결된 상태가 아니다. S의 실제 응답을 받은 뒤 I-service2에서 연결한다.
`receiver-demo-849843.js`는 이미 수신한 첫 타석의 표시용 자료, `receiver-sample.js`와 `preview-data.js`는 예시다.
`data.js`는 공개 화면용 투구별 39행과 집계이며 원본 사람 검토 메타데이터를 포함하지 않는다.

## 압축을 받은 사람이 실행할 순서

빈 폴더에 압축을 풀고 생성된 최상위 폴더로 이동한다. Python 3.12 이상과 Node가 필요하다.
Python은 `python`, macOS에서 필요하면 `python3`로 실행한다. 아래 명령은 Windows/macOS/Linux에서 같은 상대 경로를 사용한다.

먼저 파일을 수정하지 않은 상태에서 확인한다. Python 표준 라이브러리만 쓴다.

```text
python -B -S scripts/build_integration_handoff.py check .
python -B -S scripts/inspect_service_game.py --input docs/examples/service_game_v2_synthetic.json --source-kind synthetic
```

첫 명령은 파일 수·크기·SHA·추가 파일을 확인한다. 묶음 안에 `.venv`, `__pycache__`, 출력 파일을 만들면 추가 파일로 거절한다.
개발용 사본은 따로 사용한다. 두 번째 명령의 3개 행은 ready/unsupported/missing 각 1개인 **합성 예제**다.
실제 S 자료를 받으면 별도 위치의 원문과 전달받은 revision으로 `--source-kind provided_export`를 사용한다.
원문은 그대로 보존하고 화면용 투영과 구분한다. API 호출이나 모델 실행은 일어나지 않는다.

영상 없이 실행하는 화면 회귀 검사:

```text
node --test tests/js/pitch_receiver.test.cjs tests/js/pitch_home.test.cjs web/pitch-studio-tests/receiver-intake.test.cjs web/pitch-studio-tests/receiver-first-pa.test.cjs
```

계약·좌표 변환 Python 테스트는 `pytest`, `numpy`, `Pillow`가 있는 **묶음 밖 환경**에서 실행한다.
개발 환경에서 확인한 버전은 Python 3.12, numpy 2.4.4, Pillow 12.2.0, pytest 9.0.3이다.

```text
python -B -m pytest -q -p no:cacheprovider tests/test_service_game_contract.py tests/test_service_game_cli.py tests/test_intent_v0.py tests/test_intent_m2.py tests/test_intent_observation_session.py
```

이 부분집합에는 연구 학습 코드·전체 의존성 lock·모델 가중치가 없다. 이 안에서 `uv sync`나 전체 프로젝트 검사를 실행하는 패키지가 아니다.
학습/전체 실행이 필요하면 우리 전체 저장소를 같은 `source_commit`으로 체크아웃하고 그 커밋의 `pyproject.toml`, `uv.lock`, `docs/MAINTENANCE.md`를 따른다.

새 AI 응답의 부분 가림 이유 요구는 새 세션에 적용한다. 이전 코드로 시작한 세션을 새 코드로
끝내는 것은 기존 코드 SHA 검사에서 거부되므로 새 폴더로 시작한다. 과거 응답을 고치거나
이유를 만들어 채우지 않는다. 전체 저장소의 보고서는 저장된 요청의 옛/새 계약을 구분해 읽는다.

화면 구조만 로컬로 보려면:

```text
python -B -m http.server 8769 --bind 127.0.0.1 --directory web/pitch-studio
```

`http://127.0.0.1:8769/report.html`은 저장 수치의 검토 화면이다. 홈/첫 타석 영상은 이 묶음에 없어 재생할 수 없다.
영상까지 필요하면 외부 목록의 승인된 11개 자산을 개별 확인하여 같은 상대 경로에 별도 복사한다.
그 시점부터 원본 소스 묶음 검사는 추가 파일을 검출하므로 확장한 사본은 원본과 구분한다.
`check_pitch_studio.py` 전체 검사는 영상·출처 manifest가 있는 전체 저장소에서만 수행한다.
이 묶음을 웹 루트에 통째로 올리지 않는다. 외부 자료 목록과 내부 안내는 공개 배포물이 아니다.

## 수치와 좌표를 옮길 때 지킬 의미

- `detail.probability`/`selection_probability`는 구종 선택 비중이다. 스트라이크·안타 확률이나 승률이 아니다.
- S의 후보 위치는 과거 실제 도착 분포의 근사라는 전달 설명을 유지한다. 검증된 최적 목표라고 부르지 않는다.
- 미트는 투구 전 프레임에서 읽은 대리값이며 시연에서는 실제 공 공개 후 **x만 ft 단위**로 표시한다. 높이·투수 의도·제구 오차로 확대하지 않는다.
- 미트 화면 좌표와 Statcast 도착 좌표는 같은 물리 평면의 정답 쌍으로 검증되지 않았다. 둘을 빼서 제구 오차라고 표시하지 않는다.
- 새 S의 비null `catcher_setup`은 구조·단위가 미확인이라 좌표로 변환하지 않고 null을 유지한다.
- 기존 시연 39구 중 27구 좌표·12구 기권. M3는 2경기 86프레임, AI 58출력·28기권, 사람이 함께 표시한 58개에서 차이 중앙값 2.53px·90분위 6.51px이다. 한 사람 판독과 동일 변환 기준의 일치도이며 물리 정확도/독립 실시간 정확도가 아니다.
- CV24의 속도 개선은 개발 표본 측정이며 확정 미트 0을 유지한다. M3 정확도와 합쳐 실시간 정확도를 만들지 않는다.
- 우리 운영 모델과 팀원 정책의 평가 과제·기간·단위가 다르다. 별도 숫자를 단순 비교해 우수 모델이나 추천 효과를 확정하지 않는다.

## 묶음 밖 자료와 전달 조건

`external_artifacts_v1.json`은 존재를 확인한 파일의 **로컬 바이트** SHA·용도·전달 조건을 기록한다.
Git blob 해시 목록과 줄바꿈이 다를 수 있다. 별도 파일 수신 시에는 실제 받은 바이트를 비교한다.
경로 별칭은 전달자가 자기 컴퓨터의 경로에 대응시킨다.

- `LEGACY_PROJECT`: 기존 `transition-models` 체크아웃. 운영 135d 프로필/3개 가중치/보정 보고서와 Sites 작업 사본이 여기에 있다.
- `INTENT_PROJECT`: 이번 기준 `feature/intent-v0` 체크아웃. CV 검토 자료·비공개 시연 ZIP·현재 화면 자산이 여기에 있다.
- 운영 모델 코어는 이관 후보 목록일 뿐 이 묶음에서 추론을 재현하지 않았다. pickle/체크포인트는 신뢰한 전달 출처를 확인한 뒤 전체 저장소의 해당 런타임에서만 로드한다. 구형 Arsenal 135d와 운영 135d는 호환되지 않는다.
- 학습용 배열·전체 원본 영상·사람 응답·비공개 비교 그림·기기별 세션 기록은 기본 전달에서 제외한다. 필요할 때 용도/공유 범위를 정하고 별도로 전달한다.
- 기존 오프라인 v4 ZIP은 비공개 비교 그림이 포함된 과거 Site v8 자료다. 현재 화면 v9 소스와 다르며 공개 사이트/GitHub 배포용으로 사용하지 않는다.
- 사이트 작업 사본이 있어도 계정 권한·DNS·비밀키를 이식한 것이 아니다. 별도 배포 권한 확인이 필요하다. API 키와 로그인 정보는 이 묶음에 넣지 않는다.
- 제3자 영상의 기존 공개 사용 결정은 다른 원본/비공개 비교 그림의 공개 승인이나 일반 재배포 라이선스가 아니다.

## 소유권과 다음 연결 단계

우리 담당은 CV/좌표 근거·검토 도구·계약 검사·화면의 보존/이식이다. 팀원 모델·API·백엔드는 수정하지 않는다.
공용 기준 브랜치와 최종 화면/백엔드 정본은 미합의이며 이 묶음이 일방적인 채택 결정은 아니다.
다음은 실제 새 S 원문(발생한 ready/unsupported/missing), 생성 revision/SHA, 셋업 계약을 받은 뒤 한 타석을 대조하는 I-service2다.
발생하지 않은 상태는 미확인으로 남긴다. 이후 합의한 전체 소스/가중치/데이터로 독립 환경 실행(I-run1), 실제 기기/표시 시점 확인(I-release1)을 한다.
CV6의 첫 실제 사람 재검토26건은 수신했지만 독립된 두 사람 합의나 AI 오류26건을 뜻하지 않는다.
추가 독립 사람 검토와 CV7 미열람 자료는 별도로 남는다.

## 다시 생성할 때

전체 저장소에서 변경을 커밋한 다음 해당 커밋을 명시한다. 출력의 부모 폴더만 미리 만들고 같은 이름의 폴더/ZIP은 없어야 한다.

```text
python -B scripts/build_integration_handoff.py build --source-ref FULL_COMMIT_SHA --out outputs/handoff_new
python -B scripts/build_integration_handoff.py check outputs/handoff_new
```

`source_files_v1.json`의 명시 목록만 복사한다. 미커밋 파일·모델·영상·Git LFS 포인터는 전달하지 않는다.
새 전달 시 생성된 ZIP의 SHA와 기준 커밋을 별도 전달 메시지에 기록하고, 수신자가 가진 기준과 비교한다.
H-port4의 실행 결과/ZIP 식별자는 전체 저장소의 `docs/handoff/delivery_v2.json`에 기록한다.
새 파일별 manifest 사본은 `docs/handoff/source_manifest_v2.json`이다. 두 기록은 자기 자신을 포장하는
순환을 피하기 위해 ZIP에는 넣지 않는다. 과거 `delivery_v1.json`과 `source_manifest_v1.json`은 보존한다.

## 2026-10-08 후속 — 운영 모델 별도 전달 묶음

H-port2는 같은 Windows에서14개 운영 파일의 경로 이관을 실행 확인했고, H-port3는 그 자료만 담은
별도5.14MB ZIP과 실행 안내를 준비했다. 전체 저장소의 `docs/HANDOFF_OPERATIONAL_RELOCATION_V1.md`,
`docs/HANDOFF_OPERATIONAL_BUNDLE_V1.md`, `docs/handoff/operational_bundle_delivery_v1.json`을 참조한다.
이 문서와 운영 자료는 본 소스 ZIP에 포함하지 않는다. 기존 운영14파일 ZIP은 변경하지 않았으며,
그 전달 기록의 전체 소스 커밋·SHA를 사용한다. 새 소스49개 묶음도 완전한 모델 런타임이 아니다.
