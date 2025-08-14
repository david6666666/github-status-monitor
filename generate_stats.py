name: Update GitHub Stats

on:
  schedule:
    # Runs every hour
    - cron: '0 * * * *'
  workflow_dispatch:
    # Allows for manual runs

jobs:
  update-readme:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install PyGithub requests # <-- ADD 'requests' HERE

      - name: Run script to update stats and chart
        run: python generate_stats.py
        env:
          GH_PAT: ${{ secrets.GH_PAT }}

      - name: Commit and push changes
        run: |
          git config --global user.name 'github-actions[bot]'
          git config --global user.email 'github-actions[bot]@users.noreply.github.com'
          # Add both the README and the new chart file
          git add README.md stats_chart.svg # <-- ADD THE CHART FILE HERE
          if git diff --staged --quiet; then
            echo "No changes to commit."
          else
            git commit -m "📊 Chore: Update stats and chart"
            git push
          fi
