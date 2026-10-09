//! VRS context assembly.
//!
//! When `CODEX_VRS_SOCK` is set, each model request asks the VRS assembler for the
//! items to send instead of the accumulated history. The assembler reads the
//! session's rollout file, so nothing is summarized away and compaction is not
//! needed. Any failure falls back to the accumulated history for that request.

use std::collections::HashSet;
use std::io::BufRead;
use std::io::BufReader;
use std::io::Write;
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::Duration;
use std::time::Instant;

use codex_protocol::models::ResponseItem;
use tracing::info;
use tracing::warn;

const DEFAULT_BUDGET: u64 = 120_000;
const TIMEOUT: Duration = Duration::from_secs(5);

/// Threads whose latest request was assembled by VRS. Compaction is skipped for them.
static ASSEMBLED_THREADS: Mutex<Option<HashSet<String>>> = Mutex::new(None);

fn socket_path() -> Option<PathBuf> {
    std::env::var_os("CODEX_VRS_SOCK").map(PathBuf::from)
}

fn budget() -> u64 {
    std::env::var("CODEX_VRS_BUDGET")
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(DEFAULT_BUDGET)
}

pub(crate) fn enabled() -> bool {
    socket_path().is_some()
}

fn mark(thread_id: &str, assembled: bool) {
    let mut guard = ASSEMBLED_THREADS.lock().unwrap_or_else(|e| e.into_inner());
    let set = guard.get_or_insert_with(HashSet::new);
    if assembled {
        set.insert(thread_id.to_string());
    } else {
        set.remove(thread_id);
    }
}

/// True when the thread's last model request used VRS assembly.
pub(crate) fn skip_compaction(thread_id: &str) -> bool {
    enabled()
        && ASSEMBLED_THREADS
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .as_ref()
            .is_some_and(|set| set.contains(thread_id))
}

fn request(sock: PathBuf, rollout: PathBuf, budget: u64) -> anyhow::Result<(Vec<ResponseItem>, u64)> {
    let mut stream = UnixStream::connect(&sock)?;
    stream.set_read_timeout(Some(TIMEOUT))?;
    stream.set_write_timeout(Some(TIMEOUT))?;
    let line = serde_json::json!({ "rollout": rollout, "budget": budget });
    stream.write_all(format!("{line}\n").as_bytes())?;
    let mut reader = BufReader::new(stream);
    let mut response = String::new();
    reader.read_line(&mut response)?;
    let value: serde_json::Value = serde_json::from_str(&response)?;
    if value.get("ok").and_then(serde_json::Value::as_bool) != Some(true) {
        anyhow::bail!(
            "assembler error: {}",
            value.get("error").map(ToString::to_string).unwrap_or_default()
        );
    }
    let tokens = value.get("tokens").and_then(serde_json::Value::as_u64).unwrap_or(0);
    let raw = value
        .get("items")
        .and_then(serde_json::Value::as_array)
        .ok_or_else(|| anyhow::anyhow!("assembler response has no items"))?;
    let mut items = Vec::with_capacity(raw.len());
    for item in raw {
        // Skip item kinds this build does not know rather than failing the request.
        if let Ok(item) = serde_json::from_value::<ResponseItem>(item.clone()) {
            items.push(item);
        }
    }
    if items.is_empty() {
        anyhow::bail!("assembler returned no usable items");
    }
    Ok((items, tokens))
}

/// Appends one receipt line to `CODEX_VRS_LOG` when set (evidence independent of tracing setup).
fn receipt(thread_id: &str, outcome: &str, items: usize, tokens: u64, elapsed_us: u128) {
    let Some(path) = std::env::var_os("CODEX_VRS_LOG") else {
        return;
    };
    let line = serde_json::json!({
        "unix_ms": std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0),
        "thread": thread_id,
        "outcome": outcome,
        "items": items,
        "tokens": tokens,
        "us": elapsed_us as u64,
    });
    if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open(path) {
        let _ = writeln!(file, "{line}");
    }
}

/// Records that compaction was skipped for a VRS-assembled thread.
pub(crate) fn receipt_compaction_skipped(thread_id: &str) {
    receipt(thread_id, "compaction_skipped", 0, 0, 0);
}

/// Returns the VRS-assembled model input, or `None` to use the accumulated history.
pub(crate) async fn assemble(thread_id: &str, rollout: Option<PathBuf>) -> Option<Vec<ResponseItem>> {
    let sock = socket_path()?;
    let Some(rollout) = rollout else {
        warn!("vrs_assembled failed: no rollout path");
        receipt(thread_id, "no_rollout", 0, 0, 0);
        mark(thread_id, false);
        return None;
    };
    let budget = budget();
    let started = Instant::now();
    let result = tokio::task::spawn_blocking(move || request(sock, rollout, budget)).await;
    let elapsed_us = started.elapsed().as_micros();
    match result {
        Ok(Ok((items, tokens))) => {
            info!(items = items.len(), tokens, elapsed_us, "vrs_assembled");
            receipt(thread_id, "assembled", items.len(), tokens, elapsed_us);
            mark(thread_id, true);
            Some(items)
        }
        Ok(Err(err)) => {
            warn!(error = %err, elapsed_us, "vrs_assembled failed; using accumulated history");
            receipt(thread_id, &format!("failed: {err}"), 0, 0, elapsed_us);
            mark(thread_id, false);
            None
        }
        Err(err) => {
            warn!(error = %err, elapsed_us, "vrs_assembled failed; using accumulated history");
            receipt(thread_id, &format!("failed: {err}"), 0, 0, elapsed_us);
            mark(thread_id, false);
            None
        }
    }
}
