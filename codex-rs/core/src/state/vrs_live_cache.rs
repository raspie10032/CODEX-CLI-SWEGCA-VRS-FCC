//! Optimistic publication of the non-model D4 cache under the existing session mutex.
//!
//! Assemblies run independently. A refresh retains records overlapping its invocation and
//! pending VRS publication, then retires completed records at its cut. No request waits for
//! another assembly, recording call, or rollout writer.

use std::collections::BTreeMap;
use std::collections::HashSet;
use std::sync::Arc;
use std::sync::atomic::AtomicU8;
use std::sync::atomic::Ordering;

use codex_history::ResponseItemEnvelope;
use codex_protocol::models::ResponseItem;
use codex_utils_output_truncation::TruncationPolicy;

use crate::context_manager::ContextManager;

const PENDING: u8 = 0;
const PUBLISHED: u8 = 1;
const FAILED: u8 = 2;
const CANCELLED: u8 = 3;

struct RecordedBatch {
    items: Vec<ResponseItemEnvelope>,
    publication: Arc<AtomicU8>,
}

/// Dropping a recording future cannot silently classify its unpublished cache items as durable.
pub(crate) struct VrsPublication {
    state: Arc<AtomicU8>,
}

impl VrsPublication {
    pub(crate) fn finish(self, published: bool) {
        self.state.store(
            if published { PUBLISHED } else { FAILED },
            Ordering::Release,
        );
    }
}

impl Drop for VrsPublication {
    fn drop(&mut self) {
        let _ =
            self.state
                .compare_exchange(PENDING, CANCELLED, Ordering::Release, Ordering::Relaxed);
    }
}

pub(crate) struct VrsCacheCut {
    generation: u64,
    record_sequence: u64,
    pending: HashSet<u64>,
}

#[derive(Default)]
pub(crate) struct VrsLiveCache {
    last_record: u64,
    last_started_assembly: u64,
    last_installed_assembly: u64,
    records: BTreeMap<u64, RecordedBatch>,
}

impl VrsLiveCache {
    pub(crate) fn record(
        &mut self,
        history: &mut ContextManager,
        items: &mut [ResponseItemEnvelope],
        policy: TruncationPolicy,
    ) -> Result<VrsPublication, String> {
        let sequence = self.last_record.checked_add(1).ok_or_else(|| {
            "VRS live cache record sequence overflow; reopen the session".to_string()
        })?;
        let start = history.annotated_items().len();
        history.record_annotated_items(items, policy);
        // Store the already processed cache representation, including its original provenance.
        // Reconciliation must not replay provenance capture or truncate an output a second time.
        let recorded = history.annotated_items()[start..].to_vec();
        let publication = Arc::new(AtomicU8::new(PENDING));
        self.last_record = sequence;
        self.records.insert(
            sequence,
            RecordedBatch {
                items: recorded,
                publication: Arc::clone(&publication),
            },
        );
        Ok(VrsPublication { state: publication })
    }

    pub(crate) fn recording_error(&self) -> Option<String> {
        self.records.iter().find_map(|(sequence, batch)| {
            let reason = match batch.publication.load(Ordering::Acquire) {
                FAILED => "failed",
                CANCELLED => "was cancelled before publication completed",
                _ => return None,
            };
            Some(format!("VRS history record {sequence} {reason}"))
        })
    }

    pub(crate) fn begin_assembly(&mut self) -> Result<VrsCacheCut, String> {
        self.last_started_assembly =
            self.last_started_assembly.checked_add(1).ok_or_else(|| {
                "VRS live cache assembly generation overflow; reopen the session".to_string()
            })?;
        Ok(VrsCacheCut {
            generation: self.last_started_assembly,
            record_sequence: self.last_record,
            pending: self
                .records
                .iter()
                .filter_map(|(sequence, batch)| {
                    (batch.publication.load(Ordering::Acquire) == PENDING).then_some(*sequence)
                })
                .collect(),
        })
    }

    pub(crate) fn install(
        &mut self,
        history: &mut ContextManager,
        cut: VrsCacheCut,
        items: Vec<ResponseItem>,
    ) -> bool {
        if cut.generation <= self.last_installed_assembly {
            return false;
        }
        let overlaps =
            |sequence: u64| sequence > cut.record_sequence || cut.pending.contains(&sequence);
        let suffix = self
            .records
            .iter()
            .filter(|(sequence, _)| overlaps(**sequence))
            .flat_map(|(_, batch)| batch.items.iter().cloned())
            .collect();
        history.replace_assembled_with_suffix(items, suffix);
        // Even an equal-items assembly supersedes an older in-flight cache refresh. This is
        // independent of ContextManager's history version, which guardian cursors observe.
        self.last_installed_assembly = cut.generation;
        self.records.retain(|sequence, batch| {
            overlaps(*sequence) || batch.publication.load(Ordering::Acquire) != PUBLISHED
        });
        true
    }

