# 开发路线图

> 当前状态：设计和项目元数据阶段。完成状态以代码、测试和 PR 为准，不以文档中出现模块名称为准。

## Phase 0：项目基线与设计文档

- [x] 建立仓库说明和架构约束。
- [x] 记录 Pure Python + MaaFramework 决策。
- [x] 记录 Maa Native Vision 决策。
- [x] 固定 Python 3.15.2 与 uv 项目元数据。
- [x] 记录 AxleTool EXIF / LZ-String 数据格式。
- [x] 设计 BattlePlan 规范化和严格执行流程。
- [ ] 在本地执行 uv lock 并提交实际生成的 uv.lock。
- [ ] Python 3.15.2 + MaaFw 5.16.1 兼容性冒烟测试。

## Phase 1：基础运行时

- [ ] MaaRuntime：Resource、Tasker、Controller 生命周期。
- [ ] ADB 设备发现、连接、断开和重连。
- [ ] DeviceInterface / MaaDevice。
- [ ] 截图缓存、坐标映射和串行输入队列。
- [ ] 结构化日志与失败截图。

验收：连接 Android / 模拟器，稳定截图并执行可验证的基本输入。

## Phase 2：Vision Adapter 与场景系统

- [ ] VisionInterface / MaaVision。
- [ ] RecognitionResult 标准化。
- [ ] TemplateMatch、OCR 及常用识别器封装。
- [ ] 图片、ROI 和 OCR 模型资源管理。
- [ ] Scene / SceneDetector / SceneManager。
- [ ] Navigator 和通用弹窗处理。

验收：在固定截图集上识别主界面、加载、弹窗和目标功能页面；识别不确定时不执行点击。

## Phase 3：AxleTool 排轴导入

- [ ] 收集合法的 AxleTool 导出 JPEG fixture。
- [ ] ExifReader / AxleDecoder。
- [ ] 格式版本迁移。
- [ ] AxleNormalizer / AxleValidator。
- [ ] BattlePlan 数据模型。
- [ ] AxleCatalog 接口。
- [ ] 排轴预览和导入报告。
- [ ] 解析 fixture 回归测试。

验收：在不连接游戏的情况下，准确还原队伍、回合、OD、角色、技能和目标。

## Phase 4：任务系统与公共功能

- [ ] BaseTask、TaskContext、TaskRegistry。
- [ ] 依赖 DAG、循环检测、串行调度。
- [ ] 取消、超时、重试和执行记录。
- [ ] 登录、主界面导航、通用弹窗处理。

验收：多个独立 Python 任务可以组合执行，失败任务能准确停止并留下诊断信息。

## Phase 5：战斗排轴执行

- [ ] BattleAnalyzer / BattleState。
- [ ] PartyValidator。
- [ ] TurnTracker。
- [ ] ActionResolver。
- [ ] SkillExecutor / TargetExecutor。
- [ ] OverdriveExecutor。
- [ ] Switch / 追加回合特殊处理。
- [ ] FakeDevice 模拟执行测试。
- [ ] 单步确认设备测试。

验收：先在模拟环境逐项验证；实际设备执行时，每回合和每个动作都有状态校验，失败默认暂停。

## Phase 6：其他玩法与稳定性

- [ ] Daily。
- [ ] Dungeon / RoutePlanner。
- [ ] Event。
- [ ] SQLite 持久化和检查点。
- [ ] Recovery。
- [ ] 多设备 Runtime 隔离。
- [ ] 性能分析与长期运行测试。

## 里程碑原则

不以“功能能点击”为完成标准。每个阶段必须同时有接口、错误路径、测试和可观测性。涉及游戏状态的自动操作必须有执行前条件和执行后确认。
