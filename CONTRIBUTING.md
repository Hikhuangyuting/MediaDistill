# 参与贡献

感谢你愿意改进 MediaDistill。

## 提交问题

创建 Issue 前，请尽量提供：

- 操作系统与 Python 版本
- ffmpeg 版本
- 素材格式与大致时长
- 卡住或失败的 Pipeline 阶段
- 已去除个人信息的运行日志
- 可以稳定复现问题的步骤

请不要上传含有隐私、版权限制或商业机密的音视频和转写。

## 提交代码

1. 从主分支创建独立分支。
2. 保持修改范围清晰，不提交本地素材与生成结果。
3. 运行以下本地检查：

   ```bash
   python -m pip install -e ".[dev]"
   ruff check .
   ruff format --check .
   python -m unittest discover -s tests -v
   python -W error -m compileall -f -q src scripts run.py tests
   bash -n "安装 MediaDistill.command" "启动 MediaDistill.command"
   ```

4. 在 Pull Request 中说明问题、方案和验证方式。

## 设计原则

- Local-first：默认不把用户素材发送到外部服务。
- 可恢复：每个阶段有清晰状态，失败后可以继续。
- 有证据：语音、关键帧与最终结论之间保持可追溯关系。
- 不伪装完成：需要 AI Agent 时明确显示，而不是把等待状态当作成功。
- 不覆盖用户数据：导入和分组操作都应保守处理同名内容。
