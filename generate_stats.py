import os
import re
import requests
from datetime import datetime
from github import Github

# =================================CONFIG=================================
# The GitHub usernames you want to track
USERNAMES = ["david6666666", "hsliuustc0106", "fake0fan", "Gongzq5", "zhouyeju", "knlnguyen1802", "R2-Y", "natureofnature", "ahengljh", "syedmba", "wuhang2014"]
# Your GitHub Personal Access Token, read from an environment variable
GITHUB_TOKEN = os.getenv('GH_PAT')
# The output filename for the chart
CHART_FILENAME = "stats_chart.svg"
# Start date for the search query - only after 2025-06-30
SEARCH_START_DATE = "2025-06-30"
# Target organization - only vllm-project
TARGET_ORG = "vllm-project"
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
    Only includes data from vllm-project organization after 2025-06-30.
    """
    print(f"Fetching data for {username} in {TARGET_ORG} organization after {SEARCH_START_DATE}...")
    
    # Date qualifier for filtering by creation/update date
    date_qualifier = f"created:>={SEARCH_START_DATE}"
    # Organization qualifier
    org_qualifier = f"org:{TARGET_ORG}"

    # 1. PRs: Query for open and merged PRs separately in vllm-project organization
    query_open_prs = f"is:pr author:{username} is:public is:open {org_qualifier} {date_qualifier}"
    query_merged_prs = f"is:pr author:{username} is:public is:merged {org_qualifier} {date_qualifier}"
    
    print(f"Open PR query: {query_open_prs}")
    print(f"Merged PR query: {query_merged_prs}")
    
    open_prs = github_instance.search_issues(query_open_prs)
    merged_prs = github_instance.search_issues(query_merged_prs)
    
    # 2. Issues: Query for open and closed issues in vllm-project organization
    query_issues = f"is:issue author:{username} -is:pr is:public {org_qualifier} {date_qualifier}"
    print(f"Issues query: {query_issues}")
    
    issues = github_instance.search_issues(query_issues)
    
    print(f"Found for {username} in {TARGET_ORG}: {open_prs.totalCount} open PRs, {merged_prs.totalCount} merged PRs, {issues.totalCount} issues.")
    
    return {
        "open_prs": open_prs,
        "merged_prs": merged_prs,
        "issues": issues
    }

def generate_chart(user_data):
    """
    生成包含分离的Open PR、Merged PR和Issue柱状图的子图
    """
    print("Generating new grouped bar chart with separated PR types and Issues...")
    
    # 准备数据 - 确保所有用户都包含在内，即使数据为0
    usernames = []
    open_pr_counts = []
    merged_pr_counts = []
    issue_counts = []
    
    for user in user_data:
        usernames.append(user['display_name'])
        open_pr_counts.append(user['stats']['open_prs'].totalCount)
        merged_pr_counts.append(user['stats']['merged_prs'].totalCount)
        issue_counts.append(user['stats']['issues'].totalCount)
    
    print(f"Chart data - Users: {usernames}")
    print(f"Chart data - Open PR counts: {open_pr_counts}")
    print(f"Chart data - Merged PR counts: {merged_pr_counts}")
    print(f"Chart data - Issue counts: {issue_counts}")
    
    # 创建分组柱状图配置
    chart_config = {
        "type": "bar",
        "data": {
            "labels": usernames,
            "datasets": [
                {
                    "label": "Open PRs",
                    "data": open_pr_counts,
                    "backgroundColor": "rgba(255, 193, 7, 0.8)",  # 黄色 - Open PRs
                    "borderColor": "rgba(255, 193, 7, 1)",
                    "borderWidth": 1
                },
                {
                    "label": "Merged PRs",
                    "data": merged_pr_counts,
                    "backgroundColor": "rgba(40, 167, 69, 0.8)",  # 绿色 - Merged PRs
                    "borderColor": "rgba(40, 167, 69, 1)",
                    "borderWidth": 1
                },
                {
                    "label": "Issues",
                    "data": issue_counts,
                    "backgroundColor": "rgba(220, 53, 69, 0.8)",  # 红色 - Issues
                    "borderColor": "rgba(220, 53, 69, 1)",
                    "borderWidth": 1
                }
            ]
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "title": {
                "display": True,
                "text": f"{TARGET_ORG} 组织贡献统计 (自 {SEARCH_START_DATE})",
                "fontSize": 18,
                "fontColor": "#333"
            },
            "scales": {
                "yAxes": [{
                    "ticks": {
                        "beginAtZero": True,
                        "stepSize": 1,
                        "fontSize": 12
                    },
                    "scaleLabel": {
                        "display": True,
                        "labelString": "数量",
                        "fontSize": 14
                    },
                    "gridLines": {
                        "color": "rgba(0,0,0,0.1)"
                    }
                }],
                "xAxes": [{
                    "scaleLabel": {
                        "display": True,
                        "labelString": "用户",
                        "fontSize": 14
                    },
                    "ticks": {
                        "fontSize": 10,
                        "maxRotation": 45,
                        "minRotation": 0
                    },
                    "gridLines": {
                        "display": False
                    }
                }]
            },
            "legend": {
                "position": "top",
                "labels": {
                    "fontSize": 12,
                    "padding": 20
                }
            },
            "plugins": {
                "datalabels": {
                    "display": function(context) {
                        # 只在数值大于0时显示标签
                        return context.parsed.y > 0;
                    },
                    "anchor": "end",
                    "align": "top",
                    "color": "#333",
                    "font": {
                        "size": 10,
                        "weight": "bold"
                    },
                    "formatter": function(value) {
                        # 只显示非零值
                        return value > 0 ? value : '';
                    }
                }
            },
            "layout": {
                "padding": {
                    "top": 30,
                    "bottom": 10,
                    "left": 10,
                    "right": 10
                }
            }
        }
    }
    
    # 发送请求到QuickChart API
    qc_url = "https://quickchart.io/chart"
    try:
        response = requests.post(
            qc_url, 
            json={
                "chart": chart_config, 
                "format": "svg", 
                "width": 1200, 
                "height": 700,
                "backgroundColor": "white"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            with open(CHART_FILENAME, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"Chart saved successfully as {CHART_FILENAME}")
        else:
            print(f"Error generating chart: {response.status_code}")
            if response.text:
                print(f"Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error making request to QuickChart: {e}")
    except Exception as e:
        print(f"Unexpected error generating chart: {e}")

def generate_markdown(user_data):
    """Generates Markdown text for tables from the sorted user data."""
    markdown_text = f"这是根据在 **{TARGET_ORG}** 组织中自 **{SEARCH_START_DATE}** 以来的总贡献（Merged PRs + Open PRs + Issues）进行的排序。\n\n"
    markdown_text += f"总共追踪了 {len(user_data)} 个用户在 {TARGET_ORG} 组织中的贡献情况。\n\n"
    
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
            created_date = pr.created_at.strftime('%Y-%m-%d')
            row_string = f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `merged` | {created_date} |\n"
            pr_rows.append((pr.created_at, row_string))
            
        # Process open PRs
        for pr in stats['open_prs']:
            repo_name = pr.repository.full_name
            title = pr.title.replace('|', '\|')
            created_date = pr.created_at.strftime('%Y-%m-%d')
            row_string = f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `open` | {created_date} |\n"
            pr_rows.append((pr.created_at, row_string))

        if pr_rows:
            markdown_text += "| Title | Repository | State | Created |\n"
            markdown_text += "| ----- | ---------- | ----- | ------- |\n"
            
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
            markdown_text += "| Title | Repository | State | Created |\n"
            markdown_text += "| ----- | ---------- | ----- | ------- |\n"
            # Show ALL issues
            for issue in stats['issues']:
                repo_name = issue.repository.full_name
                title = issue.title.replace('|', '\|')
                created_date = issue.created_at.strftime('%Y-%m-%d')
                markdown_text += f"| [{title}]({issue.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `{issue.state}` | {created_date} |\n"
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
    readme_header = f"# GitHub Stats Report - {TARGET_ORG} Organization\n\n"
    readme_header += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
    readme_header += f"**统计范围**: {TARGET_ORG} 组织\n"
    readme_header += f"**统计时间**: {SEARCH_START_DATE} 以后\n\n"
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
    print(f"Target organization: {TARGET_ORG}")
    print(f"Date range: after {SEARCH_START_DATE}")
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
            print(f"Successfully processed {username} with {total_contributions} total contributions in {TARGET_ORG}")
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
