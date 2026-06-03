"""
Multi-provider LLM-based industry chain analysis for A-share / US stocks.
Supports DeepSeek, DashScope (Qwen), and any OpenAI-compatible API.
Auto-fallback: if the primary provider fails, the next one is tried.
Config loaded from config.yaml in the skill's root directory.
"""

import os
import json
import yaml
from openai import OpenAI

# ─── Config loading ───
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_CONFIG_PATH = os.path.join(_SKILL_DIR, "config.yaml")


def _load_config() -> dict:
    """Load LLM config from config.yaml."""
    if not os.path.exists(_CONFIG_PATH):
        raise FileNotFoundError(
            f"Config file not found: {_CONFIG_PATH}\n"
            "Please create config.yaml with your DashScope API key."
        )
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_providers(cfg: dict) -> list:
    """
    Extract provider list from config, ordered by 'provider' preference.
    Returns list of (name, config_dict). First entry is the default provider.
    """
    llm = cfg.get("llm", {})
    providers = llm.get("providers")
    default = llm.get("provider", "")

    if not providers:
        # Backward-compatible: flat config with api_key at top level
        return [("default", llm)]

    ordered = []
    if default and default in providers:
        ordered.append((default, providers[default]))
    for name, pcfg in providers.items():
        if name != default:
            ordered.append((name, pcfg))
    return ordered


def _get_client_for_provider(provider_name: str, provider_cfg: dict) -> OpenAI:
    """Create an OpenAI client for a specific provider."""
    api_key = provider_cfg.get("api_key", "")
    if not api_key:
        raise ValueError(f"Missing api_key for provider '{provider_name}'")
    base_url = provider_cfg.get("base_url", "https://api.openai.com/v1")
    return OpenAI(api_key=api_key, base_url=base_url)


def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 0) -> str:
    """
    Core LLM call with multi-provider fallback.
    Tries the default provider first, then falls back to others on any error.
    """
    cfg = _load_config().get("llm", {})
    temperature = cfg.get("temperature", 0.3)
    if max_tokens <= 0:
        max_tokens = cfg.get("max_tokens", 2000)
    providers = _get_providers(_load_config())

    errors = []
    for name, pcfg in providers:
        try:
            client = _get_client_for_provider(name, pcfg)
            model = pcfg.get("model", "gpt-3.5-turbo")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            if not content or not content.strip():
                err_msg = f"{name}: returned empty content"
                errors.append(err_msg)
                continue
            if name != providers[0][0]:
                print(f"ℹ️ 主服务商不可用，已自动切换到 {name}")
            return content
        except Exception as e:
            err_msg = f"{name}: {type(e).__name__}: {e}"
            errors.append(err_msg)
            continue

    print(f"LLM API 调用失败（所有服务商均不可用）: {'; '.join(errors)}")
    return ""


