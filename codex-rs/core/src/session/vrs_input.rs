//! Model input from the in-process VRS store (design D3, D4, D5).
//!
//! Every request that sends a thread's conversation to a model builds its input here, from the
//! assembly `A(S_t, thread)` of the VRS store. There is no fallback: when the assembly cannot be
//! computed the error is returned to the caller, and the accumulated live history is never sent
//! in its place.

use std::path::PathBuf;
use std::sync::atomic::Ordering;
use std::time::Instant;

use codex_history::RolloutItem;
use codex_protocol::error::CodexErr;
use codex_protocol::error::Result as CodexResult;
use codex_protocol::models::ResponseItem;
use codex_protocol::openai_models::InputModality;
use codex_vrs::VrsError;
use tracing::info;
use tracing::warn;

use crate::context_manager::ContextManager;
use crate::session::session::Session;

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
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
    {
        use std::io::Write as _;
        let _ = writeln!(file, "{line}");
    }
}

/// Maps an assembly failure to the error a turn reports (design D5).
pub(crate) fn vrs_error_to_codex(error: VrsError) -> CodexErr {
    match error {
        VrsError::OverWindow => CodexErr::ContextWindowExceeded,
        VrsError::NotReady => CodexErr::Fatal(
            "VRS context store is not ready (still restoring); the request was not sent"
                .to_string(),
        ),
        other => CodexErr::Fatal(format!("VRS context assembly failed: {other}")),
    }
}

/// `A(S_t, thread)`: the response items to send to the model for `sess`.
pub(crate) async fn vrs_input(sess: &Session) -> Result<Vec<ResponseItem>, VrsError> {
    let thread_id = sess.thread_id.to_string();
    let started = Instant::now();
    let result = assemble_for(sess, &thread_id).await;
    let elapsed_us = started.elapsed().as_micros();
    match &result {
        Ok((items, tokens)) => {
            info!(items = items.len(), tokens, elapsed_us, "vrs_assembled");
            receipt(&thread_id, "assembled", items.len(), *tokens, elapsed_us);
        }
        Err(err) => {
            warn!(error = %err, elapsed_us, "vrs assembly failed");
            receipt(&thread_id, &format!("failed: {err}"), 0, 0, elapsed_us);
        }
    }
    let (items, _) = result?;
    // Every consumer refreshes the bounded live cache, including snapshots and prewarm.
    // The model receives this assembly directly, never a readback of the cache.
    sess.install_assembled_history(items.clone()).await;
    Ok(items)
}

async fn assemble_for(
    sess: &Session,
    thread_id: &str,
) -> Result<(Vec<ResponseItem>, u64), VrsError> {
    if let Some(error) = sess.state.lock().await.vrs_recording_error.as_ref() {
        return Err(VrsError::Unavailable(format!(
            "rollout recording failed: {error}; reopen the session before sending another request"
        )));
    }
    // P-3'': recording callers publish their reserved lines before queuing disk writes.
    // Assembly reads VRS immediately and never waits for the rollout writer.
    let path: PathBuf = match sess.current_rollout_path().await {
        Ok(Some(path)) => path,
        Ok(None) => codex_vrs::ephemeral_path(thread_id)?,
        Err(err) => return Err(VrsError::Unavailable(format!("no rollout path: {err}"))),
    };
    let assembled = codex_vrs::assemble(&path)?;
    let items = decode_assembled_items(assembled.items)?;
    Ok((items, assembled.tokens))
}

fn decode_assembled_items(values: Vec<serde_json::Value>) -> Result<Vec<ResponseItem>, VrsError> {
    values
        .into_iter()
        .enumerate()
        .map(|(index, value)| {
            let item = serde_json::from_value::<ResponseItem>(value).map_err(|err| {
                VrsError::Unavailable(format!("invalid assembled item {index}: {err}"))
            })?;
            match item {
                ResponseItem::Other
                | ResponseItem::Compaction { .. }
                | ResponseItem::ContextCompaction { .. }
                | ResponseItem::CompactionTrigger { .. } => Err(VrsError::Unavailable(format!(
                    "unsupported assembled item {index}; the request was not sent"
                ))),
                item => Ok(item),
            }
        })
        .collect()
}

/// The prompt input for one model step (design D3 A1/A2, D4, D5).
///
/// Assembles, installs the assembly as the live history, and returns it normalized for the
/// model. The live history is never read back as model input.
pub(crate) async fn vrs_prompt_input(
    sess: &Session,
    input_modalities: &[InputModality],
) -> CodexResult<Vec<ResponseItem>> {
    let items = vrs_prompt_items(sess).await?;
    Ok(normalize_for_prompt(items, input_modalities))
}

