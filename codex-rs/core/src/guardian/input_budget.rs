//! Finalizes a pending reviewer input after tools and turn context are resolved.
//! The thread attachment is a single in-flight request, consumed before history
//! recording. Successful finalization consumes it; budget failures end the request.
//! It is not another retained history.

use codex_features::Feature;
use codex_guardian_context::ComposedContext;
use codex_guardian_context::HistoryTruncation;
use codex_guardian_context::RequestBudget;
use codex_guardian_context::effective_input_token_limit;
use codex_protocol::config_types::ReasoningSummary;
use codex_protocol::error::CodexErr;
use codex_protocol::error::Result as CodexResult;
use codex_protocol::models::ContentItem;
use codex_protocol::models::ResponseItem;
use codex_protocol::user_input::UserInput;

use crate::context::ContextualUserFragment;
use crate::context::GuardianBudgetOmission;
use crate::context_manager::estimate_item_token_count;
use crate::responses_metadata::CodexResponsesRequestKind;
use crate::session::TurnInput;
use crate::session::session::Session;
use crate::session::step_context::StepContext;
use crate::session::turn::build_prompt;
use crate::session::turn_context::TurnContext;

#[derive(Clone)]
pub(crate) struct PendingReviewContext(pub ComposedContext);

/// Reject evidence that cannot fit before constructing a reviewer request.
pub(crate) async fn check_pending(session: &Session, turn: &TurnContext) -> CodexResult<()> {
    let Some(pending) = session
        .services
        .thread_extension_data
        .get::<PendingReviewContext>()
    else {
        return Ok(());
    };
    let base = session.get_prompt_base_instructions().await;
    let minimum_prefix =
        codex_protocol::protocol::TruncationPolicy::Bytes(base.text.len()).token_budget();
    let maximum = effective_input_token_limit(turn.model_info(), turn.config.model_context_window)
        .saturating_sub(super::request_budget::INPUT_TOKEN_MARGIN);
    let mut context = pending.0.clone();
    context.retain_new_instructions(
        &session
            .vrs_history()
            .await
            .map_err(crate::session::vrs_input::vrs_error_to_codex)?
            .for_prompt_annotated(&turn.model_info().input_modalities),
    );
    if context.estimated_tokens().saturating_add(minimum_prefix) > maximum {
        context
            .enforce_budget(
                RequestBudget {
                    max_input_tokens: maximum,
                    existing_context_tokens: minimum_prefix,
                },
                GuardianBudgetOmission.render(),
                HistoryTruncation::Allow,
            )
            .map_err(|_error| {
                session
                    .services
                    .thread_extension_data
                    .insert(super::request_budget::ExhaustedReviewBudget::Detected);
                CodexErr::ContextWindowExceeded
            })?;
    }
    Ok(())
}

