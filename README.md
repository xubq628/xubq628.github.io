# 个人主页使用说明

基于 academicpages.github.io 风格的静态学术主页，**中英双语**、**数据驱动**：
所有内容来自 `data/` 下的 YAML 源文件，通过 `build.py` 自动生成 6 个 HTML 页面。

## 目录结构

```
homepage/
├── data/
│   ├── profile.yml          # 个人信息：简介、教育、项目、荣誉、学术服务、引用统计
│   ├── publications.yml     # 论文、会议、专利、软著
│   └── ui.yml               # 界面文案（导航、标题、句式、页脚、语言切换标签）
├── templates/               # Jinja2 模板（一般无需改动）
│   ├── base.html            # 公共框架：导航栏 + 侧栏 + 页脚
│   ├── index.html           # About 页
│   ├── publications.html    # Publications 页
│   └── cv.html              # CV 页
├── css/style.css            # 样式
├── images/profile.jpg       # 头像
├── files/CV_Boqiang_Xu.pdf  # CV 附件
├── build.py                 # 构建脚本
├── build.bat                # Windows 双击运行版
├── update_stats.py          # 从 Google Scholar 抓取引用数 / h-index
└── 生成的页面（勿手改）：
    ├── index.html           publications.html           cv.html            ← 英文（默认）
    └── index.zh.html        publications.zh.html        cv.zh.html         ← 中文
```

## 中英双语是怎么实现的

**英文写在各字段本身，中文写在同名 `_zh` 字段。**

```yaml
role: Postdoctoral Fellow
role_zh: 博士后研究员
```

渲染中文页面时优先取 `_zh`，缺失则自动回退英文。这样做的好处：

- **不用维护两份文件**，中英不可能错位（对比"两个平行文件"方案，改一处忘一处就会失调）；
- 没有 `_zh` 的字段天然中英共用，不需要翻译的东西（期刊名、审稿期刊列表）什么都不用写；
- 模板代码两种语言完全一致，加语言只需在 `build.py` 的 `LANGS` 里补一个代码。

页面上所有固定文字都集中在 `data/ui.yml`，按 `en` / `zh` 两组组织，带 `{xxx}` 的是占位符。

构建时会自动检查中英对应关系，发现下列问题会在终端打印 `[警告]`：

- 有 `xxx_zh` 却没有 `xxx` 英文基准；
- `xxx` 与 `xxx_zh` 都是列表但**长度不同**（这会让中文页条目错位）。

### 列表类字段怎么加中文

平行列表长度必须一致：

```yaml
honors:
  - Excellent Ph.D. Graduate, Tongji University, 2025
  - Silver Award, China International College Students' Innovation Competition, Ministry of Education, 2025
honors_zh:
  - 同济大学优秀博士毕业生，2025
  - 中国国际大学生创新大赛银奖，教育部，2025
```

字典条目则写在**同一个条目内**：

```yaml
education:
  - degree: Ph.D. in Civil Engineering (integrated master&ndash;doctoral program)
    degree_zh: 土木工程博士（硕博连读）
    school: Department of Bridge Engineering, Tongji University
    school_zh: 同济大学桥梁工程系
    period: 2021&ndash;2025            # 无 period_zh，中英共用
```

### 论文标题为什么是英文

`publications.yml` 里论文标题与期刊名**不翻译**，中英页面一律显示英文原文
（学术惯例，也便于检索与引用）。论文页的分区标题（期刊论文 / 会议论文 / 专利 / 软件著作权）
在 `ui.yml` 里，已经是中文。中文页会有一行说明提示这一点。

如需为某篇论文补中文标题，在 `publications.yml` 该条目内加 `title_zh` 即可。

## 日常更新流程

### 1. 发表新论文

打开 `data/publications.yml`，在对应分区（`journal_articles` / `conference_papers`）添加：

```yaml
  - authors: "Xu, B., Zhang, S."
    title: Your new paper title
    venue: Journal Name
    detail: "2026, 100: 123456"
    link: "https://doi.org/10.xxxx/xxxxx"   # 推荐：出版社 DOI
    scholar_id: AbCdEfGhIjK                 # 可选：Google Scholar 论文 ID
```

