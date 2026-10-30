# SITE-zone-nav1 — 타자 기록 존과 전체 경기 동선

## 완료한 사용자 기능

849843의 보유 원본에서 **262구·20타자의 기록 존 높이**를 투구 ID와 선수 ID로 연결했다.
같은 좌표축에 홈플레이트 폭 17인치의 흰 테두리와 9분할을 그린다.
사후 기록을 투구 전 정보처럼 쓰지 않도록 **결과 공개 후에만** 타자 존과 실제 플레이트 통과점을 표시한다.
결과를 다시 숨기거나 투구를 옮기면 둘 다 사라지고 추천만 남는다. 미트 포구 지점·제구 오차·심판 판정은 계산하지 않는다.

- 주 진입은 홈 → 경기 → 71타석·262구 재생이다. 첫 타석 버튼도 이 전체 경기의 첫 구를 연다.
- `?game=849843&pitch=849843%3A2%3A2`처럼 선택 위치를 URL로 보존한다. 새로고침·뒤로/앞으로 이동은 같은 투구를 열고 결과를 숨긴다.
- 과거 `?demo=849843-pa1&pitch=3`은 전체 경기 첫 타석 3구로 연결한다.
- 출처가 다른 옛 3구 수신본은 `?archive=first-pa&pitch=849843%3A1%3A3`로만 구분해 보존한다.
- 파일 입력은 `?mode=file`로 구분한다. 새로고침 후 개인 파일 내용은 복원하지 않고 재선택을 안내한다.
- 홈·경기·안내·재생·연구 페이지에 공통 메뉴를 두고, 모델 근거와 CV 연구 기록을 분리했다.
  연구 기록은 별도39구 관측/2경기86장 평가임을 명시하고 모바일 경기 복귀 링크를 제공한다.
- 연구 탭의 브라우저 이력, 로딩/오류 안내, 현지9/29·한국9/30 날짜를 정리했다.
  320px 화면의 표는 페이지를 밀지 않고 표 내부에서 스크롤한다.

## 자료와 검증 근거

제품 기준 `9ca9fca` → 구현 `7aec165` → 검토 수정 `a33de5b1fc98282ee586b8d5dbc6b0ee089d74c4`.
PR85의 연구/제품 브랜치이며 main 병합과 구분한다. 상세 숫자·배포 식별자는 [영수증](results/site_fullgame_20261030/zone-nav-receipt.json)에 있다.

- 읽은 원본은 로컬 등록부의 `sources/849843/statcast.csv`, `sources/849843/feed.json`뿐이다.
  262개의 게임/타석/투구/투수/타자 ID를 공개 경기 자료와 대조하고 높이가 유한하며 순서가 맞는지 검사했다.
  feed의 소수3자리 높이는 Statcast와 반올림 허용범위 내에서 모두 일치했다.
- Statcast SHA256: `0513145c760741abef96fa295a97c1ba80106dfc0db4301544af782277eefd9b`.
  feed SHA256: `30b82143aff97f2f85c065a7eaec6d574f8a8fe7765789197b766157c4b0fc56`.
- 별도 `game-849843-zones.json`: 42,634bytes, SHA256
  `210fd6bac3a0fe6b89c0c066ed29dd9667f6ee5362d933e17329ebc23771ea8b`.
  기존 경기 JSON·추천·영상 목록은 바이트 불변. 공개 발행 계약/IntentEstimate는 변경하지 않았다.
- 런타임은 JSON 바이트 해시, 원본 해시, 전체 투구 ID와 양쪽 선수 ID를 검사한다.
  존 자료 실패 시 잘못된 경계를 그리지 않고 격자만 표시하며 기본 관전은 유지한다.
- Python85·Node224검사 통과. 중복/누락/다른 선수/다른 투구/비유한 높이/잘못된 URL/선공개를 검사했다.
  사이트 자산·HTML 링크·기존 미디어 SHA 검사도 통과했다.
- 다른 모델 호출 설정 `gpt-6.1-terra`로 고정 변경분 검토.
  7aec165에서 사후 존 선공개와 일부 CSS 캐시 버전 지적 → a33de5b에서 수정 후 PASS.
  검토자가 위치16검사를 별도로 실행했다. 런타임 모델 식별자는 미노출이며 Claude 검토라고 쓰지 않는다.
- Windows Chrome 로컬: PA1→PA2, 타자별 높이 변경, 투구2 선택/새로고침/뒤로/앞으로, 공개/숨김,
  구형 링크, archive, 잘못된999타석의 오류/이전 내용 제거, 연구 탭 이력 확인.
  320px 홈·경기·안내·재생·연구의 가로 넘침 해소, 390px 존 표시 확인.
- 실제 공개 도메인에서도 PA2:2 선택·71타석 목록·새로고침·공개 전 존 숨김/후 표시·모바일390px를 확인했다.
  실제 iPhone/Mac 검사나 262영상 전수 재생은 이번 검사에 포함하지 않았다.

표시 근거: [MLB 홈플레이트 규격](https://www.mlb.com/glossary/rules/field-dimensions) ·
[Baseball Savant CSV 필드 설명](https://baseballsavant.mlb.com/csv-docs).
존은 기록된 기하를 그린 것이며 공 반지름을 고려한 판정기나 투구 전 모델 입력이 아니다.

## 재현

프로젝트 Python 환경과 Node를 PATH에 둔다.

```text
python scripts/export_pitch_studio_zones.py --registry-root <기존 비공개 등록부> --game web/pitch-studio/game-849843.json --out <검사용 별도 경로>/game-849843-zones.json
python scripts/check_pitch_studio.py
python -m pytest tests/test_pitch_studio_zones_export.py tests/test_pitch_studio_media_export.py tests/test_pitch_studio_export.py tests/test_checklist_model.py -q --basetemp outputs/pytest-zone-nav
```

exporter는 입력 SHA를 먼저 확인하며 다른 경기나 평가 잠금 자료를 읽지 않는다.
원본이 바뀌면 임의로 pin을 교체하지 말고 차이를 조사한다.

## 공개 결과와 다음 한 단위

기존 Sites 소스 `207a7cbd0a6d9d75b8b970a242060e4f660f8ca5`, 공개 **v12** 배포 성공.
허용40자산과 기존 hosting manifest 총41파일만 패키징했다. 팀원 코드·별도 Cloudflare 시험 서버·DNS·권한·요금제는 변경하지 않았다.

다음은 전체 경기 관전의 자동 다음 투구 선택 여부·영상 탐색 중 결과 공개 동선 같은 구체 사용자 경험을 점검한다.
영상 제외1구 출처 확인 초안, 형의 채택 관전 화면, 추가 경기, 모델 번들은 별도 조건이다.
CV50a/49c의 기권·보류·평가 잠금과 사람 검토는 유지하며 이번 작업을 미트 식별 개선으로 부르지 않는다.
