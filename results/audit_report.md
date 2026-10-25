# 离线/联网审计报告（SSE 原始事件重放）

对每个评测 run 重放 `output/runs/{run_id}.jsonl` 原始工具事件，判定其是否实际获得外部数据。
三方对照：`baseline`（关闭 execute_command/web_search，应全程离线）、`naive`（普通联网 Agent，工具全开，应联网）、`verifier`（专家核查工作流，应联网）。

| seed | agent | 期望 | 工具调用 | 工具被拒次数 | 实际获得外部数据 | run_id |
|---|---|---|---|---|---|---|
| 7 | baseline | offline | 3 | 2 | 否 | 86c582d0 |
| 123 | baseline | offline | 0 | 0 | 否 | 1b755771 |
| 2024 | baseline | offline | 0 | 0 | 否 | 0f1f975e |
| 2025 | baseline | offline | 0 | 0 | 否 | 3cad58eb |
| 7 | naive | online | 36 | 0 | 是 | 41af77af |
| 123 | naive | online | 19 | 0 | 是 | eacd729c |
| 2024 | naive | online | 3 | 0 | 是 | b35d3faa |
| 2025 | naive | online | 5 | 0 | 是 | 6ce502a0 |
| 7 | verifier | online | 16 | 0 | 是 | 885d27dc |
| 123 | verifier | online | 3 | 0 | 是 | 7b0dcdde |
| 2024 | verifier | online | 22 | 0 | 是 | 1b330f24 |
| 2025 | verifier | online | 4 | 0 | 是 | 7fc6717f |

## 基线（baseline）被拒证据摘录

### seed 7（工具调用 3 次，获得外部数据=否）
- 工具 `load_skill` 被拒：`{"skill_status": {"skill_name": "verify-bib", "bound": false, "discovered": true, "loaded": false, "runtime": "blocked", "execution": "not_observed", `
- 工具 `record_skill_outcome` 被拒：`{   "skill_status": {     "skill_name": "verify-bib",     "bound": false,     "discovered": true,     "loaded": false,     "runtime": "blocked",     "`

### seed 123（工具调用 0 次，获得外部数据=否）
- 模型未发起任何工具调用，直接以自身知识作答（纯离线）。

### seed 2024（工具调用 0 次，获得外部数据=否）
- 模型未发起任何工具调用，直接以自身知识作答（纯离线）。

### seed 2025（工具调用 0 次，获得外部数据=否）
- 模型未发起任何工具调用，直接以自身知识作答（纯离线）。
