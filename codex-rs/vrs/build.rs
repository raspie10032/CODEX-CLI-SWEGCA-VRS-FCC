//! Links the static C++ assembly library `libvrs.a`.
//!
//! The directory holding `libvrs.a` is `$VRS_LIB_DIR`, default `$HOME/vrsint`.

fn main() {
    println!("cargo:rerun-if-env-changed=VRS_LIB_DIR");
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("linux") {
        return;
    }
    let dir = std::env::var("VRS_LIB_DIR").unwrap_or_else(|_| {
        let home = std::env::var("HOME").unwrap_or_default();
        format!("{home}/vrsint")
    });
    println!("cargo:rerun-if-changed={dir}/libvrs.a");
    println!("cargo:rustc-link-search=native={dir}");
    println!("cargo:rustc-link-lib=static=vrs");
    println!("cargo:rustc-link-lib=dylib=stdc++");
    println!("cargo:rustc-link-lib=dylib=pthread");
}
