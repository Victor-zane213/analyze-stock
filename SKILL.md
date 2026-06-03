---
name: financial-assistant
description: A股/美股股票分析助手。支持A股和美股的单只及批量分析、智能推荐、牛散持仓分析、板块分析、三维入场评估（资金+技术+故事）、每日涨停复盘+概念板块排名、放量+价托选股。A股触发词：分析A股、A股分析、查A股、看盘A股；美股触发词：分析美股、美股分析、查美股、US stock、NASDAQ；批量触发词：批量分析A股、批量分析美股、对比分析、比较分析、多只股票；推荐触发词：推荐个股、超跌推荐、大师持仓、大师被套、大师新持仓；牛散触发词：牛散持仓、牛散分析、分析牛散；板块触发词：分析板块、板块分析、板块排名、哪些板块值得关注、板块轮动、热门板块；入场评估触发词：值不值得买、三维分析、资金技术故事、价托、黄金三角、模式H；涨停复盘触发词：分析涨停、涨停复盘、今日涨停、涨停板、概念板块排名、模式I；选股触发词：选股、筛选、放量选股、价托选股、模式J、放量+价托。
---

# A股/美股 股票分析助手

根据用户输入，自动识别 A 股或美股，进行全面的基本面和技术面分析。

## 十种分析模式

本 skill 支持十种模式，根据用户输入的命令前缀和股票代码格式自动切换。

**股票类型自动识别规则：**
- 纯数字代码（如 600519）→ A 股
- 包含字母的代码（如 AAPL、TSLA）→ 美股
- 如果用户提供了中文名称，同时说了"分析A股"或"分析美股"→ 按命令执行

---

### 模式A：单只A股详细分析

**触发关键词**：`分析A股 {股票名}`、`分析 {A股股票名}`、`{A股名} 怎么样`、`看看 {A股名}` 等

**行为**：按照第1-6步执行完整 A 股流程，输出详细分析报告。

### 模式B：多只A股批量对比

**触发关键词**：`批量分析A股 {股票1}、{股票2}`、`A股对比 {股票1} {股票2}`

**行为**：按照 B1-B7 A 股批量流程执行，输出汇总对比表+推荐排序。

### 模式C：单只美股详细分析

**触发关键词**：`分析美股 {股票}`、`美股分析 {股票}`、`{美股ticker} 怎么样`、`查美股 {股票}`、`US stock {ticker}`、`NASDAQ {ticker}`

**行为**：按照 C1-C6 美股流程执行，输出详细分析报告（基本面、盈利、技术指标、产业链、关联公司、综合判断六大部分）。

### 模式D：多只美股批量对比

**触发关键词**：`批量分析美股 {AAPL, TSLA, NVDA}`、`美股对比 {股票1} {股票2} {股票3}`

**行为**：按照 D1-D7 美股批量流程执行，输出汇总对比表+推荐排序。

### 模式E：智能推荐

**触发关键词**：`推荐个股`、`股票推荐`、`超跌推荐`、`跌多了推荐`、`大师持仓`、`大师新持仓`、`大师被套`、`巴菲特最新持仓`、`{公司名}新供应商`

**行为**：根据子命令执行对应的推荐策略（E1-E4），输出推荐标的列表。

### 模式F：牛散持仓分析

**触发关键词**：`牛散持仓`、`牛散分析`、`分析牛散`、`{牛散名} 持仓`

**行为**：加载 `niushan.yaml` 中的牛散名单，WebSearch 获取最新持仓，按板块分类汇总。

#### E1：超跌+基本面不变筛选

**触发**：`超跌推荐`、`跌多了推荐`、`推荐个股`（默认包含 E1）

**数据源**：纯 Python（yfinance），无需 WebSearch。

**流程**：
1. 用户可指定板块/行业（如"半导体"、"AI"），否则使用预设的 AI/半导体观察列表
2. 批量获取候选股票的 52 周高点、当前价格、EPS、营收增长
3. 筛选条件：距 52 周高点跌幅 >20%，EPS > 0，营收增长 > -5%
4. 按跌幅降序排列，输出 Top 10

**执行命令**：
```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from recommend import find_oversold_fundamentals, print_oversold_table
import json
results = find_oversold_fundamentals(max_drop_pct=20.0, top_n=10)
print_oversold_table(results)
print('\\n--- JSON ---')
print(json.dumps(results, ensure_ascii=False, indent=2))
"
```

如果用户指定了行业/板块，先通过 WebSearch 获取该板块的主要公司 ticker 列表，然后传入 `candidates` 参数：
```bash
python3 -c "
from recommend import find_oversold_fundamentals, print_oversold_table
# candidates 来自 WebSearch 返回的该板块 ticker 列表
results = find_oversold_fundamentals(candidates=[...], max_drop_pct=20.0, top_n=10)
print_oversold_table(results)
"
```

#### E2：行业巨头新被点名供应商

**触发**：`{龙头公司}新供应商`、`新被点名供应商`，如 `NVIDIA新供应商`、`Apple新供应商`

**实现方式**：WebSearch（新闻实时性，无法预计算）。

**流程**：
1. WebSearch `{龙头公司} new supplier partner announcement {当前年份}`（英文搜索）和 `{龙头公司} 新供应商 合作公告 {当前年份}`（中文搜索）
2. 从搜索结果中提取被点名公司的名称和 ticker
3. 用 `verify_supplier_fundamentals()` 验证被点名公司的基本面
4. 格式化输出，标注合作内容和公告时间

**验证命令**（在 WebSearch 提取 ticker 后执行）：
```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from recommend import verify_supplier_fundamentals, print_supplier_table
import json
# tickers 来自 WebSearch 结果
results = verify_supplier_fundamentals(['ANET', 'SMCI', 'DELL'])
print_supplier_table(results, leader='NVIDIA')
print('\\n--- JSON ---')
print(json.dumps(results, ensure_ascii=False, indent=2))
"
```

#### E3：大师最新持仓/新建仓

**触发**：`大师新持仓`、`巴菲特最新持仓`、`Burry最新持仓`、`<大师名> 持仓`

**实现方式**：WebSearch（stockcircle.com、fiscal.ai 无公开 API，但搜索结果可获取数据）。

**流程**：
1. WebSearch `{大师名} {fund name} 13F portfolio new positions Q{quarter} {年份}`
2. 补充搜索 `site:fiscal.ai {大师名} portfolio` 获取结构化数据
3. 从搜索结果中提取：新建仓 ticker、建仓规模、建仓时间
4. 对于上次未出现的持仓，可能是新持仓
5. 格式化输出，标注大师名称、建仓规模和建仓时间

**搜索关键词示例**：
- `Warren Buffett Berkshire Hathaway 13F new positions {当前年份}`
- `Bill Ackman Pershing Square portfolio changes {当前年份}`
- `Michael Burry Scion 13F latest holdings {当前年份}`
- `site:fiscal.ai Warren Buffett portfolio {当前年份}`

#### E4：大师持仓被套检测

**触发**：`大师被套`、`巴菲特被套`、`大师持仓被套`（或 E3 执行后自动触发 E4）

**数据源**：E3 获取的持仓 ticker 列表 + yfinance 价格检查。

**流程**：
1. 从 E3 WebSearch 结果中提取大师完整持仓的 ticker 列表
2. 用 yfinance 获取每只股票当前价格和 52 周/3 月高点
3. 筛选条件：距近期高点跌幅 >15%
4. 按跌幅降序排列输出

**执行命令**：
```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from recommend import find_guru_dip_holdings, print_guru_dip_table
import json
# tickers 来自 E3 WebSearch 结果
results = find_guru_dip_holdings(['AAPL','BAC','AXP','KO','OXY','CVX'], min_drop_pct=15.0)
print_guru_dip_table(results, guru_name='巴菲特', min_drop_pct=15.0)
print('\\n--- JSON ---')
print(json.dumps(results, ensure_ascii=False, indent=2))
"
```

#### 综合推荐（E1+E3+E4 全量执行）

**触发**：`推荐个股`、`股票推荐`、`智能推荐`

**行为**：按顺序执行 E1 → E3 → E4，输出完整推荐报告。

**大师名单（可扩展）：**

| 大师 | 基金 | 搜索关键词 |
|------|------|-----------|
| Warren Buffett | Berkshire Hathaway | Buffett Berkshire 13F |
| Michael Burry | Scion Asset Management | Burry Scion 13F |
| Bill Ackman | Pershing Square | Ackman Pershing 13F |
| Stanley Druckenmiller | Duquesne Family Office | Druckenmiller Duquesne 13F |
| David Tepper | Appaloosa Management | Tepper Appaloosa 13F |
| Ray Dalio | Bridgewater Associates | Bridgewater Bridgewater 13F |
| Seth Klarman | Baupost Group | Klarman Baupost 13F |

### 推荐输出格式

