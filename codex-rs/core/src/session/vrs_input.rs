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
use codex_protocol::models::BaseInstructions;
use codex_protocol::models::ResponseItem;
use codex_protocol::openai_models::InputModality;
use codex_vrs::VrsError;
use tracing::info;
use tracing::warn;

use crate::client_common::Prompt;
use crate::context_manager::ContextManager;
use crate::session::session::Session;
use crate::session::step_context::StepContext;

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
pub(crate) async fn vrs_input(
    sess: &Session,
    budget: Option<u64>,
) -> Result<Vec<ResponseItem>, VrsError> {
    let thread_id = sess.thread_id.to_string();
    let started = Instant::now();
    let result: Result<(Vec<ResponseItem>, u64), VrsError> = async {
        let (items, tokens, cut) = assemble_for(sess, budget).await?;
        // Only the private D4 cache receives concurrent records. Every model-bound caller
        // receives the exact assembly below, even when a newer refresh supersedes this one.
        sess.install_assembled_history(cut, items.clone()).await?;
        Ok((items, tokens))
    }
    .await;
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
    Ok(items)
}

async fn assemble_for(
    sess: &Session,
    budget: Option<u64>,
) -> Result<(Vec<ResponseItem>, u64, crate::state::VrsCacheCut), VrsError> {
    let cut = sess
        .state
        .lock()
        .await
        .begin_vrs_assembly()
        .map_err(recording_unavailable)?;
    // P-3'': recording callers publish their reserved lines before queuing disk writes.
    // Assembly reads VRS immediately and never waits for the rollout writer.
    let path: PathBuf = match sess.current_rollout_path().await {
        Ok(Some(path)) => path,
        Ok(None) => sess.ephemeral_vrs_path()?,
        Err(err) => return Err(VrsError::Unavailable(format!("no rollout path: {err}"))),
    };
    // D13 (round 6): a store that is still restoring is waited for, then asked again. The wait
    // returns every second so a cancelled turn drops it; a failed store is an error.
    let assembled = loop {
        match codex_vrs::assemble_with_budget(&path, budget) {
            Err(VrsError::NotReady) => {
                let wait_path = path.clone();
                tokio::task::spawn_blocking(move || codex_vrs::wait(&wait_path, 1000))
                    .await
                    .map_err(|err| VrsError::Unavailable(format!("vrs wait task: {err}")))??;
            }
            other => break other?,
        }
    };
    let items = decode_assembled_items(assembled.items)?;
    Ok((items, assembled.tokens, cut))
}

fn recording_unavailable(error: String) -> VrsError {
    VrsError::Unavailable(format!(
        "rollout recording failed: {error}; reopen the session before sending another request"
    ))
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
    step: &StepContext,
    base_instructions: &BaseInstructions,
) -> CodexResult<Vec<ResponseItem>> {
    // Reserve instructions, tools and output schema in their actual wire representation.
    // In Responses Lite those fields become input items; the same estimator counts both forms.
    let empty_prompt = super::turn::build_prompt(Vec::new(), step, base_instructions.clone());
    let overhead = estimate_prompt_tokens(sess, step, &empty_prompt).await?;
    let maximum = request_input_limit(step);
    let budget = maximum
        .checked_sub(overhead)
        .filter(|budget| *budget > 0)
        .ok_or(CodexErr::ContextWindowExceeded)?;
    let items = vrs_input(sess, Some(budget as u64))
        .await
        .map_err(vrs_error_to_codex)?;
    if items.is_empty() {
        return Err(CodexErr::Fatal(
            "VRS assembled an empty model input; the request was not sent".to_string(),
        ));
    }
    Ok(normalize_for_prompt(
        items,
        &step.settings.model_info.input_modalities,
    ))
}

/// Admission of the completed request, including normalized items and all request overhead.
/// This uses the existing model-visible byte estimates, not a tokenizer-exact token count.
/// It rejects overflow without dropping required evidence or retrying with a looser allowance.
pub(crate) async fn check_prompt_window(
    sess: &Session,
    step: &StepContext,
    prompt: &Prompt,
) -> CodexResult<()> {
    if estimate_prompt_tokens(sess, step, prompt).await? > request_input_limit(step) {
        return Err(CodexErr::ContextWindowExceeded);
    }
    Ok(())
}

fn request_input_limit(step: &StepContext) -> usize {
    codex_guardian_context::effective_input_token_limit(
        &step.settings.model_info,
        step.turn.config.model_context_window,
    )
}

