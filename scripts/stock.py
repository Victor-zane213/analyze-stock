import requests
import pandas as pd

def _get_prefix(symbol: str) -> str:
    """根据股票代码判断沪深市场前缀"""
    return "sh" if symbol.startswith(("6", "9")) else "sz"

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def get_a_share_financials(symbol: str) -> dict:
    """
    Fetch A-share financial data via akshare (同花顺财务摘要).
    Replaces ~3 WebSearch calls with one local API call (~1-2s).

    Returns dict with latest annual + latest quarter data:
      - eps, bvps, revenue, net_profit, gross_margin, net_margin
      - roe, debt_ratio, growth_rate (net profit YoY)
      - ocf_per_share, profit (bool)
    """
    try:
        import akshare as ak

        df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按年度")
        if df.empty:
            return {"available": False, "reason": "akshare 未返回数据"}

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else None

        eps = float(latest["基本每股收益"]) if latest.get("基本每股收益") else 0
        bvps = float(latest["每股净资产"]) if latest.get("每股净资产") else 0
        revenue = latest.get("营业总收入", "")
        net_profit = latest.get("净利润", "")
        gross_margin_raw = latest.get("销售毛利率", "")
        net_margin_raw = latest.get("销售净利率", "")
        roe_raw = latest.get("净资产收益率", "")
        debt_ratio_raw = latest.get("资产负债率", "")
        ocf = float(latest["每股经营现金流"]) if latest.get("每股经营现金流") else 0

        # Parse percentage strings
        def _pct(s):
            if not s:
                return 0.0
            try:
                return float(str(s).replace("%", ""))
            except (ValueError, TypeError):
                return 0.0

        gross_margin = _pct(gross_margin_raw)
        net_margin = _pct(net_margin_raw)
        roe = _pct(roe_raw)
        debt_ratio = _pct(debt_ratio_raw)

        # Growth rate
        growth_rate = 0.0
        if prev is not None:
            growth_str = latest.get("净利润同比增长率", "")
            if growth_str:
                try:
                    growth_rate = float(str(growth_str).replace("%", ""))
                except (ValueError, TypeError):
                    pass
        if growth_rate == 0 and prev is not None:
            prev_np_raw = prev.get("净利润", "")
            if prev_np_raw and isinstance(prev_np_raw, (int, float)) and prev_np_raw > 0:
                curr_np = float(net_profit) if isinstance(net_profit, (int, float)) else 0
                if curr_np > 0:
                    growth_rate = round((curr_np - prev_np_raw) / prev_np_raw * 100, 1)

        profit = eps > 0

        # Try latest quarter
        q_df = None
        try:
            q_df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按单季度")
        except Exception:
            pass

        q_data = {}
        if q_df is not None and not q_df.empty:
            q_latest = q_df.iloc[-1]
            q_data = {
                "period": str(q_latest.get("报告期", "")),
                "revenue": str(q_latest.get("营业总收入", "")),
                "net_profit": str(q_latest.get("净利润", "")),
                "growth_pct": str(q_latest.get("净利润同比增长率", "")),
            }

        return {
            "available": True,
            "annual": {
                "period": str(latest.get("报告期", "")),
                "revenue": str(revenue),
                "net_profit": str(net_profit),
                "eps": round(eps, 4),
                "bvps": round(bvps, 2),
                "gross_margin": round(gross_margin, 2),
                "net_margin": round(net_margin, 2),
                "roe": round(roe, 2),
                "debt_ratio": round(debt_ratio, 2),
                "ocf_per_share": round(ocf, 2),
                "growth_rate_pct": round(growth_rate, 1),
            },
            "quarter": q_data,
            "profit": profit,
            "eps": round(eps, 4),
            "bvps": round(bvps, 2),
            "growth_rate": round(growth_rate, 1),
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}


def print_a_share_financials(data: dict):
    """Print formatted A-share financial data from get_a_share_financials."""
    if not data.get("available"):
        print(f"财务数据获取失败：{data.get('reason', '未知错误')}")
        return

    a = data["annual"]
    print(f"\n--- 最新年报 ({a['period']}) ---")
    print(f"营业总收入：{a['revenue']}")
    print(f"归母净利润：{a['net_profit']}（同比 {a['growth_rate_pct']:+.1f}%）")
    print(f"基本每股收益：{a['eps']:.4f} 元")
    print(f"每股净资产：{a['bvps']:.2f} 元")
    print(f"销售毛利率：{a['gross_margin']:.2f}%")
    print(f"销售净利率：{a['net_margin']:.2f}%")
    print(f"ROE：{a['roe']:.2f}%")
    print(f"资产负债率：{a['debt_ratio']:.2f}%")
    print(f"每股经营现金流：{a['ocf_per_share']:.2f} 元")
    print(f"是否盈利：{'是 ✅' if data['profit'] else '否 ❌'}")

    q = data.get("quarter", {})
    if q and q.get("period"):
        print(f"\n--- 最新单季度 ({q['period']}) ---")
        print(f"营收：{q['revenue']}")
        print(f"净利润：{q['net_profit']}（同比 {q.get('growth_pct', '')}）")


def get_ak_a_stock_price(symbol: str):
    """
    A股实时价格（通过腾讯行情接口获取）
    :param symbol: 股票代码 如：600036（6位纯数字，自动判断沪深）
    """
    parts = _get_quote_data(symbol)
    if not parts:
        return None

    name = parts[1]
    now_price = parts[3]
    up_down = parts[32]
    up_amount = parts[31]

    print(f"标的：{name}")
    print(f"实时现价：{now_price} 元")
    print(f"涨跌幅：{up_down} %")
    print(f"涨跌额：{up_amount} 元")
    return float(now_price)

def get_kline_data(symbol: str, count: int = 60):
    """
    获取A股日K线数据（前复权）
    :param symbol: 股票代码 如：600036
    :param count: 获取天数
    :return: list of [日期, 开盘, 收盘, 最高, 最低, 成交量]，按时间升序
    """
    prefix = _get_prefix(symbol)
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {"param": f"{prefix}{symbol},day,,,{count},qfq"}

    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"K线数据请求失败: {e}")
        return []

    data = resp.json()
    key = f"{prefix}{symbol}"
    klines = data.get("data", {}).get(key, {}).get("qfqday", [])
    if not klines:
        print("未获取到K线数据")
        return []

    return klines

def _get_quote_data(symbol: str):
    """
    获取腾讯行情原始数据
    :return: 解析后的字段列表，失败返回 None
    """
    prefix = _get_prefix(symbol)
    url = f"https://qt.gtimg.cn/q={prefix}{symbol}"

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None

    text = resp.text.strip()
    if not text or "~" not in text:
        print("股票代码错误或无数据")
        return None

    return text.split("~")

def check_intraday_avg(symbol: str):
    """
    判断分时股价是否在分时均线（均价线）以上
    分时均价 = 总成交额 / 总成交量（即 VWAP）
    """
    parts = _get_quote_data(symbol)
    if not parts:
        return

    now_price = float(parts[3])
    vol = float(parts[36])
    amt = float(parts[37])

    if vol == 0:
        print("今日尚无成交数据")
        return

    avg_price = amt / vol * 100

    above_avg = now_price > avg_price
    print(f"\n--- 分时均价分析 ---")
    print(f"分时现价：{now_price:.2f}")
    print(f"分时均价：{avg_price:.2f}")
    print(f"分时股价在分时均线上方：{'是 ✅' if above_avg else '否 ❌'}")

