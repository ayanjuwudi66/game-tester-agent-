---
name: testcase-aggregator
description: 用例聚合编排层。负责前置校验、就地触发 run_pipeline（md2csv + validate）、从 stats.json 汇总聚合报告。所有技术工作（解析/排序/写 CSV/校验）由 md2csv-converter 承担；本 skill 不再复制任何脚本或配置到归档目录。
---

# 用例聚合器 Skill（就地调用式 · 编排层）

## 职责边界

本 skill 是**编排层**，只做 3 件事：

1. **前置校验**：归档目录 MD 源 & 上游 skill 脚本存在
2. **触发运行**：一条命令调用 `run_pipeline.py --archive-dir {归档目录}`
3. **汇总报告**：从 `_stats.json` + `_validate_report.json` 读数据生成聚合报告

**不做**：
- MD 解析 / 用例排序 / feature_point 透传 / CSV 写入 / 表头校验 / BOM 校验 / 行数对比 / 排序验证 — 全部由 `md2csv-converter/scripts/` 承担
- **也不再向归档目录复制 md2csv.py / validate.py / profiles.yaml**（就地调用式改造，见"关键约束"章节）

---

## 前置约定

- 生成器已按 conventions §8.3 append 输出 `测试用例_模块/*.jsonl`（每行一个 JSON 用例对象；UTF-8 无 BOM）
- 存在 `功能点列表.md`（供 md2csv 提取 CSV 模块排序）
- Profile 由 `testcase-conventions/references/profiles.yaml` 决定（全局唯一，脚本按固定路径就地读取）
- 归档目录已在需求阶段建立好（`output/{需求名}_{YYYYMMDDHHmm}[_debug]/`）

---

## 执行流程

### 步骤 1：前置校验

```
□ 检查 归档目录/测试用例_模块/ 存在，且至少有一份非空 *.jsonl 文件
□ 检查 归档目录/功能点列表.md 存在
□ 检查 {SKILL_DIR}/scripts/run_pipeline.py 存在
□ 检查 {SKILL_DIR}/scripts/md2csv.py 存在
□ 检查 {SKILL_DIR}/scripts/validate.py 存在
□ 检查 {SKILL_DIR}/references/profiles.yaml 存在
```

任一失败 → 中止并明确提示缺失文件。

### 步骤 2：触发运行（单条命令）

```powershell
python {SKILL_DIR}\scripts\run_pipeline.py --archive-dir {归档目录}
```

`run_pipeline.py` 会 in-process 顺序执行两步：

1. `md2csv.run(archive_dir)` → `{归档目录}/{需求名}_{YYYYMMDDHHmm}.csv` + `{归档目录}/temp/_stats.json`
2. `validate.run(archive_dir)` → `{归档目录}/temp/_validate_report.json`

**切换 Profile**（默认 `A_legacy`；profile 仅影响最终 CSV 的表头与列裁剪，不需要重跑 JSONL）：
- 归档目录后缀为 `_debug` → `$env:ACTIVE_PROFILE="C_debug"` 后再执行
- 或直接编辑 `testcase-conventions/references/profiles.yaml` 的 `active_profile` 字段（**全局唯一权威源**，永久修改）

**指定其他 profile yaml**（vibe coding 场景）：
```powershell
python {SKILL_DIR}\scripts\run_pipeline.py `
    --archive-dir {归档目录} `
    --profile-yaml {自定义 yaml 路径}
```

**退出码约定**：
| 退出码 | 含义 | 排查方向 |
|---|---|---|
| 0 | md2csv + validate 全成功 | ─ |
| 2 | md2csv 失败（validate 未执行） | 检查 MD 表格格式，看 stderr |
| 1 | md2csv 成功但 validate FAIL | 读 `_validate_report.json` 的 `failed` 数组 |

### 步骤 3：汇总聚合报告

从 `{归档目录}/temp/_stats.json` + `temp/_validate_report.json` 读取，生成 `{归档目录}/测试用例聚合报告.md`：

