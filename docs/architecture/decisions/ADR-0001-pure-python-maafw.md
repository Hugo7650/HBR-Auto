# ADR-0001：纯 Python 编排，MaaFramework 作为底层引擎

- 状态：Accepted
- 日期：2026-11-26

## 背景

项目需要长期维护日常、战斗、迷宫和活动等多种玩法。若将业务流程写入 JSON Pipeline，流程、状态、策略和任务调度会分散在不同表达方式中，不利于复杂玩法的测试、复用和调试。

## 决策

- 所有业务流程、任务调度、状态机、导航、策略和异常恢复均使用 Python 编写。
- 不使用 JSON Pipeline，不调用 Tasker.post_task() 执行业务流程。
- MaaFramework 仅提供设备 Controller、截图、Resource 生命周期和 Native Vision 能力。
- 识别通过 Tasker.post_recognition() 独立调用；需要单项 MAA Action 时，也必须由 Python 显式编排并经 Adapter 暴露。
- Resource 不加载 Pipeline Bundle，只加载项目视觉功能需要的图片和模型。
- MaaRuntime 统一创建、绑定和释放 Resource、Controller、Tasker。

## 后果

优点：

- 游戏流程和业务逻辑只有 Python 一种语言。
- 可以使用常规 Python 类型、调试器、测试工具和依赖注入。
- 设备和视觉能力可以封装为接口，减少对 MaaFramework 内部类型的耦合。

成本：

- 页面流程、重试、等待、依赖和调度都需要自行实现。
- 需要自行维护识别结果标准化、设备队列和任务日志。
- 应用需要对 MAA 的异步 Job 进行有序等待和错误处理。

## 约束

业务模块不得直接 import maa.*。只有 core/runtime、core/device 和 core/vision 的 Maa 实现适配器允许依赖 MaaFramework Python Binding。
