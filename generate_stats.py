import os
import re
import requests
import time
from datetime import datetime, timezone
from html import escape
from github import Github

# =================================CONFIG=================================
# GitHub usernames grouped by affiliation
USER_GROUPS = {
    "HUAWEI": ["david6666666", "jiangkuaixue123", "tangtiangu", "bjf-frz", "yangjianjuan ", "wuhang2014", "yenuo26", "hsliuustc0106", "amy-why-3459", "zengchuang-hw", "Shirley125", "LJH-LBJ", "Bounty-hunter", "fake0fan", "R2-Y", "natureofnature", "chickeyton", "Gaohan123", "congw729", "herotai214", "TaffyOfficial", "tzhouam", "NumberWan", "spencerr221", "fhfuih", "SamitHuang", "knlnguyen1802", "hadipash", "cyr20040123", "AndyZhou952", "wtomin", "mxuax", "zhtmike"],
    "阿里PAI": ["ZeldaHuang", "iwzbi", "Sy0307"],
    "蚂蚁": ["ApsarasX"],
    "小米": ["qibaoyuan"],
    "智谱": ["JaredforReal"],
}
USERNAMES = [username.strip() for usernames in USER_GROUPS.values() for username in usernames]
USER_AFFILIATIONS = {
    username.strip(): affiliation
    for affiliation, usernames in USER_GROUPS.items()
    for username in usernames
}
# Your GitHub Personal Access Token, read from an environment variable
GITHUB_TOKEN = os.getenv('GH_PAT')
# The output filename for the chart
CHART_FILENAME = "stats_chart.svg"
# The output filename for the standalone HTML dashboard
HTML_FILENAME = "stats_dashboard.html"
# Target repository - only vllm-project/vllm-omni
TARGET_REPO = "vllm-project/vllm-omni"
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
    获取PR的additions、deletions以及合并时间
    """
    try:
        # 获取PR的详细信息
        repo = github_instance.get_repo(pr.repository.full_name)
        pr_detail = repo.get_pull(pr.number)
        
        additions = pr_detail.additions if pr_detail.additions is not None else 0
        deletions = pr_detail.deletions if pr_detail.deletions is not None else 0
        merged_at = pr_detail.merged_at
        
        print(f"    PR #{pr.number}: +{additions} -{deletions}")
        return additions, deletions, merged_at
        
    except Exception as e:
        print(f"    Error fetching additions/deletions for PR #{pr.number}: {e}")
        return 0, 0, None

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
    备用方法：直接从组织的仓库中获取用户的PR统计
    """
    print(f"  Using fallback method for {username}...")
    
    open_prs = []
    merged_prs = []
    
    try:
        repo = github_instance.get_repo(TARGET_REPO)
        all_prs = repo.get_pulls(state='all')
        for pr in all_prs:
            if pr.user.login == username:
                if pr.state == 'open':
                    open_prs.append(pr)
                elif pr.merged:
                    merged_prs.append(pr)
                
        print(f"  Fallback results for {username}: {len(open_prs)} open PRs, {len(merged_prs)} merged PRs")
        
        # 创建包装对象
        class FallbackResult:
            def __init__(self, items):
                self._items = items
                self.totalCount = len(items)
            def __iter__(self):
                return iter(self._items)
        
        return {
            "open_prs": FallbackResult(open_prs),
            "merged_prs": FallbackResult(merged_prs)
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
            "merged_prs": EmptyResult()
        }

def get_user_stats(github_instance, username):
    """
    Fetches PRs (open and merged) for a user.
    Includes all data from vllm-project organization (no date restrictions).
    """
    print(f"Fetching all data for {username} in {TARGET_REPO} repository...")
    
    repo_qualifier = f"repo:{TARGET_REPO}"

    # 1. PRs: Query for open and merged PRs separately in the target repository
    query_open_prs = f"is:pr author:{username} is:public is:open {repo_qualifier}"
    query_merged_prs = f"is:pr author:{username} is:public is:merged {repo_qualifier}"
    
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
    
    total_found = open_prs.totalCount + merged_prs.totalCount
    print(f"  Final counts for {username}: {open_prs.totalCount} open PRs, {merged_prs.totalCount} merged PRs (Total: {total_found})")
    
    return {
        "open_prs": open_prs,
        "merged_prs": merged_prs
    }

def format_number(num):
    """
    格式化数字，添加千位分隔符
    """
    return f"{num:,}"

def summarize_by_affiliation(user_data):
    summaries = {}

    for affiliation in USER_GROUPS:
        summaries[affiliation] = {
            "users": 0,
            "total_contributions": 0,
            "open_prs": 0,
            "merged_prs": 0,
            "total_additions": 0,
            "total_deletions": 0,
        }

    for user in user_data:
        affiliation = user.get('affiliation', 'Unknown')
        if affiliation not in summaries:
            summaries[affiliation] = {
                "users": 0,
                "total_contributions": 0,
                "open_prs": 0,
                "merged_prs": 0,
                "total_additions": 0,
                "total_deletions": 0,
            }

        stats = user['stats']
        summary = summaries[affiliation]
        summary["users"] += 1
        summary["total_contributions"] += user['total_contributions']
        summary["open_prs"] += stats['open_prs'].totalCount
        summary["merged_prs"] += stats['merged_prs'].totalCount
        summary["total_additions"] += user.get('total_additions', 0)
        summary["total_deletions"] += user.get('total_deletions', 0)

    return summaries

