#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Run Spider_XHS batch note collection")
    parser.add_argument("--repo", default=".", help="Spider_XHS repo path")
    parser.add_argument("--users-excel", required=True)
    parser.add_argument("--task-name", required=True)
    parser.add_argument("--search-query", required=True)
    parser.add_argument("--keywords", required=True)
    parser.add_argument("--date-range", default="recent_7_days")
    parser.add_argument("--mode", choices=["both", "user", "search"], default="both")
    parser.add_argument("--max-search-candidates", type=int, default=1000)
    parser.add_argument("--output-dir", default="datas/batch_outputs")
    return parser.parse_args()


def main():
    args = parse_args()
    repo = Path(args.repo).resolve()
    if not (repo / "spider" / "collect_notes.py").exists():
        raise SystemExit(f"未找到 Spider_XHS 采集入口: {repo / 'spider' / 'collect_notes.py'}")
    users_excel = Path(args.users_excel)
    if not users_excel.exists():
        raise SystemExit(f"账号 Excel 不存在: {users_excel}")
    cmd = [
        sys.executable,
        "-m",
        "spider.collect_notes",
        "--users-excel",
        str(users_excel),
        "--task-name",
        args.task_name,
        "--search-query",
        args.search_query,
        "--keywords",
        args.keywords,
        "--date-range",
        args.date_range,
        "--mode",
        args.mode,
        "--max-search-candidates",
        str(args.max_search_candidates),
        "--output-dir",
        args.output_dir,
    ]
    completed = subprocess.run(cmd, cwd=str(repo), text=True)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
