# 科研论文核查员 · SciencePal AI4Science Hackathon 2026

> 一个运行在 SciencePal 上的 **AI 科研论文核查 Agent**：自动逐条联网核验参考文献的 DOI 真伪与题录一致性、审查方法学/统计问题，并以可追溯证据（来源 URL、HTTP 状态、复算过程）产出结构化报告。配套一个**带金标准的可复现量化评测**。

## 1. 要解决的问题

学术稿件中存在两类难以人工发现、却会直接影响可信度的问题：

1. **引用幻觉 / 失效引用**：参考文献的 DOI 看似合法、格式规范，但实际并不存在（LLM 辅助写作让这一问题快速放大）。
2. **题录错配**：DOI 真实存在，但被安上了错误的年份、作者、标题或期刊；以及更深层的方法学/统计问题。

通用大模型"凭记忆"无法可靠识别这些问题，它无法分辨一个不著名但真实存在的 DOI，和一个格式合法但被篡改/编造的 DOI。本项目用 Agent 的**联网核查 + 结构化判定流程**解决，并以量化实验证明其必要性。

## 2. 方案

在 SciencePal 上构建自定义 Agent「科研论文核查员」，核心设计：

- **强制联网、禁止凭记忆**：每条引用都必须在沙箱内实际请求 Crossref（`https://api.crossref.org/works/{doi}`），记录 HTTP 200/404 与来源 URL。
- **两阶段审查**：
  - 阶段一（引用与出版状态核查）：C1 DOI 有效性 → C2 元数据**逐字段严格比对**（年份/作者/标题/期刊/卷期页码，任一不一致即报错）→ C3 论断-证据一致性 → C4 出版状态（撤稿），覆盖标题前缀/后缀的 RETRACTED 标记、`relation` 的 has-retraction 关系与期刊页标注。
  - 阶段二（方法学）：M1 研究设计、M2 样本量与功效、M3 统计表述、M4 数据-结论复算（沙箱内实际运行 scipy）、M5 选择性报告。
- **证据留痕 + 机器可读输出**：人类可读中文报告，末尾固定 schema 的 JSON，便于自动评测与集成；不调用与核查无关的工具，不写入长期记忆。
- **代码级 guardrail（不是提示词说了算）**：逐事件监视 SSE，出现被禁工具（`save_memory` / 反问 / 浏览器接管）立即 `POST /agent-run/{id}/stop` 并下发纠正指令续跑；最终 JSON 必须通过"结构 / 覆盖 1..N / 证据 URL 齐备 / 判定自洽"四类机械校验，失败自动回喂错误并限 2 轮修复。实测平台配置层**关不掉**记忆工具（9 种写法全无效），所以这一层只能写在代码里。

## 3. 量化评测（Layer-1 引用核查 benchmark）

- **金标准自动构造**（脚本 `scripts/build_benchmark.py`，数据来源 Crossref REST API）：
  - `valid`：真实 DOI + 真实题录；
  - `not_found`：**过去年份、同格式后缀篡改**的 DOI，并在构造时实时请求 Crossref 确认返回 404（不依赖"未来年份"这类可被推理的线索）；
  - `mismatch`：真实 DOI 配错误题录（年份 / 作者标题 / 期刊，三类均衡）。
- **三方对照（避免稻草人基线）**：
  - **离线基线**：同一平台、同一模型，通过 `agentpress_tools` 关闭 `execute_command` / `web_search` 并传 `web_search_on=false`，SSE 审计确认未获得外部数据。
  - **普通联网 Agent**：与本作品**完全相同的模型与工具权限、沙箱全开、能联网**，只给最低限度的取证要求（联网、用 curl 取证、不反问、不等待人工、不写记忆），不提供 C1-C4/M1-M5 专家流程。它隔离的是"流程"这一变量，代表"被要求联网取证、但没有专家流程的 Agent"，并非完全无引导的裸 Agent（边界见技术报告 2.3）。
  - **专家核查工作流（本作品）**：同样全开工具，另在系统提示词固化 C1-C4 / M1-M5 流程。
- **指标**：精确率 / 召回率 / F1 / 特异度 / 准确率，对"幻觉 DOI 检测""元数据错误检测""任意问题检测"分别计算；并记录工具调用数、状态污染、输出位置等过程指标。
- **开发集 / 测试集隔离**：seed42、seed201 仅用于迭代提示词（dev）；最终指标在未参与调参的种子 7/123/2024/2025（共 48 条）上报告。

