"""
模式 I：每日涨停复盘 + 概念板块排名。
数据源：akshare 涨停板池 + 概念板块排名。
"""

import json
import os
import sys
from datetime import datetime
from typing import Optional

import akshare as ak

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

# ─── 工具函数 ───

def _today_str() -> str:
    return datetime.now().strftime("%Y%m%d")


def _today_display() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ─── 数据获取 ───

def get_daily_limit_up_pool(date: Optional[str] = None) -> list[dict]:
    """获取当日涨停板池，过滤 ST/新股，返回结构化列表。"""
    date = date or _today_str()
    try:
        df = ak.stock_zt_pool_em(date=date)
    except Exception as e:
        print(f"⚠️ 涨停板池获取失败：{e}")
        return []

    if df is None or df.empty:
        return []

    stocks = []
    for _, row in df.iterrows():
        code = str(row.get("代码", "")).zfill(6)
        name = str(row.get("名称", ""))
        if "ST" in name or "*ST" in name:
            continue
        stocks.append({
            "code": code,
            "name": name,
            "price": float(row.get("最新价", 0)),
            "change_pct": float(row.get("涨跌幅", 0)),
            "turnover": float(row.get("换手率", 0)),
            "block_fund": float(row.get("封板资金", 0)),
            "first_time": str(row.get("首次封板时间", "")),
            "last_time": str(row.get("最后封板时间", "")),
            "break_count": int(row.get("炸板次数", 0)),
            "limit_stat": str(row.get("涨停统计", "")),
            "days_linked": int(row.get("连板数", 0)),
            "industry": str(row.get("所属行业", "")),
        })
    return stocks


def get_concept_board_ranking(top_n: int = 20) -> dict:
    """获取概念板块涨跌排名，过滤元概念。"""
    try:
        df = ak.stock_board_change_em()
    except Exception as e:
        print(f"⚠️ 概念板块排名获取失败：{e}")
        return {"top": [], "bottom": [], "all": []}

    if df is None or df.empty:
        return {"top": [], "bottom": [], "all": []}

    META_PATTERNS = [
        "融资融券", "深股通", "沪股通", "昨日", "标普道琼斯", "富时罗素",
        "MSCI", "HS300", "创业", "科创", "中证", "上证", "深圳", "国证",
        "转融券", "机构重仓", "基金重仓", "信托重仓", "QFII重仓",
        "券商重仓", "保险重仓", "社保重仓", "养老金", "陆股通",
        "低价股", "低市盈率", "高市盈率", "微盘股", "小盘", "中盘", "大盘",
        "破净", "预增", "预减", "预亏", "扣非", "持续增长",
        "首板", "二板", "三板", "四板", "五板", "六板", "连板",
        "新高", "新低", "活跃", "快讯", "热搜",
    ]
    def _is_meta(name: str) -> bool:
        for p in META_PATTERNS:
            if p in name:
                return True
        return False

    concepts = []
    for _, row in df.iterrows():
        name = str(row.get("板块名称", ""))
        if _is_meta(name):
            continue
        concepts.append({
            "name": name,
            "change_pct": float(row.get("涨跌幅", 0)),
            "net_flow": float(row.get("主力净流入", 0)),
        })

    concepts.sort(key=lambda x: x["change_pct"], reverse=True)
    return {
        "top": concepts[:top_n],
        "bottom": concepts[-top_n:][::-1],
        "all": concepts,
    }


def _group_stocks_by_industry(stocks: list[dict]) -> dict:
    """按行业对涨停股分组。"""
    groups: dict[str, list[dict]] = {}
    for s in stocks:
        industry = s.get("industry", "其他")
        if not industry:
            industry = "其他"
        if industry not in groups:
            groups[industry] = []
        groups[industry].append(s)
    return dict(sorted(groups.items(), key=lambda x: len(x[1]), reverse=True))


def _format_flow(amount: float) -> str:
    """格式化资金流向。"""
    if abs(amount) > 1e8:
        return f"{amount/1e8:+.1f}亿"
    return f"{amount/1e4:+.0f}万"


# ─── 输出格式化 ───

