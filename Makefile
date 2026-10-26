# ============================================================
#  RECOMP LAB — make help เพื่อดูคำสั่งทั้งหมด
# ============================================================
SHELL  := /bin/bash
PY     ?= python3
CC     ?= cc
CFLAGS ?= -O2 -Wall -Wextra
ROM    := given/game.rom
HINTS  := hints/game.hints.json

.PHONY: help lab rom play trace disasm recomp native test nohints auto bench clean

help:
	@echo "make lab      — รันทั้ง pipeline: disasm -> recomp -> compile -> test"
	@echo "make play     — เล่นเกมต้นฉบับในอีมูเลเตอร์"
	@echo "make trace    — รันเกมพร้อมพิมพ์ทุกคำสั่ง (ไป out/trace.txt)"
	@echo "make disasm   — out/game.disasm.txt"
	@echo "make recomp   — ROM -> out/recomp_game.c"
	@echo "make native   — compile เป็น out/game_native"
	@echo "make test     — เทียบ emu vs native ทีละไบต์"
	@echo "make nohints  — สาธิต: recomp แบบไม่มี hints แล้วพังตรงไหน"
	@echo "make auto     — recomp ด้วย heuristic หา jump table อัตโนมัติ"
	@echo "make bench    — เทียบความเร็ว emu vs native"
	@echo "make rom      — (ฝั่งผู้พัฒนา) assemble dev/game.asm -> given/game.rom"

lab: disasm recomp native test
	@echo; echo ">>> เสร็จ! เล่นเกมเวอร์ชัน recomp ได้ด้วย: ./out/game_native"

rom:
	$(PY) dev/r16asm.py dev/game.asm -o $(ROM) --sym dev/game.sym

play:
	$(PY) tools/emu.py $(ROM)

trace:
	$(PY) tools/emu.py $(ROM) --trace --cov out/coverage.txt < tests/inputs/win.txt > /dev/null 2> out/trace.txt; \
	echo "ดู out/trace.txt และ out/coverage.txt"

disasm:
	@mkdir -p out
	$(PY) tools/disasm.py $(ROM) --hints $(HINTS) > out/game.disasm.txt
	@echo "[disasm] -> out/game.disasm.txt"

recomp:
	$(PY) tools/recomp.py $(ROM) -o out --hints $(HINTS)

native: recomp
	$(CC) $(CFLAGS) -Iruntime out/recomp_game.c out/rom_image.c runtime/runtime.c -o out/game_native
	@echo "[cc] -> out/game_native"

test: native
	@echo "[test] emulator vs recompiled:"
	@tests/run_tests.sh out/game_native

nohints:
	@mkdir -p out/nohints
	$(PY) tools/disasm.py $(ROM) > out/nohints/game.disasm.txt
	$(PY) tools/recomp.py $(ROM) -o out/nohints
	$(CC) $(CFLAGS) -Iruntime out/nohints/recomp_game.c out/nohints/rom_image.c runtime/runtime.c -o out/nohints/game_native
	@echo "[test] ไม่มี hints — คาดว่าจะ FAIL:"
	-@tests/run_tests.sh out/nohints/game_native

auto:
	@mkdir -p out/auto
	$(PY) tools/recomp.py $(ROM) -o out/auto --auto-tables
	$(CC) $(CFLAGS) -Iruntime out/auto/recomp_game.c out/auto/rom_image.c runtime/runtime.c -o out/auto/game_native
	@tests/run_tests.sh out/auto/game_native

bench: native
	@$(PY) -c "print('d'*2000)" > out/bench_input.txt
	@echo "emulator:"; time $(PY) tools/emu.py $(ROM) < out/bench_input.txt > /dev/null
	@echo "native  :"; time ./out/game_native < out/bench_input.txt > /dev/null

clean:
	rm -rf out
