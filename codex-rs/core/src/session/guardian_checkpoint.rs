//! Captures a completed Guardian VRS assembly as original fork response items.
//! This snapshot is in memory only; transcript durability remains part of turn completion.

use super::session::Session;
use codex_history::RolloutItem;
use codex_protocol::error::Result as CodexResult;
use codex_protocol::protocol::EventMsg;
use codex_protocol::protocol::TokenCountEvent;

impl Session {
    pub(crate) async fn guardian_fork_history(&self) -> CodexResult<Vec<RolloutItem>> {
        let history = self
            .vrs_history()
            .await
            .map_err(super::vrs_input::vrs_error_to_codex)?;
        let mut items: Vec<RolloutItem> = history
            .annotated_items()
            .iter()
            .cloned()
            .map(RolloutItem::ResponseItem)
            .collect();
        if let Some(world_state) = history.world_state_checkpoint() {
            items.push(RolloutItem::WorldState(world_state));
        }
        if let Some(context) = history.reference_context_item() {
            items.push(RolloutItem::TurnContext(context));
        }
        if let Some(record) = self.state.lock().await.latest_token_usage_record.clone() {
            items.push(RolloutItem::TokenUsageRecord(record));
        }
        items.push(RolloutItem::EventMsg(EventMsg::TokenCount(
            TokenCountEvent {
                info: history.token_info(),
                rate_limits: None,
            },
        )));
        Ok(items)
    }
}

#[cfg(test)]
#[path = "guardian_checkpoint_tests.rs"]
mod tests;
