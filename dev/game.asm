; ==============================================================
;  COIN DUNGEON — เกมตัวอย่างสำหรับเครื่อง Toybox-16 (CPU R16)
;  นี่คือ "ซอร์สต้นฉบับ" ของผู้พัฒนา
;  ในแล็บ เราจะแกล้งทำเป็นว่า "ไม่มีไฟล์นี้" มีแค่ given/game.rom
;
;  เล่น: w a s d เดิน, q ออก  เก็บ $ ให้ครบเพื่อชนะ
; ==============================================================
.equ RAM_MAP,   0x8000
.equ START_POS, 11

.org 0x0000
start:
        call init_map
        ldi  r4, START_POS      ; r4 = ตำแหน่งผู้เล่น (index ในแผนที่)
        ldi  r6, 0              ; r6 = คะแนน
main_loop:
        call render             ; render คืนจำนวนเหรียญที่เหลือใน r5
        jz   r5, win
        ldi  r1, str_prompt
        call puts
read_key:
        sys  1                  ; r0 = getc()  (0xFFFF = EOF)
        ldi  r2, 0xFFFF
        eq   r3, r0, r2
        jnz  r3, quit
        ldi  r2, 10
        eq   r3, r0, r2
        jnz  r3, read_key       ; ข้าม newline
        call decode_key         ; r0 = index คำสั่ง 0..5
        ; ---- dispatch ผ่าน jump table  (indirect jump = ศัตรูของ static recomp!) ----
        shl  r0, r0, 1
        ldi  r1, cmd_table
        add  r1, r1, r0
        ldb  r2, [r1+0]
        ldb  r3, [r1+1]
        shl  r3, r3, 8
        or   r2, r2, r3
        jr   r2

cmd_invalid:
        ldi  r1, str_bad
        call puts
        jmp  read_key
cmd_up:
        ldi  r1, -10
        jmp  try_move
cmd_left:
        ldi  r1, -1
        jmp  try_move
cmd_down:
        ldi  r1, 10
        jmp  try_move
cmd_right:
        ldi  r1, 1
        jmp  try_move
cmd_quit:
        jmp  quit

try_move:
        add  r2, r4, r1         ; r2 = ตำแหน่งใหม่
        ldi  r3, RAM_MAP
        add  r3, r3, r2         ; r3 = address ของช่องใหม่
        ldb  r0, [r3+0]
        ldi  r1, '#'
        eq   r1, r0, r1
        jnz  r1, bump
        ldi  r1, '$'
        eq   r1, r0, r1
        jz   r1, no_coin
        call add_score
no_coin:
        ldi  r1, RAM_MAP
        add  r1, r1, r4
        ldi  r0, '.'
        stb  r0, [r1+0]         ; ลบ @ เก่า
        ldi  r0, '@'
        stb  r0, [r3+0]         ; วาง @ ใหม่
        mov  r4, r2
        jmp  main_loop
bump:
        ldi  r1, str_bump
        call puts
        jmp  main_loop

win:
        ldi  r1, str_win
        call puts
        mov  r0, r6
        sys  2
        ldi  r0, 10
        sys  0
        halt
quit:
        ldi  r1, str_quit
        call puts
        halt

; ---------- add_score: คะแนน += 10 ----------
add_score:
        addi r6, 10
        ret

; ---------- init_map: copy แผนที่จาก ROM -> RAM ----------
init_map:
        ldi  r1, map_rom
        ldi  r2, RAM_MAP
im_loop:
        ldb  r3, [r1+0]
        stb  r3, [r2+0]
        jz   r3, im_done
        addi r1, 1
        addi r2, 1
        jmp  im_loop
im_done:
        ret

; ---------- render: วาดจอ + นับเหรียญที่เหลือ -> r5 ----------
render:
        ldi  r1, str_score
        call puts
        mov  r0, r6
        sys  2
        ldi  r0, 10
        sys  0
        ldi  r1, RAM_MAP
        ldi  r5, 0
r_loop:
        ldb  r0, [r1+0]
        jz   r0, r_done
        sys  0
        ldi  r2, '$'
        eq   r3, r0, r2
        add  r5, r5, r3
        addi r1, 1
        jmp  r_loop
r_done:
        ret

; ---------- puts: พิมพ์สตริงที่ r1 ----------
puts:
        ldb  r0, [r1+0]
        jz   r0, puts_done
        sys  0
        addi r1, 1
        jmp  puts
puts_done:
        ret

; ---------- decode_key: r0 = ตัวอักษร -> r0 = index (0 = ไม่รู้จัก) ----------
decode_key:
        ldi  r1, keymap
        ldi  r2, 1
dk_loop:
        ldb  r3, [r1+0]
        jz   r3, dk_none
        eq   r3, r3, r0
        jnz  r3, dk_found
        addi r1, 1
        addi r2, 1
        jmp  dk_loop
dk_none:
        ldi  r0, 0
        ret
dk_found:
        mov  r0, r2
        ret

; ======================= DATA =======================
cmd_table:  .word cmd_invalid, cmd_up, cmd_left, cmd_down, cmd_right, cmd_quit
keymap:     .string "wasdq"
str_prompt: .string "> "
str_score:  .string "\nScore: "
str_bad:    .string "?? keys: w a s d (q = quit)\n"
str_bump:   .string "Ouch! wall.\n"
str_win:    .string "*** YOU WIN! final score: "
str_quit:   .string "Bye.\n"
map_rom:    .string "#########\n#@..$...#\n#.##.##$#\n#$..$...#\n#########\n"
