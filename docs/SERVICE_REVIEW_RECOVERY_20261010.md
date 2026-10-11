# 영상 요청 중단과 재생 복구 — 2026-10-10

I-service6 완료. 선점 `cbc6f29`; 구현은 이 기록과 같은 커밋이다.
사용자 지시로 A-y44구 수동 검토를 보류하고 서비스 오류 복구를 우선했다. 고정 규약과 기존 사람 응답은 보존한다.

## 문제와 수정

앞선 로컬 Chrome 검사에서 영상 요청을 중단할 때 Windows `ConnectionAbortedError`(WinError10053)가
본문 전송에서 처리되지 않아 요청 스레드 traceback이 남았다. 서버 전체가 종료됐다는 의미는 아니다.
기존 코드는 본문 전송의 BrokenPipe/ConnectionReset만 처리했고 헤더와404/416 응답은 범위 밖이었다.

GET/HEAD 응답 경계에서 세 종류의 연결 종료만 처리하고 해당 연결을 닫는다.
다른 `OSError`를 일괄 숨기지 않으며 PermissionError가 그대로 드러나는 것을 검사했다.
현재 화면에는 재시도와 선택 초기화가 이미 있어 프런트엔드 기능은 추가하지 않았다.

## 검사

- 새 회귀20사례: 수정 전16실패/4통과 → 수정 후20통과. 실제 HTTP 핸들러에 연결 종료를 주입한다.
- 헤더/본문,GET/HEAD,200/206/404/416 경로와 다음 요청의206응답·바이트를 확인했다.
- 관련 Python115passed(27.23초),Node36passed,Ruff167경로 통과. 독립 코드 검토에서 추가 수정 항목 없음.
- 실제 Windows Chrome headless154.0.8037.58에서 아래7시나리오 통과. 네트워크 실패와 오래된 이벤트는 의도적으로 주입했다.

| 시나리오 | 확인한 결과 |
|---|---|
| MP4 요청 실패 | 추천 유지,실제 결과/미트 숨김,다시 불러오기 제공 |
| 영상 실패 뒤 수동 공개 | 실제 데이터 확인 가능 |
| 재시도·실제 재생·탐색·종료 | 기존 공개값 초기화,재생 종료 뒤 현재 투구만 공개 |
| 재생 중 투구 교체 | 이전 영상 중단·연결 제거,이전 종료 이벤트로 새 투구 공개 안 됨 |
| 공개 후 새로고침 | 첫 투구로 돌아가 실제 결과/미트 숨김 |
| 영상 미연결 투구 | 다른 투구 영상 표시 안 함,수동 공개 가능 |
| 영상 목록 요청 실패 후 복구 | 수동 공개 유지,연결 복구 후 새로고침으로 영상 정상 연결 |

브라우저 예외0·외부 요청0·GET 이외 요청0. 해당 검사 후 서버 출력에 새 traceback이 없었다.
실패/복구 화면을 캡처해 직접 확인했다. 캡처는 비공개 `outputs/service_review_recovery_20261010_v1/`에만 있다.
[기계 판독 기록](results/service_integration_20261010/playback_recovery_verification_v1.json).

## 현재 전달본

- 폴더: `outputs/service_review_video_20261010_v4/`
- ZIP: `outputs/service_review_video_20261010_v4.zip`
- 16파일,13,571,477bytes,SHA256 `cc2c5e46528711b9a026426d53ff8a38fdcad6ebfde3fe5cd5670fcd7a5cfe5b`
- 실제 압축 해제·CRC·16파일 바이트 일치·격리 Python 실행기 검사 통과.
- v3 대비 `launch_review.py`와 `receipt.json`만 변경됐다. 화면·자료·영상은 동일하며 v1~v3도 보존한다.
- 현재 세션 주소: `http://127.0.0.1:59153/`. 주소는 실행한 컴퓨터에서만 열린다.
- 다른 컴퓨터에는 비공개 ZIP을 옮겨 전체 압축 해제 후 Windows `START_WINDOWS.cmd`,Mac `START_MAC.command` 실행.
  Python3.10 이상이 필요하다. 실제 Mac/아이폰 사용 확인은 아직 하지 않았다.

재현(저장소 루트,패키지 출력은 존재하지 않는 새 경로 사용):

```powershell
.venv/Scripts/python.exe -B -m pytest -q tests/test_service_review_package.py tests/test_service_review_server.py tests/test_checklist_model.py
node --test web/service-review/review.test.cjs
.venv/Scripts/python.exe -B scripts/build_service_review.py --input outputs/service_review_received_20261009/service-game-849843.json --source-kind provided_export --include-first-pa-video --out-dir outputs/service_review_video_20261010_v4 --zip outputs/service_review_video_20261010_v4.zip
.venv/Scripts/python.exe -I -S -B -X utf8 outputs/service_review_video_20261010_v4/launch_review.py --check
```

## 범위와 남은 조건

팀원 저장소·공개 Site·모델·원본 데이터·영상·사람 응답은 변경하지 않았다.
A-y는 사용자 재개 전까지 보류하며 독립 사람 일치도는 미측정이다. 입력을 대신 만들어 완료하지 않는다.
CV-6 추가 독립 검토·CV-7 새 영상·CV-5a 시작 정의·실기기·모델 실행 합의·공개 운영 조건은 유지한다.
새 팩은 기동/재생 복구 검사이며 실제 모델 추론이나 라이브 피드 검증이 아니다. 수정 권한 반납.
