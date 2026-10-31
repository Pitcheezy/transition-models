# 전시 빌드 로컬 인수·영상팩 — 2026-11-01

## 범위

사용자가 Song #38 회신3·4를 채택했다. 새 branch codex/exhibition-intake-1101은 main4e6aba7에서 시작했으며 기존 site-first의 미커밋 변경, Claude PR86, 연구 PR과 공개 Sites v21을 보존했다. 팀원 소스·Cloudflare·DNS·기존 사이트·PR 병합/닫기는 변경하지 않았다.

## 받은 빌드

- Song fba6b2ff846dcfa9afad9ea5df4204007e0604c1. ZIP867682bytes, SHA af10293d5134219b7f750d00786366b93b0134c895519b939fd99a356d77a4bc.
- CRC와 manifest28개 원본/LF SHA,11992694bytes 일치. 파일 추출 전 검증, 원본 변경 없음.
- 849843 262고유투구/71타석/추천246/미지원16. final archive이며 next는 없다.
- 다른 경기의 추천 범위를 이번에 평가하지 않았다. 잠금849844는 ZIP 바이트 무결성 검사만 수행했다.
- Chrome 로컬38확인 통과:1440/390/320폭, 첫투구·타석선택, 안내 중 추천/존/목록숨김, 안내 뒤 오류에서 숨김유지, 정상응답 복원, game-only 안내와 복원, 날짜진입·누락404.
- 안내 응답·갱신순번은 메모리 모의 값이다. Cloudflare 스위치·저장로그·실기기 검사와 구별한다. 받은 파일은 수정하지 않았다.
- 날짜 목록23일 대비 파일5일로18일이 누락되어 있다. 전시849843 직접진입은 통과했지만 전체 날짜 탐색 인수는 조건부다. 임의로 원문을 고치지 않는다.
- Song의 이전 독립검토는32e79c2f 대상 BLOCK이며 fba6b2ff 소스 전체의 재검토를 완료했다고 주장하지 않는다. 이번 결과는 받은 빌드 로컬 동작 인수다.

## 영상팩

261개 공식MP4와262투구 등록부를 같은ID·선수·구종·play ID·원본SHA로 결속한다. 849843:69:2는 SL/FC불일치로 제외한 사실을 보존한다. 영상 합계1313406955bytes, 약35분45초의 투구별 클립이며 풀 중계가 아니다.

영상만 표시하는 플레이어는 모니터1과 같은 타석·구를 수동으로 맞춘다. 추천·실제 공좌표·미트 점은 표시하지 않는다. 수동 선택/탐색은 이어재생을 멈추고, 제외·오류를 자동으로 건너뛰지 않는다. Python3.10이상 표준라이브러리 실행기와 해시 검사기를 포함한다. 로컬 서버는127.0.0.1에만 바인딩하고 허용 파일/Range를 지원한다.

최종 ZIP은v2,1313836394bytes,SHA15fa4f349f8b13f025482cbf58ac111f1c7a631faa29de1cc276b300430e6b7b. 제품4cec0f8. 별도 새폴더 압축해제·270파일해시·소스7파일일치까지 확인했다. Python57/Node29/영상Chrome14확인. 첫3클립은끝까지실재생했고 경계는탐색보조, BFCache이벤트는모의임을 영수증에 구분했다. 이전 시험용 ZIP도 삭제하지 않는다. 영상팩과 받은 빌드는 Git/공개 링크에 넣지 않는다.

## 검토

우리 첫 구현1faada9를 다른 모델 gpt-6.1-terra로 정적 검토했다. BFCache 복원 이벤트·기존 영수증 덮어쓰기 P2와404검사 미흡을 수정했고, 후속 메타데이터 경합도 제거한4cec0f8에서 재검토PASS를 받았다. 검사 실행 주체와 정적 검토 주체는 구분한다. Claude 외부 전송은 자동 승인 검토가 이번 코드 범위의 명시적 전송 승인이 없다는 이유로 거절해 실행하지 않았다. 내부 다른 모델 검토로 분리했다.

## EXHIBIT-clips2: 교차검토 지적 수정과 팩 v3 — 2026-11-01

EXHIBIT-review2의 확인 16건(단축키 중복 1건 포함)을 Codex 코드 위에서 모두 수정했다. 반박 5건은 손대지 않았다. 등록부 의미(262행·261클립·849843:69:2 제외)와 web/pitch-studio·ops·다른 worktree는 변경하지 않았다.

