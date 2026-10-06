# 우리 CV 오프라인 시연 묶음 — v4, 2026-10-06

첫 타석 공식 영상 3구와 제공받은 실제 저장 응답을 연결한 Site v8의 비공개 발표 묶음이다.
최신 발표 동선은 [발표 대본](PITCH_STUDIO_DEMO_RUNBOOK.md)을 따른다. 과거 v3의 실제 응답
미수신 상태는 해소됐다. Song 최종 확인·실기기 리허설(E-demo2)은 여전히 별도 대기다.

## 파일과 실행

- ZIP: `outputs/demo_delivery/pitcheezy_offline_demo_20261006_v4.zip`
- 폴더: 같은 위치의 `pitcheezy_offline_demo_20261006_v4/`
- 시작: ZIP 전체 압축 해제 → `START_HERE.html` → 첫 타석 추천·영상·결과
- 크기: 18,087,236바이트, 내용 38파일 + `bundle_manifest.json`
- ZIP SHA256: `c9eed39629a90ec57dd3988c29fedc10358da4138dcef02c44e13025330bcdc9`
- 기존 v1/v2/v3는 덮어쓰지 않고 보존했다. 전달 시 v4 전체를 사용한다.

포함: 사이트 30파일(실제 응답·공식 3구 영상/포스터·판독 정지 장면·제어 코드), 기존 CV
장표 PNG/PPTX 2파일, private 비교 HTML/README/manifest 3파일, 시작 안내·대본·실행 안내 3파일.
미트는 3구 별도 정지 프레임에서만 표시한다. 1·2구 주석은 없다. 실제 저장 응답의 구종
선택 비중을 사건확률이나 사전 예측 성능으로 설명하지 않는다.

기본 시연 파일은 인터넷·모델 서버·로그인이 필요 없다. 파일 기능이 제한되면 보안 설정을
바꾸지 말고 압축 푼 폴더에서 `python -m http.server 8786 --bind 127.0.0.1`을 실행한다.
Mac은 필요하면 `python3`를 쓴다. `http://127.0.0.1:8786/START_HERE.html`, 종료 Ctrl+C.
이 안내는 사용자 기기용이다. 이번 작업에서 앱 브라우저의 file URL 차단을 우회하지 않았다.

## 재현

```bash
python scripts/check_pitch_studio.py
python scripts/build_pitch_demo_bundle.py build --comparison outputs/intent_label/delivery_20261005/intent_comparison_local --out outputs/demo_delivery/pitcheezy_offline_demo_new
python scripts/build_pitch_demo_bundle.py check outputs/demo_delivery/pitcheezy_offline_demo_new
```

새 이름을 사용한다. 기존 출력이 있으면 빌드를 거절한다. Git 소유자 경고가 발생하면
해당 저장소 한 경로만 명시적으로 신뢰하며 전역 `safe.directory=*`를 설정하지 않는다.
빌드 허용 목록에 실제 응답/영상 제어/미디어 레지스트리 JS 3개와 공식 미디어 6개를 추가했다.
미디어는 브라우저에서 동적으로 선택되므로 사이트 검사기가 별도로 경로·playId·해시를 검증한다.

## 확인과 범위

38파일 원본/출력 SHA256과 ZIP 바이트 일치, 상대 HTML 링크 및 기존 비교 HTML·M3 보고서·
내장 JPEG 5장 해시 검사 통과. 사이트 77 Node, 체크리스트 4 passed, Ruff 통과.
홈 링크 `href="./"`만 패키지 HTML 사본에서 `href="index.html"`로 바꾸며 변환을 manifest에 기록한다.
JS/CSS/영상·원본 장표·비교 그림은 바이트 그대로다. Git HEAD는 빌드 시점의 기존 커밋이며
추가 파일 이전일 수 있으므로 정확한 내용은 각 source_sha256/sha256으로 결속한다.

Windows 앱 브라우저에서 공개 사이트와 같은 소스의 세 구 재생·결과 공개·미트 정지 장면·
숨김/투구 전환·1280/390px 배치를 검수했다. ZIP의 file URL 직접 렌더링, Safari/Mac/iPhone,
실제 낭독 시간은 미확인이다. 이를 사용자/Song 현장 리허설 완료로 세지 않는다.

이 ZIP은 기존 private 비교 그림을 포함하므로 비공개 현장·지정 팀원 파일 전달용이다.
ZIP이나 comparison/은 공개 사이트·GitHub에 올리지 않았다. 팀원에게 전송하지 않았다.
공개 사이트 영상 승인과 비공개 비교 그림의 취급을 구분한다. 모델·원본 사람 라벨·private
세션·전체 중계 영상·API 인증정보는 포함하지 않는다. 기존 M3·JSONL·장표·팀원 저장소 불변.
