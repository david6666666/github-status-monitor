import os
import re
import requests
from datetime import datetime
from github import Github

# =================================CONFIG=================================
# The GitHub usernames you want to track
USERNAMES = ["david6666666", "hsliuustc0106", "fake0fan", "Gongzq5", "zhouyeju", "knlnguyen1802", "R2-Y", "natureofnature", "ahengljh", "syedmba", "wuhang2"]
# Your GitHub Personal Access Token, read from an environment variable
GITHUB_TOKEN = os.getenv('GH_PAT')
# The output filename for the chart
CHART_FILENAME = "stats_chart.svg"
# Start date for the search query to include older repositories
SEARCH_START_DATE = "2015-01-01"
# Fixed README filename
README_FILENAME = "README_data.md"
# =======================================================================

def get_user_display_name(github_instance, username):
    """
    获取用户的显示名称，如果没有则使用用户名
    """
    try:
        user = github_instance.get_user(username)
        display_name = user.name if user.name else username
        print(f"Display name for {username}: {display_name}")
        return display_name
    except Exception as e:
        print(f"Error fetching display name for {username}: {e}")
        return username

def get_user_stats(github_instance, username):
    """
    Fetches PRs (open and merged) and Issues (open and closed) for a user.
    Includes a date qualifier to find stats in older repositories.
    """
    print(f"Fetching data for {username}...")
    
    date_qualifier = f"updated:>={SEARCH_START_DATE}"

    # 1. PRs: Query for open and merged PRs separately
    query_open_prs = f"is:pr author:{username} is:public is:open {date_qualifier}"
    query_merged_prs = f"is:pr author:{username} is:public is:merged {date_qualifier}"
    
    open_prs = github_instance.search_issues(query_open_prs)
    merged_prs = github_instance.search_issues(query_merged_prs)
    
    # 2. Issues: Query for open and closed issues
    query_issues = f"is:issue author:{username} -is:pr is:public {date_qualifier}"
    issues = github_instance.search_issues(query_issues)
    
    print(f"Found for {username}: {open_prs.totalCount} open PRs, {merged_prs.totalCount} merged PRs, {issues.totalCount} issues.")
    
    return {
        "open_prs": open_prs,
        "merged_prs": merged_prs,
        "issues": issues
    }

def generate_chart(user_data):
    """
    生成包含PR和Issue柱状图的子图
    """
    print("Generating new subplot chart with PR and Issue bar charts...")
    
    # 准备数据
    usernames = [user['display_name'] for user in user_data]
    pr_counts = [user['stats']['open_prs'].totalCount + user['stats']['merged_prs'].totalCount for user in user_data]
    issue_counts = [user['stats']['issues'].totalCount for user in user_data]
    
    print(f"Chart data - Users: {usernames}")
    print(f"Chart data - PR counts: {pr_counts}")
    print(f"Chart data - Issue counts: {issue_counts}")
    
    # 创建子图配置
    chart_config = {
        "type": "bar",
        "data": {
            "labels": usernames,
            "datasets": [
                {
                    "label": "Pull Requests",
                    "data": pr_counts,
                    "backgroundColor": "rgba(54, 162, 235, 0.8)",
                    "borderColor": "rgba(54, 162, 235, 1)",
                    "borderWidth": 1
                },
                {
                    "label": "Issues",
                    "data": issue_counts,
                    "backgroundColor": "rgba(255, 99, 132, 0.8)",
                    "borderColor": "rgba(255, 99, 132, 1)",
                    "borderWidth": 1
                }
            ]
        },
        "options": {
            "responsive": True,
            "title": {
                "display": True,
                "text": "用户贡献统计 - PR和Issue数量对比",
                "fontSize": 16
            },
            "scales": {
                "yAxes": [{
                    "ticks": {
                        "beginAtZero": True,
                        "stepSize": 1
                    },
                    "scaleLabel": {
                        "display": True,
                        "labelString": "数量"
                    }
                }],
                "xAxes": [{
                    "scaleLabel": {
                        "display": True,
                        "labelString": "用户"
                    }
                }]
            },
            "legend": {
                "position": "top"
            },
            "plugins": {
                "datalabels": {
                    "anchor": "end",
                    "align": "top",
                    "color": "#444",
                    "font": {
                        "weight": "bold"
                    }
                }
            }
        }
    }
    
    qc_url = "https://quickchart.io/chart"
    response = requests.post(qc_url, json={"chart": chart_config, "format": "svg", "width": 1000, "height": 600})
    
    if response.status_code == 200:
        with open(CHART_FILENAME, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"Chart saved successfully as {CHART_FILENAME}")
    else:
        print(f"Error generating chart: {response.status_code} {response.text}")

