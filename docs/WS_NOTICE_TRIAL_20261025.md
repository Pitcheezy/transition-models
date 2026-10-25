# 본인 비상 안내 전환·복구 — 2026-10-25

**기능 통과·저장 로그 1건 확인 대기.** 본인 전용 시험 서버에서 안내 ON/OFF, 동일 로그인 세션 복구, 안내 시험 자격 회수401을 실제 확인했다. 형 최신 화면·발행기 공동시험이나 공개 운영 합격은 아니다.

## 10/25 후속 검토 기준

원본 시험과 아래 영수증은 당시 근거로 보존한다. 이번 PR64 검토는 저장된 자료의 정합성 확인이며 실제 Cloudflare·회수 자격으로 다시 시험한 것이 아니다. [후속 로그 재조회](results/ops/ws_notice_log_recheck_20261025.json)도12/13으로 동일하므로 WS-notice3 전체 증거 합격은 계속 대기다.

현재는 [협업 실행 계획](WS_COLLAB_V1_ACTIONS.md)에 따라 새 최종본·공동시험 GO를 기다린다. 요금제·전시회 요청량/추가 부하는11월 보류다. 사용자는 기존 메시지와 ZIP을 직접 보냈다고 보고했으며 상대 수신/검증과 초안 원문 동일성은 별도 확인 대상이다. 아래 미발신 문구는 작성 당시 이력이다. 이번 검토에서 새 회신·ZIP을 발신하지 않는다.

## 시험과 결과

기존 검토된 안내 기능을 사용했다. 접근문ON, 업로드/자료읽기/이용기록/피드백OFF, Workers Free를 유지했다. 운영 소스나 형 코드 변경은 없다. 개발용 `maintenance` 문구만 썼으며 공개 문구 승인으로 처리하지 않는다.

- baseline 4회: 안내 GET200/OFF → 본인 복구 코드 로그인200 → 홈200 → health503(`publication_not_enabled`).
- ON 4회: 이전 ETag에 조건부 PUT200 → GET200/ON 및 감사 확인 → 홈503/안내 HTML → health503/`service_notice`. 두 응답의 `X-Pitcheezy-Notice: maintenance`도 확인했다.
- OFF 4회: ON의 ETag에 조건부 PUT200 → GET200/OFF 및 감사 확인 → 같은 관람 세션 홈200 → health503/`publication_not_enabled`. 홈·health 응답 본문 SHA가 baseline과 정확히 같았다. 실패 뒤 재로그인하여 복구로 처리하지 않았다.
- 자격 회수 1회: 본인 복구용 안내 자격만 남기고 시험 안내 자격을 제거한 뒤, 같은 시험 bearer GET401을 확인했다. 복구 자격은 본인 비공개 파일에만 보관한다.

서비스 요청13회(관람7·안내6), 자동 재시도/리다이렉트0회다. 별도 관리 API18회는 GET16·안내 Secret 교체 PUT2이며 원장으로 구분한다. 공개 파일 업로드/삭제는0회지만 안내 상태와 감사 R2 쓰기·로그 저장·예약 정리는 있으므로 계정 전체 쓰기0이라고 하지 않는다.

ON/OFF 각각 ACK의 change_id·revision·audit_recorded와 후속 GET의 감사 id·operator·고유 시험 reason·message_id·ETag before/after 연결을 대조했다. 감사 조회 `audit_unavailable:false`다. OFF는 접속 동작 복구이며 R2 객체의 원상복원이 아니다. 증가한 revision과 감사 행은 보존된다.

## 시간과 저장 증거

- 클라이언트가 PUT 성공 본문을 받은 뒤 상태/감사를 확인하고 의도적으로2.1초 기다렸다. 홈에서 ON을 관측한 시점은 ACK 뒤 **3.430초**, OFF 복구 관측은 **3.211초**다. health는 각각3.531/3.313초다.
- 이는 해당 요청에서의 관측 경과 시간이다. 최초 전환 시간, 전 세계 엣지 전파 상한, SLA 또는 이미 열린 화면의 갱신 지연은 측정하지 않았다.
- 13개 요청 중 12개만 저장 로그와 대조했다. **안내 OFF PUT 1건은 현재 다운로드와 후속 UI 조회에서 미확인**이다. 그 응답200·R2 감사 행·후속 OFF 조회·실제 화면 복구는 확인됐지만 저장 invocation 로그를 대신하지 않으므로 전체 증거 합격으로 처리하지 않는다. 수집 지연인지 누락인지는 모름이다. 이 요청을 다시 보내 증거를 대체하지 않았다.
- 원본 JSON: 60,360bytes, SHA256 `c43bd46748c1e03b17a392e45421bbe2dc8bcebf59d4846163f78c023497b0b4`. 원본은 비공개 로컬 보관이다.
- [공유 영수증](results/ops/ws_notice_trial_20261025.json): SHA256 `8a9e8d826db10450748f38867b719c46f0c20e6c0304f56c2fee4b90a9c0c10c`. cf-ray로1:1 결합한 뒤 시각·method·path·status·version을 대조했다. 원본 IP·헤더·계정·origin·cookie·token/digest·감사 내부 reason은 공유본에서 제외했다.

## 출처와 종료 상태

