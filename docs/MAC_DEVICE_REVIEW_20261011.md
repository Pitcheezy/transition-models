# I-device2 Mac 실기기 확인 — 2026-10-11

**환경 확인 완료, 비공개 v5 영상팩 전송 대기. 서비스 화면 검사는 미실행이다.**
이 기록은 사용자의 Mac에서 직접 실행한 명령 결과다. 기존 Windows/CI 검사 결과를
Mac 서비스 검수로 옮겨 적지 않았다. [구조화 기록](results/service_integration_20261011/mac_device_preflight_v1.json).

## 실제 실행 환경과 저장소 보존

| 확인 | 실제 결과 |
|---|---|
| `uname -s` / `uname -m` | Darwin / arm64 |
| `sw_vers` | macOS 27.0, build 26A428 |
| 최초 `pwd` | `$HOME/Documents/GitHub/transition-models` |
| `git remote -v` | fetch/push 모두 `https://github.com/Pitcheezy/transition-models.git` |
| 최초 `git status` | main, HEAD `fc7d647`; 추적 파일 수정19개·미추적12개 |
| 검사용 작업트리 | `$HOME/.codex/worktrees/mac-i-device2/transition-models` |
| 검사용 브랜치·기준 | `feature/intent-v0`, `06a31107e78bd00abf47e33bf6aa2be8348edc8c` |
| 동기화 | origin fetch 후 깨끗한 별도 작업트리에서 `git pull --ff-only origin feature/intent-v0`: Already up to date |
| 기존 작업 보존 | main의 HEAD·상태 목록·기존31파일 SHA256이 최초 스냅샷과 동일 |
| 기본 `python3` | 3.9.6: 팩의 문서상 요구 Python3.10 이상에 미달 |
| 사용 가능한 Python | 기존 main의 `.venv/bin/python`: 3.12.13; uv0.11.2 |

기존 main에서 브랜치 전환·pull·stash·파일 수정을 하지 않았다. `reset --hard`, `git clean`,
강제 푸시를 사용하지 않았다. Git 메타데이터 쓰기는 샌드박스 권한을 얻어 수행했다.
팀원 SongRoute/pitcheezy 저장소는 접근하거나 수정하지 않았다.

## 영상팩 검색 결과

아래 범위에서 `service_review` 이름의 파일, `launch_review.py`, `START_MAC.command`를 찾았으나
후보가 없었다. Spotlight에서 `service_review_video_20261010_v5*` 이름 검색도0건이다.

- 기존 우리 저장소 전체(숨김·Git 제외 산출물 포함; `.git`·가상환경·node_modules 제외).
- Downloads, Desktop.
- Documents의 GitHub 및 다른 Git 저장소를 제외한 영역, Movies, iCloud Drive.
- `/Volumes` 목록에는 Macintosh HD와 Recovery만 있으며 외장 데이터 볼륨은 연결되어 있지 않았다.

이 결과는 조사 범위에서의 미발견이다. 다른 사용자 계정·미연결 외장 디스크·원격 Windows의 파일
부재까지 확인한 것은 아니다. 다른 Git 저장소나 팀원 저장소를 열어 찾지 않았다.

## 필요한 파일과 전송 방법

원래 Windows 작업 폴더의 아래 파일 **하나를 그대로** USB 또는 본인 비공개 파일 전송 경로로
이 Mac의 `~/Downloads/`에 복사한다. Git fetch/pull로는 내려오지 않는 비공개 영상팩이다.
별도 소스 ZIP에는 실제 보고서·영상이 없어 대체할 수 없다.

- 파일: `outputs/service_review_video_20261010_v5.zip`
- 기대 크기: **13,571,942 bytes**
- 기대 SHA256: `51af1e8861ac5e7294b185acb3f525fa2b421765152ff2a65abdbb2f92317546`
- 기대 내용:16파일, 실제262구 정규화 보고서와 첫 타석3클립, 단독 실행기.
- 근거: 기존 [v5 전달 영수증](handoff/delivery_v5.json)의 `separate_private_video_archive`.

