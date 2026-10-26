# Recomp Lab — เรียน Static Recompilation จากศูนย์

แล็บนี้จำลองสิ่งที่โปรเจกต์อย่าง **N64Recomp** (Zelda: Majora's Mask PC port) หรือ **XenonRecomp** ทำ แต่ย่อให้เล็กพอที่จะอ่านโค้ดทุกบรรทัดได้ในหนึ่งวัน

เรามีเครื่องเกมสมมุติชื่อ **Toybox-16** (CPU **R16**) และเกม **Coin Dungeon** ที่มาในรูป ROM ไบนารีเท่านั้น เป้าหมายคือแปลง ROM นั้นเป็น **ซอร์ส C** แล้ว compile เป็น **โปรแกรม native** ที่เล่นได้เหมือนเดิมทุกไบต์ โดยไม่แตะซอร์สต้นฉบับ

```
 given/game.rom ──► disasm.py ──► (คนอ่าน + เขียน hints) ──► recomp.py ──► recomp_game.c
                                                                              │
                         runtime.c (I/O, เริ่มเครื่อง) ──────────────► cc ◄──┘
                                                                         │
 tools/emu.py (ground truth) ──── เทียบผลทีละไบต์ ────► out/game_native ◄┘
```

## เริ่มเลย

ต้องมี `python3`, `make` และ C compiler (`gcc`/`clang`) ใช้ได้บน Linux, macOS, WSL

```bash
make lab              # ทำทั้ง pipeline: disasm -> recomp -> compile -> test
./out/game_native     # เล่นเวอร์ชัน recomp (พิมพ์ w/a/s/d แล้ว Enter, q ออก)
make play             # เล่นเวอร์ชันต้นฉบับในอีมูเลเตอร์ เพื่อเทียบ
make help             # ดูคำสั่งทั้งหมด
```

## กติกาของแล็บ: สองฝั่ง

ฝั่ง **ผู้พัฒนาเกม** อยู่ในโฟลเดอร์ `dev/` (ซอร์ส `game.asm`, แอสเซมเบลอร์, และ `game.sym` ซึ่งเป็นชื่อฟังก์ชันจริง) ฝั่ง **นักรีเวิร์ส** คือคุณ ได้แค่ `given/game.rom` กับคู่มือ CPU (`isa/r16.py`) **ห้ามเปิด `dev/` จนกว่าจะทำแบบฝึกหัดเสร็จ** ให้ใช้ `dev/game.sym` เป็นเฉลยตอนท้ายเท่านั้น

---

## ขั้นที่ 0 — รู้จักเครื่องให้ดีก่อน (`isa/r16.py`)

Recomp ไม่ใช่เวทมนตร์ มันคือการแปลภาษาเครื่องหนึ่งไปอีกภาษาหนึ่ง คุณต้องรู้ว่าทุก opcode ทำอะไร ทุก bit มีความหมายอย่างไร และฮาร์ดแวร์อื่นในเครื่อง (ที่นี่คือแค่ `SYS` สำหรับ I/O) ทำงานยังไง ในโลกจริงนี่คือการอ่านคู่มือ MIPS/PowerPC และเอกสารฮาร์ดแวร์ของคอนโซลหลายร้อยหน้า

R16 ถูกออกแบบให้ง่ายโดยตั้งใจ: คำสั่งยาวคงที่ 4 ไบต์, ไม่มี delay slot, และมี hardware return stack แยกจากหน่วยความจำ

## ขั้นที่ 1 — อีมูเลเตอร์คือ "ความจริง" (`tools/emu.py`)

ก่อนจะ recomp อะไร ต้องมีสิ่งที่บอกได้ว่า "พฤติกรรมที่ถูกต้อง" คืออะไร อีมูเลเตอร์แบบ interpreter คือคำตอบ: มันอ่านทีละคำสั่ง แล้วทำตามตอน runtime

```bash
make trace     # out/trace.txt = ทุกคำสั่งที่ถูกรัน + ค่ารีจิสเตอร์
               # out/coverage.txt = address ที่ถูกรันจริงทั้งหมด
```

ข้อเสียของ interpreter คือช้า เพราะต้อง decode ซ้ำทุกครั้ง (`make bench` จะเห็นว่าต่างกันระดับหลายร้อยเท่า) และแก้ไข/ม็อดเกมยาก

## ขั้นที่ 2 — แยกโค้ดออกจากข้อมูล (`tools/disasm.py`, `tools/analysis.py`)

ROM คือก้อนไบต์ที่โค้ดกับข้อมูลปนกัน ถ้าไล่ถอดรหัสตั้งแต่ต้นจนจบ (linear sweep) จะได้ string และ table กลายเป็น "คำสั่ง" มั่ว ๆ

เราใช้ **recursive descent** แทน: เริ่มที่ entry point แล้วไล่ตามทุก branch ที่เป็นไปได้ คำสั่ง `call` บอกว่าปลายทางคือ "ฟังก์ชันใหม่" ส่วนอะไรที่ไม่มีทางเดินไปถึงก็ถือว่าเป็นข้อมูล

```bash
make nohints
less out/nohints/game.disasm.txt
```

สังเกตบรรทัด `jr r2 ; !!! INDIRECT JUMP` ที่ 0x0058 หลังจากนั้นทั้งหมดกลายเป็น `.byte ??? data หรือโค้ดที่หาไม่เจอ` ทั้งที่จริงคือโค้ดเดินของผู้เล่นทั้งหมด

## ขั้นที่ 3 — ศัตรูตัวฉกาจ: Indirect Jump (`hints/game.hints.json`)

`jr r2` กระโดดไปที่ address ที่คำนวณตอน runtime วิเคราะห์แบบ static ไม่รู้ว่าไปไหน นี่คือปัญหาหลักของ static recomp ทุกตัว (switch-case ใน C มักถูก compile เป็น jump table แบบนี้)

วิธีแก้มีสองแบบ:

1. **มนุษย์อ่านแล้วบอก** — ดูโค้ดก่อน `jr` จะเห็น `ldi r1, 0x01C8` ตามด้วยการอ่าน 2 ไบต์มาประกอบเป็น address แปลว่า 0x01C8 คือ jump table ไปดูไบต์ตรงนั้นจะเห็น `5C 00 68 00 70 00 ...` = address ของโค้ดที่หายไป เขียนลงไฟล์ hints (N64Recomp ใช้ไฟล์ `.toml` ในบทบาทเดียวกัน)
2. **Heuristic** — `make auto` ให้เครื่องเดาเอง วิธีนี้เร็วแต่เดาผิดได้ ของจริงต้องตรวจทานเสมอ

## ขั้นที่ 4 — แปล (`tools/recomp.py` → `out/recomp_game.c`)

เปิด `out/recomp_game.c` ดู ทุกบรรทัดมีคอมเมนต์คำสั่งต้นฉบับกำกับ หลักการแปลคือ:

| R16 | C |
|---|---|
| ฟังก์ชันที่เจอจาก `call` | `void func_XXXX(Ctx *c)` |
| branch target | label `L_XXXX:` |
| `jmp` / `jz` / `jnz` | `goto` / `if (...) goto` |
| `call` / `ret` | เรียกฟังก์ชัน C / `return` |
| `jr` | `switch` เฉพาะปลายทางที่รู้จัก, ที่เหลือ → `rt_bad_jump()` |
| `sys n` | `rt_sys(c, n)` → runtime |
| รีจิสเตอร์, หน่วยความจำ | `c->r[]`, `c->mem[]` ใน `struct Ctx` |

ข้อสังเกตสำคัญ:

- ผลลัพธ์**ไม่ใช่การ decompile** โค้ดไม่สวย ไม่มีตัวแปรที่มีชื่อ แต่มัน**ถูกต้องตามความหมายทุกคำสั่ง** แล้วปล่อยให้ C compiler (`-O2`) ทำ optimization ให้
- ต้องเลียนแบบพฤติกรรม CPU ให้เป๊ะ เช่น ทุกค่าต้อง wrap ที่ 16 bit (`(uint16_t)`) และ `shl` เกิน 15 bit ใน C เป็น undefined behavior จึงต้องจัดการแยก (ดู `translate()`)
- ROM ทั้งก้อนยังถูกฝังไว้ใน `rom_image.c` เพราะเกมยังอ่าน "ข้อมูล" เช่น string, แผนที่, jump table จาก ROM อยู่

## ขั้นที่ 5 — Runtime (`runtime/runtime.c`)

โค้ด recomp แทนแค่ CPU ส่วนฮาร์ดแวร์อื่นต้องเขียนเอง ที่นี่คือ putc/getc ในโปรเจกต์จริงคือ graphics, audio, controller, save ซึ่งมักเป็นงานที่ใหญ่ที่สุด (N64Recomp ใช้ RT64 เป็น renderer)

## ขั้นที่ 6 — พิสูจน์ว่าเหมือนเดิม (`tests/run_tests.sh`)

`make test` รันอินพุตชุดเดียวกันกับทั้งอีมูเลเตอร์และ native แล้วเทียบผลทีละไบต์ (differential testing) เพิ่มไฟล์อินพุตเองได้ใน `tests/inputs/`

---

## Emulate vs Recomp vs Decompile

| | Emulator | Static Recomp | Decompile (matching) |
|---|---|---|---|
| ทำงานตอน | runtime | build time | มนุษย์เขียนใหม่ |
| ความเร็ว | ช้าสุด | เร็วมาก | เร็วมาก |
| โค้ดอ่านง่าย | ไม่มีโค้ด | ไม่ค่อย | อ่านง่าย มีชื่อ |
| แรงงาน | ปานกลาง | ปานกลาง (hints + runtime) | มหาศาล (หลายปี) |
| ตัวอย่างจริง | Dolphin, Project64 | N64Recomp, XenonRecomp | SM64 decomp, OoT decomp |

## สมมุติฐานที่ static recomp ต้องพึ่ง (และโลกจริงทำลายมันยังไง)

- **ไม่มี self-modifying code** — โค้ดถูกแปลครั้งเดียว ถ้าเกมเขียนทับโค้ดตัวเองตอนรัน ผลจะไม่ตรง
- **รู้ปลายทาง indirect jump/call ทั้งหมด** — function pointer, vtable, jump table ต้องหาให้ครบ
- **`call` กลับมาที่คำสั่งถัดไปเสมอ** — R16 ง่ายเพราะมี hardware return stack แต่ CPU จริงเก็บ return address ในรีจิสเตอร์/stack ซึ่งเกมอาจแก้เองได้
- **โค้ดอยู่ครบใน ROM ตั้งแต่ต้น** — เกม N64 จำนวนมากใช้ overlay (โหลดโค้ดใส่ RAM ทีหลัง) ต้องหาแล้ว recomp แยก
- **ฮาร์ดแวร์อื่นเลียนแบบได้** — delay slot, ความแม่นยำของ floating point, timing ล้วนต้องจัดการ

---

## แบบฝึกหัด (ง่าย → ยาก)

1. **หา jump table เอง** — ลบไฟล์ `hints/game.hints.json` (สำรองไว้ก่อน) อ่าน `out/nohints/game.disasm.txt` แล้วเขียน hints ใหม่จากศูนย์จนกว่า `make test` จะผ่าน
2. **Static vs Dynamic** — `make trace` แล้วเทียบ `out/coverage.txt` กับโค้ดที่ disasm หาเจอ มีอะไรที่ static เจอแต่ไม่ถูกรัน? ถ้าใช้แค่ coverage เพื่อหาโค้ดจะเสี่ยงอะไร?
3. **Pointer หรือตัวเลข?** — ใน disasm มี `ldi r0, 0x002E ; -> "\n"` disassembler เดาผิดตรงไหน? ทำไมเรื่องนี้ถึงยากในทางทฤษฎี
4. **ม็อดเกม** — แก้ `func_010C` ใน `out/recomp_game.c` ให้เหรียญได้ 100 แต้ม แล้ว `cc` ใหม่ (อย่ารัน `make recomp` เพราะจะเขียนทับ) จากนั้นลองออกแบบระบบ "override" ให้ recomp.py ใช้ฟังก์ชันที่เขียนด้วยมือแทนฟังก์ชันที่ระบุใน hints แบบที่ N64Recomp ทำ
5. **Optimize** — ให้ recomp.py โหลด `c->r[n]` ใส่ตัวแปร local ตอนเข้าฟังก์ชันและเขียนกลับก่อน `call`/`return` วัดผลด้วย `make bench` และดู assembly ด้วย `cc -S`
6. **เพิ่มคำสั่ง `callr rX`** (indirect call) ลงใน ISA, แอสเซมเบลอร์, อีมูเลเตอร์, แล้วแก้เกมให้ใช้ function pointer table จากนั้นทำให้ recomp รองรับ (ต้องมี dispatcher จาก address → `func_XXXX`)
7. **Self-modifying code** — แก้เกมให้ `stb` เขียนทับคำสั่งตัวเอง แล้วดูว่า test พังยังไง ให้ runtime ตรวจจับการเขียนลง ROM แล้วเตือน

## แผนที่ไฟล์

```
isa/r16.py           คู่มือ CPU: opcode, encoding, decode()
dev/                 ฝั่งผู้พัฒนา (ห้ามแอบดู): game.asm, r16asm.py, game.sym
given/game.rom       สิ่งเดียวที่คุณได้
tools/emu.py         อีมูเลเตอร์ = ground truth
tools/analysis.py    recursive descent, หาฟังก์ชัน, jump table
tools/disasm.py      disassembler ที่แยกโค้ด/ข้อมูล
tools/recomp.py      static recompiler ROM -> C
runtime/             runtime.h, runtime.c (I/O + main)
hints/               ข้อมูลที่มนุษย์บอก recompiler
tests/               อินพุต + สคริปต์เทียบผล
out/                 ไฟล์ที่สร้างทั้งหมด (ลบได้ด้วย make clean)
```

เมื่อใช้กับเกมจริง ให้ใช้กับเกมที่คุณเป็นเจ้าของ และอย่าเผยแพร่ ROM หรือ asset ของเกม โปรเจกต์ recomp จริงจะแจกแค่เครื่องมือ แล้วให้ผู้ใช้นำ ROM ของตัวเองมาเอง
