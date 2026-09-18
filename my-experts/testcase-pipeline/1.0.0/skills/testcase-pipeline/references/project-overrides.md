# 本机变更说明（testcase-pipeline）

> **标准已直接写进技能原文 —— 只有一套，不是两套。**
> 本文件不承载任何规范，只记录「本机改了哪些文件、为什么」，供排查与升级核查用。
> **升级 / 重装后跑一次**：`<python.exe> F:\WorkBuddy\apply_testcase_overrides.py`

---

## 一、本机相对上游的改动

| 文件 | 改动 |
|---|---|
| `SKILL.md` | ① §三 生成器表：testcase-exception → **YC + FCG**；② §五 门控：总用例数 ≥ 测试点数 × 2.5，**判不过直接报「未过门控」**、不自动补用例，并注明**覆盖率统计不含 FCG**；③ §六：原最低占比表 → **7 类健康区间**（提示性黄灯） |
| `agents/testcase-pipeline.md`（**专家人设**） | ① `six-category` → `seven-category`；② 核心能力「六类用例生成」→ **七类**（补 FCG 与三者分界）；③ 门控 → **覆盖率不计 FCG + 用例数唯一判据 + 不达标直接报未过**；④ 阶段 6 生成器序列 → `testcase-exception（YC + FCG）`；⑤ 阶段 7 同上 |
| `references/_shared_conventions.md` | ① §1 加载条款：**启动须一并读取本目录所有无 `_` 前缀规范文件**；② §2 字段表 6→7 类；③ §4.1 改「7 类分类」并补 FCG 定义与三者分工；④ §4.2 `CATEGORY_ORDER` 插 FCG；⑤ **删除原 §9「复杂度评分与分类目标占比映射」**（第三套占比口径）；⑥ §10.1 预估改 ≥ M×2.5；⑦ §11.2 最低用例总数基准 → 唯一判据 |
| `references/stage-05-testpoint-splitter.md` | ① 主分类枚举加 FCG；②「适用分类」列写明 FCG 触发条件；③ §2.7「重复操作」→「**非首次操作**」（与 FCG「反复」区分）；④ 示例枚举同步 |
| `references/stage-09-testcase-exception.md` | **整篇重写为 YC + FCG 双分类**：新增分界表、FCG 四子类表、易错点、FCG 模板、JSONL 示例；删除「快速连续点击 → YC」等冲突表述 |
| `references/stage-12-testcase-reviewer.md` | 分类清单 6→7 类；`avg_expand_rate` 阈值 2.0 → 2.5 |
| `references/stage-06 / 07 / 08 / 10 / 11 / 14` | 分类枚举与「禁止分类」列表统一加 FCG |
| `references/profiles.yaml` | `enum` 与 `category_order` 加 FCG（FCG 紧插 YC 后） |
| `scripts/md2csv.py` | fallback 配置加 FCG；`CATEGORY_TO_GENERATOR` 加 `FCG → testcase-exception` |
| `scripts/validate.py` | fallback 配置加 FCG |

---

## 二、现行唯一标准（速查，详情看原文）

| 项 | 标准 | 原文位置 |
|---|---|---|
| 分类 | **7 类**：HX / FHX / BJ / YC / **FCG** / BL / ZD | `_shared_conventions §4.1` |
| 三者分工 | **YC ＝ 动作本身不该发出｜FCG ＝ 做法不对｜ZD ＝ 发出后被切断** | `stage-09` |
| 生成器归属 | core→HX+FHX｜boundary→BJ｜**exception→YC+FCG**｜traverse→BL｜interrupt→ZD | `SKILL §三` |
| 占比 | **提示性区间（黄灯）**：HX 20~35（不设下限）/ FHX 12~21 / BJ 14~23 / YC 8~15 / FCG 2~13 / BL 9~14 / ZD 5~13 | `SKILL §六` |
| 用例数 | **门控（红灯，唯一判据）**：总用例数 ≥ 测试点数 × 2.5；**不过就报「未过门控」** | `SKILL §五` / `§11.2` |

---

## 三、本项目特有约定（不进技能包，故留此处）

- **已交付的三份表不回改**（阿岩 2026-09-18 拍板「表不改」）：赠礼可执行表（26 行）、玩家交互主表（16 条）、聊天系统表（8 条）**仍记 YC**。
- 追溯旧表按**等价映射**：旧 YC 中属「连点 / 反复 / 未就绪 / 乱序」的条目 ⇒ 新口径的 **FCG**。
- **FCG 数据依据**：三表 1067 条，原 YC 179 → 可归 FCG **50 条**（27.9%）。子类：连点 30 / 反复 12 / 未就绪 8 / 乱序 2。

---

## 四、上游遗留（本机未改，留待技能维护方）

1. `stage-12` 阶段 1.5 的维度引用**整体错位一行**（写成维度 6/7/8/9，实际应为 5/6/7/8）。
2. 铁律 6「未拍板项标【待确认】」与 `stage-12` 维度 4「把『待确认』当二义性扣分」**互斥**。
