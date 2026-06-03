"""
A股板块分析模块。
从 sectors.yaml 加载板块定义，计算板块整体表现，
按多维度排名，输出值得关注的板块。

数据源：腾讯行情接口（A 股 K 线）+ WebSearch（定性因子）。
"""

import os
import sys
import json
import time
from collections import defaultdict

# 复用 stock.py 中的函数
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)

from stock import get_kline_data, _get_quote_data

_SECTORS_PATH = os.path.join(_SKILL_DIR, "sectors.yaml")


# ─── Config loading ─────────────────────────────────────────

def load_sectors() -> list:
    """Load sector definitions from sectors.yaml."""
    try:
        import yaml
    except ImportError:
        print("错误：需要安装 pyyaml (pip3 install pyyaml)")
        return []

    if not os.path.exists(_SECTORS_PATH):
        print(f"错误：配置文件不存在: {_SECTORS_PATH}")
        return []

    with open(_SECTORS_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    return cfg.get("sectors", [])


# ─── Sector performance calculation ─────────────────────────

def _calc_returns(codes: list, days: int) -> dict:
    """
    Calculate average return over `days` trading days for a list of stock codes.
    Returns {avg_return: float, up_ratio: float, valid_count: int, total: int}
    """
    returns = []
    for code in codes:
        klines = get_kline_data(code, count=days + 5)
        if len(klines) < days + 1:
            continue
        closes = [float(k[2]) for k in klines]
        start_price = closes[-(days + 1)]
        end_price = closes[-1]
        if start_price <= 0:
            continue
        ret = (end_price - start_price) / start_price * 100
        returns.append(ret)

    up_count = sum(1 for r in returns if r > 0)
    avg_ret = sum(returns) / len(returns) if returns else 0
    return {
        "avg_return": round(avg_ret, 2),
        "up_ratio": round(up_count / len(returns) * 100, 1) if returns else 0,
        "valid_count": len(returns),
        "total": len(codes),
    }


def _calc_volume_trend(codes: list, days: int = 20) -> dict:
    """
    Check volume trend: is recent volume higher than average?
    Returns {volume_ratio: float, expanding_count: int}
    """
    ratios = []
    for code in codes:
        klines = get_kline_data(code, count=60)
        if len(klines) < days + 6:
            continue
        volumes = [float(k[5]) for k in klines]
        recent_5 = sum(volumes[-6:-1]) / 5
        prior_20 = sum(volumes[-26:-6]) / 20
        if prior_20 <= 0:
            continue
        ratio = recent_5 / prior_20
        ratios.append(ratio)

    expanding = sum(1 for r in ratios if r > 1.1)
    avg_ratio = sum(ratios) / len(ratios) if ratios else 0
    return {
        "volume_ratio": round(avg_ratio, 2),
        "expanding_count": expanding,
        "expanding_ratio": round(expanding / len(ratios) * 100, 1) if ratios else 0,
    }


def get_sector_performance(sector: dict) -> dict:
    """
    Calculate comprehensive sector performance metrics.
    """
    stocks = sector.get("stocks", [])
    codes = [s["code"] for s in stocks]

    perf_5d = _calc_returns(codes, 5)
    perf_10d = _calc_returns(codes, 10)
    perf_20d = _calc_returns(codes, 20)
    vol = _calc_volume_trend(codes)

    # Composite momentum score (weighted)
    mom_score = (perf_5d["avg_return"] * 0.5 + perf_10d["avg_return"] * 0.3 + perf_20d["avg_return"] * 0.2)

    return {
        "name": sector["name"],
        "stocks": stocks,
        "perf_5d": perf_5d,
        "perf_10d": perf_10d,
        "perf_20d": perf_20d,
        "volume_trend": vol,
        "momentum_score": round(mom_score, 2),
    }


# ─── Earnings season risk assessment ────────────────────────

def assess_earnings_risk(sector: dict, current_month: int = 4) -> dict:
    """
    Assess earnings season risk for a sector.
    In April (Q1 report season), stocks that haven't reported yet are risky.
    This is a qualitative flag — actual verification needs WebSearch.
    Returns {"risk_level": "低/中/高", "warning": "..."}
    """
    if current_month in [4, 8, 10]:
        return {
            "risk_level": "中",
            "note": f"{current_month}月为季报密集披露期，建议优先选择已披露业绩的标的",
            "check_items": ["营收是否同比正增长", "经营现金流是否为正", "有无大额减值/计提"],
        }
    return {"risk_level": "低", "note": "非业绩披露密集期"}


# ─── Ranking & output ───────────────────────────────────────

def analyze_all_sectors(verbose: bool = False) -> list:
    """
    Analyze all sectors and return ranked results.
    """
    sectors = load_sectors()
    if not sectors:
        print("未加载到板块配置")
        return []

    results = []
    total = len(sectors)

    print(f"\n{'='*60}")
    print(f" A股板块分析 — 共 {total} 个板块")
    print(f"{'='*60}\n")

    for i, sector in enumerate(sectors):
        name = sector["name"]
        n_stocks = len(sector.get("stocks", []))
        print(f"  [{i+1}/{total}] 分析 {name}（{n_stocks} 只成分股）...", end=" ", flush=True)

        try:
            perf = get_sector_performance(sector)
            perf["earnings_risk"] = assess_earnings_risk(sector)
            results.append(perf)
            print(f"5日 {perf['perf_5d']['avg_return']:+.1f}% | 20日 {perf['perf_20d']['avg_return']:+.1f}%")
        except Exception as e:
            print(f"失败: {e}")

        time.sleep(0.3)  # 避免腾讯接口限流

    # Sort by momentum score descending
    results.sort(key=lambda x: x["momentum_score"], reverse=True)
    return results


def print_sector_ranking(results: list, top_n: int = 10):
    """Print ranked sector analysis table."""
    if not results:
        print("无数据")
        return

    print(f"\n{'='*70}")
    print(f" 板块综合排名（按动量评分降序）")
    print(f"{'='*70}\n")

    # Main ranking table
    header = (
        "| # | 板块 | 5日涨跌 | 10日涨跌 | 20日涨跌 | 动量分 | 放量比 | 涨家比 | 业绩风险 |"
        "\n|---|------|---------|----------|----------|--------|--------|--------|----------|"
    )
    print(header)

    for i, r in enumerate(results[:top_n], 1):
        p5 = r["perf_5d"]
        p10 = r["perf_10d"]
        p20 = r["perf_20d"]
        vol = r["volume_trend"]
        risk = r["earnings_risk"]

        row = (
            f"| {i} | {r['name']} "
            f"| {p5['avg_return']:+.1f}% "
            f"| {p10['avg_return']:+.1f}% "
            f"| {p20['avg_return']:+.1f}% "
            f"| **{r['momentum_score']:+.1f}** "
            f"| {vol['volume_ratio']:.2f}x "
            f"| {p20['up_ratio']:.0f}% "
            f"| {risk['risk_level']} |"
        )
        print(row)

    # Detail breakdown for top 5
    print(f"\n{'─'*70}")
    print(" Top 5 板块成分股明细")
    print(f"{'─'*70}")

    for i, r in enumerate(results[:5], 1):
        p5 = r["perf_5d"]
        p20 = r["perf_20d"]
        vol = r["volume_trend"]

        print(f"\n### {i}. {r['name']} — 动量评分 {r['momentum_score']:+.1f}")
        print(f"> 5日涨跌 {p5['avg_return']:+.1f}%（{p5['up_ratio']:.0f}%上涨） | "
              f"20日涨跌 {p20['avg_return']:+.1f}% | "
              f"量能 {vol['volume_ratio']:.2f}x（{vol['expanding_ratio']:.0f}%放量）")

        # Per-stock breakdown
        print(f"\n| 股票 | 代码 | 5日涨跌 |")
        print(f"|------|------|--------|")
        for s in r["stocks"]:
            code = s["code"]
            perf = _calc_returns([code], 5)
            print(f"| {s['name']} | {code} | {perf['avg_return']:+.1f}% |")

    print()


def print_sector_report(results: list):
    """Print full sector analysis report with actionable insights."""
    if not results:
        return

    print_sector_ranking(results)

    # Actionable insights
    print(f"{'='*70}")
    print(" 综合判断与建议")
    print(f"{'='*70}\n")

    top3 = results[:3]

    print("**🔺 最强动量板块（短线资金主攻方向）：**")
    for i, r in enumerate(top3, 1):
        p5 = r["perf_5d"]
        vol = r["volume_trend"]
        tag = "🔥 放量上攻" if vol["volume_ratio"] > 1.2 else "⚡ 缩量上涨" if vol["volume_ratio"] < 0.9 else "➡️ 正常量能"
        print(f"  {i}. {r['name']} — 5日 {p5['avg_return']:+.1f}%（{p5['up_ratio']:.0f}%普涨）{tag}")

    # Divergence / rotation signals
    strong_mom = [r for r in results if r["momentum_score"] > 5]
    weak_mom = [r for r in results if r["momentum_score"] < -3]
    expanding = [r for r in results if r["volume_trend"]["volume_ratio"] > 1.2]

    print()
    if strong_mom:
        names = "、".join([r["name"] for r in strong_mom])
        print(f"**📈 趋势强化板块（动量>5）：** {names}")
    if expanding:
        names = "、".join([r["name"] for r in expanding])
        print(f"**📊 资金流入板块（量比>1.2）：** {names}")
    if weak_mom:
        names = "、".join([r["name"] for r in weak_mom])
        print(f"**📉 回避板块（动量<-3）：** {names}")

    print(f"\n**⚠️ 4月业绩期提醒：** 优先选择已披露一季报的板块内个股，规避业绩未出的标的。")
    print(f"   板块内涨幅领先但量能萎缩的个股 → 可能是缩量诱多，需警惕。\n")

    print(f"{'─'*70}")
    print(f"> 数据时间：当前交易日")
    print(f"> 免责声明：板块分析结果仅供参考，不构成投资建议。\n")


# ─── CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：")
        print("  python3 sector.py rank            — 分析所有板块并排名")
        print("  python3 sector.py detail <板块名>  — 查看某个板块的详细成分股表现")
        print("  python3 sector.py list            — 列出所有配置的板块")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "list":
        sectors = load_sectors()
        print(f"\n已配置 {len(sectors)} 个板块：\n")
        for i, s in enumerate(sectors, 1):
            stocks = s.get("stocks", [])
            names = "、".join([x["name"] for x in stocks])
            print(f"  {i}. {s['name']}（{len(stocks)}只：{names}）")
        print()

    elif cmd == "rank":
        results = analyze_all_sectors()
        print_sector_report(results)

    elif cmd == "detail":
        if len(sys.argv) < 3:
            print("请指定板块名称，例如: python3 sector.py detail 锂矿/能源金属")
            sys.exit(1)

        target = sys.argv[2]
        sectors = load_sectors()
        found = None
        for s in sectors:
            if s["name"] == target:
                found = s
                break

        if not found:
            # Fuzzy match
            for s in sectors:
                if target in s["name"]:
                    found = s
                    break

        if not found:
            print(f"未找到板块: {target}")
            sys.exit(1)

        print(f"\n板块: {found['name']}")
        print(f"标签: {', '.join(found.get('tags', []))}")
        print(f"\n成分股表现:\n")
        print("| 股票 | 代码 | 5日涨跌 | 10日涨跌 | 20日涨跌 |")
        print("|------|------|---------|----------|----------|")

        for s in found["stocks"]:
            code = s["code"]
            p5 = _calc_returns([code], 5)
            p10 = _calc_returns([code], 10)
            p20 = _calc_returns([code], 20)
            print(f"| {s['name']} | {code} | {p5['avg_return']:+.1f}% | {p10['avg_return']:+.1f}% | {p20['avg_return']:+.1f}% |")

        perf = get_sector_performance(found)
        vol = perf["volume_trend"]
        print(f"\n板块合计: 5日 {perf['perf_5d']['avg_return']:+.1f}% | "
              f"20日 {perf['perf_20d']['avg_return']:+.1f}% | "
              f"量比 {vol['volume_ratio']:.2f}x\n")
