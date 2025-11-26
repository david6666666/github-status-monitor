import os
import re
import requests
import time
from datetime import datetime
from github import Github

# =================================CONFIG=================================
# The GitHub usernames you want to track
USERNAMES = ["david6666666", "hsliuustc0106", "fake0fan", "LJH-LBJ", "knlnguyen1802", "R2-Y", "natureofnature", "ahengljh", "syedmba", "wuhang2014", "chickeyton", "Gaohan123", "SamitHuang", "jiangkuaixue123", "tangtiangu"]
# Your GitHub Personal Access Token, read from an environment variable
GITHUB_TOKEN = os.getenv('GH_PAT')
# The output filename for the chart
CHART_FILENAME = "stats_chart.svg"
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

def get_pr_additions_deletions(github_instance, pr):
    """
    获取PR的additions和deletions数据
    """
    try:
        # 获取PR的详细信息
        repo = github_instance.get_repo(pr.repository.full_name)
        pr_detail = repo.get_pull(pr.number)
        
        additions = pr_detail.additions if pr_detail.additions is not None else 0
        deletions = pr_detail.deletions if pr_detail.deletions is not None else 0
        
        print(f"    PR #{pr.number}: +{additions} -{deletions}")
        return additions, deletions
        
    except Exception as e:
        print(f"    Error fetching additions/deletions for PR #{pr.number}: {e}")
        return 0, 0

def count_actual_items(search_result, item_type="items"):
    """
    计算搜索结果中的实际项目数量
    """
    try:
        items = list(search_result)
        actual_count = len(items)
        print(f"  Actual {item_type} counted: {actual_count}")
        return actual_count, items
    except Exception as e:
        print(f"  Error counting actual items: {e}")
        return 0, []

def get_user_stats_fallback(github_instance, username):
    """
    备用方法：直接从组织的仓库中获取用户的PR和Issue统计
    """
    print(f"  Using fallback method for {username}...")
    
    open_prs = []
    merged_prs = []
    issues = []
    
    try:
        # 获取组织对象
        org = github_instance.get_organization(TARGET_ORG)
        
        # 遍历组织中的所有仓库
        for repo in org.get_repos():
            try:
                # 获取该用户在此仓库中的PRs
                all_prs = repo.get_pulls(state='all')
                for pr in all_prs:
                    if pr.user.login == username:
                        if pr.state == 'open':
                            open_prs.append(pr)
                        elif pr.merged:
                            merged_prs.append(pr)
                
                # 获取该用户在此仓库中的Issues
                all_issues = repo.get_issues(state='all')
                for issue in all_issues:
                    if issue.user.login == username and not issue.pull_request:
                        issues.append(issue)
                        
            except Exception as e:
                print(f"    Error processing repo {repo.name}: {e}")
                continue
                
        print(f"  Fallback results for {username}: {len(open_prs)} open PRs, {len(merged_prs)} merged PRs, {len(issues)} issues")
        
        # 创建包装对象
        class FallbackResult:
            def __init__(self, items):
                self._items = items
                self.totalCount = len(items)
            def __iter__(self):
                return iter(self._items)
        
        return {
            "open_prs": FallbackResult(open_prs),
            "merged_prs": FallbackResult(merged_prs),
            "issues": FallbackResult(issues)
        }
        
    except Exception as e:
        print(f"  Fallback method failed for {username}: {e}")
        # 返回空结果
        class EmptyResult:
            def __init__(self):
                self.totalCount = 0
                self._items = []
            def __iter__(self):
                return iter(self._items)
        
        return {
            "open_prs": EmptyResult(),
            "merged_prs": EmptyResult(),
            "issues": EmptyResult()
        }