```
## 🔍 智能推荐报告

### 📉 超跌但基本面未变（距52周高点跌幅>20%）

| # | 股票 | Ticker | 现价 | 52周高 | 跌幅 | EPS | PE | 营收YoY | 市值 | Beta |
|---|------|--------|------|--------|------|-----|-----|---------|------|------|
| 1 | QUALCOMM | QCOM | $150.00 | $205.95 | -27.2% | $4.97 | 30.2 | +5.0% | $160B | 1.28 |

> 共 N 只符合条件，显示 Top 10

### 🏆 {大师}最新建仓

| # | 股票 | Ticker | 建仓规模 | 建仓时间 | 当前价格 | 表现 |
|---|------|--------|---------|---------|---------|------|
| 1 | UnitedHealth | UNH | ~$1.2B | Q4 2025 | $550 | +5% |

### 📌 {大师}持仓被套（跌幅>15%）

| # | 股票 | Ticker | 现价 | 52周高 | 从高点跌 | 3月跌 | EPS | PE | 行业 |
|---|------|--------|------|--------|----------|-------|-----|-----|------|
| 1 | OXY | OXY | $58.61 | $67.45 | -13.1% | -13.1% | $1.35 | 43.4 | Energy |

> 共 N 只被套，显示 Top 10

### 🆕 {龙头}新被点名的供应商

| # | 股票 | Ticker | 合作内容 | 公告时间 | 当前价格 | 市值 | 高位跌幅 |
|---|------|--------|---------|---------|---------|------|----------|
| 1 | Arista Networks | ANET | AI网络交换机 | 2026-Q2 | $XXX | $XXB | -X.X% |

---
*数据时间：{日期}*
*免责声明：分析结果仅供参考，不构成投资建议。*
```

#### 推荐模式注意事项

1. **E3 和 E4 的依赖关系**：E4 依赖 E3 获取的持仓 ticker 列表，必须先执行 E3 再执行 E4。
2. **E1 独立执行**：E1（超跌筛选）无需 WebSearch，可随时独立执行。
3. **E2 实时性**：E2（新供应商）依赖 WebSearch 获取最新新闻，适合独立触发。
4. **13F 滞后性**：大师持仓数据基于 SEC 13F 文件，有约 45 天的滞后期。
5. **批量大师查询**：可以同时查询多位大师的持仓（`推荐个股` 默认查询 2-3 位），并行执行 WebSearch。

### 模式F：牛散持仓分析

**触发关键词**：`牛散持仓`、`牛散分析`、`分析牛散`、`牛散持仓 {板块}`、`{牛散名} 持仓`

**行为**：加载 `niushan.yaml` 中的牛散名单，通过 WebSearch 找到每位的 A 股最新持仓，按板块分类汇总，分析共同看好的方向。

**数据源**：全 WebSearch（A 股牛散无标准化披露机制，数据来自季报「十大流通股东」、东方财富、财经媒体）。

#### F1步：加载牛散名单

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from niushan import load_niushan_config, print_niushan_list
niushan_list = load_niushan_config()
print_niushan_list(niushan_list)
"
```

#### F2步：并行搜索每个牛散的持仓（WebSearch）

为每位牛散并行执行 WebSearch，搜索关键词由脚本自动生成。可同时发出所有搜索请求：

- `{牛散名} 最新持仓 十大流通股东 {当前年份}`
- `{牛散名} 重仓股 {当前年份}一季报`

**建议**：10 位牛散 × 2 条搜索 = 20 个 WebSearch 请求，分两批并行执行（每批 10 个）。

从搜索结果中为每位牛散提取：
- 持股名称和代码（6位数字）
- 所属行业/板块
- 持仓变动方向（新进/加仓/减仓/持有）

#### F3步：板块分类汇总

将 F2 收集到的所有持股按板块归类。使用 `niushan.py` 中的 `classify_sector()` 辅助识别板块。十大板块：

半导体/芯片、AI/人工智能、医药/生物、新能源/光伏/锂电、消费/白酒、军工/国防、金融/地产、通信/5G、汽车/自动驾驶、软件/信创

统计每个板块：有多少牛散看好、具体是哪些牛散、代表性的持股

#### F4步：输出分析报告

用 `print_sector_heatmap`、`print_niushan_consensus`、`print_niushan_details` 格式化输出。汇总所有数据后调用：

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from niushan import print_sector_heatmap, print_niushan_consensus, print_niushan_details

sector_stats = {...}  # F3 汇总结果
stocks_by_niushan = {...}  # F2 提取的每位牛散持股
niushan_list = [...]  # F1 加载的名单

print_sector_heatmap(sector_stats, len(niushan_list))
print_niushan_consensus(sector_stats)
print_niushan_details(stocks_by_niushan)
"
```

### 牛散输出格式

```
## A股牛散持仓分析报告（N位牛散）

### 板块热度汇总

| 板块 | 看好牛散数 | 占比 | 代表牛散 | 代表个股 |
|------|-----------|------|---------|---------|
| 半导体/芯片 | 5 | 50% | 葛卫东、赵建平、李欣... | 寒武纪（688256）、... |
| 医药/生物 | 4 | 40% | 陈发树、何雪萍、章建平 | 药明康德（603259）、... |
| ... | ... | ... | ... | ... |

### 牛散共识分析

**最热门板块：** 半导体/芯片（5 位牛散重仓）
**次热门板块：** 医药/生物（4 位牛散配置）
**独立看好：** 军工（王孝安）

### 各牛散最新持仓明细

#### 1. 葛卫东
  **半导体/芯片：** XXXX（000XXX）[新进]、XXXX（688XXX）[加仓]
  **AI/人工智能：** XXXX（300XXX）[持有]

#### 2. 章建平
  ...

---
> 数据来源：上市公司季报「十大流通股东」、东方财富
> 免责声明：牛散持仓数据基于公开季报披露，有滞后性，仅供参考。
```

#### 牛散模式注意事项

1. **数据滞后性**：季报披露有约 1-2 个月的滞后期（如 Q1 季报在 4 月底前披露完毕）。
2. **覆盖面有限**：只有进入「十大流通股东」的持仓才会被公开，中小仓位可能遗漏。
3. **牛散名单可扩展**：在 `niushan.yaml` 中自由增删，脚本自动生效。
4. **单独查询**：`{牛散名} 持仓` 可以只查一位牛散，跳过板块汇总步骤。
5. **板块筛选**：`牛散持仓 半导体` 可以只看某板块的牛散持仓情况。

---

### 模式G：A股板块分析

**触发关键词**：`分析板块`、`板块分析`、`板块排名`、`哪些板块值得关注`、`板块轮动`、`热门板块`、`板块强弱`

**行为**：加载 `sectors.yaml` 中的板块定义（12个板块，每个5只成分股），通过腾讯行情接口批量获取成分股K线数据，计算板块整体表现并按动量评分排名。同时结合 WebSearch 获取定性因子（政策催化、供需变化、机构动向）。

**数据源**：腾讯行情接口（K线数据）+ WebSearch（定性因子）。

#### G1步：运行定量板块排名

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from sector import analyze_all_sectors, print_sector_report
results = analyze_all_sectors()
print_sector_report(results)
"
```

从输出中提取：
- 各板块 5日/10日/20日 平均涨跌幅
- 动量评分（加权：5日×0.5 + 10日×0.3 + 20日×0.2）
- 成交量放大比例（资金是否流入）
- 板块内成分股上涨比例（普涨/分化）

#### G2步：WebSearch 获取定性因子（并行搜索 Top 5 板块）

为 G1 排名前 5 的板块并行搜索：

1. `{板块名} 2026年4月 政策 催化 利好`
2. `{板块名} 供需缺口 涨价 产能 2026`
3. `{板块名} 资金流向 主力净流入 北向资金 2026`

从搜索结果中提取：政策催化、供需格局变化、机构观点。

#### G3步：综合判断输出

将 G1 定量排名和 G2 定性因子结合，输出：
1. **板块排名表**（12个板块全量）
2. **Top 5 板块成分股明细**（每只成分股的5日涨跌）
3. **Top 3 定性分析**（催化因素、风险提示）
4. **操作建议**（哪些值得关注、哪些回避）

#### 板块输出格式

```
## A股板块分析报告

### 板块综合排名

| # | 板块 | 5日涨跌 | 10日涨跌 | 20日涨跌 | 动量分 | 放量比 | 涨家比 | 业绩风险 |
|---|------|---------|----------|----------|--------|--------|--------|----------|
| 1 | 锂矿/能源金属 | +8.5% | +15.2% | +28.3% | +15.3 | 1.45x | 100% | 中 |

> 汇总：强趋势 N 个 | 正常 N 个 | 弱势 N 个

### Top 5 板块成分股明细

