/* runtime.c — ส่วนที่ "เขียนด้วยมือ" ของ recomp: I/O, การเริ่มเครื่อง, error handling
 * ในโปรเจกต์จริง ส่วนนี้คือ graphics/audio/input (เช่น RT64 ของ N64Recomp)        */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "runtime.h"

static Ctx ctx;

void rt_sys(Ctx *c, int n) {
    switch (n) {
    case 0: putchar(c->r[0] & 0xFF); break;
    case 1: { fflush(stdout);
              int ch = getchar();
              c->r[0] = (ch == EOF) ? 0xFFFF : (uint16_t)ch; break; }
    case 2: printf("%u", (unsigned)c->r[0]); break;
    default: fprintf(stderr, "[runtime] unknown syscall %d\n", n); exit(2);
    }
}

void rt_halt(Ctx *c) { (void)c; fflush(stdout); exit(0); }

void rt_bad_jump(Ctx *c, uint16_t target, uint16_t from) {
    (void)c; fflush(stdout);
    fprintf(stderr, "\n[recomp] FATAL: indirect jump to 0x%04X (JR at 0x%04X) "
                    "— ปลายทางนี้ไม่ถูกแปลตอน recomp (ลองเพิ่ม hints)\n", target, from);
    exit(3);
}

int main(void) {
    memcpy(ctx.mem, rom_image, rom_size);   /* "เสียบตลับ" */
    recomp_entry(&ctx);                     /* รันเกม — เป็น native code ล้วน ๆ */
    fflush(stdout);
    return 0;
}
