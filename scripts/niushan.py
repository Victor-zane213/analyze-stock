"""
牛散持仓分析模块。
从 niushan.yaml 加载A股知名牛散名单，提供格式化输出功能。
实际数据获取依赖 WebSearch（无直接API），此模块负责配置加载和输出格式化。
"""

import os
import json

# ─── Config loading ───
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_CONFIG_PATH = os.path.join(_SKILL_DIR, "niushan.yaml")


def load_niushan_config() -> list:
    """Load niushan list from niushan.yaml. Returns list of dict."""
    try:
        import yaml
    except ImportError:
        print("错误：需要安装 pyyaml (pip3 install pyyaml)")
        return []

    if not os.path.exists(_CONFIG_PATH):
        print(f"错误：配置文件不存在: {_CONFIG_PATH}")
        return []

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    niushan_list = cfg.get("niushan", [])
    print(f"加载了 {len(niushan_list)} 位牛散")
    for n in niushan_list:
        print(f"  {n['name']} — {n['description']}")
    print()
    return niushan_list


def get_niushan_search_queries(niushan_list: list = None, current_year: int = 2026) -> dict:
    """
    Generate WebSearch queries for each niushan.
    Returns a dict mapping niushan name -> list of search queries.
    """
    if niushan_list is None:
        niushan_list = load_niushan_config()

    queries = {}
    for n in niushan_list:
        name = n["name"]
        kw = n.get("search_keywords", name)
        queries[name] = [
            f"{name} 最新持仓 十大流通股东 {current_year}",
            f"{name} 重仓股 {current_year}一季报",
        ]
    return queries


# ─────────────────────────────────────────
# Sector classification helpers
# ─────────────────────────────────────────

SECTOR_KEYWORDS = {
    "半导体/芯片": ["半导体", "芯片", "集成电路", "光刻", "EDA", "晶圆", "封测", "IGBT"],
    "AI/人工智能": ["AI", "人工智能", "大模型", "算力", "GPU", "算法", "机器学习"],
    "医药/生物": ["医药", "生物", "制药", "药", "CXO", "疫苗", "基因", "细胞", "诊断", "医疗器械"],
    "新能源/光伏/锂电": ["新能源", "光伏", "锂电", "电池", "储能", "逆变器", "风电", "氢能", "充电桩"],
    "消费/白酒": ["消费", "白酒", "食品", "饮料", "家电", "零售", "医美", "旅游"],
    "军工/国防": ["军工", "国防", "导弹", "雷达", "卫星", "航天", "航空"],
    "金融/地产": ["金融", "银行", "券商", "保险", "地产", "房地产"],
    "通信/5G": ["通信", "5G", "光纤", "光模块", "光通信", "6G"],
    "汽车/自动驾驶": ["汽车", "新能源车", "自动驾驶", "智能驾驶", "零部件"],
    "软件/信创": ["软件", "信创", "操作系统", "数据库", "网络安全", "SaaS"],
}


def classify_sector(stock_name: str, business_desc: str = "") -> list:
    """
    Classify a stock into sectors based on name/business keyword matching.
    Returns list of matching sector names.
    """
    text = (stock_name + " " + business_desc).lower()
    matched = []
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                matched.append(sector)
                break
    return matched if matched else ["其他"]


# ─────────────────────────────────────────
# Output formatting
# ─────────────────────────────────────────

def print_niushan_list(niushan_list: list):
    """Print loaded niushan list as a table."""
    print("| # | 牛散 | 特征 |")
    print("|---|------|------|")
    for i, n in enumerate(niushan_list, 1):
        print(f"| {i} | {n['name']} | {n['description']} |")
    print()


def print_sector_heatmap(sector_stats: dict, total_niushan: int):
    """
    Print sector heatmap from stats dict.

    :param sector_stats: dict of {sector_name: {"count": N, "investors": [...], "stocks": [...]}}
    :param total_niushan: total number of niushan analyzed
    """
    if not sector_stats:
        print("\n暂未获取到足够的持仓数据，无法生成板块热度。")
        return

    print(f"\n### 板块热度汇总（共 {total_niushan} 位牛散）\n")
    header = (
        "| 板块 | 看好牛散数 | 占比 | 代表牛散 | 代表个股 |\n"
        "|------|-----------|------|---------|---------|"
    )
    print(header)

    # Sort by count descending
    sorted_sectors = sorted(sector_stats.items(), key=lambda x: x[1]["count"], reverse=True)

    for sector, info in sorted_sectors:
        investors = "、".join(info["investors"][:4])
        if len(info["investors"]) > 4:
            investors += f"...({len(info['investors'])}位)"
        stocks = "、".join(info["stocks"][:3]) if info.get("stocks") else "—"
        pct = f"{info['count'] / total_niushan * 100:.0f}%"
        row = f"| {sector} | {info['count']} | {pct} | {investors} | {stocks} |"
        print(row)

    print()


