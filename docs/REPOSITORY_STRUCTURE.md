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
3. The monthly repository configuration tracks the six `afd-plugin` people and eight `AgentInfer` people from the team sheet. Their sheet names and locations are retained in the generated reports.
4. New repositories use two Beijing-time windows: the previous calendar month and the current calendar month through the latest run. The contribution score remains 20% commit share + 35% review share + 45% code-churn share.
5. Each repository gets an independent SVG chart and HTML dashboard. `README_data.md` links to the generated artifacts and includes the Markdown summaries.

## Change boundaries

- Modify collection/scoring behavior in `generate_stats.py`.
- Modify generated-file commit coverage in `.github/workflows/update_stats.yml`.
- Treat root Markdown/SVG/HTML files as generated output; do not hand-edit them between action runs.
- Keep personnel changes localized to the explicit repository configuration near the top of `generate_stats.py`.
