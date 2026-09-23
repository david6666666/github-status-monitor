# Repository structure

This repository is a generated GitHub contribution monitor. The source of truth is the Python generator and the scheduled workflow; the Markdown, SVG, and HTML files at the root are generated snapshots.

```text
github-status-monitor/
├── .github/
│   └── workflows/
│       └── update_stats.yml          # daily schedule + manual dispatch
├── docs/
│   ├── REPOSITORY_STRUCTURE.md       # this structure and data-flow guide
│   └── plans/                        # implementation/design plans
├── tests/
│   └── test_monthly_monitoring.py    # offline Beijing-window/scoring smoke test
├── generate_stats.py                 # GitHub API collection and rendering
├── README.md                         # short entry point
├── README_data.md                    # generated Markdown report for all tracked repos
├── stats_chart.svg                   # generated vLLM-Omni chart
├── stats_dashboard.html              # generated vLLM-Omni dashboard
├── stats_chart_afd_plugin.svg        # generated afd-plugin chart
├── stats_dashboard_afd_plugin.html   # generated afd-plugin dashboard
├── stats_chart_agentinfer.svg        # generated AgentInfer chart
└── stats_dashboard_agentinfer.html   # generated AgentInfer dashboard
```

## Data flow

1. `.github/workflows/update_stats.yml` checks out `main`, installs `PyGithub` and `requests`, and runs `generate_stats.py` with `GH_PAT`.
2. `generate_stats.py` keeps the existing vLLM-Omni all-time PR monitor and formal-release contribution windows.
3. `MONTHLY_SCENE_CONFIGS` groups the six `afd-plugin` people and eight `AgentInfer` people from the team sheet by 投入场景. Each scene lists every repo from its `涉及repo` field: `afd-plugin` covers `vllm-project/afd-plugin`, `vllm-project/vllm`, and `vllm-project/vllm-ascend`; `AgentInfer` covers `openJiuwen-ai/agent-infer`, `vllm-project/router`, `vllm-project/semantic-router`, `vllm-project/vllm`, and `vllm-project/vllm-ascend`.
4. Each scene uses two Beijing-time windows: the previous calendar month and the current calendar month through the latest run. Review candidates are searched by tracked reviewer, then each review timestamp is checked against the exact window; review collection is skipped for `vllm-project/vllm` to reduce API work, while that repo remains included in PR counts and recent PRs. Raw commit, review, and code-churn metrics are summed across that scene's repos before scoring, so shared repos are combined before the 20% commit + 35% review + 45% code-churn score is calculated.
5. All-time PR counts use GitHub's complete search counts. The monitor loads up to 10 recent PRs per contributor, repo, and state as candidates, then fetches code deltas only for the latest 80 displayed PRs. This keeps large-repository searches bounded while showing the repo beside every recent PR.
6. Each scene gets an independent SVG chart and HTML dashboard. `README_data.md` links to the generated artifacts and includes the Markdown summaries, with the repo list shown under each scene. The all-time code-delta totals refer to the displayed recent PR set; monthly code-delta totals remain based on the complete commit window.

## Change boundaries

- Modify collection/scoring behavior in `generate_stats.py`.
- Modify generated-file commit coverage in `.github/workflows/update_stats.yml`.
- Treat root Markdown/SVG/HTML files as generated output; do not hand-edit them between action runs.
- Keep personnel changes localized to the explicit repository configuration near the top of `generate_stats.py`.
