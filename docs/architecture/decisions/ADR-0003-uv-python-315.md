# ADR-0003：使用 uv 和 Python 3.15.2

- 状态：Accepted
- 日期：2026-11-26

## 背景

项目需要可重复的 Python 解释器和依赖环境，且用户要求采用最新稳定 Python。根据 2026-11-26 查询的 Python 官方发布信息，当前最新稳定补丁版为 Python 3.15.2（2026-10-25）。

## 决策

- 使用 uv 管理 Python 解释器、虚拟环境、依赖解析、锁文件和命令执行。
- .python-version 固定为 3.15.2。
- pyproject.toml 的约束为 >=3.15,<3.16。
- MaaFramework Python 包使用 PyPI 项目 MaaFw==5.16.1。
- 解析 AxleTool 图片元数据使用 piexif；LZ-String Base64 解压使用 py-lzstring。
- 依赖解析后生成并提交 uv.lock；依赖变更必须同步更新锁文件。

## 兼容性说明

MaaFw 5.16.1 的 PyPI 元数据声明 Python >=3.9，发行 wheel 使用 py3-none 标签；但该发行包的上传构建环境信息显示为 CPython 3.14.4。这不能替代在 Python 3.15.2 上的实测。

因此第一阶段验收必须包括：

1. 在 Python 3.15.2 下 uv sync 成功。
2. from maa.tasker import Tasker 等关键 Binding 可以导入。
3. Resource、Controller、Tasker 能创建和绑定。
4. 连接 ADB 设备并完成截图冒烟测试。

若第 2 或第 3 步因上游 Binding 的 3.15 兼容问题失败，应先提交可复现问题并评估临时兼容矩阵；不得静默降低 requires-python 或伪称 3.15 已验证。此时 Python 3.14 仅作为排障对照，不改变项目的首选目标。

## 后果

- 开发者通过 uv 获得一致的解释器和依赖版本。
- Python 3.15 是当前开发基线，但 MAA 的真实运行兼容性仍需验证。
- uv.lock 是应用依赖复现的权威文件；pyproject.toml 描述直接依赖和范围。
