---
name: testcase-pipeline
description: 游戏测试用例生成流水线。把需求文档（PRD / 策划案 / 原型 / Figma 导出 / 配置表）端到端转为结构化测试用例 CSV。触发场景：生成测试用例、拆解功能点、拆解测试点、评审用例漏测、导出用例 CSV、跑完整测试用例流水线。
---

# 测试用例生成流水线

把需求文档端到端转为结构化测试用例 CSV。九阶段串行，每阶段有固定输入输出契约。

## 一、路径约定

| 占位符 | 含义 |
|---|---|
| `{SKILL_DIR}` | 本 skill 根目录（`skills/testcase-pipeline/`） |
| `{归档目录}` | `output/{需求名}_{YYYYMMDDHHmm}/`，由阶段 1 建立，**全流程唯一交付载体** |

- 脚本目录：`{SKILL_DIR}/scripts/`
- 细则目录：`{SKILL_DIR}/references/`

---

## 二、加载策略（渐进式披露）

本 SKILL.md 常驻上下文，**只承载编排**，不放具体规则。细则按需读取：

| 时机 | 读取 |
|---|---|
| 进入任何生成阶段前（**强制**） | `references/_shared_conventions.md` |
| 执行阶段 N | `references/stage-0N-*.md` |
| 需要表头 / 字段 / 分类定义 | `references/profiles.yaml`（机读权威源） |
| 需要文档视角核对 | `references/_shared_conventions.md §1`（文档镜像） |

**双源冲突时以 `profiles.yaml` 为准。**

---

## 三、九阶段编排

| 阶段 | 职责 | 输入 | 输出 | 细则 |
|:---:|---|---|---|---|
| 1 | 扫描与归档 | 需求目录 | 文件清单 + 归档目录 | `stage-01-file-scanner.md` |
| 2 | 多模态解析 | 文件清单 | 带置信度与来源标注的内容 | `stage-02-multimodal-parser.md` |
| 3 | 需求整理 | 解析内容 | `需求整理报告.md` | `stage-03-requirement-organizer.md` |
| 4 | 功能点拆分 | 需求整理报告 | `功能点列表.md` | `stage-04-feature-splitter.md` |
| 5 | 测试点拆分 | 功能点列表 | `测试点列表.md`（六列） | `stage-05-testpoint-splitter.md` |
| 6 | 用例生成（调度） | 测试点列表 | `测试用例_模块/*.jsonl` | `stage-06-testcase-generator.md` |
| 7 | 门控校验 | JSONL 集合 | 覆盖率报告 | `stage-06-testcase-generator.md` §门控 |
| 8 | 评审 | CSV + 用例集 | `评审报告.md` | `stage-12-testcase-reviewer.md` |
| 9 | 聚合导出 | JSONL + 功能点列表 | CSV + `测试用例聚合报告.md` | `stage-13` / `stage-14` |

### 阶段 6 的五个并列生成器（按模块纵切）

对**每个模块**依次跑完，后续分类参考前序分类避免重复：

| 顺序 | 生成器 | 分类 | 细则 |
|:---:|---|---|---|
| ① | testcase-core | HX + FHX | `stage-07-testcase-core.md` |
| ② | testcase-boundary | BJ | `stage-08-testcase-boundary.md` |
| ③ | testcase-exception | **YC + FCG** | `stage-09-testcase-exception.md` |
| ④ | testcase-traverse | BL | `stage-10-testcase-traverse.md` |
| ⑤ | testcase-interrupt | ZD | `stage-11-testcase-interrupt.md` |

全部以 append 模式写入 `{归档目录}/测试用例_模块/{模块名}.jsonl`，并更新 `temp/_progress.json` 以支持断点续跑。

### 旁路：PRD 基线拆解

需要与 PRD 做覆盖度 / 边界 / UI 比对时，先执行 `stage-15-prd-decompose.md`，产出功能点文档、配置设计文档、UI 元素文档三份基准，供阶段 8 评审使用。

---

## 四、数据契约

### 归档目录结构

```
{归档目录}/
├── 需求整理报告.md
├── 功能点列表.md
├── 测试点列表.md
├── 测试用例_模块/
│   └── {模块}.jsonl
├── {需求名}_{YYYYMMDDHHmm}.csv
├── 测试用例聚合报告.md
├── 评审报告.md                 （可选）
└── temp/
    ├── _stats.json
    ├── _validate_report.json
    ├── _progress.json
    └── _review_data.json       （可选）
```

