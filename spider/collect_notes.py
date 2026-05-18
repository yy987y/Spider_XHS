import argparse

from apis.xhs_pc_apis import XHS_Apis
from spider.batch_account_resolver import read_red_ids_from_excel
from spider.batch_collector import BatchNoteCollector
from spider.batch_models import CollectTaskConfig
from spider.batch_report import build_keyword_rows, write_outputs
from spider.batch_time import parse_date_range
from xhs_utils.common_util import init


def parse_args():
    parser = argparse.ArgumentParser(description="小红书双通道帖子采集")
    parser.add_argument("--users-excel", required=True, help="包含 red_id 列的账号 Excel")
    parser.add_argument("--task-name", required=True, help="输出文件任务名")
    parser.add_argument("--search-query", required=True, help="小红书平台完整搜索词")
    parser.add_argument("--keywords", required=True, help="看板关键词，使用英文逗号分隔")
    parser.add_argument(
        "--date-range",
        default="recent_7_days",
        help="recent_7_days/recent_30_days/YYYY-MM-DD:YYYY-MM-DD",
    )
    parser.add_argument("--mode", choices=["both", "user", "search"], default="both")
    parser.add_argument("--max-search-candidates", type=int, default=1000)
    parser.add_argument("--output-dir", default="datas/batch_outputs")
    return parser.parse_args()


def main():
    args = parse_args()
    cookies_str, _ = init()
    if not cookies_str:
        raise RuntimeError(".env 中缺少 COOKIES")
    red_ids = read_red_ids_from_excel(args.users_excel)
    keywords = [item.strip() for item in args.keywords.split(",") if item.strip()]
    config = CollectTaskConfig(
        task_name=args.task_name,
        user_excel_path=args.users_excel,
        search_query=args.search_query,
        board_keywords=keywords,
        date_range=parse_date_range(args.date_range),
        run_user_channel=args.mode in ("both", "user"),
        run_search_channel=args.mode in ("both", "search"),
        max_search_candidates=args.max_search_candidates,
        output_dir=args.output_dir,
    )
    collector = BatchNoteCollector(api=XHS_Apis(), cookies_str=cookies_str, config=config)
    result = collector.collect(red_ids=red_ids)
    outputs = write_outputs(
        notes=result.notes,
        keyword_rows=build_keyword_rows(result.notes),
        stats_rows=result.stats_rows,
        events=result.events,
        output_dir=config.output_dir,
        task_name=config.task_name,
    )
    print(f"Excel: {outputs['xlsx']}")
    print(f"JSONL: {outputs['jsonl']}")
    print(f"Logs: {outputs['log_jsonl']}")


if __name__ == "__main__":
    main()
