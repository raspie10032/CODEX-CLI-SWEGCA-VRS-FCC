//! In-process VRS context assembly (`libvrs`).
//!
//! One process-wide handle is opened at process startup. Rollout lines are inserted by their
//! recording caller (`insert`), then released after persistence (`written`). Model input is
//! assembled from that store (`assemble`). Requests never initialize the handle. A request that
//! finds the store still restoring waits for it (`wait`) and assembles then; that is the same
//! answer later, not another input, so there is still no history fallback.

use std::ffi::CString;
use std::ffi::c_char;
use std::ffi::c_int;
use std::ffi::c_uint;
use std::fmt;
use std::path::Path;
use std::sync::atomic::AtomicBool;
use std::sync::atomic::AtomicPtr;
use std::sync::atomic::Ordering;

/// Why the VRS store could not serve a call.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VrsError {
    /// Startup has not published a handle yet, or the store is still restoring (return code 1).
    NotReady,
    /// The required input exceeds the physical window (`vrs_assemble` returned 2).
    OverWindow,
    /// The library returned another error code.
    Failed(i32),
    /// The library could not be opened or its reply could not be read.
    Unavailable(String),
}

impl fmt::Display for VrsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotReady => write!(f, "VRS store is not ready (still restoring)"),
            Self::OverWindow => write!(f, "VRS assembled input exceeds the model context window"),
            Self::Failed(code) => write!(f, "VRS call failed with code {code}"),
            Self::Unavailable(reason) => write!(f, "VRS is unavailable: {reason}"),
        }
    }
}

impl std::error::Error for VrsError {}

/// The reply of one assembly: response items as JSON, the token estimate and the assembly time.
#[derive(Debug, Clone, Default)]
pub struct Assembled {
    pub items: Vec<serde_json::Value>,
    pub tokens: u64,
    pub micros: u64,
}

#[cfg(any(target_os = "linux", target_os = "macos"))]
mod ffi {
    use super::*;

    #[repr(C)]
    pub struct VrsH {
        _private: [u8; 0],
    }

    #[repr(C)]
    pub struct VrsOpts {
        pub sessions_dir: *const c_char,
        pub index_dir: *const c_char,
        pub workers: c_uint,
        pub cpus: *const c_uint,
        pub ncpus: c_uint,
        pub segwin: c_int,
        /// libvrs extension: token budget of `vrs_assemble`; 0 selects the library default.
        pub budget: u64,
    }

    unsafe extern "C" {
        pub fn vrs_open(opts: *const VrsOpts, out: *mut *mut VrsH) -> c_int;
        pub fn vrs_insert(
            h: *mut VrsH,
            path: *const c_char,
            off: u64,
            line: *const c_char,
            len: usize,
        ) -> c_int;
        pub fn vrs_written(h: *mut VrsH, path: *const c_char, off: u64) -> c_int;
        pub fn vrs_assemble(
            h: *mut VrsH,
            path: *const c_char,
            json: *mut *mut c_char,
            len: *mut usize,
        ) -> c_int;
        pub fn vrs_assemble_b(
            h: *mut VrsH,
            path: *const c_char,
            budget: u64,
            json: *mut *mut c_char,
            len: *mut usize,
        ) -> c_int;
        pub fn vrs_wait(h: *mut VrsH, path: *const c_char, timeout_ms: u64) -> c_int;
        pub fn vrs_free(p: *mut c_char);
    }
}

struct Handle {
    #[cfg(any(target_os = "linux", target_os = "macos"))]
    raw: *mut ffi::VrsH,
}

// The library keeps its state in CAS/atomic tables and is safe to call from any thread.
unsafe impl Send for Handle {}
unsafe impl Sync for Handle {}

const WORKERS: c_uint = 12;
const SEGWIN: c_int = 1;

/// The virtual rollout path under which the lines of a thread without a rollout file are kept.
///
/// Nothing is written at this path. Each live Session has its own generation so resuming the
/// same thread cannot reuse old `(path, offset)` keys. The basename retains the thread identity.
pub fn ephemeral_path(generation: &str, thread_id: &str) -> Result<std::path::PathBuf, VrsError> {
    let home = codex_utils_home_dir::find_codex_home()
        .map_err(|err| VrsError::Unavailable(err.to_string()))?;
    Ok(home
        .as_path()
        .join("sessions")
        .join("ephemeral")
        .join(generation)
        .join(format!("{thread_id}.jsonl")))
}

