//! Loads stored agent context and prepares the history a child inherits when it forks.

use crate::agent::types::SpawnAgentOptions;
use crate::agent::types::SpawnAgentForkMode;
use crate::config::Config;
use crate::context::BaseInstructionsFragment;
use crate::context::ContextualUserFragment;
use crate::context::CurrentTimeReminder;
use crate::context::CurrentTimeUnavailable;
use crate::context::DeveloperInstructions;
use crate::context::GuardianApprovedAction;
use crate::context::ManagedDeveloperInstructions;
use crate::context::ModelInstructions;
use crate::context::MultiAgentModeInstructions;
use crate::context::MultiAgentRoleInstructions;
use crate::context::MultiAgentUsageHint;
use crate::context::world_state::IncrementalToolsHint;
use crate::context::world_state::PersistentModeState;
use crate::session::multi_agents::resolve_usage_hints;
use crate::tasks::InterruptedTurnHistoryMarker;
use crate::thread_manager::ForkSnapshot;
use crate::thread_manager::ThreadManagerState;
use crate::thread_manager::fork_history_from_snapshot;
use codex_context_fragments::set_annotated_content;
use codex_context_fragments::to_annotated_content;
use codex_history::InitialHistory;
use codex_history::ResponseItemEnvelope;
use codex_history::RolloutItem;
use codex_prompts::ResolvedModelMessages;
use codex_protocol::ThreadId;
use codex_protocol::error::CodexErr;
use codex_protocol::error::CodexErrorDetails;
use codex_protocol::error::Result as CodexResult;
use codex_protocol::models::ContentItem;
use codex_protocol::models::MessagePhase;
use codex_protocol::models::ResponseItem;
use codex_protocol::protocol::EventMsg;
use codex_protocol::protocol::MultiAgentVersion;
use codex_protocol::protocol::SessionSource;
use codex_protocol::protocol::SubAgentSource;
use codex_protocol::protocol::ThreadHistoryMode;
use codex_thread_store::LoadThreadHistoryParams;
use codex_thread_store::ReadThreadParams;

fn keep_forked_rollout_item(item: &RolloutItem, preserve_context_baselines: bool) -> bool {
    match item {
        RolloutItem::ResponseItem(envelope) => match &envelope.item {
            ResponseItem::Message { role, phase, .. } => match role.as_str() {
                "system" | "developer" | "user" => true,
                "assistant" => matches!(
                    phase,
                    Some(MessagePhase::PartialAnswer | MessagePhase::FinalAnswer)
                ),
                _ => false,
            },
            ResponseItem::AdditionalTools { .. }
            | ResponseItem::FunctionCallOutput { call_id: None, .. }
            | ResponseItem::ConfigurationUpdate { .. } => true,
            ResponseItem::AgentMessage { .. }
            | ResponseItem::Reasoning { .. }
            | ResponseItem::LocalShellCall { .. }
            | ResponseItem::FunctionCall { .. }
            | ResponseItem::ToolSearchCall { .. }
            | ResponseItem::FunctionCallOutput {
                call_id: Some(_), ..
            }
            | ResponseItem::CustomToolCall { .. }
            | ResponseItem::CustomToolCallOutput { .. }
            | ResponseItem::ToolSearchOutput { .. }
            | ResponseItem::WebSearchCall { .. }
            | ResponseItem::ImageGenerationCall { .. }
            | ResponseItem::Compaction { .. }
            | ResponseItem::CompactionTrigger { .. }
            | ResponseItem::ContextCompaction { .. }
            | ResponseItem::Other => false,
        },
        RolloutItem::RealtimeItem(_)
        | RolloutItem::InterAgentCommunication(_)
        | RolloutItem::InterAgentCommunicationMetadata { .. }
        | RolloutItem::RetainedContext(_)
        | RolloutItem::Compacted(_)
        | RolloutItem::SecurityRiskScore(_) => false,
        // Full-history forks preserve the cached prompt prefix and can keep diffing
        // from the parent's durable baseline.
        RolloutItem::TurnContext(_) | RolloutItem::WorldState(_) => preserve_context_baselines,
        // Child threads inherit model context, not the parent's cumulative usage state.
        RolloutItem::TokenUsageRecord(_) => false,
        RolloutItem::DynamicToolsUpdated { .. }
        | RolloutItem::EventMsg(_)
        | RolloutItem::SessionMeta(_) => true,
    }
}

