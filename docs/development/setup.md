# 开发环境与 uv 工作流

## 1. 版本基线

截至 2026-11-26：

- Python：3.15.2（当前最新稳定补丁版本）。
- uv：使用 Astral 发布的当前稳定版；项目在首阶段不固定 uv 的补丁号。
- MaaFramework Python 包：MaaFw==5.16.1。
- EXIF：piexif。
- AxleTool LZ-String 兼容解压：py-lzstring。

Python 版本由 .python-version 固定为 3.15.2；pyproject.toml 限制在 >=3.15,<3.16。

## 2. 安装 uv

按操作系统使用 Astral 官方安装方式：

- [uv 安装文档](https://docs.astral.sh/uv/getting-started/installation/)
- [uv Python 版本管理](https://docs.astral.sh/uv/guides/install-python/)

安装后确认：

    uv --version

## 3. 创建环境

在仓库根目录执行：

    uv python install 3.15.2
    uv python pin 3.15.2
    uv sync --all-groups

uv sync 会根据 pyproject.toml 解析依赖并创建或更新 uv.lock 与项目虚拟环境。生成的 uv.lock 应提交到版本控制，不应手工编写。

## 4. 常用命令

    # 确认项目解释器
    uv run python --version

    # 查看依赖树
    uv tree

    # 运行测试
    uv run pytest

    # 静态检查
    uv run ruff check .

    # 自动格式化
    uv run ruff format .

    # 检查锁文件与 pyproject 是否同步
    uv lock --check

    # 添加运行时依赖（示例）
    uv add package-name

    # 添加开发依赖（示例）
    uv add --group dev package-name

依赖变更后提交 pyproject.toml 和 uv.lock。

## 5. MaaFramework 兼容性冒烟测试

MaaFw 5.16.1 的 PyPI 元数据声明 Python >=3.9，wheel 使用通用 py3-none 标签；不过该包上传信息显示构建环境为 CPython 3.14.4。不能仅凭 wheel 标签断言所有 Python 3.15 平台组合都已实测。

安装后先验证 Binding 导入：

    uv run python -c "from maa.tasker import Tasker; from maa.resource import Resource; from maa.controller import AdbController; print('MaaFramework binding import OK')"

后续实现 Runtime 后，再进行 Resource / Controller / Tasker 创建与绑定、ADB 连接、截图和识别冒烟测试。未通过前，不开始长时间游戏操作。

## 6. 平台基线

首期以 Android / 模拟器 ADB 为设备目标。桌面主机的 Windows、Linux 和 macOS 支持情况需分别验证 MaaFw wheel、ADB 和设备截图/输入实现。不要把“PyPI 有 wheel”当成设备环境已验证。

## 7. 依赖说明

- MaaFw：MAA Python Binding 与 Native Runtime。
- piexif：读取 AxleTool JPG 的 EXIF UserComment。
- py-lzstring：与 AxleTool JavaScript lz-string 1.5.0 Base64 编码兼容。
- pytest：测试。
- ruff：Lint 与格式化。

首版不把 Airtest、Poco、PaddleOCR 或独立 OpenCV 模板引擎加入默认依赖。是否补充其他视觉组件必须通过 ADR 说明原因。
