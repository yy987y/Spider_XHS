# 验收与排查

## 基础验收

```bash
PYTHONPATH=. pytest -q
PYTHONPATH=. python -m spider.collect_notes --help
python /Users/yanchao03/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/xhs-note-collector
```

## 小批量试跑

```bash
python skills/xhs-note-collector/scripts/run_collection.py \
  --repo . \
  --users-excel tmp/users_smoke.xlsx \
  --task-name smoke \
  --search-query "艾薇岚 大超炮 北京" \
  --keywords "艾薇岚,大超炮,北京" \
  --date-range recent_7_days \
  --mode both \
  --max-search-candidates 20
```

## 必查日志事件

- `search_candidate_cap_reached`：公开搜索达到候选上限，标记可能未抓全。
- `user_resolve_failed`：小红书号解析失败。
- `api_error`：接口失败或 Cookie 失效。
- `before_date_range`：已翻到时间范围外。
