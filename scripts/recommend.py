"""
Stock recommendation engine for financial-assistant skill.
Provides 4 screening strategies:

E1: Oversold stocks with unchanged fundamentals (yfinance)
E2: Newly named supplier detection (WebSearch-driven)
E3: Guru new positions (WebSearch-driven)
E4: Guru holdings that dipped (yfinance cross-ref)

All functions produce JSON-compatible dicts for use in SKILL.md workflows.
"""

import json
import yfinance as yf

# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _safe_float(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0



def _get_quick_info(ticker: str) -> dict:
    """Get minimal stock info quickly (for batch screening)."""
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        return {
            "name": info.get("longName") or info.get("shortName", ticker),
            "ticker": ticker.upper(),
            "price": _safe_float(info.get("currentPrice") or info.get("regularMarketPrice")),
            "52w_high": _safe_float(info.get("fiftyTwoWeekHigh")),
            "52w_low": _safe_float(info.get("fiftyTwoWeekLow")),
            "eps": _safe_float(info.get("trailingEps")),
            "pe": _safe_float(info.get("trailingPE")),
            "revenue_growth": _safe_float(info.get("revenueGrowth")),
            "earnings_growth": _safe_float(info.get("earningsGrowth")),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "market_cap": _safe_float(info.get("marketCap")),
            "beta": _safe_float(info.get("beta")),
            "error": None,
        }
    except Exception as e:
        return {"name": ticker, "ticker": ticker.upper(), "error": str(e)}


# ─────────────────────────────────────────
# E1: Oversold Stocks with Unchanged Fundamentals
# ─────────────────────────────────────────

def find_oversold_fundamentals(
    candidates: list = None,
    max_drop_pct: float = 20.0,
    min_eps: float = 0.0,
    min_revenue_growth: float = -5.0,
    top_n: int = 10,
) -> list:
    """
    Screen stocks that have fallen significantly from 52-week high but
    whose fundamentals (EPS, revenue) remain intact.

    Args:
        candidates: List of ticker strings to screen. If None, uses a preset AI/semiconductor watchlist.
        max_drop_pct: Minimum drop from 52w high to be considered (default 20%)
        min_eps: Minimum trailing EPS to filter (default 0 = profitable)
        min_revenue_growth: Minimum YoY revenue growth % (default -5% = slight decline ok)
        top_n: Max number of results to return

    Returns:
        list of dict with ranked oversold stocks
    """
    if candidates is None:
        # Default AI / semiconductor watchlist
        candidates = [
            "NVDA", "AMD", "INTC", "AVGO", "MRVL", "QCOM", "MU", "TXN",
            "AMAT", "LRCX", "KLAC", "ASML", "TSM", "SNPS", "CDNS",
            "MSFT", "GOOGL", "AMZN", "META", "AAPL", "CRM", "ADBE",
            "ANET", "SMCI", "DELL", "HPE", "COHR", "CIEN",
            "ORCL", "SNOW", "PLTR", "CRWD", "ZS", "PANW", "FTNT",
        ]

    print(f"\n{'='*60}")
    print(f"📉 超跌基本面筛选：跌幅>{max_drop_pct}% | EPS>${min_eps} | 营收增长>{min_revenue_growth}%")
    print(f"   候选池：{len(candidates)} 只股票")
    print(f"{'='*60}")

    results = []
    for i, ticker in enumerate(candidates):
        print(f"\r   扫描进度：{i+1}/{len(candidates)} — {ticker}", end="", flush=True)
        info = _get_quick_info(ticker)
        if info.get("error"):
            continue

        high_52w = info["52w_high"]
        price = info["price"]
        eps = info["eps"]
        rev_growth = info["revenue_growth"]

        if high_52w <= 0 or price <= 0:
            continue

        drop_pct = round((1 - price / high_52w) * 100, 1)

        # Filter criteria
        if drop_pct < max_drop_pct:
            continue
        if eps < min_eps:
            continue
        if rev_growth < min_revenue_growth:
            continue

        results.append({
            "ticker": info["ticker"],
            "name": info["name"],
            "price": price,
            "52w_high": high_52w,
            "52w_low": info["52w_low"],
            "drop_pct": -drop_pct,
            "eps": eps,
            "pe": info["pe"],
            "revenue_growth": round(rev_growth * 100, 1),
            "earnings_growth": round(info["earnings_growth"] * 100, 1),
            "sector": info["sector"],
            "market_cap": info["market_cap"],
            "beta": info["beta"],
        })

    print()  # newline after progress

    # Sort by largest drop first
    results.sort(key=lambda x: x["drop_pct"])

    print(f"   筛选结果：{len(results)} 只符合条件")
    for i, r in enumerate(results[:top_n]):
        print(f"   {i+1}. {r['ticker']:6s} ${r['price']:>8.2f}  |  跌 {r['drop_pct']:>+6.1f}%  |  EPS ${r['eps']:>5.2f}  |  营收YoY {r['revenue_growth']:>+5.1f}%")

    return results[:top_n]