위 크기·해시는 **기존 영수증의 기대값**이며 이번 Mac에서 ZIP을 측정한 값이 아니다.
원본 Windows ZIP과 전달 영수증은 변경하지 않는다. 공개 업로드·팀원 전송은 수행하지 않았다.

## 파일 도착 후 첫 실행 순서 — 아직 실행하지 않음

파일이 도착하면 먼저 현재 작업 상태와 ZIP 크기·해시·CRC를 확인한다. 해시가 다르면 실행하지 않는다.

```bash
cd "$HOME/.codex/worktrees/mac-i-device2/transition-models"
git status --short --branch
stat -f '%z' "$HOME/Downloads/service_review_video_20261010_v5.zip"
shasum -a 256 "$HOME/Downloads/service_review_video_20261010_v5.zip"
unzip -t "$HOME/Downloads/service_review_video_20261010_v5.zip"
```

기대값과 일치한 경우에만 새 빈 폴더에 압축을 푼다. 폴더가 이미 있으면 덮어쓰거나 지우지 말고
다른 새 이름을 선택한다. ZIP의16파일은 최상위 폴더 없이 들어 있다.

```bash
mkdir outputs/service_review_mac_device2_20261011_v5
unzip -n "$HOME/Downloads/service_review_video_20261010_v5.zip" -d outputs/service_review_mac_device2_20261011_v5
cd outputs/service_review_mac_device2_20261011_v5
"$HOME/Documents/GitHub/transition-models/.venv/bin/python" -B -S launch_review.py --check
```

무결성 검사 성공 후 아래 명령을 실행하고, **이번 Mac의 터미널에 새로 표시되는** localhost 주소를
실제 화면이 보이는 브라우저에서 연다. 과거 Windows의59154/59158 주소는 Mac 실행 주소가 아니다.

```bash
"$HOME/Documents/GitHub/transition-models/.venv/bin/python" -B -S launch_review.py --open
```

이 Mac의 기본 `python3` 대신 위에서 확인한3.12.13을 명시한다. 패키지 설치나 기존 가상환경 변경은
필요하지 않다. `START_MAC.command`는 기본 python3를 사용하므로 이번 Mac에서는 위 명령을 우선한다.
압축 해제 경로는 기존 `outputs/service_review_*` Git 제외 규칙에 해당함을 확인했다.

## 남은 실기기 관찰

| 항목 | 이번 Mac 상태 | 파일 도착 후 관찰할 동작 |
|---|---|---|
| 영상 재생 | 미실행 | `849843:1:1`, `849843:1:2`, `849843:1:3`을 실제 끝까지 재생 |
| 결과 공개 | 미실행 | 재생 전 실제 결과 숨김, 각 클립 종료 후 해당 투구 결과 공개 |
| 투구 전환 | 미실행 | 기존 재생 중단, 공개 상태 초기화, 선택한 투구의 영상 연결 |
| 타석 전환 | 미실행 | 이전 영상 제거, 공개 초기화, 다음 타석의 영상 없음 안내 |
| 미트 가로 표시 | 미실행 | 공개 후 estimated·유한 x만 표시; 높이 제공 없음·미검토·투수 의도 아님 문구 |

검사 때 브라우저 이름·버전과 실제 관찰 결과를 새 기록으로 남긴다. 이번에는 서버 실행·브라우저
검사를 시작하지 않았고 통과 수는0이다. 합성 입력·headless·hosted macOS CI로 대체하지 않았다.
CV-30은 완료 상태를 유지하고 재개발하지 않았다. A-y는 사용자 보류, I-release1 전체도 미완료다.

## 기록 검증

이 Mac의 기존 Python3.12.13으로 `tests/test_checklist_model.py`를 실행해7passed(0.16초)를 확인했다.
I-device2 파서 상태는 `blocked`다. 새 JSON의 유효성, 기존 v5 영수증과 기대 ZIP 크기·SHA·파일 수,
새 문서 링크, `git diff --check`를 확인했다. 별도 읽기 전용 검토에서도 수정할 문제는 발견되지 않았다.
이 검사는 문서·체크리스트 검증이며 서비스 UI 검수나 전체 회귀 실행이 아니다. 수정 권한을 반납한다.
