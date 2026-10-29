# CLAUDE.md — Risk-Controlled Metadata Augmentation for RAG Retrieval

> 本项目唯一持久化研究记忆文件。所有长期研究上下文统一存储于此，不再分散到其他文件。
> 新会话直接以本文件为上下文基础，不得无故重新讨论已确认或已否决的内容。

---

## 0. Agent 工作规则（长期执行，最高优先级）

### 0.1 唯一记忆来源
- 本项目所有长期研究上下文统一存储于根目录 `CLAUDE.md`。
- 不建立 `.claude/memory/`、其他 Markdown 记忆文件、JSON 记忆库或额外研究记录文件。
- 其他项目文档可正常读取，但不作为唯一研究记忆来源。
- **开源边界**：`CLAUDE.md` 是私有研究策略（含 novelty、Related Work 分析、决策链 D1–D11、否证过程），开源时移除或保留在私侧；`README.md` 是公开安全的项目说明（只讲代码与复现）。

### 0.2 研究状态标记（必须区分，不得混淆）
| 标记 | 含义 |
|------|------|
| `VERIFIED` | 已通过可信来源或实验验证 |
| `DECIDED` | 用户已确定的研究决策 |
| `HYPOTHESIS` | 尚待验证的研究假说 |
| `CANDIDATE` | 未选定的候选设计 |
| `OPEN` | 尚未回答的问题 |
| `COMPLETED` | 已完成的任务 |

**红线**：
- 不能把计划中的实验标记为 `COMPLETED`。
- 不能把 Agent 提出的假说写成 `VERIFIED`。
- 不能把未验证的机制描述成已有实验结论。

### 0.3 决策更新规则
当用户明确修改方向、确认方案、否决候选、完成实验、确认文献证据或得出新结论时，及时维护本文件对应部分。重要决策变化保留简短变更记录（日期 / 旧决策 / 新决策 / 理由）。若新决定与旧信息矛盾，同步更新正文，避免文件内部冲突。

### 0.4 不得自动确认研究创新
- Agent 新提出的 Idea 默认属于 `CANDIDATE`，不得自动写入「已确定创新」。
- 仅当用户明确采纳时，才可更新为 `DECIDED`；即便被采纳，也不代表创新性和有效性已验证。

### 0.5 控制文件长度
- 长期保留：研究目标、核心决策、研究路线、实验协议、已验证结论、关键失败案例、重要待办。
- 压缩/整合：重复讨论、已失效的临时猜测、无实质价值的推理过程、重复文献描述。
- 可整合过时内容，但不得删除仍然有效的核心决策及其关键理由。

### 0.6 新会话行为
- 新问题先判断属于哪个阶段、是否与既有决策冲突、是否有足够证据支持。
- 不得为维持原始 Idea 而强行宣称已有方法无效。

### 0.7 研究质量要求
**不得**：编造文献与实验结果；夸大论文结论；选择性引用以支持预设 Idea；混淆真实错误率与合成错误注入率；用复杂算法包装简单机制；将已否决方案反复提出为新方向。

**鼓励**：主动质疑研究假说；寻找能否证研究问题的证据；公平比较已有方法；区分机制分析与性能提升；证据不足时直接指出不足。

### 0.8 开发环境与依赖管理
- 所有 Python 代码在根目录 `.venv` 虚拟环境内运行；执行前先激活（bash）：`source .venv/Scripts/activate`。
- 依赖统一记录在根目录 `requirements.txt`；新增或升级任何库后，同步更新该文件（`pip freeze > requirements.txt` 或手动追加包名），不装到系统全局。
- 本机默认 PyPI 存在 SSL 干扰（`decryption failed or bad record mac`），安装依赖用清华镜像：`.venv/Scripts/python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`。

---

## 1. 研究目标与范围

### 1.1 研究名称（`OPEN` — 未冻结）
暂定：**Risk-Controlled Metadata Augmentation for RAG Retrieval**

