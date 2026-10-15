//! Covers the compaction sentences fixed in the design document (E1–E12) and the bundled catalog.

use super::*;
use pretty_assertions::assert_eq;

const E: [&str; 12] = [
    "When you run out of context, the conversation is automatically compacted into a summary, but you will still see all prior user requests.",
    "Compaction does not end the task.",
    "Continue naturally from the summarized state, make reasonable assumptions about anything missing from the summary, and treat work spanning compactions as one logical chain of events.",
    "Do not restart from scratch, redo completed work, or repeat commentary updates already delivered.",
    "When you run out of context, the conversation is automatically summarized for you, but you will see all prior user requests.",
    "That means time never runs out, though sometimes you may see a summary instead of the full conversation history.",
    "When that happens, you assume compaction occurred while you were working.",
    "Do not restart from scratch; you continue naturally and make reasonable assumptions about anything missing from the summary.",
    "Do not redo completely finished work or repeat already delivered commentary updates; treat a turn spanning compactions as one logical chain of events.",
    "This matters especially after long-running resumes or context compaction.",
    "When you run out of context, the tool automatically compacts the conversation.",
    "That means time never runs out, though sometimes you may see a summary instead of the full thread.",
];

#[test]
fn every_listed_sentence_is_a_compaction_sentence() {
    let unmarked = E
        .iter()
        .filter(|sentence| !is_compaction_sentence(sentence))
        .collect::<Vec<_>>();
    assert_eq!(unmarked, Vec::<&&str>::new());
}

#[test]
fn adjective_compact_is_not_a_marker() {
    let text = "Usually skip visuals. Compact notation and small examples do not count as visualizations.\n\nUse smaller headings inside compact panels.";
    assert_eq!(without_compaction_guidance(text), text);
}

#[test]
fn keeps_user_request_guidance_and_drops_compaction_paragraphs() {
    let template = [
        "Intro.",
        &format!(
            "{} Treat the most recent user message as the latest steering. Only replace the active task when the user cancels it.",
            E[0]
        ),
        &format!("{} {} {}", E[1], E[2], E[3]),
        &format!(
            "{} Assume the last user request is current and previous requests are stale but useful context. {} {} {} {}",
            E[4], E[5], E[6], E[7], E[8]
        ),
        &format!(
            "The user may send messages while you are working. {} If the newest message asks for status, you give that update.",
            E[9]
        ),
        &format!("{} {} {} {}", E[10], E[11], E[6], E[7]),
    ]
    .join("\n\n");
    assert_eq!(
        without_compaction_guidance(&template),
        [
            "Intro.",
            "Treat the most recent user message as the latest steering. Only replace the active task when the user cancels it.",
            "Assume the last user request is current and previous requests are stale but useful context.",
            "The user may send messages while you are working. If the newest message asks for status, you give that update.",
        ]
        .join("\n\n")
    );
}

#[test]
fn dropped_last_paragraph_keeps_trailing_text_shape() {
    assert_eq!(
        without_compaction_guidance(&format!("Keep this.\n\n{}\n", E[1])),
        "Keep this."
    );
    assert_eq!(
        without_compaction_guidance(&format!("{}\n\n\nKeep this.\n", E[1])),
        "Keep this.\n"
    );
}

#[test]
fn bundled_catalog_loses_exactly_the_listed_sentences() {
    let catalog: serde_json::Value =
        serde_json::from_str(include_str!("../../models-manager/models.json"))
            .unwrap_or_else(|err| panic!("bundled models.json should parse: {err}"));
    let models = catalog["models"]
        .as_array()
        .unwrap_or_else(|| panic!("bundled models.json should list models"));
    let mut templates_with_compaction = 0;
    for model in models {
        let Some(template) = model["model_messages"]["instructions_template"].as_str() else {
            continue;
        };
        let rendered = without_compaction_guidance(template);
        let slug = model["slug"].as_str().unwrap_or_default();

        let removed = paragraphs(template)
            .into_iter()
            .flat_map(|(paragraph, _)| sentences(paragraph.trim()))
            .filter(|sentence| is_compaction_sentence(sentence))
            .collect::<Vec<_>>();
        if !removed.is_empty() {
            templates_with_compaction += 1;
        }
        let unexpected = removed
            .iter()
            .filter(|sentence| !E.contains(sentence))
            .collect::<Vec<_>>();
        assert_eq!(unexpected, Vec::<&&str>::new(), "{slug}: unexpected removal");
        for sentence in E {
            assert!(!rendered.contains(sentence), "{slug}: kept {sentence}");
        }
        for (paragraph, _) in paragraphs(template) {
            if !sentences(paragraph.trim())
                .iter()
                .any(|sentence| is_compaction_sentence(sentence))
            {
                assert!(rendered.contains(paragraph), "{slug}: changed a clean paragraph");
            }
        }
        assert_eq!(without_compaction_guidance(&rendered), rendered, "{slug}: not idempotent");
    }
    assert!(templates_with_compaction > 0);
}
