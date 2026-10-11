# H-port3 — 운영 산출물 비공개 전달 ZIP

## 실제 전달 파일

`LEGACY_PROJECT/outputs/integration_delivery/pitcheezy_operational_artifacts_20261008_v1.zip`

- 크기: **5,138,558bytes**. 모델 자료14개(원래8,986,954bytes)+manifest/안내2개.
- SHA256: `d51fa7671ec8d753dbc263469a872d2fba9cb327ffcc183861e9b495f9614d4e`
- 전체 저장소 기준: `8fda709bbfc534d0f8d377234f487aacbb640a5f`.
- [전달/검사 기록](handoff/operational_bundle_delivery_v1.json): 표준 라이브러리 단독 build/check·CRC 통과.
  새 폴더에 실제 압축 해제 후16파일이 ZIP 바이트와 같고,14자료가 목록의 SHA와 일치했다.
- H-port2의 실행 소스/입력27개는 그대로다. H-port1 소스 ZIP도 원래 SHA와 일치한다.
- 로컬 전달 준비 완료이며 **업로드·전송은 하지 않았다**. Mac/새 환경 기동 성공으로 확대하지 않는다.

2026-10-08. `scripts/build_operational_bundle.py`는 [H-port2](HANDOFF_OPERATIONAL_RELOCATION_V1.md)에서
경로 이식을 확인한 우리 운영 모델 산출물14개를 실제 ZIP으로 포장하고 검사한다.
**전달 준비용 도구이며 전송·업로드·공개 배포는 하지 않는다.** 모델이나 pickle을 로드하지 않고
Python 표준 라이브러리만 사용한다. H-port1의 기존48개 소스 ZIP과 과거 영수증은 변경하지 않는다.

## 포함 범위

[외부 자료 목록](handoff/external_artifacts_v1.json)의 `LEGACY_PROJECT` 항목 중 아래 고정14개만
허용한다. 별칭은 원본의 출처를 의미하며 `--artifact-root`에는 H-port2의 검증된 이관 사본도
지정할 수 있다. 다른 파일·폴더를 열거해 포함하지 않는다.

- `data/operational_20260921_v2/`의 `dataset_manifest.json`, `feature_builder.pkl`, `run_value_model.npz`
- `outputs/operational_20260921/mlp135_seed42/`, `mlp135_seed43/`, `mlp135_seed44/` 각각의 `manifest.json`, `best.pt`
- `outputs/operational_20260921/evaluation/`의 `probability_report.json`, `empirical.pkl`, `selection.json`
- `outputs/operational_20260921/policy_nuisance_v2/`의 `manifest.json`, `propensity.txt`

ZIP에는 이14개와 `bundle_manifest.json`, `README_KO.md`만 들어간다. 소스·실행파일·영상·이미지·
사람 라벨·계정정보·학습/평가 배열은 포함하지 않는다.14개 원문은 변환 없이 보존하므로
선택된 seed·기존 모델 버전·선택/보정 근거가 바뀌지 않는다. 실행 의존13개에 선택 근거
`selection.json`을 추가한 구성이다. 실행은 `probability_report.json`의 selection을 읽는다.

## 만들기와 검사

출력 부모 폴더는 미리 존재해야 하며 ZIP 파일은 새 이름이어야 한다. 아래 경로 별칭과
`FULL_CANONICAL_COMMIT`을 실제 전달 대상에 맞게 치환한다.

```text
python -B -S scripts/build_operational_bundle.py build --inventory docs/handoff/external_artifacts_v1.json --artifact-root <VERIFIED_RELOCATED_ARTIFACTS> --source-commit <FULL_CANONICAL_COMMIT> --out <NEW_PRIVATE_ZIP.zip>
python -B -S scripts/build_operational_bundle.py check <NEW_PRIVATE_ZIP.zip>
```

`--source-commit`은 수신자가 확보할 **우리 전체 저장소의 정확한40/64자리 소문자 커밋**이다.
도구가 실행 호환성을 새로 증명하는 값은 아니며 전달자의 명시적 선언이다. H-port2의 소스
해시·실행 환경과 대조해 지정한다. H-port1 소스48개 묶음은 완전한 모델 런타임이 아니다.
수신자가 지정 커밋과 전체 의존성을 별도로 확보해야 한다는 설명을 한국어 안내에 포함한다.

생성기는 ZIP을 만들기 전에14개 파일의 존재·크기·SHA를 모두 검사한다. 목록의 누락/중복,
허용되지 않은 운영 파일, 손상, 경로 이탈, 파일 또는 부모 폴더의 symlink/junction을 거부한다.
기존 출력 ZIP을 덮어쓰지 않는다. 입력 검사가 끝난 뒤 새 ZIP을 배타적으로 생성하며,
저장 중 오류가 발생한 불완전 ZIP도 자동 삭제하거나 다시 덮어쓰지 않는다.

고정 파일 순서·1980년 ZIP 시각·일관된 권한으로 filesystem 수정시각을 제외한다. 같은 입력과
동일 Python/zlib 환경에서는 동일 ZIP 바이트가 생성된다. manifest에는 상대경로·파일별 크기/SHA,
원래 외부 목록의 SHA, 지정 소스 커밋, 한국어 안내의 SHA를 기록하며 개인 절대경로는 기록하지
않는다. SHA는 바이트 검증이며 전달자 인증 서명이나 일반 재배포 권한은 아니다.

`check`는 정확한16개 ZIP member와 해시를 검사하며, 예상 밖 항목·중복·손상·링크 member를
거부한다. 검사를 통과한 ZIP을 새 빈 폴더에 풀고14개 파일의 해시를 다시 대조하는 것이
수신 확인 절차다. 이 과정에는 모델 실행이 필요하지 않다. 실제57번 추론 명령과 원래 보정값을
유지하는 방법은 묶음의 한국어 안내에 있다.

## 검증과 한계

`tests/test_operational_bundle.py`는 작은 합성 바이트만 사용한다. 유효 pickle/NPZ/체크포인트가
아닌 파일도 그대로 포장해, 역직렬화가 없음을 확인한다.14개 정확한 member·압축 해제 동일성,
손상/누락/덮어쓰기 거부, 미지정 비공개 파일 제외, 경로 이탈/파일 링크/부모 링크 거부,
결정적 ZIP, 표준 라이브러리 단독 CLI를 검사했다. 초기 표적 검사는 **21 passed, 0 skipped**였고
Ruff도 통과했다. 실제 전달 ZIP의 크기·SHA와 압축 해제 확인은 위 전달 기록에 있다. 정본의 관련45tests와 전체 Ruff158경로도 통과했다.

이 묶음은 우리 모델의 재현 기준을 보존하며 팀원 모델의 채택·대체 합의가 아니다.
새 Mac·다른 기기·fresh install·모델 정확도·정책 효용·완전한 배포 런타임을 검증하지 않는다.
H-port2의 동일 Windows·동일 환경·예제1개 실행 범위도 그대로 유지한다. 기존 공개 사이트나
API에 자동 연결하지 않으며 원본 모델·보고서·외부 목록·H-port2 영수증을 수정하지 않는다.
