"""Configuration schema using Pydantic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
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
    app_id: str = ""  # æœºå™¨äºº ID (AppID) from q.qq.com
    secret: str = ""  # æœºå™¨äººå¯†é’¥ (AppSecret) from q.qq.com
    allow_from: list[str] = Field(default_factory=list)  # Allowed user openids (empty = public access)


class SignalConfig(BaseModel):
    """Signal channel configuration via bridge websocket."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3011"
    allow_from: list[str] = Field(default_factory=list)


class MatrixConfig(BaseModel):
    """Matrix channel configuration via bridge websocket."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3012"
    allow_from: list[str] = Field(default_factory=list)


class TeamsConfig(BaseModel):
    """Microsoft Teams channel configuration via bridge websocket."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3013"
    allow_from: list[str] = Field(default_factory=list)


class GoogleChatConfig(BaseModel):
    """Google Chat channel configuration via bridge websocket."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3014"
    allow_from: list[str] = Field(default_factory=list)


class MattermostConfig(BaseModel):
    """Mattermost channel configuration via bridge websocket."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3015"
    allow_from: list[str] = Field(default_factory=list)


class WebexConfig(BaseModel):
    """Webex channel configuration via bridge websocket."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3016"
    allow_from: list[str] = Field(default_factory=list)


class LineConfig(BaseModel):
    """LINE channel configuration via bridge websocket."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3017"
    allow_from: list[str] = Field(default_factory=list)


class ChannelInstance(BaseModel):
    """A single channel instance configuration.

    Enables running multiple bots per platform (e.g., 4 Telegram bots, 4 Discord bots).
    Each instance has a unique ID and can be bound to a specific agent.
    """
    id: str  # Unique identifier (e.g., "work_bot", "personal_bot")
    type: str  # Channel type ("telegram", "discord", "whatsapp", etc.)
    enabled: bool = True
    config: dict[str, Any]  # Type-specific configuration
    agent_binding: str | None = None  # Optional agent binding


class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""
    # Legacy single-instance configs (backward compatibility)
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    qq: QQConfig = Field(default_factory=QQConfig)
    signal: SignalConfig = Field(default_factory=SignalConfig)
    matrix: MatrixConfig = Field(default_factory=MatrixConfig)
    teams: TeamsConfig = Field(default_factory=TeamsConfig)
    google_chat: GoogleChatConfig = Field(default_factory=GoogleChatConfig)
    mattermost: MattermostConfig = Field(default_factory=MattermostConfig)
    webex: WebexConfig = Field(default_factory=WebexConfig)
    line: LineConfig = Field(default_factory=LineConfig)

    # Multi-instance support
    instances: list[ChannelInstance] = Field(default_factory=list)
    adapters: dict[str, bool] = Field(default_factory=dict)


class SubagentDefaults(BaseModel):
    """Sub-agent safety limits."""

    max_spawn_depth: int = 1
    max_children_per_agent: int = 5
    archive_after_minutes: int = 60


class HeartbeatDefaults(BaseModel):
    """Heartbeat delivery and scheduling configuration."""

    enabled: bool = True
    interval_minutes: int = 30
    startup_delay_seconds: int = 120
    target_channel: str = "last"
    target_to: str = ""
    active_hours_start: str = ""
    active_hours_end: str = ""


class AgentDefaults(BaseModel):
    """Default agent configuration."""
    workspace: str = "~/.kabot/workspace"
    model: str | AgentModelConfig = "anthropic/claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 0.7
    max_tool_iterations: int = 20
    subagents: SubagentDefaults = Field(default_factory=SubagentDefaults)
    heartbeat: HeartbeatDefaults = Field(default_factory=HeartbeatDefaults)


class AgentModelConfig(BaseModel):
    """Model configuration for an agent."""
    primary: str
    fallbacks: list[str] = Field(default_factory=list)


class AgentSandboxConfig(BaseModel):
    """Sandbox configuration for an agent."""
    enabled: bool = True
    docker_image: str | None = None
    memory_limit: str | None = None
    cpu_limit: float | None = None
    network_disabled: bool = False


class AgentToolsConfig(BaseModel):
    """Tools configuration for an agent."""
    allowlist: list[str] | None = None
    denylist: list[str] | None = None


class AgentConfig(BaseModel):
    """Configuration for a single agent instance."""
    id: str
    name: str = ""
    model: str | AgentModelConfig | None = None
    workspace: str | None = None
    agent_dir: str | None = None
    default: bool = False
    skills: list[str] | None = None
    sandbox: AgentSandboxConfig | None = None
    tools: AgentToolsConfig | None = None
    memory_search: bool | None = None
    human_delay: int | None = None
    heartbeat: int | None = None
    identity: dict[str, Any] | None = None
    group_chat: dict[str, Any] | None = None
    subagents: dict[str, Any] | None = None


