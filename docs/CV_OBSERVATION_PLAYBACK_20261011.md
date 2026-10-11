# CV-30 — 저장된 자동 관측을 연속 영상과 연결

사용자가 요청한 남은 작업 6번의 **제한 중계 구간 연결**을 구현했다. 기존 CV24 실행을 발행 시각에 맞춰
재생하는 비공개 개발 화면이며 새 관측 실행이나 독립 정확도 실험은 아니다. 팀원 저장소는 접근하거나
변경하지 않았다. 엄격한 전체 타석 CV-5a4/CV-5a 완료 조건은 유지한다.

## 무엇이 연결되었나

- `intent/observation_playback.py`: 저장 실행과 capture, 수동 timing의 출처 결속을 검증하고 새 패키지만 생성한다.
- `web/observation-playback/`: 연속 영상, 실제 입력 정지 이미지, 원본 시계, 투구 참조, 전체 관측 기록을 표시한다.
- `intent/observation_playback_server.py`: 패키지 SHA/크기/경로를 확인한 뒤 기존 서비스 검토 서버의
  Range 지원 HTTP handler를 재사용한다. 이 컴퓨터의 `127.0.0.1`에만 연다. 일반 `http.server`에서는
  Chrome 탐색이 준비되지 않는 현상을 확인했으므로 전용 실행 명령을 사용한다.

발행 전에는 결과를 숨기고 뒤로 탐색하면 다시 숨긴다. 이전 투구의 관측을 현재 유효값으로 재사용하지
않으며, 입력 프레임을 교체하는 동안 이전 이미지를 숨긴다. 기권·오류·미시도·미배정 행을 삭제하지 않는다.
영상의 현재 프레임 위에 과거 입력의 좌표를 덧씌우지 않는다.

## 범위와 수치의 의미

경기747139의 PA2에서 중앙 카메라가 돌아온 시각 `10814804/60000`부터 `13800787/60000`초 미만이다.
약180.247–230.013초 구간이며 타자의 실제 진입부터 퇴장까지를 보증하지 않는다. 표시 반올림을 검증 시각으로
다시 쓰지 않는다. 원본–클립 시계 오프셋은 `1050049/7500`초이며, 클립 첫 PTS0·상수 오프셋·구간 전체
프레임 커버리지를 검증한다. 비상수 매핑을 평균 오프셋으로 대체하지 않는다.

기존 저장 실행 전체14개를 보존한다. 선택 구간 안 입력10개, 구간 앞 입력4개, accepted14개,
실행 오류0개, 미시도0개다. accepted는 **실행 결과 형식이 수용됨**을 뜻하며 미트 인식 성공이 아니다.
확정 미트0개, 보수적인 투구 전 시각 조건 충족0/3구다. 이는 CV24/CV25 기록의 재표시다.

발행 시각은 첫 cutoff에 실행 시작 이후의 monotonic 경과시간을 더한 기존 기록이다.
입력 프레임 시각에 단순 추론 시간을 더하거나 feed UTC를 영상 시각으로 바꾸지 않는다.
현재 타석의 참조는 기존 수동 주석이며 새 독립 사람 정답이 아니다. 후보 있음도 포수 미트 확정이나 투수 의도가 아니다.

## 재현

저장소 루트에서 기존 private 입력이 있는 환경으로 실행한다. Python 환경은 기존 `.venv` 또는
`uv run --frozen python`을 사용한다. 출력 폴더는 반드시 새 이름이어야 하며 기존 결과를 덮어쓰지 않는다.

```text
python -m intent.observation_playback --run outputs/cv_exact_seek_v1/plan_bundle/run --capture-dir outputs/cv_local_pa_interval_v1/capture --timing docs/results/mlb_p0/game_747139_timing.json --manifest docs/results/mlb_p0/game_747139_manifest.json --sources docs/results/mlb_p0/game_747139_sources.json --pa 2 --start 10814804/60000 --end 13800787/60000 --out-dir outputs/cv_replay_NEW
python -m intent.observation_playback_server --directory outputs/cv_replay_NEW --check
python -m intent.observation_playback_server --directory outputs/cv_replay_NEW --port 0
```