def print_daily_report(zt_stocks: list[dict], concept_ranking: dict):
    """输出每日复盘报告。"""
    print(f"\n## A股每日复盘报告（{_today_display()}）")
    print(f"\n> 涨停 {len(zt_stocks)} 只")

    # ─── 一、概念板块涨跌排名 ───
    print(f"\n### 一、概念板块涨跌排名")
    top = concept_ranking.get("top", [])
    bottom = concept_ranking.get("bottom", [])

    print(f"\n#### 🔥 涨幅居前 Top 20")
    print(f"| # | 概念 | 涨幅 | 主力净流入 |")
    print(f"|---|------|------|-----------|")
    for i, c in enumerate(top[:20]):
        print(f"| {i+1} | {c['name']} | {c['change_pct']:+.2f}% | {_format_flow(c['net_flow'])} |")

    print(f"\n#### 📉 跌幅居前 Bottom 20")
    print(f"| # | 概念 | 跌幅 | 主力净流入 |")
    print(f"|---|------|------|-----------|")
    for i, c in enumerate(bottom[:20]):
        print(f"| {i+1} | {c['name']} | {c['change_pct']:+.2f}% | {_format_flow(c['net_flow'])} |")

    # ─── 二、涨停个股按行业分组 ───
    print(f"\n### 二、涨停个股全景（{len(zt_stocks)}只）")
    industry_groups = _group_stocks_by_industry(zt_stocks)

    print(f"\n#### 按行业分类")
    for industry, stocks in industry_groups.items():
        print(f"\n##### {industry}（{len(stocks)}只）")
        print(f"| 股票 | 代码 | 封板 | 连板 | 炸板 | 换手 | 封板资金 |")
        print(f"|------|------|------|------|------|------|---------|")
        sorted_stocks = sorted(stocks, key=lambda x: x.get("days_linked", 0), reverse=True)
        for s in sorted_stocks:
            block_fund_str = f"{s['block_fund']/1e8:.2f}亿" if s['block_fund'] > 1e8 else f"{s['block_fund']/1e4:.0f}万"
            print(
                f"| {s['name']} | {s['code']} | "
                f"{s['first_time']} | "
                f"{s['days_linked']}板 | "
                f"{s['break_count']}次 | "
                f"{s['turnover']:.1f}% | "
                f"{block_fund_str} |"
            )

    # ─── 三、高连板标的 ───
    multi_board = [s for s in zt_stocks if s.get("days_linked", 0) >= 2]
    if multi_board:
        multi_board.sort(key=lambda x: x.get("days_linked", 0), reverse=True)
        print(f"\n### 三、连板标的（≥2板，{len(multi_board)}只）")
        print(f"| 股票 | 代码 | 连板 | 行业 | 换手 | 炸板 | 封板资金 |")
        print(f"|------|------|------|------|------|------|---------|")
        for s in multi_board:
            block_fund_str = f"{s['block_fund']/1e8:.2f}亿" if s['block_fund'] > 1e8 else f"{s['block_fund']/1e4:.0f}万"
            print(
                f"| {s['name']} | {s['code']} | "
                f"**{s['days_linked']}板** | "
                f"{s['industry']} | "
                f"{s['turnover']:.1f}% | "
                f"{s['break_count']}次 | "
                f"{block_fund_str} |"
            )

    # ─── 四、异常标的（频繁炸板/高换手） ───
    abnormal = [s for s in zt_stocks if s.get("break_count", 0) >= 3 or s.get("turnover", 0) >= 20]
    if abnormal:
        abnormal.sort(key=lambda x: x.get("break_count", 0), reverse=True)
        print(f"\n### 四、异常标的（频繁炸板或高换手，{len(abnormal)}只）")
        print(f"| 股票 | 代码 | 炸板 | 换手 | 连板 | 行业 |")
        print(f"|------|------|------|------|------|------|")
        for s in abnormal[:10]:
            print(
                f"| {s['name']} | {s['code']} | "
                f"{s['break_count']}次 | "
                f"{s['turnover']:.1f}% | "
                f"{s['days_linked']}板 | "
                f"{s['industry']} |"
            )

    print(f"\n---")
    print(f"*数据时间：{_today_display()} 交易日*")
    print(f"*免责声明：复盘分析仅供参考，不构成投资建议。*")


# ─── 主入口 ───

def run_daily_review(date: Optional[str] = None) -> dict:
    """模式 I 主入口：每日涨停复盘 + 概念板块排名。"""
    date = date or _today_str()
    print(f"📊 正在获取 {date} 涨停数据...")

    zt_stocks = get_daily_limit_up_pool(date)
    print(f"  涨停板池：{len(zt_stocks)} 只（已过滤ST/新股）")

    concept_ranking = get_concept_board_ranking(top_n=20)
    print(f"  概念板块：涨幅Top20 + 跌幅Bottom20")

    result = {
        "date": date,
        "zt_stocks": zt_stocks,
        "zt_count": len(zt_stocks),
        "concept_ranking": concept_ranking,
    }

    print_daily_report(zt_stocks, concept_ranking)
    return result