def print_niushan_consensus(sector_stats: dict):
    """Print consensus analysis based on sector stats."""
    if not sector_stats or len(sector_stats) < 2:
        return

    sorted_sectors = sorted(sector_stats.items(), key=lambda x: x[1]["count"], reverse=True)

    print(f"### 牛散共识分析\n")

    # Most popular sector
    top = sorted_sectors[0]
    print(f"**最热门板块：** {top[0]}（{top[1]['count']} 位牛散重仓）")
    if len(sorted_sectors) >= 2:
        second = sorted_sectors[1]
        print(f"**次热门板块：** {second[0]}（{second[1]['count']} 位牛散配置）")

    # Find divergence (sectors with count=1)
    lone_sectors = [(s, i) for s, i in sorted_sectors if i["count"] == 1]
    if lone_sectors:
        names = [f"{s[0]}（{s[1]['investors'][0]}）" for s in lone_sectors]
        print(f"**独立看好：** {'、'.join(names)}")

    print()


def print_niushan_details(stocks_by_niushan: dict):
    """
    Print detailed holdings per niushan.

    :param stocks_by_niushan: dict of {niushan_name: [{"name": "...", "code": "...", "sector": "..."}]}
    """
    if not stocks_by_niushan:
        return

    print(f"### 各牛散最新持仓明细\n")

    for i, (name, stocks) in enumerate(stocks_by_niushan.items(), 1):
        print(f"#### {i}. {name}")
        if not stocks:
            print("  （暂无持仓数据）\n")
            continue

        # Categorize stocks by sector
        by_sector = {}
        for s in stocks:
            sector = s.get("sector", "其他")
            if sector not in by_sector:
                by_sector[sector] = []
            by_sector[sector].append(s)

        for sector, sector_stocks in by_sector.items():
            items = []
            for s in sector_stocks[:5]:
                code = s.get("code", "")
                name_s = s.get("name", "?")
                change = s.get("change", "")
                item = f"{name_s}（{code}）" if code else name_s
                if change:
                    item += f" [{change}]"
                items.append(item)
            print(f"  **{sector}：** {'、'.join(items)}")

        print()


def print_niushan_report(
    niushan_list: list,
    sector_stats: dict,
    stocks_by_niushan: dict,
):
    """Print the complete niushan analysis report."""
    total = len(niushan_list)
    print(f"\n{'='*60}")
    print(f" A股牛散持仓分析报告（{total} 位牛散）")
    print(f"{'='*60}")

    print_sector_heatmap(sector_stats, total)
    print_niushan_consensus(sector_stats)
    print_niushan_details(stocks_by_niushan)

    print(f"{'='*60}")
    print(f"> 数据来源：上市公司季报「十大流通股东」、东方财富、财经媒体\n")
    print(f"> 免责声明：牛散持仓数据基于公开季报披露，有滞后性，仅供参考。\n")


# ─────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法：")
        print("  python3 niushan.py list                  — 列出配置中的所有牛散")
        print("  python3 niushan.py search-queries        — 生成 WebSearch 查询关键词")
        print("  python3 niushan.py classify <stock_name> — 测试板块分类")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "list":
        niushan_list = load_niushan_config()
        print_niushan_list(niushan_list)

    elif cmd == "search-queries":
        niushan_list = load_niushan_config()
        queries = get_niushan_search_queries(niushan_list)
        for name, qs in queries.items():
            print(f"\n{name}:")
            for q in qs:
                print(f"  → {q}")

    elif cmd == "classify":
        name = sys.argv[2] if len(sys.argv) > 2 else "测试"
        sectors = classify_sector(name)
        print(f"'{name}' → 板块: {', '.join(sectors)}")