fn retain_forked_developer_message(item: &mut ResponseItem, usage_hint_texts: &[String]) -> bool {
    if !matches!(item, ResponseItem::Message { role, .. } if role == "developer") {
        return true;
    }

    let Some(mut content) = to_annotated_content(item) else {
        return false;
    };
    content.retain(|content_item| {
        // Leave base instructions for the later context-baseline retention check.
        if content_item.kind().as_str() == BaseInstructionsFragment::KIND {
            return true;
        }
        // Persisted role hints can predate the current bundled wording and lack markers.
        if matches!(
            content_item.kind().as_str(),
            GuardianApprovedAction::KIND
                | MultiAgentRoleInstructions::KIND
                | MultiAgentUsageHint::KIND
        ) {
            return false;
        }
        let ContentItem::InputText { text } = content_item.content() else {
            return true;
        };

        !(MultiAgentRoleInstructions::matches_text(text)
            || text
                .starts_with(crate::guardian::AUTO_REVIEW_DENIED_ACTION_APPROVAL_DEVELOPER_PREFIX)
            || MultiAgentModeInstructions::matches_text(text)
            || CurrentTimeReminder::matches_text(text)
            || CurrentTimeUnavailable::matches_text(text)
            || usage_hint_texts
                .iter()
                .any(|usage_hint_text| usage_hint_text == text))
    });
    !content.is_empty() && set_annotated_content(item, content).is_some()
}

pub(super) async fn load_agent_model_context(
    state: &ThreadManagerState,
    thread_id: ThreadId,
    history_mode: ThreadHistoryMode,
) -> CodexResult<Option<codex_thread_store::StoredModelContext>> {
    let stored = match history_mode {
        ThreadHistoryMode::Legacy => state
            .read_stored_thread(ReadThreadParams {
                thread_id,
                include_archived: true,
                include_history: true,
            })
            .await?
            .history
            .map(|history| codex_thread_store::StoredModelContext {
                thread_id,
                revision: history.revision,
                items: history.items,
            }),
        ThreadHistoryMode::Paginated => Some(
            state
                .load_latest_model_context(LoadThreadHistoryParams {
                    thread_id,
                    include_archived: true,
                })
                .await?,
        ),
    };
    let Some(mut stored) = stored else {
        return Ok(None);
    };
    let history = match state.get_thread(thread_id).await {
        Ok(thread) => thread
            .session
            .vrs_history()
            .await
            .map_err(crate::session::vrs_input::vrs_error_to_codex)?,
        Err(error) if matches!(error.details(), CodexErrorDetails::ThreadNotFound(_)) => {
            let stored_thread = state
                .read_stored_thread(ReadThreadParams {
                    thread_id,
                    include_archived: true,
                    include_history: false,
                })
                .await?;
            let rollout_path = stored_thread.rollout_path.ok_or_else(|| {
                CodexErr::Fatal(format!(
                    "agent history source {thread_id} has no local rollout path"
                ))
            })?;
            crate::session::vrs_input::vrs_history_for_path(&rollout_path)
                .await
                .map_err(crate::session::vrs_input::vrs_error_to_codex)?
        }
        Err(error) => return Err(error),
    };
    // Preserve only host resume metadata from storage. Model-visible items come solely
    // from A(S_t, thread); accumulated rollout records are not a fallback.
    stored.items.retain(|item| {
        matches!(
            item,
            RolloutItem::SessionMeta(_)
                | RolloutItem::TurnContext(_)
                | RolloutItem::WorldState(_)
                | RolloutItem::DynamicToolsUpdated { .. }
        )
    });
    stored.items.extend(
        history
            .into_annotated_items()
            .into_iter()
            .map(RolloutItem::ResponseItem),
    );
    Ok(Some(stored))
}

