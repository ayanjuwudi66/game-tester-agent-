#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSONL 测试用例转 CSV 转换器（Schema-Driven · 就地调用式 · JSONL 输入）

【功能】
- 从任意 --archive-dir 读取 测试用例_模块/*.jsonl，输出到该目录下的 测试用例.csv + _stats.json
- 从 profiles.yaml 加载 PROFILES / CATEGORY_ORDER
- 按 active_profile拼装表头并输出 CSV（UTF-8 with BOM）
- CSV 文件名由归档目录名自动派生：{需求名}_{YYYYMMDDHHmm}.csv；无法解析时回退到 测试用例.csv
- 临时产物（_stats.json）写入 {archive_dir}/temp/ 子目录

【就地调用式（P2 保留）】
- 脚本无需被复制到归档目录；aggregator 直接指定 --archive-dir 就地运行
- profiles.yaml 默认从 {SKILL_DIR}/references/profiles.yaml 读取

【JSONL 输入】
- 每模块一份 {archive_dir}/测试用例_模块/{模块名}.jsonl
- 每行一个 JSON 对象，UTF-8 无 BOM
- module 字段以文件名 stem 为准（行内 module 只做参考）
- feature_point 由生成器在写入时静态填充（值= 测试点表格**第 2 列**「功能点描述」）；
  渲染层不再运行时反查，仅按 profile.columns 挑列输出
- 允许的字段与其含义见 profiles.yaml.fields

【单一权威源】
- profiles.yaml 位于 testcase-conventions/references/（全局唯一）
- 若加载失败：回退到内嵌 fallback（防御机制，非真理源）

【使用】
    # 基础用法
    python md2csv.py --archive-dir output/需求名_202607291611/

    # 覆盖 profile 文件
    python md2csv.py --archive-dir output/xxx/ --profile-yaml /path/to/profiles.yaml

    # 覆盖 active_profile
    ACTIVE_PROFILE=B_new python md2csv.py --archive-dir output/xxx/

【输入】
    {archive_dir}/测试用例_模块/*.jsonl # 生成器 append 输出
    {archive_dir}/功能点列表.md         # （可选）仅用于提取模块顺序
    profiles.yaml                       # 机读权威源

【输出】
    {archive_dir}/{需求名}_{YYYYMMDDHHmm}.csv  # UTF-8 with BOM（硬性要求；文件名由目录名派生）
    {archive_dir}/temp/_stats.json             # 结构化统计（聚合报告数据源）

【退出码】
    0 = 成功
    1 = 无用例 / 输入目录不存在 / active_profile 未定义
"""

import os
import re
import csv
import sys
import io
import json
import argparse
from pathlib import Path
from datetime import datetime

# Windows 中文输出兼容（避免被 run_pipeline 二次 import 时重复包装）
if sys.platform == 'win32' and not getattr(sys.stdout, '_utf8_wrapped', False):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    sys.stdout._utf8_wrapped = True
    sys.stderr._utf8_wrapped = True

SCRIPT_DIR = Path(__file__).resolve().parent

# 默认 profiles.yaml 路径：脚本在 {SKILL_DIR}/scripts/ 下，
# 上溯到 skills/，再进入 testcase-conventions/references/
DEFAULT_PROFILE_YAML = (
    SCRIPT_DIR.parent / "references" / "profiles.yaml"
)


# =============================================================================
# Profile 加载层（单一权威源：profiles.yaml；yaml 缺失时用 fallback）
# =============================================================================

def _fallback_config():
    """内嵌 fallback 配置（防御机制，非真理源）。"""
    return {
        "version": 1,
        "active_profile": "A_legacy",
        "category_order": ["HX", "FHX", "BL", "BJ", "YC", "FCG", "ZD"],
        "fields": {
            "module":        {"label_default": "模块",       "source": "feature-splitter",   "required": True},
            "submodule":     {"label_default": "子模块",     "source": "feature-splitter",   "required": True},
            "feature_point": {"label_default": "功能点",     "source": "generator",          "required": True},
            "testpoint":     {"label_default": "测试点",     "source": "testpoint-splitter", "required": True},
            "case_desc":     {"label_default": "用例描述",   "source": "generator",          "required": False},
            "precondition":  {"label_default": "前提条件",   "source": "generator",          "required": True},
            "steps":         {"label_default": "测试步骤",   "source": "generator",          "required": True},
            "expected":      {"label_default": "预期结果",   "source": "generator",          "required": True},
            "category":      {"label_default": "用例分类",   "source": "generator",          "required": True,
                              "enum": ["HX", "FHX", "BL", "BJ", "YC", "FCG", "ZD"]},
        },
        "profiles": {
            "A_legacy": {
                "label": "P组通用", "delivery": True,
                "columns": [
                    {"bind": "module",       "label": "模块"},
                    {"bind": "submodule",    "label": "子模块"},
                    {"bind": "testpoint",    "label": "测试点描述"},
                    {"bind": "case_desc",    "label": "用例描述"},
                    {"bind": "precondition", "label": "前提条件"},
                    {"bind": "steps",        "label": "操作步骤"},
                    {"bind": "expected",     "label": "预期结果"},
                    {"bind": "category",     "label": "用例分类"},
                ],
            },
            "B_new": {
                "label": "项目定制——vag通用", "delivery": True,
                "columns": [
                    {"bind": "module"},
                    {"bind": "submodule"},
                    {"bind": "feature_point"},
                    {"bind": "testpoint"},
                    {"bind": "precondition"},
                    {"bind": "steps"},
                    {"bind": "expected"},
                    {"bind": "category"},
                ],
            },
            "C_debug": {
                "label": "调试用 9 列全集", "delivery": False,
                "output_suffix": "_debug",
                "columns": [
                    {"bind": "module"},
                    {"bind": "submodule"},
                    {"bind": "feature_point"},
                    {"bind": "testpoint"},
                    {"bind": "case_desc"},
                    {"bind": "precondition"},
                    {"bind": "steps"},
                    {"bind": "expected"},
                    {"bind": "category"},
                ],
            },
        },
    }


def _resolve_profile_yaml_path(cli_override: str = None) -> Path:
    """按 [--profile-yaml > env: PROFILES_YAML_PATH > 默认路径] 顺序解析 yaml 路径。"""
    if cli_override:
        return Path(cli_override).expanduser().resolve()
    env_path = os.environ.get("PROFILES_YAML_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return DEFAULT_PROFILE_YAML


def load_config(profile_yaml_path: Path = None):
    """加载 profiles.yaml；缺失或解析失败时回退到 fallback。

    Returns:
        (cfg_dict, source_tag, effective_path)
        source_tag ∈ {"yaml", "fallback"}
    """
    yaml_path = profile_yaml_path or DEFAULT_PROFILE_YAML
    if not yaml_path.exists():
        print(f"[配置] profiles.yaml 不存在于 {yaml_path}，回退到内嵌 fallback 配置")
        return _fallback_config(), "fallback", yaml_path
    try:
        import yaml  # PyYAML
        with open(yaml_path, encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        for k in ("profiles", "category_order", "fields"):
            if k not in cfg:
                raise ValueError(f"profiles.yaml 缺失必需键: {k}")
        print(f"[配置] 从 profiles.yaml 加载成功 (version={cfg.get('version', '?')}, path={yaml_path})")
        return cfg, "yaml", yaml_path
    except ImportError:
        print("[配置] 未安装 PyYAML，回退到内嵌 fallback 配置（建议 `pip install pyyaml`）")
        return _fallback_config(), "fallback", yaml_path
    except Exception as e:
        print(f"[配置] profiles.yaml 解析失败 ({yaml_path}): {e}；回退到内嵌 fallback 配置")
        return _fallback_config(), "fallback", yaml_path


# =============================================================================
# 全局配置容器（模块级；由 initialize_config() 装填）
# =============================================================================

_CFG = None
_CFG_SOURCE = None
_CFG_PATH = None
FIELDS = None
CATEGORY_ORDER = None
_CAT_ORDER_MAP = None
PROFILES = None
ACTIVE_PROFILE = None

# 分类 → 生成器来源映射（用于 stats.json 的 source_breakdown）
CATEGORY_TO_GENERATOR = {
    "HX":  "testcase-core",
    "FHX": "testcase-core",
    "BL":  "testcase-traverse",
    "BJ":  "testcase-boundary",
    "YC":  "testcase-exception",
    "FCG": "testcase-exception",   # 项目覆写：FCG 与 YC 同源，由 testcase-exception 一并产出
    "ZD":  "testcase-interrupt",
}


def initialize_config(profile_yaml_path: Path = None):
    """加载 yaml 并装填全局配置容器。可重复调用（后调用覆盖）。"""
    global _CFG, _CFG_SOURCE, _CFG_PATH
    global FIELDS, CATEGORY_ORDER, _CAT_ORDER_MAP, PROFILES, ACTIVE_PROFILE

    _CFG, _CFG_SOURCE, _CFG_PATH = load_config(profile_yaml_path)
    FIELDS = _CFG["fields"]
    CATEGORY_ORDER = _CFG["category_order"]
    _CAT_ORDER_MAP = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    PROFILES = _CFG["profiles"]
    ACTIVE_PROFILE = os.environ.get("ACTIVE_PROFILE") or _CFG.get("active_profile", "A_legacy")


def resolve_column(col, fields):
    """从 profile.columns 的一项 (含 bind 和可选 label) 解析出 (label, bind)。"""
    bind = col["bind"]
    label = col.get("label") or fields.get(bind, {}).get("label_default") or bind
    return label, bind


# =============================================================================
# 功能点列表解析（仅用于提取模块顺序，用于 CSV 排序）
# =============================================================================

def parse_module_order(filepath: Path) -> list:
    """
    解析 功能点列表.md 提取一级模块顺序（用于 CSV 三级排序的模块层）。

    仅识别形如 `## 模块N: xxx` 或 `## xxx` 的一级标题；过滤掉"功能点统计"
    "功能点拆分说明""模块总览"等辅助段落。

    Returns:
        module_order: [模块名1, 模块名2, ...]
    """
    if not filepath.exists():
        print(f"警告: 功能点列表文件不存在: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    module_pattern = re.compile(
        r'^##\s+(?:模块[一二三四五六七八九十\d]+[：:]\s*)?(.+?)\s*$'
    )
    skip_names = {'功能点统计', '功能点拆分说明', '模块总览'}

    module_order = []
    for line in content.split('\n'):
        m = module_pattern.match(line)
        if m:
            name = m.group(1).strip()
            if name and name not in skip_names:
                module_order.append(name)

    return module_order


# =============================================================================
# JSONL 输入解析（替换双模式 MD 解析器）
# =============================================================================

def load_jsonl(input_dir: Path) -> tuple:
    """
    遍历 input_dir 下所有 *.jsonl，逐行 json.loads。

    规则：
      - module 字段以**文件名 stem** 为准（覆盖行内 module）
      - category 归一为大写；不在 enum 内的行 → 记入 parse_errors，跳过
      - json.loads 失败 → 记入 parse_errors，跳过
      - 空行跳过（不计错误）
      - 缺失 FIELDS 中的字段 → 补空字符串（不告警，soft schema）

    Returns:
        (cases: list[dict], parse_errors: dict[str,int], skipped_lines: int)
    """
    cases = []
    parse_errors = {}
    skipped_lines = 0

    if not input_dir.exists():
        return cases, parse_errors, skipped_lines

    for jsonl_file in sorted(input_dir.glob("*.jsonl")):
        module_from_filename = jsonl_file.stem
        err_count = 0

        with open(jsonl_file, encoding='utf-8') as f:
            for line_no, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line:
                    skipped_lines += 1
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    err_count += 1
                    print(f"[JSONL] {jsonl_file.name} L{line_no}: JSON 解析失败: {e}")
                    continue

                if not isinstance(obj, dict):
                    err_count += 1
                    print(f"[JSONL] {jsonl_file.name} L{line_no}: 非 dict 行，跳过")
                    continue

                # 初始化 9 字段全集为空
                case = {b: "" for b in FIELDS.keys()}
                # 用行内字段覆盖默认空值（仅取识别字段）
                for k, v in obj.items():
                    if k in FIELDS:
                        case[k] = "" if v is None else str(v)

                # module 兜底/强制使用文件名
                case["module"] = module_from_filename

                # category 归一
                cat_raw = case.get("category", "").strip()
                case["category"] = cat_raw.upper()

                if case["category"] not in _CAT_ORDER_MAP:
                    err_count += 1
                    print(f"[JSONL] {jsonl_file.name} L{line_no}: category={cat_raw!r} 不在 enum，跳过")
                    continue

                cases.append(case)

        if err_count > 0:
            parse_errors[jsonl_file.name] = err_count

    return cases, parse_errors, skipped_lines


# =============================================================================
# 主流程（接受 archive_dir 参数化）
# =============================================================================

def derive_csv_basename(archive_dir) -> str:
    """从归档目录名提取 CSV 文件基名（不含.csv 后缀）。

    匹配规则：^(.+_\\d{12})(?:_debug)?(?:_v\\d+)?$
    示例：
      商城需求_202608041530→ 商城需求_202608041530
      商城需求_202608041530_debug   → 商城需求_202608041530
      商城需求_202608041530_v1      → 商城需求_202608041530
      legacy_dir（不匹配）          → 测试用例（向后兼容回退）
    """
    m = re.match(r'^(.+_\d{12})(?:_debug)?(?:_v\d+)?$', Path(archive_dir).name)
    return m.group(1) if m else "测试用例"


def get_profile():
    if ACTIVE_PROFILE not in PROFILES:
        print(f"错误：ACTIVE_PROFILE={ACTIVE_PROFILE} 未在 PROFILES 中定义")
        return None
    return PROFILES[ACTIVE_PROFILE]


def run(archive_dir, profile_yaml_path: Path = None) -> int:
    """就地转换入口。archive_dir 为归档目录（绝对或相对路径均可）。

    Returns:
        0 成功；1 失败（无用例 / 输入目录不存在 / active_profile 未定义）
    """
    # 1. 装填配置（这次调用会覆盖模块级容器）
    initialize_config(profile_yaml_path)

    # 2. 派生路径
    archive_dir = Path(archive_dir).expanduser().resolve()
    temp_dir = archive_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    input_dir = archive_dir / "测试用例_模块"
    output_file = archive_dir / f"{derive_csv_basename(archive_dir)}.csv"
    stats_file = temp_dir / "_stats.json"
    feature_list_file = archive_dir / "功能点列表.md"

    profile = get_profile()
    if profile is None:
        return 1

    print("=" * 60)
    print(f"测试用例 JSONL 转 CSV 转换（Schema-Driven · 配置源: {_CFG_SOURCE}）")
    print("=" * 60)
    print(f"归档目录: {archive_dir}")
    print(f"输入目录: {input_dir}")
    print(f"输出文件: {output_file}")
    print(f"Profile Yaml: {_CFG_PATH}")
    print(f"表头 Profile: {ACTIVE_PROFILE} · {profile.get('label', '')}"
          f"{' [非交付]' if not profile.get('delivery', True) else ''}")

    if not input_dir.exists():
        print(f"错误: 输入目录不存在: {input_dir}")
        return 1

    # 解析功能点列表提取模块顺序（渲染层不再做反查，feature_point 由生成器写入）
    module_order_list = parse_module_order(feature_list_file)
    if module_order_list:
        print(f"\n从功能点列表提取到 {len(module_order_list)} 个模块顺序:")
        for i, name in enumerate(module_order_list, 1):
            print(f"  {i}. {name}")

    # 读取所有 JSONL
    all_cases, parse_errors, skipped_lines = load_jsonl(input_dir)
    jsonl_count = len(list(input_dir.glob("*.jsonl")))
    print(f"\n找到 {jsonl_count} 个 JSONL 文件，共解析到 {len(all_cases)} 条合法用例")
    if parse_errors:
        print("  解析错误汇总:")
        for f, n in parse_errors.items():
            print(f"    - {f}: {n} 行")
    if skipped_lines:
        print(f"  空行跳过: {skipped_lines} 行")

    if not all_cases:
        print("\n警告: 未解析到任何用例!")
        return 1

    # 构建模块顺序映射（未在功能点列表出现的模块自动兜底追加到末尾）
    module_order = {name: i for i, name in enumerate(module_order_list)}
    for c in all_cases:
        m = c.get("module", "")
        if m and m not in module_order:
            module_order[m] = len(module_order)

    # 排序：模块 → 子模块首次出现 → 测试点首次出现 → 分类
    submodule_first_seen = {}
    testpoint_first_seen = {}
    for c in all_cases:
        sm_key = (c["module"], c["submodule"])
        tp_key = (c["module"], c["submodule"], c["testpoint"])
        submodule_first_seen.setdefault(sm_key, len(submodule_first_seen))
        testpoint_first_seen.setdefault(tp_key, len(testpoint_first_seen))

    def sort_key(c):
        return (
            module_order.get(c["module"], 999),
            submodule_first_seen[(c["module"], c["submodule"])],
            testpoint_first_seen[(c["module"], c["submodule"], c["testpoint"])],
            _CAT_ORDER_MAP.get(c["category"], 999),
        )

    sorted_cases = sorted(all_cases, key=sort_key)

    # 按 profile 拼装表头与行数据
    resolved = [resolve_column(col, FIELDS) for col in profile["columns"]]
    header = [label for label, _bind in resolved]
    binds  = [bind for _label, bind in resolved]

    rows = [header]
    for c in sorted_cases:
        rows.append([c.get(b, "") for b in binds])

    # 写 CSV（UTF-8 with BOM 硬性要求）
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"\n[OK] CSV 生成完成!")
    print(f"   文件: {output_file}")
    print(f"   Profile: {ACTIVE_PROFILE}（{len(header)} 列）")
    print(f"   用例数: {len(sorted_cases)}")

    # ==================== 统计 + stats.json 输出 ====================

    module_stats = {}
    for c in sorted_cases:
        module_stats[c["module"]] = module_stats.get(c["module"], 0) + 1
    module_distribution = {
        m: module_stats[m]
        for m in sorted(module_stats.keys(), key=lambda x: module_order.get(x, 999))
    }

    category_stats = {}
    for c in sorted_cases:
        category_stats[c["category"]] = category_stats.get(c["category"], 0) + 1
    category_distribution = {
        cat: category_stats.get(cat, 0) for cat in CATEGORY_ORDER
    }

    source_breakdown = {}
    for cat, cnt in category_stats.items():
        gen = CATEGORY_TO_GENERATOR.get(cat, "unknown")
        source_breakdown[gen] = source_breakdown.get(gen, 0) + cnt

    stats = {
        "profile": ACTIVE_PROFILE,
        "profile_label": profile.get("label", ""),
        "delivery": profile.get("delivery", True),
        "columns": binds,
        "column_labels": header,
        "total_cases": len(sorted_cases),
        "module_distribution": module_distribution,
        "category_distribution": category_distribution,
        "source_breakdown": source_breakdown,
        "config_source": _CFG_SOURCE,
        "profile_yaml_path": str(_CFG_PATH),
        "archive_dir": str(archive_dir),
        "input_format": "jsonl",
        "parse_errors": parse_errors,
        "skipped_lines": skipped_lines,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # 终端展示
    print("\n[统计信息]")
    print("\n  模块分布:")
    for m, cnt in module_distribution.items():
        print(f"    {m}: {cnt}")

    total = len(sorted_cases)
    print("\n  分类分布:")
    for cat, cnt in category_distribution.items():
        pct = cnt / total * 100 if total else 0
        print(f"    {cat}: {cnt} ({pct:.1f}%)")

    print("\n  生成器来源分布:")
    for gen, cnt in sorted(source_breakdown.items(), key=lambda x: -x[1]):
        pct = cnt / total * 100 if total else 0
        print(f"    {gen}: {cnt} ({pct:.1f}%)")

    print(f"\n  [OK] stats.json 已输出: {stats_file}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        description="JSONL 测试用例转 CSV 转换器（就地调用式）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--archive-dir", required=True,
        help="归档目录路径。脚本会读 {archive-dir}/测试用例_模块/*.jsonl 和 功能点列表.md（仅取模块顺序），"
             "写 {archive-dir}/测试用例.csv 和 _stats.json"
    )
    p.add_argument(
        "--profile-yaml", default=None,
        help="profiles.yaml 路径覆盖。缺省时按 env(PROFILES_YAML_PATH) → 默认路径顺序回落"
    )
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    yaml_path = _resolve_profile_yaml_path(args.profile_yaml)
    return run(args.archive_dir, profile_yaml_path=yaml_path)


if __name__ == "__main__":
    sys.exit(main())
