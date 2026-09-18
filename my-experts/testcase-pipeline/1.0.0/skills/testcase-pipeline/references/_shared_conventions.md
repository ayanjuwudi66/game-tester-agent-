# 用例生成通用规范（Shared Conventions）

> 本文件是 `testcase-agent` 及其全部子 skill 的**权威通用配置源**。
> 任何用例生成、评审、聚合任务在启动时**必须加载**本文件并遵守全部规范。
> 项目侧如需覆盖某条规范，可在同目录新增**无 `_` 前缀**的规范文件；**启动时须一并读取本目录下所有无 `_` 前缀的规范文件**（当前为 `project-overrides.md`），其条款优先级**高于本文件与 `SKILL.md`**。

---

## §1 Profile Registry（表头版本）

本项目支持 3 种表头 profile，通过 `active_profile` 切换。**默认 `A_legacy`（P 组通用）**。

> 🔑 **机读权威源**：本节 YAML 为**文档展示镜像**，实际由脚本加载的是同目录的 `profiles.yaml`。
> 若二者不一致，**以 `profiles.yaml` 为准**；本节仅用于人工查阅。
> 参见 `testcase-conventions/SKILL.md §四` 路由表。

### 1.1 Profile 定义

```yaml
profiles:
  A_legacy:
    label: P组通用
    columns:
      - {label: "模块",         bind: module}
      - {label: "子模块",       bind: submodule}
      - {label: "测试点描述",   bind: testpoint}
      - {label: "用例描述",     bind: case_desc}
      - {label: "前提条件",     bind: precondition}
      - {label: "操作步骤",     bind: steps}
      - {label: "预期结果",     bind: expected}
      - {label: "用例分类",     bind: category}
    delivery: true      # 允许作为正式交付

  B_new:
    label: 项目定制——vag通用
    columns:
      - {label: "模块",       bind: module}
      - {label: "子模块",     bind: submodule}
      - {label: "功能点",     bind: feature_point}
      - {label: "测试点",     bind: testpoint}
      - {label: "前提条件",   bind: precondition}
      - {label: "测试步骤",   bind: steps}
      - {label: "预期结果",   bind: expected}
      - {label: "用例分类",   bind: category}
    delivery: true

  C_debug:
    label: 调试/校验用 9 列全集（含 case_desc + feature_point，非交付）
    columns:
      - {label: "模块",       bind: module}
      - {label: "子模块",     bind: submodule}
      - {label: "功能点",     bind: feature_point}
      - {label: "测试点",     bind: testpoint}
      - {label: "用例描述",   bind: case_desc}
      - {label: "前提条件",   bind: precondition}
      - {label: "测试步骤",   bind: steps}
      - {label: "预期结果",   bind: expected}
      - {label: "用例分类",   bind: category}
    delivery: false
    output_suffix: "_debug"    # 归档目录名后缀
    purpose: "字段对比与调试验证，禁止进入正式交付"

active_profile: A_legacy
c_debug_trigger_keywords: [调试, 校验, 对比, debug]
```

### 1.2 关键约束

- **一次生成，一次落盘，多种视图**：5 个生成器**永远产出 9 字段全集**（包括 `case_desc` 与 `feature_point`）。三种 profile 的差异仅在**渲染层**（aggregator + md2csv.py），按 `profile.columns` 挑选并按顺序输出到 CSV。
- **profile 的唯一作用**：`profiles.yaml.profiles.{name}.columns` 即"列白名单 + 列顺序"，位置写死。**profile 不参与生成阶段决策，切换 profile 不需要重跑 JSONL**。
- **B_new 渲染**：挑选 8 列，含 `feature_point`、无 `case_desc`
- **A_legacy 渲染**：挑选 8 列，无 `feature_point`、含 `case_desc`
- **C_debug 渲染**：9 列全出，归档目录后缀 `_debug`，**禁止进入正式交付目录**
- **`temp/_progress.json` 可选记录 `profile` 字段**：仅用于聚合阶段提示当前 profile 选择；生成阶段完全不读该字段
- **字段缺失防御**：任何 profile 列对应的字段值缺失时，降级为空字符串（不报错、不中断）；`validate.py` 会对 required 字段的空值告警
- **弱基座防御**：若 agent 未显式选择 profile，落回 `active_profile: A_legacy`

