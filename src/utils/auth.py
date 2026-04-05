import hashlib
from typing import Dict, Optional, Tuple

from ..utils.logger import Logger
from ..validators.cookie import CookieValidator

try:
    from pyncm import CreateNewSession, DumpSessionAsString, LoadSessionFromString
    from pyncm.apis.login import LoginRefreshToken, LoginViaCellphone

    PYNCM_AVAILABLE = True
except ImportError:
    PYNCM_AVAILABLE = False


class AuthService:
    SESSION_DUMP_KEY = "Session_Dump"
    RISK_CONTROL_HINT = (
        "触发网易云安全验证，脚本不会绕过验证码。"
        "请先在常用设备上手动完成一次验证，再重新运行刷新任务。"
    )

    def __init__(self, logger: Logger):
        self.logger = logger
        self.last_error = ""

        if not PYNCM_AVAILABLE:
            self.logger.error("pyncm 库未安装，无法使用登录功能")
            raise ImportError("pyncm 库未安装，请执行 pip install pyncm")

    def _set_error(self, message: str) -> None:
        self.last_error = message
        self.logger.error(message)

    def _hash_password(self, password: str) -> str:
        """将明文密码转换为 MD5 哈希"""
        return hashlib.md5(password.encode()).hexdigest()

    def _mask_phone(self, phone: str) -> str:
        if len(phone) < 7:
            return phone
        return f"{phone[:3]}****{phone[-4:]}"

    def _looks_like_risk_control(self, message: str) -> bool:
        lowered = message.lower()
        keywords = ("验证码", "安全验证", "滑块", "拼图", "captcha", "verify", "risk")
        return any(keyword in lowered for keyword in keywords)

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

    def _extract_auth_state(self, session) -> Optional[Dict[str, str]]:
        music_u_cookie = session.cookies.get("MUSIC_U")
        csrf_cookie = session.cookies.get("__csrf")

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
        """优先使用已有登录态续期，避免频繁触发高风险密码登录。"""
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

            session.csrf_token = session.cookies.get("__csrf") or session.csrf_token

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

    def login(
        self,
        phone: str,
        password: Optional[str] = None,
        md5_password: Optional[str] = None,
    ) -> Tuple[bool, Optional[Dict[str, str]]]:
        """
        通过手机号和密码登录获取 Cookie

        Args:
            phone: 手机号
            password: 明文密码（与md5_password二选一）
            md5_password: MD5加密后的密码（与password二选一）

        Returns:
            (成功状态, Cookie字典)
        """
        self.last_error = ""

        try:
            self.logger.info(f"尝试使用 pyncm 登录账号: {self._mask_phone(phone)}")

            if md5_password:
                password_hash = md5_password
                self.logger.debug("使用提供的MD5密码登录")
            elif password:
                password_hash = self._hash_password(password)
                self.logger.debug("使用明文密码（转换为MD5）登录")
            else:
                self._set_error("未提供密码，无法登录")
                return False, None

            session = CreateNewSession()
            result = LoginViaCellphone(
                phone,
                passwordHash=password_hash,
                ctcode=86,
                session=session,
            )

            if result.get("code") != 200:
                error_msg = result.get("message", "未知错误")
                self._set_error(f"登录失败: {error_msg}")
                return False, None

            session.csrf_token = session.cookies.get("__csrf") or session.csrf_token

            is_valid, message = self._validate_session(session)
            if not is_valid:
                self._set_error(f"登录成功但登录态校验失败: {message}")
                return False, None

            auth_state = self._extract_auth_state(session)
            if not auth_state:
                return False, None

            self.logger.info("登录成功并获取Cookie")
            return True, auth_state

        except Exception as exc:
            raw_message = str(exc)
            if self._looks_like_risk_control(raw_message):
                self._set_error(self.RISK_CONTROL_HINT)
            else:
                self._set_error(f"pyncm 登录过程发生异常: {raw_message}")
            return False, None