def _empty_release_affiliation_stats():
    return {
        affiliation: {
            "commit_count": 0,
            "review_count": 0,
            "reviewed_pr_count": 0,
            "commit_users": {},
            "review_users": {},
        }
        for affiliation in USER_GROUPS
    }

def _release_time(release):
    dt = release.published_at or release.created_at
    if dt and dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

def get_latest_release_contribution_stats(github_instance):
    """
    Collect commit and review contributions for the latest formal release window.
    Formal release means non-draft and non-prerelease GitHub releases.
    """
    print(f"Collecting latest formal release contribution stats for {TARGET_REPO}...")

    repo = github_instance.get_repo(TARGET_REPO)
    formal_releases = []
    for release in repo.get_releases():
        if not release.draft and not release.prerelease:
            formal_releases.append(release)
        if len(formal_releases) >= 2:
            break

    if len(formal_releases) < 2:
        print("  Not enough formal releases found to build release contribution stats.")
        return None

    latest_release = formal_releases[0]
    previous_release = formal_releases[1]
    latest_time = _release_time(latest_release)
    previous_time = _release_time(previous_release)
    if not latest_time or not previous_time:
        print("  Release timestamps are incomplete; skipping release contribution stats.")
        return None

    affiliation_stats = _empty_release_affiliation_stats()
    user_stats = {
        username: {
            "username": username,
            "affiliation": USER_AFFILIATIONS.get(username, "Unknown"),
            "commit_count": 0,
            "review_count": 0,
            "reviewed_pr_count": 0,
        }
        for username in USERNAMES
    }

    compare = repo.compare(previous_release.tag_name, latest_release.tag_name)
    compare_commits = list(compare.commits)
    total_commits = len(compare_commits)
    tracked_commits = 0

    for commit in compare_commits:
        author = getattr(commit, "author", None)
        login = getattr(author, "login", None) if author else None
        if not login or login not in USER_AFFILIATIONS:
            continue

        affiliation = USER_AFFILIATIONS[login]
        tracked_commits += 1
        affiliation_stats[affiliation]["commit_count"] += 1
        affiliation_stats[affiliation]["commit_users"][login] = (
            affiliation_stats[affiliation]["commit_users"].get(login, 0) + 1
        )
        user_stats[login]["commit_count"] += 1

    start_date = previous_time.strftime('%Y-%m-%d')
    end_date = latest_time.strftime('%Y-%m-%d')
    query = f"repo:{TARGET_REPO} is:pr is:merged merged:{start_date}..{end_date}"
    print(f"  Release PR review query: {query}")

    merged_pr_issues = list(github_instance.search_issues(query))
    total_reviews = 0
    tracked_reviews = 0
    reviewed_prs_by_user = {username: set() for username in USERNAMES}
    reviewed_prs_by_affiliation = {affiliation: set() for affiliation in USER_GROUPS}

    for issue in merged_pr_issues:
        try:
            pr = repo.get_pull(issue.number)
            for review in pr.get_reviews():
                submitted_at = review.submitted_at
                if not submitted_at:
                    continue
                if submitted_at.tzinfo:
                    submitted_at = submitted_at.astimezone(timezone.utc).replace(tzinfo=None)
                if submitted_at < previous_time or submitted_at > latest_time:
                    continue

                total_reviews += 1
                reviewer = review.user.login if review.user else None
                if not reviewer or reviewer not in USER_AFFILIATIONS:
                    continue

                affiliation = USER_AFFILIATIONS[reviewer]
                tracked_reviews += 1
                affiliation_stats[affiliation]["review_count"] += 1
                affiliation_stats[affiliation]["review_users"][reviewer] = (
                    affiliation_stats[affiliation]["review_users"].get(reviewer, 0) + 1
                )
                user_stats[reviewer]["review_count"] += 1
                reviewed_prs_by_user[reviewer].add(issue.number)
                reviewed_prs_by_affiliation[affiliation].add(issue.number)
        except Exception as e:
            print(f"    Error processing reviews for PR #{issue.number}: {e}")
            continue

    for affiliation, pr_numbers in reviewed_prs_by_affiliation.items():
        affiliation_stats[affiliation]["reviewed_pr_count"] = len(pr_numbers)
    for username, pr_numbers in reviewed_prs_by_user.items():
        user_stats[username]["reviewed_pr_count"] = len(pr_numbers)

    user_rows = [
        stats for stats in user_stats.values()
        if stats["commit_count"] or stats["review_count"] or stats["reviewed_pr_count"]
    ]
    user_rows.sort(
        key=lambda item: (item["commit_count"] + item["review_count"], item["commit_count"]),
        reverse=True,
    )

    print(
        f"  Latest formal release window: {previous_release.tag_name} -> {latest_release.tag_name}; "
        f"tracked commits {tracked_commits}/{total_commits}, tracked reviews {tracked_reviews}/{total_reviews}"
    )

    return {
        "latest_tag": latest_release.tag_name,
        "previous_tag": previous_release.tag_name,
        "latest_name": getattr(latest_release, "title", None) or getattr(latest_release, "name", None) or latest_release.tag_name,
        "previous_name": getattr(previous_release, "title", None) or getattr(previous_release, "name", None) or previous_release.tag_name,
        "latest_published_at": latest_time,
        "previous_published_at": previous_time,
        "compare_url": f"https://github.com/{TARGET_REPO}/compare/{previous_release.tag_name}...{latest_release.tag_name}",
        "merged_pr_count": len(merged_pr_issues),
        "total_commits": total_commits,
        "tracked_commits": tracked_commits,
        "total_reviews": total_reviews,
        "tracked_reviews": tracked_reviews,
        "affiliations": affiliation_stats,
        "users": user_rows,
    }

