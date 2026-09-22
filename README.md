# llama.cpp on Intel Mac + Radeon Pro Vega 48

A reproducible Vulkan setup for running **HauhauCS Qwen3.5 2B Aggressive, Q4_K_M** on an Intel Mac with a discrete AMD GPU. The verified class of machine is a six-core Intel iMac with a Radeon Pro Vega 48. The working configuration uses **upstream llama.cpp**, with **MoltenVK translating Vulkan to Metal**. No custom inference-kernel patch is needed for the successful path.

**No model weights, compiled binaries, personal logs, credentials, or machine identifiers are included in this repository.** Installation scripts download build dependencies and source code. Model downloading is a separate, explicit step.

## Fast profile (verified 2026-09-19)

Run it with **manual start only** (`llama start` / `llama stop`). It does **not** run at login. Context is the model's native **262,144** tokens. All 6 CPU cores and all 25 GPU layers are in use.

Canonical copies:

- `config/local.llama-vega.plist` — example LaunchAgent; regenerate it with `scripts/run.py` so paths match your machine
- `config/fast-profile.json` — same flags as JSON
- `scripts/run.py` — regenerates that plist (`--install-service` writes it, does **not** enable login)
- `scripts/llama.py` → `~/.local/bin/llama`

```sh
llama start    # or: llama-start
llama stop     # or: llama-stop
```

Chat: **http://127.0.0.1:18435/**  
API: **http://127.0.0.1:18435/v1**  
Alias: `HauhauCS-Qwen3.5-2B-Aggressive`  
Example model path: `/opt/llama-cpp-intel-mac-vega/models/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf` (pass any path with `--model`).

### Measured on the verified hardware

| Run | Prefill | Decode |
| --- | --- | --- |
| Fast profile, long prompt | 1741 tok in 18s, **93.51 tok/s** | 61 tok in 1.7s, 36.81 tok/s |
| Same profile, short tool call | 77.58 tok/s prefill | **55.84 tok/s** decode (58 tok / 1.0s) |
| Broken experiment (`-fa on` + q8 KV + 32k ctx) | 41.77 tok/s on 170 tok | **11.44 tok/s** — do not restore |

GPU already had all layers before the thread bump. Decode lives on Vega 48; CPU should not sit at 100% during generation.

### Every live flag

| Flag | Value | Keep it |
| --- | --- | --- |
| `--device` | `Vulkan0` | Yes. Explicit Radeon. |
| `-ngl` | `all` | Yes. 25/25 layers on GPU. |
| `--load-mode` | `none` | Yes. Leave it. |
| `-c` | `262144` | **Yes. Native window. Do not shrink.** |
| `-np` | `1` | Yes. One slot. |
| `-b` / `-ub` | `2048` / `512` | Yes. Server defaults; helped prefill. |
| `-t` / `-tb` | `6` / `6` | **Yes. All 6 cores.** Old cap was `2`. |
| `-fa` | `auto` | **Yes. Not `on`, not `off`.** |
| `--jinja` | on | Yes. Model template. |
| `--reasoning` | `off` | Yes. Direct answers. |
| `--temp` `--top-p` `--top-k` `--min-p` | `0.6` `0.95` `20` `0` | Yes. Qwen coding/chat defaults. |
| `--cache-ram` | `8192` | Yes. 8 GiB host prompt cache. |
| `--cors-origins` | `localhost` | Yes. Loopback only. |
| `-lv` | `4` | Trace logs. Harmless. |
| `--poll` / `--poll-batch` | `1` / `1` | Yes. Leave. `50` was a docs misread. |
| `--threads-http` | `6` | Yes. |
| `--metrics` | on | Yes. |
| `--presence-penalty` / `--repeat-penalty` | `0` / `1` | Yes. |
| `--tools` | `all` | Yes. Built-in server tools. |
| LaunchAgent `RunAtLoad` | `false` | **Yes. Manual only.** |
| LaunchAgent `KeepAlive` | `false` | **Yes.** |
| LaunchAgent `Nice` | *removed* | **Do not add `Nice 5` back.** |

Environment: `VK_ICD_FILENAMES` → Homebrew MoltenVK ICD JSON.

