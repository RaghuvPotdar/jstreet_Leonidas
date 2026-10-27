# USB Low-Speed ACK handshake on uo_out[5]=D+, uo_out[6]=D-.
# At 60 MHz: bit = 40 clocks, SE0 = 80 clocks (two bit times).
#
# LS idle J: D+=0 D-=1. K: D+=1 D-=0. SE0: both 0.
# Line states after NRZI (compiler would emit these from the bit stream):
#   establish J, SYNC KJKJKJKK, PID ACK -> JJKJJKKK, EOP SE0 SE0 J.

.equ DP, 5
.equ DM, 6

    LDI   R4, 40
    LDI   R5, 80

    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 0, 1, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 1, 0, R4
    PSETH DP, DM, 0, 0, R5
    PSETH DP, DM, 0, 1, R4
    HALT