---

## §2 逻辑字段字典（9 字段）

**所有生成器只认逻辑字段，不认表头文字**。生成器输出为结构化字段，表头由渲染层按 profile 拼装。

> 🔑 **机读版本**：字段字典的可加载版本见 `profiles.yaml.fields`，包含 `source` / `required` / `enum` 等元数据。

| 字段 | 语义 | 来源 |
|---|---|---|
| `module` | 一级功能模块名（需求文档中的模块划分） | feature-splitter 输出 |
| `submodule` | 二级功能点/子模块名 | feature-splitter 输出 |
| `feature_point` | 子模块的功能描述文字，用于填充「功能点」列（B_new/C_debug 显示，A_legacy 不显示）。**由生成器透传写入 JSONL，不做运行时反查**——值来源见 §3 | testpoint-splitter 六列表格**第 2 列**「功能点描述」携带 → 5 个生成器逐行写入 JSONL |
| `testpoint` | 测试点描述（一句话说明验证目标） | testpoint-splitter 输出。旧 A profile 表头写作"测试点描述"，语义与本字段等价 |
| `case_desc` | 用例描述（具体测试场景短语，A_legacy/C_debug 显示，B_new 不显示） | 生成器产出 |
| `precondition` | 前提条件（分号分隔） | 生成器产出 |
| `steps` | 操作步骤（编号 + 分号分隔） | 生成器产出。旧 A profile 表头写作"操作步骤" |
| `expected` | 预期结果（与步骤一一对应） | 生成器产出 |
| `category` | 用例分类，仅限 7 类（HX/FHX/BL/BJ/YC/FCG/ZD） | 生成器判定，参见 §4 |

**字段生成推荐顺序**：`precondition → steps → expected → case_desc（基于前三项精简而来）`

---

## §3 功能点描述传递链路

### 3.1 测试点 ID 格式（v2 新格式）

```
T{模块序号}.{子模块序号}.{序号}
```

**示例**：`T1.2.3` = 模块 1 的第 2 个子模块下的第 3 个测试点

- 模块序号：对应 `功能点列表.md` 中的一级模块编号（1、2、3...）
- 子模块序号：该模块下的子模块编号（1.1、1.2、1.3... 中的 `.2` 部分）
- 序号：该子模块下的测试点连续编号

**ID 用途**：仅用于测试点自身的唯一定位，不承担运行时反查职责。

### 3.2 功能点描述传递路径（静态透传，不做运行时反查）

```
feature-splitter                       testpoint-splitter                     5 个 testcase-* 生成器          md2csv.py（渲染层）
─────────────────                      ──────────────────                     ─────────────────────           ─────────────────
功能点列表.md                          测试点列表.md（六列表格）              测试用例_模块/*.jsonl           测试用例.csv
                                                                                                              
## 模块N: {模块名}                     | 测试点ID | 功能点描述 | ... |         每行 JSON 对象含                按 profile.columns
### N.M {子模块名}                     |----------|------------|-----|         "feature_point": "..."         挑列 + 排列
- **描述**: {功能点描述文字}     ────► | TN.M.k   | {功能点描述文字} | ... ─►   （值 = 六列表格第 2 列）  ──► （B_new/C_debug 显示）
                                                                                                              （A_legacy 不出该列）
```

