# One-off source edit for the Android port: the host's guest-thread slots (K18 / KTLS / KTLR / KGATE) go through dm_tsd_get / dm_tsd_set, which are
# Darwin TSD on Apple and a TLS_SLOT_APP block on Android (patch_nso.py DM_TARGET=android reads them as tpidr_el0[2] + key page offset).
import sys
root = sys.argv[1]

def edit(path, pairs):
    p = f'{root}/{path}'; s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        if old not in s and new in s: continue
        assert old in s, f'{path}: {old[:70]!r} not found'
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8', newline='\n').write(s)

edit('host/dm.h', [(
'extern pthread_key_t g_key18, g_keytls, g_keytlr, g_keygate;',
'''extern pthread_key_t g_key18, g_keytls, g_keytlr, g_keygate;
// The guest thread slots the rewritten code reads (patch_nso.py emit_tp): Darwin TSD keys on Apple; on Android the keys are indices into a per-thread
// block whose address bionic's TLS_SLOT_APP holds (tpidr_el0[2]), see loader.c
#if defined(__APPLE__)
#define dm_tsd_set(k, v) pthread_setspecific((k), (v))
#define dm_tsd_get(k) pthread_getspecific(k)
#else
void dm_tsd_set(pthread_key_t k, const void *v);
void *dm_tsd_get(pthread_key_t k);
#endif''')])

edit('host/thread.c', [
    ('pthread_setspecific(g_keygate, (void *)dm_gate);', 'dm_tsd_set(g_keygate, (void *)dm_gate);'),
    ('pthread_setspecific(g_key18, 0);', 'dm_tsd_set(g_key18, 0);'),
    ('pthread_setspecific(g_keytls, own[0]); pthread_setspecific(g_keytlr, tlr);', 'dm_tsd_set(g_keytls, own[0]); dm_tsd_set(g_keytlr, tlr);'),
])
edit('host/hle_thread.c', [
    ('t->ctx_x[18] = (uint64_t)(uintptr_t)pthread_getspecific(g_key18);', 't->ctx_x[18] = (uint64_t)(uintptr_t)dm_tsd_get(g_key18);'),
    ('t->svc_x18 = (uint64_t)(uintptr_t)pthread_getspecific(g_key18);', 't->svc_x18 = (uint64_t)(uintptr_t)dm_tsd_get(g_key18);'),
])
edit('host/loader.c', [(
'''static void create_keys(void) {
    if (pthread_key_create(&g_key18, NULL) || pthread_key_create(&g_keytls, NULL) ||
        pthread_key_create(&g_keytlr, NULL) || pthread_key_create(&g_keygate, NULL)) die("cannot create the host key");
    LOG("key numbers K18=%lu KTLS=%lu KTLR=%lu KGATE=%lu", g_key18, g_keytls, g_keytlr, g_keygate);
}

// K slot check: the pthread TSD layout is fixed, slot = tpidrro_el0 + 8*key
static void tsd_check(void) {
    pthread_setspecific(g_key18, (void *)0x1234);
    uint64_t base; __asm__ volatile("mrs %0, tpidrro_el0" : "=r"(base));
    uint64_t off = *(uint64_t *)(g_mod[0].base + g_mod[0].key_page_off + g_mod[0].key_idx[KEY_K18] * 8);
    if (((uint64_t *)(base & ~7ull))[off / 8] != 0x1234) die("TSD layout mismatch");
    pthread_setspecific(g_key18, 0);
}''',
'''#if defined(__APPLE__)
static void create_keys(void) {
    if (pthread_key_create(&g_key18, NULL) || pthread_key_create(&g_keytls, NULL) ||
        pthread_key_create(&g_keytlr, NULL) || pthread_key_create(&g_keygate, NULL)) die("cannot create the host key");
    LOG("key numbers K18=%lu KTLS=%lu KTLR=%lu KGATE=%lu", g_key18, g_keytls, g_keytlr, g_keygate);
}

// K slot check: the pthread TSD layout is fixed, slot = tpidrro_el0 + 8*key
static void tsd_check(void) {
    pthread_setspecific(g_key18, (void *)0x1234);
    uint64_t base; __asm__ volatile("mrs %0, tpidrro_el0" : "=r"(base));
    uint64_t off = *(uint64_t *)(g_mod[0].base + g_mod[0].key_page_off + g_mod[0].key_idx[KEY_K18] * 8);
    if (((uint64_t *)(base & ~7ull))[off / 8] != 0x1234) die("TSD layout mismatch");
    pthread_setspecific(g_key18, 0);
}
#else
// Android: bionic owns tpidr_el0 (its TLS) and 64-bit tasks read 0 from tpidrro_el0. Each thread that runs guest code gets a block of slots whose address
// sits in bionic's TLS_SLOT_APP (tpidr_el0[2], reserved for app use); the "keys" are indices 1..4 into it (0 stays unused: the loader takes a 0 key page
// entry as a missing key), and the rewriter (DM_TARGET=android) reads a slot as tpidr_el0[2] + key page entry. The block is freed when the thread exits.
#define TLS_SLOT_APP 2
#define TSD_SLOTS 8
static pthread_key_t g_tsd_free;
static uint64_t **tp_now(void) { uint64_t **tp; __asm__ volatile("mrs %0, tpidr_el0" : "=r"(tp)); return tp; }
static void tsd_block_free(void *b) { uint64_t **tp = tp_now(); if (tp[TLS_SLOT_APP] == b) tp[TLS_SLOT_APP] = NULL; free(b); }
static uint64_t *tsd_block(void) {
    uint64_t **tp = tp_now(), *b = tp[TLS_SLOT_APP];
    if (!b) {
        if (!(b = calloc(TSD_SLOTS, sizeof *b))) die("guest thread slot block allocation failed");
        tp[TLS_SLOT_APP] = b; pthread_setspecific(g_tsd_free, b);
    }
    return b;
}
void dm_tsd_set(pthread_key_t k, const void *v) { tsd_block()[k] = (uint64_t)(uintptr_t)v; }
void *dm_tsd_get(pthread_key_t k) { return (void *)(uintptr_t)tsd_block()[k]; }
static void create_keys(void) {
    if (pthread_key_create(&g_tsd_free, tsd_block_free)) die("cannot create the slot block key");
    uint64_t **tp = tp_now();
    if (tp[TLS_SLOT_APP]) die("bionic's TLS_SLOT_APP is already in use on this thread (%p): the guest thread slots cannot live there", (void *)tp[TLS_SLOT_APP]);
    g_key18 = 1; g_keytls = 2; g_keytlr = 3; g_keygate = 4;
    LOG("guest thread slots in TLS_SLOT_APP blocks: K18=%lu KTLS=%lu KTLR=%lu KGATE=%lu", (unsigned long)g_key18, (unsigned long)g_keytls, (unsigned long)g_keytlr, (unsigned long)g_keygate);
}
// K slot check: the slot the rewritten code reads (tpidr_el0[2] + the key page entry) is the one dm_tsd_set wrote
static void tsd_check(void) {
    dm_tsd_set(g_key18, (void *)0x1234);
    uint64_t off = *(uint64_t *)(g_mod[0].base + g_mod[0].key_page_off + g_mod[0].key_idx[KEY_K18] * 8);
    if (*(uint64_t *)((uint8_t *)tp_now()[TLS_SLOT_APP] + off) != 0x1234) die("guest thread slot layout mismatch");
    dm_tsd_set(g_key18, 0);
}
#endif''')])
print('ok')