def format_datetime(dt):
    """
    将datetime格式化为字符串，若不存在则返回“-”
    """
    if not dt:
        return "-"
    try:
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception:
        return "-"

def generate_chart(user_data):
    """
    生成包含堆叠PR柱状图的图表，包含additions/deletions统计
    修改：将所有字体颜色改为黑色加粗
    """
    print(f"Generating enhanced chart for ALL {len(user_data)} users...")
    
    # 准备数据 - 确保所有用户都包含在内，即使数据为0
    usernames = []
    open_pr_counts = []
    merged_pr_counts = []
    
    # 计算总数
    total_open_prs = 0
    total_merged_prs = 0
    total_additions = 0
    total_deletions = 0
    
    for user in user_data:
        usernames.append(user['display_name'])
        open_count = user['stats']['open_prs'].totalCount
        merged_count = user['stats']['merged_prs'].totalCount
        user_additions = user.get('total_additions', 0)
        user_deletions = user.get('total_deletions', 0)
        
        open_pr_counts.append(open_count)
        merged_pr_counts.append(merged_count)
        
        total_open_prs += open_count
        total_merged_prs += merged_count
        total_additions += user_additions
        total_deletions += user_deletions
    
    print(f"Chart will display {len(usernames)} users: {usernames}")
    print(f"Chart data - Open PR counts: {open_pr_counts} (Total: {total_open_prs})")
    print(f"Chart data - Merged PR counts: {merged_pr_counts} (Total: {total_merged_prs})")
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
        f"{TARGET_REPO} PR贡献统计 - 共{len(user_data)}位用户",
        f"总计: Open PRs: {total_open_prs} | Merged PRs: {total_merged_prs}",
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
    print(f"Total statistics: Open PRs: {total_open_prs}, Merged PRs: {total_merged_prs}")
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
            print(f"   Totals displayed: Open PRs: {total_open_prs}, Merged PRs: {total_merged_prs}")
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

