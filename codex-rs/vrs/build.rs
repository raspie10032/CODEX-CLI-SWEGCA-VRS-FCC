//! Links the static C++ assembly library `libvrs.a`.
//!
//! The directory holding `libvrs.a` is `$VRS_LIB_DIR`, default the prebuilt library shipped in
//! this repository (`vrs-lib7/prebuilt/x86_64-linux-gnu`, see the README there).

fn main() {
    println!("cargo:rerun-if-env-changed=VRS_LIB_DIR");
    let os = std::env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    if os != "linux" && os != "macos" {
        return;
    }
    let dir = std::env::var("VRS_LIB_DIR").unwrap_or_else(|_| {
        let manifest = std::env::var("CARGO_MANIFEST_DIR").unwrap_or_default();
        let target = std::env::var("TARGET").unwrap_or_default();
        let platform = if target == "x86_64-unknown-linux-gnu" {
            "x86_64-linux-gnu"
        } else {
            &target
        };
        format!("{manifest}/../../vrs-lib7/prebuilt/{platform}")
    });
    println!("cargo:rerun-if-changed={dir}/libvrs.a");
    println!("cargo:rustc-link-search=native={dir}");
    println!("cargo:rustc-link-lib=static=vrs");
    if os == "macos" {
        println!("cargo:rustc-link-lib=dylib=c++");
        println!("cargo:rustc-link-lib=framework=CoreServices");
        println!("cargo:rustc-link-lib=framework=CoreFoundation");
    } else {
        println!("cargo:rustc-link-lib=dylib=stdc++");
    }
    println!("cargo:rustc-link-lib=dylib=pthread");
}
