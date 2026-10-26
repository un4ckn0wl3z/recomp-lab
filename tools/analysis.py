"""
analysis.py — หัวใจของ static recompilation: "หาว่าอะไรคือโค้ด"
====================================================================
ROM เป็นแค่ก้อนไบต์ โค้ดกับข้อมูลปนกัน เราจึงใช้ recursive descent:
  1. เริ่มจาก entry point (0x0000)
  2. ไล่ถอดคำสั่งตามลำดับ, ตาม branch (jmp/jz/jnz) ไปทุกทาง
  3. เจอ CALL -> ปลายทางคือ "ฟังก์ชันใหม่" ใส่คิวไว้วิเคราะห์ต่อ
  4. เจอ JR (indirect jump) -> ไม่รู้ปลายทาง! ต้องพึ่ง
       (a) hints ที่มนุษย์เขียน (แบบ N64Recomp ใช้ไฟล์ .toml)
       (b) heuristic เดา jump table
     ถ้าไม่มีทั้งคู่ -> โค้ดที่อยู่หลัง jump table จะ "หายไป" จากผลลัพธ์
"""
import json
from collections import namedtuple
from r16 import decode, DIRECT_BRANCH, NO_FALLTHROUGH, INSN_SIZE

Func = namedtuple('Func', 'entry insns calls unresolved_jr jr_targets')


def load_hints(path):
    """อ่านไฟล์ hints -> {jr_addr: {'table': addr, 'count': n}}"""
    if not path:
        return {}
    h = json.load(open(path))
    out = {}
    for t in h.get('jump_tables', []):
        out[int(t['jr'], 0)] = {'table': int(t['table'], 0), 'count': int(t['count'])}
    return out


def read_table(mem, table, count):
    return [mem[table + 2 * k] | (mem[table + 2 * k + 1] << 8) for k in range(count)]


def guess_jump_table(mem, rom_len, jr_addr, lookback=10):
    """
    Heuristic: ย้อนหาคำสั่ง `ldi rX, <addr ใน ROM>` ก่อน JR
    แล้วอ่าน entry 16-bit ไปเรื่อย ๆ ตราบที่ดูเหมือน address ของโค้ดที่ valid
    (ของจริงจะดู bounds check / cmp ก่อน jump เพื่อหาจำนวน entry)
    """
    for k in range(1, lookback + 1):
        a = jr_addr - INSN_SIZE * k
        i = decode(mem, a)
        if i is None:
            break
        if i.name == 'ldi' and i.imm < rom_len and i.imm > jr_addr:
            table, entries = i.imm, []
            while table + 2 * len(entries) + 1 < rom_len:
                t = read_table(mem, table + 2 * len(entries), 1)[0]
                if t % INSN_SIZE or t >= rom_len or decode(mem, t) is None:
                    break
                entries.append(t)
            if entries:
                return {'table': table, 'count': len(entries)}
    return None


def analyze(mem, rom_len, entry=0, hints=None, auto_tables=False, log=None):
    hints = dict(hints or {})
    log = log or (lambda s: None)
    funcs = {}
    work = [entry]
    while work:
        f = work.pop()
        if f in funcs:
            continue
        insns, calls, unresolved, jr_targets = {}, set(), [], {}
        todo = [f]
        while todo:
            a = todo.pop()
            while a not in insns:
                i = decode(mem, a) if (a < rom_len and a % INSN_SIZE == 0) else None
                if i is None:
                    log(f'  ! invalid code at 0x{a:04X} (func 0x{f:04X})')
                    break
                insns[a] = i
                if i.name in DIRECT_BRANCH:
                    todo.append(i.imm)
                elif i.name == 'call':
                    calls.add(i.imm)
                elif i.name == 'jr':
                    info = hints.get(a)
                    if info is None and auto_tables:
                        info = guess_jump_table(mem, rom_len, a)
                        if info:
                            log(f'  ~ heuristic: JR@0x{a:04X} -> table 0x{info["table"]:04X} x{info["count"]}')
                            hints[a] = info
                    if info:
                        targets = read_table(mem, info['table'], info['count'])
                        jr_targets[a] = targets
                        todo.extend(targets)
                    else:
                        unresolved.append(a)
                if i.name in NO_FALLTHROUGH:
                    break
                a += INSN_SIZE
        funcs[f] = Func(f, insns, sorted(calls), unresolved, jr_targets)
        work.extend(calls)
    return funcs, hints


def branch_targets(func):
    t = set()
    for i in func.insns.values():
        if i.name in DIRECT_BRANCH:
            t.add(i.imm)
    for lst in func.jr_targets.values():
        t.update(lst)
    return t
