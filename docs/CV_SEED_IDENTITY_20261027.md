# CV46 — 초기점의 미트/맨손/불명 구별 검증과 기권

## 먼저 쉬운 말로

- **무엇을 고쳤나.** 지금까지의 초기점(시드)은 "AI가 미트라고 적은 좌표"를 그대로 믿었고, CV42 게이트는 그 좌표가 흔들리지 않는지만 봤다. 좌표가 안정적이어도 그 자리가 맨손(3:1·3:3)이나 디졸브 중 불명 물체(5:1)일 수 있다는 것이 재생 화면에서 지적됐다. 이번 단위는 시드 프레임의 **원본 RGB 21×21 패치만** 보고 `mitt_like / hand_like / unclear`를 내는 결정적 단서를 추가하고, `mitt_like`가 아니면 시드를 **기권(hold)** 하는 별도 후보를 같은 625프레임에서 비교했다.
- **실제 결과.** 기존 첫 적격 시드 10구 중 5구가 `mitt_like`, 5구가 `unclear`(3:1·3:3·4:1·5:1·5:6)였고 `hand_like`는 0구였다. 즉 의심 3사례(3:1·3:3·5:1)는 모두 기권됐지만 "맨손"으로 분류된 것이 아니라 "불명"으로 기권됐다. 반면 AI 개발 관찰에서 미트로 읽힌 4:1·5:6도 `unclear`로 기권됐다(보수적 오기권). CV42 게이트 시드 4구 중 3구(4:2·5:3·5:4)는 `mitt_like`, 5:6은 `unclear`로 기권 → CV46 후보는 3구만 시드한다.
- **확인되지 않은 것.** 단서는 어두운 가죽 미트를 가정한 보수적 개발 게이트이지 미트 식별이 아니다. 밝은 가죽 미트는 기권될 수 있다. 알려진 3사례의 기권은 회귀 확인이지 성공률이 아니며, 임계값은 공개된 피부 규칙과 고정값을 그대로 썼다. Claude·Codex 판독과의 대조는 "AI 합의/미확정"이지 사람 정답이 아니다. 정확도·미트 식별 성공은 미측정이다.

## 착수 전에 고정한 합격 기준

사용자 우선순위 변경(디코딩 캐시보다 초기점 오식별 우선). 작성 Claude Fable 5.1(`claude-fable-5-1`), 브랜치 `claude/cv-seed-identity-1027`, 기준 PR81 `691ac0847ac4fae88c5ed88f31619c10f6615d8c`. [착수 기록](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6434650831)의 합격 기준 ①~⑥과 임계값이 결과 전에 고정됐다. PR67→…→81 의존, main 병합·배포·팀원 코드·Cloudflare·공개 계약·기존 625장/관측/결과/사람 응답/M3 불변. 새 영상·유료·대규모 AI 판독·학습 없음.

원본 시각 대조(인계의 첫 작업 A/B): manifest의 원본은 MLB FORGE 원격 mp4(9,340초)이며 로컬 보관본이 없다. 프로젝트 outputs 폴더와 외장 D:의 제한 검색에서 248.7485~452.9525초 구간의 원본·시간 보존 자료는 없었다(로컬 클립은 다른 경기 849843 또는 135~245초 구간). 이를 B로 한 번 기록하고 반복하지 않는다.

## 1. 단서 — 결과 전 고정한 규칙 (`intent/mitt_seed_identity.py`)

입력은 시드 프레임의 원본 RGB(1280×720)와 시드 점(소스 픽셀, half-up 반올림)뿐이다. 과거·미래 프레임, 관측, 추적 결과, 결과는 들어가지 않는다(검사로 고정: 패치 밖 화소 변경은 출력을 바꾸지 않음).

| 항목 | 값 | 출처 |
|---|---|---|
| 패치 | 21×21 (추적기 템플릿과 동일) | 기존 |
| 피부 화소 규칙 | R>95, G>40, B>20, max−min>15, \|R−G\|>15, R>G, R>B | Kovac et al. 2003 공개 규칙 |
| `hand_like` | 피부 비율 ≥ 0.50 | 고정 |
| `unclear/low_texture` | 휘도(BT.601) 표준편차 < 0.03 | 추적기 `min_texture` 재사용 |
| `mitt_like` | 피부 비율 ≤ 0.10 이고 평균 휘도 ≤ 110/255 | 고정(어두운 가죽 가정) |
| 그 외 | `unclear/mixed`; 경계는 `unclear/patch_border`(통계 없음) | — |

