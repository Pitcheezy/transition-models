# H-1: "Arrow 문자열 변환 멈춤"의 원인 — 멈춤이 아니라 크래시였다 (2026-09-23)

## 한 줄 결론

Windows에서 `import hashlib`(또는 `urllib.request`) → `import torch` → 첫 pandas/pyarrow 문자열 변환 순서로 실행하면
프로세스는 **멈추는 것이 아니라 약 25초 정체 뒤 `0xC0000005`(STATUS_ACCESS_VIOLATION)로 죽는다.**
원인은 pyarrow 24.0.0 `arrow.dll`에 정적 링크된 mimalloc v3.2.7이 자기 TLS 슬롯을 할당하기 전에 TEB `TlsSlots[63]`을
힙 포인터로 읽는 것과, `hashlib`가 소비하는 TLS 슬롯 정확히 8개 때문에 torch DLL 집합이 8칸 밀려 값 `1`을 쓰는 torch DLL이
슬롯 63에 놓이는 것의 결합이다. **OpenSSL·OpenMP·MKL 중복 DLL 문제가 아니다.**

- 재현: 실패 순서 4/4 결정적 크래시(정체 25.6~27.0 s 뒤 종료 코드 3221225477), 60초 타임아웃에 걸린 적은 없음.
- 완화(채택): **torch보다 먼저 `pyarrow`를 import**한다 — 3/3 정상(9 s). `src/__init__.py`에 Windows 전용 가드로 넣었고
  `tests/test_broadcast_timing.py`에 `hashlib → src → torch → pandas` 순서의 새 프로세스 회귀 테스트를 추가했다.
- 안전망: `ARROW_DEFAULT_MEMORY_POOL=system`(3/3 정상, 단 로드 시 삼켜지는 AV와 20초 정체는 남음).
- 기존 완화(`src/data/broadcast_timing.py`의 hashlib 지연 import)는 슬롯 이동을 0으로 유지해서만 동작했다. 그대로 두되 근본 완화는 위 가드다.

방법: Claude Code Workflow — 격리된 새 프로세스 실험 12셀(각 2회, `faulthandler.dump_traceback_later(25)`), 종합 에이전트의
추가 실험(TLS 슬롯 덤프, `TlsAlloc()` 8회로 hashlib 없이 재현, `TlsSetValue(63, NULL)`로 크래시 회피, 메모리 풀 환경변수,
PE import/export 검사, WER 이벤트 로그), 검증 에이전트의 재현 4회·완화 3회. 아래 종합 보고는 에이전트 산출물을 그대로 싣고
(영문), 검증 결과와 채택 사항은 Fable 5.1 세션이 정리했다. 실험 드라이버는 저장소 밖 scratch에 있었고 저장소 파일은 건드리지 않았다.

환경: Windows 11, Python 3.12.12(uv venv), torch 2.6.0+cu124, pandas 3.0.2, pyarrow 24.0.0.

## 검증 (2026-09-23, 새 프로세스, 60초 타임아웃)

| 셀 | 결과 |
|---|---|
| `import hashlib; import torch; import pandas as pd; pd.DataFrame([{'pitch': 'FF'}])` | 4/4 실패: 25 s 시점 스택은 `import pandas` 안(pyarrow.lib DLL 로드), 이후 `0xC0000005`; 4번째 실행에서 import 완료 뒤 `pd.DataFrame`에서 죽는 것을 stdout 체크포인트로 확인 |
| `import pyarrow; import hashlib; import torch; import pandas as pd; ...` | 3/3 정상(8.6~9.5 s) |

검증 에이전트의 주석: 과제의 문구는 "hang"이었지만 60초 타임아웃에는 한 번도 걸리지 않았다. 이전 "멈춤" 보고는 종료 코드를 읽지 않는
부모 프로세스에서 25초 정체 + WER 보고 수집을 멈춤으로 본 것일 가능성이 크다(14일간 python.exe `Application Hang` 이벤트 0건,
`Application Error`(arrow.dll+0xbc542e) 28건).

## 채택한 변경

1. `src/__init__.py`: `sys.platform == "win32"`이면 `import pyarrow`를 먼저 시도한다(없으면 무시). 이 패키지를 torch보다 먼저
   import하는 모든 진입점이 보호된다. torch를 먼저 import하는 경로는 원래 안전하다(B·H 셀).
2. `tests/test_broadcast_timing.py::test_hashlib_before_src_and_torch_in_fresh_process`: 가장 나쁜 순서
   (`hashlib → src.data.broadcast_timing → torch → pandas`)가 새 프로세스에서 성공해야 한다.