### 1.2 核心研究问题（`DECIDED`）
如何在保留文档 Metadata 对 RAG 检索的有效贡献的同时，控制错误 Metadata 所引入的额外检索性能损失？

核心表述：**Preserving Metadata Benefits While Mitigating Metadata-Induced Retrieval Harm.**

两个目标：
- **主要目标**：降低错误 Metadata 造成的检索性能损失。
- **次要目标**：尽可能保留正确 Metadata 对检索的有效增益。

**研究对象（`DECIDED` — 2026-10-19，从「错误」扩为三类元数据缺陷）**：
- **错误（Error）**：值错误 / 错误归因（填错）。例：作者名错、期刊错、NCT 错链。
- **缺失（Missing）**：字段缺失（没填）。例：NCT 未回链、日期未编码。
- **表示不一致（Representation Inconsistency）**：同一实体异写。例：转写、姓名序、期刊改名、子系列、online/print 年份。
- 主次目标不变；「错误 Metadata」现指上述三类缺陷，Step 2 分别观察三类影响。

**三类缺陷的定性看法（2026-10-21 商榷）**：
- 方法论共识（`DECIDED`）：三类缺陷的检索影响**不预先假定**，由 Step 2 统一实证；凡实测无影响者，论文中如实标注「并无影响」，不选择性夸大（诚实报告 null 结果）。
- **错误（Error）**：值客观上错，损害**内在于元数据**（任何系统都救不回）；但在 curated 库中低频（0.1–3.3%，实测）。损害的量级待 Step 2 量化。
- **缺失（Missing）**：无值 ≈ 无元数据 ≈ text-only 基线。`HYPOTHESIS`：可能**无额外损失**（只失去增益、不引入损害），待 Step 2 验证；「缺失率是否仍记录」待定。
- **表示不一致（Representation Inconsistency）**：同一实体两种写法，**两种都正确**；损害**不内在于元数据**，依赖系统匹配方式（exact-match 受害、归一化则无）。`HYPOTHESIS`：是否有影响待定，Step 2 实证。
- 关键张力（`OPEN`）：能造成内在损害的只有「错误值」却低频；高频的「缺失/表示不一致」严格说都非「错误」。研究命题的成立，依赖 Step 2 实证「真实缺陷是否、以何种频率造成检索损害」。

**关键边界**：
- 不是简单判断 Metadata 是否正确再决定是否使用。
- 不是因为 Metadata 可能有害就退回纯文本检索。

### 1.3 研究范围（`DECIDED`）
限定在 RAG 的 **Retrieval Stage**，包括：
- Candidate Retrieval
- Metadata Filtering
- Metadata Enrichment
- Metadata Score Fusion
- Metadata-aware Reranking

**不研究**：Agent、LLM Generation、大规模 LLM 训练、Retrieval Cache、单纯检索效率优化。

**当前优先**：Metadata 缺陷（错误 / 缺失 / 表示不一致）导致的检索损失。正确 Metadata 因不当融合导致的损失属更广泛背景，非当前优先。

### 1.4 研究资源与目标（`DECIDED`）
- 面向有实际学术价值、可实验验证的论文工作。
- 潜在发表目标：B 类会议或中科院二区左右 SCI，但不降低研究证据标准。
- `DECIDED`：低算力不再是绝对硬约束；仍关注合理的实验成本、实现复杂度和研究周期，但不以牺牲问题真实性与研究价值为代价。

---

## 2. 三阶段研究路线（`DECIDED` — 当前最重要路线）

**逻辑主线**：真实问题存在 → 错误导致检索损害 → 现有方法无法充分解决 → 基于剩余缺陷提出新方法。
**红线**：不得跳过证据验证而直接设计算法。

