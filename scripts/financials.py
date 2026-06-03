"""
极简财务指标分析 — 财报健康度体检。

覆盖 6 大指标（来自 financial.md）：
  1. FCF/净利润 — 利润含金量
  2. 扣非净利润/净利润 — 利润来源是否靠主业
  3. 市净率(PB) — 是否破净
  4. 净利率 — 赚钱效率
  5. 营收同比增长率 — 成长性
  6. 净利润同比增长率 — 盈利成长性

数据源：
  A 股：东方财富数据中心 API（利润表 + 现金流表 + 资产负债表）
  美股：yfinance

用法：
  python3 financials.py 600519          # A股
  python3 financials.py AAPL            # 美股
"""

import os
import sys
import json
import math
import requests
from datetime import datetime, timedelta

# ─── Safe conversions ─────────────────────────────────────────

def _safe_float(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(val) -> int:
    if val is None:
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


# ═══════════════════════════════════════════════════════════════
#  A-Share Data Fetching (East Money API)
# ═══════════════════════════════════════════════════════════════

_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
}

_EM_BASE = "https://datacenter.eastmoney.com/securities/api/data/v1/get"


def _fetch_em_report(report_name: str, symbol: str, columns: str,
                     page_size: int = 10) -> list:
    """Fetch financial report data from East Money data center."""
    params = {
        "reportName": report_name,
        "columns": columns,
        "filter": f'(SECURITY_CODE="{symbol}")',
        "pageNumber": 1,
        "pageSize": page_size,
        "sortTypes": -1,
        "sortColumns": "REPORT_DATE",
        "source": "WEB",
        "client": "WEB",
    }
    try:
        resp = requests.get(_EM_BASE, params=params, headers=_EM_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success") and data.get("result"):
            return data["result"].get("data") or []
        return []
    except Exception as e:
        print(f"  东方财富 API 请求失败 ({report_name}): {e}")
        return []


def _get_a_share_financials(symbol: str) -> dict:
    """
    Fetch all financial data for an A-share stock.
    Returns raw data dict from 3 statements.
    """
    # ── Income Statement ──
    income_cols = ("SECURITY_CODE,SECURITY_NAME_ABBR,NOTICE_DATE,REPORT_DATE,"
                   "TOTAL_OPERATE_INCOME,PARENT_NETPROFIT,DEDUCT_PARENT_NETPROFIT,"
                   "OPERATE_PROFIT,TOTAL_PROFIT")
    income_data = _fetch_em_report("RPT_DMSK_FN_INCOME", symbol, income_cols, page_size=20)

    # ── Cash Flow Statement ──
    cashflow_cols = ("SECURITY_CODE,NOTICE_DATE,REPORT_DATE,"
                     "NETCASH_OPERATE,CONSTRUCT_LONG_ASSET")
    cashflow_data = _fetch_em_report("RPT_DMSK_FN_CASHFLOW", symbol, cashflow_cols, page_size=20)

    # ── Balance Sheet ──
    balance_cols = ("SECURITY_CODE,NOTICE_DATE,REPORT_DATE,"
                    "TOTAL_ASSETS,TOTAL_LIABILITIES,TOTAL_EQUITY")
    balance_data = _fetch_em_report("RPT_DMSK_FN_BALANCE", symbol, balance_cols, page_size=20)

    name = ""
    if income_data:
        name = income_data[0].get("SECURITY_NAME_ABBR", "")

    return {
        "symbol": symbol,
        "name": name,
        "income": income_data,
        "cashflow": cashflow_data,
        "balance": balance_data,
    }


def _match_report(data_list: list, date_str: str) -> dict:
    """Find a specific report by REPORT_DATE."""
    for d in data_list:
        rd = str(d.get("REPORT_DATE", ""))
        if rd.startswith(date_str):
            return d
    return {}


def _find_prior_year(report_date: str) -> str:
    """Given a report date like '2025-12-31', return prior year '2024-12-31'."""
    try:
        dt = datetime.strptime(report_date[:10], "%Y-%m-%d")
        prior = dt.replace(year=dt.year - 1)
        return prior.strftime("%Y-%m-%d")
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════
#  US Stock Data Fetching (yfinance)
# ═══════════════════════════════════════════════════════════════

def _get_us_financials(ticker: str) -> dict:
    """Fetch financial data for a US stock via yfinance."""
    try:
        import yfinance as yf
        import numpy as np

        stock = yf.Ticker(ticker.upper())
        info = stock.info

        # Income statement (annual)
        income_stmt = stock.financials  # cols = dates, rows = items
        cf_stmt = stock.cashflow
        balance = stock.balance_sheet

        def _get_latest_row(df, keyword: str):
            """Get the value from the row whose index contains keyword."""
            if df is None or df.empty:
                return 0.0
            for idx in df.index:
                if keyword.lower() in str(idx).lower():
                    row = df.loc[idx]
                    if len(row) > 0:
                        return _safe_float(row.iloc[0])
            return 0.0

        def _get_comparison(df, keyword: str):
            """Get latest and prior year values."""
            if df is None or df.empty:
                return 0.0, 0.0
            for idx in df.index:
                if keyword.lower() in str(idx).lower():
                    row = df.loc[idx]
                    vals = [_safe_float(v) for v in row.values if _safe_float(v) != 0]
                    if len(vals) >= 2:
                        return vals[0], vals[1]
                    elif len(vals) == 1:
                        return vals[0], 0.0
            return 0.0, 0.0

        net_income, net_income_prior = _get_comparison(income_stmt, "Net Income")
        revenue, revenue_prior = _get_comparison(income_stmt, "Total Revenue")
        operating_cf = _get_latest_row(cf_stmt, "Operating Cash Flow")
        capex = _get_latest_row(cf_stmt, "Capital Expenditure")
        total_assets = _get_latest_row(balance, "Total Assets")
        total_liabilities = _get_latest_row(balance, "Total Liabilities")
        total_equity = _get_latest_row(balance, "Total Equity")
        # US stocks: use Net Income (no 扣非 equivalent in standard yfinance)
        eps = _safe_float(info.get("trailingEps"))
        book_value = _safe_float(info.get("bookValue"))
        price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
        shares = _safe_float(info.get("sharesOutstanding"))
        name = info.get("longName") or info.get("shortName", ticker)

        return {
            "symbol": ticker.upper(),
            "name": name,
            "market": "US",
            "price": price,
            "revenue": revenue,
            "revenue_prior": revenue_prior,
            "net_profit": net_income,
            "net_profit_prior": net_income_prior,
            "deducted_np": net_income,  # no 扣非 equivalent
            "operating_cf": operating_cf,
            "capex": abs(capex),  # capex is negative in yfinance
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            "eps": eps,
            "bvps": book_value,
            "report_date": "",
            "has_deducted": False,  # US stocks don't have 扣非
        }
    except Exception as e:
        print(f"  yfinance 数据获取失败: {e}")
        return {"symbol": ticker.upper(), "name": ticker, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
#  A-Share: Extract & Calculate Indicators
# ═══════════════════════════════════════════════════════════════

def _build_a_share_indicators(raw: dict) -> dict:
    """
    From raw East Money data, extract the latest annual and latest quarterly
    figures, then calculate the 6 indicators.
    """
    income = raw.get("income", [])
    cashflow = raw.get("cashflow", [])
    balance = raw.get("balance", [])

    if not income:
        return {"error": "无法获取利润表数据"}

    # Separate annual (12-31) and quarterly reports
    annual_income = [d for d in income if "-12-31" in str(d.get("REPORT_DATE", ""))]
    annual_cf = [d for d in cashflow if "-12-31" in str(d.get("REPORT_DATE", ""))]
    annual_balance = [d for d in balance if "-12-31" in str(d.get("REPORT_DATE", ""))]

    if not annual_income:
        return {"error": "未找到年报数据"}

    latest = annual_income[0]
    report_date = str(latest.get("REPORT_DATE", ""))[:10]
    prior_date = _find_prior_year(report_date)

    # Income statement data
    revenue = _safe_float(latest.get("TOTAL_OPERATE_INCOME"))
    net_profit = _safe_float(latest.get("PARENT_NETPROFIT"))
    deducted_np = _safe_float(latest.get("DEDUCT_PARENT_NETPROFIT"))
    operate_profit = _safe_float(latest.get("OPERATE_PROFIT"))

    # Prior year data for YoY
    prior_income = _match_report(annual_income, prior_date)
    revenue_prior = _safe_float(prior_income.get("TOTAL_OPERATE_INCOME"))
    net_profit_prior = _safe_float(prior_income.get("PARENT_NETPROFIT"))

    # Cash flow data
    latest_cf = _match_report(annual_cf, report_date) if annual_cf else {}
    operating_cf = _safe_float(latest_cf.get("NETCASH_OPERATE"))
    capex = abs(_safe_float(latest_cf.get("CONSTRUCT_LONG_ASSET")))

    # Balance sheet data
    latest_bs = _match_report(annual_balance, report_date) if annual_balance else {}
    total_assets = _safe_float(latest_bs.get("TOTAL_ASSETS"))
    total_liabilities = _safe_float(latest_bs.get("TOTAL_LIABILITIES"))
    total_equity = _safe_float(latest_bs.get("TOTAL_EQUITY"))

    # Also get latest quarterly data for more timely view
    quarterly_income = income[0]  # most recent, could be Q1/Q2/Q3/annual
    q_revenue = _safe_float(quarterly_income.get("TOTAL_OPERATE_INCOME"))
    q_net_profit = _safe_float(quarterly_income.get("PARENT_NETPROFIT"))
    q_deducted_np = _safe_float(quarterly_income.get("DEDUCT_PARENT_NETPROFIT"))
    q_report_date = str(quarterly_income.get("REPORT_DATE", ""))[:10]

    return {
        "symbol": raw["symbol"],
        "name": raw["name"],
        "market": "A",
        "report_date": report_date,
        "q_report_date": q_report_date,
        "revenue": revenue,
        "revenue_prior": revenue_prior,
        "net_profit": net_profit,
        "net_profit_prior": net_profit_prior,
        "deducted_np": deducted_np,
        "operating_cf": operating_cf,
        "capex": capex,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "q_revenue": q_revenue,
        "q_net_profit": q_net_profit,
        "q_deducted_np": q_deducted_np,
        "has_deducted": True,
    }


# ═══════════════════════════════════════════════════════════════
#  Core: Apply the 6 Indicators
# ═══════════════════════════════════════════════════════════════

def analyze_financial_health(data: dict, price: float = None) -> dict:
    """
    Apply the 6 极简财务指标 to judge financial health.

    Args:
        data: dict from _build_a_share_indicators() or _get_us_financials()
        price: current stock price (optional, for PB). If None, uses data.get('price')

    Returns:
        dict with indicators, scores, and overall verdict
    """
    results = {
        "symbol": data.get("symbol", ""),
        "name": data.get("name", ""),
        "market": data.get("market", ""),
        "report_date": data.get("report_date", ""),
        "indicators": [],
        "score": 0,
        "max_score": 6,
        "verdict": "",
    }

    rev = data.get("revenue", 0)
    rev_prior = data.get("revenue_prior", 0)
    np_net = data.get("net_profit", 0)
    np_prior = data.get("net_profit_prior", 0)
    deducted = data.get("deducted_np", 0)
    ocf = data.get("operating_cf", 0)
    capex = data.get("capex", 0)
    total_equity = data.get("total_equity", 0)
    total_assets = data.get("total_assets", 0)
    total_liab = data.get("total_liabilities", 0)
    has_deducted = data.get("has_deducted", True)

    # ── Indicator 1: FCF / Net Profit ──
    fcf = ocf - capex  # simplified FCF
    if np_net > 0:
        fcf_ratio = round(fcf / np_net, 2)
    elif np_net < 0:
        fcf_ratio = None  # 亏损公司无意义
    else:
        fcf_ratio = 0

    if fcf_ratio is None:
        i1_grade = "N/A"
        i1_verdict = "亏损，不适用"
        i1_score = 0
    elif fcf_ratio >= 1.0:
        i1_grade = "优秀"
        i1_verdict = "利润含金量高，赚的是真金白银"
        i1_score = 2
    elif fcf_ratio >= 0.75:
        i1_grade = "良好"
        i1_verdict = "利润含金量较好"
        i1_score = 2
    else:
        i1_grade = "差"
        i1_verdict = "利润含金量不足，警惕应收账款堆积或假账风险"
        i1_score = 0

    results["indicators"].append({
        "name": "FCF/净利润",
        "value": f"{fcf_ratio:.2f}" if fcf_ratio is not None else "N/A",
        "detail": f"FCF≈{fcf/1e8:.1f}亿 (OCF {ocf/1e8:.1f}亿 - CAPEX {capex/1e8:.1f}亿)",
        "rule": ">1 优秀 | 0.75-1 良好 | <0.75 差",
        "grade": i1_grade,
        "verdict": i1_verdict,
        "score": i1_score,
    })

    # ── Indicator 2: 扣非净利润 / 净利润 ──
    if has_deducted and np_net != 0 and deducted != 0:
        deducted_ratio = round(deducted / np_net, 2)
    elif np_net <= 0:
        deducted_ratio = None
    else:
        deducted_ratio = None

    if deducted_ratio is None:
        i2_grade = "N/A"
        i2_verdict = "亏损或无扣非数据，不适用"
        i2_score = 0
    elif deducted_ratio >= 0.8:
        i2_grade = "优秀"
        i2_verdict = "利润主要来自主营业务，靠真本事赚钱"
        i2_score = 2
    elif deducted_ratio >= 0.5:
        i2_grade = "良好"
        i2_verdict = "主业贡献大部分利润，但有非经常性收入"
        i2_score = 2
    elif deducted_ratio >= 0:
        i2_grade = "差"
        i2_verdict = "利润主要靠非经常性损益（卖资产/补贴/投资收益），不可持续"
        i2_score = 0
    else:
        i2_grade = "极差"
        i2_verdict = "扣非净利润为负，主业实际亏损！当前净利润靠非经常性收益粉饰"
        i2_score = 0

    results["indicators"].append({
        "name": "扣非净利润/净利润",
        "value": f"{deducted_ratio:.2f}" if deducted_ratio is not None else "N/A",
        "detail": f"扣非={deducted/1e8:.1f}亿 / 净利={np_net/1e8:.1f}亿",
        "rule": ">0.8 优秀 | 0.5-0.8 良好 | <0.5 差",
        "grade": i2_grade,
        "verdict": i2_verdict,
        "score": i2_score,
    })

    # ── Indicator 3: 市净率 (PB) ──
    if price is None:
        price = data.get("price", 0)

    if total_equity > 0 and price > 0:
        # For A-shares, we need total shares to compute BVPS
        # Use the more accessible approach: check balance sheet BVPS
        # If we don't have shares outstanding, try a different approach
        pass

    # PB judgment - try multiple approaches
    pb = None
    pb_grade = "N/A"
    pb_verdict = ""
    pb_score = 0

    # Try using total equity from balance + price from market data
    if price > 0 and total_equity > 0:
        # Get shares from market data (try stock.py helper)
        try:
            _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, _SCRIPT_DIR)
            from stock import _get_quote_data
            parts = _get_quote_data(data["symbol"])
            if parts:
                # Field 45 = total market value, field 44 = market cap in 亿
                # Field 46 = PB ratio direct from market
                try:
                    pb = float(parts[46]) if len(parts) > 46 and parts[46] else None
                except (ValueError, IndexError):
                    pass
        except Exception:
            pass

    if pb is not None and pb > 0:
        if pb < 1.0:
            pb_grade = "破净"
            pb_verdict = "股价低于每股净资产，市场极度悲观或公司资产质量差"
            pb_score = 0
        elif pb < 2.0:
            pb_grade = "合理偏低"
            pb_verdict = "股价略高于净资产"
            pb_score = 2
        elif pb < 5.0:
            pb_grade = "中等"
            pb_verdict = "股价显著高于净资产，需结合ROE判断是否合理"
            pb_score = 1
        else:
            pb_grade = "偏高"
            pb_verdict = "PB极高，轻资产或高ROE公司常态，需验证是否可持续"
            pb_score = 1
    else:
        pb_grade = "N/A"
        pb_verdict = "无法获取PB数据"
        pb_score = 0

    results["indicators"].append({
        "name": "市净率(PB)",
        "value": f"{pb:.2f}" if pb else "N/A",
        "detail": "股价是否破净" if pb and pb < 1 else ("PB合理" if pb and pb < 5 else "PB偏高"),
        "rule": ">1 股价高于净资产 | <1 破净",
        "grade": pb_grade,
        "verdict": pb_verdict,
        "score": pb_score,
    })

    # ── Indicator 4: 净利率 ──
    if rev > 0:
        net_margin = round(np_net / rev * 100, 1)
    else:
        net_margin = None

    if net_margin is None:
        i4_grade = "N/A"
        i4_verdict = "营收为0，不适用"
        i4_score = 0
    elif net_margin >= 15:
        i4_grade = "优秀"
        i4_verdict = "赚钱效率高，有较强定价权或成本优势"
        i4_score = 2
    elif net_margin >= 5:
        i4_grade = "一般"
        i4_verdict = "赚钱效率中等"
        i4_score = 1
    else:
        i4_grade = "差"
        i4_verdict = "赚钱效率低，可能是低利润率行业或竞争处于劣势"
        i4_score = 0

    results["indicators"].append({
        "name": "净利率",
        "value": f"{net_margin:.1f}%" if net_margin is not None else "N/A",
        "detail": f"净利={np_net/1e8:.1f}亿 / 营收={rev/1e8:.1f}亿",
        "rule": ">15% 优秀 | 5-15% 一般 | <5% 差",
        "grade": i4_grade,
        "verdict": i4_verdict,
        "score": i4_score,
    })

    # ── Indicator 5: 营收同比增长率 ──
    if rev_prior > 0:
        rev_yoy = round((rev - rev_prior) / rev_prior * 100, 1)
    else:
        rev_yoy = None

    if rev_yoy is None:
        i5_grade = "N/A"
        i5_verdict = "无法计算同比"
        i5_score = 0
    elif rev_yoy > 10:
        i5_grade = "增长好"
        i5_verdict = "营收保持双位数增长，业务在扩张"
        i5_score = 2
    elif rev_yoy >= 0:
        i5_grade = "低速"
        i5_verdict = "营收微增，增长动力不足"
        i5_score = 1
    else:
        i5_grade = "衰退"
        i5_verdict = "营收同比下滑，业务可能萎缩或面临竞争压力"
        i5_score = 0

    results["indicators"].append({
        "name": "营收同比增长率",
        "value": f"{rev_yoy:+.1f}%" if rev_yoy is not None else "N/A",
        "detail": f"本期={rev/1e8:.1f}亿 / 上期={rev_prior/1e8:.1f}亿",
        "rule": ">10% 增长好 | 0-10% 低速 | <0% 衰退",
        "grade": i5_grade,
        "verdict": i5_verdict,
        "score": i5_score,
    })

    # ── Indicator 6: 净利润同比增长率 ──
    if np_prior > 0:
        np_yoy = round((np_net - np_prior) / abs(np_prior) * 100, 1)
    elif np_prior < 0:
        # Prior year was loss, current year profit → huge growth
        if np_net > 0:
            np_yoy = float("inf")
        else:
            np_yoy = round((np_net - np_prior) / abs(np_prior) * 100, 1)
    else:
        np_yoy = None

    if np_yoy is None:
        i6_grade = "N/A"
        i6_verdict = "无法计算同比"
        i6_score = 0
    elif np_yoy == float("inf"):
        i6_grade = "扭亏"
        i6_verdict = "上期亏损本期盈利，大幅好转"
        i6_score = 2
    elif np_yoy > 10:
        i6_grade = "优秀"
        i6_verdict = "净利润保持双位数增长，盈利能力在增强"
        i6_score = 2
    elif np_yoy >= 0:
        i6_grade = "一般"
        i6_verdict = "净利润微增，盈利能力改善有限"
        i6_score = 1
    else:
        i6_grade = "变差"
        i6_verdict = "净利润同比下滑，盈利能力在弱化"
        i6_score = 0

    yoy_display = "扭亏为盈" if np_yoy == float("inf") else f"{np_yoy:+.1f}%" if np_yoy is not None else "N/A"

    results["indicators"].append({
        "name": "净利润同比增长率",
        "value": yoy_display,
        "detail": f"本期={np_net/1e8:.1f}亿 / 上期={np_prior/1e8:.1f}亿",
        "rule": ">10% 优秀 | 0-10% 一般 | <0% 变差",
        "grade": i6_grade,
        "verdict": i6_verdict,
        "score": i6_score,
    })

    # ── Summary ──
    total_score = sum(ind["score"] for ind in results["indicators"])
    max_possible = sum(2 for ind in results["indicators"] if ind["grade"] != "N/A")
    results["score"] = total_score
    results["max_score"] = max(1, max_possible)  # avoid divide by zero

    score_pct = total_score / results["max_score"] * 100 if results["max_score"] > 0 else 0
    if score_pct >= 80:
        results["verdict"] = "🟢 健康 — 财报质量好，核心指标优秀"
    elif score_pct >= 50:
        results["verdict"] = "🟡 一般 — 部分指标有瑕疵，需关注具体弱项"
    else:
        results["verdict"] = "🔴 警惕 — 多项指标显示财报质量较差"

    return results


# ═══════════════════════════════════════════════════════════════
#  Output Formatting
# ═══════════════════════════════════════════════════════════════

def print_health_report(results: dict):
    """Print the formatted financial health report."""
    indicators = results.get("indicators", [])
    name = results.get("name", "")
    symbol = results.get("symbol", "")
    market = results.get("market", "")
    report_date = results.get("report_date", "")

    print(f"\n{'='*65}")
    print(f"【极简财报体检：{name}（{symbol}）】")
    if report_date:
        print(f"  数据截止：{report_date}")
    print(f"{'='*65}")

    print(f"\n{'指标':<22} {'数值':>10} {'评级':<10} {'得分':<5}")
    print(f"{'-'*22} {'-'*10} {'-'*10} {'-'*5}")

    for ind in indicators:
        name = ind["name"]
        value = ind["value"]
        grade = ind["grade"]
        score = ind["score"]
        print(f"{name:<22} {value:>10} {grade:<10} {score}/2")

    # Summary line
    total = results.get("score", 0)
    max_s = results.get("max_score", 6)
    print(f"{'-'*22} {'-'*10} {'-'*10} {'-'*5}")
    print(f"{'合计':<22} {'':>10} {'':<10} {total}/{max_s}")

    print(f"\n📋 详细解读：")
    for ind in indicators:
        icon = "✅" if ind["score"] == 2 else ("⚠️" if ind["score"] == 1 else "❌")
        if ind["grade"] == "N/A":
            icon = "⬜"
        print(f"  {icon} {ind['name']}：{ind['verdict']}")
        if ind["detail"]:
            print(f"     └─ {ind['detail']}（标准：{ind['rule']}）")

    print(f"\n{'='*65}")
    print(f"综合评分：{total}/{max_s} → {results.get('verdict', '')}")
    print(f"{'='*65}\n")


def run_financial_health_check(symbol: str, price: float = None) -> dict:
    """
    Main entry point: automatically detects A-share vs US, fetches data,
    calculates indicators, and returns results dict.
    """
    is_us = any(c.isalpha() for c in symbol)

    if is_us:
        print(f"  获取 {symbol.upper()} 美股财报数据 ...")
        raw = _get_us_financials(symbol)
        if raw.get("error"):
            return {"error": raw["error"]}
        data = raw  # already in indicator-ready format
    else:
        print(f"  获取 {symbol} A股财报数据 ...")
        raw = _get_a_share_financials(symbol)
        if raw.get("error"):
            return {"error": raw["error"]}
        if not raw.get("income"):
            return {"error": "未获取到利润表数据"}

        # Get market price for PB
        if price is None:
            try:
                _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
                sys.path.insert(0, _SCRIPT_DIR)
                from stock import _get_quote_data
                parts = _get_quote_data(symbol)
                if parts:
                    price = _safe_float(parts[3])
            except Exception:
                pass
        data = _build_a_share_indicators(raw)
        if data.get("error"):
            return {"error": data["error"]}
        data["price"] = price

    # Count valid data points
    has_data = data.get("revenue", 0) > 0 or data.get("net_profit", 0) != 0
    if not has_data:
        return {"error": "财务数据为空，请检查股票代码是否正确"}

    results = analyze_financial_health(data, price)
    return results


# ═══════════════════════════════════════════════════════════════
#  CLI Entry Point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：")
        print("  python3 financials.py 600519     # A股")
        print("  python3 financials.py AAPL       # 美股")
        sys.exit(1)

    symbol = sys.argv[1].strip()
    results = run_financial_health_check(symbol)

    if results.get("error"):
        print(f"❌ 错误：{results['error']}")
        sys.exit(1)

    print_health_report(results)
    print("\n--- JSON ---")
    print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
