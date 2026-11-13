# relay/batter3d — 3D 타자 독립 데모 단위 1 기록 (2026-11-08)

로컬 시안 전용. 기존 relay 파일(index.html, relay.css, relay.js, data/)은 수정하지 않았다. 호스트 연결, 공개 배포, Song 저장소 변경, 발신은 이 단위에 없다. 구현은 이 Claude 세션, 검토는 GPT(고정 결과만).

## 1. 자산 확인 결과 (2026-11-08 13:40~13:55 KST)

로컬에 쓸 수 있는 캐릭터·동작 자산은 **없다**.

- 검색 범위: `C:\Users\zpfh1\{Downloads,Documents,Desktop,Projects,Pictures,Videos}`(깊이 6)와 `D:\`(깊이 4)에서 `*.glb, *.gltf, *.fbx, *.bvh, *.blend, *.vrm`, 이름에 mixamo/batter/swing/mocap 등. 결과 0건(코드 파일 `batter_clustering.py` 1건은 무관).
- 도구: Blender 없음(Program Files, LocalAppData, Store 모두). Node v24.1.0, Python 3.13.7 있음. `gltf-pipeline`, `gltfpack`, `FBX2glTF` 명령 없음.
- npm 레지스트리 메타만 조회(설치 안 함): `three` 0.187.0(MIT), `fbx2gltf` 0.9.7-p1(BSD-3-Clause, 바이너리 포함 약 35.6 MB), `@gltf-transform/cli` 4.5.1(MIT).

### 무료 후보의 실제 확보 가능 여부 (브라우저로 직접 확인)

| 후보 | 확인한 것 | 판단 |
|---|---|---|
| Adobe Mixamo (mixamo.com) | 첫 화면은 "Log in / Sign up"만 보이고 라이브러리는 로그인 뒤에만 열린다. FAQ(helpx.adobe.com, 2021-09-14 갱신) 원문: "You can use both characters and animations royalty free for personal, commercial, and non-profit projects". 야구 클립 이름은 공식 목록을 못 봤고, 제3자 근거만 있다: 한 야구 게임 저장소의 PR이 "Baseball Strike"와 "Hit" 클립 3종, "Baseball Catcher", "Baseball Umpire"를 사용. 판매자 자료에 "Baseball Step Up To Bat", "Baseball Bunt". "Baseball Idle"은 근거 없음 | **가장 유력한 무료 경로. 사람의 Adobe 로그인이 필요하다.** 클립 이름·좌우·정확한 길이는 로그인 뒤 확인 |
| Quaternius Universal Animation Library 1·2 | CC0, 120+ / 130+ 애니메이션, FBX·GLB·Blend, 로그인 없이 내려받기 가능. 설명은 이동·전투·총·농사·낚시 등이며 야구·배트 스윙 언급 없음. 목록 페이지·뷰어 링크를 찾지 못함 | 야구 스윙 미확인. 캐릭터(Universal Base Characters, CC0)만 쓰고 스윙을 직접 키프레임하는 대비책(C안)에는 쓸 수 있음 |
| poly.pizza "baseball" | 57건 전부 배트·구장·모자·공 모델. 애니메이션 타자 없음 | 부적합 |
| Sketchfab (downloadable + animated, 야구 타자·스윙 검색어 2개) | 첫 검색 0건. 둘째 검색 2건: "Nitro-Slugger"는 배트 소품(46.3k 삼각형, 설명 확인), "low poly Character"는 미확인. 내려받기는 로그인 필요 | 부적합 또는 미확인 |
| Kenney 캐릭터(CC0) | 웹 검색 요약상 노드 리그·클립 27개, 야구 없음 | 부적합 |

### 유료 후보 (구매하지 않음, 조회 시점 표시가)

| 후보 | 표시가 | 확인한 것 | 주의 |
|---|---|---|---|
| 외부 판매처 A의 타자 모델 상품 | 유료 | 설명문·동작 이름·FBX 포함 여부는 페이지 본문 미확인 | 내려받기에 전용 편집기 필요. 애니메이션 형식 미확인 |
| Renderhub "Animo Mocap Baseball" | $69.99 | 모션 팩만(장비·캐릭터 미포함 명시), FBX, 타자 모션 34개 | 캐릭터 별도 확보와 리타겟 필요 |
| Player Motion "Baseball" | $58(Starter 50) | GPT 조사값. 이 세션에서 미조회 | 미확인 |

### Blender 없이 변환하는 길 (자산 확보 뒤 선택)

1. 브라우저 안 변환: three.js `FBXLoader`로 Mixamo FBX(캐릭터 1 + 클립)를 로컬 페이지에서 읽고 `GLTFExporter`로 glb 하나로 저장. 설치 없음, 로컬 http 서버만 필요.
2. `npx fbx2gltf`(BSD-3 바이너리)로 FBX → glb 뒤 `@gltf-transform/cli`로 텍스처 1024 축소·압축.
3. 어느 쪽이든 결과 glb와 원본 FBX는 Git 밖(`D:\pitcheezy_assets\` 제안)에 두고 `assets/LICENSES.md`에 출처·조항·확인자·일시를 적는다.

## 2. 모의 배치 (`layout-mock.html`, 호스트 미적용)

`../relay.css`를 읽기만 하고 relay.js·경기 자료는 쓰지 않는다. 존 창은 relay.js `zoneWindow`와 같은 viewBox(282×301 단위). 측정은 `http://localhost:8790/relay/batter3d/layout-mock.html`에서 뷰포트 390×844, 320×700으로 했다(file:// 로 열면 CSS가 붙지 않아 수치가 틀린다).

| 안 | 390px: 존 그림 / 스트라이크 박스 / 타자 자리 | 320px: 존 그림 / 박스 / 타자 자리 |
|---|---|---|
| A. 지금 호스트(40px 열 둘, 320px 미만 32px) | 270×289 / 159×172 / 40×289 | 216×231 / 127×137 / 32×231 |
| **B. 제안: 서 있는 쪽만 88px(320px 미만 72px), 반대쪽 0** | 262×280 / 154×167 / 88×280 | 208×222 / 122×132 / 72×222 |
| C. 비교용: 양쪽 88px(채택 안 함) | 174×186 / 103×111 / 88×200 | 136×145 / 80×86 / 72×200 |

결론: B안은 존 그림 폭을 A 대비 8px(약 3%)만 줄이면서 타자 자리를 2.2배 넓힌다. C안은 존이 36% 줄어 부적합. 3D 캔버스 높이는 존 그림 높이에 맞춘다(390px에서 280px, 320px에서 222px). 캡처: `captures-20261108/layout-mock-390-A-B-left.jpg`, `layout-mock-390-B-right-C.jpg`, `layout-mock-320-A-B-left.jpg`.

## 3. 다음 사람 단계 (이 단위를 이어가려면)

1. Mixamo에 로그인해 다음을 내려받아 `D:\pitcheezy_assets\mixamo\`에 둔다(Git 밖).
   - 캐릭터 1: 글자·로고·등번호가 없는 사람형(유니폼 느낌이면 좋음). 설정 FBX Binary, With Skin, T-pose.
   - 클립: "Baseball Strike"(헛스윙용), "Baseball Hit" 3종 중 자연스러운 1개(타격용), 대기용 "Baseball Step Up To Bat" 또는 일반 "Idle". 설정 FBX Binary, Without Skin, 30 fps, Keyframe Reduction none, In Place 체크(있으면).
   - 각 클립 미리보기에서 좌타 전용 버전이 있는지, 접촉 프레임이 몇 초인지 메모.
2. 그다음 Claude가 CHECKLIST에 단위를 등록하고 변환 → `batter3d.js` + `demo.html`(진행률 슬라이더, contact/miss/reset, 좌우, 테마) → 캡처와 검사 기록.

## 4. 토큰·시간 (실측 가능한 범위만)

- 세션 문맥 크기(앱 get_usage): 단위 시작 326,989 → 모의 배치 측정 직후 368,540 토큰. 주간 한도 사용률(Fable) 15% → 16%. 과금 총 토큰(캐시 읽기 포함)은 앱이 보여 주지 않아 **미측정**.
- 작업 시간: 약 25분(13:30~13:55 KST).

## 5. 미측정·하지 않은 것

- 3D 타자 외형·스윙 품질(자산 없음). 좌우 반전 외형, 테마 대비, 용량, fps 전부 미측정.
- Mixamo 클립의 정확한 이름·길이·좌타 유무(로그인 필요).
- 유료 후보 자산의 내용물(FBX 여부), Player Motion 조회.
- 다크 테마에서의 모의 배치 캡처(버튼은 있으나 캡처하지 않음).
- CHECKLIST 등록은 자산 준비 뒤(사용자 지시 순서).

## 6. 추가 조사 (2026-11-08 14:10~14:30 KST, 내려받기·구매 없음)

| 후보 | 종류 | 비용 | 로그인 | 확인한 것 | 남는 일 |
|---|---|---|---|---|---|
| CMU Graphics Lab 모션 캡처 DB, subject 124 | 야구 동작 데이터(Baseball Swing 124_07, Bunt 124_08, Pitch 124_01·02), 120 fps | 무료 | 불필요 | FAQ 원문 "The motion capture data may be copied, modified, or redistributed without permission". 공식 포맷 asf/amc/c3d. BVH 변환본은 cgspeed 목록과 GitHub 미러(una-dinosauria/cmu-mocap), FBX 변환본은 Hugging Face(gbionics/cmu-fbx)에 있다고 검색 결과가 말하나 124_07 포함 여부는 미확인 | 캐릭터가 따로 필요(Quaternius CC0 등)하고 리타겟(뼈 이름 대응)과 배트 부착을 직접 해야 함. 품질 위험: 발 미끄러짐, 손 위치 |
| 외부 판매처 B의 타자 모델 상품 | 캐릭터 + 동작 9개(대기·타격·헛스윙·준비·달리기 등) | 표시가 유료(조회 시점) | 판매처 계정 | 형식에 FBX 표시 → 전용 편집기 없이 FBX로 받을 수 있을 가능성. 동작이 우리 3종(idle/contact/miss)과 대응 | FBX에 애니메이션 포함 여부 미확인 |
| 판매처 B의 무료 야구 동작 묶음 | 동작 11개(pitching, batting, catching, swinging, wind-up 등) | 무료 | 판매처 계정 | 형식이 게임 엔진 전용 | FBX로 꺼내려면 그 엔진 설치 필요(수십 GB). 비실용 |
| Sketchfab "Animated baseball player"(JohnyxTR, 2018) | 저폴리 손그림 캐릭터, 2k 삼각형, 애니메이션 포함 | 무료 | Sketchfab 계정 | 라이선스 CC Attribution, 758회 내려받음 | 동작 목록·리깅 품질 미확인 |
| Meshy Text to Motion | AI로 스윙 생성 + 자동 리깅, FBX/GLB 내보내기 | 크레딧(무료 구간 있음) | Meshy 계정 | 라이브러리에 Baseball Pitching(Pro)만 있고 타격은 없음. 테니스 데모처럼 글로 스윙을 생성하는 방식 | 결과 품질과 상업 사용 조건 미확인 |

판단: 사람 로그인 10분이 가능하면 Mixamo(무료, 야구 전용 클립)가 1순위. 돈을 쓰더라도 확실한 걸 원하면 위 유료 후보(FBX, idle/hit/miss 포함)가 2순위. 로그인·결제 없이 전부 Claude가 하려면 CMU 124_07 + Quaternius 캐릭터(둘 다 무료)지만 리타겟 작업과 품질 위험이 붙는다. 헛스윙 전용 클립이 없어도 같은 스윙을 재사용해도 된다(실제 타자의 몸동작은 접촉 여부와 거의 같다).

## 7. 단위 1 결과: 독립 데모 (2026-11-08 15:05~15:35 KST)

사용자가 Mixamo에서 받아 전달한 FBX 4개로 glb 하나를 만들고, 진행률 제어 모듈과 독립 데모로 타자 1명·스윙 2종을 눈으로 확인했다. 호스트(relay) 파일·`data/`·호스트 연결·공개 배포·발신 변경 0. CHECKLIST 상단 `EXHIBIT-batter3d-1` 블록에 등록.

### 파일

| 경로 | 역할 |
|---|---|
| `batter3d.js` | 모듈. `createBatter3D(container, opts)`, `setSide / setTheme / setSwing(kind, k) / reset / resize / dispose`, 데모용 `setView / setBat / getState / sample`. 시계·타이머·Promise 체인 없음(로딩 제외), 모든 메서드 동기·예외 없음, 렌더는 호출 때만 |
| `demo.html` | 독립 데모. 호스트 run()을 흉내 내는 rAF(이 페이지가 시계), 진행률 슬라이더, 좌우·테마·열 폭(40/72/88/120/260px)·높이, 접촉 프레임 추정, 스윙 전 구간 표본, 메서드 예외 검사, 조절값 메타 저장 |
| `tools/fbx-to-glb.html` | 변환 도구. FBXLoader로 4개를 읽어 검사하고 캐릭터 + 클립(idle, contact, contact_hit, contact_hit1, contact_hit2, miss)을 GLTFExporter로 glb 하나에 담아 자산 서버에 저장 |
| `tools/asset-server.mjs` | 로컬 자산 서버(Node 내장 모듈만). `D:\pitcheezy_assets`를 127.0.0.1:8794에서 GET, `build/` 아래만 POST 저장. CORS는 localhost 출처만 |
| `vendor/` | three.js 0.187.0(MIT) 본체와 addons 8파일, LICENSE, README. 2.6 MB |
| `layout-mock.html`, `captures-20261108/` | 2절 모의 배치와 캡처 23장(560 KB) |
| `.gitignore` | `assets/`, `*.fbx`, `*.glb` 제외 |

자산(Git 밖): `D:\pitcheezy_assets\mixamo\Baseball_{Hit,Hit_1,Hit_2,Strike}.fbx`(SHA-256 `f395f753…`, `f33d2ff2…`, `6e16c8a2…`, `f6e1d54f…`, 각 FBX 7700 바이너리, With Skin, 텍스처 0). 변환 결과 `D:\pitcheezy_assets\build\batter.glb`(9,093,508 bytes = 8.67 MB, SHA-256 `4aa29d8d441a630f8a00dab893ff11dd1ae806f008ae9b7b4b0709ed3a511432`)와 `batter.meta.json`.

### 실행 명령과 결과

1. `python -m http.server 8790 --bind 127.0.0.1 --directory web/pitch-studio-home-mobile` (앱 launch "mobile-home-demo")와 `node web/pitch-studio-home-mobile/relay/batter3d/tools/asset-server.mjs 8794` (launch "batter3d-assets").
2. `http://localhost:8790/relay/batter3d/tools/fbx-to-glb.html` → 검사 → glb 저장 → 다시 읽기. 결과: 캐릭터는 Mixamo 기본 마네킹(메시 Beta_Surface·Beta_Joints, 삼각형 49,112, 뼈 129, 키 180.9 단위, MeshPhong 2종), 클립 mixamo.com 1개씩 30 fps(Hit 3.90 s, Hit_1 2.90 s, Hit_2 1.97 s, Strike 6.93 s, 각 53트랙). 다시 읽기에서 메시 2·삼각형 49,112·뼈 129·클립 6개 일치.
3. `http://localhost:8790/relay/batter3d/demo.html` → 아래 검사.

