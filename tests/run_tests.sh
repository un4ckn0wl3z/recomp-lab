#!/usr/bin/env bash
# เทียบผลลัพธ์ "อีมูเลเตอร์ (ground truth)" กับ "ไบนารี recomp" ทีละไบต์
# ใช้งาน: tests/run_tests.sh [path/to/native_binary]
cd "$(dirname "$0")/.."
BIN="${1:-out/game_native}"
mkdir -p out/test
pass=0; fail=0
for f in tests/inputs/*.txt; do
    name=$(basename "$f" .txt)
    python3 tools/emu.py given/game.rom < "$f" > "out/test/$name.emu"    2>/dev/null; e1=$?
    "$BIN"                         < "$f" > "out/test/$name.native" 2>"out/test/$name.err"; e2=$?
    if cmp -s "out/test/$name.emu" "out/test/$name.native" && [ $e1 -eq $e2 ]; then
        echo "  PASS  $name"; pass=$((pass+1))
    else
        echo "  FAIL  $name   (exit emu=$e1 native=$e2)"; fail=$((fail+1))
        head -c 300 "out/test/$name.err"
        diff <(cat "out/test/$name.emu") <(cat "out/test/$name.native") | head -5
    fi
done
echo "  ---- $pass passed, $fail failed"
[ $fail -eq 0 ]