# ─── 板块持续性分析 ───

def _get_trading_dates(lookback: int = 10) -> list[str]:
    """获取最近N个交易日日期列表（YYYYMMDD格式），从近到远。"""
    dates = []
    today = datetime.now()
    cursor = today
    attempts = 0
    max_attempts = lookback * 3  # 最多跳跃3倍天数（含周末和长假）

    while len(dates) < lookback and attempts < max_attempts:
        d_str = cursor.strftime("%Y%m%d")
        # 尝试获取当日涨停板池，成功说明是交易日
        try:
            df = ak.stock_zt_pool_em(date=d_str)
            if df is not None and not df.empty:
                dates.append(d_str)
        except Exception:
            pass
        cursor = cursor - __import__('datetime').timedelta(days=1)
        attempts += 1

    return dates


def _score_by_count(limit_count: int) -> int:
    """涨停数→日得分。"""
    if limit_count >= 8:
        return 10
    elif limit_count >= 5:
        return 7
    elif limit_count >= 3:
        return 4
    elif limit_count >= 1:
        return 1
    return 0


def sector_persistence(lookback: int = 10, date: Optional[str] = None) -> dict:
    """板块持续性分析：回溯N个交易日，按行业分组评分。"""
    date = date or _today_str()
    trading_dates = _get_trading_dates(lookback)
    if not trading_dates:
        print("⚠️ 无法获取交易日列表")
        return {}

    print(f"📊 板块持续性分析（回溯{lookback}个交易日：{trading_dates[-1]} → {trading_dates[0]}）")

    # score_by_day[date][sector] = (score, stock_codes)
    score_by_day: dict[str, dict[str, tuple[int, list[str]]]] = {}
    # sector_scores[sector] = [score_day0, score_day1, ...]
    sector_scores: dict[str, list[int]] = {}
    # sector_stocks[sector] = {date: [codes]}
    sector_stocks: dict[str, dict[str, list[str]]] = {}

    for d in trading_dates:
        try:
            df = ak.stock_zt_pool_em(date=d)
        except Exception:
            continue
        if df is None or df.empty:
            continue

        day_data: dict[str, tuple[int, list[str]]] = {}
        for _, row in df.iterrows():
            name = str(row.get("名称", ""))
            if "ST" in name or "*ST" in name:
                continue
            industry = str(row.get("所属行业", "")) or "其他"
            code = str(row.get("代码", "")).zfill(6)
            if industry not in day_data:
                day_data[industry] = (0, [])
            cnt, codes = day_data[industry]
            codes.append(code)
            day_data[industry] = (cnt + 1, codes)

        score_by_day[d] = {}
        for industry, (cnt, codes) in day_data.items():
            s = _score_by_count(cnt)
            score_by_day[d][industry] = (s, codes)
            if industry not in sector_scores:
                sector_scores[industry] = []
            sector_scores[industry].append(s)
            if industry not in sector_stocks:
                sector_stocks[industry] = {}
            sector_stocks[industry][d] = codes

    # 补齐缺失天数
    for industry in sector_scores:
        while len(sector_scores[industry]) < len(trading_dates):
            sector_scores[industry].append(0)

    # 计算总分并按降序排列
    ranked = []
    for industry, scores in sector_scores.items():
        total = sum(scores)
        # 分段：今日(d0), 1-3日(d1-d3), 4-7日(d4-d7), 8-10日(d8-d10)
        n = len(scores)
        today_score = scores[0] if n > 0 else 0
        seg_1_3 = sum(scores[1:4]) if n > 1 else 0
        seg_4_7 = sum(scores[4:8]) if n > 4 else 0
        seg_8_10 = sum(scores[8:11]) if n > 8 else 0

        # 趋势判断：近期(0-2) vs 远期(7-9)
        recent = sum(scores[:3]) if n >= 3 else sum(scores)
        older = sum(scores[7:10]) if n >= 10 else (sum(scores[7:]) if n > 7 else 0)
        if older == 0 and recent > 0:
            trend = "🆕 新主线"
        elif recent > older * 1.5:
            trend = "↗ 加速"
        elif recent > older:
            trend = "↗ 走强"
        elif recent == older:
            trend = "→ 持平"
        elif recent > 0:
            trend = "↘ 减弱"
        else:
            trend = "✗ 消失"

        # 存活率：5天前的涨停股，今天还在涨停的有多少
        survival_rate = None
        if n >= 5 and scores[0] > 0:
            d5 = trading_dates[4] if len(trading_dates) > 4 else None  # 5天前
            d0 = trading_dates[0]
            if d5 and d5 in sector_stocks.get(industry, {}) and d0 in sector_stocks.get(industry, {}):
                old_codes = set(sector_stocks[industry][d5])
                new_codes = set(sector_stocks[industry][d0])
                if old_codes:
                    survived = old_codes & new_codes
                    survival_rate = len(survived) / len(old_codes)

        ranked.append({
            "industry": industry,
            "total": total,
            "today": today_score,
            "seg_1_3": seg_1_3,
            "seg_4_7": seg_4_7,
            "seg_8_10": seg_8_10,
            "trend": trend,
            "survival_rate": survival_rate,
            "scores": scores[:lookback],
            "active_days": sum(1 for s in scores if s > 0),
        })

    ranked.sort(key=lambda x: x["total"], reverse=True)

    # 只保留总分 > 0 的板块
    ranked = [r for r in ranked if r["total"] > 0]

    result = {
        "date": date,
        "trading_dates": trading_dates,
        "lookback": lookback,
        "sectors": ranked,
    }

    print_sector_persistence(result)
    return result