#### 1. 锂矿/能源金属 — 动量评分 +15.3
> 5日涨跌 +8.5% | 20日涨跌 +28.3% | 量能 1.45x（80%放量）

| 股票 | 代码 | 5日涨跌 |
|------|------|--------|
| 天齐锂业 | 002466 | +12.1% |
| 赣锋锂业 | 002460 | +9.8% |
...

### 综合判断与建议

**最强动量板块：**
1. 锂矿/能源金属 — 5日 +8.5%（100%普涨）🔥 放量上攻
2. 半导体/芯片 — 5日 +3.2%（60%上涨）⚡ 缩量上涨
...

**资金流入板块：** ...

**回避板块：** ...

**4月业绩期提醒：** 优先选择已披露一季报的板块内个股。

---
*数据时间：当前交易日*
*免责声明：板块分析结果仅供参考，不构成投资建议。*
```

#### 板块分析注意事项

1. **成分股代表性**：每个板块只取 5 只代表性龙头，可能存在偏差。用户可以在 `sectors.yaml` 中增删。
2. **业绩风险**：4/8/10 月为季报密集披露期，优先选已出业绩的标的。
3. **定量+定性结合**：G1 只看价格和量能，G2 补充政策和供需逻辑，两者缺一不可。
4. **动量不持续**：短期动量评分高的板块可能随时反转，需结合 WebSearch 判断催化因素是否可持续。
5. **板块可扩展**：在 `sectors.yaml` 中自由增删板块和成分股，脚本自动生效。

---

### 模式H：三维入场评估（资金 + 技术 + 故事）

**触发关键词**：`值不值得买`、`值不值得入手`、`三维分析`、`资金技术故事`、`入场评估`、`模式H`、`价托`、`黄金三角`、`{股票} 能买吗`

**适用范围**：仅 **A 股**（6 位数字代码或股票名称）。美股请用模式 C。

**核心理念**：用三个维度判断「值不值得入手」，默认权重 **资金 35% + 技术 35% + 故事 30%**（用户说偏短线可提高资金权重至 40%）。

| 维度 | 数据来源 | 评分要点 |
|------|----------|----------|
| **资金** | akshare 个股主力净流入、股东户数（筹码）、量价 | 近5/10日主力净流入天数与金额、涨放量 |
| **技术** | 腾讯 K 线 + 原7项综合判断 + **价托/黄金三角** | 7项技术 0–55 分 + 价托时间加分 0/4/6 分 |
| **故事** | LLM 产业链分析 + 故事五维打分 | 逻辑清晰度、催化、供需、业绩验证、风险、**增量逻辑**（谁在花钱买什么、技术迭代趋势、订单是否已验证。区分真实增量 vs 远期故事）、**业务纯正度**（营收中直接来自最热增量市场的比例，同行对比。例如 MLCC：AI 服务器端 > 汽车端 > 消费电子端） |

#### 价托 / 黄金三角（技术形态新增项）

**定义（顺序金叉）**：
1. 5 日均线上穿 10 日均线
2. 5 日均线上穿 20 日均线
3. 10 日均线上穿 20 日均线

**含义**：
- 趋势反转：下跌 → 上涨，底部区域确立
- 强支撑：三角形区域为多头成本区，回调不易跌破
- 资金进场：常伴随成交量放大
- 易涨难跌：「托盘」效应，股价在托上运行更稳

**价托加分（计入技术分，以 10日上穿20日 完成为准）**：
- **+6 分**：10 日上穿 20 日距今日 ≤ **10** 个交易日
- **+4 分**：10 日上穿 20 日距今日 ≤ **20** 个交易日
- **+0 分**：超过 20 日（仍可能「有价托」，判断栏注明：价托形成时间距离目前较远，并显示距今日天数）
- **形成中 / 无**：不加分

**三维表「判断」栏**：技术行必须包含价托有无、距今日天数及加分说明；综合结论首行输出 **价托有无**。

#### H1步：运行三维评估（主命令）

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from entry_model import analyze_entry_signal, print_entry_report
import json

result = analyze_entry_signal(
    symbol='{股票代码}',
    stock_name='{股票名称}',
    use_llm_narrative=True,
)
print_entry_report(result)
print('\n--- JSON ---')
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
"
```

若用户已执行过模式 A 的产业链分析，可传入 `chain_analysis` 避免重复调 LLM（在 Python 中把 dict 赋给变量后传入）。

**仅快速看价托（不跑全量 H）**：

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import detect_golden_triangle, print_golden_triangle_report
print_golden_triangle_report('{股票代码}')
"
```

#### H2步：解读综合结论

从输出中关注：
- **总分 / 等级**：A≥75、B≥60、C≥45、D<45
- **三维共振**：资金/技术/故事各 ≥55 分为 ✅，3/3 为强烈关注
- **价托状态**：是否「成立+新鲜+放量」
- **操作建议**：脚本给出的 `action` 字段
- **年线**：`analyze_entry_signal` 不包含年线数据，需额外执行 `check_annual_line('{股票代码}')`，补充到技术项明细中

#### 模式H输出格式

```
## {股票名称}（{代码}）三维入场评估 · 模式H

### 综合结论
- **总分：** 78/100（B级）
- **判定：** 值得关注
- **共振：** 2/3 — 资金✅ 技术✅ 故事❌
- **建议：** …

### 三维得分
| 维度 | 得分 | 判断 |
|------|------|------|
| 资金 | 72/100 | 近5日主力净流入为正 4/5 天；… |
| 技术 | 45/100 | 综合技术 5/7…。价托：有价托且结构有效；10日内形成（距今日 8 日，技术分+6）。多头排列…；年线：在年线之上 ✅ |
| 故事 | 58/100 | CMP国产替代逻辑清晰…。增量逻辑：1.6T光模块拉动磷化铟需求，已进入小批量阶段… |

### 技术项明细（7+2项）
- 是否盈利：{✅/❌}
- 分时股价在分时均线上方：{✅/❌}
- 股价在5日线上方：{✅/❌}
- 均线多头排列：{✅/❌}
- 均线向上发散：{✅/❌}
- 上涨放量：{✅/❌}
- 近20日阶段新高：{✅/❌}
- 价托/黄金三角：{✅/❌} — {价托成立（新鲜+放量）/价托失效/…}
- 股价在年线（MA250）之上：{✅/❌}

### 价托 / 黄金三角
- **状态：** 价托成立（新鲜+放量）
- **5→10 / 5→20 / 10→20：** 日期
…
```

**输出结尾必须附加交易纪律（祖训）：**

```
### 交易纪律（祖训）

> 以下为投资基本原则，每次交易前应默念：

**准备工作：**
1. 做好调研，做好交易计划
2. 只做自己看得懂的机会，不盲目跟风

**买操作：**
1. 是否有止损，没止损不开仓
2. 买在无人问津时，卖在人声鼎沸处
3. 不要在年线（MA250）之下买票
4. 日K上不要在10日线下方买票
5. 不要盘中买，买入时间限制在10:30前或14:45后

**仓位管理：**
1. 绝对不重仓一个票，严控单笔风险
2. 亏损不加仓（摊薄成本是掩饰错误的开始）

**卖点：**
1. 止盈不提前落袋，也不要贪婪死拿。分仓止盈/移动止盈，让利润奔跑
2. 亏了要认，不要硬扛不割肉

**心态：**
1. 做好自己该做的事（分析逻辑还在不在，资金如何，是否到达止损点），不要眼红别人什么机会都抓住
2. 交易就是观之等之，随之应之。股市是：放弃的艺术，等待的智慧，知对错方得盈余
```

#### 模式H注意事项

1. **A 股专用**：资金流、价托均依赖 A 股 K 线与 akshare。
2. **故事分需 LLM**：`use_llm_narrative=True` 时会调用 `analyze_industry_chain` + 故事打分；网络或 Key 失败时用规则兜底，分数偏中性。
3. **增量逻辑必写**：故事判断栏必须回答"谁在花多少钱买什么"，技术迭代趋势（如 1.6T→3.2T），以及订单/营收是否已验证。明确区分：当前真实增量（已有财报验证）vs 远期故事（行业有前景但尚无公司兑现业绩，如 SiC 目前 Wolfspeed 仍亏损）。
4. **业务纯正度必写**：同一行业标签（如 MLCC）下，终端结构差异巨大。必须拆解公司营收的终端占比（AI 服务器/汽车/消费电子等），对比同行判断纯正度。例如：同样 MLCC，只做 AI 服务器高容的纯正度 > 车规为主的 > 消费电子通用的。行业标签不能说明问题，终端结构才能。
5. **资金数据口径**：主力净流入来自东方财富划分，宜看**趋势与天数**，不宜迷信单日绝对值。
6. **价托非买入信号**：价托是技术加分项；需与资金、故事共振或至少两维同向。
7. **与模式 A 关系**：H 是「入场决策」轻量版；要完整财报、估值、关联公司 → 再用模式 A。

---

### 模式I：每日涨停复盘 + 概念板块排名

**触发关键词**：`分析涨停`、`涨停复盘`、`今日涨停`、`涨停板`、`概念板块排名`、`模式I`

**行为**：通过 akshare 涨停板池 + 概念板块排名接口，纯数据驱动输出每日涨停复盘报告。

**数据源**：纯 akshare（`stock_zt_pool_em` + `stock_board_change_em`），无需截图、LLM 或 WebSearch。

#### I1步：运行每日复盘

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from concept_quality import run_daily_review
result = run_daily_review()
"
```

