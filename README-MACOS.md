# FCC v1.1.2 Apple Silicon macOS preview

This port targets Apple Silicon Macs running macOS 14.4 or newer. It keeps the
round-7 VRS assembler and removes context compaction exactly as the Linux fork
does. Intel Macs are not included in this release.

This release includes the 1.1.2 fixes for VRS input in ephemeral prediction
forks, parent-history references, Markdown-link user messages, and release of
idle thread history. Its upstream base is `b783265f784ec54539fbc37594fd35e37d1ab869`.
The first launch rebuilds older VX06 indexes as VX07 from the unchanged original
session records.

## Install

Extract the macOS ARM64 binary archive, keep `codex` and
`codex-code-mode-host` together in the same directory, and run `codex`:

```sh
./bin/codex --version
./bin/codex
```

The FCC CLI is ad hoc signed, not Apple notarized. It uses your normal Codex
authentication and configuration. Keep the official bundled executable available
for rollback.

For the ChatGPT desktop app, place the binary at a stable path and export that
absolute path as `CODEX_CLI_PATH` in the login shell configuration. For zsh, an
example line in `~/.zprofile` is:

```sh
export CODEX_CLI_PATH="$HOME/.local/bin/codex-fcc"
```

Completely quit and reopen ChatGPT after changing this setting. This selection
path was inspected in desktop apps 26.1013.31256 and 26.1013.40934. Confirm the actual app-server child
executable after restart: an invalid absolute override can cause the app to
select its bundled binary. The existing running session is not switched by an
environment change alone.

To return to the bundled version, remove the export, run
`launchctl unsetenv CODEX_CLI_PATH` if it was also set there, and completely
restart the app. Original rollout files are retained.

## Build

Check out tag `fcc-v1.1.2-macos.1`, or use the macOS source bundle attached to the
release. Both include this port and the ARM64 static library. Unlike the first
macOS preview, the tag identifies the complete macOS source commit.

```sh
cd codex-rs
MACOSX_DEPLOYMENT_TARGET=14.4 cargo build --locked --release -p codex-cli
```

Rust 1.95.0 is pinned by the repository. On an 8 GB Mac the release was built
with two Cargo jobs, release debug information disabled, thin LTO disabled, and
16 codegen units to limit build memory. The C++ assembler is optimized with `-O2`.

The included Code Mode host is the unmodified, signature-verified companion from
ChatGPT.app 26.1013.31256; the staged 26.1013.40934 app contains identical bytes.
Its package version is 0.163.0-alpha.10.2. The FCC CLI remains on the upstream
0.162.0-alpha.17.2 base, so `codex --version` reports that upstream version.
The FCC release version, hashes, exact source commit, companion provenance and
runtime test results are recorded in `BUILD-INFO.json`.

The companion was reused from the installed app, not built from the attached
source. The first preview's local helper build could not fetch the required
sandbox-enabled V8 archive. A complete helper source build was not performed
for this update.

The standalone archive includes the CLI and Code Mode host. Optional desktop
voice and bundled shell/search resources are not included. The maintainer's
local desktop installation links those resources from the existing app package.

To rebuild only libvrs from its original SWEGCA core sources:

```sh
bash vrs-lib7/build-macos.sh /path/to/swegca_cpp
```

## Validation and limits

The macOS native adapter is covered by `vrs-lib7/test-macos.py`: recursive file
creation, external append, atomic rename, direct inserts, original user message
retention, over-budget failure, timed waits, fork wakeup, restart and shutdown.
`vrs-lib7/test-macos-migration.py` reproduces the old link-message omission,
opens that VX06 index with the new library, checks the over-budget error and all
24 original user messages, and verifies that rollout bytes are unchanged.

`vrs-lib7/test-macos-app.py` exercises the real CLI and app-server with a local
mock provider: new conversation, resume, ephemeral prediction fork, fork unload
and parent continuation. It checks original input, VRS receipts and absence of
compaction events. Authenticated Code Mode file-read and resume checks are
reported separately in the release build information. Static inspection of the
desktop app is not a claim of a completed GUI restart or multi-day stability.

This is a macOS preview. The Linux multi-day use figures in the main README are
not macOS evidence. The same long-session limits apply: required original user
input or a single active turn can exceed the model window and stop with an
error. No compression or accumulated-history fallback is added by this port.
