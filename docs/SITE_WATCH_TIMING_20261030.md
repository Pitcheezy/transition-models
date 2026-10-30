# SITE-watch2 — 공 도착 표시와 맞춤 재생바

실제 영상에서 공 도착 구간을 확인한 첫 타석3구는 그 구간 상한부터 실제 위치를 표시한다.
구종·판정·최종 타구 결과는 클립 종료 뒤 공개한다. 나머지258개 연결 클립은 종료 기준을 유지한다.
영상261구/자료262구의 기존 구분은 그대로다. 전체 경기의 정밀 포구 동기화 완료가 아니다.

## 근거와 화면 동작

- 1구 포구 상한3.450855556초, 2구3.466977778초. 3구3.384211111초는 파울팁의
  배트 접촉/포구를 분리할 수 없어 `plate_arrival`로만 기록했다.
- MP4 실제 PTS/time_base를 사용하며 첫 비디오 프레임의 오프셋을 빼지 않는다.
  매체 시각에 맞춰 표시하고 지원 브라우저에서는 requestVideoFrameCallback을 사용한다.
- 두 AI의 개발용 시각 검토다. 초기 너무 이른 추정은 철회하고 늦은 구간을 재확인했다.
  [근거 기록](results/site_fullgame_20261030/watch-timing-evidence.json)에 수정 전 가설과 한계를 보존했다.
  사람 평가·정확한 물리적 충돌 시점의 정답·자동 검출기 결과가 아니다.
- 라임색 진행바·주황색 도착 마커·±3초·속도·음소거·전체화면을 추가했다.
  탐색/되감기/투구 전환은 이전 결과를 지우며, 해당 시각을 지난 경우에만 현재 점을 표시한다.
- 타이밍 파일은 고정 SHA, 투구 ID, play ID, 기존 영상 SHA에 결속한다. 실패하면 종료 기준으로 돌아간다.
  점의 좌표는 기존 실제 플레이트 통과 위치이며 새 미트/포구 좌표나 제구 오차가 아니다.

## 검증과 배포

기준446d990 → 제품58baee4414a2ca7eb4106b93f1440c32fa52e5c4, PR85(main 미통합).
Node318(관전32·타이밍23 포함), 체크리스트8, 링크/기존 미디어 SHA 검사 통과.
다른 모델 고정 읽기 검토 PASS: 호출 설정 gpt-6.1-terra, 실제 런타임 ID 미노출.
Chrome 실제 영상 도착 전후·탐색·결과 보류와390/320px 넘침 없음 확인. 실제 모바일 기기 검사는 별도다.

기존 공개 사이트 v15, Sites 소스e713e37c7f7f9e7d182a46eec0bde9914d0c73bf,46자산+hosting47파일.
팀원 저장소·별도 Cloudflare 서버·DNS·비용·접근 권한은 변경하지 않았다.
[검사·배포 영수증](results/site_fullgame_20261030/watch-timing-receipt.json)을 따른다.

```text
python scripts/check_pitch_studio.py
node --test web/pitch-studio-tests/watch.test.cjs web/pitch-studio-tests/watch-timing.test.cjs
python -m pytest tests/test_checklist_model.py -q --basetemp outputs/site_pa_sequence_20261030/pytest-watch2
```

다음은 미확인 클립의 사건 시각 근거 확장이다. 현재 표시 규칙을 전 경기에서 확인한 것으로 쓰지 않는다.
범위는 PLAN의 첫5타석 조사 경계 안에서 시작하며, 불명확한 장면은 종료 기준을 유지한다.