# ========================
# 我新增：强势股综合判断函数
# ========================
def check_strong_stock(symbol: str):
    klines = get_kline_data(symbol, 60)
    if len(klines) < 60:
        print("K线数据不足，无法判断强势特征")
        return

    df = pd.DataFrame(klines, columns=["date", "open", "close", "high", "low", "volume"])
    df[["open", "close", "high", "low", "volume"]] = df[["open", "close", "high", "low", "volume"]].astype(float)

    # 均线
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()
    df["ma5v"] = df["volume"].rolling(5).mean()

    d = df.iloc[-1]
    last3 = df.tail(3)
    last5 = df.tail(5)
    last20 = df.tail(20)

    # ========= 强势特征 =========
    多头排列 = d.ma5 > d.ma10 > d.ma20 > d.ma60
    站稳5日线 = d.close > d.ma5
    站稳20日线 = d.close > d.ma20
    上涨放量 = d.volume > d.ma5v * 0.9
    阶段新高 = d.close >= last20["high"].max()
    拒绝深调 = (last3["close"].min() / last3["close"].max()) > 0.93
    五日内阴线少 = (last5["close"] < last5["open"]).sum() <= 2

    conds = [多头排列, 站稳5日线, 站稳20日线, 上涨放量, 阶段新高, 拒绝深调, 五日内阴线少]
    得分 = sum(conds)
    是强势股 = 得分 >= 5

    print("\n======================================")
    print(f"【📈 强势股综合判断：{symbol}】")
    print("======================================")
    print(f"均线多头排列：{'是 ✅' if 多头排列 else '否 ❌'}")
    print(f"股价在5日线上：{'是 ✅' if 站稳5日线 else '否 ❌'}")
    print(f"股价在20日线上：{'是 ✅' if 站稳20日线 else '否 ❌'}")
    print(f"上涨放量健康：{'是 ✅' if 上涨放量 else '否 ❌'}")
    print(f"阶段新高：{'是 ✅' if 阶段新高 else '否 ❌'}")
    print(f"拒绝深调(抗跌)：{'是 ✅' if 拒绝深调 else '否 ❌'}")
    print(f"阴线少走势强：{'是 ✅' if 五日内阴线少 else '否 ❌'}")
    print("======================================")
    print(f"强势得分：{得分}/7")
    print(f"最终结论：【{'🔥 强势股' if 是强势股 else '⚠️ 非强势股'}】")
    print("======================================\n")

def check_ma_status(symbol: str):
    klines = get_kline_data(symbol, 30)
    if len(klines) < 20:
        print("K线数据不足，无法计算均线")
        return

    closes = [float(k[2]) for k in klines]
    latest_date = klines[-1][0]
    latest_close = closes[-1]

    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20

    ma5_prev = sum(closes[-6:-1]) / 5
    ma10_prev = sum(closes[-11:-1]) / 10
    ma20_prev = sum(closes[-21:-1]) / 20

    above_ma5 = latest_close > ma5
    bullish_alignment = ma5 > ma10 > ma20
    ma5_rising = ma5 > ma5_prev
    ma10_rising = ma10 > ma10_prev
    ma20_rising = ma20 > ma20_prev
    all_ma_rising = ma5_rising and ma10_rising and ma20_rising
    diverging = bullish_alignment and all_ma_rising

    print(f"\n--- 均线分析（{latest_date}）---")
    print(f"最新收盘价：{latest_close:.2f}")
    print(f"MA5：{ma5:.2f}  MA10：{ma10:.2f}  MA20：{ma20:.2f}")
    print(f"股价在5日线上方：{'是 ✅' if above_ma5 else '否 ❌'}")
    print(f"均线多头排列：{'是 ✅' if bullish_alignment else '否 ❌'}")
    print(f"均线向上发散：{'是 ✅' if diverging else '否 ❌'}")


def check_annual_line(symbol: str):
    """检查股价是否在年线（250日均线）上方"""
    klines = get_kline_data(symbol, 300)
    if len(klines) < 250:
        print("K线数据不足，无法计算年线（需250日）")
        return None

    closes = [float(k[2]) for k in klines]
    latest_date = klines[-1][0]
    latest_close = closes[-1]
    ma250 = sum(closes[-250:]) / 250
    above_annual = latest_close > ma250

    print(f"\n--- 年线分析（{latest_date}）---")
    print(f"最新收盘价：{latest_close:.2f}")
    print(f"年线 MA250：{ma250:.2f}")
    print(f"股价在年线上方：{'是 ✅' if above_annual else '否 ❌'}")
    return above_annual


