import os
import re
import requests # 用于请求图表API
from github import Github

# =================================CONFIG=================================
# The GitHub usernames you want to track
USERNAMES = ["david6666666", "hsliuustc0106", "fake0fan"]
# The path to the README file to be updated
README_PATH = "README.md"
# Your GitHub Personal Access Token, read from an environment variable
GITHUB_TOKEN = os.getenv('GH_PAT')
# The maximum number of items to display per user per category
MAX_ITEMS_PER_TABLE = 5
# The output filename for the chart
CHART_FILENAME = "stats_chart.svg"
# =======================================================================

def get_user_stats(github_instance, username):
    """
    Fetches PRs (open and merged) and Issues (open and closed) for a user.
    """
    print(f"Fetching data for {username}...")
    
    # 1. PRs: Query for open and merged PRs separately
    query_open_prs = f"is:pr author:{username} is:public is:open"
    query_merged_prs = f"is:pr author:{username} is:public is:merged"
    
    open_prs = github_instance.search_issues(query_open_prs)
    merged_prs = github_instance.search_issues(query_merged_prs)
    
    # 2. Issues: Query for open and closed issues
    query_issues = f"is:issue author:{username} -is:pr is:public"
    issues = github_instance.search_issues(query_issues)
    
    print(f"Found for {username}: {open_prs.totalCount} open PRs, {merged_prs.totalCount} merged PRs, {issues.totalCount} issues.")
    
    return {
        "open_prs": open_prs,
        "merged_prs": merged_prs,
        "issues": issues
    }

def generate_chart(user_data):
    """
    Generates a bar chart using QuickChart.io and saves it as an SVG file.
    """
    print("Generating chart...")
    # Prepare data for the chart
    labels = []
    open_pr_counts = []
    merged_pr_counts = []
    issue_counts = []

    for user in user_data:
        labels.append(user['username'])
        open_pr_counts.append(user['stats']['open_prs'].totalCount)
        merged_pr_counts.append(user['stats']['merged_prs'].totalCount)
        issue_counts.append(user['stats']['issues'].totalCount)

    # Configure the chart using QuickChart.io JSON format
    chart_config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Merged PRs",
                    "data": merged_pr_counts,
                    "backgroundColor": "rgba(110, 107, 213, 0.7)", # Purple
                },
                {
                    "label": "Open PRs",
                    "data": open_pr_counts,
                    "backgroundColor": "rgba(40, 167, 69, 0.7)", # Green
                },
                {
                    "label": "Issues",
                    "data": issue_counts,
                    "backgroundColor": "rgba(255, 159, 64, 0.7)", # Orange
                }
            ]
        },
        "options": {
            "title": {
                "display": True,
                "text": "用户贡献统计"
            },
            "scales": {
                "yAxes": [{"ticks": {"beginAtZero": True}}],
                "xAxes": [{"stacked": True}], # Stack bars for a compact view
            }
        }
    }
    
    # Make the API request to QuickChart
    qc_url = "https://quickchart.io/chart"
    response = requests.post(qc_url, json={"chart": chart_config, "format": "svg"})
    
    if response.status_code == 200:
        with open(CHART_FILENAME, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"Chart saved successfully as {CHART_FILENAME}")
    else:
        print(f"Error generating chart: {response.status_code} {response.text}")


def generate_markdown(user_data):
    """Generates Markdown text for tables from the sorted user data."""
    markdown_text = "这是根据总贡献（Merged PRs + Open PRs + Issues）进行的排序。\n\n"
    for user in user_data:
        username = user['username']
        stats = user['stats']
        
        markdown_text += f"### 👤 {username}\n\n"
        
        # Combined PR Table
        markdown_text += f"**Pull Requests ({stats['open_prs'].totalCount} open, {stats['merged_prs'].totalCount} merged)**\n"
        
        # Combine and display top PRs
        all_prs = list(stats['open_prs']) + list(stats['merged_prs'])
        if all_prs:
            markdown_text += "| Title | Repository | State |\n"
            markdown_text += "| ----- | ---------- | ----- |\n"
            for pr in all_prs[:MAX_ITEMS_PER_TABLE]:
                repo_name = pr.repository.full_name
                title = pr.title.replace('|', '\|')
                state = "merged" if pr.state == 'closed' else pr.state # Show 'merged' instead of 'closed' for PRs
                markdown_text += f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `{state}` |\n"
        else:
            markdown_text += "_No relevant pull requests found._\n"
        markdown_text += "\n"

        # Issue Table
        markdown_text += f"**Issues ({stats['issues'].totalCount} total)**\n"
        if stats['issues'].totalCount > 0:
            markdown_text += "| Title | Repository | State |\n"
            markdown_text += "| ----- | ---------- | ----- |\n"
            for issue in stats['issues'][:MAX_ITEMS_PER_TABLE]:
                repo_name = issue.repository.full_name
                title = issue.title.replace('|', '\|')
                markdown_text += f"| [{title}]({issue.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `{issue.state}` |\n"
        else:
            markdown_text += "_No public issues found._\n"
        markdown_text += "\n"
        
    return markdown_text


def update_readme(content):
    """Writes new content into the README between the specified markers."""
    with open(README_PATH, 'r', encoding='utf-8') as f:
        readme_content = f.read()
    
    new_readme = re.sub(
        r"(?s)(.*?)",
        f"\n{content}\n",
        readme_content
    )
    
    with open(README_PATH, 'w', encoding='utf-8') as f:
        f.write(new_readme)
    print("README.md updated successfully.")


if __name__ == "__main__":
    if not GITHUB_TOKEN:
        raise ValueError("GH_PAT environment variable not set.")
        
    github = Github(GITHUB_TOKEN)
    
    # Fetch data for all users
    all_user_data = []
    for username in USERNAMES:
        stats = get_user_stats(github, username)
        total_contributions = stats['merged_prs'].totalCount + stats['open_prs'].totalCount + stats['issues'].totalCount
        all_user_data.append({
            "username": username,
            "stats": stats,
            "total_contributions": total_contributions
        })
        
    # Sort users by total contributions (descending)
    all_user_data.sort(key=lambda x: x['total_contributions'], reverse=True)
    
    # 1. Generate and save the chart
    generate_chart(all_user_data)
    
    # 2. Generate the markdown tables
    markdown_output = generate_markdown(all_user_data)
    
    # 3. Update the README file
    update_readme(markdown_output)

    print("\n✅ All tasks completed successfully.")