一次调用输出四部分：
- **一、概念板块涨跌排名**（涨幅 Top 20 + 跌幅 Bottom 20）
- **二、涨停个股全景**（按行业分组，含封板时间、连板数、炸板次数、换手率、封板资金）
- **三、连板标的**（≥2板个股）
- **四、异常标的**（频繁炸板≥3次或换手≥20%）

#### I2步：板块持续性分析

回溯10个交易日，按行业分组评分。默认仅展示 Top 20 高分板块。

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from concept_quality import sector_persistence
result = sector_persistence(lookback=10)
"
```

输出：
- **10日总分**：累计评分，≥8只=10分，5-7只=7分，3-4只=4分，1-2只=1分
- **分段时间**：今日 / 1-3日 / 4-7日 / 8-10日，看热度是在上升还是消退
- **趋势箭头**：↗加速（近期>远期1.5倍）、↗走强、→持平、↘减弱、🆕新主线（近期有热度但远期无）、✗消失
- **5日存活率**：5个交易日前的涨停股今天还在涨停的比例

#### 模式I输出格式

```
## A股每日复盘报告（YYYY-MM-DD）

> 涨停 N 只

### 一、概念板块涨跌排名
#### 🔥 涨幅居前 Top 20
| # | 概念 | 涨幅 | 主力净流入 |
...

#### 📉 跌幅居前 Bottom 20
| # | 概念 | 跌幅 | 主力净流入 |
...

### 二、涨停个股全景（N只）
#### 按行业分类
##### 光学光电（10只）
| 股票 | 代码 | 封板 | 连板 | 炸板 | 换手 | 封板资金 |
...

### 三、连板标的（≥2板，M只）
### 四、异常标的（频繁炸板或高换手，K只）
```

#### 模式I注意事项

1. **数据实时性**：akshare 涨停板池数据来自东方财富，交易日当天可用。
2. **自动过滤**：ST/\*ST 股票和新股自动过滤，不纳入复盘。
3. **概念板块排名**：自动过滤"融资融券"、"深股通"、"机构重仓"等元概念，只保留有实际产业含义的概念板块。
4. **日期支持**：`run_daily_review(date='20260520')` 可指定历史日期复盘。
5. **与 limit-up-analyzer 区别**：模式 I 纯 akshare 数据，无需截图和 LLM 调用的，适合快速复盘；limit-up-analyzer 从截图提取+概念关联度分析，适合深度分析个股与概念的关联。

---

## 输入

**A 股（模式A/B）**：A股股票名称（如"贵州茅台"）或代码（如"600519"），纯数字 6 位。

**美股（模式C/D）**：美股 ticker（如 AAPL、TSLA、NVDA），包含字母。如果只提供公司名称，需要用 WebSearch 确认对应的 ticker 符号。

## 工作流程

严格按照以下步骤执行，每一步都不可省略：

### 第1步：获取财务数据和实时行情（akshare + 腾讯行情，并行执行）

**第1步合并了原第1步（WebSearch财务）+ 第2步（行情/均线），一次并行执行替代过去4次串行调用。**

使用 Bash 工具并行执行以下两个命令：

**命令A：akshare 财务数据（替代 WebSearch × 3）**

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import get_a_share_financials, print_a_share_financials
import json
data = get_a_share_financials('{股票代码}')
print_a_share_financials(data)
print('\n--- JSON ---')
print(json.dumps(data, ensure_ascii=False, indent=2))
"
```

从输出中提取：
- 最新年报：营收、归母净利润及同比增速、EPS、BVPS
- 最新单季度：营收、净利润及同比
- 毛利率、净利率、ROE、资产负债率、每股经营现金流
- 是否盈利（profit: true/false）

**命令B：腾讯行情 + 均线（替代原第2步）**

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import get_ak_a_stock_price, check_intraday_avg, check_ma_status, check_annual_line
get_ak_a_stock_price('{股票代码}')
check_intraday_avg('{股票代码}')
check_ma_status('{股票代码}')
check_annual_line('{股票代码}')
"
```

从输出中提取：实时股价、涨跌幅、分时均价、MA5/MA10/MA20、均线排列状态、年线MA250、是否在年线上方。

**注意**：
- 命令A和命令B互不依赖，**必须并行**发出（两个 Bash tool call 放在同一条消息中）。
- 如果 akshare 调用失败（`available: false`），回退到 WebSearch 搜索财报。搜索关键词：`{股票名称} {当前年份} 年报 主营业务 归母净利润`、`{股票名称} {当前年份} 一季报 业绩`。
- 公司主营业务描述从命令A数据中推断（不需要单独搜索），如果需要更详细描述再补搜一次 WebSearch。

### 第4步：产业链深度分析（核心步骤）

这一步是整个分析的核心，不能只罗列概念板块标签，必须深入挖掘股价上涨/下跌的产业链底层逻辑。

使用 Bash 工具执行本 skill 目录下 `scripts/llm_analysis.py` 中的函数，调用大模型（阿里千问）进行产业链分析：

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from llm_analysis import analyze_industry_chain
result = analyze_industry_chain(
    stock_name='{股票名称}',
    stock_code='{股票代码}',
    main_business='{主营业务描述（从 akshare 行业推断，或补搜一次 WebSearch）}',
    profit_status='{第1步A命令获取的盈利情况}',
    price_change_pct={第1步B命令获取的涨跌幅数值}
)
"
```

从分析结果中提取：
- **产业链定位**：上游（原材料/矿产）→ 中游（加工/制造）→ 下游（终端应用）
- **核心产品/原材料**：公司最关键的产出物或所需原材料
- **供需现状**：核心产品是否涨价/缺货/产能扩张/产能过剩
- **下游需求驱动**：是什么终端需求在拉动
- **产业链逻辑链**：完整的因果传导链
- **核心驱动因素**：股价变动的真实原因（1-2句话）
- **增量逻辑**：核心产品的具体增量来源是什么？是技术迭代（如 1.6T→3.2T 光模块拉动磷化铟需求）、产能扩张、还是下游客户资本开支周期？必须写清"谁在花多少钱买什么、增速多少"，区分实打实的当前增量（已有订单/营收验证）vs 远期故事（如 SiC 目前 Wolfspeed 仍亏损、增量尚未兑现）
- **业务纯正度**：公司营收/毛利中有多少比例直接来自最火热的增量市场？同一行业（如 MLCC）内，不同公司的终端结构可能差异很大：AI 服务器端 > 汽车端 > 消费电子端。必须写明各终端占比估算，并与同行对比纯正度高低。例如：同样做 MLCC，A 公司 60% 营收来自 AI 服务器高容 MLCC（纯正度高），B 公司 80% 来自消费电子通用 MLCC（只是蹭概念）。**

**注意**：优先使用大模型分析。如果 LLM 调用失败（API Key 未配置或网络错误），回退到使用 WebSearch 进行产业链分析，搜索关键词：
1. `{股票名称} 产业链 上游原材料 核心产品 {当前年份}`
2. `{股票名称} 为什么涨 核心逻辑 供需 {当前年份}`
3. `{股票名称} 产品 供需缺口 涨价 缺货 {当前年份}`
4. `{股票名称} 下游客户 下游需求 {当前年份}`

### 第5步：关联核心公司

根据第4步的产业链分析结果，找到产业链同一环节或上下游的**A股相关核心公司**。

使用 Bash 工具执行本 skill 目录下 `scripts/llm_analysis.py` 中的函数查找关联公司：

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from llm_analysis import find_related_companies
companies = find_related_companies(
    stock_name='{股票名称}',
    stock_code='{股票代码}',
    chain_analysis={第4步返回的dict变量}
)
"
```

**注意**：此函数依赖第4步的返回结果。如果第4步使用 LLM 成功，会返回一个 dict 对象，直接传入即可。如果第4步使用 WebSearch 回退，需要手动构造 chain_analysis 参数：

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from llm_analysis import find_related_companies
companies = find_related_companies(
    stock_name='{股票名称}',
    stock_code='{股票代码}',
    chain_analysis={'chain_position': '{产业链定位}', 'core_products': ['{核心产品}'], 'core_raw_materials': ['{原材料}'], 'logic_chain': '{逻辑链}'}
)
"
```

