//! Request-effort pins across initial replay and sampling.
use crate::session::step_settings::ResolvedStepSettings;
use crate::session::tests::make_session_and_context_with_auth_and_config_and_rx;
use codex_features::Feature;
use codex_history::InitialHistory;
use codex_history::ResumedHistory;
use codex_login::CodexAuth;
use codex_protocol::ThreadId;
use codex_protocol::openai_models::ReasoningEffort;
use pretty_assertions::assert_eq;
use std::sync::Arc;
use test_case::test_case;

#[test_case(InitialHistory::Forked(Vec::new()); "fork")]
#[test_case(InitialHistory::Resumed(ResumedHistory {
history_revision: None,
    conversation_id: ThreadId::default(),
    history: Arc::new(Vec::new()),
    rollout_path: None,
}); "resume")]
#[tokio::test]
async fn initial_replay_preserves_prewarmed_effort(history: InitialHistory) {
    let (session, turn_context, _events) = make_session_and_context_with_auth_and_config_and_rx(
        CodexAuth::from_api_key("Test API Key"),
        Vec::new(),
        |config| {
            config
                .features
                .enable(Feature::ReasoningEffortOverride)
                .unwrap();
        },
    )
    .await;
    let mut model_info = Arc::clone(&turn_context.initial_settings.model_info);
    Arc::make_mut(&mut model_info).supports_reasoning_effort_updates = true;
    let mut selected = turn_context.initial_settings.selected().clone();
    selected.collaboration_mode.settings.reasoning_effort = Some(ReasoningEffort::Medium);
    let prewarm_settings = ResolvedStepSettings::new(
        Arc::new(selected.clone()),
        Arc::clone(&model_info),
        &codex_features::Features::default(),
    );
    // Force the ordering where prewarm pins its request before initial replay finishes.
    assert_eq!(
        session
            .reasoning_effort_for_request(&prewarm_settings)
            .await,
        Some(ReasoningEffort::Medium),
    );
    session.record_initial_history(history).await;

    selected.collaboration_mode.settings.reasoning_effort = Some(ReasoningEffort::High);
    let turn_settings = ResolvedStepSettings::new(
        Arc::new(selected),
        model_info,
        &codex_features::Features::default(),
    );
    assert_eq!(
        session.reasoning_effort_for_request(&turn_settings).await,
        Some(ReasoningEffort::Medium),
    );
}