- 고정 클라이언트: `47ac078e8523877008d8bafe8295a94881a3df49`의 notice-client/notice/monitor. 운영 runtime은 `e9b362b75d6d4768c552740bfc6e0124872805e1`과 동일하다.
- 원격 bundle SHA256 `3312fbff2dac2a22b32e474392ee7eb107663c79e9749781810a681e5ee07cfd`. 두 안내 자격 교체 전후 각각 latest=100% deployed와 전체 바이트 일치를 확인했다.
- 최종 배포 버전 `d714e7fb-20d4-4a80-9f29-695e44130955` /100%. 안내 OFF, 관람문ON, 업로드·자료읽기·이용기록·피드백OFF. 본인 복구 자격 유지, 시험 안내/발행 자격 회수. Logs100%·저장ON을 포함한 기존 설정 전체를 annotations 제외 대조했다.
- 작성 Codex(GPT-6 계열, 세부 모델ID 미확인), 독립 검토 `gpt-5.6-sol` PASS. 검토는 고정 비공개 helper와 pinned client의 정적 읽기이며 검토자는 실제 접속·자격·원본 로그를 다루지 않았다. helper별 SHA는 영수증에 고정했다.

실행 명령은 영수증의 `commands`에 있다. 각 phase는 exclusive 시작/응답/결과 파일과 이전 phase 통과를 요구한다. 현재 시험 자격은 회수됐으므로 **기존 명령을 재실행하지 않는다.** 불명확한 쓰기나 감사 부재는 별도 cleanup 원장으로 처리하도록 준비했지만 이번 정상 경로에서는 cleanup 요청이 없었다.

## 남은 것

1. 안내 OFF PUT의 실제 저장 로그1건 조회. 다른12건·R2 감사·복구 성공을 로그1건의 대체 증거로 부르지 않는다.
2. 새 v7/v4.5 또는 이를 대체하는 고정 전달본·전체SHA·검토 결과, 최신 화면의 열린 추천 숨김/복구와 알려진 결함 처리 확인.
3. 양쪽 사람이 정한 새 창·접속 자격·단일 writer로 발행/읽기/철회/복구·양측 증거를 대조하는 공동시험. 현재 시험 자격 재사용 금지.
4. 공개 문구·Song 안내 제어 권한·실제 연락/응답 체계와 공개 여부 결정, 실제30~50명/최신UI 부하 검증. 현재는 호스트 HTTP 전환만 확인했다.

팀원 레포·프로세스·배포는 다루지 않았다. 새 회신은 아래 초안이며 아직 발신하지 않았다.

## 기록 검증

체크리스트 규약8 passed(2.11초), Node/Python 비공개 실행기 문법·고정클라이언트SHA·문서diff 검사 통과. 별도 문서 감사에서 요청수/로그12건/미확인1건/개인정보 제외와 미완료 상태 일치를 확인했다. 공유 영수증에 PUT ACK 본문 수신 시각을 추가해 관측 경과 시간을 재계산할 수 있게 했다. 운영 소스 변경이 없어 전체 학습 검사는 반복하지 않았다. PR64의 앞선 기록47ac078은 Ubuntu/macOS CI 모두통과했으며 후속 기록의 CI는 해당PR에서 확인한다.

## WS-evidence1 검토·통합 기록 — 2026-10-25

- 검토 대상: PR64 고정 `abddb240a698e91923d14ef413e36081a4af5315`, 기존 기준 `24fea70f12ba53d3503823c90b3b06cec045a277`. PR63은 사용자 승인·동일 head CI8/8 확인 뒤 main `06aa6d0f3ad24a7e9f0649491f9887283d8f77d8`에 병합했다. PR64에는 이 main을 통합하며 AGENTS·CHECKLIST·운영 인계 충돌3곳을 해소했다.
- 작성 Codex(GPT-6 계열, 세부 ID 미확인), 검토 `gpt-5.6-sol`: 고정 PR64의 공개 문서/JSON에서 P1/P2 없음. 원본 영수증2개 Git LF 바이트/SHA, 안내13=안내6+관람7·관리18=GET16+PUT2, 로그12/13 및 `complete:false`, 발행HEAD404→401→503과 만료 전 시각, 고정 client SHA3개를 확인했다.
- PUT ACK 본문 수신→후속 응답 헤더 관측의 경과4값(ON홈3430/health3531, OFF홈3211/health3313ms)을 재계산했다. 본문 수신까지의 지연이나 전체 엣지 전파 상한을 새로 측정한 것이 아니다.
- root도 공개 영수증 불변·계수/시각/버전·지연·client SHA를 대조했다. 현재 구역 상대링크128개, main 날짜별 이력3구역 보존, 운영 코드 변경 없음, `git diff --check` 통과. `python -m pytest tests/test_checklist_model.py -q`:8 passed(2.05초).
- 이 검토는 기존 공개 증거의 일관성 확인이다. 비공개 원본 로그·helper·원격 bundle의 원문이나 실제 Cloudflare를 다시 조회하지 않았으므로 당시의 비공개 1:1 결합을 독립 재실행했다고 부르지 않는다. 공개 기록에서 자격값·계정/접속 주소·개인정보 노출은 발견되지 않았다.
- 기존 안내·발행 영수증과 회신 초안은 바꾸지 않았다. main이 이미 가진 WS-publish4/WS-notice3를 중복 등록하지 않았으며 OFF PUT1건 미확인·새 최종본/공동시험 GO·11월 요금/요청량 보류를 유지한다. [착수 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6393493153), [새 head CI/병합 상태](https://github.com/Pitcheezy/transition-models/pull/64).