`IdentityParams` digest `cdd2839f0fd42efc3f28a04e9cc625e1aa4866dfa37b307d12ddba388bcf9354`. `accepts()`는 `mitt_like`만 시드로 허용한다. 모든 출력은 `mitt_identity: "unverified"`다.

## 2. 파일럿 (`intent/mitt_seed_identity_pilot.py`)

CV42와 같은 고정 입력(manifest `58cb57c9…`, pilot `6e95c402…`, answers `395679bf…`, CV37b 기준선 625행 `9b564920…`)을 해시로 대조하고, 기준선 625행 전 필드 재현을 먼저 확인한다. 그 뒤 (a) 기존 첫 적격 시드 10구 (b) CV42 게이트 시드(`mitt_seed_pilot.choose`, 결정적)에 단서를 적용하고, 세 후보를 같은 625프레임에서 재생한다: `gate_cv42`(CV42 재현), `cv46_gate_plus_cue`(게이트 시드 중 `mitt_like`만), `first_usable_plus_cue`(첫 적격 시드 중 `mitt_like`만). 보류 사유를 투구별로 남기고, CV46 후보는 접두 불변(라벨 전 행 비교)과 일관성 위반 7종을 검사한다. 시드 crop(비공개, 표식 없음)은 모든 검사 통과 뒤에만 저장한다. `merge` 하위 명령은 Claude·Codex 판독을 보고서 사본에 붙이며, 판독 항목은 `reading/evidence/model`만 허용하고 경로 구분자를 거부한다. 공개 사본은 시드 좌표·패치 상자·crop 참조를 제거한다.

## 3. 같은 625프레임 결과 (`outputs/cv_mitt_seed_identity_20261027_v2`, Git 제외)

[공개 보고](results/cv_seed_identity_20261027/report_public_v1.json). 기준선 625행 전 필드 재현, 입력 668파일 SHA 보존, 접두 불변 310행, 일관성 위반 7종 모두 0.

| 투구 | 첫 적격 시드(프레임) 단서 | 피부비율 / 평균휘도 / 질감 | CV42 게이트 시드 단서 | CV46 시드 | CV37b AI 관찰(참고, 정답 아님) |
|---|---|---|---|---|---|
| 3:1 | 14946 **unclear/mixed** | 0.39 / 109 / 0.179 | 게이트 보류 | 없음 | not_mitt(맨손) |
| 3:2 | 16262 mitt_like | 0.05 / 71 / 0.166 | 게이트 보류 | 없음 | likely_mitt |
| 3:3 | 17233 **unclear/mixed** | 0.20 / 117 / 0.264 | 게이트 보류 | 없음 | not_mitt(맨손) |
| 4:1 | 19585 **unclear/mixed** | 0.28 / 70 / 0.096 | 게이트 보류 | 없음 | likely_mitt |
| 4:2 | 20470 mitt_like | 0.02 / 32 / 0.078 | 20494 mitt_like | **시드** | likely_mitt |
| 5:1 | 21342 **unclear/mixed** | 0.38 / 108 / 0.099 | 게이트 보류 | 없음 | not_mitt(디졸브) |
| 5:2 | 22118 mitt_like | 0.01 / 38 / 0.056 | 게이트 보류 | 없음 | likely_mitt |
| 5:3 | 23212 mitt_like | 0.00 / 33 / 0.060 | 23236 mitt_like | **시드** | likely_mitt |
| 5:4 | 24396 mitt_like | 0.00 / 31 / 0.045 | 24420 mitt_like | **시드** | likely_mitt |
| 5:6 | 26778 **unclear/mixed** | 0.15 / 45 / 0.094 | 26802 unclear/mixed | 기권 | likely_mitt |

| 후보 | 시드 수 | 상태(625행) | 재획득 | 정지 사건 |
|---|---|---|---|---|
| 기준선(첫 적격 시드, CV37b) | 10 | tracking 178 · search 26 · candidate 21 · lost 318 · unseeded 82 | 16 | 13 |
| CV42 게이트 | 4 | tracking 77 · search 12 · candidate 4 · lost 139 · unseeded 393 | 4 | 5 |
| **CV46 게이트+단서** | 3 | tracking 71 · search 8 · candidate 4 · lost 90 · unseeded 452 | 4 | 4 |
| 첫 적격 시드+단서 | 5 | tracking 100 · search 14 · candidate 11 · lost 158 · unseeded 342 | 8 | 6 |

