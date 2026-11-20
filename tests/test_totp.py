import unittest

from core.totp import generate_totp, normalize_totp_secret, totp_seconds_remaining


class TotpTests(unittest.TestCase):
    def test_rfc6238_vector(self):
        # RFC 6238 test secret: "12345678901234567890" in Base32.
        secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        self.assertEqual(generate_totp(secret, timestamp=59), "287082")

    def test_otpauth_uri_and_remaining_time(self):
        uri = "otpauth://totp/Test:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=Test"
        self.assertEqual(normalize_totp_secret(uri), "JBSWY3DPEHPK3PXP")
        self.assertEqual(totp_seconds_remaining(timestamp=61), 29)


if __name__ == "__main__":
    unittest.main()
