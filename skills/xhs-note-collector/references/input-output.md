# 输入输出

## 输入

当前 Skill 默认只需要用户用自然语言说清：

- 小红书搜索词
- 时间范围，例如近 7 天
- 可选：看板关键词和最多检查候选数；默认最多检查 50 条搜索候选

Agent 会把这些信息传给网页向导并自动打开浏览器。用户不需要手工复制 Cookie、打开开发者工具或执行命令；没有 Cookie 时页面会自动展示小红书二维码，用户扫码确认后自动保存 Cookie 并继续采集。详情补全阶段会使用 skill 专用 Chrome profile 打开笔记页面并通过 CDP 读取内容。

真实分发场景只发送 `xhs-note-collector/` skill 文件夹即可。脚本默认使用 `runtime/` 下内置的 Spider_XHS 必要运行子集，不依赖外部完整仓库。

## 关键词

- `search_query` 是完整平台搜索词，例如 `艾薇岚 大超炮 北京`。
- `keywords` 是看板关键词，英文逗号分隔，例如 `艾薇岚,大超炮,北京`。

## Excel 输出

- `命中帖子汇总`：按 `note_id` 去重。
- `按关键词展开明细`：同一帖子命中多个关键词时可出现多行。
- `采集统计`：记录通道、候选数、命中数、去重数。
- `异常与边界日志`：记录接口失败、候选上限和疑似未抓全。

## HTML 输出

静态笔记看板由导出的 XLSX 和详情索引生成，不改动原始 XLSX。看板默认是列表视图，支持按点赞、评论、转发、收藏排序；如果对应笔记已成功导出 Markdown，会展示“打开正文”入口。

## 详情输出

- `小红书详情_<任务名>_<时间>_md/`：每篇成功补全的笔记一个 Markdown。
- `小红书详情_<任务名>_<时间>.details.jsonl`：每篇笔记的 CDP 抽取状态、耗时、内容统计和错误信息。
- `小红书详情_<任务名>_<时间>.details.summary.json`：本次详情补全总数、成功数、失败数、平均耗时和 Markdown 目录。

详情失败不阻断整体导出；失败原因会写入 details JSONL 和 summary。

## 核心字段

`note_id`、`note_url`、`cover_url`、`title`、`author_nickname`、`author_user_id`、`publish_time_text`、`note_type`、`liked_count`、`collected_count`、`comment_count`、`share_count`、`detail_status`、`matched_keywords`、`sources`、`search_query`、`crawl_time`。

Markdown 详情包含：标题、笔记 ID、页面 URL、类型、作者、发布时间、IP 属地、标签、互动信息、正文、图片和前 20 条评论。
