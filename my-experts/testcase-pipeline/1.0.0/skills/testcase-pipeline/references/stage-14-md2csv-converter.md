---
name: md2csv-converter
description: 将测试用例（JSONL 中间产物）转换为 CSV 格式。就地调用式：脚本从上游 skill 直接读取归档目录，不再复制副本到目标目录。
---

# JSONL 转 CSV 转换器 Skill（就地调用式 · 渲染层）

---

## 🚨 核心职责

**本 Skill 负责将生成器输出的 JSONL 中间产物转换为最终 CSV**，作为整条流水线的**渲染层出口**。

- ✅ 输入：`{archive_dir}/测试用例_模块/*.jsonl` + `{archive_dir}/功能点列表.md`（仅用于提取模块顺序）
- ✅ 输出：`{archive_dir}/{需求名}_{YYYYMMDDHHmm}.csv`（文件名由归档目录名自动派生，回退为 `测试用例.csv`）
- ✅ 临时产物：`{archive_dir}/temp/_stats.json`（统计）、`{archive_dir}/temp/_validate_report.json`（校验）
- ✅ CSV 编码：**UTF-8 with BOM（`utf-8-sig`）—— 硬性要求**
- ✅ JSONL 编码：**UTF-8 无 BOM**（生成器 append 时严禁 BOM）

**就地调用式**：
- `md2csv.py` / `validate.py` / `run_pipeline.py` 三个脚本**永远留在本 skill 的 `scripts/` 目录**
- 通过 `--archive-dir` 就地读写目标归档目录，**不再复制脚本或配置副本到归档目录**
- `profiles.yaml` 默认从 `{SKILL_DIR}/references/profiles.yaml` 就地读取

---

## 使用场景

在 5 个生成器（core / boundary / exception / interrupt / traverse）分别 append 完 JSONL 后，编排层调用 `run_pipeline.py` 一条命令完成 CSV 生成 + 格式校验。

---

## Profile 驱动

CSV 表头由 `profiles.yaml` 的 `active_profile` 字段决定（可被环境变量 `ACTIVE_PROFILE` 覆盖）。支持 3 种 profile：

| Profile | 列数 | 定位 | 归档目录后缀 |
|---|:---:|---|:---:|
| `A_legacy` | 8 | P组通用（**默认交付**） | 无 |
| `B_new` | 8 | 项目定制——vag通用 | 无 |
| `C_debug` | 9 | 全字段并集（含 `case_desc` + `feature_point`），调试/校验用 | `_debug` |

**Profile 权威定义**：`testcase-conventions/references/profiles.yaml`（**全局唯一**）

**关键约定**：
- 生成器输出**JSONL**（每行一个用例对象）；不再是 MD 表格
- 生成器写全**9 字段**（`submodule / feature_point / testpoint / case_desc / precondition / steps / expected / category`，其中 `feature_point` 值 = testpoint-splitter 六列表格**第 2 列**「功能点描述」携带）；`module` 由渲染层用文件名兜底
- 渲染层不做运行时反查：profile 的唯一作用是"按 `profile.columns` 挑列 + 定顺序"
- 切换 profile 优先级：`env ACTIVE_PROFILE` > `profiles.yaml.active_profile`

---

## JSONL 输入格式（生成器产出）

**中间产物**：`{archive_dir}/测试用例_模块/{模块名}.jsonl`
**编码**：UTF-8 无 BOM
**每行**：一个 JSON 对象，`ensure_ascii=False` 保证中文明文

```jsonl
{"submodule":"创建房间","feature_point":"玩家在游戏主页面创建新房间，支持公开/密码两种模式","testpoint":"验证创建房间功能","case_desc":"正常创建","precondition":"...","steps":"1.输入房间名\n2.点击创建","expected":"1.文字显示\n2.创建成功","category":"HX"}
{"submodule":"创建房间","feature_point":"玩家在游戏主页面创建新房间，支持公开/密码两种模式","testpoint":"验证房间名长度","case_desc":"边界10字符","precondition":"...","steps":"...","expected":"...","category":"BJ"}
```

