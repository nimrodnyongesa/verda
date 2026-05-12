import unittest

from wakili.services.encryption import decrypt, encrypt


class EncryptionTests(unittest.TestCase):
    def test_round_trip(self):
        plaintext = b"Verda case bundle smoke test " * 50
        blob = encrypt(plaintext, "passphrase-of-the-day")
        self.assertTrue(blob.startswith(b"WAKILI1"))
        self.assertEqual(decrypt(blob, "passphrase-of-the-day"), plaintext)

    def test_wrong_passphrase_is_rejected(self):
        blob = encrypt(b"hello", "right-passphrase")
        with self.assertRaises(ValueError):
            decrypt(blob, "wrong-passphrase")

    def test_truncated_blob_is_rejected(self):
        blob = encrypt(b"hello", "passphrase-x")
        with self.assertRaises(ValueError):
            decrypt(blob[:-5], "passphrase-x")

    def test_known_vector_round_trip(self):
        # Two encryptions with the same passphrase produce different blobs
        # (different random salts/nonces) but both decrypt back to plaintext.
        a = encrypt(b"abc", "p")
        b = encrypt(b"abc", "p")
        self.assertNotEqual(a, b)
        self.assertEqual(decrypt(a, "p"), b"abc")
        self.assertEqual(decrypt(b, "p"), b"abc")


if __name__ == "__main__":
    unittest.main()