### Step 1 — 证明元数据缺陷（错误 / 缺失 / 表示不一致）客观存在且发生频繁
- **目标**：寻找高可信度证据，证明真实数据中元数据缺陷（错误 / 缺失 / 表示不一致）确实存在，且发生率有实际研究意义。
- **需回答**：
  1. 哪些实际场景容易出现 Metadata 错误？
  2. 哪些字段经常出错？
  3. 是否有可信研究测量过真实错误率？
  4. 错误率的统计依据、样本规模和定义是什么？
- **关注字段（示例，非穷举、非冻结）**：如 Date/Timestamp、Author、Source、Category、Document Attribution 等结构化属性，仅作研究示例，不限定元数据字段范围。
- **关注错误类型**：Incorrect Values、Incorrect Attribution、Stale Metadata、Extraction Errors、Inconsistent Metadata。
- **关注错误来源（引入阶段）**：错误来源机制与「错误类型」是两个正交维度；因元数据字段总类不可穷举，故按「来源 / 引入阶段」组织，而非按具体字段或具体腐蚀算子：

  | 错误类别 | 引入阶段 |
  |----------|----------|
  | 人工录入错误（Manual-entry） | 元数据人工录入 / 数据库迁移与批量加工阶段 |
  | OCR 错误（OCR-induced） | 文档数字化 / 扫描与自动抽取阶段 |
  | LLM 貌似正确错误（LLM plausible-hallucination） | RAG 系统内 LLM 生成 / 自动打标阶段 |

  > `CANDIDATE`：三类作为工作框架，代表性待 Step 1 文献与审计验证；暂不在此规定具体字段与具体算子。
- **注意区分（三类缺陷，`DECIDED`）**：**错误**（值错/归因错）、**缺失**（字段缺失）、**表示不一致**（同实体异写）——三者机制与检索后果不同，须分别统计；另区分过期信息、正常的不一致。
- **证据标准（`DECIDED`）**：
  - 优先：同行评审论文中的真实数据错误统计、公开数据集审计、真实数据质量实证研究、可复现的抽样检查。
  - 不能用人造注入的合成错误率声称真实世界错误频繁发生。
  - 不能编造错误率或夸大已有论文结论。
  - **充分条件（怎样才算够，`DECIDED`）**：不追求「普遍存在」这一不可证的全称命题；Step 1 成立判据 = S1 ∧ S2 ∧ S3：
    - **S1 存在性**：一次金标准有界测量，错误率非平凡（CI 下界 > 0）。
    - **S2 机制**：错误源于生命周期中不可避免的过程 P（OCR / 人工录入 / LLM 生成），而非某语料偶然。
    - **S3 泛化**：多点收敛证据（≥2 独立语料/域，或文献三角互证）。
    - 三者齐，结论为「错误客观存在、非平凡、源于不可避免机制、非语料特异」——可辩护且扛审，比「普遍存在」更强。
- **已确认的重要决策（`DECIDED`）**：Step 1 不需要额外证明错误 Metadata 经常进入 RAG 系统（该项要求被认为不必要，检索影响由 Step 2 直接对照实验回答）。Step 1 只需证明：错误客观存在 + 发生频率具有实际意义。
- **Step 1 实测证据（审计，`VERIFIED` — 2026-10-14）**：
  - 方法：分层随机 n=1000（5 个出版年份层 × 200，OpenAlex `sample`），按 DOI join Crossref 为金标准；归一化 + 匹配后算「候选错误率」（Wilson 95% CI）。join 成功 940。
  - 三层结果（95% CI）：
    - 原始字符串差异：venue 10.0% / author 6.8% / year 0.1%。
    - 归一化后（HTML 解码 + 西里尔转写 + 姓名序不敏感）候选错误率：venue **4.8%** [3.6%, 6.4%] / author **4.7%** [3.5%, 6.2%] / year **0.1%** [0.02%, 0.6%]。
    - 人工裁决后「真错误值」（双标注，κ=1.0 on 12 条边界候选）：venue **0.1%**（1/940）/ author **0.3%**（3/940）/ year 0.1%（1/940）。
  - 关键发现①：默认排序（高被引名篇）低估错误率约 10 倍（冒烟 venue 1% → 随机 10%），必须用随机采样。
  - 关键发现②：候选错误率与真错误值之间的大落差 = **「表示不一致」**（期刊改名、姓名全称/缩写/转写/姓名序、子系列、online/print 年份、HTML 实体编码）——与「错误值」是两类现象：「表示不一致」高频（venue 7.6% / author 4.4% / year 3.2%）且贴 RAG 过滤漏召回；「错误值」低频（~0.1–0.3%）。
  - 关键发现③：作者错误率随年代上升（pre-1990 2.6% → 2020+ 7.2%），指向聚合/消歧机制，但可能被近年国际化作者增多（更多转写/CJK 名）混淆；venue 的 pre-1990 高峰（8.2%）主要来自期刊改名。
  - `DECIDED`：「错误 / 缺失 / 表示不一致」三类缺陷已确立（2026-10-19 从「错误值 vs 表示不一致」二分扩展）。
