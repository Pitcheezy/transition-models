# 고정 배포 후보 패키지 — WS-ops4a

우리 호스팅 파일과 별도로 받은 공개 화면 빌드를 한 목록으로 묶는다.
**이 형식은 우리 배포 도구의 형식이며 Song의 공개 발행 JSON 계약이 아니다.**
팀원 저장소를 조회·변경하거나 빌드 명령을 실행하지 않는다. 계정·업로드·배포 기능도 없다.

## 입력과 산출물

- 우리 호스트: 지정한 40자리 Git 커밋에서 운영 파일10개를 읽는다. 미커밋 변경은 포함하지 않는다.
- 공개 화면: 사용자가 지정한 빌드 디렉터리. index.html이 필요하다. 기존 Sites/비공개 영상팩을 자동 복사하지 않는다.
- 공급자 메타데이터: 저장소, 고정 커밋, 빌드 명령, Node/npm 버전, 계약별 버전·커밋.
  화면 파일이 실제 그 커밋에서 빌드됐는지는 이 도구가 증명하지 않는다.
- 출력: 새 디렉터리 안 release.zip, receipt.json. 기존 경로 덮어쓰기·삭제 없음.
- ZIP: host/ 운영 파일, public/ 화면 파일, release-manifest.json.
  manifest는 각 파일 경로·바이트 수·SHA-256을 담고 자기 자신은 목록에서 제외한다.
  receipt가 manifest와 ZIP의 SHA-256을 별도로 담는다.

mode는 synthetic 또는 candidate다. **어느 모드든 deployable=false**다.
검사 통과는 패키지 바이트와 목록의 일치만 뜻한다. 서명·저자 인증·공개 권리·기능·실계정 검사를 대신하지 않는다.
후보를 배포할 때 필요한 Wrangler 실계정 설정도 별도로 검토해야 한다.
[오프라인 설정 검사](CONFIG_CHECK.md)는 패키지 경로·설정 일치까지만 확인한다.
동봉한 wrangler.example.jsonc의 상대 assets 경로는 패키지 실행용으로 자동 수정하지 않는다.

## 실행

저장소 루트에서 Python3.12 표준 라이브러리와 Git을 사용한다. 아래 호스트 커밋은 WS-ops3 병합본이다.
새로운 실행마다 출력 폴더 이름을 바꾸고, 실제 사용 시 검토한 전체 커밋으로 바꾼다.

~~~text
python -B -S scripts/build_public_host_release.py build --frontend ops/public-host/examples/synthetic-dist --provenance ops/public-host/examples/synthetic-provenance.json --host-commit c8a6865af0e64f46551d6da168d607a838cdcf74 --mode synthetic --output .cache/ws-release-example-new
python -B -S scripts/build_public_host_release.py check .cache/ws-release-example-new/release.zip
~~~

부모 .cache 폴더는 먼저 만들어 두어야 한다. 출력 폴더 자체는 없어야 한다.
예제 메타데이터의 111…/222… 커밋은 **가상값**이다. 실제 전달을 뜻하지 않는다.
최소 실행 의존성만 쓰므로 uv/학습 가중치/영상/MLB 계정은 필요 없다.
실제 후보에는 공급받은 고정 메타데이터와 공개 빌드만 넣는다. 브랜치 이름·latest는 받지 않는다.

성공은 종료0, 거부는 종료2이며 JSON 진단을 출력한다. check는 압축을 풀거나 내용을 실행하지 않는다.
ZIP 파일을 임의로 다시 압축하면 거부한다. manifest 변경 후 재압축해서 출처를 인증할 수 있는 도구가 아니다.

## 방어 범위와 한계

- 고정 파일 수·전체100MiB·파일20MiB·목록2MiB 상한. Git 객체 크기도 읽기 전 검사.
- 상대 ASCII 경로만 수용. 경로 탈출·Windows 예약명·대소문자 충돌·파일/폴더 충돌 거부.
- 디스크 symlink/junction/reparse 경로·일반 파일 아닌 입력 거부. 입력을 읽는 동안 바뀌면 거부.
- 비밀 설정명·데이터 API 폴더·영상·음성·ZIP·DB·가중치·source map 등은 공개 빌드로 수용하지 않는다.
- LFS 포인터·일부 키/token 패턴 검사. **모든 비밀·개인정보를 자동 탐지한다는 보장은 없다.**
  HTML/JS 안의 외부 주소·스크립트 동작·재배포 범위는 별도 검토한다.
- 압축하지 않은 정렬된 ZIP, 고정 시각·권한. 같은 입력은 같은 ZIP SHA.
  검사한 파일로 다시 만든 바이트와 원본 ZIP 전체를 대조하여 extra/comment/앞뒤 부착 데이터도 거부한다.
- ZIP 내부 경로·크기·CRC·해시·추가/누락 파일·중복 JSON 키를 검사한다.
- 신뢰할 수 있는 로컬 작업 디렉터리에서 사용한다. 동시에 적대적으로 파일을 바꾸는 사용자와의
  OS 수준 격리 도구는 아니다. 미검토 빌드의 JavaScript를 실행하지 않는다.

## 검증

~~~text
python -m pytest tests/test_public_host_release.py -q
~~~

경로/비공개 파일·변조/누락/추가·ZIP·링크·고정 Git blob·CLI·출력 보존을 검사한다.
작업트리의 host 파일을 바꿔도 지정 커밋의 파일을 선택하는지 별도 임시 Git 저장소에서 확인한다.
실제 Song 빌드/실계정/CDN/Safari 검사가 아니다. 실제 전달물 도착 후 WS-ops2에서 이어간다.
