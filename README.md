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
| Windows 10/11 | 已验证 | 提供双击安装、启动脚本与 PowerShell 安装方式 |

MediaDistill 的 Python 依赖会安装进项目自己的 `.venv`，但 Python、ffmpeg 和 ffprobe 是
系统级前置依赖，需要先由各操作系统的包管理器安装：

| 系统 | 推荐命令 |
| --- | --- |
| macOS | `brew install python ffmpeg` |
| Windows 10/11 | `winget install -e --id Python.Python.3.13`，然后 `winget install -e --id Gyan.FFmpeg` |
| Ubuntu/Debian | `sudo apt update && sudo apt install python3 python3-venv ffmpeg` |

WinGet 仅属于 Windows；macOS 中承担同类职责的是 Homebrew。双击安装脚本不会在用户未确认的
情况下修改系统软件，它只检查前置依赖，然后创建 `.venv` 并安装 Python 包。

## 最简单的使用方式（macOS）

以下步骤适用于常见的 Intel 和 Apple 芯片 Mac。

### 第一步：打开终端并检查现有环境

按 `Command + 空格键` 打开聚焦搜索，输入“终端”或 `Terminal`，按回车打开。后续命令请逐行
复制到终端，每输入一行按一次回车。

先运行：

```bash
sw_vers -productVersion
python3 --version
ffmpeg -version
ffprobe -version
```

如果 Python 为 3.10 或更高版本，且 `ffmpeg`、`ffprobe` 都能显示版本，可以直接跳到第四步，
**不需要为了 MediaDistill 重复安装 Homebrew 或 FFmpeg**。

macOS 14 或更高版本是当前 Homebrew 正式支持的环境。macOS 13 仍可能安装成功，但部分依赖会
改为本机编译，可能耗时一小时以上，并反复显示 Command Line Tools 警告。

### 第二步：检查网络和 Command Line Tools

Homebrew 需要终端访问 GitHub。浏览器能打开 GitHub，不代表终端也能访问；代理软件有时只代理
浏览器。先运行：

```bash
curl -I https://github.com
curl -I https://raw.githubusercontent.com
```

两条命令都应返回 HTTP 状态。如果出现 `Connection reset`、`Operation timed out` 或
`Couldn't connect to server`，请先切换网络，或在代理软件中启用系统代理/TUN。使用本地代理时，
按代理软件显示的实际端口设置，例如：

```bash
export http_proxy="http://127.0.0.1:你的代理端口"
export https_proxy="http://127.0.0.1:你的代理端口"
```

再次运行两条 `curl` 命令，确认成功后再继续。

接着检查 Apple Command Line Tools：

```bash
xcode-select -p
clang --version
```

如果提示尚未安装，运行：

```bash
xcode-select --install
```

如果 Homebrew 随后明确提示工具过旧，先到 `系统设置 → 通用 → 软件更新` 安装更新。若
`xcode-select` 认为已经安装、`softwareupdate --list` 却没有更新，并且
`pkgutil --pkg-info=com.apple.pkg.CLTools_Executables` 找不到安装记录，说明旧工具状态异常。
不要直接删除，先备份后重新安装：

```bash
sudo mv /Library/Developer/CommandLineTools /Library/Developer/CommandLineTools.backup
sudo xcode-select --reset
xcode-select --install
```

### 第三步：只安装缺少的依赖

先检查电脑是否已有 Homebrew：

```bash
brew --version
```

如果能看到版本号，直接进入第三步。如果提示 `command not found: brew`，执行 Homebrew 官方
安装命令：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

安装过程中可能要求输入 Mac 登录密码。输入密码时终端不会显示字符，这是 macOS 的正常安全
设计；输入完成后按回车即可。安装程序如果显示 `Next steps`，请复制并执行它给出的命令。

安装结束后关闭终端，再重新打开一个终端，并再次运行：

```bash
brew --version
```

Apple 芯片 Mac 如果仍提示找不到 `brew`，先执行：

```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
```

只在 Python 缺失或低于 3.10 时安装 Python：

```bash
brew install python
```

只在 `ffmpeg` 或 `ffprobe` 缺失时安装 FFmpeg：

```bash
brew install ffmpeg
```

Homebrew 出现 `[y/n]` 时，输入小写 `y` 并按回车。macOS 13 上可能长时间编译；看到窗口标题中
有 `ruby`，或在另一终端能查到 `brew`、`make`、`clang` 进程，说明仍在工作，不要重复输入。

安装结束后逐项确认：

```bash
python3 --version
ffmpeg -version
ffprobe -version
```