### 합격 기준 대조

| 기준 | 결과 |
|---|---|
| (1) contact·miss가 k 0→1에서 끊김 없이, reset으로 idle 복귀 | 통과. 호스트 run 흉내 480 ms에서 k 0.227(122 ms) → 0.504(244 ms) → 0.747(371 ms) → 끝·reset(573 ms 시점 확인). 연속 캡처 k 0.25/0.31/0.37/0.43(타격), 0.16/0.22/0.28(헛스윙) |
| (2) 좌우 × 두 동작 캡처, 스윙 전 구간 검사 | 통과(육안 + 수치). 캡처 `demo-R-idle-v1`, `demo-R-contact-k037-v1`, `demo-L-idle-v1`, `demo-L-contact-k037-v1`, `demo-R-miss-k0187-v1`, 연속 7장. 수치(21표본, 미터): 타격 발 최저 y 0.000·최고 0.384(스트라이드), 헛스윙 발 최저 −0.001·최고 0.203. 바닥 아래 0. 손 간격 대기 0.126 → 팔로스루 0.957(타격)/0.494(헛스윙): Mixamo 클립이 위 손을 놓는 동작이라 배트는 아래 손(왼손)에 붙였다. 메시 찌그러짐·글자 거울 없음(텍스처 없음). 배트 방향은 주먹 가로축(새끼→집게) 추정값으로 대기·접촉·팔로스루 모두 자연스러움 |
| (3) 라이트·다크 윤곽 | 통과. `demo-dark-R-idle`, `demo-dark-R-contact` |
| (4) 메서드 동기 예외 0 | 통과. 생존 중 잘못된 입력 10회 예외 0, ok 유지. dispose 뒤 6회 호출 예외 0, ok false, mode disposed, 캔버스 제거 |
| (5) 콘솔 오류 0, 외부 요청 0 | 통과. 콘솔 오류 0. 네트워크는 localhost:8790과 127.0.0.1:8794만(41건) |
| (6) 용량 기록 | glb 8.67 MB(목표 3 MB 미달, 기록만), 폴더 2.9 MB(벤더 2.6 MB). 축소는 후속: 49k 삼각형 감축, 중복 클립 제거, Draco/quantization |
| (7) B안 틀에서 식별 | 통과(육안). 88px 열 `demo-col88-R-idle/R-contact/L-idle/L-contact`, 72px 열 `demo-col72-R-miss`. 타자가 존 쪽을 향한다 |

접촉 프레임(배트 끝 속도 최대, 클립 앞 70% 안): contact 0.375, contact_hit1 0.500, contact_hit2 0.604, miss 0.171. 손 속도 기준(0.370/0.471/0.564/0.187)보다 배트 기준을 메타에 채택했다. 호스트 연결 시 시작 시각 = 비행 시간 − contactFrac × 스윙 길이.

### 토큰·시간 (앱 표시값만)

세션 문맥 379,126 → 535,321 토큰(이 단위 구간, 약 15.6만). 주간 Fable 한도 16% → 18%, 전체 모델 9%. 과금 총 토큰은 미측정. 시간 약 30분(자산 확인·모의 배치 25분은 4절).

### 미측정·다음 단위 후보

- 미측정: 휴대폰 fps, 감속 모션 경로, 호스트 연결, 실제 사람 외형(마네킹형). 60 fps·3 MB 목표는 숫자만 기록.
- 다음 단위 후보(승인 뒤): ① 호스트 최소 연결(renderZone의 side, playAnim의 swingBat 자리, cancelAnim의 reset, run() 슬롯, setTheme) + 실패 시 SVG 폴백, ② glb 축소(클립 정리·Draco), ③ 캐릭터 교체(글자 없는 사람형, 같은 Mixamo 리그면 클립 재사용), ④ GPT 검토 반영.

## 8. 단위 2 결과: 독립 데모 보완 + 원형 보존 경량화 (2026-11-08 18:2x~18:5x KST)

GPT가 단위 1의 파일·자산·브라우저 데모를 검토한 뒤 사용자가 지시한 7개 항목을 이 Claude 세션이 구현했다. 호스트 연결·캐릭터 교체·공개 배포·Song 저장소·Cloudflare·경기 자료 변경 0. 기존 FBX 4개·`batter.glb`·`batter.meta.json`은 바이트 그대로 보존(아래 SHA)하고 후보 `batter-indexed.*`를 새로 만들었다. CHECKLIST 상단 `EXHIBIT-batter3d-2` 블록.

### 변경 파일(검토용 고정 변경분, SHA-256)

| 파일 | SHA-256 | 바이트 | 바뀐 것 |
|---|---|---|---|
| `batter3d.js` | `300643222ed4bc1090c7facf01fecac82e0c5f231570e7f9966c338c43eb7171` | 18,735 | 초기화 실패 뒤에도 쓰는 필드를 생성자 첫머리에 전부 두고, 실패 시 `mode="init-failed"`. `getState()`는 try로 감싸 어떤 상태에서도 답한다(`error`, `gpu`(렌더러 geometry·texture·program 수), `batParts` 추가). 배트 재생성은 `disposeBat()` → `disposeTree()`가 Set으로 geometry·material을 모아 공유분(손잡이·손잡이끝 material)을 한 번씩만 해제. `sample(kind, k, {sole, soleFull})`가 스킨 적용 메시 최저점(발바닥)을 계산. `createBatter3D(..., {modelName})` 추가 |
| `demo.html` | `aa060069aea05c9d7c0eacd27e7b1b11f57811afb3f6dc5097268837c9e674df` | 28,301 | `?model=` 선택(build/ 목록에서), 기존/후보 비교(좌우×타격/헛스윙×중간/끝 + reset, 픽셀 차·뼈 위치 차·대조군), WebGL 실패 흉내, 배트 재생성 누수 검사, 발바닥 전체 정점 검증, 연출 기준 시점 추정이 `contactFrac`·`contactTime`을 같은 표본·같은 길이로 함께 갱신(구간 중점), 기존 `batter.meta.json`은 저장 금지(후보 메타에만) |
| `tools/fbx-to-glb.html` | `35768f07f47db14ee26269c25c56106bd0530489d1e0a0bbe9870789a59f2617` | 25,902 | 출력 이름(기본 `batter-indexed`)·기존 파일 덮어쓰기 금지(build/ 목록으로 확인, 확인 실패도 '있음' 취급), 비트 단위 동일 정점만 합치는 `indexExact()` + 되풀기 대조 `verifyIndexed()` + three `mergeVertices(1e-6)` 참고값, 저장 응답 실패(fetch 예외·non-2xx)는 즉시 중단(메타 저장 안 함), 저장 뒤 다시 읽어 glb·메타 SHA-256·바이트 대조, 손 속도 추정을 '연출 기준 시점 추정(handSpeed, 구간 중점)'으로 표기, `pattern` 속성 정규식 오류 수정 |
| `tools/asset-server.mjs` | `4d2a04e9af16090631d8dcbb532585ac8361ce95466bef14ab2d77310af9e72c` | 4,576 | `decodeURIComponent` 예외·NUL 문자 → 400, 요청 처리 예외 → 500 응답 후 계속 실행, 끊긴 업로드는 반쪽 파일 삭제 후 400, 읽기 스트림 오류 처리, `clientError` 400 |
| `captures-20261108/u2-*.png` | 14장(7자세 × 위 후보/아래 기존), 아래 표 | 110×350 | 캔버스를 패널색 위에 합성한 PNG |
| `README.md`(이 절), `CHECKLIST.md`(블록 2 추가·블록 1 경로 오타), 메모리 | — | — | 기록 |

`vendor/`, `layout-mock.html`, `.gitignore`, launch.json은 변경 없음. 기존 relay 파일·`data/` 변경 0.

### 자산 결과(Git 밖, D:\pitcheezy_assets\build)

| 파일 | 바이트 | SHA-256 | 비고 |
|---|---|---|---|
| `batter.glb`(기존) | 9,093,508 | `4aa29d8d441a630f8a00dab893ff11dd1ae806f008ae9b7b4b0709ed3a511432` | 단위 1과 동일, 변경 없음 |
| `batter.meta.json`(기존) | 2,961 | `d9df301ba6dcfef768f708d1d53be5eb70191bf8cb3156a9a4dc3c37f12ac6ff` | 변경 없음. contact의 `contactTime` 1.4417(손 기준)과 `contactFrac` 0.375(배트 기준)가 서로 다른 기준인 채로 보존됨(알려진 불일치, 후보에서 해소) |
| `batter-indexed.glb`(후보) | **2,727,816**(2.60 MiB = 2.73 MB) | `4b744d1cb01c815356020c83d40a0124c1f1b17b260f3b9229aeab7a51ac34db` | 기존 대비 30.0 %. 변환기가 저장 뒤 다시 읽어 바이트·SHA 일치 확인, 3번 버튼 재확인도 일치 |
| `batter-indexed.meta.json`(후보) | 4,694 | 데모 저장 뒤 값(변환기 저장 시점 4,221 bytes `3552e724…`, 데모에서 배트 기준 추정·조절값 저장으로 갱신) | `indexing` 통계, `output.glbSha256`, `contactNote` 포함 |

