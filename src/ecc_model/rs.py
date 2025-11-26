from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


class DecodeError(Exception):
    pass


@dataclass
class RustCodec:
    """
    Rust-backed codec via pyo3 extension ecc_model._rs.
    Exposes encode/decode with correction locations.
    """

    nsym: int
    nsize: int

    def __post_init__(self) -> None:
        try:
            from . import _rs as _rs_mod  # type: ignore
        except Exception as exc:
            raise RuntimeError("Rust extension ecc_model._rs is not installed. Build with maturin.") from exc
        self._rs = _rs_mod

    def encode(self, message: bytes) -> bytes:
        return self._rs.encode(self.nsym, self.nsize, message)  # type: ignore[no-any-return]

    def decode(self, codeword: bytes) -> Tuple[bytes, List[int]]:
        try:
            decoded, positions = self._rs.decode(self.nsym, self.nsize, codeword)  # type: ignore[misc]
        except Exception as exc:
            raise DecodeError(str(exc)) from exc
        return decoded, list(positions)


def get_codec(*, nsym: int, nsize: int):
    """
    Factory returning a codec with a uniform interface:
      - encode(message: bytes) -> bytes
      - decode(codeword: bytes) -> tuple[bytes, list[int]]
    """
    return RustCodec(nsym=nsym, nsize=nsize)