### 3.1 代码级 guardrail：从"观测到没违规"到"机制上不放过"（6 个注入用例）

稿件内容是不可信输入。我们构造 6 个注入用例（CSV 交付、写记忆、不必联网、替作者辩护、改 schema、只查前 3 条），题录与金标准不变，同一判据比较"有无 guardrail"：

| 指标 | 无 guardrail | 有 guardrail |
|---|---|---|
| 交付可用（可解析 + 四类校验全过） | 4/6 | **6/6** |
| 契约违规 | 2 | 0 |
| 运行时中断 / 自动修复 | 0 / 0 | 1 / 4 |

两个失败样例：覆盖截断（F1=0）与契约破坏（F1=0），有 guardrail 时均被修复为合规交付。校验器本身另做故障注入：6 类失败模式 × 3 来源 = 18 例，**18/18 检出、0 误报**。
把同一契约套回全部 35 个 run（专家/普通/离线三组均为契约定稿前跑出）：专家流程 5/5、guardrail 开启 11/11、guardrail 关闭 5/7、普通联网 Agent 2/4、离线基线 0/7。普通联网 Agent 的失败是"证据张冠李戴"（对 3 个不存在的 DOI 填了最接近的真实 DOI，F1 仍 1.000，但点开链接是另一篇文献）。
诚实边界：拦截只能中断、不能撤销已执行的写入（两组"写入实际发生"均为 1/6）；修复代价为平均 token +82%。完整协议与逐例数据见 [`results/guardrail/PROTOCOL.md`](results/guardrail/PROTOCOL.md)。

<!-- CLEAN48_START -->
> 干净 48 条（4 个 seed × 12 条）guardrail 复跑：**4/4 可用**，契约违规 **0** 次，自动修复 **0** 次、拦截 **0** 次；F1 1.000，与无 guardrail 组一致（无回归）。
<!-- CLEAN48_END -->

### 3.2 补充实验：换模型与真实书目

- **换模型复现**：同一批 48 条换 `deepseek-v4-pro`，4 个 seed 的 F1 仍全为 1.000、guardrail 零干预（平均耗时 152.6s vs flash 78.7s）。
- **真实已发表论文的书目**：取一篇 2024 年真实论文的 Crossref 参考文献表（50 条可核对，其中 4 条年份与原文不符），模型 4/4 检出、0 误报。
- 明细：`results/guardrail/SUMMARY_extras.md`；构造脚本 `scripts/build_realworld.py`。

### 结果（48 条测试集，n=48）

> 数字由 `scripts/run_batch.py` 与 `scripts/run_naive.py` 自动生成，汇总见 `scripts/export_results.py` 与 `results/metrics_summary.csv`。

| 任务 | 指标 | 离线基线 | 普通联网 Agent | 专家核查工作流 |
|---|---|---|---|---|
| 幻觉 DOI 检测 | F1 | 0.621 | 1.000 | 1.000 |
| 幻觉 DOI 检测 | 特异度（误报控制） | 0.778 | 1.000 | 1.000 |
| 元数据错误检测 | F1 | 0.824 | 1.000 | 1.000 |
| 任意问题检测 | F1 | 0.821 | 1.000 | 1.000 |
| 三项任务误报数合计 | FP | 23 | 0 | 0 |

**核心结论（诚实三方对照）**：决定性的能力闸门是"强制联网核验"，它把幻觉 DOI F1 从 0.621 提升到 1.000、误报从 23 降到 0；但在当前这一代强模型（deepseek-v4-flash）上，**普通联网 Agent 与专家工作流的 F1 完全相同，专家流程没有额外的判对率增益**。我们在撤稿、统计复算、冷门撤稿限定任务三个隐式案例上做同输入对照，两个联网 Agent 也都做对。

