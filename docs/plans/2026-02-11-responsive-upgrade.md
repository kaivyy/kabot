# Responsive Kabot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Kabot feel more "human" and responsive by providing comprehensive status updates for all tools and encouraging self-narration.

**Architecture:**
1.  **Status Expansion:** Update `AgentLoop._get_tool_status_message` to cover all available tools (memory, weather, stocks, cron, etc.).
2.  **Instruction Tuning:** Update `ContextBuilder` to instruct the LLM to be more communicative about its actions.

**Tech Stack:** Python.

---

### Task 1: Expand Tool Status Coverage

**Files:**
- Modify: `kabot/agent/loop.py`

**Step 1: Update `_get_tool_status_message`**

Add `elif` blocks for the following tools in `kabot/agent/loop.py`:
- `save_memory`: "💾 Menyimpan ingatan..."
- `get_memory`: "🧠 Mengingat kembali..."
- `list_reminders`: "📋 Mengecek pengingat..."
- `weather`: "🌤️ Mengecek cuaca di {location}..."
- `stock`: "📈 Mengecek saham {symbol}..."
- `crypto`: "₿ Mengecek harga {symbol}..."
- `stock_analysis`: "📊 Menganalisis saham {symbol}..."
- `cron`: "⏰ Mengatur jadwal..."
- `download_manager`: "📥 Mengunduh file..." (Check tool name in registry)

**Step 2: Commit**

```bash
git add kabot/agent/loop.py
git commit -m "feat: expand status updates for all tools"
```

---

### Task 2: Enhance Communication Instructions

**Files:**
- Modify: `kabot/agent/context.py`

**Step 1: Add "Self-Narration" Instruction**

In `kabot/agent/context.py`, add a new section to `_get_identity()` string:

```text
## Communication Style
- **Be Responsive**: Don't just do things silently. Tell the user what you have done after finishing a task.
- **Narrate Actions**: When performing multi-step tasks (like downloading then sending), briefly mention the completion of each step.
- **Confirm Completion**: Always end task-based interactions with a clear confirmation.
```

**Step 2: Commit**

```bash
git add kabot/agent/context.py
git commit -m "feat: enhance system prompt for better responsiveness"
```
