"""
Valuation Model Analysis for financial-assistant skill.

Provides 7 valuation models:
  A-share & US: P/E Multiple, P/B Multiple, Graham Number, PEG, DDM
  US only: EV/EBITDA, DCF Framework

All functions print results to stdout AND return JSON-compatible dicts.

Usage:
  python3 valuation.py US AAPL
  python3 valuation.py A 600519  # requires EPS/BVPS from WebSearch
"""

import os
import json
import math
import yfinance as yf
import numpy as np

# ─── Safe type conversions ────────────────────────────────────

def _safe_float(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _safe_bool(val) -> bool:
    return bool(val)


# ─── Reference data loading ───────────────────────────────────

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_REF_PATH = os.path.join(_SKILL_DIR, "valuation_reference.yaml")


def _load_valuation_ref() -> dict:
    """Load valuation reference data from yaml config."""
    try:
        import yaml
        if os.path.exists(_REF_PATH):
            with open(_REF_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    except Exception:
        pass
    return {}


def get_industry_pe(sector: str, is_us: bool = False) -> float:
    """
    Get reference industry P/E multiple.
    Falls back to broad market average (A: 25, US: 20) if sector not found.
    """
    ref = _load_valuation_ref()
    key = "us_sectors" if is_us else "a_share_sectors"
    sectors = ref.get(key, {})
    pe = sectors.get(sector, {}).get("pe", 0)
    if pe > 0:
        return pe
    return 20.0 if is_us else 25.0


def get_industry_ev_ebitda(sector: str) -> float:
    """Get reference industry EV/EBITDA multiple for US sectors."""
    ref = _load_valuation_ref()
    sectors = ref.get("us_sectors", {})
    mult = sectors.get(sector, {}).get("ev_ebitda", 0)
    if mult > 0:
        return mult
    # Broad defaults by sector type
    broad_defaults = {
        "Technology": 18.0, "Consumer Cyclical": 12.0, "Financial Services": 10.0,
        "Healthcare": 15.0, "Industrials": 13.0, "Energy": 7.0,
        "Basic Materials": 8.0, "Real Estate": 20.0, "Utilities": 12.0,
        "Communication Services": 10.0, "Consumer Defensive": 14.0,
    }
    return broad_defaults.get(sector, 12.0)


def get_default_wacc(sector: str) -> float:
    """Get default WACC for a US sector."""
    ref = _load_valuation_ref()
    sectors = ref.get("us_sectors", {})
    wacc = sectors.get(sector, {}).get("wacc", 0)
    if wacc > 0:
        return wacc
    return 0.10  # default 10%


# ═══════════════════════════════════════════════════════════════
#  A-Share Valuation Models
# ═══════════════════════════════════════════════════════════════

def pe_valuation_a(eps: float, current_pe: float, industry_pe: float = None,
                    historical_pe: float = None) -> dict:
    """
    P/E multiple valuation for A-shares.
    Fair price = EPS × appropriate P/E multiple.

    Uses 3 scenarios: conservative, base, optimistic.
    """
    if eps <= 0:
        return {"available": False, "reason": "EPS <= 0，无法使用 P/E 估值"}

    if industry_pe is None:
        industry_pe = 25.0
    if historical_pe is None:
        historical_pe = industry_pe

    # Conservative: use lower of industry and historical, minus 20% safety margin
    base_pe = min(industry_pe, historical_pe)
    conservative_pe = round(base_pe * 0.80, 1)
    optimistic_pe = round(base_pe * 1.20, 1)

    fair_conservative = round(eps * conservative_pe, 2)
    fair_base = round(eps * base_pe, 2)
    fair_optimistic = round(eps * optimistic_pe, 2)

    return {
        "available": True,
        "model": "P/E 倍数法",
        "eps": round(eps, 2),
        "current_pe": round(current_pe, 1) if current_pe else None,
        "industry_pe": round(industry_pe, 1),
        "historical_pe": round(historical_pe, 1),
        "conservative": {"pe": conservative_pe, "price": fair_conservative},
        "base": {"pe": base_pe, "price": fair_base},
        "optimistic": {"pe": optimistic_pe, "price": fair_optimistic},
        "range": [fair_conservative, fair_optimistic],
    }


def pb_valuation_a(bvps: float, current_pb: float, industry_pb: float = None) -> dict:
    """
    P/B multiple valuation for A-shares.
    Fair price = BVPS × appropriate P/B multiple.
    """
    if bvps <= 0:
        return {"available": False, "reason": "BVPS <= 0，无法使用 P/B 估值"}

    if industry_pb is None:
        # Rough industry P/B defaults
        industry_pb = 3.0 if bvps > 20 else 2.0

    conservative_pb = round(industry_pb * 0.75, 1)
    optimistic_pb = round(industry_pb * 1.25, 1)

    return {
        "available": True,
        "model": "P/B 倍数法",
        "bvps": round(bvps, 2),
        "current_pb": round(current_pb, 1) if current_pb else None,
        "industry_pb": round(industry_pb, 1),
        "conservative": {"pb": conservative_pb, "price": round(bvps * conservative_pb, 2)},
        "base": {"pb": industry_pb, "price": round(bvps * industry_pb, 2)},
        "optimistic": {"pb": optimistic_pb, "price": round(bvps * optimistic_pb, 2)},
        "range": [round(bvps * conservative_pb, 2), round(bvps * optimistic_pb, 2)],
    }


def graham_number_a(eps: float, bvps: float) -> dict:
    """
    Benjamin Graham Number: √(22.5 × EPS × BVPS)
    Based on max P/E of 15 and max P/B of 1.5.
    """
    if eps <= 0 or bvps <= 0:
        return {"available": False, "reason": "EPS 或 BVPS <= 0，无法计算格雷厄姆数"}

    gn = round(math.sqrt(22.5 * eps * bvps), 2)

    return {
        "available": True,
        "model": "格雷厄姆数",
        "formula": "√(22.5 × EPS × BVPS)",
        "eps": round(eps, 2),
        "bvps": round(bvps, 2),
        "graham_number": gn,
    }


def peg_valuation_a(eps: float, growth_rate: float) -> dict:
    """
    PEG-based fair valuation (Peter Lynch).
    Fair P/E = earnings growth rate (in %).
    Fair price = EPS × growth rate.

    growth_rate: percentage like 15.0 for 15%
    """
    if eps <= 0:
        return {"available": False, "reason": "EPS <= 0，无法使用 PEG 估值"}
    if growth_rate is None or growth_rate <= 0:
        return {"available": False, "reason": "增长率数据缺失或为负"}

    fair_pe = growth_rate
    fair_price = round(eps * fair_pe, 2)

    # PEG ranges: 0.8x growth (conservative) to 1.2x growth (optimistic)
    peg_conservative = round(eps * growth_rate * 0.8, 2)
    peg_optimistic = round(eps * growth_rate * 1.2, 2)

    return {
        "available": True,
        "model": "PEG 估值",
        "eps": round(eps, 2),
        "growth_rate_pct": round(growth_rate, 1),
        "fair_pe": round(fair_pe, 1),
        "fair_price": fair_price,
        "range": [peg_conservative, peg_optimistic],
    }


def ddm_valuation_a(dps: float, growth_rate: float = 0.03,
                     required_return: float = 0.10) -> dict:
    """
    Gordon Growth Dividend Discount Model.
    Fair price = DPS × (1+g) / (r-g)

    dps: annual dividend per share
    growth_rate: perpetual growth rate (default 3%)
    required_return: required rate of return (default 10%)
    """
    if dps <= 0:
        return {"available": False, "reason": "无股息或 DPS <= 0"}
    if growth_rate >= required_return:
        return {"available": False, "reason": f"增长率({growth_rate:.1%}) >= 要求回报率({required_return:.1%})"}

    fair_price = round(dps * (1 + growth_rate) / (required_return - growth_rate), 2)

    # Sensitivity: ±1% growth rate
    low_price = round(dps * (1 + growth_rate - 0.01) / (required_return - growth_rate + 0.01), 2)
    high_price = round(dps * (1 + growth_rate + 0.01) / (required_return - growth_rate - 0.01), 2)

    return {
        "available": True,
        "model": "股息贴现模型 (DDM)",
        "dps": round(dps, 2),
        "growth_rate": round(growth_rate * 100, 1),
        "required_return": round(required_return * 100, 1),
        "fair_price": fair_price,
        "range": [low_price, high_price],
    }


def comprehensive_valuation_a(symbol: str, name: str = "",
                               eps: float = None, bvps: float = None,
                               growth_rate: float = None, dps: float = None,
                               current_pe: float = None, current_pb: float = None,
                               industry_pe: float = None, industry_pb: float = None,
                               current_price: float = None,
                               profit: bool = True) -> dict:
    """
    Run all applicable A-share valuation models.
    Returns composite results with models list and summary.
    """
    results = {"symbol": symbol, "name": name, "models": [], "summary": {}}

    if not profit:
        results["summary"] = {"rating": "不适用", "reason": "公司亏损，估值模型不可靠"}
        return results

    # 1. P/E Multiple
    if eps and eps > 0:
        m = pe_valuation_a(eps, current_pe or 0, industry_pe)
        results["models"].append(m)

    # 2. P/B Multiple
    if bvps and bvps > 0:
        m = pb_valuation_a(bvps, current_pb or 0, industry_pb)
        results["models"].append(m)

    # 3. Graham Number
    if eps and eps > 0 and bvps and bvps > 0:
        m = graham_number_a(eps, bvps)
        results["models"].append(m)

    # 4. PEG
    if eps and eps > 0 and growth_rate and growth_rate > 0:
        m = peg_valuation_a(eps, growth_rate)
        results["models"].append(m)

    # 5. DDM
    if dps and dps > 0:
        m = ddm_valuation_a(dps)
        results["models"].append(m)

    # ── Summary ──
    all_ranges = []
    for m in results["models"]:
        if m.get("fair_price"):
            all_ranges.append(m["fair_price"])
        elif m.get("graham_number"):
            all_ranges.append(m["graham_number"])
        r = m.get("range", [])
        if r:
            all_ranges.extend(r)

    if not all_ranges:
        results["summary"] = {"rating": "数据不足", "reason": "无可用估值模型"}
        return results

    low_val = min(all_ranges)
    high_val = max(all_ranges)
    # Remove extreme outliers: if high/low > 3, use 20th/80th percentile
    sorted_vals = sorted(all_ranges)
    if len(sorted_vals) >= 5 and sorted_vals[-1] / sorted_vals[0] > 3:
        low_val = sorted_vals[len(sorted_vals) // 5]
        high_val = sorted_vals[len(sorted_vals) * 4 // 5]

    price = current_price or 0
    rating = "合理"
    discount_pct = 0
    if price > 0 and high_val > 0:
        mid_val = (low_val + high_val) / 2
        discount_pct = round((mid_val - price) / price * 100, 1)
        if discount_pct > 20:
            rating = "显著低估"
        elif discount_pct > 5:
            rating = "略低估"
        elif discount_pct < -20:
            rating = "显著高估"
        elif discount_pct < -5:
            rating = "略高估"

    buy_prices = _calculate_buy_prices(results["models"], price)

    results["summary"] = {
        "valuation_range": [round(low_val, 2), round(high_val, 2)],
        "current_price": price,
        "discount_pct": discount_pct,
        "rating": rating,
        "models_used": len(results["models"]),
        "scenarios": _build_scenarios_a(results["models"], price),
        "buy_prices": buy_prices,
    }

    return results


def _calculate_buy_prices(models: list, current_price: float) -> dict:
    """
    Calculate recommended buy prices with safety margins.
    Conservative fair value = median of models' conservative estimates (robust to outliers).
    Then apply three tiers of safety margin (Graham-style).
    """
    # Collect conservative prices from models with explicit scenarios (P/E, P/B, EV/EBITDA).
    # These are the most grounded estimates. Single-point models (Graham, DDM, PEG, DCF)
    # use very different assumptions and can produce extreme values.
    scenario_prices = []
    fallback_prices = []
    for m in models:
        if m.get("conservative") and isinstance(m["conservative"], dict):
            p = m["conservative"].get("price")
            if p and p > 0:
                scenario_prices.append(p)
        gn = m.get("graham_number")
        if gn and gn > 0:
            fallback_prices.append(gn)
        fp = m.get("fair_price")
        if fp and fp > 0 and not m.get("conservative"):
            fallback_prices.append(fp * 0.85)

    # Prefer scenario-based models if we have at least 2
    if len(scenario_prices) >= 2:
        conservative_prices = scenario_prices
    elif len(scenario_prices) == 1:
        conservative_prices = scenario_prices + fallback_prices
    else:
        conservative_prices = fallback_prices

    if not conservative_prices:
        return {"available": False, "reason": "无可用保守估值数据"}

    # Use median as the conservative fair value (robust to remaining outliers)
    sorted_prices = sorted(conservative_prices)
    n = len(sorted_prices)
    if n % 2 == 0:
        conservative_fair = (sorted_prices[n // 2 - 1] + sorted_prices[n // 2]) / 2
    else:
        conservative_fair = sorted_prices[n // 2]

    safe_buy = round(conservative_fair * 0.75, 2)
    recommended_buy = round(conservative_fair * 0.85, 2)
    aggressive_buy = round(conservative_fair * 0.95, 2)

    result = {
        "available": True,
        "conservative_fair_value": round(conservative_fair, 2),
        "models_for_buy_price": len(conservative_prices),
        "safe": {"price": safe_buy, "margin_pct": 25},
        "recommended": {"price": recommended_buy, "margin_pct": 15},
        "aggressive": {"price": aggressive_buy, "margin_pct": 5},
    }

    if current_price > 0:
        result["current_price"] = current_price
        result["safe"]["discount_vs_current"] = round((safe_buy - current_price) / current_price * 100, 1)
        result["recommended"]["discount_vs_current"] = round((recommended_buy - current_price) / current_price * 100, 1)
        result["aggressive"]["discount_vs_current"] = round((aggressive_buy - current_price) / current_price * 100, 1)
        result["in_buy_zone"] = current_price <= recommended_buy
        if current_price <= safe_buy:
            result["buy_zone_tier"] = "safe"
        elif current_price <= recommended_buy:
            result["buy_zone_tier"] = "recommended"
        elif current_price <= aggressive_buy:
            result["buy_zone_tier"] = "aggressive"
        else:
            result["buy_zone_tier"] = "none"

    return result


def _build_scenarios_a(models: list, current_price: float) -> list:
    """Build scenario analysis from model results."""
    scenarios = []
    for m in models:
        if m.get("conservative") and m.get("optimistic"):
            cp = m["conservative"]["price"]
            bp = m["base"]["price"]
            op = m["optimistic"]["price"]
            label = m.get("model", "")
            discount = ""
            if current_price > 0:
                disc = round((bp - current_price) / current_price * 100, 1)
                discount = f"{disc:+}%"
            scenarios.append({
                "model": label,
                "conservative": cp,
                "base": bp,
                "optimistic": op,
                "discount_vs_current": discount,
            })
    return scenarios


def print_valuation_report_a(symbol: str, name: str, results: dict, current_price: float = None):
    """Print formatted A-share valuation report."""
    price = current_price or results["summary"].get("current_price", 0)

    print(f"\n{'='*60}")
    print(f"【估值模型分析：{name}（{symbol}）】")
    print(f"{'='*60}")

    summary = results.get("summary", {})
    if summary.get("rating") in ("不适用", "数据不足"):
        print(f"  结论：{summary['rating']} — {summary.get('reason', '')}")
        print(f"{'='*60}\n")
        return

    # Summary table
    print(f"\n### 多模型估值汇总\n")
    header = (
        "| 估值模型 | 保守估值 | 基准估值 | 乐观估值 | 当前价格 | 折价/溢价 | 判断 |\n"
        "|---------|---------|---------|---------|---------|----------|------|"
    )
    print(header)

    for m in results.get("models", []):
        model_name = m.get("model", "?")
        if m.get("graham_number"):
            # Graham Number: single value, not a range
            gn = m["graham_number"]
            disc = round((gn - price) / price * 100, 1) if price > 0 else 0
            judgement = "低估" if disc > 5 else ("高估" if disc < -5 else "合理")
            print(f"| {model_name} | — | ¥{gn:.2f} | — | ¥{price:.2f} | {disc:+}% | {judgement} |")
        elif m.get("fair_price"):
            fp = m["fair_price"]
            r = m.get("range", [fp, fp])
            disc = round((fp - price) / price * 100, 1) if price > 0 else 0
            judgement = "低估" if disc > 5 else ("高估" if disc < -5 else "合理")
            print(f"| {model_name} | ¥{r[0]:.2f} | ¥{fp:.2f} | ¥{r[1]:.2f} | ¥{price:.2f} | {disc:+}% | {judgement} |")
        elif m.get("conservative"):
            cp = m["conservative"]["price"]
            bp = m["base"]["price"]
            op = m["optimistic"]["price"]
            disc = round((bp - price) / price * 100, 1) if price > 0 else 0
            judgement = "低估" if disc > 5 else ("高估" if disc < -5 else "合理")
            print(f"| {model_name} | ¥{cp:.2f} | ¥{bp:.2f} | ¥{op:.2f} | ¥{price:.2f} | {disc:+}% | {judgement} |")

    # ── Conclusion ──
    vr = summary.get("valuation_range", [0, 0])
    print(f"\n#### 估值结论\n")
    print(f"**综合估值区间：** ¥{vr[0]:.2f} — ¥{vr[1]:.2f}")
    print(f"**当前价格：** ¥{price:.2f}，{summary.get('rating', '')}（{summary.get('discount_pct', 0):+}%）")
    print(f"**使用模型数：** {summary.get('models_used', 0)} 个")
    print(f"**情景分析：**")
    for s in summary.get("scenarios", []):
        print(f"  • {s['model']}：保守 ¥{s['conservative']:.2f} / 基准 ¥{s['base']:.2f} / 乐观 ¥{s['optimistic']:.2f}（基准 {s['discount_vs_current']}）")

    # ── Buy Price Recommendation ──
    bp = summary.get("buy_prices", {})
    if bp.get("available"):
        print(f"\n#### 推荐买入价格\n")
        print(f"**保守公允价值（各模型保守估值中位数）：** ¥{bp['conservative_fair_value']:.2f}")
        print(f"")
        zone = bp.get("buy_zone_tier", "none")
        zone_labels = {"safe": "🟢 安全买入区", "recommended": "🟡 推荐买入区", "aggressive": "🟠 激进买入区", "none": "🔴 未进入买入区"}
        print(f"| 类型 | 价格 | 安全边际 | 相对现价 |")
        print(f"|------|------|---------|----------|")
        for tier, label in [("safe", "安全买入"), ("recommended", "推荐买入"), ("aggressive", "激进买入")]:
            t = bp[tier]
            disc = t.get("discount_vs_current", 0)
            marker = " ✅" if bp.get("buy_zone_tier") == tier else ""
            print(f"| {label} | ¥{t['price']:.2f} | {t['margin_pct']}% | {disc:+}%{marker} |")
        print(f"| **当前价格** | **¥{price:.2f}** | — | — |")
        print(f"")
        print(f"**当前状态：** {zone_labels.get(zone, '—')}")
        if bp.get("in_buy_zone"):
            print(f"> ✅ 当前价格已进入推荐买入区间")
        elif price > 0:
            drop_needed = round((price - bp["recommended"]["price"]) / price * 100, 1)
            print(f"> ⏳ 距推荐买入价还需下跌约 {drop_needed}%")

    print(f"\n{'='*60}\n")


# ═══════════════════════════════════════════════════════════════
#  US Stock Valuation Models
# ═══════════════════════════════════════════════════════════════

def pe_valuation_us(eps: float, current_pe: float, industry_pe: float = None,
                     growth_rate: float = None) -> dict:
    """
    P/E multiple valuation for US stocks with conservative/growth scenarios.
    """
    if eps <= 0:
        return {"available": False, "reason": "EPS <= 0"}

    if industry_pe is None:
        industry_pe = 20.0

    # Conservative: industry PE × 0.8 or current PE × 0.85, whichever lower
    conservative_pe = round(min(industry_pe * 0.80, current_pe * 0.85) if current_pe else industry_pe * 0.80, 1)
    # Growth scenario: if growth > industry, use higher PE
    if growth_rate and growth_rate > 0:
        growth_pe = round(min(growth_rate * 1.2, industry_pe * 1.3), 1)
    else:
        growth_pe = round(industry_pe * 1.20, 1)

    return {
        "available": True,
        "model": "P/E 倍数法",
        "eps": round(eps, 2),
        "current_pe": round(current_pe, 1) if current_pe else None,
        "industry_pe": round(industry_pe, 1),
        "conservative": {"pe": conservative_pe, "price": round(eps * conservative_pe, 2)},
        "base": {"pe": industry_pe, "price": round(eps * industry_pe, 2)},
        "optimistic": {"pe": growth_pe, "price": round(eps * growth_pe, 2)},
        "range": [round(eps * conservative_pe, 2), round(eps * growth_pe, 2)],
    }


def ev_ebitda_valuation_us(ticker: str) -> dict:
    """
    EV/EBITDA valuation for US stocks.
    Fetches EBITDA, total debt, cash, shares outstanding from yfinance.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info

        ebitda = _safe_float(info.get("ebitda"))
        total_debt = _safe_float(info.get("totalDebt"))
        cash = _safe_float(info.get("totalCash"))
        shares = _safe_float(info.get("sharesOutstanding"))
        sector = info.get("sector", "")

        if ebitda <= 0:
            return {"available": False, "reason": "EBITDA <= 0，无法使用 EV/EBITDA 估值"}
        if shares <= 0:
            return {"available": False, "reason": "无法获取流通股数"}

        industry_mult = get_industry_ev_ebitda(sector)

        # EV = EBITDA × multiple
        ev_conservative = ebitda * industry_mult * 0.80
        ev_base = ebitda * industry_mult
        ev_optimistic = ebitda * industry_mult * 1.20

        net_debt = total_debt - cash

        mkt_cap_conservative = ev_conservative - net_debt
        mkt_cap_base = ev_base - net_debt
        mkt_cap_optimistic = ev_optimistic - net_debt

        price_conservative = round(mkt_cap_conservative / shares, 2)
        price_base = round(mkt_cap_base / shares, 2)
        price_optimistic = round(mkt_cap_optimistic / shares, 2)

        return {
            "available": True,
            "model": "EV/EBITDA",
            "ebitda_b": round(ebitda / 1e9, 1),
            "net_debt_b": round(net_debt / 1e9, 1),
            "industry_multiple": round(industry_mult, 1),
            "shares_outstanding_m": round(shares / 1e6, 1),
            "conservative": {"ev_multiple": round(industry_mult * 0.80, 1), "price": price_conservative},
            "base": {"ev_multiple": round(industry_mult, 1), "price": price_base},
            "optimistic": {"ev_multiple": round(industry_mult * 1.20, 1), "price": price_optimistic},
            "range": [price_conservative, price_optimistic],
        }
    except Exception as e:
        return {"available": False, "reason": f"yfinance 数据获取失败: {e}"}


def graham_number_us(eps: float, bvps: float) -> dict:
    """Graham Number for US stocks."""
    if eps <= 0 or bvps <= 0:
        return {"available": False, "reason": "EPS 或 BVPS <= 0"}
    gn = round(math.sqrt(22.5 * eps * bvps), 2)
    return {
        "available": True,
        "model": "格雷厄姆数",
        "eps": round(eps, 2),
        "bvps": round(bvps, 2),
        "graham_number": gn,
    }


def peg_valuation_us(eps: float, growth_rate: float) -> dict:
    """PEG valuation for US stocks."""
    if eps <= 0 or growth_rate is None or growth_rate <= 0:
        return {"available": False, "reason": "EPS <= 0 或增长率缺失"}
    fair_pe = growth_rate
    return {
        "available": True,
        "model": "PEG 估值 (Peter Lynch)",
        "eps": round(eps, 2),
        "growth_rate_pct": round(growth_rate, 1),
        "fair_pe": round(fair_pe, 1),
        "fair_price": round(eps * fair_pe, 2),
        "range": [round(eps * growth_rate * 0.8, 2), round(eps * growth_rate * 1.2, 2)],
    }


def dcf_framework_us(ticker: str) -> dict:
    """
    DCF framework for US stocks.
    Uses yfinance FCF data and presents valuation ranges with varying assumptions.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info

        fcf = _safe_float(info.get("freeCashflow"))
        shares = _safe_float(info.get("sharesOutstanding"))
        sector = info.get("sector", "")
        rev_growth = _safe_float(info.get("revenueGrowth"))

        if fcf <= 0:
            return {"available": False, "reason": "FCF <= 0，无法使用 DCF"}
        if shares <= 0:
            return {"available": False, "reason": "无法获取流通股数"}

        fcf_per_share = fcf / shares

        wacc = get_default_wacc(sector)
        growth_stage = max(min(rev_growth, 0.20), 0.02) if rev_growth else 0.08

        # Build sensitivity table: WACC vs terminal growth
        wacc_range = [wacc - 0.02, wacc, wacc + 0.02]
        tg_range = [0.01, 0.02, 0.03]

        sensitivity = []
        for w in wacc_range:
            w_adj = max(w, 0.05)
            row = {"wacc": round(w_adj * 100, 1), "prices": []}
            for tg in tg_range:
                t_adj = min(tg, w_adj - 0.02)
                if t_adj <= 0:
                    row["prices"].append(None)
                    continue
                # 5-year projection + terminal value
                total_pv = 0
                fcf_curr = fcf_per_share
                for yr in range(1, 6):
                    fcf_proj = fcf_curr * (1 + growth_stage) ** yr
                    total_pv += fcf_proj / (1 + w_adj) ** yr
                terminal_value = fcf_curr * (1 + growth_stage) ** 5 * (1 + t_adj) / (w_adj - t_adj)
                pv_terminal = terminal_value / (1 + w_adj) ** 5
                fair = round(total_pv + pv_terminal, 2)
                row["prices"].append(fair)
            sensitivity.append(row)

        base_price = sensitivity[1]["prices"][1] if len(sensitivity) > 1 and sensitivity[1]["prices"][1] else 0
        all_prices = [p for r in sensitivity for p in r["prices"] if p]
        price_range = [round(min(all_prices), 2), round(max(all_prices), 2)] if all_prices else [0, 0]

        return {
            "available": True,
            "model": "DCF (现金流折现)",
            "fcf_per_share": round(fcf_per_share, 2),
            "growth_stage_pct": round(growth_stage * 100, 1),
            "base_wacc_pct": round(wacc * 100, 1),
            "shares_m": round(shares / 1e6, 1),
            "fair_price": base_price,
            "range": price_range,
            "sensitivity": sensitivity,
        }
    except Exception as e:
        return {"available": False, "reason": f"DCF 计算失败: {e}"}


def ddm_valuation_us(dps: float, growth_rate: float = 0.03,
                      required_return: float = 0.10) -> dict:
    """Gordon Growth DDM for US stocks."""
    if dps <= 0:
        return {"available": False, "reason": "无股息"}
    if growth_rate >= required_return:
        return {"available": False, "reason": f"g({growth_rate:.1%}) >= r({required_return:.1%})"}
    fair = round(dps * (1 + growth_rate) / (required_return - growth_rate), 2)
    return {
        "available": True,
        "model": "股息贴现模型 (DDM)",
        "dps": round(dps, 2),
        "growth_rate_pct": round(growth_rate * 100, 1),
        "required_return_pct": round(required_return * 100, 1),
        "fair_price": fair,
        "range": [
            round(dps * (1 + growth_rate - 0.01) / (required_return - growth_rate + 0.01), 2),
            round(dps * (1 + growth_rate + 0.01) / (required_return - growth_rate - 0.01), 2),
        ],
    }


def comprehensive_valuation_us(ticker: str, eps: float = None,
                                growth_rate: float = None,
                                profit: bool = True) -> dict:
    """
    Run all applicable US valuation models.
    Returns composite results with models list and summary.
    """
    results = {"ticker": ticker.upper(), "models": [], "summary": {}}

    if not profit:
        results["summary"] = {"rating": "不适用", "reason": "公司亏损，估值模型不可靠"}
        return results

    # Fetch all needed data from yfinance
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info

        current_price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
        if eps is None:
            eps = _safe_float(info.get("trailingEps"))
        bvps = _safe_float(info.get("bookValue"))
        current_pe = _safe_float(info.get("trailingPE"))
        current_pb = _safe_float(info.get("priceToBook"))
        sector = info.get("sector", "")
        name = info.get("longName") or info.get("shortName", ticker)
        dps = _safe_float(info.get("dividendRate"))
        if growth_rate is None:
            growth_rate = _safe_float(info.get("earningsGrowth"))
            # earningsGrowth is decimal; if > 1.0 it could be percentage
            if growth_rate and growth_rate > 1.0:
                growth_rate = growth_rate
            elif growth_rate:
                growth_rate = growth_rate * 100

        results["name"] = name
        results["sector"] = sector
        results["current_price"] = current_price

        industry_pe = get_industry_pe(sector, is_us=True)

    except Exception as e:
        results["summary"] = {"rating": "数据不足", "reason": f"yfinance 数据获取失败: {e}"}
        return results

    # 1. P/E
    if eps and eps > 0:
        m = pe_valuation_us(eps, current_pe or 0, industry_pe, growth_rate)
        results["models"].append(m)

    # 2. EV/EBITDA
    m = ev_ebitda_valuation_us(ticker)
    if m.get("available"):
        results["models"].append(m)

    # 3. Graham Number
    if eps and eps > 0 and bvps and bvps > 0:
        m = graham_number_us(eps, bvps)
        results["models"].append(m)

    # 4. PEG
    if eps and eps > 0 and growth_rate and growth_rate > 0:
        m = peg_valuation_us(eps, growth_rate)
        results["models"].append(m)

    # 5. DCF
    m = dcf_framework_us(ticker)
    if m.get("available"):
        results["models"].append(m)

    # 6. DDM
    if dps and dps > 0:
        m = ddm_valuation_us(dps)
        results["models"].append(m)

    # ── Summary ──
    all_prices = []
    for m in results["models"]:
        for key in ("fair_price", "graham_number"):
            v = m.get(key)
            if v and v > 0:
                all_prices.append(v)
        for key in ("conservative", "base", "optimistic"):
            sc = m.get(key, {})
            if isinstance(sc, dict) and sc.get("price"):
                all_prices.append(sc["price"])

    if not all_prices:
        results["summary"] = {"rating": "数据不足", "reason": "无可用估值模型"}
        return results

    sorted_prices = sorted(all_prices)
    low_val = sorted_prices[len(sorted_prices) // 10]  # 10th percentile
    high_val = sorted_prices[len(sorted_prices) * 9 // 10]  # 90th percentile
    if len(sorted_prices) < 5:
        low_val = sorted_prices[0]
        high_val = sorted_prices[-1]

    rating = "合理"
    discount_pct = 0
    if current_price > 0:
        mid_val = (low_val + high_val) / 2
        discount_pct = round((mid_val - current_price) / current_price * 100, 1)
        if discount_pct > 20:
            rating = "显著低估"
        elif discount_pct > 5:
            rating = "略低估"
        elif discount_pct < -20:
            rating = "显著高估"
        elif discount_pct < -5:
            rating = "略高估"

    results["summary"] = {
        "valuation_range": [round(low_val, 2), round(high_val, 2)],
        "current_price": current_price,
        "discount_pct": discount_pct,
        "rating": rating,
        "models_used": len(results["models"]),
        "scenarios": _build_scenarios_us(results["models"], current_price),
        "buy_prices": _calculate_buy_prices(results["models"], current_price),
    }

    return results


def _build_scenarios_us(models: list, current_price: float) -> list:
    """Build scenario analysis for US stocks."""
    scenarios = []
    for m in models:
        if m.get("conservative") and m.get("optimistic"):
            cp = m["conservative"]["price"]
            bp = m.get("base", {}).get("price", (cp + m["optimistic"]["price"]) / 2)
            op = m["optimistic"]["price"]
            label = m.get("model", "")
            disc = round((bp - current_price) / current_price * 100, 1) if current_price > 0 else 0
            scenarios.append({
                "model": label,
                "conservative": cp,
                "base": bp,
                "optimistic": op,
                "discount_vs_current": f"{disc:+}%",
            })
    return scenarios


def print_valuation_report_us(ticker: str, name: str, results: dict):
    """Print formatted US stock valuation report."""
    price = results.get("current_price", 0)

    print(f"\n{'='*60}")
    print(f"【估值模型分析：{name}（{ticker.upper()}）】")
    print(f"{'='*60}")

    summary = results.get("summary", {})
    if summary.get("rating") in ("不适用", "数据不足"):
        print(f"  结论：{summary['rating']} — {summary.get('reason', '')}")
        print(f"{'='*60}\n")
        return

    print(f"\n### 多模型估值汇总\n")
    header = (
        "| 估值模型 | 保守估值 | 基准估值 | 乐观估值 | 当前价格 | 折价/溢价 | 判断 |\n"
        "|---------|---------|---------|---------|---------|----------|------|"
    )
    print(header)

    for m in results.get("models", []):
        model_name = m.get("model", "?")

        if m.get("graham_number"):
            gn = m["graham_number"]
            disc = round((gn - price) / price * 100, 1) if price > 0 else 0
            judgement = "低估" if disc > 5 else ("高估" if disc < -5 else "合理")
            print(f"| {model_name} | — | ${gn:.2f} | — | ${price:.2f} | {disc:+}% | {judgement} |")

        elif m.get("fair_price"):
            fp = m["fair_price"]
            r = m.get("range", [fp, fp])
            disc = round((fp - price) / price * 100, 1) if price > 0 else 0
            judgement = "低估" if disc > 5 else ("高估" if disc < -5 else "合理")
            print(f"| {model_name} | ${r[0]:.2f} | ${fp:.2f} | ${r[1]:.2f} | ${price:.2f} | {disc:+}% | {judgement} |")

            # DCF: print sensitivity
            if model_name.startswith("DCF") and m.get("sensitivity"):
                print(f"|   ── DCF 敏感性分析 ── | WACC \\ g | 1% | 2% | 3% |")
                for row in m["sensitivity"]:
                    prices = [f"${p:.2f}" if p else "—" for p in row["prices"]]
                    print(f"|   | {row['wacc']}% | {prices[0]} | {prices[1]} | {prices[2]} |")

        elif m.get("conservative"):
            cp = m["conservative"]["price"]
            bp = m["base"]["price"]
            op = m["optimistic"]["price"]
            disc = round((bp - price) / price * 100, 1) if price > 0 else 0
            judgement = "低估" if disc > 5 else ("高估" if disc < -5 else "合理")
            print(f"| {model_name} | ${cp:.2f} | ${bp:.2f} | ${op:.2f} | ${price:.2f} | {disc:+}% | {judgement} |")

    # ── Conclusion ──
    vr = summary.get("valuation_range", [0, 0])
    print(f"\n#### 估值结论\n")
    print(f"**综合估值区间：** ${vr[0]:.2f} — ${vr[1]:.2f}")
    print(f"**当前价格：** ${price:.2f}，{summary.get('rating', '')}（{summary.get('discount_pct', 0):+}%）")
    print(f"**使用模型数：** {summary.get('models_used', 0)} 个")

    if summary.get("scenarios"):
        print(f"\n**情景分析：**")
        for s in summary["scenarios"]:
            print(f"  • {s['model']}：保守 ${s['conservative']:.2f} / 基准 ${s['base']:.2f} / 乐观 ${s['optimistic']:.2f}（基准 {s['discount_vs_current']}）")

    # ── Buy Price Recommendation ──
    bp = summary.get("buy_prices", {})
    if bp.get("available"):
        print(f"\n#### 推荐买入价格\n")
        print(f"**保守公允价值（各模型保守估值中位数）：** ${bp['conservative_fair_value']:.2f}")
        print(f"")
        zone = bp.get("buy_zone_tier", "none")
        zone_labels = {"safe": "🟢 安全买入区", "recommended": "🟡 推荐买入区", "aggressive": "🟠 激进买入区", "none": "🔴 未进入买入区"}
        print(f"| 类型 | 价格 | 安全边际 | 相对现价 |")
        print(f"|------|------|---------|----------|")
        for tier, label in [("safe", "安全买入"), ("recommended", "推荐买入"), ("aggressive", "激进买入")]:
            t = bp[tier]
            disc = t.get("discount_vs_current", 0)
            marker = " ✅" if bp.get("buy_zone_tier") == tier else ""
            print(f"| {label} | ${t['price']:.2f} | {t['margin_pct']}% | {disc:+}%{marker} |")
        print(f"| **当前价格** | **${price:.2f}** | — | — |")
        print(f"")
        print(f"**当前状态：** {zone_labels.get(zone, '—')}")
        if bp.get("in_buy_zone"):
            print(f"> ✅ 当前价格已进入推荐买入区间")
        elif price > 0:
            drop_needed = round((price - bp["recommended"]["price"]) / price * 100, 1)
            print(f"> ⏳ 距推荐买入价还需下跌约 {drop_needed}%")

    print(f"\n{'='*60}\n")


# ═══════════════════════════════════════════════════════════════
#  Main entry point for standalone use
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage:")
        print("  python3 valuation.py US AAPL")
        print("  python3 valuation.py US AAPL [eps] [growth_rate]")
        print("  python3 valuation.py A 600519 [eps] [bvps] [growth_rate] [dps]")
        print()
        print("For A-shares, EPS/BVPS/growth_rate must be provided (from WebSearch).")
        print("For US stocks, all data is auto-fetched from yfinance.")
        sys.exit(0)

    mode = sys.argv[1].upper()
    ticker = sys.argv[2]

    if mode == "US":
        eps = float(sys.argv[3]) if len(sys.argv) > 3 else None
        growth = float(sys.argv[4]) if len(sys.argv) > 4 else None

        results = comprehensive_valuation_us(ticker, eps=eps, growth_rate=growth)
        print_valuation_report_us(ticker, results.get("name", ticker), results)
        print("\n--- JSON ---")
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))

    elif mode == "A":
        symbol = ticker
        eps = float(sys.argv[3]) if len(sys.argv) > 3 else None
        bvps = float(sys.argv[4]) if len(sys.argv) > 4 else None
        growth = float(sys.argv[5]) if len(sys.argv) > 5 else None
        dps = float(sys.argv[6]) if len(sys.argv) > 6 else None

        if eps is None:
            print("错误：A 股估值需要提供 EPS（从 WebSearch 财报获取）")
            sys.exit(1)

        # Get current P/E, P/B, price from market data
        current_pe = None
        current_pb = None
        current_price = None
        try:
            from stock import _get_quote_data, _get_prefix
            parts = _get_quote_data(symbol)
            if parts:
                current_price = float(parts[3])
                # PE from field 39, PB from field 46
                try:
                    current_pe = float(parts[39]) if parts[39] else None
                except (ValueError, IndexError):
                    pass
                try:
                    current_pb = float(parts[46]) if len(parts) > 46 and parts[46] else None
                except (ValueError, IndexError):
                    pass
        except Exception:
            pass

        results = comprehensive_valuation_a(
            symbol, name=symbol,
            eps=eps, bvps=bvps, growth_rate=growth, dps=dps,
            current_pe=current_pe, current_pb=current_pb,
            current_price=current_price,
        )
        print_valuation_report_a(symbol, symbol, results, current_price)
        print("\n--- JSON ---")
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