def detect_golden_triangle(symbol: str, lookback: int = 80, fresh_days: int = 20) -> dict:
    """
    检测价托（黄金三角）：5日上穿10日 → 5日上穿20日 → 10日上穿20日，顺序完成且维持多头排列。

    含义：趋势由跌转涨、底部区域确立、三角形内为多头成本支撑区。
    :return: dict with formed, fresh, volume_confirm, cross dates, score (0-45), details
    """
    klines = get_kline_data(symbol, lookback + 25)
    klines = [k[:6] for k in klines]
    empty = {
        "formed": False,
        "fresh": False,
        "forming": False,
        "volume_confirm": False,
        "bullish_alignment": False,
        "cross_5_10_date": None,
        "cross_5_20_date": None,
        "cross_10_20_date": None,
        "days_since_complete": None,
        "triangle_score": 0,
        "label": "未形成价托",
        "interpretation": "尚未出现完整的黄金三角金叉序列。",
    }
    if len(klines) < 25:
        empty["interpretation"] = "K线数据不足，无法判断价托。"
        return empty

    df = pd.DataFrame(klines, columns=["date", "open", "close", "high", "low", "volume"])
    df[["close", "volume"]] = df[["close", "volume"]].astype(float)
    df["ma5"] = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma5v"] = df["volume"].rolling(5).mean()

    def _cross_up(fast_col: str, slow_col: str, idx: int) -> bool:
        if idx < 1:
            return False
        return df[fast_col].iloc[idx] > df[slow_col].iloc[idx] and df[fast_col].iloc[idx - 1] <= df[slow_col].iloc[idx - 1]

    start = max(20, len(df) - lookback)
    best = None
    for i in range(start, len(df)):
        if not _cross_up("ma5", "ma10", i):
            continue
        d1 = df["date"].iloc[i]
        j5_20 = None
        for j in range(i, min(i + 30, len(df))):
            if _cross_up("ma5", "ma20", j):
                j5_20 = j
                break
        if j5_20 is None:
            continue
        d2 = df["date"].iloc[j5_20]
        j10_20 = None
        for k in range(j5_20, min(j5_20 + 30, len(df))):
            if _cross_up("ma10", "ma20", k):
                j10_20 = k
                break
        if j10_20 is None:
            continue
        d3 = df["date"].iloc[j10_20]
        if best is None or j10_20 > best["complete_idx"]:
            best = {
                "complete_idx": j10_20,
                "cross_5_10_date": d1,
                "cross_5_20_date": d2,
                "cross_10_20_date": d3,
            }

    latest = df.iloc[-1]
    bullish = latest["ma5"] > latest["ma10"] > latest["ma20"]
    above_ma5 = latest["close"] > latest["ma5"]

    # 形成中：已有 5>10 金叉，但三角未完成
    cross_5_10_recent = any(_cross_up("ma5", "ma10", i) for i in range(max(20, len(df) - 15), len(df)))
    has_5_above_10 = latest["ma5"] > latest["ma10"]
    has_5_above_20 = latest["ma5"] > latest["ma20"]
    has_10_above_20 = latest["ma10"] > latest["ma20"]
    forming = not best and has_5_above_10 and (has_5_above_20 or cross_5_10_recent) and not has_10_above_20

    if not best:
        score = 12 if forming else 0
        label = "价托形成中" if forming else "未形成价托"
        interp = (
            "5日线已上穿10日线，等待5日上穿20日及10日上穿20日完成黄金三角。"
            if forming
            else "尚未出现完整的黄金三角（5→10→5→20→10→20）金叉序列。"
        )
        return {
            **empty,
            "forming": forming,
            "bullish_alignment": bullish,
            "triangle_score": score,
            "label": label,
            "interpretation": interp,
        }

    days_since = len(df) - 1 - best["complete_idx"]
    formed = bullish and above_ma5
    fresh = days_since <= fresh_days

    # 价托完成后 5 日内量能是否放大（主力共识代理）
    vol_window = df.iloc[max(0, best["complete_idx"] - 2) : best["complete_idx"] + 6]
    volume_confirm = False
    if len(vol_window) >= 3 and vol_window["ma5v"].iloc[-1] > 0:
        avg_vol = vol_window["volume"].mean()
        base_vol = df["ma5v"].iloc[max(0, best["complete_idx"] - 10)]
        volume_confirm = avg_vol > base_vol * 1.05 if base_vol > 0 else False
    if not volume_confirm and latest["ma5v"] > 0:
        volume_confirm = latest["volume"] > latest["ma5v"] * 0.95

    if formed and fresh and volume_confirm:
        triangle_score = 45
        label = "价托成立（新鲜+放量）"
        interpretation = (
            f"黄金三角已于 {best['cross_10_20_date']} 完成（{days_since} 个交易日前），"
            "当前多头排列且价在5日线上，量能配合。趋势反转信号强，三角形区域为多头成本支撑。"
        )
    elif formed and fresh:
        triangle_score = 35
        label = "价托成立（新鲜）"
        interpretation = (
            f"黄金三角 {best['cross_10_20_date']} 完成，多头排列确立，"
            "底部区域支撑有效；可关注回踩三角区域不破后的加仓机会。"
        )
    elif formed:
        triangle_score = 25
        label = "价托已成立"
        interpretation = (
            f"黄金三角已于 {best['cross_10_20_date']} 完成（{days_since} 日前），"
            "仍维持多头排列，托盘效应仍在；若距今较久需结合资金与故事是否仍有效。"
        )
    elif bullish:
        triangle_score = 15
        label = "价托历史完成"
        interpretation = "三角金叉曾完成，但股价已跌破5日线或结构走弱，价托支撑需重新确认。"
    else:
        triangle_score = 8
        label = "价托失效"
        interpretation = "曾出现黄金三角，但均线结构已破坏，不宜仅凭历史价托看多。"

    return {
        "formed": formed,
        "fresh": fresh and formed,
        "forming": False,
        "volume_confirm": volume_confirm,
        "bullish_alignment": bullish,
        "cross_5_10_date": best["cross_5_10_date"],
        "cross_5_20_date": best["cross_5_20_date"],
        "cross_10_20_date": best["cross_10_20_date"],
        "days_since_complete": days_since,
        "triangle_score": triangle_score,
        "label": label,
        "interpretation": interpretation,
    }


def print_golden_triangle_report(symbol: str, result: dict = None):
    """打印价托（黄金三角）分析报告。"""
    if result is None:
        result = detect_golden_triangle(symbol)
    print("\n======================================")
    print(f"【价托 / 黄金三角：{symbol}】")
    print("======================================")
    print(f"  状态：{result.get('label', '未知')}")
    print(f"  5日上穿10日：{result.get('cross_5_10_date') or '—'}")
    print(f"  5日上穿20日：{result.get('cross_5_20_date') or '—'}")
    print(f"  10日上穿20日：{result.get('cross_10_20_date') or '—'}")
    if result.get("days_since_complete") is not None:
        print(f"  三角完成距今：{result['days_since_complete']} 个交易日")
    print(f"  多头排列：{'是 ✅' if result.get('bullish_alignment') else '否 ❌'}")
    print(f"  量能配合：{'是 ✅' if result.get('volume_confirm') else '否 ❌'}")
    print(f"  价托得分：{result.get('triangle_score', 0)}/45")
    print(f"  解读：{result.get('interpretation', '')}")
    print("======================================\n")


def comprehensive_judge(symbol: str, profit: bool = True, reason: str = ""):
    """
    综合判断：7项指标打分，给出买入/观望/卖出评级
    :param symbol: 股票代码
    :param profit: 是否盈利（从财报搜索结果传入）
    :param reason: 可能上涨理由（从产业链分析传入）
    评分规则：5-7项符合=买入，3-4项=观望，0-2项=卖出
    """
    # ---- 指标1: 是否盈利 ----
    item_profit = profit

    # ---- 指标2: 分时股价在分时均线上方 ----
    parts = _get_quote_data(symbol)
    item_intraday = False
    if parts:
        now_price = float(parts[3])
        vol = float(parts[36])
        amt = float(parts[37])
        if vol > 0:
            avg_price = amt / vol * 100
            item_intraday = now_price > avg_price

    # ---- 指标3-5: 均线分析（5日线、多头排列、发散）----
    klines = get_kline_data(symbol, 30)
    item_above_ma5 = False
    item_bullish = False
    item_diverging = False
    if len(klines) >= 21:
        closes = [float(k[2]) for k in klines]
        latest_close = closes[-1]
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20
        ma5_prev = sum(closes[-6:-1]) / 5
        ma10_prev = sum(closes[-11:-1]) / 10
        ma20_prev = sum(closes[-21:-1]) / 20

        item_above_ma5 = latest_close > ma5
        item_bullish = ma5 > ma10 > ma20
        item_diverging = item_bullish and (ma5 > ma5_prev) and (ma10 > ma10_prev) and (ma20 > ma20_prev)

    # ---- 指标6: 上涨放量 ----
    item_volume = False
    klines60 = get_kline_data(symbol, 60) if len(klines) < 60 else klines
    klines60 = [k[:6] for k in klines60]  # strip ex-dividend metadata column
    if len(klines60) >= 10:
        import pandas as pd
        df = pd.DataFrame(klines60, columns=["date", "open", "close", "high", "low", "volume"])
        df[["open", "close", "high", "low", "volume"]] = df[["open", "close", "high", "low", "volume"]].astype(float)
        df["ma5v"] = df["volume"].rolling(5).mean()
        d = df.iloc[-1]
        item_volume = d.volume > d.ma5v * 0.9

    # ---- 指标7: 近20日阶段新高 ----
    item_newhigh = False
    if len(klines60) >= 20:
        df20 = pd.DataFrame(klines60[-20:], columns=["date", "open", "close", "high", "low", "volume"])
        df20[["open", "close", "high", "low", "volume"]] = df20[["open", "close", "high", "low", "volume"]].astype(float)
        item_newhigh = df20.iloc[-1]["close"] >= df20["high"].max()

    # ---- 汇总 ----
    items = {
        "是否盈利": item_profit,
        "分时股价在分时均线上方": item_intraday,
        "股价在5日线上方": item_above_ma5,
        "均线多头排列": item_bullish,
        "均线向上发散": item_diverging,
        "上涨放量": item_volume,
        "近20日阶段新高": item_newhigh,
    }
    score = sum(items.values())

    if score >= 5:
        rating = "买入"
    elif score >= 3:
        rating = "观望"
    else:
        rating = "卖出"

    print("\n======================================")
    print(f"【综合判断：{symbol}】")
    print("======================================")
    for name, passed in items.items():
        mark = "是 ✅" if passed else "否 ❌"
        print(f"  {name}：{mark}")
    print("--------------------------------------")
    print(f"  符合项数：{score}/7")
    print(f"  综合评级：【{rating}】")
    if reason:
        print(f"  可能上涨理由：{reason}")
    print("======================================\n")


