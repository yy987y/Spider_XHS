# 输入输出

## 输入 Excel

必须包含 `red_id` 列，一行一个小红书号。

## 关键词

- `search_query` 是完整平台搜索词，例如 `艾薇岚 大超炮 北京`。
- `keywords` 是看板关键词，英文逗号分隔，例如 `艾薇岚,大超炮,北京`。

## Excel 输出

- `命中帖子汇总`：按 `note_id` 去重。
- `按关键词展开明细`：同一帖子命中多个关键词时可出现多行。
- `采集统计`：记录通道、候选数、命中数、去重数。
- `异常与边界日志`：记录账号解析失败、接口失败、候选上限和疑似未抓全。

## 核心字段

`note_id`、`note_url`、`cover_url`、`title`、`desc`、`tags`、`author_nickname`、`author_user_id`、`red_id`、`publish_time`、`liked_count`、`collected_count`、`comment_count`、`share_count`、`matched_keywords`、`matched_in_title`、`matched_in_desc`、`matched_in_tags`、`sources`、`search_query`、`crawl_time`。
