# HBR-Auto

面向《Heaven Burns Red / 绯染天空》的 Python 自动化项目。业务流程、任务调度和战斗逻辑全部由 Python 编排；MaaFramework 提供底层设备控制与 Native Vision，不使用 JSON Pipeline。

## 技术基线

- Python 3.15.2（由 .python-version 固定），uv 管理解释器和依赖。
- MaaFramework Python Binding：MaaFw 5.16.1。
- Android / 模拟器 ADB。
- Maa Native Vision，经项目自有 VisionInterface 调用。
- 导入 HBR-AxleTool-vue 导出的 JPEG，从 EXIF UserComment 读取 LZ-String Base64 数据。

## 已实现的基础能力

- MaaRuntime：Resource、ADB Controller、Tasker 生命周期，原生图片/OCR 资源加载，绑定和初始截图验证。
- DeviceInterface / MaaDevice：截图、点击、滑动、按键、ADB 设备发现与无线连接、坐标映射、截图缓存和串行访问。
- VisionInterface / MaaVision：独立 TemplateMatch 与 OCR 识别调用，标准化项目识别结果。
- Scene / Navigator / PopupHandler：置信度门槛、歧义拒绝、唯一导航路径和每步场景验证。
- TaskRegistry / TaskScheduler：依赖 DAG、循环检测、串行执行、协作式取消/超时与执行记录。
- AxleTool Importer：EXIF 读取、LZ-String Base64 解压入口、格式白名单、迁移、输入限制与结构规范化。
- BattlePlan / PreparationPlanner：六人队伍档案、被动技能、行动轴主动技能/目标、OD、Switch/追加回合、技能目录核对、差异预览和 READY 门禁。
- BattlePlanRunner：严格 BattleRuntimeAdapter 契约、回合/动作/OD 状态校验与 FakeBattleRuntime。
- JSON Lines 日志、PNG 失败截图保存及离线 FakeDevice / FakeVision。

核心逻辑和模拟器已通过离线单元测试；不代表具体 HBR 游戏页面、角色技能目录或实机点击流程已经完成。详见 docs/implementation/status.md。

## 安装与验证

在项目目录运行：

    uv python install 3.15.2
    uv sync --all-groups
    uv run python --version
    uv run pytest
    uv run ruff check .
    uv run ruff format --check .

uv.lock 必须使用目标 Python 环境实际执行 uv lock / uv sync 生成后提交，不可手工伪造。本次开发容器无法取得 Python 3.15.2 构建，因此没有生成锁文件，也没有声称 MaaFw 5.16.1 已在 Python 3.15.2 实机验证。

## CLI

列出主机可见的 ADB 设备：

    uv run python -m hbr_auto adb-devices

检查 AxleTool JPEG 并输出排轴/战前方案摘要（不会连接游戏）：

    uv run python -m hbr_auto inspect-plan path/to/axle-export.jpg
    uv run python -m hbr_auto inspect-plan path/to/axle-export.jpg --output plan-summary.json

CLI 导入需要 piexif 和 py-lzstring。主动/被动技能的习得状态及 EX 装备检查必须接入经过核对的 AxleCatalog 和游戏状态识别器；默认空目录会 fail closed。

## 尚未完成

1. Python 3.15.2 + MaaFw 5.16.1 的真实导入、连接、截图冒烟测试。
2. 用户真实 AxleTool 导出 JPEG 与 JavaScript/Python LZ-String 互操作回归。
3. 真实 HBR 截图集、编队/角色/技能设置识别样本和审核过的角色技能目录。
4. PartyStateAnalyzer、队伍/被动/EX 自动配置执行器和共鸣支援识别。
5. 生产版 BattleAnalyzer、技能/目标/OD/Switch/追加回合设备执行器。
6. Daily、Dungeon、Event、多队伍游戏内切换、SQLite、Recovery 和多设备隔离。

**安全规则：**识别未知、画面歧义、技能目录不完整或当前配置未知时停止；养成类字段只作提示，不自动消耗资源。只有战前报告达到 READY 且用户明确确认，才允许调用战斗运行器。

## 文档

- 架构总览：docs/architecture/overview.md
- 技术决策记录：docs/architecture/decisions/README.md
- AxleTool 排轴导入：docs/battle/axletool-import.md
- 战前编队与技能准备：docs/battle/prebattle-preparation.md
- BattlePlan 与战斗执行：docs/battle/plan-execution.md
- 开发环境与 uv 工作流：docs/development/setup.md
- 开发路线图：docs/roadmap.md
- 本次实作状态与限制：docs/implementation/status.md
