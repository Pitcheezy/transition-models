# 월드시리즈 최종 전달본 — 수신·우리 호스트 검증

2026-10-21 / WS-partner4. **최종 파일 수신과 노트북 합성 호환 검증을 완료했다. 실제 배포·Song 접속·공동시험은 실행하지 않았다.**
우리 기준 `9ed7135873a3c0bca2b4ce678f2659ffc0e262e2`. 팀원 저장소/장비/프로세스는 변경하지 않았다.
[정형 결과](results/ops/ws_final_delivery_20261021.json), [공동시험 협의안](WS_JOINT_TRIAL_GATE06_20261021.md), [미발신 회신](mail_drafts/COLLAB-001-final-delivery-reply-20261021.md).
[사전 합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6312118763).

## 무엇을 확인했나

- 한 키 실행본: `pitcheezy-onekey-delivery-final2-000e4ba0.zip`,47,695bytes,SHA-256 `f8f1c48a9925913857827144e8fb997016417d4f6cac7b71d333d25a33646796`.
- 전달팩: `partner-runnable-review-v4.4-000e4ba.zip`,188,620bytes,SHA-256 `c431b3f737c4d7eaa1e8d8e1e119b2c25dfb32f65588f7c8dcda7c23c1bab18e`.
- 사용자 메시지에는 SHA 앞뒤만 있었고 그것과 일치했다. 조회 시 #38에는 새 최종 회신/전체 SHA가 아직 보이지 않았다. 따라서 외부에서 받은 전체 기대값과 대조 완료했다고 쓰지 않는다. 전체값을 회신에 넣어 상대와 확인한다.
- 각각7/23개 일반 파일, CRC·경로이탈·중복·case충돌·링크/암호화 검사 통과. manifest22개, SHA256SUMS6개 일치. 공개자료에 원본 ZIP/소스를 넣지 않는다.
- 최종 등록서와 v4.4의 source4/build4가8/8 일치. 우리 main의 runtime5 Git blob/CR제거SHA가 등록서 PR42 `48ec406589982547e298ff2ee4bc2d64ed0216c0` 기대값과5/5 일치. **소스의 일치이며 실제 배포 증거는 아니다.**
- 공급자 명시 소스는 `000e4ba0d83bb81fee8db82539e67c7ab0e7d0b3`. 팀원 원격 commit tree와 별도 대조하거나 전체 빌드를 재현하지 않았다.
- REVIEW-007의 wrapper/등록서 SHA와 실제 파일 일치. 작성 `claude-opus-5-5`, 검토 `claude-fable-5-1`를 확인했다. 이는 최종 N23 변경분의 검토 기록이며, 이전 REVIEW-005/006 원문과 테스트/로그는 포함되지 않았다. 공급자21/14/26검사 및368회귀/4loopback 보고를 우리 재실행 결과로 세지 않는다.

## v4.2 이후 달라진 점

README의 ‘형식 그대로’는 v4.3.1 대비 설명이다. 우리가 앞서 받은 v4.2와 비교하면 optional `next.reference`와 예제가 추가됐고 profile_reference 설정이 켜졌다. 미지원 투수의 과거 구종 빈도는 추천이나 사건확률이 아니며 새 화면도 별도 ‘참고·기록 통계’로 표시했다.

일정 조회가 끊겨도 마지막 정상 목록의 진행 중 경기는 확인한다. health의 `game_checks`를 읽고 `schedule_unavailable`을 feed실패와 구분한다. 현재 우리 감시기는 reason 열거값으로 이를 거부하지 않아 운영 코드 수정 필요 근거는 발견하지 못했다.

화면은 투수 시점으로 바뀌고 raw좌표는 그대로다. 합성 캡처에서 우타자 표시가 오른쪽이고 ‘투수 시점’ 범례를 직접 확인했다. 물리 좌표 정확도나 실제 모바일 기기 검증은 아니다. 공통15초 지연은 패키지 밖 Mac 운영 설정으로 실측하지 않았다.

## 실제로 실행한 검사와 한계