- **Step 1 实测证据②（临床试验域，`VERIFIED` — 2026-10-19）**：
  - 方法：ClinicalTrials.gov 拉取带 RESULT 引用的试验（n=1000，得 181 个 RESULT 引用），对每个 PMID efetch PubMed XML，检查 DataBankList 的 NCT。
  - 结果（RESULT 引用 n=181，Wilson 95% CI）：错误（错链=指向错误试验）**3.3%** [1.5%, 7.0%]（6/181）；缺失（NCT 未回链）**68.5%** [61.4%, 74.8%]（124/181）；匹配 28.2%。
  - 关键发现：NCT 是「可选/次要字段」，出版商常不填 → 缺失高（68.5%）；错链低频（3.3%）但非平凡。
  - 错链人工裁决（`VERIFIED` — 2026-10-19）：对比 NCT 标题/条件 vs PMID 标题/摘要，6/6 均为**真错链**（指向早先/不同试验的论文或 protocol），0 个多试验发表伪影；坐实错误率 3.3% [1.5%, 7.0%]。裁决明细见 `data/audit_ct/nct_mismatch_verdicts.json`。
  - `OPEN`：样本单疾病（diabetes）非分层。
- **Step 1 三类缺陷汇总（跨域，`VERIFIED`）**：

  | 域/字段 | 错误 | 缺失 | 表示不一致 |
  |---------|------|------|-----------|
  | 科研 venue | 0.1% | — | 7.6% |
  | 科研 author | 0.3% | 0.7% | 4.4% |
  | 科研 year | 0.1% | — | 3.2% |
  | 临床 NCT | 3.3% | 68.5% | — |

  - 跨域规律（`DECIDED`）：「错误」低频（0.1–3.3%），「缺失」与「表示不一致」高频（3.2–68.5%）——三类是不同现象，Step 2 分别观察其检索影响。
- **当前状态**：`VERIFIED`（部分）— 已有两域实测（科研 venue/author/year + 临床 NCT，错链已人工裁决）；S1/S2/S3（≥2 独立域）均已满足，第三域尝试（MARC、音乐域）已否决（见 §5）。

### Step 2 — 证明 Metadata 错误确实造成检索损失
- **目标**：用代表性的 Metadata 引入方式，证明错误 Metadata 是否会改变检索决策并造成可量化损失。不仅关注平均性能，还关注逐查询损失的频率、幅度与严重程度。

#### 三组核心对照（`DECIDED`）
| 组 | 定义 | 作用 |
|----|------|------|
| A. Text-only Retrieval | 完全不用待研究 Metadata | 基本参考基线 |
| B. Clean Metadata Retrieval | 使用正确/已验证 Metadata | 评估潜在正向收益 |
| C. Corrupted Metadata Retrieval | 使用错误 Metadata | 评估错误造成的性能退化 |

**必须同时观察（不得混淆）**：
- **Clean vs. Corrupted**：错误相对于正确 Metadata 导致的性能下降。
- **Text-only vs. Corrupted**：错误 Metadata 是否让检索比不用 Metadata 更差。

