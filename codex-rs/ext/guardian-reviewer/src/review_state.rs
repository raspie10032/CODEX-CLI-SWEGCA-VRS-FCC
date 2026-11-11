//! Owns reviewer transcript progress and fork-history bookkeeping.
//! The host captures VRS history and validates authorization before publishing a fork snapshot.
//! Evidence advances only after the matching review turn records its transcript input.

use codex_analytics::GuardianReviewSessionKind;
use codex_history::InitialHistory;
use codex_history::RolloutItem;
use codex_protocol::models::ContentItem;
use codex_protocol::models::ResponseItem;
use codex_protocol::protocol::Event;
use codex_protocol::protocol::EventMsg;
use tokio::sync::Mutex;

use crate::ConversationCheckpoint;
use crate::ConversationState;
use crate::GUARDIAN_TRANSCRIPT_START;

/// Opaque conversation progress retained while ThreadManager starts a reviewer.
pub struct GuardianReviewState {
    pub conversation: ConversationState<GuardianReviewHistory>,
    // The cursor describes evidence admitted for this reviewer-history version.
    pub transcript_history_version: u64,
    pub transcript_source: Option<GuardianTranscriptSource>,
    pub last_admitted_node_repl_response_sequence: u64,
    pub pending_node_repl_evidence_admission: Option<PendingNodeReplEvidenceAdmission>,
}

// These histories have independent version counters; a cursor must identify its source.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum GuardianTranscriptSource {
    Retained,
}

pub struct PendingNodeReplEvidenceAdmission {
    pub turn_id: String,
    pub response_sequence: u64,
}

pub type GuardianReviewForkSnapshot = ConversationCheckpoint<GuardianReviewHistory>;

/// Host-owned history and admitted evidence used to seed a private reviewer fork.
#[derive(Clone)]
pub struct GuardianReviewHistory {
    pub initial_history: InitialHistory,
    transcript_source: Option<GuardianTranscriptSource>,
    last_admitted_node_repl_response_sequence: u64,
}

impl GuardianReviewState {
    /// Restores fork progress or starts with an empty reviewer transcript.
    pub fn for_session(
        kind: GuardianReviewSessionKind,
        snapshot: Option<GuardianReviewForkSnapshot>,
    ) -> (Self, Option<InitialHistory>) {
        let mut conversation = snapshot
            .map(ConversationState::from)
            .unwrap_or_default();
        let history = match kind {
            GuardianReviewSessionKind::EphemeralForked => conversation.take_history(),
            // Replacement trunks keep the checkpoint if their first review is invalidated.
            GuardianReviewSessionKind::TrunkNew | GuardianReviewSessionKind::TrunkReused => {
                conversation
                    .snapshot()
                    .map(|checkpoint| checkpoint.history().clone())
            }
        };
        let state = Self {
            conversation,
            transcript_history_version: 0,
            transcript_source: history
                .as_ref()
                .and_then(|history| history.transcript_source),
            last_admitted_node_repl_response_sequence: history.as_ref().map_or(0, |history| {
                history.last_admitted_node_repl_response_sequence
            }),
            pending_node_repl_evidence_admission: None,
        };
        let initial_history = history.map(|history| history.initial_history);
        (state, initial_history)
    }

    /// Publishes captured history after the host's final authorization validation.
    pub fn commit_snapshot(&mut self, items: Vec<RolloutItem>) {
        let last_admitted_node_repl_response_sequence =
            self.last_admitted_node_repl_response_sequence;
        let transcript_source = self.transcript_source;
        self.conversation.commit_snapshot(GuardianReviewHistory {
            initial_history: InitialHistory::Forked(items),
            transcript_source,
            last_admitted_node_repl_response_sequence,
        });
    }
}

pub async fn admit_node_repl_evidence(state: &Mutex<GuardianReviewState>, event: &Event) {
    // Annotated review inputs are recorded as response items without UI turn
    // items. Both input paths emit this event after history admission.
    let EventMsg::RawResponseItem(recorded) = &event.msg else {
        return;
    };
    let ResponseItem::Message { role, content, .. } = &recorded.item else {
        return;
    };
    if role != "user"
        || !content.iter().any(|item| {
            matches!(item, ContentItem::InputText { text }
                if text == GUARDIAN_TRANSCRIPT_START || text == ">>> TRANSCRIPT DELTA START\n")
        })
    {
        return;
    }

    let mut state = state.lock().await;
    let Some(pending) = state.pending_node_repl_evidence_admission.as_ref() else {
        return;
    };
    if event.id == pending.turn_id {
        state.last_admitted_node_repl_response_sequence = state
            .last_admitted_node_repl_response_sequence
            .max(pending.response_sequence);
        state.pending_node_repl_evidence_admission = None;
    }
}
