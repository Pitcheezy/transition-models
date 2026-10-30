# SITE-pa-sequence1 — 한 타석 이어보기

사용자 기능: 기존 경기 재생 화면에서 ‘이 타석 이어보기’를 누르면 현재 공부터
영상 → 실제 결과 5초 → 같은 타석 다음 공으로 이어진다. 마지막 공에서는 정지한다.
현재 공부터 시작함을 표시하며 자동으로 다음 타석을 넘기거나 누락 영상을 건너뛰지 않는다.

## 구현과 합격 근거

- 기준 a9ad2cd → 제품 57d15fde5ebfa3e6d95c9cf0332a4230c49359e9, PR85(main 미통합).
- 독립 제어기는 투구 ID·자료 세대·타석을 대조한다. 중복 종료·오래된 타이머·늦은 재생 응답을 무효화한다.
- 수동 선택/공개/숨김/이력 이동, 정지·탐색·별도 미트 이미지·영상 오류·페이지 이탈은 자동 진행을 취소한다.
- 영상이 없으면 해당 투구에서 정지하고 직접 결과를 공개할 수 있다. 새 좌표·추천·결과를 생성하지 않는다.
- Node255 통과(이어보기/영상48 포함), 체크리스트 Python8, 링크·기존 미디어 SHA 검사 통과.
  처음 Python 실행은 기본 임시폴더 접근 오류였고 지정 outputs 임시폴더로 통과했다.
  UTF-8 환경을 명시한 최종 실행은 경고 없이 8개 통과했다.
- 다른 모델 호출 설정 gpt-6.1-terra의 고정57d15fd 읽기 검토 PASS, 독립48검사 통과.
  런타임 모델 ID는 미노출이다. Claude 검토 또는 사람 검수로 부르지 않는다.
- Windows Chrome에서 실제 첫 타석3클립 자동 연결·마지막공 정지, 결과 대기 중 멈춤,
  수동투구 전환 초기화, 390px 시작/정지·가로폭, 영상 제외69:2 비활성 확인.
  초기 프로그램 되감기가 사용자 탐색으로 오인되던 결함은 불필요한 시각 대입을 제거해 수정했다.
- 실제 iPhone/Mac·모든261클립 전수재생·실시간/부하 검사는 하지 않았다.

## 배포와 재현

기존 Sites 공개 v13 성공. Sites 소스8174777d35e955726d5e1cfa2457bcb48a81e07a.
허용41자산+기존 hosting manifest 총42파일. 기존 공개 범위 유지, 별도 Cloudflare 시험 서버 변경 없음.
[기계 판독 기록](results/site_fullgame_20261030/pa-sequence-receipt.json).
공개 pitcheezy.com에서도 첫 타석3구를 실제 자동 재생하고 849843:1:3 결과 공개·타석 종료 정지를 확인했다.

```text
python scripts/check_pitch_studio.py
node --test web/pitch-studio-tests/receiver-sequence.test.cjs web/pitch-studio-tests/receiver-video.test.cjs
python -m pytest tests/test_checklist_model.py -q --basetemp outputs/pytest-pa-sequence
```

Python 환경은 UTF-8, Node는 PATH에 둔다. 이전a9ad2cd의 Ubuntu/macOS CI는 run41019359785 모두 성공했다.

## 형 모델 연결에서 완료와 미완료

완료: 받은849843의71타석262구(추천246/미지원16), 영상261, 사후 기록존262를 공개 사이트에서 재생.
서버에서 새로 모델을 실행하는 구조가 아니라 형이 계산한 결과 파일을 읽는다.
현재 한 경기 시연에는 가중치 인수가 필수가 아니다.

미완료: SITE-2 채택할 최신 Song 관전 빌드·전체SHA·검토 기록, 추가 경기의 완성 추천 파일,
실시간 발행 갱신 및 공동시험 최종 합격. 10/30 조회 기준 #38의 10/27 화면 인수 요청 뒤 새 회신은 확인되지 않았다.
10/29 Song 연구 결과를 새 서비스 모델이나 전달 완료로 승격하지 않았다.

10/26 공동시험은 STOPPED다. 당시 업로드/읽기/삭제·만료403 확인과 관리 설정 종료를
옛 토큰401/OFF503 실측으로 바꾸지 않는다. 이 브랜치의 WS_OPERATIONS_HANDOFF 상단10/25는 과거 기록이다.
최신 운영 근거는 고정77b958dbf3424c8c69259127cc7f2b93511c42ee의
[종료 보고](https://github.com/Pitcheezy/transition-models/blob/77b958dbf3424c8c69259127cc7f2b93511c42ee/docs/WS_JOINT_TRIAL_CLOSEOUT_20261026.md)다.

다음 한 단위: 사용자 관전 검수에서 나온 구체 결함 수정 또는 채택 빌드 수신 시 SITE-2.
추가 경기/제외1구 출처 요청은 새 발신 승인 범위에 따라 처리한다. 요금제·30/50명 실측은11월 유지.