### Do not change these (they made it slow)

| Change | What happened |
| --- | --- |
| `-t 2 -tb 2` + `Nice 5` | Old desktop-responsiveness cap. Only 2 of 6 cores. |
| `-c 32768` | Cut native 256k context. User needs the full window for real work. |
| `-fa on` | MoltenVK/AMD log: *Flash Attention assigned to device CPU*. Gen **55 → 11 tok/s**. |
| `-ctk q8_0 -ctv q8_0` | KV quant on this Vulkan stack wrecked decode. Keep default f16. |
| `--poll 50` | Docs default; not the fast profile. Leave `--poll 1`. |
| `--load-mode mmap` | Unproven here. Keep `none`. |
| `--prio 2` | Needs root. `Permission denied`. Skip. |
| `RunAtLoad true` / `KeepAlive` crash-restart | Loads the 2B model at login and holds the GPU. Use `llama start` instead. |

### Shell aliases (`~/.zshrc`)

```sh
export PATH="$HOME/.local/bin:$PATH"
alias llama-start='llama start'
alias llama-stop='llama stop'
```

## Start here: both parts of the fix

1. **GPU inference:** build upstream llama.cpp with Vulkan/MoltenVK and select the Radeon explicitly.
2. **Responsive Hermes startup:** use the lightweight Hermes setup below. The original Hermes request included 13,802 prompt tokens; the compact prompt and tool schemas measured 1,095 tokens in offline tokenization, about 92% fewer. The model's available context remains 262,144 tokens.

`setup_hermes.py` now installs the lightweight prompt patch and its configuration **by default**. This is part of the Intel Mac recipe, not a step left for the operator to discover. No model files or personal configuration are included here.

## Verified result

| Item | Verified configuration |
| --- | --- |
| Computer class | Intel iMac, six-core 3.7 GHz Core i5 |
| System memory | 32 GB |
| GPU | Radeon Pro Vega 48, 8 GB dedicated VRAM |
| Operating system | macOS 15.7.9 |
| llama.cpp | `b10985`, commit `7609846557c50f9d984719a9e1e8c5f3d02f807b` |
| Backend | Vulkan, MoltenVK 1.4.2 |
| Model | HauhauCS Qwen3.5 2B Aggressive, Q4_K_M |
| GPU placement | 25/25 model layers offloaded |
| Context / simultaneous requests | **262,144** tokens / one (live). Early smoke used 8,192. |
| Warm generation | Short decode **~56 tok/s**; long-prompt prefill **~93 tok/s** (2026-09-19 fast profile) |
| Observed GPU activity | Up to 95% during the initial validation |

An arithmetic request returned `391` for `17 × 23`. An explanation of the blue sky returned readable, relevant English. A Python function response contained the requested maximum-finding logic. A separate request correctly named red, green, and blue as the primary colors of light.

These are **smoke checks on one physical machine**, not a comprehensive model-quality benchmark. The Python response hit its 180-token output limit; its complete surrounding explanation was not evaluated. The initial arithmetic request included first-request overhead and was slower than warm requests. Activity samples measure the GPU as a whole, including other apps; the server's explicit device and layer-placement logs provide the additional attribution evidence.

The same hardware and OS should be a reasonable reproduction target. Other Intel Mac GPUs, older macOS releases, different models, and future dependency combinations are **not verified by these results**. Apple Silicon uses a different preferred setup.

## Why this setup matters

There were two separate failures in the investigated configuration:

1. The stock Intel llama.cpp release executable did not expose a Metal GPU device. A runtime directory named `metal` did not establish that GPU acceleration was actually present. Use `--list-devices` to check the executable itself.
2. A locally compiled Metal backend could place all 25 layers on the Vega 48 and generate about 49 tokens/second, but returned corrupted text. High speed and allocated VRAM were insufficient proof of success.

The successful configuration uses the official Vulkan build path, explicitly selects the Radeon, disables Flash Attention, and checks actual generated answers. llama.cpp's issue tracker documents correctness and scheduling problems on some non-Apple-Silicon Metal devices, including Vega/GCN hardware with 64-wide execution groups. This repository does **not** assert that a single issue explains every affected Mac.

