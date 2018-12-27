"""Encoders and decoders between binary and one-hot representation."""

from .. import *


class Encoder:
    """Encode one-hot to binary.

    If one bit in ``i`` is asserted, ``n`` is low and ``o`` indicates the asserted bit.
    Otherwise, ``n`` is high and ``o`` is ``0``.

    Parameters
    ----------
    width : int
        Bit width of the input

    Attributes
    ----------
    i : Signal(width), in
        One-hot input.
    o : Signal(max=width), out
        Encoded binary.
    n : Signal, out
        Invalid: either none or multiple input bits are asserted.
    """
    def __init__(self, width):
        self.i = Signal(width)
        self.o = Signal(max=max(2, width))
        self.n = Signal()

    def get_fragment(self, platform):
        m = Module()
        with m.Switch(self.i):
            for j in range(len(self.i)):
                with m.Case(1 << j):
                    m.d.comb += self.o.eq(j)
            with m.Case():
                m.d.comb += self.n.eq(1)
        return m.lower(platform)


class PriorityEncoder:
    """Priority encode requests to binary.

    If any bit in ``i`` is asserted, ``n`` is low and ``o`` indicates the least significant
    asserted bit.
    Otherwise, ``n`` is high and ``o`` is ``0``.

    Parameters
    ----------
    width : int
        Bit width of the input.

    Attributes
    ----------
    i : Signal(width), in
        Input requests.
    o : Signal(max=width), out
        Encoded binary.
    n : Signal, out
        Invalid: no input bits are asserted.
    """
    def __init__(self, width):
        self.i = Signal(width)
        self.o = Signal(max=max(2, width))
        self.n = Signal()

    def get_fragment(self, platform):
        m = Module()
        for j, b in enumerate(reversed(self.i)):
            with m.If(b):
                m.d.comb += self.o.eq(len(self.i) - j - 1)
        m.d.comb += self.n.eq(self.i == 0)
        return m.lower(platform)


class Decoder:
    """Decode binary to one-hot.

    If ``n`` is low, only the ``i``th bit in ``o`` is asserted.
    If ``n`` is high, ``o`` is ``0``.

    Parameters
    ----------
    width : int
        Bit width of the output.

    Attributes
    ----------
    i : Signal(max=width), in
        Input binary.
    o : Signal(width), out
        Decoded one-hot.
    n : Signal, in
        Invalid, no output bits are to be asserted.
    """
    def __init__(self, width):
        self.i = Signal(max=max(2, width))
        self.n = Signal()
        self.o = Signal(width)

    def get_fragment(self, platform):
        m = Module()
        with m.Switch(self.i):
            for j in range(len(self.o)):
                with m.Case(j):
                    m.d.comb += self.o.eq(1 << j)
        with m.If(self.n):
            m.d.comb += self.o.eq(0)
        return m.lower(platform)


class PriorityDecoder(Decoder):
    """Decode binary to priority request.

    Identical to :class:`Decoder`.
    """
