# 먼저 읽기 — COLLAB-001 우리 호스팅 전달팩

2026-10-18. **Song의 발행기와 연결을 검토하기 위한 우리 소스 묶음**입니다.
우리 호스팅 담당 코드만 포함합니다. Song 모델·화면·소스·영상이나 실제 접속 자격은 없습니다.
이 파일은 ZIP 안에서 START_HERE.md로 제공됩니다.

## 1. 먼저 확인할 것

- 소스 고정 커밋: `3ea7ad69781daec8e80ce257ea39633ad6b2770a` (`Pitcheezy/transition-models`).
- 전달 형식: 필요한 소스 + 합성 예제 + lock 파일 + 검사 + 파일별 SHA-256 + 결과/한계.
- `MANIFEST.json`: 들어 있는 파일의 이름·바이트·SHA-256·출처. 자기 자신은 제외합니다.
- `VALIDATION.json`: 이 묶음을 노트북 새 폴더에서 실행한 결과. 실제 공동 연결 결과는 아닙니다.
- ZIP 자체 SHA-256은 같은 mail #18 회신과 별도 전달 영수증에서 대조합니다.
- ZIP은 기존 사람 간 비공개 전달로 주고받고, 요청·결과는 기존 mail #18에 이어 남깁니다.
  우리 쪽 준비 완료와 Song의 실제 수신은 별도로 확인합니다.

## 2. 읽는 순서

1. 이 문서 → `ops/public-host/README.md`: 업로드 API, 파일 경로, 응답 의미.
2. `ops/public-host/PUBLISH_SCOPE.md`: 시험 키 하나와 UTC 만료 제한. **현재 배포에는 미반영**.
3. `ops/public-host/ACCESS.md`, `NOTICE.md`: 관람 접근 문과 긴급 안내, 401/503 처리.
4. `ops/public-host/PUBLISHER.md`: 조건부 PUT/DELETE/HEAD와 불확실한 결과 처리.
5. `docs/WS_PUBLISH_SCOPE_20261017.md`, `docs/WS_LAPTOP_OPS_20261018.md`: 기존 검증 근거·한계.

`ops/public-host/`의 Git 추적 파일만 넣었습니다. node_modules나 실제 운영 설정은 없습니다.
이전 문서의 다른 저장소 경로/검사 명령은 역사적 참고이며, 이 팩에서 실행할 명령은 아래 3절입니다.
동봉되지 않은 문서는 소스 고정 커밋의 GitHub 파일로 확인할 수 있습니다.
패키지/설정용 Python 도구와 Song 화면 빌드는 이 소스 검토팩에 포함하지 않습니다.

## 3. 노트북에서 확인하는 방법

Node 24 이상과 npm이 필요합니다. 검사 환경은 Windows / Node 24.1.0입니다.
별도의 새 폴더에 압축을 풀고, **이 파일이 있는 폴더**에서 아래 순서로 실행합니다.
원래 저장소나 실행 중인 서버를 변경하지 않습니다. 의존성 설치는 npm 레지스트리 접속이 필요합니다.

```text
npm ci --ignore-scripts --prefix ops/public-host
npm --prefix ops/public-host run check
npm --prefix ops/public-host test
node ops/public-host/publisher-cli.mjs --plan ops/public-host/examples/publish-plan.json
node ops/public-host/rehearse-operator-tools.mjs
```

- 첫 줄은 lock에 고정된 검사 의존성을 설치하며 설치 스크립트는 실행하지 않습니다.
- check/test는 문법 및 합성 검사입니다. 검사들이 새 로컬 Worker를 잠깐 실행할 수 있습니다.
- publisher 명령은 기본 **dry-run**입니다. `--execute`를 추가하지 않습니다. 실제 업로드 없음.
- 마지막 명령은 새 임시 loopback Worker에서 도구를 연결하고 자기 임시 자원만 정리합니다.
  Mac/Song 맥미니/Cloudflare/외부 이메일에 연결하지 않습니다.
- 기존 Windows workerd 연결 종료 진단이 나올 수 있습니다. 명령 종료 코드와 결과를 함께 봅니다.
- 두 번째 시험은 기존 결과를 덮어쓰지 않고 새 폴더에서 진행합니다.

