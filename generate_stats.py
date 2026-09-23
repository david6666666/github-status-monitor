import os
import re
import requests
import time
from itertools import islice
from datetime import datetime, timedelta, timezone
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
    "Committer": ["Gaohan123", "hsliuustc0106", "david6666666", "gcanlin", "Isotr0py", "linyueqian", "lishunyang12", "princepride", "RuixiangMa", "SamitHuang", "tzhouam", "wtomin", "ZeldaHuang", "ZJY0516", "yuanheng-zhao", "Sy0307", "alex-jw-brooks"],
}
USER_LABELS = {}
for affiliation, usernames in USER_GROUPS.items():
    for username in usernames:
        USER_LABELS.setdefault(username.strip(), []).append(affiliation)
USERNAMES = list(USER_LABELS)
USER_AFFILIATIONS = {
    username: labels[0]
    for username, labels in USER_LABELS.items()
}
# Your GitHub Personal Access Token, read from an environment variable
GITHUB_TOKEN = os.getenv('GH_PAT')
# The output filename for the chart
CHART_FILENAME = "stats_chart.svg"
# The output filename for the standalone HTML dashboard
HTML_FILENAME = "stats_dashboard.html"
# Target repository - only vllm-project/vllm-omni
TARGET_REPO = "vllm-project/vllm-omni"
# Fixed UTC+08:00 is sufficient for Beijing time because it has no DST changes.
BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
PR_SAMPLE_PER_QUERY = 10
RECENT_PR_DISPLAY_LIMIT = 80
MONTHLY_REVIEW_EXCLUDED_REPOS = {"vllm-project/vllm"}
# Monthly reports use the personnel and display names from the supplied team sheet.
# Each scene aggregates every repository listed in the sheet's "涉及repo" column.
MONTHLY_SCENE_CONFIGS = {
    "afd-plugin": {
        "label": "afd-plugin",
        "chart_filename": "stats_chart_afd_plugin.svg",
        "html_filename": "stats_dashboard_afd_plugin.html",
        "repositories": [
            "vllm-project/afd-plugin",
            "vllm-project/vllm",
            "vllm-project/vllm-ascend",
        ],
        "people": [
            {"name": "江晨舟", "username": "jiangkuaixue123", "location": "杭州"},
            {"name": "白竞帆", "username": "bjf-frz", "location": "杭州"},
            {"name": "周子恒", "username": "jiaran-king", "location": "杭州"},
            {"name": "曹玉娟", "username": "yujuancao07", "location": "上海"},
            {"name": "李瑞鑫", "username": "lirx-pd", "location": "上海"},
            {"name": "侯安捷", "username": "specture724", "location": "上海"},
        ],
    },
    "AgentInfer": {
        "label": "AgentInfer",
        "chart_filename": "stats_chart_agentinfer.svg",
        "html_filename": "stats_dashboard_agentinfer.html",
        "repositories": [
            "openJiuwen-ai/agent-infer",
            "vllm-project/router",
            "vllm-project/semantic-router",
            "vllm-project/vllm",
            "vllm-project/vllm-ascend",
        ],
        "people": [
            {"name": "杨剑娟", "username": "yangjianjuan", "location": "杭州"},
            {"name": "吴航", "username": "wuhang2014", "location": "杭州"},
            {"name": "敬昊昱", "username": "PharosEast", "location": "杭州"},
            {"name": "胡海川", "username": "KaisennHu", "location": "上海"},
            {"name": "梁腾文", "username": "LiangTengwen", "location": "上海"},
            {"name": "李雯琳", "username": "Evelynn-V", "location": "上海"},
            {"name": "张璇", "username": "potatoZhx", "location": "上海"},
            {"name": "牛衍昌", "username": "warriorsniu", "location": "北京"},
        ],
    },
}
# Fixed README filename
README_FILENAME = "README_data.md"
CONTRIBUTION_WEIGHTS = {
    "commit": 0.20,
    "review": 0.35,
    "code": 0.45,
}
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

class _CombinedResult:
    """Small PyGithub-like result wrapper for multi-repository PR totals."""

    def __init__(self, items, total_count=None):
        self._items = list(items)
        self.totalCount = (
            len(self._items) if total_count is None else total_count
        )

    def __iter__(self):
        return iter(self._items)


def get_user_stats_fallback(github_instance, username, target_repo=TARGET_REPO):
    """
    备用方法：直接从组织的仓库中获取用户的PR统计
    """
    print(f"  Using fallback method for {username}...")
    
    open_prs = []
    merged_prs = []
    
    try:
        repo = github_instance.get_repo(target_repo)
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

def get_user_stats(
    github_instance,
    username,
    target_repo=TARGET_REPO,
    item_limit=PR_SAMPLE_PER_QUERY,
):
    """
    Fetch exact open/merged PR counts and a bounded list of newest PRs.
    """
    print(f"Fetching all data for {username} in {target_repo} repository...")

    repo_qualifier = f"repo:{target_repo}"

    # 1. PRs: Query for open and merged PRs separately in the target repository
    query_open_prs = f"is:pr author:{username} is:public is:open {repo_qualifier}"
    query_merged_prs = f"is:pr author:{username} is:public is:merged {repo_qualifier}"
    
    print(f"  Open PR query: {query_open_prs}")
    print(f"  Merged PR query: {query_merged_prs}")
    
    # 添加延迟以避免API限制
    time.sleep(1)
    
    try:
        open_search = github_instance.search_issues(
            query_open_prs, sort="created", order="desc"
        )
        merged_search = github_instance.search_issues(
            query_merged_prs, sort="created", order="desc"
        )
        
        print(f"  ✓ Search API Success for {username}")

        open_count = open_search.totalCount
        merged_count = merged_search.totalCount
        if item_limit is None:
            open_items = list(open_search)
            merged_items = list(merged_search)
            open_count = len(open_items)
            merged_count = len(merged_items)
        else:
            open_items = list(islice(open_search, item_limit))
            merged_items = list(islice(merged_search, item_limit))

        open_prs = _CombinedResult(open_items, open_count)
        merged_prs = _CombinedResult(merged_items, merged_count)
        print(f"    Open PRs totalCount: {open_count}; loaded: {len(open_items)}")
        print(f"    Merged PRs totalCount: {merged_count}; loaded: {len(merged_items)}")
        
    except Exception as e:
        print(f"  ✗ Search API Error for {username}: {type(e).__name__}: {e}")
        if item_limit is not None:
            print("    Skipping unbounded fallback scan for this repository.")
            return {
                "open_prs": _CombinedResult([]),
                "merged_prs": _CombinedResult([]),
            }
        return get_user_stats_fallback(
            github_instance, username, target_repo=target_repo
        )
    
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

def get_affiliation_labels(username):
    return USER_LABELS.get(username, [USER_AFFILIATIONS.get(username, "Unknown")])

def format_affiliation_labels(labels):
    return ", ".join(labels)

def format_percent(value):
    return f"{value:.1f}%"

def _code_line_weight(additions, deletions):
    return max(additions, 0) + max(deletions, 0)

def _stats_value(stats, name):
    if not stats:
        return 0
    if isinstance(stats, dict):
        return stats.get(name, 0) or 0
    return getattr(stats, name, 0) or 0

def _get_commit_line_delta(repo, commit):
    stats = getattr(commit, "stats", None)
    if stats is None:
        try:
            stats = repo.get_commit(commit.sha).stats
        except Exception as e:
            print(f"    Error fetching code delta for commit {commit.sha}: {e}")
            return 0, 0
    return _stats_value(stats, "additions"), _stats_value(stats, "deletions")

def _score_release_items(items):
    total_commits = sum(item.get("commit_count", 0) for item in items)
    total_reviews = sum(item.get("review_count", 0) for item in items)
    total_code_weight = sum(item.get("code_line_weight", 0) for item in items)

    for item in items:
        commit_component = (
            item.get("commit_count", 0) / total_commits * CONTRIBUTION_WEIGHTS["commit"] * 100
            if total_commits else 0
        )
        review_component = (
            item.get("review_count", 0) / total_reviews * CONTRIBUTION_WEIGHTS["review"] * 100
            if total_reviews else 0
        )
        code_component = (
            item.get("code_line_weight", 0) / total_code_weight * CONTRIBUTION_WEIGHTS["code"] * 100
            if total_code_weight else 0
        )
        item["commit_component"] = commit_component
        item["review_component"] = review_component
        item["code_component"] = code_component
        item["contribution_score"] = commit_component + review_component + code_component

def _release_score_note():
    return (
        "Contribution score = 20% commit share + 35% review share + "
        "45% code churn share, where code churn is additions + deletions. "
        "Commit share reflects delivery, review share reflects quality influence, "
        "and code churn linearly reflects change scale."
    )

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
        affiliations = user.get('affiliations') or [user.get('affiliation', 'Unknown')]
        stats = user['stats']

        for affiliation in affiliations:
            if affiliation not in summaries:
                summaries[affiliation] = {
                    "users": 0,
                    "total_contributions": 0,
                    "open_prs": 0,
                    "merged_prs": 0,
                    "total_additions": 0,
                    "total_deletions": 0,
                }

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
            "additions": 0,
            "deletions": 0,
            "code_line_count": 0,
            "code_line_weight": 0,
            "commit_component": 0,
            "review_component": 0,
            "code_component": 0,
            "contribution_score": 0,
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