3. `src/data/broadcast_timing.py`의 주석을 "hang"에서 실제 원인으로 고쳤다. hashlib 지연 import는 유지한다(무해).

## 미검증으로 남긴 것

- 슬롯 53/55(밀린 뒤 61/63)에 `1`을 쓰는 torch DLL이 정확히 무엇인지(`libiomp5md.dll` 단독 로드는 아니었다).
- 삼켜진 예외가 `LoadLibraryExW` 안에서 왜 ~20초를 소모하는지(WER first-chance 보고로 추정).
- 최신 pyarrow/mimalloc(3.3.x)에서 고쳐졌는지 — Arrow #50471은 다른 mimalloc 3.3.x 스레드 초기화 크래시를 보고한다.
- 저장소 import 그래프에 TLS 슬롯을 8개 소비하는 다른 모듈이 있는지.

---

## 종합 보고 (워크플로 에이전트 산출물, 원문)

## Root cause of the "hang" at the first Arrow-backed string conversion (Windows, torch 2.6.0+cu124, pandas 3.0.2, pyarrow 24.0.0)

### TL;DR
It is not a hang and not an OpenSSL/OpenMP duplicate-DLL problem. It is a **use of an unallocated Win32 TLS slot by the mimalloc allocator (v3.2.7) statically linked into pyarrow's `arrow.dll`**: before mimalloc has allocated its own TLS slots it reads `TlsSlots[63]` of the TEB (`__readgsqword(0x1480 + 63*8)`) as its thread-heap pointer. Whatever DLL owns slot 63 in the process decides the outcome. When exactly 8 TLS slots are consumed before `import torch` (that is what `import hashlib` / `import urllib.request` do via `_hashlib.pyd` + `libcrypto-3-x64.dll`), the torch DLL set shifts up by 8 and the DLL that stores the value `1` in its slot lands on slot 63. mimalloc then dereferences `0x1` -> `STATUS_ACCESS_VIOLATION` at `arrow.dll+0xbc542e`, first (swallowed) inside the DLL-load of `pyarrow.lib`, then fatally at the first Arrow allocation (`pa.array` from `ArrowStringArray._from_sequence`, `string_arrow.py:239`). The "hang" seen earlier is this crash plus a ~20 s stall inside the DLL load and WER report collection, observed from a parent that did not read the exit code.

### 1. Which import combination and order triggers it (all runs fresh processes, 60 s timeout)
| order | result |
|---|---|
| pandas alone (A), hashlib->pandas (D), ssl->torch->pandas (F), torch->pandas (B), torch->hashlib->pandas (H), hashlib->pyarrow->torch (L) | ok, 2/2 each |
| hashlib->torch->pandas (C, I, K), urllib.request->torch->pandas (E), hashlib->torch->pyarrow (G, J) | **crash 0xC0000005 every run (23/23 in the table; 28 WER `Application Error` events for python.exe in 14 days, all `arrow.dll` offset `0xbc542e`/`0xbc5431`)**; never a true 60 s timeout |
| `[k.TlsAlloc() for _ in range(8)]`->torch->pyarrow (X2, no hashlib at all) | crash (same address) |
| `TlsAlloc()` x9 ->torch->pyarrow (X3) | crash at `0xbc5431` (slot 63 held a heap pointer instead of 1) |
| hashlib->torch->`TlsSetValue(63, NULL)`->pyarrow->`pa.array` (X4) | **ok** |
| pyarrow->hashlib->torch->pandas (X5) | ok 2/2 |
| pandas->hashlib->torch (X6) | ok |
| hashlib->torch->pandas with `ARROW_DEFAULT_MEMORY_POOL=system` (M) | ok 3/3 (a swallowed load-time AV and the ~20 s stall remain) |
| same with `ARROW_DEFAULT_MEMORY_POOL=jemalloc` | crash; Windows wheel prints "Unsupported backend 'jemalloc' (supported: 'mimalloc', 'system')" |

`urllib.request` behaves like `hashlib` because `urllib/request.py:87` does `import hashlib`. `ssl` (F) is harmless because `_ssl.pyd` consumes only 1 TLS slot (measured: next free slot 8->9) whereas `hashlib` consumes 8 (8->17, slots 8..15). `import torch` itself imports `hashlib` in Python after its DLLs are loaded, which is why torch->hashlib (H) equals torch alone. `ARROW_DEFAULT_MEMORY_POOL=system` avoids the fatal fault because the pool is created at first allocation (`pool_only` cell printed `pool mimalloc` right before dying).