如果日志显示 FFmpeg 已安装，但 `ffprobe` 仍提示 `command not found`，通常是旧的
`/usr/local/bin/ffmpeg` 阻止 Homebrew 建立完整链接。先备份旧文件，再重新链接：

```bash
sudo mv /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg.before-homebrew
brew link ffmpeg
ffmpeg -version
ffprobe -version
```

Apple 芯片 Mac 的冲突路径通常位于 `/opt/homebrew/bin`，请以 Homebrew 错误信息中显示的
`Target` 路径为准。不要在未备份时直接运行 `rm` 或 `brew link --overwrite`。

中国大陆网络如果无法连接 GitHub，可以改用可信镜像。镜像不是 Homebrew 官方服务器，使用前
应了解并接受其信任边界；具体命令请参考[中国科学技术大学开源镜像说明](https://mirrors.ustc.edu.cn/help/brew.git.html)。

### 第四步：下载并解压 MediaDistill

在 GitHub 仓库页面点击 `Code → Download ZIP`。下载完成后，在 Finder 的“下载”目录中双击
ZIP 文件解压，再把解压后的项目文件夹移动到桌面或其他固定位置。

不要直接在 ZIP 压缩包中运行文件，也不要只复制其中一个安装脚本。

### 第五步：安装 MediaDistill

打开解压后的项目文件夹，右键点击 `安装 MediaDistill.command`，选择“打开”，在系统提示中
再次点击“打开”。首次安装需要保持网络连接，程序会创建 `.venv` 并安装 Python 依赖。

看到“安装完成”后按回车关闭窗口。项目文件夹中出现 `.venv` 是正常现象；Finder 默认可能
隐藏以点开头的目录，不需要手动打开或修改它。

如果系统提示文件没有执行权限，打开终端，先输入 `cd `（`cd` 后保留一个空格），把项目文件夹
从 Finder 拖进终端窗口，然后按回车。接着执行：

```bash
chmod +x "安装 MediaDistill.command" "启动 MediaDistill.command"
```

再重新右键打开安装脚本。

### 第六步：启动网页工具

双击 `启动 MediaDistill.command`，并保持终端窗口打开。浏览器会自动打开：

<http://127.0.0.1:8765/>

如果浏览器没有自动打开，可以手动输入这个地址。看到 MediaDistill 素材库页面后，即可批量
导入视频或音频。

关闭启动终端窗口，或在终端中按 `Control + C`，即可停止本地服务。

## 最简单的使用方式（Windows 10/11）

以下步骤适用于 Windows 10 1809 或更高版本以及 Windows 11。

### 第一步：下载并解压 MediaDistill

在 GitHub 仓库页面点击 `Code → Download ZIP`，下载完成后右键 ZIP 文件并选择“全部解压”。
请把项目解压到桌面或其他固定目录，不要直接在 ZIP 压缩包预览窗口中运行脚本。

### 第二步：安装 Python 和 FFmpeg

打开 PowerShell，依次执行：

```powershell
python --version
```

如果显示 Python 3.10 或更高版本，可以跳过 Python 安装；否则执行：

```powershell
winget install -e --id Python.Python.3.13
```

然后安装 FFmpeg：

```powershell
winget install -e --id Gyan.FFmpeg
```

第一次使用 WinGet 时，系统可能要求确认来源协议，输入 `Y` 并按回车即可。

安装完成后，**完整关闭这个 PowerShell 窗口，再重新打开一个新 PowerShell 窗口**。这是让
Windows 载入 FFmpeg 新路径所必需的步骤。然后执行：

```powershell
python --version
ffmpeg -version
ffprobe -version
```

三个命令都能显示版本信息后，再继续下一步。如果 `python` 不可用，可以尝试
`py -3 --version`，后续把安装命令开头的 `python` 换成 `py -3`。

### 第三步：安装 MediaDistill

进入解压后的文件夹，双击 `安装 MediaDistill.bat`。安装程序会创建项目专用的 `.venv`，
并安装所需 Python 依赖；首次安装需要保持网络连接。

看到“安装完成”后，点击文件资源管理器顶部的地址栏，输入 `powershell` 并按回车。新打开的
PowerShell 会自动位于当前项目目录。执行下面两条命令确认安装结果：

```powershell
Test-Path .\.venv\Scripts\python.exe
.\.venv\Scripts\python.exe .\scripts\bootstrap.py --check
```

第一条应返回 `True`，第二条应显示 Python、ffmpeg、ffprobe、虚拟环境和 faster-whisper
均可用。如果双击脚本没有完成安装，可在同一个 PowerShell 窗口直接执行：

```powershell
python .\scripts\bootstrap.py
```

安装过程会同时保存到 `logs\windows-install.log`，便于在安装未完成时查看具体提示。

### 第四步：启动网页工具

双击 `启动 MediaDistill.bat`，不要关闭随后出现的命令提示符窗口。浏览器会自动打开：

<http://127.0.0.1:8765/>

如果浏览器没有自动打开，也可以手动输入这个地址。只有命令提示符窗口中的本地服务保持
运行时，页面才可以访问。关闭该窗口，或在窗口中按 `Control + C`，即可停止工具。

### 没有 WinGet 时

可以通过 Microsoft Store 安装或更新“应用安装程序”，再重新打开 PowerShell。也可以分别
从 Python 与 FFmpeg 官方网站下载安装，但安装时需要勾选把程序加入 PATH。WinGet 官方要求
Windows 10 1809（内部版本 17763）或更高版本。

如果 FFmpeg 安装完成后当前窗口仍找不到命令，优先关闭并重新打开 PowerShell；不方便关闭时，
也可以使用本文“常见问题”中的 PATH 刷新方法。

## 使用终端安装（macOS、Windows、Linux）

终端安装的流程是通用的：安装系统前置依赖 → 获取代码 → 运行统一的
`scripts/bootstrap.py` → 启动网页。不同系统只有 Python 命令和虚拟环境可执行文件路径不同。

先用上方表格中的命令安装 Python、ffmpeg 与 ffprobe，然后获取代码：

```bash
git clone https://github.com/Hikhuangyuting/MediaDistill.git
cd MediaDistill
```

macOS / Linux：

```bash
python3 scripts/bootstrap.py
python3 scripts/bootstrap.py --check

.venv/bin/python run.py --web --port 8765
```

Windows PowerShell：

```powershell
python .\scripts\bootstrap.py
.\.venv\Scripts\python.exe .\scripts\bootstrap.py --check

.\.venv\Scripts\python.exe .\run.py --web --port 8765
```

如果系统只有 Python Launcher，也可以把第一条命令换成 `py -3 .\scripts\bootstrap.py`。

`--check` 不会安装或修改内容，只检查 Python、ffmpeg、ffprobe、`.venv` 和
faster-whisper 是否已经可用。启动后浏览器访问：<http://127.0.0.1:8765/>。

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

更可靠的方式是在项目目录打开 PowerShell，直接运行统一安装程序：

```powershell
python .\scripts\bootstrap.py
```

只有最后显示“安装完成”，并且 `.venv\Scripts\python.exe` 确实存在，才表示安装成功。
如果失败，请查看 `logs\windows-install.log`；该日志包含系统、Python、ffmpeg 路径和 pip
输出，但不会记录密码或 GitHub Token。

### Windows 启动后浏览器提示无法访问 127.0.0.1？

这表示本地服务没有持续运行，不是浏览器地址错误。请在项目目录的 PowerShell 中执行：

```powershell
Test-Path .\.venv\Scripts\python.exe
.\.venv\Scripts\python.exe .\scripts\bootstrap.py --check
.\.venv\Scripts\python.exe .\run.py --web --port 8765
```

保持 PowerShell 窗口打开。看到
`MediaDistill 本地工作台：http://127.0.0.1:8765` 后再访问页面。若第一条返回 `False`，执行
`python .\scripts\bootstrap.py`；若提示端口占用，改用 `--port 8766` 并访问
`http://127.0.0.1:8766/`。

### Windows 已显示 FFmpeg 安装成功，但仍提示找不到命令？

首先关闭安装 FFmpeg 时使用的整个 PowerShell 窗口，重新打开 PowerShell 后再测试。WinGet
安装的便携命令通常通过 `%LOCALAPPDATA%\Microsoft\WinGet\Links` 提供；旧窗口仍保存着
安装前的 PATH。

如果新窗口仍然找不到，依次运行：

```powershell
winget list -e --id Gyan.FFmpeg
$links = "$env:LOCALAPPDATA\Microsoft\WinGet\Links"
Test-Path $links
Get-ChildItem $links
$env:Path -split ";" | Where-Object { $_ -like "*WinGet*" }
Get-Command ffmpeg -ErrorAction SilentlyContinue
```

- `winget list` 找不到包：重新运行 `winget install -e --id Gyan.FFmpeg`。
- `Links` 目录中有 `ffmpeg.exe`，但 PATH 没有该目录：先运行前文的 PATH 重新载入命令。
- 重新载入后仍缺少该目录，可以把它补进用户 PATH：

```powershell
$links = "$env:LOCALAPPDATA\Microsoft\WinGet\Links"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ";") -notcontains $links) {
    [Environment]::SetEnvironmentVariable(
        "Path",
        "$($userPath.TrimEnd(';'));$links",
        "User"
    )
}
```

执行后再次完整关闭并重新打开 PowerShell。

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
