# 实作状态（2026-11-26）

本文件区分代码实现、离线测试和游戏实机验证。

## 已实现代码

- core.runtime：Maa Resource / ADB Controller / Tasker 生命周期、资源加载、绑定检查、初始截图和关闭流程；不调用 post_task，不加载 Pipeline JSON。
- core.device：ADB 设备发现、无线连接、DeviceInterface、MaaDevice、串行设备包装、截图缓存、坐标映射、FakeDevice 和单工作线程调用队列。
- core.vision：RecognitionResult / VisionInterface、Maa Native TemplateMatch / OCR Adapter、FakeVision。
- core.scenes：置信度门槛、歧义场景拒绝、唯一最短导航路径、逐步转场截图核验和 PopupHandler。
- core.tasks：BaseTask、TaskContext、TaskRegistry、依赖 DAG、循环检测、串行调度、协作式取消/超时和执行记录。
- core.observability：JSON Lines 结构化日志与 PNG 失败截图保存。
- battle.axle_import：JPEG EXIF UserComment、LZ-String Base64 解压入口、格式版本白名单、输入限制、结构规范化及 AxleTool 1.0.0 迁移。
- battle.models / catalog：BattlePlan、六槽 PartyProfile、PartyMemberSpec、BattleTurn、BattleAction、OD、技能类型目录协议和静态目录。
- battle.preparation：队伍档案与主动/被动技能分离编译、技能类别/习得/EX 装备校验、队伍/战型/被动/共鸣支援差异、阻塞项、dry-run 预览及 READY + 用户确认门禁。
- battle.runner：BattleRuntimeAdapter 协议、计划指纹绑定、逐回合/逐动作状态验证、OD 验证和 FakeBattleRuntime。
- cli：inspect-plan 和 adb-devices 命令。

## 离线验证

当前容器执行：

- python -m pytest -q：32 passed。
- python -m compileall -q hbr_auto tests：通过。

运行解释器为 Python 3.13.5，不是项目目标 Python 3.15.2。没有声称 Ruff 或 Python 3.15 / MaaFw 真实设备测试通过。

## 尚未完成的验收项

1. 当前容器无法取得 Python 3.15.2 构建，因此没有生成可信 uv.lock，也未完成 MaaFw 5.16.1 的导入/运行测试。
2. 尚无真实 AxleTool 导出 JPEG。测试 fixture 是合成、脱敏的 JSON payload；仍需真实导出图验证 piexif 与 py-lzstring 互操作。
3. 没有 HBR 客户端截图集和审核过的角色技能目录，因此没有实现主界面、编队、角色详情和技能设置页的生产识别器。
4. PartyStateAnalyzer、PartySetupExecutor、PassiveSkillSetupExecutor、EXSkillSetupExecutor 与 ResonanceSetupValidator 需要真实截图样本及 UI 语义后实现。PreparationPlanner 只计算差异；DryRunPreparationExecutor 不发送设备输入。
5. BattleRuntimeAdapter 目前只有协议与 FakeBattleRuntime。没有生产版 BattleAnalyzer、技能/目标/OD 输入执行器或 Switch / 追加回合设备处理。
6. 多个 AxleTool teamTab 当前始终不能通过 READY 门禁；没有推断其游戏内切换动作。
7. Daily、Dungeon、Event、SQLite 检查点、Recovery、多设备 Runtime 隔离及长时间稳定性测试尚未实现。

## 安全语义

- Unknown / 低置信度场景不产生输入动作。
- 当前队伍、被动技能槽位映射、共鸣支援、技能习得或 EX 装备状态未知时不能 READY。
- 多 teamTab 排轴不能通过单队伍 READY 门禁。
- 养成与装备快照不触发自动消耗资源。
- 战斗执行前再次验证战斗场景、回合、技能和目标；准备 READY 不代表战斗已经启动。