읽는 법:
- 의심 3사례(3:1·3:3·5:1)는 피부 비율 0.20~0.39로 `hand_like` 문턱(0.50)에 못 미쳐 **`unclear`로 기권**됐다. 손 패치에는 그림자·배경·손가락 사이 틈이 섞여 공개 규칙의 피부 비율이 절반을 넘지 않는다. 기권이라는 결과는 맞지만 "맨손" 판정은 아니며, 이를 손 식별 성공으로 쓰지 않는다.
- 4:1(붉은 표식이 있는 어두운 글러브, 피부 0.28)·5:6(주황 손목 보호대 옆의 어두운 글러브, 피부 0.13~0.15)은 AI 관찰상 미트인데도 `unclear`로 기권됐다. 피부 규칙이 붉은/주황 계열 반사광을 피부로 세는 한계다. 보수적 기권이며, 이 두 사례에 맞춰 임계값을 바꾸지 않았다.
- `mitt_like` 5구는 모두 평균 휘도 31~71, 피부 비율 ≤0.05의 어두운 가죽이다. 이 판정도 "어두운 질감 있는 물체"일 뿐 미트 식별이 아니다.
- CV46 후보는 CV42보다 시드 1구(5:6) 적고 추적 행 77→71이다. 출력이 줄어든 보수적 후보이며 정확도 개선이 아니다.

## 4. AI 개발 판독 대조 (사람 정답 아님)

14개 시드 crop(첫 적격 10 + 게이트 4; 81×81px 3배 확대, 표식 없음)을 Claude(이 세션, 접촉 사진의 청록 상자로 21px 패치 위치 표시)와 Codex CLI(`gpt-6-astra`, 이미지 입력, 5·5·4장 묶음)가 각각 `mitt/hand/unclear`로 읽었다. 단서·Claude·Codex 셋이 같을 때만 `ai_agreement`, 아니면 `undetermined`다. 결과 표는 [판독 병합](results/cv_seed_identity_20261027/readings_merged_public_v1.json)에 있다.

| 투구 | 시드 | 프레임 | 단서 | Claude | Codex | 판정 |
|---|---|---|---|---|---|---|
| 3:1 | baseline | 14946 | unclear | hand | unclear | 미확정 |
| 3:2 | baseline | 16262 | mitt | mitt | mitt | AI 합의: mitt |
| 3:3 | baseline | 17233 | unclear | hand | hand | 미확정 |
| 4:1 | baseline | 19585 | unclear | mitt | unclear | 미확정 |
| 4:2 | baseline | 20470 | mitt | mitt | mitt | AI 합의: mitt |
| 4:2 | gate | 20494 | mitt | mitt | 미실행(한도) | 미확정 |
| 5:1 | baseline | 21342 | unclear | unclear | 미실행(한도) | 미확정 |
| 5:2 | baseline | 22118 | mitt | mitt | 미실행(한도) | 미확정 |
| 5:3 | baseline | 23212 | mitt | mitt | 미실행(한도) | 미확정 |
| 5:3 | gate | 23236 | mitt | mitt | 미실행(한도) | 미확정 |
| 5:4 | baseline | 24396 | mitt | mitt | 미실행(한도) | 미확정 |
| 5:4 | gate | 24420 | mitt | mitt | 미실행(한도) | 미확정 |
| 5:6 | baseline | 26778 | unclear | mitt | 미실행(한도) | 미확정 |
| 5:6 | gate | 26802 | unclear | mitt | 미실행(한도) | 미확정 |

요약: 판독 대상 14개 시드 중 AI 합의 2·미확정 12. Codex 판독은 첫 묶음 5개 시드만 받았고 나머지 9개는 ChatGPT 사용 한도(2026-11-02 초기화)로 미실행이라 미확정으로 남긴다(재시도하지 않음). 합의 2건(3:2·4:2 첫 적격 시드)도 "세 AI 출처가 같은 말을 했다"는 뜻일 뿐 미트 식별이 아니다. 3:1은 단서 unclear·Claude hand·Codex unclear, 3:3은 단서 unclear·Claude hand·Codex hand, 4:1은 단서 unclear·Claude mitt·Codex unclear로 서로 달라 미확정이다.

## 5. 검사·검토

