# CODEX-CLI-SWEGCA-VRS-FCC

**No more context compaction.** About the name:

- **SWEGCA VRS** is the verification-reinforced synapse (&#xAC80;&#xC99D;&#xAC15;&#xD654;&#xC2DC;&#xB0C5;&#xC2A4;) that rebuilds each request.
- **FCC** stands for Full Context Continuity.

Welcome! This is a fork of [OpenAI Codex CLI](https://github.com/openai/codex) with **context compaction removed entirely**. Nothing summarizes, trims or remotely compacts your conversation. That covers automatic compaction, the manual compact task, remote compaction, and the token-limit trigger. The original session records (rollout files) are kept losslessly. Every model request is rebuilt from those originals by **libvrs**, a C++ assembly library linked right into the process.

Every place that builds model input calls that same assembly. That includes the first attempt, retries, guardian reviews and forks. There is no outside assembler process or socket, and there is deliberately no fallback. If assembly fails, you get an error rather than a request built from the accumulated history.

## Where things stand

- **Base:** `rust-v0.164.0-alpha.11.1` (`6905ece`), the Codex version bundled with ChatGPT desktop app 26.1021. The first VRS build was on `rust-v0.162.0-alpha.2` (`74e804dee`, tagged `vrs-base`) and was merged forward through `rust-v0.162.0-alpha.17.2` (v1.1.0 to v1.1.2).
- **Incremental tools:** upstream's experimental `incremental_tools` feature records instructions and tool definitions into the history. This fork rebuilds that prefix on every request instead, so the feature is accepted but ignored.
- **Branch:** `main`, with libvrs round 7 (`vrs-lib7/`). The work was done on a branch named `vrs-int`, which the design records still mention.
- **Release:** [`fcc-v1.1.3`](https://github.com/raspie10032/CODEX-CLI-SWEGCA-VRS-FCC/releases/tag/fcc-v1.1.3) has a prebuilt, stripped `codex` and `codex-code-mode-host` for x86_64 Linux.
- **macOS preview:** [`fcc-v1.1.2-macos.1`](https://github.com/raspie10032/CODEX-CLI-SWEGCA-VRS-FCC/releases/tag/fcc-v1.1.2-macos.1) is a prerelease for Apple Silicon (macOS 14.4 or newer). See [macOS (preview)](#macos-preview) below.
- **In daily use:** this fork has been the Codex binary of the maintainer's ChatGPT desktop app on Linux since 2026-10-13. It ran on the alpha.2 base with app 26.1002 until 2026-10-15, on alpha.17.2 with app 26.1007 until 2026-10-27, and since then on this base with app 26.1021.
- **Gates:** the application smoke gates (S1-S5) pass, with no failed receipts and no compaction events.
- **CI:** [`fcc-ci`](.github/workflows/fcc-ci.yml) builds and tests on x86_64 Linux with the prebuilt libvrs, then runs one mock-provider turn that must be assembled by VRS. Upstream's Bazel and multi-platform workflows are turned off in this repository: they need OpenAI's own runners and a toolchain the prebuilt library is not built for.
- **Real use (alpha.2 base):** this branch was measured across 5 threads with 2,577 model requests after it replaced the app's Codex. The long-run figures below are being measured again on the new base.
  - Result: zero compaction, zero errors or aborts, and every request assembled.
  - Two threads cleared the long-run bar (2 hours or 300 requests): 1,019 requests over 37 hours, and 961 requests.
  - The largest request was 127,480 tokens, 49% of the window.
- **Open defects:** no blocking defects are open. Smaller items are listed in the design document.

## Build

Building from this branch is Linux only (on other systems the store refuses to open). For a Mac, see [macOS (preview)](#macos-preview).

To skip building, download the binaries from the [`fcc-v1.1.3` release](https://github.com/raspie10032/CODEX-CLI-SWEGCA-VRS-FCC/releases/tag/fcc-v1.1.3). They were built on Ubuntu 24.04 (glibc 2.39) and run there and on newer distributions.

The library is already here: [`vrs-lib7/prebuilt/x86_64-linux-gnu/libvrs.a`](vrs-lib7/prebuilt/x86_64-linux-gnu/) is the exact libvrs round 7 used by the deployed build, with the SWEGCA C++ core compiled in. The Rust build links it by default, so this is all you need:

```bash
cd codex-rs
cargo build --release -p codex-cli
```

A few notes:

- The prebuilt archive is for x86_64 and was built with GCC 14.2.0 on Ubuntu 24.04 (glibc 2.39). It needs glibc 2.38 or newer and a `libstdc++` from GCC 13 or newer; CI links it on Ubuntu 24.04. The [prebuilt README](vrs-lib7/prebuilt/x86_64-linux-gnu/README.md) has the details.
- To link a different `libvrs.a`, set `VRS_LIB_DIR` to the directory that holds it. The library source is `vrs-lib7/vrs_lib.cpp`. The SWEGCA core sources it also needs are not included, only their compiled objects inside the prebuilt archive.
- Keep `codex-code-mode-host` in the same directory as `codex`. Code Mode is on by default in this base, and `codex` looks for the host next to itself; without it, Code Mode tool calls fail.
- To build the host too, add `-p codex-code-mode-host`. It links V8 from an archive that only OpenAI publishes for this configuration, so fetch it first: `l3check/ci/fetch_rusty_v8.sh . <dir>` downloads it from the `rusty-v8-v152.2.0` release of openai/codex and checks it against `third_party/v8`, as upstream CI does. Then set `RUSTY_V8_ARCHIVE` and `RUSTY_V8_SRC_BINDING_PATH` to the two files it prints.
- To use it with the ChatGPT desktop app, point `CODEX_CLI_PATH` at your build. The app picks its Codex binary from that variable.

## macOS (preview)

[`fcc-v1.1.2-macos.1`](https://github.com/raspie10032/CODEX-CLI-SWEGCA-VRS-FCC/releases/tag/fcc-v1.1.2-macos.1) is a prerelease of v1.1.2 for Apple Silicon, so it does not have the v1.1.3 base yet. It needs macOS 14.4 or newer on arm64. There is no Intel Mac build, and the Linux release is still the stable one.

- **Install:** download `fcc-v1.1.2-macos.1-aarch64-apple-darwin.tar.gz` and `SHA256SUMS` from the release, compare the archive's hash (`shasum -a 256 <archive>`), and extract it. Keep `codex` and `codex-code-mode-host` together in its `bin` directory, because Code Mode models need the host. Then run `./codex --version`.
- **ChatGPT desktop app:** export the absolute path of `codex` as `CODEX_CLI_PATH` in your login shell configuration, then quit the app completely and open it again. The override was inspected in app builds 26.1013.31256 and 26.1013.40934.
- **Signing:** the FCC `codex` is ad hoc signed and not notarized by Apple. `codex-code-mode-host` is the unmodified, signature-verified one from the ChatGPT app (version 0.163.0-alpha.10.2), not built from this source. `BUILD-INFO.json` in the archive records the source commit, hashes, build options and test results.
- **Source:** the macOS tag holds the port (FSEvents for file watching, Darwin's atomic wait/wake API), its tests and the arm64 `libvrs.a`. GitHub's source download for the tag and the attached `fcc-v1.1.2-macos.1-source.tar.gz` both contain the complete macOS commit. Build instructions are in `README-MACOS.md`.
- **Tested so far:** the native adapter, the VX06 to VX07 index migration, a CLI and app-server prediction-fork smoke, and authenticated Code Mode file-read and resume checks, all with zero compaction events. Multi-day stability on macOS has not been measured; the multi-day numbers in this README were measured on Linux.

## How it runs

- The store lives next to your sessions: rollouts in `$CODEX_HOME/sessions`, the index in `$CODEX_HOME/vrs/idx`. It is opened once at startup and restored in the background, usually in about half a second. A request that arrives while the store is still restoring waits for it instead of failing.
- The input budget follows the model's context window. For the desktop app's model that is 258,400 tokens. In everyday use the assembled requests usually stay under about 150k, so there is plenty of headroom. (That 150k figure is the maintainer's observation, not a benchmark.)
- Every past user message is **required input**. If those alone no longer fit the window, assembly reports that the required input is over budget, and the turn stops with an error instead of quietly dropping your words.
- **Instructions:** the base instructions in the model catalog (the bundled one and the one the server sends) tell the model that a long conversation gets compacted into a summary. Here that never happens, so those sentences are dropped before a request goes out, including for threads saved before this change. The rest of the instructions is sent unchanged, and instructions you supply yourself (`model_instructions_file`) are never edited.

## Known limitations

- **Very long sessions:** as above, a session whose user messages alone exceed the context window can no longer be continued.
- **Very long single turns:** every step of the turn in progress is required input too. A single autonomous turn whose own tool calls and outputs outgrow the window stops with a context-window error. Everyday turns stay far below that; long unattended agent runs can hit it.
- **Memory per process:** each Codex process loads its own copy of the store. The desktop app's app-server process was observed at about 3.6 GB resident.
- **Upstream README:** everything below the divider is the unmodified upstream README, so some of its descriptions do not match this fork.

## Documentation

The design documents are written in Korean.

- [VRS\_&#xCF54;&#xB371;&#xC2A4;&#xC77C;&#xCCB4;&#xD654;\_v1.md](VRS_%EC%BD%94%EB%8D%B1%EC%8A%A4%EC%9D%BC%EC%B2%B4%ED%99%94_v1.md): goals, definitions, proofs, tests and deployment records for every round.
- [vrs-lib5/](vrs-lib5/), [vrs-lib6/](vrs-lib6/), [vrs-lib7/](vrs-lib7/): library sources, patches, tests and reports for rounds 5-7.
- [l3check/](l3check/): integration audits, test classification and the application smoke gates.

Paths in these records are written relative to `~` or as `$WORK/`, a stand-in for the maintainer's working directory, so some of the older test scripts need their paths adjusted before they run elsewhere. The release smoke test in [l3check/release1/](l3check/release1/) runs anywhere: `./run.sh <path-to-codex>`.

---

<p align="center"><strong>Codex CLI</strong> is a coding agent from OpenAI that runs locally on your computer.
<p align="center">
  <img src="https://github.com/openai/codex/blob/main/.github/codex-cli-splash.png" alt="Codex CLI splash" width="80%" />
</p>
</br>
If you want Codex in your code editor (VS Code, Cursor, Windsurf), <a href="https://developers.openai.com/codex/ide">install in your IDE.</a>
</br>If you want the desktop app experience, run <code>codex app</code> or visit <a href="https://chatgpt.com/codex?app-landing-page=true">the Codex App page</a>.
</br>If you are looking for the <em>cloud-based agent</em> from OpenAI, <strong>Codex Web</strong>, go to <a href="https://chatgpt.com/codex">chatgpt.com/codex</a>.</p>

---

## Quickstart

### Installing and running Codex CLI

Run the following on Mac or Linux to install Codex CLI:

```shell
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

Run the following on Windows to install Codex CLI:

```shell
powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"
```

The standalone installers download from `https://releases.openai.com/codex` by default and fall back to GitHub Releases if a metadata or asset download is unavailable. To force GitHub Releases, set `CODEX_INSTALLER_USE_RELEASES_OPENAI_COM` to `false` (`0` and `no` are also accepted):

```shell
curl -fsSL https://chatgpt.com/codex/install.sh | CODEX_INSTALLER_USE_RELEASES_OPENAI_COM=false sh
```

```powershell
$env:CODEX_INSTALLER_USE_RELEASES_OPENAI_COM='false'; irm https://chatgpt.com/codex/install.ps1 | iex
```

Codex CLI can also be installed via the following package managers:

```shell
# Install using npm
npm install -g @openai/codex
```

```shell
# Install using Homebrew
brew install --cask codex
```

Then simply run `codex` to get started.

<details>
<summary>You can also go to the <a href="https://github.com/openai/codex/releases/latest">latest GitHub Release</a> and download the appropriate binary for your platform.</summary>

Each GitHub Release contains many executables, but in practice, you likely want one of these:

- macOS
  - Apple Silicon/arm64: `codex-aarch64-apple-darwin.tar.gz`
  - x86_64 (older Mac hardware): `codex-x86_64-apple-darwin.tar.gz`
- Linux
  - x86_64: `codex-x86_64-unknown-linux-musl.tar.gz`
  - arm64: `codex-aarch64-unknown-linux-musl.tar.gz`

Each archive contains a single entry with the platform baked into the name (e.g., `codex-x86_64-unknown-linux-musl`), so you likely want to rename it to `codex` after extracting it.

</details>

### Using Codex with your ChatGPT plan

Run `codex` and select **Sign in with ChatGPT**. We recommend signing into your ChatGPT account to use Codex as part of your Plus, Pro, Business, Edu, or Enterprise plan. [Learn more about what's included in your ChatGPT plan](https://help.openai.com/en/articles/11369540-codex-in-chatgpt).

You can also use Codex with an API key, but this requires [additional setup](https://developers.openai.com/codex/auth#sign-in-with-an-api-key).

## Docs

- [**Codex Documentation**](https://developers.openai.com/codex)
- [**Contributing**](./docs/contributing.md)
- [**Installing & building**](./docs/install.md)
- [**Open source fund**](./docs/open-source-fund.md)

This repository is licensed under the [Apache-2.0 License](LICENSE).