**详细规范**（字段含义、必填/可选、L2 聚合策略）参见 `_shared_conventions.md §8.3`。

---

## Python 转换脚本（scripts/ 目录 · 就地调用式）

```
{SKILL_DIR}/scripts/
├── md2csv.py         # JSONL → CSV + _stats.json；接受 --archive-dir / --profile-yaml
├── validate.py       # CSV/JSONL 校验 → _validate_report.json；同款 CLI 参数
└── run_pipeline.py   # 编排入口，in-process 顺序调用 md2csv + validate
```

**⚠️ 硬约束**：
- 三个脚本**永远留在本目录**；aggregator 与任何调用方都通过 `--archive-dir` 就地调用
- **禁止**在 SKILL.md 或任何调用方文档内维护完整脚本副本
- **禁止**向归档目录复制脚本或配置副本
- 任何脚本改动直接改 `scripts/`；任何 profile / 字段 / 分类改动直接改 `testcase-conventions/references/profiles.yaml`

**脚本关键设计要点**：
1. **CLI 入参**：`--archive-dir`（必填，归档目录路径）+ `--profile-yaml`（可选，覆盖默认 yaml 路径）
2. **配置寻址**：`--profile-yaml` > `env PROFILES_YAML_PATH` > 默认路径（`testcase-conventions/references/profiles.yaml`）> 内嵌 fallback
3. **`ACTIVE_PROFILE`**：`env ACTIVE_PROFILE` > yaml 里的 `active_profile`（默认 `A_legacy`）
4. **9逻辑字段全集**：`module / submodule / feature_point / testpoint / case_desc / precondition / steps / expected / category`（生成器写全 9 字段，其中 `feature_point` 从 testpoint-splitter **第 2 列**「功能点描述」透传，`module` 可省略由渲染层文件名兜底）
5. **`parse_module_order()`**：从 `{archive_dir}/功能点列表.md` **仅**提取一级模块顺序（用于 CSV 三级排序的模块层），不再构造子模块反查表
6. **`load_jsonl()`**：遍历 `{archive_dir}/测试用例_模块/*.jsonl`；`module` 以文件名 stem 为准；`category` 大写归一后按 enum 过滤；解析失败/非 dict/缺 category → 记入 `parse_errors`，跳过
7. **profile 挑列**：按 `profile.columns` 定义的 `bind` 顺序，从每条 case 里挑出对应字段，输出到 CSV；未在 `columns` 声明的字段不出现在 CSV 里
8. **三级聚合排序**：模块 → 子模块首次出现 → 测试点首次出现 → 分类
9. **CSV 写入**：`encoding='utf-8-sig'`，BOM 硬性存在
10. **stats.json 输出**：profile 元信息 + total_cases + module_distribution + category_distribution + source_breakdown + `input_format: "jsonl"` + `parse_errors` + `skipped_lines`

---

## 调用方式（就地调用 CLI）

### 方式 1：run_pipeline.py 一条龙（推荐，aggregator 默认走此路）

```powershell
python {SKILL_DIR}\scripts\run_pipeline.py --archive-dir {归档目录}
```

- 顺序执行：`md2csv.run(archive_dir)` → `validate.run(archive_dir)`
- 摘要输出：profile / 用例数 / 校验结果
- 退出码：`0` 全成功；`2` md2csv 失败；`1` validate FAIL

### 方式 2：单独运行 md2csv 或 validate（调试用）

```powershell
# 只做转换
python {SKILL_DIR}\scripts\md2csv.py --archive-dir output\需求名_xxx\

# 只做校验（前提是 CSV 已存在）
python {SKILL_DIR}\scripts\validate.py --archive-dir output\需求名_xxx\

# 切 profile
$env:ACTIVE_PROFILE="A_legacy"
python {SKILL_DIR}\scripts\run_pipeline.py --archive-dir output\xxx\
```