실행기가 출력한 주소를 같은 컴퓨터에서 연다. 새 모델/가중치 다운로드는 없지만, 원래 영상과 capture
framemd5/mapping, CV24 저장 실행의 이미지·영수증·참조 파일이 필요하다. 영상이 포함된 생성물은 Git 제외이며
공개 사이트에 배포하지 않는다. 코드와 데이터 계약은 저장소에 포함한다.

서버는 검증된 바이트를 메모리에 보관한다. 총512MiB, 단일 파일128MiB, JSON5MiB 상한이며 현재51MB 영상은
해당 범위다. 이 소규모 도구는 최대50관측/100투구 참조만 지원한다. 생성 후 수정된 파일은 SHA 검사에서 거절한다. 원본 URL·절대 경로·실행 로그·사람 응답은
화면 데이터에 복사하지 않는다. 패키지 SHA는 파일 일치 증거이고 외부 출처 인증은 아니다.

브라우저 회귀는 원래 private CV24 자료에 대한 재현 검사다. Playwright를 `tests/browser`의 lock으로 설치하고
아래 환경 변수를 설정한 뒤 `node tests/browser/observation-playback-private.cjs`를 실행한다.

- `OBSERVATION_PLAYBACK_PACKAGE`: 생성 패키지 폴더
- `OBSERVATION_PLAYBACK_URL`: 실행기가 연 loopback URL
- `OBSERVATION_PLAYBACK_QA`: Git 제외의 새 화면 캡처/결과 폴더
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`: 선택 사항, 실제 Chrome 실행 파일

이 검사는 개발 경기 PA2의 기존 시각에 맞춘15개 시나리오다. 임의 경기의 범용 성공 증거로 쓰지 않는다.
합성 Node 검사와 Python 검사도 따로 있다. private 영상 없는 CI는 합성 검사를 실행한다.

## 검증 기록

최종 검사는 관련 Python80passed(새 builder28·서버22·기존 deadline29·Node wrapper1), Node26cases,
Windows Chrome154.0.8037.58의 실제 영상 브라우저15시나리오 통과다. 320px 폭은 자동 뷰포트 검사이며 실제 아이폰이 아니다.
전체 CPU2254passed/8skipped/2deselected(406.51초); 이후 추가한 Range 서버22검사는 관련80검사에 포함해 별도 통과했다. 기존 Pillow 테스트의 폐기 예정 API 경고2개가 있다.

최종 비공개 팩은 `outputs/cv_replay_view_20261011_v4`(21파일,52899890bytes)이며
manifest SHA256은 `ef7fcbd7ea5734900aeb8195dcc72b486f9c3f736700a6bdc2b14ae18fe70f11`이다.
사용 중인 이 노트북의 로컬 주소는 `http://127.0.0.1:59158/`다.
[검증 영수증](results/cv_followup_20261011/observation_playback_v1.json)에 범위·입력 SHA·브라우저 항목을 기록했다. 화면 캡처는 MLB 영상이 있으므로 로컬에만 보존한다.
실제 Mac·아이폰·사용자 수용 검사를 Windows headless Chrome 또는 hosted CI 결과로 대체하지 않는다.

## 4번 I-device2 — 실제 Mac 확인 대기

현재 Windows의 OpenSSH 존재, SSH 설정의 Mac 항목 부재, `johyeonjun-ui-Macmini.local` DNS 실패를 확인했다.
Codex에서 현재 사용할 수 있는 프로젝트에도 접근 가능한 원격 Mac 체크아웃이 확인되지 않았다.
비밀번호·개인 키를 읽거나 호스트 키 검증을 끄지 않았다. Mac 실제 실행은 하지 못했으며, 사용 가능한
접속 주소/계정 또는 도구 연결이 필요하다. 사용자에게 연결 정보를 요청했다.

기존 서비스 검토용 v5 소스/영상 ZIP은 그대로 사용할 수 있다. 이번 CV-30 화면은 별도 개발 도구이며
v5 팀원 서비스 시연 패키지나 공개 Site를 교체하지 않는다. Mac/아이폰·I-release1 전체는 미완료다.
A-y 사람 검토는 사용자 보류를 유지한다.