# ========================
# 批量分析相关函数（静默版，返回 dict）
# ========================

def get_technical_dict(symbol: str) -> dict:
    """
    获取单只股票的全部技术指标，以 dict 形式返回（静默，不打印）。
    供批量分析模式使用。
    返回格式：
    {
        "name": "股票名",
        "code": "603259",
        "price": 110.57,
        "change_pct": 10.0,
        "change_amount": 10.05,
        "intraday_price": 110.57,
        "intraday_avg": 110.00,
        "above_intraday_avg": True,
        "ma5": 102.12,
        "ma10": 102.08,
        "ma20": 102.79,
        "above_ma5": True,
        "bullish_alignment": False,
        "diverging": False,
        "date": "2026-04-28"
    }
    """
    result = {
        "code": symbol,
        "name": "",
        "price": 0.0,
        "change_pct": 0.0,
        "change_amount": 0.0,
        "intraday_price": 0.0,
        "intraday_avg": 0.0,
        "above_intraday_avg": False,
        "ma5": 0.0,
        "ma10": 0.0,
        "ma20": 0.0,
        "above_ma5": False,
        "bullish_alignment": False,
        "diverging": False,
        "date": "",
    }

    # ---- 实时行情 ----
    parts = _get_quote_data(symbol)
    if parts:
        result["name"] = parts[1]
        result["price"] = float(parts[3])
        result["change_pct"] = float(parts[32])
        result["change_amount"] = float(parts[31])

        # ---- 分时均价 ----
        vol = float(parts[36])
        amt = float(parts[37])
        if vol > 0:
            result["intraday_price"] = result["price"]
            result["intraday_avg"] = round(amt / vol * 100, 2)
            result["above_intraday_avg"] = result["price"] > result["intraday_avg"]

    # ---- 均线 ----
    klines = get_kline_data(symbol, 30)
    if len(klines) >= 21:
        closes = [float(k[2]) for k in klines]
        result["date"] = klines[-1][0]
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20
        ma5_prev = sum(closes[-6:-1]) / 5
        ma10_prev = sum(closes[-11:-1]) / 10
        ma20_prev = sum(closes[-21:-1]) / 20

        result["ma5"] = round(ma5, 2)
        result["ma10"] = round(ma10, 2)
        result["ma20"] = round(ma20, 2)
        result["above_ma5"] = closes[-1] > ma5
        result["bullish_alignment"] = ma5 > ma10 > ma20
        result["diverging"] = result["bullish_alignment"] and (ma5 > ma5_prev) and (ma10 > ma10_prev) and (ma20 > ma20_prev)

    return result


def comprehensive_judge_dict(symbol: str, profit: bool, reason: str = "") -> dict:
    """
    综合判断（静默版），返回 dict 而非打印。
    返回格式：
    {
        "items": {"是否盈利": True, ...},
        "score": 5,
        "rating": "买入",
        "reason": "..."
    }
    """
    items = {}
    items["是否盈利"] = profit

    # 分时、均线数据复用 get_technical_dict 的逻辑
    tech = get_technical_dict(symbol)
    items["分时股价在分时均线上方"] = tech["above_intraday_avg"]
    items["股价在5日线上方"] = tech["above_ma5"]
    items["均线多头排列"] = tech["bullish_alignment"]
    items["均线向上发散"] = tech["diverging"]

    # 上涨放量 & 20日新高
    klines = get_kline_data(symbol, 60)
    klines = [k[:6] for k in klines]  # strip ex-dividend metadata column
    item_volume = False
    item_newhigh = False
    if len(klines) >= 10:
        import pandas as pd
        df = pd.DataFrame(klines, columns=["date", "open", "close", "high", "low", "volume"])
        df[["open", "close", "high", "low", "volume"]] = df[["open", "close", "high", "low", "volume"]].astype(float)
        df["ma5v"] = df["volume"].rolling(5).mean()
        item_volume = df.iloc[-1]["volume"] > df["ma5v"].iloc[-1] * 0.9
    if len(klines) >= 20:
        df20 = pd.DataFrame(klines[-20:], columns=["date", "open", "close", "high", "low", "volume"])
        df20[["high", "close"]] = df20[["high", "close"]].astype(float)
        item_newhigh = df20.iloc[-1]["close"] >= df20["high"].max()
    items["上涨放量"] = bool(item_volume)
    items["近20日阶段新高"] = bool(item_newhigh)

    triangle = detect_golden_triangle(symbol)
    score = sum(items.values())
    if score >= 5:
        rating = "买入"
    elif score >= 3:
        rating = "观望"
    else:
        rating = "卖出"

    return {
        "items": items,
        "score": score,
        "rating": rating,
        "reason": reason,
        "golden_triangle": triangle,
    }


def print_comparison_table(stocks_data: list):
    """
    打印所有股票的批量分析汇总对比表。

    :param stocks_data: list of dict，每只股票的数据汇总 dict，格式如下：
    [
        {
            "name": "药明康德",
            "code": "603259",
            "price": 110.57,
            "change_pct": 10.0,
            "profit": True,
            "net_profit": "191.51亿（+102.65%）",
            "q1_data": "营收124.36亿，净利46.52亿（+26.68%）",
            "chain_position": "中游 CRO/CDMO一体化",
            "core_driver": "TIDES平台商业化突破...",
            "judge": { "items": {...}, "score": 5, "rating": "买入" }
        },
        ...
    ]
    """
    if not stocks_data:
        print("无数据")
        return

    # 表头
    header = (
        "| 股票 | 代码 | 股价 | 涨跌幅 | 盈利 | 分时 | 5日线 | 多头 | 发散 | 放量 | 新高 | 评分 | 评级 | 核心驱动 |"
        "\n|------|------|------|--------|------|------|-------|------|------|------|------|------|------|----------|"
    )
    print(header)

    for s in stocks_data:
        judge = s.get("judge", {})
        items = judge.get("items", {})
        score = judge.get("score", 0)
        rating = judge.get("rating", "未知")
        name = s.get("name", "")
        code = s.get("code", "")
        price = s.get("price", 0)
        change_pct = s.get("change_pct", 0)

        def _check(key):
            return "✅" if items.get(key, False) else "❌"

        row = (
            f"| {name} | {code} | {price:.2f} | {change_pct:+.2f}% "
            f"| {_check('是否盈利')} | {_check('分时股价在分时均线上方')} | {_check('股价在5日线上方')} "
            f"| {_check('均线多头排列')} | {_check('均线向上发散')} | {_check('上涨放量')} | {_check('近20日阶段新高')} "
            f"| **{score}/7** | **{rating}** | {s.get('core_driver', '')[:25]}... |"
        )
        print(row)

    # 汇总统计
    ratings = [s.get("judge", {}).get("rating", "未知") for s in stocks_data]
    buy_count = ratings.count("买入")
    watch_count = ratings.count("观望")
    sell_count = ratings.count("卖出")
    print(f"\n> 汇总：买入 {buy_count} 只 | 观望 {watch_count} 只 | 卖出 {sell_count} 只")


