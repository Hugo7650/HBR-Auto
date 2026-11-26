# ADR-0005：战前编队和技能配置准备阶段

- 状态：Accepted
- 日期：2026-11-26

## 背景

AxleTool 导出数据不只是每回合的技能行动轴。char 字段还记录队伍 Tab 下的六个角色槽位、战型、被动技能、共鸣支援和若干养成状态。skills / turns 则记录战斗中每回合的主动技能和目标。

若导入后直接运行 BattlePlan，会遗漏战前编队和技能配置，导致计划引用的角色、战型或技能在实际战斗中不存在或不可用。

HBR 官方帮助文档明确说明被动技能需要通过菜单的部队/角色/技能设置界面装配到技能槽；EX 技能习得后还需要装备才能使用。

## 决策

- 在 BattlePlanImporter 与 BattlePlanRunner 之间增加 PreBattlePreparation 阶段。
- 从 BattlePlan 编译出一个或多个 PartyProfile，以及 RequiredSkill 集合。
- PartyProfile 管理六个角色槽位、角色身份、战型、被动技能和共鸣支援。
- RequiredSkill 从所有行动行汇总，管理排轴会使用的主动技能要求；EX 技能额外检查装备状态。
- 将角色/战型/被动技能/EX 技能/共鸣支援的当前状态与目标状态进行差异比较。
- 首版支持差异预览、dry-run 和逐项验证；未完成验证前禁止开始战斗。
- rank、flower、earring、spiritual、reincarnation 等养成/装备快照首版只报告差异，不自动消耗资源修改。
- 多个 AxleTool team Tab 保留为多个独立 PartyProfile；Tab 不映射为游戏内队伍预设 ID。多 profile 的切换语义需专项验证。
- 行动轴中的 target 属于战斗动作，不属于战前配置。
- 当角色、战型、技能或目标配置不可用/未知时默认暂停，不擅自替换。

## 后果

- 用户导入排轴后，在开战前能看到并校准队伍和技能配置。
- 新增 PreBattlePreparation、PartyProfile、RequiredSkill、PreparationDiff 和 PreparationReport 等领域模型。
- 需要额外识别游戏队伍页面、角色详情和技能设置界面。
- 自动配置必须是幂等的，并在每项变化后重新截图验证。
- 首版不能自动处理未确认语义的 Switch 或多 profile 切换。

## 官方参考

- [HBR 官方被动技能说明](https://wfs-heaven-burns-red.zendesk.com/hc/ja/articles/35138394732441-%E3%83%91%E3%83%83%E3%82%B7%E3%83%96%E3%82%B9%E3%82%AD%E3%83%AB)
- [HBR 官方 EX 技能说明](https://wfs-heaven-burns-red.zendesk.com/hc/ja/articles/35139098350105-EX%E3%82%B9%E3%82%AD%E3%83%AB)
- [AxleTool 数据压缩源码](https://github.com/FuseFairy/HBR-AxleTool-vue/blob/d684896639a36f679707d5368f85abbe9a2acced/src/utils/axle/compressAxleData.js)
