# vendor — three.js 0.187.0 (MIT)

출처: npm 레지스트리 패키지 `three@0.187.0` (`npm pack three@0.187.0`, 2026-11-08, tarball 4,795,351 bytes). 라이선스 원문은 이 폴더의 `LICENSE`(MIT, three.js authors). 수정 없이 복사했다. 런타임에 CDN이나 외부 네트워크 요청은 없다.

복사한 파일과 원래 경로:

| 이 폴더 | 패키지 안 경로 | 용도 |
|---|---|---|
| `three.module.js`, `three.core.js` | `build/` | 본체(three.module.js가 three.core.js를 가져온다) |
| `addons/loaders/FBXLoader.js` | `examples/jsm/loaders/` | 변환 도구에서 Mixamo FBX 읽기 |
| `addons/libs/fflate.module.js` | `examples/jsm/libs/` | FBXLoader 의존(압축 해제) |
| `addons/curves/NURBSCurve.js`, `NURBSUtils.js` | `examples/jsm/curves/` | FBXLoader 의존 |
| `addons/loaders/GLTFLoader.js` | `examples/jsm/loaders/` | 데모·모듈에서 glb 읽기 |
| `addons/utils/BufferGeometryUtils.js` | `examples/jsm/utils/` | GLTFLoader 의존 |
| `addons/utils/SkeletonUtils.js` | `examples/jsm/utils/` | GLTFLoader 의존(스킨 복제) |
| `addons/exporters/GLTFExporter.js` | `examples/jsm/exporters/` | 변환 도구에서 glb 쓰기 |

가져오기 방식: 페이지의 import map으로 `"three": "./vendor/three.module.js"`, `"three/addons/": "./vendor/addons/"`를 선언한다. addons 파일들은 내부에서 `'three'` 와 상대 경로(`../libs/…`)를 쓰므로 폴더 구조를 그대로 유지한다. Draco·meshopt 디코더는 넣지 않았다(압축은 후속).
