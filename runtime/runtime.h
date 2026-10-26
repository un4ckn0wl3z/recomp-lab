/* runtime.h — "เครื่อง" ที่โค้ด recomp ทำงานอยู่บน (แทน hardware จริง) */
#pragma once
#include <stdint.h>

typedef struct {
    uint16_t r[8];          /* รีจิสเตอร์ของ CPU ต้นฉบับ */
    uint8_t  mem[65536];    /* หน่วยความจำของเครื่องต้นฉบับ (ROM + RAM) */
} Ctx;

/* ทุก address ถูกตัดเหลือ 16 bit เหมือน CPU จริง (wrap-around) */
#define MEM8(a) (c->mem[(uint16_t)(a)])

void rt_sys(Ctx *c, int n);                              /* I/O: putc/getc/putnum */
void rt_halt(Ctx *c);
void rt_bad_jump(Ctx *c, uint16_t target, uint16_t from);

extern const uint8_t  rom_image[];
extern const uint32_t rom_size;
void recomp_entry(Ctx *c);                               /* สร้างโดย recomp.py */
