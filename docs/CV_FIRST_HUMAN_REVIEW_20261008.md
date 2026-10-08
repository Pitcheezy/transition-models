# CV6 첫 사람 응답과 자세 분류 한계 — 2026-10-08

## 수신과 검사 결과

사용자가 원본 화면을 검토해 제출한 응답 한 개를 기존 v1 검사기로 처리했다.
프로그램은 작성자의 신원·독립 작업 여부나 시각적 정확성을 인증하지 않는다.

| 항목 | 실제 결과 |
|---|---|
| 검토자 응답 | 1개 |
| 대상 | 기존 개발 이미지26장: 823407·849845 각13장 |
| 미트 중심 | marked26, unavailable0, status unknown0, unreviewed0 |
| 가시성 | 제출값 full26 |
| 자세 | 제출값 resting18, moving5, presented_target2, unknown1 |
| 원본 연결 | manifest·이미지 SHA·원본 크기·관측 ID·투구 키 연결 검사 통과 |
| 원응답 보존 | 9,035bytes, 원본과 비공개 사본 SHA 동일 |
| 기존 검토 팩 | 고정31파일 SHA 불변, 빈 양식 불변 |
| 점 자료 | 26고유 프레임·26점, 원응답의 점/상태/가시성/자세/메모 그대로 보존 |
| 사람 간 비교 | 응답1개이므로 비교쌍0, 일치도 미측정 |
| 학습 | 학습 선택0, ready_for_training=false, 실제 학습 없음 |

원응답 SHA256: `d25fa9908aa90aacfcdab6e068543e62e8eca698bd7322e615c428fb6df5ffeb`.
검토 manifest SHA256: `d7d01b7776436c4539900e3a44115343e2b7db2eb6ae27489c3ae2f7a7f1a468`.
[수신 검사 기록](results/cv_independent_20261008/review_intake_v1.json) ·
[공유용 점 집계](results/cv_independent_20261008/review_point_summary_received_v1.json).

이는 데이터 구조·출처·좌표 범위의 검사다. 26점이 시각적으로 정확하다는 검증이나
AI 기권26건이 모두 잘못됐다는 판정이 아니다. 기존84점 중26장의 재검토이며 새 이미지26장이 아니다.
pose의 unknown1은 status unknown과 다르므로 미검토나 기권으로 집계하지 않았다.

## 사용자가 발견한 분류 문제

사용자는 미트를 들기 직전에 낮게 놓은 장면이 많아 ‘내려놓거나 쉬는 자세’와
‘움직이는 자세’ 사이의 선택이 애매하다고 보고했다. 이는 전체 응답에 동반된 피드백이며,
어떤 행을 어느 값으로 고치라는 개별 수정 지시가 아니다.

- 정지 화면의 낮은 위치는 휴식의 증거가 아니다. 공을 받을 준비 과정일 가능성도 있으나 이번 파일로 확정하지 않는다.
- 낮게 위치하면서 동시에 움직이는 경우도 가능하므로 공간적 자세와 시간적 움직임은 서로 반대인 두 상태가 아니다.
- 이번18개의 resting을 ‘실제 휴식18건’으로 읽거나 일괄 moving/unknown/목표 위치로 바꾸지 않는다.
- moving5도 연속 프레임으로 검증된 이동5건을 뜻하지 않는다. presented_target2도 투수 의도 정답이 아니다.
- 미트가 낮아도 중심이 보이면 표시한다는 기존 관측 규약은 유지한다. 자세 선택의 모호함만으로26점을 버리지 않는다.

원응답과 피드백을 별도 파일에 보존했다. 원래 pose 값을 유지하되 현재 응답의 자세 필드는
기술용 참고 속성으로만 다룬다. 목표 제시·휴식·이동의 확정 정답이나 학습 대상으로 선택하지 않았다.
현재 검토 UI와 schema, 기존 프로토콜을 소급 변경하지 않았다.

## 다음 규약 개선 방향 — 아직 적용 전

1. 단일 프레임에서는 미트 중심과 가시성을 기록한다. 자세 판단 근거가 부족하면 pose=unknown을 허용한다.
   중심을 표시하면서 자세만 unknown인 것은 정상적인 응답이다.
2. ‘올리는 중 / 일정 시간 제시·유지 / 내리는 중’ 같은 동작은 시간순 연속 프레임으로 정의하고 검증한다.
   무엇을 안정된 제시로 볼지, 어느 구간을 관측할지는 새 규약과 별도 개발 자료에서 고정해야 한다.
3. 실제 투구 전 서비스에서는 해당 시점까지 도착한 영상으로만 판단한다. 릴리스 뒤를 보고 과거 프레임을
   목표로 확정한 결과와 구분한다. 보이는 미트 중심→제시 후보 선택→좌표 변환은 별도 단계다.

v2 명칭·지속시간 기준·새 자세 필드를 이번 수신 작업에서 임의로 확정하지 않았다.
새 규약으로 다시 판단할 경우 별도 응답을 받고 v1 원본을 유지한다.

## 보관과 재현

비공개 폴더: `outputs/cv_review_response_20261008_v1/`.
`human_review_response.json`은 원본 바이트 사본, `reviewer_feedback.json`은 전역 피드백,
`check.json`·`review_summary_private.json`은 검사/집계, `point_data/manifest.json`은 개별점·출처를 담는다.
이 폴더는 Git 제외다. 공유용 산출물은 위 두 집계 파일로 한정한다.

실제 실행한 기존 함수는 `check_response` → `summarize` → `review_point_data.prepare`다.
같은 입력은 아래 CLI로 재현할 수 있다. `NEW` 출력 경로는 새 이름이어야 한다.

```text
python -m intent.review_queue check-response --package outputs/cv_review_20261008_ko_v1 --response outputs/cv_review_response_20261008_v1/human_review_response.json
python -m intent.review_summary --package outputs/cv_review_20261008_ko_v1 --response outputs/cv_review_response_20261008_v1/human_review_response.json --out outputs/cv_review_response_20261008_v1/summary_NEW.json
python -m intent.review_point_data --package outputs/cv_review_20261008_ko_v1 --dataset-manifest outputs/cv_local_dataset_v1/manifest.json --dataset-audit docs/results/cv_local_20261007/dataset_audit_v1.json --response outputs/cv_review_response_20261008_v1/human_review_response.json --out outputs/cv_review_points_NEW
```

CV-6a 수신·검사·개발 집계·점 자료 준비는 완료다. CV-6의 첫 사람 재검토도 제출 완료이며,
기권 원인 분류·합의 판정은 아직 미완료다. 가용성 합의와 사람 간 일치도에는 별도의 독립된 두 판단이 필요하다.
CV7 미열람 영상·새 독립 검토자, 팀원 S 응답, 기존 M3/공개 서비스 상태는 바뀌지 않았다.

검사 기록: 기존 check→summary→point prepare의 실제 자료 실행 성공,26행 원응답 필드 일치·비공개 사본 바이트 동일,
공유 JSON의 개별 ID/좌표/경로 제외 확인, 체크리스트 가드7 passed(2.02초). 모델·서비스 코드는 변경하지 않았다.
