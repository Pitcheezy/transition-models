# SITE-exhibit1 — 전시 관전 동선과 시각 안내 개선

2026-10-30. 기존 Pitcheezy 공개 사이트에 홈·경기 선택·이용 안내·관전 개선을 반영했다.
최종 제품 `b0ab6e55468a0b826ce3a4dff998921a1b1383cc` / `codex/site-first-1029` / PR85. **main 병합과 Sites 공개는 별개**다.
현재 작업·담당은 [CHECKLIST](../CHECKLIST.md), 상세 검증·56자산 해시는 [영수증](results/site_fullgame_20261030/exhibition-polish-receipt.json)을 따른다.

## 완료한 사용자 기능

- 기존 홈의 실제 경기 하이라이트를 유지하고, 주 동선의 미검토 미트 오버레이를 첫 타석 관전 링크로 교체했다. 영상 실패·동작 줄이기 때는 공식 경기 정지 화면과 재생 버튼을 제공한다.
- 컵스·파드리스·필리스·브레이브스·레이스의 공식 팀 로고 5종을 홈·경기·관전·상세 분석에 연결했다. 현재 관전 가능한 경기와 CV 연구 자료를 구분한다.
- 선택·추천·실제 비교·근거를 설명하는 SVG 4종을 홈과 이용 안내에 추가했다. 실제 결과를 꾸며낸 그림이 아닌 기능 안내 도식으로 표시한다.
- 경기·안내에서 첫 타석으로 바로 진입하고, 관전에서는 영상·비교·투구 리본을 먼저 보여준다. 긴 조건·용어·선수 검색·선택 연구 기능은 접어서 읽는다.
- 핵심 경기부터 표시하고 부가 자료는 제한 시간 안에서 읽는다. 실패 안내·수동 재시도·잘못된 주소의 첫 공 복구·키보드 포커스·탐색바 성능을 개선했다.
- 원래 받은 71타석·262구, 추천246/미지원16, 영상261구의 자료와 공개 시점 규칙은 보존했다. 미트와 공의 물리적 제구 오차·사람 대비 정확도를 새로 주장하지 않는다.

## 검증 근거

- 관련 Node **257/257 통과**(관전68·홈7 포함). 신규 관전9건은 수정 전9실패→수정 후9통과다.
- 사이트 정적 검사: 원본 미디어 SHA·허용 파일·HTML 참조·기존 예시 격리 PASS. 체크리스트 **8/8 통과**.
- 첫 체크리스트 실행은 임시 폴더 접근 권한 때문에 setup 실패했으며, 작업 폴더 안의 `--basetemp`로 8개 모두 통과했다. 기능 실패로 숨기거나 최초 실행을 성공으로 기록하지 않는다.
- Chrome 1440/800/390/320px. 주요8페이지 모바일 DOM 확인, 홈320px 넘침 수정 후 해소, 팀 로고·설명 그림 로드 확인. 실제 스마트폰 기기 검수는 아니다.
- 실제 영상 재생·종료 결과 공개·0초 되감기 숨김, 잘못된 주소→첫 공, 키보드 리본2구 선택 후 포커스 유지 확인. 관전 placeholder 중 src가 없는 숨김 이미지들은 깨진 자산으로 계산하지 않는다.
- 최초 고정본 `f0fba262`의 새 SVG9개 XML·스크립트 없음·내부참조77개 누락0·기존 정의/평가10항목 원문 보존을 별도 읽기 감사했다.

```text
node --test web/pitch-studio-tests/*.test.cjs tests/js/pitch_receiver*.test.cjs tests/js/pitch_home.test.cjs
python scripts/check_pitch_studio.py
python -m pytest tests/test_checklist_model.py -q --basetemp outputs/site_pa_sequence_20261030/pytest-polish-final
```

## 실제 Claude 교차검토

| 단계 | 런타임 보고 모델 | 결과 | 소요 |
| --- | --- | --- | --- |
| design | claude-fable-5-1 | completed; design findings | 54.74초 |
| final | claude-fable-5-1 | conditional approval; six findings | 275.44초 |
| recheck | claude-fable-5-1 | APPROVE | 222.33초 |

최초 고정본 `f0fba262`의 지적6건을 최종 제품에 반영했다. 수정본 첫 호출은 DNS ENOTFOUND로 실패했으며 승인으로 세지 않았다. 재시도의 실제 응답만 최종 검토 근거로 사용한다. 모델명은 CLI 응답의 modelUsage이며 같은 모델의 다른 세션을 독립 모델로 세지 않는다.

