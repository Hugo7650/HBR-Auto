# ADR-0004：将 AxleTool 排轴图片作为战斗计划输入

- 状态：Accepted
- 日期：2026-11-26

## 背景

HBR-AxleTool-vue 支持将队伍和行动轴导出为 JPEG。导出器把结构化排轴数据压缩后写入 EXIF ExifIFD.UserComment。数据包含队伍、角色、战型、回合、OD、技能和目标字段。

## 决策

- 战斗模块提供独立 AxlePlanImporter，读取 JPEG EXIF UserComment、解压 LZ-String Base64 并解析 JSON。
- 导入数据先经过版本迁移、字段规范化和完整校验，再转换为内部 BattlePlan。
- 战斗执行器只消费 BattlePlan，不直接读取 AxleTool 原始 JSON。
- 原始排轴图片和导入记录可关联保存，供回归测试和问题排查。
- 首版采用严格执行模式。当前队伍、回合、技能或目标与计划不一致时暂停。
- AxleTool 角色技能目录用于补足导出数据中未携带的技能展示名和 SP 元信息，但必须固定来源版本并保留上游许可与来源说明。

## 后果

- 用户可以复用现有排轴社区工具，不需要在本项目再做排轴编辑器。
- 导入器需要兼容 AxleTool 格式版本，不能将外部 JSON 直接视为稳定内部 API。
- 目标执行仍需通过实时游戏画面把排轴中的角色标识映射为当前可选对象。
- Switch、追加回合和 OD Bonus 等特殊指令必须按实际游戏行为单独验证，不能按普通回合或普通技能猜测处理。

## 参考实现

基于 HBR-AxleTool-vue 的以下源码快照进行格式分析：

- Repository: https://github.com/FuseFairy/HBR-AxleTool-vue
- Analyzed commit: d684896639a36f679707d5368f85abbe9a2acced
- [图片导出 domToImage.js](https://github.com/FuseFairy/HBR-AxleTool-vue/blob/d684896639a36f679707d5368f85abbe9a2acced/src/utils/browser/domToImage.js)
- [数据压缩 compressAxleData.js](https://github.com/FuseFairy/HBR-AxleTool-vue/blob/d684896639a36f679707d5368f85abbe9a2acced/src/utils/axle/compressAxleData.js)
- [数据解压 decompressAxleData.js](https://github.com/FuseFairy/HBR-AxleTool-vue/blob/d684896639a36f679707d5368f85abbe9a2acced/src/utils/axle/decompressAxleData.js)
