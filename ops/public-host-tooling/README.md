# 고정 Cloudflare CLI — WS-stage2

Wrangler 4.151.0을 이 폴더의 lockfile로 고정한다. 기존 `../public-host`의 Miniflare 리허설 의존성을 바꾸지 않는다.
배포 패키지에 이 도구 폴더/node_modules/로그를 포함하지 않는다. 자동 배포 스크립트는 제공하지 않는다.
Windows Node24.1.0/npm11.3.0에서 설치·버전·합성 dry-run을 확인했다. 다른 OS 실행은 미확인이다.

## 설치와 로컬 검사

이 폴더를 현재 작업 폴더로 한 뒤 실행한다. 설치는 공식 npm registry를 사용하며 계정 로그인은 하지 않는다.

```text
npm ci --ignore-scripts --no-fund --no-audit
npm audit --json
```

최초 고정은 `npm install --ignore-scripts --no-fund --no-audit --fetch-retries=0 --fetch-timeout=30000`으로 했다.
10/15 audit은 알려진 취약점0건이다. 취약점 부재의 보증은 아니며 공개 운영 전 다시 확인한다.
Wrangler는 Node>=22를 요구하지만 이 저장소의 운영/검사 기준은 Node>=24다.

**자격증명이 없는 별도 자식 프로세스에서만 다음 dry-run을 재현한다.** 일반 로그인 터미널에서 그대로 실행하지 않는다.
1. 새 빈 프로필 디렉터리 아래 home/config/cache/temp/appdata/localappdata를 만든다.
2. OS 실행에 필요한 환경 이름만 전달한다: PATH, PATHEXT, SYSTEMROOT, WINDIR, COMSPEC,
   PROCESSOR_ARCHITECTURE, NUMBER_OF_PROCESSORS. 그 외 기존 환경/비밀을 상속하지 않는다.
3. USERPROFILE/HOME은 새 home의 절대경로, HOMEDRIVE는 그 드라이브, HOMEPATH는 드라이브를 제외한 경로로 지정한다.
   APPDATA/LOCALAPPDATA는 새 appdata/localappdata,
   XDG_CONFIG_HOME은 새 config, XDG_CACHE_HOME/WRANGLER_CACHE_DIR은 새 cache,
   TEMP/TMP는 새 temp로 지정한다. Node `os.homedir()`가 새 home과 같은지 먼저 확인한다.
4. `CLOUDFLARE_AUTH_USE_KEYRING=false`, `CLOUDFLARE_LOAD_DEV_VARS_FROM_DOT_ENV=false`,
   `WRANGLER_SEND_METRICS=false`, `WRANGLER_SEND_ERROR_REPORTS=false`, `CI=true`, `NO_COLOR=1`만 추가한다.
5. 새 빈 env 파일을 만들고 아래 `--env-file`로 명시한다. 새 작업 복사본의 host 폴더에서 실행한다.
   개인 인증 파일·키체인·브라우저 로그인은 읽거나 복사하지 않는다.

```text
node <이폴더절대경로>/node_modules/wrangler/bin/wrangler.js --version
node <이폴더절대경로>/node_modules/wrangler/bin/wrangler.js deploy --dry-run --env-file <새빈파일> --config <작업복사본>/host/wrangler.deploy.json --outdir <후보밖새출력폴더>
```

`deploy --dry-run`은 업로드하지 않는다. 이를 네트워크 차단/통신0건 검증이라고 부르지는 않는다.
`WRANGLER_HOME`은 이 버전의 지원 변수로 사용하지 않는다. XDG만 바꾸면 기존 home의 인증을 읽을 수 있다.
[인증 경로 구현](https://github.com/cloudflare/workers-sdk/blob/wrangler%404.151.0/packages/workers-utils/src/global-wrangler-config-path.ts),
[환경 변수](https://developers.cloudflare.com/workers/wrangler/system-environment-variables/),
[CLI env 파일](https://github.com/cloudflare/workers-sdk/blob/wrangler%404.151.0/packages/wrangler/src/index.ts).

## 검증 원본과 도구 작업 복사본

패키지/설정 검사를 통과한 원본은 보존한다. 도구 실행에는 그 바이트를 복사한 별도 폴더를 쓴다.
4.151.0 dry-run은 host/.wrangler/tmp 디렉터리를 생성한다. 원본에서 실행하면 엄격한 설정 검사에서
`invalid_path`로 거부된다. 이를 허용하도록 검사기를 느슨하게 바꾸거나 원본에 도구 로그를 섞지 않는다.
실행 뒤 원본 설정 검사를 재수행하고, 복사본의 원래16개 파일을 원본 SHA와 대조한다.
생성된 bundle/source map은 로컬 검사 산출물이며 공개 화면에 복사하지 않는다.

실제 배포는 승인된 실계정 설정·비밀·고정 화면·경로·검토 근거가 필요하다. `secret put`도 새 버전을
배포하는 명령이므로 로컬 비밀 준비로 취급하지 않는다. 실제 실행 절차는
[계정 확인과 시험안](../../docs/WS_ACCOUNT_READINESS_20261015.md)을 따른다.
