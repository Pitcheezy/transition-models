# main 통합 기록 — 2026-10-11

## 범위와 기준

사용자가 Codex·Claude 작업을 모두 main으로 합치도록 요청했다. 대상은 우리
`Pitcheezy/transition-models` 한 저장소다. 별도 `codex/integrate-main` 작업트리에서
이력을 보존하는 merge를 사용했으며 SongRoute/pitcheezy에는 접근하거나 변경하지 않았다.

조회한 원격/로컬 작업 브랜치는 다음과 같다. 원격 조회 후 새 커밋이 생기면 별도 확인한다.

- 기존 main: `fc7d6475d78953fbb9a0a7f1e417bc006a4b9f68`.
- 최신 웹·CV·검토 UI: `feature/intent-v0@78f4bcc85fea84a73d39ff7e6498a07273dca8c2`.
  기존 main은 이 이력의 조상이며 340커밋 앞선다.
- 별도 Codex OCR 변경: `codex/fix-point-label-alignment@dad552252be4143f839cdf87cf2fd9d015de1a7e`.
  feature 대비 고유 7커밋을 포함했다. 단순 최신 브랜치 선택만으로는 이 변경이 빠졌다.
- 과거 M3 전달 요청: `codex/cv-m3-oct05-deliverables@ed05b3a53a3b6d05fad7269abdd960cf0da2e695`.
  별도 요청 1커밋이며 원래 PR #1의 변경이다.

선점 `ecffd54`, OCR 병합 `5d1dd67`, M3 요청 병합 `9474efb`.
`git merge-base --is-ancestor <각 원본 해시> HEAD`로 세 원본이 모두 포함됨을 확인했다.
미커밋/미추적 자료는 이 통합 범위에 포함하지 않았다. 기존 Windows 작업 폴더와 Mac의
기존 변경, 실행 중 서버, Git 제외 영상/모델/사람 응답을 가져오거나 삭제하지 않았다.
원본 브랜치를 삭제하거나 reset/clean/강제 push하지 않는다.

## 충돌 해결과 보존한 의미

- 기능 코드 충돌은 없었다. CHECKLIST와 재개 문서의 현재 상태를 수동으로 합쳤다.
- F-4h의 첫 투구 전 교체 처리·PA60 평가·v4 후보를 보존했다. 기본 OCR은 v2이며
  F-4i 새 영상 확대는 보류다. 기존 판독 보고서와 코드 해시를 함께 보존했다.
- 최신 feature의 서비스 검토·관측 재생·CV 처리·CI·의존성 lock은 유지했다.
- 2026-10-03 M3 요청은 작성 시점을 명시해 보존했다. 이후 사람 라벨 반영과
  시연 범위를 과거 미체크 요청으로 되돌리지 않았다. M3를 재측정하지 않았다.
- A-y 사용자 보류, CV-6 추가 독립 응답, CV-7 미열람 영상, I-run1 실행 번들,
  I-device2 실제 Mac·아이폰 검사 조건은 유지했다.

## 검증

검사 환경은 Windows 노트북/Python 3.12.12/Node 24.1.0이다.
Python은 기존 feature 가상환경을 재사용하고 검사 cwd는 새 통합 작업트리로 고정했다.
이는 새 환경 설치 검사가 아니다. 새 Linux/macOS 설치는 PR CI에서 별도로 확인한다.

- `python scripts/check_project.py --cpu-only --test-timeout 900`: 전체 검사 진행 중.
- `python scripts/check_pitch_studio.py`: 공개 정적 화면 자산·JS·미디어 출처/SHA·회귀 통과.
- `node --test web/service-review/review.test.cjs web/observation-playback/playback.test.cjs`: 70 passed.
- `scripts/74_evaluate_player_identity_ocr.py check`: PA6 v1/v2, PA60 v2/v4 저장 보고서 4개가
  새 키 기반 집계와 일치하고 pipeline_matches_current_code=true. 새 OCR/사람 판독은 하지 않았다.
- `tests/browser` 합성 Chrome 154/WebKit 26.5: 각각 22 passed. 테스트가 만든 임시 서버/합성 영상만 사용했다.
- 새 worktree의 LFS 포인터만 존재하여 최초 전체 검사 중 추론 10개가 실패했다.
  실제 LFS 객체를 checkout한 뒤 `tests/test_inference.py`는 11 passed(8.55초).
  새 checkout에서는 `git lfs pull` 후 검사한다. 코드나 테스트를 우회·변경하지 않았다.
- 별도 읽기 전용 병합 검토: feature 기능·비OCR 보고서 유지, Codex OCR 코드·테스트·보고서 동일,
  세 입력 커밋 포함, 잔여 충돌 표식/차단 사유 없음.

공개 두 도메인의 PowerShell HEAD(Mozilla User-Agent)는 200, 로컬59154/59158도200이었다.
Python 기본 User-Agent의 공개 HEAD는403이었으므로 이를 일괄 접속 불능으로 해석하지 않는다.
현재 로컬 listener PID37460/45424는 보존했다.

검사 통과는 기능 회귀 범위다. 정책 효용·새 정확도·라이브 추론·실제 Mac/아이폰 검수는 아니다.

## main 반영과 이후 작업

이 문서 작성 시점에는 통합 브랜치 검사 중이다. 원격 main 반영 여부는 PR과 실제 원격 해시로
확인한다. merge commit을 사용하여 세 원본 이력을 남기고, main 반영 직전 원격 변경을 다시 확인한다.

통합 완료 후 새 작업은 최신 main에서 짧은 `codex/<작업명>` 또는 작업자별 짧은 브랜치로 시작한다.
오래된 feature/OCR 브랜치에서 계속 작업하면 다시 갈라지므로 현재 변경을 보존한 채 새 기준으로 옮긴다.
Mac의 미커밋 변경은 이 노트북에서 처리하지 않았다. 그 환경은 별도 status 확인·보존 후 전환한다.

[Codex Cloud 운영 설명과 복사 프롬프트](CODEX_CLOUD_HANDOFF.md)에 공개 Sites, 로컬 S 검토 v5,
관측 재생 v9, Linux 설치·합성 검사·실행 명령을 정리했다. main push는 공개 사이트 배포가 아니다.
Git 제외 자료와 노트북 localhost는 Cloud에 자동으로 따라오지 않는다.
