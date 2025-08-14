import os
from github import Github
import re

# =================================CONFIG=================================
# 需要统计的 GitHub 用户名列表
USERNAMES = ["david6666666", "hsliuustc0106", "fake0fan"]
# 要更新的 README 文件路径
README_PATH = "README.md"
# GitHub 个人访问令牌，从环境变量中读取
GITHUB_TOKEN = os.getenv('GH_PAT')
# =======================================================================

def get_user_stats(github_instance, username):
    """获取用户的 PR 和 Issue 信息"""
    print(f"Fetching data for {username}...")
    # 获取公开的 PRs
    pull_requests = github_instance.search_issues(f"is:pr author:{username} is:public")
    # 获取公开的 Issues (并排除 PRs)
    issues = github_instance.search_issues(f"is:issue author:{username} -is:pr is:public")
    
    # 限制每个用户的条目数量，防止 README 过长
    pr_list = [pr for pr in pull_requests[:10]]
    issue_list = [issue for issue in issues[:10]]
    print(f"Found {pull_requests.totalCount} PRs, {issues.totalCount} issues for {username}. Displaying top 10 each.")
    
    return pr_list, issue_list

def generate_markdown_table(stats_dict):
    """根据统计数据生成 Markdown 文本"""
    markdown_text = ""
    for username, stats in stats_dict.items():
        markdown_text += f"### 👤 {username}\n\n"
        
        # PR 表格
        markdown_text += f"**Pull Requests ({stats['prs'].totalCount} total)**\n"
        if stats['prs']:
            markdown_text += "| Title | Repository | State |\n"
            markdown_text += "| ----- | ---------- | ----- |\n"
            for pr in stats['prs']:
                repo_name = pr.repository.full_name
                title = pr.title.replace('|', '\|') # 转义标题中的竖线
                markdown_text += f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `{pr.state}` |\n"
        else:
            markdown_text += "_No public pull requests found._\n"
        markdown_text += "\n"

        # Issue 表格
        markdown_text += f"**Issues ({stats['issues'].totalCount} total)**\n"
        if stats['issues']:
            markdown_text += "| Title | Repository | State |\n"
            markdown_text += "| ----- | ---------- | ----- |\n"
            for issue in stats['issues']:
                repo_name = issue.repository.full_name
                title = issue.title.replace('|', '\|')
                markdown_text += f"| [{title}]({issue.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `{issue.state}` |\n"
        else:
            markdown_text += "_No public issues found._\n"
        markdown_text += "\n"
        
    return markdown_text

def update_readme(new_content):
    """将新内容写入 README 的标记之间"""
    with open(README_PATH, 'r', encoding='utf-8') as f:
        readme_content = f.read()
    
    # 使用正则表达式替换标记之间的内容
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
    all_stats = {}
    for user in USERNAMES:
        prs, issues = get_user_stats(g, user)
        all_stats[user] = {"prs": prs, "issues": issues}
        
    markdown_output = generate_markdown_table(all_stats)
    update_readme(markdown_output)