def generate_markdown(user_data):
    """Generates Markdown text for tables from the sorted user data."""
    markdown_text = f"这是根据总贡献（Merged PRs + Open PRs + Issues）进行的排序。\n\n"
    markdown_text += f"总共追踪了 {len(user_data)} 个用户的贡献情况。\n\n"
    
    for user in user_data:
        username = user['username']
        display_name = user['display_name']
        stats = user['stats']
        total_contributions = user['total_contributions']
        
        # 显示用户名和显示名称
        if display_name != username:
            markdown_text += f"### 👤 {display_name} (@{username}) - 总贡献: {total_contributions}\n\n"
        else:
            markdown_text += f"### 👤 {username} - 总贡献: {total_contributions}\n\n"
        
        # PR Table
        markdown_text += f"**Pull Requests ({stats['open_prs'].totalCount} open, {stats['merged_prs'].totalCount} merged)**\n"
        
        # Process PRs by type to assign the correct state, then sort.
        pr_rows = []
        
        # Process merged PRs
        for pr in stats['merged_prs']:
            repo_name = pr.repository.full_name
            title = pr.title.replace('|', '\|')
            row_string = f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `merged` |\n"
            pr_rows.append((pr.created_at, row_string))
            
        # Process open PRs
        for pr in stats['open_prs']:
            repo_name = pr.repository.full_name
            title = pr.title.replace('|', '\|')
            row_string = f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `open` |\n"
            pr_rows.append((pr.created_at, row_string))

        if pr_rows:
            markdown_text += "| Title | Repository | State |\n"
            markdown_text += "| ----- | ---------- | ----- |\n"
            
            # Sort all PRs by creation date, descending
            pr_rows.sort(key=lambda x: x[0], reverse=True)
            
            # Add ALL rows to the markdown
            for _, row_string in pr_rows:
                markdown_text += row_string
        else:
            markdown_text += "_No relevant pull requests found._\n"
        markdown_text += "\n"

        # Issue Table
        markdown_text += f"**Issues ({stats['issues'].totalCount} total)**\n"
        if stats['issues'].totalCount > 0:
            markdown_text += "| Title | Repository | State |\n"
            markdown_text += "| ----- | ---------- | ----- |\n"
            # Show ALL issues
            for issue in stats['issues']:
                repo_name = issue.repository.full_name
                title = issue.title.replace('|', '\|')
                markdown_text += f"| [{title}]({issue.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `{issue.state}` |\n"
        else:
            markdown_text += "_No public issues found._\n"
        markdown_text += "\n"
        
    return markdown_text

def create_fixed_readme(content):
    """Creates a README file with fixed filename."""
    # 确保先删除已存在的文件
    if os.path.exists(README_FILENAME):
        os.remove(README_FILENAME)
        print(f"Removed existing {README_FILENAME}")
    
    # Create the full README content with header
    readme_header = f"# GitHub Stats Report\n\n"
    readme_header += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
    readme_header += f"![GitHub Stats Chart]({CHART_FILENAME})\n\n"
    readme_header += "---\n\n"
    
    full_content = readme_header + content
    
    # Write to the fixed filename with explicit encoding
    with open(README_FILENAME, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    print(f"README created successfully: {README_FILENAME}")
    print(f"README file size: {os.path.getsize(README_FILENAME)} bytes")
    return README_FILENAME

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        raise ValueError("GH_PAT environment variable not set.")
        
    print(f"Starting GitHub stats generation for {len(USERNAMES)} users...")
    print(f"Users to track: {USERNAMES}")
    
    github = Github(GITHUB_TOKEN)
    
    all_user_data = []
    for username in USERNAMES:
        try:
            display_name = get_user_display_name(github, username)
            stats = get_user_stats(github, username)
            total_contributions = stats['merged_prs'].totalCount + stats['open_prs'].totalCount + stats['issues'].totalCount
            all_user_data.append({
                "username": username,
                "display_name": display_name,
                "stats": stats,
                "total_contributions": total_contributions
            })
            print(f"Successfully processed {username} with {total_contributions} total contributions")
        except Exception as e:
            print(f"Error processing user {username}: {e}")
            # 继续处理其他用户
            continue
        
    print(f"Successfully processed {len(all_user_data)} users")
    all_user_data.sort(key=lambda x: x['total_contributions'], reverse=True)
    
    generate_chart(all_user_data)
    markdown_output = generate_markdown(all_user_data)
    readme_filename = create_fixed_readme(markdown_output)

    print(f"\n✅ All tasks completed successfully. README saved as: {readme_filename}")
    print(f"Processed users: {[user['username'] for user in all_user_data]}")
