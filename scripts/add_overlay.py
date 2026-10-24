# One-off source edit: the on-screen gamepad's drawing in dm/android/gfx_vk_present.c (swapchain views, CPU raster, blend pipeline, draw after the blit)
import sys
p = sys.argv[1]; s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    if a not in s and b in s: return
    assert a in s, a[:70]; s = s.replace(a, b, 1)
rep('#include <time.h>\n', '#include <time.h>\n#include "overlay_layout.h"\n#include "font5x7.h"\n#include "overlay_vert.spv.h"\n#include "overlay_frag.spv.h"\n')
rep("static ANativeWindow *g_win;\n", "static ANativeWindow *g_win;\nstatic VkImageView g_sview[8];\n__attribute__((weak)) int dm_overlay_visible(void) { return 0; }\n")
rep("    if (g_swap) { vkDeviceWaitIdle(V.dev); vkDestroySwapchainKHR(V.dev, g_swap, NULL); g_swap = VK_NULL_HANDLE; }",
    "    if (g_swap) { vkDeviceWaitIdle(V.dev); for (uint32_t i = 0; i < g_nsimg; i++) if (g_sview[i]) { vkDestroyImageView(V.dev, g_sview[i], NULL); g_sview[i] = VK_NULL_HANDLE; }\n"
    "                  vkDestroySwapchainKHR(V.dev, g_swap, NULL); g_swap = VK_NULL_HANDLE; }")
rep("    g_sext = caps.currentExtent.width != UINT32_MAX ? caps.currentExtent : (VkExtent2D){1920, 1080};",
    "    g_sext = (VkExtent2D){(uint32_t)ANativeWindow_getWidth(w), (uint32_t)ANativeWindow_getHeight(w)};   // the window as it is now; Android's compositor rotates (identity transform)\n"
    "    if (!g_sext.width || !g_sext.height) g_sext = caps.currentExtent;")
rep("VK_SHARING_MODE_EXCLUSIVE, 0, NULL, caps.currentTransform,", "VK_SHARING_MODE_EXCLUSIVE, 0, NULL, VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR,")
rep("    g_nsimg = 8; vkGetSwapchainImagesKHR(V.dev, g_swap, &g_nsimg, g_simg);",
    "    g_nsimg = 8; vkGetSwapchainImagesKHR(V.dev, g_swap, &g_nsimg, g_simg);\n"
    "    for (uint32_t i = 0; i < g_nsimg; i++) { VkImageViewCreateInfo vi = {VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, NULL, 0, g_simg[i], VK_IMAGE_VIEW_TYPE_2D, g_sfmt, {0}, {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};\n"
    "        VKCHK(vkCreateImageView(V.dev, &vi, NULL, &g_sview[i])); }")
rep("    if (r == VK_ERROR_OUT_OF_DATE_KHR || r == VK_SUBOPTIMAL_KHR) { swap_destroy();", "    if (r == VK_ERROR_OUT_OF_DATE_KHR) { swap_destroy();")
rep("""    barrier(cb, g_simg[idx], VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_PRESENT_SRC_KHR);
    vkEndCommandBuffer(cb);""",
"""    VkImageLayout lay = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    if (dm_overlay_visible() && overlay_ready(cb)) {
        barrier(cb, g_simg[idx], lay, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL); lay = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
        VkRenderingAttachmentInfo ca = {VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO, NULL, g_sview[idx], lay, 0, NULL, VK_IMAGE_LAYOUT_UNDEFINED, VK_ATTACHMENT_LOAD_OP_LOAD, VK_ATTACHMENT_STORE_OP_STORE};
        VkRenderingInfo ri = {VK_STRUCTURE_TYPE_RENDERING_INFO, NULL, 0, {{0, 0}, g_sext}, 1, 0, 1, &ca, NULL, NULL};
        vkCmdBeginRendering(cb, &ri);
        vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_GRAPHICS, g_ov.pipe);
        vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_GRAPHICS, g_ov.layout, 0, 1, &g_ov.set, 0, NULL);
        VkViewport vp = {0, 0, (float)g_sext.width, (float)g_sext.height, 0, 1}; VkRect2D sc = {{0, 0}, g_sext};
        vkCmdSetViewport(cb, 0, 1, &vp); vkCmdSetScissor(cb, 0, 1, &sc);
        vkCmdDraw(cb, 3, 1, 0, 0);
        vkCmdEndRendering(cb);
    }
    barrier(cb, g_simg[idx], lay, VK_IMAGE_LAYOUT_PRESENT_SRC_KHR);
    vkEndCommandBuffer(cb);""")
OVERLAY = open(sys.argv[2], encoding='utf-8').read()
rep("static void present_window(vkimg_t *im, const int crop[4]) {", OVERLAY + "static void present_window(vkimg_t *im, const int crop[4]) {")
open(p, 'w', encoding='utf-8', newline='\n').write(s); print('ok')