GPT 읽기 계산 약 2.73 MB와 실측 2,727,816 bytes(2.728 MB)가 일치한다. 구성(glb 안 bufferView 합):

| 구성 | 기존 | 후보 |
|---|---|---|
| 정점 속성(POSITION·NORMAL·TEXCOORD_0·JOINTS_0·WEIGHTS_0, 정점당 56 B) | 8,250,816 (정점 147,336) | 1,588,944 (정점 28,374) |
| 인덱스(Uint16) | 0 | 294,672 |
| 애니메이션 6클립(idle 2,112 / contact 126,508 / contact_hit 126,508 / contact_hit1 95,048 / contact_hit2 64,700 / miss 159,984) | 574,860 | 574,860(동일) |
| JSON 청크(노드 132, extras 132) | 259,548 | 261,056 |
| 삼각형 | 49,112 | 49,112(동일) |

인덱스화: Beta_Surface 84,816 → 15,901, Beta_Joints 62,520 → 12,473(각 87 ms·57 ms). 인덱스를 되풀어 원본과 전 속성 비트 단위 대조 "일치", three `mergeVertices(1e-6)` 참고값도 같은 수. 삼각형 감축·압축·새 자산 구매 없음.

### 검사 결과(지시 항목별)

| 항목 | 결과 |
|---|---|
| 1 연출 기준 시점 재추정 | 후보 메타에 `contact` k 0.360417 / t 1.405625 s(길이 3.9000 s), `miss` k 0.172917 / t 1.198889 s(6.9333 s), `contactBy: batTipSpeed`, `contactNote`에 "실제 공 접촉 시각이 아니다" 명시. 같은 240표본의 구간 중점과 모듈이 가진 클립 길이로 둘을 함께 계산. 단위 1의 0.375는 끝점 귀속·당시 배트 부착 설정의 값이라 숫자가 다르다(둘 다 연출용 추정) |
| 2 WebGL 실패·배트 재생성 | `getContext`가 null을 돌려주게 바꾼 뒤 생성: `ok=false mode=init-failed error="THREE.WebGLRenderer: Error creating WebGL context."`, 메서드·getState·sample 11회 호출 예외 0, 캔버스 잔류 0(three 자체의 console.error 1줄은 의도한 실패의 출력). dispose 뒤 8회 호출 예외 0, getState 정상. 배트 재생성 60회: gpu geometries 6→6, programs 3→3, textures 3→3(기존·후보 모두) |
| 3 변환기 저장 실패 중단·해시 대조 | 저장 요청 예외/비 2xx는 `postOrAbort`가 throw → "중단(오류)" 로그, 메타 저장 생략. 정상 경로: 보낸 glb·메타의 SHA-256과 다시 읽은 바이트·SHA 대조 "일치"(위 표). 첫 빌드(18:39)는 27,872,320 bytes로 **커졌는데**, 원인은 원본 geometry를 `userData`에 보관한 것을 GLTFExporter가 extras로 JSON 직렬화(JSON 청크 25.4 MB)한 것 → Map 보관으로 수정하고 그 파일은 삭제, 두 번째 빌드(18:41)가 위 후보 |
| 4 자산 서버 | 수정 전 서버에 `%E0%A4%A` 요청 → `URIError: URI malformed`로 **프로세스 종료**(앱 로그 확인, GPT 지적 재현). 수정 후: `%E0%A4%A`·`%zz`·`%00`·`/../../Windows/win.ini`(`--path-as-is`)·`%2e%2e` 전부 `400 bad path`, 이어진 `/build/` 목록 200, build 밖 POST 403, PUT 405, 없는 파일 404, 외부 Origin에는 `Access-Control-Allow-Origin: null` |
| 5 원형 보존 경량화 | 위 자산 표. 기존 3파일 SHA 불변, 후보는 새 이름 |
| 6 기존/후보 비교 | 같은 열(88 px, DPR 2 → 110×350 버퍼 38,500 px)에서 우타·좌타 × contact·miss × k(연출 기준·1.0) 8자세 + reset 2 = 10자세 전부 **픽셀 차 0/38,500**, 뼈·배트 끝 위치 최대 차 0.000 m, reset 뒤 kind null·k 0 양쪽 동일. 대조군(위 contact 연출 기준 vs 아래 idle) 픽셀 차 4,207 → 측정 유효. 캡처 7쌍 PNG는 쌍마다 SHA-256까지 같다 |
| 6 발 뼈 표본 vs 발바닥 | **발 뼈(관절) 표본**(LeftFoot·RightFoot·ToeBase 월드 y, 21표본): contact 최저 0.000·최고 0.384 m, miss 최저 −0.001 m. **발바닥(스킨 적용 메시 최저점)**: contact 최저 −0.0009 m(k 1.0), miss 최저 −0.0017 m(k 0.25), idle(k 0) 0.0042 m. 즉 관절 기준으론 바닥 아래 0이지만 메시 기준으론 최대 1.7 mm 파고든다(눈에 띄지 않는 수준, 기록만). 바인딩 자세 낮은 8 % 정점(후보 3,802개 / 기존 20,114개)만 본 값과 전체 정점(28,374 / 147,336)을 본 값이 k 0·연출 기준·1.0 × contact·miss 6자세 모두 일치. 기존·후보 수치 동일 |
| 7 기록·고정 | 이 절 + CHECKLIST `EXHIBIT-batter3d-2`. 커밋·push 없음(사용자 결정 대기) |

### 캡처(`captures-20261108/`, 각 110×350, 위=후보 batter-indexed, 아래=기존 batter)

`u2-R-contact-cue0360`, `u2-R-contact-end`, `u2-L-contact-cue0360`, `u2-L-contact-end`, `u2-R-miss-cue0173`, `u2-L-miss-end`, `u2-R-reset-idle` × `-top-indexed.png` / `-bottom-existing.png`. 쌍 SHA-256(동일): 132d552b… / 024f5ec3… / 89c969d9… / 23caad52… / 0e294f6e… / c214c1b0… / f76b5769….

### 발견 사항(결함 아님, 다음 단위 참고)

- **contact 클립(Baseball_Hit 3.9 s)의 끝은 타자가 1루 쪽으로 달려 나가는 동작**이라 k ≈ 0.85 이후 화면 밖이다(머리 x: k 0.8 −0.55 m → 0.9 −0.97 m → 1.0 −1.73 m, 접지 원은 원점에 남음). `u2-*-contact-end` 캡처에 접지 원만 보이는 이유. 호스트 연결 때는 스윙 구간을 k ≤ 0.8쯤으로 자르거나 짧은 contact_hit1(2.9 s)·contact_hit2(1.97 s)를 쓰는 결정이 필요. miss 클립은 끝까지 화면 안.
- 후보 glb의 JSON 청크 261 KB(FBX에서 온 노드 extras)와 중복 클립 `contact_hit`(=`contact`, 126,508 B)는 다음 경량화 후보(원형 보존 범위 안). Draco·삼각형 감축은 이번에 하지 않았다.
- 자산 서버는 Range를 지원하지 않는다(개발용).

### 실행 명령

1. 자산 서버 재시작(앱 launch "batter3d-assets" = `node tools/asset-server.mjs 8794`; 수정 전 프로세스는 위 4번 재현으로 종료돼 있었음), 정적 서버 launch "mobile-home-demo"(8790).
2. `http://localhost:8790/relay/batter3d/tools/fbx-to-glb.html` → 1 검사 → 2 빌드(출력 `batter-indexed`, 인덱스화 켬, 덮어쓰기 끔) → 3 다시 읽기.
3. `http://localhost:8790/relay/batter3d/demo.html?model=batter-indexed` → 상태 / 스윙 전 구간 표본(contact·miss) / 발바닥 전체 정점 검증 / 메서드 예외 검사 / 배트 재생성 누수 검사 / WebGL 실패 흉내 / 연출 기준 시점 추정(contact·miss) → 조절값을 메타에 저장 / 기존/후보 비교 → 콘솔에서 `__pz.dispose()`. `?model=batter`로 기존 모델도 표본·예외·누수 검사.
4. 서버 검사는 curl(`--path-as-is`) 7건.

### 토큰·시간 (앱 표시값만)

세션 문맥 137,627(요약 직후) → 281,646(문서 작성 전) → 311,963 토큰(기록 완료 후), 주간 Fable 한도 18 % → 20 %, 전체 모델 10 % → 11 %. 과금 총 토큰 미측정. 시간 약 35분.

### 미측정

휴대폰 fps, 감속 모션 경로, 호스트 연결, 사람다운 외형, 320 px 실기기. 후보 glb의 Draco/quantization 효과(하지 않음).

## 9. 단위 3 결과: 호스트 최소 연결 (2026-11-08 20:1x~21:xx KST)

사용자 지시 5항목(정점 속성 보존 확인 → 체크포인트 커밋 → 후보 모델 최소 연결 + SVG 대체 보존 → 클립 비교·선택 → 실제 호스트 검증). 팀원 저장소·Cloudflare·경기 자료(`data/`) 변경 0. 추가 경량화는 보류.

### 9.1 정점 병합이 모든 속성을 보존하는지 (`tools/verify-glb-attrs.mjs`, Node 전용·의존 없음)

```
node tools/verify-glb-attrs.mjs D:\pitcheezy_assets\build\batter.glb D:\pitcheezy_assets\build\batter-indexed.glb
```

후보의 각 속성을 indices로 되풀어 원본과 **요소별 바이트** 대조(componentType·type·normalized·min/max 포함).

| 메시 | 속성(둘 다 동일 집합) | 원본 요소 | 후보 정점 | 되풀기 비교 |
|---|---|---|---|---|
| Beta_Surface(mesh0) | JOINTS_0 VEC4/u16, NORMAL VEC3/f32, POSITION VEC3/f32, TEXCOORD_0 VEC2/f32, WEIGHTS_0 VEC4/f32 | 84,816 | 15,901 (Uint16) | 5속성 전부 일치, 중복 정점 0 |
| Beta_Joints(mesh1) | 같음 | 62,520 | 12,473 (Uint16) | 5속성 전부 일치, 중복 정점 0 |

스킨 2(joints 65/64 이름 순서·inverseBindMatrices 바이트 일치), 애니메이션 6(채널 53, 대상·보간·키프레임 바이트 일치), materials JSON 일치, nodes 132 일치. **문제 없음 → 수정 불필요.** JSON 청크 259,548 → 261,053 B(indexing 메타), BIN 8,833,932 → 2,466,732 B.

### 9.2 체크포인트 커밋(push 없음)

> 2026-11-12 덧붙임: 이 커밋은 로컬 전용이다. push하지 않았고 공개 저장소에는 모델 파일(.glb)이 없다. 아래 `.gitignore` 예외 설명은 그 로컬 커밋의 것이고, 지금 `web/pitch-studio-home-mobile/` 아래의 무시 규칙은 모든 `.glb`·`.fbx`를 막는다.

`5191357` feat(exhibit): batter3d local demo checkpoint (units 1-2) with indexed candidate model — 22파일, 브랜치 `claude/mobile-home-demo-1103`(기준 main `d320316`).
포함: `relay/batter3d/`의 모듈·데모·배치 모의·변환기·자산 서버·README·vendor(three 0.187.0 + LICENSE)·`.gitignore`, **후보 모델 `assets/batter-indexed.glb`(2,727,816 B, SHA `4b744d1c…`) + `.meta.json`(4,694 B, SHA `e55fc807…`)**, `CHECKLIST.md`(단위 1·2 블록 4줄).
제외: 검증 캡처 전체, 11.6 MB mp4, 호스트 relay 파일(`index.html`·`relay.js`·`relay.css`·`data/`·NOTES·GPT 프롬프트), songapp-mock, docs/outputs 미추적분.
`.gitignore` 예외는 후보 한 쌍만(`assets/*` 제외 뒤 `!assets/batter-indexed.*`); Mixamo FBX 원본·기존 `batter.glb`(9.09 MB)는 계속 Git 밖(D:). 후보 복사본 SHA는 D: 원본과 동일 확인.
Git blob: batter3d.js `ce6f37da…`, demo.html `a5f6b3f7…`, fbx-to-glb.html `f004bc3d…`, asset-server.mjs `f4ea8219…`, batter-indexed.glb `a9b67cc7…`. (autocrlf 경고: 작업본 LF 파일 SHA는 체크아웃 설정에 따라 달라질 수 있어 blob id를 함께 적음)

