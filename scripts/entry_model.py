"""
模式 H：三维入场评估 — 资金 + 技术形态（含价托/黄金三角）+ 故事
"""

from __future__ import annotations

import json
import os
from typing import Optional

import yaml

from stock import (
    _get_prefix,
    get_a_share_financials,
    get_kline_data,
    get_technical_dict,
    comprehensive_judge_dict,
    detect_golden_triangle,
    analyze_shareholder_trend,
)
from llm_analysis import analyze_industry_chain, _call_llm, _parse_json_response

# 宏观风险配置文件路径
_MACRO_RISKS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "macro_risks.yaml"
)

# 默认权重：中线偏均衡
DEFAULT_WEIGHTS = {"capital": 0.35, "technical": 0.35, "narrative": 0.30}


def get_macro_risk_penalty() -> dict:
    """
    宏观风险过滤器：读取 macro_risks.yaml 并自动检测美10年期国债收益率。
    返回 {total_penalty, evidence, details}
    """
    penalty = 0
    evidence = []
    details = []

    try:
        with open(_MACRO_RISKS_PATH) as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        cfg = {}

    max_penalty = cfg.get("max_total_penalty", 20)

    # --- 定性风险（通用遍历，按 yaml 中的 active/penalty/label 自动处理） ---
    qualitative_risks = ["war_risk", "tariff_risk", "us_iran_risk"]
    for key in qualitative_risks:
        risk = cfg.get(key, {})
        if risk.get("active"):
            p = risk.get("penalty", 6)
            label = risk.get("label", key)
            penalty += p
            evidence.append(f"⚠️ {label}：-{p}分")
            details.append({"risk": label, "penalty": p, "source": "manual"})

    # --- 定量：美10年期国债收益率 ---
    us10y = cfg.get("us10y_yield", {})
    if us10y.get("enabled", True):
        try:
            import yfinance as yf
            tnx = yf.Ticker("^TNX")
            hist = tnx.history(period="5d")
            if not hist.empty:
                yield_val = float(hist["Close"].iloc[-1])
                warn_threshold = us10y.get("threshold_warn", 4.5)
                severe_threshold = us10y.get("threshold_severe", 5.0)

                if yield_val > severe_threshold:
                    p = us10y.get("penalty_severe", 10)
                    label_tpl = us10y.get("label", "美10年期国债收益率{value}%")
                    label = label_tpl.format(value=round(yield_val, 2))
                    penalty += p
                    evidence.append(f"⚠️ {label} > {severe_threshold}%（严重）：-{p}分")
                    details.append({"risk": label, "penalty": p, "value": yield_val, "source": "yfinance"})
                elif yield_val > warn_threshold:
                    p = us10y.get("penalty_warn", 6)
                    label_tpl = us10y.get("label", "美10年期国债收益率{value}%")
                    label = label_tpl.format(value=round(yield_val, 2))
                    penalty += p
                    evidence.append(f"⚠️ {label} > {warn_threshold}%（警戒）：-{p}分")
                    details.append({"risk": label, "penalty": p, "value": yield_val, "source": "yfinance"})
                else:
                    details.append({"risk": "美10年期国债收益率", "value": yield_val, "penalty": 0, "source": "yfinance"})
            else:
                evidence.append("美10Y国债数据未获取（跳过）")
        except Exception as e:
            evidence.append(f"美10Y国债检测失败：{e}")

    # 上限封顶
    actual = min(penalty, max_penalty)
    if penalty > max_penalty:
        evidence.append(f"宏观扣分触达上限 {max_penalty} 分（原始 {penalty} 分）")

    return {
        "total_penalty": actual,
        "raw_penalty": penalty,
        "max_penalty": max_penalty,
        "evidence": evidence,
        "details": details,
        "has_risk": actual > 0,
    }


_NARRATIVE_SCORE_SYSTEM = """你是A股短线/波段交易研究员。根据产业链与基本面信息，对「投资故事」进行0-100打分。

输出纯JSON：
{
  "logic_clarity": 0-100,
  "catalyst_timing": 0-100,
  "supply_demand": 0-100,
  "earnings_validation": 0-100,
  "risk_level": 0-100,
  "summary": "一句话故事结论",
  "core_story": "30字内核心故事",
  "risks": ["风险1", "风险2"]
}

说明：risk_level 越高表示风险越低（故事越安全）。只输出JSON。"""


