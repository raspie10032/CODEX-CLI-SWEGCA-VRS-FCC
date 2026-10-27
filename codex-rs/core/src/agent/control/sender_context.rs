//! Captures genuine sender instructions and assistant context for host-delivered task messages.
//! Only turn-input admission calls this, before queueing; ordinary tool results and
//! quoted delegation text cannot establish sender provenance. Unloaded senders are read
//! through the host's authenticated thread store, without resuming their runtime.

use crate::context::GuardianSenderExchange;
use crate::context::GuardianSenderMessages;
use codex_guardian_context::GuardianRootMessage;
use codex_history::RetainedContextEntry;
use codex_history::RetainedContextOrder;
use codex_protocol::ThreadId;
use codex_protocol::error::CodexErr;
use codex_protocol::error::CodexErrorDetails;
use codex_protocol::error::Result as CodexResult;
use codex_protocol::models::ResponseItem;
use codex_thread_store::ReadThreadParams;
use std::time::Duration;

use super::LocalAgentRuntime;

impl LocalAgentRuntime {
    pub(crate) async fn capture_sender_user_messages(
        &self,
        item: &ResponseItem,
        receiver_thread_id: ThreadId,
    ) -> CodexResult<Option<GuardianSenderMessages>> {
        let ResponseItem::FunctionCallOutput {
            id: Some(id),
            call_id: None,
            name: Some(name),
            namespace: Some(namespace),
            output,
            ..
        } = item
        else {
            return Ok(None);
        };
        if !matches!(
            (namespace.as_str(), name.as_str()),
            ("codex_app" | "codex_tui", "send_message_to_thread")
                | ("codex_app", "create_thread")
                | ("cloud_threads", "send_message")
        ) {
            return Ok(None);
        }
        // Recognized deliveries always get their own snapshot, even without usable provenance.
        let source_thread_id = output.body.to_text().and_then(|text| {
            let (source, input) = text
                .strip_prefix("<codex_delegation>")?
                .strip_suffix("</codex_delegation>")?
                .trim()
                .strip_prefix("<source_thread_id>")?
                .split_once("</source_thread_id>")?;
            input
                .trim()
                .strip_prefix("<input>")?
                .strip_suffix("</input>")?;
            ThreadId::from_string(source)
                .ok()
                .filter(|source| *source != receiver_thread_id)
        });
        let mut fragment = GuardianSenderMessages {
            source: source_thread_id,
            delivery: id.to_string(),
            from_storage: false,
            messages: Vec::new(),
        };
        if let Some(source_thread_id) = source_thread_id
            && let Ok(manager) = self.upgrade()
        {
            let context = match manager.get_thread(source_thread_id).await {
                Ok(sender) => {
                    let history = sender.conversation_history_snapshot().await?;
                    history.retained_context().cloned()
                }
                Err(_) => {
                    // The store owns authorization, including cross-worker tenant boundaries.
                    // Bound path lookup and VRS assembly together so unavailable storage
                    // cannot stall turn admission.
                    let context = tokio::time::timeout(Duration::from_secs(/*secs*/ 5), async {
                        let stored = match manager
                            .read_stored_thread(ReadThreadParams {
                                thread_id: source_thread_id,
                                include_archived: true,
                                include_history: false,
                            })
                            .await
                        {
                            Ok(stored) => stored,
                            Err(error)
                                if matches!(
                                    error.details(),
                                    CodexErrorDetails::ThreadNotFound(_)
                                ) =>
                            {
                                return Ok(None);
                            }
                            Err(error) => return Err(error),
                        };
                        if stored.thread_id != source_thread_id || stored.source.is_internal() {
                            return Ok(None);
                        }
                        let Some(rollout_path) = stored.rollout_path else {
                            return Ok(None);
                        };
                        let history = crate::session::vrs_input::vrs_history_for_path(
                            rollout_path.as_path(),
                        )
                        .await
                        .map_err(crate::session::vrs_input::vrs_error_to_codex)?;
                        Ok::<_, CodexErr>(Some(history.retained_context().clone()))
                    })
                    .await
                    .map_err(|_| CodexErr::Timeout)??;
                    if context.is_some() {
                        fragment.from_storage = true;
                    }
                    context
                }
            };
            if let Some(context) = context {
                let mut exchanges = Vec::new();
                let mut assistant = None;
                for (order, entry) in context.ordered_entries() {
                    match (order, entry) {
                        (
                            RetainedContextOrder::Local(_),
                            RetainedContextEntry::UserMessage(message),
                        ) => exchanges.push((message, assistant.take())),
                        (
                            RetainedContextOrder::Local(_),
                            RetainedContextEntry::AssistantMessage(message),
                        ) => assistant = Some(message),
                        (RetainedContextOrder::Inherited(_), _)
                        | (_, RetainedContextEntry::VerifiedAnswer(_)) => {}
                    }
                }
                fragment.messages = exchanges
                    .into_iter()
                    .rev()
                    .take(/*n*/ 3)
                    .map(|(user, assistant)| GuardianSenderExchange {
                        user: user.complete.then(|| user.text.clone()),
                        assistant: assistant.map(|message| {
                            if message.complete {
                                GuardianRootMessage::Assistant(message.text.clone())
                            } else {
                                GuardianRootMessage::IncompleteAssistantContext
                            }
                        }),
                    })
                    .collect();
                fragment.messages.reverse();
            }
        }
        Ok(Some(fragment))
    }
}
