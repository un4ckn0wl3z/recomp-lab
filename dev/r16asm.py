#!/usr/bin/env python3
"""
r16asm — แอสเซมเบลอร์ของ "ฝั่งผู้พัฒนาเกม"
ใช้สร้าง ROM จาก game.asm  (ฝั่งรีเวิร์สในแล็บจะแกล้งทำเป็นว่าไม่มีไฟล์นี้)

ใช้งาน: python3 dev/r16asm.py dev/game.asm -o given/game.rom [--sym dev/game.sym]
"""
import os
import re
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'isa'))
from r16 import OPS, NAME_TO_OP  # noqa: E402


def strip_comment(line):
    out, q = [], None
    for ch in line:
        if q:
            out.append(ch)
            if ch == q:
                q = None
        else:
            if ch == ';':
                break
            if ch in '"\'':
                q = ch
            out.append(ch)
    return ''.join(out).strip()


def parse_string(s):
    s = s.strip()
    assert s[0] == '"' and s[-1] == '"', f'bad string: {s}'
    return s[1:-1].encode('latin-1').decode('unicode_escape').encode('latin-1')


class Asm:
    def __init__(self):
        self.syms = {}

    def value(self, tok, final):
        tok = tok.strip()
        if len(tok) == 3 and tok[0] == tok[2] == "'":
            return ord(tok[1])
        if re.fullmatch(r'-?(0x[0-9a-fA-F]+|\d+)', tok):
            return int(tok, 0) & 0xFFFF
        if tok in self.syms:
            return self.syms[tok]
        if final:
            raise SyntaxError(f'unknown symbol: {tok}')
        return 0

    @staticmethod
    def reg(tok):
        m = re.fullmatch(r'r([0-7])', tok.strip())
        if not m:
            raise SyntaxError(f'expected register: {tok}')
        return int(m.group(1))

    def memop(self, tok, final):
        m = re.fullmatch(r'\[\s*r([0-7])\s*(?:\+\s*([^\]]+))?\]', tok.strip())
        if not m:
            raise SyntaxError(f'expected [rN+off]: {tok}')
        off = self.value(m.group(2), final) if m.group(2) else 0
        return int(m.group(1)), off & 0xFF

    def encode(self, mnem, ops, final):
        op = NAME_TO_OP[mnem]
        fmt = OPS[op][1]
        R, V = self.reg, lambda t: self.value(t, final)
        if fmt == '':
            return [op, 0, 0, 0]
        if fmt == 'ri':
            v = V(ops[1])
            return [op, R(ops[0]), v & 0xFF, v >> 8]
        if fmt == 'rr':
            return [op, R(ops[0]), R(ops[1]), 0]
        if fmt == 'rrr':
            return [op, R(ops[0]), R(ops[1]), R(ops[2])]
        if fmt == 'rrb':
            return [op, R(ops[0]), R(ops[1]), V(ops[2]) & 0xFF]
        if fmt == 'rm':
            b, off = self.memop(ops[1], final)
            return [op, R(ops[0]), b, off]
        if fmt == 'i':
            v = V(ops[0])
            return [op, 0, v & 0xFF, v >> 8]
        if fmt == 'r':
            return [op, R(ops[0]), 0, 0]
        if fmt == 'b':
            return [op, V(ops[0]) & 0xFF, 0, 0]
        raise ValueError(fmt)

    def run(self, lines, final):
        img = {}
        pc = 0
        for lineno, raw in enumerate(lines, 1):
            line = strip_comment(raw)
            try:
                while True:
                    m = re.match(r'^([A-Za-z_]\w*):\s*(.*)$', line)
                    if not m:
                        break
                    if not final:
                        if m.group(1) in self.syms:
                            raise SyntaxError(f'duplicate label {m.group(1)}')
                        self.syms[m.group(1)] = pc
                    line = m.group(2)
                if not line:
                    continue
                parts = line.split(None, 1)
                mnem = parts[0].lower()
                rest = parts[1] if len(parts) > 1 else ''
                if mnem == '.org':
                    pc = self.value(rest, True)
                elif mnem == '.equ':
                    name, val = [t.strip() for t in rest.split(',', 1)]
                    self.syms[name] = self.value(val, True)
                elif mnem == '.string':
                    data = parse_string(rest) + b'\0'
                    for b in data:
                        img[pc] = b
                        pc += 1
                elif mnem == '.word':
                    for t in rest.split(','):
                        v = self.value(t, final)
                        img[pc], img[pc + 1] = v & 0xFF, v >> 8
                        pc += 2
                elif mnem in NAME_TO_OP:
                    if pc % 4:
                        raise SyntaxError('instruction not 4-byte aligned')
                    ops = [t.strip() for t in rest.split(',')] if rest else []
                    for k, b in enumerate(self.encode(mnem, ops, final)):
                        img[pc + k] = b
                    pc += 4
                else:
                    raise SyntaxError(f'unknown mnemonic {mnem}')
            except Exception as e:
                sys.exit(f'line {lineno}: {e}\n  {raw.rstrip()}')
        return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--sym')
    a = ap.parse_args()
    lines = open(a.src, encoding='utf-8').read().splitlines()
    asm = Asm()
    asm.run(lines, final=False)      # pass 1: เก็บ label
    img = asm.run(lines, final=True)  # pass 2: ออกโค้ดจริง
    size = max(img) + 1
    rom = bytearray(size)
    for k, v in img.items():
        rom[k] = v
    open(a.out, 'wb').write(rom)
    print(f'[asm] {a.out}: {size} bytes')
    if a.sym:
        with open(a.sym, 'w') as f:
            for name, addr in sorted(asm.syms.items(), key=lambda kv: kv[1]):
                f.write(f'0x{addr:04X} {name}\n')


if __name__ == '__main__':
    main()
