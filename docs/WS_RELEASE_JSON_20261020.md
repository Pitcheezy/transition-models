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
변경3파일 Ruff check/format 통과. 관련 전체 검사와 고정 소스의 다른 모델 검토는 진행 중이다.

실제 연결·Cloudflare 자원·접속 권한·기존 배포·Mac·팀원 저장소는 변경하지 않는다.
