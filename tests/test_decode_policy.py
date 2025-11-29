from __future__ import annotations

import unittest

from ecc_model.core import DecodePolicy, decode_with_policy, positions_contiguous
from ecc_model.rs import DecodeError


class DummyCodec:
    def __init__(self, *, decoded: bytes | None = None, positions: list[int] | None = None, error: Exception | None = None):
        self._decoded = decoded
        self._positions = positions or []
        self._error = error

    def decode(self, _: bytes):
        if self._error is not None:
            raise self._error
        if self._decoded is None:
            raise AssertionError("decoded payload must be provided for successful decode")
        return self._decoded, list(self._positions)


class PositionsContiguousTests(unittest.TestCase):
    def test_contiguous_sequences(self) -> None:
        self.assertTrue(positions_contiguous([]))
        self.assertTrue(positions_contiguous([5]))
        self.assertTrue(positions_contiguous([3, 4, 5]))
        self.assertTrue(positions_contiguous([9, 8, 7]))

    def test_non_contiguous_sequences(self) -> None:
        self.assertFalse(positions_contiguous([1, 3]))
        self.assertFalse(positions_contiguous([0, 1, 3]))
        self.assertFalse(positions_contiguous([4, 6, 5, 8]))


class DecodePolicyTests(unittest.TestCase):
    def test_detects_suspect_locations(self) -> None:
        codec = DummyCodec(decoded=b"OK", positions=[0, 2])
        policy = DecodePolicy(enforce_contiguous_locations=True)
        outcome = decode_with_policy(codec, b"", b"OK", policy)
        self.assertIsNone(outcome.corrected)
        self.assertTrue(outcome.silent)
        self.assertTrue(outcome.suspect_locations)

    def test_success_with_contiguous_locations(self) -> None:
        codec = DummyCodec(decoded=b"DATA", positions=[5, 6])
        policy = DecodePolicy(enforce_contiguous_locations=True)
        outcome = decode_with_policy(codec, b"", b"DATA", policy)
        self.assertTrue(outcome.corrected)
        self.assertFalse(outcome.silent)

    def test_uncorrectable_on_decoder_error(self) -> None:
        codec = DummyCodec(error=DecodeError("boom"))
        policy = DecodePolicy()
        outcome = decode_with_policy(codec, b"", b"", policy)
        self.assertFalse(outcome.corrected)
        self.assertFalse(outcome.silent)

    def test_mismatch_counts_silent(self) -> None:
        codec = DummyCodec(decoded=b"wrong", positions=[])
        policy = DecodePolicy()
        outcome = decode_with_policy(codec, b"", b"expected", policy)
        self.assertIsNone(outcome.corrected)
        self.assertTrue(outcome.silent)
        self.assertFalse(outcome.suspect_locations)


if __name__ == "__main__":
    unittest.main()

