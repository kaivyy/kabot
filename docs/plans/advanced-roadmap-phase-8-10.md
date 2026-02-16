# Advanced Kabot Roadmap: Phases 8-10 🚀
*Detailed Technical Specification - 2026-02-15*

Master blueprint for elevating Kabot to enterprise-grade, mirroring OpenClaw's architecture.

---

## ⚙️ Phase 8: System Internals

### 1. Slash Command Router (`kabot/core/router.py`)

```python
class CommandRouter:
    registry: Dict[str, CommandHandler]
    
    def register(cmd: str, handler: Callable, description: str)
    async def route(message: str, context: Any) -> Optional[str]
```

**Commands**: `/switch`, `/status`, `/benchmark`, `/help`, `/restart`, `/update`

### 2. Status & Benchmark (`kabot/features/status.py`)
- Uptime, Memory (psutil), LLM Latency (moving avg), Error Rate
- Benchmark: TTFT + TPS measurement with standardized prompt

### 3. Doctor Service (`kabot/core/doctor.py`)
| Check | Logic | Auto-Fix |
|-------|-------|----------|
| `db_schema` | Compare alembic versions | `alembic upgrade head` |
| `auth_valid` | Test API call | Trigger `TokenRefreshService` |
| `env_vars` | Check required vars | Prompt user |

### 4. Update System (`kabot/infra/update.py`)
Git Pull → Dep Check → Install → Doctor → Restart

---

## 🏗️ Phase 9: Architecture Overhaul

### 1. MsgContext Schema (`kabot/core/types.py`)
```python
class MsgContext(BaseModel):
    id: str; channel: ChannelType; sender_id: str
    body: str; timestamp: datetime; metadata: Dict
    is_system_event: bool = False
```

### 2. Input Adaptors (`kabot/channels/`)
- `InputMonitor(ABC)` → `start()`, `on_event(raw)` → normalize → dispatch
- Implementations: `WebMonitor`, `WhatsappMonitor`

### 3. Directives (`kabot/core/directives.py`)
- `/think`, `/verbose`, `/json`, `/model <name>`
- Regex: `r"\/([a-zA-Z]+)(?:\s+(.*))?"`

### 4. Resilience (`kabot/llm/resilience.py`)
- `AuthManager.rotate()` on 429/401
- `ModelRegistry.fallback()` cascade

---

## 🔌 Phase 10: Plugin System

### 1. Manifest (`plugin.json`)
```json
{"id": "...", "name": "...", "version": "1.0", "entry_point": "main.py"}
```

### 2. Loader (`kabot/plugins/loader.py`)
Scan `plugins/` → parse manifest → `importlib.import_module` → `register()`

### 3. Hooks (`kabot/core/hooks.py`)
Events: `ON_MESSAGE`, `PRE_LLM_CALL`, `POST_LLM_CALL`, `ON_TOOL_CALL`