class PeerMatch(BaseModel):
    """Peer matching configuration."""
    kind: str  # "direct", "group", "channel"
    id: str


class AgentBindingMatch(BaseModel):
    """Match criteria for agent binding."""
    channel: str | None = None
    account_id: str | None = None  # Supports "*" wildcard
    peer: PeerMatch | None = None
    guild_id: str | None = None  # Discord guild
    team_id: str | None = None  # Slack team


class AgentBinding(BaseModel):
    """Binding configuration to route messages to specific agents."""
    agent_id: str
    match: AgentBindingMatch


class SessionConfig(BaseModel):
    """Session management configuration."""
    dm_scope: str = "main"  # "main", "per-peer", "per-channel-peer", "per-account-channel-peer"
    identity_links: dict[str, list[str]] = Field(default_factory=dict)


class AgentsConfig(BaseModel):
    """Agent configuration."""
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)
    enable_hybrid_memory: bool = True
    agents: list[AgentConfig] = Field(default_factory=list)
    bindings: list[AgentBinding] = Field(default_factory=list)
    session: SessionConfig = Field(default_factory=SessionConfig)


class AuthProfile(BaseModel):
    """Authentication profile for a specific account."""
    name: str = "default"
    api_key: str = ""
    oauth_token: str | None = None
    refresh_token: str | None = None       # NEW: for auto-refresh
    expires_at: int | None = None          # NEW: ms since epoch
    token_type: str | None = None          # NEW: "oauth" | "api_key" | "token"
    client_id: str | None = None           # NEW: OAuth client ID
    client_secret: str | None = None       # Optional OAuth client secret (provider-specific)
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
    setup_token: str | None = None
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
    openai_codex: ProviderConfig = Field(default_factory=ProviderConfig)
    mistral: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    kilocode: ProviderConfig = Field(default_factory=ProviderConfig)
    together: ProviderConfig = Field(default_factory=ProviderConfig)
    venice: ProviderConfig = Field(default_factory=ProviderConfig)
    huggingface: ProviderConfig = Field(default_factory=ProviderConfig)
    qianfan: ProviderConfig = Field(default_factory=ProviderConfig)
    nvidia: ProviderConfig = Field(default_factory=ProviderConfig)
    xai: ProviderConfig = Field(default_factory=ProviderConfig)
    cerebras: ProviderConfig = Field(default_factory=ProviderConfig)
    opencode: ProviderConfig = Field(default_factory=ProviderConfig)
    xiaomi: ProviderConfig = Field(default_factory=ProviderConfig)
    volcengine: ProviderConfig = Field(default_factory=ProviderConfig)
    byteplus: ProviderConfig = Field(default_factory=ProviderConfig)
    synthetic: ProviderConfig = Field(default_factory=ProviderConfig)
    cloudflare_ai_gateway: ProviderConfig = Field(default_factory=ProviderConfig)
    vercel_ai_gateway: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)  # é˜¿é‡Œäº‘é€šä¹‰åƒé—®
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax: ProviderConfig = Field(default_factory=ProviderConfig)
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)  # AiHubMix API gateway
    letta: ProviderConfig = Field(default_factory=ProviderConfig)  # Letta stateful agent platform


class GatewaySecurityHeadersConfig(BaseModel):
    strict_transport_security: bool = False
    strict_transport_security_value: str = "max-age=31536000; includeSubDomains"


class GatewayHttpConfig(BaseModel):
    security_headers: GatewaySecurityHeadersConfig = Field(default_factory=GatewaySecurityHeadersConfig)


class GatewayConfig(BaseModel):
    """Gateway/server configuration."""
    host: str = "0.0.0.0"
    port: int = 18790
    bind_mode: str = "local" # loopback, local, public
    auth_token: str = ""     # Bearer token for API access
    tailscale: bool = False  # Enable Tailscale exposure
    http: GatewayHttpConfig = Field(default_factory=GatewayHttpConfig)


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""
    api_key: str = ""  # Brave Search API key (default provider)
    max_results: int = 5
    provider: str = "brave"  # "brave" | "perplexity" | "grok" | "kimi" | "auto"
    cache_ttl_minutes: int = 5
    perplexity_api_key: str = ""
    perplexity_model: str = "sonar-pro"
    xai_api_key: str = ""
    xai_model: str = "grok-3-mini"
    kimi_api_key: str = ""
    kimi_model: str = "moonshot-v1-8k"