**关键要点**：
- `feature_point` 值在 **feature-splitter 阶段就确定**，沿 pipeline 逐级向下透传
- **testpoint-splitter**：从 `功能点列表.md` 抄写子模块「描述」到测试点表格**第 2 列**「功能点描述」；同一子模块下所有测试点该列内容相同
- **5 个生成器**：读六列表格**第 2 列**「功能点描述」，写入 JSONL 的 `feature_point` 字段（必填）
- **md2csv.py（渲染层）**：只做"按 profile 挑列 + 输出 CSV"，**不再解析 `功能点列表.md` 反查描述**；`功能点列表.md` 仅用于提取模块顺序

### 3.3 兼容性说明

- **旧 ID 格式 `T{模块}.{序号}`（两段，如 `T1.2`）** 已废弃
- 存量测试点若为旧格式，需由 `testpoint-splitter` 统一升级到 v2 格式
- 旧数据（`feature_point` 缺失的 JSONL）：CSV 渲染时该列为空；validate 会告警。**不做自动迁移，需重跑生成器**

### 3.4 前提约束

- `feature-splitter` 输出的每个子模块必须包含 `- **描述**: {文字}` 一行（标准格式已明确）
- `testpoint-splitter` 输出必须为**六列表格**且**第 2 列**「功能点描述」不得为空（缺失时兜底填子模块名）
- 5 个生成器**必须**在 JSONL 每行写入 `feature_point` 字段，值 = 六列表格**第 2 列**「功能点描述」

---

## §4 用例分类定义

### 4.1 7 类分类

| 简称 | 全称 | 定义 |
|:---:|---|---|
| **HX** | 核心用例 | 所有玩家必定会触发的用例 |
| **FHX** | 非核心用例 | 玩家不一定触发但属于重要用例 |
| **BL** | 功能遍历 | 同一功能点的多种输入组合 |
| **BJ** | 边界场景 | 边界值相关的测试用例 |
| **YC** | 异常操作 | 正常玩家不会做的操作 |
| **FCG** | 玩家非常规操作 | 操作**本身合法**，但执行方式不正常：连点 / 反复 / 未就绪 / 乱序 |
| **ZD** | 中断/重连 | 功能运行中被中断后恢复 |

**三个"非正常"分类的分工**：**YC ＝ 动作本身不该发出｜FCG ＝ 动作做对了、做法不对｜ZD ＝ 动作发出后被切断**

**❌ 禁止使用**：P0/P1/P2、高/中/低、Critical/Major 等其他格式

### 4.2 排序优先级（CSV 聚合时）

```
CATEGORY_ORDER = [HX, FHX, BL, BJ, YC, FCG, ZD]
```

> 🔑 **机读版本**：见 `profiles.yaml.category_order`。

**CSV 三级排序**（从高到低）：
1. 模块顺序：按 `功能点列表.md` 中的模块顺序
2. 子模块顺序：按每个 `{模块}.jsonl` 中 `submodule` 首次出现的顺序
3. 测试点顺序：按测试点首次出现顺序（**同一测试点的不同分类聚合**）
4. 分类优先级：按 `CATEGORY_ORDER`

**关键约束**：同一测试点的 HX/FHX/BL/BJ/YC/FCG/ZD 用例**必须紧挨着**输出，不得被拆散。

---

## §5 用例撰写规范（7条，全部强制）

### 规范1：操作步骤详尽（完整描述用户操作路径）

一条用例可以包含多步操作，操作步骤与预期结果应一一对应。使用编号标记每个步骤。

| ❌ 过于精简（遗漏步骤） | ✅ 详尽写法（完整路径） |
|---|---|
| 点击红心图标 | 1.进入游戏主页；2.点击红心图标 |
| 退出登录 | 1.进入设置页面；2.找到退出登录按钮；3.点击退出登录 |
| 修改名称后保存 | 1.点击编辑按钮；2.修改名称；3.点击保存 |

**详尽原则**：
- 保留导航步骤（进入页面、找到按钮等）
- 保留观察步骤（查看、确认显示等）
- 操作步骤应能独立执行，无需额外猜测

### 规范2：操作步骤与预期结果一一对应

多步操作时，预期结果应与操作步骤编号对应：

