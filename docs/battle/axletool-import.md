# AxleTool 排轴图片导入设计

> 格式分析基准：HBR-AxleTool-vue commit d684896639a36f679707d5368f85abbe9a2acced；该快照 package.json 版本为 1.0.1。上游格式改变时，必须重新检查导出和解压源码，并增加 fixture。

## 1. 用户体验

1. 用户选择 AxleTool 导出的 JPG/JPEG。
2. 本地读取 EXIF ExifIFD.UserComment。
3. 使用与 JavaScript lz-string@1.5.0 兼容的 LZ-String Base64 解压算法。
4. 验证 JSON 结构和格式版本。
5. 执行迁移与规范化，形成内部 BattlePlan。
6. 显示排轴预览和校验报告。
7. 用户确认后才允许进入战斗执行阶段。

图片本身用于预览和留档；排轴语义从 EXIF 元数据读取。不得把 OCR 识别图片上的文字作为权威数据源。

## 2. 上游导出链路

当前上游源码的导出逻辑：

1. compressAxleData() 生成 customData。
2. JSON.stringify(customData)。
3. LZString.compressToBase64(jsonString)，依赖 lz-string ^1.5.0。
4. 将压缩字符串写入 ExifIFD.UserComment。
5. 通过 piexif.dump() 创建 EXIF 数据。
6. 通过 piexif.insert() 将 EXIF 数据写入 JPEG。

导入时必须使用 LZ-String 的 Base64 专用解压函数，不是普通 Base64 解码，也不是 UTF-16 解压函数。

## 3. 顶层数据结构

当前 compressAxleData.js 输出字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| version | string | 排轴保存格式版本；当前源码由 package version 写入，分析快照为 1.0.1 |
| char | object | 排轴实际使用的队伍及角色槽位信息 |
| axleName | string | 排轴名称 |
| skills | array[array[object]] | 每行三个行动槽位的数据 |
| turns | array[object] | 每行回合和 OD 标记，与 skills 行索引对应 |
| rows | number | 行数 |
| language | string | AxleTool 界面技能语言标记 |

turns 导出时会去掉内部临时 id 字段。

## 4. 队伍与角色

char 结构：

    char
    └── "<teamTab>"
        ├── "<slot 1>"
        ├── "<slot 2>"
        └── ... "<slot 6>"

队伍 Tab 与游戏内部部队标识不是同一个概念：

- teamTab 是 AxleTool 队伍页签编号，作为 skills[row][slot].selectedTab 的引用键。
- 角色选择数据中的 team 表示角色所属的游戏部队或队伍分类。
- 槽位 key 是角色在该 Tab 中的位置。

角色选择记录包含（字段可能因历史数据版本而异）：

- character：角色标识。
- team：角色数据所属队伍分类。
- style、style_id：战型标识。
- rank、flower、passiveSkill。
- earring、spiritual、reincarnation。
- support：共鸣支援信息，包含 team、character、style、style_id、rank 等字段。

导出会从角色槽位副本中删除 skill、passiveSkill_value、character_info 和 commandSkill，因此这些字段不能假定一定存在。

getUsedTeams() 从行动槽位的 selectedTab 收集实际使用的 Tab；未被行动轴引用的其他队伍可能不会写入导出数据。

## 5. 回合与行动槽位

skills 为二维数组，结构是 skills[rowIndex][actionSlot]。当前编辑器每行初始化三个行动槽位，索引为 0、1、2。

行动槽位主要字段：

| 字段 | 说明 |
|---|---|
| selectedTab | 对应 char 的队伍 Tab key |
| style | 该动作使用的战型 |
| style_id | 战型数据 ID；历史格式可能缺失 |
| activeFormId | 多形态战型当前形态；历史格式可能缺失 |
| style_img | AxleTool 预览资源路径，不是游戏内角色身份的权威字段 |
| skill | 所选技能的 value 字符串，不是本地化显示文字 |
| target | 目标角色选项的 value；需在当前队伍中解析 |
| is1Damage | 伤害上限标记，布尔值 |

