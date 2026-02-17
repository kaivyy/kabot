"""Configuration schema using Pydantic."""

from __future__ import annotations

from typing import Any
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class WhatsAppConfig(BaseModel):
    """WhatsApp channel configuration."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers


class TelegramConfig(BaseModel):
    """Telegram channel configuration."""
    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames
    proxy: str | None = None  # HTTP/SOCKS5 proxy URL, e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:1080"


class FeishuConfig(BaseModel):
    """Feishu/Lark channel configuration using WebSocket long connection."""
    enabled: bool = False
    app_id: str = ""  # App ID from Feishu Open Platform
    app_secret: str = ""  # App Secret from Feishu Open Platform
    encrypt_key: str = ""  # Encrypt Key for event subscription (optional)
    verification_token: str = ""  # Verification Token for event subscription (optional)
    allow_from: list[str] = Field(default_factory=list)  # Allowed user open_ids


class DingTalkConfig(BaseModel):
    """DingTalk channel configuration using Stream mode."""
    enabled: bool = False
    client_id: str = ""  # AppKey
    client_secret: str = ""  # AppSecret
    allow_from: list[str] = Field(default_factory=list)  # Allowed staff_ids


class DiscordConfig(BaseModel):
    """Discord channel configuration."""
    enabled: bool = False
    token: str = ""  # Bot token from Discord Developer Portal
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377  # GUILDS + GUILD_MESSAGES + DIRECT_MESSAGES + MESSAGE_CONTENT

class EmailConfig(BaseModel):
    """Email channel configuration (IMAP inbound + SMTP outbound)."""
    enabled: bool = False
    consent_granted: bool = False  # Explicit owner permission to access mailbox data

    # IMAP (receive)
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_mailbox: str = "INBOX"
    imap_use_ssl: bool = True

    # SMTP (send)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    from_address: str = ""

    # Behavior
    auto_reply_enabled: bool = True  # If false, inbound email is read but no automatic reply is sent
    poll_interval_seconds: int = 30
    mark_seen: bool = True
    max_body_chars: int = 12000
    subject_prefix: str = "Re: "
    allow_from: list[str] = Field(default_factory=list)  # Allowed sender email addresses


class SlackDMConfig(BaseModel):
    """Slack DM policy configuration."""
    enabled: bool = True
    policy: str = "open"  # "open" or "allowlist"
    allow_from: list[str] = Field(default_factory=list)  # Allowed Slack user IDs


class SlackConfig(BaseModel):
    """Slack channel configuration."""
    enabled: bool = False
    mode: str = "socket"  # "socket" supported
    webhook_path: str = "/slack/events"
    bot_token: str = ""  # xoxb-...
    app_token: str = ""  # xapp-...
    user_token_read_only: bool = True
    group_policy: str = "mention"  # "mention", "open", "allowlist"
    group_allow_from: list[str] = Field(default_factory=list)  # Allowed channel IDs if allowlist
    dm: SlackDMConfig = Field(default_factory=SlackDMConfig)


class QQConfig(BaseModel):
    """QQ channel configuration using botpy SDK."""
    enabled: bool = False
    app_id: str = ""  # 机器人 ID (AppID) from q.qq.com
    secret: str = ""  # 机器人密钥 (AppSecret) from q.qq.com
    allow_from: list[str] = Field(default_factory=list)  # Allowed user openids (empty = public access)


class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    qq: QQConfig = Field(default_factory=QQConfig)


class AgentDefaults(BaseModel):
    """Default agent configuration."""
    workspace: str = "~/.kabot/workspace"
    model: str = "anthropic/claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 0.7
    max_tool_iterations: int = 20


class AgentConfig(BaseModel):
    """Configuration for a single agent instance."""
    id: str
    name: str = ""
    model: str | None = None
    workspace: str | None = None
    default: bool = False


class AgentsConfig(BaseModel):
    """Agent configuration."""
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)
    enable_hybrid_memory: bool = True
    agents: list[AgentConfig] = Field(default_factory=list)


class AuthProfile(BaseModel):
    """Authentication profile for a specific account."""
    name: str = "default"
    api_key: str = ""
    oauth_token: str | None = None
    refresh_token: str | None = None       # NEW: for auto-refresh
    expires_at: int | None = None          # NEW: ms since epoch
    token_type: str | None = None          # NEW: "oauth" | "api_key" | "token"
    client_id: str | None = None           # NEW: OAuth client ID
    setup_token: str | None = None
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None

    def is_expired(self) -> bool:
        """Check if the OAuth token has expired."""
        if self.token_type != "oauth" or not self.expires_at:
            return False  # API keys don't expire
        import time
        return int(time.time() * 1000) >= self.expires_at


class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    api_key: str = ""  # Legacy/Primary key
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None  # Custom headers (e.g. APP-Code for AiHubMix) 
    fallbacks: list[str] = Field(default_factory=list)
    
    # Multi-profile support
    profiles: dict[str, AuthProfile] = Field(default_factory=dict)
    active_profile: str = "default"

class ProvidersConfig(BaseModel):
    """Configuration for LLM providers."""
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)  # 阿里云通义千问
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax: ProviderConfig = Field(default_factory=ProviderConfig)
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)  # AiHubMix API gateway
    letta: ProviderConfig = Field(default_factory=ProviderConfig)  # Letta stateful agent platform


class GatewayConfig(BaseModel):
    """Gateway/server configuration."""
    host: str = "0.0.0.0"
    port: int = 18790
    bind_mode: str = "local" # loopback, local, public
    auth_token: str = ""     # Bearer token for API access
    tailscale: bool = False  # Enable Tailscale exposure


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""
    api_key: str = ""  # Brave Search API key
    max_results: int = 5


class WebToolsConfig(BaseModel):
    """Web tools configuration."""
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class DockerConfig(BaseModel):
    """Docker sandbox configuration."""
    enabled: bool = False
    image: str = "python:3.11-alpine"
    memory_limit: str = "512m"
    cpu_limit: float = 0.5
    network_disabled: bool = False


class ExecToolConfig(BaseModel):
    """Shell exec tool configuration."""
    timeout: int = 60
    docker: DockerConfig = Field(default_factory=DockerConfig)


class ToolsConfig(BaseModel):
    """Tools configuration."""
    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = False  # If true, restrict all tool access to workspace directory


class LoggingConfig(BaseModel):
    """Logging configuration."""
    enabled: bool = True
    level: str = "INFO"
    file_enabled: bool = True
    file_path: str = "~/.kabot/logs/kabot.log"
    rotation: str = "10 MB"
    retention: str = "7 days"
    db_enabled: bool = True
    db_retention_days: int = 30


class Config(BaseSettings):
    """Root configuration for kabot."""
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    skills: dict[str, dict[str, Any]] = Field(default_factory=dict)
    
    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()
    
    def _match_provider(self, model: str | None = None) -> tuple["ProviderConfig | None", str | None]:
        """Match provider config and its registry name. Returns (config, spec_name)."""
        from kabot.providers.registry import PROVIDERS
        model_lower = (model or self.agents.defaults.model).lower()

        def has_credentials(p: "ProviderConfig") -> bool:
            """Check if provider has any credentials (api_key or profiles with tokens)."""
            if p.api_key:
                return True
            # Check if any profile has credentials
            for profile in p.profiles.values():
                if profile.api_key or profile.oauth_token:
                    return True
            return False

        # Match by keyword (order follows PROVIDERS registry)
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and any(kw in model_lower for kw in spec.keywords) and has_credentials(p):
                return p, spec.name

        # Fallback: gateways first, then others (follows registry order)
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and has_credentials(p):
                return p, spec.name
        return None, None

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Get matched provider config (api_key, api_base, extra_headers). Falls back to first available."""
        p, _ = self._match_provider(model)
        return p

    def get_provider_name(self, model: str | None = None) -> str | None:
        """Get the registry name of the matched provider (e.g. "deepseek", "openrouter")."""
        _, name = self._match_provider(model)
        return name

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model. Supports profiles with legacy fallback."""
        p = self.get_provider(model)
        if not p:
            return None

        # Try active profile first
        if p.active_profile in p.profiles:
            profile = p.profiles[p.active_profile]

            # If OAuth token is expired, log a warning (sync path can't refresh)
            if profile.is_expired():
                from loguru import logger
                logger.warning(f"OAuth token for {p.active_profile} is expired. "
                              "Use async get_api_key_async() for auto-refresh.")

            if profile.api_key:
                return profile.api_key
            if profile.oauth_token:
                return profile.oauth_token

        # Legacy fallback
        return p.api_key

    async def get_api_key_async(self, model: str | None = None) -> str | None:
        """Async version of get_api_key with OAuth auto-refresh."""
        from kabot.auth.refresh import TokenRefreshService

        p = self.get_provider(model)
        if not p:
            return None

        if p.active_profile in p.profiles:
            profile = p.profiles[p.active_profile]

            # Auto-refresh expired OAuth tokens
            if profile.is_expired() and profile.refresh_token:
                provider_name = self._provider_name_for(model) or ""
                service = TokenRefreshService()
                updated = await service.refresh(provider_name, profile)
                if updated:
                    # Update in-memory config
                    p.profiles[p.active_profile] = updated
                    profile = updated

            if profile.api_key:
                return profile.api_key
            if profile.oauth_token:
                return profile.oauth_token

        # Legacy fallback
        return p.api_key

    def _provider_name_for(self, model: str | None) -> str | None:
        """Extract provider name from model string."""
        if not model:
            return None
        # Handle "provider/model" format
        if "/" in model:
            return model.split("/")[0]
        # Try to match against known providers
        _, name = self._match_provider(model)
        return name

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL for the given model. Supports profiles."""
        from kabot.providers.registry import find_by_name
        p, name = self._match_provider(model)
        if not p:
            return None
            
        # Try active profile first
        if p.active_profile in p.profiles:
            profile = p.profiles[p.active_profile]
            if profile.api_base:
                return profile.api_base
                
        if p.api_base:
            return p.api_base
            
        if name:
            spec = find_by_name(name)
            if spec and spec.is_gateway and spec.default_api_base:
                return spec.default_api_base
        return None

    class Config:
        env_prefix = "NANOBOT_"
        env_nested_delimiter = "__"