# ========================================================================
# 美股分析函数（数据源：Yahoo Finance / yfinance）
# ========================================================================

import yfinance as yf
import numpy as np


def _safe_float(val) -> float:
    """Convert numpy or other numeric types to native Python float."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _safe_bool(val) -> bool:
    """Convert numpy bool_ to native Python bool."""
    return bool(val)


def is_us_ticker(symbol: str) -> bool:
    """判断是否为美股 ticker（含字母则为美股，纯数字为 A 股）"""
    return bool(symbol) and any(c.isalpha() for c in symbol)


def get_us_stock_info(ticker: str):
    """
    获取美股实时行情和公司基本信息。
    :param ticker: 美股代码 如：AAPL, TSLA, NVDA
    :return: dict with price, change, market cap, PE, EPS, sector, industry
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
    except Exception as e:
        print(f"美股数据获取失败: {e}")
        return None

    price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose", 0)
    prev_close = info.get("previousClose", price)
    change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0

    net_income = info.get("netIncomeToCommon")
    net_income_str = ""
    if net_income is not None:
        ni = _safe_float(net_income)
        sign = "-" if ni < 0 else ""
        an = abs(ni)
        if an >= 1e9:
            net_income_str = f"{sign}${an/1e9:.2f}B"
        elif an >= 1e6:
            net_income_str = f"{sign}${an/1e6:.0f}M"
        else:
            net_income_str = f"{sign}${an:.0f}"

    result = {
        "name": info.get("longName") or info.get("shortName", ticker),
        "ticker": ticker.upper(),
        "price": price,
        "change_pct": round(change_pct, 2),
        "market_cap": info.get("marketCap"),
        "pe": info.get("trailingPE"),
        "eps": info.get("trailingEps"),
        "revenue": info.get("totalRevenue"),
        "net_income": net_income,
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "summary": info.get("longBusinessSummary", ""),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "beta": info.get("beta"),
    }

    print(f"\n--- 美股基本信息 ---")
    print(f"公司：{result['name']} ({result['ticker']})")
    print(f"行业：{result['sector']} / {result['industry']}")
    print(f"实时股价：${result['price']:.2f}")
    print(f"涨跌幅：{result['change_pct']:+.2f}%")
    print(f"市值：${result['market_cap']:.0f}" if result['market_cap'] else "市值：N/A")
    print(f"PE：{result['pe']:.2f}" if result['pe'] else "PE：N/A")
    print(f"EPS：${result['eps']:.2f}" if result['eps'] else "EPS：N/A")
    print(f"归母净利润：{net_income_str}" if net_income_str else "归母净利润：N/A")
    print(f"52周高：${result['52w_high']:.2f}" if result['52w_high'] else "52周高：N/A")
    print(f"52周低：${result['52w_low']:.2f}" if result['52w_low'] else "52周低：N/A")
    print(f"Beta：{result['beta']:.2f}" if result['beta'] else "Beta：N/A")

    return result


def get_us_ma_status(ticker: str, period: str = "1y"):
    """
    获取美股均线状态（50日线和200日线）。
    :param ticker: 美股代码
    :param period: 数据周期（默认1年，足够算200日线）
    :return: dict with ma50, ma200, above_ma50, above_ma200, golden_cross
    """
    try:
        stock = yf.Ticker(ticker.upper())
        hist = stock.history(period=period)
        if len(hist) < 50:
            print(f"历史数据不足（{len(hist)} 天），无法计算美股均线")
            return {
                "ma50": 0, "ma200": 0,
                "above_ma50": False, "above_ma200": False,
                "golden_cross": False, "data_days": len(hist)
            }

        dates = hist.index
        closes = hist["Close"].values
        latest_close = closes[-1]
        latest_date = dates[-1].strftime("%Y-%m-%d")

        ma50 = np.mean(closes[-50:]) if len(closes) >= 50 else 0
        ma200 = np.mean(closes[-200:]) if len(closes) >= 200 else 0
        above_ma50 = latest_close > ma50 if ma50 else False
        above_ma200 = latest_close > ma200 if ma200 else False
        golden_cross = ma50 > ma200 if (ma50 and ma200) else False

        print(f"\n--- 美股均线分析（{latest_date}）---")
        print(f"最新收盘价：${latest_close:.2f}")
        if ma50:
            print(f"50日MA：${ma50:.2f}")
            print(f"股价在50日线上方：{'是 ✅' if above_ma50 else '否 ❌'}")
        if ma200:
            print(f"200日MA：${ma200:.2f}")
            print(f"股价在200日线上方：{'是 ✅' if above_ma200 else '否 ❌'}")
        print(f"黄金交叉（50日线 > 200日线）：{'是 ✅' if golden_cross else '否 ❌'}")

        return {
            "ma50": round(float(ma50), 2),
            "ma200": round(float(ma200), 2),
            "above_ma50": above_ma50,
            "above_ma200": above_ma200,
            "golden_cross": golden_cross,
            "data_days": len(hist),
            "date": latest_date,
        }
    except Exception as e:
        print(f"美股均线计算失败: {e}")
        return {"ma50": 0, "ma200": 0, "above_ma50": False, "above_ma200": False, "golden_cross": False, "error": str(e)}


def get_us_rsi(ticker: str, rsi_period: int = 14, hist_period: str = "6mo"):
    """
    计算美股 14 日 RSI。
    :param ticker: 美股代码
    :param rsi_period: RSI 周期（默认14）
    :param hist_period: 历史数据周期
    :return: dict with rsi value and status
    """
    try:
        stock = yf.Ticker(ticker.upper())
        hist = stock.history(period=hist_period)
        if len(hist) < rsi_period + 1:
            print(f"数据不足，无法计算 RSI")
            return {"rsi": None, "overbought": False, "oversold": False, "normal": False}

        closes = hist["Close"].values
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[:rsi_period])
        avg_loss = np.mean(losses[:rsi_period])

        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        # Smooth subsequent values
        for i in range(rsi_period, len(deltas)):
            avg_gain = (avg_gain * (rsi_period - 1) + gains[i]) / rsi_period
            avg_loss = (avg_loss * (rsi_period - 1) + losses[i]) / rsi_period
            if avg_loss == 0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

        rsi_val = round(float(rsi), 1)
        overbought = rsi_val > 70
        oversold = rsi_val < 30
        normal = 30 <= rsi_val <= 70

        print(f"\n--- 美股 RSI 分析 ---")
        print(f"RSI(14)：{rsi_val}")
        print(f"RSI 在正常区间（30-70）：{'是 ✅' if normal else '否 ❌'}")
        if overbought:
            print(f"⚠️ RSI > 70 超买")
        if oversold:
            print(f"⚠️ RSI < 30 超卖")

        return {"rsi": rsi_val, "overbought": overbought, "oversold": oversold, "normal": normal}
    except Exception as e:
        print(f"RSI 计算失败: {e}")
        return {"rsi": None, "overbought": False, "oversold": False, "normal": False, "error": str(e)}


