# ncmp (青龙面板版)

基于 [ACAne0320/ncmp](https://github.com/ACAne0320/ncmp) 调整的网易云音乐合伙人自动化脚本，适配青龙面板运行。

## 功能

- 自动完成每日评分任务
- 支持青龙环境变量读取
- 支持在青龙容器内读取 `auth.json` 更新环境变量
- Cookie 失效或任务异常时发送邮件通知
- 仅使用现有登录态续期 Cookie，不再执行手机号密码登录

## 首次准备

首次使用需要手动抓取一次 Cookie：

1. 在常用设备浏览器登录 [网易云音乐网页版](https://music.163.com/)
2. 完成必要的安全验证
3. 打开开发者工具，在 `https://music.163.com/` 请求头的 `Cookie` 中取出 `MUSIC_U` 和 `__csrf`
4. 写入青龙环境变量

## 青龙配置

### 依赖

安装 Python 依赖：

```text
requests pycryptodome pyncm
```

### 环境变量

必填：

- `MUSIC_U`
- `CSRF`

可选：

- `NETEASE_PYNCM_SESSION`
- `SCORE`
- `FULL_EXTRA_TASKS`
- `WAIT_TIME_MIN`
- `WAIT_TIME_MAX`
- `NOTIFY_EMAIL`
- `EMAIL_PASSWORD`
- `SMTP_SERVER`
- `SMTP_PORT`

说明：

- `NETEASE_PYNCM_SESSION` 不建议手动填写。首次成功续期后，脚本会自动写回。
- `refresh_cookie.py` 现在只会使用现有登录态续期；如果 `MUSIC_U` 和 `CSRF` 已失效，脚本不会再尝试手机号密码登录。

### 定时任务

拉库任务示例：

```bash
ql repo https://github.com/enoungh/ncmp-qinglong.git "main.py|refresh_cookie.py" "tests" "src" "main"
```

评分任务：

```text
task 你的GitHub用户名_ncmp/main.py
```

刷新任务：

```text
task 你的GitHub用户名_ncmp/refresh_cookie.py
```

## 风控说明

本项目不会绕过图形验证码，也不再执行手机号密码登录。

如果日志提示现有登录态失效、需要安全验证，或续期失败，你需要：

1. 在常用设备上重新登录网易云并完成验证
2. 重新抓取 `MUSIC_U` 和 `__csrf`
3. 覆盖青龙中的 `MUSIC_U`、`CSRF`
4. 删除或清空旧的 `NETEASE_PYNCM_SESSION`
5. 再运行一次 `refresh_cookie.py`

## 声明

仅供学习交流使用，使用风险自负。
