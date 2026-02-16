# Kabot vs OpenClaw: The Gap Analysis 📊

> **Objective**: To visualize the architectural differences between the current Kabot codebase and the OpenClaw "Gold Standard".
> **Date**: 2026-02-16
> **Status**: 🟢 Ready for Roadmap Planning

---

## Executive Summary
Kabot has a strong foundation in **Resilience** and basic **Agent Logic**, but lacks the sophisticated **Infrastructure**, **Memory**, and **Interface** layers that make OpenClaw production-ready.

| Category | Parity Score | Key Missing Piece |
| :--- | :---: | :--- |
| **🧠 Intelligence** | 🟡 40% | Hybrid Memory (Vector DB) |
| **🛡️ Resilience** | 🟢 80% | Atomic Writes & PID Locking |
| **👮 Security** | 🟡 30% | Command Approvals & Windows ACLs |
| **🗣️ Interface** | 🔴 10% | TUI, Canvas, & TTS |
| **🔌 Infrastructure** | 🔴 0% | Tailscale & Bonjour |

---

## 1. Core Intelligence (The Brain) 🧠

| Feature | OpenClaw | Kabot Current State | Status |
| :--- | :--- | :--- | :---: |
| **Context Guard** | Proactive + Adaptive Compaction | Basic Token Counting | 🟡 Partial |
| **Memory** | **Hybrid (Vector + BM25)** | **Markdown Files Only** | 🔴 Major Gap |
| **Model Fallback** | Cascade + Cooldowns | Cascade + Cooldowns (`resilience.py`) | 🟢 Parity |
| **Directives** | `/think`, `/model`, `/exec` | Parser exists, logic unhooked | 🟡 Partial |

> **Action Item**: Implement `sqlite-vec` integration immediately. Kabot is currently "amnesiac" compared to OpenClaw.

## 2. Stability & Resilience (The Immune System) 🛡️

| Feature | OpenClaw | Kabot Current State | Status |
| :--- | :--- | :--- | :---: |
| **Atomic Writes** | `.tmp` -> `rename` | Direct file writes (Risky) | 🔴 Missing |
| **PID Locking** | Multi-process safety | None (Race conditions possible) | 🔴 Missing |
| **Sentinel** | Crash recovery file | Basic Restart Logic | 🟡 Partial |
| **Daemon** | Native Windows Service | CLI Loop only | 🔴 Missing |

> **Action Item**: Implement `AtomicFileWriter` utility to prevent config corruption.

## 3. Security (The Gatekeeper) 👮

| Feature | OpenClaw | Kabot Current State | Status |
| :--- | :--- | :--- | :---: |
| **Cmd Approvals** | Granular (`allowlist`, `ask`) | None (Unsafe shell access) | 🔴 Critical |
| **Security Audit** | Windows ACLs + Net Checks | Regex Secrets Only | 🟡 Partial |
| **Sandboxing** | Docker / Firecracker | None (Runs on Host) | 🔴 Missing |

> **Action Item**: Kabot's `security_audit.py` explicitly *skips* Windows checks (`if os.name == 'nt': return`). This must be reversed to match OpenClaw's Windows-first security.

## 4. Interface (The Face) 🗣️

| Feature | OpenClaw | Kabot Current State | Status |
| :--- | :--- | :--- | :---: |
| **TUI** | Hacker-style Terminal UI | Basic `print()` logs | 🔴 Missing |
| **Canvas** | Web UI Host (`localhost`) | None | 🔴 Missing |
| **TTS** | Edge / OpenAI / ElevenLabs | None (Silent) | 🔴 Missing |
| **Shortcodes** | `[[quick_replies: ...]]` | None | 🔴 Missing |

> **Action Item**: Phase 12 should prioritize a basic TUI to improve developer experience.

## 5. Infrastructure (The Nervous System) 🔌

| Feature | OpenClaw | Kabot Current State | Status |
| :--- | :--- | :--- | :---: |
| **Tailscale** | Native Funnel/Serve control | None | 🔴 Missing |
| **Bonjour** | `openclaw.local` Discovery | None (IP Address required) | 🔴 Missing |
| **Cron** | Advanced (`everyMs`, `atMs`) | Basic Interval (`X menit`) | 🟡 Partial |
| **Costing** | Per-Session Token Audit | Basic Logging | 🟡 Partial |

> **Action Item**: These are "Nice to Have" for now, except for **Cron** which needs to be robust for the alarm/reminder features.

## 6. Hidden Architecture (The Secret Sauce) 💎

| Feature | OpenClaw | Kabot Current State | Status |
| :--- | :--- | :--- | :---: |
| **Pi Agent** | Embedded "Mini-Me" for speed | Single Agent only | 🔴 Missing |
| **Browser Relay** | Hijack existing Chrome Extension | None | 🔴 Missing |
| **Windows Native** | WSL Detection, Clipboard, `schtasks` | Python `os` calls only | 🔴 Missing |
| **Multi-Platform Daemon** | `LaunchAgent` (Mac), `systemd` (Linux) | Manual Setup | 🔴 Missing |
| **Network** | SSH Tunneling, Wide-Area DNS | None | 🔴 Missing |

> **Action Item**: The **Windows Native** integration (Clipboard, WSL) is low-hanging fruit that would make Kabot feel much more "premium" on the user's desktop.

---

## Recommendation Roadmap

### Phase 12 (Immediate: Anti-Crash)
1.  **Context Guard Upgrade**: Implement `ToolResultTruncator` (Finding 9) and Adaptive Compaction.
2.  **Atomic Writes**: secure all `json` and `md` file operations.

### Phase 13 (Intelligence)
1.  **Hybrid Memory**: Drop `MEMORY.md` and implement `sqlite-vec`.

### Phase 14 (Security)
1.  **Windows ACLs**: Update `security_audit.py` to use `icacls`.
2.  **Command Approvals**: Implement the "Firewall" for `run_command`.

### Phase 15 (Experience)
1.  **TUI**: Build the hacker interface.
2.  **Directives**: Fully wire up `/think` and `/verbose`.
