# MediaDistill · 影音萃取

> 在本地把视频与音频整理成可检索、可复用的 Markdown 知识。

MediaDistill 是一个面向课程、演讲、播客和产品演示的本地影音分析工具。它将语音转写、场景检测、关键帧筛选、音画融合和知识提炼组织成一条可恢复的处理流水线，并提供深色网页工作台管理素材和结果。

项目采用 **local-first** 设计：素材、音频、转写和中间文件默认保留在自己的电脑上，网页服务也只监听 `127.0.0.1`。

## 它能做什么

- 批量导入 MOV、MP4、MKV、WebM、M4A、MP3、WAV、FLAC
- 使用 faster-whisper 在本地完成中文语音转写
- 根据时长自适应抽帧，并通过清晰度、信息量和相似度筛选画面
- 合并语音章节与视觉变化，生成音画时间线
- 用断点状态保存每一步，失败后可以从指定阶段继续
- 输出带 YAML 元数据的 Markdown 知识笔记
- 在网页中管理导入顺序、分组、多选和处理状态
- 在网页中预览并下载最终 Markdown

## 当前版本的边界

MediaDistill 目前是一个 **半自动本地工作流**：

- 音频提取、转写、场景检测、关键帧筛选和 Markdown 渲染由本地程序完成。
- 画面语义理解与知识提炼会生成 Agent 任务文件，需要 Cursor、Codex、Claude Code 等具备文件读写能力的 AI Agent 完成对应 JSON。
- 项目没有偷偷调用外部模型 API，也没有内置云端账号或密钥。

因此，在没有接入 AI Agent 的情况下，流水线可能停在“需要 AI 分析”。这不是程序崩溃，而是在等待语义分析结果。

## 工作流程

```mermaid
flowchart LR
    A[导入音视频] --> B[本地语音转写]
    B --> C[场景检测与关键帧]
    C --> D[画面语义分析]
    D --> E[音画融合]
    E --> F[知识提炼]
    F --> G[Markdown]
    G --> H[网页预览与下载]
```

视频流水线：

```text
Extract Audio → Speech → Scene Detection → Extract Frames
→ Vision → Multimodal → Knowledge → Markdown
```

音频流水线：

```text
Speech → Text Analysis → Knowledge → Markdown
```

## 安装要求与平台状态

- Python 3.10 或更高版本
- `ffmpeg` 与 `ffprobe`
- 首次下载 faster-whisper 模型时需要网络连接和足够磁盘空间

当前平台验证情况：

| 平台 | 状态 | 说明 |
| --- | --- | --- |
| macOS | 已验证 | 提供双击安装与启动脚本 |
| Linux | 预期可用 | 请使用终端安装，欢迎反馈发行版兼容性 |
| Windows 10/11 | 提供安装指导 | 提供双击脚本；尚待更多真机兼容性反馈 |

macOS 可以使用 Homebrew 安装 ffmpeg：

```bash
brew install ffmpeg
```

## 最简单的使用方式（macOS）

1. 下载或克隆项目。
2. 双击 `安装 MediaDistill.command`，等待依赖安装完成。
3. 双击 `启动 MediaDistill.command`。
4. 浏览器会打开 `http://127.0.0.1:8765/`。
5. 点击“批量导入”或把影音文件拖入页面。

关闭启动终端窗口，或在终端中按 `Control + C`，即可停止本地服务。

> macOS 第一次打开从互联网下载的 `.command` 文件时，可能需要右键文件，选择“打开”，再确认一次。

## 最简单的使用方式（Windows 10/11）

1. 在 GitHub 仓库页面点击 `Code → Download ZIP`，解压到一个固定目录；不要直接在 ZIP
   压缩包预览窗口中运行。
2. 安装 Python 3.10 或更高版本，以及包含 `ffmpeg`、`ffprobe` 的 ffmpeg 套件。
3. 双击 `安装 MediaDistill.bat`，等待依赖安装完成。
4. 双击 `启动 MediaDistill.bat`。
5. 浏览器会打开 `http://127.0.0.1:8765/`，然后即可批量导入素材。

在 Windows 10 1809 或更高版本、Windows 11 中，可以打开 PowerShell 并使用 WinGet 安装
前置依赖：

```powershell
winget install -e --id Python.Python.3.13
winget install -e --id Gyan.FFmpeg
```

安装后请关闭并重新打开 PowerShell，再确认：

```powershell
python --version
ffmpeg -version
ffprobe -version
```