专家流程的真实价值在**可复现性、效率与可审计**而非判对率：平均工具调用更少（8.29 vs 12.43，上限 22 vs 36）、7 个 run 中没有写状态或与核查无关的调用（普通 Agent 有 1 次在提示词禁止下仍调用 save_memory）、最终 JSON 稳定出现在末轮固定 schema（普通 Agent 有 1 次落在中间轮，需改造解析器）。需要注意：这些是 n=7 对 n=7 的小样本观测、未做统计检验，save_memory 与 JSON 错位各只出现 1 次，应视为观测到的事件而非统计显著差异。**这些观测已在后续工作中被代码级 guardrail 取代**：现在拦截与 schema 校验由 `scripts/guardrail.py` + `scripts/report_schema.py` 强制执行，不再依赖模型自觉（见 3.1）。逐条明细见 `results/per_item_results.csv`，过程指标见 `results/process_reliability.json`，Layer-2 同输入对照见 `results/layer2/compare/`。

## 4. 项目结构

```
SciencePal/
├── .env                      # 需自行填写：SCIENCEPAL_API_KEY 等（已 gitignore，勿提交）
├── scripts/
│   ├── common.py             # 读取 .env / 路径
│   ├── sp_client.py          # SciencePal HTTP API 客户端（发起/ SSE 流/查询）
│   ├── runner.py             # 一次 Agent run：发起、收集 SSE、解析最终报告/JSON/工具
│   ├── build_benchmark.py    # Layer-1 金标准评测集生成（Crossref，可复现）
│   ├── run_batch.py          # 批量评测（离线基线 + 专家工作流）+ 联网审计 + 汇总
│   ├── run_naive.py          # 普通联网 Agent 批量评测（第三组对照）
│   ├── create_naive_agent.py # 创建普通联网 Agent（工具全开、不给专家流程）
│   ├── score_eval.py         # 对齐金标准，计算 P/R/F1/特异度/准确率
│   ├── verify_refs.py        # 命令行入口：真跑 / 离线回放已保存 run
│   ├── guardrail.py          # 运行时拦截 + 交付契约 + 有界自动修复（核心新增）
│   ├── report_schema.py      # 报告 JSON 契约（S/C/E/V 四类校验，零依赖）
│   ├── build_adversarial.py  # 6 个稿件注入用例（题录不变，只加注入段）
│   ├── run_guardrail_eval.py # 干预前/后对照跑批
│   ├── guardrail_fault_injection.py # 校验器故障注入（检测能力）
│   ├── analyze_guardrail.py  # 汇总可用率/违规/修复/成本
│   ├── test_guardrail_offline.py # 状态机离线断言（不需配额）
│   ├── plot_guardrail.py     # 对照图（results/figures/guardrail_compare.png）
│   ├── plot_guardrail_timeline.py # 真实拦截时间线（results/figures/guardrail_timeline.png）
│   ├── audit_contract.py     # 回溯审计：契约套到全部历史结果
│   ├── finalize_guardrail.py # 把 clean-48 结果回填进 README / 技术报告
│   ├── export_results.py     # 导出三组指标到 results/
│   ├── process_reliability.py# 过程可靠性指标（工具数/状态污染/输出位置）
│   ├── audit_runs.py         # 三组 run 的 SSE 联网审计（离线/普通/专家，验证对照公平）
│   ├── add_verifier_c4.py    # 幂等下发 C4 撤稿检查
│   ├── run_layer2_compare.py # Layer-2 撤稿/统计的同输入对照
│   ├── run_layer2_obscure.py # Layer-2 冷门撤稿 + 限定任务对照
│   └── update_verifier_prompt.py / update_baseline_prompt.py  # 提示词下发
├── data/eval/                # Layer-1 金标准评测集（每个 seed 一个 json，含 prompt）
├── results/                  # 指标、逐条结果、Layer-2 案例、技术报告（入库）
└── output/eval/ + output/runs/  # 评测结果与原始 SSE（本地，gitignore；可按脚本复现）
```

## 5. 复现步骤

