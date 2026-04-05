import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.tasks.cookie_refresh import CookieRefreshTask
from src.utils.auth import AuthService
from src.utils.logger import Logger


class DummyNotifier:
    def __init__(self):
        self.messages = []

    def send_notification(self, subject, content):
        self.messages.append((subject, content))
        return True


class DummyQinglongService:
    def __init__(self, should_succeed=True):
        self.should_succeed = should_succeed
        self.updated_payload = None

    def update_cookies(self, payload):
        self.updated_payload = payload
        return self.should_succeed


class TestCookieRefreshTask(unittest.TestCase):
    def setUp(self):
        self.logger = Logger()
        self.notifier = DummyNotifier()

        auth_patcher = patch("src.core.tasks.cookie_refresh.AuthService")
        ql_patcher = patch("src.core.tasks.cookie_refresh.QinglongService")
        self.addCleanup(auth_patcher.stop)
        self.addCleanup(ql_patcher.stop)

        self.mock_auth_cls = auth_patcher.start()
        self.mock_ql_cls = ql_patcher.start()

        self.mock_auth_service = self.mock_auth_cls.return_value
        self.mock_auth_service.last_error = ""
        self.mock_ql_service = DummyQinglongService()
        self.mock_ql_cls.return_value = self.mock_ql_service

    @patch.dict(os.environ, {
        "MUSIC_U": "existing_music_u",
        "CSRF": "existing_csrf",
    }, clear=True)
    def test_prefers_existing_login_state(self):
        self.mock_auth_service.refresh_login_state.return_value = (
            True,
            {
                "Cookie_MUSIC_U": "refreshed_music_u",
                "Cookie___csrf": "refreshed_csrf",
                AuthService.SESSION_DUMP_KEY: "session_dump_value",
            },
        )

        task = CookieRefreshTask(self.logger, self.notifier)

        self.assertTrue(task.execute())
        self.mock_auth_service.refresh_login_state.assert_called_once_with(
            session_dump=None,
            music_u="existing_music_u",
            csrf="existing_csrf",
        )
        self.mock_auth_service.login.assert_not_called()
        self.assertEqual(
            self.mock_ql_service.updated_payload,
            {
                "MUSIC_U": "refreshed_music_u",
                "CSRF": "refreshed_csrf",
                "NETEASE_PYNCM_SESSION": "session_dump_value",
            },
        )

    @patch.dict(os.environ, {
        "MUSIC_U": "stale_music_u",
        "CSRF": "stale_csrf",
        "NETEASE_PHONE": "13812345678",
        "NETEASE_MD5_PASSWORD": "0123456789abcdef0123456789abcdef",
    }, clear=True)
    def test_falls_back_to_password_login(self):
        self.mock_auth_service.last_error = "现有登录态不可用"
        self.mock_auth_service.refresh_login_state.return_value = (False, None)
        self.mock_auth_service.login.return_value = (
            True,
            {
                "Cookie_MUSIC_U": "new_music_u",
                "Cookie___csrf": "new_csrf",
                AuthService.SESSION_DUMP_KEY: "new_session_dump",
            },
        )

        task = CookieRefreshTask(self.logger, self.notifier)

        self.assertTrue(task.execute())
        self.mock_auth_service.login.assert_called_once_with(
            phone="13812345678",
            password=None,
            md5_password="0123456789abcdef0123456789abcdef",
        )
        self.assertEqual(
            self.mock_ql_service.updated_payload,
            {
                "MUSIC_U": "new_music_u",
                "CSRF": "new_csrf",
                "NETEASE_PYNCM_SESSION": "new_session_dump",
            },
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_stops_when_no_valid_state_or_credentials(self):
        task = CookieRefreshTask(self.logger, self.notifier)

        self.assertFalse(task.execute())
        self.mock_auth_service.refresh_login_state.assert_not_called()
        self.mock_auth_service.login.assert_not_called()
        self.assertIsNone(self.mock_ql_service.updated_payload)


if __name__ == "__main__":
    unittest.main()