| 操作步骤 | 预期结果 |
|---|---|
| 1.进入游戏主页；2.点击Create Now按钮 | 1.页面正常显示；2.跳转到创作页面 |
| 1.输入框内输入内容；2.点击Create Now按钮 | 1.文字显示在输入框中；2.跳转到创作页面，输入框出现对应内容 |

### 规范3：前提条件省略规则

子模块名称已隐含的状态不需要重复描述：
- 子模块为"成员列表展示" → 前提只写"位于成员列表界面"
- 子模块为"房间创建" → 前提只写"已打开创建房间弹窗"

### 规范4：用例描述精简

| ❌ 冗余描述 | ✅ 精简描述 |
|---|---|
| 验证用户在正常网络环境下成功创建无密码房间 | 创建无密码房间 |
| 检查房间列表在数据加载完成后的正确展示 | 房间列表加载展示 |
| 验证点击退出登录按钮后系统正确弹出二次确认弹窗 | 点击退出登录弹出确认弹窗 |

### 规范5：执行顺序考量

同一子模块内的用例排列顺序应考虑实际执行顺序：
- 默认/常见状态优先（如：公开房间先于私密房间）
- 简单操作优先（如：查看先于编辑）
- 正向流程优先（如：成功先于失败）

### 规范6：通用测试维度（即使需求未提及也须考虑）

| 维度 | 适用场景 |
|---|---|
| 空值保存 | 所有包含输入/编辑/保存的功能 |
| 敏感词过滤 | 所有包含文本输入的功能 |
| 特殊字符 | 所有包含文本输入的功能 |
| 默认状态优先 | 有多种配置/状态的功能 |
| 首次/非首次 | 涉及引导/缓存的功能 |

### 规范7：预期结果精简与实质化（强制）

每条预期结果必须描述**可观测、可验证的具体结果**，禁止使用套话。

**精简原则**：去除已隐含或已在前提中的观察步骤（如"编辑器正常加载"若前提已要求进入编辑器则冗余）。

**实质化原则**：预期必须说明具体发生了什么，而非仅表达"没有问题"。

**禁止使用的套话（写入 `validate.py` 禁词校验）**：

|❌ 禁止套话 | ✅ 改为具体描述 |
|---|---|
| 界面正常加载 | 弹窗显示/页面跳转到xxx/列表展示N条数据 |
| 操作结果符合预期 | 房间创建成功，房间列表出现该房间 |
| 无异常 | 无错误弹窗，输入框内容保留 |
| 操作正常| 按钮变为不可点击状态 |
| 正常显示 | 显示"xxx"文字/图标可见/数值变为N |
| 系统无报错 | 接口返回成功，本地状态更新 |

**BL聚合词禁止**（`case_desc`/`steps` 中禁止出现）：每档、每种、遍历、全部…页签页数等聚合表达 → 必须每个具体输入组合独立成一条用例。

**BJ 复合边界禁止**（`case_desc`/`steps` 中禁止出现）：斜杠分隔的多值边界表达（如 `-180°/360°`、`空/1位`、`最小/最大`）→ 每个边界值必须独立成一条用例。

---

## §6 数值具体化规范（强制）

**所有涉及数量、长度、时间的描述，必须使用具体数值：**

| ❌ 模糊写法 | ✅ 具体写法 |
|---|---|
| 验证房间列表最多显示若干房间 | 验证房间列表最多显示8个房间 |
| 验证房间名长度限制 | 验证房间名最多输入10个字符 |
| 验证Toast自动消失 | 验证Toast显示3秒后自动消失 |
| 验证密码位数要求 | 验证密码必须为6位数字 |

**自检词汇替换**：`若干` / `一定时间` / `不足X位` / `超过X个` / `上限` / `下限` → 全部替换为具体数值；范围类描述拆分为具体数值的独立用例。

---

## §7 UI 走查排除规则（最高优先级）

**以下内容禁止生成测试用例，应由 UI 走查覆盖：**

