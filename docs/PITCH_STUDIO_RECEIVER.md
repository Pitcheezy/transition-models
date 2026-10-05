# 우리 쪽 응답 수신·표시 도구 — 2026-10-05

## 완료 범위

팀원의 모델·API·화면을 수정하거나 호출하지 않았다. 우리 공개 사이트에 별도 로컬 수신
페이지 `receiver.html`을 추가했다. 서비스의 ‘연결 구조 보기 → 전달받은 응답 파일 확인’으로
연다. 파일은 사용자의 브라우저 메모리에서만 처리하며 업로드·원격 요청·localStorage가 없다.
새로고침이나 ‘자료 비우기’로 입력을 제거한다.

실제 팀원 응답은 아직 받지 않았다. 포함된 게임 900001/선수 900001·900002의 자료는
이 도구의 **합성 검사 예시**이며 실제 모델·경기·성능 결과가 아니다. 예시 화면이나 이
검사 결과를 실제 서비스 통합 완료, 사전 예측 성능, 투수·타자 책임 판정으로 보고하지 않는다.

## 전달 양식

브라우저의 ‘전달 양식 받기’가 전체 합성 JSON을 내려받는다. 실제 자료를 받을 때 우리 쪽에서
아래 봉투에 묶으면 된다. 팀원에게 API 변경이나 신규 export 기능 구현을 요구하지 않는다.

```json
{
  "schema": "pitcheezy-receiver-v1",
  "source": {
    "kind": "provided_export",
    "revision": "40자리 소스 커밋",
    "model_id": "제공자가 확인한 모델 식별자",
    "exported_at": "시간대 포함 ISO 생성 시각"
  },
  "game_pk": 849843,
  "at_bat_number": 1,
  "timeline": "GET /api/watch/849843의 JSON 객체",
  "reveals": [
    {
      "pitch_id": "849843:1:3",
      "source_endpoint": "/api/watch/849843/reveal/원래index",
      "response": "해당 reveal JSON 객체"
    }
  ]
}
```

위는 구조 설명이며 그대로 검사에 통과하는 파일이 아니다. `timeline`/`response`에는 문자열
대신 응답 객체를 넣고 선택한 타석의 모든 decision에 reveal을 하나씩 제공한다.
경기 전체 timeline도 받을 수 있지만 우리 도구는 지정된 한 타석만 투영한다.
`index`는 원래 경기 전체 0기반 순서를 유지한다. `pa_id=game_pk:at_bat_number`,
`pitch_id=game_pk:at_bat_number:pitch_number`; 배열 위치로 연결하지 않는다.
`half`는 Top/Bot, 주자는 비트마스크 0..7(1루 1, 2루 2, 3루 4)이다.

확인 기준: 읽기 전용으로 본 SongRoute/pitcheezy의
`demo/ws-2026@9c3018913780cde2d12db522c2a420a6e283db7c`.
`watch_along.py`, `demo_precompute.py`, `tests/test_watch_along.py`를 참고했다.
실제 API timeline schema는 `pitcheezy-watch-along-v1`다.
원본 SSD watch 파일은 game.final 및 decision.actual/we가 있어 거절한다.

## 검증·표시 규칙

- 5MB 이하 UTF-8 JSON만 읽는다. 브라우저와 CLI가 같은 `receiver-contract.js`를 사용한다.
- 중복 키/index, PA·경기 불일치, reveal 키/index/엔드포인트 불일치, 누락 reveal,
  잘못된 숫자·볼카운트·좌우 유형·주자·WE 전후/공격 방향을 거절한다.
- WE 대조 허용 오차는 0.001이다. 값이 null이면 그 산술 비교를 생략한다.
- 사용 필드와 연결 구조를 검증한다. policy/location/전체 구종 law 등 표시하지 않는 부가
  메타데이터의 모델 의미·추정법을 인증하지 않는다. 새 API 필드가 생기면 명시적으로 계약을 갱신한다.