def get_us_technical_dict(ticker: str) -> dict:
    """
    获取美股全部技术指标（静默版，返回 dict，供批量分析使用）。
    返回格式：
    {
        "name": "Apple Inc.",
        "ticker": "AAPL",
        "price": 195.0, "change_pct": 1.5,
        "ma50": 190.0, "ma200": 180.0,
        "above_ma50": True, "above_ma200": True, "golden_cross": True,
        "rsi": 55.0, "rsi_normal": True,
        "volume_above_avg": True,
        "near_52w_high": True,
        "eps": 6.5, "pe": 30.0, "net_income": 117.78,
        "sector": "Technology", "industry": "Consumer Electronics",
        "52w_high": 200.0, "date": "2026-04-28"
    }
    """
    import numpy as np

    result = {
        "name": "", "ticker": ticker.upper(),
        "price": 0, "change_pct": 0,
        "ma50": 0, "ma200": 0,
        "above_ma50": False, "above_ma200": False, "golden_cross": False,
        "rsi": 0, "rsi_normal": False,
        "volume_above_avg": False,
        "near_52w_high": False,
        "eps": 0, "pe": 0, "net_income": 0,
        "sector": "", "industry": "",
        "52w_high": 0, "date": "",
    }

    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        hist = stock.history(period="1y")

        result["name"] = info.get("longName") or info.get("shortName", ticker)
        result["sector"] = str(info.get("sector", ""))
        result["industry"] = str(info.get("industry", ""))
        result["eps"] = _safe_float(info.get("trailingEps"))
        result["pe"] = _safe_float(info.get("trailingPE"))
        result["net_income"] = _safe_float(info.get("netIncomeToCommon")) / 1e9 if info.get("netIncomeToCommon") else 0
        result["52w_high"] = _safe_float(info.get("fiftyTwoWeekHigh"))

        if len(hist) >= 50:
            closes = hist["Close"].values
            result["price"] = round(float(closes[-1]), 2)
            result["date"] = hist.index[-1].strftime("%Y-%m-%d")

            prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else result["price"]
            result["change_pct"] = round((result["price"] - prev_close) / prev_close * 100, 2) if prev_close else 0

            result["ma50"] = round(float(np.mean(closes[-50:])), 2)
            if len(closes) >= 200:
                result["ma200"] = round(float(np.mean(closes[-200:])), 2)

            result["above_ma50"] = _safe_bool(result["price"] > result["ma50"])
            result["above_ma200"] = _safe_bool(result["price"] > result["ma200"]) if result["ma200"] else False
            result["golden_cross"] = _safe_bool(result["ma50"] > result["ma200"]) if result["ma200"] else False

            # RSI
            try:
                rsi_data = get_us_rsi(ticker)
                result["rsi"] = _safe_float(rsi_data.get("rsi"))
                result["rsi_normal"] = _safe_bool(rsi_data.get("normal", False))
            except Exception:
                pass

            # Volume above 5-day average
            volumes = hist["Volume"].values
            if len(volumes) >= 6:
                avg_vol_5 = np.mean(volumes[-6:-1])
                result["volume_above_avg"] = _safe_bool(volumes[-1] > avg_vol_5 * 0.9)

            # Near 52-week high (within 10%)
            if result["52w_high"] and result["52w_high"] > 0:
                result["near_52w_high"] = _safe_bool(result["price"] >= result["52w_high"] * 0.90)

    except Exception as e:
        result["error"] = str(e)

    return result


def comprehensive_judge_us(ticker: str, profit: bool = True, reason: str = ""):
    """
    美股综合判断：7项指标打分，给出买入/观望/卖出评级。
    :param ticker: 美股代码
    :param profit: 是否盈利（EPS > 0 或 WebSearch 确认）
    :param reason: 可能上涨理由（从产业链分析传入）
    评分规则：5-7项符合=买入，3-4项=观望，0-2项=卖出
    """
    import numpy as np

    # 指标1: 是否盈利
    item_profit = profit

    # 获取技术数据
    item_above_ma50 = False
    item_above_ma200 = False
    item_golden_cross = False
    item_rsi_normal = False
    item_volume = False
    item_near_high = False

    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        hist = stock.history(period="1y")

        if len(hist) >= 200:
            closes = hist["Close"].values
            latest_close = closes[-1]
            ma50 = np.mean(closes[-50:])
            ma200 = np.mean(closes[-200:])

            item_above_ma50 = latest_close > ma50
            item_above_ma200 = latest_close > ma200
            item_golden_cross = ma50 > ma200

            # 成交量
            volumes = hist["Volume"].values
            if len(volumes) >= 6:
                avg_vol_5 = np.mean(volumes[-6:-1])
                item_volume = volumes[-1] > avg_vol_5 * 0.9

        # RSI
        try:
            rsi_data = get_us_rsi(ticker)
            item_rsi_normal = rsi_data.get("normal", False)
        except Exception:
            pass

        # 52周高点
        high_52w = info.get("fiftyTwoWeekHigh")
        if high_52w and len(hist) >= 1:
            item_near_high = float(closes[-1]) >= high_52w * 0.90

    except Exception as e:
        print(f"美股综合判断数据获取失败: {e}")

    # 汇总
    items = {
        "是否盈利": item_profit,
        "股价在50日线上方": item_above_ma50,
        "股价在200日线上方": item_above_ma200,
        "黄金交叉（50>200）": item_golden_cross,
        "RSI在30-70区间": item_rsi_normal,
        "成交量高于5日均量": item_volume,
        "接近52周高点（10%内）": item_near_high,
    }
    score = sum(items.values())

    if score >= 5:
        rating = "买入"
    elif score >= 3:
        rating = "观望"
    else:
        rating = "卖出"

    print("\n======================================")
    print(f"【美股综合判断：{ticker.upper()}】")
    print("======================================")
    for name, passed in items.items():
        print(f"  {name}：{'是 ✅' if passed else '否 ❌'}")
    print("--------------------------------------")
    print(f"  符合项数：{score}/7")
    print(f"  综合评级：【{rating}】")
    if reason:
        print(f"  可能上涨理由：{reason}")
    print("======================================\n")


