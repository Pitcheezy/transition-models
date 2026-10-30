# SITE-fullgame1 — 849843 저장 경기 전체 연결

후속: [SITE-video1](SITE_GAME_VIDEO_20261030.md)에서 영상261구 연결·1구종불일치 제외와 공개v11을 완료했다. 아래 영상3구/v10은 당시 고정 기록이다.

## 완료한 사용자 기능

기존 PC·모바일 재생 화면에서 컵스 @ 파드리스의 **71타석·262구**를 탐색한다.
이닝·타석·현재 타석 투구를 선택하고 추천을 본 뒤 실제 결과·플레이트 위치를 공개한다.
홈과 경기 페이지는 전체 경기로 연결되며 별도 첫 타석 영상 모드는 보존했다.

- 추천246구·미지원16구. 선택 비중을 정확도나 사건확률로 표시하지 않는다.
- 영상 연결3구·미연결259구. 영상이 없어도 수동 결과 공개가 가능하다.
- 셋업은 estimated27·unavailable12·미제공223. 같은 수신본의 가로 추정만 결과 뒤 표시한다.
- 전체 경기 자료에는 승리 기대/사건확률/실행 서버 커밋이 없으므로 미제공·미확인으로 남겼다.
- 별도 첫 타석 응답의 승리 기대·미트 판독 프레임을 전체 경기 응답에 섞지 않는다.
- 전체 경기 표시 날짜는 수신본의 한국 날짜09/30이며 홈/경기 카드의 현지 날짜는09/29다.

## 구현·자료 경계

입력은 이미 수신한 비공개 v5 영상 검토팩의 `review-data.json`이다. 새 팀원 API 호출은 없다.
`scripts/export_pitch_studio_game.py`는 ZIP/report/원문 SHA를 확인하고 공개 허용 필드만 선별한다.
원문 reason·play_text·내부 섹션·개인 경로는 제외했다. 71개의 타석 종료 사건은 모두 해당
타석 마지막 투구에만 있는 것을 확인했다. 원본 ZIP·영상·가중치·독립 평가 자료는 바꾸지 않았다.

`web/pitch-studio/receiver-fullgame.js`는 기존 watch/reveal 계약과 분리한 저장 화면 내부 형식이다.
공개 발행 계약이나 IntentEstimate v1.1 변경이 아니다. 투구 ID·index·타석 순서를 검사하고,
목록 순서에 의존하지 않는다. 실제 fetch 바이트 SHA까지 고정해 영상의 다른 자료 오연결을 거부한다.
이 해시는 일관성 검사이며 제공자 인증·권리·정확도 검증이 아니다.

## 검증 근거

- 구현 `7551da0`, 검토 지적 수정 `7d18fe1de50115f76ae0efee8beb41fcc59a0e52`.
- Node125 통과(전체 경기30 포함), Python22 통과(선별14+체크리스트8), 사이트 링크/미디어 SHA 검사 통과.
- 다른 모델 호출 설정 `gpt-6.1-terra`: 첫 P2(선언된 원문 SHA만 확인) 발견 후 실제 파일 바이트 고정,
  변조 회귀 추가; 고정7d18fe1 재검토 APPROVE. 검토자의 자체 식별은 GPT-6까지만 노출됐다.
- Windows Chrome 실제 UI: 첫 영상 종료 공개, 71타석 선택, PA2·미지원41·마지막71,
  이닝 경계 이동, 공개/숨김·이전 자료 초기화·기존 첫타석 모드 복귀 확인.
- 모바일390×844 설정에서 문서폭375/내용폭375로 가로 넘침 없음. 실제 휴대폰 검사는 아니다.
- 전체262구 공개 전/후 ID 결합·기권/미지원 수는 자동 검사했고 실제 영상 전수 재생 검사는 하지 않았다.

재현: `node --test tests/js/pitch_fullgame.test.cjs`, `python scripts/check_pitch_studio.py`,
`python -m pytest tests/test_pitch_studio_export.py tests/test_checklist_model.py -q --basetemp outputs/pytest-fullgame-check`.
선별: `python scripts/export_pitch_studio_game.py --input-zip <private-v5.zip> --output web/pitch-studio/game-849843.json`.

## 실제 공개 반영

사용자의 기존 공개 반영 지시에 따라 같은 Sites 프로젝트·public 범위를 유지했다.
35개 허용 자산과 hosting manifest 총36파일 패키지의 경로·SHA를 대조했다.
이전 HTTP500 중단 이력은 보존하며 이번 일반 소스 푸시·버전 저장·배포는 성공했다.
Sites 소스 `d6e89eb71715a169bf61a01390e980c2c6844cf2`, 공개 **v10**.
배포 `appgdep_6ae41be6832c81918899fbb58eef093f`는 succeeded다.
공개 도메인에서도 전체 목록·마지막 투구 결과가 표시되는 것을 확인했다.
Git main 통합과 실제 공개 배포는 별개다. 이 기능은 PR85 작업 브랜치에 있다.

상세 해시·검사·배포 영수증: [receipt.json](results/site_fullgame_20261030/receipt.json).
팀원 저장소·별도 Cloudflare 시험 Worker·DNS·접근권한·요금제는 변경하지 않았다.

## 남은 장애물과 다음 한 단위

전체 경기의 추천·결과 탐색은 완료했지만 영상 전구간·자동 CV·실시간 모델 연결은 아니다.
다음은 이미 조사한 PA2 5구의 공식 클립을 고정 등록부/투구 ID/SHA로 연결하고,
실제 재생·전환 초기화를 확인하는 CV-50b다. 새 미트 점이나 제구 오차를 만들어 채우지 않는다.
채택된 Song 최신 관전 빌드·실시간 공개 발행 연결·30~50명 시험은 별도 조건을 유지한다.