def _is_integer_formal_release(release):
    return re.fullmatch(r"v\d+\.\d+\.0", release.tag_name or "") is not None

def _get_formal_releases(repo, count=2):
    formal_releases = []
    for release in repo.get_releases():
        if (
            not release.draft
            and not release.prerelease
            and _is_integer_formal_release(release)
        ):
            formal_releases.append(release)
        if len(formal_releases) >= count:
            break
    return formal_releases

def _collect_release_window_stats(
    github_instance,
    repo,
    base_release,
    head_ref,
    end_time,
    section_title,
    headline_label,
    headline_value,
):
    base_time = _release_time(base_release)
    if not base_time or not end_time:
        print(f"  Release timestamps are incomplete; skipping {section_title}.")
        return None

    affiliation_stats = _empty_release_affiliation_stats()
    user_stats = {
        username: {
            "username": username,
            "affiliation": USER_AFFILIATIONS.get(username, "Unknown"),
            "affiliations": get_affiliation_labels(username),
            "commit_count": 0,
            "review_count": 0,
            "reviewed_pr_count": 0,
            "additions": 0,
            "deletions": 0,
            "code_line_count": 0,
            "code_line_weight": 0,
            "commit_component": 0,
            "review_component": 0,
            "code_component": 0,
            "contribution_score": 0,
        }
        for username in USERNAMES
    }

    compare = repo.compare(base_release.tag_name, head_ref)
    compare_commits = list(compare.commits)
    total_commits = len(compare_commits)
    tracked_commits = 0

    for commit in compare_commits:
        author = getattr(commit, "author", None)
        login = getattr(author, "login", None) if author else None
        if not login or login not in USER_AFFILIATIONS:
            continue

        additions, deletions = _get_commit_line_delta(repo, commit)
        code_line_count = additions + deletions
        code_line_weight = _code_line_weight(additions, deletions)
        tracked_commits += 1
        for affiliation in get_affiliation_labels(login):
            affiliation_stats[affiliation]["commit_count"] += 1
            affiliation_stats[affiliation]["additions"] += additions
            affiliation_stats[affiliation]["deletions"] += deletions
            affiliation_stats[affiliation]["code_line_count"] += code_line_count
            affiliation_stats[affiliation]["code_line_weight"] += code_line_weight
            affiliation_stats[affiliation]["commit_users"][login] = (
                affiliation_stats[affiliation]["commit_users"].get(login, 0) + 1
            )
        user_stats[login]["commit_count"] += 1
        user_stats[login]["additions"] += additions
        user_stats[login]["deletions"] += deletions
        user_stats[login]["code_line_count"] += code_line_count
        user_stats[login]["code_line_weight"] += code_line_weight

    start_date = base_time.strftime('%Y-%m-%d')
    end_date = end_time.strftime('%Y-%m-%d')
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
                if submitted_at < base_time or submitted_at > end_time:
                    continue

                total_reviews += 1
                reviewer = review.user.login if review.user else None
                if not reviewer or reviewer not in USER_AFFILIATIONS:
                    continue

                tracked_reviews += 1
                for affiliation in get_affiliation_labels(reviewer):
                    affiliation_stats[affiliation]["review_count"] += 1
                    affiliation_stats[affiliation]["review_users"][reviewer] = (
                        affiliation_stats[affiliation]["review_users"].get(reviewer, 0) + 1
                    )
                user_stats[reviewer]["review_count"] += 1
                reviewed_prs_by_user[reviewer].add(issue.number)
                for affiliation in get_affiliation_labels(reviewer):
                    reviewed_prs_by_affiliation[affiliation].add(issue.number)
        except Exception as e:
            print(f"    Error processing reviews for PR #{issue.number}: {e}")
            continue

    for affiliation, pr_numbers in reviewed_prs_by_affiliation.items():
        affiliation_stats[affiliation]["reviewed_pr_count"] = len(pr_numbers)
    for username, pr_numbers in reviewed_prs_by_user.items():
        user_stats[username]["reviewed_pr_count"] = len(pr_numbers)

    affiliation_items = list(affiliation_stats.values())
    user_items = list(user_stats.values())
    _score_release_items(affiliation_items)
    _score_release_items(user_items)

    user_rows = [
        stats for stats in user_stats.values()
        if (
            stats["commit_count"]
            or stats["review_count"]
            or stats["reviewed_pr_count"]
            or stats["code_line_count"]
        )
    ]
    user_rows.sort(
        key=lambda item: (
            item["contribution_score"],
            item["commit_count"] + item["review_count"],
            item["code_line_count"],
        ),
        reverse=True,
    )
    tracked_additions = sum(user["additions"] for user in user_stats.values())
    tracked_deletions = sum(user["deletions"] for user in user_stats.values())

    print(
        f"  {section_title}: {base_release.tag_name} -> {head_ref}; "
        f"tracked commits {tracked_commits}/{total_commits}, "
        f"tracked reviews {tracked_reviews}/{total_reviews}, "
        f"tracked code delta +{tracked_additions}/-{tracked_deletions}"
    )

    return {
        "section_title": section_title,
        "headline_label": headline_label,
        "headline_value": headline_value,
        "latest_tag": head_ref,
        "previous_tag": base_release.tag_name,
        "latest_published_at": end_time,
        "previous_published_at": base_time,
        "compare_url": f"https://github.com/{TARGET_REPO}/compare/{base_release.tag_name}...{head_ref}",
        "merged_pr_count": len(merged_pr_issues),
        "total_commits": total_commits,
        "tracked_commits": tracked_commits,
        "total_reviews": total_reviews,
        "tracked_reviews": tracked_reviews,
        "tracked_additions": tracked_additions,
        "tracked_deletions": tracked_deletions,
        "tracked_code_line_count": tracked_additions + tracked_deletions,
        "score_note": _release_score_note(),
        "affiliations": affiliation_stats,
        "users": user_rows,
    }

def get_release_contribution_stats(github_instance):
    """
    Collect commit and review contributions for the last formal release and
    current main branch development window.
    """
    print(f"Collecting release contribution stats for {TARGET_REPO}...")

    repo = github_instance.get_repo(TARGET_REPO)
    formal_releases = _get_formal_releases(repo, count=2)
    if len(formal_releases) < 2:
        print("  Not enough formal releases found to build release contribution stats.")
        return None, None

    latest_release = formal_releases[0]
    previous_release = formal_releases[1]
    latest_time = _release_time(latest_release)
    previous_time = _release_time(previous_release)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    if not latest_time or not previous_time:
        print("  Release timestamps are incomplete; skipping release contribution stats.")
        return None, None

    last_release_stats = _collect_release_window_stats(
        github_instance=github_instance,
        repo=repo,
        base_release=previous_release,
        head_ref=latest_release.tag_name,
        end_time=latest_time,
        section_title="Last Release Contributions",
        headline_label="Last formal release",
        headline_value=latest_release.tag_name,
    )
    current_release_stats = _collect_release_window_stats(
        github_instance=github_instance,
        repo=repo,
        base_release=latest_release,
        head_ref="main",
        end_time=now_utc,
        section_title="Current Release Contributions",
        headline_label="Current head",
        headline_value="main",
    )
    return last_release_stats, current_release_stats