### 9.3 클립 비교와 선택 (측정, 이름으로 결정하지 않음)

데모(`demo.html?model=batter-indexed`, 캔버스 110×350)에서 좌·우 × 4클립을 1/60 간격으로 재생하며 몸통 뼈(Hips·Head·양발)의 화면 좌표(NDC |x|)와 실루엣 픽셀 수를 쟀다. 발견: **contact(Baseball_Hit)·contact_hit1·contact_hit2 셋 다 끝부분에서 타자가 1루로 달려 나가 화면 밖**이다. 헛스윙(miss)만 전 구간 화면 안.

| 클립(원본 길이) | 연출 기준 시점 cue(배트 끝 속도 최대) | 변환기 handSpeed 값 | 몸통 이탈 시작(k, 초) R / L | cue 뒤 몸통 최대 \|x\|(안전 구간) |
|---|---|---|---|---|
| contact 3.90 s | k 0.360417 · 1.406 s | 1.4375 s | 0.833·3.25 s / 0.883·3.45 s | ≤ 0.64 (~2.7 s까지) |
| contact_hit1 2.90 s | **k 0.502083 · 1.456 s** | 1.3625 s | 0.867·2.51 s / 0.867·2.51 s | **≤ 0.51 (~2.3 s까지)** |
| contact_hit2 1.97 s | k 0.497917 · 0.979 s | 1.1042 s | 0.900·1.77 s / 0.850·1.67 s | ≤ 0.62 (~1.4 s까지, 팔로스루 0.4 s뿐) |
| miss 6.93 s | k 0.172917 · 1.199 s | — | 없음 / 없음 | ≤ 0.71 전 구간, 6.9 s에 대기 자세로 복귀 |

자세 시트(`captures-20261108/u3-pose-sheet.png`, `u3-zoom-R.png`, `u3-zoom-L.png`): hit1의 cue(1.456 s)는 좌·우 모두 배트가 플레이트 쪽으로 수평 뻗은 접촉 자세, contact의 cue(1.406 s)는 배트가 아래로 향하고 1.5 s에야 수평. 팔로스루도 hit1이 몸통 이동이 작다.
**선택:** 타격·파울·파울팁 = `contact_hit1`, 헛스윙 = `miss`. 둘 다 **재생 구간을 제한**한다(원본 클립은 그대로, 호스트가 구간만 재생):

| 연출 | 클립 원본 길이 | 재생 구간(원본 시간) | cue(공 도착) | cue 앞 구간 | cue 뒤 팔로스루(원속도) |
|---|---|---|---|---|---|
| contact | 2.9000 s | 0 → 2.10 s (k 0 → 0.7241) | 1.456042 s (k 0.5021) | 공 비행 시간(560~900 ms)에 맞춰 1.6~2.6배 빠르게 | 0.644 s |
| miss | 6.9333 s | 0 → 2.45 s (k 0 → 0.3534) | 1.198889 s (k 0.1729) | 같은 방식 1.3~2.1배 | 1.251 s |

cue 재검증: 데모와 같은 방법(240표본, 구간 중점, 앞 70 %)으로 후보 모델에서 다시 계산한 값이며, 메타의 handSpeed 값과 0.09 s 차이(3프레임)가 있어 **배트 끝 속도 기준을 쓰고 둘 다 기록**했다. 모두 '연출 기준 시점 추정'이며 실제 공 접촉 시각이 아니다. 끝 지점(2.10/2.45 s)은 동작 속도가 거의 0이 되는 지점(뼈 편차 정체 구간)으로 골랐다.

### 9.4 호스트 연결 구조(최소)

| 파일 | 변경 | 핵심 |
|---|---|---|
| `relay/index.html` | +4줄 | import map(`three` → `./batter3d/vendor/three.module.js`, `three/addons/`), `<script type="module" src="batter3d-host.js">` (relay.js defer 뒤) |
| `relay/batter3d-host.js` | 신규 6,600 B | 어댑터 모듈: `createBatter3D(assets/batter-indexed)` → ok·mode·클립/구간 검사 → `window.PZRelay.attach3D(api)`. 실패(로딩·초기화·검사·attach)마다 상자 제거·dispose, `PZBatter3D.status().last`에 사유. 캔버스 `webglcontextlost`를 받아 즉시 `detach3D`(9.7). `?batter3d=off`/`?batter3d=<이름>` 검증용. ResizeObserver 1개 |
| `relay/relay.js` | 692 → 739줄 | `S.anim.raf3d` 슬롯, `run(..., slot)`, `cancelAnim`이 3D도 끊고 reset, `renderZone`→`b3Show(side)`(상자를 서 있는 쪽 띠로 이동·has3d/side-l/side-r·setSide·setTheme·resize·reset), `playAnim`에서 3D면 `api.swing(kind, flightMs)`로 rAF 구동(연출 중 3D가 멈추면 그 프레임에서 detach + SVG 스윙), 연출 중 attach는 전환을 다음 투구로 미룸, `setTheme` 훅, 4c절 `attach3D/detach3D/b3Show`, `window.PZRelay` |
| `relay/relay.css` | +7줄 | `.zone-row.has3d.side-l/.side-r` 열 88px(359px 이하 `--wide3d` 72px)·반대쪽 0, `.bat3d` 상자, has3d일 때만 `.batter` 숨김 |
| `relay/batter3d/batter3d.js` | +3/−1줄(단위 2 고정본 수정) | `disposeInternal`: 스켈레톤 뼈 텍스처 `skeleton.dispose()`, `renderer.dispose()` 뒤 문맥이 살아 있으면 `forceContextLoss()`(9.7 지적 3) |

결과 판정(`ANIM_OF`·`animPlan`)·공 연출·자막은 변경 없음. 3D는 `plan.swing`일 때 `plan.kind === "miss"` → miss, 그 밖(foul·tip·inplay) → contact. 감속 모션·탭 숨김·위치 없음·스위치 꺼짐은 기존대로 스윙 없음(3D는 대기 자세). 스윙 끝 자세는 다음 투구(renderZone → cancelAnim → reset)까지 유지.

### 9.5 실제 호스트 검증(`http://localhost:8790/relay/`, 브라우저 탭을 앞에 둔 상태)

주의: 탭이 뒤에 있으면 rAF가 1 Hz로 묶여(간격 1,000 ms 실측) 연출 시작이 늦어 보인다. 앞 탭에서 rAF 간격 중앙값·최대 17 ms.

| 검사 | 결과 |
|---|---|
| 부착 | mode webgl, 상자 88×320 CSS px, 캔버스 110×400(dpr 1.25), SVG `.batter` display none, 열 `88px 1fr 0`(좌타) / `0 1fr 88px`(우타), 콘솔 오류 0 |
| 좌·우 × 헛스윙·타격·파울 6회 | 첫 프레임 ≤31 ms, 공 도착 시 k = 0.497/0.488/0.483/0.5015(기대 0.5021, 25 ms 표본 오차 ±0.018)·0.1678/0.1712(기대 0.1729), 끝 k 0.7241/0.3534 정확, 끝 자세 유지, 상자가 bat-right/bat-left로 이동, 자막(삼진 헛스윙·홈런·파울·타구 아웃) 그대로 |
| 안 치는 공(볼·루킹) | 3D kind null 유지(스윙 없음) |
| reset | 투구 바꿀 때마다 kind null·k 0 확인(idle) |
| 연속 재생 30회(120 ms 간격, 스윙 중 끊기) | 미해결 rAF 0, 캔버스 1, 상자 1, geometries 6→6·programs 3→3·textures 3→3, 리스너 순증 0 |
| 화면 진입·이탈 20회(라인업↔중계) | 상자 0 ↔ 88 px 20쌍 전부, 미해결 rAF 0, gpu 불변, 리스너 순증 0, 부착 유지 |
| 모델 로딩 실패(`?batter3d=nope`) | 부착 안 됨, 상자·캔버스 0, SVG 보임·열 40px, SVG 스윙 클래스 동작, 예외 0(404 콘솔 2건은 의도) |
| WebGL 실패 흉내(getContext null → init) | init null, 사유 "초기화 실패: init-failed …", SVG 유지, 예외 0(three.js 오류 로그 1건 의도) → 복구 init 뒤 부착 |
| 수동 해제(detach3D) → 재연결 | SVG 복귀 → init으로 재부착, gpu 동일 |
| 실제 문맥 상실(`WEBGL_lose_context`) | 다음 투구의 b3Show에서 ok()=false → detach → SVG, 재연결 가능 |
| 애니메이션 스위치 끔 | 스윙 투구에서도 kind null(대기 자세), 켜면 다시 연출 |
| 테마 | 어둡게 전환 시 3D theme dark(조명 변경) 캡처 |
| 375 px / 320 px | 열 88 / 72 px, 상자 88×320 / 72×262, 캔버스 110×400 / 90×327 |

캡처: `captures-20261108/u3-host-desktop-L-idle-light.jpg`, `u3-host-375-L-idle-light.jpg`, `u3-host-375-R-hit-end-light.jpg`, `u3-host-375-L-hit-end-dark.jpg`, `u3-host-320-L-hit-end-dark.jpg`(스크린샷, 소프트웨어 렌더 환경).

### 9.6 남은 한계(이번 단위에서 해결하지 않음)

- **끝 자세 → 다음 투구 컷**: 스윙 뒤 자세를 유지하다 다음 투구에서 대기 자세로 바로 바뀐다(되돌아오는 동작 없음; Mixamo 클립이 달려 나가므로). 자동 진행 10 s에서는 약 7 s 동안 끝 자세.
- cue 앞 구간을 공 비행 시간에 맞춰 1.3~2.6배 빠르게 재생한다(원속도 아님). 스윙 본동작 0.1~0.15 s로 실제 스윙 시간대와 비슷하지만 대기 동작이 빠르다.
- 픽셀 비율은 생성 때 값으로 고정된다(모듈 `resize`가 dpr 재설정 안 함): 데스크톱 확대·모니터 이동 뒤 흐려질 수 있음. 실기기는 dpr 고정이라 영향 없음.
- 감속 모션(prefers-reduced-motion)은 에뮬레이션 수단이 없어 **미측정**(코드 경로는 스위치 끔과 같이 playAnim이 스윙 전에 반환).
- 휴대폰 실기기 fps·발열·2.7 MB glb + 2.1 MB three.js 첫 로딩 시간 미측정(로컬 서버만). 구형 브라우저(import map·type=module 미지원)는 SVG로만 동작하며 실기기 확인 없음.
- `detach` 때 `console.info` 1줄을 남긴다(오류 아님). 실제 문맥 상실 때는 three.js의 `Context Lost.` 로그(log 수준)도 1줄 남는다.
- 어댑터 PLAY 값은 후보 모델 기준이며 다른 모델(`?batter3d=<이름>`)에서는 클립 길이 검사만 한다(cue 재추정 없음).

### 9.7 독립 읽기 검토(Workflow, 검토 2 + 반박 검증 3 = 에이전트 5, 소비 521,776 토큰, 13.8분)와 반영

같은 Claude(Fable 5.1) 세션의 하위 에이전트가 읽기 전용으로 검토한 것이라 **GPT의 다른 모델 검토를 대신하지 않는다**(규칙 유지). 지적 5건(중복 1건 포함) 중 상위 3건을 반박 검증했고, 2건 확인·1건은 "검증 중에 이미 고쳐짐"으로 판정됐다. 전부 반영 뒤 재검증.