def _market_for_akshare(symbol: str) -> str:
    return "sh" if _get_prefix(symbol) == "sh" else "sz"


def get_capital_flow_dict(symbol: str, days: int = 10) -> dict:
    """
    个股资金流向（东方财富 / akshare）。
  """
    result = {
        "available": False,
        "days": days,
        "positive_days_5": 0,
        "positive_days_10": 0,
        "main_net_5d": 0.0,
        "main_net_10d": 0.0,
        "main_ratio_5d_avg": 0.0,
        "latest_main_net": 0.0,
        "latest_main_ratio": 0.0,
        "error": None,
    }
    try:
        import akshare as ak

        market = _market_for_akshare(symbol)
        df = ak.stock_individual_fund_flow(stock=symbol, market=market)
        if df is None or df.empty:
            result["error"] = "无资金流向数据"
            return result

        col_net = "主力净流入-净额"
        col_ratio = "主力净流入-净占比"
        if col_net not in df.columns:
            result["error"] = "数据列缺失"
            return result

        tail = df.tail(days)
        nets = []
        ratios = []
        for _, row in tail.iterrows():
            try:
                nets.append(float(row[col_net]))
            except (TypeError, ValueError):
                nets.append(0.0)
            try:
                ratios.append(float(row[col_ratio]))
            except (TypeError, ValueError):
                ratios.append(0.0)

        result["available"] = True
        result["main_net_5d"] = sum(nets[-5:])
        result["main_net_10d"] = sum(nets)
        result["positive_days_5"] = sum(1 for x in nets[-5:] if x > 0)
        result["positive_days_10"] = sum(1 for x in nets if x > 0)
        result["main_ratio_5d_avg"] = round(sum(ratios[-5:]) / min(5, len(ratios)), 2) if ratios else 0
        result["latest_main_net"] = nets[-1] if nets else 0
        result["latest_main_ratio"] = ratios[-1] if ratios else 0
    except Exception as e:
        result["error"] = str(e)
    return result


def capital_score(symbol: str) -> dict:
    """资金维度 0-100。"""
    flow = get_capital_flow_dict(symbol)
    holder = analyze_shareholder_trend(symbol)
    tech = get_technical_dict(symbol)

    points = 0.0
    evidence = []

    if flow.get("available"):
        pd5 = flow["positive_days_5"]
        pd10 = flow["positive_days_10"]
        points += pd5 * 6  # max 30
        points += pd10 * 2  # max 20
        evidence.append(f"近5日主力净流入为正 {pd5}/5 天")
        evidence.append(f"近10日主力净流入为正 {pd10}/10 天")

        if flow["main_net_5d"] > 0:
            points += 10
            evidence.append(f"5日主力净流入合计 {flow['main_net_5d']/1e8:.2f} 亿（正）")
        elif flow["main_net_5d"] < 0:
            points -= 5
            evidence.append(f"5日主力净流出 {abs(flow['main_net_5d'])/1e8:.2f} 亿")

        if flow["main_ratio_5d_avg"] > 5:
            points += 8
            evidence.append(f"5日平均主力净占比 {flow['main_ratio_5d_avg']}%（偏强）")
        elif flow["main_ratio_5d_avg"] < -5:
            points -= 5
            evidence.append(f"5日平均主力净占比 {flow['main_ratio_5d_avg']}%（偏弱）")
    else:
        evidence.append(f"主力资金流：{flow.get('error', '未获取')}")

    # 量价：涨 + 放量 作为资金确认
    klines = get_kline_data(symbol, 10)
    if len(klines) >= 6:
        klines = [k[:6] for k in klines]
        last = klines[-1]
        prev5_vol = sum(float(k[5]) for k in klines[-6:-1]) / 5
        vol = float(last[5])
        chg = tech.get("change_pct", 0)
        if chg > 0 and prev5_vol > 0 and vol > prev5_vol * 1.1:
            points += 10
            evidence.append("今日上涨且成交量明显放大")
        elif chg < 0 and vol > prev5_vol * 1.2:
            points -= 8
            evidence.append("下跌放量，资金可能出逃")

    # 筹码（季度慢变量，权重较低）
    if not holder.get("error"):
        sig = holder.get("signal", "")
        if "偏多" in sig:
            points += 12
            evidence.append(f"筹码：{holder.get('trend')}（{sig}）")
        elif "偏空" in sig:
            points -= 8
            evidence.append(f"筹码：{holder.get('trend')}（{sig}）")
        else:
            points += 3
            evidence.append(f"筹码：{holder.get('trend', '中性')}")

    score = max(0, min(100, round(points)))
    if score >= 70:
        label = "资金偏多"
    elif score >= 45:
        label = "资金中性"
    else:
        label = "资金偏空"

    judgment = "；".join(evidence) if evidence else label

    return {
        "score": score,
        "label": label,
        "judgment": judgment,
        "flow": flow,
        "holder": {k: holder.get(k) for k in ("trend", "signal", "interpretation") if k in holder},
        "evidence": evidence,
    }


