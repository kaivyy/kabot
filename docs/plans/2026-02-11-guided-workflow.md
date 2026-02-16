# Guided Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Modify Kabot's system prompt to proactively guide users through the development workflow (Brainstorm -> Plan -> Execute) instead of jumping straight to coding.

**Architecture:** Update `PROFILES` in `context.py` to include workflow guidance instructions in `CODING` and `GENERAL` profiles.

**Tech Stack:** Python.

---

### Task 1: Add Guided Workflow Instructions

**Files:**
- Modify: `kabot/agent/context.py`

**Step 1: Update CODING and GENERAL profiles**

Edit `kabot/agent/context.py` to add the following instruction to the `PROFILES` dictionary (specifically `CODING` and `GENERAL`):

```text
GUIDED WORKFLOW:
If the user asks to build a complex application or feature from scratch (e.g. "Create a Todo App"):
1. DO NOT start writing code immediately.
2. OFFER to start with the **Brainstorming** phase to clarify requirements.
3. EXPLAIN the workflow: Brainstorm -> Design -> Plan -> Execute.
```

**Step 2: Commit**

```bash
git add kabot/agent/context.py
git commit -m "feat: add guided workflow instructions to system prompt"
```
