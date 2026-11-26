# ADR-0002：优先使用 MaaFramework Native Vision

- 状态：Accepted
- 日期：2026-11-26

## 背景

HBR 的玩法需要按钮和图标匹配、OCR、场景与角色识别以及状态判断。MaaFramework 已提供多种内置识别器和 Python 独立识别接口。若同时维护独立 OpenCV 模板库和 OCR 引擎，会造成配置、结果类型、坐标处理和调试链路重复。

## 决策

第一阶段优先通过 MAA Python Binding 调用 Native Vision：

- TemplateMatch：按钮、图标和稳定 UI 标记。
- OCR：页面文本、任务名称和游戏内可读数值。
- FeatureMatch / ColorMatch：在适用场景使用。
- NeuralNetwork：经模型和实际游戏截图验证后用于分类或检测。
- And / Or：由 Python 组合多个识别调用；若锁定版本的参数 API 适用，也可使用 MAA 组合识别类型。

通过 VisionInterface 和 MaaVision 隔离实际的 MAA 参数对象与结果类型。业务层只接收项目定义的 RecognitionResult、TextResult 等对象。

暂不把 Airtest / Poco 引入核心，也不将独立 OpenCV / PaddleOCR 作为默认视觉栈。若某项能力经验证无法由 MAA 满足，再以独立 Adapter 补充，不让业务直接依赖第三方实现。

## 后果

- 使用同一套识别资源、日志和 MAA 调试能力。
- 业务接口保持稳定。
- 减少重复 OCR 和模板匹配实现。

成本和风险：

- 需要锁定 MaaFw 版本，并针对 5.16.1 验证实际识别参数与结果模型。
- 需要维护 MAA 图片资源、OCR 模型和 ROI 坐标规范。
- Python 3.15 与 MAA 运行时的兼容性必须通过实际导入及设备冒烟测试确认。

## 参考

- [MaaFramework Python Binding](https://github.com/MaaXYZ/MaaFramework/tree/v5.16.1/source/binding/Python/maa)
- [Tasker API](https://github.com/MaaXYZ/MaaFramework/blob/v5.16.1/source/binding/Python/maa/tasker.py)
- [MaaFramework Releases](https://github.com/MaaXYZ/MaaFramework/releases)
