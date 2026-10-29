# SITE-1d 공개 사이트 갱신 시도 — 2026-10-29

## 결과

사용자는 현재까지 완성한 사이트 변경을 실제 공개 사이트에 반영하도록 승인했다.
공개 자산 준비·최종 검토·패키징은 완료했지만 **Sites 원격 Git 소스 저장이 HTTP 500으로 실패하여 공개 배포는 미완료**다.
기존 공개 버전은 9, 접근 범위 public이며 그대로 유지된다. 새 버전 저장/배포 도구는 호출하지 않았다.

## 고정 대상과 검증

- 제품 코드: `2e5a80f2ae8a538dc06423e57961193f7a4d9b50`, 우리 `codex/site-first-1029` / PR85. main 미통합.
- 작성: Codex. 별도 모델 최종 검토: `gpt-6.1-terra`, 고정 코드 APPROVE. 이전 Fable 승인을 재사용하지 않았다.
- 검토: 이전 중간 지적 수정, 공개 전후 분리·초기화, 추천 순위 겹침, 접근성, 예시 자산 참조 제거, 위치 의미, 수치의 분모·한계. Node 51검사 통과.
- 검토 모델이 실제 브라우저·실기기·외부 원문·실운영을 재검증한 것은 아니다.
- 제품 CI: validation run `40844678338`, Ubuntu24.04/macOS15 모두 SUCCESS.
- 로컬 검사·브라우저 근거: [SITE-1 기록](SITE_FIRST_20261029.md). 로컬 결과를 공개 운영 검증으로 승격하지 않는다.
- 좁은 모바일 검증 리포트의 일부 카드 가로 넘침은 알려진 별도 수정 항목이다.

## 공개 자산과 보존 상태

`scripts/build_pitch_demo_bundle.py`의 `SITE_FILES` **33개만** 기존 Sites checkout의 dist에 반영했다.
비공개 전체 발표팩·사람 응답·비교 갤러리·가중치·추가 경기 원문은 포함하지 않았다.
예전 생성 파일 `preview-data.js`, `studio.js`, `studio.css`는 로컬 백업 후 새 dist에서 제외했다.
기존 공개 영상·저장 추천 응답·CV 기록은 보존했다.

공식 package-site helper의 archive는 `dist/.openai/hosting.json` 포함34파일이다.
모든 자산 경로와 SHA가 허용 목록과 일치한다. [자산·해시 영수증](results/site_publication_20261029/receipt.json).
첫 자체 목록 검사는 manifest를 archive 루트에 있을 것으로 가정해 실패했으며,
공식 helper의 실제 dist prefix를 확인하고 정확한34경로/33자산 SHA 검사로 수정해 통과했다.

기존 project ID·audience를 재사용했고 원격 공개 소스 `a3a7a6bb7bc434c6ba93ae45f12bca23c8898012`를 확인했다.
로컬 Sites 소스 커밋 `f3b97a29e1e73373953794877816f7631d0036db`는 생성·보존됐지만 원격 푸시는 실패했다.
새 source credential로 원격 조회가 성공한 뒤 재시도했고,
프로세스 한정 HTTP/1.1까지 총3회 모두 같은 HTTP500이었다. 기존 원격 이력을 덮어쓰지 않았다.
Windows 소유자 차이는 프로세스 한정 safe.directory로 처리했다. 전역 Git 설정은 바꾸지 않았다.
인증 값은 helper의 숨김 표준입력으로만 전달했으며 문서·원장·공개 소스에 저장하지 않았다.

## 재개

1. 같은 Site·checkout의 원격 HEAD와 최신 공개 상태를 조회한다. 로컬 커밋과 archive는 보존한다.
2. 새 credential와 공식 `site-workflow.mjs`로 일반푸시·원격 HEAD 일치를 확인한다. 강제푸시하지 않는다.
3. 성공한 helper의 commit/archive로 `save_site_version` 후 기존 public audience에 `deploy_site_version`을 실행한다.
4. 성공 뒤 실제 공개 홈·경기·안내·첫 타석 추천/결과/전환을 확인하고 이 기록·CHECKLIST·우리 board를 갱신한다.

현재 후보는 첫 타석3구 범위다. 이미 받은71타석·262구 및 별도 내부 검토 화면 연결은 다음 단위다.
최신 Song 관전 UI·실시간 연결 완료가 아니다. 팀원 저장소·별도 Cloudflare 시험 Worker·DNS·권한·요금제는 변경하지 않았다.