    /// Design §12 D4'': the thread is unused, so the cache gives up its assembly. An assembly
    /// started before this is not installed later; records not yet published keep their items,
    /// so the next install still unions them (D4).
    pub(crate) fn release(&mut self, history: &mut ContextManager) {
        self.last_installed_assembly = self.last_started_assembly;
        self.records
            .retain(|_, batch| batch.publication.load(Ordering::Acquire) != PUBLISHED);
        history.replace_assembled_with_suffix(Vec::new(), Vec::new());
    }

    pub(crate) fn reset(&mut self) {
        self.last_installed_assembly = self.last_started_assembly;
        // A destructive host reset invalidates old cache payloads, but cannot make an
        // unfinished or failed publication disappear from the D5 error check.
        self.records.retain(|_, batch| {
            batch.items.clear();
            batch.publication.load(Ordering::Acquire) != PUBLISHED
        });
    }
}

#[cfg(test)]
mod tests {
    use codex_history::CodexHarnessMetadata;
    use codex_protocol::ResponseItemId;
    use codex_protocol::models::ContentItem;

    use super::*;

    fn message(text: &str) -> ResponseItem {
        ResponseItem::Message {
            id: Some(ResponseItemId::new("msg")),
            role: "user".to_string(),
            content: vec![ContentItem::InputText {
                text: text.to_string(),
            }],
            status: None,
            encrypted_content: None,
            phase: None,
            internal_chat_message_metadata_passthrough: None,
        }
    }

    fn record(
        cache: &mut VrsLiveCache,
        history: &mut ContextManager,
        item: &ResponseItem,
    ) -> VrsPublication {
        cache
            .record(
                history,
                &mut [ResponseItemEnvelope::new(item.clone())],
                TruncationPolicy::Tokens(10_000),
            )
            .expect("record reservation")
    }

    fn items(history: &ContextManager) -> Vec<ResponseItem> {
        history.raw_items().cloned().collect()
    }

    #[test]
    fn post_snapshot_record_survives_install_then_retires_at_next_cut() {
        let mut cache = VrsLiveCache::default();
        let mut history = ContextManager::new();
        let before = message("before snapshot");
        let after = message("after snapshot");
        record(&mut cache, &mut history, &before).finish(true);
        let cut = cache.begin_assembly().unwrap();
        record(&mut cache, &mut history, &after).finish(true);

        assert!(cache.install(&mut history, cut, vec![before.clone()]));
        assert_eq!(items(&history), vec![before.clone(), after.clone()]);
        assert_eq!(cache.records.len(), 1);

        let cut = cache.begin_assembly().unwrap();
        assert!(cache.install(&mut history, cut, vec![before.clone(), after.clone()]));
        assert_eq!(items(&history), vec![before, after]);
        assert!(cache.records.is_empty());
    }

    #[test]
    fn pre_snapshot_pending_record_survives_publication_during_assembly() {
        let mut cache = VrsLiveCache::default();
        let mut history = ContextManager::new();
        let pending = message("accepted locally but not yet in S");
        let publication = record(&mut cache, &mut history, &pending);
        let cut = cache.begin_assembly().unwrap();
        publication.finish(true);

        cache.install(&mut history, cut, Vec::new());
        assert_eq!(items(&history), vec![pending.clone()]);
        assert_eq!(cache.records.len(), 1);

        let cut = cache.begin_assembly().unwrap();
        cache.install(&mut history, cut, vec![pending.clone()]);
        assert_eq!(items(&history), vec![pending]);
        assert!(cache.records.is_empty());
    }

    #[test]
    fn newer_equal_assembly_supersedes_older_completion_without_changing_history_version() {
        let mut cache = VrsLiveCache::default();
        let mut history = ContextManager::new();
        let current = message("newer S");
        record(&mut cache, &mut history, &current).finish(true);
        let initial = cache.begin_assembly().unwrap();
        cache.install(&mut history, initial, vec![current.clone()]);
        let version = history.history_version();

        let old = cache.begin_assembly().unwrap();
        let new = cache.begin_assembly().unwrap();
        assert!(cache.install(&mut history, new, vec![current.clone()]));
        assert_eq!(history.history_version(), version);
        assert!(!cache.install(&mut history, old, vec![message("stale S")]));
        assert_eq!(items(&history), vec![current]);
        assert_eq!(history.history_version(), version);
    }

