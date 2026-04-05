import os
from typing import Optional

from ...utils.auth import AuthService
from ...utils.qinglong import QinglongService
from ...utils.logger import Logger
from ...utils.notification import NotificationService

class CookieRefreshTask:
    SESSION_ENV_NAME = "NETEASE_PYNCM_SESSION"
    AUTH_STATE_SESSION_KEY = "Session_Dump"

    def __init__(self, logger: Logger, notifier: Optional[NotificationService] = None):
        self.logger = logger
        self.notifier = notifier
        self.auth_service = AuthService(logger)
        self.ql_service = QinglongService(logger)
        
    def execute(self) -> bool:
        """执行Cookie刷新任务并写入青龙"""
        try:
            self.logger.info("开始执行Cookie刷新任务")

            current_music_u = os.environ.get("MUSIC_U")
            current_csrf = os.environ.get("CSRF")
            session_dump = os.environ.get(self.SESSION_ENV_NAME)

            if not (session_dump or (current_music_u and current_csrf)):
                self.logger.error("未设置可用的登录态，至少需要 MUSIC_U 和 CSRF，或 NETEASE_PYNCM_SESSION")
                return False

            self.logger.info("仅使用现有登录态续期 Cookie，不再执行密码登录")
            success, auth_state = self.auth_service.refresh_login_state(
                session_dump=session_dump,
                music_u=current_music_u,
                csrf=current_csrf,
            )

            if not success or not auth_state:
                self.logger.error(self.auth_service.last_error or "现有登录态续期失败，无法获取新的Cookie")
                return False

            secrets_to_update = {
                "MUSIC_U": auth_state.get("Cookie_MUSIC_U", ""),
                "CSRF": auth_state.get("Cookie___csrf", ""),
            }

            session_dump_value = auth_state.get(self.AUTH_STATE_SESSION_KEY, "")
            if session_dump_value:
                secrets_to_update[self.SESSION_ENV_NAME] = session_dump_value

            update_success = self.ql_service.update_cookies(secrets_to_update)

            if update_success:
                self.logger.info("成功更新青龙环境变量中的Cookie")
                if self.notifier:
                    self.notifier.send_notification(
                        "网易云音乐合伙人 - Cookie更新成功",
                        "已成功续期或刷新登录态，并写入青龙面板"
                    )
                return True
            else:
                self.logger.error("更新青龙面板失败")
                return False

        except Exception as e:
            error_message = f"Cookie刷新任务执行异常: {str(e)}"
            self.logger.error(error_message)
            return False