turns[rowIndex] 与 skills[rowIndex] 通过相同索引对应。常见字段：

- turn：T1 至 T80、Switch、追加回合或空值。
- od：OD 指令，如 OD1、OD1/Bonus1、OD2 至 OD5/Bonus3，也可能为空值。

AxleTool 在将回合改为 Switch 时，会清空该行三个行动槽位并清除 OD。项目必须保留这个特殊行标记，不应擅自把它当成普通技能回合。其游戏内实际语义由后续战斗专项测试确认。

## 6. EXIF 与解压规则

推荐依赖：

- piexif：读取 JPEG EXIF。
- py-lzstring：兼容 JavaScript lz-string 1.5.0 的 Python 实现。

逻辑步骤：

    JPG/JPEG
      -> EXIF ExifIFD.UserComment
      -> 取得字符串或字节并规范化
      -> 若存在标准 UserComment ASCII 编码前缀则去除
      -> LZ-String decompress_from_base64
      -> JSON parse
      -> schema check
      -> version migration
      -> normalized BattlePlan

上游当前通过 piexifjs 将压缩字符串直接赋给 UserComment。实现时应针对真实上游 JPG fixture 确认 Python piexif.load() 返回的类型和内容。不要无条件剥离前缀；只有确认存在 ASCII\0\0\0 前缀时才去除。

LZ-String 的 Base64 字符串不是让应用自行用 base64.b64decode 解码后当作 JSON。应调用 LZ-String 对应解压 API。

## 7. 版本迁移与兼容策略

当前上游解压代码要求格式版本至少为 1.0.0。它对低于 1.0.1 的历史数据补充或迁移 style_id 和 activeFormId；并对旧数据补齐 support、is1Damage 等默认值。

本项目策略：

- 以 version 选择显式迁移函数，例如 migrate_1_0_0_to_1_0_1。
- 规范化后的内部模型独立使用本项目自己的 schema version。
- 已知旧版本：迁移并产生警告清单。
- 当前支持版本：直接解析。
- 未知未来版本：拒绝导入并提示更新解析器，不猜字段含义。
- 不因缺少可选展示字段就丢弃排轴；若缺少角色、技能、回合等关键身份字段则校验失败。

## 8. 角色与技能目录

压缩数据中的 char 记录不包含完整技能选项列表。上游通过角色、队伍分类和战型，从 src/assets/char-data 与 common skill 数据重新获取技能、被动和指挥技能选项。

因此本项目需要一个版本化 AxleCatalog：

- 根据 team / character / style 查找角色和战型元数据。
- 根据行动槽位中的技能 value 解析技能定义与 SP 消耗（如果目录中有提供）。
- 处理通用技能、战型技能、指挥技能和多形态技能。
- 处理多语言名称，但内部使用稳定 value/id，不以展示名作为主键。

角色目录数据的引入和再分发需要单独核对上游 MIT 代码许可及其中游戏素材和数据的权利边界。首版优先实现可替换 Catalog 接口，不在未审核前批量复制上游图片资源。

## 9. 输入安全与校验

JPG 和 EXIF 元数据都视为不可信输入：

- 限制文件大小和解压后 JSON 大小。
- 只接受 JPEG/JPG。
- 检查 EXIF tag 是否存在、类型是否支持。
- 解压失败、JSON 无效、字段类型错误必须给出明确错误。
- 对数组长度、行数、技能槽数量和字符串长度设置上限。
- 校验 teamTab、character、style、skill、target 引用关系。
- 不执行或反序列化 Python 对象；只处理 JSON。
- 未知格式版本 fail closed。

## 10. 导入模块验收

1. 使用真实 AxleTool 导出 JPG fixture，能读取 UserComment。
2. Python 解压结果与浏览器端 decompressFromBase64 解析的 JSON 结构一致。
3. 队伍、角色、回合、OD、技能和目标的数组索引关系保持不变。
4. 空槽位、Switch、追加回合和 OD Bonus 都能无损表达。
5. 不支持的版本和损坏 EXIF 有可读错误。
6. 导入不需要连接 MAA 或启动游戏。
