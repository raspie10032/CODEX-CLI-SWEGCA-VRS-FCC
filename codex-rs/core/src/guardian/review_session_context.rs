//! Owns sync reviewer checkpoint and invalidation policy for each context mode.
//! Independent review preserves thread-owned authorization without inheriting parent checkpoints.

use codex_features::Feature;

use crate::codex_thread::GuardianAuthorizationVersion;
use crate::config::ManagedFeatures;
use crate::context::GuardianContextMode;
use crate::session::session::Session;

#[derive(Clone, Copy, PartialEq, Eq)]
pub(super) enum ReviewContextPolicy {
    Legacy,
    LegacyWithCheckpointReuse,
    ThreadOwned,
    Independent,
}

impl ReviewContextPolicy {
    pub(super) fn for_context(mode: GuardianContextMode, features: &ManagedFeatures) -> Self {
        match mode {
            GuardianContextMode::ThreadOwned => Self::ThreadOwned,
            GuardianContextMode::Independent => Self::Independent,
            GuardianContextMode::Legacy
                if features.enabled(Feature::GuardianReuseParentCompaction) =>
            {
                Self::LegacyWithCheckpointReuse
            }
            GuardianContextMode::Legacy => Self::Legacy,
        }
    }

    pub(super) async fn root_review_version(
        self,
        session: &Session,
    ) -> anyhow::Result<Option<(GuardianAuthorizationVersion, u64)>> {
        if matches!(self, Self::Legacy | Self::LegacyWithCheckpointReuse) {
            return Ok(None);
        }
        Ok(session
            .services
            .agent_control
            .get_guardian_package(session.thread_id)
            .await?
            .map(|snapshot| {
                (
                    snapshot.authorization_version,
                    snapshot.review_context_revision,
                )
            }))
    }
}
