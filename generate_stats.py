import os
import re
import requests
import time
from datetime import datetime
from github import Github

# =================================CONFIG=================================
# The GitHub usernames you want to track
USERNAMES = ["david6666666", "hsliuustc0106", "fake0fan", "Gongzq5", "zhouyeju", "knlnguyen1802", "R2-Y", "natureofnature", "ahengljh", "syedmba", "wuhang2014", "chickeyton"]
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

def get_user_commits_stats(github_instance, username):
    """
    获取用户在目标组织中的所有 commit 统计信息
    """
    print(f"  Fetching commits for {username} in {TARGET_ORG}...")
    
    commits_data = []
    total_additions = 0
    total_deletions = 0
    
    try:
        # 获取组织对象
        org = github_instance.get_organization(TARGET_ORG)
        
        # 遍历组织中的所有仓库
        for repo in org.get_repos():
            try:
                print(f"    Processing repo: {repo.name}")
                
                # 获取该用户在此仓库中的 commits
                commits = repo.get_commits(author=username)
                
                repo_commits = 0
                for commit in commits:
                    try:
                        # 获取 commit 的详细信息（包括 stats）
                        commit_detail = repo.get_commit(commit.sha)
                        
                        # 提取统计信息
                        additions = commit_detail.stats.additions if commit_detail.stats else 0
                        deletions = commit_detail.stats.deletions if commit_detail.stats else 0
                        
                        total_additions += additions
                        total_deletions += deletions
                        
                        commits_data.append({
                            'repo': repo.full_name,
                            'sha': commit.sha[:8],  # 短 hash
                            'message': commit.commit.message.split('\n')[0][:100],  # 第一行，限制长度
                            'date': commit.commit.author.date,
                            'additions': additions,
                            'deletions': deletions,
                            'url': commit.html_url
                        })
                        
                        repo_commits += 1
                        
                        # 每10个commit添加小延迟
                        if repo_commits % 10 == 0:
                            time.sleep(0.1)
                            
                    except Exception as e:
                        print(f"      Error processing commit {commit.sha[:8]}: {e}")
                        continue
                
                print(f"    Found {repo_commits} commits in {repo.name}")
                
                # 仓库间添加延迟
                time.sleep(0.5)
                
            except Exception as e:
                print(f"    Error processing repo {repo.name}: {e}")
                continue
        
        # 按日期排序（最新的在前）
        commits_data.sort(key=lambda x: x['date'], reverse=True)
        
        print(f"  Total commits for {username}: {len(commits_data)} (Additions: +{total_additions}, Deletions: -{total_deletions})")
        
        # 创建结果对象
        class CommitsResult:
            def __init__(self, commits, additions, deletions):
                self.totalCount = len(commits)
                self.totalAdditions = additions
                self.totalDeletions = deletions
                self._commits = commits
            
            def __iter__(self):
                return iter(self._commits)
        
        return CommitsResult(commits_data, total_additions, total_deletions)
        
    except Exception as e:
        print(f"  Error fetching commits for {username}: {e}")
        # 返回空结果
        class EmptyCommitsResult:
            def __init__(self):
                self.totalCount = 0
                self.totalAdditions = 0
                self.totalDeletions = 0
                self._commits = []
            
            def __iter__(self):
                return iter(self._commits)
        
        return EmptyCommitsResult()

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
    Fetches PRs (open and merged), Issues, and Commits for a user.
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
        fallback_result = get_user_stats_fallback(github_instance, username)
        # 添加空的 commits 结果
        fallback_result["commits"] = get_user_commits_stats(github_instance, username)
        return fallback_result
    
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
    
    # 3. Commits: 获取 commits 统计
    print(f"  Fetching commits statistics...")
    commits = get_user_commits_stats(github_instance, username)
    
    total_found = open_prs.totalCount + merged_prs.totalCount + issues.totalCount + commits.totalCount
    print(f"  Final counts for {username}: {open_prs.totalCount} open PRs, {merged_prs.totalCount} merged PRs, {issues.totalCount} issues, {commits.totalCount} commits (Total: {total_found})")
    
    return {
        "open_prs": open_prs,
        "merged_prs": merged_prs,
        "issues": issues,
        "commits": commits
    }

