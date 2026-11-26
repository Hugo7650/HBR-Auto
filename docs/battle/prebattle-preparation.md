# 战前编队与技能准备设计

## 1. 目标

导入 AxleTool 排轴图片后，不能直接进入战斗。系统必须先根据排轴生成战前准备方案，将游戏当前编队和技能设置调整到排轴要求，再进行最终校验。只有战前校验通过，才允许开始战斗。

完整流程：

    AxleTool JPEG -> EXIF/LZ-String 导入 -> BattlePlan -> PreparationPlan
      -> 识别当前编队 -> 计算差异 -> 调整角色/战型/被动技能/EX 技能
      -> 验证配置 -> 用户确认 -> READY -> BattlePlanRunner

PreBattlePreparation 是独立于 BattlePlanRunner 的阶段。BattlePlanRunner 不能承担队伍配置工作，也不能默认当前队伍已经满足排轴要求。

## 2. 必须区分三种数据

### 2.1 队伍档案（char）

char 保存 AxleTool 队伍 Tab 下的六个角色槽位信息，用于生成战前目标编队：

- character：角色身份。
- team：角色所属部队分类。
- style / style_id：目标战型。
- rank、flower、earring、spiritual、reincarnation：养成或装备状态参考信息。
- passiveSkill：角色选择的被动技能列表。
- support：该槽位关联的共鸣支援信息。

导出只包含行动轴引用过的队伍 Tab。Tab 编号是 AxleTool 内部档案编号，不等同于游戏中的队伍预设编号。

### 2.2 战斗行动（skills + turns）

skills[row][slot] 与 turns[row] 通过相同索引关联，每行有三个行动槽位。行动槽位中的 skill 是该回合计划使用的主动技能 value；target 是计划指定的目标角色 value；selectedTab 指向对应 AxleTool 队伍档案。

这些字段定义战斗中每回合选择的技能和目标，不代表把每回合技能预先装备到固定技能槽。

### 2.3 战前技能配置

HBR 另有战前技能设置：

- 被动技能：在角色技能设置界面分配到技能槽，被动技能自动生效，不能在战斗中作为主动技能选择。
- EX 技能：需要习得并装备后，才可以在战斗中使用。
- 排轴主动技能：战斗中逐回合选择；战前阶段检查角色/战型是否拥有该技能，以及 EX 技能是否满足装备条件。

