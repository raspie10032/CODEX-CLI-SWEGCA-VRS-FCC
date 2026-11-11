//! Owns sync reviewer history policy for each context mode.
//! Model-visible parent history is supplied by the captured VRS assembly.

use codex_features::Features;

use crate::GuardianContextMode;

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum ReviewContextPolicy {
    Legacy,
    ThreadOwned,
    Independent,
}

impl ReviewContextPolicy {
    pub fn for_context(mode: GuardianContextMode, _features: &Features) -> Self {
        match mode {
            GuardianContextMode::ThreadOwned => Self::ThreadOwned,
            GuardianContextMode::Independent => Self::Independent,
            GuardianContextMode::Legacy => Self::Legacy,
        }
    }
}
