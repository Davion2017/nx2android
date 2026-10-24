# One-off source edit for the Android port: Mach-O-only assembly syntax and section names in the host's C sources become the dm.h DM_ASM_* / DM_SECTION macros.
import sys
root = sys.argv[1]

def edit(path, pairs):
    p = f'{root}/{path}'; s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        if old not in s and new in s: continue   # already done
        assert old in s, f'{path}: {old[:60]!r} not found'
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8', newline='\n').write(s)

BS = '\\'
edit('host/hle.h', [
    ('section("__DATA,swhle")', 'DM_SECTION("swhle")'),
    ('section("__DATA,swforce")', 'DM_SECTION("swforce")'),
    ('__asm__(".text' + BS + 'n.p2align 2' + BS + 'n.globl _" #cname "_bs' + BS + 'n.private_extern _" #cname "_bs' + BS + 'n_" #cname "_bs:' + BS + 'n" ',
     '__asm__(".text' + BS + 'n.p2align 2' + BS + 'n.globl " DM_ASM_SYM(#cname "_bs") "' + BS + 'n" DM_ASM_PRIVATE " " DM_ASM_SYM(#cname "_bs") "' + BS + 'n" DM_ASM_SYM(#cname "_bs") ":' + BS + 'n" '),
    ('"    adrp x16, _" #cname "@PAGE' + BS + 'n    add x16, x16, _" #cname "@PAGEOFF' + BS + 'n    b _dm_bigstack_enter' + BS + 'n")',
     '"    adrp x16, " DM_ASM_PAGE(#cname) "' + BS + 'n    add x16, x16, " DM_ASM_PAGEOFF(#cname) "' + BS + 'n    b " DM_ASM_SYM("dm_bigstack_enter") "' + BS + 'n")'),
])
edit('gfx/nvn/hle_nvn.c', [('section("__DATA,swnvn")', 'DM_SECTION("swnvn")')])
edit('host/hle_bigstack.c', [
    ('".globl _dm_bigstack_enter' + BS + 'n"', '".globl " DM_ASM_SYM("dm_bigstack_enter") "' + BS + 'n"'),
    ('".private_extern _dm_bigstack_enter' + BS + 'n"', 'DM_ASM_PRIVATE " " DM_ASM_SYM("dm_bigstack_enter") "' + BS + 'n"'),
    ('"_dm_bigstack_enter:' + BS + 'n"', 'DM_ASM_SYM("dm_bigstack_enter") ":' + BS + 'n"'),
    ('"    bl _dm_bigstack_top' + BS + 'n"', '"    bl " DM_ASM_SYM("dm_bigstack_top") "' + BS + 'n"'),
])
print('ok')
