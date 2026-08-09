# 发布检查清单

## 自动检查

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
python -W error -m compileall -f -q src scripts run.py tests
python -m pip check
bash -n "安装 MediaDistill.command" "启动 MediaDistill.command"
```

推送后确认 GitHub Actions 在 Linux Python 3.10、3.13 和 Windows Python 3.13
上全部通过。

## 隐私与仓库内容

- 用 `git status --ignored` 确认素材、输出、日志、本机配置和虚拟环境均被忽略。
- 用 `git diff --cached --check` 检查待提交内容。
- 检索 API Key、Token、密码、个人绝对路径和私有知识内容。
- 确认没有大文件；影音素材不应依赖 Git LFS 进入公开仓库。

## 人工冒烟测试

- 在一份全新克隆中完成安装并启动网页。
- 导入一个短音频和一个短视频，确认同名文件不会被覆盖。
- 检查素材排序、新建分组、多选和拖拽分组。
- 检查转写、关键帧、等待 AI、断点恢复和 Markdown 下载。
- 检查失败日志能说明原因、缺少内容和恢复命令。

## 版本发布

- 更新 `pyproject.toml`、README 当前版本和 `CHANGELOG.md`。
- 创建带注释的标签，例如 `git tag -a v0.1.0 -m "MediaDistill v0.1.0"`。
- GitHub Release 中说明新增功能、已知限制、升级方法和校验结果。
- 发布后用 Release 压缩包再做一次干净安装。
