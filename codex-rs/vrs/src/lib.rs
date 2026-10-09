//! In-process VRS context assembly (`libvrs`).
//!
//! One process-wide handle is opened lazily on first use. Rollout lines are inserted where they
//! are written (`insert`), and the model input of a thread is assembled from the store
//! (`assemble`). There is no fallback: every failure is returned to the caller.

use std::ffi::CString;
use std::ffi::c_char;
use std::ffi::c_int;
use std::ffi::c_uint;
use std::fmt;
use std::path::Path;
use std::sync::OnceLock;

/// Why the VRS store could not serve a call.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VrsError {
    /// The store is still restoring (`vrs_assemble` returned 1).
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

#[cfg(target_os = "linux")]
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
        pub fn vrs_assemble(
            h: *mut VrsH,
            path: *const c_char,
            json: *mut *mut c_char,
            len: *mut usize,
        ) -> c_int;
        pub fn vrs_free(p: *mut c_char);
    }
}

struct Handle {
    #[cfg(target_os = "linux")]
    raw: *mut ffi::VrsH,
}

// The library keeps its state in CAS/atomic tables and is safe to call from any thread.
unsafe impl Send for Handle {}
unsafe impl Sync for Handle {}

const WORKERS: c_uint = 12;
const SEGWIN: c_int = 1;

/// The virtual rollout path under which the lines of a thread without a rollout file are kept.
///
/// Nothing is written at this path; it only names the thread in the store.
pub fn ephemeral_path(thread_id: &str) -> Result<std::path::PathBuf, VrsError> {
    let home = codex_utils_home_dir::find_codex_home()
        .map_err(|err| VrsError::Unavailable(err.to_string()))?;
    Ok(home
        .as_path()
        .join("sessions")
        .join("ephemeral")
        .join(format!("{thread_id}.jsonl")))
}

static HANDLE: OnceLock<Result<Handle, String>> = OnceLock::new();

#[cfg(target_os = "linux")]
fn open_handle() -> Result<Handle, String> {
    let home = codex_utils_home_dir::find_codex_home().map_err(|err| err.to_string())?;
    let sessions = home.as_path().join("sessions");
    let index = home.as_path().join("vrs").join("idx");
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

#[cfg(not(target_os = "linux"))]
fn open_handle() -> Result<Handle, String> {
    Err("libvrs is only available on Linux".to_string())
}

fn handle() -> Result<&'static Handle, VrsError> {
    HANDLE
        .get_or_init(open_handle)
        .as_ref()
        .map_err(|reason| VrsError::Unavailable(reason.clone()))
}

#[cfg(target_os = "linux")]
fn c_path(path: &Path) -> Result<CString, VrsError> {
    use std::os::unix::ffi::OsStrExt;
    CString::new(path.as_os_str().as_bytes())
        .map_err(|_| VrsError::Unavailable("path contains a NUL byte".to_string()))
}

/// Inserts one rollout line (including its trailing newline) written at byte `off` of `path`.
///
/// The insert is a union on the key `(path, off)`, so inserting the same line twice is harmless.
#[cfg(target_os = "linux")]
pub fn insert(path: &Path, off: u64, line: &[u8]) -> Result<(), VrsError> {
    let handle = handle()?;
    let path = c_path(path)?;
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
    if rc == 0 {
        Ok(())
    } else {
        Err(VrsError::Failed(rc))
    }
}

#[cfg(not(target_os = "linux"))]
pub fn insert(_path: &Path, _off: u64, _line: &[u8]) -> Result<(), VrsError> {
    handle().map(|_| ())
}

/// Assembles the model input of the thread whose rollout is `path`.
#[cfg(target_os = "linux")]
pub fn assemble(path: &Path) -> Result<Assembled, VrsError> {
    let handle = handle()?;
    let path = c_path(path)?;
    let mut json: *mut c_char = std::ptr::null_mut();
    let mut len: usize = 0;
    // SAFETY: the handle is live for the process lifetime; the out pointers are valid.
    let rc = unsafe { ffi::vrs_assemble(handle.raw, path.as_ptr(), &mut json, &mut len) };
    // The library may return a JSON body (an error message) with a non-zero code too.
    let body = if json.is_null() {
        None
    } else {
        // SAFETY: the library returns `len` readable bytes at `json`.
        let bytes = unsafe { std::slice::from_raw_parts(json.cast::<u8>(), len) };
        let parsed = if rc == 0 { Some(parse_reply(bytes)) } else { None };
        // SAFETY: `json` was allocated by the library and is not used after this point.
        unsafe { ffi::vrs_free(json) };
        parsed
    };
    match rc {
        0 => body.unwrap_or_else(|| {
            Err(VrsError::Unavailable("vrs_assemble returned no JSON".to_string()))
        }),
        1 => Err(VrsError::NotReady),
        2 => Err(VrsError::OverWindow),
        other => Err(VrsError::Failed(other)),
    }
}

#[cfg(not(target_os = "linux"))]
pub fn assemble(_path: &Path) -> Result<Assembled, VrsError> {
    handle().map(|_| Assembled::default())
}

fn parse_reply(bytes: &[u8]) -> Result<Assembled, VrsError> {
    let value: serde_json::Value = serde_json::from_slice(bytes)
        .map_err(|err| VrsError::Unavailable(format!("invalid VRS reply: {err}")))?;
    if value.get("ok").and_then(serde_json::Value::as_bool) == Some(false) {
        return Err(VrsError::Unavailable(format!(
            "assembler error: {}",
            value.get("error").map(ToString::to_string).unwrap_or_default()
        )));
    }
    let items = value
        .get("items")
        .and_then(serde_json::Value::as_array)
        .cloned()
        .ok_or_else(|| VrsError::Unavailable("VRS reply has no items".to_string()))?;
    Ok(Assembled {
        items,
        tokens: value.get("tokens").and_then(serde_json::Value::as_u64).unwrap_or(0),
        micros: value.get("us").and_then(serde_json::Value::as_u64).unwrap_or(0),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

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