def jiatuo_bonus_info(triangle: dict) -> dict:
    """
    价托加分与判断文案（以 10日上穿20日 完成为准）。
    - 10 日内完成：技术分 +6
    - 20 日内完成：技术分 +4
    - 超过 20 日：不加分，注明距今日天数
    """
    cross_10_20 = triangle.get("cross_10_20_date")
    days = triangle.get("days_since_complete")

    if triangle.get("forming"):
        return {
            "has_jiatuo": False,
            "jiatuo_forming": True,
            "bonus": 0,
            "days_since_10_20": None,
            "judgment_part": "价托：形成中（5已上穿10，三角未完成，不加分）",
        }

    if not cross_10_20 or days is None:
        return {
            "has_jiatuo": False,
            "jiatuo_forming": False,
            "bonus": 0,
            "days_since_10_20": None,
            "judgment_part": "价托：无",
        }

    # 黄金三角已完成（有价托）
    if days <= 10:
        bonus = 6
        time_desc = f"10日内形成（10日上穿20日距今日 {days} 日，技术分+6）"
    elif days <= 20:
        bonus = 4
        time_desc = f"20日内形成（10日上穿20日距今日 {days} 日，技术分+4）"
    else:
        bonus = 0
        time_desc = f"价托形成时间距离目前时间较远（10日上穿20日距今日 {days} 日，不加分）"

    valid = triangle.get("formed", False)
    if valid:
        state = "有价托且结构有效"
    elif triangle.get("bullish_alignment"):
        state = "有价托（多头排列，股价需确认5日线）"
    else:
        state = "有价托但结构走弱"

    return {
        "has_jiatuo": True,
        "jiatuo_forming": False,
        "bonus": bonus,
        "days_since_10_20": days,
        "cross_10_20_date": cross_10_20,
        "judgment_part": f"价托：{state}；{time_desc}",
    }


def _build_technical_judgment(
    base_score: int,
    judge_items: dict,
    triangle: dict,
    jiatuo: dict,
    tech_pts: int,
    base_pts: int,
) -> str:
    """组装技术维度「判断」栏完整文案。"""
    parts = [f"综合技术 {base_score}/7 项符合（基础 {base_pts} 分）"]
    parts.append(jiatuo["judgment_part"])
    if jiatuo["bonus"] > 0:
        parts.append(f"价托加分 +{jiatuo['bonus']}")
    # 简要技术面
    flags = []
    if judge_items.get("均线多头排列"):
        flags.append("多头排列")
    if judge_items.get("均线向上发散"):
        flags.append("均线发散")
    if judge_items.get("上涨放量"):
        flags.append("上涨放量")
    if judge_items.get("分时股价在分时均线上方") is False:
        flags.append("分时在均价下方")
    if judge_items.get("近20日阶段新高") is False and base_score >= 4:
        flags.append("未创20日新高")
    if flags:
        parts.append("；".join(flags))
    return "。".join(parts) + f"。技术合计 {tech_pts} 分"