# ─────────────────────────────────────────
# E2: New Supplier Detection Helpers
# ─────────────────────────────────────────

def verify_supplier_fundamentals(tickers: list) -> list:
    """
    For a list of ticker candidates (found via WebSearch), verify their
    fundamentals and add financial context.

    Args:
        tickers: List of ticker strings

    Returns:
        list of dict with verified fundamental data
    """
    print(f"\n{'='*60}")
    print(f"🆕 供应商基本面验证：{len(tickers)} 个候选")
    print(f"{'='*60}")

    results = []
    for ticker in tickers:
        info = _get_quick_info(ticker)
        if info.get("error"):
            results.append({"ticker": ticker.upper(), "error": info["error"]})
            continue

        results.append({
            "ticker": info["ticker"],
            "name": info["name"],
            "price": info["price"],
            "eps": info["eps"],
            "pe": info["pe"],
            "market_cap": info["market_cap"],
            "sector": info["sector"],
            "revenue_growth": round(info["revenue_growth"] * 100, 1),
            "drop_from_high": round((1 - info["price"] / info["52w_high"]) * 100, 1) if info["52w_high"] and info["52w_high"] > 0 else 0,
        })
        print(f"   {info['ticker']:6s} ${info['price']:.2f}  |  EPS ${info['eps']:.2f}  |  PE {info['pe']:.1f}")

    return results


# ─────────────────────────────────────────
# E4: Guru Holdings Dip Detector
# ─────────────────────────────────────────

def find_guru_dip_holdings(
    tickers: list,
    min_drop_pct: float = 15.0,
) -> list:
    """
    Given a list of guru portfolio tickers, find those that have dipped
    significantly from their recent highs.

    Args:
        tickers: List of ticker strings from guru portfolio
        min_drop_pct: Minimum drop % to flag (default 15%)

    Returns:
        list of dict with dipped holdings, sorted by drop magnitude
    """
    print(f"\n{'='*60}")
    print(f"📌 大师持仓被套检测：{len(tickers)} 只持仓中筛选跌幅>{min_drop_pct}%")
    print(f"{'='*60}")

    results = []
    for i, ticker in enumerate(tickers):
        print(f"\r   扫描进度：{i+1}/{len(tickers)} — {ticker}", end="", flush=True)
        info = _get_quick_info(ticker)
        if info.get("error"):
            continue

        high_52w = info["52w_high"]
        price = info["price"]
        if high_52w <= 0 or price <= 0:
            continue

        drop_pct = round((1 - price / high_52w) * 100, 1)
        if drop_pct < min_drop_pct:
            continue

        # Calculate drop from 3-month high
        drop_3m = 0
        try:
            hist = yf.Ticker(ticker.upper()).history(period="3mo")
            if len(hist) >= 1:
                high_3m = float(hist["High"].max())
                if high_3m > 0:
                    drop_3m = round((1 - price / high_3m) * 100, 1)
        except Exception:
            pass

        results.append({
            "ticker": info["ticker"],
            "name": info["name"],
            "price": price,
            "52w_high": high_52w,
            "drop_pct": -drop_pct,
            "drop_3m_pct": -drop_3m if drop_3m else None,
            "eps": info["eps"],
            "pe": info["pe"],
            "sector": info["sector"],
            "market_cap": info["market_cap"],
            "revenue_growth": round(info["revenue_growth"] * 100, 1),
        })

    print()
    results.sort(key=lambda x: x["drop_pct"])

    print(f"   筛选结果：{len(results)} 只跌幅>{min_drop_pct}%")
    for i, r in enumerate(results):
        print(f"   {i+1}. {r['ticker']:6s} ${r['price']:>8.2f}  |  跌 {r['drop_pct']:>+6.1f}%  |  3月跌 {r.get('drop_3m_pct', 0):>+6.1f}%")

    return results


# ─────────────────────────────────────────
# Output formatting
# ─────────────────────────────────────────

def print_oversold_table(results: list):
    """Print oversold screening results table."""
    if not results:
        print("\n📉 超跌筛选中没有符合条件的标的。")
        return

    print(f"\n### 📉 超跌但基本面未变（距52周高点跌幅>20%）\n")
    header = (
        "| # | 股票 | Ticker | 现价 | 52周高 | 跌幅 | EPS | PE | 营收YoY | 市值 | Beta |"
        "\n|---|------|--------|------|--------|------|-----|----|---------|------|------|"
    )
    print(header)

    for i, r in enumerate(results[:10], 1):
        name = r["name"][:20]
        mkt_cap_str = f"${r['market_cap']/1e9:.0f}B" if r["market_cap"] else "N/A"
        pe_str = f"{r['pe']:.1f}" if r["pe"] else "N/A"
        row = (
            f"| {i} | {name} | {r['ticker']} | ${r['price']:.2f} | ${r['52w_high']:.2f} "
            f"| {r['drop_pct']:+.1f}% | ${r['eps']:.2f} | {pe_str} "
            f"| {r['revenue_growth']:+.1f}% | {mkt_cap_str} | {r['beta']:.1f} |"
        )
        print(row)

    print(f"\n> 共 {len(results)} 只符合条件，显示 Top {min(10, len(results))}\n")


