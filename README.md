# HBR-Auto

面向《Heaven Burns Red / 绯染天空》的模块化 Python 自动化项目。

## 当前技术路线

- **自动化底座**：MaaFramework 5.16.1，使用 Python Binding。
- **流程控制**：纯 Python；不使用 JSON Pipeline。
- **视觉识别**：优先使用 MaaFramework Native Vision，通过 Python Adapter 暴露统一接口。
- **战斗计划**：支持导入 HBR-AxleTool-vue 导出的 JPEG 排轴图片，从 EXIF `ExifIFD.UserComment` 读取压缩数据，解析为内部 BattlePlan。
- **Python 与依赖管理**：uv；目标解释器 Python 3.15.2。
- **首要平台**：Android / 模拟器 ADB；设备层保留后续扩展其他 Controller 的接口。

## 文档

项目设计、技术决策、AxleTool 数据格式、开发环境和路线图见：

- [架构总览](docs/architecture/overview.md)
- [技术决策记录（ADR）](docs/architecture/decisions/README.md)
- [AxleTool 排轴格式与导入设计](docs/battle/axletool-import.md)
- [战斗排轴执行设计](docs/battle/plan-execution.md)
- [开发环境与 uv 工作流](docs/development/setup.md)
- [开发路线图](docs/roadmap.md)

## 当前阶段

当前先落实架构与设计文档、Python/uv 项目元数据和开发约定。尚未实现设备控制、视觉调用、排轴解析或游戏内操作；文档中的代码职责和接口属于设计约定，不代表已有可运行实现。

## 设计原则

1. MaaFramework 提供设备和原生视觉能力；Python 控制所有业务流程。
2. 游戏业务不得直接依赖 MaaFramework 的具体类型，统一经由 Device / Vision Adapter。
3. 所有识别结果先验证，再执行有副作用的输入。
4. 排轴数据是计划，不是盲目点击序列；运行时状态与计划不一致时默认暂停。
5. 业务模块按功能拆分，任务调度、场景管理、视觉、状态和恢复机制彼此解耦。
6. 仅使用正常画面识别与设备输入，不采用进程注入、内存修改或协议绕过。

## 状态

设计与项目脚手架阶段。后续实现以文档中的 ADR 和接口边界为准。