def print_sector_persistence(result: dict, top_n: int = 20):
    """格式化输出板块持续性分析报告。"""
    if not result or not result.get("sectors"):
        print("无板块持续性数据。")
        return

    all_sectors = result["sectors"]
    display = all_sectors[:top_n]

    trading_dates = result.get("trading_dates", [])
    date_range = f"{trading_dates[-1][4:6]}/{trading_dates[-1][6:]}" + \
                 f" → {trading_dates[0][4:6]}/{trading_dates[0][6:]}" if len(trading_dates) >= 2 else ""

    print(f"\n### 板块持续性分析（近{result['lookback']}交易日：{date_range}）")
    print()
    print(f"| # | 板块 | 10日总分 | 今日 | 1-3日 | 4-7日 | 8-10日 | 活跃天数 | 趋势 | 5日存活率 |")
    print(f"|---|------|---------|------|-------|-------|--------|---------|------|----------|")

    for i, s in enumerate(display):
        surv_str = f"{s['survival_rate']:.0%}" if s['survival_rate'] is not None else "—"
        print(
            f"| {i+1} | {s['industry']} | "
            f"**{s['total']}** | "
            f"{s['today']} | "
            f"{s['seg_1_3']} | "
            f"{s['seg_4_7']} | "
            f"{s['seg_8_10']} | "
            f"{s['active_days']}天 | "
            f"{s['trend']} | "
            f"{surv_str} |"
        )

    # 主线判定（基于全部板块，不只是Top N）
    main_line = [s for s in all_sectors if "新主线" in s["trend"] or "加速" in s["trend"]]
    weakening = [s for s in all_sectors if "减弱" in s["trend"] or "消失" in s["trend"]]
    if main_line:
        names = "、".join(s["industry"] for s in main_line[:3])
        print(f"\n**当前主线：** {names}")
    if weakening:
        names = "、".join(s["industry"] for s in weakening[:3])
        print(f"**退潮板块：** {names}")

    print(f"\n> 评分规则：≥8只=10分，5-7只=7分，3-4只=4分，1-2只=1分。存活率=5日前涨停股今日仍涨停比例。")

    # 汇总摘要
    total_sectors = len(all_sectors)
    active_sectors = sum(1 for s in all_sectors if s["active_days"] >= 3)
    total_omitted = total_sectors - len(display)
    omitted_note = f" | 仅显示 Top {top_n}" if total_omitted > 0 else ""
    print(f"> 共 {total_sectors} 个板块出现过涨停 | 持续活跃(≥3天) {active_sectors} 个{omitted_note}")


if __name__ == "__main__":
    # 先跑每日复盘
    result = run_daily_review()
    print("\n--- JSON ---")
    summary = {
        "zt_count": result.get("zt_count", 0),
        "top_concept": result.get("concept_ranking", {}).get("top", [{}])[0].get("name", "") if result.get("concept_ranking", {}).get("top") else "",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # 再跑板块持续性
    print("\n" + "="*60)
    p_result = sector_persistence(lookback=10)
    if p_result:
        print("\n--- PERSISTENCE JSON ---")
        print(json.dumps({
            "lookback": p_result["lookback"],
            "trading_dates": p_result["trading_dates"],
            "sector_count": len(p_result["sectors"]),
        }, ensure_ascii=False, indent=2))
