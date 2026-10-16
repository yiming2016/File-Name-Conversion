# 文件名翻译器 — 项目交接文档

**生成时间**：2026-10-17 ｜ **当前版本**：v2.1

**项目路径**：`C:\software\文件名翻译\`

**GitHub**：https://github.com/yiming2016/File-Name-Conversion （源码仓库，main 分支）

**发行版**：https://github.com/yiming2016/File-Name-Conversion/releases/tag/v2.1 （附件 `File-Name-Translator-v2.1.zip`，17.66 MB）

---

## 1. 项目目标

批量把文件名翻译成目标语言（默认外文→中文）的 Windows 桌面小工具：用户选文件夹/文件 → 逐条预览翻译结果 → 勾选、手工修正 → 一键批量重命名，并可撤销。

## 2. 技术栈与架构

**技术栈**

- 语言：Python 3.8+（实测 3.11）；全中文注释与文档
- GUI：tkinter / ttk（纯标准库 + 大量自绘控件，无第三方 UI 框架）
- 依赖（`requirements.txt`）：`requests>=2.28`、`PySocks>=1.7.1`、`Pillow>=10.0`
- 打包：PyInstaller 6.x，`--onefile --windowed`，spec 文件 `源码\文件名翻译器.spec`，一键脚本 `源码\build_exe.bat`

**目录结构（真实路径）**

```
C:\software\文件名翻译\
├─ 源码\                         ← git 仓库（源码，推送 GitHub）
│  ├─ main.py                   14 行  入口，支持 python main.py --selftest
│  ├─ app\
│  │  ├─ config.py             309 行  默认配置/语言表/AI 预设/知名词库清单/配置读写
│  │  ├─ core.py               259 行  文件发现、重命名规划、执行与撤销
│  │  ├─ engines.py            848 行  11 类翻译引擎、代理识别、模型列表/余额查询
│  │  ├─ glossary.py           509 行  词库：手动词条 CSV、目录扫描、6 种格式解析、占位符保护
│  │  ├─ gui.py               4777 行  全部界面与交互（自绘控件集中在此）
│  │  ├─ ipinfo.py              64 行  IP 位置/类型/风控查询
│  │  └─ selftest.py           315 行  86 项离线自测
│  ├─ 词库\                     默认词库.csv + tsv/tbx/tmx/json/csv/txt 六个格式子目录
│  ├─ docs\                     README 用的界面截图
│  ├─ logo.ico / logo.png / app\github.png   图标资源（同时已内嵌进 exe）
│  ├─ build_exe.bat             一键打包（输出到 ..\软件）
│  ├─ README.md / 使用说明.md / requirements.txt / .gitignore
│  └─ config.json               ⚠ 含 API Key，已被 .gitignore 排除，不入库
├─ 软件\                         ← 发布态目录（干净，只放运行所需）
│  ├─ 文件名翻译器.exe          19.0 MB（图标资源已内嵌）
│  ├─ 词库\  ├─ 使用说明.md  ├─ LICENSE  └─ config.json（首次运行自动生成）
└─ 文件名翻译器-v2.1.zip        发行版压缩包（已排除 config.json）
```

**核心数据流**

```
选文件夹/文件 → 任务队列(_tasks)
   → core.build_plan()：逐文件调用引擎翻译（词库先做占位符保护→翻译→还原）→ post_filter 过滤 → 生成 new_path
   → 翻译框预览：勾选 / 双击改新名（manual_edit）/ 移除队列
   → core.apply_plan()：两阶段重命名（先改临时名，再改最终名，避免互相冲突）+ 写"重命名记录.log"
   → core.undo_plan()：倒序改回