def technical_score(symbol: str, profit: bool = True) -> dict:
    """技术维度 0-100：7项基础（0-90）+ 价托时间加分（0/4/6），满分96。"""
    judge = comprehensive_judge_dict(symbol, profit=profit)
    triangle = judge.get("golden_triangle") or detect_golden_triangle(symbol)
    items = judge.get("items", {})
    base_score = judge.get("score", 0)
    jiatuo = jiatuo_bonus_info(triangle)

    base_pts = round(base_score / 7 * 90)
    tech_pts = base_pts + jiatuo["bonus"]
    tech_pts = max(0, min(100, tech_pts))

    judgment = _build_technical_judgment(
        base_score, items, triangle, jiatuo, tech_pts, base_pts
    )

    evidence = [judgment]
    if triangle.get("interpretation"):
        evidence.append(triangle["interpretation"])

    display_items = dict(items)
    display_items["价托/黄金三角"] = jiatuo["has_jiatuo"]

    if tech_pts >= 70:
        label = "技术强势"
    elif tech_pts >= 45:
        label = "技术中性"
    else:
        label = "技术偏弱"

    return {
        "score": tech_pts,
        "label": label,
        "judgment": judgment,
        "base_pts": base_pts,
        "jiatuo_bonus": jiatuo["bonus"],
        "jiatuo": jiatuo,
        "judge": judge,
        "golden_triangle": triangle,
        "items": display_items,
        "evidence": evidence,
    }


def narrative_score(
    stock_name: str,
    stock_code: str,
    main_business: str = "",
    profit_status: str = "",
    price_change_pct: float = 0.0,
    chain_analysis: Optional[dict] = None,
    use_llm: bool = True,
) -> dict:
    """故事维度 0-100。优先用已有产业链分析，否则调 LLM。"""
    if chain_analysis is None and use_llm:
        chain_analysis = analyze_industry_chain(
            stock_name=stock_name,
            stock_code=stock_code,
            main_business=main_business or "未知",
            profit_status=profit_status or "未知",
            price_change_pct=price_change_pct,
        )

    chain = chain_analysis or {}
    core_driver = chain.get("core_driver", "")
    logic_chain = chain.get("logic_chain", "")
    supply = chain.get("supply_demand_status", "")

    llm_sub = None
    if use_llm and (core_driver or logic_chain):
        user = f"""公司：{stock_name}（{stock_code})
主营业务：{main_business}
盈利：{profit_status}
涨跌幅：{price_change_pct}%
产业链定位：{chain.get('chain_position', '')}
核心驱动：{core_driver}
供需：{supply}
逻辑链：{logic_chain}"""
        raw = _call_llm(_NARRATIVE_SCORE_SYSTEM, user)
        llm_sub = _parse_json_response(raw)

    if llm_sub:
        dims = [
            llm_sub.get("logic_clarity", 50),
            llm_sub.get("catalyst_timing", 50),
            llm_sub.get("supply_demand", 50),
            llm_sub.get("earnings_validation", 50),
            llm_sub.get("risk_level", 50),
        ]
        try:
            dims = [max(0, min(100, float(x))) for x in dims]
        except (TypeError, ValueError):
            dims = [50] * 5
        score = round(sum(dims) / len(dims))
        summary = llm_sub.get("summary", core_driver)
        core_story = llm_sub.get("core_story", core_driver[:30])
        risks = llm_sub.get("risks", [])
    else:
        # 规则兜底
        score = 50
        if core_driver:
            score += 15
        if supply and any(w in supply for w in ("涨价", "缺货", "紧张", "扩张")):
            score += 10
        if profit_status and "盈" in str(profit_status):
            score += 10
        score = max(0, min(100, score))
        summary = core_driver or "故事信息不足"
        core_story = (core_driver or "待补充")[:30]
        risks = []

    if score >= 70:
        label = "故事强"
    elif score >= 45:
        label = "故事一般"
    else:
        label = "故事弱"

    judgment = summary if summary else label

    return {
        "score": score,
        "label": label,
        "judgment": judgment,
        "chain_analysis": chain,
        "summary": summary,
        "core_story": core_story,
        "risks": risks,
        "evidence": [summary] if summary else ["未能获取故事评分"],
    }


