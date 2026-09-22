import sys
import types
from datetime import datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

github_stub = types.ModuleType("github")
github_stub.Github = object
sys.modules["github"] = github_stub

import generate_stats as monitor


def test_beijing_month_windows_and_monthly_scoring():
    beijing = monitor.BEIJING_TZ
    now = datetime(2026, 9, 22, 12, 0, tzinfo=beijing)
    windows = monitor.get_month_windows(now)

    assert windows[0]["start"] == datetime(2026, 8, 1, 0, 0, tzinfo=beijing)
    assert windows[0]["end"] == datetime(2026, 9, 1, 0, 0, tzinfo=beijing)
    assert windows[1]["start"] == datetime(2026, 9, 1, 0, 0, tzinfo=beijing)
    assert windows[1]["end"] == now

    class User:
        def __init__(self, login):
            self.login = login

    class Stats:
        def __init__(self, additions, deletions):
            self.additions = additions
            self.deletions = deletions

    class Commit:
        def __init__(self, login, additions, deletions):
            self.author = User(login)
            self.sha = login
            self.stats = Stats(additions, deletions)

    class Review:
        def __init__(self, login, submitted_at):
            self.user = User(login)
            self.submitted_at = submitted_at

    class PullRequest:
        def __init__(self, number, reviews):
            self.number = number
            self._reviews = reviews

        def get_reviews(self):
            return self._reviews

    class Issue:
        def __init__(self, number):
            self.number = number

    class Repo:
        def get_commits(self, since, until):
            return [
                Commit("jiangkuaixue123", 10, 2),
                Commit("untracked-user", 4, 4),
            ]

        def get_pull(self, number):
            return PullRequest(
                number,
                [
                    Review(
                        "bjf-frz",
                        datetime(2026, 8, 15, 4, tzinfo=timezone.utc),
                    )
                ],
            )

    class Github:
        def search_issues(self, query):
            return [Issue(1)] if "updated:" in query else [Issue(2)]

    people = monitor.MONTHLY_SCENE_CONFIGS["afd-plugin"]["people"]
    stats = monitor._collect_monthly_window_stats(
        Github(),
        Repo(),
        "vllm-project/afd-plugin",
        people,
        windows[0]["start"],
        windows[0]["end"],
        windows[0]["section_title"],
    )

    assert stats["tracked_commits"] == 1
    assert stats["tracked_reviews"] == 1
    assert stats["tracked_additions"] == 10
    assert stats["tracked_deletions"] == 2
    assert round(sum(user["contribution_score"] for user in stats["users"]), 6) == 100.0
    assert stats["users"][0]["username"] == "jiangkuaixue123"

    merged_stats = monitor._merge_monthly_window_stats(
        [stats, stats],
        people,
        windows[0]["section_title"],
        windows[0]["start"],
        windows[0]["end"],
    )
    assert merged_stats["tracked_commits"] == 2
    assert merged_stats["tracked_reviews"] == 2
    assert merged_stats["tracked_additions"] == 20
    assert merged_stats["tracked_deletions"] == 4
    assert round(
        sum(user["contribution_score"] for user in merged_stats["users"]), 6
    ) == 100.0


def test_scene_repo_configuration():
    assert monitor.MONTHLY_SCENE_CONFIGS["afd-plugin"]["repositories"] == [
        "vllm-project/afd-plugin",
        "vllm-project/vllm",
        "vllm-project/vllm-ascend",
    ]
    assert monitor.MONTHLY_SCENE_CONFIGS["AgentInfer"]["repositories"] == [
        "openJiuwen-ai/agent-infer",
        "vllm-project/router",
        "vllm-project/semantic-router",
        "vllm-project/vllm",
        "vllm-project/vllm-ascend",
    ]


if __name__ == "__main__":
    test_beijing_month_windows_and_monthly_scoring()
    test_scene_repo_configuration()
    print("monthly monitoring smoke test passed")
