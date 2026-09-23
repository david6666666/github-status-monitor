# Multi-Repository Monthly Monitoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the existing GitHub status monitor to report the `afd-plugin` and `AgentInfer` 投入场景 using their configured personnel and repositories, with Beijing-time current/previous-month contribution windows while preserving the existing vLLM-Omni release-window report.

**Architecture:** Keep the existing vLLM-Omni reporting behavior stable while naming its output files explicitly. Maintain an explicit configuration for the two monthly scenes, including each scene's people and repo list, parameterize the existing all-time PR query and chart generator where needed, and use the generic monthly-window collection/rendering helpers. Each scene gets its own SVG chart and HTML dashboard; `README_data.md` becomes the generated index/report for vLLM-Omni plus the two scenes. Monthly raw metrics are aggregated across a scene before scoring. All-time PR totals use full search counts while candidate lists and code-detail lookups are bounded to avoid walking large repositories' entire PR histories.

**Tech Stack:** Python 3.9+, PyGithub, requests, GitHub Actions, GitHub Search/REST API, Markdown, standalone HTML/SVG.

---

### Task 1: Capture the repository structure and monitoring design

**Files:**
- Create: `docs/plans/2026-09-22-multi-repo-monthly-monitoring.md`
- Create: `docs/REPOSITORY_STRUCTURE.md`

**Step 1: Record the current layout and data flow**

Document the existing generator, generated artifacts, scheduled workflow, preserved vLLM-Omni release semantics, and the new per-repository monthly outputs.

**Step 2: Verify the plan before implementation**

Check that every requested repository has a known owner/name, a known default branch, and an explicit personnel list from the source sheet.

### Task 2: Add repository/person configuration and Beijing month windows

**Files:**
- Modify: `generate_stats.py`

**Step 1: Add explicit monthly scene configuration**

Add the six `afd-plugin` people and ten `AgentInfer` people, including the two subsequently added Hong Kong contributors, retaining display names and each person's location. Map `afd-plugin` to `vllm-project/afd-plugin`, `vllm-project/vllm`, and `vllm-project/vllm-ascend`; map `AgentInfer` to `openJiuwen-ai/agent-infer`, `vllm-project/router`, `vllm-project/semantic-router`, `vllm-project/vllm`, and `vllm-project/vllm-ascend`. Define output names per scene and keep the existing vLLM-Omni reporting flow intact.

**Step 2: Parameterize all-time PR collection**

Allow the existing PR search/fallback path to receive a repository name instead of always using the global vLLM-Omni target. Preserve the old default so the existing report remains behavior-compatible.

**Step 3: Implement fixed Beijing-time month boundaries**

Use UTC+08:00 explicitly. Define:

- Current month: first day of the current Beijing calendar month at 00:00 through the current Beijing timestamp.
- Previous month: first day of the previous Beijing calendar month at 00:00 through the first day of the current month at 00:00.

Convert API timestamps to one comparable timezone before filtering.

### Task 3: Collect, aggregate, and score monthly contributions

**Files:**
- Modify: `generate_stats.py`

**Step 1: Collect commits in a bounded month window**

Read repository commits between the window boundaries, retain tracked GitHub authors, and aggregate commit count plus additions/deletions.

**Step 2: Collect reviews in the same window**

Search PRs reviewed by tracked contributors and updated in the bounded window, inspect review submissions, and count only review events whose `submitted_at` lies inside the window. Skip review collection for `vllm-project/vllm` to reduce API work, but continue including that repository in PR monitoring/counts. Retain the existing 20% commit + 35% review + 45% code-churn scoring rule.

**Step 3: Aggregate scene metrics before scoring**

Sum raw metrics from every configured repo in a scene for each user and `属地`, then score the merged totals once. Keep zero-activity users so the personnel view remains complete.

**Step 4: Build per-user and per-location summaries**

Produce the same score components for each tracked person and each `属地` label, including zero-activity users only where useful for a complete personnel view.

### Task 4: Generate added scene artifacts and aggregate README

**Files:**
- Modify: `generate_stats.py`
- Modify: `.github/workflows/update_stats.yml`

**Step 1: Generate one chart and dashboard per monthly scene**

Reuse the existing chart generator with parameterized output paths. Add a compact standalone HTML dashboard per monthly scene containing the covered repos, monitoring totals, recent PRs, and previous/current month contribution tables.

**Step 2: Append monthly reports to `README_data.md`**

Keep the existing vLLM-Omni report first, then add links, the scene repo lists, all-time PR monitoring summaries, Beijing-time window metadata, and contribution tables for `afd-plugin` and `AgentInfer`.

**Step 3: Update the action artifact list**

Include the scene-specific SVG and HTML files in `file_pattern`; keep the daily schedule and manual dispatch path because the added API work should not turn the existing monitor into an hourly rate-limit risk.

### Task 5: Verify, review, commit, push, and trigger

**Files:**
- Generated: `README_data.md`, `stats_chart_vllm_omni.svg`, `stats_dashboard_vllm_omni.html`, `stats_chart_afd_plugin.svg`, `stats_dashboard_afd_plugin.html`, `stats_chart_agentinfer.svg`, `stats_dashboard_agentinfer.html`

**Step 1: Run local static checks**

Run `python -m py_compile generate_stats.py` and targeted helper smoke tests that do not require network credentials. Inspect generated diffs and verify no unrelated files are changed.

**Step 2: Review the generated structure**

Check the README links, repo names, Beijing timezone labels, two monthly windows, score weights, and workflow artifact list.

**Step 3: Commit with repository signing convention**

Use a signed-off commit (`git commit -s`) containing only the requested monitor changes and documentation.

**Step 4: Push and dispatch the GitHub Action**

Push the implementation to `main`, manually dispatch `Update GitHub Stats`, then inspect the workflow run and generated artifact commit. Report any remote-only validation that could not be completed locally.