```markdown
## 测试用例聚合报告

### Profile 元信息
- Profile: {profile} · {profile_label}
- 交付类型: {正式交付 | 非交付（调试）}
- 表头列数: {len(columns)}
- Profile 权威源: {profile_yaml_path}
- 配置源标签: {config_source}   # yaml 或 fallback

### 数据来源
| 来源 | 分类 | 用例数量 |
|------|------|----------|
| testcase-core       | HX + FHX | {source_breakdown.testcase-core} |
| testcase-boundary   | BJ       | {source_breakdown.testcase-boundary} |
| testcase-exception  | YC       | {source_breakdown.testcase-exception} |
| testcase-interrupt  | ZD       | {source_breakdown.testcase-interrupt} |
| testcase-traverse   | BL       | {source_breakdown.testcase-traverse} |
| **合计**            | -        | **{total_cases}** |

### 模块分布
| 模块 | 用例数量 |
|------|----------|
| {module_distribution 遍历} | ... |

### 分类分布
| 分类 | 数量 | 占比 |
|------|------|------|
| {category_distribution 遍历，按 CATEGORY_ORDER} | ... | ... |

### 校验结果
- 总体: {validate_report.overall}
- 通过: {len(validate_report.passed)} 项
- 失败: {len(validate_report.failed)} 项
- 警告: {len(validate_report.warnings)} 项

### 输出文件
| 类型 | 文件 | 说明 |
|------|------|------|
| CSV| {需求名}_{YYYYMMDDHHmm}.csv | UTF-8 with BOM，可导入 Excel |
| MD       | 测试用例_模块/*.jsonl   | 生成器 append 产出，中间产物（保留） |
| Stats    | temp/_stats.json            | 结构化统计（本报告数据源） |
| Report   | temp/_validate_report.json  | 校验结果（本报告数据源） |
```

**不再手工统计任何数字**：所有数字直接读 `_stats.json` 与 `_validate_report.json`。

---

## 目录结构

执行完成后归档目录：

```
{归档目录}/
├── 测试用例_模块/           # 生成器 append 输出（每模块一份JSONL）
│   └── {模块名}.jsonl
├── 功能点列表.md            # feature-splitter 输出
├── 测试点列表.md            # testpoint-splitter 输出
├── {需求名}_{YYYYMMDDHHmm}.csv  # md2csv 输出（UTF-8 BOM，动态命名）
├── 测试用例聚合报告.md      # 本skill 输出
└── temp/                    # 临时产物
    ├── _stats.json          # md2csv 输出（结构化统计）
    └── _validate_report.json# validate 输出（结构化校验结果）
```

**归档目录不再包含** md2csv.py / validate.py / profiles.yaml（就地调用式改造后从上游 skill 直接读取）。

---

## 关键约束

1. **不再复制脚本或配置到归档目录**：所有技术文件保留在上游 skill（`md2csv-converter/scripts/` 与 `testcase-conventions/references/`），run_pipeline 通过 `--archive-dir` 就地处理归档目录内容。此约束是沙箱化 + vibe coding 的前置条件
2. **不做手工排序 / 手工统计 / 手工校验**：所有技术工作由 `run_pipeline.py` 及其子脚本承担
3. **不内嵌 Python 代码**：SKILL.md 严禁抄写 Python 源码；aggregator 只调 CLI
4. **UTF-8 BOM 硬性要求**：由 `md2csv.py` 保证；`validate.py` 显式校验
5. **Profile 权威源**：`testcase-conventions/references/profiles.yaml`（全局唯一）；其他规范见 `_shared_conventions.md`

---

## 与其他 skill 的关系

```
生成器 (core/boundary/exception/interrupt/traverse)
    ↓ append 一行 JSON → 测试用例_模块/{模块}.jsonl
本 skill (testcase-aggregator · 编排层)
    ↓ 单条命令：python run_pipeline.py --archive-dir {归档目录}
md2csv-converter (渲染层，就地调用)
    ├── run_pipeline.py  → 顺序编排
    ├── md2csv.py        → 测试用例.csv + _stats.json
    └── validate.py      → _validate_report.json
    ↑ 就地读取 testcase-conventions/references/profiles.yaml
本 skill 读 _stats.json + _validate_report.json → 生成 测试用例聚合报告.md
```