// Startup publishes exactly one immutable result. The allocation and library handle live for
// the process lifetime, so readers need neither a lock nor ownership/refcount updates.
static OPEN_STARTED: AtomicBool = AtomicBool::new(false);
static HANDLE: AtomicPtr<Result<Handle, VrsError>> = AtomicPtr::new(std::ptr::null_mut());

/// Opens the process-wide store before the application starts serving requests.
///
/// Opening starts the library's background restore and returns without waiting for readiness.
/// Repeated or concurrent calls never reopen the store: they return its published result, or
/// `NotReady` while the first caller is opening it. Request paths must only call `insert`,
/// `written`, and `assemble`, which read the published handle without initializing it.
pub fn initialize() -> Result<(), VrsError> {
    initialize_once(|| {
        let home = codex_utils_home_dir::find_codex_home()
            .map_err(|err| VrsError::Unavailable(err.to_string()))?;
        open_handle(home.as_path()).map_err(VrsError::Unavailable)
    })
}

/// Initializes a process whose Codex home is supplied by its embedding application or test.
///
/// Like `initialize`, this is a startup operation. The first startup call fixes the home for
/// the process lifetime; subsequent calls only read that result.
pub fn initialize_for_home(home: &Path) -> Result<(), VrsError> {
    initialize_once(|| open_handle(home).map_err(VrsError::Unavailable))
}

fn initialize_once(open: impl FnOnce() -> Result<Handle, VrsError>) -> Result<(), VrsError> {
    if OPEN_STARTED
        .compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
        .is_ok()
    {
        HANDLE.store(Box::into_raw(Box::new(open())), Ordering::Release);
    }
    handle().map(|_| ())
}

#[cfg(any(target_os = "linux", target_os = "macos"))]
fn open_handle(home: &Path) -> Result<Handle, String> {
    let sessions = home.join("sessions");
    let index = home.join("vrs").join("idx");
    // libvrs refuses to open without its rollout tree, and its index lives beside it.
    std::fs::create_dir_all(&sessions)
        .map_err(|err| format!("create {}: {err}", sessions.display()))?;
    std::fs::create_dir_all(&index).map_err(|err| format!("create {}: {err}", index.display()))?;
    let sessions_c = c_path(&sessions).map_err(|err| err.to_string())?;
    let index_c = c_path(&index).map_err(|err| err.to_string())?;
    let cpus: Vec<c_uint> = (0..WORKERS).collect();
    let opts = ffi::VrsOpts {
        sessions_dir: sessions_c.as_ptr(),
        index_dir: index_c.as_ptr(),
        workers: WORKERS,
        cpus: cpus.as_ptr(),
        ncpus: cpus.len() as c_uint,
        segwin: SEGWIN,
        budget: 0,
    };
    let mut raw: *mut ffi::VrsH = std::ptr::null_mut();
    // SAFETY: `opts` and the buffers it points to outlive the call; `raw` is a valid out pointer.
    let rc = unsafe { ffi::vrs_open(&opts, &mut raw) };
    if rc != 0 || raw.is_null() {
        return Err(format!("vrs_open returned {rc}"));
    }
    Ok(Handle { raw })
}

#[cfg(not(any(target_os = "linux", target_os = "macos")))]
fn open_handle(_home: &Path) -> Result<Handle, String> {
    Err("libvrs is only available on Linux and macOS".to_string())
}

fn handle() -> Result<&'static Handle, VrsError> {
    let result = HANDLE.load(Ordering::Acquire);
    // SAFETY: only startup stores this pointer, after fully constructing its allocation. It is
    // immutable and never freed or replaced; a null pointer means startup has not published yet.
    let result = unsafe { result.as_ref() }.ok_or(VrsError::NotReady)?;
    result.as_ref().map_err(Clone::clone)
}

