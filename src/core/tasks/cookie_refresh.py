import os
from typing import Dict, Optional, Tuple

from ...utils.auth import AuthService
from ...utils.qinglong import QinglongService
from ...utils.logger import Logger
from ...utils.notification import NotificationService

class CookieRefreshTask:
    def __init__(self, logger: Logger, notifier: Optional[NotificationService] = None):
        self.logger = logger
        self.notifier = notifier
        self.auth_service = AuthService(logger)
        self.ql_service = QinglongService(logger)
        
    def execute(self) -> bool:
        """执行Cookie刷新任务并写入青龙"""
        try:
            self.logger.info("开始执行Cookie刷新任务")
            
            # 获取登录凭据
            phone = os.environ.get("NETEASE_PHONE")
            password = os.environ.get("NETEASE_PASSWORD")
            md5_password = os.environ.get("NETEASE_MD5_PASSWORD")
            
            if not phone:
                self.logger.error("未设置手机号，无法执行自动登录")
                return False
                
            if not md5_password and not password:
                self.logger.error("未设置密码，无法执行自动登录")
                return False
                
            # 执行登录
            success, cookies = self.auth_service.login(
                phone=phone,
                password=password if not md5_password else None,
                md5_password=md5_password
            )
            
            if not success or not cookies:
                self.logger.error("登录失败，无法获取新的Cookie")
                return False
                
            # 提取需要更新的 Cookie 并写入青龙
            secrets_to_update = {
                "MUSIC_U": cookies.get("Cookie_MUSIC_U", ""),
                "CSRF": cookies.get("Cookie___csrf", "")
            }
            
            update_success = self.ql_service.update_cookies(secrets_to_update)
            
            if update_success:
                self.logger.info("成功更新青龙环境变量中的Cookie")
                if self.notifier:
                    self.notifier.send_notification(
                        "网易云音乐合伙人 - Cookie更新成功",
                        "已成功获取新的Cookie并写入青龙面板"
                    )
                return True
            else:
                self.logger.error("更新青龙面板失败")
                return False
                
        except Exception as e:
            error_message = f"Cookie刷新任务执行异常: {str(e)}"
            self.logger.error(error_message)
            return False