| 排除类型 | 错误示例 ❌ | 正确做法 ✅ |
|---|---|---|
| 精确尺寸验证 | "验证弹窗尺寸560×840px" | 仅验证"弹窗正常显示" |
| 颜色值验证 | "遮罩颜色rgba(0,0,0,0.3)" | 仅验证"遮罩层显示" |
| 字号验证 | "标题24px字号" | 仅验证"标题显示正确" |
| 圆角/间距 | "按钮圆角65px" | 不单独设计用例 |
| 像素位置 | "按钮位于右下角20px处" | 仅验证"按钮可见" |
| 纯样式验证 | "文字为灰色" | 不单独设计用例 |

---

## §8 JSONL/CSV 渲染约定

### 8.1 编码要求（硬性）

| 文件类型 | 编码 | 说明 |
|---|---|---|
| **CSV** | **`utf-8-sig`（UTF-8 with BOM）** | **硬性要求**：CSV 文件开头必须含 BOM（`EF BB BF`），确保 Windows Excel 打开无乱码。任何 CSV 输出违反此项 = 任务失败 |
| **JSONL** | **`utf-8`（严禁 BOM）** | **硬性要求**：JSONL 每次 append 都是尾部追加；若含 BOM，首行 `json.loads` 将失败。生成器 `open(mode='a', encoding='utf-8')` |
| MD | `utf-8` | 标准 UTF-8（`功能点列表.md`/`测试点列表.md`/聚合报告等） |
| Python | `utf-8` | 标准 UTF-8 |

**md2csv.py 写入规范**：

```python
# CSV 写入必须使用 utf-8-sig
with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(HEADER)   # HEADER 由 profile 提供
    writer.writerows(rows)
```

### 8.2 CSV 内容禁忌

- **禁 HTML 残留**：单元格内禁止出现 `<br>` / `<p>` / `&lt;` / `&gt;` / `&nbsp;` / `&amp;` 等 HTML 标签或实体。多行文本用 `\n` 换行（Python `csv.writer` 会自动加双引号包围）
- **禁独立分类文件**：不生成 `边界场景.jsonl`、`YC用例.jsonl` 等按分类分文件；所有用例归属到功能模块 JSONL（文件名 = 模块显示名）

### 8.3 JSONL append 规范（生成器唯一写入方式）

**中间产物形态**：`测试用例_模块/{模块名}.jsonl`，每行一个用例对象（UTF-8 无 BOM）。

**唯一允许的写入方式** —— append-only：

```python
import json
from pathlib import Path

out_file = Path(archive_dir) / "测试用例_模块" / f"{module_name}.jsonl"
out_file.parent.mkdir(parents=True, exist_ok=True)
with open(out_file, "a", encoding="utf-8") as f:      # 硬约束：mode='a'
    for case in cases:
        f.write(json.dumps(case, ensure_ascii=False) + "\n")   # 硬约束：ensure_ascii=False
```

**禁止事项**：
- ❌ 禁止用 `write_to_file` 覆盖已有 `.jsonl`（多 skill 追加时会互相冲刷）
- ❌ 禁止用 `replace_in_file` 修改 JSONL（这不是行导向 MD，无稳定锚点）
- ❌ 禁止在 JSONL 里写入 BOM 或非 JSON 内容（注释/标题/表格骨架）
- ❌ 禁止 `json.dumps(..., ensure_ascii=True)`（会把中文变 `\uxxxx`）

**允许事项**：
- ✅ 首次生成模块时若文件不存在，`open('a')` 会自动创建
- ✅ 同一模块 `.jsonl` 可以被 5 个生成器 skill 分别 append（追加顺序无强制要求；最终 CSV 顺序由 md2csv 三级稳定排序保证）