```bash
# 1) 安装依赖（Python 3.11+）
pip install httpx          # 跑批 / 评测必需
pip install matplotlib     # 仅 plot_guardrail*.py 与 build_ppt.py 需要
# 官方 SDK（可选，脚本默认走原生 HTTP）
pip install https://sciencepal.ai/downloads/sdk/sciencepal_sdk-0.2.2-py3-none-any.whl

# 2) 配置 .env
#    SCIENCEPAL_API_KEY=sp_live_xxx
#    BASE_URL=https://sciencepal.ai/api
#    VERIFIER_AGENT_ID=<专家核查 Agent ID>
#    GENERAL_AGENT_ID=<离线基线 Agent ID>
#    NAIVE_AGENT_ID=<普通联网 Agent ID>

# 3) 生成评测集（已包含在 data/eval；如需重建）
python3 scripts/build_benchmark.py --n 12 --seed 7

# 4) 批量跑三方对照
python3 scripts/run_batch.py --seeds 7 123 2024 2025 --n 12   # 离线基线 + 专家工作流
python3 scripts/run_naive.py --seeds 7 123 2024 2025 --n 12 --fresh  # 普通联网 Agent

# 5) 导出三组指标、过程可靠性
python3 scripts/export_results.py
python3 scripts/process_reliability.py

# 6) Layer-2 隐式错误同输入对照
python3 scripts/run_layer2_compare.py
python3 scripts/run_layer2_obscure.py

# 7) 代码级 guardrail 对照（注入用例 × 干预前/后）
python3 scripts/build_adversarial.py
python3 scripts/run_guardrail_eval.py --mode unguarded --case adversarial
python3 scripts/run_guardrail_eval.py --mode guarded   --case adversarial
python3 scripts/guardrail_fault_injection.py
python3 scripts/analyze_guardrail.py        # → results/guardrail/SUMMARY.md
python3 scripts/test_guardrail_offline.py   # 状态机离线断言（17 项，无需配额）

# 8) 自用：核查自己的参考文献列表 / 离线回放任意已保存 run
python3 scripts/verify_refs.py --input refs.txt --out report.json
python3 scripts/verify_refs.py --replay output/runs/<run_id>.jsonl   # 不联网、不耗配额
python3 scripts/report_schema.py --emit-schema results/guardrail/report.schema.json
python3 scripts/plot_guardrail.py           # → results/figures/guardrail_compare.png
python3 scripts/plot_guardrail_timeline.py  # → results/figures/guardrail_timeline.png
python3 scripts/audit_contract.py           # 回溯审计 → results/guardrail/CONTRACT_AUDIT.md
```

### 三个 Agent 的配置要点（也可在 SciencePal 网页端创建）

- **专家核查工作流**：`runtime_agent_type=general`，工具默认开启（需要 `execute_command` 联网）；系统提示词见 `scripts/update_verifier_prompt.py`，撤稿检查 C4 见 `scripts/add_verifier_c4.py`。
- **离线基线 Agent**：同样 `general`，但通过 `PUT /agents/{id}` 设置
  `agentpress_tools={"execute_command":{"enabled":false},"web_search":{"enabled":false}}`，
  并在发起时传 `web_search_on=false`；提示词见 `scripts/update_baseline_prompt.py`。
- **普通联网 Agent**：`general`，工具保持全开（不 PUT 任何工具配置），提示词只要求用 curl 取证、不反问、不写记忆、不等待人工接管，**不给 C1-C4/M1-M5 流程**；见 `scripts/create_naive_agent.py`。

## 6. 数据与伦理

- 评测数据全部来自公开的 Crossref 元数据；金标准 DOI 状态在构造时实时核验。
- 评测只使用论文题录（不含付费全文），不存储任何个人信息。
- 方法学案例使用明确标注为虚构的教学稿件，避免对真实作者的无据指控。
- 方法定位为"辅助审稿/作者自检"，最终判定保留人工复核环节（suspect 即提示人工介入）。

## 7. 局限与后续

- **单模型阴性结论**：专家流程在显性错误上的 F1 增益为零，仅在 deepseek-v4-flash 与更强的 v4-pro 上验证；平台未提供更弱模型，"固化流程能否补偿弱模型"尚未检验，这是首要的后续实验。
- n=48 全对时 F1 点估计 1.0，Wilson 95% 置信下界约 0.926，不能等同于零错误率；Layer-2 撤稿与统计为小样本案例，尚未形成大规模量化基准。
- 撤稿识别依赖 Crossref 标题标记与 `relation` 关系，冷门撤稿在 Crossref 标题中往往无标记，需接入 Retraction Watch 等专门库才能系统评测。
- C3 论断-证据错配、统计方法选择错误等需读全文的更隐蔽错误仅做定性演示，未构造金标准。
- 数据源目前以 Crossref 为主，之后可接入 PubMed、Semantic Scholar、OpenAlex 与中文文献库做多源交叉验证。
