# 已迁移目录说明

## 变更历史

### P0（2026-07-29）· 权威脚本迁移
原 `md2csv.py` 从本目录移除，权威脚本迁至：
```
{SKILL_DIR}/scripts/md2csv.py
```

### P2（本次改造）· 就地调用式
本目录**永久保持为空**（保留仅为历史迁移说明）。
Aggregator 已改为就地调用，**不再向任何归档目录复制脚本或配置**：

```powershell
# 唯一入口：
python {SKILL_DIR}\scripts\run_pipeline.py --archive-dir {归档目录}
```

## 变更原因

架构重构目标：
- **消除双副本**：原本 `aggregator/scripts/md2csv.py` 与 `md2csv-converter/scripts/md2csv_template.py` 并存 → P0 已解决
- **就地调用式**：脚本 + 配置全部留在上游 skill；归档目录只放 MD 源与产物（CSV / stats / report / 聚合报告）→ P2 已解决
- **沙箱化前置**：aggregator 步骤 2 从 3 条 Copy-Item 变为 0，达成"零文件复制"（沙箱最小写权限）
- **Vibe coding 铺垫**：脚本入口统一为 CLI（`--archive-dir` / `--profile-yaml`），后续加运行时字段覆盖能力时改动局部

## 历史归档目录说明

已存在的 `output/*/` 归档目录里若仍有旧的 `md2csv.py` 副本，**不受影响**：这些是自包含副本，可继续独立执行。
新增归档目录一律走 `run_pipeline.py --archive-dir` 就地调用。
