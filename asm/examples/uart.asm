# UART TX: byte 0xB1 on pin 1, 16 clocks per level, LSB first.
# R0 = shifter, R1 = bit count, R2 = pin desc, R3 = duration.
.equ TX, 0x11
.equ BIT, 16

    LDI  R2, TX         # 0
    LDI  R3, BIT        # 1
    LDI  R0, 0xB1       # 2
    PSET R2, 0, R3      # 3
    LDI  R1, 8          # 4
loop:
    OUT  R2, R0, R3     # 5
    DJNZ R1, loop       # 6
    PSET R2, 1, R3      # 7
    HALT                # 8