/// The prompt input for prewarm (design D3 A4); assembly also refreshes the D4 cache.
pub(crate) async fn vrs_prompt_snapshot(
    sess: &Session,
    input_modalities: &[InputModality],
) -> CodexResult<Vec<ResponseItem>> {
    let items = vrs_prompt_items(sess).await?;
    Ok(normalize_for_prompt(items, input_modalities))
}

async fn vrs_prompt_items(sess: &Session) -> CodexResult<Vec<ResponseItem>> {
    let items = vrs_input(sess).await.map_err(vrs_error_to_codex)?;
    if items.is_empty() {
        return Err(CodexErr::Fatal(
            "VRS assembled an empty model input; the request was not sent".to_string(),
        ));
    }
    Ok(items)
}

fn normalize_for_prompt(
    items: Vec<ResponseItem>,
    input_modalities: &[InputModality],
) -> Vec<ResponseItem> {
    let mut assembled = ContextManager::new();
    assembled.replace_assembled(items);
    assembled.for_prompt(input_modalities)
}

impl Session {
    /// Makes `items` the live history (design D4). Truncation was already applied by the assembler.
    pub(crate) async fn install_assembled_history(&self, items: Vec<ResponseItem>) {
        let mut state = self.state.lock().await;
        state.history.replace_assembled(items);
    }

    /// Installs the stored assembly as the live history of a resumed or forked thread (design D4).
    ///
    /// When the store cannot assemble yet the history stays empty. Model input never reads it:
    /// the next step assembles again and reports the failure if it persists.
    pub(crate) async fn restore_history_from_vrs(&self) {
        if let Err(err) = vrs_input(self).await {
            warn!("VRS history not installed on resume: {err}");
        }
    }

    /// A history snapshot whose items are `A(S_t, thread)`, for consumers that read a
    /// `ContextManager` (guardian budgets and reviewer parents, design D3 A8-A10, A13).
    pub(crate) async fn vrs_history(&self) -> Result<ContextManager, VrsError> {
        let items = vrs_input(self).await?;
        let state = self.state.lock().await;
        Ok(state.history.with_assembled_items(items))
    }

    /// Records rollout items of a thread that has no rollout file into the store (design D1).
    pub(crate) async fn insert_ephemeral_vrs_lines(
        &self,
        items: &[RolloutItem],
    ) -> Result<(), VrsError> {
        let history_mode = self.state.lock().await.session_configuration.history_mode;
        let path = codex_vrs::ephemeral_path(&self.thread_id.to_string())?;
        for item in items {
            if !codex_rollout::is_persisted_rollout_item(item, history_mode) {
                continue;
            }
            let line = codex_rollout::encode_rollout_line(item, None).map_err(|err| {
                VrsError::Unavailable(format!("rollout line encoding failed: {err}"))
            })?;
            let offset = self
                .ephemeral_vrs_offset
                .fetch_add(line.len() as u64, Ordering::Relaxed);
            codex_vrs::insert(&path, offset, line.as_bytes())?;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::decode_assembled_items;
    use serde_json::json;

    #[test]
    fn malformed_assembly_does_not_keep_the_valid_prefix() {
        let valid = json!({"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "keep my complete request"}
        ]});
        assert!(decode_assembled_items(vec![valid.clone()]).is_ok());
        assert!(decode_assembled_items(vec![valid, json!({"type": "message"})]).is_err());
    }

    #[test]
    fn unsupported_assembly_is_an_error_instead_of_an_omission() {
        for kind in [
            "future_item",
            "compaction",
            "context_compaction",
            "compaction_trigger",
        ] {
            assert!(
                decode_assembled_items(vec![json!({
                    "type": kind, "encrypted_content": "obsolete summary"
                })])
                .is_err()
            );
        }
    }

    #[tokio::test]
    async fn recording_failure_prevents_assembly_before_any_model_request() {
        let (session, _turn) = crate::session::tests::make_session_and_context().await;
        session.state.lock().await.vrs_recording_error = Some("injected insert failure".into());
        let error = super::vrs_prompt_input(
            &session,
            &[codex_protocol::openai_models::InputModality::Text],
        )
        .await
        .expect_err("incomplete store must not produce a prompt");
        assert!(error.to_string().contains("injected insert failure"));
        assert!(error.to_string().contains("reopen the session"));
    }
}