def _parse_json_response(raw: str):
    """Parse JSON from LLM response, handling markdown code blocks.
    Returns parsed JSON (dict, list, etc.) or empty dict on failure."""
    import re

    if not raw:
        return {}
    text = raw.strip()

    # Strip markdown code block markers
    if text.startswith("```"):
        # Remove opening ```json / ``` line
        text = re.sub(r"^```\w*\s*\n?", "", text)
        # Remove closing ``` line
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: try to extract first JSON array or object with regex
    array_match = re.search(r"\[.*\]", text, re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass

    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    if obj_match:
        try:
            return json.loads(obj_match.group(0))
        except json.JSONDecodeError:
            pass

    return {}


# ─────────────────────────────────────────
# Step 4: Industry Chain Analysis
# ─────────────────────────────────────────

_INDUSTRY_CHAIN_SYSTEM_PROMPT = """你是一位专业的A股产业链分析师。你的任务是根据给定的上市公司信息，深入分析其在产业链中的定位、核心产品、供需逻辑和股价驱动因素。

要求：
1. 必须给出具体的产业链环节定位，不能只说"属于XX概念"
2. 核心产品/原材料必须写出具体名称（如"磷化铟"、"锗"等），不能只说"电子产品"
3. 供需分析要说明当前状态：涨价/跌价/缺货/产能过剩/产能扩张
4. 产业链逻辑链必须形成完整的因果链：终端需求变化 → 中游传导 → 上游影响
5. 股价驱动因素要用1-2句话说出根本原因

请以JSON格式输出，结构如下：
{
  "chain_position": "上游/中游/下游 - 具体环节描述",
  "core_products": ["核心产品1", "核心产品2"],
  "core_raw_materials": ["原材料1", "原材料2"],
  "supply_demand_status": "供需现状描述",
  "downstream_drivers": "下游需求驱动的具体描述",
  "logic_chain": "终端需求XX → 中游XX → 上游XX → 对公司的影响",
  "core_driver": "用1-2句话概括股价变动的根本原因"
}

只输出JSON，不要输出其他内容。"""

_INDUSTRY_CHAIN_USER_TEMPLATE = """请分析以下A股公司的产业链情况：

公司名称：{stock_name}
股票代码：{stock_code}
主营业务：{main_business}
盈利情况：{profit_status}
当前股价变动：涨跌幅 {price_change_pct}%

请深入分析该公司的产业链定位和核心驱动逻辑。"""


def analyze_industry_chain(
    stock_name: str,
    stock_code: str,
    main_business: str,
    profit_status: str,
    price_change_pct: float,
) -> dict:
    """
    Step 4: Use LLM to analyze industry chain position and core drivers.
    Returns a dict with chain analysis data, or empty dict on failure.
    """
    user_prompt = _INDUSTRY_CHAIN_USER_TEMPLATE.format(
        stock_name=stock_name,
        stock_code=stock_code,
        main_business=main_business,
        profit_status=profit_status,
        price_change_pct=price_change_pct,
    )

    raw = _call_llm(_INDUSTRY_CHAIN_SYSTEM_PROMPT, user_prompt)
    if not raw:
        print("产业链分析失败：LLM 未返回结果")
        return {}

    result = _parse_json_response(raw)
    if not result:
        print("LLM 返回非JSON格式，使用原始文本")
        result = {
            "chain_position": "",
            "core_products": [],
            "core_raw_materials": [],
            "supply_demand_status": "",
            "downstream_drivers": "",
            "logic_chain": raw,
            "core_driver": "",
        }

    print("\n======================================")
    print(f"【产业链深度分析：{stock_name}（{stock_code}）】")
    print("======================================")
    print(f"产业链定位：{result.get('chain_position', '未能获取')}")
    print(f"核心产品：{', '.join(result.get('core_products', [])) or '未能获取'}")
    print(f"核心原材料：{', '.join(result.get('core_raw_materials', [])) or '未能获取'}")
    print(f"供需现状：{result.get('supply_demand_status', '未能获取')}")
    print(f"下游需求驱动：{result.get('downstream_drivers', '未能获取')}")
    print(f"产业链逻辑链：{result.get('logic_chain', '未能获取')}")
    print(f"核心驱动因素：{result.get('core_driver', '未能获取')}")
    print("======================================\n")

    return result


# ─────────────────────────────────────────
# Step 5: Related Companies
# ─────────────────────────────────────────

_RELATED_COMPANIES_SYSTEM_PROMPT = """你是一位专业的A股市场研究员。根据给定的产业链分析结果，列出产业链上中下游各个环节的A股相关核心公司。

要求：
1. 只列出A股上市公司，提供公司名称和股票代码（6位数字）
2. 按产业链环节分组：上游原材料、中游制造、下游应用
3. 标注哪些公司是龙头或产能最大的
4. 每个环节列出3-8家公司
5. 不要对每家公司做详细分析，只列名称和代码

请以JSON格式输出：
{
  "upstream": [
    {"name": "公司名", "code": "000000", "note": "龙头/简要描述"}
  ],
  "midstream": [
    {"name": "公司名", "code": "000000", "note": "简要描述"}
  ],
  "downstream": [
    {"name": "公司名", "code": "000000", "note": "简要描述"}
  ]
}

只输出JSON，不要输出其他内容。"""

_RELATED_COMPANIES_USER_TEMPLATE = """请根据以下产业链分析，列出A股相关核心公司：

公司名称：{stock_name}（{stock_code}）
产业链定位：{chain_position}
核心产品：{core_products}
核心原材料：{core_raw_materials}
产业链逻辑：{logic_chain}

请按产业链上中下游列出A股相关公司。"""


def find_related_companies(
    stock_name: str,
    stock_code: str,
    chain_analysis: dict,
) -> dict:
    """
    Step 5: Use LLM to find related A-share companies by industry chain segment.
    Returns a dict with upstream/midstream/downstream company lists.
    """
    if not chain_analysis:
        print("产业链分析结果为空，无法查找关联公司")
        return {}

    user_prompt = _RELATED_COMPANIES_USER_TEMPLATE.format(
        stock_name=stock_name,
        stock_code=stock_code,
        chain_position=chain_analysis.get("chain_position", "未知"),
        core_products=", ".join(chain_analysis.get("core_products", [])) or "未知",
        core_raw_materials=", ".join(chain_analysis.get("core_raw_materials", [])) or "未知",
        logic_chain=chain_analysis.get("logic_chain", "未知"),
    )

    raw = _call_llm(_RELATED_COMPANIES_SYSTEM_PROMPT, user_prompt)
    if not raw:
        print("关联公司查找失败：LLM 未返回结果")
        return {}

    result = _parse_json_response(raw)
    if not result:
        print("LLM 返回非JSON格式")
        return {"raw_text": raw}

    print("\n======================================")
    print(f"【关联核心公司：{stock_name}（{stock_code}）】")
    print("======================================")
    for segment in ["upstream", "midstream", "downstream"]:
        label = {"upstream": "上游原材料", "midstream": "中游制造", "downstream": "下游应用"}[segment]
        companies = result.get(segment, [])
        if companies:
            items = []
            for c in companies:
                note = f"，{c['note']}" if c.get("note") else ""
                items.append(f"{c['name']}（{c['code']}{note}）")
            print(f"{label}：{'、'.join(items)}")
    print("======================================\n")

    return result


# ========================================================================
# 美股产业链分析函数（全球市场视角）
# ========================================================================

_INDUSTRY_CHAIN_US_SYSTEM_PROMPT = """You are a professional US stock market industry analyst. Your task is to analyze the company's position in the global industry chain, its core products/services, supply-demand dynamics, and stock price drivers.

Requirements:
1. Identify the company's specific position in the global industry chain (not just "tech stock")
2. Name specific core products/services (e.g., "iPhone", "Azure Cloud", "Model Y", "ChatGPT API")
3. Analyze current supply-demand: pricing trends, market share shifts, capacity expansion, demand recovery
4. Form a complete causal chain: end-market demand → sector impact → company-specific effect
5. Explain the stock price driver in 1-2 sentences

Output in JSON format:
{
  "chain_position": "Upstream/Midstream/Downstream - specific description",
  "core_products": ["product/service 1", "product/service 2"],
  "core_customers_or_suppliers": ["key customer/supplier 1", "key customer/supplier 2"],
  "supply_demand_status": "Supply-demand status description",
  "market_drivers": "Specific description of market demand drivers",
  "logic_chain": "End demand X → sector Y → company Z impact",
  "core_driver": "1-2 sentences on the fundamental reason for stock price movement",
  "key_risks": "Key risk factor description"
}

Output ONLY JSON, nothing else."""

_INDUSTRY_CHAIN_US_USER_TEMPLATE = """Analyze the industry chain position and core drivers for this US-listed company:

Company: {stock_name} ({ticker})
Sector: {sector}
Industry: {industry}
Business: {main_business}
EPS: {eps}
PE Ratio: {pe}
Current Price Change: {price_change_pct}%

Provide a deep analysis of the company's global industry chain position and core investment thesis."""


def analyze_industry_chain_us(
    stock_name: str,
    ticker: str,
    sector: str = "",
    industry: str = "",
    main_business: str = "",
    eps: float = 0,
    pe: float = 0,
    price_change_pct: float = 0,
) -> dict:
    """
    US stock industry chain analysis using LLM.
    Returns a dict with chain analysis data, or empty dict on failure.
    """
    user_prompt = _INDUSTRY_CHAIN_US_USER_TEMPLATE.format(
        stock_name=stock_name,
        ticker=ticker.upper(),
        sector=sector or "Unknown",
        industry=industry or "Unknown",
        main_business=main_business or f"{stock_name} is a {sector} company in the {industry} industry",
        eps=f"${eps:.2f}" if eps else "N/A",
        pe=f"{pe:.2f}" if pe else "N/A",
        price_change_pct=price_change_pct,
    )

    raw = _call_llm(_INDUSTRY_CHAIN_US_SYSTEM_PROMPT, user_prompt)
    if not raw:
        print("美股产业链分析失败：LLM 未返回结果")
        return {}

    result = _parse_json_response(raw)
    if not result:
        print("LLM 返回非JSON格式，使用原始文本")
        result = {
            "chain_position": "",
            "core_products": [],
            "core_customers_or_suppliers": [],
            "supply_demand_status": "",
            "market_drivers": "",
            "logic_chain": raw,
            "core_driver": "",
            "key_risks": "",
        }

    print("\n======================================")
    print(f"【美股产业链分析：{stock_name}（{ticker.upper()}）】")
    print("======================================")
    print(f"产业定位：{result.get('chain_position', '未能获取')}")
    print(f"核心产品/服务：{', '.join(result.get('core_products', [])) or '未能获取'}")
    print(f"关键客户/供应商：{', '.join(result.get('core_customers_or_suppliers', [])) or '未能获取'}")
    print(f"供需现状：{result.get('supply_demand_status', '未能获取')}")
    print(f"市场驱动：{result.get('market_drivers', '未能获取')}")
    print(f"产业链逻辑：{result.get('logic_chain', '未能获取')}")
    print(f"核心驱动因素：{result.get('core_driver', '未能获取')}")
    if result.get('key_risks'):
        print(f"关键风险：{result['key_risks']}")
    print("======================================\n")

    return result


# ─────────────────────────────────────────
# US Stock Related Companies
# ─────────────────────────────────────────

_RELATED_COMPANIES_US_SYSTEM_PROMPT = """You are a US stock market research analyst. Based on the industry chain analysis, list related US-listed companies in the same sector or adjacent segments.

Requirements:
1. List ONLY companies listed on US exchanges (NYSE, NASDAQ)
2. Provide company name and ticker symbol
3. Group by industry segment: direct competitors, upstream suppliers, downstream customers
4. Mark which are industry leaders or largest by market cap
5. List 3-8 companies per segment
6. Do NOT provide detailed analysis of each company

Output in JSON format:
{
  "competitors": [
    {"name": "Company Name", "ticker": "AAPL", "note": "Market leader/description"}
  ],
  "suppliers": [
    {"name": "Company Name", "ticker": "QCOM", "note": "Key supplier description"}
  ],
  "customers_or_partners": [
    {"name": "Company Name", "ticker": "MSFT", "note": "Customer/partner description"}
  ]
}

Output ONLY JSON, nothing else."""

_RELATED_COMPANIES_US_USER_TEMPLATE = """Based on the following industry chain analysis, list related US-listed companies:

Company: {stock_name} ({ticker})
Industry Chain Position: {chain_position}
Core Products/Services: {core_products}
Key Suppliers/Customers: {core_customers}
Market Logic: {logic_chain}

List direct competitors, upstream suppliers, and downstream customers/partners."""


def find_related_companies_us(
    stock_name: str,
    ticker: str,
    chain_analysis: dict,
) -> dict:
    """
    Find related US-listed companies based on industry chain analysis.
    Returns a dict with competitors/suppliers/customers company lists.
    """
    if not chain_analysis:
        print("美股产业链分析结果为空，无法查找关联公司")
        return {}

    user_prompt = _RELATED_COMPANIES_US_USER_TEMPLATE.format(
        stock_name=stock_name,
        ticker=ticker,
        chain_position=chain_analysis.get("chain_position", "Unknown"),
        core_products=", ".join(chain_analysis.get("core_products", [])) or "Unknown",
        core_customers=", ".join(chain_analysis.get("core_customers_or_suppliers", [])) or "Unknown",
        logic_chain=chain_analysis.get("logic_chain", "Unknown"),
    )

    raw = _call_llm(_RELATED_COMPANIES_US_SYSTEM_PROMPT, user_prompt)
    if not raw:
        print("美股关联公司查找失败：LLM 未返回结果")
        return {}

    result = _parse_json_response(raw)
    if not result:
        print("LLM 返回非JSON格式")
        return {"raw_text": raw}

    print("\n======================================")
    print(f"【美股关联公司：{stock_name}（{ticker.upper()}）】")
    print("======================================")
    for segment in ["competitors", "suppliers", "customers_or_partners"]:
        label = {
            "competitors": "直接竞争对手",
            "suppliers": "上游供应商",
            "customers_or_partners": "下游客户/合作伙伴",
        }[segment]
        companies = result.get(segment, [])
        if companies:
            items = []
            for c in companies:
                note = f"，{c['note']}" if c.get("note") else ""
                items.append(f"{c['name']}（{c['ticker']}{note}）")
            print(f"{label}：{'、'.join(items)}")
    print("======================================\n")

    return result


if __name__ == "__main__":
    # Quick test with 云南锗业
    result = analyze_industry_chain(
        stock_name="云南锗业",
        stock_code="002428",
        main_business="锗及其他相关有色金属的采选、冶炼和深加工",
        profit_status="2024年前三季度归母净利润约1.2亿元，同比增长约280%",
        price_change_pct=5.2,
    )
    if result:
        find_related_companies("云南锗业", "002428", result)