- 받은 예제6개를 받은 game/health schema와 format checker로 검사: 통과.
- 원본 `python -B -S verify_offline.py`: exit1. 별도 원본 runner import 검사에서 `ModuleNotFoundError: fcntl` 확인. 원본 수정·shim·Mac 실행 없음. 네이티브 Windows에서 발행기를 실행하지 않고 우리 노트북은 호스팅을 담당한다.
- Windows의 실제 Worker/Miniflare/R2 + 받은 public-build4개 원문 + 합성 JSON으로 기능34항목 통과. driver52/browser98,합계150 HTTP는 모두 loopback이다. 외부 브라우저 요청0, 원본23파일 불변, 새 브라우저/서버 정리 완료. 이150회는 합성 화면 검증량이며 한 키 본시험18회 또는 실제 요청 예산으로 옮기지 않는다.
- 추천/결과/확인중/미지원/참고통계, raw bytes와ETag/304, health만 갱신할 때 불필요한game 재조회 없음, file_sequence 증가 때 재조회, 철회/복원, 접근문/logout, 모바일 너비390의 문서 가로넘침 없음 등을 확인했다. 실제 iPhone/Safari는 미실행.
- **안내 ON 완전 철회 조건은 미충족:** maintenance/data_hold 모두 이미 열린 화면에서12초 후 안내와 ‘마지막으로 받은 추천’이 함께 남았다. 새로고침한 화면/새 자료 요청은503으로 차단되고 OFF 후 페이지200 복구를 확인했다.34개 기능검사가 이 제한까지 통과했다는 뜻은 아니다. Song 화면 수정 또는 허용범위 결정이 필요하다.
- 안내 관련3개 테스트 파일 통과. 별도 단일 isolate loopback: ON PUT18.81ms → 첫 안내15.18ms, OFF PUT19.02ms → 첫 정상22.17ms. 실제 CDN/운영 RTO는 미측정, isolate별2초캐시·열린화면 폴링과 구분한다.
- 초기 우리 harness는 notice요청에 불필요한schema를 넣어400을 받았다. 수정 후 ‘다음 공 추천’만 사라지는 것을 완전철회로 잘못 판정한 검사를 바로잡았다. 별도 오래된 고정예제의 복구 후 새추천문구 대기도timeout이라 최종 검사는 HTTP200복구와 최신추천 여부를 구분했다. 실패/중간 원본 기록은 덮어쓰지 않고 보존했다.

## 실제 배포 전 후보

받은 public-build와 기존 검토된 host `5effc7a4deef21ee37d07f8574b43b23935d2189`를 묶었다. runtime5는 현재main과 같고 받아온파일은 재빌드/수정하지 않았다.

- 비공개 `outputs/partner_final_20261021/candidate-prep/release/release.zip`.
- 509,591bytes / SHA-256 `a969d701d5992558bf94d82d0cbdce7d99166d5e9a2ba746d7fab04145680704`.
- build/check 및 설정10항목 통과. `deployable:false`, `deployment_approved:false`.
- placeholder 자원·만료된 scope, gateON, read/upload/telemetry/feedbackOFF. 실자원 식별자·현재 창/만료·승인 조건을 채운 새 배포안을 만들기 전에는 사용하지 않는다.
- 이번 Wrangler dry-run은 실행하지 않았다. 검사 통과를 실제 bundling/배포 완료로 바꾸지 않는다. 마지막 클라우드 확인은10/16이며 현재는 미확인이다.

## 결과 인수와 남은 결정

N23는 정적 흐름상 첫 요청·키장부 쓰기 전에 거부한다. NaN과 후속 대상해시 방어도 확인했으나 원본 wrapper를 실행한 것은 아니다. `run --dry-run`은 client실행/로컬쓰기가 있으며 단순조회로 취급하지 않는다.

조건부 정적 소견: 운영자가 승인reference에 비밀을 잘못 붙인 경우 grant에 복사되고 finish의 비밀검사에서 실패할 수 있다. 이때 이미 작성된 PUBLIC-SUMMARY의PASS가 남는 흐름이 있다. 정상입력의 유출을 발견한 것은 아니며 실행재현은 미실시다. 자동 승인 검토가 격리 함수실행을 최초 읽기전용 범위 위반으로 거절해 우회하지 않았다. 종료코드+wrapper-log가 실패이면 공개 요약을 공유하지 않는 조건을 적용한다.

다음은 현재 Cloudflare 상태 조회·구체배포안, 전체요청/정상회수GATE-06, 창별GO·긴급연락·양쪽 안내권한, 열린화면 안내처리 확인이다. 일정은10/22오전~14시 설정/18~19:30시험/21시판정의 **제안** 상태다. 새 대외발신·자격/접속확대·배포는 미실행이다.

## 재현 명령

아래 경로의 받은 원본과 로컬 설치 환경이 있어야 한다. Git에는 비공개 소스/빌드·원시 기록·캡처를 넣지 않았다.

```text
python -B -S outputs/partner_final_20261021/original/verify_offline.py
node outputs/partner_final_20261021/integration-accepted/combined-review.mjs
node --test ops/public-host/tests/notice.test.mjs ops/public-host/tests/notice-client.test.mjs ops/public-host/tests/notice-cli.test.mjs
node ops/public-host/rehearse-notice.mjs --output <새-비공개-영수증.json>
python -B -S scripts/build_public_host_release.py check outputs/partner_final_20261021/candidate-prep/release/release.zip
python -B -S scripts/check_public_host_config.py outputs/partner_final_20261021/candidate-prep/candidate
```

Python3.12/Node24.1.0, 설치된Miniflare·Edge/Playwright 사용. 원시 영수증/harness SHA는 정형 결과에 고정했다. 내부 경로·토큰 지문·접속 주소를 제거한 결과만 저장소에 기록한다.

별도 문서·증거 검토: 고정 `e8f486e6677a1982a6be6b6e0e84dd0a00870df8`의 gpt-5.6-sol 검토PASS. 새 운영코드 없음. 체크리스트8·신규문서 상대링크·추가본문 개인정보/비공개주소 검사 통과. 현재 계정 조회를 시도하려 했으나 로그인된 in-app 브라우저 조회 도구가 이 세션에 없어 Cloud API/설정 조회는 하지 않았다.