def comprehensive_judge_us_dict(ticker: str, profit: bool, reason: str = "") -> dict:
    """
    美股综合判断（静默版），返回 dict。
    """
    import numpy as np

    items = {"是否盈利": _safe_bool(profit)}

    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        hist = stock.history(period="1y")

        if len(hist) >= 200:
            closes = hist["Close"].values
            ma50 = np.mean(closes[-50:])
            ma200 = np.mean(closes[-200:])
            items["股价在50日线上方"] = _safe_bool(closes[-1] > ma50)
            items["股价在200日线上方"] = _safe_bool(closes[-1] > ma200)
            items["黄金交叉（50>200）"] = _safe_bool(ma50 > ma200)

            volumes = hist["Volume"].values
            if len(volumes) >= 6:
                items["成交量高于5日均量"] = _safe_bool(volumes[-1] > np.mean(volumes[-6:-1]) * 0.9)
        else:
            items["股价在50日线上方"] = False
            items["股价在200日线上方"] = False
            items["黄金交叉（50>200）"] = False
            items["成交量高于5日均量"] = False

        try:
            rsi_data = get_us_rsi(ticker)
            items["RSI在30-70区间"] = _safe_bool(rsi_data.get("normal", False))
        except Exception:
            items["RSI在30-70区间"] = False

        high_52w = _safe_float(info.get("fiftyTwoWeekHigh"))
        if high_52w > 0 and len(hist) >= 1:
            items["接近52周高点（10%内）"] = _safe_bool(float(closes[-1]) >= high_52w * 0.90)
        else:
            items["接近52周高点（10%内）"] = False

    except Exception:
        for k in ["股价在50日线上方", "股价在200日线上方", "黄金交叉（50>200）", "RSI在30-70区间", "成交量高于5日均量", "接近52周高点（10%内）"]:
            if k not in items:
                items[k] = False

    score = sum(items.values())
    if score >= 5:
        rating = "买入"
    elif score >= 3:
        rating = "观望"
    else:
        rating = "卖出"

    return {"items": items, "score": score, "rating": rating, "reason": reason}


def print_comparison_table_us(stocks_data: list):
    """
    打印所有美股批量分析汇总对比表。

    :param stocks_data: list of dict
    [
        {
            "name": "Apple Inc.", "ticker": "AAPL",
            "price": 195.0, "change_pct": 1.5,
            "profit": True, "eps": 6.5, "pe": 30.0,
            "sector": "Technology",
            "chain_position": "中游 消费电子制造",
            "core_driver": "iPhone需求复苏 + 服务收入增长",
            "judge": {"items": {...}, "score": 5, "rating": "买入"}
        },
    ]
    """
    if not stocks_data:
        print("无数据")
        return

    header = (
        "| 股票 | Ticker | 股价 | 涨跌幅 | 盈利 | 50日线 | 200日线 | 金叉 | RSI | 放量 | 52高 | 评分 | 评级 | 核心驱动 |"
        "\n|------|--------|------|--------|------|--------|---------|------|-----|------|------|------|------|--------|"
    )
    print(header)

    for s in stocks_data:
        judge = s.get("judge", {})
        items = judge.get("items", {})
        score = judge.get("score", 0)
        rating = judge.get("rating", "未知")
        name = s.get("name", "")
        ticker = s.get("ticker", "")
        price = s.get("price", 0)
        change_pct = s.get("change_pct", 0)

        def _check(key):
            return "✅" if items.get(key, False) else "❌"

        row = (
            f"| {name} | {ticker} | ${price:.2f} | {change_pct:+.2f}% "
            f"| {_check('是否盈利')} | {_check('股价在50日线上方')} | {_check('股价在200日线上方')} "
            f"| {_check('黄金交叉（50>200）')} | {_check('RSI在30-70区间')} | {_check('成交量高于5日均量')} "
            f"| {_check('接近52周高点（10%内）')} "
            f"| **{score}/7** | **{rating}** | {s.get('core_driver', '')[:20]} |"
        )
        print(row)

    ratings = [s.get("judge", {}).get("rating", "未知") for s in stocks_data]
    buy_count = ratings.count("买入")
    watch_count = ratings.count("观望")
    sell_count = ratings.count("卖出")
    print(f"\n> 汇总：买入 {buy_count} 只 | 观望 {watch_count} 只 | 卖出 {sell_count} 只")


# ========================================================================
# 散户数量分析（股东户数变化趋势）
# ========================================================================

def get_shareholder_data(symbol: str) -> list:
    """
    获取A股季度股东户数数据。
    数据源：东方财富 F10 数据中心。
    :param symbol: 股票代码（6位）
    :return: list of dict，按时间降序排列
    """
    url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    params = {
        "reportName": "RPT_F10_EH_HOLDERNUM",
        "columns": ("SECURITY_CODE,END_DATE,HOLDER_TOTAL_NUM,TOTAL_NUM_RATIO,"
                    "HOLDER_A_NUM,HOLDER_ANUM_RATIO,AVG_FREE_SHARES,"
                    "AVG_FREESHARES_RATIO,HOLD_FOCUS,PRICE,AVG_HOLD_AMT,"
                    "HOLD_RATIO_TOTAL,FREEHOLD_RATIO_TOTAL,HOLDER_TOTAL_NUMCHANGE"),
        "filter": f'(SECURITY_CODE="{symbol}")',
        "pageNumber": 1,
        "pageSize": 12,
        "sortTypes": -1,
        "sortColumns": "END_DATE",
        "source": "WEB",
        "client": "WEB",
    }
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success") and data.get("result"):
            return data["result"].get("data") or []
        return []
    except Exception as e:
        print(f"股东户数数据获取失败: {e}")
        return []


