# 협업 v1 실행 계획 — 2026-10-12

[규약](COLLABORATION_PROTOCOL.md)은 사용자 채택 완료. 이 문서는 구현 상태와 미구현 합격 기준이다.
현재 호스트 기준은 `8f1aca688ed98e91e31457d0176cd13a90d22911`.
역할/정책 적용과 소프트웨어 출시를 구별한다. 새 기능은 이번 문서 반영에서 구현하지 않았다.

## 팀원이 묻는 세 가지 — 발송 전 답안

1. **즉시 내림 스위치를 만들 수 있다 — 2026-10-13 로컬 구현·합성 검증 완료(WS-safe1).** 기존 DATA_READ_ENABLED는 JSON 차단만 하므로
   전체 화면 내림 기능으로 간주하지 않는다. 호스트의 운영자 경로 `/_notice/v1/state`(별도 토큰 digest, 조건부 쓰기, 감사 기록)로
   화면·asset·공개 JSON·수집을 503 안내 응답으로 바꾸고 업로드는 유지한다. 직접 경로 우회·캐시·이미 열린 화면·뒤로가기·복구를
   로컬 Worker와 Chromium으로 확인했다([기록](../ops/public-host/NOTICE.md)). 실제 문구·전환·토큰 전달·다른 모델 검토는 남아 있다.
2. **접근 코드를 켜고 끄는 문을 만들 수 있다 — 2026-10-13 로컬 구현·합성 검증 완료(WS-access1).** `ACCESS_GATE_ENABLED`와 코드 digest·세션 비밀로
   HTML·JSON·정적 자산·수집의 직접 접근까지 401로 막고, 업로드/안내 인증과 분리된 무상태 세션 쿠키(HttpOnly·Strict)를 쓴다.
   만료·코드 철회·비밀 회전·로그아웃·요청 제한·same-origin 검사를 로컬 Worker와 Chromium으로 확인했다([기록](../ops/public-host/ACCESS.md)).
   화면은 호스트와 같은 출처여야 하고 `credentials: "omit"` fetch는 401이 된다(Song 요청 초안). 대상/공개 전환/코드 전달은 사람이 결정한다.
   접근 제한 자체가 MLB 이용 허가를 뜻하지 않는다.
3. **우리 쪽 하루 한 번 확인은 가능하며 예약을 등록했다.** 매일 09:00 한국 시간,
   읽기 전용으로 새 전달물/결정 요청을 확인한다. 앱/기기·인증·사용량에 따른 실행 실패는 별도 기록한다.
   Song 쪽 수행 가능 여부와 응답 가능 시간은 아직 확인하지 않았다.

위 내용은 로컬 회신 초안이다. 상대 mail에 자동 발송하지 않았으며 새 구현 완료를 주장하지 않는다.

## 다음 독립 작업과 먼저 적을 합격 기준

이 합격 기준은 착수할 때 관련 mail 또는 우리 board에 먼저 기록하고 선점한다.
이 목록의 순서는 기존 요청을 수행하기 위한 제안이며 사람의 우선순위 변경 권한은 유지한다.