> `DECIDED`（2026-10-19）：C 组「Corrupted」进一步拆为三类缺陷分别注入/观察——**错误**（改值）、**缺失**（删字段）、**表示不一致**（异写），各自单独对照 Clean 与 Text-only。

#### 四类候选 Metadata 引入方式（`CANDIDATE` — 代表性待文献论证）
1. **Metadata Filtering**：按时间/来源/类别过滤候选文档；风险：错误 Metadata 提前过滤掉真正相关文档。
2. **Metadata Enrichment / Textualization**：Metadata 转文本与文档内容共同编码/检索；风险：错误信息干扰文本匹配或语义相关性判断。
3. **Metadata Score Fusion**：语义得分与 Metadata 得分融合；风险：错误 Metadata 提高无关文档得分导致排序错误。
4. **Metadata-aware Reranking**：重排阶段引入 Metadata；风险：错误 Metadata 影响最终排序，甚至覆盖正确文本相关性证据。

> 注：这四类为当前选定候选框架，尚需文献证明其代表性，不能直接宣称是使用频率最高的四种方法。

#### 主要实验指标
`nDCG@k`、`Recall@k`、`Harm Rate`、`Mean Harm`、`Severe Harm Rate`、`Mean Gain`

#### 研究重点（`OPEN`）
1. 错误 Metadata 造成多少平均性能损失？
2. 有多少查询的性能下降？
3. 损失严重程度如何分布？
4. 哪类 Metadata 引入方式更脆弱？
5. 是否发生 Candidate Exclusion？
6. 是否出现 Ranking Reversal？
7. 是否存在错误 Metadata 覆盖正确语义证据的机制？

#### 实验原则（`DECIDED`）
- 同一实验尽可能保持检索骨干一致。
- 区分真实 Metadata 错误与合成错误。
- 合成注入不能代替真实错误发生率证据。
- 不人为构造只对某一方法不利的错误分布。
- Reranking 实验应考虑固定候选集合，以隔离排序机制影响。
- `OPEN`：Baseline、数据集、错误注入协议尚未确定，不能虚构已完成实验。

- **当前状态**：研究框架基本确定，具体实验尚未开展。

### Step 3 — 证明现有方法不能充分解决问题
- **目标**：验证现有检索方法及容错策略能否在 Metadata 错误时既降低损失又保留正确 Metadata 的收益。这是证明研究缺口的关键步骤。
- **红线**：不能直接假定现有方法无法解决问题。

#### 现有解决策略（`CANDIDATE` — 待调研/待实验的候选对照，非正式冻结 Baseline）
- Metadata Weight Reduction
- Relaxed Metadata Filtering
- Text-only Fallback
- Larger Candidate Pool + Semantic Reranking
- Metadata Verification / Correction
- Robust Metadata Fusion

#### 重点研究的潜在矛盾（`HYPOTHESIS` — 待验证假说，非已证结论）
降低 Metadata 使用强度可能缓解错误损失，却同时削弱正确 Metadata 增益：
- 降低权重 → 可能减少错误排序，也可能减少有用信号。
- 放松过滤 → 可能恢复被误排除文档，也可能失去有效过滤收益。
- Text-only Fallback → 可能控制损失，却无法利用有价值 Metadata。
- Metadata 校验 → 可能出现误判并引入额外成本。

#### 最关键问题（`OPEN`）
现有方法是否存在无法同时充分控制错误损害和保留正确 Metadata 收益的局限？必须通过公平对照回答。若现有简单方法已能充分解决问题，应承认创新空间不足，重新评估研究方向。

- **当前状态**：`OPEN` — 尚未完成系统性方法比较及 Failure Mode 验证。

---

## 3. 算法设计（Step 4，`OPEN` — 尚未确定）

