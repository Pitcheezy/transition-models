# 고정 시각 순차 관측 실행 — 2026-10-06

CV-5a3: 기존에 검증한 프레임 추출을 실제 Claude 관측 호출과 연결했다.
한 명령으로 예정 시각 대기 → 정확한 프레임 추출 → 익명 요청 → 원응답 검증·저장을
순차 수행한다. 기존 M3·시연본·사이트와 팀원 코드는 변경하지 않는다.

## 시간과 실패의 의미

계획의 첫 cutoff를 0초로 하는 1배속 시계를 한 번 시작한다. 다음 예정 시각은
항상 첫 시각을 기준으로 계산한다. 호출이 밀려도 시계를 다시 시작하지 않는다.
각 시각의 준비 시작, 프레임 준비, 실제 관측기 호출, 프로세스 종료, 검증된 결과
발행을 별도로 남긴다. `accepted_latency_from_schedule_seconds`는 `finish()`의
재검증과 파일 저장이 끝난 뒤 찍은 시각이다. 디코딩·해시·CLI 시작·인증·네트워크·
모델 처리·응답 검증을 포함하며 모델 단독 추론 시간과 다르다.

실패·timeout·잘못된 JSON은 오류로 보존한다. 모델이 반환한 `unknown/unavailable`과
구분한다. 기본 재시도·암묵적 이어쓰기·과거 응답 재사용은 없다. 실패하면 원문 로그를
검토하고 새 출력 폴더를 사용한다. 강제 종료/저장 장치 오류에는 부분 파일이 남을 수 있다.
외부 어댑터가 만든 하위 프로세스 전체의 종료를 보장하는 일반 실행 환경은 아니므로
관측기의 내부 timeout보다 바깥 timeout을 길게 설정한다(실제 실행: 120초/240초).

## 관측기와 출처

Claude Max의 기존 `claude.ai` 로그인으로만 호출하며 API 키/별도 공급자 전환은
거절한다. 익명 요청과 JPEG를 stream-json stdin에 직접 전달한다. 도구·MCP·프로젝트
설정·자동 메모리를 비활성화하고 저장소 밖 임시 작업 폴더를 사용한다. 관리자 정책을
우회하지 않으며 보안 샌드박스나 완전한 맥락 격리라고 주장하지 않는다.
provider 로그에 도구 호출이나 실패 결과가 있으면 응답을 수락하지 않는다.

프레임·요청·계획·코드 해시, 실제 프로세스 출력과 provider가 보고한 모델·사용량을
보존한다. provider 비용 필드는 실제 청구 영수증이 아니다. private 폴더에는 로컬 경로·
세션 정보가 있으므로 그대로 공개하지 않는다. 모델에는 투구 키·릴리스 시각·정답·다음
프레임을 전달하지 않는다. AI 관측을 사람 라벨로 처리하지 않는다.

CLI 형식 근거: [공식 비대화형 실행](https://code.claude.com/docs/en/headless),
[이미지 스트리밍 입력](https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode),
[호출별 hook 설정](https://code.claude.com/docs/en/hooks).

## 재현

먼저 [캡처](CV_CLIP_CLOCK_V1.md)를 준비한다. 계획은 아래 8개 필드를 모두 가지며
파일 경로는 계획 파일 기준이다. `observer_argv`는 쉘 문자열이 아닌 인수 배열이다.
예시를 로컬 파일로 저장하고 capture/실행 파일 경로를 맞춘다. Windows에서는
`--claude-bin` 뒤 값을 설치된 실제 `claude.exe` 절대 경로로 바꾼다.

```json
{
  "schema": "intent_observation_loop_plan_v1",
  "capture_dir": "outputs/cv_clip_clock_new",
  "cutoffs": ["180", "185", "190"],
  "observer_argv": ["python", "scripts/observe_claude_frame.py", "{request}", "{image}", "{response}", "--claude-bin", "claude"],
  "observer_code_files": ["scripts/observe_claude_frame.py"],
  "observer_timeout_seconds": 240,
  "ffmpeg": "ffmpeg",
  "extract_timeout_seconds": 120
}
```

```bash
python -m intent.observation_loop --plan local-plan.json --out outputs/cv_clip_loop_new
uv run --frozen python scripts/check_project.py --cpu-only
```

cutoff는 엄격히 증가하는 정수/유리수 문자열 1–50개다. 프레임은 상한보다 늦은
영상을 사용하지 않는다. 실제 실행에서는 Claude 실행 파일도 `observer_code_files`에
포함해 해시를 고정했다. 자동 모델 전환/대체 모델 호출은 없다.

## 범위와 다음 작업

현재 결과는 이미 검토한 개발 영상의 세 시각을 샘플링한 로컬 리플레이다.
실제 중계 수신, 연속 한 타석 전체, 투구 전 성공률, 좌표 정확도, 독립 검증은
완료하지 않았다. CV-5a 전체는 진행 중이다. 다음은 타석 시작·종료를 시각적으로
확인하고, 관측 빈도·허용 지연·적체 처리 기준을 정한 뒤 한 타석 리플레이를 측정하는
것이다. E-site5 실제 응답과 E-demo2 현장 확인은 별도 대기다.

## 실제 실행 결과

첫 실행은 3호출 중 2건 수락·1건 JSON 형식 오류였다. 실패 원문은 JSON 하나를 감싼 Markdown 코드 블록이었다. 어댑터를 수정해 전체 문자열이 정확히 하나의 `json` 코드 블록인 경우에만 껍질을 제거하고 동일한 필드·ID·이미지 SHA 검사를 적용한다. 주변 설명·여러 블록·잘못된 JSON은 거절한다. provider 원문은 그대로 보존한다.

수정 후 새 출력 폴더에서 세 시각 모두 새 모델 호출을 수행했다. v1 실패를 소급하여 성공으로 바꾸지 않았다. 실제 모델은 provider 보고값을 기록했으며 자동 전환하지 않았다.

### v1

| 상한(초) | 결과 | 미트 픽셀 | 예정→호출(초) | 예정→검증 발행(초) |
|---:|---|---|---:|---:|
| 180 | unavailable | None | 1.625 | 12.844 |
| 185 | 오류(JSON 형식) | 미수락 | 9.594 | 미발행 |
| 190 | unavailable | None | 17.032 | 27.891 |

### v2

| 상한(초) | 결과 | 미트 픽셀 | 예정→호출(초) | 예정→검증 발행(초) |
|---:|---|---|---:|---:|
| 180 | unavailable | None | 1.516 | 13.391 |
| 185 | marked | [703, 273] | 10.172 | 23.860 |
| 190 | unavailable | None | 20.500 | 32.297 |

상세 원응답·모델명·해시는 [공유 실행 기록](results/cv_followup_20261006/observation_loop_v1.json)에 있다. 첫 실행과 재실행 모두 합성 자료가 아닌 실제 호출이다. 두 실행의 차이를 모델 정확도 비교로 해석하지 않는다. 5초 간격보다 처리 시간이 길어 지연이 누적되므로 이 구성으로 실시간 처리가 된다고 말할 수 없다.

전체 검사 **1028 passed / 5 skipped / 2 deselected**(코드 블록 형식 수정 직전). 최종 어댑터 25 tests 및 Ruff 111경로 통과. 고정 207파일 SHA 불변.
전체 검사 경고 3건: 기존 체크리스트 subprocess 출력의 Windows UTF-8 디코딩 경고 1건과 Pillow 폐기 예정 API 경고 2건. 이번 실행기 테스트의 실패는 없었다.
