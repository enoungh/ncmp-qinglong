import json
import os
import requests
from ..utils.logger import Logger

class QinglongService:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.base_url = "http://127.0.0.1:5800"
        self.client_id = os.environ.get("QL_CLIENT_ID")
        self.client_secret = os.environ.get("QL_CLIENT_SECRET")
        self.token = self._get_token()
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _get_token(self):
        """获取青龙 Token（支持应用授权 或 容器内免签读取）"""
        # 方式一：如果用户配置了 Client ID 和 Secret (标准的 OpenAPI 应用调用方式)
        if self.client_id and self.client_secret:
            try:
                res = requests.get(f"{self.base_url}/open/auth/token?client_id={self.client_id}&client_secret={self.client_secret}")
                data = res.json()
                if data.get("code") == 200:
                    self.logger.info("通过青龙应用 Client ID 获取 Token 成功")
                    return data["data"]["token"]
            except Exception as e:
                self.logger.error(f"通过应用获取Token失败: {str(e)}")

        # 方式二：如果脚本就跑在青龙容器内部，直接白嫖本地的 auth.json (免配置)
        auth_paths = [
            "/ql/data/config/auth.json",  # 新版青龙路径
            "/ql/config/auth.json"        # 老版青龙路径
        ]
        for path in auth_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.logger.info("通过读取本地 auth.json 获取 Token 成功")
                        return data.get("token")
                except Exception:
                    pass
        
        self.logger.error("无法获取青龙面板 token")
        return ""

    def update_env(self, name: str, value: str) -> bool:
        """更新或创建青龙环境变量"""
        if not self.token:
            return False
            
        try:
            # 兼容 Open API 和 内部 API 路径
            api_prefix = "/open" if self.client_id else "/api"
            
            # 1. 查询现有的环境变量
            search_url = f"{self.base_url}{api_prefix}/envs?searchValue={name}"
            res = requests.get(search_url, headers=self.headers).json()
            
            envs = res.get("data", [])
            target_env = next((env for env in envs if env.get("name") == name), None)
            
            if target_env:
                # 2. 存在则更新
                update_url = f"{self.base_url}{api_prefix}/envs"
                payload = {
                    "name": name,
                    "value": value,
                    "remarks": target_env.get("remarks", "ncmp自动更新"),
                    "id": target_env.get("id", target_env.get("_id"))
                }
                put_res = requests.put(update_url, headers=self.headers, json=payload).json()
                if put_res.get("code") == 200:
                    self.logger.info(f"成功更新青龙环境变量: {name}")
                    
                    # 更新后必须启用一次，防止它被禁用
                    enable_url = f"{self.base_url}{api_prefix}/envs/enable"
                    requests.put(enable_url, headers=self.headers, json=[payload["id"]])
                    return True
            else:
                # 3. 不存在则创建
                create_url = f"{self.base_url}{api_prefix}/envs"
                payload = [{"name": name, "value": value, "remarks": "ncmp自动创建"}]
                post_res = requests.post(create_url, headers=self.headers, json=payload).json()
                if post_res.get("code") == 200:
                    self.logger.info(f"成功创建青龙环境变量: {name}")
                    return True
                    
            return False
        except Exception as e:
            self.logger.error(f"操作青龙环境变量异常: {str(e)}")
            return False

    def update_cookies(self, cookies: dict) -> bool:
        """批量更新 Cookies"""
        results = [self.update_env(k, v) for k, v in cookies.items()]
        return all(results)