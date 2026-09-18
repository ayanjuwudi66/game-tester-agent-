#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aggregator 编排入口：一条命令完成 md2csv → validate → 汇总摘要。

【设计】
- in-process 复用（`from md2csv import run as md2csv_run` / validate 同款），
  避免子进程 stdio 编码问题；同一 Python 进程只需初始化一次
- 顺序：md2csv.run() → validate.run()（validate 依赖 md2csv 的产物）
- 任一步失败即中止并返回非零退出码

【使用】
    # 最常见：一条命令完成
    python run_pipeline.py --archive-dir output/需求名_202607291611/

    # 仅生成 CSV 不做校验
    python run_pipeline.py --archive-dir output/xxx/ --skip-validate

    # 覆盖 profiles.yaml 路径
    python run_pipeline.py --archive-dir output/xxx/ --profile-yaml /path/to/profiles.yaml

【退出码】
    0 = 全部成功
    2 = md2csv 失败（validate 未执行）
    1 = md2csv 成功但 validate FAIL

【日后扩展】
- 需要进程隔离时（例如沙箱要求纯子进程），可加 --use-subprocess 走 subprocess.run。
  当前默认 in-process 以避免 Windows PowerShell 下的子进程 stdio 编码坑。
"""

import sys
import io
import json
import argparse
from pathlib import Path

# Windows 中文输出兼容（放在其他 import 之前）
# 用属性打标，避免被 md2csv/validate import 时重复包装 → 前一层 wrapper 被 GC 关闭
if sys.platform == 'win32' and not getattr(sys.stdout, '_utf8_wrapped', False):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    sys.stdout._utf8_wrapped = True
    sys.stderr._utf8_wrapped = True

SCRIPT_DIR = Path(__file__).resolve().parent

# 确保能 import 同目录下的 md2csv / validate 模块
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import md2csv          # noqa: E402
import validate        # noqa: E402


def _load_json_safe(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def build_parser():
    p = argparse.ArgumentParser(
        description="Aggregator 编排入口：md2csv → validate 一条龙",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--archive-dir", required=True,
        help="归档目录路径。转发给 md2csv.py 与 validate.py 的 --archive-dir"
    )
    p.add_argument(
        "--profile-yaml", default=None,
        help="profiles.yaml 路径覆盖。转发给下游脚本"
    )
    p.add_argument(
        "--skip-validate", action="store_true",
        help="只跑 md2csv 不跑 validate（快速迭代用；正式聚合不建议）"
    )
    return p


def print_banner(title: str):
    print("\n" + "=" * 60)
    print(f"[run_pipeline] {title}")
    print("=" * 60)


def print_final_summary(archive_dir: Path, md2csv_rc: int, validate_rc,
                        skip_validate: bool):
    """从 archive_dir 读 _stats.json + _validate_report.json 打印统一摘要。"""
    print_banner("Pipeline Summary")

    stats = _load_json_safe(archive_dir / "temp" / "_stats.json")
    if stats:
        print(f"Profile        : {stats.get('profile')} · {stats.get('profile_label', '')}"
              f"{' [非交付]' if not stats.get('delivery', True) else ''}")
        print(f"配置源         : {stats.get('config_source')} ({stats.get('profile_yaml_path')})")
        print(f"用例总数       : {stats.get('total_cases')}")
        print(f"模块数         : {len(stats.get('module_distribution', {}))}")
        cat_dist = stats.get('category_distribution', {})
        print(f"分类分布       : " + ", ".join(f"{k}={v}" for k, v in cat_dist.items() if v))
    else:
        print("Stats          : (未读到 _stats.json)")

    if skip_validate:
        print("Validate       : (跳过)")
    else:
        report = _load_json_safe(archive_dir / "temp" / "_validate_report.json")
        if report:
            print(f"Validate       : {report.get('overall')}  "
                  f"[passed={len(report.get('passed', []))} "
                  f"failed={len(report.get('failed', []))} "
                  f"warnings={len(report.get('warnings', []))}]")
            for msg in report.get('failed', []):
                print(f"  ❌ {msg}")
        else:
            print("Validate       : (未读到 _validate_report.json)")

    # 退出码汇总
    if md2csv_rc != 0:
        rc = 2
    elif not skip_validate and validate_rc and validate_rc != 0:
        rc = 1
    else:
        rc = 0
    print(f"\nExit Code      : {rc}")
    print("=" * 60)
    return rc


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    archive_dir = Path(args.archive_dir).expanduser().resolve()
    yaml_override = Path(args.profile_yaml).expanduser().resolve() if args.profile_yaml else None

    # Step 1: md2csv
    print_banner("Step 1/2  md2csv (MD → CSV + stats.json)")
    md2csv_rc = md2csv.run(archive_dir, profile_yaml_path=yaml_override)
    if md2csv_rc != 0:
        print(f"\n[run_pipeline] md2csv 失败 (rc={md2csv_rc})；跳过 validate 并退出")
        return print_final_summary(archive_dir, md2csv_rc, None,
                                   skip_validate=args.skip_validate)

    # Step 2: validate（可选跳过）
    validate_rc = None
    if not args.skip_validate:
        print_banner("Step 2/2  validate (CSV/MD 校验 → validate_report.json)")
        validate_rc = validate.run(archive_dir, profile_yaml_path=yaml_override)
    else:
        print("\n[run_pipeline] --skip-validate 生效，跳过 validate 步骤")

    return print_final_summary(archive_dir, md2csv_rc, validate_rc,
                               skip_validate=args.skip_validate)


if __name__ == "__main__":
    sys.exit(main())
