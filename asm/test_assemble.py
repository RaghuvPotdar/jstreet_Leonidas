import pytest

from assemble import assemble


@pytest.mark.parametrize("src", ["LDI R0, 300", "LDI R0, -1", "DJNZ R1, 256", "JL R0, 0x1FF"])
def test_rejects_out_of_range_operand(src):
    with pytest.raises(ValueError, match="0..255"):
        assemble(src)


def test_rejects_duplicate_label():
    with pytest.raises(ValueError, match="duplicate label"):
        assemble("x:\nHALT\nx:\nHALT\n")


def test_edges_still_assemble():
    assert assemble("LDI R0, 255\nJL R0, 0\nx:\nDJNZ R1, x") == [0x00FF, 0x6000, 0x3102]


# Hand-encoded from docs/isa.md bit layouts, not from the encoder functions.
@pytest.mark.parametrize(
    "src, word",
    [
        ("CAP R5", 0x9500),                  # 1001 0 101 00000000
        ("SMP R6, R3", 0xAC18),              # 1010 110 000 011 000
        ("HCFG R1, R2, R3", 0xB298),         # 1011 001 010 011 000
        ("LDH", 0xC000),                     # 1100 000000000000
        ("ODO R4, R7", 0xD9C0),              # 1101 100 111 000000
    ],
)
def test_rx_opcodes(src, word):
    assert assemble(src) == [word]


@pytest.mark.parametrize("word", [0xE000, 0xF000])
def test_free_opcodes_have_no_mnemonic(word):
    # 1110 and 1111 stay free no-ops. No mnemonic may produce them.
    import assemble as asm

    ops = {v for k, v in vars(asm).items() if k.startswith("OP_")}
    assert word >> 12 not in ops


@pytest.mark.parametrize("src", ["CAP", "SMP R1", "HCFG R1, R2", "LDH R0", "ODO R1"])
def test_rx_opcodes_reject_bad_arity(src):
    with pytest.raises(ValueError):
        assemble(src)
