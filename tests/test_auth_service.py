import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyncm import CreateNewSession

from src.utils.auth import AuthService
from src.utils.logger import Logger


class TestAuthService(unittest.TestCase):
    def setUp(self):
        self.auth_service = AuthService(Logger())

    def test_get_cookie_value_handles_duplicate_csrf(self):
        session = CreateNewSession()
        session.cookies.set("__csrf", "manual_csrf")
        session.cookies.set("__csrf", "refreshed_csrf", domain=".music.163.com", path="/")

        cookie_value = self.auth_service._get_cookie_value(session, "__csrf")

        self.assertEqual(cookie_value, "refreshed_csrf")


if __name__ == "__main__":
    unittest.main()
