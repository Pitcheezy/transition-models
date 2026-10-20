# 배포 자료의 JSON 실패 처리 — WS-release1

2026-10-20. 기준 `172d3490722a5edcf9186ce8beb592468b649f59`, 선점 `ffabc17`.
[합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6284264075).

## 문제와 수정 범위

작은 JSON 안에도 Python의 정수 변환 제한을 넘는 긴 숫자가 들어갈 수 있다.
기존 공통 parser는 문법 오류와 재귀 초과만 처리하여 이때 발생하는 일반 ValueError를 놓쳤다.
그 결과 배포 후보 생성·검사 CLI가 정해진 오류 JSON 대신 traceback과 로컬 경로를 출력했다.
정상 후보로 통과하거나 파일을 배포한 문제는 아니다.

공통 parser에서 이 변환 실패를 `invalid_json`으로 처리한다. 중복 키의 기존
`duplicate_json_key`는 그대로 보존하며 입력 크기·정수 변환 제한을 완화하지 않는다.
팀원 계약이나 전달팩을 변경하지 않고 우리 로컬 배포 도구만 수정한다.

## 검증 상태

수정 전 신규4개 검사 모두 실패하여 공통 parser의 ValueError와 실제 CLI3개의 종료1을 재현했다.
수정 후 신규4개와 기존 중복 키 검사1개가 통과했다(5 passed, 1.97초).
입력 바이트 불변·출력 미생성·정해진 오류 JSON·traceback/경로 미출력을 확인했다.
변경3파일 Ruff check/format 통과. 배포·설정·비용·체크리스트 관련 전체238검사 통과(54.32초).
고정 `499b18537bea3d7d6979e89f7a1d93864ee17d80`의 gpt-5.6-sol 검토 PASS, P1/P2 없음,
독립 집중5검사 통과. 작성자는 Codex/GPT-6 계열이며 정확한 세션 모델 ID는 노출되지 않았다.
검토 모델 근거는 해당 모델을 명시한 성공한 하위 에이전트 호출이며 내부 모델 조회를 주장하지 않는다.
검토자의 최초 실행은 임시폴더 권한으로2통과·3 setup error였고, 별도 쓰기 가능한 임시폴더로5통과했다.
이는 구현 실패로 기록하지 않는다.

[파일 SHA·명령·결과 영수증](results/ops/ws_release_json_20261020.json).

```text
PYTHONUTF8=1 python -B -m pytest -q tests/test_public_host_release.py tests/test_public_host_config.py tests/test_public_host_cost.py tests/test_checklist_model.py
python -m ruff check src/operations/release_bundle.py tests/test_public_host_release.py tests/test_public_host_config.py
python -m ruff format --check src/operations/release_bundle.py tests/test_public_host_release.py tests/test_public_host_config.py
```

로컬 합성 입력 검증이다. GitHub CI/병합과 현재 수정 권한은 CHECKLIST와 우리 board를 따른다.
WS-review3의 release_bundle.py 근거는 이번 수정 이전이며, 이 고정 검토를 새 근거로 연결한다.

실제 연결·Cloudflare 자원·접속 권한·기존 배포·Mac·팀원 저장소는 변경하지 않는다.