- 只有前三步提供足够证据后才决定具体算法。
- 原则：**先发现现有方法真正无法解决的 Failure Mode，再寻找最合适的算法，不要反过来。**

#### 已探索的候选方向（全部为 `CANDIDATE`，非确认创新）
1. Unknown Metadata Corruption Detection
2. Cross-Metadata Consistency
3. Metadata Reliability Estimation
4. Retrieval Risk Estimation
5. Robust Metadata Fusion
6. Risk-Aware Reranking

#### 需警惕的陷阱
- 「检测 Metadata 是否正确，正确就用、错误就不用」可能只是已有可靠性检测与门控融合的简单组合，若无独立且有意义的创新，不应作为最终方法。
- 不能直接将 Risk Estimation、Ranking Constraint 等复杂形式当创新，除非对应问题及机制已获实验支持。

---

## 4. 已确定决策（DECIDED — 长期保留，防止重复讨论）

| # | 决策 |
|---|------|
| D1 | 研究重心从广义 Metadata-Induced Harm 收敛到 **Metadata Error-Induced Retrieval Harm**，优先解决 Metadata 自身错误。 |
| D2 | 需同时研究错误情况下的损失控制与正确情况下的增益保留；二者非两个同等独立方向，**损失控制是主要目标**。 |
| D3 | 采用三阶段证据链：客观错误发生率 → 检索损害验证 → 现有方法局限验证。 |
| D4 | Step 1 不额外承担「证明错误频繁进入 RAG 系统」任务；其检索影响由 Step 2 评估。 |
| D5 | 不能为算法创新反向构造无实际意义的 Failure Mode。 |
| D6 | 不应只关注平均性能，需分析逐查询损害分布。 |
| D7 | 不应把 Metadata Correctness Detection 自动等同于研究创新。 |
| D8 | 具体 Baseline、最终算法及完整实验协议尚未确定。 |
| D9 | 不再将低算力作为绝对限制，但仍考虑实验可行性。 |
| D10 | 任何文献发现须区分：作者明确报告的实验结论 / 文献提及但未验证的问题 / Agent 基于文献的推论。不能把后两者冒充为已有实验证据。 |
| D11 | 研究对象从「错误 Metadata」扩为「元数据缺陷三类：错误 / 缺失 / 表示不一致」；Step 2 分别观察三类影响（2026-10-19 定，B 路线，取代 D1 的窄口径）。 |

---

## 5. 候选方法与否决理由

- **候选方法**：见 Step 2 四类引入方式、Step 3 六类解决策略、Step 4 六个算法方向（均为 `CANDIDATE`）。
- **已否决/降级**：
  - 将「判断 Metadata 正确性 → 决定是否使用」直接作为创新方法：否决为最终方法（可能是已有可靠性检测 + 门控融合的简单组合）。
  - 以「Metadata 可能有害 → 退回纯文本检索」作为方案：否定（违背核心研究问题设定）。
  - 以低算力作为绝对硬约束：已否决（见 D9）。
  - **图书馆目录 MARC 作为 S3 第三域**：否决（2026-10-21）——权威编目（LoC/国家图书馆）专业编制、错误率天然过低，测不出有意义的缺陷率。
  - **音乐域（Discogs vs MusicBrainz）作为 S3 第三域**：否决/不可用（2026-10-21）——genre/category 无客观真值（流派主观判定）；year/artist 缺乏既独立于两源、又可批量程序化获取的金标准（Wikidata 同为社区源，且其音乐数据大量从 MB/Discogs 循环导入，非独立证据）。

---

## 6. Related Work：撞车文献检索（2026-10-11）

> 检索目的：评估与「保留 Metadata 收益 + 控制错误 Metadata 检索损害」这一核心命题的撞车程度。检索方式 WebSearch/WebFetch。
> 标注遵循 D10：`VERIFIED` = 本会话已二次核实为真实文献；`待核实` = Agent 检索报告但未逐一复核，纳入 Related Work 前须再核。