def _to_utc_datetime(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_beijing_datetime(dt):
    utc_dt = _to_utc_datetime(dt)
    return utc_dt.astimezone(BEIJING_TZ) if utc_dt else None


def get_month_windows(now=None):
    """Return previous/current calendar-month windows using Beijing time."""
    now_beijing = _to_beijing_datetime(now or datetime.now(timezone.utc))
    current_start = now_beijing.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    previous_start = (current_start - timedelta(days=1)).replace(day=1)
    return [
        {
            "key": "previous_month",
            "section_title": "上月贡献（北京时间）",
            "start": previous_start,
            "end": current_start,
        },
        {
            "key": "current_month",
            "section_title": "本月贡献（北京时间）",
            "start": current_start,
            "end": now_beijing,
        },
    ]


def _empty_window_affiliation_stats(labels):
    return {
        label: {
            "commit_count": 0,
            "review_count": 0,
            "reviewed_pr_count": 0,
            "additions": 0,
            "deletions": 0,
            "code_line_count": 0,
            "code_line_weight": 0,
            "commit_component": 0,
            "review_component": 0,
            "code_component": 0,
            "contribution_score": 0,
            "commit_users": {},
            "review_users": {},
        }
        for label in labels
    }


def _empty_window_user_stats(people):
    return {
        person["username"]: {
            "username": person["username"],
            "display_name": person["name"],
            "affiliation": person["location"],
            "affiliations": [person["location"]],
            "commit_count": 0,
            "review_count": 0,
            "reviewed_pr_count": 0,
            "additions": 0,
            "deletions": 0,
            "code_line_count": 0,
            "code_line_weight": 0,
            "commit_component": 0,
            "review_component": 0,
            "code_component": 0,
            "contribution_score": 0,
        }
        for person in people
    }


def _collect_monthly_window_stats(
    github_instance,
    repo,
    repo_name,
    people,
    start_time,
    end_time,
    section_title,
):
    start_utc = _to_utc_datetime(start_time)
    end_utc = _to_utc_datetime(end_time)
    labels = sorted({person["location"] for person in people})
    label_by_username = {
        person["username"]: person["location"] for person in people
    }
    tracked_usernames = set(label_by_username)
    affiliation_stats = _empty_window_affiliation_stats(labels)
    user_stats = _empty_window_user_stats(people)

    try:
        commits = list(repo.get_commits(since=start_utc, until=end_utc))
    except Exception as exc:
        print(f"  Error fetching commits for {repo_name} ({section_title}): {exc}")
        commits = []

    tracked_commits = 0
    for commit in commits:
        author = getattr(commit, "author", None)
        login = getattr(author, "login", None) if author else None
        if login not in tracked_usernames:
            continue

        additions, deletions = _get_commit_line_delta(repo, commit)
        code_line_count = additions + deletions
        code_line_weight = _code_line_weight(additions, deletions)
        label = label_by_username[login]
        tracked_commits += 1

        summary = affiliation_stats[label]
        summary["commit_count"] += 1
        summary["additions"] += additions
        summary["deletions"] += deletions
        summary["code_line_count"] += code_line_count
        summary["code_line_weight"] += code_line_weight
        summary["commit_users"][login] = summary["commit_users"].get(login, 0) + 1

        user = user_stats[login]
        user["commit_count"] += 1
        user["additions"] += additions
        user["deletions"] += deletions
        user["code_line_count"] += code_line_count
        user["code_line_weight"] += code_line_weight

    start_date = start_utc.strftime("%Y-%m-%d")
    end_date = end_utc.strftime("%Y-%m-%d")
    review_issues_by_number = {}
    reviews_excluded = repo_name in MONTHLY_REVIEW_EXCLUDED_REPOS
    if reviews_excluded:
        print(f"  Skipping monthly review collection for {repo_name} by configuration.")
    else:
        for username in sorted(tracked_usernames):
            review_query = (
                f"repo:{repo_name} is:pr reviewed-by:{username} "
                f"updated:{start_date}..{end_date}"
            )
            print(f"  Monthly review query: {review_query}")
            try:
                for issue in github_instance.search_issues(review_query):
                    review_issues_by_number.setdefault(issue.number, issue)
            except Exception as exc:
                print(
                    f"  Error fetching review candidates for {repo_name}/"
                    f"{username}: {exc}"
                )

    tracked_reviews = 0
    reviewed_prs_by_user = {username: set() for username in tracked_usernames}
    reviewed_prs_by_label = {label: set() for label in labels}

    for issue in review_issues_by_number.values():
        try:
            pr = repo.get_pull(issue.number)
            for review in pr.get_reviews():
                submitted_at = _to_utc_datetime(review.submitted_at)
                if not submitted_at or not (start_utc <= submitted_at < end_utc):
                    continue

                reviewer = review.user.login if review.user else None
                if reviewer not in tracked_usernames:
                    continue

                tracked_reviews += 1
                label = label_by_username[reviewer]
                summary = affiliation_stats[label]
                summary["review_count"] += 1
                summary["review_users"][reviewer] = (
                    summary["review_users"].get(reviewer, 0) + 1
                )
                user_stats[reviewer]["review_count"] += 1
                reviewed_prs_by_user[reviewer].add(issue.number)
                reviewed_prs_by_label[label].add(issue.number)
        except Exception as exc:
            print(f"    Error processing reviews for PR #{issue.number}: {exc}")

    for label, pr_numbers in reviewed_prs_by_label.items():
        affiliation_stats[label]["reviewed_pr_count"] = len(pr_numbers)
    for username, pr_numbers in reviewed_prs_by_user.items():
        user_stats[username]["reviewed_pr_count"] = len(pr_numbers)

    try:
        merged_query = (
            f"repo:{repo_name} is:pr is:merged merged:{start_date}..{end_date}"
        )
        merged_results = github_instance.search_issues(merged_query)
        merged_pr_count = getattr(merged_results, "totalCount", None)
        if merged_pr_count is None:
            merged_pr_count = len(merged_results)
    except Exception as exc:
        print(f"  Error fetching merged PR count for {repo_name}: {exc}")
        merged_pr_count = 0

    _score_release_items(list(affiliation_stats.values()))
    _score_release_items(list(user_stats.values()))
    user_rows = sorted(
        user_stats.values(),
        key=lambda item: (
            item["contribution_score"],
            item["commit_count"] + item["review_count"],
            item["code_line_count"],
            item["username"],
        ),
        reverse=True,
    )
    tracked_additions = sum(user["additions"] for user in user_stats.values())
    tracked_deletions = sum(user["deletions"] for user in user_stats.values())

    print(
        f"  {repo_name} {section_title}: "
        f"tracked commits {tracked_commits}/{len(commits)}, "
        f"tracked reviews {tracked_reviews}, "
        f"tracked code delta +{tracked_additions}/-{tracked_deletions}"
    )
    return {
        "repo_name": repo_name,
        "reviews_excluded": reviews_excluded,
        "section_title": section_title,
        "window_start": start_time,
        "window_end": end_time,
        "tracked_commits": tracked_commits,
        "total_commits": len(commits),
        "tracked_reviews": tracked_reviews,
        "tracked_additions": tracked_additions,
        "tracked_deletions": tracked_deletions,
        "tracked_code_line_count": tracked_additions + tracked_deletions,
        "merged_pr_count": merged_pr_count,
        "score_note": _release_score_note(),
        "affiliations": affiliation_stats,
        "users": user_rows,
    }


def _merge_monthly_window_stats(repo_stats, people, section_title, start_time, end_time):
    """Merge raw monthly metrics across all repositories in one scene."""
    labels = sorted({person["location"] for person in people})
    affiliation_stats = _empty_window_affiliation_stats(labels)
    user_stats = _empty_window_user_stats(people)
    numeric_fields = (
        "commit_count",
        "review_count",
        "reviewed_pr_count",
        "additions",
        "deletions",
        "code_line_count",
        "code_line_weight",
    )

    for stats in repo_stats:
        for label, source in stats["affiliations"].items():
            target = affiliation_stats[label]
            for field in numeric_fields:
                target[field] += source.get(field, 0)
            for field in ("commit_users", "review_users"):
                for username, count in source.get(field, {}).items():
                    target[field][username] = target[field].get(username, 0) + count

        for source in stats["users"]:
            target = user_stats[source["username"]]
            for field in numeric_fields:
                target[field] += source.get(field, 0)

    _score_release_items(list(affiliation_stats.values()))
    _score_release_items(list(user_stats.values()))
    user_rows = sorted(
        user_stats.values(),
        key=lambda item: (
            item["contribution_score"],
            item["commit_count"] + item["review_count"],
            item["code_line_count"],
            item["username"],
        ),
        reverse=True,
    )
    return {
        "section_title": section_title,
        "window_start": start_time,
        "window_end": end_time,
        "review_excluded_repos": sorted(
            stats["repo_name"]
            for stats in repo_stats
            if stats.get("reviews_excluded") and stats.get("repo_name")
        ),
        "tracked_commits": sum(stats["tracked_commits"] for stats in repo_stats),
        "total_commits": sum(stats["total_commits"] for stats in repo_stats),
        "tracked_reviews": sum(stats["tracked_reviews"] for stats in repo_stats),
        "tracked_additions": sum(
            stats["tracked_additions"] for stats in repo_stats
        ),
        "tracked_deletions": sum(
            stats["tracked_deletions"] for stats in repo_stats
        ),
        "tracked_code_line_count": sum(
            stats["tracked_code_line_count"] for stats in repo_stats
        ),
        "merged_pr_count": sum(stats["merged_pr_count"] for stats in repo_stats),
        "score_note": _release_score_note(),
        "affiliations": affiliation_stats,
        "users": user_rows,
    }


def get_monthly_contribution_stats(
    github_instance, scene_name, repo_names, people, now=None
):
    """Collect and scene-aggregate previous/current Beijing-month windows."""
    print(
        f"Collecting monthly contribution stats for {scene_name} across "
        f"{len(repo_names)} repos"
    )
    repos = [
        (repo_name, github_instance.get_repo(repo_name))
        for repo_name in repo_names
    ]
    stats = []
    for window in get_month_windows(now):
        repo_window_stats = []
        for repo_name, repo in repos:
            repo_window_stats.append(
                _collect_monthly_window_stats(
                    github_instance=github_instance,
                    repo=repo,
                    repo_name=repo_name,
                    people=people,
                    start_time=window["start"],
                    end_time=window["end"],
                    section_title=window["section_title"],
                )
            )
        stats.append(
            _merge_monthly_window_stats(
                repo_window_stats,
                people,
                window["section_title"],
                window["start"],
                window["end"],
            )
        )
    return stats


def collect_scene_user_data(github_instance, scene_name, repo_names, people):
    """Collect all-time PR monitoring data across every repo in one scene."""
    all_user_data = []
    for person in people:
        username = person["username"]
        open_prs = []
        merged_prs = []
        open_count = 0
        merged_count = 0
        try:
            print(f"\nProcessing {scene_name} user: {username}")
            for repo_name in repo_names:
                stats = get_user_stats(
                    github_instance,
                    username,
                    target_repo=repo_name,
                    item_limit=PR_SAMPLE_PER_QUERY,
                )
                open_prs.extend(list(stats["open_prs"]))
                merged_prs.extend(list(stats["merged_prs"]))
                open_count += stats["open_prs"].totalCount
                merged_count += stats["merged_prs"].totalCount

            combined_stats = {
                "open_prs": _CombinedResult(open_prs, open_count),
                "merged_prs": _CombinedResult(merged_prs, merged_count),
            }
            total_contributions = (
                combined_stats["merged_prs"].totalCount
                + combined_stats["open_prs"].totalCount
            )
            all_user_data.append(
                {
                    "username": username,
                    "affiliation": person["location"],
                    "affiliations": [person["location"]],
                    "display_name": person["name"],
                    "stats": combined_stats,
                    "total_contributions": total_contributions,
                    "total_additions": 0,
                    "total_deletions": 0,
                }
            )
        except Exception as exc:
            print(f"Error processing {scene_name} user {username}: {exc}")

    all_user_data.sort(key=lambda item: item["total_contributions"], reverse=True)
    _attach_recent_pr_deltas(github_instance, all_user_data)
    return all_user_data


def format_beijing_datetime(dt):
    beijing_dt = _to_beijing_datetime(dt)
    if not beijing_dt:
        return "-"
    return beijing_dt.strftime("%Y-%m-%d %H:%M:%S GMT+8")


def _monthly_recent_prs(user_data, limit=RECENT_PR_DISPLAY_LIMIT):
    recent_prs = []
    for user in user_data:
        for state, prs in (
            ("merged", user["stats"]["merged_prs"]),
            ("open", user["stats"]["open_prs"]),
        ):
            for pr in prs:
                recent_prs.append(
                    {
                        "title": pr.title,
                        "url": pr.html_url,
                        "repo": pr.repository.full_name,
                        "state": state,
                        "created_at": pr.created_at,
                        "additions": getattr(pr, "_additions", 0),
                        "deletions": getattr(pr, "_deletions", 0),
                        "user": user["username"],
                        "display_name": user["display_name"],
                        "location": user["affiliation"],
                        "_pull_request": pr,
                        "_user_record": user,
                    }
                )

    recent_prs.sort(
        key=lambda item: item["created_at"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return recent_prs[:limit]


def _attach_recent_pr_deltas(github_instance, user_data, limit=RECENT_PR_DISPLAY_LIMIT):
    """Fetch code deltas only for PRs shown in the recent-PR tables."""
    for user in user_data:
        user["total_additions"] = 0
        user["total_deletions"] = 0

    recent_prs = _monthly_recent_prs(user_data, limit=limit)
    for item in recent_prs:
        pr = item["_pull_request"]
        additions, deletions, merged_at = get_pr_additions_deletions(
            github_instance, pr
        )
        pr._additions = additions
        pr._deletions = deletions
        pr._merged_at = merged_at
        item["additions"] = additions
        item["deletions"] = deletions
        user = item["_user_record"]
        user["total_additions"] += additions
        user["total_deletions"] += deletions
        time.sleep(0.5)


def _append_monthly_window_markdown(markdown_text, window_stats):
    markdown_text += f"#### {window_stats['section_title']}\n\n"
    markdown_text += (
        f"时间: {format_beijing_datetime(window_stats['window_start'])} -> "
        f"{format_beijing_datetime(window_stats['window_end'])}\n\n"
    )
    markdown_text += (
        f"Tracked commits: {format_number(window_stats['tracked_commits'])}/"
        f"{format_number(window_stats['total_commits'])}; "
        f"Tracked reviews: {format_number(window_stats['tracked_reviews'])}; "
        f"Tracked code delta: +{format_number(window_stats['tracked_additions'])}/"
        f"-{format_number(window_stats['tracked_deletions'])}; "
        f"Merged PRs in window: {format_number(window_stats['merged_pr_count'])}\n\n"
    )
    if window_stats["review_excluded_repos"]:
        markdown_text += (
            "Review counts exclude "
            f"{', '.join(window_stats['review_excluded_repos'])}; "
            "PR monitoring/counts still include these repositories.\n\n"
        )
    markdown_text += f"Scoring: {window_stats['score_note']}\n\n"
    markdown_text += "| 属地 | Contribution | Commits | Reviews | Reviewed PRs | Additions | Deletions | Code Lines |\n"
    markdown_text += "| ---- | ------------ | ------- | ------- | ------------ | --------- | --------- | ---------- |\n"
    affiliation_rows = sorted(
        window_stats["affiliations"].items(),
        key=lambda item: item[1]["contribution_score"],
        reverse=True,
    )
    for label, summary in affiliation_rows:
        markdown_text += (
            f"| {label} | {format_percent(summary['contribution_score'])} | "
            f"{format_number(summary['commit_count'])} | "
            f"{format_number(summary['review_count'])} | "
            f"{format_number(summary['reviewed_pr_count'])} | "
            f"{format_number(summary['additions'])} | "
            f"{format_number(summary['deletions'])} | "
            f"{format_number(summary['code_line_count'])} |\n"
        )
    markdown_text += "\n| 姓名 | GitHub ID | 属地 | Contribution | Commits | Reviews | Reviewed PRs | Additions | Deletions |\n"
    markdown_text += "| ---- | --------- | ---- | ------------ | ------- | ------- | ------------ | --------- | --------- |\n"
    for user in window_stats["users"]:
        markdown_text += (
            f"| {user['display_name']} | @{user['username']} | "
            f"{user['affiliation']} | {format_percent(user['contribution_score'])} | "
            f"{format_number(user['commit_count'])} | "
            f"{format_number(user['review_count'])} | "
            f"{format_number(user['reviewed_pr_count'])} | "
            f"{format_number(user['additions'])} | "
            f"{format_number(user['deletions'])} |\n"
        )
    return markdown_text + "\n"


def generate_monthly_scene_markdown(scene_name, config, user_data, monthly_stats):
    total_open = sum(user["stats"]["open_prs"].totalCount for user in user_data)
    total_merged = sum(user["stats"]["merged_prs"].totalCount for user in user_data)
    total_additions = sum(user.get("total_additions", 0) for user in user_data)
    total_deletions = sum(user.get("total_deletions", 0) for user in user_data)
    repo_links = "、".join(
        f"[{repo}](https://github.com/{repo})" for repo in config["repositories"]
    )
    markdown_text = (
        f"\n---\n\n## {config['label']} 月度监控与贡献度\n\n"
        f"投入场景: **{scene_name}**  \n"
        f"涉及 repo: {repo_links}  \n"
        f"独立看板: [{config['html_filename']}]({config['html_filename']})\n\n"
        f"![{config['label']} contribution chart]({config['chart_filename']})\n\n"
        f"本次追踪 {len(user_data)} 人；PR 总量 {format_number(total_open + total_merged)} "
        f"（Open {format_number(total_open)} / Merged {format_number(total_merged)}）；"
        f"最近展示的最多 {RECENT_PR_DISPLAY_LIMIT} 个 PR 代码变更 "
        f"+{format_number(total_additions)} / -{format_number(total_deletions)}。\n\n"
        "### PR 监控汇总\n\n"
        f"PR 总数为完整搜索计数；最近 PR 候选按每人、每 repo、每状态最多 "
        f"{PR_SAMPLE_PER_QUERY} 条读取，代码变更只统计下方展示项。\n\n"
        "| 姓名 | GitHub ID | 属地 | Total PRs | Open PRs | Merged PRs | Recent Additions | Recent Deletions |\n"
        "| ---- | --------- | ---- | --------- | -------- | ---------- | ---------------- | ---------------- |\n"
    )
    for user in user_data:
        stats = user["stats"]
        markdown_text += (
            f"| {user['display_name']} | @{user['username']} | {user['affiliation']} | "
            f"{format_number(user['total_contributions'])} | "
            f"{format_number(stats['open_prs'].totalCount)} | "
            f"{format_number(stats['merged_prs'].totalCount)} | "
            f"{format_number(user.get('total_additions', 0))} | "
            f"{format_number(user.get('total_deletions', 0))} |\n"
        )
    markdown_text += "\n"
    for window_stats in monthly_stats:
        if window_stats:
            markdown_text = _append_monthly_window_markdown(markdown_text, window_stats)
        else:
            markdown_text += "#### Monthly contribution unavailable\n\n"
    markdown_text += f"### 最近 PR（最多 {RECENT_PR_DISPLAY_LIMIT} 条，跨场景 repo）\n\n"
    markdown_text += "| Title | Repository | State | User | Created | Additions | Deletions |\n"
    markdown_text += "| ----- | ---------- | ----- | ---- | ------- | --------- | --------- |\n"
    recent_prs = _monthly_recent_prs(user_data)
    for pr in recent_prs:
        title = pr["title"].replace("|", "\\|")
        created_date = (
            format_beijing_datetime(pr["created_at"]).replace(" GMT+8", "")
            if pr["created_at"]
            else "-"
        )
        markdown_text += (
            f"| [{title}]({pr['url']}) | [{pr['repo']}](https://github.com/{pr['repo']}) | "
            f"`{pr['state']}` | "
            f"{pr['display_name']} (@{pr['user']}) | {created_date} | "
            f"{format_number(pr['additions'])} | {format_number(pr['deletions'])} |\n"
        )
    if not recent_prs:
        markdown_text += "| _No relevant pull requests found._ | | | | | | |\n"
    return markdown_text + "\n"


def create_monthly_dashboard(scene_name, config, user_data, monthly_stats):
    """Create a compact standalone dashboard for one aggregated scene."""
    generated_at = format_beijing_datetime(datetime.now(timezone.utc))
    total_open = sum(user["stats"]["open_prs"].totalCount for user in user_data)
    total_merged = sum(user["stats"]["merged_prs"].totalCount for user in user_data)
    total_additions = sum(user.get("total_additions", 0) for user in user_data)
    total_deletions = sum(user.get("total_deletions", 0) for user in user_data)
    repo_links_html = " · ".join(
        f"<a href='https://github.com/{escape(repo)}'>{escape(repo)}</a>"
        for repo in config["repositories"]
    )

    try:
        with open(config["chart_filename"], "r", encoding="utf-8") as chart_file:
            chart_markup = chart_file.read()
    except OSError:
        chart_markup = "<p>Chart is not available in this run.</p>"

    monitoring_rows = []
    for user in user_data:
        stats = user["stats"]
        monitoring_rows.append(
            f"<tr><td>{escape(user['display_name'])}</td>"
            f"<td>@{escape(user['username'])}</td>"
            f"<td>{escape(user['affiliation'])}</td>"
            f"<td class='num'>{format_number(user['total_contributions'])}</td>"
            f"<td class='num'>{format_number(stats['open_prs'].totalCount)}</td>"
            f"<td class='num'>{format_number(stats['merged_prs'].totalCount)}</td>"
            f"<td class='num'>+{format_number(user.get('total_additions', 0))}</td>"
            f"<td class='num'>-{format_number(user.get('total_deletions', 0))}</td></tr>"
        )

    window_sections = []
    for window_stats in monthly_stats:
        if not window_stats:
            window_sections.append(
                "<section><h2>Monthly contribution unavailable</h2></section>"
            )
            continue
        label_rows = []
        for label, summary in sorted(
            window_stats["affiliations"].items(),
            key=lambda item: item[1]["contribution_score"],
            reverse=True,
        ):
            label_rows.append(
                f"<tr><td>{escape(label)}</td>"
                f"<td class='num'>{format_percent(summary['contribution_score'])}</td>"
                f"<td class='num'>{format_number(summary['commit_count'])}</td>"
                f"<td class='num'>{format_number(summary['review_count'])}</td>"
                f"<td class='num'>{format_number(summary['reviewed_pr_count'])}</td>"
                f"<td class='num'>+{format_number(summary['additions'])}</td>"
                f"<td class='num'>-{format_number(summary['deletions'])}</td></tr>"
            )
        user_rows = []
        for user in window_stats["users"]:
            user_rows.append(
                f"<tr><td>{escape(user['display_name'])}</td>"
                f"<td>@{escape(user['username'])}</td>"
                f"<td>{escape(user['affiliation'])}</td>"
                f"<td class='num'>{format_percent(user['contribution_score'])}</td>"
                f"<td class='num'>{format_number(user['commit_count'])}</td>"
                f"<td class='num'>{format_number(user['review_count'])}</td>"
                f"<td class='num'>{format_number(user['reviewed_pr_count'])}</td>"
                f"<td class='num'>+{format_number(user['additions'])}</td>"
                f"<td class='num'>-{format_number(user['deletions'])}</td></tr>"
            )
        review_exclusion_note = ""
        if window_stats["review_excluded_repos"]:
            review_exclusion_note = (
                "<p class='muted'>Review counts exclude "
                f"{escape(', '.join(window_stats['review_excluded_repos']))}; "
                "PR monitoring/counts still include these repositories.</p>"
            )
        window_sections.append(
            f"<section><h2>{escape(window_stats['section_title'])}</h2>"
            f"<p class='muted'>时间: {escape(format_beijing_datetime(window_stats['window_start']))}"
            f" → {escape(format_beijing_datetime(window_stats['window_end']))}</p>"
            f"{review_exclusion_note}"
            f"<p>{escape(window_stats['score_note'])}</p>"
            f"<table><thead><tr><th>属地</th><th>Contribution</th><th>Commits</th>"
            f"<th>Reviews</th><th>Reviewed PRs</th><th>Additions</th><th>Deletions</th></tr></thead>"
            f"<tbody>{''.join(label_rows)}</tbody></table>"
            f"<table><thead><tr><th>姓名</th><th>GitHub ID</th><th>属地</th>"
            f"<th>Contribution</th><th>Commits</th><th>Reviews</th><th>Reviewed PRs</th>"
            f"<th>Additions</th><th>Deletions</th></tr></thead>"
            f"<tbody>{''.join(user_rows)}</tbody></table></section>"
        )

    recent_rows = []
    for pr in _monthly_recent_prs(user_data):
        recent_rows.append(
            f"<tr><td><a href='{escape(pr['url'])}'>{escape(pr['title'])}</a>"
            f"<span class='muted'>{escape(pr['repo'])}</span></td>"
            f"<td>{escape(pr['state'])}</td><td>{escape(pr['display_name'])}"
            f"<span class='muted'>@{escape(pr['user'])}</span></td>"
            f"<td>{escape(format_beijing_datetime(pr['created_at']))}</td>"
            f"<td class='num'>+{format_number(pr['additions'])}</td>"
            f"<td class='num'>-{format_number(pr['deletions'])}</td></tr>"
        )

    html_content = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(scene_name)} monthly contribution monitor</title>
  <style>
    :root {{ --bg: #f3efe5; --surface: #fffdfa; --ink: #151516; --muted: #6c665c; --line: #d9d1c2; --accent: #00796b; }}
    * {{ box-sizing: border-box; }} body {{ margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.5 "Segoe UI", sans-serif; }}
    main {{ width: min(1500px, calc(100% - 32px)); margin: 0 auto; padding: 22px 0 48px; }}
    h1, h2 {{ font-family: "Bahnschrift", "Segoe UI", sans-serif; }} h1 {{ font-size: clamp(32px, 6vw, 72px); line-height: .95; margin: 20px 0 10px; }}
    h2 {{ border-bottom: 2px solid var(--ink); padding-bottom: 8px; margin-top: 28px; }}
    .muted {{ color: var(--muted); display: block; }} .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }}
    .metric, section, .chart {{ background: var(--surface); border: 1px solid var(--line); padding: 14px; margin-top: 14px; }}
    .metric strong {{ display: block; font-size: 28px; margin-top: 8px; }} .chart svg {{ max-width: 100%; height: auto; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0; background: var(--surface); }} th, td {{ border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #ebe4d6; }} .num {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
    a {{ color: inherit; font-weight: 700; }} @media (max-width: 760px) {{ .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} table {{ font-size: 12px; display: block; overflow-x: auto; }} }}
  </style>
</head>
<body><main>
  <p class="muted">{escape(scene_name)} · Generated {escape(generated_at)}</p>
  <h1>{escape(config['label'])}<br>monthly monitor</h1>
  <p class="muted">涉及 repo: {repo_links_html}</p>
  <p class="muted">PR 计数为完整结果；最近 PR 候选按每人、每 repo、每状态最多 {PR_SAMPLE_PER_QUERY} 条读取，代码变更只统计下方展示项。</p>
  <div class="metrics">
    <div class="metric"><span>Tracked users</span><strong>{format_number(len(user_data))}</strong></div>
    <div class="metric"><span>Total PRs</span><strong>{format_number(total_open + total_merged)}</strong></div>
    <div class="metric"><span>Open / merged</span><strong>{format_number(total_open)} / {format_number(total_merged)}</strong></div>
    <div class="metric"><span>Recent displayed PR code delta (max {RECENT_PR_DISPLAY_LIMIT})</span><strong>+{format_number(total_additions)} / -{format_number(total_deletions)}</strong></div>
  </div>
  <div class="chart">{chart_markup}</div>
  <section><h2>PR 监控汇总</h2><table><thead><tr><th>姓名</th><th>GitHub ID</th><th>属地</th><th>Total PRs</th><th>Open</th><th>Merged</th><th>Recent Additions</th><th>Recent Deletions</th></tr></thead><tbody>{''.join(monitoring_rows)}</tbody></table></section>
  {''.join(window_sections)}
  <section><h2>最近 PR（最多 {RECENT_PR_DISPLAY_LIMIT} 条，跨场景 repo）</h2><table><thead><tr><th>Title / Repository</th><th>State</th><th>User</th><th>Created</th><th>Additions</th><th>Deletions</th></tr></thead><tbody>{''.join(recent_rows) or '<tr><td colspan="6">No relevant pull requests found.</td></tr>'}</tbody></table></section>
</main></body></html>"""

    with open(config["html_filename"], "w", encoding="utf-8") as html_file:
        html_file.write(html_content)
    print(f"Monthly HTML dashboard created successfully: {config['html_filename']}")
    return config["html_filename"]

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

def generate_chart(user_data, chart_filename=CHART_FILENAME, target_repo=TARGET_REPO):
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
    print(
        f"Chart data - Recent displayed PR additions: {format_number(total_additions)}, "
        f"deletions: {format_number(total_deletions)}"
    )
    
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
        f"{target_repo} PR贡献统计 - 共{len(user_data)}位用户",
        f"总计: Open PRs: {total_open_prs} | Merged PRs: {total_merged_prs}",
        f"最近展示 PR 代码变更 (最多 {RECENT_PR_DISPLAY_LIMIT} 条): "
        f"+{format_number(total_additions)} -{format_number(total_deletions)}"
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
                        "labelString": f"用户名称 (最近展示 PR 代码变更: +{format_number(total_additions)} -{format_number(total_deletions)})",
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
            with open(chart_filename, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"✅ Enhanced chart with black bold fonts saved successfully as {chart_filename}")
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
                    with open(chart_filename, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    print(f"✅ Smaller enhanced chart with black bold fonts saved successfully as {chart_filename}")
                else:
                    print(f"❌ Even smaller chart failed: {response.status_code}")
                    
    except requests.exceptions.RequestException as e:
        print(f"❌ Error making request to QuickChart: {e}")
    except Exception as e:
        print(f"❌ Unexpected error generating chart: {e}")

def _append_release_markdown(markdown_text, release_stats, fallback_title):
    markdown_text += f"## {fallback_title}\n\n"
    if not release_stats:
        markdown_text += "_Release contribution stats unavailable. Check the GitHub Actions log for details._\n\n"
        return markdown_text

    markdown_text += (
        f"区间: [{release_stats['previous_tag']}...{release_stats['latest_tag']}]({release_stats['compare_url']})  \n"
        f"时间: {format_datetime(release_stats['previous_published_at'])} -> "
        f"{format_datetime(release_stats['latest_published_at'])}\n\n"
    )
    markdown_text += (
        f"Tracked commits: {format_number(release_stats['tracked_commits'])}/"
        f"{format_number(release_stats['total_commits'])}; "
        f"Tracked reviews: {format_number(release_stats['tracked_reviews'])}/"
        f"{format_number(release_stats['total_reviews'])}; "
        f"Tracked code delta: +{format_number(release_stats['tracked_additions'])}/"
        f"-{format_number(release_stats['tracked_deletions'])}; "
        f"Merged PRs in window: {format_number(release_stats['merged_pr_count'])}\n\n"
    )
    markdown_text += f"Scoring: {release_stats['score_note']}\n\n"
    markdown_text += "| Affiliation | Contribution | Commits | Reviews | Reviewed PRs | Additions | Deletions | Code Lines |\n"
    markdown_text += "| ---- | ------------ | ------- | ------- | ------------ | --------- | --------- | ---------- |\n"
    affiliation_rows = sorted(
        release_stats["affiliations"].items(),
        key=lambda item: item[1]["contribution_score"],
        reverse=True,
    )
    for affiliation, summary in affiliation_rows:
        markdown_text += (
            f"| {affiliation} | {format_percent(summary['contribution_score'])} | "
            f"{format_number(summary['commit_count'])} | "
            f"{format_number(summary['review_count'])} | "
            f"{format_number(summary['reviewed_pr_count'])} | "
            f"{format_number(summary['additions'])} | "
            f"{format_number(summary['deletions'])} | "
            f"{format_number(summary['code_line_count'])} |\n"
        )
    markdown_text += "\n"
    markdown_text += "| User | Labels | Contribution | Commits | Reviews | Reviewed PRs | Additions | Deletions | Code Lines |\n"
    markdown_text += "| ---- | ------ | ------------ | ------- | ------- | ------------ | --------- | --------- | ---------- |\n"
    for user in release_stats["users"]:
        labels = format_affiliation_labels(user.get('affiliations') or [user.get('affiliation', 'Unknown')])
        markdown_text += (
            f"| @{user['username']} | {labels} | "
            f"{format_percent(user['contribution_score'])} | "
            f"{format_number(user['commit_count'])} | "
            f"{format_number(user['review_count'])} | "
            f"{format_number(user['reviewed_pr_count'])} | "
            f"{format_number(user['additions'])} | "
            f"{format_number(user['deletions'])} | "
            f"{format_number(user['code_line_count'])} |\n"
        )
    markdown_text += "\n"
    return markdown_text

def generate_markdown(user_data, last_release_stats=None, current_release_stats=None):
    """生成包含additions/deletions统计的Markdown表格"""
    markdown_text = f"这是根据在 **{TARGET_REPO}** 仓库中的 PR 贡献（Merged PRs + Open PRs）进行的排序。\n\n"
    markdown_text += (
        f"总共追踪了 {len(user_data)} 个用户；Open/Merged PR 数为完整搜索计数，"
        f"代码变更统计覆盖最近展示的最多 {RECENT_PR_DISPLAY_LIMIT} 个 PR。\n\n"
    )
    
    # 计算总的additions和deletions
    total_all_additions = sum(user.get('total_additions', 0) for user in user_data)
    total_all_deletions = sum(user.get('total_deletions', 0) for user in user_data)
    
    markdown_text += (
        f"**最近展示 PR 代码变更统计**: +{format_number(total_all_additions)} 行添加, "
        f"-{format_number(total_all_deletions)} 行删除\n\n"
    )
    markdown_text += "## 按归属统计\n\n"
    markdown_text += "| 归属 | 用户数 | Total PRs | Open PRs | Merged PRs | Recent Additions | Recent Deletions |\n"
    markdown_text += "| ---- | ------ | --------- | -------- | ---------- | ---------------- | ---------------- |\n"

    for affiliation, summary in summarize_by_affiliation(user_data).items():
        markdown_text += (
            f"| {affiliation} | {summary['users']} | {summary['total_contributions']} | "
            f"{summary['open_prs']} | {summary['merged_prs']} | "
            f"{format_number(summary['total_additions'])} | {format_number(summary['total_deletions'])} |\n"
        )

    markdown_text += "\n"

    markdown_text = _append_release_markdown(
        markdown_text, last_release_stats, "Last Release Contributions"
    )
    markdown_text = _append_release_markdown(
        markdown_text, current_release_stats, "Current Release Contributions"
    )

    for user in user_data:
        username = user['username']
        display_name = user['display_name']
        stats = user['stats']
        total_contributions = user['total_contributions']
        user_additions = user.get('total_additions', 0)
        user_deletions = user.get('total_deletions', 0)
        affiliation = format_affiliation_labels(user.get('affiliations') or [user.get('affiliation', 'Unknown')])
        
        # 显示用户名和显示名称，包含代码变更统计
        if display_name != username:
            markdown_text += f"### 👤 {display_name} (@{username}) - {affiliation} - 总贡献: {total_contributions}\n"
        else:
            markdown_text += f"### 👤 {username} - {affiliation} - 总贡献: {total_contributions}\n"
        
        markdown_text += (
            f"**最近展示 PR 代码变更**: +{format_number(user_additions)} 行添加, "
            f"-{format_number(user_deletions)} 行删除\n\n"
        )
        
        # PR Table with additions/deletions and merged time
        markdown_text += (
            f"**Pull Requests ({stats['open_prs'].totalCount} open, "
            f"{stats['merged_prs'].totalCount} merged; up to "
            f"{PR_SAMPLE_PER_QUERY} newest per state shown)**\n"
        )
        
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
            additions = (
                format_number(pr._additions) if hasattr(pr, "_additions") else "—"
            )
            deletions = (
                format_number(pr._deletions) if hasattr(pr, "_deletions") else "—"
            )
            
            row_string = f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `merged` | {created_date} | {merged_date} | {additions} | {deletions} |\n"
            pr_rows.append((pr.created_at, row_string))
            
        # Process open PRs
        for pr in stats['open_prs']:
            repo_name = pr.repository.full_name
            title = pr.title.replace('|', '\|')
            created_date = pr.created_at.strftime('%Y-%m-%d')
            merged_at = getattr(pr, '_merged_at', None) or getattr(pr, 'merged_at', None)
            merged_date = format_datetime(merged_at)
            
            # 获取PR的additions和deletions (如果已存储)
            additions = (
                format_number(pr._additions) if hasattr(pr, "_additions") else "—"
            )
            deletions = (
                format_number(pr._deletions) if hasattr(pr, "_deletions") else "—"
            )
            
            row_string = f"| [{title}]({pr.html_url}) | [{repo_name}](https://github.com/{repo_name}) | `open` | {created_date} | {merged_date} | {additions} | {deletions} |\n"
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
    readme_header += (
        f"**统计范围**: {TARGET_REPO} 仓库的完整 PR 计数；代码变更统计覆盖最近展示的 "
        f"最多 {RECENT_PR_DISPLAY_LIMIT} 个 PR。\n\n"
    )
    readme_header += f"![Enhanced GitHub Stats Chart]({CHART_FILENAME})\n\n"
    readme_header += "---\n\n"
    
    full_content = readme_header + content
    
    # Write to the fixed filename with explicit encoding
    with open(README_FILENAME, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    print(f"Enhanced README created successfully: {README_FILENAME}")
    print(f"README file size: {os.path.getsize(README_FILENAME)} bytes")
    return README_FILENAME

def create_dashboard_html(user_data, last_release_stats=None, current_release_stats=None):
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

    def affiliation_attr(labels):
        return escape("|".join(labels), quote=True)

    def affiliation_pills(labels):
        return "".join(f'<span class="pill">{escape(label)}</span>' for label in labels)

    def render_release_section(release_stats, fallback_title):
        if not release_stats:
            return f"""
    <section class="section">
      <div class="section-head">
        <h2>{escape(fallback_title)}</h2>
        <p class="timestamp">Release stats unavailable</p>
      </div>
      <div class="table-panel release-empty">
        Release contribution stats could not be collected in this run. Check the GitHub Actions log for details.
      </div>
    </section>"""

        release_group_rows = []
        affiliation_rows = sorted(
            release_stats["affiliations"].items(),
            key=lambda item: item[1]["contribution_score"],
            reverse=True,
        )
        for affiliation, summary in affiliation_rows:
            release_group_rows.append(f"""
          <tr data-affiliations="{escape(affiliation, quote=True)}">
            <td><span class="pill">{escape(affiliation)}</span></td>
            <td class="num">{format_percent(summary['contribution_score'])}</td>
            <td class="num">{format_percent(summary['commit_component'])}</td>
            <td class="num">{format_percent(summary['review_component'])}</td>
            <td class="num">{format_percent(summary['code_component'])}</td>
            <td class="num">{format_number(summary['commit_count'])}</td>
            <td class="num">{format_number(summary['review_count'])}</td>
            <td class="num">{format_number(summary['reviewed_pr_count'])}</td>
            <td class="num">+{format_number(summary['additions'])}</td>
            <td class="num">-{format_number(summary['deletions'])}</td>
            <td class="num">{format_number(summary['code_line_count'])}</td>
          </tr>""")

        release_user_rows = []
        for user in release_stats["users"]:
            affiliations = user.get('affiliations') or [user.get('affiliation', 'Unknown')]
            release_user_rows.append(f"""
          <tr data-affiliations="{affiliation_attr(affiliations)}">
            <td class="person">@{escape(user['username'])}</td>
            <td><div class="pill-list">{affiliation_pills(affiliations)}</div></td>
            <td class="num">{format_percent(user['contribution_score'])}</td>
            <td class="num">{format_percent(user['commit_component'])}</td>
            <td class="num">{format_percent(user['review_component'])}</td>
            <td class="num">{format_percent(user['code_component'])}</td>
            <td class="num">{format_number(user['commit_count'])}</td>
            <td class="num">{format_number(user['review_count'])}</td>
            <td class="num">{format_number(user['reviewed_pr_count'])}</td>
            <td class="num">+{format_number(user['additions'])}</td>
            <td class="num">-{format_number(user['deletions'])}</td>
            <td class="num">{format_number(user['code_line_count'])}</td>
          </tr>""")

        return f"""
    <section class="section">
      <div class="section-head">
        <h2>{escape(release_stats['section_title'])}</h2>
        <p class="timestamp">
          <a href="{escape(release_stats['compare_url'])}">
            {escape(release_stats['previous_tag'])}...{escape(release_stats['latest_tag'])}
          </a>
        </p>
      </div>
      <div class="release-grid">
        <div class="metric"><span>{escape(release_stats['headline_label'])}</span><strong>{escape(release_stats['headline_value'])}</strong></div>
        <div class="metric"><span>Tracked commits</span><strong>{format_number(release_stats['tracked_commits'])}</strong></div>
        <div class="metric"><span>Tracked reviews</span><strong>{format_number(release_stats['tracked_reviews'])}</strong></div>
        <div class="metric"><span>Tracked code delta</span><strong>+{format_number(release_stats['tracked_additions'])} / -{format_number(release_stats['tracked_deletions'])}</strong></div>
        <div class="metric"><span>Merged PRs</span><strong>{format_number(release_stats['merged_pr_count'])}</strong></div>
      </div>
      <p class="score-note">{escape(release_stats['score_note'])}</p>
      <div class="release-tables">
        <div class="table-panel">
          <table>
            <thead><tr><th>Affiliation</th><th class="num">Contribution</th><th class="num">Commit pts</th><th class="num">Review pts</th><th class="num">Code pts</th><th class="num">Commits</th><th class="num">Reviews</th><th class="num">Reviewed PRs</th><th class="num">Add</th><th class="num">Del</th><th class="num">Lines</th></tr></thead>
            <tbody>{''.join(release_group_rows)}</tbody>
          </table>
        </div>
        <div class="table-panel">
          <table>
            <thead><tr><th>User</th><th>Affiliation</th><th class="num">Contribution</th><th class="num">Commit pts</th><th class="num">Review pts</th><th class="num">Code pts</th><th class="num">Commits</th><th class="num">Reviews</th><th class="num">Reviewed PRs</th><th class="num">Add</th><th class="num">Del</th><th class="num">Lines</th></tr></thead>
            <tbody>{''.join(release_user_rows)}</tbody>
          </table>
        </div>
      </div>
    </section>"""

    release_sections = (
        render_release_section(last_release_stats, "Last Release Contributions")
        + render_release_section(current_release_stats, "Current Release Contributions")
    )

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
        affiliations = user.get('affiliations') or [user.get('affiliation', 'Unknown')]
        stats = user['stats']
        total = user['total_contributions']
        bar_width = (total / max_contributions * 100) if max_contributions else 0
        leaderboard_rows.append(f"""
          <tr data-affiliations="{affiliation_attr(affiliations)}">
            <td class="rank">{rank}</td>
            <td>
              <a class="person" href="https://github.com/{escape(username)}">{escape(display_name)}</a>
              <span class="muted">@{escape(username)}</span>
            </td>
            <td><div class="pill-list">{affiliation_pills(affiliations)}</div></td>
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
                    "affiliations": user.get('affiliations') or [user.get('affiliation', 'Unknown')],
                })

    recent_prs.sort(key=lambda pr: pr["created_at"] or datetime.min, reverse=True)
    recent_rows = []
    for pr in recent_prs[:80]:
        created_date = pr["created_at"].strftime('%Y-%m-%d') if pr["created_at"] else "-"
        affiliations = pr.get('affiliations') or [pr.get('affiliation', 'Unknown')]
        recent_rows.append(f"""
          <tr data-affiliations="{affiliation_attr(affiliations)}">
            <td>
              <a class="pr-title" href="{escape(pr['url'])}">{escape(pr['title'])}</a>
              <span class="muted">{escape(pr['repo'])}</span>
            </td>
            <td><span class="state {escape(pr['state'])}">{escape(pr['state'])}</span></td>
            <td><div class="pill-list">{affiliation_pills(affiliations)}</div></td>
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
      --bg: #f3efe5;
      --surface: #fffdfa;
      --surface-2: #f8f3e8;
      --ink: #151516;
      --muted: #6c665c;
      --line: #d9d1c2;
      --line-strong: #1f1f1f;
      --green: #00796b;
      --amber: #b76500;
      --red: #b83f35;
      --blue: #315c98;
      --shadow: 0 18px 44px rgba(34, 30, 23, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      background:
        linear-gradient(90deg, rgba(21,21,22,0.045) 1px, transparent 1px),
        linear-gradient(rgba(21,21,22,0.04) 1px, transparent 1px),
        radial-gradient(circle at 0 0, rgba(0,121,107,0.10), transparent 34%),
        var(--bg);
      background-size: 32px 32px, 32px 32px, 100% 620px, auto;
      color: var(--ink);
      font-family: "Aptos", "Bahnschrift", "Segoe UI", sans-serif;
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1560px, calc(100% - 36px)); margin: 0 auto; padding: 22px 0 48px; }}
    .topline {{
      align-items: center;
      background: rgba(255,253,250,0.82);
      border: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 12px 14px;
      position: sticky;
      top: 12px;
      z-index: 8;
      backdrop-filter: blur(14px);
    }}
    .mark {{ font: 800 12px/1.1 "Bahnschrift", "Aptos", sans-serif; letter-spacing: 0.13em; text-transform: uppercase; }}
    .timestamp {{ color: var(--muted); font: 12px/1.4 "Aptos", sans-serif; }}
    .hero {{
      align-items: stretch;
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(420px, 0.85fr);
      gap: 18px;
      padding: 28px 0 18px;
    }}
    h1 {{
      align-self: end;
      font: 800 clamp(42px, 6vw, 92px)/0.92 "Bahnschrift", "Aptos", sans-serif;
      letter-spacing: 0;
      margin: 0;
      max-width: 920px;
    }}
    .summary-strip {{
      align-self: stretch;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .metric {{
      background: linear-gradient(180deg, rgba(255,253,250,0.98), rgba(248,243,232,0.96));
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      min-height: 104px;
      padding: 16px;
      position: relative;
      overflow: hidden;
    }}
    .metric::before {{
      background: var(--green);
      content: "";
      height: 4px;
      left: 0;
      position: absolute;
      top: 0;
      width: 100%;
    }}
    .release-grid .metric:nth-child(2)::before {{ background: var(--blue); }}
    .release-grid .metric:nth-child(3)::before {{ background: var(--amber); }}
    .release-grid .metric:nth-child(4)::before {{ background: var(--red); }}
    .metric span, .eyebrow, th, .muted, dt {{
      color: var(--muted);
      font: 800 10px/1.35 "Bahnschrift", "Aptos", sans-serif;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .metric strong {{ display: block; font: 800 clamp(24px, 3vw, 42px)/1 "Bahnschrift", "Aptos", sans-serif; margin-top: 13px; }}
    .section {{ margin-top: 18px; }}
    .section-head {{
      align-items: end;
      border-bottom: 2px solid var(--ink);
      display: flex;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 12px;
      padding-bottom: 10px;
    }}
    h2 {{ font: 800 clamp(22px, 2.5vw, 34px)/1 "Bahnschrift", "Aptos", sans-serif; margin: 0; }}
    .filters {{
      align-items: center;
      background: rgba(255,253,250,0.88);
      border: 1px solid var(--line);
      box-shadow: 0 10px 30px rgba(34,30,23,0.08);
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 10px 0 18px;
      padding: 10px;
      position: sticky;
      top: 72px;
      z-index: 7;
      backdrop-filter: blur(14px);
    }}
    .filter-btn {{
      background: var(--surface);
      border: 1px solid var(--line);
      color: var(--ink);
      cursor: pointer;
      font: 800 11px/1 "Bahnschrift", "Aptos", sans-serif;
      padding: 10px 12px;
      text-transform: uppercase;
      transition: background 140ms ease, border-color 140ms ease, color 140ms ease;
    }}
    .filter-btn.active, .filter-btn:hover {{
      background: var(--ink);
      border-color: var(--ink);
      color: var(--surface);
    }}
    .groups {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; }}
    .release-grid {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-bottom: 10px; }}
    .release-tables {{ display: grid; grid-template-columns: minmax(0, 0.78fr) minmax(0, 1.22fr); gap: 12px; }}
    .score-note {{
      background: rgba(21,21,22,0.035);
      border-left: 4px solid var(--green);
      color: var(--muted);
      font: 12px/1.55 "Aptos", sans-serif;
      margin: 0 0 12px;
      padding: 10px 12px;
    }}
    .group-card {{
      background: var(--surface);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      min-height: 142px;
      padding: 14px;
    }}
    .group-card h3 {{ font: 800 34px/1 "Bahnschrift", "Aptos", sans-serif; margin: 10px 0 18px; }}
    dl {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px 12px; margin: 0; }}
    dd {{ font: 800 18px/1 "Bahnschrift", "Aptos", sans-serif; margin: 4px 0 0; }}
    .chart-panel, .table-panel {{
      background: rgba(255,253,250,0.94);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .release-tables .table-panel {{ overflow-x: auto; }}
    .release-empty {{ color: var(--muted); padding: 18px; }}
    .chart-panel {{ padding: 12px; }}
    .chart-panel img {{ display: block; width: 100%; height: auto; background: white; border: 1px solid var(--line); }}
    .chart-svg {{ background: white; border: 1px solid var(--line); overflow-x: auto; }}
    .chart-svg svg {{ display: block; height: auto; max-width: none; width: 100%; }}
    .chart-placeholder {{ background: white; border: 1px solid var(--line); color: var(--muted); padding: 22px; }}
    table {{ border-collapse: collapse; min-width: 100%; width: 100%; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 12px; text-align: left; vertical-align: middle; }}
    th {{
      background: #ebe4d6;
      box-shadow: inset 0 -1px 0 var(--line);
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    tbody tr:hover {{ background: #fff4d1; }}
    tr[hidden] {{ display: none; }}
    .num {{ font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }}
    .rank {{ color: var(--red); font: 800 20px/1 "Bahnschrift", "Aptos", sans-serif; width: 58px; }}
    .person, .pr-title {{ font-weight: 800; }}
    .person:hover, .pr-title:hover {{ color: var(--green); }}
    .muted {{ display: block; margin-top: 3px; text-transform: none; letter-spacing: 0; }}
    .pill, .state {{
      border: 1px solid var(--line);
      display: inline-flex;
      font: 800 10px/1 "Bahnschrift", "Aptos", sans-serif;
      padding: 6px 8px;
      white-space: nowrap;
    }}
    .pill {{ background: #fff; }}
    .pill-list {{ display: flex; flex-wrap: wrap; gap: 5px; }}
    .state.open {{ background: #fff0bd; border-color: #c99000; color: #654800; }}
    .state.merged {{ background: #dff3e8; border-color: #3b956b; color: #145331; }}
    .bar {{ background: #e2dbcf; height: 9px; min-width: 90px; overflow: hidden; }}
    .bar span {{ background: linear-gradient(90deg, var(--green), var(--amber)); display: block; height: 100%; }}
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

    <nav class="filters" aria-label="Filter by affiliation">
      {''.join(filter_buttons)}
    </nav>

    {release_sections}

    <section class="section groups">
      {''.join(group_cards)}
    </section>

    <section class="section">
      <div class="section-head">
        <h2>Contribution Volume</h2>
        <p class="timestamp">Recent displayed PR code delta (max {RECENT_PR_DISPLAY_LIMIT}): +{format_number(total_additions)} / -{format_number(total_deletions)}</p>
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
              <th class="num">Open</th><th class="num">Merged</th><th class="num">Recent Add</th><th class="num">Recent Del</th><th>Scale</th>
            </tr>
          </thead>
          <tbody>{''.join(leaderboard_rows)}</tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <h2>Recent Pull Requests</h2>
        <p class="timestamp">Latest {RECENT_PR_DISPLAY_LIMIT} PRs across tracked contributors and configured repos</p>
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
    const filterableRows = document.querySelectorAll('tr[data-affiliations]');

    filterButtons.forEach((button) => {{
      button.addEventListener('click', () => {{
        const filter = button.dataset.filter;
        filterButtons.forEach((item) => item.classList.toggle('active', item === button));
        filterableRows.forEach((row) => {{
          const labels = (row.dataset.affiliations || '').split('|');
          row.hidden = filter !== 'all' && !labels.includes(filter);
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
        
    print(f"Starting GitHub stats generation for {len(USERNAMES)} users...")
    print(f"Target repository: {TARGET_REPO}")
    print(
        f"PR counts are complete; code deltas are fetched for the latest "
        f"{RECENT_PR_DISPLAY_LIMIT} displayed PRs."
    )
    print(f"Users to track: {USERNAMES}")
    
    github = Github(GITHUB_TOKEN, per_page=100)
    
    all_user_data = []
    for username in USERNAMES:
        try:
            print(f"\n{'='*50}")
            print(f"Processing user: {username}")
            
            display_name = get_user_display_name(github, username)
            stats = get_user_stats(
                github, username, item_limit=PR_SAMPLE_PER_QUERY
            )
            total_contributions = stats['merged_prs'].totalCount + stats['open_prs'].totalCount

            all_user_data.append({
                "username": username,
                "affiliation": USER_AFFILIATIONS.get(username, "Unknown"),
                "affiliations": get_affiliation_labels(username),
                "display_name": display_name,
                "stats": stats,
                "total_contributions": total_contributions,
                "total_additions": 0,
                "total_deletions": 0
            })
            
            print(f"✅ Successfully processed {username}:")
            print(f"   Total contributions: {total_contributions}")
            
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
    _attach_recent_pr_deltas(github, all_user_data)
    
    # 打印最终统计
    print(f"\nFinal contribution summary:")
    total_all_additions = 0
    total_all_deletions = 0
    for user in all_user_data:
        user_additions = user.get('total_additions', 0)
        user_deletions = user.get('total_deletions', 0)
        total_all_additions += user_additions
        total_all_deletions += user_deletions
        affiliations = format_affiliation_labels(user.get('affiliations') or [user.get('affiliation', 'Unknown')])
        print(f"  {user['display_name']} (@{user['username']}, {affiliations}): {user['total_contributions']} contributions, +{format_number(user_additions)} -{format_number(user_deletions)}")
    
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
        last_release_stats, current_release_stats = get_release_contribution_stats(github)
    except Exception as e:
        print(f"Error collecting release contribution stats: {e}")
        last_release_stats = None
        current_release_stats = None

    monthly_reports = []
    for scene_name, scene_config in MONTHLY_SCENE_CONFIGS.items():
        print(f"\n{'=' * 50}")
        print(
            f"Collecting monthly report for {scene_name} across "
            f"{len(scene_config['repositories'])} repos"
        )
        try:
            monthly_user_data = collect_scene_user_data(
                github,
                scene_name,
                scene_config["repositories"],
                scene_config["people"],
            )
            monthly_stats = get_monthly_contribution_stats(
                github,
                scene_name,
                scene_config["repositories"],
                scene_config["people"],
            )
            generate_chart(
                monthly_user_data,
                chart_filename=scene_config["chart_filename"],
                target_repo=scene_name,
            )
            create_monthly_dashboard(
                scene_name, scene_config, monthly_user_data, monthly_stats
            )
            monthly_reports.append(
                {
                    "scene_name": scene_name,
                    "config": scene_config,
                    "user_data": monthly_user_data,
                    "monthly_stats": monthly_stats,
                }
            )
        except Exception as exc:
            print(f"Error collecting monthly report for {scene_name}: {exc}")

    print(f"\nGenerating enhanced chart for all {len(all_user_data)} users...")
    generate_chart(all_user_data)
    markdown_output = generate_markdown(all_user_data, last_release_stats, current_release_stats)
    for monthly_report in monthly_reports:
        markdown_output += generate_monthly_scene_markdown(
            monthly_report["scene_name"],
            monthly_report["config"],
            monthly_report["user_data"],
            monthly_report["monthly_stats"],
        )
    readme_filename = create_fixed_readme(markdown_output)
    html_filename = create_dashboard_html(all_user_data, last_release_stats, current_release_stats)

    print(f"\n✅ All enhanced tasks completed successfully. README saved as: {readme_filename}")
    print(f"Enhanced chart saved as: {CHART_FILENAME}")
    print(f"HTML dashboard saved as: {html_filename}")
    print(
        "Monthly dashboards saved as: "
        f"{[report['config']['html_filename'] for report in monthly_reports]}"
    )
    print(f"Processed users: {[user['username'] for user in all_user_data]}")