官方帮助文档：
- [被动技能设置](https://wfs-heaven-burns-red.zendesk.com/hc/ja/articles/35138394732441-%E3%83%91%E3%83%83%E3%82%B7%E3%83%96%E3%82%B9%E3%82%AD%E3%83%AB)：菜单 -> 部队 -> 角色 -> 技能设置 -> 技能槽 -> 被动技能。
- [EX 技能](https://wfs-heaven-burns-red.zendesk.com/hc/ja/articles/35139098350105-EX%E3%82%B9%E3%82%AD%E3%83%AB)：EX 技能需习得并装备后才可使用。

## 3. PreparationPlan

从 BattlePlan 编译出独立 PreparationPlan：

- PartyProfile：每个被引用 AxleTool teamTab 对应一个目标队伍档案。
- PartyMemberSpec：槽位、角色、战型、被动技能、共鸣支援和养成参考状态。
- RequiredSkill：从所有行动行汇总的主动技能要求，按 character + style + skill value 去重。
- PreparationDiff：当前游戏配置与目标配置之间的差异。
- PreparationReport：已完成修改、未完成项、阻塞原因和截图证据。

RequiredSkill 需要由 AxleCatalog 解析为 normal、EX、switch、command 等类型；未知类型不能自动调整。

## 4. 多个 AxleTool Tab

一个排轴文件可能引用多个 selectedTab。必须分别生成 PartyProfile，不能把多个 Tab 的六人阵容合并。

1. 收集行动轴实际引用的 selectedTab。
2. 为每个 Tab 构建独立 PartyProfile。
3. 分析每个行动行和 Switch 标记引用的 profile。
4. 单 profile 可直接作为目标编队。
5. 多 profile 时展示 profile 与行动行映射，并要求确认游戏中的切队方式。
6. 不得仅凭 AxleTool 的 Switch 标签推断游戏内切队动作；其语义和时机必须实测。

首版优先支持单个 profile。多 profile 的自动切换放在后续专项阶段。

## 5. 战前配置执行顺序

所有调整均采用“识别当前状态 -> 计算差异 -> 执行单项修改 -> 重新识别验证”。

### 5.1 角色、战型和位置

- 识别当前六个槽位。
- 对比 PartyProfile 的 slot、character_id 和 style_id。
- 处理空位、角色不匹配和位置不匹配。
- 角色正确但战型不同，则切换战型。
- 每次修改后重新识别角色身份和战型标记。
- 未持有角色、未解锁战型或识别不唯一时暂停，不以相似角色代替。

### 5.2 被动技能

- 从 PartyMemberSpec.passive_skills 读取目标列表。
- 打开角色技能设置界面，识别各技能槽及当前被动技能。
- 用 AxleCatalog 将 value 解析为游戏界面名称/图标。
- 逐槽调整并验证最终已装备集合。
- 被动未习得、技能槽不足或识别不确定时暂停。
- 上游数组未提供明确 slot ID，不得假定数组顺序无歧义对应游戏技能槽。需经上游数据语义和游戏界面实测确认；无法确认时让用户选择槽位映射。

### 5.3 主动技能和 EX 技能

- 汇总所有行动行的 skill value，按 character + style 去重。
- 用 AxleCatalog 解析技能类型和所属战型。
- 检查指定角色/战型是否习得对应技能。
- EX 技能需检查是否装备；未装备时进入技能设置界面调整并验证。
- 普通主动技能若由当前战型自动提供，则不伪造预装备步骤，只需确认战斗时确实可选。
- Switch Skill、Command Skill、形态限定技能必须由 Catalog 明确分类；未知类型暂停。

行动轴中的 target 属于战斗时目标选择，不属于战前配置。

### 5.4 共鸣支援

将 support 解析为 ResonanceSupportSpec，对比当前共鸣支援角色、战型和槽位关系。若当前客户端 UI 支持对应设置，则逐项调整并验证；无法确认时列为人工确认项。

### 5.5 养成和装备快照

rank、flower、earring、spiritual、reincarnation 首版只核对并报告差异，不自动执行突破、转生、饰品强化或其他消耗资源的动作。

## 6. 差异计算与幂等性

PreparationPlanner 构建目标状态，PreparationDiff 比较当前状态和目标状态，PreparationExecutor 只执行差异项：

- 已符合目标：不操作。
- 不同且可安全修改：执行并验证。
- 当前状态未知：重新识别，不猜测。
- 目标不可实现：标记 blocker 并暂停。
- 修改后仍不匹配：停止准备流程，保存截图和诊断。

禁止每次导入排轴都无条件重置整支队伍。

## 7. 战前状态门禁

PreparationStatus：NOT_STARTED、ANALYZING、NEEDS_USER_INPUT、APPLYING、VERIFYING、READY、BLOCKED、FAILED。

只有 READY 可以解锁开始战斗。必要条件：

1. 六个角色槽位与选定 PartyProfile 一致。
2. 指定角色战型一致。
3. 要求的被动技能已装备并验证。
4. 排轴主动技能已习得且可用；需要装备的 EX 技能已装备。
5. 共鸣支援要求已验证，或用户明确确认不适用。
6. 没有未处理的未知字段、角色缺失或技能不可用 blocker。
7. 最终编队截图/识别报告已保存。

进入战斗后仍需 BattleAnalyzer 独立确认战斗状态，不能把 READY 当作战斗已启动的证明。

## 8. 用户交互

战前预览展示：AxleTool Tab/profile、六个角色位置和战型、当前与目标差异、每位角色被动技能、排轴主动技能及 EX 装备状态、共鸣支援、未解决 blocker。

默认先生成差异预览，用户确认后执行。角色替换、被动技能更改和 EX 装备等操作逐项展示验证结果。未得到用户确认前不自动开始战斗。

## 9. 测试与验收

- 使用 AxleTool fixture 测试 PartyProfile 六人槽位、被动技能和 support 解析。
- 使用固定游戏截图测试当前队伍和技能设置读取。
- 使用 FakeDevice / FakeVision 测试差异计算、操作顺序、幂等性和 blocker。
- 对角色替换、战型切换、被动技能槽设置和 EX 技能装备建立截图回归集。
- 设备测试先 dry-run，再逐项人工确认。
- 测试“配置已经正确”的二次运行，确认不会重复修改。
- 测试角色缺失、技能未习得、技能槽不足、未知 profile 和 Switch 等异常路径。
