#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV 格式验证脚本（Schema-Driven · 就地调用式· JSONL 输入）

【功能】
- 检查 CSV 是否含 UTF-8 BOM（EF BB BF）
- 按 active_profile 校验表头列名与列数
- 检查 category列的合法性（enum 由 profiles.yaml 定义）
- 对比JSONL 用例总数 vs CSV 数据行数
- 校验三级聚合排序（模块 → 子模块 → 测试点→ 分类）
- 校验 required 字段非空
- JSONL schema 检查（每行必须是 dict、必有合法 category）
- 【新增】禁词校验：聚合词/复合边界/预期套话（warnings 级别，不阻塞）

【就地调用模式】
    python validate.py --archive-dir output/xxx/
    python validate.py --archive-dir output/xxx/ --profile-yaml /path/to/profiles.yaml

【输入】
    {archive_dir}/{需求名}_{YYYYMMDDHHmm}.csv    # md2csv.py输出（文件名由目录名派生）
    {archive_dir}/测试用例_模块/*.jsonl           # 生成器append输出

【输出】
    {archive_dir}/temp/_validate_report.json      # 结构化验证报告
    stdout汇总# 通过/失败/警告项

【退出码】
    0 = PASS（无failed 项）
    1 = FAIL（存在 failed 项）
"""

import os
import re
import csv
import json
import sys
import io
import argparse
from pathlib import Path

# Windows 中文输出兼容
if sys.platform == 'win32' and not getattr(sys.stdout, '_utf8_wrapped', False):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    sys.stdout._utf8_wrapped = True
    sys.stderr._utf8_wrapped = True

SCRIPT_DIR = Path(__file__).resolve().parent

# 确保能import 同目录下的 md2csv 模块
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from md2csv import derive_csv_basename  # noqa: E402

DEFAULT_PROFILE_YAML = (
    SCRIPT_DIR.parent / "references" / "profiles.yaml"
)


# =============================================================================
# Profile 加载（与 md2csv.py 使用相同寻址策略）
# =============================================================================

def _fallback_config():
    return {
        "active_profile": "A_legacy",
        "category_order": ["HX", "FHX", "BL", "BJ", "YC", "FCG", "ZD"],
        "fields": {
            "module":        {"label_default": "模块",       "required": True},
            "submodule":     {"label_default": "子模块",     "required": True},
            "feature_point": {"label_default": "功能点",     "required": True},
            "testpoint":     {"label_default": "测试点",     "required": True},
            "case_desc":     {"label_default": "用例描述"},
            "precondition":  {"label_default": "前提条件",   "required": True},
            "steps":         {"label_default": "测试步骤",   "required": True},
            "expected":      {"label_default": "预期结果",   "required": True},
            "category":      {"label_default": "用例分类",   "required": True,
                              "enum": ["HX", "FHX", "BL", "BJ", "YC", "FCG", "ZD"]},
        },
        "profiles": {
            "A_legacy": {
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
                "columns": [
                    {"bind": "module"}, {"bind": "submodule"}, {"bind": "feature_point"},
                    {"bind": "testpoint"}, {"bind": "precondition"}, {"bind": "steps"},
                    {"bind": "expected"}, {"bind": "category"},
                ],
            },
        },
    }


def _resolve_profile_yaml_path(cli_override: str = None) -> Path:
    if cli_override:
        return Path(cli_override).expanduser().resolve()
    env_path = os.environ.get("PROFILES_YAML_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return DEFAULT_PROFILE_YAML


def load_config(profile_yaml_path: Path = None):
    yaml_path = profile_yaml_path or DEFAULT_PROFILE_YAML
    if not yaml_path.exists():
        return _fallback_config(), "fallback", yaml_path
    try:
        import yaml
        with open(yaml_path, encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        return cfg, "yaml", yaml_path
    except Exception:
        return _fallback_config(), "fallback", yaml_path


# =============================================================================
# 校验主体（封装在 Validator 类）
# =============================================================================

class Validator:
    """封装一次校验的全部状态。archive_dir + profile_yaml_path 决定 IO 与配置。"""

    def __init__(self, archive_dir, profile_yaml_path: Path = None):
        self.archive_dir = Path(archive_dir).expanduser().resolve()
        self.temp_dir = self.archive_dir / "temp"
        self.temp_dir.mkdir(exist_ok=True)
        self.csv_file = self.archive_dir / f"{derive_csv_basename(self.archive_dir)}.csv"
        self.jsonl_dir = self.archive_dir / "测试用例_模块"
        self.report_file = self.temp_dir / "_validate_report.json"

        # 加载配置
        self.cfg, self.cfg_source, self.cfg_path = load_config(profile_yaml_path)
        self.fields = self.cfg["fields"]
        self.category_order = self.cfg["category_order"]
        self.cat_order_map = {c: i for i, c in enumerate(self.category_order)}
        self.profiles = self.cfg["profiles"]
        self.active_profile = os.environ.get("ACTIVE_PROFILE") or self.cfg.get("active_profile", "A_legacy")

        # 解析当前 profile 列绑定
        self.active_cols = self._resolve_columns(self.active_profile)
        self.expected_header = [label for label, _ in self.active_cols]
        self.binds = [bind for _, bind in self.active_cols]
        try:
            self.category_col = next(i for i, b in enumerate(self.binds) if b == "category")
        except StopIteration:
            self.category_col = None

        self.results = {"passed": [], "failed": [], "warnings": []}

    def _resolve_columns(self, profile_name):
        prof = self.profiles[profile_name]
        result = []
        for col in prof["columns"]:
            bind = col["bind"]
            label = col.get("label") or self.fields.get(bind, {}).get("label_default") or bind
            result.append((label, bind))
        return result

    # ---------- 各项检查 ----------

    def check_bom(self):
        if not self.csv_file.exists():
            self.results["failed"].append(f"BOM检测: CSV 文件不存在 {self.csv_file}")
            return False
        with open(self.csv_file, "rb") as f:
            bom = f.read(3)
        if bom == b'\xef\xbb\xbf':
            self.results["passed"].append("BOM检测: UTF-8 BOM 存在 ✅")
            return True
        self.results["failed"].append(f"BOM检测: 文件开头不是 UTF-8 BOM，实际为 {bom.hex()}")
        return False

    def read_csv(self):
        with open(self.csv_file, encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            data_rows = list(reader)
        return header, data_rows

    def check_header(self, header):
        if header == self.expected_header:
            self.results["passed"].append(
                f"表头校验: profile={self.active_profile}（{len(self.expected_header)} 列）✅"
            )
        else:
            self.results["failed"].append(
                f"表头校验: 期望 {self.expected_header}，实际 {header}"
            )

    def check_category_legality(self, data_rows):
        if self.category_col is None:
            self.results["warnings"].append("分类合法性: 当前 profile 缺少 category 列，跳过")
            return
        enum = self.fields.get("category", {}).get("enum", self.category_order)
        illegal = [
            (i + 2, r[self.category_col])
            for i, r in enumerate(data_rows)
            if len(r) > self.category_col and r[self.category_col] not in enum
        ]
        if not illegal:
            self.results["passed"].append(f"分类合法性: 所有分类均属于 {enum} ✅")
        else:
            self.results["failed"].append(f"分类合法性: 以下行包含非法分类: {illegal[:5]}")

    def count_jsonl_cases(self):
        """统计 JSONL 目录下所有 .jsonl 文件的合法用例行数。

        规则：
          - 空行跳过（不计错误）
          - 非 dict 或缺 category → 计错误、跳过
          - category ∈ enum → 计入 md_total（沿用旧命名，本质是"源用例数"）
          - json.loads 失败 → 计错误、跳过
        同时输出 schema 检查报告（jsonl_schema_errors）。
        """
        if not self.jsonl_dir.is_dir():
            self.results["warnings"].append(f"JSONL 目录不存在: {self.jsonl_dir}，跳过行数对比")
            return None, {}

        enum = self.fields.get("category", {}).get("enum", self.category_order)
        total = 0
        schema_errors = {}  # {filename: [error_msg, ...]}

        for fname in sorted(os.listdir(self.jsonl_dir)):
            if not fname.endswith(".jsonl"):
                continue
            fpath = self.jsonl_dir / fname
            file_errors = []

            with open(fpath, encoding='utf-8') as f:
                for line_no, raw in enumerate(f, start=1):
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError as e:
                        file_errors.append(f"L{line_no}: JSON 解析失败 {e}")
                        continue
                    if not isinstance(obj, dict):
                        file_errors.append(f"L{line_no}: 非 dict 行")
                        continue
                    cat = str(obj.get("category", "")).strip().upper()
                    if not cat:
                        file_errors.append(f"L{line_no}: 缺失 category")
                        continue
                    if cat not in enum:
                        file_errors.append(f"L{line_no}: 非法 category={cat!r}")
                        continue
                    total += 1

            if file_errors:
                schema_errors[fname] = file_errors

        return total, schema_errors

    def check_row_count(self, data_rows):
        source_total, schema_errors = self.count_jsonl_cases()
        if source_total is None:
            return

        # 汇报 JSONL schema
        if schema_errors:
            summary = ", ".join(f"{k}({len(v)})" for k, v in schema_errors.items())
            self.results["warnings"].append(f"JSONL Schema: 有异常行 {summary}")
        else:
            self.results["passed"].append("JSONL Schema: 所有行合法 ✅")

        csv_total = len(data_rows)
        if source_total == csv_total:
            self.results["passed"].append(f"行数对比: JSONL({source_total}) == CSV({csv_total}) ✅")
        else:
            self.results["failed"].append(
                f"行数对比: JSONL({source_total}) != CSV({csv_total})，差值={csv_total - source_total}"
            )

    def check_sort_order(self, data_rows):
        """校验三级聚合排序：子模块 → 测试点 → 分类"""
        sub_col = next((i for i, b in enumerate(self.binds) if b == "submodule"), None)
        tp_col = next((i for i, b in enumerate(self.binds) if b == "testpoint"), None)
        if sub_col is None or tp_col is None or self.category_col is None:
            self.results["warnings"].append("排序验证: 当前 profile 缺少必要列，跳过")
            return

        submodule_order, testpoint_order = {}, {}
        for r in data_rows:
            if len(r) <= self.category_col:
                continue
            sm, tp = r[sub_col], r[tp_col]
            submodule_order.setdefault(sm, len(submodule_order))
            testpoint_order.setdefault(tp, len(testpoint_order))

        order_errors = []
        prev_key = (-1, -1, -1)
        for i, r in enumerate(data_rows):
            if len(r) <= self.category_col:
                continue
            sm_pri = submodule_order.get(r[sub_col], 999)
            tp_pri = testpoint_order.get(r[tp_col], 999)
            cat_pri = self.cat_order_map.get(r[self.category_col], 999)
            key = (sm_pri, tp_pri, cat_pri)
            if key < prev_key:
                order_errors.append(
                    f"第{i + 2}行排序异常: {r[sub_col]} / {r[tp_col]} / {r[self.category_col]}"
                )
            prev_key = key

        if not order_errors:
            self.results["passed"].append("排序验证: 测试点聚合顺序正确 ✅")
        else:
            self.results["warnings"].append(
                f"排序验证: {len(order_errors)} 处乱序，首个: {order_errors[0]}"
            )

    def check_required_fields(self, data_rows):
        """校验 required 字段的值不为空"""
        required_binds = [b for b, meta in self.fields.items()
                          if meta.get("required") and b in self.binds]
        empty_counts = {b: 0 for b in required_binds}
        for r in data_rows:
            for b in required_binds:
                idx = self.binds.index(b)
                if idx < len(r) and not r[idx].strip():
                    empty_counts[b] += 1

        total_empty = sum(empty_counts.values())
        if total_empty == 0:
            self.results["passed"].append(f"必填字段: 全部 required 字段无空值 ✅")
        else:
            detail = {b: n for b, n in empty_counts.items() if n > 0}
            self.results["warnings"].append(f"必填字段: 检测到 {total_empty} 个空值 {detail}")

    def check_forbidden_phrases(self, data_rows):
        """扫描 CSV 每行的 case_desc/steps/expected，检查三类禁词（warnings级别，不阻塞）。

        三类禁词：
          1. 聚合词（BL用例禁止）：在 case_desc/steps 中出现聚合遍历表达
             → 每档、每种、遍历+宾语、全部.*页签、各.*档、中文/英文/数字（并列输入类型）
          2. 复合边界（BJ 用例禁止）：在 case_desc/steps 中出现斜杠分隔的多值边界
             → 形如 "xxx/yyy" 且两侧均含数值/状态词
          3. 预期套话：在 expected 中出现空泛套话，不描述可验证的具体结果
        """
        # ── 列索引 ──────────────────────────────────────────────────
        def _col(bind_name):
            try:
                return self.binds.index(bind_name)
            except ValueError:
                return None

        desc_col= _col("case_desc")
        steps_col  = _col("steps")
        exp_col    = _col("expected")
        cat_col    = self.category_col

        # ── 正则模式 ─────────────────────────────────────────────────
        # 类型1：聚合词（case_desc / steps）
        AGGREGATE_PATTERNS = [
            re.compile(r'每[档种]'),                          # 每档、每种
            re.compile(r'遍历.{0,8}(全部|所有|各)'),          # 遍历...全部/所有/各
            re.compile(r'全部.{0,8}页签'),                    # 全部...页签
            re.compile(r'所有.{0,8}类型'),                    # 所有...类型
            re.compile(r'各.{0,4}[档级]'),                   # 各...档/级
            re.compile(r'[全各][部种].{0,6}(操作|方式|类型)'), # 全部/各种...操作/方式/类型
        ]

        # 类型2：复合边界（case_desc / steps）—— 斜杠分隔的多值边界
        COMPOSITE_BOUNDARY_PATTERNS = [
            re.compile(r'-?\d+[°度%]?\s*/\s*-?\d+[°度%]?'),  # 数值/数值（如 -180°/360°）
            re.compile(r'(空|0|最小|最少)\s*/\s*(满|最大|最多|\d+)'),  # 空/满、0/最大
            re.compile(r'(最小|最少|最低)\s*/\s*(最大|最多|最高)'),   # 最小/最大
            re.compile(r'[开关启停]\s*/\s*[开关启停]'),         # 开/关、启/停
        ]

        # 类型3：预期套话（expected）
        EXPECTED_CLICHE_PATTERNS = [
            re.compile(r'界面正常[加载显示]'),
            re.compile(r'操作结果符合预期'),
            re.compile(r'(操作|功能|系统|页面)\s*正常'),# "操作正常"、"功能正常"等
            re.compile(r'无[异错]常'),# "无异常"、"无错常"
            re.compile(r'正常[加载打开跳]'),                   # "正常加载"、"正常打开" 等（非"数据正常加载N条"）
        ]

        # ── 扫描 ──────────────────────────────────────────────────────
        agg_hits, bound_hits, cliche_hits = [], [], []

        for row_idx, r in enumerate(data_rows, start=2):  # start=2:跳过表头，行号从2起

            def _cell(col_idx):
                if col_idx is None or col_idx >= len(r):
                    return ""
                return r[col_idx]

            case_text= _cell(desc_col)
            steps_text = _cell(steps_col)
            exp_text   = _cell(exp_col)
            category= _cell(cat_col).strip().upper()

            # 类型1：聚合词（BL 用例重点检查，其他也检查）
            for pat in AGGREGATE_PATTERNS:
                for field_name, text in [("case_desc", case_text), ("steps", steps_text)]:
                    m = pat.search(text)
                    if m:
                        agg_hits.append(
                            f"第{row_idx}行[{field_name}]聚合词: {m.group()!r}→每个组合应独立成一条用例"
                        )
                        break# 一个字段只报一次

            # 类型2：复合边界（BJ 用例重点检查，其他也检查）
            for pat in COMPOSITE_BOUNDARY_PATTERNS:
                for field_name, text in [("case_desc", case_text), ("steps", steps_text)]:
                    m = pat.search(text)
                    if m:
                        bound_hits.append(
                            f"第{row_idx}行[{field_name}] 复合边界: {m.group()!r}  → 每个边界值应独立成一条用例"
                        )
                        break

            # 类型3：预期套话
            for pat in EXPECTED_CLICHE_PATTERNS:
                m = pat.search(exp_text)
                if m:
                    # 排除误判：若包含具体数量词则放行（如"数据正常加载3条"）
                    if re.search(r'\d+\s*条', exp_text):
                        continue
                    cliche_hits.append(
                        f"第{row_idx}行[expected] 预期套话: {m.group()!r}  → 应描述可观测的具体结果"
                    )
                    break

        # ── 汇总 ──────────────────────────────────────────────────────
        if not (agg_hits or bound_hits or cliche_hits):
            self.results["passed"].append("禁词校验: 未检出聚合词/复合边界/预期套话 ✅")
        else:
            total = len(agg_hits) + len(bound_hits) + len(cliche_hits)
            summary = (
                f"禁词校验: 共{total} 处警告 "
                f"（聚合词 {len(agg_hits)} | 复合边界 {len(bound_hits)} | 预期套话 {len(cliche_hits)}）"
            )
            self.results["warnings"].append(summary)
            # 每类最多上报前3条，避免刷屏
            for hit in (agg_hits + bound_hits + cliche_hits)[:9]:
                self.results["warnings"].append(f"  └─ {hit}")

    # ---------- 主入口 ----------

    def run(self) -> int:
        print("=" * 60)
        print(f"CSV 格式验证（Schema-Driven · 配置源: {self.cfg_source}）")
        print("=" * 60)
        print(f"归档目录       : {self.archive_dir}")
        print(f"CSV 文件       : {self.csv_file}")
        print(f"JSONL 目录     : {self.jsonl_dir}")
        print(f"Profile Yaml   : {self.cfg_path}")
        print(f"Active Profile : {self.active_profile}（{len(self.expected_header)} 列）")

        if not self.check_bom():
            return self._finalize()

        try:
            header, data_rows = self.read_csv()
        except Exception as e:
            self.results["failed"].append(f"CSV 读取失败: {e}")
            return self._finalize()

        self.check_header(header)
        self.check_category_legality(data_rows)
        self.check_row_count(data_rows)      # 含JSONL schema汇报
        self.check_sort_order(data_rows)
        self.check_required_fields(data_rows)
        self.check_forbidden_phrases(data_rows)  # 禁词校验（warnings级别）

        return self._finalize(total=len(data_rows))

    def _finalize(self, total=0) -> int:
        report = {
            "profile": self.active_profile,
            "expected_header": self.expected_header,
            "total_cases": total,
            "config_source": self.cfg_source,
            "profile_yaml_path": str(self.cfg_path),
            "archive_dir": str(self.archive_dir),
            "input_format": "jsonl",
            "passed": self.results["passed"],
            "failed": self.results["failed"],
            "warnings": self.results["warnings"],
            "overall": "PASS" if not self.results["failed"] else "FAIL",
        }
        with open(self.report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n{'=' * 60}")
        print(f"验证结果: {report['overall']}")
        print(f"总用例数: {report['total_cases']}")
        print(f"通过项  : {len(self.results['passed'])}")
        print(f"失败项  : {len(self.results['failed'])}")
        print(f"警告项  : {len(self.results['warnings'])}")
        for msg in self.results['passed']:
            print(f"  ✅ {msg}")
        for msg in self.results['warnings']:
            print(f"  ⚠️  {msg}")
        for msg in self.results['failed']:
            print(f"  ❌ {msg}")
        print("=" * 60)

        return 0 if report['overall'] == 'PASS' else 1


# =============================================================================
# CLI 入口
# =============================================================================

def build_parser():
    p = argparse.ArgumentParser(
        description="测试用例 CSV 格式验证（就地调用式 · JSONL 输入）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--archive-dir", required=True,
        help="归档目录路径。脚本会读 {archive-dir}/测试用例.csv 与 测试用例_模块/*.jsonl，"
             "写 {archive-dir}/_validate_report.json"
    )
    p.add_argument(
        "--profile-yaml", default=None,
        help="profiles.yaml 路径覆盖。缺省时按 env(PROFILES_YAML_PATH) → 默认路径顺序回落"
    )
    return p


def run(archive_dir, profile_yaml_path: Path = None) -> int:
    """暴露给 run_pipeline.py 的 in-process 调用入口。"""
    yaml_path = profile_yaml_path or _resolve_profile_yaml_path(None)
    v = Validator(archive_dir, yaml_path)
    return v.run()


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    yaml_path = _resolve_profile_yaml_path(args.profile_yaml)
    return run(args.archive_dir, profile_yaml_path=yaml_path)


if __name__ == "__main__":
    sys.exit(main())