def get_user_stats(github_instance, username):
    """
    Fetches PRs (open and merged) and Issues (open and closed) for a user.
    Includes all data from vllm-project organization (no date restrictions).
    """
    print(f"Fetching all data for {username} in {TARGET_ORG} organization...")
    
    # Organization qualifier
    org_qualifier = f"org:{TARGET_ORG}"

    # 1. PRs: Query for open and merged PRs separately in vllm-project organization
    query_open_prs = f"is:pr author:{username} is:public is:open {org_qualifier}"
    query_merged_prs = f"is:pr author:{username} is:public is:merged {org_qualifier}"
    
    print(f"  Open PR query: {query_open_prs}")
    print(f"  Merged PR query: {query_merged_prs}")
    
    # 添加延迟以避免API限制
    time.sleep(1)
    
    try:
        open_prs = github_instance.search_issues(query_open_prs)
        merged_prs = github_instance.search_issues(query_merged_prs)
        
        print(f"  ✓ Search API Success for {username}")
        print(f"    Open PRs totalCount: {open_prs.totalCount}")
        print(f"    Merged PRs totalCount: {merged_prs.totalCount}")
        
        # 验证totalCount的准确性
        actual_open_count, open_items = count_actual_items(open_prs, "open PRs")
        actual_merged_count, merged_items = count_actual_items(merged_prs, "merged PRs")
        
        # 如果totalCount不准确，使用实际计数
        if open_prs.totalCount != actual_open_count:
            print(f"  ⚠️  Open PR count mismatch: API={open_prs.totalCount}, Actual={actual_open_count}")
            open_prs.totalCount = actual_open_count
            
        if merged_prs.totalCount != actual_merged_count:
            print(f"  ⚠️  Merged PR count mismatch: API={merged_prs.totalCount}, Actual={actual_merged_count}")
            merged_prs.totalCount = actual_merged_count
        
    except Exception as e:
        print(f"  ✗ Search API Error for {username}: {type(e).__name__}: {e}")
        print(f"    Switching to fallback method...")
        
        # 使用备用方法
        return get_user_stats_fallback(github_instance, username)
    
    # 2. Issues: Query for all issues in vllm-project organization
    query_issues = f"is:issue author:{username} -is:pr is:public {org_qualifier}"
    print(f"  Issues query: {query_issues}")
    
    # 添加延迟
    time.sleep(1)
    
    try:
        issues = github_instance.search_issues(query_issues)
        print(f"    Issues totalCount: {issues.totalCount}")
        
        # 验证Issues计数
        actual_issues_count, issues_items = count_actual_items(issues, "issues")
        if issues.totalCount != actual_issues_count:
            print(f"  ⚠️  Issues count mismatch: API={issues.totalCount}, Actual={actual_issues_count}")
            issues.totalCount = actual_issues_count
            
    except Exception as e:
        print(f"  ✗ Issues API Error for {username}: {type(e).__name__}: {e}")
        # 创建空的Issues结果
        class EmptyResult:
            def __init__(self):
                self.totalCount = 0
                self._items = []
            def __iter__(self):
                return iter(self._items)
        issues = EmptyResult()
    
    total_found = open_prs.totalCount + merged_prs.totalCount + issues.totalCount
    print(f"  Final counts for {username}: {open_prs.totalCount} open PRs, {merged_prs.totalCount} merged PRs, {issues.totalCount} issues (Total: {total_found})")
    
    return {
        "open_prs": open_prs,
        "merged_prs": merged_prs,
        "issues": issues
    }

def format_number(num):
    """
    格式化数字，添加千位分隔符
    """
    return f"{num:,}"