### 2. Where the Python stack is when it "hangs"
Two access violations per run, same thread (main), captured with `faulthandler.enable()` and a ctypes vectored exception handler:
1. **During `import pyarrow.lib`** - `importlib._bootstrap_external:1293 create_module` <- `pyarrow/__init__.py:71` <- `pandas/compat/pyarrow.py:12` <- `pandas/__init__.py:34`. Native: `arrow.dll+0xbc542e` (READ of address `0x1`), called from `arrow.dll+0xbc9340` (mimalloc DllMain/TLS-callback path) <- ntdll loader (`LdrpCallInitRoutine` region, `LdrLoadDll`) <- `KERNELBASE!LoadLibraryExW`. The loader swallows it, the load "succeeds" with mimalloc half-initialised (the load allocates 4 TLS slots instead of the 6-7 seen in good orders), and the process sits ~20-25 s in `create_module` (25 s faulthandler dumps land here).
2. **Fatal** - `pandas/core/arrays/string_arrow.py:239 _from_sequence` (`pa.array(result, type=pa.large_string(), from_pandas=True)`) <- `construction.py:671 sanitize_array` <- `indexes/base.py:580 Index.__new__` (building the column Index `['pitch']`, so `dtype=object` columns do not avoid it) <- `frame.py:837`. Native: `arrow.dll+0xbc542e` again (WER: `Faulting module arrow.dll, offset 0xbc542e, code 0xc0000005`).
The instruction bytes at `arrow.dll` RVA `0xbc542e` are `48 8d 04 c5 00 00 00 00 | 65 48 8b 00 | 48 85 c0 | 75 08 | 48 8d 05 .. | c3 | 48 8b 00 <fault> | 48 8b 40 18` = `mov rax, gs:[slot*8]` (mimalloc `mi_prim_tls_slot`), `test rax,rax`, then `mov rax,[rax]` (`theap->heap`): it is `_mi_thread_init_theap_default()` -> `mi_theap_is_initialized(theap)` with `theap == 0x1`.

