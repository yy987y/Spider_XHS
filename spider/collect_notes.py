import argparse
from typing import Optional

from apis.xhs_pc_apis import XHS_Apis
from spider.batch_account_resolver import read_red_ids_from_excel
from spider.batch_collector import BatchNoteCollector
from spider.batch_models import CollectTaskConfig
from spider.batch_report import build_keyword_rows, write_outputs
from spider.batch_time import parse_date_range
from spider.cdp_note_exporter import export_note_details
from xhs_utils.common_util import init

DEFAULT_MAX_SEARCH_CANDIDATES = 50


def _search_note_time_choice(date_range_value: str) -> int:
    normalized = (date_range_value or "").strip()
    if normalized in ("", "recent_7_days", "近7天"):
        return 2
    if normalized in ("recent_30_days", "近30天"):
        return 3
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="小红书关键词笔记采集")
    parser.add_argument("--users-excel", help="可选。包含 red_id 列的账号 Excel")
    parser.add_argument("--task-name", required=True, help="输出文件任务名")
    parser.add_argument("--search-query", required=True, help="小红书平台完整搜索词")
    parser.add_argument("--keywords", required=True, help="看板关键词，使用英文逗号分隔")
    parser.add_argument(
        "--date-range",
        default="recent_7_days",
        help="recent_7_days/recent_30_days/YYYY-MM-DD:YYYY-MM-DD",
    )
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


def run_collection(
    *,
    task_name: str,
    search_query: str,
    keywords,
    date_range_value: str = "recent_7_days",
    max_search_candidates: int = DEFAULT_MAX_SEARCH_CANDIDATES,
    output_dir: str = "datas/batch_outputs",
    users_excel: Optional[str] = None,
    mode: str = "search",
    cookies_str: Optional[str] = None,
    enrich_details: bool = False,
    use_note_detail_api: bool = False,
    cdp_profile_dir: Optional[str] = None,
    cdp_client=None,
):
    cookies_str = cookies_str or init()[0]
    if isinstance(keywords, str):
        keywords = [item.strip() for item in keywords.split(",") if item.strip()]
    else:
        keywords = [str(item).strip() for item in keywords if str(item).strip()]
    if not cookies_str:
        raise RuntimeError(".env 中缺少 COOKIES")
    if mode in ("both", "user") and not users_excel:
        raise RuntimeError("指定用户通道需要 --users-excel")
    red_ids = read_red_ids_from_excel(users_excel) if users_excel else []
    config = CollectTaskConfig(
        task_name=task_name,
        user_excel_path=users_excel or "",
        search_query=search_query,
        board_keywords=keywords,
        date_range=parse_date_range(date_range_value),
        run_user_channel=mode in ("both", "user"),
        run_search_channel=mode in ("both", "search"),
        use_note_detail_api=use_note_detail_api,
        max_search_candidates=max_search_candidates,
        search_note_time_choice=_search_note_time_choice(date_range_value),
        output_dir=output_dir,
    )
    collector = BatchNoteCollector(api=XHS_Apis(), cookies_str=cookies_str, config=config)
    result = collector.collect(red_ids=red_ids)
    detail_outputs = None
    if enrich_details and result.notes:
        detail_outputs = export_note_details(
            notes=result.notes,
            output_dir=config.output_dir,
            task_name=config.task_name,
            cdp_profile_dir=cdp_profile_dir or "datas/cache/xhs-note-collector-chrome",
            cookies_str=cookies_str,
            cdp_client=cdp_client,
        )
    outputs = write_outputs(
        notes=result.notes,
        keyword_rows=build_keyword_rows(result.notes),
        stats_rows=result.stats_rows,
        events=result.events,
        output_dir=config.output_dir,
        task_name=config.task_name,
        detail_index=(detail_outputs or {}).get("detail_index"),
    )
    if detail_outputs:
        outputs.update(
            {
                "details_dir": detail_outputs["md_dir"],
                "detail_jsonl": detail_outputs["jsonl"],
                "detail_summary": detail_outputs["summary"],
            }
        )
    return outputs


def main():
    args = parse_args()
    outputs = run_collection(
        task_name=args.task_name,
        search_query=args.search_query,
        keywords=args.keywords,
        date_range_value=args.date_range,
        max_search_candidates=args.max_search_candidates,
        output_dir=args.output_dir,
        users_excel=args.users_excel,
        mode=args.mode,
        enrich_details=args.enrich_details,
        use_note_detail_api=args.use_note_detail_api,
        cdp_profile_dir=args.cdp_profile_dir,
    )
    print(f"Excel: {outputs['xlsx']}")
    print(f"HTML: {outputs['html']}")
    print(f"JSONL: {outputs['jsonl']}")
    print(f"Logs: {outputs['log_jsonl']}")
    if outputs.get("details_dir"):
        print(f"Details Markdown: {outputs['details_dir']}")
        print(f"Details JSONL: {outputs['detail_jsonl']}")
        print(f"Details Summary: {outputs['detail_summary']}")


if __name__ == "__main__":
    main()