如果 LLM 调用也失败，回退到 WebSearch：
1. `{核心产品/原材料} A股 上市公司 生产厂商 {当前年份}`
2. `{核心产品/原材料} 概念股 龙头 公司 {当前年份}`

**输出规则**：
- 只需列出公司名称和股票代码，不需要对这些公司再做详细分析
- 按产业链环节分组（上游原材料、中游制造、下游应用）
- 标注哪些公司是龙头/产能最大

### 第6步：综合判断

完成第4步产业链分析后，使用 Bash 工具执行 `comprehensive_judge` 函数生成最终评级。

将第1步A命令的**是否盈利**（`profit` 字段，True/False）和第4步的**核心驱动因素**（1-2句话概括）作为参数传入：

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import comprehensive_judge
comprehensive_judge('{股票代码}', profit={True/False}, reason='{核心驱动因素}')
"
```

**评级规则：**
- 7项中符合 **5-7项** → 买入
- 7项中符合 **3-4项** → 观望
- 7项中符合 **0-2项** → 卖出

**7项指标：** 是否盈利、分时股价在分时均线上方、股价在5日线上方、均线多头排列、均线向上发散、上涨放量、近20日阶段新高

### 第7步：价值投资视角（巴菲特框架）

从第1步A命令已获取的财报数据中提取以下指标，按巴菲特的价值投资框架进行评分。**数据全部来自 akshare，无需额外 API 调用。**

**评分维度（7项，每项 ✅/❌）：**

| # | 指标 | 标准 | 数据来源 |
|---|------|------|---------|
| 1 | ROE | 最新年报 ROE > 15% | 第1步A命令（`roe` 字段） |
| 2 | ROE 稳定性 | 近3年 ROE 均 > 10%（或趋势向上） | 第1步A命令（如仅有当年数据，看是否高于15%） |
| 3 | 毛利率趋势 | 最新毛利率不低于3年前水平 | 第1步A命令（`gross_margin` 字段） |
| 4 | 负债水平 | 资产负债率 < 60%（A股）/ Debt/Equity < 2（美股） | 第1步A命令（`debt_ratio` 字段） |
| 5 | 自由现金流 | 经营现金流净额 > 0 且 资本开支/经营现金流 < 0.7 | 第1步A命令（`ocf_per_share` 字段） |
| 6 | PEG | PE(TTM) / 净利润增速 < 1.5（增速用最新/预期值） | PE 来自第1步B命令，增速来自A命令 |
| 7 | 护城河 | LLM 综合判断（从主营业务、毛利率稳定性、行业地位推断） | LLM 推断 |

**评级规则：**
- 7项中符合 **5-7项** → 优（符合巴菲特选股标准）
- 7项中符合 **3-4项** → 中（部分达标，有改善空间）
- 7项中符合 **0-2项** → 差（不符合价值投资标准）

**注意：** 如果某项数据无法从搜索中获取，不编造数据，标注"未获取"，该项计为 ❌（但需在报告中注明"数据不足"）。

## 输出格式

按以下格式输出分析结果：

```
## {股票名称}（{股票代码}）分析报告

### 一、公司基本面

**主营业务：** {主营业务描述}

### 二、盈利情况

**最近一年归母净利润：** {金额}（同比 {变化百分比}%）
**最近一个报告期业绩：** {报告期名称}，营收 {金额}，净利润 {金额}（同比 {变化百分比}%）
**是否盈利：** {盈利/亏损}

### 三、技术指标

**实时股价：** {价格} 元（涨跌幅 {百分比}%）
**分时股价是否在分时均线以上：** {是/否}（分时现价 {价格}，分时均价 {价格}）
**MA5 / MA10 / MA20：** {MA5} / {MA10} / {MA20}
**股价是否在5日线以上：** {是/否}
**均线多头排列：** {是/否}
**均线向上发散：** {是/否}
**年线 MA250：** {数值}，股价在年线之上：{是/否}

### 四、产业链分析

**产业链定位：** {公司处于产业链的哪个环节}
**核心产品/原材料：** {具体材料或产品名称}
**产业链逻辑链：** {下游需求变化} → {中游产品变化} → {上游原材料变化} → {对公司的影响}
**核心驱动因素：** {用1-2句话说清楚股价变动的真实原因，不能只说"属于XX概念"}
**增量逻辑：** {具体增量：谁在花钱买什么、技术迭代趋势（如1.6T→3.2T）、订单/营收是否已验证。区分当前真实增量 vs 远期故事}
**业务纯正度：** {公司营收中直接来自最热增量市场的比例估算，终端结构拆解（AI服务器/汽车/消费电子等），与同行对比纯正度高低}

### 五、关联核心公司

**上游原材料：** {公司名（代码，简要标签）}、...
**中游制造：** {公司名（代码，简要标签）}、...
**下游应用：** {公司名（代码，简要标签）}、...

### 六、综合判断

**7项指标明细：**
1. 是否盈利：{是/否}
2. 分时股价在分时均线上方：{是/否}
3. 股价在5日线上方：{是/否}
4. 均线多头排列：{是/否}
5. 均线向上发散：{是/否}
6. 上涨放量：{是/否}
7. 近20日阶段新高：{是/否}

**符合项数：** {N}/7
**综合评级：** {买入/观望/卖出}
**可能上涨理由：** {核心驱动因素}

### 七、价值投资视角（巴菲特框架）

| # | 指标 | 标准 | 实际 | 判断 |
|---|------|------|------|------|
| 1 | ROE | > 15% | {最新年报ROE} | {✅/❌} |
| 2 | ROE 稳定性 | 近3年均>10% | {近3年ROE数据或趋势} | {✅/❌} |
| 3 | 毛利率趋势 | 不下降 | {近年毛利率趋势} | {✅/❌} |
| 4 | 负债水平 | < 60% | {资产负债率} | {✅/❌} |
| 5 | 自由现金流 | 经营现金流>0 且 CAPEX/OCF<0.7 | {FCF指标} | {✅/❌} |
| 6 | PEG | < 1.5 | {PE/增速} | {✅/❌} |
| 7 | 护城河 | LLM判断 | {定性判断} | {✅/❌} |

**符合项数：** {N}/7
**巴菲特评级：** {优/中/差}
**一句话总结：** {从价值投资角度的简要结论}

---
*数据时间：{数据日期}*
*提示：以上数据来自互联网搜索，建议结合实时行情软件验证。*

### 九、交易纪律（祖训）

> 以下为投资基本原则，每次交易前应默念：

**准备工作：**
1. 做好调研，做好交易计划
2. 只做自己看得懂的机会，不盲目跟风

**买操作：**
1. 是否有止损，没止损不开仓
2. 买在无人问津时，卖在人声鼎沸处
3. 不要在年线（MA250）之下买票
4. 日K上不要在10日线下方买票
5. 不要盘中买，买入时间限制在10:30前或14:45后

**仓位管理：**
1. 绝对不重仓一个票，严控单笔风险
2. 亏损不加仓（摊薄成本是掩饰错误的开始）

**卖点：**
1. 止盈不提前落袋，也不要贪婪死拿。分仓止盈/移动止盈，让利润奔跑
2. 亏了要认，不要硬扛不割肉

**心态：**
1. 做好自己该做的事（分析逻辑还在不在，资金如何，是否到达止损点），不要眼红别人什么机会都抓住
2. 交易就是观之等之，随之应之。股市是：放弃的艺术，等待的智慧，知对错方得盈余
```

---

### 第8步：估值模型分析

完成前面 7 步后，执行估值模型分析。使用 `valuation.py` 中的函数，对股票进行多模型交叉估值。

#### A股估值模型

从第1步A命令获取 EPS、BVPS、归母净利润增速、每股股息（如有）。从第1步B命令获取当前 P/E、P/B、当前股价。

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from valuation import comprehensive_valuation_a, print_valuation_report_a
import json

results = comprehensive_valuation_a(
    symbol='{股票代码}',
    name='{股票名称}',
    eps={EPS},
    bvps={BVPS或None},
    growth_rate={净利润增速%或None},
    dps={每股股息或None},
    current_pe={当前PE},
    current_pb={当前PB},
    current_price={当前股价},
    profit={True/False}
)
print_valuation_report_a('{股票代码}', '{股票名称}', results, {当前股价})
print('\n--- JSON ---')
print(json.dumps(results, ensure_ascii=False, indent=2))
"
```

**数据获取说明：**
- EPS (`eps`)、BVPS (`bvps`)、归母净利润增速 (`growth_rate`)、每股股息 → 从第1步A命令 JSON 输出中提取
- 当前 P/E、P/B → 从第1步B命令腾讯行情接口自动获取（字段39、46）
- 当前股价 → 第1步B命令已获取