### 3. Mechanism (named libraries)
- **Library A: mimalloc v3.2.7 inside pyarrow 24.0.0's `arrow.dll`** (Arrow `versions.txt`: `ARROW_MIMALLOC_BUILD_VERSION=v3.2.7`, built with `MI_LOCAL_DYNAMIC_TLS=ON`, `MI_BUILD_SHARED=OFF`). In `src/init.c`: `_mi_theap_default_slot = MI_TLS_USER_LAST_SLOT` (= TEB slot 63) is the *default before* `_mi_tls_slots_init()` calls `TlsAlloc()`, with the comment "we initially use the last user slot so NULL is returned"; `_mi_tls_slots_init` is deferred to the first setter, so the very first read in process init goes to slot 63, which mimalloc does not own. `mi_theap_is_initialized` only checks `theap != NULL && theap->heap != NULL`.
- **Library B: the torch 2.6.0+cu124 DLL set** (`torch/__init__.py::_load_dll_libraries` LoadLibrary's every DLL in `torch/lib`), one of which stores the value `1` (looks like an Intel-OpenMP-style `gtid+1`, but loading `libiomp5md.dll` alone did not set it, so the exact writer is unverified) in the two TLS slots it allocates. Measured on the main thread: torch alone -> non-NULL `1` at slots 53 and 55, slot 63 NULL, works; hashlib (8 slots) then torch -> `1` at slots 61 and **63** -> crash. Any non-NULL value in slot 63 crashes (X3).
- Not involved: there is **no second OpenSSL, OpenMP, MKL or TBB copy**. Inventory: OpenSSL only in the interpreter (`...\cpython-3.12-windows-x86_64-none\DLLs\libcrypto-3-x64.dll` 7,976,960 B v3.5.5, `libssl-3-x64.dll` 1,579,008 B v3.5.5; a static OpenSSL 3.6.0 sits in `pyarrow/arrow_flight.dll` and `parquet.dll`, which `pyarrow.lib` does not load; `arrow.dll` uses bcrypt/ncrypt/WinHTTP, no `EVP_*`). OpenMP only `torch/lib/libiomp5md.dll` 1,310,600 B (Intel 5.0, build 20240820) + `libiompstubs5md.dll` 43,912 B (plus unrelated `sklearn/.libs/vcomp140.dll`). MKL/TBB: none. MSVC C++ runtime copies coexist by design (System32 `msvcp140.dll` 14.50.35719 used by torch; delvewheel-mangled `pyarrow.libs/msvcp140-f22b...dll` 14.44.35223 + `msvcp140_atomic_wait-...dll`; `numpy.libs`/`pandas.libs` mangled 14.40.33810; `vcruntime140.dll` 14.44.35211 next to python.exe) and are present in the passing orders too.

### 4. Mitigations, ranked (evidence)
1. **Import-order rule (recommended, code-level):** import `pyarrow` (or `pandas`) *before* `torch` in every entry point / test (X5 2/2 ok, X6 ok, L 2/2 ok, T4 ok). mimalloc then allocates its real slots while slot 63 is still NULL, and the later torch load cannot hurt it. Deferring `hashlib` (the current fix in `src/data/broadcast_timing.py:26`) only works by keeping the shift at 0 and breaks again for any pre-torch import that consumes 8 (or otherwise lands a non-NULL value on slot 63).
2. **Environment fallback:** `ARROW_DEFAULT_MEMORY_POOL=system` (3/3 ok). Keeps pyarrow off mimalloc; the swallowed load-time AV and the ~20 s `import pyarrow` stall remain, so it is a safety net, not the fix. `jemalloc` is not available in the Windows wheel.
3. **Upgrade pyarrow** to a build whose mimalloc initialises its TLS slots at process attach (mimalloc release notes list Windows TLS-slot/DLL-load fixes in v3.3.0; Arrow 25.0.0 bumped mimalloc to 3.3.1, but Arrow issue #50471 reports a different mimalloc-3.3.x thread-init crash) - unverified here.
4. **Not recommended:** `TlsSetValue(63, NULL)` before importing pyarrow (X4 ok) clobbers another DLL's slot; `OMP_NUM_THREADS`/`KMP_DUPLICATE_LIB_OK` (K), `pa.set_cpu_count(1)` (J) and `dtype=object` (I) do nothing.

### 5. Still unverified
- Which torch DLL writes `1` into slots 53/55 (61/63 after the shift) - not `libiomp5md.dll` on its own (X1); probably set lazily during torch's init.
- Why the swallowed exception costs ~20 s inside `LoadLibraryExW` (WER first-chance reporting or loader exception handling; no symbols for ntdll frames).
- Whether the original "hang" reports were exactly this (crash + WER dialog/report hold) - no `Application Hang` events exist for python.exe in 14 days, only `Application Error` events for `arrow.dll+0xbc542e`.
- Whether a newer pyarrow/mimalloc fixes it; whether other 8-slot consumers exist in the repo's import graph.

Scratch drivers (no repo files touched): `C:/Users/zpfh1/AppData/Local/Temp/claude/C--Users-zpfh1-Projects/789f73ca-11f1-4334-95b4-01773f4f4dc7/scratchpad/h1/run_cell_M_pool.py` (memory-pool env), `run_cell_T_tls.py` / `run_cell_U_tlsdiff.py` (TLS slot counting), `run_cell_V_veh.py` (VEH native fault info, TLS dumps, X1-X6), `pe_imports.py` / `pe_exports.py` (PE inspection).

Sources: [apache/arrow #50471](https://github.com/apache/arrow/issues/50471), [apache/arrow #37361](https://github.com/apache/arrow/issues/37361), [Arrow memory docs](https://arrow.apache.org/docs/python/memory.html), [mimalloc #1078](https://github.com/microsoft/mimalloc/issues/1078), [mimalloc](https://github.com/microsoft/mimalloc), [Old New Thing on unallocated TLS](https://devblogs.microsoft.com/oldnewthing/20221128-00/?p=107456), [golang #59213](https://github.com/golang/go/issues/59213), [Nynaeve explicit TLS](http://www.nynaeve.net/?p=181), [mimalloc v3.2.7 src/init.c](https://raw.githubusercontent.com/microsoft/mimalloc/v3.2.7/src/init.c), [mimalloc v3.2.7 include/mimalloc/prim.h](https://raw.githubusercontent.com/microsoft/mimalloc/v3.2.7/include/mimalloc/prim.h), [Arrow 24.0.0 versions.txt](https://raw.githubusercontent.com/apache/arrow/apache-arrow-24.0.0/cpp/thirdparty/versions.txt), [Arrow 24.0.0 ThirdpartyToolchain.cmake](https://raw.githubusercontent.com/apache/arrow/apache-arrow-24.0.0/cpp/cmake_modules/ThirdpartyToolchain.cmake)