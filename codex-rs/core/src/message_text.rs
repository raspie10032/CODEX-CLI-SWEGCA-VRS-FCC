//! Text helpers over message content.

use codex_protocol::models::ContentItem;
use codex_prompts::SUMMARY_PREFIX;

/// Joins the text parts of `content`, or `None` when it has no text.
pub fn content_items_to_text(content: &[ContentItem]) -> Option<String> {
    let mut pieces = Vec::new();
    for item in content {
        match item {
            ContentItem::InputText { text } | ContentItem::OutputText { text } => {
                if !text.is_empty() {
                    pieces.push(text.as_str());
                }
            }
            ContentItem::InputImage { .. } | ContentItem::InputAudio { .. } => {}
        }
    }
    if pieces.is_empty() {
        None
    } else {
        Some(pieces.join("\n"))
    }
}

/// True for the summary message that rollouts written before compaction was removed contain.
pub(crate) fn is_summary_message(message: &str) -> bool {
    message.starts_with(format!("{SUMMARY_PREFIX}\n").as_str())
}