## 공개 결과

- Sites 소스: `f8078b0eca4cd2e3ce5e20662d46a58069866386`
- 공개 버전: **v19**, 배포 상태 `succeeded`
- 기존 [Pitcheezy](https://pitcheezy.com)에 공개. 56허용 자산+기존 hosting manifest, 현재 공개 범위 유지.
- 공개 주소에서 홈 새 그림·팀 로고·관전 자료/영상 로드 확인. 배포 식별자·아카이브 SHA는 영수증에 기록한다.
- 팀원 저장소·API·별도 Cloudflare 시험 설정·계약·평가 잠금·보류한 사람 응답은 변경하지 않았다.

### 로고·설명 그림의 고정 바이트

아래 경로는 모두 `web/pitch-studio/media/` 기준이다. 로고는 작업에 사용한 MLB 원본 주소를 기록했고, 해시는 이 문서 작성 시 실제 로컬 파일 바이트에서 계산했다. 9개 해시는 `f0fba262` 감사 때 계산한 값과 같다. 이 문서 작성 중 원격 파일을 다시 받거나 원격 바이트를 재대조하지 않았다.

| 파일 | 출처·용도 | SHA-256 |
| --- | --- | --- |
| `team-chc.svg` | Chicago Cubs · [MLB 원본](https://www.mlbstatic.com/team-logos/112.svg) | `8fe99678c053859b50adbbe769aade0011ed6b2349962a9963dcc0b6db162aef` |
| `team-sd.svg` | San Diego Padres · [MLB 원본](https://www.mlbstatic.com/team-logos/135.svg) | `c0d5f92ef4a58f097c74aedebb9fd1ff4270217d45b75ef7aa6eeded115131da` |
| `team-phi.svg` | Philadelphia Phillies · [MLB 원본](https://www.mlbstatic.com/team-logos/143.svg) | `465da43739de56c09d5f8ec3328be11e9318f53959cc05979d3ab3d0a547a3bb` |
| `team-atl.svg` | Atlanta Braves · [MLB 원본](https://www.mlbstatic.com/team-logos/144.svg) | `11162237c379e6e6e54916ee4eebe4407961b4d37293b71b21868077d1bead0d` |
| `team-tb.svg` | Tampa Bay Rays · [MLB 원본](https://www.mlbstatic.com/team-logos/139.svg) | `b50fd02140a8fe66e57eb5c421fc6847a52abfbc7469bc3099a49d1e09ff77fc` |
| `feature-select.svg` | 이 저장소에서 제작한 투구 선택 안내 도식 | `15693bd4150298704d12dc557c2f5659edd63ef686973dd030057eeef9d98ae7` |
| `feature-recommend.svg` | 이 저장소에서 제작한 추천 읽기 안내 도식 | `5b6391c5417450f820da633ae6ff94c7841e9dad66af9083776e7dc56dca7cc6` |
| `feature-compare.svg` | 이 저장소에서 제작한 추천·실제 위치 비교 도식 | `8b70e08c9395a5655b8e2163fe0b0dc9a62dda2593d00c6411a1ac49385e9c3e` |
| `feature-evidence.svg` | 이 저장소에서 제작한 예측 평가·추천 효과 구분 도식 | `f67fd465d4eae84371d5f0d6c9e86bda2f9e62fd678ba02ef49383594626a090` |

화면의 출처 안내는 `guide.html#sources`에 있다. 팀 로고는 구단 식별용이며, Pitcheezy가 MLB와 제휴한 공식 서비스라는 뜻이 아니다. 파일 해시는 파일 식별 근거이지 출처 인증이나 이용 권한의 증명이 아니다.


## 남은 장애물 / 다음 한 단위

849843 전체 중계 원본과 같은 시간축의 투구별 시각표는 아직 확보하지 못했다. 현재는 개별 클립 이어보기이고 경기 탐색바는 투구 순서다. 전체 영상이 있으면 구간 탐색→추천→도착/결과 전환을 연결할 수 있지만, 클립 길이 합산으로 전체 중계 시각표를 만들지 않는다.

첫3구는 AI 프레임 검토의 도착 구간 상한, 나머지는 클립 종료 기준이다. 정확한 포구 한 프레임·전 경기 정밀 동기화·미트 높이/의도·제구 오차는 미완료다. 다음은 사용자 시연 확인과 전체 중계 원본/시간표 확보이며, 새 CV 판독은 PLAN의 범위로 별도 진행한다.