async fn estimate_prompt_tokens(
    sess: &Session,
    step: &StepContext,
    prompt: &Prompt,
) -> CodexResult<usize> {
    let metadata = sess
        .responses_metadata(
            step,
            crate::responses_metadata::CodexResponsesRequestKind::Turn,
        )
        .await;
    let request = sess.services.model_client.build_responses_request(
        prompt,
        &step.settings.model_info,
        None,
        codex_protocol::config_types::ReasoningSummary::None,
        None,
        &metadata,
        true,
    )?;
    Ok(crate::guardian::estimate_request_tokens(&request))
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
    /// Installs A plus overlapping records into the private D4 cache, without awaiting a writer.
    pub(crate) async fn install_assembled_history(
        &self,
        cut: crate::state::VrsCacheCut,
        items: Vec<ResponseItem>,
    ) -> Result<(), VrsError> {
        let mut state = self.state.lock().await;
        state
            .install_vrs_history(cut, items)
            .map(|_| ())
            .map_err(recording_unavailable)
    }

    /// Installs the stored assembly as the live history of a resumed or forked thread (design D4).
    ///
    /// When the store cannot assemble yet the history stays empty. Model input never reads it:
    /// the next step assembles again and reports the failure if it persists.
    pub(crate) async fn restore_history_from_vrs(&self) {
        if let Err(err) = vrs_input(self, None).await {
            warn!("VRS history not installed on resume: {err}");
        }
    }

    /// A history snapshot whose items are `A(S_t, thread)`, for consumers that read a
    /// `ContextManager` (guardian budgets and reviewer parents, design D3 A8-A10, A13).
    pub(crate) async fn vrs_history(&self) -> Result<ContextManager, VrsError> {
        let items = vrs_input(self, None).await?;
        let state = self.state.lock().await;
        Ok(state.history.with_assembled_items(items))
    }

    /// One immutable generation per live Session; insertion and assembly share this identity.
    pub(super) fn ephemeral_vrs_path(&self) -> Result<PathBuf, VrsError> {
        codex_vrs::ephemeral_path(
            &self.ephemeral_vrs_generation.to_string(),
            &self.thread_id.to_string(),
        )
    }

    /// Ingests the original supplied non-local history into this Session's new S (design D1).
    /// The backend already owns these records, so do not append a duplicate copy there.
    pub(super) async fn seed_non_local_vrs_history(&self, items: &[RolloutItem]) {
        let result = match self.current_rollout_path().await {
            Ok(Some(_)) => return,
            Ok(None) => self.insert_ephemeral_vrs_lines(items).await,
            Err(error) => Err(VrsError::Unavailable(format!("no rollout path: {error}"))),
        };
        if let Err(error) = result {
            warn!("failed to ingest resumed non-local VRS history: {error}");
            self.state
                .lock()
                .await
                .vrs_recording_error
                .get_or_insert_with(|| error.to_string());
        }
    }

    /// Records rollout items of a thread that has no rollout file into the store (design D1).
    pub(crate) async fn insert_ephemeral_vrs_lines(
        &self,
        items: &[RolloutItem],
    ) -> Result<(), VrsError> {
        let history_mode = self.state.lock().await.session_configuration.history_mode;
        let path = self.ephemeral_vrs_path()?;
        for item in items {
            let Some(item) = codex_rollout::persisted_rollout_item(item, history_mode) else {
                continue;
            };
            let line = codex_rollout::encode_rollout_line(item.as_ref(), None).map_err(|err| {
                VrsError::Unavailable(format!("rollout line encoding failed: {err}"))
            })?;
            let offset = self
                .ephemeral_vrs_offset
                .fetch_update(Ordering::Relaxed, Ordering::Relaxed, |offset| {
                    offset.checked_add(line.len() as u64)
                })
                .map_err(|_| VrsError::Unavailable("virtual rollout offset overflow".into()))?;
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
        let (session, turn) = crate::session::tests::make_session_and_context().await;
        session.state.lock().await.vrs_recording_error = Some("injected insert failure".into());
        let error = super::vrs_prompt_input(
            &session,
            &crate::session::step_context::StepContext::for_test(std::sync::Arc::new(turn)),
            &codex_protocol::models::BaseInstructions::default(),
        )
        .await
        .expect_err("incomplete store must not produce a prompt");
        assert!(error.to_string().contains("injected insert failure"));
        assert!(error.to_string().contains("reopen the session"));
    }

    fn set_window(
        step: &mut std::sync::Arc<crate::session::step_context::StepContext>,
        window: i64,
        lite: bool,
    ) {
        let settings =
            std::sync::Arc::make_mut(&mut std::sync::Arc::get_mut(step).unwrap().settings);
        let model = std::sync::Arc::make_mut(&mut settings.model_info);
        model.context_window = Some(window);
        model.max_context_window = Some(window);
        model.effective_context_window_percent = 100;
        model.used_fallback_model_metadata = false;
        model.use_responses_lite = lite;
    }

    #[tokio::test]
    async fn request_window_is_per_call_and_preserves_required_input() {
        use codex_history::RolloutItem;
        use codex_protocol::error::CodexErrorDetails;
        use codex_protocol::models::BaseInstructions;
        use codex_protocol::models::ResponseItem;
        use std::sync::Arc;

        let (session, turn) = crate::session::tests::make_session_and_context().await;
        let item = serde_json::from_value::<ResponseItem>(json!({
            "type": "message", "role": "user", "content": [{
                "type": "input_text", "text": "required direct user input ".repeat(512)
            }]
        }))
        .unwrap();
        session
            .insert_ephemeral_vrs_lines(&[RolloutItem::ResponseItem(item.clone().into())])
            .await
            .expect("publish required user input");
        let turn = Arc::new(turn);
        let mut large = crate::session::step_context::StepContext::for_test(Arc::clone(&turn));
        let mut small = crate::session::step_context::StepContext::for_test(turn);
        set_window(&mut large, 16_000, false);
        set_window(&mut small, 512, false);
        let base = BaseInstructions::default();
        let original = super::vrs_prompt_input(&session, &large, &base)
            .await
            .unwrap();
        assert_eq!(
            original,
            super::normalize_for_prompt(vec![item], &large.settings.model_info.input_modalities)
        );
        assert!(matches!(
            super::vrs_prompt_input(&session, &small, &base).await,
            Err(err) if matches!(err.details(), CodexErrorDetails::ContextWindowExceeded)
        ));
        // A rejected smaller model must not truncate the store or mutate another request's budget.
        assert_eq!(
            super::vrs_prompt_input(&session, &large, &base)
                .await
                .unwrap(),
            original
        );
    }

    #[tokio::test]
    async fn request_window_reserves_base_instructions_before_assembly() {
        use codex_protocol::error::CodexErrorDetails;
        use codex_protocol::models::BaseInstructions;
        use std::sync::Arc;

        let (session, turn) = crate::session::tests::make_session_and_context().await;
        let turn = Arc::new(turn);
        for lite in [false, true] {
            let mut step = crate::session::step_context::StepContext::for_test(Arc::clone(&turn));
            set_window(&mut step, 128, lite);
            let base = BaseInstructions {
                text: "required instructions ".repeat(128),
                provenance: None,
            };
            // Even an empty S cannot make room for this fixed request overhead.
            assert!(matches!(
                super::vrs_prompt_input(&session, &step, &base).await,
                Err(err) if matches!(err.details(), CodexErrorDetails::ContextWindowExceeded)
            ));
        }
    }

    #[tokio::test]
    async fn final_admission_counts_tools_and_schema_in_both_wire_formats() {
        use codex_protocol::error::CodexErrorDetails;
        use std::sync::Arc;

        let (session, turn) = crate::session::tests::make_session_and_context().await;
        let turn = Arc::new(turn);
        for lite in [false, true] {
            let mut step = crate::session::step_context::StepContext::for_test(Arc::clone(&turn));
            set_window(&mut step, 128, lite);
            let mut prompt = crate::client_common::Prompt::default();
            // This fixture measures tool/schema overhead from an actually empty prompt.
            // Prompt::default() otherwise includes the full bundled base instructions.
            prompt.base_instructions.text.clear();
            super::check_prompt_window(&session, &step, &prompt)
                .await
                .unwrap();
            prompt.tools = vec![codex_tools::ToolSpec::Function(
                codex_tools::ResponsesApiTool {
                    name: "large_tool".into(),
                    description: "required tool description ".repeat(128),
                    strict: false,
                    defer_loading: None,
                    parameters: serde_json::from_value(json!({"type": "object", "properties": {}}))
                        .unwrap(),
                    output_schema: None,
                },
            )]
            .into();
            assert!(matches!(
                super::check_prompt_window(&session, &step, &prompt).await,
                Err(err) if matches!(err.details(), CodexErrorDetails::ContextWindowExceeded)
            ));
            prompt.tools = Arc::default();
            prompt.output_schema = Some(
                json!({"type": "string", "description": "required output schema ".repeat(128)}),
            );
            assert!(matches!(
                super::check_prompt_window(&session, &step, &prompt).await,
                Err(err) if matches!(err.details(), CodexErrorDetails::ContextWindowExceeded)
            ));
        }
    }
}