- 플레이어(web/clip-chain): 재생 속도가 다음 공·이어 재생·다시 불러오기에서도 유지된다(defaultPlaybackRate). 표기는 모니터 1 기준으로 "9회 초 · Nico Hoerner · 2구"(초/말은 Song 규칙 Top→초, 그 외→말; 이전엔 132구가 "Bot"), 타석 목록 "9회 초 · Nico Hoerner", 전체 목록은 순번+같은 표기. "PA N"은 쓰지 않고 투구 ID는 보조 표시로 유지. 마우스로 버튼을 누른 뒤에도 Space/←→가 동작한다(포인터 클릭 후 blur). play() 거절은 NotAllowedError만 자동재생 안내로 표시하고 AbortError·오류 상태는 덮어쓰지 않는다. 미디어 오류 문구는 serve.py 터미널 확인·표시된 주소 재접속을 안내한다. 등록되지 않은 ?pitch=는 첫 투구를 표시하고 상태줄에 알린다. 전체 화면은 stage(식별줄·영상·투구 ID)를 대상으로 하여 클립 교체에도 유지된다. 표기 함수 label/paLabel은 core.js로 옮겨 Node 검사 대상이다.
- 실행기(scripts/clip_pack_runtime): serve.py는 mimetypes 대신 고정 Content-Type 표(html/css/js utf-8, json, mp4)를 쓰고 그 외 확장자는 404, Windows는 독점 바인드(SO_EXCLUSIVEADDRUSE, 주소 재사용 끔), macOS/Linux는 주소 재사용 유지(실행 중 서버 위로는 묶이지 않고, 끈 직후 재시작해도 8741을 되찾음 — Opus 검토 수정), 기본 포트 8741(저장소 내 다른 용도 없음), 사용 중이면 빈 포트로 열며 사유를 출력, 명시 --port가 사용 중이면 종료. verify.py는 .DS_Store·Thumbs.db·desktop.ini, 기대 파일 옆의 ._파일, __MACOSX/ 안의 그런 이름만 경고로 통과시키고 그 외 추가/누락 파일은 이름(최대 8개)과 함께 실패한다. README에 py -3 대안, Mac Command Line Tools 안내, 기본 주소·복구 절차, 이닝·타자·N구 맞춤 설명을 넣었다.
- 인수(scripts/intake_exhibition_bundle.py): 날짜 파일은 v1/games/YYYY-MM-DD.json 정확 경로만 집계하고 그 외 v1/games 파일은 unlisted_games_files로 분리한다. source_commit은 유지하되 source_commit_basis "sender_declared_manifest_unverified", declared_commit_dirty와 한계 문구를 추가했다. 받은 ZIP 재실행: 28파일/23일 중 5일/누락 18, unlisted 0. 기존 영수증 docs/results/exhibition_20261101/received-build-integrity.json은 당시 기록으로 그대로 두었다.
- 검사: Python 83 통과(tests/test_exhibition_clip_pack.py·tests/test_exhibition_bundle_intake.py), Node 30 통과(tests/js/clip_chain.test.cjs), 설치 Chrome 19 검사 통과(tests/browser/clip-chain-acceptance.cjs, v3 추출본을 8741에서 실행, 외부 요청 0·페이지 오류 0). 같은 검사 파일을 14d3db2 원본 소스 사본에 돌리면 Python 27 실패·Node 1 실패·Chrome 8 검사 실패(속도 [2,1,1], "1회 Bot · PA 4 · 1구", 포커스 next, 옛 오류 문구, ZIP 안내, 전체화면 불가)로 수정 전 결함이 재현된다. play() 분류는 오류 상태에서 Space, 요청 보류 중 멈추기 두 경로를 14d3db2에서 자동재생 안내로 재현했다.
- 팩 v3: D:/pitcheezy_exhibit_check/pitcheezy-849843-clips-v3.zip 1313843498bytes, SHA 26f0b83d7403312c190f0c176fd4ffbaf452b1c953de896ffc74cf8926fe2baa, builder_base_commit 14d3db2(작업트리 파일은 MANIFEST 해시로 식별). 새 폴더 clips-v3-extracted에 경로 검사 추출 후 python -I -B verify.py 270파일 통과, 소스 7파일이 작업트리와 바이트 일치. v1·v2 ZIP과 추출본은 보존. 영상 1313406955bytes 변동 없음.
- 한계: 실제 Mac Finder/exFAT·Windows 레지스트리 .js 재현은 하지 않았고 단위 검사로 대체했다. 전체 화면·단축키는 headless Chrome에서 확인했으며 실제 모니터 2 PC와 Safari는 미확인이다. 자동 두 모니터 동기화는 여전히 없다.

## 다음: 시험 호스트 연결 전에 설명할 것

1. ASSETS에 정적4파일, R2에는 공개발행API로v1자료를 등록하는 구성을 고정한다. site/ 전체를 ASSETS나R2에 단순복사하면 현재Worker의 경로/저장형식과 맞지 않는다.
2. 받은23일목록/5일파일 차이와 고정경기 진입 범위를 Song과 확인할 초안을 준비한다. 발신은 별도 승인 범위다.
3. 시험 Worker 한정 대상·현재설정·접근 대상·자료 업로드/회수·유한요청 예산·원본 보존을 설명한 뒤 실행한다.
4. 도메인 전환은 기존Sites경로/호스트접근문/HTTPS/되돌릴설정을 정리해 설명한 뒤 시행한다. 이번 세션에서는 실행하지 않는다.
5. 실제Mac/iPhone·모니터2대 수동동선·30~50명 용량·공동시험미대조2건·풀중계원본은 별도 미완료다.

## 재현

- python -B scripts/intake_exhibition_bundle.py <받은ZIP>
- python -B -m pytest tests/test_exhibition_bundle_intake.py tests/test_exhibition_clip_pack.py -q -p no:cacheprovider
- node --test tests/js/clip_chain.test.cjs
- PLAYWRIGHT_MODULE을 설치된Playwright경로로 지정하고 node tests/browser/exhibition-build-acceptance.cjs <추출site> <비공개결과폴더>
- 영상팩에서 python -B verify.py 후 python -B serve.py(기본 http://127.0.0.1:8741/). Windows와Mac의 명령은 팩README참조.
- NODE_PATH를 설치된 Playwright의 node_modules로 지정하고 node tests/browser/clip-chain-acceptance.cjs http://127.0.0.1:8741/ <비공개결과폴더> (영상 플레이어 19검사).

로컬 입력·런타임 경로는 Git제외 outputs/exhibition_1101/local-inputs.private.json. 새 Claude 세션은 docs/CLAUDE_EXHIBITION_RESUME.md부터 읽는다.
