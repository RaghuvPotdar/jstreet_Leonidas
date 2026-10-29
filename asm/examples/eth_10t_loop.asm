# 10BASE-T TX, looped. IEEE Manchester OUTM, 6 clocks/bit, pin 6.
# Payload is in dmem (host strobe 11 before start). One OUTM per bit.
# First LD in idle arms the OUTM dmem stream. After that only OUTM+DJNZ:
# leftover hold hides DJNZ, and every 8th OUTM refills R0 from dmem.
# Same 27-byte runt as eth_10t.asm (preamble/SFD/frame/FCS).
# R0 shifter, R1 pins, R3 duration, R4 bit count (27*8), R5 dmem ptr.

.equ PINS, 0x66
.equ BIT,  6
.equ N,    216

    LDI   R1, PINS      # 0
    LDI   R3, BIT       # 1
    LDI   R5, 0         # 2
    LD    R0, [R5]      # 3  idle high; arms stream
    LDI   R4, N         # 4
loop:
    OUTM  R1, R0, R3    # 5
    DJNZ  R4, loop      # 6
    HALT                # 7
