# BattlePlan 与战斗执行设计

## 1. 目标与完整流程

将 AxleTool 排轴、后续其他排轴来源和 Python 内置策略统一为内部 BattlePlan。战斗执行层不直接读取 EXIF 或 AxleTool 原始 JSON，也不依赖排轴图片 OCR。

导入排轴后必须先运行 PreBattlePreparation，将队伍及技能配置校准到排轴要求。其状态达到 READY 后才允许启动 BattlePlanRunner。

    AxleTool JPEG
      -> AxlePlanImporter
      -> BattlePlan
      -> PreparationPlan
      -> PreBattlePreparation
      -> READY
      -> 用户确认
      -> BattlePlanRunner

详细战前准备见 [prebattle-preparation.md](prebattle-preparation.md)。

## 2. 计划数据模型

目标领域模型：

- BattlePlan：名称、来源、原始格式版本、内部 schema 版本、语言、队伍、回合列表和导入警告。
- PartyMember：team tab、槽位、character、team 分类、style、style_id、rank、support 和其他编队元数据。
- BattleTurn：序号、原始 turn label、OD 指令、三个有序行动槽位。
- BattleAction：action slot、角色身份、战型身份、主动技能 value、目标角色 value、is1Damage。
- SpecialInstruction：Switch、追加回合及未来上游增加的特殊指令。

领域模型应使用不可变数据类或等价的强类型模型；原始 AxleTool JSON 单独保留为导入边界对象。标准化后不要继续传播任意字典。

## 3. 战前准备模型

从 BattlePlan 编译出单独的 PreparationPlan：

- PartyProfile：每个被引用 AxleTool teamTab 对应一个目标队伍档案。
- PartyMemberSpec：角色槽位、角色、战型、被动技能、共鸣支援及养成参考状态。
- RequiredSkill：从行动轴所有回合汇总的主动技能要求，按 character + style + skill value 去重。
- PreparationDiff：当前游戏配置与目标配置的差异。
- PreparationReport：已完成修改、未完成项、阻塞原因及截图证据。
- PreparationStatus：NOT_STARTED / ANALYZING / NEEDS_USER_INPUT / APPLYING / VERIFYING / READY / BLOCKED / FAILED。

队伍档案、被动技能和主动技能的含义及准备顺序以 [战前编队与技能准备设计](prebattle-preparation.md) 为准。

## 4. 角色、技能、目标解析

### 角色

行动项中的 selectedTab 与 style 用于在 char[selectedTab] 的角色槽位中定位实际角色。解析优先使用 character、style 和 style_id 联合验证，不得只依赖图片路径 style_img。

### 被动技能

char 角色记录中的 passiveSkill 是战前被动技能设置要求，应由 PreBattlePreparation 检查和配置。被动技能不能在战斗中当作主动技能选择。

### 主动技能

行动项的 skill 是某个回合要使用的主动技能 value。本项目使用 AxleCatalog 将其关联到技能定义、SP 消耗、技能类型和多语言展示名。战前汇总所有 RequiredSkill，检查其习得和装备条件；回合执行时再检查 SP、使用次数和当前可用状态。

EX 技能若要求装备，必须在战前确认已装备。普通主动技能若由当前战型直接提供，不需要伪造额外预装备步骤。

### 目标

target 对应队伍角色选项的 value。它不是屏幕坐标，也不是敌人的固定槽位编号。执行器需要将目标角色标识映射到当前战斗 UI 中可选择的目标，再验证选中结果。目标选择属于战斗回合阶段，不属于战前编队调整。

### 形态

style_id 可能是单个 ID，也可能按上游多形态逻辑表现为可选 ID 集合；activeFormId 表示当前选择。两者应由 Catalog / Resolver 解释，战前核验目标形态。

## 5. 战斗执行组件

