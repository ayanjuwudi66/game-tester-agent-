# 用例流水线（Test Case Pipeline）

把需求文档端到端转为结构化测试用例 CSV 的九阶段流水线专家。

## 类型

Agent 型（单个 AI 专家）

## 功能

由 iWarden 的 16 个原子 skill 整合而成的**单一分层 skill**，把原来依赖模型自觉加载的「软调度」链路，改写为 SKILL.md 内硬编码的九阶段流程。

| 阶段 | 职责 | 产出 |
|:---:|---|---|
| 1 | 扫描与归档（file-scanner） | 文件清单 + 归档目录 |
| 2 | 多模态解析（multimodal-parser） | 带置信度与来源标注的内容 |
| 3 | 需求整理（requirement-organizer） | 需求整理报告.md |
| 4 | 功能点拆分（feature-splitter） | 功能点列表.md |
| 5 | 测试点拆分（testpoint-splitter） | 测试点列表.md（六列表格） |
| 6 | 六类用例生成（core / boundary / exception / traverse / interrupt） | 测试用例_模块/*.jsonl |
| 7 | 门控校验 | 覆盖率报告（阻断性） |
| 8 | 九维评审（testcase-reviewer） | 评审报告.md |
| 9 | 聚合导出（aggregator → md2csv） | CSV + 测试用例聚合报告.md |

**旁路**：prd-decompose 可生成 PRD 基线三文档，供评分阶段做覆盖度 / 边界 / UI 比对。

### 目录分层

- `SKILL.md` —— 编排层，常驻上下文，只放流程与契约（不放具体规则）
- `references/` —— 细则层，按阶段按需读取（16 份内容全文保留）
- `scripts/` —— 可执行脚本（聚合、转换、校验、docx 解析）

### 分类体系

HX（核心）/ FHX（非核心）/FCG（非常规） BJ（边界）/ YC（异常）/ BL（遍历）/ ZD（中断）

## 使用示例

- 把这份需求文档跑一遍完整流水线，导出测试用例 CSV
- 先拆解这份 PRD 的功能点和测试点，我确认后再生成用例
- 评审已生成的测试用例，找出漏测点和重复用例

## 已知状态与缺口

| 项 | 状态 |
|---|---|
| `profiles.yaml` 的 `active_profile` | 当前为 `C_debug`（调试用九列，**非交付格式**）。正式交付前需确认为 `A_legacy` 或 `B_new` |
| `references/文字输入框通用用例.md` | 被引用但源包中不存在，遇输入框场景按通用撰写规范自行设计 |
| `scripts/md2csv_template.py` | 被文档引用但源包中不存在，当前无实际依赖 |
| PyYAML | `profiles.yaml` 生效的运行时依赖；缺失时回落内嵌 fallback（三个 profile 仍完整可用） |

## 头像

头像已自动生成在 `avatars/` 目录下。如需替换为自定义头像，要求：
- 格式：PNG（推荐）或 JPG
- 尺寸：512×512 px
- 大小：单张不超过 500KB

## 安装

将专家包目录放到专家目录下：

```
C:\Users\v_shiyning\.workbuddy\plugins\marketplaces\my-experts\plugins/testcase-pipeline/
```

然后运行注册命令使其可见：

```bash
python3 scripts/register_expert.py <expert-dir>
```

## 打包分享

```bash
zip -r testcase-pipeline.zip testcase-pipeline/
```
