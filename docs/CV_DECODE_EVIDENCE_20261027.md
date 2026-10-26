# CV45 — 새 영상 추출의 시각 근거 보존

## 문제와 범위

[착수·합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6424552029). 기존 `mitt_dev_bundle`은 프레임 선택을 디코더 로그로 확인하지만 성공 로그를 버리고, 시각을 고정 FPS에서 다시 계산했다. 새 추출에서 실제 time base·PTS와 선택 JPEG의 결속을 남기는 선택 옵션을 추가한다. 이미 저장된 625장에 원본 로그를 만들어 붙이지 않는다.

기존 개발 자료의 이미지 시각 범위는248.7485~452.9525초다. 확인 가능한 로컬 `broadcast_context.mp4`의 기존 framemd5는135.001533~244.99475초이므로 해당625장의 직접 디코딩 대조를 대신할 수 없다. 이 한계를 숨기거나 AI 교차검토로 독립 시각 검증을 대체하지 않는다.

## 합격 기준

- 새 추출의 선택 옵션으로만 기록하며 기존 기본 동작과 자료를 보존한다.
- 실제 필터 입력 time base·PTS·유리수 시각, 선택 이미지 상대경로·SHA·바이트, 버전·코드SHA·시도 상태를 결속한다.
- 실패·재시도·timeout 근거를 남기고 주소·개인 경로를 기록하지 않는다. 디코더 전체 원문이 아니라 허용된 숫자 필드로 구성한 필터 로그다.
- 누락/다른 time base, 순서·개수 불일치는 증거 성공으로 기록하지 않는다.
- 같은 추출에서 얻은 근거이며 `independent_decoded_pts_verified=false`다. 별도 원본 디코딩과 사람 평가를 완료한 것이 아니다.
- 로컬에서 만든 짧은 합성 영상으로 실제 FFmpeg 동작을 확인하고, 고정 소스를 Claude Fable이 검토한다. 새 MLB 영상 다운로드·모델·OCR 실행은 하지 않는다.

## 결과

구현 `5e10e9e`, 수리 `a669e48`. [합성 실측 영수증](results/cv_decode_evidence_20261027/verification_v1.json)과 [실제 Claude Fable 고정 검토](results/cv_decode_evidence_20261027/cross_review_v1.json)를 보존했다.

- `python -m intent.mitt_dev_bundle extract --out outputs/<새폴더> --save-decode-evidence`가 선택 옵션이다. 이 명령은 기존 수집 경로를 실행하므로 이번 검증에서는 호출하지 않았고, `extract_one`에 로컬 합성 파일을 직접 전달했다.
- 3초·128×96·60000/1001fps·time base1/60000 합성 MP4180프레임을 만들었다. 실제FFmpeg8.0이138프레임(원본번호18~155)을 디코딩하고9장을 선택했다. 출력JPEG9개 전부 SHA·크기·PTS 유리수와 결속 확인, 시도1회0.23초. 이 속도는 실제경기 처리량이 아니다.
- `decode_evidence/pa1_p1/attempt_01.json` 형태의 별도 증거를 보존한다. 최종 합성 증거SHA `58cd0a3e686e9c49d066e00ddbd354c003303b1c7cc7aa65069d6a1ce11fac34`.
- 모듈17·체크리스트 포함25검사 통과, Ruff194경로 통과. 기본 출력 필드·timeout 전파 호환, 재시도별 보존, 잘못된 설정/순서/개수, 주소·경로 비노출을 확인했다.
- Claude `claude-fable-5-1` 초기134.58초·수정재검토42.84초, 모두 `approve_with_nits`. 실패 원인 미기록은 허용목록 단서/비showinfo행수로 보완했고, 출력 경로는 아직 옮기기 전의 예정 경로라고 명시했다. 실제 최종 존재·SHA는 추출 완료 기록과 별도로 확인한다.

선택 옵션은 앞뒤 여유 구간까지 연속성을 검사해 기본 모드의 창 내부 검사보다 엄격하다. 실패 단서는 키워드 기반이며 확인된 근본 원인이 아니다. 비showinfo행수는 성공/실패 모두 기록한다. 재검토의 `re` import 누락 가정은 기존 import로, `Parsed_showinfo` 가정은 실제 사용한 명명 필터 `showinfo@all/kept`와 합성 실행 로그로 확인해 기각했다. 로그 원문을 보존하지 않아 모든 FFmpeg 오류를 분류하지는 못한다.

기존625장·OCR·AI 관측·사람 응답·M3·다른 작업 폴더는 변경하지 않았다. 이 기록은 새 추출 과정의 증거이며 원영상의 별도 재디코딩 검증·미트 정확도·사람 평가가 아니다. 팀원·Cloudflare·공개사이트·main/운영 배포는 변경하지 않았다.