**A股可用模型（5个）：**
1. **P/E 倍数法** — 合理股价 = EPS × 行业合理PE，分保守/基准/乐观三档
2. **P/B 倍数法** — 合理股价 = BVPS × 行业合理PB
3. **格雷厄姆数** — Graham Number = √(22.5 × EPS × BVPS)
4. **PEG 估值** — 合理PE = 盈利增速，合理股价 = EPS × 增速
5. **DDM 股息贴现** — Gordon Growth Model（仅当有分红时适用）

**注意：** 如果某项数据缺失（如 BVPS 无法获取），对应模型会自动跳过，不会编造数据。

#### A股输出格式（追加在第七部分之后）

在输出模板的"七、价值投资视角"之后，追加：

```
### 八、估值模型分析

#### 多模型估值汇总

| 估值模型 | 保守估值 | 基准估值 | 乐观估值 | 当前价格 | 折价/溢价 | 判断 |
|---------|---------|---------|---------|---------|----------|------|
| P/E倍数法 | ¥XX.XX | ¥XX.XX | ¥XX.XX | ¥XX.XX | +XX% | 略低估 |
| P/B倍数法 | ¥XX.XX | ¥XX.XX | ¥XX.XX | ¥XX.XX | -XX% | 合理 |
| 格雷厄姆数 | — | ¥XX.XX | — | ¥XX.XX | +XX% | 高于GN |
| PEG估值 | ¥XX.XX | ¥XX.XX | ¥XX.XX | ¥XX.XX | -XX% | 略高估 |
| DDM(股息) | ¥XX.XX | ¥XX.XX | ¥XX.XX | ¥XX.XX | +XX% | 低估 |

#### 估值结论

**综合估值区间：** ¥XX.XX — ¥XX.XX
**当前价格：** ¥XX.XX，处于XX区间（折价/溢价 XX%）
**情景分析：**
- 保守情景（P/E=XXx）：¥XX.XX
- 基准情景（P/E=XXx）：¥XX.XX
- 乐观情景（P/E=XXx）：¥XX.XX

#### 推荐买入价格

**保守公允价值（各模型保守估值均值）：** ¥XX.XX

| 类型 | 价格 | 安全边际 | 相对现价 |
|------|------|---------|----------|
| 安全买入 | ¥XX.XX | 25% | -XX% |
| 推荐买入 | ¥XX.XX | 15% | -XX% ✅ |
| 激进买入 | ¥XX.XX | 5% | -XX% |
| **当前价格** | **¥XX.XX** | — | — |

**当前状态：** 🟢/🟡/🟠/🔴
> ✅ 当前价格已进入推荐买入区间 / ⏳ 距推荐买入价还需下跌约 XX%

> 使用 X 个模型进行交叉验证。估值仅作为长期价值参考，短期价格受情绪和资金驱动。
```

---

## &#32654;&#32929;&#27169;&#24335;C&#65306;&#21333;&#21482;&#32654;&#32929;&#35814;&#32454;&#20998;&#26512;

### C1步：获取美股基本面和财务数据

使用 Bash 工具执行 `scripts/stock.py` 中的美股函数来获取公司信息和财务数据：

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import get_us_stock_info
info = get_us_stock_info('{TICKER}')
"
```

从输出中提取：公司名、行业、股价、涨跌幅、市值、PE、EPS、归母净利润、52周高低点、Beta。

### C2步：搜索美股最新资讯和财报

使用 WebSearch 搜索美股相关新闻和财报信息。**搜索语言以英文为主**：

1. `{Company Name} {current year} quarterly earnings revenue EPS`
2. `{ticker} stock news analyst rating {current year}`
3. `{ticker} earnings call transcript {current year}`

从搜索结果中提取：主营业务描述、最新季度营收/EPS及同比变化、是否盈利（EPS > 0）。

### C3步：获取美股技术指标

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import get_us_ma_status, get_us_rsi
get_us_ma_status('{TICKER}')
get_us_rsi('{TICKER}')
"
```

提取：50日MA、200日MA、股价是否在50/200日线上方、黄金交叉状态、RSI(14)数值。

### C4步：美股产业链分析（核心步骤）

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from llm_analysis import analyze_industry_chain_us
result = analyze_industry_chain_us(
    stock_name='{公司名}',
    ticker='{TICKER}',
    sector='{C1获取的sector}',
    industry='{C1获取的industry}',
    main_business='{C2获取的主营业务}',
    eps={EPS},
    pe={PE},
    price_change_pct={涨跌幅}
)
"
```

提取：全球产业定位、核心产品/服务、关键客户/供应商、供需现状、市场驱动、产业链逻辑、核心驱动因素、关键风险。

LLM 失败时回退到 WebSearch：`{Company Name} market analysis supply chain {current year}`。

### C5步：美股关联公司

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from llm_analysis import find_related_companies_us
companies = find_related_companies_us(
    stock_name='{公司名}',
    ticker='{TICKER}',
    chain_analysis={C4返回的dict}
)
"
```

输出：直接竞争对手、上游供应商、下游客户/合作伙伴。

### C6步：美股综合判断

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import comprehensive_judge_us
comprehensive_judge_us('{TICKER}', profit={True/False}, reason='{核心驱动}')
"
```

**7项指标：** 是否盈利、股价在50日线上方、股价在200日线上方、黄金交叉（50>200）、RSI在30-70区间、成交量高于5日均量、接近52周高点（10%内）

**评级：** 5-7项→买入，3-4项→观望，0-2项→卖出

### C7步：价值投资视角（巴菲特框架）

与 A 股第7步完全相同的逻辑，但指标标准做以下调整：

- 负债水平：Debt/Equity < 2（美股替代资产负债率<60%）
- PEG：同样 PE(TTM) / 净利润增速 < 1.5
- 其余指标（ROE、毛利率趋势、FCF、护城河）标准不变

数据来源：ROE/毛利率/负债/FCF 来自 C2 步的 WebSearch 财报数据；PE 和净利润增速来自 C1 步的 yfinance 输出。

**评级规则同A股第7步。**

### C8步：估值模型分析（核心步骤）

完成前面 C1-C7 步后，使用 `valuation.py` 对美股进行多模型交叉估值。美股数据源更丰富（yfinance 提供 EBITDA、FCF、净债务等），可用模型比 A 股更全面。

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from valuation import comprehensive_valuation_us, print_valuation_report_us
import json

results = comprehensive_valuation_us(
    ticker='{TICKER}',
    eps={C1步获取的EPS或None},
    growth_rate={盈利增速%或None},
    profit={True/False}
)
print_valuation_report_us('{TICKER}', '{C1步获取的公司名}', results)
print('\n--- JSON ---')
print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
"
```

**美股可用模型（6个）：**
1. **P/E 倍数法** — 分保守/基准/增长三档，对标行业PE
2. **EV/EBITDA** — 企业价值倍数法，更适合重资产行业（参考CLF文章方法）
3. **格雷厄姆数** — Graham Number = √(22.5 × EPS × BVPS)
4. **PEG 估值** — Peter Lynch 方法，合理PE = 盈利增速
5. **DCF 现金流折现** — 5年预测 + 终值，附带 WACC×g 敏感性分析表
6. **DDM 股息贴现** — Gordon Growth Model（仅当有分红时适用）

**数据获取说明：**
- EPS、BVPS、EBITDA、FCF、净债务、股息 → 全部从 yfinance 自动获取
- 当前股价、P/E → C1步已获取
- 行业PE、行业EV/EBITDA、WACC → 从 `valuation_reference.yaml` 读取
- DCF 的增长率和 WACC → 基于行业默认值，可通过 LLM 增强

**DCF 敏感性分析：** DCF 模型会输出 WACC（±2%）× 永续增长率（1%-3%）的 3×3 矩阵，展示不同假设下的估值区间。

#### 美股输出格式（追加在第七部分之后）

在美股输出模板的"七、价值投资视角"之后，追加：

