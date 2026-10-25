# 科研论文核查员 · SciencePal AI4Science Hackathon 2026

> 一个运行在 SciencePal 上的 **AI 科研论文核查 Agent**：自动逐条联网核验参考文献的 DOI 真伪与题录一致性、审查方法学/统计问题，并以可追溯证据（来源 URL、HTTP 状态、复算过程）产出结构化报告。配套一个**带金标准的可复现量化评测**。

## 1. 要解决的问题

学术稿件中存在两类难以人工发现、却会直接影响可信度的问题：

1. **引用幻觉 / 失效引用**：参考文献的 DOI 看似合法、格式规范，但实际并不存在（LLM 辅助写作让这一问题快速放大）。
2. **题录错配**：DOI 真实存在，但被安上了错误的年份、作者、标题或期刊；以及更深层的方法学/统计问题。

通用大模型"凭记忆"无法可靠识别这些问题——它无法分辨一个不著名但真实存在的 DOI，和一个格式合法但被篡改/编造的 DOI。本项目用 Agent 的**联网核查 + 结构化判定流程**解决，并以量化实验证明其必要性。

## 2. 方案

在 SciencePal 上构建自定义 Agent「科研论文核查员」，核心设计：

- **强制联网、禁止凭记忆**：每条引用都必须在沙箱内实际请求 Crossref（`https://api.crossref.org/works/{doi}`），记录 HTTP 200/404 与来源 URL。
- **两阶段审查**：
  - 阶段一（引用核查）：C1 DOI 有效性 → C2 元数据**逐字段严格比对**（年份/作者/标题/期刊/卷期页码，任一不一致即报错）→ C3 论断-证据一致性。
  - 阶段二（方法学）：M1 研究设计、M2 样本量与功效、M3 统计表述、M4 数据-结论复算、M5 选择性报告。
- **证据留痕 + 机器可读输出**：人类可读中文报告，末尾固定 schema 的 JSON，便于自动评测与集成。

## 3. 量化评测（Layer-1 引用核查 benchmark）

- **金标准自动构造**（脚本 `scripts/build_benchmark.py`，数据来源 Crossref REST API）：
  - `valid`：真实 DOI + 真实题录；
  - `not_found`：**过去年份、同格式后缀篡改**的 DOI，并在构造时实时请求 Crossref 确认返回 404（不依赖"未来年份"这类可被推理的线索）；
  - `mismatch`：真实 DOI 配错误题录（年份 / 作者标题 / 期刊，三类均衡）。
- **对照设计**：
  - **Verifier（本作品）**：完整联网核查 Agent；
  - **Baseline（纯模型）**：同一平台、同一模型，但通过 `agentpress_tools` 关闭 `execute_command` / `web_search`，并辅以 `web_search_on=false`；用 SSE 工具事件**审计**确认每个基线 run 都未获得外部数据（工具被拒记录为 `blocked`/`tool_unavailable`）。
- **指标**：精确率 / 召回率 / F1 / 特异度 / 准确率，对"幻觉 DOI 检测""元数据错误检测""任意问题检测"分别计算。
- **开发集 / 测试集隔离**：seed42、seed201 仅用于迭代提示词（dev）；最终指标在未参与调参的种子 7/123/2024/2025（共 48 条）上报告。

### 结果（48 条测试集，n=48）

> 数字由 `python3 scripts/run_batch.py --seeds 7 123 2024 2025 --n 12` 自动生成，见 `output/eval/summary_seeds7-123-2024-2025.json`。

| 任务 | 指标 | 纯模型基线（离线） | 核查 Agent（联网） |
|---|---|---|---|
| 幻觉 DOI 检测 | F1 | 0.621 | **1.000** |
| 幻觉 DOI 检测 | 召回率 R | 0.750 | **1.000** |
| 幻觉 DOI 检测 | 特异度（误报控制） | 0.778 | **1.000** |
| 元数据错误检测 | F1 | 0.824 | **1.000** |
| 任意问题检测 | F1 | 0.821 | **1.000** |
| 三项任务误报数合计 | FP | 8 + 6 + 9 = 23 | **0** |

