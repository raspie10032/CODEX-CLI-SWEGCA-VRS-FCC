//! Checks complete VRS-assembled synchronous reviewer requests before sampling.
//! Admitted sampling inputs are observed once per step, independent of transport retries.

use codex_api::ResponsesApiRequest;
use codex_guardian_context::REQUEST_TOKENS_BOUNDARIES;
use codex_guardian_context::REQUEST_TOKENS_METRIC;
use codex_guardian_context::effective_input_token_limit;
use codex_protocol::error::CodexErr;
use codex_protocol::error::Result as CodexResult;
use codex_protocol::protocol::TruncationPolicy;

use crate::context_manager::estimate_item_token_count_uncached;
use crate::session::session::Session;
use crate::session::step_context::StepContext;

pub(super) const INPUT_TOKEN_MARGIN: usize = 256;

// Keep reviewers that exhaust the input budget out of reuse. Also distinguishes
// local budget failures from backend errors.
pub(crate) enum ExhaustedReviewBudget {
    Detected,
}

/// Guardian-owned marker scoped to one sampling step, including all transport retries.
struct ObservedRequest;

pub(crate) fn estimate_request_tokens(request: &ResponsesApiRequest) -> usize {
    let input = request
        .input
        .iter()
        .map(estimate_item_token_count_uncached)
        .fold(0i64, i64::saturating_add);
    let metadata = serde_json::to_vec(&(&request.tools, &request.text))
        .map(|bytes| TruncationPolicy::Bytes(bytes.len()).token_budget())
        .unwrap_or(usize::MAX);
    usize::try_from(input)
        .unwrap_or(usize::MAX)
        .saturating_add(metadata)
}

/// Checks the complete request without adding items outside the VRS assembly.
pub(crate) async fn prepare_prompt(
    session: &Session,
    prompt: &mut crate::client_common::Prompt,
    step: &StepContext,
    metadata: &crate::responses_metadata::CodexResponsesMetadata,
) -> CodexResult<()> {
    let model = &step.settings.model_info;
    let maximum = effective_input_token_limit(model, step.turn.config.model_context_window)
        .saturating_sub(INPUT_TOKEN_MARGIN);
    let request = session.services.model_client.build_responses_request(
        prompt,
        model,
        /*effort*/ None,
        codex_protocol::config_types::ReasoningSummary::None,
        /*service_tier*/ None,
        metadata,
        /*include_internal*/ true,
    )?;
    let total = estimate_request_tokens(&request);
    if total > maximum {
        session
            .services
            .thread_extension_data
            .insert(ExhaustedReviewBudget::Detected);
        return Err(CodexErr::ContextWindowExceeded);
    }
    session
        .services
        .thread_extension_data
        .remove::<ExhaustedReviewBudget>();
    if step
        .extension_data
        .insert_if(ObservedRequest, |existing| existing.is_none())
    {
        step.session_telemetry.histogram_with_boundaries(
            REQUEST_TOKENS_METRIC,
            i64::try_from(total).unwrap_or(i64::MAX),
            REQUEST_TOKENS_BOUNDARIES,
            &[
                ("target", "sync"),
                ("component", "total"),
                (
                    "token_bucket",
                    codex_guardian_context::request_token_bucket(total),
                ),
            ],
        );
    }
    Ok(())
}

#[cfg(test)]
#[path = "request_budget_tests.rs"]
mod tests;