- **WS-safe1: 긴급 안내 화면 — 로컬 구현·검증 완료(2026-10-13, Claude Fable 5.1, PR #20).** 로컬 합성 모드에서 ON/OFF·GET/HEAD·
  직접 HTML/JSON/asset 접근·이미 열린 화면·새로고침·뒤로가기·복구를 실제 로컬 Worker와 Chromium으로 검사했다(WebKit은 CI).
  ON 때 새 경기/민감 콘텐츠·내부 사유가 노출되지 않고 개발용 사전 등록 문구만 표시한다. 내려받은 자료의 원격 삭제는 보장하지 않는다.
  인증 운영자 경로·양쪽 담당자 절차·감사 기록·복구 조건·loopback 실측(PUT 후 첫 안내 응답 11.71 ms, 단일 isolate)은
  [NOTICE.md](../ops/public-host/NOTICE.md)와 [영수증](results/ops/ws_notice_rehearsal_20261013.json)에 있다.
  실제 다중 colo 전환 지연은 미측정이며, 공개 문구·전환·토큰·Song 화면의 안내 표시(요청 초안만)는 사람 결정이다.
- **WS-access1: 관람 접근 문 — 로컬 구현·검증 완료(2026-10-13, Claude Fable 5.1, PR #21).** OFF/ON, 정상/잘못된 코드, 만료·회전·철회·로그아웃,
  요청 제한, 쿠키/CSRF·private 캐시 분리, 직접 파일 접근 및 업로드/안내 인증 분리를 실제 로컬 Worker와 Chromium으로 검증했다(WebKit은 CI).
  소스/URL/로그/응답/영수증에 코드·digest·비밀을 남기지 않는다. 기본값은 게이트 OFF이며 승인된 접근 범위·활성화·코드 전달은 사람 결정이다.
  [ACCESS.md](../ops/public-host/ACCESS.md) · [영수증](results/ops/ws_access_rehearsal_20261013.json). 실제 https/Safari/CDN은 미검사.
- **WS-alert1: 양쪽 알림 연결 후보 — 모의 전송 구현·검증 완료(2026-10-13, Claude Fable 5.1, PR #22).** 감시 이벤트를 발행 중단(Song 우선)·
  호스팅 오류(우리 우선)·혼합(양쪽)·안내/접근 문/복구(정보)로 분류해 두 수신자에게 전달하고, 중복 억제·재알림 창·전송 실패 재시도/소진 기록을
  mock transport로 검증했다([ALERTS.md](../ops/public-host/ALERTS.md) · [영수증](results/ops/ws_alert_rehearsal_20261013.json)).
  실제 채널·연락처·발송 승인은 WS-human1 대기이며 `delivery_confirmed:false`를 항상 남긴다. 모의 성공은 전달 성공이 아니다.
- **WS-report1: 경기 종료 기록 양식/생성 — 구현·검증 완료(2026-10-13, Claude Fable 5.1, PR #23).** 경기 ID·집계 기간(UTC)·증거 라벨(합성/오프라인 재생/실경기)·
  동의/누락·수집 OFF·감시 이벤트/안내 전환/모의 알림 결과·조치·호스트/화면 커밋·계약 버전·manifest 해시·실행 명령·미측정을 담은 이슈 초안(Markdown+JSON)을
  입력 파일에서 생성한다. `collection_off`/`no_data`(미측정)·`zero_rows`(0세션)·`counted`를 구별하고 자료 없음을 0명으로 쓰지 않는다. 실제 로컬 D1 요약과 실제 감시 상태 기계로 리허설했다
  ([REPORT.md](../ops/public-host/REPORT.md) · [영수증](results/ops/ws_report_rehearsal_20261013.json)). 자동 게시 없음; 게시 범위는 사람 결정이다.
- **WS-review1: 다른 모델의 출시 검토 — 검토 기록·확정 결함 수정 완료(2026-10-13, Claude Fable 5.1, PR #25), 조건은 미충족.**
  main `70aa241`을 네 관점 + 지적별 반박 2명으로 검토해 24건 중 확정 12건을 수정하고 기각 12건(9건 추가 보강·3건 유지)의 사유를 남겼다
  ([기록](WS_REVIEW1_20261013.md) · [영수증](results/ops/ws_review1_recheck_20261013.json)). 작성 모델은 커밋 trailer로 Codex(2026-10-12)/Claude(2026-10-13) 묶음으로 분리했다.
  규약 5절 조건: Codex 작성분은 Codex 모델 id 사용자 확인 대기, Claude 작성분은 같은 모델 계열 검토라 **미충족** — "구현/자체검사 완료 · 출시 검토 미완료"로 인계하며
  비Claude 검토자 지정은 사람 결정(WS-review2)이다. 기존 같은 Codex의 별도 검토는 이 조건으로 소급하지 않는다.
- **WS-access2·WS-access3·WS-monitor2: 접근 문 결함 수정과 접근 문 ON 감시 — 완료(2026-10-13, Claude Opus 5.5, PR #26), Codex 교차 검토 대기.**
  세션 길이 축소 뒤 쿠키 부활(서명된 발급 시각 v2), 접근 문 ON에서 수집 요청 401(명시적 `accessGate`와 설정 검사, 거절 시 참여 종료),
  접근 문 ON 발행 감시(감시 전용 코드 로그인, 코드·쿠키 비노출)와 경기별 기록의 감시 범위 판정을 고쳤다([기록](WS_ACCESS2_20261013.md)).
  직전 "실행 가능한 작업 없음" 판정은 철회했고 다음 실행 가능 단위는 WS-alert2(열린 장애 재분류 알림)다.
- **WS-human1: 사람 결정 묶음.** 10/20까지 양쪽 연락 수단·시간대, 공개/초대 범위·비용,
  안내 문구·이미 합의한 긴급 내림의 조작 경로/접근 권한·복구 담당, 실경기 연결과 외부 회신/경기별 게시 범위를 확정한다.
  10/21 이후 고장 수리만 하며 승인되지 않은 기능 확대를 멈춘다.

## COLLAB-001 현재 수신 상태

근거: [mail #18 및 첫 연결 댓글](https://github.com/Pitcheezy/transition-models/issues/18#issuecomment-6118069441),
2026-10-12 `gh issue view 18 -R Pitcheezy/transition-models --json title,body,comments`로 조회.
아래는 **Song의 전달 안내**이며 이번 작업에서 파일 내용/빌드를 실행 검증하지 않았다.

- 발행기 `svc/ws-publisher@d5a1dd9`, 예제/스키마 `apps/observer/publish_contract/v1/`.
- 공개 화면 `svc/ws-static-web@ef4e4df`, `apps/observer/web`에서 `npm run build:public`.
- 첫 연결 문서 `collab/ws-2026:docs/pm/transfers/COLLAB-001-first-connection-pack.md`.
- 미지원 투수 예제 누락, 추천 후보 `detail.probability`/`target` 스키마 2곳 수정 예정.
- ETag/304를 사용하는 읽기 최적화는 변경 예고다. 현재 우리 GET/HEAD 후보는
  ETag 조건부 수정과 구별해야 하며, **GET If-None-Match/304 계약 연결은 아직 검증하지 않았다.**
- 2026-10-13 WS-ops2에서 예시 13·스키마 6을 고정 커밋 SHA로 받아 대조(19/19)·스키마 검증(오류 0)·호스트 제약 대조했고, 문서 절차대로 우리 로컬 Worker에 올린 뒤
  고정 커밋 공개 화면 빌드가 목록·경기 전·추천·확인 중·연결 끊김·공수 교대·종료·발행 중단(갱신 지연)을 구별해 읽는 것을 Chromium으로 확인했다
  ([기록](WS_OPS2_FIRST_CONNECTION_20261013.md)). 공개 GET 304는 구현했다. `unsupported` 예시·추천 후보 스키마 2곳은 Song 후속, 실제 발행기 업로드·계정 연결은 WS-ops4다.
  다른 레포 코드를 바꾸거나 발행기를 실행하지 않았다.

## 기존 구현을 과장하지 않는 회신 근거

- 업로드 API 후보는 `/_publish/v1/...`의 Bearer 인증 PUT/DELETE/HEAD,
  `UPLOAD_ENABLED`·`PUBLISH_TOKEN_SHA256`과 허용 경로를 사용한다.
  공개 읽기는 `/v1/...` GET/HEAD이며 원본 바이트/조건부 변경/삭제 표식 구현은
  [호스트 README](../ops/public-host/README.md), [전송기](../ops/public-host/PUBLISHER.md)에 있다.
- 호스팅 조건 1-1의 로컬 전송 검사는 완료했지만 실제 CDN Date/Age/헤더·삭제 전파·
  다중 파일 발행 정합성·Song 화면과 스키마는 WS-ops2/4에서 확인해야 한다.
- 미트 한 경기 처리 시간/처리량은 **미측정**. 확보 영상·투구 대응·보정 가능한 범위를
  먼저 고정한 뒤 출력/기권/미검토 범위를 함께 재야 한다. 기존 모델/사람 평가 수치를 처리시간으로 대신하지 않는다.
- 실제 알림 수신·공개 배포·접근 코드·안내 화면 스위치는 **미완료**다.

## 이번 반영의 증거

- 합격 기준 선기록: 우리 board #3의 H-collab2 선점, 선점 커밋 `12d4639`.
- 변경 범위: 협업 문서·양식·작업 지침·체크리스트. 운영 코드/상대 레포/실행 서버/배포 변경 없음.
- 검증 명령: `python -m pytest tests/test_checklist_model.py -q`; YAML 파싱·현재 상대 링크 확인;
  `git diff --check`; 별도 Codex 문서 대조. 체크리스트 7 passed, YAML 파싱/현재 상대 링크 24개/공백 검사 통과.
  같은 모델 문서 검토이며 운영 코드 교차 모델 검토가 아니다.
- 증거 종류: 문서/저장소 및 이슈 조회. 합성/오프라인/실경기 성능 측정 **해당 없음**.
- 완료 커밋·파일 SHA·실행 결과는 우리 board 종료 기록에 고정한다.