| # | 지적(심각도) | 반영 | 재검증(앞 탭, 20~25 ms 표본) |
|---|---|---|---|
| 1 | WebGL 문맥 상실 뒤 `has3d`가 남아 다음 투구까지 **타자가 아무것도 안 보임**(중간→검증자 판정 낮음) | 어댑터가 캔버스 `webglcontextlost`를 받아 즉시 `detach3D("WebGL 문맥 상실")` | 연출 도중 `loseContext()` → 23 ms 안에 해제·SVG 표시·상자 0 |
| 2 | 연출 도중 3D가 멈추면(guard 실패 등) 그 투구에 스윙이 없음; `detach3D`가 raf3d를 안 끊음(낮음) | `playAnim`의 3D frame을 감싸 `ok()` 아니면 그 프레임에서 `detach3D` + `swingBat(side)`; `detach3D`는 api 없으면 조용히 반환(두 번 불려도 안전) | 위 시험에서 같은 23 ms 표본에 SVG `.swing` 클래스 켜짐(SVG 스윙으로 이어짐) |
| 3 | 자료가 먼저 오고 glb가 늦게 와 **연출 중 attach**되면 예약된 SVG 스윙이 숨겨진 채 돌아 그 투구에 스윙이 안 보임(낮음, 2명 중복 지적) | `attach3D`에서 연출 진행 중(`raf`·`raf3d`·타이머)이면 api만 저장하고 전환은 다음 `renderZone`으로 미룸 | 헛스윙 투구 클릭 직후 `init()`: 177 ms에 부착되지만 `has3d` 없음, SVG 스윙 554→1,033 ms 표시, 다음 투구에서 3D 전환·miss 재생 |
| 4 | `disposeInternal`이 문맥을 잃게 하지 않고 스켈레톤 뼈 텍스처도 안 지워 **해제·재연결 반복 시 WebGL 문맥 누적**(약 16개에서 브라우저가 가장 오래된 문맥을 잃게 함)(낮음) | 모듈 `disposeInternal`에 `skeleton.dispose()` + 문맥이 살아 있을 때만 `forceContextLoss()` | 해제·재연결 20회: 이전 캔버스 20/20 `isContextLost()` true, "Too many active WebGL contexts" 경고 0, 캔버스 1, geometries 6·programs 3 불변; 이미 잃은 문맥에는 부르지 않아 경고 0(처음 구현에서 1건 나와 수정) |

재검증 뒤 정상 타이밍 재확인: 우타 타격 첫 프레임 27 ms·도착 k 0.4991·끝 0.7241, 좌타 헛스윙 첫 프레임 26 ms·도착 k 0.1714. 페이지 예외 0.

### 9.8 고정 변경분(단위 3, 미커밋)과 토큰

| 파일 | 크기 | SHA-256(앞 16) |
|---|---|---|
| `relay/index.html` | 11,054 B | `18d790a4ac6e3105` |
| `relay/relay.js` | 56,004 B | `621d21c08781d549` |
| `relay/relay.css` | 25,779 B | `483cb301025b2b42` |
| `relay/batter3d-host.js`(신규) | 6,600 B | `3e3b3183f9c55494` |
| `relay/batter3d/batter3d.js`(체크포인트 `ce6f37da…` 대비 +3/−1) | 19,310 B | `bc7af493ba9d6165` |
| `relay/batter3d/tools/verify-glb-attrs.mjs`(신규) | 11,545 B | `dd245d8d6199c26a` |

캡처 8장 추가(`captures-20261108/u3-*`, 폴더 45장 1.6 MB, Git 밖).

**토큰·시간(앱 표시값만):** 세션 문맥 190,422(단위 3 착수) → 386,401 토큰(기록 완료 직전), 주간 Fable 한도 21 % → 25 %, 전체 모델 11 % → 13 %. 독립 검토 Workflow 하위 에이전트 521,776 토큰 별도. 과금 총량 미측정. 20:1x~21:3x KST.

### 9.9 사용자 추가 FBX 확인 (2026-11-08 21:3x KST, 다음 단위 참고)

사용자가 올린 `Baseball_Hit_4.fbx`(488,096 B, SHA `66455c9969ded0c9…`)를 `D:/pitcheezy_assets/mixamo/`에 복사(기존 4개는 그대로)하고 FBXLoader로 열었다: **메시 0·재질 0·텍스처 0**, 뼈 65(접두어 `mixamorig1`, 기존 캐릭터는 `mixamorig`), 클립 1개 1.967 s(= Baseball_Hit_2와 같은 길이·53트랙). 즉 Mixamo에서 **"Without Skin"으로 받은 동작 전용 파일**이라 캐릭터(외형)로는 쓸 수 없다. 동작으로 쓰려면 뼈 이름 접두어를 바꿔 리타겟해야 하고, 캐릭터를 바꾸려면 그 캐릭터로 클립 4개를 **"With Skin"**으로 다시 받아야 한다(변환기는 `mixamo/Baseball_Hit.fbx`에서 캐릭터를 읽음 → 다음 단위에서 입력 폴더/접두어 선택 추가 필요).

### 9.10 타자 크기 키우기 (2026-11-08 21:4x KST, 사용자 요청)

100×320 px 틀(데모 스테이지를 호스트 열 크기로 바꿔 측정)에서 카메라 zoom별로 대기·타격(cue, +0.3 s, 끝)·헛스윙(cue, 1.5 s, 끝) × 좌·우 14자세를 쟀다.

| zoom | 대기 자세 키 / 틀 높이 | 몸통 뼈 최대 \|x\| | 가장자리에 걸리는 자세(픽셀 수) |
|---|---|---|---|
| 1.0 | 40 % | 0.49 | 4자세, 배트 끝 ≤5 px |
| **1.5(채택)** | **60 %** | **0.74**(몸 안 잘림) | 8자세, 팔로스루 배트 ≤54 px |
| 1.8 | 72 % | 0.90(몸통이 가장자리에 닿기 시작) | 12자세, ≤111 px |
| 2.0 | 81 % | 1.00(몸 잘림) | 12자세, ≤227 px |

적용: `relay.css` 열 88→**100 px**(359 px 이하 72→**84 px**), `batter3d-host.js`에 `HOST_VIEW = { zoom: 1.5 }`(모델 메타의 view 위에 덮어씀, 메타 파일은 그대로). 375 px에서 열 100 px·상자 100×251(존이 235 px로 좁아져 높이도 320→251), 320 px에서 84×211. 캡처 `u3-big-375-L-idle.jpg`, `u3-big-375-R-hit-end.jpg`(팔로스루 배트 끝이 오른쪽 가장자리 밖, 의도), `u3-big-375-L-miss-end.jpg`, `u3-big-320-L-idle.jpg`. 타이밍 코드는 바뀌지 않았다(k 0.7241/0.3534 유지 확인).

### 9.11 스윙이 틀에 안 가리게 (2026-11-08 21:5x KST, 사용자 요청) + 첫 로딩 전환 수정

사용자: "스윙이 보더판에 가리는데 안 가리게". 9.10의 열 100 px + zoom 1.5는 팔로스루 배트가 열 가장자리에서 잘렸다. 해결: **캔버스를 격자 열보다 넓게(열의 2.6배, 375 px에서 260×251) 두고 열 가운데에 맞춰 양옆으로 넘치게** 한다(`position:absolute`, 투명 배경, `pointer-events:none`, `z-index:1`). 격자 열 폭(100/84 px)과 존 크기는 그대로, 밖으로 나간 부분은 `.zone-fig { overflow:hidden }`이 잘라 가로 스크롤이 없다(scrollWidth 375 = 뷰포트). 넓은 캔버스는 세로 기준 프레이밍이 되므로 zoom을 0.8로 낮췄다.

260×251·202×211 틀(375·320 px) × zoom 0.7~1.0 × 좌·우 9자세(대기·타격 cue/1.6/1.75/2.1 s·헛스윙 cue/1.3/1.5/2.45 s) 측정:

| zoom | 대기 키 / 틀 높이(375 px) | 배트 끝 최대 \|x\| | 가장자리 접촉 |
|---|---|---|---|
| 0.7 | 68 % (171 px) | 0.93 | 0 |
| **0.8(채택)** | **78 % (196 px)** | 1.07(240 px 폭 기준; 채택한 260 px 폭에서는 틀 안) | 240 px 폭에서 2자세 배트 끝 8~9 px → 260 px 폭에서 0(호스트 캡처로 확인) |
| 0.9 | 88 % | 1.22 | 4자세 |
| 1.0 | 98 % | 1.38 | 머리·발이 위아래에 닿음(17자세) |

호스트 확인(375 px): 상자 260×251(좌타 left −64 px, 우타 right 439 px → 그림 틀 밖은 잘림), 열 `100px 1fr 0`, 가로 스크롤 없음, 터치 통과. 320 px: 상자 218×209. 캡처 `u3-wide-375-L-idle-firstload.jpg`, `u3-wide-375-R-hit-end-final.jpg`(배트가 화면 오른쪽 끝까지 온전히 보임), `u3-wide-375-L-miss-end.jpg`, `u3-wide-320-R-foul-end.jpg`.

**함께 고친 것:** 9.7의 "연출 중 attach는 다음 투구로 미룸"이 첫 로딩에서 역효과를 냈다 — 자료가 먼저 와 1구 연출이 시작된 뒤 glb가 붙으면 사용자가 다음 투구를 누르기 전까지 3D가 안 보였다(21:5x 확인). `b3ShowWhenIdle()`: 연출(rAF·타이머)이 끝나는 대로 120 ms 간격 재확인 뒤 전환, 새 투구가 오면 cancelAnim이 그 타이머도 지운다. 확인: 첫 로딩 attach 557 ms → 1구 연출 끝난 778 ms에 has3d(클릭 없음); 연출 중 attach 재시험 attach 157 ms → SVG 스윙 555~1,039 ms 표시 → 1,185 ms에 3D 전환, 스윙 중 전환 0.

최종 SHA(작업본): relay.js `ae512da1858dc30c…`(56510 B, 745줄), relay.css `2ea92305c1f13f65…`(27067 B), batter3d-host.js `82d4e7832e714c0e…`(7059 B). 나머지(index.html·batter3d.js·verify-glb-attrs.mjs)는 9.8과 같다.

토큰(앱 표시값): 9.8의 386,401 → 455,809(9.10·9.11 포함, 기록 완료 직전), 주간 Fable 25 % → 26 %. 과금 총량 미측정.

## 10. 단위 4 착수: 사람형 캐릭터 교체 준비 (2026-11-08 22:0x KST)

사용자 요청 "사람으로 캐릭터 바꾸자". 캐릭터 자산은 로그인이 필요한 Mixamo에서 사용자가 받아야 하므로, 받기 전에 변환 경로를 준비해 두었다(파일이 오면 변환 → 데모 검사 → 호스트 `?batter3d=<이름>` → 좌우·크기·배트 위치 재측정 순서).

**변환기 변경(`tools/fbx-to-glb.html`, SHA `d694236d4cff80cf…`, 30,494 B):**
- 입력 폴더 칸(`#srcDir`, 기본 `mixamo`): 캐릭터별 하위 폴더(예 `mixamo/remy`)에 같은 4개 파일 이름(Baseball_Hit, Baseball_Hit_1, Baseball_Hit_2, Baseball_Strike)으로 두면 된다. 자산 서버 아래 경로만 허용.
- 파일을 fetch로 읽어 **SHA-256을 실측**하고 기존 마네킹 기록값과 같은지 표시; 메타 `source.dir`·`files[].sha256`·`sameAsMannequin`에 실제 값을 적는다(이전엔 상수).
- `FBXLoader.parse(buf, 기준경로)`로 바꿔 외부 텍스처 파일도 폴더 기준으로 찾는다(내장 텍스처는 blob).
- 검사 로그에 **텍스처 목록**(재질.슬롯, 크기, 내장/외부, transparent/alphaTest) 추가. 메타 `character.textures`.
- 텍스처 내보내기 옵션: 최대 변(원본/1024/512, GLTFExporter `maxTextureSize`), 형식(PNG / WebP=`EXT_texture_webp` / JPEG, `texture.userData.mimeType`). 기본 1024·WebP. 마네킹(텍스처 0)은 무관.

