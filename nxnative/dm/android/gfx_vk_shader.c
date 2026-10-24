// Android port, Vulkan backend: the game's shaders (see gfx_vk.h).
// The bundle (dm/android/tools/shader_vk.py) is mapped read-only: entries sorted by key, each the SPIR-V of one Switch shader and its binary reflection.
// The translator numbers every stage's bindings from 0 in set 0; at module creation each stage's bindings move to a set of its own (vertex 0, fragment 1,
// geometry 2, tessellation 3 / 4; compute 0) by rewriting the DescriptorSet decorations, so a program's stages never collide.
#include "gfx_vk.h"
#include "nvn_hmap.h"
#include <fcntl.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

typedef struct __attribute__((packed)) { uint64_t key; uint32_t stage, spv_off, spv_len, refl_off, refl_len, pad; } bent;
static const uint8_t *g_bundle; static uint32_t g_nent; static const bent *g_ent;
void vk_shaders_open(const char *path) {
    int fd = open(path, O_RDONLY | O_CLOEXEC); struct stat st;
    if (fd < 0 || fstat(fd, &st)) { VKLOG("[RED] no shader bundle at %s: nothing will be drawn", path); if (fd >= 0) close(fd); return; }
    g_bundle = mmap(NULL, (size_t)st.st_size, PROT_READ, MAP_SHARED, fd, 0); close(fd);
    if (g_bundle == MAP_FAILED || memcmp(g_bundle, "DMSV", 4)) { VKLOG("[RED] %s is not a shader bundle", path); g_bundle = NULL; return; }
    memcpy(&g_nent, g_bundle + 8, 4); g_ent = (const bent *)(g_bundle + 12);
    VKLOG("shader bundle %s: %u shaders, %.1f MB", path, g_nent, st.st_size / 1048576.0);
}
static void bundle_open_once(void) {
    const char *p = getenv("DM_VK_SHADERS"); char buf[1024];
    if (!p) { const char *r = getenv("DM_ROOT"); snprintf(buf, sizeof buf, "%s/shaders.dmsv", r ? r : "."); p = buf; }
    vk_shaders_open(p);
}
// once, and every caller waits until it is open: the replay and the prewarm threads both look shaders up at start, and a lookup that ran before the bundle
// was open cached its shader as missing for good (every draw skipped as "no program" in some runs)
static void bundle_auto(void) { static pthread_once_t once = PTHREAD_ONCE_INIT; pthread_once(&once, bundle_open_once); }
static const bent *find(uint64_t key) {
    uint32_t lo = 0, hi = g_nent;
    while (lo < hi) { uint32_t m = (lo + hi) / 2; uint64_t k; memcpy(&k, &g_ent[m].key, 8); if (k < key) lo = m + 1; else hi = m; }
    if (lo < g_nent) { uint64_t k; memcpy(&k, &g_ent[lo].key, 8); if (k == key) return &g_ent[lo]; }
    return NULL;
}
int vk_shader_stage(uint64_t key) { bundle_auto(); const bent *e = g_bundle ? find(key) : NULL; return e ? (int)e->stage : -1; }   // the NVN stage the bundle has this shader as
static VkShaderStageFlags stage_flag(int st) {
    switch (st) { case 0: return VK_SHADER_STAGE_VERTEX_BIT; case 1: return VK_SHADER_STAGE_FRAGMENT_BIT; case 2: return VK_SHADER_STAGE_GEOMETRY_BIT;
                  case 3: return VK_SHADER_STAGE_TESSELLATION_CONTROL_BIT; case 4: return VK_SHADER_STAGE_TESSELLATION_EVALUATION_BIT; default: return VK_SHADER_STAGE_COMPUTE_BIT; }
}
static int set_of(int st) { return st == 5 ? 0 : st == 0 ? 0 : st == 1 ? 1 : st == 2 ? 2 : st; }
static VkDescriptorType desc_type(int d) {
    switch (d) { case RD_UBO: return VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER; case RD_SSBO: return VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; case RD_SAMPLED: return VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
                 case RD_STORAGE: return VK_DESCRIPTOR_TYPE_STORAGE_IMAGE; case RD_TBUF: return VK_DESCRIPTOR_TYPE_UNIFORM_TEXEL_BUFFER; case RD_STORAGE_TBUF: return VK_DESCRIPTOR_TYPE_STORAGE_TEXEL_BUFFER;
                 case RD_IMAGE: return VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE; default: return VK_DESCRIPTOR_TYPE_SAMPLER; }
}
static nvn_hmap g_shaders = {.klen = 16};   // {key, stage} → vkshader_t*
static pthread_mutex_t g_sh_mu = PTHREAD_MUTEX_INITIALIZER;
vkshader_t *vk_shader(uint64_t key, int stage) {
    bundle_auto();
    struct { uint64_t key; uint64_t stage; } hk = {key, (uint64_t)stage};
    pthread_mutex_lock(&g_sh_mu);
    vkshader_t *s = nvn_hm_get(&g_shaders, &hk);
    if (s) { pthread_mutex_unlock(&g_sh_mu); return s == (void *)1 ? NULL : s; }
    const bent *e = g_bundle ? find(key) : NULL;
    if (!e) { nvn_hm_put(&g_shaders, &hk, (void *)1); pthread_mutex_unlock(&g_sh_mu);
              static int n; if (n++ < 16) VKLOG("[RED] shader %016llx (stage %d) is not in the bundle", (unsigned long long)key, stage); return NULL; }
    s = calloc(1, sizeof *s); s->key = key; s->stage = stage; s->set = set_of(stage);
    // reflection
    const uint8_t *r = g_bundle + e->refl_off; uint32_t hdr[5]; memcpy(hdr, r, 20);
    s->nbind = (int)hdr[0]; s->c1_len = hdr[1]; memcpy(s->local, hdr + 2, 12);
    s->b = (const dmsv_bind *)(r + 20); s->c1 = r + 20 + 20 * s->nbind;
    // SPIR-V with the stage's set
    uint32_t nw = e->spv_len / 4; uint32_t *w = malloc(e->spv_len); memcpy(w, g_bundle + e->spv_off, e->spv_len);
    int f64_used = 0;
    for (uint32_t i = 5; i < nw;) { uint32_t n = w[i] >> 16, op = w[i] & 0xffff; if (!n) break; if (op == 71 && n >= 4 && w[i + 2] == 34) w[i + 3] = (uint32_t)s->set;   // OpDecorate DescriptorSet
        if (op == 22 && n == 3 && w[i + 2] == 64) f64_used = 1;   // OpTypeFloat 64
        i += n; }
    // the translator declares Float64 in every shader; the device has shaderFloat64 off (Adreno has none), which makes the declaration invalid: when the
    // shader has no 64-bit float type it becomes a second Shader declaration
    if (!f64_used) for (uint32_t i = 5; i < nw;) { uint32_t n = w[i] >> 16, op = w[i] & 0xffff; if (!n || op != 17) break; if (n == 2 && w[i + 1] == 10) w[i + 1] = 1; i += n; }
    // the translator declares fragment shader interlock in every pixel shader; the device has no VK_EXT_fragment_shader_interlock: when the shader uses no
    // interlock instruction, its OpCapability and OpExtension are dropped
    { int used = 0; for (uint32_t i = 5; i < nw;) { uint32_t n = w[i] >> 16, op = w[i] & 0xffff; if (!n) break; if (op == 5364 || op == 5365) used = 1; i += n; }   // OpBegin/EndInvocationInterlockEXT
      if (!used) { uint32_t o = 5;
        for (uint32_t i = 5; i < nw;) { uint32_t n = w[i] >> 16, op = w[i] & 0xffff; if (!n || i + n > nw) { while (i < nw) w[o++] = w[i++]; break; }
            int drop = (op == 17 && n == 2 && (w[i + 1] == 5378 || w[i + 1] == 5363 || w[i + 1] == 5372)) ||   // FragmentShader{Pixel,Sample,ShadingRate}InterlockEXT
                       (op == 10 && !memcmp(&w[i + 1], "SPV_EXT_fragment_shader_interlock", 33));
            if (drop) i += n; else for (uint32_t k = 0; k < n; k++) w[o++] = w[i++]; }
        nw = o; } }
    VkShaderModuleCreateInfo ci = {VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, NULL, 0, (size_t)nw * 4, w};
    VkResult vr = vkCreateShaderModule(V.dev, &ci, NULL, &s->mod); free(w);
    if (vr) { VKLOG("[RED] shader %016llx: vkCreateShaderModule %d", (unsigned long long)key, vr); free(s); nvn_hm_put(&g_shaders, &hk, (void *)1); pthread_mutex_unlock(&g_sh_mu); return NULL; }
    // descriptor set layout: one entry per binding
    // The game's constant buffers and the driver segment are dynamic uniform buffers: their offset is given when the set is bound, so a set matches any draw's
    // with the same buffers (Unity updates a constant buffer before nearly every draw, and each update is a shadow at a new offset: NEO made a new set for
    // 94% of its draws, 5 ms a frame). Up to half the device's limit per stage, as the vertex and fragment sets share a pipeline layout. DM_VK_DYN_UBO=0: none.
    static int dyn_on = -1; if (dyn_on < 0) { const char *e = getenv("DM_VK_DYN_UBO"); dyn_on = !(e && !atoi(e)); }
    uint32_t dynmax = dyn_on ? V.props.limits.maxDescriptorSetUniformBuffersDynamic / 2 : 0;
    VkDescriptorSetLayoutBinding lb[96]; uint32_t nl = 0;
    for (int i = 0; i < s->nbind && nl < 96; i++) {
        const dmsv_bind *b = &s->b[i];
        int dyn = b->desc == RD_UBO && (b->kind == RK_CBUF || b->kind == RK_DRV) && b->count == 1 && (uint32_t)s->ndyn < dynmax;
        s->dyn[i] = (uint8_t)dyn; s->ndyn += dyn;
        lb[nl++] = (VkDescriptorSetLayoutBinding){b->binding, dyn ? VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC : desc_type(b->desc), b->count ? b->count : 32, stage_flag(stage), NULL};
    }
    VkDescriptorSetLayoutCreateInfo li = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, NULL, 0, nl, lb};
    VKCHK(vkCreateDescriptorSetLayout(V.dev, &li, NULL, &s->dsl));
    void vk_dsl_register(VkDescriptorSetLayout l, const VkDescriptorSetLayoutBinding *b, uint32_t n); vk_dsl_register(s->dsl, lb, nl);
    nvn_hm_put(&g_shaders, &hk, s);
    pthread_mutex_unlock(&g_sh_mu);
    return s;
}
// static buffers: Ryujinx's support buffer (render scales 1.0, nothing else set: as nvn_mtl.m support_buf) and 64 KB of zeros (unbound uniform slots, driver segments nobody reads)
static VkBuffer static_buf(int which) {
    static VkBuffer b[2]; static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
    pthread_mutex_lock(&mu);
    if (!b[which]) {
        VkBufferCreateInfo bi = {VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, NULL, 0, 65536, VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT | VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_VERTEX_BUFFER_BIT, VK_SHARING_MODE_EXCLUSIVE};
        VKCHK(vkCreateBuffer(V.dev, &bi, NULL, &b[which])); VkMemoryRequirements req; vkGetBufferMemoryRequirements(V.dev, b[which], &req);
        VkMemoryAllocateInfo ai = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, NULL, req.size, vk_mem_type(req.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT, 0)};
        VkDeviceMemory m; VKCHK(vkAllocateMemory(V.dev, &ai, NULL, &m)); VKCHK(vkBindBufferMemory(V.dev, b[which], m, 0));
        void *p; VKCHK(vkMapMemory(V.dev, m, 0, VK_WHOLE_SIZE, 0, &p)); memset(p, 0, 65536);
        if (which == 0) for (int i = 0; i < 73; i++) *(float *)((uint8_t *)p + 192 + 16 * i) = 1.0f;   // render_scale[i].x (SupportBuffer.cs layout)
    }
    pthread_mutex_unlock(&mu);
    return b[which];
}
VkBuffer vk_support_buffer(void) { return static_buf(0); }
VkBuffer vk_zero_buffer(void) { return static_buf(1); }
// a shader's c1 constants: copied once into a buffer of their own (the bundle bytes do not change)
void vk_shader_c1(vkshader_t *s, VkBuffer *buf, VkDeviceSize *off, VkDeviceSize *len) {
    if (!s->c1_len) { *buf = vk_zero_buffer(); *off = 0; *len = 65536; return; }
    if (!s->c1_buf) {
        VkBufferCreateInfo bi = {VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, NULL, 0, (s->c1_len + 255) & ~255u, VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT, VK_SHARING_MODE_EXCLUSIVE};
        VKCHK(vkCreateBuffer(V.dev, &bi, NULL, &s->c1_buf)); VkMemoryRequirements req; vkGetBufferMemoryRequirements(V.dev, s->c1_buf, &req);
        VkMemoryAllocateInfo ai = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, NULL, req.size, vk_mem_type(req.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT, 0)};
        VkDeviceMemory m; VKCHK(vkAllocateMemory(V.dev, &ai, NULL, &m)); VKCHK(vkBindBufferMemory(V.dev, s->c1_buf, m, 0));
        void *p; VKCHK(vkMapMemory(V.dev, m, 0, VK_WHOLE_SIZE, 0, &p)); memset(p, 0, bi.size); memcpy(p, s->c1, s->c1_len);
    }
    *buf = s->c1_buf; *off = 0; *len = (s->c1_len + 255) & ~255u;
}
// pipeline layouts by the set layouts of their stages (an empty layout fills the sets of absent stages)
VkPipelineLayout vk_pipeline_layout(VkDescriptorSetLayout sets[5], int nsets) {
    static VkDescriptorSetLayout empty; static nvn_hmap cache = {.klen = 5 * sizeof(VkDescriptorSetLayout)}; static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
    pthread_mutex_lock(&mu);
    if (!empty) { VkDescriptorSetLayoutCreateInfo li = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO}; VKCHK(vkCreateDescriptorSetLayout(V.dev, &li, NULL, &empty)); }
    VkDescriptorSetLayout k[5]; for (int i = 0; i < 5; i++) { k[i] = i < nsets && sets[i] ? sets[i] : (i < nsets ? empty : VK_NULL_HANDLE); if (i < nsets) sets[i] = k[i]; }   // absent stages get the empty layout (the caller allocates their sets from it)
    VkPipelineLayout pl = nvn_hm_get(&cache, k);
    if (!pl) {
        VkPipelineLayoutCreateInfo ci = {VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, NULL, 0, (uint32_t)nsets, k};
        VKCHK(vkCreatePipelineLayout(V.dev, &ci, NULL, &pl)); nvn_hm_put(&cache, k, pl);
    }
    pthread_mutex_unlock(&mu);
    return pl;
}
