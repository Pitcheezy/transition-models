# 로컬 글러브 후보 영상 연결 — CV-14

CV-13에서 범용 모델의 미트 판독 채택은 보류했다. 이 작업은 로컬 후보를 시간순 영상 처리에
연결하는 기술 점검이다. 기존 747139 개발 영상의 같은 10시각을 사용하며 전체 타석·독립 영상·
실시간 서비스 성공을 주장하지 않는다.

Faster R-CNN 전체 화면, GPU, 임계값 0.5를 고정했다. 매 프레임 CLI 프로세스와 모델을 새로
만들며 시작 비용을 숨기지 않는다. 5초 간격의 원래 일정을 유지해 누적 지연도 기록한다.
원본·요청·설정·가중치·코드의 해시와 개별 오류/미시도를 보존한다.

기존 응답은 항상 `mitt=null`, `visibility/pose=unknown`이다. 단일/복수 후보는 `unknown`,
후보 없음은 `unavailable`이다. 검출 실패를 실제 미트 부재로 판정하지 않는다.
별도 `local_detector_result.json`에 상자·중심·점수·처리 시간을 남기고, 설정의 원바이트를
`local_detector_config.json`에 보존한다. 모델 오류는 실패이며 기권으로 바꾸지 않는다.

보고 도구는 원본 동영상이나 체크포인트 없이 raw loop의 요청 이미지·설정 사본·응답·시도 기록을
재검증한다. 이 입력 파일이 없으면 검증을 느슨하게 바꾸지 않는다. 공개 보고서는 절대 경로나
원본 이미지·원문 로그를 포함하지 않는다. 세부 시계와 외부 루프는 기간만 비교한다.

[호출 전 규약](results/cv_local_20261007/observer_preregister_v1.json).

```bash
python -m intent.observation_loop --plan PLAN.json --out outputs/cv_local_observer_run_NEW
python -m intent.local_glove_observer_report --run outputs/cv_local_observer_run_NEW --out NEW_REPORT.json
```

아직 이 문서 최초 커밋 시점에는 실제 10시각 호출 전이다. M3·기존 JSONL·사이트·팀원 영역은 고정한다.