**검증:** 기존 마네킹 4개를 `mixamo/ybot-test/`에 복사해 새 경로로 검사·빌드 → 출력 glb **2,727,816 B, SHA `4b744d1c…` = 기존 후보와 바이트 동일**(경로 변경이 결과를 바꾸지 않음, 결정적 출력). 시험 산출물(`build/batter-ybot-test.*`)과 복사본은 삭제, 기존 파일 변경 0.

**사용자가 받아야 할 것(Mixamo, 로그인 필요):** 사람형 캐릭터 하나 선택 → Animations에서 Baseball Hit / Baseball Hit 1 / Baseball Hit 2 / Baseball Strike 4개 → Download: Format **FBX Binary(.fbx)**, Skin **With Skin**, Frames per Second 30, Keyframe Reduction none → D:\pitcheezy_assets\mixamo\<캐릭터>\ 폴더에 위 4개 이름으로 저장. 올려 준 `Baseball_Hit_4.fbx`는 Without Skin(메시 0)이라 캐릭터로 못 쓴다(9.9).

**미리 아는 위험:** 텍스처가 붙으면 glb가 커진다(1024 WebP 기준 1~3 MB 추가 예상, 미측정). 캐릭터마다 메시 여러 개·투명 재질(머리카락·속눈썹)이 있을 수 있어 alphaMode 확인 필요. 뼈 접두어가 `mixamorig1`이어도 모듈·변환기는 이름 끝으로 찾아 동작한다(Baseball_Hit_4에서 확인). 키 정규화(1.8 m)와 배트 부착(아래 손 뼈)은 자동이지만 배트 위치·회전은 데모 조절 패널로 다시 맞춰야 할 수 있다.

### 10.1 Mixamo 밖 캐릭터 후보 조사 (2026-11-08 22:1x KST, 내려받기·구매 없음)

사용자: "Mixamo에는 야구 사이트에 맞는 캐릭터가 마네킹뿐". 웹 검색 6회 + Sketchfab API(다운로드 가능 모델 58건) + 외부 판매처 상품 페이지 확인.

| 순위 | 후보 | 비용·라이선스 | 내용(상품 페이지 기재) | 우리 파이프라인에 넣는 길 | 위험 |
|---|---|---|---|---|---|
| 1 | 외부 구매 타자 모델 — 스토어 두 곳 | 스토어 두 곳에서 유료 판매(가격·등급은 비공개 기록) | 선수 + 헬멧·배트·공, 텍스처 포함, 사람형 리그, 타격·헛스윙·대기·준비 등 동작 9개 + 기준 자세, 수작업(모캡 아님), 제자리 동작, 미리보기 영상 있음 | (a) 패키지를 풀어 FBX·텍스처 추출 → 텍스처 PNG 변환 → 변환기(뼈 이름 대응표 필요, 배트는 자산에 포함) → 자체 클립 사용; (b) 기준 자세 FBX를 Mixamo에 올려 자동 리깅 → 지금 쓰는 Mixamo 4클립 그대로 | 구매는 사용자 결정(이 세션은 결제 안 함). 원본·변환본은 Git에 넣지 않는다. 애니메이션 품질은 영상으로 확인 필요 |
| 2 | Sketchfab CC-BY 저폴리: "Animated baseball player"(johnyxtr, 2018, 1,950면, 애니 1개) / "Baseball Player"(patrick.ambrose2840, 2022, 1,908면, 정지) | 무료, CC Attribution(출처 표기) | 손그림 저폴리, 리그·포즈는 받아 봐야 앎 | Sketchfab 계정(무료)으로 사용자가 받기 → T/A-pose면 Mixamo 자동 리깅 → 4클립 | 만화풍이라 "실사" 요구와 거리, 리그 품질 미확인 |
| 3 | AI 생성(Meshy 등) "baseball batter in uniform, T-pose" → 자동 리깅 | 무료 구간 CC BY 4.0, 상업은 유료 플랜(2026 페이지) | 품질 편차 큼 | 계정은 사용자, 결과 FBX → Mixamo 자동 리깅 → 4클립 | 손·얼굴 왜곡 흔함, 약관 재확인 |
| 4 | CC0 사람 베이스(Shyr Base Character itch, Quaternius Universal Base Characters, Blender Studio Human Base Meshes, MakeHuman) + 유니폼 텍스처 손질 | 무료 CC0 | 일반 인체 | Mixamo 자동 리깅 → 4클립 | 유니폼·모자가 없어 작업 많음, Blender 필요할 수 있음 |
| 제외 | CGTrader MLB 30개 팀 팩·Tampa Bay/Houston 캐릭터($75~, Editorial 라이선스), 실제 선수 모델(Ohtani 등) | — | 실제 구단 로고·선수 초상 | — | 상업·공개 사용 제한, 초상권 |

핵심: Mixamo의 캐릭터 목록이 아니라 **"Upload Character"(자동 리깅)**를 쓰면 어떤 사람형 메시든 지금의 Mixamo 야구 클립 4개를 입힐 수 있다(T/A-pose·단일 메시 권장, OBJ/FBX). 따라서 외형은 다른 데서 구하고 동작은 지금 것을 유지하는 길이 열려 있다.

### 10.2 결제 불가 → 무료·오픈소스 재조사 (2026-11-08 22:3x KST, 내려받기·계정 생성 없음)

Sketchfab API 재검색(91건, CC0/CC-BY만, 사람형·800~200k면 필터)·웹 검색 6회·TurboSquid(403 차단)·poly.pizza(사이트 허용 안 됨)·Ready Player Me 문서(허용 안 됨, 검색 결과로 대체).

| 길 | 무엇 | 비용·라이선스(확인한 범위) | 우리 쪽 작업 | 평가 |
|---|---|---|---|---|
| A. AI 생성(Meshy 무료 구간 또는 Hugging Face Space의 Hunyuan3D-2/TRELLIS) | 글·그림 → "흰 유니폼 타자, T-pose" 3D → (Meshy는 자동 리깅 포함) FBX/GLB | Meshy 무료 구간 산출물 CC BY 4.0(출처 표기, 상업 가능), Space는 각 모델 라이선스 | 사용자가 계정·생성 → FBX를 Mixamo "Upload Character"에 올려 야구 클립 4개 With Skin으로 받기(GLB면 내가 OBJ+텍스처 zip으로 바꿔 줌) → 지금 변환기 | **유니폼 입은 사람에 가장 가까운 무료 길**. 손·얼굴 왜곡·텍스처 번짐 흔함, 2~3번 재생성 각오. Mixamo 자동 리깅은 2025년부터 간헐 장애 보고 |
| B. Ready Player Me(무료 아바타 생성기) | 사실풍 스타일 사람 아바타, 옷 선택(운동복·티셔츠·바지; 야구 유니폼·모자는 없을 가능성), GLB 바로 내려받기 | 생성기 아바타는 비상업 CC(출처 표기), 상업은 무료 개발자 등록 필요(문서 요약) | GLB 뼈 이름이 Mixamo와 같고 접두어만 없다는 커뮤니티 보고 → 변환기에 SkeletonUtils 리타겟 추가해 Mixamo 업로드 없이 기존 4클립 적용(검증 필요) | **"사람"은 가장 빨리 됨(5분)**, 야구복은 아님. 뼈 호환은 받아 봐야 확정 |
| C. Mixamo 사람형 캐릭터 + 옷 텍스처 색 바꾸기 | Mixamo 기본 캐릭터(Ty·Brian·Remy·Jasper 등, Malcolm은 2022 삭제 보고)에 With Skin 4클립 → 내가 셔츠·바지 텍스처를 팀 색으로 | 무료(Mixamo FAQ) | 텍스처 영역 색 치환(UV를 보고 수작업) | 사용자가 "적합한 게 없다"고 판단한 길. 모자 없음 |
| D. Sketchfab 무료 | "Animated baseball player"(johnyxtr, 1,950면, CC-BY), "Baseball Player"(patrick.ambrose2840, 1,908면), "Baseball girl"(31k, 만화), "The Pitcher"(138k, 콘셉트 포즈) | CC Attribution | 받아서 T/A-pose면 Mixamo 자동 리깅 | 전부 만화·저폴리. 유니폼 입은 사실풍 사람은 **허용 라이선스로 0건** |
| E. MakeHuman/MPFB(CC0 인체) + Blender | 사실풍 인체 생성, 옷은 티셔츠·바지 수준(야구 모자·유니폼 자산 못 찾음) | CC0(공식 빌드 내보내기) | Blender 설치·헤드리스 스크립트·Mixamo | 작업 가장 많음 → 보류 |
| 제외 | TurboSquid 무료 athlete 모음(접근 403, 라이선스 미확인), Zepeto 내보내기(권리 불명), 실제 선수·구단 | — | — | — |

판단: 결제 없이 "유니폼 입은 사람"을 얻는 현실적인 길은 **A(AI 생성 → Mixamo 자동 리깅)**, "사람 느낌만 빨리"는 **B(Ready Player Me)**. 둘 다 계정·생성은 사용자(이 세션은 계정을 만들지 않음), 리깅·변환·연결·검증은 Claude.


## 11. 단위 4 결과 — 사람형 캐릭터(외부 구매 타자 모델) 교체 (2026-11-09)

사용자가 외부에서 구매한 모델 패키지를 Mac에서 내려받아 15 MB 조각 3개로 나눠 채팅으로 전달. 이 PC에서 합쳐 Git 밖 자산 폴더에 저장하고 풀었다(자산 폴더 밖 경로는 거부). **원본·변환본 모두 Git에 넣지 않는다**(`web/pitch-studio-home-mobile/` 아래의 무시 규칙이 모든 `.glb`·`.fbx`를 막는다. 예외는 `batter-indexed.meta.json` 하나이고 `git check-ignore`로 확인).

### 11.1 에셋 내용(검사, Node + three.js FBXLoader)

| 항목 | 값 |
|---|---|
| 동작 FBX(각각 스킨 메시 + 뼈 68 + 클립 1, 30 fps, 바이너리 7500) | 타격 2.1667 s, 헛스윙 3.3333 s, 대기 1.5 s, 준비 5.3333 s, 그 밖에 달리기·점프·슬라이드·걷기 2종(미사용) |
| 메시 | Body 43,692 정점(재질 구간 46, 재질 4: Skin·Clothes·Eyes·Corneas), Head 24,048, Helmet 3,894(Dummy_Helmet 뼈에 스킨), A-pose 파일에 Baseball_Bat 4,032(더미 뼈 1개에 가중치 1.0) |
| 뼈 이름 | Root, Pelvis, spine_01~03, neck_01, clavicle_l, Upperarm_L, lowerarm_l, Hand_L, 손가락, head, Thigh_L, calf_l, Foot_L, ball_l(+_r). `spine_03`·`neck_01`은 원본부터 같은 이름이 둘(자식 중복) |
| 키 | A-pose 183.2 단위(cm), 타격 자세 174.4 |
| 텍스처(TGA) | Skin·Clothes D/N/SP 2048², Helmet·Bat·Skin_Detail 1024², Eyes 512². FBX가 참조하는 것은 D(색)·N(법선)뿐(각막은 Skin_Detail_N을 bump로) |
| 배트 부착 | `Dummy_Baseball_Bat`은 **Hand_R의 자식**, 로컬 위치 (11.07, 3.01, 0.44), 회전 없음. 손잡이끝이 더미 원점에서 −20, 끝이 +65.2(길이 85.2, 더미 z축) |
| 타격 손 | 우타(대기 자세에서 왼손이 손잡이끝에 가까움: 배트 축 기준 L 7.4 / R 19.6). 에셋은 배트를 오른손(위 손)에 붙였고 타격 뒤 왼손을 놓는다(손 간격 최대 0.93 m) |
| 이동 | Hit_Ball: 골반 이동 ≤ 22 cm, 끝에서 원위치로 돌아오되 1.9 s부터 1루 달리기 시작(왼발 들림). Missing_Ball: ≤ 30 cm, 끝에서 타격 자세로 복귀. **마네킹처럼 화면 밖으로 달려 나가지 않는다** |

