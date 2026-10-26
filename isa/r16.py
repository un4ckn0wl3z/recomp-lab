"""
R16 — ซีพียูของเครื่องเกมสมมุติ "Toybox-16"
==============================================
ไฟล์นี้เปรียบเหมือน "คู่มือ CPU" ที่นักรีเวิร์สหาได้จากสาธารณะ
(เหมือนที่คนทำ N64Recomp รู้สเปก MIPS R4300 จากเอกสาร)

สเปกสั้น ๆ
-----------
- รีจิสเตอร์ 16-bit 8 ตัว: r0..r7
- หน่วยความจำ 64 KB (byte addressable)
    0x0000-0x7FFF : ROM (โค้ด + ข้อมูลของเกม ถูกโหลดที่นี่)
    0x8000-0xFFFF : RAM
- คำสั่งยาวคงที่ 4 ไบต์: [opcode, x, y, z]
    imm16 = y | (z << 8)   (little-endian)
- CALL/RET ใช้ "hardware return stack" แยกจากหน่วยความจำ
  (ทำให้ recomp ง่ายขึ้น: CALL -> เรียกฟังก์ชัน C, RET -> return)
- I/O ผ่านคำสั่ง SYS n:
    SYS 0 = putc(r0)      SYS 1 = r0 = getc() (EOF = 0xFFFF)
    SYS 2 = พิมพ์ r0 เป็นเลขฐานสิบ
"""
from collections import namedtuple

ROM_BASE = 0x0000
RAM_BASE = 0x8000
MEM_SIZE = 0x10000
INSN_SIZE = 4

# opcode: (mnemonic, format)
# format: ''   ไม่มี operand
#         'ri' rd, imm16         'rr'  rd, rs        'rrr' rd, rs, rt
#         'rrb' rd, rs, imm8     'rm'  r, [rb+off8]  'i'   imm16
#         'r'  rs                'b'   imm8 (ใน x)
OPS = {
    0x00: ('halt', ''),
    0x01: ('ldi',  'ri'),
    0x02: ('mov',  'rr'),
    0x03: ('add',  'rrr'),
    0x04: ('sub',  'rrr'),
    0x05: ('and',  'rrr'),
    0x06: ('or',   'rrr'),
    0x07: ('xor',  'rrr'),
    0x08: ('shl',  'rrb'),
    0x09: ('shr',  'rrb'),
    0x0A: ('addi', 'ri'),
    0x0B: ('ldb',  'rm'),
    0x0C: ('stb',  'rm'),
    0x0D: ('jmp',  'i'),
    0x0E: ('jz',   'ri'),
    0x0F: ('jnz',  'ri'),
    0x10: ('call', 'i'),
    0x11: ('ret',  ''),
    0x12: ('jr',   'r'),
    0x13: ('sys',  'b'),
    0x14: ('eq',   'rrr'),
    0x15: ('lt',   'rrr'),
}
NAME_TO_OP = {name: op for op, (name, _) in OPS.items()}

# คำสั่งที่ "ไม่ไหลต่อ" ไปคำสั่งถัดไป (จบ basic block แบบไม่มี fallthrough)
NO_FALLTHROUGH = {'halt', 'jmp', 'ret', 'jr'}
# คำสั่งกระโดดที่รู้ปลายทางตอน static (imm16)
DIRECT_BRANCH = {'jmp', 'jz', 'jnz'}

Insn = namedtuple('Insn', 'addr op name fmt x y z imm')


def decode(mem, addr):
    """ถอดรหัสคำสั่งที่ addr; คืน None ถ้าไม่ใช่คำสั่งที่ถูกต้อง"""
    if addr < 0 or addr + 4 > len(mem):
        return None
    op, x, y, z = mem[addr:addr + 4]
    if op not in OPS:
        return None
    name, fmt = OPS[op]
    # ตรวจว่าฟิลด์รีจิสเตอร์อยู่ในช่วง 0..7
    regs = {'ri': [x], 'rr': [x, y], 'rrr': [x, y, z], 'rrb': [x, y],
            'rm': [x, y], 'r': [x]}.get(fmt, [])
    if any(r > 7 for r in regs):
        return None
    return Insn(addr, op, name, fmt, x, y, z, y | (z << 8))


def fmt_insn(i, sym=lambda a: f'0x{a:04X}'):
    """แปลงคำสั่งเป็นข้อความ assembly"""
    n, f = i.name, i.fmt
    if f == '':
        return n
    if f == 'ri':
        v = sym(i.imm) if n in ('jz', 'jnz') else f'0x{i.imm:04X}'
        return f'{n:<5} r{i.x}, {v}'
    if f == 'rr':
        return f'{n:<5} r{i.x}, r{i.y}'
    if f == 'rrr':
        return f'{n:<5} r{i.x}, r{i.y}, r{i.z}'
    if f == 'rrb':
        return f'{n:<5} r{i.x}, r{i.y}, {i.z}'
    if f == 'rm':
        return f'{n:<5} r{i.x}, [r{i.y}+{i.z}]'
    if f == 'i':
        return f'{n:<5} {sym(i.imm)}'
    if f == 'r':
        return f'{n:<5} r{i.x}'
    if f == 'b':
        return f'{n:<5} {i.x}'
    return n
