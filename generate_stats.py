import os
from github import Github
import re

# =================================CONFIG=================================
# The GitHub usernames you want to track
USERNAMES = ["david6666666", "hsliuustc0106", "fake0fan"]
# The path to the README file to be updated
README_PATH = "README.md"
# Your GitHub Personal Access Token, read from an environment variable
GITHUB_TOKEN = os.getenv('GH_PAT')
# The maximum number of items to display per user per category
MAX_ITEMS = 10
# =======================================================================

def get_user_stats(github_instance, username):
    """
    Fetches the full result objects for a user's PRs and Issues.
    The result object, not a list, is returned to retain the 'totalCount'.
    """
    print(f"Fetching data for {username}...")
    # Fetch public PRs
    pull_requests = github_instance.search_issues(f"is:pr author:{username} is:public")
    # Fetch public Issues (and exclude PRs)
    issues = github_instance.search_issues(f"is:issue author:{username} -is:pr is:public")
    
    print(f"Found {pull_requests.totalCount} PRs and {issues.totalCount} issues for {username}.")
    
    return pull_requests, issues

def generate_markdown_table(stats_dict):
    """Generates Markdown text from the statistics dictionary."""
    markdown_text = ""
    for username, stats in stats_dict.items():
        prs = stats['prs']
        issues = stats['issues']
        
        markdown_text += f"### 👤 {username}\n\n"
        
        # PR Table
        markdown_text += f"**Pull Requests ({prs.totalCount} total)**\n"
        if prs.totalCount > 0:
            markdown_text += "| Title | Repository | State |\n"
            markdown_text += "| ----- | ---------- | ----- |\n"
            # Iterate over a slice of the results to limit display
            for pr in prs[:MAX_ITEMS]:
                repo_name = pr.repository.full_name
                # Escape pipe characters in titles to prevent table corruption
                title = pr.title.replace('|', '\|')
                markdown_text += f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `{pr.state}` |\n"
        else:
            markdown_text += "_No public pull requests found._\n"
        markdown_text += "\n"

        # Issue Table
        markdown_text += f"**Issues ({issues.totalCount} total)**\n"
        if issues.totalCount > 0:
            markdown_text += "| Title | Repository | State |\n"
            markdown_text += "| ----- | ---------- | ----- |\n"
            # Iterate over a slice of the results to limit display
            for issue in issues[:MAX_ITEMS]:
                repo_name = issue.repository.full_name
                title = issue.title.replace('|', '\|')
                markdown_text += f"| [{title}]({issue.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `{issue.state}` |\n"
        else:
            markdown_text += "_No public issues found._\n"
        markdown_text += "\n"
        
    return markdown_text

def update_readme(new_content):
    """Writes the new content into the README between the specified markers."""
    try:
        with open(README_PATH, 'r', encoding='utf-8') as f:
            readme_content = f.read()
    except FileNotFoundError:
        print(f"Error: {README_PATH} not found. Please ensure the file exists.")
        return

    # Use a regular expression to replace the content between the markers
    new_readme = re.sub(
        r"(?s)(.*?)",
        f"\n{new_content}\n",
        readme_content
    )
    
    with open(README_PATH, 'w', encoding='utf-8') as f:
        f.write(new_readme)
    print("README.md updated successfully.")

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        raise ValueError("GH_PAT environment variable not set. Please provide a GitHub Personal Access Token.")
        
    g = Github(GITHUB_TOKEN)
    all_user_stats = {}
    for user in USERNAMES:
        user_prs, user_issues = get_user_stats(g, user)
        all_user_stats[user] = {"prs": user_prs, "issues": user_issues}
        
    markdown_output = generate_markdown_table(all_user_stats)
    update_readme(markdown_output)
