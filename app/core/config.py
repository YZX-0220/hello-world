"""应用配置。

所有可调参数从 .env 文件读取，通过 pydantic-settings 加载到 Settings 单例。
字段名自动对应 .env 中的大写环境变量（不区分大小写、忽略额外变量）。
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# 生产环境判定：APP_ENV 非 dev 时视为生产。
_PRODUCTION_ENVS = {"prod", "production"}


class Settings(BaseSettings):
    """全局配置单例。"""

    # ---- 应用 ----
    app_env: str = "dev"
    app_name: str = "Hello World Backend"
    version: str = "0.1.0"
    app_base_url: str = "http://127.0.0.1:8000"
    frontend_origin: str = "http://127.0.0.1:5173"
    log_level: str = "INFO"
    request_id_header: str = "X-Request-ID"

    # ---- 数据库与 Redis ----
    # 时间语义为【服务器本地时间】，不使用 UTC。
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    sqlite_busy_timeout_ms: int = 30000
    redis_url: str = "redis://127.0.0.1:6379/0"

    # ---- 安全 ----
    # 生产环境必须为强随机值，仍为示例值时拒绝启动（见 ensure_secure）。
    app_secret: str = "dev-please-change-me"
    credential_encryption_keys: str = ""  # Fernet 密钥列表，当前+上一把，逗号分隔
    session_ttl_seconds: int = 604800  # 7 天
    csrf_cookie_name: str = "hw_csrf"
    cookie_secure: bool = False
    session_cookie_name: str = "hw_session"
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # ---- SMTP 验证码邮件 ----
    # email_provider: fake（开发，验证码输出到日志）或 smtp（真实发信，如 qq 邮箱）
    email_provider: str = "fake"
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    smtp_tls: str = "NONE"  # NONE / SSL / STARTTLS
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "hello-world@example.com"
    smtp_connect_timeout: int = 10

    # ---- 文本与搜索 ----
    text_provider: str = "fake"
    text_base_url: str = ""
    text_api_key: str = ""
    text_model: str = ""
    text_timeout: int = 60
    search_enabled: bool = False
    search_provider: str = "fake"  # fake / configured
    search_base_url: str = ""
    search_api_key: str = ""
    search_timeout: int = 15
    search_max_calls: int = 3
    # 长对话摘要：对话内部 user/assistant 消息数超过该值时，把较早历史交给文本模型生成摘要并压缩上下文
    history_summary_threshold: int = 20

    # ---- 视频生成（外部厂商调用）----
    # video_provider: fake（开发，返回可控假状态）或 generic_v1（通用异步 JSON 协议）
    video_provider: str = "fake"
    video_provider_timeout: int = 120          # 单次厂商请求总超时（秒）
    video_connect_timeout: int = 10            # 连接超时（秒）
    video_max_response_bytes: int = 5 * 1024 * 1024  # 厂商响应体大小上限（字节）
    video_poll_interval_seconds: int = 3  # 视频任务主动轮询的建议间隔（秒）

    # ---- 平台自有视频通道（B：平台预置、每用户每天限 1）----
    video_platform_api_key: str = ""  # 平台级密钥（如火山方舟 ARK key）
    video_platform_base_url: str = "https://ark.cn-beijing.volces.com"
    video_platform_model: str = ""  # 平台通道使用的模型/接入点（如 ep-…）

    # ---- 存储与限制 ----
    storage_root: str = "./data"
    upload_dir: str = "./data/uploads"
    video_dir: str = "./data/videos"
    temp_dir: str = "./data/tmp"
    image_max_bytes: int = 10 * 1024 * 1024
    video_max_bytes: int = 524288000
    audio_max_bytes: int = 104857600
    image_max_pixels: int = 12000000
    signed_url_ttl_seconds: int = 600
    result_retention_days: int = 30
    max_video_jobs_per_user: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        """当前环境是否为生产环境。"""
        return self.app_env.strip().lower() in _PRODUCTION_ENVS

    def ensure_secure(self) -> None:
        """生产环境必须校验关键密钥：缺失或有仍为示例值则直接拒绝启动。

        首期仅做强口令/示例值检查；Fernet 密钥列表在视频配置批次再启用。
        """
        if not self.is_production:
            return
        if not self.app_secret or self.app_secret.startswith("dev-"):
            raise RuntimeError("生产环境 APP_SECRET 缺失或仍为示例值，拒绝启动")
        if not self.credential_encryption_keys:
            raise RuntimeError("生产环境 CREDENTIAL_ENCRYPTION_KEYS 缺失，拒绝启动")


settings = Settings()  # 单例