```
### 八、估值模型分析

#### 多模型估值汇总

| 估值模型 | 保守估值 | 基准估值 | 乐观估值 | 当前价格 | 折价/溢价 | 判断 |
|---------|---------|---------|---------|---------|----------|------|
| P/E倍数法 | $XX.XX | $XX.XX | $XX.XX | $XX.XX | +XX% | 低估 |
| EV/EBITDA | $XX.XX | $XX.XX | $XX.XX | $XX.XX | -XX% | 合理 |
| 格雷厄姆数 | — | $XX.XX | — | $XX.XX | +XX% | 高于GN |
| PEG估值 | $XX.XX | $XX.XX | $XX.XX | $XX.XX | -XX% | 高估 |
| DCF(折现) | $XX.XX | $XX.XX | $XX.XX | $XX.XX | +XX% | 低估 |

> DCF敏感性：WACC 8%/10%/12% × g 1%/2%/3%

#### 估值结论

**综合估值区间：** $XX.XX — $XX.XX
**当前价格：** $XX.XX，处于XX区间（XX%）
**情景分析：**
- 保守情景：$XX.XX（P/E=XXx / EV/EBITDA=XXx）
- 基准情景：$XX.XX（P/E=XXx / EV/EBITDA=XXx）
- 乐观情景：$XX.XX（P/E=XXx / EV/EBITDA=XXx）

#### 推荐买入价格

**保守公允价值（各模型保守估值均值）：** $XX.XX

| 类型 | 价格 | 安全边际 | 相对现价 |
|------|------|---------|----------|
| 安全买入 | $XX.XX | 25% | -XX% |
| 推荐买入 | $XX.XX | 15% | -XX% ✅ |
| 激进买入 | $XX.XX | 5% | -XX% |
| **当前价格** | **$XX.XX** | — | — |

**当前状态：** 🟢/🟡/🟠/🔴
> ✅ 当前价格已进入推荐买入区间 / ⏳ 距推荐买入价还需下跌约 XX%

> 使用 X 个模型交叉验证。估值模型假设来自 valuation_reference.yaml，可自行调整。
```

### 美股单只输出格式

```
## {公司名}（{TICKER}）美股分析报告

### 一、公司基本面
**行业：** {Sector} / {Industry}
**主营业务：** {描述}

### 二、盈利情况
**最新 EPS：** {数值}
**PE Ratio：** {数值}
**归母净利润：** {金额}（TTM）
**市值：** {市值}
**最近季度业绩：** 营收{金额}，EPS{金额}（同比{变化}%）
**是否盈利：** {盈利/亏损}

### 三、技术指标
**实时股价：** ${价格}（涨跌幅{百分比}%）
**50日MA / 200日MA：** ${MA50} / ${MA200}
**股价在50日线上方：** {是/否}
**股价在200日线上方：** {是/否}
**黄金交叉（50>200）：** {是/否}
**RSI(14)：** {数值}（正常/超买/超卖）
**52周高低：** ${高} / ${低}

### 四、产业链分析
**产业定位：** {全球产业链位置}
**核心产品/服务：** {具体产品}
**产业链逻辑链：** {需求→行业→公司}
**核心驱动因素：** {1-2句话}
**关键风险：** {风险}

### 五、关联核心公司
**直接竞争对手：** {公司名（TICKER）}、...
**上游供应商：** {公司名（TICKER）}、...
**下游客户/合作伙伴：** {公司名（TICKER）}、...

### 六、综合判断
**7项指标明细：**
1. 是否盈利：{是/否}
2. 股价在50日线上方：{是/否}
3. 股价在200日线上方：{是/否}
4. 黄金交叉（50>200）：{是/否}
5. RSI在30-70区间：{是/否}
6. 成交量高于5日均量：{是/否}
7. 接近52周高点（10%内）：{是/否}

**符合项数：** {N}/7
**综合评级：** {买入/观望/卖出}

### 七、价值投资视角（巴菲特框架）

| # | 指标 | 标准 | 实际 | 判断 |
|---|------|------|------|------|
| 1 | ROE | > 15% | {最新年报ROE} | {✅/❌} |
| 2 | ROE 稳定性 | 近3年均>10% | {近3年ROE数据或趋势} | {✅/❌} |
| 3 | 毛利率趋势 | 不下降 | {近年毛利率趋势} | {✅/❌} |
| 4 | 负债水平 | D/E < 2 | {Debt/Equity} | {✅/❌} |
| 5 | 自由现金流 | OCF>0 且 CAPEX/OCF<0.7 | {FCF指标} | {✅/❌} |
| 6 | PEG | < 1.5 | {PE/增速} | {✅/❌} |
| 7 | 护城河 | LLM判断 | {定性判断} | {✅/❌} |

**符合项数：** {N}/7
**巴菲特评级：** {优/中/差}
**一句话总结：** {从价值投资角度的简要结论}

---
*数据时间：{日期}*
*免责声明：分析结果仅供参考，不构成投资建议。*
```

---

## 美股模式D：批量对比分析

**触发：** `批量分析美股 AAPL, TSLA, NVDA`

### D1步：并行获取所有美股基本数据

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import get_us_stock_info
get_us_stock_info('AAPL')
"
```

每只股票并行执行，提取：公司名、股价、涨跌幅、EPS、PE、Sector。

### D2步：并行搜索财报和新闻（WebSearch）

为每只股票并行搜索：`{ticker} {current year} quarterly earnings revenue`。

### D3步：并行获取技术指标（静默版）

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import get_us_technical_dict
import json
result = get_us_technical_dict('AAPL')
print(json.dumps(result, ensure_ascii=False))
"
```

### D4步：并行美股产业链分析

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from llm_analysis import analyze_industry_chain_us
result = analyze_industry_chain_us(stock_name='Apple Inc.', ticker='AAPL', sector='Technology', industry='Consumer Electronics', main_business='...', eps=6.5, pe=30.0, price_change_pct=1.5)
"
```

### D5步：并行美股关联公司

调用 `find_related_companies_us`，依赖 D4 结果。

### D6步：并行美股综合判断（可与D4/D5同时）

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import comprehensive_judge_us_dict
import json
result = comprehensive_judge_us_dict('AAPL', profit=True, reason='...')
print(json.dumps(result, ensure_ascii=False))
"
```

### D7步：打印美股汇总对比表

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import print_comparison_table_us
stocks_data = [
    {'name': 'Apple Inc.', 'ticker': 'AAPL', 'price': 195.0, 'change_pct': 1.5, 'profit': True, 'eps': 6.5, 'pe': 30.0, 'sector': 'Technology', 'chain_position': 'Downstream - Consumer Electronics', 'core_driver': 'iPhone+服务收入增长', 'judge': {'items': {...}, 'score': 5, 'rating': '买入'}},
    ...
]
print_comparison_table_us(stocks_data)
"
```

### 美股批量输出格式

```
## 美股批量分析汇总

| 股票 | Ticker | 股价 | 涨跌幅 | 盈利 | 50日线 | 200日线 | 金叉 | RSI | 放量 | 52高 | 评分 | 评级 | 核心驱动 |
|------|--------|------|--------|------|--------|---------|------|-----|------|------|------|------|--------|
| Apple Inc. | AAPL | $195.00 | +1.50% | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **7/7** | **买入** | iPhone+服务增长 |

> 汇总：买入 N 只 | 观望 N 只 | 卖出 N 只

### 推荐排序
1. **AAPL** — 7/7 买入，iPhone+服务增长
2. **TSLA** — 4/7 观望，利润率承压
```

### 美股批量注意事项

1. 最大限度并行执行。
2. D5（关联公司）依赖 D4（产业链分析）结果。
3. D6（综合判断）只依赖 D1/D3，可与 D4/D5 同时执行。
4. 每批次最多 8 只股票。
5. WebSearch 以英文为主。

---

### 模式J：放量+价托 双条件选股

**触发关键词**：`选股`、`筛选`、`放量选股`、`价托选股`、`模式J`、`放量+价托`

**行为**：全市场扫描 A 股（可限定板块），筛选同时满足以下两条件的股票：
1. **昨日成交量 >= 前日成交量 × 1.8**（可自定义倍数）
2. **近 10 个交易日内完成价托**（10日上穿20日完成 ≤ 10 日）

**数据源**：腾讯 K 线接口（日线数据），无需 akshare（避免频率限制）。

#### J1步：运行全市场扫描

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from screener import screen_volume_jiatuo, print_screen_results, screen_to_json
import json

results = screen_volume_jiatuo(
    volume_ratio=1.8,
    jiatuo_days=10,
    exclude_st=True,
    boards=None,        # 全市场；可选 ['主板', '创业板', '科创板']
    max_workers=30,
    top_n=50,
)
print_screen_results(results, volume_ratio=1.8, jiatuo_days=10)
print('\n--- JSON ---')
print(screen_to_json(results))
"
```

**参数说明：**
- `volume_ratio`：放量倍数阈值（默认 1.8，即昨日量 >= 前日量 × 1.8）
- `jiatuo_days`：价托最大天数（默认 10，即 10日上穿20日 完成 ≤ 10 个交易日）
- `boards`：限定板块，如 `['主板']`、`['创业板', '科创板']`；`None` = 全市场
- `max_workers`：并发线程数（默认 30，网络好可调至 50）
- `top_n`：返回前 N 只（按放量倍数降序排列）

#### J2步：解读结果与二次筛选

从 J1 输出中关注：
- **放量倍数**：越大越好，说明资金异动越明显
- **价托天数**：越近越好（≤5 日为新鲜价托，放量配合更可信）
- **多头排列**：✅ 表示 MA5 > MA10 > MA20，趋势健康
- **涨跌幅**：放量上涨 > 放量下跌（但放量下跌也可能是洗盘）
- **量能确认**：价托完成时是否有量能配合