```

**配置机制**：`config.json` 与程序同目录；目录不可写时自动退回 `C:\Users\<用户>\.文件名翻译器_config.json`。配置文件不存在时使用内置默认值（已验证可正常启动并自动生成）。

## 3. 当前进度

**已完成（v2.1，全部可运行并已发布）**

- 翻译源 11 类：谷歌(免费)、DeepL、Yandex、百度、火山、小牛、腾讯云、**Bing(免费)**、**Papago**、**AI 模型（7 个预设独立块）**、**自定义 HTTP 源**
- AI 预设块：DeepSeek / OpenAI / 通义千问(阿里) / 智谱GLM / Moonshot(Kimi) / 本地 Ollama / 自定义；每块含获取 Key 链接、余额查询、接口地址、Key、模型名(+获取模型列表)、温度、系统提示词、测试翻译；**本地 Ollama 无余额查询，改为推荐模型链接（点击填入模型名并跳转下载页）**
- 语言设置：源语言**多选**、目标语言、**跳过语言**（多选，默认不选）、跳过已是目标语言的文件
- 自定义词库：手动词条（子串/整词/正则，支持 `\1`；译文=原文表示保留原名）+ 词库文件（txt/csv/tsv/json/tmx/tbx 六格式、三级树形、文件夹级联勾选、**知名词库弹窗**（内置 17 个词库链接，本地已存在显示绿色、双击打开本地文件夹））
- 界面：左设置右预览；任务队列（双击查看详情弹窗）；翻译框**逐列着色**（成功绿/失败红、手动改过的新名为绿、选中态高亮可读）；快捷键与撤销重做（Ctrl+Z/Y）；日志独立窗口
- 设置窗口：页签分两组（**常规** / **AI**），**竖排组名**，页签**长按拖动排序（限同行、实时吸附、顺序记忆）**，**改完即自动保存**，**“设为默认”**（同时固定默认页签与默认翻译源）
- 网络：代理 HTTP/SOCKS5 手动选择或自动识别；当前 IP/位置/类型/风控等级显示
- 打包：图标资源**内嵌 exe**（`--add-data` + `sys._MEIPASS`，文件夹优先回退）；发行版 v2.1 已发布

**进行中**：无

**待办 / 未验证**

- ⚠️ **除谷歌外的渠道未用真实 Key 联调**：Bing、Papago、各 AI 预设块、百度/火山/小牛/腾讯云的请求参数只做了代码实现，`selftest` 是**离线**自测（不联网）
- 源语言/跳过语言的检测：只有谷歌能返回真实检测结果；其他引擎用文字体系粗判（中文/日文/韩文/俄文/泰文/阿拉伯文等可判，**英文等纯字母语言判不出**）
- 使用说明文档尚未补充 v2.1 新增项（跳过语言、设为默认、页签拖动、AI 分块）——README 已写，`使用说明.md` 部分内容滞后

## 4. 关键决策与理由

| 决策 | 理由 |
|---|---|
| tkinter + 纯自绘控件，不引入 Qt/Web | 零额外运行库，单文件打包体积可控，用户环境无需装任何东西 |
| PyInstaller `--onefile`，显式 `--distpath "..\软件"` | 用户要求“打开即用”；显式指定输出目录，避免默认落到 `dist\` 让用户困惑 |
| 图标/图片**内嵌 exe**（`_MEIPASS`），文件夹里放同名单文件可覆盖 | 发布目录只剩 exe + 词库；同时保留“用户可自行替换图标”的能力 |
| 词库用**占位符保护**（原文→`KWSxxxxKWS`→云端翻译→还原） | 云端翻译不可控，这样专有名词/敏感词不会被乱翻；译文=原文即可实现“保留原名” |
| 翻译框**逐列着色**用透明 Label 覆盖 Treeview 单元格 | ttk.Treeview 的 tag 只能整行着色，无法“原文件名绿、新文件名黑”分列上色 |
| 覆盖标签自行实现点击语义（单击/ctrl/shift/框选/双击/右键转发） | 见第 5 节：生成的鼠标事件无法驱动原生选择 |
| 设置窗口**改完即存、无保存按钮** | 用户明确要求；且避免“忘记点保存” |
| “设为默认”同时写 `default_settings_tab` 与 `engine` | 用户预期：设为默认=软件启动时的默认翻译源，不只是记住页签 |
| 页签拖动**限制在同一行内** | 跨行拖动命中不精准，用户明确反馈“跨行不精准” |
| `config.json` 不入 git | 内含 API Key；软件能自动生成默认配置（已验证），不影响别人克隆使用 |
| 软件只走 **GitHub 发行版**，不把 exe 提交进仓库 | 源码仓库保持干净；发行版附件命名用 ASCII（GitHub 会过滤中文） |
| 词库目录按格式分子文件夹 + 默认内置两个 LDNOOBW 词库 | 用户明确要求，且开箱即用 |

## 5. 已尝试但失败的方案（踩坑清单，勿重复）

1. **ttk.Treeview 用 tag 整行着色** → 无法满足分列着色需求 → 改为覆盖 Label 方案
2. **`event_generate("<Button-1>")` 驱动 Treeview 原生选择** → 生成的鼠标事件不触发原生选中 → 自己实现单击/ctrl 多选/shift 范围/拖动框选
3. **`event_generate("<Double-1>")`** → 直接报错 `Double, Triple, or Quadruple modifier not allowed` → 改为直接调用处理函数
4. **`tree.identify("region", x, y)`** → 本机 Tk 8.6.12 上对文本列返回 `"nothing"`（曾导致双击改名失效）→ 改用 `identify_row()` + `identify_column()`
5. **`ttk.Label(..., bg=...)`** → `unknown option "-bg"`（ttk 走 style）→ 去掉 bg（样式已带背景色）
6. **跨行拖动排序** → 命中不精准 → 限同行 + 纵向吸附 + 实时吸附排序
7. **`ThumbScrollbar`（Canvas）未设高度** → 请求高度约 396px，把父容器撑爆、下方控件被挤没 → 显式 `height=10`
8. **左栏被右栏覆盖/按钮被裁** → 自绘控件请求尺寸过大 → `left.pack_propagate(False)` + 固定宽度 + 长提示文字改单行
9. **“保存设置”按钮在“管理翻译源”窗口崩溃**（该窗口没有词库页的 `g_case_var`）→ 删除保存按钮改自动保存，顺带修掉
10. **词库 `active_count` 把编译失败的正则也算作“生效”** → 改为统计实际可用词条
11. **重新选文件夹不刷新文件列表**（出现“新文件夹路径+旧文件列表”）→ 改为始终按新文件夹重扫
12. **把 exe/图片散落进发布目录** → 精简为 exe + 词库（图片内嵌）
13. **GitHub 附件名用中文** → 被过滤成 `-v2.1.zip` → 用 ASCII：`File-Name-Translator-v2.1.zip`
14. **git 推送走本机代理失败**（`127.0.0.1:10808` 握手超时）→ 直连推送 `git -c http.proxy= -c https.proxy= push`；Python 请求用 `session.trust_env = False`
15. **`.git/config` 里残留明文令牌**（多余的 `puttykeyfile` 字段）→ 已 `git config --unset` 删除；**令牌不要落盘、不要提交、不要打印**
16. **PowerShell 管道传中文给 Python 会乱码**（`python -` 按控制台编码转坏中文字面量）→ 用环境变量传中文路径/文件名，脚本里只用 ASCII 或 `\uXXXX` 转义
17. **打包产物污染源码目录** → 每次打包后清理 `源码\build\` 与 `app\__pycache__\`（已在 .gitignore 中，但仍应清掉）

## 6. 重要代码约定与偏好

- **语言与文案**：注释/docstring 全中文；面向小白用户，报错必须**白话**——统一走 `gui.py::plain_error()`（把 429/超时/连接失败/401 等转成“翻译源限流，请稍后重试”“网络连接失败，请检查代理或网络设置”）。翻译框失败行的“新文件名”列显示白话原因，不显示堆栈
- **自绘控件**（都在 `gui.py`）：`RoundedButton`（圆角按钮，`style="gray/blue/green/orange/red"`）、`ThumbScrollbar`（自绘可见滑块滚动条，**必须显式设 height**）、`StatusNotebook`（可变色页签 + 分组 + 竖排组名 + 长按拖动排序）、`RowList`（文件/任务列表框）、`PlayPauseButton`（▶/■ 播放器按钮）、`center_window()`（弹窗一律屏幕居中）
- **版本号**：`app/gui.py` 顶部 `APP_VERSION = "2.1"`，右下角显示 `v{APP_VERSION}`；升版本只改这一处
- **颜色常量**：`gui.py` 顶部集中定义（`APP_BG`/`PRIMARY`/`TAB_BG_*`/`TITLE_COLORS`(5 级标题色)/`TITLE_FONTS`/`TREE_FG_OK`/`TREE_FG_ERROR`/`TREE_FG_MANUAL`）
- **引擎 key 约定**：内置用 `google/deepl/yandex/baidu/volcengine/niutrans/tencent/bing/papago`；**AI 渠道用 `ai:<预设名>`**（如 `ai:DeepSeek`，预设名必须与 `config.AI_PRESETS` 的键一致）；自定义源用其名称。`config["engine"]` 存的就是这些 key
- **`build_plan` 的 `post_filter` 约定**：返回 `True`=保留；`False`=按默认原因跳过（“源语言不在所选范围，跳过”）；**返回字符串=按该字符串作为原因跳过**（“跳过语言”功能就是用它实现）
- **配置字段**：`source_langs`(列表)、`skip_langs`(列表)、`skip_target`、`target_lang`、`engine`、`proxy`/`proxy_type`、`timeout`、各渠道密钥、`ai.providers{预设名:{base_url,api_key,model,temperature,system_prompt}}` + `ai.current`、`glossary{enabled,case_sensitive,files}`、`window_size`、`default_settings_tab`、`settings_tab_order{group0,group1}`。新增字段必须同时补进 `config.default_config()`，旧配置缺字段靠 `load_config()` 的逐层合并兜底
- **每次改完必跑**：`python main.py --selftest`（86 项，必须全部 PASS）；构建 exe 走 `build_exe.bat`
- **提交纪律**：`config.json`、`build/`、`__pycache__/`、日志一律不入库（.gitignore）；改完 UI 建议截图核对（识图接口额度可能耗尽，可退回程序化断言：直接调用方法、检查控件几何与变量值）

## 7. 下一步行动（按优先级）

1. **真机联调新增渠道**：用真实 Key 依次验证 Bing、Papago、AI 各预设块（DeepSeek/OpenAI/通义千问/智谱/Kimi/Ollama）与百度/火山/小牛/腾讯云——确认端点、语言代码映射（如 Bing 用 `zh-Hans`、Papago 用 `zh-CN`）、错误提示是否符合预期。目前这些只有离线自测覆盖
2. **固化发布流程**：把“跑 selftest → build_exe.bat → 清理 build/__pycache__ → 打包 zip（排除 config.json）→ 打 tag + 上传发行版附件（ASCII 命名）”写成一个脚本，避免每次手工操作；同时把 `使用说明.md` 补齐 v2.1 新增功能（跳过语言、设为默认、页签拖动、AI 分块、图标已内嵌）
3. **补 GUI 层冒烟测试**：给 `selftest.py` 增加界面级检查（打开设置窗口、切换全部页签、拖动排序、管理词库弹窗、知名词库弹窗），把本轮多次“界面能用但细节出错”的问题挡在发布前
