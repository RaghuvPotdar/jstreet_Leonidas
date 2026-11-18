# 10BASE-T style Manchester RX on uio[6] (pin 14), 6 clocks/bit.
# Every bit has a mid-bit edge. INW waits for it, shifts in the new
# level (IEEE: that level is the bit), then holds 4 clocks so the
# bit-boundary edge (+3) is skipped. The next INW re-locks on the next
# mid-bit edge (+6), so sender clock error does not add up.
# Receives 64 bits; R0 keeps the last 8. Echoes R0 as UART on uo[1].

.equ RX,    0xEE
.equ TX,    0x11
.equ HOLD,  4
.equ NBITS, 64
.equ BIT,   16

    LDI  R1, RX
    LDI  R5, TX
    LDI  R4, HOLD
    LDI  R3, BIT
    LDI  R2, NBITS
rx:
    INW  R1, R0, R4
    DJNZ R2, rx
    LDI  R2, 8
    PSET R5, 0, R3
echo:
    OUT  R5, R0, R3
    DJNZ R2, echo
    PSET R5, 1, R3
    HALT