**二次筛选建议：**
- 优先选：放量倍 > 2.0x + 价托 ≤ 5 日 + 多头排列 ✅ + 当日上涨
- 次优：放量倍 > 1.8x + 价托 ≤ 10 日 + 多头排列 ✅
- 排除：放量下跌过多（当日跌 > 3%）且价托已超 20 日

**批量快速分析（对 Top 5 做三维评估）：**
对 J1 返回的 Top 5 标的，可自动运行模式 H 进行三维打分，确认资金/技术/故事共振情况。

#### 模式J输出格式

```
## 放量+价托 选股结果（YYYY-MM-DD HH:MM）

> 条件：昨日成交量 ≥ 前日 × 1.8  |  价托完成 ≤ 10 个交易日
> 命中 N 只

| 排名 | 代码 | 名称 | 现价 | 涨跌% | 放量倍 | 价托日 | 5日线 | 10日线 | 20日线 | 多头 |
|------|------|------|------|--------|--------|--------|--------|--------|--------|------|
| 1 | 300179 | 四方达 | 50.93 | +6.75% | 2.15x | 2026-06-01 | 48.50 | 45.20 | 42.10 | ✅ |

📈 统计：平均放量 X.XXx | 上涨 X/N | 多头排列 X/N

### 详细列表

  1. XX科技（300XXX）| 50.93 (+6.75%) | 放量 2.15x | 价托 2日前 | 多头✅ 量能✅
  2. ...
```

#### 模式J注意事项

1. **全市场扫描耗时**：5,500+ 只股票，30 线程约需 60-90 秒，请耐心等待。
2. **数据延迟**：腾讯 K 线数据为日线级别，当日数据在收盘后更新。
3. **价托检测精度**：依赖 80 天 K 线数据，新股（上市 < 25 天）会被自动排除。
4. **ST 自动排除**：默认排除 ST/\*ST 股票。
5. **与模式 H 互补**：J 模式是海选筛股，对 Top 标的用 H 模式做三维深度评估。
6. **自定义参数**：`volume_ratio=2.0` 可收紧放量条件，`jiatuo_days=5` 可要求更新鲜的价托。
7. **板块限定**：传 `boards=['创业板']` 可只扫创业板，大幅缩短扫描时间。

---

## 重要注意事项

1. **A股财务数据优先用 akshare**：第1步/B1步优先使用 `get_a_share_financials()`（akshare 同花顺接口），失败时回退到 WebSearch。
2. **数据时效性**：所有搜索必须包含当前年份/日期，确保获取最新数据。
3. **诚实标注**：如果某个指标无法获取，明确标注"未能获取"而不是编造数据。
4. **免责声明**：分析结果仅供参考，不构成投资建议。
5. **搜索语言**：A股搜索用中文，美股搜索以英文为主，允许中文结果。
6. **产业链分析深度**：第4/C4步是核心，必须深入挖掘产业链逻辑，不能停留在表面概念标签。
7. **关联公司只列名称**：第5/C5步只需列出关联公司的名称和代码，不要再逐一运行完整分析。
8. **美股数据源**：美股使用 yfinance（Yahoo Finance），无需额外 API Key，数据可能有延迟。
9. **Ticker 格式**：美股 ticker 一律大写（如 AAPL），A 股代码为 6 位数字。
10. **推荐模式不单独分析**：E1/E4 仅做筛选排序，不深入到每只股票的产业链分析和综合判断。如需详细分析某只推荐标的，再使用模式A或C。
11. **模式H与模式A分工**：H 用于「值不值得入手」三维打分（资金+技术含价托+故事）；A 用于完整八步深度报告。可先 H 筛选，再对高分标的跑 A。

---

## A股批量分析模式

当用户提供一个 A 股股票列表（如"分析药明康德、致尚科技、爱建集团"或"批量分析A股 603259 301486"），进入 A 股批量模式。批量模式下需要平衡效率和准确性：

### 输入

用户提供一个A股股票名称或代码列表，如 `["药明康德", "致尚科技", "爱建集团"]` 或 `["603259", "301486", "600643"]`。

### 批量工作流程

#### B1步：并行获取所有股票的财务+行情数据（akshare + 腾讯行情）

为每只股票并行执行两条命令（财务 + 技术），所有调用一次性发出：

**命令A（akshare 财务）：**
```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import get_a_share_financials
import json
data = get_a_share_financials('{股票代码}')
print(json.dumps(data, ensure_ascii=False, indent=2))
"
```

**命令B（腾讯行情+技术指标）：**
```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import get_technical_dict
import json
result = get_technical_dict('{股票代码}')
print(json.dumps(result, ensure_ascii=False))
"
```

从命令A提取：eps、bvps、growth_rate、profit、gross_margin、roe、debt_ratio、ocf_per_share、revenue、net_profit
从命令B提取：price、change_pct、intraday_price、intraday_avg、above_intraday_avg、ma5、ma10、ma20、above_ma5、bullish_alignment、diverging

**注意**：命令A和命令B互不依赖，必须并行发出。如果 akshare 调用失败（`available: false`），回退到 WebSearch 搜索 `{股票名称} {当前年份} 年报 归母净利润`。

#### B4步：并行执行产业链分析（核心步骤）

为每只股票并行调用 `analyze_industry_chain`（LLM 分析），所有调用可以一次性发出：

```bash
# 股票1
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from llm_analysis import analyze_industry_chain
result = analyze_industry_chain(stock_name='药明康德', stock_code='603259', main_business='...', profit_status='...', price_change_pct=10.0)
"
# 股票2 (并行)
python3 -c "..."
# 股票3 (并行)
python3 -c "..."
```

从每个结果中提取：chain_position, core_products, core_driver 等。

#### B5步：并行查找关联核心公司

为每只股票并行调用 `find_related_companies`，传入上一步获取的 chain_analysis dict：

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from llm_analysis import find_related_companies
companies = find_related_companies(stock_name='药明康德', stock_code='603259', chain_analysis={'chain_position': '...', ...})
"
```

只列出关联公司名称和代码，不需要展开分析。

#### B6步：并行执行综合判断

为每只股票并行调用 `comprehensive_judge_dict`（静默版）：

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import comprehensive_judge_dict
import json
result = comprehensive_judge_dict('603259', profit=True, reason='核心驱动因素描述')
print(json.dumps(result, ensure_ascii=False))
"
```

#### B7步：打印汇总对比表

将 B1-B6 步收集到的所有数据汇总为一个 list of dict，调用 `print_comparison_table` 输出：

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/bertramliu/.claude/skills/financial-assistant/scripts')
from stock import print_comparison_table
stocks_data = [
    {
        'name': '药明康德', 'code': '603259', 'price': 110.57, 'change_pct': 10.0,
        'profit': True, 'net_profit': '191.51亿（+102.65%）', 'q1_data': '营收124.36亿，净利46.52亿（+26.68%）',
        'chain_position': '中游 CRO/CDMO一体化', 'core_driver': 'TIDES平台商业化突破，在手订单597.7亿创新高',
        'judge': {'items': {...}, 'score': 5, 'rating': '买入', 'reason': '...'}
    },
    ...
]
print_comparison_table(stocks_data)
"
```

### 批量输出格式

对比表之后，可选地为评分最高的 1-2 只股票输出简要的产业链分析（core_driver），并给出最终推荐排序。

```
## 批量分析汇总

| 股票 | 代码 | 股价 | 涨跌幅 | 盈利 | 分时 | 5日线 | 多头 | 发散 | 放量 | 新高 | 评分 | 评级 | 核心驱动 |
|------|------|------|--------|------|------|-------|------|------|------|------|------|------|----------|
| 药明康德 | 603259 | 110.57 | +10.00% | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | **5/7** | **买入** | TIDES平台商业化... |
| 致尚科技 | 301486 | 202.86 | -3.44% | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | **2/7** | **卖出** | 主业扣非亏损拖累... |

> 汇总：买入 1 只 | 观望 0 只 | 卖出 1 只

### 推荐排序

1. **药明康德（603259）** — 5/7 买入，TIDES平台商业化突破...
2. **致尚科技（301486）** — 2/7 卖出，主业扣非亏损+消费电子拖累...
```

### 批量模式注意事项

1. **最大限度并行**：B1-B6 各步中，所有股票独立的任务可以并行发出。
2. **B4/B5 依赖关系**：B5（关联公司）依赖 B4（产业链分析）的结果，必须等 B4 全部完成后才能执行 B5。
3. **B6 可与 B4/B5 并行**：B6（综合判断）只依赖 B1（盈利）和 B2（技术指标）的数据，可以与 B4/B5 同时执行。
4. **LLM API 限制**：每批次最多分析 8 只股票，超过则分两批。
5. **输出格式**：批量模式只输出汇总对比表+推荐排序，单只股票的详细报告见模式A。