class WebFetchConfig(BaseModel):
    """Web fetch tool configuration."""
    firecrawl_api_key: str = ""
    firecrawl_base_url: str = "https://api.firecrawl.dev"
    cache_ttl_minutes: int = 5
    max_response_bytes: int = 2_000_000


class WebToolsConfig(BaseModel):
    """Web tools configuration."""
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    fetch: WebFetchConfig = Field(default_factory=WebFetchConfig)


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
    auto_approve: bool = False
    policy_preset: str = "strict"  # "strict" | "balanced" | "compat"
    docker: DockerConfig = Field(default_factory=DockerConfig)


class ToolsConfig(BaseModel):
    """Tools configuration."""
    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = False  # If true, restrict all tool access to workspace directory


class MemoryConfig(BaseModel):
    """Memory backend configuration."""

    backend: str = "hybrid"  # "hybrid" | "sqlite_only" | "disabled"
    embedding_provider: str = "sentence"  # "sentence" | "ollama"
    embedding_model: str | None = None
    enable_hybrid_search: bool = True
    enable_graph_memory: bool = True
    graph_injection_limit: int = 8
    auto_unload_timeout: int = 300


class McpServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    transport: str = "stdio"  # "stdio" | "streamable_http"
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True

    @model_validator(mode="after")
    def _validate_transport_requirements(self) -> "McpServerConfig":
        transport = self.transport.strip().lower()
        if transport not in {"stdio", "streamable_http"}:
            raise ValueError("transport must be 'stdio' or 'streamable_http'")
        if transport == "stdio" and not self.command.strip():
            raise ValueError("command is required for stdio MCP servers")
        if transport == "streamable_http" and not self.url.strip():
            raise ValueError("url is required for streamable_http MCP servers")
        self.transport = transport
        return self


class McpConfig(BaseModel):
    """Top-level MCP runtime configuration."""

    enabled: bool = False
    servers: dict[str, McpServerConfig] = Field(default_factory=dict)


class RuntimeResilienceConfig(BaseModel):
    """Runtime safety controls for fallback and tool retry behavior."""

    enabled: bool = True
    dedupe_tool_calls: bool = True
    max_model_attempts_per_turn: int = 4
    max_tool_retry_per_turn: int = 1
    strict_error_classification: bool = True
    prevent_model_chain_mutation: bool = True
    idempotency_ttl_seconds: int = 600


class RuntimePerformanceConfig(BaseModel):
    """Runtime performance controls for first-response latency."""

    fast_first_response: bool = True
    defer_memory_warmup: bool = True
    embed_warmup_timeout_ms: int = 1200
    max_context_build_ms: int = 500
    max_first_response_ms_soft: int = 4000
    token_mode: str = "boros"  # "boros" | "hemat"


class RuntimeAutopilotConfig(BaseModel):
    """Default proactive patrol loop for bottleneck elimination."""

    enabled: bool = True
    prompt: str = (
        "Autopilot patrol: review recent context, pending schedules, and recent failures. "
        "Identify one highest bottleneck that blocks user outcomes. "
        "Execute at most one safe action to reduce it; otherwise respond with 'no_action'."
    )
    max_actions_per_beat: int = 1


class RuntimeObservabilityConfig(BaseModel):
    """Structured runtime observability controls."""

    enabled: bool = True
    emit_structured_events: bool = True
    sample_rate: float = 1.0
    redact_secrets: bool = True


class RuntimeQuotaConfig(BaseModel):
    """Soft/hard runtime request quota guardrails."""

    enabled: bool = False
    max_cost_per_day_usd: float = 0.0
    max_tokens_per_hour: int = 0
    enforcement_mode: str = "warn"  # "warn" | "hard"


class RuntimeQueueConfig(BaseModel):
    """Inbound message queue policy for burst handling and responsiveness."""

    enabled: bool = True
    mode: str = "debounce"  # "off" | "debounce"
    debounce_window_ms: int = 1200
    max_pending_per_session: int = 4
    drop_policy: str = "drop_oldest"  # "drop_oldest" | "drop_newest"
    summarize_dropped: bool = True


class RuntimeConfig(BaseModel):
    """Runtime feature flags for resilience and performance behavior."""

    resilience: RuntimeResilienceConfig = Field(default_factory=RuntimeResilienceConfig)
    performance: RuntimePerformanceConfig = Field(default_factory=RuntimePerformanceConfig)
    autopilot: RuntimeAutopilotConfig = Field(default_factory=RuntimeAutopilotConfig)
    observability: RuntimeObservabilityConfig = Field(default_factory=RuntimeObservabilityConfig)
    quotas: RuntimeQuotaConfig = Field(default_factory=RuntimeQuotaConfig)
    queue: RuntimeQueueConfig = Field(default_factory=RuntimeQueueConfig)