def analyze_shareholder_trend(symbol: str) -> dict:
    """
    分析散户数量变化趋势，判断筹码集中/分散。

    规则：
    - 股东户数持续减少 + 人均持股增加 → 筹码集中（机构吸筹，偏多）
    - 股东户数持续增加 + 人均持股减少 → 筹码分散（机构出货，偏空）
    - 混合信号 → 震荡，需观察

    :return: dict with trend analysis, quarterly data, and verdict
    """
    data = get_shareholder_data(symbol)
    if not data:
        return {"error": "未获取到股东户数数据", "symbol": symbol}

    quarters = []
    def _parse_float_or_zero(val):
        """Parse float, handling string values like '非常分散'."""
        try:
            return round(float(val), 2)
        except (TypeError, ValueError):
            return 0.0

    for d in data:
        end_date = str(d.get("END_DATE", ""))[:10]
        total_holders = d.get("HOLDER_TOTAL_NUM")
        holder_change_pct = d.get("TOTAL_NUM_RATIO")
        avg_free_shares = d.get("AVG_FREE_SHARES")
        avg_share_change_pct = d.get("AVG_FREESHARES_RATIO")
        hold_focus = d.get("HOLD_FOCUS")
        top10_hold = d.get("HOLD_RATIO_TOTAL")
        top10_free_hold = d.get("FREEHOLD_RATIO_TOTAL")
        price = d.get("PRICE")
        avg_amt = d.get("AVG_HOLD_AMT")
        holder_change_abs = d.get("HOLDER_TOTAL_NUMCHANGE")

        hf = _parse_float_or_zero(hold_focus) if hold_focus is not None else 0.0

        quarters.append({
            "date": end_date,
            "holders": int(total_holders) if total_holders is not None else 0,
            "holder_change_pct": round(float(holder_change_pct), 2) if holder_change_pct is not None else 0,
            "holder_change_abs": int(holder_change_abs) if holder_change_abs is not None else 0,
            "avg_free_shares": int(avg_free_shares) if avg_free_shares is not None else 0,
            "avg_share_change_pct": round(float(avg_share_change_pct), 2) if avg_share_change_pct is not None else 0,
            "hold_focus": hf,
            "hold_focus_raw": str(hold_focus) if hold_focus else "",
            "top10_hold_pct": round(float(top10_hold), 2) if top10_hold is not None else None,
            "top10_free_hold_pct": round(float(top10_free_hold), 2) if top10_free_hold is not None else None,
            "avg_price": round(float(price), 2) if price is not None else 0,
            "avg_hold_amt": round(float(avg_amt), 0) if avg_amt is not None else 0,
        })

    if not quarters:
        return {"error": "解析股东户数数据失败", "symbol": symbol}

    latest = quarters[0]

    # ── Trend analysis: look at last 4 quarters ──
    recent = quarters[:min(4, len(quarters))]
    consec_decrease = 0  # consecutive quarters of holder decrease (from latest backwards)
    consec_increase = 0

    for q in recent:
        if q["holder_change_pct"] < 0:
            consec_decrease += 1
        else:
            break  # stop at first non-decrease
    for q in recent:
        if q["holder_change_pct"] > 0:
            consec_increase += 1
        else:
            break  # stop at first non-increase

    # Previous trend (for reversal detection)
    was_increasing = False
    if len(recent) > consec_decrease and consec_decrease > 0:
        # check the quarter before the decrease streak
        prev_q = recent[consec_decrease] if consec_decrease < len(recent) else None
        if prev_q and prev_q["holder_change_pct"] > 0:
            was_increasing = True

    # Calculate multi-quarter changes
    qoq_change = recent[0]["holder_change_pct"]  # latest quarter change
    if len(recent) >= 2:
        two_q_change = round((recent[0]["holders"] - recent[1]["holders"]) / recent[1]["holders"] * 100, 1)
    else:
        two_q_change = None
    if len(recent) >= 4:
        four_q_change = round((recent[0]["holders"] - recent[3]["holders"]) / recent[3]["holders"] * 100, 1)
    else:
        four_q_change = None

    # ── Verdict ──
    if consec_decrease >= 3:
        trend = "筹码持续集中"
        signal = "🟢 偏多"
        interpretation = (
            f"股东户数连续{consec_decrease}个季度减少，人均持股持续增加。"
            "机构或大户在持续收集筹码，散户在退出。这是典型的底部吸筹特征，"
            "中长期偏多。但需结合股价位置判断——若股价已大幅上涨，也可能是利好兑现前的集中。"
        )
    elif consec_decrease >= 2:
        trend = "筹码趋于集中"
        signal = "🟢 略偏多"
        interpretation = (
            f"近{consec_decrease}个季度股东户数减少，筹码向少数人集中。"
            "趋势向好，建议再观察1-2个季度确认持续性。"
        )
    elif consec_increase >= 3:
        trend = "筹码持续分散"
        signal = "🔴 偏空"
        interpretation = (
            f"股东户数连续{consec_increase}个季度增加，人均持股持续减少。"
            "机构或大户可能在出货，散户在接盘。这是典型的顶部派发特征，"
            "需警惕。但如果公司业绩高增长、有新机构入场，也可能是股东结构换手。"
        )
    elif consec_increase >= 2:
        trend = "筹码趋于分散"
        signal = "🟡 略偏空"
        interpretation = (
            f"近{consec_increase}个季度股东户数增加，散户数量上升。"
            "需关注是否伴随业绩恶化或机构减持。"
        )
    else:
        trend = "筹码震荡"
        signal = "⚪ 中性"
        interpretation = "股东户数有增有减，无明显趋势，筹码结构处于博弈阶段。"

    # ── Supplement: check for extreme concentration ──
    hf = latest.get("hold_focus", 0)
    hf_raw = latest.get("hold_focus_raw", "")
    if hf > 70:
        interpretation += f" 当前筹码集中度{hf:.1f}%（极度集中），股价容易被少数资金影响。"
    elif hf > 40:
        interpretation += f" 当前筹码集中度{hf:.1f}%（较为集中）。"
    elif hf == 0 and hf_raw:
        interpretation += f" 筹码集中度：{hf_raw}。"
    elif hf < 20 and hf > 0:
        interpretation += f" 当前筹码集中度{hf:.1f}%（较为分散），无主力控盘迹象。"

    if latest.get("top10_hold_pct") and latest["top10_hold_pct"] > 60:
        interpretation += " 前十大股东持股超60%，筹码高度锁定。"

    result = {
        "symbol": symbol,
        "latest": latest,
        "quarters": quarters,
        "consec_decrease": consec_decrease,
        "consec_increase": consec_increase,
        "qoq_change": qoq_change,
        "two_q_change": two_q_change,
        "four_q_change": four_q_change,
        "trend": trend,
        "signal": signal,
        "interpretation": interpretation,
    }

    return result


def print_shareholder_report(result: dict):
    """打印股东户数分析报告。"""
    if result.get("error"):
        print(f"❌ {result['error']}")
        return

    symbol = result["symbol"]
    latest = result["latest"]
    quarters = result["quarters"]

    print(f"\n{'='*60}")
    print(f"【散户数量分析：{symbol}】")
    print(f"{'='*60}")

    # ── Latest data ──
    print(f"\n📊 最新数据（{latest['date']}）：")
    print(f"  股东总户数：{latest['holders']:,} 户")
    change_word = "减少" if latest["holder_change_pct"] < 0 else "增加"
    print(f"  较上期变化：{change_word} {abs(latest['holder_change_pct']):.1f}%（{abs(latest['holder_change_abs']):,} 户）")
    print(f"  人均持股：{latest['avg_free_shares']:,} 股（{latest['avg_share_change_pct']:+.1f}%）")
    print(f"  人均持股市值：¥{latest['avg_hold_amt']:,}")
    print(f"  筹码集中度：{latest['hold_focus']:.1f}%")
    if latest.get("top10_hold_pct"):
        print(f"  前十大股东持股：{latest['top10_hold_pct']:.1f}%")

    # ── Trend table ──
    print(f"\n📈 近4季度股东户数变化：\n")
    header = "| 报告期 | 股东户数 | 较上期变化 | 人均持股 | 人均持股变化 | 筹码集中度 |"
    sep = "|--------|---------|-----------|---------|------------|-----------|"
    print(header)
    print(sep)
    for q in quarters[:min(4, len(quarters))]:
        chg = f"{q['holder_change_pct']:+.1f}%"
        avg_chg = f"{q['avg_share_change_pct']:+.1f}%"
        print(f"| {q['date']} | {q['holders']:,} | {chg} | {q['avg_free_shares']:,} | {avg_chg} | {q['hold_focus']:.1f}% |")

    # ── Long-term trend ──
    if result.get("four_q_change") is not None:
        print(f"\n📐 中期趋势：")
        print(f"  近1季度变化：{result['qoq_change']:+.1f}%")
        print(f"  近2季度变化：{result['two_q_change']:+.1f}%")
        print(f"  近4季度变化：{result['four_q_change']:+.1f}%")

    # ── Verdict ──
    print(f"\n{'='*60}")
    print(f"趋势判断：{result['trend']}")
    print(f"信号：{result['signal']}")
    print(f"\n解读：{result['interpretation']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    symbol = "002428"
    get_ak_a_stock_price(symbol)
    check_intraday_avg(symbol)
    check_ma_status(symbol)
    check_strong_stock(symbol)
    comprehensive_judge(
        symbol,
        profit=True,
        reason="光模块缺货→磷化铟需求爆发→公司是国内磷化铟最大生产商，供需缺口超70%"
    )