# HBR-Auto

面向《Heaven Burns Red / 绯染天空》的模块化 Python 自动化项目。

## 当前技术路线

- **自动化底座**：MaaFramework 5.16.1，使用 Python Binding。
- **流程控制**：纯 Python；不使用 JSON Pipeline。
- **视觉识别**：优先使用 MaaFramework Native Vision，通过 Python Adapter 暴露统一接口。
- **战斗计划**：支持导入 HBR-AxleTool-vue 导出的 JPEG 排轴图片，从 EXIF `ExifIFD.UserComment` 读取压缩数据，解析为内部 BattlePlan。
- **战前准备**：根据排轴中的队伍档案、角色、战型、被动技能和行动技能需求，生成编队及技能差异方案；校验通过后才允许开战。
- **Python 与依赖管理**：uv；目标解释器 Python 3.15.2。
- **首要平台**：Android / 模拟器 ADB；设备层保留后续扩展其他 Controller 的接口。

## 文档

- [架构总览](docs/architecture/overview.md)
- [技术决策记录（ADR）](docs/architecture/decisions/README.md)
- [AxleTool 排轴格式与导入设计](docs/battle/axletool-import.md)
- [战前编队与技能准备设计](docs/battle/prebattle-preparation.md)
- [BattlePlan 与战斗执行设计](docs/battle/plan-execution.md)
- [开发环境与 uv 工作流](docs/development/setup.md)
- [开发路线图](docs/roadmap.md)

## 当前阶段

当前先落实架构与设计文档、Python/uv 项目元数据和开发约定。尚未实现设备控制、视觉调用、排轴解析、战前编队调整或游戏内操作；文档中的代码职责和接口属于设计约定，不代表已有可运行实现。

## 设计原则

1. MaaFramework 提供设备和原生视觉能力；Python 控制所有业务流程。
2. 游戏业务不得直接依赖 MaaFramework 的具体类型，统一经由 Device / Vision Adapter。
3. 所有识别结果先验证，再执行有副作用的输入。
4. 排轴数据是计划，不是盲目点击序列；运行时状态与计划不一致时默认暂停。
5. 战斗前先将当前队伍及技能配置与排轴进行差异比较，逐项修改并验证。
6. 业务模块按功能拆分，任务调度、场景管理、视觉、状态和恢复机制彼此解耦。
7. 仅使用正常画面识别与设备输入，不采用进程注入、内存修改或协议绕过。

## 状态

设计与项目脚手架阶段。后续实现以文档中的 ADR 和接口边界为准。
