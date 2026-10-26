#!/usr/bin/env python3
"""
disasm.py — disassembler แบบ recursive descent
แยก "โค้ด" กับ "ข้อมูล" ออกจากกัน, ตั้งชื่อ label อัตโนมัติ, ชี้ string ที่ถูกอ้างถึง

ใช้งาน:
  python3 tools/disasm.py given/game.rom [--hints hints/game.hints.json] [--auto-tables]
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'isa'))
sys.path.insert(0, os.path.dirname(__file__))
from r16 import MEM_SIZE, fmt_insn  # noqa: E402
from analysis import analyze, load_hints, branch_targets, guess_jump_table  # noqa: E402


def c_string_at(mem, addr, rom_len, maxlen=40):
    s = bytearray()
    while addr < rom_len and mem[addr] != 0 and len(s) < maxlen:
        b = mem[addr]
        if not (32 <= b < 127 or b == 10):
            return None
        s.append(b)
        addr += 1
    return s.decode().replace('\n', '\\n') if s else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('--hints')
    ap.add_argument('--auto-tables', action='store_true')
    a = ap.parse_args()

    rom = open(a.rom, 'rb').read()
    mem = bytearray(MEM_SIZE)
    mem[:len(rom)] = rom
    logs = []
    funcs, hints = analyze(mem, len(rom), 0, load_hints(a.hints), a.auto_tables, logs.append)

    code = {}
    labels = {}
    for f in funcs.values():
        labels[f.entry] = f'func_{f.entry:04X}'
        code.update(f.insns)
    for f in funcs.values():
        for t in branch_targets(f):
            labels.setdefault(t, f'loc_{t:04X}')
    tables = {h['table']: h['count'] for h in hints.values()}
    referenced = {i.imm for i in code.values() if i.name == 'ldi' and i.imm < len(rom)}
    sym = lambda v: labels.get(v, f'0x{v:04X}')  # noqa: E731

    print(f'; ROM size: {len(rom)} bytes, functions found: {len(funcs)}')
    print(f'; code bytes: {len(code) * 4}, data/unknown bytes: {len(rom) - len(code) * 4}')
    for line in logs:
        print(';' + line)
    print()

    addr = 0
    while addr < len(rom):
        if addr in labels:
            if addr in funcs:
                print(f'\n; ------------------------------------------- function')
            print(f'{labels[addr]}:')
        if addr in code:
            i = code[addr]
            comment = ''
            if i.name == 'ldi':
                s = c_string_at(mem, i.imm, len(rom))
                if i.imm in tables:
                    comment = f'  ; -> jump table [{tables[i.imm]}]'
                elif s and i.imm not in code and len(s) >= 2:
                    comment = f'  ; -> "{s}"'
                elif 32 <= i.imm < 127:
                    comment = f"  ; '{chr(i.imm)}'"
            if i.name == 'jr':
                comment = '  ; !!! INDIRECT JUMP'
            raw = ' '.join(f'{b:02X}' for b in mem[addr:addr + 4])
            print(f'  {addr:04X}: {raw}   {fmt_insn(i, sym)}{comment}')
            addr += 4
        elif addr in tables:
            n = tables[addr]
            for k in range(n):
                v = mem[addr] | (mem[addr + 1] << 8)
                print(f'  {addr:04X}: .word {sym(v)}')
                addr += 2
        else:
            s = c_string_at(mem, addr, len(rom), maxlen=200)
            n = len(s.replace('\\n', '\n')) if s else 0
            # string ที่ถูก ldi อ้างถึง หรือยาวพอจะเชื่อได้ว่าเป็นข้อความ
            if s and addr + n < len(rom) and ((addr in referenced and n >= 2) or n >= 4):
                print(f'  {addr:04X}: .string "{s}"')
                addr += n + 1
            else:
                # ไบต์ที่ไม่รู้ว่าเป็นอะไร — รวบเป็นแถวละไม่เกิน 4 ไบต์
                chunk = [addr]
                while (len(chunk) < 4 and chunk[-1] + 1 < len(rom)
                       and chunk[-1] + 1 not in labels and chunk[-1] + 1 not in code
                       and chunk[-1] + 1 not in referenced):
                    chunk.append(chunk[-1] + 1)
                hexs = ', '.join(f'0x{mem[b]:02X}' for b in chunk)
                print(f'  {addr:04X}: .byte {hexs:<24} ; ??? data หรือโค้ดที่หาไม่เจอ')
                addr = chunk[-1] + 1

    # รายงาน indirect jump ที่ยังแก้ไม่ได้ + ข้อเสนอจาก heuristic
    unresolved = [(f.entry, j) for f in funcs.values() for j in f.unresolved_jr]
    if unresolved:
        print('\n; ================= UNRESOLVED INDIRECT JUMPS =================')
        sugg = []
        for fe, j in unresolved:
            g = guess_jump_table(mem, len(rom), j)
            print(f'; JR at 0x{j:04X} in func_{fe:04X}: ไม่รู้ปลายทาง -> โค้ดหลังจากนี้อาจหายไป')
            if g:
                print(f';   heuristic เดาว่า: table=0x{g["table"]:04X} count={g["count"]}')
                sugg.append({'jr': f'0x{j:04X}', 'table': f'0x{g["table"]:04X}', 'count': g['count']})
        if sugg:
            print('; ลองใส่ลงไฟล์ hints:')
            for line in json.dumps({'jump_tables': sugg}, indent=2).splitlines():
                print(';   ' + line)


if __name__ == '__main__':
    main()
