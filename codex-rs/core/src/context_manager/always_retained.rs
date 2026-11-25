//! Items marked to survive every window, `Ret(S)` (design 16.1 3(b)).

use std::collections::HashSet;
use std::sync::Arc;

use codex_history::ResponseItemEnvelope;
use codex_protocol::models::ResponseItem;

use super::history::is_api_message;
use super::history::is_user_turn_boundary;

/// The union of retained items by item id, kept in rollout position order.
#[derive(Clone, Debug, Default)]
pub(crate) struct AlwaysRetained {
    items: Arc<Vec<ResponseItemEnvelope>>,
    ids: Arc<HashSet<String>>,
}

impl AlwaysRetained {
    pub(crate) fn items(&self) -> Arc<Vec<ResponseItemEnvelope>> {
        Arc::clone(&self.items)
    }

    pub(crate) fn insert(&mut self, envelope: &ResponseItemEnvelope) {
        if !envelope.is_always_retained() {
            return;
        }
        let Some(id) = envelope.id() else {
            return;
        };
        if self.ids.contains(id.as_str()) {
            return;
        }
        Arc::make_mut(&mut self.ids).insert(id.as_str().to_owned());
        Arc::make_mut(&mut self.items).push(envelope.clone());
    }
}

/// Reads `Ret(S)` off saved rollout lines without keeping the other items.
///
/// Rollback markers occur only in historical rollouts. With `turns` the number of surviving
/// instruction turns at a line, a retained line is dropped when a later marker lowers the count
/// below the count at that line.
#[derive(Default)]
pub(crate) struct RetentionReplay {
    turns: usize,
    retained: Vec<(usize, ResponseItemEnvelope)>,
}

impl RetentionReplay {
    pub(crate) fn record(&mut self, envelope: &ResponseItemEnvelope) {
        if is_api_message(&envelope.item, envelope.metadata.as_ref()) {
            self.record_item(&envelope.item);
        }
        if envelope.is_always_retained() {
            self.retained.push((self.turns, envelope.clone()));
        }
    }

    /// Records an item that carries no harness metadata.
    pub(crate) fn record_item(&mut self, item: &ResponseItem) {
        if is_user_turn_boundary(item) {
            self.turns = self.turns.saturating_add(1);
        }
    }

    pub(crate) fn rollback(&mut self, num_turns: u32) {
        self.turns = self
            .turns
            .saturating_sub(usize::try_from(num_turns).unwrap_or(usize::MAX));
        while self
            .retained
            .last()
            .is_some_and(|(turns, _)| *turns > self.turns)
        {
            self.retained.pop();
        }
    }

    pub(crate) fn finish(self) -> Vec<ResponseItemEnvelope> {
        let mut union = AlwaysRetained::default();
        for (_, envelope) in &self.retained {
            union.insert(envelope);
        }
        Arc::unwrap_or_clone(union.items)
    }
}