- 새 검사 `tests/test_mitt_seed_identity.py`(8): 기록된 개발 색상(맨손 평균 RGB≈(188,152,144) → hand_like, 인접 어두운 물체≈(84,81,96) → mitt_like; AI 관찰 수치이지 정답 아님), 저질감·혼합·밝은 패치의 unclear, 경계 기권, 패치 밖 무관·half-up 반올림, 형식 오류 거부, 파라미터 검증·digest, 피부 규칙·휘도 정의. `tests/test_mitt_seed_identity_pilot.py`(6): 합성 3구(어두운 질감/피부색/평탄) 재생에서 보류 사유·분모·공개 사본 제거·접두 불변(게이트 시드가 반 접두 안에 오도록 12프레임)·실패 시 출력 폴더 없음, 고정 해시 불일치·기존 폴더 거부, 변경 프레임 거부, 판독 병합의 합의/미확정·허용 키·경로 구분자·null·반복 병합 거부.
- 관련 8파일 129 passed, 1 warning, 린트 `check_project.py --lint-only` 통과(새 4파일을 필수 목록에 추가). 실행 결과와 SHA는 [검증](results/cv_seed_identity_20261027/verification_v1.json).
- 다른 모델 검토: 로컬 Codex CLI 0.162.0-alpha.2 `gpt-6-astra`(ChatGPT 로그인, 읽기 전용 샌드박스, diff stdin, 검토자 명령 실행 없음). 시도 a(28,666 토큰): P2 2건·P3 1건 — 병합 판독이 공개 제거를 우회, 반복 병합 집계 오류, 잘못된 판독 객체를 누락으로 처리 → 허용 키 목록·반복 병합 거부·판독 객체 검증으로 수리. 실제 재생에서 드러난 접두 검사의 라벨 불일치도 수리(라벨 전 행 비교, 검사 통과 뒤 crop 저장, 픽스처 12프레임). 시도 b(18,100 토큰): 2·4 해결, 1·3은 명시적 null 허용으로 미해결 → 존재하는 판독 키는 dict 필수·evidence/model은 존재 시 문자열 필수로 수리. 시도 c(15,622 토큰)는 작성자의 수리 패치가 앵커 불일치로 적용되지 않은 채 보낸 옛 본문을 검토해 "미해결"로 답했고(정확한 판정), 정확한 편집으로 다시 적용한 뒤 시도 d(15,051 토큰)가 두 항목 해결·새 결함 없음으로 답했다. [영수증](results/cv_seed_identity_20261027/cross_review_v1.json).

## 6. 한계

- 단서는 어두운 가죽 가정의 보수적 게이트다. 밝은/탄색 미트는 기권되고, 붉은 표식·주황 반사광이 있는 미트도 기권될 수 있다(4:1·5:6). 반대로 어둡고 질감 있는 비미트 물체는 통과할 수 있다.
- 의심 3사례가 `hand_like`가 아닌 `unclear`로 기권된 것은 규칙의 한계를 보여 준다. 손 판정에는 패치 밖 문맥이나 별도 판독이 필요하며 이번 범위 밖이다.
- AI 판독 합의는 사람 정답·독립 정확도가 아니다. 사람 검토(CV35/36)와 새 경기 평가는 그대로 남는다.
- 기존 PatchTracker·SeedGate·기준선·CV42 출력은 바꾸지 않았다. 원본 667파일·기준선 625행·AI 관측·사람 응답·M3 불변.

## 7. 재현

```sh
python -m intent.mitt_seed_identity_pilot run --bundle <bundle_v1> --pilot <pilot_v1> --baseline <CV37b records_candidate_cpu.json> --manifest-sha256 58cb57c9dbd542ca60db84f8f1e2242867e4680c15e1914a5ca1352ec1bcf87a --pilot-sha256 6e95c402504bd613c474f16cb7356c6f320a16177dd5831b9378972b3b002594 --answers-sha256 395679bfa6c5fb9efcc069bd8482ab6cdd6cde1049cc52e81d18f6c070d095ba --baseline-sha256 9b564920883be8fbacd5e621713ece66b968dd311d1538d04dfabdff6088898c --out <새 비공개 폴더>
python -m intent.mitt_seed_identity_pilot merge --report <새 폴더>/report.json --readings <판독 JSON> --out <새 폴더>/readings_merged.json
python -m pytest -q tests/test_mitt_seed_identity.py tests/test_mitt_seed_identity_pilot.py
python scripts/check_project.py --lint-only
```