def generate_markdown(user_data, release_stats=None):
    """生成包含additions/deletions统计的Markdown表格"""
    markdown_text = f"这是根据在 **{TARGET_REPO}** 仓库中的 PR 贡献（Merged PRs + Open PRs）进行的排序。\n\n"
    markdown_text += f"总共追踪了 {len(user_data)} 个用户在 {TARGET_REPO} 仓库中的贡献情况。\n\n"
    
    # 计算总的additions和deletions
    total_all_additions = sum(user.get('total_additions', 0) for user in user_data)
    total_all_deletions = sum(user.get('total_deletions', 0) for user in user_data)
    
    markdown_text += f"**总代码变更统计**: +{format_number(total_all_additions)} 行添加, -{format_number(total_all_deletions)} 行删除\n\n"
    markdown_text += "## 按归属统计\n\n"
    markdown_text += "| 归属 | 用户数 | Total PRs | Open PRs | Merged PRs | Additions | Deletions |\n"
    markdown_text += "| ---- | ------ | --------- | -------- | ---------- | --------- | --------- |\n"

    for affiliation, summary in summarize_by_affiliation(user_data).items():
        markdown_text += (
            f"| {affiliation} | {summary['users']} | {summary['total_contributions']} | "
            f"{summary['open_prs']} | {summary['merged_prs']} | "
            f"{format_number(summary['total_additions'])} | {format_number(summary['total_deletions'])} |\n"
        )

    markdown_text += "\n"

    markdown_text += "## 当前最新正式版本贡献统计\n\n"
    if not release_stats:
        markdown_text += "_Release contribution stats unavailable. Check the GitHub Actions log for details._\n\n"
    else:
        markdown_text += (
            f"版本: **{release_stats['latest_tag']}**  \n"
            f"区间: [{release_stats['previous_tag']}...{release_stats['latest_tag']}]({release_stats['compare_url']})  \n"
            f"发布时间: {format_datetime(release_stats['previous_published_at'])} -> "
            f"{format_datetime(release_stats['latest_published_at'])}\n\n"
        )
        markdown_text += (
            f"Tracked commits: {format_number(release_stats['tracked_commits'])}/"
            f"{format_number(release_stats['total_commits'])}; "
            f"Tracked reviews: {format_number(release_stats['tracked_reviews'])}/"
            f"{format_number(release_stats['total_reviews'])}; "
            f"Merged PRs in window: {format_number(release_stats['merged_pr_count'])}\n\n"
        )
        markdown_text += "| 归属 | Commit Count | Review Count | Reviewed PRs |\n"
        markdown_text += "| ---- | ------------ | ------------ | ------------ |\n"
        for affiliation, summary in release_stats["affiliations"].items():
            markdown_text += (
                f"| {affiliation} | {format_number(summary['commit_count'])} | "
                f"{format_number(summary['review_count'])} | "
                f"{format_number(summary['reviewed_pr_count'])} |\n"
            )
        markdown_text += "\n"

    for user in user_data:
        username = user['username']
        display_name = user['display_name']
        stats = user['stats']
        total_contributions = user['total_contributions']
        user_additions = user.get('total_additions', 0)
        user_deletions = user.get('total_deletions', 0)
        affiliation = user.get('affiliation', 'Unknown')
        
        # 显示用户名和显示名称，包含代码变更统计
        if display_name != username:
            markdown_text += f"### 👤 {display_name} (@{username}) - {affiliation} - 总贡献: {total_contributions}\n"
        else:
            markdown_text += f"### 👤 {username} - {affiliation} - 总贡献: {total_contributions}\n"
        
        markdown_text += f"**代码变更**: +{format_number(user_additions)} 行添加, -{format_number(user_deletions)} 行删除\n\n"
        
        # PR Table with additions/deletions and merged time
        markdown_text += f"**Pull Requests ({stats['open_prs'].totalCount} open, {stats['merged_prs'].totalCount} merged)**\n"
        
        # Process PRs by type to assign the correct state, then sort.
        pr_rows = []
        
        # Process merged PRs
        for pr in stats['merged_prs']:
            repo_name = pr.repository.full_name
            title = pr.title.replace('|', '\|')
            created_date = pr.created_at.strftime('%Y-%m-%d')
            merged_at = getattr(pr, '_merged_at', None) or getattr(pr, 'merged_at', None)
            merged_date = format_datetime(merged_at)
            
            # 获取PR的additions和deletions (如果已存储)
            additions = getattr(pr, '_additions', 0)
            deletions = getattr(pr, '_deletions', 0)
            
            row_string = f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `merged` | {created_date} | {merged_date} | {format_number(additions)} | {format_number(deletions)} |\n"
            pr_rows.append((pr.created_at, row_string))
            
        # Process open PRs
        for pr in stats['open_prs']:
            repo_name = pr.repository.full_name
            title = pr.title.replace('|', '\|')
            created_date = pr.created_at.strftime('%Y-%m-%d')
            merged_at = getattr(pr, '_merged_at', None) or getattr(pr, 'merged_at', None)
            merged_date = format_datetime(merged_at)
            
            # 获取PR的additions和deletions (如果已存储)
            additions = getattr(pr, '_additions', 0)
            deletions = getattr(pr, '_deletions', 0)
            
            row_string = f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `open` | {created_date} | {merged_date} | {format_number(additions)} | {format_number(deletions)} |\n"
            pr_rows.append((pr.created_at, row_string))

        if pr_rows:
            markdown_text += "| Title | Repository | State | Created | Merged | Additions | Deletions |\n"
            markdown_text += "| ----- | ---------- | ----- | ------- | ------ | --------- | --------- |\n"
            
            # Sort all PRs by creation date, descending
            pr_rows.sort(key=lambda x: x[0], reverse=True)
            
            # Add ALL rows to the markdown
            for _, row_string in pr_rows:
                markdown_text += row_string
                
            # Add user totals row
            markdown_text += f"| **Total for {display_name}** | | | | - | **{format_number(user_additions)}** | **{format_number(user_deletions)}** |\n"
        else:
            markdown_text += "_No relevant pull requests found._\n"
        markdown_text += "\n"

    return markdown_text

