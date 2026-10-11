# macOS/Linux 가상환경 실행파일 결속 수정 — CV-19

실제 원격 [CI 37560147593](https://github.com/Pitcheezy/transition-models/actions/runs/37560147593)
(커밋2a560a7)에서 Ubuntu와macOS가 각각17 failed/1514 passed로 실패했다.
pytest시간은46.19/92.24초로180초 제한 이내였고 설치·Ruff는 통과했다.
정상 `.venv/bin/python3` 심볼릭 링크를 observation_loop._prepare가 데이터 경로처럼
거절한 것이 공통 원인이었다. timeout을 늘려 해결할 문제가 아니다.

현재 프로세스 `sys.executable`이고 현재 venv의 bin/Scripts에 있는 launcher 링크만
예외적으로 허용한다. 명령은 원래 launcher 경로를 유지해 venv 환경을 잃지 않도록 한다.
실제 대상 파일과 pyvenv.cfg는 기존 SHA 결속 목록에 넣고, launcher 링크 사슬과 raw target은
observer_launcher_binding에 동결한다. 작업 준비·dispatch직전·runner성공/예외직후 재확인한다.
같은bytes인 다른 대상으로 바꿔도 링크 연결이 달라지면 거절한다.

일반 실행파일 링크, 영상·입력·출력의 symlink/junction 거절은 유지하며 clip_capture._plain_path는
변경하지 않았다. 신뢰된 로컬 실행기이며 OS보안 sandbox라는 주장은 하지 않는다.
계획schema와 요청/응답 의미는 유지한다. CV14/17 과거결과는 해당 커밋 코드로 재현한다.

Windows 관련검사36 passed(10.35초), Ruff통과. 현재Python subprocess의 sys.prefix 보존,
정상링크 모의처리, retarget와일반링크거절, 상대경로/PATH표준해결을 검사했다.
실제 수정 커밋 `5b108f2`의 [CI 37561107783](https://github.com/Pitcheezy/transition-models/actions/runs/37561107783)은 양쪽 모두 성공했다.
Ubuntu24.04/torch2.6.0:1542 passed·6 skipped·2 deselected(48.29초).
macOS15/torch2.8.0 CPU검사:1542 passed·6 skipped·2 deselected(102.93초).
기존180초 제한을 유지했고 Ruff136경로·JavaScript구문·의존성설치도 성공했다.
mac의 runtime탐지는MPS available이지만 실제검사는 --cpu-only이며 MPS성능 검증이 아니다.
