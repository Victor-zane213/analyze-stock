"""
A股选股筛选器：放量 + 价托 双条件筛选。

模式 J：放量+价托选股
- 条件1：昨日成交量 >= 前日成交量 × volume_ratio（默认 1.8 倍）
- 条件2：近 jiatuo_days（默认 10）个交易日内完成价托（10日上穿20日）
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd
import requests

sys.path.insert(0, "/Users/bertramliu/.claude/skills/financial-assistant/scripts")
from stock import _get_prefix, _HEADERS, detect_golden_triangle


# ── 股票池 ────────────────────────────────────────────

def get_stock_pool(exclude_st: bool = True, boards: list | None = None) -> list[tuple[str, str]]:
    """
    获取 A 股候选股票列表。
    :param exclude_st: 是否排除 ST/*ST
    :param boards: 限定板块，如 ['主板', '创业板', '科创板']，None 表示全部
    :return: [(代码, 名称), ...]
    """
    import akshare as ak

    df = ak.stock_info_a_code_name()
    codes = []

    for _, row in df.iterrows():
        code = row["code"]
        name = row["name"]

        if exclude_st and ("ST" in name or "*ST" in name):
            continue

        if boards:
            if code.startswith("60") and "主板" not in boards:
                continue
            if code.startswith("00") and "主板" not in boards:
                continue
            if code.startswith("30") and "创业板" not in boards:
                continue
            if code.startswith("688") and "科创板" not in boards:
                continue

        codes.append((code, name))

    return codes


# ── K 线获取与条件判断 ────────────────────────────────

def _fetch_kline(symbol: str, count: int = 80) -> list | None:
    """获取单只股票的日K线数据（前复权），返回原始 list 或 None。"""
    prefix = _get_prefix(symbol)
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {"param": f"{prefix}{symbol},day,,,{count},qfq"}

    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=8)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    data = resp.json()
    klines = data.get("data", {}).get(f"{prefix}{symbol}", {}).get("qfqday", [])
    if not klines or len(klines) < 25:
        return None
    return klines


def check_single_stock(
    code: str, name: str, volume_ratio: float = 1.8, jiatuo_days: int = 10
) -> dict | None:
    """
    检查单只股票是否满足两个条件。

    :return: dict 包含筛选详情，不满足则返回 None
    """
    klines = _fetch_kline(code, count=80)
    if not klines:
        return None

    # ── 条件1：昨日成交量 >= 前日 × volume_ratio ──
    # K线数据按时间升序，最后一条是最近交易日
    if len(klines) < 2:
        return None

    yesterday_vol = float(klines[-1][5])
    day_before_vol = float(klines[-2][5])
    if day_before_vol <= 0:
        return None

    vol_ratio_actual = yesterday_vol / day_before_vol
    if vol_ratio_actual < volume_ratio:
        return None

    # ── 条件2：近 jiatuo_days 日内有价托 ──
    gt = detect_golden_triangle(code, lookback=80, fresh_days=20)
    if not gt.get("cross_10_20_date"):
        return None

    days_since = gt["days_since_complete"]
    if days_since is None or days_since > jiatuo_days:
        return None

    # ── 提取附加指标 ──
    latest_open = float(klines[-1][1])
    latest_close = float(klines[-1][2])
    latest_high = float(klines[-1][3])
    latest_low = float(klines[-1][4])
    change_pct = (latest_close - float(klines[-2][2])) / float(klines[-2][2]) * 100 if len(klines) >= 2 else 0

    # 均线
    closes = [float(k[2]) for k in klines]
    volumes = [float(k[5]) for k in klines]
    ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else 0
    ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else 0
    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else 0
    avg_vol_20 = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else yesterday_vol

    return {
        "code": code,
        "name": name,
        "price": round(latest_close, 2),
        "change_pct": round(change_pct, 2),
        "vol_ratio": round(vol_ratio_actual, 2),
        "yesterday_vol": int(yesterday_vol),
        "day_before_vol": int(day_before_vol),
        "vol_vs_20avg": round(yesterday_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 0,
        "ma5": round(ma5, 2),
        "ma10": round(ma10, 2),
        "ma20": round(ma20, 2),
        "jiatuo_days": days_since,
        "jiatuo_label": gt["label"],
        "jiatuo_cross_date": gt["cross_10_20_date"],
        "bullish_alignment": gt["bullish_alignment"],
        "volume_confirm": gt["volume_confirm"],
    }


# ── 主筛选函数 ─────────────────────────────────────────

def screen_volume_jiatuo(
    volume_ratio: float = 1.8,
    jiatuo_days: int = 10,
    exclude_st: bool = True,
    boards: list | None = None,
    max_workers: int = 30,
    top_n: int = 50,
    verbose: bool = True,
) -> list[dict]:
    """
    主力筛选：放量 + 近期价托。

    :param volume_ratio: 放量倍数阈值（昨日量 / 前日量）
    :param jiatuo_days: 价托必须在最近 N 个交易日内完成
    :param exclude_st: 排除 ST
    :param boards: 限定板块
    :param max_workers: 并发线程数
    :param top_n: 返回前 N 只（按放量倍数降序）
    :param verbose: 是否打印进度
    :return: 符合条件的股票列表
    """
    stock_pool = get_stock_pool(exclude_st=exclude_st, boards=boards)
    total = len(stock_pool)

    if verbose:
        board_label = ", ".join(boards) if boards else "全市场"
        print(f"📊 选股池：{board_label}，共 {total} 只（已排除ST）")
        print(f"🔍 条件：昨日量 >= 前日量 × {volume_ratio}  |  价托 ≤ {jiatuo_days} 日")
        print(f"⚡ 并发线程：{max_workers}")
        print(f"{'─' * 55}")

    results = []
    done = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(check_single_stock, code, name, volume_ratio, jiatuo_days): (code, name)
            for code, name in stock_pool
        }

        for future in as_completed(futures):
            done += 1
            if verbose and done % 500 == 0:
                elapsed = time.time() - start_time
                rate = done / elapsed
                hits = len(results)
                print(f"  进度：{done}/{total}（{done * 100 / total:.0f}%） | "
                      f"命中 {hits} 只 | 速率 {rate:.0f} 只/秒")

            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception:
                pass

    elapsed = time.time() - start_time
    results.sort(key=lambda x: x["vol_ratio"], reverse=True)

    if verbose:
        print(f"{'─' * 55}")
        print(f"✅ 筛选完成！耗时 {elapsed:.1f} 秒，命中 {len(results)} 只")
        if len(results) > top_n:
            print(f"   显示 Top {top_n}（按放量倍数降序）")

    return results[:top_n]


# ── 输出格式化 ─────────────────────────────────────────

def print_screen_results(results: list[dict], volume_ratio: float = 1.8, jiatuo_days: int = 10):
    """打印筛选结果表格。"""
    if not results:
        print("\n❌ 无符合条件的股票。")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n## 放量+价托 选股结果（{now}）\n")
    print(f"> 条件：昨日成交量 ≥ 前日 × {volume_ratio}  |  价托完成 ≤ {jiatuo_days} 个交易日")
    print(f"> 命中 {len(results)} 只\n")

    # 表头
    header = (
        f"{'排名':<5} {'代码':<8} {'名称':<10} {'现价':>8} {'涨跌%':>8} "
        f"{'放量倍':>7} {'价托日':<12} {'5日线':>8} {'10日线':>8} {'20日线':>8} {'多头':>5}"
    )
    print(header)
    print("─" * len(header))

    for i, r in enumerate(results, 1):
        line = (
            f"{i:<5} {r['code']:<8} {r['name']:<10} {r['price']:>8.2f} {r['change_pct']:>+7.2f}% "
            f"{r['vol_ratio']:>6.2f}x  {r['jiatuo_cross_date']:<12} "
            f"{r['ma5']:>8.2f} {r['ma10']:>8.2f} {r['ma20']:>8.2f} "
            f"{'✅' if r['bullish_alignment'] else '❌':>5}"
        )
        print(line)

    print()
    # 统计摘要
    avg_ratio = sum(r["vol_ratio"] for r in results) / len(results)
    up_count = sum(1 for r in results if r["change_pct"] > 0)
    alignment_count = sum(1 for r in results if r["bullish_alignment"])
    print(f"📈 统计：平均放量 {avg_ratio:.2f}x | 上涨 {up_count}/{len(results)} | "
          f"多头排列 {alignment_count}/{len(results)}")

    print()
    for i, r in enumerate(results, 1):
        print(f"  {i:>2}. {r['name']:　<6s} {r['code']} | "
              f"{r['price']:.2f} ({r['change_pct']:+.2f}%) | "
              f"放量 {r['vol_ratio']:.2f}x | "
              f"价托 {r['jiatuo_days']}日前 | "
              f"多头{'✅' if r['bullish_alignment'] else '❌'} "
              f"量能{'✅' if r['volume_confirm'] else '❌'}")


# ── JSON 输出（供后续处理） ────────────────────────────

def screen_to_json(results: list[dict]) -> str:
    """将筛选结果转为 JSON 字符串。"""
    return json.dumps(results, ensure_ascii=False, indent=2)


# ── CLI 入口 ───────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A股放量+价托选股筛选器")
    parser.add_argument("--volume-ratio", type=float, default=1.8, help="放量倍数阈值（默认 1.8）")
    parser.add_argument("--jiatuo-days", type=int, default=10, help="价托最大天数（默认 10）")
    parser.add_argument("--boards", nargs="*", default=None, help="限定板块，如：主板 创业板 科创板")
    parser.add_argument("--workers", type=int, default=30, help="并发线程数（默认 30）")
    parser.add_argument("--top-n", type=int, default=50, help="返回前 N 只（默认 50）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")

    args = parser.parse_args()

    results = screen_volume_jiatuo(
        volume_ratio=args.volume_ratio,
        jiatuo_days=args.jiatuo_days,
        boards=args.boards,
        max_workers=args.workers,
        top_n=args.top_n,
    )

    if args.json:
        print(screen_to_json(results))
    else:
        print_screen_results(results, volume_ratio=args.volume_ratio, jiatuo_days=args.jiatuo_days)