- `authors` 中的 `Xu, B.` 会**自动加粗**；
- 链接优先级 **`link` > `scholar_id`**，即页面跳 DOI 页；两个都留空则标题为纯文本；
- `scholar_id` 获取方法：打开论文的 Scholar 页面，URL 中 `citation_for_view=bW6bHowAAAAJ:` **冒号后**的部分；
- 专利/软著条目通常没有链接，只填 `authors` / `title` / `detail`。

### 2. 获得新奖励 / 新项目 / 学术服务

打开 `data/profile.yml`，在对应列表添加条目；**记得同步补 `_zh` 版本**（否则中文页会显示英文）：

- `honors:` / `honors_zh:` 荣誉奖励（平行列表，长度必须一致）
- `projects:` 科研项目（role / title / funder / period，各自的 `_zh`）
- `education:` 教育经历
- `service.guest_editor` 的 `topic` / `topic_zh`
- `about:` 简介、`research_interests:` 研究兴趣

### 3. 更新引用统计

**方式一：自动抓取（推荐）**

```bash
python update_stats.py            # 抓取并写入 citations / h_index / stats_as_of(_zh)
python update_stats.py --dry-run  # 只打印将要写入的值，不改文件
python update_stats.py --check    # 只验证能否抓取成功
```

抓取失败（网络异常、验证码、页面结构变更）时**以非零码退出且不改动任何文件**，
所以放进定期任务里是安全的。

> ⚠️ Google Scholar 没有官方 API，本脚本是模拟浏览器请求其公开主页。
> **请勿高频运行，建议每天最多一次**，否则可能触发验证码或临时限制当前 IP。

**方式二：手工修改** `profile.yml` 顶部：

```yaml
citations: 348
h_index: 9
stats_as_of: September 2026
stats_as_of_zh: 2026 年 9 月
```

### 4. 重新生成页面

```bash
python build.py
```

或直接**双击 `build.bat`**（使用已配置好的 Python 环境，含 pyyaml / jinja2 依赖）。
一次生成 6 个页面：3 个页面 × 2 种语言。

### 5. 本地预览

```bash
python -m http.server 8642
# 英文 http://127.0.0.1:8642/index.html
# 中文 http://127.0.0.1:8642/index.zh.html
```

### 6. 全自动更新（可选）

主页是纯静态站，没有后端，所以"自动更新"= **定时抓取 + 重建**：

```bash
python update_stats.py && python build.py
```

用 Windows「任务计划程序」把它设成每天定时执行，指向
`C:\Users\84170\.workbuddy\binaries\python\envs\default\Scripts\python.exe`，
起始于本目录。若已把站点托管到 GitHub Pages，再在末尾追加 `git commit && git push` 完成发布。

## 注意事项

- **不要直接编辑根目录的 6 个 HTML**——每次构建都会被覆盖，改 `data/` 和 `templates/` 才是源头；
- YAML 中冒号后需跟一个空格；含特殊字符（冒号、引号）的文本用双引号包裹；
- 支持 HTML 实体（如 `&ndash;`、`&rsquo;`）和内嵌 HTML（如 `<a href="...">`）；
- **新增页面**：在 `templates/` 加模板，在 `build.py` 的 `PAGES` 中登记（同时给出 `en` / `zh` 两个输出名），
  并在 `ui.yml` 两个语言组里补 `nav_<页面ID>` 与 `h1_<页面ID>`；
- **新增语言**（比如日后加繁体）：`ui.yml` 加一组、`profile.yml` 补 `_tw` 字段、
  `build.py` 的 `LANGS` 加一个代码即可，模板无需改动；
- 更换头像：替换 `images/profile.jpg`；更新 CV：替换 `files/CV_Boqiang_Xu.pdf` 后重新构建
  （CV 目前只有英文版，中文页会提示"目前仅提供英文版简历"）；
- 全仓库统一使用 LF 换行（`build.py` 与 `update_stats.py` 均显式写 LF）。若用 Word/WPS 之类工具直接编辑 `data/*.yml`，注意别被自动转成 CRLF，否则 diff 会显示整文件变更。
