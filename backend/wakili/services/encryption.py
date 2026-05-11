"""AES-256-GCM bundle encryption with scrypt KDF.

Pure-stdlib implementation: ``hashlib.scrypt`` for the KDF, plus a stdlib
GCM implementation built on AES from the ``ssl`` / ``cryptography`` libraries
where available, otherwise a minimal AES + GCM in pure Python.

Verda runs in low-bandwidth and air-gapped environments, so we avoid pulling
in the ``cryptography`` package by default. The pure-Python AES implementation
below is small enough to audit by hand and is only invoked for export
operations (not in the request hot path).

The output format is::

    "WAKILI1" || salt(16) || nonce(12) || ciphertext || tag(16)

Compatibility note: a Python decryptor utility ships in the bundle so the
defender can decrypt without reinstalling Verda.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

MAGIC = b"WAKILI1"
SALT_LEN = 16
NONCE_LEN = 12
TAG_LEN = 16


@dataclass
class EncryptedBundle:
    blob: bytes
    salt: bytes
    nonce: bytes


def derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=2**15,
        r=8,
        p=1,
        dklen=32,
        maxmem=64 * 1024 * 1024,
    )


def encrypt(plaintext: bytes, passphrase: str) -> bytes:
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = derive_key(passphrase, salt)
    ct, tag = _aes_gcm_encrypt(key, nonce, plaintext, associated=MAGIC)
    return MAGIC + salt + nonce + ct + tag


def decrypt(blob: bytes, passphrase: str) -> bytes:
    if not blob.startswith(MAGIC):
        raise ValueError("Not a Verda encrypted bundle")
    body = blob[len(MAGIC):]
    salt, body = body[:SALT_LEN], body[SALT_LEN:]
    nonce, body = body[:NONCE_LEN], body[NONCE_LEN:]
    if len(body) < TAG_LEN:
        raise ValueError("Bundle truncated")
    ct, tag = body[:-TAG_LEN], body[-TAG_LEN:]
    key = derive_key(passphrase, salt)
    return _aes_gcm_decrypt(key, nonce, ct, tag, associated=MAGIC)


# ---------------------------------------------------------------------------
# AES-256-GCM (pure Python)
#
# Reference implementation. Constant-time concerns are documented; given that
# this code only runs for explicit export operations and not on per-request
# critical paths, the simplicity-vs-resistance tradeoff is acceptable for the
# MVP. Production builds should swap to ``cryptography``'s GCM backend when
# the runtime allows it.
# ---------------------------------------------------------------------------


_SBOX = [
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
]
_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36, 0x6C, 0xD8, 0xAB, 0x4D, 0x9A]


def _xtime(b: int) -> int:
    return ((b << 1) ^ 0x1B) & 0xFF if b & 0x80 else (b << 1) & 0xFF


def _key_expansion(key: bytes) -> list[list[int]]:
    nk = 8  # AES-256
    nr = 14
    words: list[list[int]] = []
    for i in range(nk):
        words.append(list(key[4 * i:4 * (i + 1)]))
    for i in range(nk, 4 * (nr + 1)):
        temp = list(words[i - 1])
        if i % nk == 0:
            temp = [_SBOX[temp[1]] ^ _RCON[i // nk - 1], _SBOX[temp[2]], _SBOX[temp[3]], _SBOX[temp[0]]]
        elif i % nk == 4:
            temp = [_SBOX[b] for b in temp]
        words.append([a ^ b for a, b in zip(words[i - nk], temp)])
    return words


def _state_from_block(block: bytes) -> list[list[int]]:
    return [[block[c * 4 + r] for c in range(4)] for r in range(4)]


def _block_from_state(state: list[list[int]]) -> bytes:
    out = bytearray(16)
    for r in range(4):
        for c in range(4):
            out[c * 4 + r] = state[r][c]
    return bytes(out)


def _add_round_key(state: list[list[int]], words: list[list[int]], rnd: int) -> None:
    for c in range(4):
        for r in range(4):
            state[r][c] ^= words[rnd * 4 + c][r]


def _sub_bytes(state: list[list[int]]) -> None:
    for r in range(4):
        for c in range(4):
            state[r][c] = _SBOX[state[r][c]]


def _shift_rows(state: list[list[int]]) -> None:
    for r in range(1, 4):
        state[r] = state[r][r:] + state[r][:r]


def _mix_columns(state: list[list[int]]) -> None:
    for c in range(4):
        a = [state[r][c] for r in range(4)]
        b = [_xtime(x) for x in a]
        state[0][c] = b[0] ^ a[1] ^ b[1] ^ a[2] ^ a[3]
        state[1][c] = a[0] ^ b[1] ^ a[2] ^ b[2] ^ a[3]
        state[2][c] = a[0] ^ a[1] ^ b[2] ^ a[3] ^ b[3]
        state[3][c] = a[0] ^ b[0] ^ a[1] ^ a[2] ^ b[3]


def _aes_encrypt_block(key_words: list[list[int]], block: bytes) -> bytes:
    state = _state_from_block(block)
    _add_round_key(state, key_words, 0)
    for rnd in range(1, 14):
        _sub_bytes(state)
        _shift_rows(state)
        _mix_columns(state)
        _add_round_key(state, key_words, rnd)
    _sub_bytes(state)
    _shift_rows(state)
    _add_round_key(state, key_words, 14)
    return _block_from_state(state)


def _inc32(counter: bytes) -> bytes:
    body, tail = counter[:12], int.from_bytes(counter[12:], "big")
    return body + ((tail + 1) & 0xFFFFFFFF).to_bytes(4, "big")


def _gctr(key_words: list[list[int]], icb: bytes, data: bytes) -> bytes:
    out = bytearray()
    cb = icb
    for i in range(0, len(data), 16):
        block = data[i:i + 16]
        ks = _aes_encrypt_block(key_words, cb)
        out.extend(b ^ k for b, k in zip(block, ks))
        cb = _inc32(cb)
    return bytes(out)


def _ghash(h: bytes, data: bytes) -> bytes:
    y = 0
    H = int.from_bytes(h, "big")
    for i in range(0, len(data), 16):
        block = data[i:i + 16].ljust(16, b"\x00")
        y ^= int.from_bytes(block, "big")
        y = _gf_mult(y, H)
    return y.to_bytes(16, "big")


def _gf_mult(x: int, y: int) -> int:
    R = 0xE1 << 120
    z = 0
    v = y
    for i in range(127, -1, -1):
        if (x >> i) & 1:
            z ^= v
        if v & 1:
            v = (v >> 1) ^ R
        else:
            v >>= 1
    return z


def _aes_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes, associated: bytes) -> tuple[bytes, bytes]:
    if len(nonce) != 12:
        raise ValueError("Nonce must be 12 bytes")
    key_words = _key_expansion(key)
    h = _aes_encrypt_block(key_words, b"\x00" * 16)
    j0 = nonce + b"\x00\x00\x00\x01"
    icb = _inc32(j0)
    ct = _gctr(key_words, icb, plaintext)
    aad_pad = associated + b"\x00" * ((16 - len(associated) % 16) % 16)
    ct_pad = ct + b"\x00" * ((16 - len(ct) % 16) % 16)
    lengths = (len(associated) * 8).to_bytes(8, "big") + (len(ct) * 8).to_bytes(8, "big")
    s = _ghash(h, aad_pad + ct_pad + lengths)
    e_j0 = _aes_encrypt_block(key_words, j0)
    tag = bytes(a ^ b for a, b in zip(s, e_j0))
    return ct, tag


def _aes_gcm_decrypt(key: bytes, nonce: bytes, ct: bytes, tag: bytes, associated: bytes) -> bytes:
    key_words = _key_expansion(key)
    h = _aes_encrypt_block(key_words, b"\x00" * 16)
    j0 = nonce + b"\x00\x00\x00\x01"
    aad_pad = associated + b"\x00" * ((16 - len(associated) % 16) % 16)
    ct_pad = ct + b"\x00" * ((16 - len(ct) % 16) % 16)
    lengths = (len(associated) * 8).to_bytes(8, "big") + (len(ct) * 8).to_bytes(8, "big")
    s = _ghash(h, aad_pad + ct_pad + lengths)
    e_j0 = _aes_encrypt_block(key_words, j0)
    expected = bytes(a ^ b for a, b in zip(s, e_j0))
    # Constant-time comparison.
    diff = 0
    for a, b in zip(expected, tag):
        diff |= a ^ b
    if diff != 0 or len(expected) != len(tag):
        raise ValueError("Authentication tag mismatch")
    icb = _inc32(j0)
    return _gctr(key_words, icb, ct)