#[cfg(any(target_os = "linux", target_os = "macos"))]
fn c_path(path: &Path) -> Result<CString, VrsError> {
    use std::os::unix::ffi::OsStrExt;
    CString::new(path.as_os_str().as_bytes())
        .map_err(|_| VrsError::Unavailable("path contains a NUL byte".to_string()))
}

/// Inserts one rollout line written at byte `off` of `path`.
///
/// The insert is a union on the key `(path, off)`, so inserting the same line twice is harmless.
/// An optional trailing newline is removed to match the C API's line contract.
#[cfg(any(target_os = "linux", target_os = "macos"))]
pub fn insert(path: &Path, off: u64, line: &[u8]) -> Result<(), VrsError> {
    let handle = handle()?;
    let path = c_path(path)?;
    let line = line.strip_suffix(b"\n").unwrap_or(line);
    // SAFETY: the handle is live for the process lifetime; `line` is valid for `line.len()` bytes.
    let rc = unsafe {
        ffi::vrs_insert(
            handle.raw,
            path.as_ptr(),
            off,
            line.as_ptr().cast::<c_char>(),
            line.len(),
        )
    };
    match rc {
        0 => Ok(()),
        1 => Err(VrsError::NotReady),
        other => Err(VrsError::Failed(other)),
    }
}

#[cfg(not(any(target_os = "linux", target_os = "macos")))]
pub fn insert(_path: &Path, _off: u64, _line: &[u8]) -> Result<(), VrsError> {
    handle().map(|_| ())
}

/// Releases the library's in-memory copy after the line at `off` has been written and flushed.
///
/// This acknowledges persistence; it does not wait for a writer or assembly operation.
#[cfg(any(target_os = "linux", target_os = "macos"))]
pub fn written(path: &Path, off: u64) -> Result<(), VrsError> {
    let handle = handle()?;
    let path = c_path(path)?;
    // SAFETY: the handle lives for the process lifetime and the path outlives this call.
    let rc = unsafe { ffi::vrs_written(handle.raw, path.as_ptr(), off) };
    match rc {
        // The watcher may have read the persisted line first, or a retry may acknowledge
        // an already released copy. Both mean there is nothing left to release (§5.6).
        0 | -3 => Ok(()),
        1 => Err(VrsError::NotReady),
        other => Err(VrsError::Failed(other)),
    }
}

#[cfg(not(any(target_os = "linux", target_os = "macos")))]
pub fn written(_path: &Path, _off: u64) -> Result<(), VrsError> {
    handle().map(|_| ())
}

/// Waits until the store can answer `path` exactly (restored, and the file's lineage set up).
///
/// Returns `Ok(true)` when it can, `Ok(false)` when `timeout_ms` passed first (call again),
/// and an error when the store failed. The caller sleeps on the library's progress word; no
/// other call is held.
#[cfg(any(target_os = "linux", target_os = "macos"))]
pub fn wait(path: &Path, timeout_ms: u64) -> Result<bool, VrsError> {
    let handle = handle()?;
    let path = c_path(path)?;
    // SAFETY: the handle lives for the process lifetime and the path outlives this call.
    let rc = unsafe { ffi::vrs_wait(handle.raw, path.as_ptr(), timeout_ms) };
    match rc {
        0 => Ok(true),
        1 => Ok(false),
        other => Err(VrsError::Failed(other)),
    }
}

#[cfg(not(any(target_os = "linux", target_os = "macos")))]
pub fn wait(_path: &Path, _timeout_ms: u64) -> Result<bool, VrsError> {
    handle().map(|_| true)
}

/// Assembles a diagnostic snapshot using the store's default input budget.
pub fn assemble(path: &Path) -> Result<Assembled, VrsError> {
    assemble_with_budget(path, None)
}

