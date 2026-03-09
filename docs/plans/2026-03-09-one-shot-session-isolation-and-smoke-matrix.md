# One-Shot Session Isolation And Smoke Matrix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make ad-hoc `kabot agent -m ...` runs isolated by default while adding a reusable multilingual smoke-matrix runner for agent CLI verification.

**Architecture:** Keep interactive sessions unchanged, but resolve one-shot default sessions to ephemeral IDs unless the user explicitly passes `--session`. Add a package-local smoke runner that uses list-arg subprocess calls instead of shell strings, so Unicode prompts and path prompts stay stable across Windows, macOS, and Linux.

**Tech Stack:** Python, Typer, Click parameter source, pytest, subprocess

---