def _build_macro_info(macro: dict) -> dict:
    """从宏观检测结果构建风险提示文本和市场环境分析。"""
    if not macro:
        return {"risk_text": "", "regime": None}

    # 风险文本
    lines = []
    for d in macro.get("details", []):
        if d.get("penalty", 0) > 0:
            lines.append(d.get("risk", ""))
    risk_text = "；".join(lines) if lines else ""

    # 提取美10年期收益率数值
    yield_val = None
    for d in macro.get("details", []):
        if d.get("source") == "yfinance" and d.get("value") is not None:
            yield_val = d["value"]
            break

    regime = _get_market_regime(yield_val) if yield_val is not None else None
    return {"risk_text": risk_text, "regime": regime}


def _get_market_regime(yield_val: float) -> dict:
    """根据美10年期国债收益率判断市场环境区间。"""
    if yield_val <= 3.5:
        return {
            "level": "low",
            "label": "低利率 / 宽松环境（≤3.5%）",
            "risk_degree": "宽松",
            "market_traits": "钱便宜、流动性泛滥、成长股牛市",
            "strong_sectors": ["科技成长（QQQ、AI、半导体）", "小盘成长", "新能源车", "REITs", "公用事业"],
            "weak_sectors": ["银行/保险（净息差收窄）", "高股息（吸引力低）"],
            "position": "7–9 成（偏成长）",
            "allocation": "QQQ 40% + 半导体 20% + 小盘 15% + 现金 25%",
        }
    elif yield_val <= 4.25:
        return {
            "level": "neutral",
            "label": "中性区间（3.5%–4.25%）",
            "risk_degree": "中性",
            "market_traits": "经济不错、利率不高、板块轮动",
            "strong_sectors": ["大盘价值+成长均衡", "医药", "必需消费", "部分金融"],
            "weak_sectors": ["纯高估值小票", "高负债公用事业"],
            "position": "6–7 成（均衡）",
            "allocation": "标普500 30% + 医药 20% + 金融 15% + 现金 35%",
        }
    elif yield_val <= 4.75:
        return {
            "level": "caution",
            "label": "警惕区间（4.25%–4.75%）",
            "risk_degree": "警惕",
            "market_traits": "利率抬升、成长开始承压、价值走强",
            "strong_sectors": ["银行/保险（XLF）", "能源", "高股息", "黄金"],
            "weak_sectors": ["AI", "半导体", "未盈利SaaS", "REITs", "公用事业"],
            "position": "4–5 成（降成长、加价值/固收）",
            "allocation": "高股息 20% + 金融 15% + 能源 10% + 短债 40% + 现金 15%",
        }
    elif yield_val <= 5.25:
        return {
            "level": "danger",
            "label": "高危区间（4.75%–5.25%）",
            "risk_degree": "高危",
            "market_traits": "估值重定价、资金从股市抽离、回调高发",
            "strong_sectors": ["短债/美债", "黄金", "现金", "极少数高现金流巨头（AAPL等）"],
            "weak_sectors": ["几乎所有成长", "AI", "半导体", "REITs", "公用事业"],
            "position": "2–3 成（轻仓、防御为主）",
            "allocation": "现金 30% + 10年期美债 40% + 黄金 10% + 龙头价值 20%",
        }
    else:
        return {
            "level": "extreme",
            "label": "极端风险（≥5.25%）",
            "risk_degree": "极端风险",
            "market_traits": "融资成本爆炸、衰退预期强、波动率飙升",
            "strong_sectors": ["现金", "短债", "黄金", "防御性必需消费"],
            "weak_sectors": ["全板块承压，成长尤甚"],
            "position": "0–2 成（观望为主）",
            "allocation": "现金 50% + 短债 40% + 黄金 10%",
        }


