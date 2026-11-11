//! Reviewer policy carried by each VRS history snapshot.

use codex_extension_api::ConversationHistorySnapshot;

/// Selects checkpoint-based, legacy, or independent reviewer history.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub enum GuardianContextMode {
    Legacy,
    /// Thread-owned authorization with an independent reviewer transcript.
    Independent,
    #[default]
    ThreadOwned,
}

impl GuardianContextMode {
    /// Stable, bounded label for the context actually selected for a review.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Legacy => "legacy",
            Self::Independent => "independent",
            Self::ThreadOwned => "thread_owned",
        }
    }

    /// Read reviewer policy from the same snapshot as its evidence, including delayed reviews.
    pub fn from_history(history: &dyn ConversationHistorySnapshot) -> Self {
        if history.uses_independent_review_history() {
            Self::Independent
        } else if history.uses_parent_context_for_review() {
            Self::ThreadOwned
        } else {
            Self::Legacy
        }
    }
}