    #[test]
    fn continuously_overlapping_records_do_not_pin_completed_history() {
        let mut cache = VrsLiveCache::default();
        let mut history = ContextManager::new();
        let mut latest = message("initial");
        record(&mut cache, &mut history, &latest).finish(true);
        for index in 0..256 {
            let cut = cache.begin_assembly().unwrap();
            let next = message(&format!("overlapping record {index}"));
            record(&mut cache, &mut history, &next).finish(true);
            cache.install(&mut history, cut, vec![latest.clone()]);
            assert_eq!(items(&history), vec![latest, next.clone()]);
            assert_eq!(cache.records.len(), 1);
            latest = next;
        }
        let cut = cache.begin_assembly().unwrap();
        cache.install(&mut history, cut, vec![latest.clone()]);
        assert_eq!(items(&history), vec![latest]);
        assert!(cache.records.is_empty());
    }

    #[test]
    fn overlapping_identity_keeps_assembled_representation_and_original_provenance() {
        let mut cache = VrsLiveCache::default();
        let mut history = ContextManager::new();
        let mut original = ResponseItemEnvelope {
            item: message("full original record"),
            metadata: Some(CodexHarnessMetadata {
                user_input_order: Some(7),
                ..Default::default()
            }),
        };
        let publication = cache
            .record(
                &mut history,
                std::slice::from_mut(&mut original),
                TruncationPolicy::Tokens(10_000),
            )
            .unwrap();
        let cut = cache.begin_assembly().unwrap();
        publication.finish(true);
        let mut assembled = original.item.clone();
        if let ResponseItem::Message { content, .. } = &mut assembled {
            *content = vec![ContentItem::InputText {
                text: "assembler selected representation".to_string(),
            }];
        }
        let original_metadata = history.annotated_items()[0].metadata.clone();

        cache.install(&mut history, cut, vec![assembled.clone()]);
        assert_eq!(items(&history), vec![assembled]);
        assert_eq!(history.annotated_items()[0].metadata, original_metadata);
    }

    #[test]
    fn identical_idless_records_retain_ambiguous_overlap_until_publication_is_covered() {
        let mut cache = VrsLiveCache::default();
        let mut history = ContextManager::new();
        let mut item = message("the same content from two distinct records");
        item.set_id(None);
        record(&mut cache, &mut history, &item).finish(true);
        let initial = cache.begin_assembly().unwrap();
        cache.install(&mut history, initial, vec![item.clone()]);

        let pending = record(&mut cache, &mut history, &item);
        let cut = cache.begin_assembly().unwrap();
        // A still contains only the old occurrence. Content dedup would lose the new one.
        cache.install(&mut history, cut, vec![item.clone()]);
        assert_eq!(items(&history), vec![item.clone(), item.clone()]);

        let cut = cache.begin_assembly().unwrap();
        // Publication may reach S before its caller marks completion. Without an identity
        // watermark the cache conservatively keeps the overlap; it is never model input.
        cache.install(&mut history, cut, vec![item.clone(), item.clone()]);
        assert_eq!(
            items(&history),
            vec![item.clone(), item.clone(), item.clone()]
        );
        assert_eq!(cache.records.len(), 1);
        pending.finish(true);

        let cut = cache.begin_assembly().unwrap();
        cache.install(&mut history, cut, vec![item.clone(), item.clone()]);
        assert_eq!(items(&history), vec![item.clone(), item]);
        assert!(cache.records.is_empty());
    }

    #[test]
    fn failed_or_cancelled_publication_remains_visible_to_d5_after_reset() {
        for published in [Some(false), None] {
            let mut cache = VrsLiveCache::default();
            let mut history = ContextManager::new();
            let publication = record(&mut cache, &mut history, &message("pending"));
            if let Some(published) = published {
                publication.finish(published);
            } else {
                drop(publication);
            }
            assert!(cache.recording_error().is_some());
            cache.reset();
            assert!(cache.recording_error().is_some());
        }
    }

    #[test]
    fn destructive_reset_supersedes_inflight_refresh_without_replaying_old_payloads() {
        let mut cache = VrsLiveCache::default();
        let mut history = ContextManager::new();
        let publication = record(&mut cache, &mut history, &message("old record"));
        let old_cut = cache.begin_assembly().unwrap();
        cache.reset();
        history.replace_annotated(Vec::new());
        publication.finish(true);
        assert!(!cache.install(&mut history, old_cut, vec![message("old assembly")]));
        let new_cut = cache.begin_assembly().unwrap();
        cache.install(&mut history, new_cut, Vec::new());
        assert!(items(&history).is_empty());
        assert!(cache.records.is_empty());
    }
}