`examples/publish-payload.json`은 **합성 전송 자료**이며 Song의 경기 JSON Schema 예제가 아닙니다.
`wrangler.example.jsonc` 등의 설정은 실제 계정이 없는 가상 예제이고 접근 문 기본값도 false입니다.
현재 실제 호스트 설정으로 오해하거나 `wrangler deploy`에 바로 사용하지 않습니다.

## 4. 연결 API 요약 — 기존 계약 유지

공개 파일 경로 앞에 `/_publish`를 붙입니다. 발행 bearer와 관람 세션은 별개입니다.

- PUT: JSON 원문 바이트의 SHA-256, 첫 저장 `If-None-Match: *`, 교체 `If-Match`.
- HEAD: 인증 후 현재 ETag·SHA·삭제표식 여부 확인. 기존 키/표식이면 공동 시험을 시작하지 않습니다.
- DELETE: 현재 ETag 조건으로 삭제표식을 만듭니다. 물리 삭제가 아닙니다.
- 복원: 삭제표식 ETag 조건으로 PUT. 412 또는 unknown이면 새 조건으로 자동 덮어쓰지 않습니다.
- 저장 성공의 `schema_validated:false`: 운반·저장 성공일 뿐 경기 스키마/발행 묶음 검증이 아닙니다.
- 관람 세션 없음: 401 `access_required`. 긴급 안내: 503 `service_notice`.
- 공개 파일 v1·공개 발행 문서 초안 v0·IntentEstimate v1.1은 서로 다른 버전입니다. 이번에 변경하지 않습니다.

## 5. 현재 코드와 실제 배포를 구분합니다

- 이 팩: 위 main 고정 소스. 단일 키·절대 만료 제한과 운영 도구가 들어 있습니다.
- 마지막 확인된 실제 호스팅 소스: `87168d7bc42f11f76886e475f919caff7674b60a` (10/16).
- 10/16 종료 상태: 접근 문 ON, 자료읽기/업로드/수집/피드백 OFF, 안내 OFF.
- 10/18 실제 계정 상태는 재조회하지 않았습니다. 새 팩이 실제 배포를 바꾸지 않습니다.
- 기존 클라우드 발행 bearer는 경로 전체에 유효하고 서버 강제 만료가 없습니다.
  이 팩의 좁은 키·만료 기능을 실제 사용할 때는 새 배포·설정·회수 검증이 필요합니다.

## 6. 확인한 범위와 아직 확인하지 않은 범위

기존 WS-laptop1은 로컬 CLI 29회·Node304 검사입니다. 새 압축해제 검사는 VALIDATION.json을 따릅니다.
작성 코드의 고정 다른 모델 검토 근거는 동봉한 두 검증 문서에 있습니다.
이번 전달 작업은 운영 코드를 고치지 않습니다. 새 작성 모델 증거가 생긴 것으로 소급하지 않습니다.

- 이 로컬 CLI29회는 **Song runner의 총18 HTTP 요청/120초 예산 검증이 아닙니다**.
- 전체 HTTP 수, 실제 만료 시각 경계, Ctrl+C, 공동 HTTPS, 실경기, 실제 이메일 전달은 미측정입니다.
- 현재 합성 리허설은 health 키를 씁니다. 공동 시험의 게임 키·본문2KiB·18요청·120초와 별개입니다.
- 송수신 파일의 SHA 일치는 무결성 근거이며 운영 승인·저자 인증·자료 이용 권리의 증거가 아닙니다.

## 7. 이 팩을 받은 다음

Song 쪽은 자기 작업 폴더에서 파일 해시와 필요한 계약을 확인하고, 고정 소스/공개 빌드/스키마/
미지원 예제/비활성 runner 설정/검증·한계를 같은 방식으로 전달하면 됩니다. 상대 저장소는 수정하지 않습니다.
우리는 받은 고정 파일을 검증한 뒤 한 키 합성 공동 시험의 실행안을 고정합니다.

실제 시험 전에는 접속 허용·단일 writer·시험 시간·운영자·발행/관람 자격 전달과 회수를 따로 정합니다.
실제 주소·토큰·코드·개인 경로는 공개 이슈에 쓰지 않습니다. 배포·공개·실경기·추가 비용은 이 전달에 포함하지 않습니다.

공동 기록: https://github.com/Pitcheezy/transition-models/issues/18