**每行 JSON 对象字段约定**：
| 字段 | 由谁写 | 说明 |
|---|---|---|
| `module` | 可省略 | 若写了会被渲染层用**文件名 stem** 覆盖；写不写都行 |
| `submodule` | 生成器必写 | 每条用例的子模块归属 |
| `testpoint` | 生成器必写 | 来源于 `测试点列表.md` |
| `case_desc` | 生成器必写 | 用例场景描述 |
| `precondition` | 生成器必写 | 前提条件 |
| `steps` | 生成器必写 | 多步骤用 `\n` 换行 |
| `expected` | 生成器必写 | 与 steps 编号一一对应 |
| `category` | 生成器必写 | 本 skill 允许的分类（HX/FHX/BJ/YC/FCG/BL/ZD 之一） |
| `feature_point` | **生成器必写** | 值 = testpoint-splitter 六列表格**第 2 列**「功能点描述」；生成器逐行透传，禁止依赖渲染层反查 |

**JSONL 数据示例**（一个 `{模块}.jsonl` 的内容片段）：

```jsonl
{"submodule":"创建房间","feature_point":"玩家在游戏主页面创建新房间，支持公开/密码两种模式","testpoint":"验证创建房间功能","case_desc":"正常创建无密码房间","precondition":"已进入创建房间页面","steps":"1.输入房间名\n2.点击创建按钮","expected":"1.文字显示\n2.房间创建成功","category":"HX"}
{"submodule":"创建房间","feature_point":"玩家在游戏主页面创建新房间，支持公开/密码两种模式","testpoint":"验证创建房间功能","case_desc":"已在房间内创建","precondition":"玩家已在房间内","steps":"1.点击创建按钮","expected":"1.提示已在房间中","category":"FHX"}
{"submodule":"创建房间","feature_point":"玩家在游戏主页面创建新房间，支持公开/密码两种模式","testpoint":"验证房间名长度","case_desc":"边界10字符","precondition":"已进入创建房间页面","steps":"1.输入10字符\n2.点击创建","expected":"1.完整接受\n2.创建成功","category":"BJ"}
```

### 8.4 Windows Python 脚本中文输出

```python
import sys, io
# 用属性打标，避免被上游脚本二次 import 时重复包装
if sys.platform == 'win32' and not getattr(sys.stdout, '_utf8_wrapped', False):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    sys.stdout._utf8_wrapped = True
    sys.stderr._utf8_wrapped = True
```

---

## §10 用例数量预估 + 路径/目录规则

### 10.1 用例数量预估

```
📊 用例生成预估
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 功能模块：{N} 个
📍 测试点数：{M} 个
📝 预计用例：≥ {M×2.5} 条
⏱️ 预计耗时：{按测试点数计算} 分钟
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**耗时预估表**：

| 测试点数量 | 预估耗时 |
|---|---|
| 1-10 个 | 1-3 分钟 |
| 11-30 个 | 3-8 分钟 |
| 30+ 个 | 8-15 分钟 |

### 10.2 输出目录命名规则

- **基础名称**：`output/{需求名}_{YYYYMMDDHHmm}/`（精确到分钟）
- **防重名**：已存在时自动添加后缀 `_v1` / `_v2` / ...
- **C_debug 特殊后缀**：使用 C_debug profile 时，目录追加 `_debug` 后缀（如 `output/xxx_202607281430_debug/`），**不进入正式交付**

### 10.3 输出目录结构

```
output/{需求文件名}_{YYYYMMDDHHmm}[_vN][_debug]/
├── 需求整理报告.md          # requirement-organizer 输出
├── 功能点列表.md            # feature-splitter 输出
├── 测试点列表.md            # testpoint-splitter 输出（含 v2 格式 ID）
├── 测试用例_模块/           # 各模块用例 JSONL 文件（生成器 append）
│├── {模块1}.jsonl
│   └── ...
├── {需求名}_{YYYYMMDDHHmm}.csv  # aggregator 输出（按active_profile渲染，UTF-8 BOM，动态命名）
├── 测试用例聚合报告.md      # aggregator 输出
├── 评审报告.md              # reviewer 输出（可选）
└── temp/                    # 临时产物（非交付）
    ├── _stats.json          # md2csv 输出（结构化统计，聚合报告数据源）
    ├── _validate_report.json# validate 输出（校验结果）
    ├── _progress.json       # 断点续跑状态（含 profile 字段）
    ├── _review_data.py      # reviewer 预计算脚本（可选）
    └── _review_data.json    # reviewer 预计算结果（可选）
