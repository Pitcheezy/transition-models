# 개발용 시간순 프레임 공급 v1

2026-10-05. **경기 849845 PA43에 남은 3구·5구의 두 압축 영상 창, 122장**으로 프레임 공급을 검증했다. 전체 타석이나 연속 원본 경기 영상은 아니다. 기존 파일의 바이트·출처를 검사하고 복사했으며 새 이미지 판독이나 미트 추론은 수행하지 않았다.

## 완료한 것

[intent/replay.py](../intent/replay.py)는 windows와 timing의 경기·투구 ID·영상 URL·fps·frame index·재생 시각을 검사한다. 선택한 decision frame의 실제 존재와 각 이미지 SHA를 대조한 뒤 새 로컬 패키지를 만든다. 원본·기존 산출물을 덮어쓰지 않는다.

- `processor/manifest.json`과 익명 이미지: 관측 ID, 원본 시각, SHA, 익명 이미지 경로만 담는다.
- `evaluator_manifest.json`: 투구 ID, decision/release 시각, 원본 경로·출처를 따로 담는다. 처리기에 전달하지 않는다.
- `PrefixStream.advance(t)`: t 이하의 누적 프레임 목록만 반환하며 제공 직전에 이미지 바이트 SHA를 다시 검사한다. 시간을 뒤로 돌릴 수 없다.
- `prefix` CLI: 마지막 cutoff와 manifest SHA를 저장해 별도 호출에서도 역행을 거절한다. 단일 순차 실행용이다.

첫 로드부터 준비 당시 processor manifest SHA를 대조하므로, 첫 호출 전에 프레임 시각만 앞당긴 변경도 거절한다. 경로 탈출·symlink·중복 키·해시 불일치·잘못된 시계를 테스트했다.

패키지 전체에는 미래 이미지와 평가 파일이 있다. **신뢰하는 로컬 runner가 처리기에 반환된 prefix만 제공하는 계약**이며 파일 접근을 막는 보안 sandbox가 아니다. 두 manifest를 함께 바꾸는 공격까지 인증하는 서명 시스템도 아니다.

## 실제 로컬 확인

프레임은 원본 60000/1001fps에서 매 3프레임을 뽑은 표본이다. 두 창 사이에는 영상이 빠져 있고 각각 투구 후 화면도 들어 있다. 미래 프레임을 이후 cutoff에서 전달하는 것은 허용되며, 이후 결과를 투구 전 결과로 표시해서는 안 된다.

| cutoff(영상 재생 초) | 누적 제공 프레임 |
|---:|---:|
| 620 | 0 |
| 621 | 10 |
| 634 | 61 |
| 636 | 76 |
| 639 | 122 |

639초 호출 후 621초로 되돌리는 호출은 거절됐고 이전 상태 파일은 보존됐다. 기존 M3·시연 관련 186개 파일 SHA도 동일했다. [검증 기록](results/cv_followup_20261005/replay_pa43_v1.json)에 소스와 패키지 SHA를 남겼다.

이 검증은 **수동으로 지정한 다섯 cutoff의 프레임 공급 검사**다. 프레임 도착을 실제 시간에 맞춰 재생하거나 관측 결과 발행 시각을 계측하지 않았다. 자동 미트 검출, 투구 전 정확도, 실시간 지연, 전체 영상 처리량은 미측정이다.

## 재현

저장소 루트의 기존 Python 환경에서 실행한다. `--out`은 새 폴더여야 한다. 프레임 원본은 로컬에 있어야 하며 자동 다운로드하지 않는다.

```bash
python -m intent.replay prepare --game 849845 --pa 43 --out outputs/cv_replay_new
python -m intent.replay prefix --package outputs/cv_replay_new --cutoff 621
python -m intent.replay prefix --package outputs/cv_replay_new --cutoff 639
```

준비된 로컬 패키지는 `outputs/cv_replay_849845_pa43_v1/`에 있다. 이미 639초까지 공급했으므로 CLI로 다시 앞에서 시작하려면 새 패키지 경로를 사용한다. API는 새 `PrefixStream` 인스턴스마다 별도 세션이다. 원본 이미지·패키지는 Git에 포함하지 않는다.

```python
from intent.replay import PrefixStream

stream = PrefixStream("outputs/cv_replay_new")
frames = stream.advance(621)
# Only pass these anonymous frame records to the future observer.
# Do not pass stream, its complete manifest, or evaluator metadata.
```

현재는 관측기를 호출하지 않는다. 다음 단계에서 실제 관측기를 연결하되 [관측 v1 규약](CV_OBSERVATION_PROTOCOL_V1.md)의 대상 정의·독립 평가 조건을 따른다. 연속 영상·시점별 도착 일정·처리 완료와 출력 발행 시각을 갖추기 전에는 라이브 완료로 표시하지 않는다.

CV-5의 완료 범위는 이 **두 창의 공급 준비와 검증**이다. 전체 한 타석의 시간순 관측/실시간 계측은 CV-5a로 남긴다. 기권 불일치 26건의 사람 판정과 미열람 영상 독립 평가는 CV-6·7에서 진행한다.

검증: 새 replay 테스트 18건, 관련 도구 4개 합계 **108 passed**. 최종 `check_project.py --cpu-only`: **760 passed, 5 skipped, 2 deselected**, Ruff 92경로 통과. 기존 Pillow 경고 2건.