def generate_chart(user_data):
    """
    生成包含 PRs、Issues 和 Commits 的堆叠柱状图
    """
    print(f"Generating chart for ALL {len(user_data)} users including commits...")
    
    # 准备数据
    usernames = []
    open_pr_counts = []
    merged_pr_counts = []
    issue_counts = []
    commit_counts = []
    
    # 计算总数
    total_open_prs = 0
    total_merged_prs = 0
    total_issues = 0
    total_commits = 0
    total_additions = 0
    total_deletions = 0
    
    for user in user_data:
        usernames.append(user['display_name'])
        open_count = user['stats']['open_prs'].totalCount
        merged_count = user['stats']['merged_prs'].totalCount
        issue_count = user['stats']['issues'].totalCount
        commit_count = user['stats']['commits'].totalCount
        
        open_pr_counts.append(open_count)
        merged_pr_counts.append(merged_count)
        issue_counts.append(issue_count)
        commit_counts.append(commit_count)
        
        total_open_prs += open_count
        total_merged_prs += merged_count
        total_issues += issue_count
        total_commits += commit_count
        total_additions += user['stats']['commits'].totalAdditions
        total_deletions += user['stats']['commits'].totalDeletions
    
    print(f"Chart data - Open PRs: {open_pr_counts} (Total: {total_open_prs})")
    print(f"Chart data - Merged PRs: {merged_pr_counts} (Total: {total_merged_prs})")
    print(f"Chart data - Issues: {issue_counts} (Total: {total_issues})")
    print(f"Chart data - Commits: {commit_counts} (Total: {total_commits})")
    print(f"Code changes - Additions: +{total_additions}, Deletions: -{total_deletions}")
    
    # 修复：确保宽度不超过 QuickChart 的限制 (3000px)
    max_allowed_width = 3000
    min_width = 1200
    calculated_width = max(min_width, min(len(user_data) * 200, max_allowed_width))
    chart_width = calculated_width
    chart_height = 900  # 增加高度以容纳更多数据
    
    print(f"Chart dimensions: {chart_width}x{chart_height}px")
    
    # 创建标题（包含代码变更统计）
    title_with_totals = f"{TARGET_ORG} 组织贡献统计\\n{len(user_data)}位用户 | PRs: {total_open_prs + total_merged_prs} | Issues: {total_issues} | Commits: {total_commits}\\n代码变更: +{total_additions} additions, -{total_deletions} deletions"
    
    # 创建图表配置
    chart_config = {
        "type": "bar",
        "data": {
            "labels": usernames,
            "datasets": [
                {
                    "label": f"Open PRs ({total_open_prs})",
                    "data": open_pr_counts,
                    "backgroundColor": "rgba(255, 193, 7, 0.9)",
                    "borderColor": "rgba(255, 193, 7, 1)",
                    "borderWidth": 2,
                    "stack": "contributions"
                },
                {
                    "label": f"Merged PRs ({total_merged_prs})",
                    "data": merged_pr_counts,
                    "backgroundColor": "rgba(40, 167, 69, 0.9)",
                    "borderColor": "rgba(40, 167, 69, 1)",
                    "borderWidth": 2,
                    "stack": "contributions"
                },
                {
                    "label": f"Issues ({total_issues})",
                    "data": issue_counts,
                    "backgroundColor": "rgba(220, 53, 69, 0.9)",
                    "borderColor": "rgba(220, 53, 69, 1)",
                    "borderWidth": 2,
                    "stack": "contributions"
                },
                {
                    "label": f"Commits ({total_commits})",
                    "data": commit_counts,
                    "backgroundColor": "rgba(102, 16, 242, 0.9)",
                    "borderColor": "rgba(102, 16, 242, 1)",
                    "borderWidth": 2,
                    "stack": "contributions"
                }
            ]
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "title": {
                "display": True,
                "text": title_with_totals,
                "fontSize": max(14, min(20, chart_width // 120)),
                "fontColor": "#333",
                "fontStyle": "bold",
                "padding": 20,
                "lineHeight": 1.2
            },
            "scales": {
                "yAxes": [{
                    "stacked": True,
                    "ticks": {
                        "beginAtZero": True,
                        "stepSize": 1,
                        "fontSize": max(10, min(14, chart_width // 200)),
                        "fontColor": "#333",
                        "padding": 5
                    },
                    "scaleLabel": {
                        "display": True,
                        "labelString": "贡献数量",
                        "fontSize": max(12, min(16, chart_width // 150)),
                        "fontColor": "#333",
                        "fontStyle": "bold"
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
                        "labelString": "用户名称",
                        "fontSize": max(12, min(16, chart_width // 150)),
                        "fontColor": "#333",
                        "fontStyle": "bold"
                    },
                    "ticks": {
                        "fontSize": max(8, min(12, chart_width // 250)),
                        "fontColor": "#333",
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
                    "fontSize": max(9, min(14, chart_width // 200)),
                    "fontColor": "#333",
                    "padding": 10,
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
                        "size": max(7, min(10, chart_width // 300)),
                        "weight": "bold"
                    },
                    "formatter": "function(value) { return value > 0 ? value : ''; }",
                    "textStrokeColor": "#000",
                    "textStrokeWidth": 1
                }
            },
            "layout": {
                "padding": {
                    "top": 60,
                    "bottom": 60,
                    "left": 15,
                    "right": 15
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
            print(f"✅ Chart with commits saved successfully as {CHART_FILENAME}")
            print(f"   Total statistics: PRs: {total_open_prs + total_merged_prs}, Issues: {total_issues}, Commits: {total_commits}")
            print(f"   Code changes: +{total_additions} additions, -{total_deletions} deletions")
        else:
            print(f"❌ Error generating chart: {response.status_code}")
            if response.text:
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Error generating chart: {e}")

def generate_markdown(user_data):
    """生成包含 commits 统计的 Markdown 表格"""
    markdown_text = f"这是根据在 **{TARGET_ORG}** 组织中的总贡献（Merged PRs + Open PRs + Issues + Commits）进行的排序。\n\n"
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
        
        # Process PRs
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
            
            pr_rows.sort(key=lambda x: x[0], reverse=True)
            
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
            for issue in stats['issues']:
                repo_name = issue.repository.full_name
                title = issue.title.replace('|', '\|')
                created_date = issue.created_at.strftime('%Y-%m-%d')
                markdown_text += f"| [{title}]({issue.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `{issue.state}` | {created_date} |\n"
        else:
            markdown_text += "_No public issues found._\n"
        markdown_text += "\n"
        
        # Commits Table
        commits_stats = stats['commits']
        markdown_text += f"**Commits ({commits_stats.totalCount} total, +{commits_stats.totalAdditions} additions, -{commits_stats.totalDeletions} deletions)**\n"
        
        if commits_stats.totalCount > 0:
            markdown_text += "| Message | Repository | Date | Hash | +Adds | -Dels |\n"
            markdown_text += "| ------- | ---------- | ---- | ---- | ----- | ----- |\n"
            
            # 显示最多50个最新的commits，避免表格过长
            commits_to_show = list(commits_stats)[:50]
            for commit in commits_to_show:
                message = commit['message'].replace('|', '\|')
                repo_name = commit['repo']
                date = commit['date'].strftime('%Y-%m-%d')
                hash_short = commit['sha']
                additions = commit['additions']
                deletions = commit['deletions']
                
                markdown_text += f"| [{message}]({commit['url']}) | [{repo_name}](https://github.com/{repo_name}) | {date} | `{hash_short}` | +{additions} | -{deletions} |\n"
            
            if commits_stats.totalCount > 50:
                markdown_text += f"\n_Showing latest 50 commits out of {commits_stats.totalCount} total._\n"
        else:
            markdown_text += "_No commits found._\n"
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
    readme_header += f"**统计范围**: {TARGET_ORG} 组织的所有贡献（PRs, Issues, Commits）\n\n"
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
    print(f"Including all contributions: PRs, Issues, and Commits with code changes")
    print(f"Users to track: {USERNAMES}")
    
    github = Github(GITHUB_TOKEN)
    
    all_user_data = []
    for username in USERNAMES:
        try:
            print(f"\n{'='*50}")
            print(f"Processing user: {username}")
            
            display_name = get_user_display_name(github, username)
            stats = get_user_stats(github, username)
            total_contributions = (stats['merged_prs'].totalCount + 
                                 stats['open_prs'].totalCount + 
                                 stats['issues'].totalCount + 
                                 stats['commits'].totalCount)
            
            all_user_data.append({
                "username": username,
                "display_name": display_name,
                "stats": stats,
                "total_contributions": total_contributions
            })
            print(f"✅ Successfully processed {username} with {total_contributions} total contributions in {TARGET_ORG}")
            print(f"   Commits: {stats['commits'].totalCount} (+{stats['commits'].totalAdditions} additions, -{stats['commits'].totalDeletions} deletions)")
            
            # 添加延迟避免API限制
            time.sleep(3)  # 增加延迟，因为现在需要获取更多数据
            
        except Exception as e:
            print(f"❌ Error processing user {username}: {e}")
            continue
        
    print(f"\n{'='*50}")
    print(f"Successfully processed {len(all_user_data)} users")
    
    # 按总贡献数排序
    all_user_data.sort(key=lambda x: x['total_contributions'], reverse=True)
    
    # 打印最终统计
    print(f"\nFinal contribution summary (including commits):")
    total_all_additions = 0
    total_all_deletions = 0
    for user in all_user_data:
        commits_stats = user['stats']['commits']
        total_all_additions += commits_stats.totalAdditions
        total_all_deletions += commits_stats.totalDeletions
        print(f"  {user['display_name']} (@{user['username']}): {user['total_contributions']} contributions")
        print(f"    Commits: {commits_stats.totalCount} (+{commits_stats.totalAdditions}, -{commits_stats.totalDeletions})")
    
    print(f"\nOverall code changes: +{total_all_additions} additions, -{total_all_deletions} deletions")
    
    print(f"\nGenerating chart with commits data for all {len(all_user_data)} users...")
    generate_chart(all_user_data)
    markdown_output = generate_markdown(all_user_data)
    readme_filename = create_fixed_readme(markdown_output)

    print(f"\n✅ All tasks completed successfully. README saved as: {readme_filename}")
    print(f"Processed users: {[user['username'] for user in all_user_data]}")
    print(f"Total statistics across all users:")
    print(f"  Code changes: +{total_all_additions} additions, -{total_all_deletions} deletions")
