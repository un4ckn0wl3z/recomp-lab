#!/usr/bin/env python3
"""
emu.py — อีมูเลเตอร์ (interpreter) ของ Toybox-16
บทบาทในแล็บ: "ground truth" — ใช้ตรวจว่าเกมที่ recomp แล้วทำงานเหมือนเดิมทุกไบต์

ใช้งาน:
  python3 tools/emu.py given/game.rom                 # เล่นแบบโต้ตอบ
  python3 tools/emu.py given/game.rom < input.txt     # replay อินพุต
  python3 tools/emu.py given/game.rom --trace         # พิมพ์ทุกคำสั่งที่รัน (stderr)
  python3 tools/emu.py given/game.rom --cov cov.txt   # บันทึก address ที่ถูกรันจริง
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'isa'))
from r16 import MEM_SIZE, decode, fmt_insn  # noqa: E402


class Machine:
    def __init__(self, rom, fin, fout):
        self.mem = bytearray(MEM_SIZE)
        self.mem[:len(rom)] = rom
        self.r = [0] * 8
        self.pc = 0
        self.stack = []          # hardware return stack
        self.halted = False
        self.fin, self.fout = fin, fout
        self.steps = 0
        self.covered = set()

    def step(self, trace=False):
        pc, r, m = self.pc, self.r, self.mem
        i = decode(m, pc)
        if i is None:
            raise RuntimeError(f'illegal instruction at 0x{pc:04X}')
        self.covered.add(pc)
        if trace:
            regs = ' '.join(f'{v:04X}' for v in r)
            sys.stderr.write(f'{pc:04X}: {fmt_insn(i):<24} | {regs}\n')
        n, x, y, z, imm = i.name, i.x, i.y, i.z, i.imm
        nxt = pc + 4
        if n == 'halt':
            self.halted = True
        elif n == 'ldi':
            r[x] = imm
        elif n == 'mov':
            r[x] = r[y]
        elif n == 'add':
            r[x] = (r[y] + r[z]) & 0xFFFF
        elif n == 'sub':
            r[x] = (r[y] - r[z]) & 0xFFFF
        elif n == 'and':
            r[x] = r[y] & r[z]
        elif n == 'or':
            r[x] = r[y] | r[z]
        elif n == 'xor':
            r[x] = r[y] ^ r[z]
        elif n == 'shl':
            r[x] = (r[y] << z) & 0xFFFF
        elif n == 'shr':
            r[x] = r[y] >> z
        elif n == 'addi':
            r[x] = (r[x] + imm) & 0xFFFF
        elif n == 'ldb':
            r[x] = m[(r[y] + z) & 0xFFFF]
        elif n == 'stb':
            m[(r[y] + z) & 0xFFFF] = r[x] & 0xFF
        elif n == 'jmp':
            nxt = imm
        elif n == 'jz':
            if r[x] == 0:
                nxt = imm
        elif n == 'jnz':
            if r[x] != 0:
                nxt = imm
        elif n == 'call':
            self.stack.append(nxt)
            nxt = imm
        elif n == 'ret':
            if not self.stack:          # ret จาก entry = จบโปรแกรม
                self.halted = True
            else:
                nxt = self.stack.pop()
        elif n == 'jr':
            nxt = r[x]
        elif n == 'sys':
            self.syscall(x)
        elif n == 'eq':
            r[x] = int(r[y] == r[z])
        elif n == 'lt':
            r[x] = int(r[y] < r[z])
        self.pc = nxt & 0xFFFF
        self.steps += 1

    def syscall(self, n):
        r = self.r
        if n == 0:
            self.fout.write(bytes([r[0] & 0xFF]))
        elif n == 1:
            self.fout.flush()
            ch = self.fin.read(1)
            r[0] = ch[0] if ch else 0xFFFF
        elif n == 2:
            self.fout.write(str(r[0]).encode())
        else:
            raise RuntimeError(f'unknown syscall {n}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--cov', help='เขียน address ที่ถูกรันลงไฟล์')
    ap.add_argument('--max-steps', type=int, default=10_000_000)
    a = ap.parse_args()
    rom = open(a.rom, 'rb').read()
    mach = Machine(rom, sys.stdin.buffer, sys.stdout.buffer)
    while not mach.halted:
        mach.step(a.trace)
        if mach.steps > a.max_steps:
            sys.exit('[emu] step limit reached')
    sys.stdout.buffer.flush()
    if a.cov:
        with open(a.cov, 'w') as f:
            for addr in sorted(mach.covered):
                f.write(f'0x{addr:04X}\n')
        sys.stderr.write(f'[emu] {len(mach.covered)} unique PCs executed -> {a.cov}\n')


if __name__ == '__main__':
    main()