/// Assembles with the current request's input allowance, without changing shared store options.
/// A zero allowance is an overflow, never a request to use the default budget.
#[cfg(any(target_os = "linux", target_os = "macos"))]
pub fn assemble_with_budget(path: &Path, budget: Option<u64>) -> Result<Assembled, VrsError> {
    if budget == Some(0) {
        return Err(VrsError::OverWindow);
    }
    let handle = handle()?;
    let path = c_path(path)?;
    let mut json: *mut c_char = std::ptr::null_mut();
    let mut len: usize = 0;
    // SAFETY: the handle is live for the process lifetime; the out pointers are valid.
    let rc = unsafe {
        match budget {
            Some(budget) => {
                ffi::vrs_assemble_b(handle.raw, path.as_ptr(), budget, &mut json, &mut len)
            }
            None => ffi::vrs_assemble(handle.raw, path.as_ptr(), &mut json, &mut len),
        }
    };
    // The library may return a JSON body (an error message) with a non-zero code too.
    let body = if json.is_null() {
        None
    } else {
        // SAFETY: the library returns `len` readable bytes at `json`.
        let bytes = unsafe { std::slice::from_raw_parts(json.cast::<u8>(), len) };
        let parsed = if rc == 0 {
            Some(parse_reply(bytes))
        } else {
            None
        };
        // SAFETY: `json` was allocated by the library and is not used after this point.
        unsafe { ffi::vrs_free(json) };
        parsed
    };
    match rc {
        0 => body.unwrap_or_else(|| {
            Err(VrsError::Unavailable(
                "vrs_assemble returned no JSON".to_string(),
            ))
        }),
        1 => Err(VrsError::NotReady),
        2 => Err(VrsError::OverWindow),
        other => Err(VrsError::Failed(other)),
    }
}

#[cfg(not(any(target_os = "linux", target_os = "macos")))]
pub fn assemble_with_budget(_path: &Path, budget: Option<u64>) -> Result<Assembled, VrsError> {
    if budget == Some(0) {
        return Err(VrsError::OverWindow);
    }
    handle().map(|_| Assembled::default())
}

fn parse_reply(bytes: &[u8]) -> Result<Assembled, VrsError> {
    let value: serde_json::Value = serde_json::from_slice(bytes)
        .map_err(|err| VrsError::Unavailable(format!("invalid VRS reply: {err}")))?;
    if value.get("ok").and_then(serde_json::Value::as_bool) == Some(false) {
        return Err(VrsError::Unavailable(format!(
            "assembler error: {}",
            value
                .get("error")
                .map(ToString::to_string)
                .unwrap_or_default()
        )));
    }
    let items = value
        .get("items")
        .and_then(serde_json::Value::as_array)
        .cloned()
        .ok_or_else(|| VrsError::Unavailable("VRS reply has no items".to_string()))?;
    Ok(Assembled {
        items,
        tokens: value
            .get("tokens")
            .and_then(serde_json::Value::as_u64)
            .unwrap_or(0),
        micros: value
            .get("us")
            .and_then(serde_json::Value::as_u64)
            .unwrap_or(0),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn requests_before_startup_return_not_ready_without_opening() {
        let path = Path::new("not-created-before-vrs-startup.jsonl");
        assert!(matches!(insert(path, 0, b"{}\n"), Err(VrsError::NotReady)));
        assert!(matches!(written(path, 0), Err(VrsError::NotReady)));
        assert!(matches!(assemble(path), Err(VrsError::NotReady)));
        assert!(matches!(
            assemble_with_budget(path, Some(512)),
            Err(VrsError::NotReady)
        ));
        assert!(matches!(
            assemble_with_budget(path, Some(0)),
            Err(VrsError::OverWindow)
        ));
        assert!(!OPEN_STARTED.load(Ordering::Acquire));
        assert!(HANDLE.load(Ordering::Acquire).is_null());
    }

    #[test]
    fn parses_reply() {
        let reply = br#"{"ok":true,"items":[{"type":"message"}],"tokens":7,"us":12}"#;
        let assembled = parse_reply(reply).expect("reply parses");
        assert_eq!(assembled.items.len(), 1);
        assert_eq!(assembled.tokens, 7);
        assert_eq!(assembled.micros, 12);
    }

    #[test]
    fn rejects_reply_without_items() {
        assert!(parse_reply(br#"{"ok":true}"#).is_err());
        assert!(parse_reply(br#"{"ok":false,"error":"x"}"#).is_err());
    }
}