### 11.2 변환(변환기 `tools/fbx-to-glb.html` 'ctl' 프로필)

입력은 Git 밖 자산 폴더의 ctl 입력 폴더(동작 FBX 4 + A-pose 1, TGA는 PIL로 같은 이름의 PNG로 미리 변환 — 변환기는 `LoadingManager.setURLModifier`로 `.tga`→`.png`). 처리 순서: 뼈 이름을 모듈 규약으로(Pelvis→Hips, head→Head, Hand_L/R→LeftHand/RightHand, index/pinky_01→…Index1/…Pinky1, Foot→…Foot, ball→…ToeBase; 뼈 노드와 트랙 이름 모두) → 메시 노드 이름 `Mesh_` 접두(glTF에서 뼈 `Head`와 메시 `Head`가 겹치면 GLTFLoader가 뒤의 것을 `Head_1`로 바꿔 모듈이 머리 뼈를 못 찾는다 — 빌드 2에서 발견) → 전부 1.0인 정점 색 제거 → 같은 재질 구간 병합(Body 46→2, Head 4→3) → Phong→Standard(색 흰색, 금속성 0, 거칠기 재질별 추정값, 각막 투명 유지) → 전 속성 일치 정점 인덱스화(Body 43,692→8,803, Head →4,441, Helmet →754, 되풀기 대조 일치) → **실제 배트 이식**: A-pose 파일의 배트 스킨 메시를 더미 뼈 로컬 공간으로 굽고(스킨 식 `dummyW⁻¹·meshW·bindInv·dummyW·boneInverse·bind`, 가중치 1 단일 뼈) 캐릭터의 RightHand 아래 `Bat`(더미의 로컬 변환) 노드에 일반 Mesh로 달고 `BatTip`(0,0,65.2)·`BatKnob`(0,0,−20) 표지 추가. 모듈 원통 배트는 메타 `bat.enabled=false`로 끔 → 클립 contact·miss·idle·prepare(트랙 최적화: 마지막 키가 사라져 길이가 줄면 원본 유지) → 텍스처 최대 1024 px WebP → `build/batter-ctl.glb`.

| 산출물 | 값 |
|---|---|
| `batter-ctl.glb` | **2,979,472 B(2.84 MB)**, SHA-256 `4e5a0369…`(빌드 3; 마네킹 batter-indexed 2,727,816 B와 비슷). 다시 읽으면 primitive 7(Body 2, Head 3, Helmet, Bat), 삼각형 25,222, 뼈 67(glTF 조인트 기준) |
| `batter-ctl.meta.json` | 빌드 메타 + 데모 측정(아래) + 손 보정. `play`(호스트 재생 구간)·`bat.embedded`·`view.targetY` 포함 |
| 저장 뒤 대조 | glb·meta 둘 다 다시 읽어 SHA 일치 |

### 11.3 모듈·어댑터·데모 변경

- `batter3d.js`: 키 정규화 경계를 **스킨 메시만**으로(`skinnedBounds`; glb에 든 배트 메시가 키를 왜곡하지 않게. 마네킹은 전부 스킨 메시라 결과 동일). glb의 `BatTip`/`BatKnob` 표지를 `sample()`의 배트 끝 측정에 사용(원통 배트 없을 때). `soleMinY` 후보 정점을 **첫 호출 자세의 월드 높이**로 선택(geometry 로컬 y로 고르면 Z-up 출처에서 엉뚱한 정점이 뽑혀 발바닥이 0.7~1.4 m로 나왔다 → 고친 뒤 −0.011~0 m, 전체 정점 검증 6지점 일치).
- `batter3d-host.js`: 재생 구간을 `b.meta.play`에서 읽는 `resolvePlay`(없거나 모자라면 마네킹 상수 PLAY). `status()`에 `play` 노출.
- `demo.html`: 배트 끝 속도 기준 시점 저장 시 `meta.play[kind].cue`도 갱신.
- 변환기: 'ctl' 프로필 전부(위). mixamo 프로필 동작은 그대로(FILES·SHA 기록·subclip idle).

### 11.4 측정(데모 + 호스트, 앱 안 Chromium)

| 항목 | 값 |
|---|---|
| 역할 뼈 | 12개 전부 찾음(Head 포함, 빌드 3) |
| 키 단위 | 174.4(타격 자세) → 1.8 m 정규화 |
| 연출 기준 시점(배트 끝 속도 최대, 240표본) | contact k 0.3438 = **0.7448 s**/2.1667 s(손 속도 기준 0.8125 s), miss k 0.1688 = **0.5625 s**/3.3333 s(손 속도 기준과 같음) |
| 발바닥 최저(메시, 21표본) | contact −0.0033~0 m, miss −0.0114~0 m. 발 뼈 최저 0.000 |
| 호스트 재생 구간(meta.play) | contact cue 0.7448, **end 1.85 s**(1.9 s부터 왼발이 들리며 달리기 시작 → 두 발이 땅에 있는 팔로스루 끝에서 멈춤), miss cue 0.5625, end 3.3333(타격 자세로 복귀) |
| 호스트 동작 | `?batter3d=batter-ctl`: 첫 로딩 뒤 붙음(3 MB라 마네킹보다 늦음, 수치 미측정), 좌타 거울·헛스윙·파울팁 타격 재생, 끝 자세 유지, 자막 정상. 1280px 캔버스 260×310, 390px 260×267(기하 불변) |
| 틀 여유 | 대기 자세 배트 끝(y 2.13 m)이 zoom 0.8 틀 위 끝에서 약 3 cm(캡처로 끝이 닿음) → 메타 `view.targetY 0.55`로 0.09 m 올림(위 여유 약 12 cm, 발 아래 약 27 cm, 계산+캡처) |

### 11.5 알려진 한계·미측정

- 타격 클립은 에셋 설계대로 **오른손(위 손)에 배트가 남고 왼손을 놓는** 한 손 팔로스루. 실제 타자와 반대(보통 위 손을 놓음)지만 에셋 그대로다.
- `spine_03`·`neck_01` 중복 이름: three.js FBXLoader는 트랙을 이름으로 묶어 두 번째 뼈의 움직임은 첫 번째에 겹친다(원본 도구는 ID로 구분). 눈에 띄는 변형은 못 봤으나 **정밀 비교 미측정**.
- idle 클립(1.5 s 흔들림)은 모듈이 시간 0만 쓴다(반복 재생 없음). prepare(5.3 s)는 담아 두기만 함.
- 거칠기 값·흰색 베이스 색은 추정(SP 맵 미사용). 다크 조명에서의 피부·유니폼 톤은 캡처로만 확인.
- 첫 로딩 시간·실기기 fps **미측정**. 헤드리스 캡처 환경(SwiftShader)에서는 시험하지 않음.
- 좌타 거울 반전 시 유니폼 글자·로고가 좌우 반전된다(마네킹과 같은 한계).
- 기본 모델 교체(`DEFAULT_MODEL`)는 **하지 않았다**(사용자 결정). 지금은 `?batter3d=batter-ctl`로만 본다.

### 11.6 파일 SHA(작업본, 2026-11-09)

| 파일 | 크기 | SHA-256 앞 8자리 |
|---|---|---|
| `tools/fbx-to-glb.html` | 44,774 B | `7f3b3258` |
| `batter3d.js` | 20,607 B | `b4b398ec` |
| `../batter3d-host.js` | 7,740 B | `940d9691` |
| `demo.html` | 28,510 B | `f431d2a6` |
| `assets/batter-ctl.glb`(git 무시) | 2,979,472 B | `4e5a0369` |
| `assets/batter-ctl.meta.json`(git 무시) | 9,437 B | `ad7820b2` |

같은 모델 하위 에이전트의 독립 검토(Workflow, 3 관점 + 반박 검증)를 돌렸다. 결과와 반영은 11.7절. GPT(다른 모델) 검토는 사용자 몫이며 이 검토가 대체하지 않는다. 커밋·push·배포 없음.

### 11.7 독립 검토(같은 모델 Workflow 8 에이전트, 3 관점 + 반박 검증) 결과와 반영 — 2026-11-09 02:1x~02:4x

확정 3건 전부 반영, 반박된 2건은 기록만. 상세는 각 지적의 코드 위치와 함께 아래.

| # | 관점 | 지적(요약) | 판정 | 반영 |
|---|---|---|---|---|
| 1 | 수학 | ctl 프로필에서 '검사' 없이 build를 다시 누르면 `graftBat()`가 기존 'Bat' holder를 확인하지 않아 배트가 두 개 겹쳐 들어가고, 배트 이식 전 측정(`describe`)이 첫 배트를 포함해 메타 삼각형 수가 부풀려진다(현재 산출물은 Bat 1개로 정상) | 확정(중) | `graftBat()` 첫머리에서 손 뼈의 기존 'Bat' 자식 제거, build()에서도 이전 배트가 있으면 떼어내고 몸만 다시 잰다 |
| 2 | 런타임 | glb 배트 표지(BatTip/BatKnob)를 생성자에서만 잡아 `setBat({enabled:true})→false`로 켰다 끄면 영구히 잃고, 데모 기준 시점 추정이 표본 0에서 k=0을 메타에 쓴다(콘솔 API 경로에서만 재현) | 확정(낮) | 표지 잡기를 `buildBat()`의 비활성 분기(`pickEmbeddedMarkers`)로 옮김; 데모는 표본 0이면 메타를 쓰지 않고 로그로 중단 |
| 3 | 위생 | 변환기가 만드는 `meta.play.contact.end`(원본 끝 2.1667 s)가 배포 메타의 손수정 값(1.85 s)과 달라 재빌드 시 조용히 되돌아간다 | 확정(중) | 프로필 상수 `playEnd.contact = 1.85`(근거 주석) 추가, 생성값 = 배포값. 변환기 주석도 측정대로 수정 |
| 4 | 런타임 | resolvePlay가 모듈이 재생하지 않는 클립 이름을 통과시킬 수 있다 | 반박(파이프라인이 만드는 메타에서는 발생 불가, 손수정 때만) | 기록만 |
| 5 | 위생 | 라이선스 표기 관련 지적 1건 | 반박 | 비공개 기록 |

검토 중 확인된 것: 마네킹 glb(전부 스킨 메시)에서 `skinnedBounds`는 `Box3.setFromObject`와 같은 상자(동작 불변); git 위생(배트·텍스처·FBX 미추적, D: 경로 유출 없음, 외부 URL 없음) 이상 없음. 검토 비용: 하위 에이전트 토큰 998,173(앱 보고값), 23분.

### 11.8 대기 동작 반복·카메라 각도 수정안·추가 Mixamo 클립 2개 — 2026-11-09 02:5x

사용자 요청 둘: "자세 전후(투구 넘어가기 전·동작 끝난 뒤)에는 항상 대기 자세였으면" + Mixamo `Baseball_Idle.fbx`, "타자 각도가 보는 사람 입장에서 부자연스럽다, 체크하고 수정안" + Mixamo `Baseball_Step_Out.fbx`("스트라이크나 볼 자세?").

**대기 동작 반복(구현·검증)** — 모듈 `reset()`: idle 클립이 0.4 s 이상이면 `LoopRepeat`로 자체 rAF 반복(30 fps 상한, 탭 복귀 등 긴 공백은 dt 0.1 s로 자름), 스윙 끝에서 부르면 스윙 액션에서 0.35 s crossfade. `setSwing()`은 반복을 끄고 호스트 진행률로만 그린다. `dispose`·문맥 상실·`stopIdle`에서 rAF 취소. 마네킹(idle 2프레임 0.033 s)은 전처럼 시간 0 정지. 호스트 `relay.js`: 3D 스윙 `run()`의 done에서 `api.reset()` → 끝 자세를 다음 투구까지 들고 있던 한계가 사라짐. 측정(호스트 1280px, 앞 탭): 대기 중 `idleLoop true`, 그린 프레임 2초에 60(=30 fps); 헛스윙 중 `idleLoop false`(k 0.25), 끝난 뒤 4 s에 `true`·kind null(자세 복귀 캡처 `u4-host1280-after-miss-idle.jpg`); 파울팁 타격도 같음(`…after-contact-idle.jpg`); `detach3D` 뒤 attached false·행 클래스 제거, `init()` 재연결 뒤 캔버스 1개·반복 재개. 콘솔 오류: 변환기 페이지의 `pattern` 속성이 Chrome v 플래그 정규식에서 거부되던 것 2건(`-`·`/` 이스케이프로 수정), 그 밖에 relay 페이지 오류 0.

