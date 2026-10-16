# WS-notice2 / WS-monitor3 — 운영 도구

2026-10-17. 토큰을 명령 인자로 전달하던 수동 안내 전환과 단발 감시만 있던 운용 경로를 보완했다. 실제 서비스의 설정·토글·권한·스케줄은 바꾸지 않았다. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6218430481)·[검증 영수증](results/ops/ws_operator_tools_20261017.json).

## 안내 운영자 도구

`ops/public-host/notice-client.mjs`와 `notice-cli.mjs`는 기존 `/_notice/v1/state`만 사용한다. JSON 계획 파일에 method·고정 조건·원하는 변경을 넣고, 기본 dry-run으로 검토한다. `--execute`를 명시해도 사람의 권한이 새로 생기지 않는다. 비밀은 `PITCHEEZY_NOTICE_TOKEN` 환경 변수에서만 읽으며 주소·토큰·내부 사유·ETag를 stdout에 내보내지 않는다.

GET/HEAD의 ETag는 명시한 새 비공개 snapshot 파일로만 저장한다. PUT은 그 조건을 사람이 계획에 고정해야 하며, 충돌412에서 새 ETag로 자동 재쓰기하지 않는다. 타임아웃/응답 유실은 unknown으로 구별한다. 저장됐지만 감사가 누락된 결과와 조회 시 감사 누락도 단순 성공으로 처리하지 않는다. 복구는 별도 사람 승인 범위를 따른다.

집중16검사에서 실제 임시 loopback Worker/R2의 조회→ON→경합412→OFF를 확인했다. 저장 후 응답을 잃는 상황에서 요청1회/unknown을 기록하고 후속 조회로 저장을 확인한 뒤 새 명시 조건으로 복구했다. 실제 Cloudflare 안내 전환을 다시 실행하지 않았다. 자세한 형식과 실행 명령은 [NOTICE.md](../ops/public-host/NOTICE.md)를 따른다.

## 유한 감시 실행기

`ops/public-host/monitor-runner.mjs`와 `monitor-runner-cli.mjs`는 기존 `runOnce`와 모의 알림을 직렬로 호출한다. 기본 dry-run이며 실행에는 횟수·기간·간격을 모두 명시한다. 최대1000회/24시간과 간격최소1초, 기존 상태 파일/별도 runner잠금으로 반복 실행·재개를 관리한다.

실패·부분측정·열린 장애·자체오류를 누적해 마지막 정상 결과가 앞선 실패를 지우지 않는다. 구성이나 방금 기록한 보고서가 바뀌면 오래된 결과로 알림을 만들지 않고 중단한다. Ctrl+C/SIGTERM은 새 검사를 중단하고 진행 중 원자 기록을 마친 뒤 정리한다. 기간은 새 probe 시작 예산이며 OS/파일시스템 지연까지 강제 종료하는 보장은 아니다.

집중21검사에서 합성 시계와 실제 로컬 HTTP로 장애2회→실행 재시작→정상2회의 장애/복구 이력 및 양쪽 **모의** 알림을 확인했다. 실제 이메일·OS 서비스 등록·상시 감시·팀원 프로세스 연결이 아니다. [MONITORING.md](../ops/public-host/MONITORING.md)에 실행 조건과 잔존 잠금 수동 처리 한계를 기록했다.

## 검사와 재현

- 전체 Node280/280, 실패0,16.57초. 집중16+21은 전체에 포함되므로 합산하지 않는다.
- 체크리스트8/8. Windows workerd 종료 경고가 있었으나 검사 실패는0이다.
- 다른 모델 고정 코드 검토와 PR CI는 구현 커밋 뒤 진행하며, 결과는 이 기록에 추가한다.

```text
node --test ops/public-host/tests/*.test.mjs
node --test ops/public-host/tests/notice-client.test.mjs ops/public-host/tests/notice-cli.test.mjs
node --test ops/public-host/tests/monitor-runner.test.mjs
python -B -m pytest tests/test_checklist_model.py -q -p no:cacheprovider
```

실제 대상 실행·권한/문구·기간·알림 제공자 결정은 [사람 결정서](WS_HUMAN_DECISIONS.md)와 [Song 시험 준비](WS_PARTNER_TRIAL_PREPARATION_20261017.md)를 따른다. 기존 호스트 코드를 새로 배포한 것이 아니며, 공개 파일 계약이나 Song 저장소는 변경하지 않았다.
