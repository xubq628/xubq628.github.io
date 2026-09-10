#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
引用统计自动更新脚本
====================
从 Google Scholar 个人主页抓取引用数 / h-index，回写到 data/profile.yml。
同时刷新 `stats_as_of`（英文月份）与 `stats_as_of_zh`（中文月份），
以配合主页的中英双语版本。

用法：
    python update_stats.py              # 抓取并写入（仅在数值变化时写）
    python update_stats.py --dry-run    # 只打印，不修改文件
    python update_stats.py --check      # 只校验能否抓取，成功/失败由退出码表示

实现说明：
    Google Scholar 没有官方 API，本脚本模拟浏览器请求其公开主页，
    从两处冗余解析（meta description 的 "Cited by N"，以及 gsc_rsb_std 统计表），
    二者互为校验，不一致则以统计表为准并给出警告。

    ⚠️ 请勿高频运行（建议每天最多一次）。高频请求会触发验证码或临时封禁。
    抓取失败时脚本以非零退出码结束，且**不改动任何文件**，
    因此可以安全地放进定期任务里，不会因为一次失败就破坏页面。

之所以不改用 build.py 直接在线抓取：构建应当是离线、确定性的，
网络抖动不应导致构建失败或产出不同结果。
"""

import argparse
import datetime
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
PROFILE = ROOT / "data" / "profile.yml"

SCHOLAR_BASE = "https://scholar.google.com/citations"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def load_profile() -> tuple:
    """
    读取 profile.yml，返回 (内部统一用 \\n 的文本, 原始换行符)。
    必须先读字节再自行解码，不能用 read_text —— 后者会做换行符转换，
    写回时又会按平台把 \\n 变成 \\r\\n（Windows），导致整文件 diff 全变。
    """
    raw = PROFILE.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    return text, nl


def save_profile(text: str, nl: str) -> None:
    """按原始换行符写回，保证只有真正改动的行体现在 diff 中。"""
    data = text.replace("\n", nl).encode("utf-8")
    PROFILE.write_bytes(data)


def read_scholar_user() -> str:
    """从 profile.yml 读取 scholar_user，避免把 ID 写死两处。"""
    text, _ = load_profile()
    m = re.search(r"^scholar_user:\s*([A-Za-z0-9_\-]+)\s*$", text, re.MULTILINE)
    if not m:
        raise SystemExit("错误：profile.yml 中找不到 scholar_user。")
    return m.group(1)


def fetch_profile(user: str, retries: int = 3, timeout: int = 30) -> str:
    """抓取 Scholar 主页 HTML，失败时指数退避重试。"""
    url = f"{SCHOLAR_BASE}?hl=en&user={user}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            return raw.decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            last_err = e
            if attempt < retries:
                wait = 2 ** attempt  # 2, 4 秒
                print(f"  第 {attempt} 次请求失败（{e}），{wait}s 后重试…")
                time.sleep(wait)
    raise SystemExit(f"错误：多次抓取 Scholar 主页均失败：{last_err}")


def parse_stats(html: str) -> dict:
    """解析引用数、h-index、i10。返回 dict。"""
    if re.search(r"(not a robot|unusual traffic|/sorry/)", html, re.IGNORECASE):
        raise SystemExit(
            "错误：Google 返回了验证码 / 流量异常页面。\n"
            "      通常意味着请求过于频繁或当前 IP 被临时限制。\n"
            "      请稍后（数小时）再试，或降低更新频率。"
        )

    # 主来源：gsc_rsb_std 统计表，6 个单元格依次为
    # 引用(全部) 引用(近5年) h(全部) h(近5年) i10(全部) i10(近5年)
    cells = re.findall(r'gsc_rsb_std">(?:<[^>]*>)*?(\d+)', html)
    if len(cells) < 6:
        raise SystemExit(
            "错误：无法从 Scholar 页面解析出统计表（页面结构可能已变更，"
            f"或该主页未公开引用数）。实际解析到 {len(cells)} 个单元格。"
        )

    stats = {
        "citations": int(cells[0]),
        "h_index": int(cells[2]),
        "i10_index": int(cells[4]),
    }

    # 交叉校验：meta description 里也有 "Cited by N"
    m = re.search(r"Cited by (\d+)", html)
    if m and int(m.group(1)) != stats["citations"]:
        print(
            f"  警告：meta 描述显示 Cited by {m.group(1)}，"
            f"统计表显示 {stats['citations']}，二者不一致，以统计表为准。"
        )
    return stats


def patch_profile_yaml(text: str, updates: dict, insert_after: dict = None) -> str:
    """
    以正则替换的方式改写 YAML 中已存在的标量字段，
    而不是 yaml.load + dump —— 后者会丢掉全部注释和原有排版。

    找不到字段时：
      - 若 insert_after 给出了锚点字段，则插入到锚点行之后（用于新增字段）；
      - 否则报错退出，避免静默生成一个游离的重复键。
    """
    for key, value in updates.items():
        pattern = re.compile(rf"^({re.escape(key)}:\s*)(.*)$", re.MULTILINE)
        if pattern.search(text):
            text = pattern.sub(lambda m: f"{m.group(1)}{value}", text, count=1)
            continue

        anchor_key = (insert_after or {}).get(key)
        if anchor_key:
            anchor = re.search(rf"^{re.escape(anchor_key)}:\s*.*$", text, re.MULTILINE)
            if not anchor:
                raise SystemExit(
                    f"错误：profile.yml 中既没有 `{key}`，也找不到锚点 `{anchor_key}`，未做任何修改。"
                )
            text = text[:anchor.end()] + f"\n{key}: {value}" + text[anchor.end():]
            continue

        raise SystemExit(f"错误：profile.yml 中找不到字段 `{key}`，未做任何修改。")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description="从 Google Scholar 更新引用统计")
    ap.add_argument("--dry-run", action="store_true", help="只打印结果，不写文件")
    ap.add_argument("--check", action="store_true", help="只验证能否抓取，返回退出码")
    args = ap.parse_args()

    user = read_scholar_user()
    print(f"Google Scholar user = {user}")

    html = fetch_profile(user)
    stats = parse_stats(html)

    today = datetime.date.today()
    as_of = f"{MONTHS[today.month - 1]} {today.year}"
    as_of_zh = f"{today.year} 年 {today.month} 月"

    print(
        f"抓取结果：citations = {stats['citations']}, "
        f"h-index = {stats['h_index']}, i10-index = {stats['i10_index']}"
    )

    if args.check:
        print("校验通过：可以正常抓取。")
        return 0

    text, nl = load_profile()

    old_cit = re.search(r"^citations:\s*(\d+)", text, re.MULTILINE)
    old_h = re.search(r"^h_index:\s*(\d+)", text, re.MULTILINE)
    old_asof = re.search(r"^stats_as_of:\s*(.+)$", text, re.MULTILINE)
    old_asof_zh = re.search(r"^stats_as_of_zh:\s*(.+)$", text, re.MULTILINE)

    print(
        f"当前 profile.yml：citations = {old_cit.group(1) if old_cit else '?'}, "
        f"h-index = {old_h.group(1) if old_h else '?'}, "
        f"as of {old_asof.group(1).strip() if old_asof else '?'}"
    )

    unchanged = (
        old_cit
        and old_h
        and old_asof
        and old_asof_zh
        and int(old_cit.group(1)) == stats["citations"]
        and int(old_h.group(1)) == stats["h_index"]
        and old_asof.group(1).strip() == as_of
        and old_asof_zh.group(1).strip() == as_of_zh
    )
    if unchanged:
        print("无变化，无需写入。")
        return 0

    # stats_as_of_zh 若不存在会自动插入到 stats_as_of 之后，保持中英字段相邻
    new_text = patch_profile_yaml(
        text,
        {
            "citations": stats["citations"],
            "h_index": stats["h_index"],
            "stats_as_of": as_of,
            "stats_as_of_zh": as_of_zh,
        },
        insert_after={"stats_as_of_zh": "stats_as_of"},
    )

    if args.dry_run:
        print("\n[dry-run] 将要写入：")
        for key, val in (
            ("citations", stats["citations"]),
            ("h_index", stats["h_index"]),
            ("stats_as_of", as_of),
            ("stats_as_of_zh", as_of_zh),
        ):
            print(f"  {key}: {val}")
        print("[dry-run] 未修改文件。")
        return 0

    save_profile(new_text, nl)
    print(
        f"已更新 profile.yml：citations {old_cit.group(1)} → {stats['citations']}, "
        f"h-index {old_h.group(1)} → {stats['h_index']}, as of {as_of}"
    )
    print("请接着运行 build.py 重新生成页面。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
