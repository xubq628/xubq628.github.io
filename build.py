#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Homepage 构建脚本（中英双语）
==============================
读取 data/ 下的 YAML 源文件，渲染 templates/ 中的模板，为每种语言生成一套页面：

    语言         About                Publications               CV
    英文(默认)   index.html           publications.html          cv.html
    中文         index.zh.html        publications.zh.html       cv.zh.html

中英对照的实现方式
------------------
英文写在各字段本身（如 role），中文写在同名 `_zh` 字段（如 role_zh）。
渲染中文页面时优先取 `_zh`，缺失则自动回退英文 —— 所以没有 `_zh` 的字段
中英共用（例如期刊名、审稿期刊），而且**新增内容只需维护一份结构**，
中英不会错位。模板代码对两种语言完全一致。

页面上所有固定文字（导航、标题、句式、页脚）集中在 data/ui.yml。

用法：
    python build.py

依赖：pyyaml, jinja2  （pip install pyyaml jinja2）
"""

import datetime
import pathlib
import sys

import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = pathlib.Path(__file__).resolve().parent

LANGS = ["en", "zh"]          # 顺序即优先级，第一个为默认语言
DEFAULT_LANG = LANGS[0]

# 页面清单：(模板名, 页面 ID, {语言: 输出文件名})
PAGES = [
    ("index.html", "about", {"en": "index.html", "zh": "index.zh.html"}),
    ("publications.html", "publications", {"en": "publications.html", "zh": "publications.zh.html"}),
    ("cv.html", "cv", {"en": "cv.html", "zh": "cv.zh.html"}),
]

# 发表列表分区：(数据键, ui.yml 中的标题键)
PUB_SECTIONS = [
    ("journal_articles", "pub_journal_articles"),
    ("conference_papers", "pub_conference_papers"),
    ("patents", "pub_patents"),
    ("software_copyrights", "pub_software_copyrights"),
]

SELF_NAMES = ("Xu, B.", "Xu, B,")  # 自动加粗的本人署名写法


def load_yaml(name):
    with open(ROOT / "data" / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def localize(obj, lang):
    """
    生成指定语言的数据视图。

    对每个字典键 `k`，若存在 `k_<lang>` 且不是默认语言，则取其值；否则沿用 `k`。
    `_<lang>` 覆盖字段本身不会出现在结果里。
    始终返回新的容器，因此不会污染原始数据（默认语言也不例外）。
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k.endswith(f"_{lang}"):
                continue
            override = f"{k}_{lang}"
            if lang != DEFAULT_LANG and override in obj:
                out[k] = localize(obj[override], lang)
            else:
                out[k] = localize(v, lang)
        return out
    if isinstance(obj, list):
        return [localize(item, lang) for item in obj]
    return obj


def audit(data, path="", issues=None):
    """
    静态检查中英对应关系，早于页面暴露问题：
      - 有 `xxx_zh` 却没有 `xxx` 作为英文基准；
      - `xxx` 与 `xxx_zh` 都是列表但长度不同（会导致中文页条目错位）。
    """
    if issues is None:
        issues = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key.endswith("_zh"):
                base = key[:-3]
                if base not in data:
                    issues.append(f"{path}{base}: 存在 `{key}` 但缺少 `{base}` 英文基准")
                elif isinstance(data[base], list) and isinstance(value, list) \
                        and len(data[base]) != len(value):
                    issues.append(
                        f"{path}{base}: 中英条目数不一致"
                        f"（en {len(data[base])} 条 vs zh {len(value)} 条），中文页会错位"
                    )
            else:
                audit(value, f"{path}{key}.", issues)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            audit(item, f"{path}[{i}].", issues)
    return issues


def bold_self(authors: str) -> str:
    """将作者列表中的本人署名加粗。"""
    for name in SELF_NAMES:
        if name in authors:
            return authors.replace(name, f"<strong>{name}</strong>")
    return authors


def scholar_citation_url(user: str, cid: str) -> str:
    return (
        "https://scholar.google.com/citations?view_op=view_citation"
        f"&hl=en&user={user}&citation_for_view={user}:{cid}"
    )


def process_pubs(pubs: dict, scholar_user: str, ui: dict) -> list:
    """为每条记录预计算 authors_html 与 url，并按分区打包（标题取 ui 文案）。"""
    sections = []
    for key, ui_key in PUB_SECTIONS:
        entries = []
        for p in pubs.get(key) or []:
            p = dict(p)
            p["authors_html"] = bold_self(p.get("authors", ""))
            if p.get("link"):
                p["url"] = p["link"]
            elif p.get("scholar_id"):
                p["url"] = scholar_citation_url(scholar_user, p["scholar_id"])
            else:
                p["url"] = None
            entries.append(p)
        sections.append({"title": ui[ui_key], "entries": entries})
    return sections


def main():
    profile_raw = load_yaml("profile.yml")
    pubs_raw = load_yaml("publications.yml")
    ui_all = load_yaml("ui.yml")

    issues = audit(profile_raw) + audit(pubs_raw)
    for msg in issues:
        print(f"[警告] 中英不对应 —— {msg}")
    if issues:
        print()

    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates")),
        autoescape=False,  # 数据为本地可信 YAML 内容，允许内嵌 HTML
    )
    year = datetime.date.today().year

    for tpl_name, page_id, out_files in PAGES:
        tpl = env.get_template(tpl_name)

        for lang in LANGS:
            ui = ui_all[lang]
            profile = localize(profile_raw, lang)

            # 侧栏 / 页脚用到的完整 Scholar 主页地址
            scholar_profile_url = (
                f"https://scholar.google.com/citations?user={profile_raw['scholar_user']}&hl=en"
            )

            # 审稿期刊渲染为斜体（在本地化之后计算，故取的是该语言视图）
            reviewer = profile.get("service", {}).get("reviewer", [])
            profile["service"]["reviewer_html"] = ", ".join(f"<em>{j}</em>" for j in reviewer)

            # 导航：指向同一语言下的页面
            nav = [
                {"id": pid, "file": files[lang], "label": ui_all[lang][f"nav_{pid}"]}
                for _, pid, files in PAGES
            ]

            # 语言切换目标：同一页面在另一种语言下的文件名
            other_lang = next(l for l in LANGS if l != lang)

            context = {
                "profile": profile,
                "ui": ui,
                "lang": lang,
                "nav": nav,
                "page_id": page_id,
                "page_title": ui[f"nav_{page_id}"],
                "alt_url": out_files[other_lang],
                "scholar_profile_url": scholar_profile_url,
                "pub_sections": process_pubs(
                    localize(pubs_raw, lang), profile_raw["scholar_user"], ui
                ),
                "year": year,
            }

            html = tpl.render(**context)
            out_path = ROOT / out_files[lang]
            # 显式写 LF：write_text 在 Windows 上会把 \n 转成 \r\n，
            # 与 data/ 源文件的 LF 不一致，且不利于跨平台复现。
            out_path.write_bytes(html.replace("\r\n", "\n").encode("utf-8"))
            print(f"[OK] {out_files[lang]}  ({lang})")

    print(f"\n构建完成，共 {len(PAGES) * len(LANGS)} 个页面"
          f"（{len(PAGES)} 页 × {len(LANGS)} 语言）。")
    print("修改 data/*.yml 后重新运行本脚本即可更新页面。")


if __name__ == "__main__":
    sys.exit(main())