- 상위 추천 비율은 합이 1보다 작아도 그대로 둔다. 구종 선택 비율을 사건 확률로 변환하지 않는다.
- 미지원 추천과 null 좌표는 미지원으로 유지하며 0이나 예시값으로 대체하지 않는다.
- 공개 전에는 현재 투구의 상황·선수·추천만 표시한다. 원시 status/reason, 미래 투구의 상황,
  결과는 표시하지 않는다. 공개 후 다음 투구로 이동할 수 있고, 이동/되감기/숨김은 공개 상태를 초기화한다.
- 투구 후 결과와 우리 미트 관측은 결과 공개 후에만 표시한다. 합성 파일에는 실제 관측을 붙이지 않는다.
- 제공 응답에서 CV 키·투수 이름·타자 이름·실제 구종이 기존 저장 자료와 모두 같아야 미트 x를 표시한다.
  불일치는 표시 보류, 관측 없음은 미연결, 기권은 null이다. 자동 no_pitch 사건도 번호에 포함될 수 있어
  이 대조를 영상 대응 검증으로 취급하지 않는다. 별도 영상 확인이 여전히 필요하다.
- 미트와 공은 측정 평면이 다르므로 차이·수행 점수·책임을 계산하지 않는다.
- 잘못된 파일을 선택하면 이전 추천과 결과도 제거한다. 비동기 읽기 경쟁에서는 최신 선택만 반영한다.

**검사 통과의 한계:** 입력 전체의 원본 바이트 SHA256은 파일 결속 기록이며 제공자가 기재한
모델 식별자/커밋/생성 시각의 진위를 인증하지 않는다. reveal 원응답에는 game_pk/pitch_id가
없으므로 wrapper의 연결 근거도 제공 시점에 확인해야 한다. 잘못된 경기의 reveal을 올바른
메타데이터로 거짓 포장하는 경우를 응답 본문만으로 알아낼 수 없다.
또한 이 도구는 과거 파일을 브라우저에 보유한다. 공개 전 숨김은 표시 규칙이며 파일 내용에
접근하지 못하게 하는 보안 장치나 실시간 미래 정보 차단 서버가 아니다.

## 재현 명령과 결과

```bash
node scripts/check_pitch_receiver.cjs /path/to/received.json
node --test tests/js/pitch_receiver.test.cjs
uv run --frozen python scripts/check_pitch_studio.py
uv run --frozen python scripts/export_pitch_studio.py
```

- Node 테스트 **34 passed**: 재정렬·키 오연결·미래 필드·누락값·공개 상태·원시 상태 제거·CV 대조.
- CLI 정상 합성 파일 통과, game.final 주입 파일 exit 1 거절.
- 브라우저 정상 파일 열기·SHA256 일치, 미지원 투구, 공개/다음 투구 시 결과 제거,
  잘못된 원본 거절과 이전 화면 제거 확인. 390px 모바일 가로 넘침 없음, 콘솔 오류 없음.
- 기존 39키/27좌표/12기권·고정 M3 대조 통과, 체크리스트 가드 4 passed.
- 배포 소스 `648fd43c36b1c28a02277b77fd80b06e97ce336c`, 상태 `succeeded`.

기존 M3·JSONL·장표·리허설 문서와 팀원 저장소는 변경하지 않았다.
수정한 제품은 우리 Site와 그 저장소 사본뿐이다. 신규 검사 명령은 기존 사이트 검사기에도 포함했다.

## 다음 한 단위

사용자/Song이 제공하는 한 타석의 공개용 timeline/reveal 응답과 모델 정보를 받는다.
우리 쪽에서 봉투를 만들고 검증한 뒤, 실제 영상에서 키·자동 호출 사건·공개 시점·좌우를 확인한다.
그 증거가 있기 전까지 E-site5와 Song UI 리허설을 완료로 바꾸지 않는다.
결과 확률/책임/교체 효과 API 개발, 팀원 관전 UI 변경, CV 추가 학습은 이번 단위에 포함하지 않는다.