pub(crate) async fn finalize(
    session: &Session,
    step: &StepContext,
    input: &mut Vec<TurnInput>,
    history_truncation: HistoryTruncation,
) -> CodexResult<()> {
    let Some(pending) = session
        .services
        .thread_extension_data
        .get::<PendingReviewContext>()
    else {
        return Ok(());
    };
    let [TurnInput::UserInput { content, .. }] = input.as_slice() else {
        return Err(CodexErr::InvalidRequest(
            "Guardian expects one review input".to_owned(),
        ));
    };
    let mut context = pending.0.clone();
    let model = &step.settings.model_info;
    let history = session
        .vrs_history()
        .await
        .map_err(crate::session::vrs_input::vrs_error_to_codex)?;
    let history = history.for_prompt_annotated(&model.input_modalities);
    // Use the history that will actually reach the model.
    context.retain_new_instructions(&history);
    let prompt = build_prompt(
        history
            .into_iter()
            .map(codex_history::ResponseItemEnvelope::into_item)
            .collect(),
        step,
        session.get_prompt_base_instructions().await,
    );
    let request = session.services.model_client.build_responses_request(
        &prompt,
        model,
        /*effort*/ None,
        ReasoningSummary::None,
        /*service_tier*/ None,
        &session
            .responses_metadata(step, CodexResponsesRequestKind::Turn)
            .await,
        /*include_internal*/ true,
    )?;
    let mut existing = super::request_budget::estimate_request_tokens(&request)
        .max(usize::try_from(session.get_total_token_usage().await).unwrap_or(usize::MAX));
    // These reminders are appended after the accepted input. Reserve their full
    // serialized cost before choosing optional evidence, even if the time
    // reminder's interval ultimately suppresses it.
    if step
        .turn
        .config
        .features
        .enabled(Feature::CurrentTimeReminder)
        && step.turn.config.current_time_reminder.is_some()
    {
        let reminder = ContextualUserFragment::into(crate::context::CurrentTimeReminder::new(
            chrono::Utc::now(),
        ));
        existing = existing.saturating_add(
            usize::try_from(estimate_item_token_count(&reminder)).unwrap_or(usize::MAX),
        );
    }
    if let Some(reminder) = session
        .services
        .agent_control
        .pending_budget_reminder(session.thread_id(), &session.current_window_id().await)
        .await
    {
        let reminder = ContextualUserFragment::into(crate::context::RolloutBudgetContext {
            remaining_tokens: reminder.remaining_tokens,
        });
        existing = existing.saturating_add(
            usize::try_from(estimate_item_token_count(&reminder)).unwrap_or(usize::MAX),
        );
    }
    // Reserve the real input annotations as well as the shared content cost.
    // Removing optional items can only reduce this metadata. The remaining
    // margin covers IDs and timestamps assigned when recording the message.
    let mut framing = session.response_item_from_user_input(content.clone());
    if let ResponseItem::Message { content, .. } = &mut framing {
        content.clear();
    }
    let budget = RequestBudget {
        max_input_tokens: effective_input_token_limit(model, step.turn.config.model_context_window)
            .saturating_sub(super::request_budget::INPUT_TOKEN_MARGIN),
        existing_context_tokens: existing.saturating_add(
            usize::try_from(estimate_item_token_count(&framing)).unwrap_or(usize::MAX),
        ),
    };
    let context = context
        .enforce_budget(budget, GuardianBudgetOmission.render(), history_truncation)
        .map_err(|error| {
            session
                .services
                .thread_extension_data
                .insert(super::request_budget::ExhaustedReviewBudget::Detected);
            match error {
                codex_guardian_context::SectionError::EvidenceLimitExceeded { .. } => {
                    CodexErr::ContextWindowExceeded
                }
                error => CodexErr::InvalidRequest(error.to_string()),
            }
        })?;
    for (section, cost) in context.section_costs() {
        for (measurement, value) in cost.measurements() {
            session
                .services
                .session_telemetry
                .histogram_with_boundaries(
                    codex_guardian_context::SECTION_COST_METRIC,
                    i64::try_from(value).unwrap_or(i64::MAX),
                    codex_guardian_context::SECTION_COST_BOUNDARIES,
                    &[
                        ("target", "sync"),
                        ("section", section),
                        ("measurement", measurement),
                    ],
                );
        }
    }
    match context.clone().into_annotated_user_inputs() {
        Ok((user_input, metadata)) => {
            if metadata.is_some() {
                input[0] = TurnInput::ResponseItem(codex_history::ResponseItemEnvelope {
                    item: session.response_item_from_user_input(user_input),
                    metadata,
                });
            } else if let TurnInput::UserInput { content, .. } = &mut input[0] {
                *content = user_input;
            }
        }
        Err(codex_guardian_context::SectionError::UnsupportedDelivery {
            section: "conversation_transcript",
        }) => {
            *input = context
                .into_annotated_messages()
                .into_iter()
                .map(|mut envelope| {
                    // Preserve the ordinary user-content annotations on each text segment;
                    // native messages retain the original author, recipient and ciphertext.
                    if let ResponseItem::Message { role, content, .. } = &envelope.item
                        && role == "user"
                    {
                        let user_input = content
                            .iter()
                            .map(|item| match item {
                                ContentItem::InputText { text } => Ok(UserInput::Text {
                                    text: text.clone(),
                                    text_elements: Vec::new(),
                                }),
                                ContentItem::InputImage { image, detail } => Ok(UserInput::Image {
                                    image: image.clone(),
                                    detail: *detail,
                                }),
                                ContentItem::OutputText { .. } | ContentItem::InputAudio { .. } => {
                                    Err(CodexErr::InvalidRequest(
                                        "Unsupported Guardian input content".to_owned(),
                                    ))
                                }
                            })
                            .collect::<CodexResult<Vec<_>>>()?;
                        envelope.item = session.response_item_from_user_input(user_input);
                    }
                    Ok(TurnInput::ResponseItem(envelope))
                })
                .collect::<CodexResult<Vec<_>>>()?;
        }
        Err(error) => return Err(CodexErr::InvalidRequest(error.to_string())),
    }
    session
        .services
        .thread_extension_data
        .remove::<PendingReviewContext>();
    session
        .services
        .thread_extension_data
        .remove::<super::request_budget::ExhaustedReviewBudget>();
    Ok(())
}

#[cfg(test)]
#[path = "input_budget_tests.rs"]
mod tests;
