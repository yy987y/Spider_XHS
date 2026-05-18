import json
from pathlib import Path
from typing import Dict, List, Optional

import openpyxl

from spider.batch_models import ResolvedUser


def read_red_ids_from_excel(path: str) -> List[str]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(value).strip() if value is not None else "" for value in rows[0]]
        if "red_id" not in headers:
            raise ValueError("账号 Excel 必须包含 red_id 列")
        red_id_index = headers.index("red_id")
        red_ids = []
        for row in rows[1:]:
            value = row[red_id_index] if red_id_index < len(row) else None
            red_id = str(value).strip() if value is not None else ""
            if red_id:
                red_ids.append(red_id)
        return red_ids
    finally:
        wb.close()


class AccountResolver:
    def __init__(self, api, cookies_str: str, cache_path: str, proxies=None):
        self.api = api
        self.cookies_str = cookies_str
        self.cache_path = Path(cache_path)
        self.proxies = proxies
        self._cache = self._load_cache()

    def _load_cache(self) -> Dict[str, ResolvedUser]:
        cache = {}
        if not self.cache_path.exists():
            return cache
        for line in self.cache_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                cache[item["red_id"]] = ResolvedUser(
                    red_id=item["red_id"],
                    user_id=item["user_id"],
                    user_url=item["user_url"],
                    nickname=item.get("nickname", ""),
                    source="cache",
                    raw_summary=item.get("raw_summary", {}),
                )
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        return cache

    def _append_cache(self, resolved: ResolvedUser) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "red_id": resolved.red_id,
            "user_id": resolved.user_id,
            "user_url": resolved.user_url,
            "nickname": resolved.nickname,
            "raw_summary": resolved.raw_summary,
        }
        with self.cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def resolve(self, red_id: str) -> ResolvedUser:
        if red_id in self._cache:
            return self._cache[red_id]
        success, msg, users = self.api.search_some_user(red_id, 10, self.cookies_str, self.proxies)
        if not success:
            raise RuntimeError(f"小红书号解析失败: {red_id}, msg={msg}")
        exact = self._pick_exact_user(red_id, users)
        if not exact:
            raise RuntimeError(f"未找到匹配小红书号: {red_id}")
        user_info = exact.get("user_info", exact)
        user_id = user_info["user_id"]
        resolved = ResolvedUser(
            red_id=red_id,
            user_id=user_id,
            user_url=f"https://www.xiaohongshu.com/user/profile/{user_id}",
            nickname=user_info.get("nickname", ""),
            source="api",
            raw_summary={"matched_user": user_info},
        )
        self._append_cache(resolved)
        self._cache[red_id] = resolved
        return resolved

    @staticmethod
    def _pick_exact_user(red_id: str, users: list) -> Optional[dict]:
        for user in users:
            user_info = user.get("user_info", user)
            if str(user_info.get("red_id", "")).strip() == red_id:
                return user
        return None
