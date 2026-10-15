//! Omits sentences telling the model its context may be compacted or summarized.
//!
//! This build never compacts: every request is assembled from the original records, so catalog
//! text describing compaction is false here. Paragraphs without such a sentence stay byte-for-byte.

/// Phrases that mark a compaction sentence, besides inflected forms of "compact".
const MARKER_PHRASES: [&str; 3] = [
    "run out of context",
    "summary instead of the full",
    "restart from scratch",
];
/// Endings that turn "compact" into the compaction verb or noun; the bare adjective stays.
const COMPACT_ENDINGS: [&str; 4] = ["ion", "ions", "ed", "s"];

/// Call only for Codex-owned prompt text; custom instructions must remain unchanged.
pub fn without_compaction_guidance(instructions: &str) -> String {
    let pieces = paragraphs(instructions);
    let mut kept: Vec<(String, &str)> = Vec::with_capacity(pieces.len());
    let last = pieces.len().saturating_sub(1);
    for (index, (paragraph, separator)) in pieces.into_iter().enumerate() {
        match without_marked_sentences(paragraph) {
            Some(text) => kept.push((text, separator)),
            // A dropped last paragraph hands its (empty) separator to the paragraph before it.
            None if index == last => {
                if let Some(previous) = kept.last_mut() {
                    previous.1 = separator;
                }
            }
            None => {}
        }
    }
    let mut rendered = String::with_capacity(instructions.len());
    for (text, separator) in kept {
        rendered.push_str(&text);
        rendered.push_str(separator);
    }
    rendered
}

/// Splits text into (paragraph, following separator) pairs; a separator is a run of two or more
/// newlines, and the last paragraph's separator is empty.
fn paragraphs(text: &str) -> Vec<(&str, &str)> {
    let bytes = text.as_bytes();
    let mut pieces = Vec::new();
    let mut start = 0;
    let mut index = 0;
    while index + 1 < bytes.len() {
        if bytes[index] == b'\n' && bytes[index + 1] == b'\n' {
            let mut end = index + 2;
            while end < bytes.len() && bytes[end] == b'\n' {
                end += 1;
            }
            pieces.push((&text[start..index], &text[index..end]));
            start = end;
            index = end;
        } else {
            index += 1;
        }
    }
    pieces.push((&text[start..], ""));
    pieces
}

/// Returns the paragraph unchanged when no sentence is marked, the unmarked sentences joined by
/// one space otherwise, and `None` when every sentence is marked.
fn without_marked_sentences(paragraph: &str) -> Option<String> {
    let body = paragraph.trim();
    let sentences = sentences(body);
    if !sentences.iter().any(|sentence| is_compaction_sentence(sentence)) {
        return Some(paragraph.to_string());
    }
    let unmarked = sentences
        .into_iter()
        .filter(|sentence| !is_compaction_sentence(sentence))
        .collect::<Vec<_>>();
    if unmarked.is_empty() {
        return None;
    }
    let leading = &paragraph[..paragraph.len() - paragraph.trim_start().len()];
    let trailing = &paragraph[paragraph.trim_end().len()..];
    Some(format!("{leading}{}{trailing}", unmarked.join(" ")))
}

/// Cuts after `.`, `!` or `?` followed by whitespace, dropping that whitespace.
fn sentences(body: &str) -> Vec<&str> {
    let bytes = body.as_bytes();
    let mut sentences = Vec::new();
    let mut start = 0;
    let mut index = 0;
    while index + 1 < bytes.len() {
        if matches!(bytes[index], b'.' | b'!' | b'?') && bytes[index + 1].is_ascii_whitespace() {
            sentences.push(&body[start..=index]);
            let mut next = index + 1;
            while next < bytes.len() && bytes[next].is_ascii_whitespace() {
                next += 1;
            }
            start = next;
            index = next;
        } else {
            index += 1;
        }
    }
    if start < bytes.len() {
        sentences.push(&body[start..]);
    }
    sentences
}

fn is_compaction_sentence(sentence: &str) -> bool {
    let lower = sentence.to_ascii_lowercase();
    if MARKER_PHRASES.iter().any(|phrase| lower.contains(phrase)) {
        return true;
    }
    let bytes = lower.as_bytes();
    lower.match_indices("compact").any(|(at, word)| {
        let starts_word = at == 0 || !bytes[at - 1].is_ascii_alphabetic();
        let ending_start = at + word.len();
        let ending_len = bytes[ending_start..]
            .iter()
            .take_while(|byte| byte.is_ascii_alphabetic())
            .count();
        starts_word
            && COMPACT_ENDINGS.contains(&&lower[ending_start..ending_start + ending_len])
    })
}

#[cfg(test)]
#[path = "compaction_guidance_tests.rs"]
mod tests;
