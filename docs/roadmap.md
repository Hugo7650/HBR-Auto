# 开发路线图

> 状态更新时间：2026-11-26。勾选代表已有代码和相应离线测试；游戏实机验收另行标记，不因接口存在而视为通过。

## Phase 0：项目基线与设计文档

- [x] 建立仓库说明、架构约束、技术决策和 AxleTool 数据格式说明。
- [x] 固定 Python 3.15.2 与 uv 项目元数据。
- [ ] 在目标 Python 环境执行 uv lock 并提交实际生成的 uv.lock。
- [ ] Python 3.15.2 + MaaFw 5.16.1 兼容性冒烟测试。

## Phase 1：基础运行时

- [x] MaaRuntime：Resource、Tasker、Controller 生命周期（Fake 工厂覆盖启动/关闭路径）。
- [x] ADB 设备发现、无线连接入口。
- [x] DeviceInterface / MaaDevice。
- [x] 截图缓存、坐标映射和串行输入队列。
- [x] 结构化日志与失败截图。
- [ ] 在目标 Python 环境连接 Android / 模拟器，验证真实截图和基本输入。

**实机验收尚未通过：**当前执行环境无法取得 Python 3.15.2，亦未连接 HBR 设备。

## Phase 2：Vision Adapter 与场景系统

- [x] VisionInterface / MaaVision。
- [x] RecognitionResult 标准化。
- [x] TemplateMatch、OCR 独立识别封装。
- [x] 图片和 OCR 模型资源路径加载入口。
- [x] Scene / SceneDetector / SceneManager。
- [x] Navigator 与 PopupHandler 协议；唯一路径和每步转场验证。
- [ ] 为主界面、加载、弹窗、编队、角色技能设置和目标页面建立截图样本与实际识别器。

**实机验收尚未通过：**没有 HBR 固定截图集，识别配置须用真实客户端样本校准。

## Phase 3：AxleTool 排轴导入与战前方案编译

- [x] EXIF UserComment / LZ-String Base64 解码入口与可注入测试边界。
- [x] 格式版本白名单与 1.0.0 -> 1.0.1 迁移。
- [x] AxleNormalizer / AxleValidator。
- [x] BattlePlan、PartyProfile、PartyMemberSpec、RequiredSkill 模型。
- [x] 从 char 生成六人队伍、被动技能和共鸣支援需求。
- [x] 从 skills + turns 汇总主动技能和 EX 技能需求。
- [x] AxleCatalog 接口和 fail-closed 默认实现。
- [x] PreparationPlanner / PreparationDiff / READY 门禁。
- [x] 排轴及战前配置 JSON 摘要预览。
- [x] 合成 JSON fixture 解析与规范化回归测试。
- [ ] 收集合法、脱敏的真实 AxleTool JPEG fixture。
- [ ] 验证真实 EXIF UserComment 与 JS lz-string / Python py-lzstring 互操作。

**离线验收：**合成 fixture 可还原队伍、角色、战型、被动技能、回合、OD、主动技能和目标。真实 JPEG 验收仍待 fixture。

## Phase 4：任务系统与公共功能

- [x] BaseTask、TaskContext、TaskRegistry。
- [x] 依赖 DAG、循环检测、串行调度。
- [x] 协作式取消、超时与执行记录。
- [x] SceneManager、唯一最短路径 Navigator 和弹窗处理器接口。
- [ ] 登录、主界面各具体页面导航和游戏专属弹窗规则。

**说明：**超时为协作式检查点机制；不会强制终止正在执行的 Python 线程或任意 Maa Job。

## Phase 5：战前配置与战斗排轴执行

- [x] PreparationReport / READY 门禁与用户确认。
- [x] FakeDevice / FakeVision / FakeBattleRuntime 模拟与核心差异测试。
- [x] dry-run 差异预览。
- [x] 战斗 runner 的每回合、每动作和 OD 状态校验协议。
- [ ] PartyStateAnalyzer：从 HBR 截图读取当前六人编队及顺序。
- [ ] PartySetupExecutor：调整角色、战型和位置。
- [ ] PassiveSkillSetupExecutor：调整被动技能槽。
- [ ] RequiredSkillValidator：使用真实技能目录核对主动技能。
- [ ] EXSkillSetupExecutor：调整必需的 EX 技能装备。
- [ ] ResonanceSetupValidator：核对共鸣支援。
- [ ] 生产版 BattleAnalyzer / BattleState。
- [ ] SkillExecutor / TargetExecutor / OverdriveExecutor。
- [ ] Switch / 追加回合特殊处理（需先确认游戏语义）。
- [ ] dry-run、逐项人工确认和单步设备测试。

**实机验收尚未通过：**当前只提供接口、模拟器、准备差异和门禁，没有真实 HBR 页面识别或点击执行器。未达到 verified READY 时 BattlePlanRunner 会拒绝开战。

## Phase 6：其他玩法与稳定性

- [ ] Daily。
- [ ] Dungeon / RoutePlanner。
- [ ] Event。
- [ ] 多 AxleTool teamTab 的游戏内切换专项支持。
- [ ] SQLite 持久化和检查点。
- [ ] Recovery。
- [ ] 多设备 Runtime 隔离。
- [ ] 性能分析与长期运行测试。

## 里程碑原则

不以“功能能点击”为完成标准。每个阶段必须同时有接口、错误路径、测试和可观测性。涉及游戏状态的自动操作必须有执行前条件和执行后确认。未实测的 UI 动作不得标记为完成。