class SkillEntryConfig(BaseModel):
    """Per-skill override settings."""

    model_config = ConfigDict(extra="allow")

    enabled: bool | None = None
    env: dict[str, str] = Field(default_factory=dict)
    api_key: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)


class SkillsLoadConfig(BaseModel):
    """Skill source directory settings."""

    managed_dir: str = "~/.kabot/skills"
    extra_dirs: list[str] = Field(default_factory=list)


class SkillsInstallConfig(BaseModel):
    """Skill dependency planning/install preferences."""

    mode: str = "manual"  # "manual" | "auto"
    node_manager: str = "npm"  # "npm" | "pnpm" | "yarn" | "bun"
    prefer_brew: bool = True

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)


class SkillsOnboardingConfig(BaseModel):
    """One-shot skill onboarding preferences."""

    auto_prompt_env: bool = True
    auto_enable_after_install: bool = True
    soul_injection_mode: str = "prompt"  # "disabled" | "prompt" | "auto"


class SkillsConfig(BaseModel):
    """Canonical typed skills config with dict-like compatibility helpers."""

    model_config = ConfigDict(extra="allow")

    entries: dict[str, SkillEntryConfig] = Field(default_factory=dict)
    allow_bundled: list[str] = Field(default_factory=list)
    load: SkillsLoadConfig = Field(default_factory=SkillsLoadConfig)
    install: SkillsInstallConfig = Field(default_factory=SkillsInstallConfig)
    onboarding: SkillsOnboardingConfig = Field(default_factory=SkillsOnboardingConfig)
    limits: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_skills_payload(cls, value: Any) -> Any:
        from kabot.config.skills_settings import normalize_skills_settings

        if isinstance(value, SkillsConfig):
            return value.to_dict()
        return normalize_skills_settings(value if isinstance(value, dict) else {})

    @classmethod
    def from_raw(cls, raw: Any) -> "SkillsConfig":
        from kabot.config.skills_settings import normalize_skills_settings

        if isinstance(raw, SkillsConfig):
            return raw
        normalized = normalize_skills_settings(raw)
        return cls.model_validate(normalized)

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="python", exclude_none=True)
        extra = getattr(self, "__pydantic_extra__", None) or {}
        if isinstance(extra, dict):
            data.update(extra)
        return data

    def get(self, key: str, default: Any = None) -> Any:
        if key in type(self).model_fields:
            return getattr(self, key)
        extra = getattr(self, "__pydantic_extra__", None) or {}
        return extra.get(key, default)

    def __contains__(self, key: str) -> bool:
        if key in type(self).model_fields:
            return True
        extra = getattr(self, "__pydantic_extra__", None) or {}
        return key in extra

    def __getitem__(self, key: str) -> Any:
        if key in type(self).model_fields:
            return getattr(self, key)
        extra = getattr(self, "__pydantic_extra__", None) or {}
        if key in extra:
            return extra[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in type(self).model_fields:
            setattr(self, key, value)
            return
        if getattr(self, "__pydantic_extra__", None) is None:
            self.__pydantic_extra__ = {}
        assert isinstance(self.__pydantic_extra__, dict)
        self.__pydantic_extra__[key] = value

    def items(self):
        return self.to_dict().items()


class BootstrapParityConfig(BaseModel):
    """Bootstrap parity policy for dev/production consistency checks."""

    enabled: bool = True
    required_files: list[str] = Field(
        default_factory=lambda: [
            "AGENTS.md",
            "SOUL.md",
            "USER.md",
            "IDENTITY.md",
            "BOOTSTRAP.md",
        ]
    )
    baseline_dir: str = ""  # Optional path to canonical bootstrap templates
    enforce_hash: bool = False


class HttpGuardConfig(BaseModel):
    """HTTP target guard configuration for integration tools."""

    enabled: bool = True
    block_private_networks: bool = True
    allow_hosts: list[str] = Field(default_factory=list)
    deny_hosts: list[str] = Field(
        default_factory=lambda: [
            "localhost",
            "127.0.0.1",
            "169.254.169.254",
            "metadata.google.internal",
        ]
    )


class MetaIntegrationConfig(BaseModel):
    """Meta Graph API integration configuration."""

    enabled: bool = False
    access_token: str = ""
    access_token_env: str = ""
    app_secret: str = ""
    verify_token: str = ""
    threads_user_id: str = ""
    instagram_user_id: str = ""


class IntegrationsConfig(BaseModel):
    """External integration guardrails."""

    http_guard: HttpGuardConfig = Field(default_factory=HttpGuardConfig)
    meta: MetaIntegrationConfig = Field(default_factory=MetaIntegrationConfig)


class SecurityTrustModeConfig(BaseModel):
    """Skill trust-mode controls."""

    enabled: bool = False
    verify_skill_manifest: bool = False
    allowed_signers: list[str] = Field(default_factory=list)


class SecurityConfig(BaseModel):
    """Top-level security policies."""

    trust_mode: SecurityTrustModeConfig = Field(default_factory=SecurityTrustModeConfig)


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
    model_config = ConfigDict(env_prefix="NANOBOT_", env_nested_delimiter="__")

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    bootstrap: BootstrapParityConfig = Field(default_factory=BootstrapParityConfig)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()

    def _normalize_model_for_provider(self, model: str) -> str:
        if model.startswith("openai/gpt-5.3-codex"):
            return model.replace("openai/", "openai-codex/", 1)
        if model.startswith("gpt-5.3-codex"):
            return f"openai-codex/{model}"
        return model

    def _primary_model_value(self, value: str | AgentModelConfig | None) -> str | None:
        if isinstance(value, AgentModelConfig):
            return value.primary
        return value

    def _match_provider(self, model: str | None = None) -> tuple["ProviderConfig | None", str | None]:
        """Match provider config and its registry name. Returns (config, spec_name)."""
        from kabot.providers.registry import PROVIDERS
        model_value = self._primary_model_value(model or self.agents.defaults.model) or ""
        model_lower = self._normalize_model_for_provider(model_value).lower()

        def has_credentials(p: "ProviderConfig") -> bool:
            """Check if provider has any credentials (api_key or profiles with tokens)."""
            if p.api_key or p.setup_token:
                return True
            # Check if any profile has credentials
            for profile in p.profiles.values():
                if profile.api_key or profile.oauth_token or profile.setup_token:
                    return True
            return False

        # Match by explicit provider prefix first to avoid ambiguous keyword collisions.
        # Example: together/moonshotai/... should resolve to provider=together, not moonshot.
        if "/" in model_lower:
            prefix = model_lower.split("/", 1)[0]
            provider_aliases = {
                "google": "gemini",
                "google-gemini-cli": "gemini",
                "qwen-portal": "dashscope",
                "zai": "zhipu",
                "z-ai": "zhipu",
                "x-ai": "xai",
                "minimax-portal": "minimax",
                "volcengine-plan": "volcengine",
                "byteplus-plan": "byteplus",
            }
            provider_name = provider_aliases.get(prefix, prefix)
            for spec in PROVIDERS:
                if spec.name != provider_name:
                    continue
                config_key = spec.name.replace("-", "_")
                provider_cfg = getattr(self.providers, config_key, None)
                if provider_cfg and has_credentials(provider_cfg):
                    return provider_cfg, spec.name
                break

        # Match by keyword (order follows PROVIDERS registry)
        for spec in PROVIDERS:
            config_key = spec.name.replace("-", "_")
            p = getattr(self.providers, config_key, None)
            if p and any(kw in model_lower for kw in spec.keywords) and has_credentials(p):
                return p, spec.name

        # Fallback: gateways first, then others (follows registry order)
        for spec in PROVIDERS:
            config_key = spec.name.replace("-", "_")
            p = getattr(self.providers, config_key, None)
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
            if profile.setup_token:
                return profile.setup_token

        # Legacy fallback
        return p.api_key or p.setup_token

    async def get_api_key_async(self, model: str | None = None) -> str | None:
        """Async version of get_api_key with OAuth auto-refresh."""
        from kabot.auth.refresh import TokenRefreshService

        p, provider_name = self._match_provider(model)
        if not p:
            return None

        if p.active_profile in p.profiles:
            profile = p.profiles[p.active_profile]

            # Auto-refresh expired OAuth tokens
            if profile.is_expired() and profile.refresh_token:
                service = TokenRefreshService()
                updated = await service.refresh(provider_name or "", profile)
                if updated:
                    # Update in-memory config
                    p.profiles[p.active_profile] = updated
                    profile = updated

            if profile.api_key:
                return profile.api_key
            if profile.oauth_token:
                return profile.oauth_token
            if profile.setup_token:
                return profile.setup_token

        # Legacy fallback
        return p.api_key or p.setup_token

    def _provider_name_for(self, model: str | None) -> str | None:
        """Extract provider name from model string."""
        if not model:
            _, name = self._match_provider(None)
            return name
        normalized = self._normalize_model_for_provider(model)
        # Handle "provider/model" format
        if "/" in normalized:
            return normalized.split("/")[0]
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

