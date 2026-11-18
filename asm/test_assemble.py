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