def composite_verdict(
    capital: dict,
    technical: dict,
    narrative: dict,
    weights: Optional[dict] = None,
    macro_penalty: Optional[dict] = None,
) -> dict:
    w = weights or DEFAULT_WEIGHTS
    total = round(
        capital["score"] * w["capital"]
        + technical["score"] * w["technical"]
        + narrative["score"] * w["narrative"]
    )
    macro = macro_penalty or {}
    c_ok = capital["score"] >= 55
    t_ok = technical["score"] >= 55
    n_ok = narrative["score"] >= 55
    resonance = sum([c_ok, t_ok, n_ok])

    tri = technical.get("golden_triangle", {})
    if resonance == 3:
        verdict = "强烈关注"
        action = "三维共振，可考虑分批介入；优先等回踩5日线或价托区域不破确认。"
    elif resonance == 2:
        verdict = "值得关注"
        weak = []
        if not c_ok:
            weak.append("资金")
        if not t_ok:
            weak.append("技术")
        if not n_ok:
            weak.append("故事")
        action = f"两维共振，{'/'.join(weak)}偏弱，宜小仓或等待{'/'.join(weak)}改善。"
    elif resonance == 1 and n_ok and not t_ok:
        verdict = "好故事待验证"
        action = "故事尚可但资金/技术未确认，适合观察不买。"
    elif resonance == 1 and t_ok and tri.get("formed"):
        verdict = "技术先行"
        action = "价托或技术形态良好，需资金与故事后续配合再加仓。"
    else:
        verdict = "暂不建议"
        action = "三维未共振，不建议重仓介入。"

    if total >= 75:
        grade = "A"
    elif total >= 60:
        grade = "B"
    elif total >= 45:
        grade = "C"
    else:
        grade = "D"

    return {
        "total_score": total,
        "grade": grade,
        "verdict": verdict,
        "action": action,
        "resonance": resonance,
        "resonance_tags": {
            "资金": "✅" if c_ok else "❌",
            "技术": "✅" if t_ok else "❌",
            "故事": "✅" if n_ok else "❌",
        },
        "weights": w,
        "macro_risk_text": _build_macro_info(macro).get("risk_text", ""),
        "macro_regime": _build_macro_info(macro).get("regime"),
    }


def analyze_entry_signal(
    symbol: str,
    stock_name: str = "",
    profit: Optional[bool] = None,
    main_business: str = "",
    price_change_pct: Optional[float] = None,
    chain_analysis: Optional[dict] = None,
    use_llm_narrative: bool = True,
    weights: Optional[dict] = None,
) -> dict:
    """
    模式 H 主入口：返回资金/技术/故事三维评分及综合结论。
    """
    symbol = str(symbol).zfill(6) if symbol.isdigit() else symbol
    fin = get_a_share_financials(symbol)
    tech_q = get_technical_dict(symbol)

    if not stock_name:
        stock_name = tech_q.get("name") or fin.get("name", symbol)
    if profit is None:
        profit = fin.get("profit", True)
    if price_change_pct is None:
        price_change_pct = tech_q.get("change_pct", 0.0)
    if not main_business and fin.get("available"):
        annual = fin.get("annual") or {}
        main_business = str(annual.get("revenue", "")).strip()

    profit_status = "盈利" if profit else "亏损"
    cap = capital_score(symbol)
    tech = technical_score(symbol, profit=profit)
    narr = narrative_score(
        stock_name=stock_name,
        stock_code=symbol,
        main_business=main_business,
        profit_status=profit_status,
        price_change_pct=price_change_pct,
        chain_analysis=chain_analysis,
        use_llm=use_llm_narrative,
    )
    macro = get_macro_risk_penalty()
    composite = composite_verdict(cap, tech, narr, weights=weights, macro_penalty=macro)

    return {
        "symbol": symbol,
        "name": stock_name,
        "price": tech_q.get("price"),
        "change_pct": price_change_pct,
        "capital": cap,
        "technical": tech,
        "narrative": narr,
        "composite": composite,
        "macro": macro,
    }


