#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
sys.dont_write_bytecode = True

from bootstrap import ensure_environment, find_repo

DEFAULT_MAX_SEARCH_CANDIDATES = 50


def parse_args():
    parser = argparse.ArgumentParser(description="Run Spider_XHS keyword note collection")
    parser.add_argument("--repo", help="开发调试用：覆盖 skill 内置 runtime 路径")
    parser.add_argument("--users-excel")
    parser.add_argument("--task-name", required=True)
    parser.add_argument("--search-query", required=True)
    parser.add_argument("--keywords", required=True)
    parser.add_argument("--date-range", default="recent_7_days")
    parser.add_argument("--mode", choices=["both", "user", "search"], default="search")
    parser.add_argument("--max-search-candidates", type=int, default=DEFAULT_MAX_SEARCH_CANDIDATES)
    parser.add_argument(
        "--use-note-detail-api",
        action="store_true",
        help="开发排查用：允许调用易触发频控的帖子详情接口",
    )
    parser.add_argument("--output-dir", default="datas/batch_outputs")
    parser.add_argument(
        "--enrich-details",
        action="store_true",
        help="使用 Chrome CDP 为命中笔记导出 Markdown/JSONL 详情",
    )
    parser.add_argument(
        "--cdp-profile-dir",
        help="Chrome CDP 专用用户数据目录，默认使用 datas/cache/xhs-note-collector-chrome",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    repo = Path(args.repo).expanduser().resolve() if args.repo else find_repo()
    if not (repo / "spider" / "collect_notes.py").exists():
        raise SystemExit(f"未找到小红书采集运行时: {repo / 'spider' / 'collect_notes.py'}")
    ensure_environment(repo)
    users_excel = Path(args.users_excel) if args.users_excel else None
    if users_excel and not users_excel.exists():
        raise SystemExit(f"账号 Excel 不存在: {users_excel}")
    cmd = [
        sys.executable,
        "-m",
        "spider.collect_notes",
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
    if users_excel:
        cmd.extend(["--users-excel", str(users_excel)])
    if args.enrich_details:
        cmd.append("--enrich-details")
    if args.use_note_detail_api:
        cmd.append("--use-note-detail-api")
    if args.cdp_profile_dir:
        cmd.extend(["--cdp-profile-dir", args.cdp_profile_dir])
    completed = subprocess.run(cmd, cwd=str(repo), text=True)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