def print_guru_dip_table(results: list, guru_name: str = "", min_drop_pct: float = 15.0):
    """Print guru dipped holdings table."""
    if not results:
        print(f"\n📌 {guru_name}持仓暂未检测到跌幅>{min_drop_pct}%的标的。")
        return

    print(f"\n### 📌 {guru_name}持仓被套（跌幅>{min_drop_pct}%）\n")
    header = (
        "| # | 股票 | Ticker | 现价 | 52周高 | 从高点跌 | 3月跌 | EPS | PE | 行业 |"
        "\n|---|------|--------|------|--------|----------|-------|-----|----|------|"
    )
    print(header)

    for i, r in enumerate(results[:10], 1):
        name = r["name"][:20]
        drop_3m = f"{r['drop_3m_pct']:+.1f}%" if r.get("drop_3m_pct") else "N/A"
        pe_str = f"{r['pe']:.1f}" if r["pe"] else "N/A"
        row = (
            f"| {i} | {name} | {r['ticker']} | ${r['price']:.2f} | ${r['52w_high']:.2f} "
            f"| {r['drop_pct']:+.1f}% | {drop_3m} "
            f"| ${r['eps']:.2f} | {pe_str} | {r['sector']} |"
        )
        print(row)

    print(f"\n> 共 {len(results)} 只被套，显示 Top {min(10, len(results))}\n")


def print_guru_new_positions(positions: list, guru_name: str = ""):
    """Print guru new positions table."""
    if not positions:
        print(f"\n🏆 暂未找到{guru_name}最新建仓数据。")
        return

    print(f"\n### 🏆 {guru_name}最新建仓\n")
    header = (
        "| # | 股票 | Ticker | 建仓规模 | 建仓时间 | 当前价格 | 表现 |"
        "\n|---|------|--------|---------|---------|---------|------|"
    )
    print(header)

    for i, p in enumerate(positions[:10], 1):
        name = p.get("name", "")[:20]
        size = p.get("size", "N/A")
        date = p.get("date", "N/A")
        price = p.get("current_price", "N/A")
        perf = p.get("perf", "N/A")
        row = f"| {i} | {name} | {p.get('ticker', '?')} | {size} | {date} | {price} | {perf} |"
        print(row)

    print()


def print_supplier_table(results: list, leader: str = ""):
    """Print new supplier results table."""
    if not results:
        print(f"\n🆕 暂未找到{leader}新被点名供应商。")
        return

    print(f"\n### 🆕 {leader}新被点名的供应商/合作伙伴\n")
    header = (
        "| # | 股票 | Ticker | 合作内容 | 公告时间 | 当前价格 | 市值 | 高位跌幅 |"
        "\n|---|------|--------|---------|---------|---------|------|----------|"
    )
    print(header)

    for i, s in enumerate(results[:10], 1):
        name = s.get("name", "")[:18]
        note = s.get("note", "")[:25]
        date = s.get("date", "N/A")
        price = f"${s.get('price', 0):.2f}" if s.get("price") else "N/A"
        mkt_cap = f"${s['market_cap']/1e9:.0f}B" if s.get("market_cap") and s["market_cap"] > 0 else "N/A"
        drop = f"{s.get('drop_from_high', 0):+.1f}%" if s.get("drop_from_high") is not None else "N/A"
        row = f"| {i} | {name} | {s.get('ticker', '?')} | {note} | {date} | {price} | {mkt_cap} | {drop} |"
        print(row)

    print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法：")
        print("  python3 recommend.py oversold [板块名]      — E1 超跌筛选")
        print("  python3 recommend.py verify AAPL,TSLA,NVDA  — E2 供应商验证")
        print("  python3 recommend.py dip AAPL,TSLA,KO,...   — E4 大师持仓被套检测")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "oversold":
        sector = sys.argv[2] if len(sys.argv) > 2 else None
        # If sector specified, note it (actual candidate filtering happens via the watchlist)
        results = find_oversold_fundamentals()
        print_oversold_table(results)
        print("\n--- JSON ---")
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif cmd == "verify":
        tickers_str = sys.argv[2] if len(sys.argv) > 2 else ""
        tickers = [t.strip().upper() for t in tickers_str.split(",") if t.strip()]
        results = verify_supplier_fundamentals(tickers)
        print("\n--- JSON ---")
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif cmd == "dip":
        tickers_str = sys.argv[2] if len(sys.argv) > 2 else ""
        tickers = [t.strip().upper() for t in tickers_str.split(",") if t.strip()]
        results = find_guru_dip_holdings(tickers)
        print_guru_dip_table(results)
        print("\n--- JSON ---")
        print(json.dumps(results, ensure_ascii=False, indent=2))