### 6.1 撞车风险最高的论文（均 `VERIFIED`）

| 论文 | 出处 | 撞车点 | 与本研究的关键差异 |
|------|------|--------|-------------------|
| **SURE** — Quantifying and Improving the Robustness of RAG Against Spurious Features in Grounding Data (Yang et al.) | ACL 2026, arXiv:2503.05587 | 明确把 Metadata（时间戳、来源）当作伤害 RAG 的 spurious feature，注入错误并量化鲁棒性 | 因变量是**生成端**答案翻转（RR/WR/LR），非检索端 nDCG/Recall/候选排除；合成扰动，非真实错误率 |
| **RA-RAG** — RAG with Estimation of Source Reliability (Hwang et al.) | EMNLP 2025, arXiv:2410.22954 | 无监督 source 可靠性估计 + 加权投票，=「Metadata Reliability Estimation + Robust Fusion」的已有实现 | **source 级**（非字段级 date/author/category）；目标生成端抗冲突 |
| **Metadata Utility Boundary**（QGFace-LLaVA + CMRR） | MDPI 2313-7673/11/8/582 | 用「Clean Gain vs Metadata Dependence Index」的收益-鲁棒权衡框架，与本研究双目标几乎同构 | 领域是**人脸识别**，非文档检索 |
| **Faithful or Findable?** (Terrenzi & Ayvaz) | SynthIR@SIGIR 2026, arXiv:2607.05970 | 证明错误/虚构元数据可「不忠实却更可检索」 | RDF **数据集检索**，非文档级 RAG；测忠实度非错误损害 |

### 6.2 待核实的次级相关文献（`待核实`）

- Stale-Document Poisoning (arXiv:2609.31342)：仅时间过期维度。
- Metadata, Structure, or Strategy (arXiv:2606.29645)：元数据「正确但不可用」的损害，非错误元数据。
- CONFACT / Media Source Backgrounds (arXiv:2505.17762)：媒体可信度加权排序。
- Reliability-Gated Multimodal Fusion (IEEE doc 11626865)：corrupted metadata 下可靠性门控，但多模态分类。
- C-RAG (arXiv:2402.03181)、Conformal Ranked Retrieval (arXiv:2404.17769)：检索风险控制，但无元数据可靠性概念。
- MetaEnhance (JCDL 2023)：元数据纠错 + 回滚。

### 6.3 检索结论（`HYPOTHESIS` — 检索判断，非已证创新）

1. **无论文精确占据本研究位置**：检索阶段 text-only/clean/corrupted 三组对照 + 逐查询 Harm Rate 的「错误元数据检索损害」量化，目前未见声称。
2. **朴素路线已拥挤**：「检测正确性→门控使用」及「可靠性估计 + 门控融合」的所有积木均已被占（RA-RAG、CONFACT、可靠性门控多模态融合等），印证 D7——此路线不可作为创新。
3. **潜在未占空档**：显式建模「检测器/门控本身误判 → 正确元数据被抑制 → 损失正确收益」的 failure mode，目前无人声称；但需证明其非「校准 + 门控」的平凡组合。
4. 正面对手为 **SURE**（生成端）与 **Metadata Utility Boundary**（vision 端），写作时须明确区分。

---

## 7. 当前进度与下一步

### 7.1 当前进度（截至 2026-10-19）

**已确定（`DECIDED`）**：
- 核心研究问题、研究范围
- 元数据缺陷三类（错误 / 缺失 / 表示不一致）为主要研究对象
- 三阶段证据路线
- Text-only / Clean / Corrupted 三组实验框架（Corrupted 拆三类分别观察）
- 四类候选 Metadata 引入方式
- 逐查询损失评估的重要性

**已完成（`VERIFIED`）**：
- Step 1 科研域审计（n=1000，金标准 Crossref）：错误 venue 0.1% / author 0.3% / year 0.1%；表示不一致 venue 7.6% / author 4.4% / year 3.2%
- Step 1 临床域审计（n=181 RESULT 引用）：NCT 错误（错链）3.3% / 缺失 68.5%（错链已人工裁决：6/6 真错链，0 伪影）

