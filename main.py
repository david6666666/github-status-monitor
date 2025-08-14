import os
from github import Github

# Get the GitHub token from environment variables
GH_TOKEN = os.getenv("GH_TOKEN")
if not GH_TOKEN:
    raise ValueError("GitHub token is not set. Please add a GH_TOKEN secret to your repository.")

# Initialize the GitHub instance
g = Github(GH_TOKEN)

# The list of users to monitor
users = ["david6666666", "hsliuustc0106", "fake0fan"]
user_stats = {}

# Iterate over each user
for username in users:
    print(f"Fetching data for user: {username}")
    user = g.get_user(username)
    
    # Initialize counts
    total_pr = 0
    total_issue = 0

    # Get all public repositories for the user
    repos = user.get_repos()
    
    for repo in repos:
        # Check for PRs and issues in the repository
        # This will count all open and closed PRs/Issues
        total_pr += repo.get_pulls(state='all').totalCount
        total_issue += repo.get_issues(state='all').totalCount
    
    user_stats[username] = {
        "pr_count": total_pr,
        "issue_count": total_issue
    }
    
# Generate the Markdown table
table_header = "| User | Total PRs | Total Issues |\n"
table_separator = "|---|---|---|\n"
table_rows = ""

for username, stats in user_stats.items():
    table_rows += f"| [{username}](https://github.com/{username}) | {stats['pr_count']} | {stats['issue_count']} |\n"

# Combine everything into the final Markdown content
markdown_content = f"""
# GitHub User Statistics

This table shows the total number of Pull Requests and Issues for the specified users.

_Last updated: {g.get_organization('github').get_members().next().created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}_

{table_header}
{table_separator}
{table_rows}
"""

# Write the content to the README.md file
with open("README.md", "w", encoding="utf-8") as f:
    f.write(markdown_content)

print("Successfully updated README.md with the latest stats.")
