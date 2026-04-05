from typing import Dict, Optional, Tuple

from ..utils.logger import Logger
from ..validators.cookie import CookieValidator

try:
    from pyncm import CreateNewSession, DumpSessionAsString, LoadSessionFromString
    from pyncm.apis.login import LoginRefreshToken

    PYNCM_AVAILABLE = True
except ImportError:
    PYNCM_AVAILABLE = False


class AuthService:
    SESSION_DUMP_KEY = "Session_Dump"

    def __init__(self, logger: Logger):
        self.logger = logger
        self.last_error = ""

        if not PYNCM_AVAILABLE:
            self.logger.error("pyncm 库未安装，无法使用登录功能")
            raise ImportError("pyncm 库未安装，请执行 pip install pyncm")

    def _set_error(self, message: str) -> None:
        self.last_error = message
        self.logger.error(message)

    def _build_session(
        self,
        session_dump: Optional[str] = None,
        music_u: Optional[str] = None,
        csrf: Optional[str] = None,
    ):
        if session_dump:
            try:
                session = LoadSessionFromString(session_dump)
                self.logger.debug("已从持久化的 pyncm session 恢复登录态")
                return session
            except Exception as exc:
                self.logger.warning(f"恢复持久化 session 失败，将退回 Cookie 模式: {exc}")

        session = CreateNewSession()
        if music_u:
            session.cookies.set("MUSIC_U", music_u)
        if csrf:
            session.cookies.set("__csrf", csrf)
            session.csrf_token = csrf
        return session

    def _get_cookie_value(self, session, name: str) -> Optional[str]:
        candidates = [cookie for cookie in session.cookies if cookie.name == name]
        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0].value

        preferred_domains = (
            ".music.163.com",
            "music.163.com",
            ".interface.music.163.com",
            "interface.music.163.com",
            "",
        )

        def sort_key(cookie):
            domain = cookie.domain or ""
            try:
                domain_rank = preferred_domains.index(domain)
            except ValueError:
                domain_rank = len(preferred_domains)

            # 优先保留更具体、更新的服务端 cookie，而不是最初手工注入的裸 cookie。
            return (domain_rank, 0 if domain else 1, -len(domain), -(len(cookie.path or "/")))

        selected = sorted(candidates, key=sort_key)[0]
        domains = ", ".join(cookie.domain or "<host-only>" for cookie in candidates)
        self.logger.warning(
            f"检测到多个同名 Cookie: {name}，已自动选择 domain={selected.domain or '<host-only>'}。候选域名: {domains}"
        )
        return selected.value

    def _extract_auth_state(self, session) -> Optional[Dict[str, str]]:
        music_u_cookie = self._get_cookie_value(session, "MUSIC_U")
        csrf_cookie = self._get_cookie_value(session, "__csrf")

        if not music_u_cookie:
            self._set_error("未能从会话中获取 MUSIC_U cookie")
            return None

        if not csrf_cookie:
            self._set_error("未能从会话中获取 __csrf cookie")
            return None

        session_dump = DumpSessionAsString(session)
        self.logger.debug(
            f"成功提取登录态: MUSIC_U={music_u_cookie[:10]}..., __csrf={csrf_cookie}"
        )
        self.logger.debug(f"会话信息: {session_dump[:50]}...")
        return {
            "Cookie_MUSIC_U": music_u_cookie,
            "Cookie___csrf": csrf_cookie,
            self.SESSION_DUMP_KEY: session_dump,
        }

    def _validate_session(self, session) -> Tuple[bool, str]:
        validator = CookieValidator(session, self.logger)
        return validator.validate()

    def refresh_login_state(
        self,
        session_dump: Optional[str] = None,
        music_u: Optional[str] = None,
        csrf: Optional[str] = None,
    ) -> Tuple[bool, Optional[Dict[str, str]]]:
        """使用已有登录态续期 Cookie。"""
        self.last_error = ""

        if not session_dump and not (music_u and csrf):
            self._set_error("缺少可用的历史登录态，无法执行免登录续期")
            return False, None

        try:
            session = self._build_session(session_dump=session_dump, music_u=music_u, csrf=csrf)

            is_valid, message = self._validate_session(session)
            if not is_valid:
                self._set_error(f"现有登录态不可用: {message}")
                return False, None

            self.logger.info("现有登录态有效，尝试续期 Cookie")
            refresh_result = LoginRefreshToken(session=session)

            if refresh_result.get("code") != 200:
                refresh_message = refresh_result.get("message", "刷新登录令牌失败")
                self.logger.warning(f"续期接口返回异常，保留当前有效登录态: {refresh_message}")
                return True, self._extract_auth_state(session)

            session.csrf_token = self._get_cookie_value(session, "__csrf") or session.csrf_token

            refreshed_valid, refreshed_message = self._validate_session(session)
            if not refreshed_valid:
                self._set_error(f"续期后的登录态校验失败: {refreshed_message}")
                return False, None

            auth_state = self._extract_auth_state(session)
            if not auth_state:
                return False, None

            self.logger.info("使用现有登录态续期成功")
            return True, auth_state

        except Exception as exc:
            self._set_error(f"使用现有登录态刷新 Cookie 失败: {exc}")
            return False, None