**待完成（`OPEN`）**：
- 元数据引入方式代表性论证
- 数据集与检索 Baseline 选择
- 错误注入协议（三类缺陷分别注入）
- Step 2 实验
- Step 3 现有方法对照
- Failure Mode 确认
- Step 4 算法设计

### 7.2 下一步（`OPEN`）
Step 1 已满足（S1 存在性 + S2 机制 + S3 泛化≥2 域均完成；第三域 MARC/音乐域已否决，见 §5）。下一步进 **Step 2**：三类缺陷（错误/缺失/表示不一致）分别注入，观察各自检索影响。

> 已完成（2026-10-19）：NCT 错链人工裁决——6/6 均为真错链，0 多试验发表伪影。

---

## 8. 研究变更日志（精简）

- 2026-10-10：确立三阶段研究路线（D3），明确 Step 1 不承担「证明错误频繁进入 RAG 系统」任务（D4）。
- 2026-10-10：研究重心收敛到 Metadata Error-Induced Retrieval Harm（D1）。
- 2026-10-10：取消低算力绝对硬约束，降级为「仍关注实验可行性」（D9）。
- 2026-10-11：完成撞车文献检索（新增 §6 Related Work）。核心结论：无精确撞车，但 SURE(ACL2026)/RA-RAG(EMNLP2025)/Metadata Utility Boundary(vision) 须重点区分；朴素「检测→门控」路线已被占，印证 D7。
- 2026-10-13：Step 1 增加「错误来源（引入阶段）」维度——人工录入 / OCR / LLM 貌似正确三类，明确按来源而非字段组织（字段总类不可穷举），暂不规定具体字段与算子。
- 2026-10-13：Step 1 证据标准补充「充分条件」——不追求不可证的「普遍存在」，以 S1 存在性 + S2 机制 + S3 泛化 为成立判据。
- 2026-10-14：完成 Step 1 首次分层随机审计（n=1000，金标准 Crossref）。候选错误率 venue 10.0% / author 6.8% / year 0.1%（Wilson CI）；发现默认排序低估 10 倍、作者错误随年代上升（指向聚合/消歧机制）。
- 2026-10-15：归一化修复（HTML 解码 + 西里尔转写 + 姓名序不敏感）后候选错误率降至 venue 4.8% / author 4.7%；双标注裁决真错误值 venue 0.1% / author 0.3%（κ=1.0），「错误值 vs 表示不一致」taxonomy 定为 `DECIDED`。
- 2026-10-19：研究对象从「错误 Metadata」扩为「元数据缺陷三类（错误/缺失/表示不一致）」（D11，B 路线）；Step 2 分别观察三类影响；临床域审计 NCT 错误 3.3% / 缺失 68.5%。
- 2026-10-19：NCT 错链人工裁决完成——6/6 均为真错链（0 多试验发表伪影），坐实临床域错误率 3.3% [1.5%, 7.0%]。
- 2026-10-21：S3 第三域探索失败——「图书馆目录 MARC」（权威编目错误率过低）与「音乐域 Discogs vs MusicBrainz」（genre 无客观真值；year/artist 缺独立可批量获取的金标准，Wikidata 系社区源且从 MB/Discogs 循环导入）均否决，音乐域标记「不可用」。S3 以现有两域（科研+临床）满足，不再扩展第三域，直接进 Step 2。
- 2026-10-21：三类缺陷定性商榷——错误值=内在损害但低频；缺失≈无元数据（`HYPOTHESIS` 无额外损失）；表示不一致两值均正确（损害依赖系统匹配、影响待定）。方法论共识：影响不预设，Step 2 统一实证，无影响者论文如实标注「并无影响」。

> 变更日志仅保留关键决策变化（日期 / 决策 / 理由）。其余细节以正文为准。
