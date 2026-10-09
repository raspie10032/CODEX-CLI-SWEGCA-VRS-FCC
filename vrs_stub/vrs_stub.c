/* Link stub for libvrs (doc P-5). Every call reports "not ready" (1) until the real
 * libvrs.a built in $WORK/vrsint replaces it. Build:
 *   cc -O2 -fPIC -c vrs_stub.c -o vrs_stub.o && ar rcs libvrs.a vrs_stub.o
 */
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

typedef struct vrs_h { int unused; } vrs_h;
typedef struct {
    const char* sessions_dir;
    const char* index_dir;
    unsigned workers;
    const unsigned* cpus;
    unsigned ncpus;
    int segwin;
} vrs_opts;

int vrs_open(const vrs_opts* opts, vrs_h** out) {
    (void)opts;
    static vrs_h h;
    *out = &h;
    return 0;
}

int vrs_ready(vrs_h* h) {
    (void)h;
    return 0; /* restoring */
}

int vrs_insert(vrs_h* h, const char* path, uint64_t off, const char* line, size_t len) {
    (void)h; (void)path; (void)off; (void)line; (void)len;
    return 0;
}

int vrs_assemble(vrs_h* h, const char* path, char** json, size_t* len) {
    (void)h; (void)path;
    *json = NULL;
    *len = 0;
    return 1; /* not ready */
}

void vrs_free(char* p) { free(p); }

void vrs_close(vrs_h* h) { (void)h; }