### JSONL 字段（每个生成器输出）

必填 8 项：`submodule / feature_point / testpoint / case_desc / precondition / steps / expected / category`

- `module` 可省略，由文件名兜底
- `feature_point` = 测试点表格第 2 列「功能点描述」，同子模块内取值一致
- 多步骤用 `\n` 换行，禁用 `<br>`
- **JSONL 必须 UTF-8 无 BOM**（写入方式只有 append）

### 编码与表头

- **CSV 必须 UTF-8 BOM**
- 表头 profile 三选一：`A_legacy` / `B_new` / `C_debug`
- `C_debug` 为调试用九列全集（含 `case_desc` + `feature_point`），**非交付格式**
- 归档目录名带 `_debug` 后缀时启用 `C_debug`

---

## 五、门控（阻断性，不可绕过）

进入阶段 9 前，两项必须同时通过：

| 门控 | 阈值 | 不通过的处理 |
|---|---|---|
| 测试点-分类覆盖率 | ≥ 90% | 回溯对应生成器补全后重查 |
| 总用例数 | ≥ 测试点数 × 2.5 | **直接告知用户「未过门控」**并附实测值；不自动补用例、不跳阶段 |

> **统计口径**：覆盖率统计**不含 FCG** —— FCG 属建议层，出不出都不卡门控（详见 `stage-06` 门控1）。

回溯优先级与阈值明细见 `references/_shared_conventions.md §11`。

---

## 六、分类体系与占比基准

| 分类 | 含义 | 健康区间 |
|---|---|---|
| HX | 核心功能用例 | 20~35%（不设下限） |
| FHX | 非核心功能用例 | 12~21% |
| BJ | 边界场景 | 14~23% |
| YC | 异常操作 | 8~15% |
| FCG | 玩家非常规操作 | 2~13% |
| BL | 功能遍历 | 9~14% |
| ZD | 中断场景 | 5~13% |

- **区间为提示性（黄灯），非门控**：落在区间外只提示关注，**不判不通过、不触发回溯补用例**；禁止按百分比反推补用例。
- **HX 不设下限**：判据是**流程位置**（所有玩家必经路径），占比由主链必经节点数决定，**HX 低 ≠ 覆盖不足**。
- **FCG** = 操作本身合法、但执行方式不正常（连点 / 反复 / 未就绪 / 乱序），与 YC（动作本身不该发出）、ZD（动作发出后被切断）互斥。
- **用例数门控（唯一判据）**：**总用例数 ≥ 测试点数 × 2.5**；判不过**直接告知用户「未过门控」**，不自动补用例。

---

## 七、铁律

1. **先拿材料再动手**：未拿到需求材料前，禁止产出通用模板或示例用例。
2. **绝不篡改原材料**：用户原始表述原样引用并标注出处；主动补充的内容单独成节，全部标记「待确认」。
3. **不臆造**：图片中无任何线索的功能一律不补。任何一张图没读全，必须当场告知用户，不得含糊带过。
4. **数值具体化**：禁用"若干""一定时间"等模糊表述。
5. **UI 走查排除**：不生成纯样式类用例（尺寸、颜色、字号、圆角）。
6. **未拍板项不外泄**：一律单列《待确认项清单》，不得在用例预期中写死推断值。
7. **门控不可绕过**：覆盖率或用例数不达标时，禁止跳到聚合阶段。
8. **边界**：只做功能与玩法测试设计。性能、安全、兼容性、数值平衡四类专项不覆盖，观察到风险记录并转交对应专项组。

---

## 八、已知状态与缺口（迁移时确认，务必留意）

| 项 | 状态 | 处理建议 |
|---|---|---|
| `profiles.yaml` 的 `active_profile` 当前为 **`C_debug`** | 非交付格式（九列含调试字段） | 正式交付前确认为 `A_legacy` 或 `B_new`，或在归档目录名加 `_debug` 后缀以显式启用调试模式 |
| `references/文字输入框通用用例.md` | 被 `stage-07` / `stage-06` 引用，但**源包中不存在** | 遇输入框相关测试点时，按 `_shared_conventions.md` 通用撰写规范自行设计，不要中断流程 |
| `scripts/md2csv_template.py` | 被文档引用，但**源包中不存在** | 当前无实际依赖，忽略即可 |
| PyYAML | `profiles.yaml` 生效的运行时依赖 | 缺失时脚本自动回落内嵌 fallback（三个 profile 均完整），功能不受影响，但 yaml 覆盖机制失效 |
