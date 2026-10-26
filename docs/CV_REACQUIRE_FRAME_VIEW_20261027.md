# CV-41b — 같은 프레임의 기존 추적·재탐색·OCR 비교

## 목적과 경계

Claude가 완료한 CV37b의 저장 재탐색 결과를 CV39c의 OCR 재생 화면에 연결했다.
기준은 PR74 `0112f018e7485a0fc35c12575b990345f3239c4b`, 별도 연구 브랜치는
`codex/cv-reacquire-view-1027`이다. [착수·합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6422121130).

사용자는 공동시험 준비·인계 결함을 정리한 뒤 CV를 계속하라고 요청했다. 운영 수정은 별도
[PR76](https://github.com/Pitcheezy/transition-models/pull/76)에 보존했다. 회수 순서, 후속 세 요청의
403/401/503 배분, 준비 시점과 실제 시험·종료 결과를 구별했다. 취소됐던 WebKit 설치 작업은
한 번 재실행하여 성공했다. 이는 공동시험의 STOPPED 판정을 바꾸지 않는다. 누락 요청 두 건의
원인과 해당 회차 401/503 실측은 아직 미확인이다. 이 연구 작업은 서버를 변경하지 않았다.

## 구현

- `intent/mitt_reacquire_view.py`: 고정 OCR 팩 영수증 → 모든 파일의 크기/SHA → 기준선/재탐색 보고서·625행 → 각 프레임의 투구 키/번호/자료 시각/이미지 SHA를 대조한다. 선택기만 저장 행에 적용하여 현재·과거 멈춤 판정의 일관성을 검사한다. 추적 알고리즘이나 OCR 엔진은 실행하지 않는다.
- 기존 frame의 `selection`은 보존하고 `reacquire.tracking`, `reacquire.selection`을 추가한다. 별도 `comparison_schema`는 개발 뷰어 내부 형식이며 공개 발행 계약·IntentEstimate 변경이 아니다.
- PA3의 같은 203 JPEG에서 기존 추적/제한된 재탐색을 전환한다. 전환할 때 재생을 멈추고 프레임 번호를 유지한다. 현재 구간 번호와 추적/멈춤 판정 이유를 함께 표시한다.
- 탐색·미확정 후보·소실 중에는 현재 점을 표시하지 않는다. 다음 프레임의 연속 확인을 통과한 뒤 저장 결과가 추적으로 바뀌어야 점을 표시한다. 과거 멈춤 사건은 그 사건의 이미지에만 남는다.
- 첫 투구의 저장 OCR74행은 그대로이고 나머지 두 투구는 관측 자료 없음이다. 이름 보간·교정·선수 교체 추론은 하지 않는다.
- 기존 비교 기능 없는 팩도 계속 실행할 수 있다. 새 비교 선택은 숨겨진다. 새 Node 회귀를 기존 CI에 포함했다.

## 읽는 순서

첫 투구의 9번째 장(원본14958)은 미확정 재탐색 후보라 점이 없다. 다음 10번째 장(14964)은 구간2로 확인된 패치만 나타난다. 16번째 장(15000)은 구간3의 기하학적 멈춤 후보다. 21번째 장(15030)은 탐색 소진으로 현재 점을 지우고 과거 사건은 별도 이미지에만 표시한다.

3구의 원본17413에서는 추적의 `patch_continuity`와 멈춤 판정의 `motion_restart`가 함께 보인다. 패치가 이어져도 멈춤 후보는 사라질 수 있음을 구별하기 위해서다. 원본17431에서는 새 구간2가 시작하므로 멈춤 조건도 다시 채운다.

## 재현

```sh
python -m intent.mitt_reacquire_view --pack <고정 OCR 팩> --pack-receipt-sha256 <전체 SHA> --candidate-report <CV37b report_v1.json> --candidate-report-sha256 <전체 SHA> --candidate-records <records_candidate_cpu.json> --baseline-records <records_cpu.json> --ocr-observations <observations.json> --out <새 비공개 폴더>
python -m pytest -q tests/test_mitt_reacquire_view.py tests/test_mitt_track_view.py tests/test_mitt_ocr_view.py
node --test tests/test_reacquire_frame_view_ui.cjs tests/test_track_frame_view_ui.cjs tests/test_ocr_frame_view_ui.cjs
python scripts/check_project.py --lint-only
python -m http.server 8768 --bind 127.0.0.1 --directory <새 비공개 폴더>
```

`8768`은 예시이며 다른 서버가 쓰면 빈 포트를 사용한다. 비공개 영상이 든 팩을 Git이나 공개 호스팅에 올리지 않는다. 입력 경로는 본인 로컬 저장 위치를 지정한다.

## 검증과 한계

**다른 모델 검토·수리·수정 재검토 완료.** 실제 `claude-fable-5-1`의 UI 검토128.52초·빌더 검토77.02초·고정 수리 `0f29502` 재검토112.86초에서 최종 답변을 받았다. 마지막 판정은 PASS이며 남은 낮은 우선순위 견고성 참고사항을 별도 기록했다. [진단·최종 검토](results/cv_reacquire_view_20261027/cross_review_v2.json).

과거600/300초 시도는 진행 로그가 없어 정확한 원인이 미확정이다. 현재 로그인과 짧은 동일 옵션 요청은 정상이고, 큰 high 검토는 분석 이벤트가 계속되는 중240초 제한에 도달했다. 실제 실행 파일을 직접 호출하고 소스를 나눈 medium 검토로 해결했다. 도구의 전역 설정·승인·격리는 바꾸지 않았다. 과거 실패 [영수증](results/cv_reacquire_view_20261027/review_attempts_v1.json)은 보존한다.

입력의 UTF8·이미지 디코딩 오류·기준선 보존을 검사하고, 화면에서도 새 비교 자료의 크기·투구/프레임/시각/SHA 연결·OCR 비교 관계를 확인한다. 빈 자료/잘못된 기록 좌표/화면 처리 실패를 구별한다. Python37·Node40·린트186경로 통과. 새 v2 팩208파일 검증, payload/OCR/203JPEG205파일 바이트 불변, 실제 JS 소비자에서 OCR74행 수용·129장 자료 없음·불일치0. Windows에서 재탐색/기존 방식 같은 프레임 전환·다음 투구 초기화를 재확인했다. [수리 후 영수증](results/cv_reacquire_view_20261027/verification_v2.json). 원 v1 팩과 아래 전체 시나리오 검증 이력은 보존한다. PR77은 연구 의존 PR이므로 main/운영에 병합하지 않았다.

반복적으로 예외를 내는 외부 렌더 callback의 완전 격리와 큰 비정상 이미지의 디코딩 전 크기 거부는 낮은 우선순위 참고로 남는다. 실제 고정 자료에서 오류가 재현됐다는 뜻은 아니다.

실행 결과·입력/산출물 SHA는 [검증 영수증](results/cv_reacquire_view_20261027/verification_v1.json)에 기록한다.
새 Python33·기존 뷰어/OCR/체크리스트74, Node32 검사와 린트186경로를 통과했다.
기록 커밋 `620673f`의 Ubuntu/macOS CI 두 작업도 성공했다(실행40368090669). 이후 검토 시간 초과 기록만 추가했으며, CI 통과를 다른 모델 검토로 취급하지 않는다.
실제 203장·3구에서 화면 전환, 미확정/확정/소실, 과거 사건 분리, OCR 문자열과 관측 없음,
마지막 장 자동 정지, 재생 중 모드 전환을 Windows 인앱 브라우저로 확인했다. 콘솔 오류·경고0.
새 비공개 팩은 `outputs/cv_mitt_reacquire_view_20261027_v1/`이며 영수증 제외208파일을
모두 SHA/크기 대조했다. 영수증 SHA는 `3914d1f12fb2143b3a89adcec927d0aacc75dc7283cc22cdcd8c7554d246dfd1`이다.
이 화면은 저장 개발 결과를 확인하는 도구다. 오래 따라가는 현상을 미트 식별이나 정확도 개선으로
해석하지 않는다. 미트 아닌 시드를 재탐색으로 연장하는 사례가 이미 CV37b에 기록돼 있다.
독립 PTS·사람 정확도·새 경기 일반화·실시간 처리·Mac/아이폰 검증은 하지 않았다.
CV35/36·A-y/F-4i 조건과 기존 M3 수치는 그대로다.

다음 기술 과제는 이 비교 화면에서 확인되는 잘못된 시드와 짧은 재획득 구간을 바탕으로,
**미트 식별 조건과 안정적으로 비교할 순간의 조건을 별도로 검증**하는 것이다.
시드가 잘못된 상태에서 추적 시간만 늘리는 것을 목표로 하지 않는다.