/// Prepare copied history while leaving startup settings and timing with the caller.
pub(super) async fn prepare_forked_history(
    state: &ThreadManagerState,
    session_source: &SessionSource,
    options: &SpawnAgentOptions,
    config: &Config,
    multi_agent_version: MultiAgentVersion,
) -> CodexResult<(InitialHistory, Option<ThreadHistoryMode>)> {
    if options.fork_parent_spawn_call_id.is_none() {
        return Err(CodexErr::Fatal(
            "spawn_agent fork requires a parent spawn call id".to_string(),
        ));
    }
    let Some(fork_mode) = options.fork_mode.as_ref() else {
        return Err(CodexErr::Fatal(
            "spawn_agent fork requires a fork mode".to_string(),
        ));
    };
    let SessionSource::SubAgent(SubAgentSource::ThreadSpawn {
        parent_thread_id, ..
    }) = session_source
    else {
        return Err(CodexErr::Fatal(
            "spawn_agent fork requires a thread-spawn session source".to_string(),
        ));
    };

    let parent_thread_id = *parent_thread_id;
    let parent_thread = match state.get_thread(parent_thread_id).await {
        Ok(thread) => Some(thread),
        Err(error) if matches!(error.details(), CodexErrorDetails::ThreadNotFound(_)) => None,
        Err(error) => return Err(error),
    };
    let (subagent_developer_instructions, parent_developer_instructions) = match (
        multi_agent_version,
        config
            .multi_agent_v2
            .subagent_developer_instructions
            .as_ref(),
    ) {
        (MultiAgentVersion::V2, override_instructions)
            if override_instructions.is_some() || session_source.get_agent_role().is_some() =>
        {
            let parent_developer_instructions = if let Some(parent_thread) = &parent_thread {
                match parent_thread
                    .session
                    .new_default_turn()
                    .await
                    .developer_instructions
                    .clone()
                {
                    Some(instructions) if !instructions.is_empty() => Some(instructions),
                    Some(_) | None => None,
                }
            } else {
                None
            };
            (
                Some(config.developer_instructions.clone().unwrap_or_default()),
                parent_developer_instructions,
            )
        }
        (MultiAgentVersion::Disabled | MultiAgentVersion::V1, _) | (MultiAgentVersion::V2, _) => {
            (None, None)
        }
    };
    let (parent_history_mode, parent_history) = if let Some(parent_thread) = &parent_thread {
        (
            parent_thread.config_snapshot().await.history_mode,
            parent_thread
                .session
                .vrs_history()
                .await
                .map_err(crate::session::vrs_input::vrs_error_to_codex)?,
        )
    } else {
        let stored_thread = state
            .read_stored_thread(ReadThreadParams {
                thread_id: parent_thread_id,
                include_archived: true,
                include_history: false,
            })
            .await?;
        let rollout_path = stored_thread.rollout_path.ok_or_else(|| {
            CodexErr::Fatal(format!(
                "parent thread {parent_thread_id} has no local rollout path for fork"
            ))
        })?;
        (
            stored_thread.history_mode,
            crate::session::vrs_input::vrs_history_for_path(&rollout_path)
                .await
                .map_err(crate::session::vrs_input::vrs_error_to_codex)?,
        )
    };
    let destination_history_mode = matches!(parent_history_mode, ThreadHistoryMode::Paginated)
        .then_some(ThreadHistoryMode::Paginated);
    let world_state = parent_history.world_state_checkpoint();
    let mut forked_rollout_items = parent_history
        .into_annotated_items()
        .into_iter()
        .map(RolloutItem::ResponseItem)
        .collect::<Vec<_>>();
    if matches!(fork_mode, SpawnAgentForkMode::FullHistory) {
        if let Some(parent_thread) = &parent_thread
            && let Some(reference_context) = parent_thread.session.reference_context_item().await
        {
            forked_rollout_items.push(RolloutItem::TurnContext(reference_context));
        }
        if let Some(world_state) = world_state {
            forked_rollout_items.push(RolloutItem::WorldState(world_state));
        }
    }

    let multi_agent_v2_usage_hint_texts_to_filter: Vec<String> =
        if multi_agent_version == MultiAgentVersion::V2
            && let Some(parent_thread) = &parent_thread
        {
            let parent_config = parent_thread.session.get_config().await;
            let parent_usage_hints = resolve_usage_hints(
                &parent_config.multi_agent_v2,
                ResolvedModelMessages::bundled().multi_agent(),
                !parent_config.update_plan_enabled,
            );
            [parent_usage_hints.root, parent_usage_hints.subagent]
                .into_iter()
                .flatten()
                .map(|instructions| instructions.render().into_text().unwrap_or_default())
                .collect()
        } else {
            Vec::new()
        };
    let preserve_context_baselines = matches!(fork_mode, SpawnAgentForkMode::FullHistory);
    let mut replaced_parent_developer_instructions = false;
    let preserve_fork_prefix = multi_agent_version == MultiAgentVersion::V2
        && config.multi_agent_v2.preserve_fork_prefix
        && preserve_context_baselines;
    if preserve_fork_prefix {
        let InitialHistory::Forked(items) = fork_history_from_snapshot(
            ForkSnapshot::Interrupted,
            InitialHistory::Forked(forked_rollout_items),
            InterruptedTurnHistoryMarker::Disabled,
        ) else {
            unreachable!("a forked snapshot remains forked");
        };
        forked_rollout_items = items;
    }
    let retain_forked_item = |envelope: &mut ResponseItemEnvelope, replaced: &mut bool| {
        if multi_agent_version == MultiAgentVersion::V2
            && (preserve_fork_prefix
                || matches!(&envelope.item, ResponseItem::Message { role, .. } if role == "user" || role == "assistant"))
        {
            // Resume must not recapture copied parent messages as local authorization.
            envelope
                .metadata
                .get_or_insert_default()
                .inherited_user_message = true;
        }
        if let Some(metadata) = &mut envelope.metadata
            && (metadata.sender_user_messages.take().is_some()
                || !matches!(&envelope.item, ResponseItem::Message { role, .. } if role == "user"))
        {
            // Assistant and tool positions belong to the parent counter, not the child.
            metadata.user_input_order = None;
        }
        if preserve_fork_prefix {
            return true;
        }
        let response_item = &mut envelope.item;
        // Tool declarations and their comparison baseline must survive or be rebuilt together.
        if matches!(response_item, ResponseItem::AdditionalTools { .. }) {
            return preserve_context_baselines;
        }
        if matches!(response_item, ResponseItem::AgentMessage { .. }) {
            return false;
        }
        if !retain_forked_developer_message(
            response_item,
            &multi_agent_v2_usage_hint_texts_to_filter,
        ) {
            return false;
        }

        if matches!(response_item, ResponseItem::Message { role, .. } if role == "developer") {
            let Some(mut content) = to_annotated_content(response_item) else {
                return false;
            };
            content.retain_mut(|content_item| {
                if matches!(
                    content_item.kind().as_str(),
                    BaseInstructionsFragment::KIND | IncrementalToolsHint::KIND
                ) {
                    return preserve_context_baselines;
                }
                let ContentItem::InputText { text } = content_item.content_mut() else {
                    return true;
                };
                if ManagedDeveloperInstructions::matches_text(text)
                    || ModelInstructions::matches_text(text)
                    || PersistentModeState::matches_text(text)
                {
                    // If the child will rebuild its initial context, drop the inherited
                    // instructions; startup will add the current requirements and effort
                    // instructions once.
                    return preserve_context_baselines;
                }
                let (Some(parent_developer_instructions), Some(subagent_developer_instructions)) = (
                    parent_developer_instructions.as_ref(),
                    subagent_developer_instructions.as_ref(),
                ) else {
                    return true;
                };
                // TODO(anp) track better message fragment provenance in rollouts.
                if !text.contains(parent_developer_instructions) {
                    return true;
                }

                *replaced = true;
                let replacement = if preserve_context_baselines {
                    subagent_developer_instructions.as_str()
                } else {
                    ""
                };
                *text = text.replace(parent_developer_instructions, replacement);
                !text.is_empty()
            });
            return !content.is_empty() && set_annotated_content(response_item, content).is_some();
        }

        true
    };
    forked_rollout_items.retain_mut(|item| {
        let keep = (preserve_fork_prefix && matches!(item, RolloutItem::ResponseItem(_)))
            || keep_forked_rollout_item(item, preserve_context_baselines);
        if !keep
            || destination_history_mode == Some(ThreadHistoryMode::Paginated)
                && matches!(
                    &*item,
                    RolloutItem::EventMsg(
                        EventMsg::ItemCompleted(_)
                            | EventMsg::TokenCount(_)
                            | EventMsg::ThreadGoalUpdated(_)
                            | EventMsg::ThreadSettingsApplied(_),
                    )
                )
        {
            return false;
        }

        match item {
            RolloutItem::ResponseItem(response_item) => {
                retain_forked_item(response_item, &mut replaced_parent_developer_instructions)
            }
            // VRS assemblies never contain rollout compaction records.
            RolloutItem::Compacted(_) => false,
            RolloutItem::WorldState(world_state) => {
                if multi_agent_version == MultiAgentVersion::V2 {
                    world_state.state.remove("multi_agent_usage_hint");
                }
                true
            }
            RolloutItem::RealtimeItem(_) => false,
            RolloutItem::DynamicToolsUpdated { .. }
            | RolloutItem::EventMsg(_)
            | RolloutItem::SessionMeta(_)
            | RolloutItem::TurnContext(_)
            | RolloutItem::InterAgentCommunication(_)
            | RolloutItem::InterAgentCommunicationMetadata { .. } => true,
            RolloutItem::RetainedContext(_)
            | RolloutItem::TokenUsageRecord(_)
            | RolloutItem::SecurityRiskScore(_) => false,
        }
    });
    if preserve_fork_prefix {
        forked_rollout_items.push(RolloutItem::ResponseItem(
            ContextualUserFragment::into(MultiAgentUsageHint::new(
                "You are now a newly spawned child agent. The preceding conversation is inherited parent context. Follow your own role, identity, and task below; earlier identities, tasks, and action-specific approvals belong to your ancestors. Inherited tool calls are historical records; live tool sessions and process handles are not inherited. Report your result to your parent.",
            )).into(),
        ));
    }
    // Full forks reuse the parent's reference context instead of rebuilding it. If that
    // context omitted the parent's developer fragment, append the child's override so its
    // instructions still reach the model exactly once.
    if let Some(subagent_developer_instructions) = subagent_developer_instructions.as_ref()
        && preserve_context_baselines
        && !replaced_parent_developer_instructions
        && !subagent_developer_instructions.is_empty()
        && let Some(parent_thread) = &parent_thread
        && parent_thread.session.reference_context_item().await.is_some()
    {
        let developer_message = ContextualUserFragment::into(DeveloperInstructions::new(
            subagent_developer_instructions,
        ));
        forked_rollout_items.push(RolloutItem::ResponseItem(developer_message.into()));
    }
    if preserve_context_baselines
        && multi_agent_version == MultiAgentVersion::V2
        && let Some(subagent_usage_hint) = options
            .multi_agent_v2_usage_hints
            .as_ref()
            .map(|hints| hints.subagent.clone())
            .unwrap_or_else(|| {
                resolve_usage_hints(
                    &config.multi_agent_v2,
                    ResolvedModelMessages::bundled().multi_agent(),
                    !config.update_plan_enabled,
                )
                .subagent
            })
    {
        let subagent_usage_hint_message = ContextualUserFragment::into(subagent_usage_hint);
        forked_rollout_items.push(RolloutItem::ResponseItem(
            subagent_usage_hint_message.into(),
        ));
    }
    Ok((
        InitialHistory::Forked(forked_rollout_items),
        destination_history_mode,
    ))
}
