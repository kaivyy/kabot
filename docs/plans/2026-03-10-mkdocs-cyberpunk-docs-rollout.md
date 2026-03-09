# MkDocs Cyberpunk Docs Rollout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a complete public MkDocs documentation site for Kabot with a cyberpunk neon visual style, beginner and advanced tracks, and GitHub Pages deployment support.

**Architecture:** Keep existing `docs/` as the mixed internal knowledge/archive area and introduce a curated public docs tree dedicated to MkDocs. Use MkDocs Material with custom CSS/JS overrides for the cyberpunk neon aesthetic, while authoring beginner/advanced guides by consolidating existing README and docs content into cleaner public pages.

**Tech Stack:** MkDocs, MkDocs Material, Markdown, custom CSS, optional lightweight JavaScript, GitHub Actions, Python packaging optional dependencies.

---

### Task 1: Define public docs boundary and IA

**Files:**
- Create: `site_docs/`
- Modify: `README.md`
- Reference: `HOW_TO_USE.MD`, `docs/authentication.md`, `docs/skill-system.md`, `docs/multi-agent.md`, `docs/SECURITY.md`

**Step 1: Define the public docs sections**

Create a public information architecture with:
- landing / overview
- getting started for beginners
- installation
- quickstart
- configuration/setup wizard
- gateway/dashboard
- CLI usage
- channels/integrations
- skills
- memory
- multi-agent
- security
- troubleshooting
- advanced guides
- reference

**Step 2: Keep internal planning docs out of the main docs nav**

Do not expose `docs/plans/` in the main public nav.

**Step 3: Update README docs link targets**

Point readers at the new MkDocs entrypoint instead of a raw `docs/` directory link.

### Task 2: Add MkDocs config and theme assets

**Files:**
- Create: `mkdocs.yml`
- Create: `site_docs/assets/stylesheets/extra.css`
- Create: `site_docs/assets/javascripts/extra.js`
- Create: `site_docs/assets/`

**Step 1: Configure MkDocs Material**

Set:
- `site_name`
- `site_url`
- `repo_url`
- `docs_dir`
- `theme`
- `nav`
- search plugin
- markdown extensions

**Step 2: Add cyberpunk neon styling**

Implement:
- dark background palette
- neon accent tokens
- mono display/body fonts
- terminal-like cards
- grid/noise/scanline ambience
- custom code block and sidebar styling

**Step 3: Add small JS polish**

Keep JS minimal:
- optional ambient class hooks
- no heavy client framework

### Task 3: Write beginner docs

**Files:**
- Create: `site_docs/index.md`
- Create: `site_docs/getting-started/index.md`
- Create: `site_docs/getting-started/install.md`
- Create: `site_docs/getting-started/first-run.md`
- Create: `site_docs/getting-started/quickstart.md`
- Create: `site_docs/getting-started/dashboard.md`

**Step 1: Write a beginner-friendly landing page**

Explain:
- what Kabot is
- who it is for
- first 5-minute path

**Step 2: Write installation docs**

Cover:
- Windows
- macOS
- Linux
- Termux
- pip install
- developer install

**Step 3: Write first-run and quickstart docs**

Cover:
- `kabot config`
- `kabot gateway`
- `kabot agent -m`
- dashboard access

### Task 4: Write core feature docs

**Files:**
- Create: `site_docs/guide/configuration.md`
- Create: `site_docs/guide/cli.md`
- Create: `site_docs/guide/gateway-dashboard.md`
- Create: `site_docs/guide/channels.md`
- Create: `site_docs/guide/google-suite.md`
- Create: `site_docs/guide/skills.md`
- Create: `site_docs/guide/memory.md`
- Create: `site_docs/guide/multi-agent.md`
- Create: `site_docs/guide/security.md`

**Step 1: Consolidate existing docs into structured guides**

Reuse material from:
- `HOW_TO_USE.MD`
- `docs/authentication.md`
- `docs/skill-system.md`
- `docs/multi-agent.md`
- `docs/SECURITY.md`

**Step 2: Normalize language**

Prefer clean English docs with practical command examples.

### Task 5: Write advanced and reference sections

**Files:**
- Create: `site_docs/advanced/index.md`
- Create: `site_docs/advanced/runtime-architecture.md`
- Create: `site_docs/advanced/operator-patterns.md`
- Create: `site_docs/advanced/troubleshooting.md`
- Create: `site_docs/reference/commands.md`
- Create: `site_docs/reference/configuration.md`
- Create: `site_docs/reference/authentication.md`

**Step 1: Add advanced operator/developer pages**

Explain:
- runtime architecture
- fallback/model routing
- operator workflows
- common failure recovery patterns

**Step 2: Add reference pages**

Summarize commands, config areas, auth modes, and dashboard routes.

### Task 6: Add packaging and deployment support

**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/workflow.yml` or create dedicated docs workflow

**Step 1: Add docs dependencies**

Add a `docs` optional dependency with MkDocs Material and any needed plugins.

**Step 2: Add GitHub Pages publishing**

Ensure docs can be built and deployed from GitHub Actions.

### Task 7: Verify locally

**Files:**
- Test: `mkdocs build --strict`

**Step 1: Build docs locally**

Run:
- `mkdocs build --strict`

**Step 2: Fix broken nav/links/style issues**

Keep iterating until build passes.

**Step 3: Summarize assumptions and results**

Document that the public docs site is curated and intentionally excludes the internal `docs/plans` archive from the main sidebar.
