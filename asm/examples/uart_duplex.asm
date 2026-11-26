# Full-duplex UART. TX: 0xB1 frames on uo1 (pin 1), repeated. RX: the
# sampler (SMP) receives 8N1 on uio2 (pin 10) and puts each byte in rxp.
# The host reads rxp with the pull handshake (docs/isa.md, host rules).
# The program never branches on the status pins: TX timing does not
# depend on RX. If the host is too slow, new bytes are dropped.
#
# Host pins (HCFG): data uo0, uo2..uo7 and uio3 (pin 11), n=8.
# Strobe pin 12 (uio4). Request uio5 (pin 13). The host keeps uio2 high
# (UART idle) from before the program starts.
.equ TX, 0x11
.equ BIT, 16
.equ RXSRC, 0x0A      # SMP source: Rp[3]=1, uio index 2
.equ UMASK, 0xFD
.equ IOMASK, 0x08
.equ SR, 0xC5         # strobe pin 12, request uio5
.equ Z, 0x88          # uio0 is low after the load: JL Z always jumps

    LDI  R2, TX
    LDI  R3, BIT
    LDI  R5, RXSRC
    SMP  R5, R3
    LDI  R4, UMASK
    LDI  R6, IOMASK
    LDI  R7, SR
    HCFG R4, R6, R7
    LDI  R7, Z
top:
    LDI  R0, 0xB1
    PSET R2, 0, R3
    LDI  R1, 8
bit:
    OUT  R2, R0, R3
    DJNZ R1, bit
    PSET R2, 1, R3
    JL   R7, top
