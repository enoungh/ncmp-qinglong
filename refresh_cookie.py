#!/usr/bin/env python3
# coding: utf-8
# new Env("网易云音乐账号刷新Cookie")
# cron: 0 22 * * 0

import os
import sys
# 确保在青龙容器中运行时能正确导入 src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.tasks.cookie_refresh import CookieRefreshTask
from src.utils.config import Config
from src.utils.logger import Logger
from src.utils.notification import NotificationService

def main():
    try:
        # 初始化基础组件
        config = Config()
        logger = Logger()
        notifier = NotificationService(config, logger)
        
        # 环境变量兜底
        if not os.environ.get("NETEASE_PHONE") and config.get("netease_phone"):
            os.environ["NETEASE_PHONE"] = config.get("netease_phone")
            
        if not os.environ.get("NETEASE_PASSWORD") and config.get("netease_password"):
            os.environ["NETEASE_PASSWORD"] = config.get("netease_password")
            
        if not os.environ.get("NETEASE_MD5_PASSWORD") and config.get("netease_md5_password"):
            os.environ["NETEASE_MD5_PASSWORD"] = config.get("netease_md5_password")
        
        # 初始化并执行刷新任务
        task = CookieRefreshTask(logger, notifier)
        success = task.execute()
        
        # 处理执行结果
        if success:
            logger.info("✅ Cookie刷新成功")
        else:
            logger.error("❌ Cookie刷新失败")
            
    except Exception as e:
        error_message = f"Cookie刷新程序异常: {str(e)}"
        logger = Logger()
        logger.error(error_message)

if __name__ == "__main__":
    main()