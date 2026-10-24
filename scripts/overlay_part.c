// ---- the on-screen gamepad: rasterized on the CPU once per window size (half resolution), blended over each frame ----
static struct { VkImage img; VkDeviceMemory mem; VkImageView view; VkSampler samp; VkDescriptorSetLayout dsl; VkPipelineLayout layout; VkDescriptorPool pool; VkDescriptorSet set;
                VkPipeline pipe; VkFormat pfmt; uint32_t w, h; VkBuffer up; VkDeviceMemory upm; int uploaded; } g_ov;
static void ov_plot(uint8_t *px, uint32_t w, uint32_t h, int x, int y, uint8_t a, uint8_t v) {
    if (x < 0 || y < 0 || (uint32_t)x >= w || (uint32_t)y >= h) return;
    uint8_t *p = px + 4 * ((size_t)y * w + (size_t)x); if (p[3] >= a) return;
    p[0] = p[1] = p[2] = v; p[3] = a;
}
static void ov_circle(uint8_t *px, uint32_t w, uint32_t h, float cx, float cy, float r, float ring) {
    for (int y = (int)(cy - r - 2); y <= (int)(cy + r + 2); y++) for (int x = (int)(cx - r - 2); x <= (int)(cx + r + 2); x++) {
        float d = sqrtf((x - cx) * (x - cx) + (y - cy) * (y - cy));
        if (d <= r && d >= r - ring) ov_plot(px, w, h, x, y, 150, 255);   // the ring
        else if (d < r - ring) ov_plot(px, w, h, x, y, 50, 30);           // a dark, see-through inside
    }
}
static void ov_text(uint8_t *px, uint32_t w, uint32_t h, float cx, float cy, const char *s, int scale) {
    int n = (int)strlen(s), x0 = (int)(cx - n * 6 * scale / 2.0f), y0 = (int)(cy - 7 * scale / 2.0f);
    for (int i = 0; i < n; i++) {
        unsigned c = (unsigned char)s[i]; const unsigned char *g = FONT5X7[(c >= 32 && c < 127 ? c : 63) - 32];
        for (int col = 0; col < 5; col++) for (int row = 0; row < 7; row++) if (g[col] >> row & 1)
            for (int dy = 0; dy < scale; dy++) for (int dx = 0; dx < scale; dx++) ov_plot(px, w, h, x0 + i * 6 * scale + col * scale + dx, y0 + row * scale + dy, 220, 255);
    }
}
static void ov_raster(uint8_t *px, uint32_t w, uint32_t h) {
    memset(px, 0, (size_t)w * h * 4);
    float H = (float)h; int ts = h > 600 ? 3 : 2;
    for (int i = 0; i < OV_N; i++) {
        const ov_ctl *c = &OV_CTLS[i]; float cx = c->x * w, cy = c->y * h, r = c->r * H;
        if (c->kind == OV_DPAD) {
            float s = r * 0.42f;
            for (int k = 0; k < 4; k++) { float ox = k == 0 ? s * 1.2f : k == 1 ? -s * 1.2f : 0, oy = k == 2 ? s * 1.2f : k == 3 ? -s * 1.2f : 0; ov_circle(px, w, h, cx + ox, cy + oy, s * 0.75f, 2.5f); }
            continue;
        }
        ov_circle(px, w, h, cx, cy, r, c->kind == OV_BUTTON ? 2.5f : 3.0f);
        if (c->kind != OV_BUTTON) ov_circle(px, w, h, cx, cy, r * 0.42f, 2.0f);   // the stick's knob at rest
        if (c->label[0]) ov_text(px, w, h, cx, cy, c->label, ts);
    }
}
static int overlay_ready(VkCommandBuffer cb) {
    uint32_t w = g_sext.width / 2, h = g_sext.height / 2;
    if (!g_ov.dsl) {
        VkDescriptorSetLayoutBinding b = {0, VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1, VK_SHADER_STAGE_FRAGMENT_BIT, NULL};
        VkDescriptorSetLayoutCreateInfo li = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, NULL, 0, 1, &b}; VKCHK(vkCreateDescriptorSetLayout(V.dev, &li, NULL, &g_ov.dsl));
        VkPipelineLayoutCreateInfo pl = {VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, NULL, 0, 1, &g_ov.dsl}; VKCHK(vkCreatePipelineLayout(V.dev, &pl, NULL, &g_ov.layout));
        VkDescriptorPoolSize ps = {VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1}; VkDescriptorPoolCreateInfo pi = {VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO, NULL, 0, 1, 1, &ps};
        VKCHK(vkCreateDescriptorPool(V.dev, &pi, NULL, &g_ov.pool));
        VkDescriptorSetAllocateInfo ai = {VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO, NULL, g_ov.pool, 1, &g_ov.dsl}; VKCHK(vkAllocateDescriptorSets(V.dev, &ai, &g_ov.set));
        VkSamplerCreateInfo si = {VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO, NULL, 0, VK_FILTER_LINEAR, VK_FILTER_LINEAR, VK_SAMPLER_MIPMAP_MODE_NEAREST,
            VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE, VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE, VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE};
        VKCHK(vkCreateSampler(V.dev, &si, NULL, &g_ov.samp));
    }
    if (g_ov.pfmt != g_sfmt) {   // the pipeline renders into the swapchain's format
        VkShaderModule vm, fm;
        VkShaderModuleCreateInfo vc = {VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, NULL, 0, sizeof overlay_vert_spv, overlay_vert_spv}; VKCHK(vkCreateShaderModule(V.dev, &vc, NULL, &vm));
        VkShaderModuleCreateInfo fc = {VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, NULL, 0, sizeof overlay_frag_spv, overlay_frag_spv}; VKCHK(vkCreateShaderModule(V.dev, &fc, NULL, &fm));
        VkPipelineShaderStageCreateInfo ss[2] = {{VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, NULL, 0, VK_SHADER_STAGE_VERTEX_BIT, vm, "main", NULL},
                                                {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, NULL, 0, VK_SHADER_STAGE_FRAGMENT_BIT, fm, "main", NULL}};
        VkPipelineVertexInputStateCreateInfo vi = {VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
        VkPipelineInputAssemblyStateCreateInfo ia = {VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO, NULL, 0, VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, 0};
        VkPipelineViewportStateCreateInfo vs = {VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO, NULL, 0, 1, NULL, 1, NULL};
        VkPipelineRasterizationStateCreateInfo rs = {VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO, NULL, 0, 0, 0, VK_POLYGON_MODE_FILL, VK_CULL_MODE_NONE, VK_FRONT_FACE_COUNTER_CLOCKWISE, 0, 0, 0, 0, 1};
        VkPipelineMultisampleStateCreateInfo ms = {VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO, NULL, 0, VK_SAMPLE_COUNT_1_BIT};
        VkPipelineColorBlendAttachmentState ba = {1, VK_BLEND_FACTOR_SRC_ALPHA, VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA, VK_BLEND_OP_ADD, VK_BLEND_FACTOR_ZERO, VK_BLEND_FACTOR_ONE, VK_BLEND_OP_ADD, 0xf};
        VkPipelineColorBlendStateCreateInfo cbs = {VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO, NULL, 0, 0, 0, 1, &ba};
        VkDynamicState dyn[] = {VK_DYNAMIC_STATE_VIEWPORT, VK_DYNAMIC_STATE_SCISSOR}; VkPipelineDynamicStateCreateInfo dy = {VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO, NULL, 0, 2, dyn};
        VkPipelineRenderingCreateInfo rci = {VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO, NULL, 0, 1, &g_sfmt};
        VkGraphicsPipelineCreateInfo ci = {VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO, &rci, 0, 2, ss, &vi, &ia, NULL, &vs, &rs, &ms, NULL, &cbs, &dy, g_ov.layout};
        VkResult r = vkCreateGraphicsPipelines(V.dev, V.pcache, 1, &ci, NULL, &g_ov.pipe);
        vkDestroyShaderModule(V.dev, vm, NULL); vkDestroyShaderModule(V.dev, fm, NULL);
        if (r) { VKRED_ONCE(92, "overlay pipeline failed: %d", r); return 0; }
        g_ov.pfmt = g_sfmt;
    }
    if (g_ov.w != w || g_ov.h != h) {   // (re)rasterize for this window size
        vkDeviceWaitIdle(V.dev);
        if (g_ov.view) { vkDestroyImageView(V.dev, g_ov.view, NULL); vkDestroyImage(V.dev, g_ov.img, NULL); vkFreeMemory(V.dev, g_ov.mem, NULL); vkDestroyBuffer(V.dev, g_ov.up, NULL); vkFreeMemory(V.dev, g_ov.upm, NULL); }
        VkImageCreateInfo ic = {VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, NULL, 0, VK_IMAGE_TYPE_2D, VK_FORMAT_R8G8B8A8_UNORM, {w, h, 1}, 1, 1, VK_SAMPLE_COUNT_1_BIT, VK_IMAGE_TILING_OPTIMAL,
            VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT, VK_SHARING_MODE_EXCLUSIVE, 0, NULL, VK_IMAGE_LAYOUT_UNDEFINED};
        VKCHK(vkCreateImage(V.dev, &ic, NULL, &g_ov.img)); VkMemoryRequirements rq; vkGetImageMemoryRequirements(V.dev, g_ov.img, &rq);
        VkMemoryAllocateInfo ai = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, NULL, rq.size, vk_mem_type(rq.memoryTypeBits, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, 0)};
        VKCHK(vkAllocateMemory(V.dev, &ai, NULL, &g_ov.mem)); VKCHK(vkBindImageMemory(V.dev, g_ov.img, g_ov.mem, 0));
        VkImageViewCreateInfo vi = {VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, NULL, 0, g_ov.img, VK_IMAGE_VIEW_TYPE_2D, VK_FORMAT_R8G8B8A8_UNORM, {0}, {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
        VKCHK(vkCreateImageView(V.dev, &vi, NULL, &g_ov.view));
        VkBufferCreateInfo bc = {VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, NULL, 0, (VkDeviceSize)w * h * 4, VK_BUFFER_USAGE_TRANSFER_SRC_BIT, VK_SHARING_MODE_EXCLUSIVE};
        VKCHK(vkCreateBuffer(V.dev, &bc, NULL, &g_ov.up)); VkMemoryRequirements bq; vkGetBufferMemoryRequirements(V.dev, g_ov.up, &bq);
        VkMemoryAllocateInfo bi = {VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, NULL, bq.size, vk_mem_type(bq.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT, 0)};
        VKCHK(vkAllocateMemory(V.dev, &bi, NULL, &g_ov.upm)); VKCHK(vkBindBufferMemory(V.dev, g_ov.up, g_ov.upm, 0));
        void *px; VKCHK(vkMapMemory(V.dev, g_ov.upm, 0, VK_WHOLE_SIZE, 0, &px)); ov_raster(px, w, h);
        VkDescriptorImageInfo ii = {g_ov.samp, g_ov.view, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};
        VkWriteDescriptorSet wr = {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, g_ov.set, 0, 0, 1, VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, &ii};
        vkUpdateDescriptorSets(V.dev, 1, &wr, 0, NULL);
        g_ov.w = w; g_ov.h = h; g_ov.uploaded = 0;
    }
    if (!g_ov.uploaded) {
        VkImageMemoryBarrier b = {VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER, NULL, 0, VK_ACCESS_TRANSFER_WRITE_BIT, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
            VK_QUEUE_FAMILY_IGNORED, VK_QUEUE_FAMILY_IGNORED, g_ov.img, {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
        vkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, NULL, 0, NULL, 1, &b);
        VkBufferImageCopy c = {0, 0, 0, {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1}, {0, 0, 0}, {g_ov.w, g_ov.h, 1}};
        vkCmdCopyBufferToImage(cb, g_ov.up, g_ov.img, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &c);
        b.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT; b.dstAccessMask = VK_ACCESS_SHADER_READ_BIT; b.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL; b.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
        vkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT, 0, 0, NULL, 0, NULL, 1, &b);
        g_ov.uploaded = 1;
    }
    return 1;
}
