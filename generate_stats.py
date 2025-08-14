import os
import re
import requests
from github import Github

# =================================CONFIG=================================
USERNAMES = ["david6666666", "hsliuustc0106", "fake0fan"]
README_PATH = "README.md"
GITHUB_TOKEN = os.getenv('GH_PAT')
MAX_ITEMS_PER_TABLE = 5
CHART_FILENAME = "stats_chart.svg"
# =======================================================================

def get_user_stats(github_instance, username):
    print(f"Fetching data for {username}...")
    
    # [FIX] Reverted to the most standard query for merged PRs, removing date qualifiers.
    query_open_prs = f"is:pr author:{username} is:public is:open"
    query_merged_prs = f"is:pr author:{username} is:public is:merged"
    query_issues = f"is:issue author:{username} -is:pr is:public"
    
    open_prs = github_instance.search_issues(query_open_prs)
    merged_prs = github_instance.search_issues(query_merged_prs)
    issues = github_instance.search_issues(query_issues)
    
    print(f"Found for {username}: {open_prs.totalCount} open PRs, {merged_prs.totalCount} merged PRs, {issues.totalCount} issues.")
    return {"open_prs": open_prs, "merged_prs": merged_prs, "issues": issues}

def generate_chart(user_data):
    print("Generating doughnut chart...")
    labels = [user['username'] for user in user_data]
    data = [user['total_contributions'] for user in user_data]
    colors = ['rgba(110, 107, 213, 0.8)', 'rgba(40, 167, 69, 0.8)', 'rgba(255, 159, 64, 0.8)', 'rgba(255, 99, 132, 0.8)', 'rgba(54, 162, 235, 0.8)']
    chart_config = {"type":"doughnut","data":{"labels":labels,"datasets":[{"data":data,"backgroundColor":colors,"borderColor":"#ffffff","borderWidth":2}]},"options":{"title":{"display":True,"text":"用户总贡献占比"},"legend":{"position":"right"},"plugins":{"datalabels":{"color":"#ffffff","formatter":"(value) => { return value > 0 ? value : ''; }"}}}}
    
    response = requests.post("https://quickchart.io/chart", json={"chart": chart_config, "format": "svg"})
    if response.status_code == 200:
        with open(CHART_FILENAME, 'w', encoding='utf-8') as f: f.write(response.text)
        print(f"Chart saved successfully as {CHART_FILENAME}")
    else:
        print(f"Error generating chart: {response.status_code} {response.text}")

def generate_markdown(user_data):
    markdown_text = "这是根据总贡献（Merged PRs + Open PRs + Issues）进行的排序。\n\n"
    for user in user_data:
        username, stats = user['username'], user['stats']
        markdown_text += f"### 👤 {username}\n\n**Pull Requests ({stats['open_prs'].totalCount} open, {stats['merged_prs'].totalCount} merged)**\n"
        pr_rows = []
        for pr in stats['merged_prs']: pr_rows.append((pr.created_at, f"| [{pr.title.replace('|', '\|')}]({pr.html_url}) | [{pr.repository.full_name}](https://github.com/{pr.repository.full_name}) | `merged` |\n"))
        for pr in stats['open_prs']: pr_rows.append((pr.created_at, f"| [{pr.title.replace('|', '\|')}]({pr.html_url}) | [{pr.repository.full_name}](https://github.com/{pr.repository.full_name}) | `open` |\n"))
        if pr_rows:
            markdown_text += "| Title | Repository | State |\n| ----- | ---------- | ----- |\n"
            pr_rows.sort(key=lambda x: x[0], reverse=True)
            for _, row_string in pr_rows[:MAX_ITEMS_PER_TABLE]: markdown_text += row_string
        else: markdown_text += "_No relevant pull requests found._\n"
        markdown_text += "\n"
        markdown_text += f"**Issues ({stats['issues'].totalCount} total)**\n"
        if stats['issues'].totalCount > 0:
            markdown_text += "| Title | Repository | State |\n| ----- | ---------- | ----- |\n"
            for issue in stats['issues'][:MAX_ITEMS_PER_TABLE]: markdown_text += f"| [{issue.title.replace('|', '\|')}]({issue.html_url}) | [{issue.repository.full_name}](https://github.com/{issue.repository.full_name}) | `{issue.state}` |\n"
        else: markdown_text += "_No public issues found._\n"
        markdown_text += "\n"
    return markdown_text

def update_readme(content):
    with open(README_PATH, 'r', encoding='utf-8') as f: readme_content = f.read()
    start_marker, end_marker = "", ""
    if start_marker not in readme_content or end_marker not in readme_content:
        raise ValueError(f"CRITICAL ERROR: Markers '{start_marker}' or '{end_marker}' not found in {README_PATH}. Aborting to prevent file corruption.")
    new_readme = re.sub(rf"(?s){start_marker}(.*?){end_marker}", f"{start_marker}\n{content}\n{end_marker}", readme_content)
    with open(README_PATH, 'w', encoding='utf-8') as f: f.write(new_readme)
    print("README.md updated successfully in memory.")

if __name__ == "__main__":
    if not GITHUB_TOKEN: raise ValueError("GH_PAT environment variable not set.")
    github = Github(GITHUB_TOKEN)
    all_user_data = []
    for username in USERNAMES:
        stats = get_user_stats(github, username)
        total_contributions = stats['merged_prs'].totalCount + stats['open_prs'].totalCount + stats['issues'].totalCount
        all_user_data.append({"username": username, "stats": stats, "total_contributions": total_contributions})
    all_user_data.sort(key=lambda x: x['total_contributions'], reverse=True)
    generate_chart(all_user_data)
    markdown_output = generate_markdown(all_user_data)
    update_readme(markdown_output)
    print("\n✅ All tasks completed successfully.")
