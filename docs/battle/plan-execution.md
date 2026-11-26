# BattlePlan 与战斗执行设计

## 1. 目标

将 AxleTool 排轴、后续其他排轴来源和 Python 内置策略统一为内部 BattlePlan。战斗执行层不直接读取 EXIF 或 AxleTool 原始 JSON，也不依赖排轴图片 OCR。

## 2. 计划数据模型

目标领域模型：

- BattlePlan：名称、来源、原始格式版本、内部 schema 版本、语言、队伍、回合列表和导入警告。
- PartyMember：team tab、槽位、character、team 分类、style、style_id、rank、support 和其他编队元数据。
- BattleTurn：序号、原始 turn label、OD 指令、三个有序行动槽位。
- BattleAction：action slot、角色身份、战型身份、技能 value、目标角色 value、is1Damage。
- SpecialInstruction：Switch、追加回合及未来上游增加的特殊指令。

领域模型应使用不可变数据类或等价的强类型模型；原始 AxleTool JSON 单独保留为导入边界对象。标准化后不要继续传播任意字典。

## 3. 角色、技能、目标解析

### 角色

行动项中的 selectedTab 与 style 用于在 char[selectedTab] 的角色槽位中定位实际角色。解析优先使用 character、style 和 style_id 联合验证，不得只依赖图片路径 style_img。

### 技能

行动项的 skill 是上游技能选项的 value。本项目使用 AxleCatalog 将其关联到技能定义、SP 消耗、技能类型和多语言展示名。实际执行前，必须通过当前游戏画面重新确认技能按钮和可用状态。

### 目标

target 对应队伍角色选项的 value。它不是屏幕坐标，也不是敌人的固定槽位编号。执行器需要将目标角色标识映射到当前战斗 UI 中可选择的目标，再验证选中结果。

### 形态

style_id 可能是单个 ID，也可能按上游多形态逻辑表现为可选 ID 集合；activeFormId 表示当前选择。两者应由 Catalog / Resolver 解释，执行前核验当前战型。

## 4. 执行组件

- PartyValidator：核验当前队伍和排轴队伍是否一致。
- BattleAnalyzer：从截图生成 BattleState，包括当前阶段、回合、可用角色、技能、目标及可识别资源状态。
- TurnTracker：将游戏中识别到的回合与排轴行对应。
- ActionResolver：把 BattleAction 解析为当前屏幕中的可执行动作。
- SkillExecutor：选择技能并确认 SP / 可用状态。
- TargetExecutor：选择目标并确认选择结果。
- OverdriveExecutor：处理 OD 指令与 Bonus。
- SpecialTurnHandler：处理 Switch 和追加回合等特殊指令。
- BattlePlanRunner：按计划顺序推进状态机，记录每项动作结果。

Strategy 只产生决策，不直接调用 Device。Executor 才拥有执行输入的权限。

## 5. 严格模式（首版默认）

以下情况必须暂停，不可自行换技能或跳过：

- 当前战斗场景与预期不符。
- 当前队伍成员、战型或位置无法与排轴匹配。
- 当前回合与排轴行不同。
- 计划中的技能未解锁、SP 不足、当前不可用或无法唯一识别。
- 目标不存在或无法确认已选中。
- OD 级别或 Bonus 与计划不符。
- 角色倒下、状态变化或 UI 变化导致动作含义不再确定。

允许用户检查当前画面后手动继续、跳过或终止，但应写入执行记录。

## 6. 特殊指令

- T1 至 T80：普通回合标签。不能假定所有排轴都会使用连续数字。
- 追加回合：保留为独立指令；必须通过实际游戏流程验证它与普通回合的同步规则。
- Switch：上游用于分隔或标记特殊编排行，并将该行行动槽清空。首版先识别并暂停或交由专门 Handler，未确认其游戏内操作语义前不得自动点击。
- OD1 至 OD5 及 Bonus1 至 Bonus3：作为结构化 OD 指令，不能仅按字符串前缀推断可触发状态。

## 7. 动作验证与重试

每个动作按以下小状态机执行：

    PRECHECK
      -> INPUT_SENT
      -> UI_CONFIRMATION
      -> COMMITTED

若在 INPUT_SENT 后无法确认结果，状态标记为 UNKNOWN 并暂停。不可逆操作不能直接重复点击。只有确认上一次输入未生效时，才允许按重试策略重新执行。

每个动作记录：plan ID、turn index、action slot、预期角色/技能/目标、识别证据、输入坐标或 UI 控件、结果和耗时。

## 8. 策略来源

统一接口：

- AxlePlanStrategy：严格按导入的 BattlePlan 执行。
- NativeStrategy：完全由 Python 根据 BattleState 决策。
- AdaptiveStrategy：未来可在明确规则下调整排轴；默认不启用，必须对每次偏离记录原因。

## 9. 执行前预览

开始战斗前显示：

- 排轴名称与数据版本。
- 预计队伍及每个槽位角色/战型。
- 回合数、OD 指令、Switch 和追加回合标记。
- 每回合三个行动槽位的角色、技能和目标。
- 未解析字段、未知技能、缺少 Catalog 元数据等警告。

只有通过强校验并经用户确认，才允许启动自动执行。

## 10. 测试策略

- 纯单元测试：计划模型、角色/技能/目标 Resolver、回合状态机。
- 解析 fixture：来自 AxleTool 的真实导出图片，注意脱敏和许可。
- 截图回放测试：使用已保存的 UI 截图验证 Scene / BattleAnalyzer。
- 模拟执行测试：用 FakeDevice / FakeVision 检查动作顺序。
- 设备冒烟测试：先允许单步确认，不直接跑完整长轴。