Early smoke checks used 8K context and two CPU threads so the desktop stayed responsive. The **live profile is 262,144 context and six threads**. Do not shrink context “for speed”; that was tried and rejected. The 8K / 2-thread table below is historical only.

## 1. Prerequisites

- Intel Mac running macOS 15 or newer; only 15.7.9 is verified here.
- Radeon Pro Vega 48 for the verified hardware configuration.
- Xcode Command Line Tools, Python 3, and [Homebrew](https://brew.sh/).
- Several GB of free disk space for source, generated shaders, and compiler output, in addition to your model.

Check tools:

```sh
xcode-select -p
python3 --version
brew --prefix
```

If the Command Line Tools are absent, run `xcode-select --install` and complete Apple's installer. Do not delete an existing toolchain merely because Homebrew prints a generic update suggestion.

## 2. Build the runtime

From a checkout of this repository:

```sh
python3 scripts/bootstrap.py
```

The script:

1. Verifies that this is Intel macOS.
2. Installs the Vulkan loader, MoltenVK, headers, OpenSSL, and CMake through Homebrew.
3. Retrieves a **pinned, SHA-256-verified Intel shaderc 2026.3 bottle** from Homebrew's GHCR registry. This avoids compiling shaderc and its large dependencies from scratch on an older desktop.
4. Downloads and verifies the exact llama.cpp source archive listed in `versions.json`.
5. Builds `llama-server` with `GGML_VULKAN=ON`, `GGML_METAL=OFF`, and native CPU support.
6. Copies the server and required llama.cpp libraries into a runtime directory, changes build-directory library search paths to `@loader_path`, and applies local ad-hoc signatures.
7. Lists the devices available to the installed server.

The default installation root is `~/.local/share/llama-vega`. `--home PATH` changes it. The model is not downloaded by this script.

The compiler runs at **nice priority 15**, with **two make jobs**. For a more responsive machine during compilation:

```sh
python3 scripts/bootstrap.py --jobs 1
```

Upstream shader generation has its own internal concurrency, so the make job count is not a strict limit on every compiler subprocess. Avoid running multiple builds or inference jobs at the same time. Once installed, no compilation is needed to chat.

If dependencies are already installed:

```sh
python3 scripts/bootstrap.py --skip-dependencies
```

Advanced: import an existing, trusted `build/bin` made from the pinned source:

```sh
python3 scripts/bootstrap.py --skip-dependencies --import-build /path/to/llama.cpp/build/bin
```

The import checks for the server and Vulkan library; it does not independently authenticate the provenance of your existing build.

### Reproducibility boundaries

`versions.json` pins the llama.cpp source and shader compiler archive with hashes, and records the tested Homebrew dependency versions. Homebrew installs its currently available dependencies; those dependencies are **recorded, not forcibly downgraded**. Upstream's server build can also retrieve its web-UI assets. This is a pinned source recipe and a tested configuration, **not a promise of byte-identical builds**.

Do not commit generated runtimes or build directories. Binaries can embed local source paths even after runtime library paths are fixed.

## 3. Obtain the model separately

Model page: [HauhauCS/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive](https://huggingface.co/HauhauCS/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive).

The verified file is **Q4_K_M**, 1,270,808,032 bytes. The vision projector is not needed for text chat and was not part of this validation.

If you already have this GGUF, use its current location. Otherwise this explicit command downloads the model into a directory outside the repository:

```sh
mkdir -p "$HOME/Models"
curl -fL --retry 3 \
  'https://huggingface.co/HauhauCS/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive/resolve/2bcf35c1ebf62c837c12c1aa90b578ff4717e831/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf' \
  -o "$HOME/Models/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf.part"
shasum -a 256 "$HOME/Models/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf.part"
```

Expected SHA-256:

```text
be3ccca13a9d1bc8b67165ea80bd103cd6151a37ad131183cc7ca388f78d9517
```

Only after the hash matches, rename the file:

```sh
mv "$HOME/Models/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf.part" \
   "$HOME/Models/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf"
```

The model's “uncensored” description and refusal evaluations belong to its publisher. This project's validation concerns runtime correctness, GPU use, and speed.

## 4. Run and chat

```sh
python3 scripts/run.py \
  --model "$HOME/Models/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf"
```

Then open **http://127.0.0.1:18435/**. This is llama.cpp's own built-in chat UI. Keep the terminal running, or write the LaunchAgent below and use `llama start` / `llama stop`. It does **not** start at login.

The API base URL for a compatible local client is **http://127.0.0.1:18435/v1**, and the default model alias is `HauhauCS-Qwen3.5-2B-Aggressive`. This setup listens on the loopback interface and limits browser CORS origins to localhost. The live profile enables llama.cpp's built-in `--tools all` (loopback only).

The launcher refuses to proceed if the selected device is not an available AMD Vulkan device; it does not silently switch to CPU. Defaults match the live fast profile: `--device Vulkan0`, `--port 18435`, `--context 262144`, six threads, batch 2048/512, `-fa auto`. `--runtime PATH` and `--alias NAME` can be specified explicitly.

### Exact working settings (live)

See **Live fast profile** at the top of this file and `config/fast-profile.json`. Summary:

| Setting | Live value | Do not revert to |
| --- | --- | --- |
| Backend build | Vulkan on, Metal off | Metal (gibberish on Vega) |
| Device / layers | `Vulkan0` / `all` | CPU or partial offload |
| Load mode | `none` | `mmap` (unproven) |
| Context | `262144` | `8192` or `32768` |
| Parallel slots | `1` | >1 |
| Batch / microbatch | `2048` / `512` | `256` / `128` |
| CPU threads | `6` / `6` | `2` / `2` |
| Flash Attention | `auto` | `on` (CPU fallback, ~11 tok/s) or forced `off` unless you are debugging gibberish |
| KV cache type | default f16 | `q8_0` |
| Sampling | temp 0.6, top-p 0.95, top-k 20, min-p 0 | 0.7 / 0.8 from the old 8K profile |
| Host prompt cache | `8192` MiB | `256` |
| Login | off (`RunAtLoad` false) | `RunAtLoad` true / `Nice` 5 |

The verification script uses temperature 0 to make its short checks more consistent. Those timings describe verification, not the live chat profile.

## 5. Verify real GPU inference

In a second terminal:

```sh
python3 scripts/verify.py
```

This checks the health endpoint, retrieves the actual web UI, asks three short questions, prints replies and timings, and samples non-identifying GPU counters. It checks answer content and successful completion; a health response alone does not count as success. Its content checks are intentionally narrow and do not constitute a full correctness benchmark.

Look for lines like these in server output:

```text
using device Vulkan0 (AMD Radeon Pro Vega 48)
offloaded 25/25 layers to GPU
Vulkan0 model buffer size = 1201.48 MiB
Vulkan0 KV buffer size = 3072.00 MiB   # 256k context; 8K smoke was 96 MiB
```

Use **Activity Monitor → Window → GPU History** while a response is being generated. Red in the CPU history graph means system CPU time; it is not a GPU-use indicator. Low GPU activity between requests is normal. A two-billion-parameter model need not consume all 8 GB of VRAM to use the GPU effectively.

The bundled UI uses compressed assets. A simplistic HTTP client requesting only an uncompressed response can receive HTTP 415. `verify.py` explicitly requests gzip; ordinary browsers already support it.

## 6. Optional: write the LaunchAgent (manual start, not login)

Stop the foreground server first with Control-C, then:

```sh
python3 scripts/run.py \
  --model "/opt/llama-cpp-intel-mac-vega/models/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf" \
  --install-service
```

This writes a user LaunchAgent named `local.llama-vega`. It requires no system daemon and no administrator privileges. Moving the model or runtime afterward requires reinstalling the service with the new paths.

`--install-service` **only writes** `~/Library/LaunchAgents/local.llama-vega.plist` with `RunAtLoad` false and `KeepAlive` false. It does **not** start at login. Use `llama start` / `llama stop`. There is no nice-priority cap.

Inspect:

```sh
launchctl print "gui/$(id -u)/local.llama-vega"
tail -n 60 "$HOME/Library/Logs/llama-vega.log"
```

## Terminal shortcut

After installing the service, install the command:

```sh
mkdir -p "$HOME/.local/bin"
install -m 755 scripts/llama.py "$HOME/.local/bin/llama"
```

Ensure `~/.local/bin` is on your shell's `PATH`. Then:

```sh
llama start
llama stop
```

`llama start` (or bare `llama`) enables and starts the service, waits for readiness, and opens the chat page. It reuses an already-running model. `llama stop` disables the service and unloads it, freeing the model's GPU memory. It will **not** come back at login. The chat browser can remain open; its model backend is stopped. Model files are retained.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Device list contains only BLAS/Accelerate | The executable lacks a working GPU backend. BLAS is CPU acceleration. Confirm the Vulkan build and ICD path. |
| Intel GPU selected | Read `--list-devices` and select the Radeon device explicitly. Device numbering may differ. |
| Fast gibberish | Do not accept throughput as proof. Confirm Vulkan/MoltenVK, `-fa auto` (not `-fa on`), model hash, chat template, and readable smoke-check output. `-fa on` on this Vega/MoltenVK stack assigned Flash Attention to CPU and dropped gen to ~11 tok/s. |
| Model loads but takes minutes to answer | Check actual GPU placement (`25/25` layers), that `-c` is still 262144, and prompt length. Do not shrink context as a speed hack. |
| Build makes the desktop sluggish | Use `--jobs 1`; avoid concurrent builds or inference. Prefer the pinned shader compiler binary over building shaderc from source. |
| Port already in use | Stop the other server or choose a different `--port`. Do not start duplicate model servers. |
| GPU idle after an answer | Expected: inference work has finished. Observe GPU History during generation. |
| Model not in another app's picker | Configure that app's custom OpenAI-compatible endpoint explicitly. This project does not modify existing app profiles. |
| Service fails after source cleanup | Inspect `otool -l` search paths. Runtime libraries must resolve from the installed runtime, not a removed build tree. |
| CPU architecture changed | Rebuild on the target computer. `GGML_NATIVE=ON` optimizes for the build CPU; copying native binaries to a different Intel generation is not validated. |

## Cleanup

Stop and remove only this project's service:

```sh
launchctl bootout "gui/$(id -u)/local.llama-vega"
rm "$HOME/Library/LaunchAgents/local.llama-vega.plist"
```

After verifying the installed runtime, its `source`, `build`, `toolchain`, and `cache` subdirectories can be removed to recover disk space. Keep `runtime`. Keep Homebrew's Vulkan loader, MoltenVK, and OpenSSL installed: the runtime links to those dependencies. No script deletes models or modifies other inference installations.

## What stays off this tree

Model weights, compiled binaries, runtime logs, and generated LaunchAgents are not included. `.gitignore` excludes those artifacts. The checked-in LaunchAgent example uses `/opt/llama-cpp-intel-mac-vega` placeholders. Regenerate the real plist on your Mac with `scripts/run.py --install-service`.

Do not commit system-profiler output, runtime logs, or build logs. They can contain local paths.

## Primary references

- [llama.cpp build instructions, Vulkan on macOS](https://github.com/ggml-org/llama.cpp/blob/7609846557c50f9d984719a9e1e8c5f3d02f807b/docs/build.md)
- [Exact upstream release b10985](https://github.com/ggml-org/llama.cpp/releases/tag/b10985)
- [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/tree/7609846557c50f9d984719a9e1e8c5f3d02f807b/tools/server)
- [MoltenVK](https://github.com/KhronosGroup/MoltenVK)
- [Homebrew shaderc formula containing the pinned Intel bottle](https://github.com/Homebrew/homebrew-core/blob/4cca0351efd02828ff8adcff9de9f144c19e793a/Formula/s/shaderc.rb)
- [Vega/GCN Metal concurrency issue #25866](https://github.com/ggml-org/llama.cpp/issues/25866)
- [Intel/discrete-GPU Metal buffer alignment issue #26949](https://github.com/ggml-org/llama.cpp/issues/26949)
- [Vulkan correctness discussion on Intel Macs #20104](https://github.com/ggml-org/llama.cpp/issues/20104)

Issue reports are hardware-specific observations, not blanket guarantees. The working configuration and the measured results above are the basis for this recipe.


## Full-context configuration and Hermes

The baseline measurements above used 8K context and direct answers. An additional configuration loads the model's full native **262,144-token** window with reasoning enabled. That window includes input and output; filling it is substantially more work than a short chat. This setting does not make a 2B model equivalent to a larger model.

For full context, native host tools, and persistent always-allow browser preferences:

```sh
python3 scripts/configure_ui.py --allow-host-tools
python3 scripts/run.py \
  --model "$HOME/Models/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf" \
  --context 262144 --reasoning on --host-tools \
  --ui-path "$HOME/.local/share/llama-vega/ui" --install-service
```

The UI script seeds the seven built-in server tools as always allowed once per browser profile. Existing chats are retained. Subsequent permission changes remain under the user's control. Tools execute on the host, starting in the user's home directory, with that macOS account's permissions. OS administrator/Privacy permissions remain separate from application tool approvals.

Configure an **existing Hermes installation** without launching Hermes:

```sh
"$HOME/.hermes/hermes-agent/venv/bin/python" scripts/setup_hermes.py --allow-host-tools
```

This sets the custom Chat Completions endpoint to `http://127.0.0.1:18435/v1`, model `HauhauCS-Qwen3.5-2B-Aggressive`, and context 262144. The key `local` is a placeholder for the keyless loopback server. Hermes's own model manager is disabled to avoid launching a competing CPU-only runtime. Hermes still uses its own tools.

The explicit `--allow-host-tools` option disables Hermes command approvals, user-defined deny rules, the optional tirith scanner, and protected-instruction-file confirmation, and enables automatic hook acceptance. Omit this option to retain those existing settings. No Hermes process is launched by the setup script.

Text auxiliary tasks route to the main local model; automatic title generation is disabled to avoid extra inference competing with the main request. Terminal execution is native/local. Compression begins at 85% of its input budget rather than 50%; its lean tail strategy preserves a summary and recent context. Both clients permit up to 1000 tool cycles before their continuation limit.

Then run:

```sh
llama start
hermes
```

Exit any provider-selection dialog opened before configuration and start a fresh Hermes session so it reads the saved settings. `llama stop` disables and unloads the backend. Hermes testing is intentionally left to the operator; the setup script only changes configuration.

### Settings review

- GPU placement stays Vulkan/Radeon, all layers and F16 KV cache on GPU. Flash Attention is **`auto`**, not `on` (CPU fallback) and not forced `off` unless debugging gibberish.
- Full-context mode uses batch 2048, microbatch 512, 8 GiB host prompt-cache, one request slot, **six** compute threads, six HTTP threads. Do not go back to two threads.
- Reasoning uses Qwen's precise-coding sampling recommendation: temperature 0.6, top-p 0.95, top-k 20, min-p 0, presence penalty 0, repetition penalty 1. No artificial server output cap is added. Prior reasoning is excluded from browser history context following Qwen's recommendation.
- Model-native RoPE, EOS handling, Jinja template, prompt reuse, and warm-up remain enabled/default. No unsupported context extrapolation or grammar constraints are imposed.
- Speculative draft models, MoE placement, LoRA/control vectors, embeddings, reranking, multi-GPU splits, image/video/audio projector settings, and synthetic benchmarking options do not apply to this single-GPU text configuration and remain unused.
- Localhost binding and localhost CORS remain enabled. They do not sandbox local tool execution.
- These are a verified hardware configuration and deliberate tradeoffs, not a mathematical guarantee of maximal speed or intelligence for every workload.

References: [Hermes configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration), [Hermes custom providers](https://hermes-agent.nousresearch.com/docs/integrations/providers), [Qwen sampling and context guidance](https://huggingface.co/Qwen/Qwen3.5-2B).


## Lightweight Hermes prompt

This repository ships a narrowly scoped, opt-in prompt patch in `hermes-minimal-prompt.patch`. It replaces the generated identity/guidance/skills/context bundle when `agent.base_system_prompt` is set. New sessions use `You are a helpful assistant.`. Normal Hermes prompt behavior is unchanged when this option is absent.

`agent.compact_tool_descriptions: true` shortens tool documentation while retaining tool names, parameter types, required fields, defaults, and constraints. The local profile uses the `terminal` and `file` toolsets rather than advertising unrelated tools on every request. Shell and file access remain native, with the existing approvals settings. Reasoning effort is `none` for direct replies.

The prompt replacement is per-agent and goes through Hermes's existing cached prompt tiers. Start a fresh Hermes process after applying it; an already-running process retains its imported code and prompt. Hermes updates may overwrite the patch, so review and reapply it against the installed version when necessary. No claim of an end-to-end Hermes timing test is made: only prompt assembly and tokenization were checked, without starting a Hermes session or generating an answer.


### Reproduce the complete Hermes change

With the GPU runtime installed and your model available:

```sh
python3 scripts/run.py \
  --model "$HOME/Models/Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf" \
  --context 262144 --install-service
"$HOME/.hermes/hermes-agent/venv/bin/python" scripts/setup_hermes.py --allow-host-tools
mkdir -p "$HOME/.local/bin"
install -m 755 scripts/llama.py "$HOME/.local/bin/llama"
```

Then exit any old Hermes process and start a fresh `hermes` session yourself. Setup does not start Hermes or send a model request. The `--allow-host-tools` flag is the explicit choice to apply the native access/approval settings documented above.

The setup command checks the patch against your installed files before applying it. Re-running it recognizes an already-applied patch. A mismatched Hermes revision stops before modifying configuration. The tested source revision is recorded in `versions.json`; the patch contains only the relevant changes to `agent/agent_init.py` and `agent/system_prompt.py`.

For nonstandard installations, pass `--home PATH` for the Hermes configuration directory and `--repo PATH` for its source checkout. `--standard-prompt` skips lightweight prompt installation/configuration and leaves existing prompt/tool preferences in place; it does not undo a previously applied lightweight profile.

`hermes-config.example.yaml` is a sanitized reference for the final settings. Use the setup script to merge them into an existing installation rather than replacing an entire personal config file with this example. Full native context, the custom local endpoint, direct replies, native terminal/file tools, and approvals settings are carried by that script. Other built-in Hermes toolsets are no longer advertised by default; the terminal can still perform local operations with the user's account permissions.

Parameter names, types, required fields, validation constraints, and literal defaults remain in the compact schemas. Long descriptive prose is removed. `agent.base_system_prompt` replaces Hermes's generated identity, skills, memory, workspace, and guidance prose for this profile; those omitted blocks are intentionally not silently reintroduced. It is an opt-in local source extension, not an upstream Hermes setting until the patch is applied.


## Responsive desktop and true context settings

The active local profile keeps the model's native 262,144-token window; shrinking the startup instructions does not shrink that window. This was checked against both GGUF metadata and the running server's `/props` response. Hermes explicitly receives the same context length.

Compaction is enabled at 85% of the available input budget: 222,822 tokens when no separate output reservation is configured. A positive output reservation reduces the input budget first. Absolute token caps and per-model threshold overrides are cleared; idle compaction, per-turn micro-compaction, and proactive pruning are disabled. This leaves roughly 39K tokens of headroom at the default trigger instead of waiting for an over-capacity error.

The `lean` compaction strategy is retained to avoid replaying a huge verbatim tail after a summary. `target_ratio` is 0.2; it is not a promise of a 20% verbatim tail in lean mode. Archived session history is separate from the model's finite live context. Normal short conversations should not reach this threshold. Very long input still takes time to process; no full-window speed or freeze-free guarantee is implied.

Hermes's `◎ 84%` indicator means prompt-cache reuse, not 84% context usage. Its context indicator is a separate value.

A short comparison in the original 8K profile measured ~56 tok/s with two CPU threads vs ~55–56 with three, so two threads were kept then. **That is obsolete.** The live profile uses all **six** cores, no nice cap, 256k context, and `-fa auto`. Direct-answer mode stays the default. These checks used the llama.cpp API, not a new Hermes session.

The native context size comes from [Qwen's model specification](https://huggingface.co/Qwen/Qwen3.5-2B). Compaction settings follow [Hermes's official configuration reference](https://hermes-agent.nousresearch.com/docs/user-guide/configuration#context-compression) and the installed compressor's threshold calculation.