def generate_chart(user_data):
    """
    生成包含堆叠PR柱状图和独立Issue柱状图的图表，包含additions/deletions统计
    修改：将所有字体颜色改为黑色加粗
    """
    print(f"Generating enhanced chart for ALL {len(user_data)} users...")
    
    # 准备数据 - 确保所有用户都包含在内，即使数据为0
    usernames = []
    open_pr_counts = []
    merged_pr_counts = []
    issue_counts = []
    
    # 计算总数
    total_open_prs = 0
    total_merged_prs = 0
    total_issues = 0
    total_additions = 0
    total_deletions = 0
    
    for user in user_data:
        usernames.append(user['display_name'])
        open_count = user['stats']['open_prs'].totalCount
        merged_count = user['stats']['merged_prs'].totalCount
        issue_count = user['stats']['issues'].totalCount
        user_additions = user.get('total_additions', 0)
        user_deletions = user.get('total_deletions', 0)
        
        open_pr_counts.append(open_count)
        merged_pr_counts.append(merged_count)
        issue_counts.append(issue_count)
        
        total_open_prs += open_count
        total_merged_prs += merged_count
        total_issues += issue_count
        total_additions += user_additions
        total_deletions += user_deletions
    
    print(f"Chart will display {len(usernames)} users: {usernames}")
    print(f"Chart data - Open PR counts: {open_pr_counts} (Total: {total_open_prs})")
    print(f"Chart data - Merged PR counts: {merged_pr_counts} (Total: {total_merged_prs})")
    print(f"Chart data - Issue counts: {issue_counts} (Total: {total_issues})")
    print(f"Chart data - Total additions: {format_number(total_additions)}, Total deletions: {format_number(total_deletions)}")
    
    # 修复：确保宽度不超过 QuickChart 的限制 (3000px)
    max_allowed_width = 3000
    min_width = 1200
    # 根据用户数量动态计算，但限制在最大允许范围内
    calculated_width = max(min_width, min(len(user_data) * 200, max_allowed_width))
    chart_width = calculated_width
    chart_height = 800  # 降低高度以保持合理比例
    
    print(f"Chart dimensions adjusted: {chart_width}x{chart_height}px (within QuickChart limits)")
    
    # 修复：使用数组格式来表示多行标题，这是Chart.js的正确方式
    title_lines = [
        f"{TARGET_ORG} 组织贡献统计 - 共{len(user_data)}位用户",
        f"总计: Open PRs: {total_open_prs} | Merged PRs: {total_merged_prs} | Issues: {total_issues}",
        f"代码变更: +{format_number(total_additions)} -{format_number(total_deletions)}"
    ]
    
    # 创建堆叠柱状图配置 - 修改：所有字体颜色改为黑色加粗
    chart_config = {
        "type": "bar",
        "data": {
            "labels": usernames,
            "datasets": [
                {
                    "label": f"Open PRs (总计: {total_open_prs})",
                    "data": open_pr_counts,
                    "backgroundColor": "rgba(255, 193, 7, 0.9)",
                    "borderColor": "rgba(255, 193, 7, 1)",
                    "borderWidth": 2,
                    "stack": "PRs"
                },
                {
                    "label": f"Merged PRs (总计: {total_merged_prs})",
                    "data": merged_pr_counts,
                    "backgroundColor": "rgba(40, 167, 69, 0.9)",
                    "borderColor": "rgba(40, 167, 69, 1)",
                    "borderWidth": 2,
                    "stack": "PRs"
                },
                {
                    "label": f"Issues (总计: {total_issues})",
                    "data": issue_counts,
                    "backgroundColor": "rgba(220, 53, 69, 0.9)",
                    "borderColor": "rgba(220, 53, 69, 1)",
                    "borderWidth": 2,
                    "stack": "Issues"
                }
            ]
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "title": {
                "display": True,
                "text": title_lines,
                "fontSize": max(14, min(20, chart_width // 120)),
                "fontColor": "#000000",  # 修改：标题字体颜色改为黑色
                "fontStyle": "bold",     # 修改：标题字体加粗
                "padding": 25,
                "lineHeight": 1.2
            },
            "scales": {
                "yAxes": [{
                    "stacked": True,
                    "ticks": {
                        "beginAtZero": True,
                        "stepSize": 1,
                        "fontSize": max(10, min(16, chart_width // 200)),
                        "fontColor": "#000000",  # 修改：Y轴刻度字体颜色改为黑色
                        "fontStyle": "bold",     # 修改：Y轴刻度字体加粗
                        "padding": 5
                    },
                    "scaleLabel": {
                        "display": True,
                        "labelString": "贡献数量",
                        "fontSize": max(12, min(18, chart_width // 150)),
                        "fontColor": "#000000",  # 修改：Y轴标签字体颜色改为黑色
                        "fontStyle": "bold"      # 修改：Y轴标签字体加粗
                    },
                    "gridLines": {
                        "color": "rgba(0,0,0,0.15)",
                        "lineWidth": 1
                    }
                }],
                "xAxes": [{
                    "stacked": True,
                    "scaleLabel": {
                        "display": True,
                        "labelString": f"用户名称 (总代码变更: +{format_number(total_additions)} -{format_number(total_deletions)})",
                        "fontSize": max(12, min(18, chart_width // 150)),
                        "fontColor": "#000000",  # 修改：X轴标签字体颜色改为黑色
                        "fontStyle": "bold"      # 修改：X轴标签字体加粗
                    },
                    "ticks": {
                        "fontSize": max(8, min(14, chart_width // 250)),
                        "fontColor": "#000000",  # 修改：X轴刻度字体颜色改为黑色
                        "fontStyle": "bold",     # 修改：X轴刻度字体加粗
                        "maxRotation": 45,
                        "minRotation": 45,
                        "padding": 5
                    },
                    "gridLines": {
                        "display": False
                    }
                }]
            },
            "legend": {
                "position": "top",
                "labels": {
                    "fontSize": max(10, min(16, chart_width // 200)),
                    "fontColor": "#000000",  # 修改：图例字体颜色改为黑色
                    "fontStyle": "bold",     # 修改：图例字体加粗
                    "padding": 15,
                    "usePointStyle": True,
                    "pointStyle": "rect"
                }
            },
            "plugins": {
                "datalabels": {
                    "display": "function(context) { return context.parsed.y > 0; }",
                    "anchor": "center",
                    "align": "center",
                    "color": "#fff",
                    "font": {
                        "size": max(8, min(12, chart_width // 300)),
                        "weight": "bold"
                    },
                    "formatter": "function(value) { return value > 0 ? value : ''; }",
                    "textStrokeColor": "#000",
                    "textStrokeWidth": 1
                }
            },
            "layout": {
                "padding": {
                    "top": 50,
                    "bottom": 70,
                    "left": 15,
                    "right": 15
                }
            },
            "elements": {
                "rectangle": {
                    "borderSkipped": "bottom"
                }
            }
        }
    }
    
    print(f"Sending enhanced chart request for {len(usernames)} users...")
    print(f"Chart dimensions: {chart_width}x{chart_height}px (within API limits)")
    print(f"Total statistics: Open PRs: {total_open_prs}, Merged PRs: {total_merged_prs}, Issues: {total_issues}")
    print(f"Code changes: +{format_number(total_additions)} -{format_number(total_deletions)}")
    
    # 发送请求到QuickChart API
    qc_url = "https://quickchart.io/chart"
    try:
        response = requests.post(
            qc_url, 
            json={
                "chart": chart_config, 
                "format": "svg", 
                "width": chart_width,
                "height": chart_height,
                "backgroundColor": "white",
                "devicePixelRatio": 2
            },
            timeout=30
        )
        
        if response.status_code == 200:
            with open(CHART_FILENAME, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"✅ Enhanced chart with black bold fonts saved successfully as {CHART_FILENAME}")
            print(f"   Chart size: {chart_width}x{chart_height}px with {len(usernames)} users displayed")
            print(f"   Totals displayed: Open PRs: {total_open_prs}, Merged PRs: {total_merged_prs}, Issues: {total_issues}")
            print(f"   Code changes: +{format_number(total_additions)} -{format_number(total_deletions)}")
        else:
            print(f"❌ Error generating chart: {response.status_code}")
            if response.text:
                print(f"Response: {response.text}")
                
            # 如果仍然失败，尝试生成更小的图表
            if response.status_code == 400 and "width" in response.text.lower():
                print("⚠️  Trying with smaller dimensions...")
                smaller_config = chart_config.copy()
                response = requests.post(
                    qc_url, 
                    json={
                        "chart": smaller_config, 
                        "format": "svg", 
                        "width": 1200,
                        "height": 600,
                        "backgroundColor": "white",
                        "devicePixelRatio": 1
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    with open(CHART_FILENAME, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    print(f"✅ Smaller enhanced chart with black bold fonts saved successfully as {CHART_FILENAME}")
                else:
                    print(f"❌ Even smaller chart failed: {response.status_code}")
                    
    except requests.exceptions.RequestException as e:
        print(f"❌ Error making request to QuickChart: {e}")
    except Exception as e:
        print(f"❌ Unexpected error generating chart: {e}")

def generate_markdown(user_data):
    """生成包含additions/deletions统计的Markdown表格"""
    markdown_text = f"这是根据在 **{TARGET_ORG}** 组织中的总贡献（Merged PRs + Open PRs + Issues）进行的排序。\n\n"
    markdown_text += f"总共追踪了 {len(user_data)} 个用户在 {TARGET_ORG} 组织中的贡献情况。\n\n"
    
    # 计算总的additions和deletions
    total_all_additions = sum(user.get('total_additions', 0) for user in user_data)
    total_all_deletions = sum(user.get('total_deletions', 0) for user in user_data)
    
    markdown_text += f"**总代码变更统计**: +{format_number(total_all_additions)} 行添加, -{format_number(total_all_deletions)} 行删除\n\n"
    
    for user in user_data:
        username = user['username']
        display_name = user['display_name']
        stats = user['stats']
        total_contributions = user['total_contributions']
        user_additions = user.get('total_additions', 0)
        user_deletions = user.get('total_deletions', 0)
        
        # 显示用户名和显示名称，包含代码变更统计
        if display_name != username:
            markdown_text += f"### 👤 {display_name} (@{username}) - 总贡献: {total_contributions}\n"
        else:
            markdown_text += f"### 👤 {username} - 总贡献: {total_contributions}\n"
        
        markdown_text += f"**代码变更**: +{format_number(user_additions)} 行添加, -{format_number(user_deletions)} 行删除\n\n"
        
        # PR Table with additions/deletions
        markdown_text += f"**Pull Requests ({stats['open_prs'].totalCount} open, {stats['merged_prs'].totalCount} merged)**\n"
        
        # Process PRs by type to assign the correct state, then sort.
        pr_rows = []
        
        # Process merged PRs
        for pr in stats['merged_prs']:
            repo_name = pr.repository.full_name
            title = pr.title.replace('|', '\|')
            created_date = pr.created_at.strftime('%Y-%m-%d')
            
            # 获取PR的additions和deletions (如果已存储)
            additions = getattr(pr, '_additions', 0)
            deletions = getattr(pr, '_deletions', 0)
            
            row_string = f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `merged` | {created_date} | {format_number(additions)} | {format_number(deletions)} |\n"
            pr_rows.append((pr.created_at, row_string))
            
        # Process open PRs
        for pr in stats['open_prs']:
            repo_name = pr.repository.full_name
            title = pr.title.replace('|', '\|')
            created_date = pr.created_at.strftime('%Y-%m-%d')
            
            # 获取PR的additions和deletions (如果已存储)
            additions = getattr(pr, '_additions', 0)
            deletions = getattr(pr, '_deletions', 0)
            
            row_string = f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `open` | {created_date} | {format_number(additions)} | {format_number(deletions)} |\n"
            pr_rows.append((pr.created_at, row_string))

        if pr_rows:
            markdown_text += "| Title | Repository | State | Created | Additions | Deletions |\n"
            markdown_text += "| ----- | ---------- | ----- | ------- | --------- | --------- |\n"
            
            # Sort all PRs by creation date, descending
            pr_rows.sort(key=lambda x: x[0], reverse=True)
            
            # Add ALL rows to the markdown
            for _, row_string in pr_rows:
                markdown_text += row_string
                
            # Add user totals row
            markdown_text += f"| **Total for {display_name}** | | | | **{format_number(user_additions)}** | **{format_number(user_deletions)}** |\n"
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
    readme_header = f"# Enhanced GitHub Stats Report - {TARGET_ORG} Organization\n\n"
    readme_header += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
    readme_header += f"**统计范围**: {TARGET_ORG} 组织的所有贡献（包含代码变更统计）\n\n"
    readme_header += f"![Enhanced GitHub Stats Chart]({CHART_FILENAME})\n\n"
    readme_header += "---\n\n"
    
    full_content = readme_header + content
    
    # Write to the fixed filename with explicit encoding
    with open(README_FILENAME, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    print(f"Enhanced README created successfully: {README_FILENAME}")
    print(f"README file size: {os.path.getsize(README_FILENAME)} bytes")
    return README_FILENAME

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        raise ValueError("GH_PAT environment variable not set.")
        
    print(f"Starting Enhanced GitHub stats generation for {len(USERNAMES)} users...")
    print(f"Target organization: {TARGET_ORG}")
    print(f"Including all contributions with additions/deletions tracking")
    print(f"Users to track: {USERNAMES}")
    
    github = Github(GITHUB_TOKEN)
    
    all_user_data = []
    for username in USERNAMES:
        try:
            print(f"\n{'='*50}")
            print(f"Processing user: {username}")
            
            display_name = get_user_display_name(github, username)
            stats = get_user_stats(github, username)
            total_contributions = stats['merged_prs'].totalCount + stats['open_prs'].totalCount + stats['issues'].totalCount
            
            # 获取PR的additions和deletions
            print(f"  Fetching additions/deletions for {username}'s PRs...")
            user_total_additions = 0
            user_total_deletions = 0
            
            # 处理merged PRs
            for pr in stats['merged_prs']:
                try:
                    additions, deletions = get_pr_additions_deletions(github, pr)
                    pr._additions = additions
                    pr._deletions = deletions
                    user_total_additions += additions
                    user_total_deletions += deletions
                    time.sleep(0.5)  # API rate limiting
                except Exception as e:
                    print(f"    Error processing merged PR #{pr.number}: {e}")
                    pr._additions = 0
                    pr._deletions = 0
            
            # 处理open PRs
            for pr in stats['open_prs']:
                try:
                    additions, deletions = get_pr_additions_deletions(github, pr)
                    pr._additions = additions
                    pr._deletions = deletions
                    user_total_additions += additions
                    user_total_deletions += deletions
                    time.sleep(0.5)  # API rate limiting
                except Exception as e:
                    print(f"    Error processing open PR #{pr.number}: {e}")
                    pr._additions = 0
                    pr._deletions = 0
            
            all_user_data.append({
                "username": username,
                "display_name": display_name,
                "stats": stats,
                "total_contributions": total_contributions,
                "total_additions": user_total_additions,
                "total_deletions": user_total_deletions
            })
            
            print(f"✅ Successfully processed {username}:")
            print(f"   Total contributions: {total_contributions}")
            print(f"   Code changes: +{format_number(user_total_additions)} -{format_number(user_total_deletions)}")
            
            # 添加延迟避免API限制
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Error processing user {username}: {e}")
            # 继续处理其他用户
            continue
        
    print(f"\n{'='*50}")
    print(f"Successfully processed {len(all_user_data)} users")
    
    # 按总贡献数排序
    all_user_data.sort(key=lambda x: x['total_contributions'], reverse=True)
    
    # 打印最终统计
    print(f"\nFinal contribution summary:")
    total_all_additions = 0
    total_all_deletions = 0
    for user in all_user_data:
        user_additions = user.get('total_additions', 0)
        user_deletions = user.get('total_deletions', 0)
        total_all_additions += user_additions
        total_all_deletions += user_deletions
        print(f"  {user['display_name']} (@{user['username']}): {user['total_contributions']} contributions, +{format_number(user_additions)} -{format_number(user_deletions)}")
    
    print(f"\nOverall totals:")
    print(f"  Total contributions: {sum(user['total_contributions'] for user in all_user_data)}")
    print(f"  Total code changes: +{format_number(total_all_additions)} -{format_number(total_all_deletions)}")
    
    print(f"\nGenerating enhanced chart for all {len(all_user_data)} users...")
    generate_chart(all_user_data)
    markdown_output = generate_markdown(all_user_data)
    readme_filename = create_fixed_readme(markdown_output)

    print(f"\n✅ All enhanced tasks completed successfully. README saved as: {readme_filename}")
    print(f"Enhanced chart saved as: {CHART_FILENAME}")
    print(f"Processed users: {[user['username'] for user in all_user_data]}")