**核心结论**：纯模型对"格式合法但不存在"的 DOI 缺乏可靠识别力（幻觉 DOI F1 仅 0.621，且 8 次把真实文献误判为虚假、特异度仅 0.778）；核查 Agent 在三项任务上 F1 全部为 1.000，**零误报、零漏报**。逐条明细见 `results/per_item_results.csv`，离线审计见 `results/audit_report.md`。

## 4. 项目结构

```
SciencePal/
├── .env                      # 需自行填写：SCIENCEPAL_API_KEY 等（已 gitignore，勿提交）
├── scripts/
│   ├── common.py             # 读取 .env / 路径
│   ├── sp_client.py          # SciencePal HTTP API 客户端（发起/ SSE 流/查询）
│   ├── runner.py             # 一次 Agent run：发起、收集 SSE、解析最终报告/JSON/工具
│   ├── build_benchmark.py    # Layer-1 金标准评测集生成（Crossref，可复现）
│   ├── run_eval.py           # 单个 bundle 跑某个 Agent
│   ├── run_batch.py          # 批量评测 + 离线审计 + 汇总指标
│   ├── score_eval.py         # 对齐金标准，计算 P/R/F1/特异度/准确率
│   ├── update_verifier_prompt.py  # 核查 Agent 提示词（可一键下发）
│   └── update_baseline_prompt.py  # 离线基线 Agent 提示词
├── data/eval/                # Layer-1 金标准评测集（每个 seed 一个 json，含 prompt）
└── output/eval/              # 评测结果与汇总（本地，gitignore；可按脚本复现）
```

## 5. 复现步骤

```bash
# 1) 安装依赖（Python 3.11+）
pip install httpx
# 官方 SDK（可选，脚本默认走原生 HTTP）
pip install https://sciencepal.ai/downloads/sdk/sciencepal_sdk-0.2.2-py3-none-any.whl

# 2) 配置 .env
#    SCIENCEPAL_API_KEY=sp_live_xxx
#    BASE_URL=https://sciencepal.ai/api
#    VERIFIER_AGENT_ID=<核查 Agent ID>
#    GENERAL_AGENT_ID=<离线基线 Agent ID>

# 3) 生成评测集（已包含在 data/eval；如需重建）
python3 scripts/build_benchmark.py --n 12 --seed 7

# 4) 批量跑对照评测（含离线审计）
python3 scripts/run_batch.py --seeds 7 123 2024 2025 --n 12

# 5) 单独查看某个 bundle 的评分
python3 scripts/score_eval.py --bundle data/eval/layer1_seed7_n12.json \
    --result output/eval/layer1_seed7_n12__verifier.json
```

### 两个 Agent 的配置要点（也可在 SciencePal 网页端创建）

- **核查 Agent**：`runtime_agent_type=general`，工具默认开启（需要 `execute_command` 联网）；系统提示词见 `scripts/update_verifier_prompt.py`。
- **离线基线 Agent**：同样 `general`，但通过 `PUT /agents/{id}` 设置
  `agentpress_tools={"execute_command":{"enabled":false},"web_search":{"enabled":false}}`，
  并在发起时传 `web_search_on=false`；提示词见 `scripts/update_baseline_prompt.py`。

## 6. 数据与伦理

- 评测数据全部来自公开的 Crossref 元数据；金标准 DOI 状态在构造时实时核验。
- 评测只使用论文题录（不含付费全文），不存储任何个人信息。
- 方法定位为"辅助审稿/作者自检"，最终判定保留人工复核环节（suspect 即提示人工介入）。

## 7. 局限与后续

- Layer-1 当前为题录层；Layer-2 正在补充**真实 PMC 开放获取论文端到端方法学审查**与**撤稿论文（Retraction Watch）识别**的小样本案例。
- 元数据比对对"在线优先/正式见刊多年份"等 Crossref 多日期场景仍有边界情况，报告中以证据原文呈现。
- 可扩展更多数据源（PubMed、Semantic Scholar、OpenAlex）与中文文献库。