如果电脑没有 `winget`，可通过 Microsoft Store 安装或更新“应用安装程序”，也可以分别从
Python 与 ffmpeg 官方网站下载安装。WinGet 官方要求 Windows 10 1809（内部版本 17763）
或更高版本。

停止工具的方法：关闭运行 MediaDistill 的命令提示符窗口，或在窗口中按 `Control + C`。

## 使用终端安装

```bash
git clone https://github.com/Hikhuangyuting/MediaDistill.git
cd media-distill

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python run.py --web --port 8765
```

浏览器访问：<http://127.0.0.1:8765/>

Windows PowerShell 对应命令：

```powershell
git clone https://github.com/Hikhuangyuting/MediaDistill.git
Set-Location MediaDistill

py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py --web --port 8765
```

## 网页工作台

网页界面支持：

- 单个或批量导入素材
- 按导入顺序浏览素材
- 创建、展开和折叠分组
- 多选素材并拖入分组
- 查看阶段进度和运行日志
- 浏览转写和 Markdown
- 下载 Markdown

## 与 AI Agent 配合

当网页显示“需要 AI 分析”时，在项目中查找：

```text
workspace/<asset_id>/agent_tasks/
```

其中的 `TASK.md` 会说明：

- 需要读取哪些转写、关键帧或时间线文件
- 需要遵循什么分析规则
- JSON 应写入什么位置
- 输出必须满足什么 Schema

让支持本地文件操作的 AI Agent 执行任务后，再次处理同一素材，流水线会从断点继续。

## 命令行

```bash
# 启动网页工作台
python run.py --web --port 8765

# 处理全部待办素材
python run.py

# 列出素材
python run.py --list

# 查看全部或单个素材状态
python run.py --status
python run.py --status <asset_id>

# 只处理一个素材
python run.py --asset <asset_id>

# 运行到指定阶段
python run.py --asset <asset_id> --through speech

# 从指定阶段开始强制重跑，并使下游结果失效
python run.py --asset <asset_id> --force speech
```

## 项目目录

```text
media-distill/
├── audio/                  # 导入的音频，本地使用，不提交 Git
├── videos/                 # 导入的视频，本地使用，不提交 Git
├── config/                 # Pipeline、Schema 与 Prompt 配置
├── src/                    # 核心处理逻辑与网页工作台
├── workspace/              # 缓存、状态、Agent 任务，不提交 Git
├── output/markdown/        # 最终 Markdown，不提交 Git
├── logs/                   # 本地运行日志，不提交 Git
├── run.py                  # 统一入口
├── 安装 MediaDistill.command
├── 启动 MediaDistill.command
├── 安装 MediaDistill.bat
└── 启动 MediaDistill.bat
```

## 数据与隐私

- Web 服务只绑定本机 `127.0.0.1`，不直接暴露给局域网或互联网。
- `.gitignore` 默认排除视频、音频、转写、关键帧、模型缓存、日志、输出和本机配置。
- 请在提交前运行 `git status`，确认没有个人素材、路径、密钥或知识笔记被加入暂存区。
- faster-whisper 模型由 Hugging Face 下载，其缓存位置取决于本机环境。

## 常见问题

### 为什么停在“需要 AI 分析”？

本地预处理已经完成，但画面理解或知识提炼任务尚未被 AI Agent 执行。按“与 AI Agent 配合”一节处理对应 `TASK.md`。

### 为什么首次转写很慢？

首次运行需要下载模型；CPU 推理速度也会受视频时长、模型大小和电脑性能影响。完成后的结果会缓存，后续不会重复计算。

### 为什么关键帧不是均匀截图？

工具会先生成时间与场景候选，再按清晰度、视觉信息量和相似度过滤，尽量保留文字丰富或内容变化明显的画面。

### 为什么没有上传到在线网站？

MediaDistill 需要读取本机大文件、调用 ffmpeg 并运行本地模型，当前定位是本地网页工具，不是托管式在线服务。

### Windows 双击脚本一闪而过怎么办？

先打开命令提示符，进入解压后的 MediaDistill 目录，再运行：

```bat
"安装 MediaDistill.bat"
```

这样窗口不会立即消失，可以看到 Python、ffmpeg、网络连接或依赖安装的具体错误。

## 开发状态

当前版本：`0.1.0`，属于公开预览版，适合个人本地使用和共同迭代。版本变化见
[CHANGELOG.md](CHANGELOG.md)。

欢迎通过 Issue 提交：

- 可复现的错误和运行日志
- 不同平台的安装体验
- 抽帧与语音覆盖问题
- 更通用的 AI Provider 接入方案

## License

[MIT](LICENSE)
