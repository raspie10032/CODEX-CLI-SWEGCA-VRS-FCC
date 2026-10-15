use super::session::Session;
use super::turn_context::TurnContext;
use codex_protocol::openai_models::ModelInfo;

#[derive(Debug)]
pub(crate) struct ContextWindowTokenStatus {
    // Full active context usage.
    pub(crate) active_context_tokens: i64,
    pub(crate) full_context_window_limit: Option<i64>,
    pub(crate) base_window_tokens_remaining: Option<i64>,
    pub(crate) full_context_window_limit_reached: bool,
    pub(crate) token_limit_reached: bool,
}

fn tokens_remaining(limit: Option<i64>, used: i64) -> Option<i64> {
    limit.map(|limit| limit.saturating_sub(used).max(0))
}

pub(crate) async fn context_window_token_status(
    sess: &Session,
    turn_context: &TurnContext,
) -> ContextWindowTokenStatus {
    context_window_token_status_for_model(sess, turn_context.model_info().as_ref()).await
}

async fn context_window_token_status_for_model(
    sess: &Session,
    model_info: &ModelInfo,
) -> ContextWindowTokenStatus {
    let active_context_tokens = sess.get_total_token_usage().await;

    // The model's full context window is a hard cap.
    let full_context_window_limit = model_info.resolved_context_window().map(|context_window| {
        context_window.saturating_mul(model_info.effective_context_window_percent) / 100
    });
    let base_window_tokens_remaining =
        tokens_remaining(full_context_window_limit, active_context_tokens);
    let full_context_window_limit_reached =
        full_context_window_limit.is_some_and(|limit| active_context_tokens >= limit);

    ContextWindowTokenStatus {
        active_context_tokens,
        full_context_window_limit,
        base_window_tokens_remaining,
        full_context_window_limit_reached,
        token_limit_reached: full_context_window_limit_reached,
    }
}
