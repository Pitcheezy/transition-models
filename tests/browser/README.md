# Local service review browser regression

These tests build a new review package from the committed **synthetic** current-export
example, start its real Python standard-library server on a free loopback port, and
exercise it in headless Playwright. They never read teammate repositories, actual
service exports, human responses, MLB footage, or existing browser tabs. All browser
requests stay on their own test servers. Review/observation reads use GET or HEAD; the separately described telemetry checks send synthetic opt-in POSTs. File selection stays local.

## Install

Use Node.js 24 or newer and Python 3.12 (project baseline; no Python third-party
packages are needed for this suite). From this directory:

```text
npm ci --ignore-scripts
npm --prefix ../../ops/public-host ci --ignore-scripts
npx playwright install chromium webkit
```

`package-lock.json` pins Playwright 1.62.1 and its dependencies. Linux runners may use
`npx playwright install --with-deps chromium webkit` to install OS browser dependencies.
Browser installation contacts Playwright's download hosts; the tests themselves only
browse their own loopback server.

## Run

Linux/macOS example, from this directory:

```sh
PYTHON_BIN=python3 BROWSER_ENGINE=chromium npm test
PYTHON_BIN=python3 BROWSER_ENGINE=webkit npm test
```

PowerShell example with this repository's Python environment:

```powershell
$env:PYTHON_BIN = (Resolve-Path ../../.venv/Scripts/python.exe).Path
$env:BROWSER_ENGINE = 'chromium'
npm test
$env:BROWSER_ENGINE = 'webkit'
npm test
```

`PYTHON_BIN` is an executable name or absolute path, not a shell command containing
arguments. It defaults to `python` on Windows and `python3` elsewhere. To check an
existing Chrome installation instead of the downloaded Chromium, set
`BROWSER_EXECUTABLE` to its absolute executable path. This override is accepted for
`BROWSER_ENGINE=chromium` only; unset it before running WebKit. For example:

```powershell
$env:BROWSER_ENGINE = 'chromium'
$env:BROWSER_EXECUTABLE = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
npm test
Remove-Item Env:BROWSER_EXECUTABLE
$env:BROWSER_ENGINE = 'webkit'
npm test
```

The suite owns a uniquely named directory under the OS temporary directory. It stops
its own server and verifies the directory's resolved parent and name before cleanup.
It does not delete project files. Windows subprocesses are hidden. Python stdin signals
a normal KeyboardInterrupt shutdown so a venv launcher does not leave a child server.

## Covered behavior

- Initial results and mitt estimates remain hidden; manual reveal works.
- Pitch and plate-appearance changes hide previous results; unsupported/missing states remain distinct.
- Invalid JSON, files over 5 MiB, identity mismatches, unsupported units, excessive
  selection share totals and duplicate pitch types are rejected; valid-file recovery works.
- Replacing a revealed report clears its results; a late default-file response cannot
  replace a user-selected report.
- Enter and Space preserve the selected pitch button's focus through a render; rendering
  does not steal focus from another control.
- The document does not overflow horizontally at 320px, before or after reveal.

The fixture adds one invented second pitch to the ready plate appearance. This is a UI
regression test, not a performance study or an accuracy result. No clips are included:
video codec playback, real Mac/iPhone use, human acceptance, live feeds and teammate
model execution require separate evidence. Headless WebKit is not an actual Safari
or iPhone verification.

## Private observation playback (CV-30)

`observation-playback-private.cjs` is a separate, opt-in Chromium check of the existing
CV24 private video and saved observations. It is **not** run by `npm test` or public CI.
It records 15 playback/publication/seek checks and screenshots in a private output path.
See [the run instructions](../../docs/CV_OBSERVATION_PLAYBACK_20261011.md).
Do not upload its MLB screenshots to public CI artifacts. The portable synthetic
publication gates run through `tests/test_observation_playback_ui.py` in normal pytest.

## Local Worker rehearsal (WS-ops4c)

public-host-rehearsal.test.cjs starts an isolated Miniflare Worker/R2 with synthetic HTML/data.
Node-side helpers publish/withdraw via authenticated requests; the browser only reads the same local
Worker. No upload credential enters browser JavaScript and responses are not mocked by Playwright.
Two checks cover keyboard/375px version changes, withdrawal/restore, actual JSON404, and successful
Worker reads after the browser closes. Both browser engines run in CI.

Set BROWSER_CHANNEL=chrome for the new host tests to use local Chrome; the older review tests use
BROWSER_EXECUTABLE. CI uses the bundled engines. Headless WebKit is not physical Safari.
Windows WebKit closing a connection can print workerd WSARecv64 despite passing functions and a
successful post-close Worker read; this runtime diagnostic remains unresolved.
See ../../ops/public-host/REHEARSAL.md for measured local scope and limits.