- PartyValidator：在战斗启动前确认当前编队与已选 PartyProfile 一致。
- BattleAnalyzer：从截图生成 BattleState，包括当前阶段、回合、可用角色、技能、目标及可识别资源状态。
- TurnTracker：将游戏中识别到的回合与排轴行对应。
- ActionResolver：把 BattleAction 解析为当前屏幕中的可执行动作。
- SkillExecutor：选择技能并确认 SP / 可用状态。
- TargetExecutor：选择目标并确认选择结果。
- OverdriveExecutor：处理 OD 指令与 Bonus。
- SpecialTurnHandler：处理 Switch 和追加回合等特殊指令。
- BattlePlanRunner：仅在战前准备 READY 后，按计划顺序推进战斗状态机并记录每项动作结果。

PreBattlePreparation 拥有编队和技能设置界面的配置权限；BattlePlanRunner 拥有战斗内行动输入权限。两者不互相绕过对方的状态门禁。

Strategy 只产生决策，不直接调用 Device。Executor 才拥有执行输入的权限。

## 6. 严格模式（首版默认）

战前准备和战斗执行均采用严格模式。

战前阶段以下情况必须暂停：

- 角色不在用户拥有的角色范围内，或无法识别。
- 目标战型未拥有、未解锁或无法确认。
- 目标被动技能未习得、技能槽不足或槽位配置不明确。
- 排轴主动技能无法由 Catalog 解析。
- EX 技能需要装备但未习得或无法完成装备。
- 多个 AxleTool teamTab 的游戏内切换关系尚未确认。
- 当前画面与预期设置页面不符。

战斗阶段以下情况必须暂停：

- 当前战斗场景与预期不符。
- 当前队伍成员、战型或位置无法与排轴匹配。
- 当前回合与排轴行不同。
- 计划中的技能未解锁、SP 不足、当前不可用或无法唯一识别。
- 目标不存在或无法确认已选中。
- OD 级别或 Bonus 与计划不符。
- 角色倒下、状态变化或 UI 变化导致动作含义不再确定。

允许用户检查当前画面后手动继续、跳过或终止，但应写入执行记录。

## 7. 特殊指令

- T1 至 T80：普通回合标签。不能假定所有排轴都会使用连续数字。
- 追加回合：保留为独立指令；必须通过实际游戏流程验证它与普通回合的同步规则。
- Switch：上游用于分隔或标记特殊编排行，并将该行行动槽清空。首版先识别并暂停或交由专门 Handler，未确认其游戏内操作语义前不得自动点击。
- OD1 至 OD5 及 Bonus1 至 Bonus3：作为结构化 OD 指令，不能仅按字符串前缀推断可触发状态。

## 8. 动作验证与重试

每个动作按以下小状态机执行：

    PRECHECK
      -> INPUT_SENT
      -> UI_CONFIRMATION
      -> COMMITTED

若在 INPUT_SENT 后无法确认结果，状态标记为 UNKNOWN 并暂停。不可逆操作不能直接重复点击。只有确认上一次输入未生效时，才允许按重试策略重新执行。

战前配置采用差异驱动和幂等更新：已经符合目标的角色、技能不重复操作；每个修改后重新识别确认。战斗中每个动作记录 plan ID、turn index、action slot、预期角色/技能/目标、识别证据、输入和结果。

## 9. 执行前预览

正式进入战斗前，预览分成两个部分：

1. **战前配置报告**：目标队伍、六个角色位置、战型、被动技能、EX 装备要求、共鸣支援、当前与目标差异、阻塞项。
2. **行动轴报告**：排轴名称与数据版本、回合数、OD 指令、特殊行、每回合三个行动槽位的角色、主动技能和目标。

只有战前准备达到 READY 且用户确认，才允许启动 BattlePlanRunner。

## 10. 测试策略

- 纯单元测试：计划模型、角色/技能/目标 Resolver、PreparationPlanner、PreparationDiff、战斗回合状态机。
- 解析 fixture：来自 AxleTool 的真实导出图片，注意脱敏和许可。
- 截图回放测试：使用已保存的 UI 截图验证 Scene / BattleAnalyzer 和技能设置页面识别。
- 模拟执行测试：用 FakeDevice / FakeVision 检查战前调整顺序、幂等性和战斗动作顺序。
- 设备冒烟测试：先 dry-run，再逐项人工确认，最后单步确认，不直接跑完整长轴。