**카메라 각도 점검** — 데모(260×360)에서 azimuth +90/−90/180을 찍어 좌표계를 확인: 이 캐릭터는 가슴이 −x(존·홈플레이트 쪽), 투수가 +z, 카메라 azimuth 0은 투수 자리, 양수는 타자 **등 쪽**으로 돈다. 기본값 +28°는 투수 자리에서 등 쪽으로 28° 돌아간 카메라라 타자가 몸을 돌려 선 듯 보였다(사용자 지적과 일치). 수정안: **azimuth −22°, elevation 10°**(가슴 쪽으로 22°; 중계 센터 카메라가 우타자를 보는 쪽). 비교 시트 `u4-angle-proposal-sheet.png`(대기 +28/0/−15/−22/−30/−40, 타격 기준 시점 +28/0/+8/−22/−30·고도12/−40, 참고 ±90/180). 메타 `view`에 넣었고(`batter-ctl`만; 마네킹 메타는 그대로) 호스트 캡처 `u4-host1280-L-stance-az-22.jpg`·`…miss-midswing-az-22.jpg`. 선택은 사용자 몫(−15·−30도 시트에 있음).

**추가 Mixamo 클립 2개**(→ 11.11에서 Step_Out을 자체 재대상 도구 `tools/retarget-mixamo.mjs`로 옮겨 반응 클립 'take'로 사용, 보류 해제 2026-11-09 10시) — `Baseball_Idle.fbx`(448,512 B, SHA `346226d5…`, 2.333 s)·`Baseball_Step_Out.fbx`(563,344 B, SHA `24a1515d…`, 3.1 s): 둘 다 Mixamo 뼈대(`mixamorig6`, 65개) **Without Skin**(메시 0). 이 캐릭터(외부 구매 모델 뼈대 68개, A-pose)에는 그대로 못 쓴다. three.js `SkeletonUtils.retargetClip`(뼈 이름 51개 대응, T-pose→A-pose 정렬 없이)로 자동 재대상 시험(Node, `scratchpad/nodeinspect/retarget-probe.mjs`): 결과 자세가 망가짐 — 발 높이 53~95 cm(정상 9), 머리 85~128 cm(정상 149), 손 200 cm 이상. 쓰려면 두 뼈대의 휴식 자세(T↔A)와 뼈 축 정렬을 따로 맞추는 작업이 필요하고 품질은 미지수. 그래서 대기 자세는 **캐릭터 자체 idle 클립**(1.5 s, 이 캐릭터용 타격 대기 흔들림)으로 반복했다. '스트라이크/볼 때 스텝아웃' 반응은 이 캐릭터에 해당 클립이 없어 보류(선택지: 같은 뼈대 클립 추가 구매, 재대상 정렬 작업, 또는 `prepare` 5.3 s 클립 일부 활용). 마네킹(Mixamo 뼈대)에는 두 클립을 그대로 붙일 수 있다(접두 `mixamorig6`→`mixamorig` 정리 필요, 미구현).

### 11.9 파일 SHA(작업본, 11.7~11.8 반영 뒤)

| 파일 | 크기 | SHA-256 앞 8자리 |
|---|---|---|
| `tools/fbx-to-glb.html` | 46,236 B | `99933e5f` |
| `batter3d.js` | 23,227 B | `e9b8b187` |
| `../batter3d-host.js` | 7,740 B | `940d9691` |
| `../relay.js` | 56,693 B | `8d29c3d3` |
| `demo.html` | 28,761 B | `4d790311` |
| `assets/batter-ctl.meta.json`(git 무시) | 9,861 B | `b02fb95a` |

glb는 재빌드하지 않았다(11.7의 변환기 수정은 재빌드 결과를 바꾸지 않는 멱등성·생성값 정합 수정). 커밋·push·배포 없음.


### 11.10 batter-ctl 누적 검사(화면 진입·이탈·해제·재연결) — 2026-11-09 09:1x

단위 3(9.5)의 누적 검사는 마네킹으로 했고, 단위 4의 캐릭터 교체·대기 반복(자체 rAF)에 대해서는 다시 하지 않았었다. 사용자가 Codex '단위 3' 지시문을 다시 붙여 준 것을 계기로 `v2.html?batter3d=batter-ctl`(앞 탭)에서 재측정: 라인업↔중계 20회(띠 0↔140 px 20쌍), 연속 재생 30회(120 ms)·4 s 대기 복귀, `PZRelay.detach3D`→`PZBatter3D.init` 10회(203~557 ms) 뒤 — 캔버스 1·상자 1, geometries 8→8·programs 4→4·textures 14→14, 미해결 rAF 1(대기 반복의 다음 프레임), 리스너 순증 0, 대기 30 프레임/s 유지. 코드 변경 없음. 상세 표는 `../NOTES.md` '버전 이름 정리'.


### 11.11 안 치는 공 반응 'take' — Mixamo Step Out을 이 뼈대로 옮김 (2026-11-09 09:3x~10:3x)

사용자 요청(스트라이크·볼에 반응). 패키지에 반응 클립이 없어 `tools/retarget-mixamo.mjs`(Node, 새 파일 17,873 B, SHA `7b373171`; 로더 `node-three.mjs` 298 B, SHA `e10da97f`, `node-three-hooks.mjs` 562 B, SHA `760542eb`)로 Mixamo `Baseball_Step_Out.fbx`(Without Skin, 3.1 s)를 옮겼다: 휴식 자세(바인드 A-pose vs T-pose) 방향 정렬 + 월드 회전 변화량 + 위→아래 로컬 변환, 골반은 다리 길이 비율 1.6327. 결과 발목 8.2~19.5 cm·발끝 최저 -2.9 cm·머리 143.4~152.4 cm(보고서 `D:/pitcheezy_assets/build/retarget-take-report.json`). 변환기 'ctl' 프로필에 `extraClips`·`playEnd.take 2.6`·`playCue.take 0.3` → **빌드 4** `assets/batter-ctl.glb` 3,089,640 B, SHA `c34da227`(클립 5: contact·miss·idle·prepare·take), 메타는 데모 측정값 유지 + take 합침(11,138 B, SHA `10ee9acd`), 빌드 3은 `D:/pitcheezy_assets/build/prev-build3/`. 모듈 `batter3d.js` 28,039 B, SHA `aaa744a9`: take 종류, 대기→클립 0.3 s·클립→대기 0.35 s(take 0.6 s) 섞기를 모듈이 직접 가중치로(`startBlend/stepBlend`, 합 1 유지; three.js crossFade는 끊기면 튐·이전 reset의 crossFadeTo는 paused 액션에서 컷이었음), `reset({still})`·감속 모션 정지, `sample()` 섞기 즉시 종료, `getState().weights/blending`. 어댑터 `../batter3d-host.js` 9,950 B, SHA `53ec539a`: `resolvePlay` 선택 항목 take(glb와 안 맞으면 take만 제외), `api.react(leadMs)`(도착 + 250 ms 뒤 0.3→2.6 s), `reset(o)`. 호스트 `../relay.js` 58,620 B, SHA `ec682d16`: take|block 분기(`typeof react` 확인), `b3Still()`(스위치 끔·감속·중계 탭 아님 → 정지 자세). `demo.html` 29,429 B, SHA `a4bab486` 종류 선택에 take. 변환기 49,132 B, SHA `9ce73bd5`. 측정·캡처·한계는 `../NOTES.md` '안 치는 공 반응'. 독립 검토: Workflow 29 에이전트(관점 3 × 읽기 검토 → 지적마다 반박 2, 350만 토큰, 30분). 지적 13건 중 확정 12(중복 포함)·기각 1(같은 이름 뼈 트랙 바인딩 — 원본 클립과 같은 방식이라 문제 아님). 확정 지적과 반영: 커밋·push·배포 없음.


### 11.12 안타·홈런 타격 'hit' — Mixamo Baseball Hit 5를 이 뼈대로 옮김 (2026-11-09 13:1x~14:xx)

사용자 요청("유효한 타격·진루·홈런은 치고 나가는 동작, 맞는 상황만"). `tools/retarget-mixamo.mjs`로 `Baseball_Hit_5.fbx`(Without Skin, 2.9 s)를 옮겼다(대상 ANIM_Idle.fbx; 결과 발목 6.8~35.3 cm·발끝 최저 -4.5 cm·머리 118.3~146.6 cm, 골반 2.9 s에 −133.5 cm로 달려 나감; 보고서 `D:/pitcheezy_assets/build/retarget-hit-report.json`). 변환기 'ctl' 프로필 `extraClips`에 hit·`playEnd.hit 2.9`·`playCue.hit 1.7(임시)` → **빌드 5** `assets/batter-ctl.glb` 3,212,124 B, SHA `c56571c4`(클립 6), 메타는 기존 측정값 유지 + hit 합침, **cue 1.443958 s는 데모 배트 끝 속도 최대(k 0.4979)로 갱신**(12,860 B, SHA `804cceda`). 빌드 4는 `D:/pitcheezy_assets/build/prev-build4/`·`prev-build4-assets/`. 모듈 `batter3d.js` 28,713 B, SHA `cd57caed`: hit 종류, `FADE_BACK_HIT 0`(달려 나간 뒤 k ≥ 0.65에서 끝·끊김이면 컷, 그 전 끊김은 0.35 s 섞기). 어댑터 `../batter3d-host.js` 10,700 B, SHA `e9bd543e`: 선택 항목 hit, `swing("hit")`(없으면 contact), 돌려주는 객체에 실제 고른 `kind`. 호스트 `../relay.js` 60,551 B, SHA `ef419daf`: 인플레이 ∧ 타석 결과 single·double·triple·home_run → hit, `sw.kind === "hit"`일 때 진행률 0.86~1에 상자 투명도 1→0 뒤 reset(+0.35 s 전환), cancelAnim에서 즉시 복원. `demo.html` 29,514 B, SHA `73b81385` 종류 선택에 hit. 변환기 50,466 B, SHA `39148373`. 측정·캡처·한계(홈런 트롯 없음, 좌타 거울이라 달리는 방향이 실제 1루와 반대)는 `../NOTES.md` '안타·홈런 타격'. 독립 검토: 1차: 다른 세션 에이전트(일반 목적, 읽기 전용) 1명 — 지적 3건(모두 경미) 전부 반영. (1) 변환기 메타의 클립별 `source.note`가 take 문구로 고정돼 hit에도 "Baseball Step Out … play.take"가 붙음 → 항목별 `retargeted`·길이·이름으로 템플릿화, 작업본 메타의 hit·take note 수정(런타임엔 읽지 않는 값). (2) 모듈 `reset()`이 hit 뒤엔 진행률과 무관하게 컷 → 타격 직후(틀 안, k < 0.65) 끊기면 다른 클립처럼 0.35 s 섞고, 달려 나간 뒤(k ≥ 0.65)만 컷. 측정: k 0.61 끊음 → 섞기, k 0.96 끊음 → 컷. (3) 호스트의 투명 처리가 클립 이름(`sw.clip === "hit"`)에 묶여 메타의 clip 이름이 다르면 조용히 빠짐 → 어댑터가 실제 고른 항목 `kind`를 돌려주고 호스트는 `sw.kind === "hit"`로 판단. 질문 7개는 모두 "문제 없음"으로 확인(actual null 안전, detach 뒤 상자 재사용 없음, cancelAnim 순서, 거울·먼 골반 위치에 의존하는 코드 없음(바닥 그림자 원반은 원점 고정), 0초 섞기의 NaN 없음·idle 처음부터, 마네킹은 contact 대체, demo take 비교만). 미검증: 실제 렌더 결과(검토자는 브라우저 미실행). 커밋·push·배포 없음.