```

**归档目录不再包含**：md2csv.py / validate.py / profiles.yaml（P2 就地调用式改造后由上游 skill 直接读取）。

## §11 最小用例数量配置（集中可配置项）

> 本节是所有生成器和评审 skill 的**唯一用例数量权威来源**。各 skill 中禁止硬编码具体数字，统一引用本节。
> 项目侧如需调整，在同目录自定义规范文件中覆写本节对应条目。

### 11.1 每测试点最小覆盖数（分类级别）

| 分类 | 最小用例数/测试点 | 适用条件 | 备注 |
|:---:|:---:|---|---|
| **HX/FHX** | ≥ 1 | 纯展示型测试点 | 仅有展示无交互 |
| **HX/FHX** | ≥ 2 | 非纯展示型测试点 | 含网络请求/输入/状态变更的测试点 |
| **BJ** | ≥ 1 | 含「适用分类 BJ」的测试点 | 最低覆盖 |
| **BJ** | ≥ 3 | 含输入框的测试点 | 建议：空/临界/超限 |
| **BJ** | ≥ 3 | 含列表/数值的测试点 | 建议：空/最小/最大/超限，取3-4条 |
| **BL** | ≥ 1 | 含「适用分类 BL」的测试点 | 最低覆盖 |
| **YC** | ≥ 1 | 含「适用分类 YC」的测试点 | 最低覆盖 |
| **FCG** | ≥ 1 | 含「适用分类 FCG」的测试点 | 最低覆盖；连点 / 反复 / 未就绪 / 乱序命中任一即可 |
| **ZD** | ≥ 1 | 含「适用分类 ZD」的测试点 | 最低覆盖 |

### 11.2 生成器门控参数

| 参数 | 值 | 说明 |
|---|:---:|---|
| 非展示型 HX 回溯阈值 | < 2 条 | HX/FHX 用例数不足时回溯 testcase-core |
| BJ 回溯阈值 | < 3 条 | 含输入框/数值测试点 BJ 不足时回溯 testcase-boundary |
| YC 回溯阈值 | < 2 条 | 含网络请求测试点 YC 不足时回溯 testcase-exception |
| BL/ZD 回溯阈值 | 仅1条但展开说明含多场景 | 展开说明含"/"分隔多场景时触发回溯 |
| 最低用例总数基准 | 测试点数 × 2.5 | **唯一判据** —— 判不过直接告知用户「未过门控」，不自动补用例 |

### 11.3 粒度合理性区间（评审参考）

| 判定 | 条件 | 处理建议 |
|---|---|---|
| **过大** | 一个测试点对应 > 4 条用例 | 检查测试点是否涵盖过多场景，考虑拆分测试点 |
| **合理** | 一个测试点对应 2–4 条用例，或1条但描述充分（≥5字） | 无需调整 |
| **过小** | 一个测试点仅1条用例且描述极短（< 5字） | 检查是否测试点过于碎片化 |

---

## 附录：与旧规范的兼容性说明

- 本文件由 P0 阶段新建，替代原 `{SKILL_DIR}/references/_shared_conventions.md`
- 主 agent 与各子 skill 的引用路径同步更新为 `{SKILL_DIR}/references/_shared_conventions.md`
- 旧文件在 P0 阶段**保留**（不删除），P2 主文档瘦身时统一清理
- 项目自定义规范（`.codebuddy/项目自定义/skills/monster-testcase-specs/`、`pvp-testcase-specs/`）本次改造**不涉及**，保持现状