### 方式 3：覆盖 profiles.yaml 路径（vibe coding / 沙箱场景）

```powershell
python {SKILL_DIR}\scripts\run_pipeline.py `
    --archive-dir output\xxx\ `
    --profile-yaml D:\custom\profiles.yaml
```

---

## 错误处理

| 问题 | 原因 | 解决方案 |
|---|---|---|
| 解析到 0 条用例 | `测试用例_模块/` 下没有 `.jsonl` /所有行都不合法 | 检查生成器是否已执行；检查 `temp/_stats.json.parse_errors` 定位问题行 |
| stats.json 显示 `parse_errors` | JSONL 有非法行（非 dict / json 解析失败 / 缺 category） | 逐条修复；`_stats.json.parse_errors[file]` 给出每文件错误数 |
| 中文乱码 | 编码问题 | 脚本已用 `encoding='utf-8-sig'` 写 CSV；JSONL 严禁 BOM（多次 append 会破坏 `json.loads`） |
| 分类无效 | category 不在 `HX/FHX/BL/BJ/YC/FCG/ZD` | 修正生成器输出；`load_jsonl` 会自动跳过非法行并记入 parse_errors |
| `feature_point` 列为空 | 生成器漏写 `feature_point` 字段（旧数据或写入 bug） | `validate.py` 会将其作为 required 空值告警；重跑对应生成器补齐 |
| 表头列数不对 | `active_profile` 与预期不一致 | `$env:ACTIVE_PROFILE=...` 或修改 `profiles.yaml.active_profile` |
| 提示"回退到内嵌 fallback 配置" | `profiles.yaml` 找不到 或 PyYAML 未安装 | 检查 `testcase-conventions/references/profiles.yaml` 是否存在；`pip install pyyaml` |
| `--archive-dir` 参数缺失 | 忘记传 CLI 参数 | 所有脚本必须显式传 `--archive-dir` |

---

## 输出验证

由 `validate.py` 就地承担 6 项校验：
1. BOM（CSV 首 3 字节 = `EF BB BF`）
2. 表头（列名与列数按 active_profile 匹配）
3. 分类合法性（category ∈ enum）
4. 行数对比（JSONL 合法用例数 == CSV 数据行数）
5. 排序（三级聚合顺序）
6. 必填字段（required 字段无空值）
+ JSONL Schema 汇报（异常行数按文件汇总到 warnings）

```powershell
python {SKILL_DIR}\scripts\validate.py --archive-dir output\xxx\
# 结果输出到 {archive_dir}/temp/_validate_report.json
```

---

## 注意事项

1. **UTF-8 BOM 是硬性要求**（仅限 CSV） —— 任何 CSV 输出必须以 BOM 开头（`EF BB BF`），无例外
2. **JSONL 严禁 BOM** —— 多次 append 会产生嵌入式 BOM 破坏 `json.loads`；生成器必须 `open('a', encoding='utf-8')`
3. **脚本就地调用** —— 脚本永远留在 `scripts/`，通过 `--archive-dir` 就地处理归档目录；不复制副本
4. **配置单源** —— PROFILES / CATEGORY_ORDER / FIELDS 全部在 `testcase-conventions/references/profiles.yaml`；脚本代码不硬编码字段列表（fallback 副本仅作 yaml 缺失时的兜底）
5. **Profile 切换** —— 修改 `profiles.yaml.active_profile` 或 `env ACTIVE_PROFILE`；新增 profile = yaml `profiles` 下新增键；**profile 仅影响 CSV 表头与列裁剪，切 profile 无需重跑 JSONL**
6. **加自定义字段** —— 改 1 处 `profiles.yaml` + 生成器写 JSONL 时多产一个字段即可（无需改 SKILL.md 描述示例）
7. **feature_point 由生成器透传** —— 值来自 testpoint-splitter 六列表格**第 2 列**「功能点描述」；渲染层不做运行时反查，若JSONL 缺失该字段则CSV 对应列为空，`validate.py` 会告警