def print_entry_report(result: dict):
    """打印三维入场评估报告。"""
    name = result.get("name", "")
    code = result.get("symbol", "")
    comp = result.get("composite", {})
    cap = result.get("capital", {})
    tech = result.get("technical", {})
    narr = result.get("narrative", {})
    tri = tech.get("golden_triangle", {})
    jiatuo = tech.get("jiatuo") or jiatuo_bonus_info(tri)
    if jiatuo.get("has_jiatuo"):
        jiatuo_line = "有"
        if jiatuo.get("bonus"):
            jiatuo_line += f"（10日上穿20日距今日 {jiatuo.get('days_since_10_20')} 日，技术+{jiatuo['bonus']}分）"
        else:
            jiatuo_line += f"（10日上穿20日距今日 {jiatuo.get('days_since_10_20')} 日，超时未加分）"
    elif jiatuo.get("jiatuo_forming"):
        jiatuo_line = "形成中"
    else:
        jiatuo_line = "无"

    print(f"\n## {name}（{code}）三维入场评估 · 模式H")
    print(f"\n**现价：** {result.get('price')}  **涨跌幅：** {result.get('change_pct')}%")
    print(f"\n### 综合结论")
    print(f"- **价托有无：** {jiatuo_line}")
    print(f"- **总分：** {comp.get('total_score')}/100（{comp.get('grade')}级）")
    print(f"- **判定：** {comp.get('verdict')}")
    print(f"- **共振：** {comp.get('resonance')}/3 — 资金{comp['resonance_tags']['资金']} 技术{comp['resonance_tags']['技术']} 故事{comp['resonance_tags']['故事']}")
    print(f"- **建议：** {comp.get('action')}")

    print(f"\n### 三维得分")
    print(f"| 维度 | 得分 | 判断 |")
    print(f"|------|------|------|")
    print(f"| 资金 | {cap.get('score')}/100 | {cap.get('judgment', cap.get('label', ''))} |")
    print(f"| 技术 | {tech.get('score')}/100 | {tech.get('judgment', tech.get('label', ''))} |")
    print(f"| 故事 | {narr.get('score')}/100 | {narr.get('judgment', narr.get('label', ''))} |")

    print(f"\n### 价托 / 黄金三角")
    print(f"- **有无价托：** {'有 ✅' if jiatuo.get('has_jiatuo') else ('形成中 ⏳' if jiatuo.get('jiatuo_forming') else '无 ❌')}")
    print(f"- **脚本标签：** {tri.get('label')}")
    print(f"- **5→10：** {tri.get('cross_5_10_date') or '—'}  **5→20：** {tri.get('cross_5_20_date') or '—'}  **10→20：** {tri.get('cross_10_20_date') or '—'}")
    if jiatuo.get("days_since_10_20") is not None:
        print(f"- **10日上穿20日距今日：** {jiatuo['days_since_10_20']} 个交易日")
    print(f"- **价托技术加分：** +{jiatuo.get('bonus', 0)} 分")
    print(f"- **量能配合：** {'是' if tri.get('volume_confirm') else '否'}")
    print(f"- {tri.get('interpretation', '')}")

    print(f"\n### 资金证据")
    for e in cap.get("evidence", []):
        print(f"- {e}")

    print(f"\n### 技术项（含价托）")
    for k, v in tech.get("items", {}).items():
        extra = f" — {tri.get('label', '')}" if k == "价托/黄金三角" else ""
        print(f"- {k}：{'✅' if v else '❌'}{extra}")

    print(f"\n### 故事")
    print(f"- **核心故事：** {narr.get('core_story', '')}")
    print(f"- **摘要：** {narr.get('summary', '')}")
    for r in narr.get("risks", [])[:3]:
        print(f"- ⚠️ {r}")

    risk_text = comp.get("macro_risk_text", "")
    regime = comp.get("macro_regime")
    if regime:
        print(f"\n### 宏观风险")
        if risk_text:
            print(f"- **当前风险：** {risk_text}")
        print(f"- **市场环境：** 美10年期国债收益率 {regime['label']}")
        print(f"- **风险程度：** {regime['risk_degree']}")
        print(f"- **市场特征：** {regime['market_traits']}")
        strong = "、".join(regime['strong_sectors'])
        weak = "、".join(regime['weak_sectors'])
        print(f"- **强势板块：** {strong}")
        print(f"- **弱势板块：** {weak}")
        print(f"- **建议仓位：** {regime['position']}")
        print(f"- **配置举例：** {regime['allocation']}")
    elif risk_text:
        print(f"\n### 宏观风险")
        print(f"- {risk_text}")

    print("\n---\n*免责声明：三维评估仅供参考，不构成投资建议。*\n")


if __name__ == "__main__":
    import sys

    code = sys.argv[1] if len(sys.argv) > 1 else "600519"
    r = analyze_entry_signal(code, use_llm_narrative=False)
    print_entry_report(r)
    print("\n--- JSON ---")
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