def create_fixed_readme(content):
    """Creates a README file with fixed filename."""
    # 确保先删除已存在的文件
    if os.path.exists(README_FILENAME):
        os.remove(README_FILENAME)
        print(f"Removed existing {README_FILENAME}")
    
    # Create the full README content with header
    readme_header = f"# Enhanced GitHub Stats Report - {TARGET_REPO}\n\n"
    readme_header += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
    readme_header += f"**统计范围**: {TARGET_REPO} 仓库的所有 PR 贡献（包含代码变更统计）\n\n"
    readme_header += f"![Enhanced GitHub Stats Chart]({CHART_FILENAME})\n\n"
    readme_header += "---\n\n"
    
    full_content = readme_header + content
    
    # Write to the fixed filename with explicit encoding
    with open(README_FILENAME, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    print(f"Enhanced README created successfully: {README_FILENAME}")
    print(f"README file size: {os.path.getsize(README_FILENAME)} bytes")
    return README_FILENAME

def create_dashboard_html(user_data, release_stats=None):
    """Creates a standalone HTML dashboard for the generated stats."""
    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    affiliation_summaries = summarize_by_affiliation(user_data)

    total_users = len(user_data)
    total_contributions = sum(user['total_contributions'] for user in user_data)
    total_open_prs = sum(user['stats']['open_prs'].totalCount for user in user_data)
    total_merged_prs = sum(user['stats']['merged_prs'].totalCount for user in user_data)
    total_additions = sum(user.get('total_additions', 0) for user in user_data)
    total_deletions = sum(user.get('total_deletions', 0) for user in user_data)
    max_contributions = max((user['total_contributions'] for user in user_data), default=1)

    try:
        with open(CHART_FILENAME, 'r', encoding='utf-8') as f:
            chart_markup = f'<div class="chart-svg">{f.read()}</div>'
    except OSError:
        chart_markup = (
            f'<div class="chart-placeholder">'
            f'{escape(CHART_FILENAME)} is not available in this generated view.'
            f'</div>'
        )

    filter_buttons = ['<button class="filter-btn active" type="button" data-filter="all">All</button>']
    for affiliation in affiliation_summaries:
        filter_buttons.append(
            f'<button class="filter-btn" type="button" data-filter="{escape(affiliation, quote=True)}">'
            f'{escape(affiliation)}</button>'
        )

    if release_stats:
        release_group_rows = []
        for affiliation, summary in release_stats["affiliations"].items():
            release_group_rows.append(f"""
          <tr>
            <td><span class="pill">{escape(affiliation)}</span></td>
            <td class="num">{format_number(summary['commit_count'])}</td>
            <td class="num">{format_number(summary['review_count'])}</td>
            <td class="num">{format_number(summary['reviewed_pr_count'])}</td>
          </tr>""")

        release_user_rows = []
        for user in release_stats["users"][:30]:
            release_user_rows.append(f"""
          <tr>
            <td class="person">@{escape(user['username'])}</td>
            <td><span class="pill">{escape(user['affiliation'])}</span></td>
            <td class="num">{format_number(user['commit_count'])}</td>
            <td class="num">{format_number(user['review_count'])}</td>
            <td class="num">{format_number(user['reviewed_pr_count'])}</td>
          </tr>""")

        release_section = f"""
    <section class="section">
      <div class="section-head">
        <h2>Current Release Contributions</h2>
        <p class="timestamp">
          <a href="{escape(release_stats['compare_url'])}">
            {escape(release_stats['previous_tag'])}...{escape(release_stats['latest_tag'])}
          </a>
        </p>
      </div>
      <div class="release-grid">
        <div class="metric"><span>Latest formal release</span><strong>{escape(release_stats['latest_tag'])}</strong></div>
        <div class="metric"><span>Tracked commits</span><strong>{format_number(release_stats['tracked_commits'])}</strong></div>
        <div class="metric"><span>Tracked reviews</span><strong>{format_number(release_stats['tracked_reviews'])}</strong></div>
        <div class="metric"><span>Merged PRs</span><strong>{format_number(release_stats['merged_pr_count'])}</strong></div>
      </div>
      <div class="release-tables">
        <div class="table-panel">
          <table>
            <thead><tr><th>Affiliation</th><th class="num">Commits</th><th class="num">Reviews</th><th class="num">Reviewed PRs</th></tr></thead>
            <tbody>{''.join(release_group_rows)}</tbody>
          </table>
        </div>
        <div class="table-panel">
          <table>
            <thead><tr><th>User</th><th>Affiliation</th><th class="num">Commits</th><th class="num">Reviews</th><th class="num">Reviewed PRs</th></tr></thead>
            <tbody>{''.join(release_user_rows)}</tbody>
          </table>
        </div>
      </div>
    </section>"""
    else:
        release_section = """
    <section class="section">
      <div class="section-head">
        <h2>Current Release Contributions</h2>
        <p class="timestamp">Release stats unavailable</p>
      </div>
      <div class="table-panel release-empty">
        Release contribution stats could not be collected in this run. Check the GitHub Actions log for details.
      </div>
    </section>"""

    group_cards = []
    for affiliation, summary in affiliation_summaries.items():
        share = (summary['total_contributions'] / total_contributions * 100) if total_contributions else 0
        group_cards.append(f"""
          <article class="group-card">
            <div>
              <p class="eyebrow">{escape(affiliation)}</p>
              <h3>{format_number(summary['total_contributions'])}</h3>
            </div>
            <dl>
              <div><dt>Users</dt><dd>{summary['users']}</dd></div>
              <div><dt>Open</dt><dd>{format_number(summary['open_prs'])}</dd></div>
              <div><dt>Merged</dt><dd>{format_number(summary['merged_prs'])}</dd></div>
              <div><dt>Share</dt><dd>{share:.1f}%</dd></div>
            </dl>
          </article>""")

    leaderboard_rows = []
    for rank, user in enumerate(user_data, start=1):
        username = user['username']
        display_name = user['display_name']
        affiliation = user.get('affiliation', 'Unknown')
        stats = user['stats']
        total = user['total_contributions']
        bar_width = (total / max_contributions * 100) if max_contributions else 0
        leaderboard_rows.append(f"""
          <tr data-affiliation="{escape(affiliation, quote=True)}">
            <td class="rank">{rank}</td>
            <td>
              <a class="person" href="https://github.com/{escape(username)}">{escape(display_name)}</a>
              <span class="muted">@{escape(username)}</span>
            </td>
            <td><span class="pill">{escape(affiliation)}</span></td>
            <td class="num">{format_number(total)}</td>
            <td class="num">{format_number(stats['open_prs'].totalCount)}</td>
            <td class="num">{format_number(stats['merged_prs'].totalCount)}</td>
            <td class="num">+{format_number(user.get('total_additions', 0))}</td>
            <td class="num">-{format_number(user.get('total_deletions', 0))}</td>
            <td><div class="bar"><span style="width: {bar_width:.1f}%"></span></div></td>
          </tr>""")

    recent_prs = []
    for user in user_data:
        for state, prs in (("merged", user['stats']['merged_prs']), ("open", user['stats']['open_prs'])):
            for pr in prs:
                recent_prs.append({
                    "title": pr.title,
                    "url": pr.html_url,
                    "repo": pr.repository.full_name,
                    "state": state,
                    "created_at": pr.created_at,
                    "additions": getattr(pr, '_additions', 0),
                    "deletions": getattr(pr, '_deletions', 0),
                    "user": user['username'],
                    "affiliation": user.get('affiliation', 'Unknown'),
                })

    recent_prs.sort(key=lambda pr: pr["created_at"] or datetime.min, reverse=True)
    recent_rows = []
    for pr in recent_prs[:80]:
        created_date = pr["created_at"].strftime('%Y-%m-%d') if pr["created_at"] else "-"
        recent_rows.append(f"""
          <tr data-affiliation="{escape(pr['affiliation'], quote=True)}">
            <td>
              <a class="pr-title" href="{escape(pr['url'])}">{escape(pr['title'])}</a>
              <span class="muted">{escape(pr['repo'])}</span>
            </td>
            <td><span class="state {escape(pr['state'])}">{escape(pr['state'])}</span></td>
            <td><span class="pill">{escape(pr['affiliation'])}</span></td>
            <td class="muted">@{escape(pr['user'])}</td>
            <td>{created_date}</td>
            <td class="num">+{format_number(pr['additions'])}</td>
            <td class="num">-{format_number(pr['deletions'])}</td>
          </tr>""")

    html_content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(TARGET_REPO)} PR Contribution Dashboard</title>
  <style>
    :root {{
      --bg: #f6f2ea;
      --ink: #171411;
      --muted: #6d665e;
      --line: #d8d0c4;
      --panel: #fffaf0;
      --panel-strong: #fff4d9;
      --accent: #006b5f;
      --accent-2: #bb3e03;
      --shadow: 0 24px 60px rgba(48, 39, 27, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        linear-gradient(90deg, rgba(23,20,17,0.035) 1px, transparent 1px),
        linear-gradient(rgba(23,20,17,0.035) 1px, transparent 1px),
        var(--bg);
      background-size: 28px 28px;
      color: var(--ink);
      font-family: Georgia, "Times New Roman", serif;
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1480px, calc(100% - 40px)); margin: 0 auto; padding: 34px 0 56px; }}
    .topline {{
      align-items: center;
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding-bottom: 14px;
    }}
    .mark {{ font: 700 13px/1.1 "Trebuchet MS", sans-serif; letter-spacing: 0.12em; text-transform: uppercase; }}
    .timestamp {{ color: var(--muted); font: 12px/1.4 "Trebuchet MS", sans-serif; }}
    .hero {{ display: grid; grid-template-columns: 1.08fr 0.92fr; gap: 28px; padding: 42px 0 26px; }}
    h1 {{
      font-size: clamp(42px, 7vw, 104px);
      line-height: 0.88;
      margin: 0;
      max-width: 900px;
      letter-spacing: 0;
    }}
    .summary-strip {{
      align-self: end;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      min-height: 118px;
      padding: 18px;
    }}
    .metric span, .eyebrow, th, .muted, dt {{
      color: var(--muted);
      font: 700 11px/1.35 "Trebuchet MS", sans-serif;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .metric strong {{ display: block; font-size: clamp(28px, 4vw, 54px); line-height: 1; margin-top: 14px; }}
    .section {{ margin-top: 22px; }}
    .section-head {{ align-items: end; display: flex; justify-content: space-between; gap: 18px; margin-bottom: 12px; }}
    h2 {{ font-size: clamp(24px, 3vw, 42px); line-height: 1; margin: 0; }}
    .filters {{
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 22px 0 0;
    }}
    .filter-btn {{
      background: #fffaf0;
      border: 1px solid var(--ink);
      color: var(--ink);
      cursor: pointer;
      font: 700 12px/1 "Trebuchet MS", sans-serif;
      padding: 11px 14px;
      text-transform: uppercase;
    }}
    .filter-btn.active, .filter-btn:hover {{
      background: var(--ink);
      color: #fffaf0;
    }}
    .groups {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }}
    .release-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }}
    .release-tables {{ display: grid; grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr); gap: 12px; }}
    .group-card {{
      background: var(--panel-strong);
      border: 1px solid var(--ink);
      box-shadow: 8px 8px 0 var(--ink);
      min-height: 180px;
      padding: 17px;
    }}
    .group-card h3 {{ font-size: 42px; line-height: 1; margin: 12px 0 24px; }}
    dl {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin: 0; }}
    dd {{ font-size: 22px; margin: 4px 0 0; }}
    .chart-panel, .table-panel {{
      background: rgba(255, 250, 240, 0.88);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .release-empty {{ color: var(--muted); padding: 18px; }}
    .chart-panel {{ padding: 18px; }}
    .chart-panel img {{ display: block; width: 100%; height: auto; background: white; border: 1px solid var(--line); }}
    .chart-svg {{ background: white; border: 1px solid var(--line); overflow-x: auto; }}
    .chart-svg svg {{ display: block; height: auto; max-width: none; width: 100%; }}
    .chart-placeholder {{ background: white; border: 1px solid var(--line); color: var(--muted); padding: 22px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 12px 14px; text-align: left; vertical-align: middle; }}
    th {{ background: #eee5d7; position: sticky; top: 0; z-index: 1; }}
    tbody tr:hover {{ background: #fff3d4; }}
    tr[hidden] {{ display: none; }}
    .num {{ font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }}
    .rank {{ color: var(--accent-2); font-size: 22px; font-weight: 700; width: 58px; }}
    .person, .pr-title {{ font-weight: 700; }}
    .person:hover, .pr-title:hover {{ color: var(--accent); }}
    .muted {{ display: block; margin-top: 3px; text-transform: none; letter-spacing: 0; }}
    .pill, .state {{
      border: 1px solid var(--line);
      border-radius: 999px;
      display: inline-flex;
      font: 700 11px/1 "Trebuchet MS", sans-serif;
      padding: 7px 9px;
      white-space: nowrap;
    }}
    .pill {{ background: #fff; }}
    .state.open {{ background: #fff1b8; border-color: #b88a00; color: #644b00; }}
    .state.merged {{ background: #dff4e8; border-color: #4d9b70; color: #14552f; }}
    .bar {{ background: #e7ded0; height: 10px; min-width: 90px; overflow: hidden; }}
    .bar span {{ background: linear-gradient(90deg, var(--accent), var(--accent-2)); display: block; height: 100%; }}
    .table-scroll {{ max-height: 760px; overflow: auto; }}
    @media (max-width: 980px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .groups {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .release-grid, .release-tables {{ grid-template-columns: 1fr; }}
      .summary-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 640px) {{
      .shell {{ width: min(100% - 24px, 1480px); padding-top: 20px; }}
      .topline, .section-head {{ align-items: flex-start; flex-direction: column; }}
      .groups, .summary-strip {{ grid-template-columns: 1fr; }}
      th, td {{ padding: 10px; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topline">
      <div class="mark">{escape(TARGET_REPO)} contribution monitor</div>
      <div class="timestamp">Generated {generated_at}</div>
    </header>

    <section class="hero">
      <h1>PR contribution dashboard</h1>
      <div class="summary-strip">
        <div class="metric"><span>Tracked users</span><strong>{format_number(total_users)}</strong></div>
        <div class="metric"><span>Total PRs</span><strong>{format_number(total_contributions)}</strong></div>
        <div class="metric"><span>Open PRs</span><strong>{format_number(total_open_prs)}</strong></div>
        <div class="metric"><span>Merged PRs</span><strong>{format_number(total_merged_prs)}</strong></div>
      </div>
    </section>

    <section class="section groups">
      {''.join(group_cards)}
    </section>

    {release_section}

    <nav class="filters" aria-label="Filter by affiliation">
      {''.join(filter_buttons)}
    </nav>

    <section class="section">
      <div class="section-head">
        <h2>Contribution Volume</h2>
        <p class="timestamp">Code delta: +{format_number(total_additions)} / -{format_number(total_deletions)}</p>
      </div>
      <div class="chart-panel">
        {chart_markup}
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <h2>Contributor Ranking</h2>
        <p class="timestamp">Sorted by total open and merged PRs</p>
      </div>
      <div class="table-panel table-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Contributor</th><th>Affiliation</th><th class="num">Total</th>
              <th class="num">Open</th><th class="num">Merged</th><th class="num">Add</th><th class="num">Del</th><th>Scale</th>
            </tr>
          </thead>
          <tbody>{''.join(leaderboard_rows)}</tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <h2>Recent Pull Requests</h2>
        <p class="timestamp">Latest 80 PRs across tracked contributors</p>
      </div>
      <div class="table-panel table-scroll">
        <table>
          <thead>
            <tr>
              <th>Pull Request</th><th>State</th><th>Affiliation</th><th>User</th>
              <th>Created</th><th class="num">Add</th><th class="num">Del</th>
            </tr>
          </thead>
          <tbody>{''.join(recent_rows)}</tbody>
        </table>
      </div>
    </section>
  </main>
  <script>
    const filterButtons = document.querySelectorAll('.filter-btn');
    const filterableRows = document.querySelectorAll('tr[data-affiliation]');

    filterButtons.forEach((button) => {{
      button.addEventListener('click', () => {{
        const filter = button.dataset.filter;
        filterButtons.forEach((item) => item.classList.toggle('active', item === button));
        filterableRows.forEach((row) => {{
          row.hidden = filter !== 'all' && row.dataset.affiliation !== filter;
        }});
      }});
    }});
  </script>
</body>
</html>
"""

    with open(HTML_FILENAME, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML dashboard created successfully: {HTML_FILENAME}")
    print(f"HTML dashboard file size: {os.path.getsize(HTML_FILENAME)} bytes")
    return HTML_FILENAME

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        raise ValueError("GH_PAT environment variable not set.")
        
    print(f"Starting Enhanced GitHub stats generation for {len(USERNAMES)} users...")
    print(f"Target repository: {TARGET_REPO}")
    print(f"Including PR contributions with additions/deletions tracking")
    print(f"Users to track: {USERNAMES}")
    
    github = Github(GITHUB_TOKEN)
    
    all_user_data = []
    for username in USERNAMES:
        try:
            print(f"\n{'='*50}")
            print(f"Processing user: {username}")
            
            display_name = get_user_display_name(github, username)
            stats = get_user_stats(github, username)
            total_contributions = stats['merged_prs'].totalCount + stats['open_prs'].totalCount
            
            # 获取PR的additions和deletions
            print(f"  Fetching additions/deletions for {username}'s PRs...")
            user_total_additions = 0
            user_total_deletions = 0
            
            # 处理merged PRs
            for pr in stats['merged_prs']:
                try:
                    additions, deletions, merged_at = get_pr_additions_deletions(github, pr)
                    pr._additions = additions
                    pr._deletions = deletions
                    pr._merged_at = merged_at
                    user_total_additions += additions
                    user_total_deletions += deletions
                    time.sleep(0.5)  # API rate limiting
                except Exception as e:
                    print(f"    Error processing merged PR #{pr.number}: {e}")
                    pr._additions = 0
                    pr._deletions = 0
                    pr._merged_at = None
            
            # 处理open PRs
            for pr in stats['open_prs']:
                try:
                    additions, deletions, merged_at = get_pr_additions_deletions(github, pr)
                    pr._additions = additions
                    pr._deletions = deletions
                    pr._merged_at = merged_at
                    user_total_additions += additions
                    user_total_deletions += deletions
                    time.sleep(0.5)  # API rate limiting
                except Exception as e:
                    print(f"    Error processing open PR #{pr.number}: {e}")
                    pr._additions = 0
                    pr._deletions = 0
                    pr._merged_at = None
            
            all_user_data.append({
                "username": username,
                "affiliation": USER_AFFILIATIONS.get(username, "Unknown"),
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
        print(f"  {user['display_name']} (@{user['username']}, {user.get('affiliation', 'Unknown')}): {user['total_contributions']} contributions, +{format_number(user_additions)} -{format_number(user_deletions)}")
    
    print(f"\nOverall totals:")
    print(f"  Total contributions: {sum(user['total_contributions'] for user in all_user_data)}")
    print(f"  Total code changes: +{format_number(total_all_additions)} -{format_number(total_all_deletions)}")

    print(f"\nAffiliation summary:")
    for affiliation, summary in summarize_by_affiliation(all_user_data).items():
        print(
            f"  {affiliation}: {summary['users']} users, "
            f"{summary['total_contributions']} contributions "
            f"({summary['open_prs']} open, {summary['merged_prs']} merged), "
            f"+{format_number(summary['total_additions'])} -{format_number(summary['total_deletions'])}"
        )

    try:
        latest_release_stats = get_latest_release_contribution_stats(github)
    except Exception as e:
        print(f"Error collecting latest release contribution stats: {e}")
        latest_release_stats = None
    
    print(f"\nGenerating enhanced chart for all {len(all_user_data)} users...")
    generate_chart(all_user_data)
    markdown_output = generate_markdown(all_user_data, latest_release_stats)
    readme_filename = create_fixed_readme(markdown_output)
    html_filename = create_dashboard_html(all_user_data, latest_release_stats)

    print(f"\n✅ All enhanced tasks completed successfully. README saved as: {readme_filename}")
    print(f"Enhanced chart saved as: {CHART_FILENAME}")
    print(f"HTML dashboard saved as: {html_filename}")
    print(f"Processed users: {[user['username'] for user in all_user_data]}")
