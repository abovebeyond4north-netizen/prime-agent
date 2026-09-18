#!/usr/bin/env python3
"""Public x402 Bazaar market scanner.

Fetches Coinbase's public x402 discovery catalog, normalizes usage/price data,
flags likely inorganic activity, scores opportunities, and emits JSON/CSV/Markdown.
No API key or third-party Python package is required.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Iterable

DEFAULT_DISCOVERY_URL = "https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources"
BASE_USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
BASE_SEPOLIA_USDC = "0x036cbd53842c5426634e7929541ec2318f3dcf7e"
KNOWN_USDC = {BASE_USDC, BASE_SEPOLIA_USDC}

CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("search-retrieval", ("search", "web", "crawl", "scrape", "fetch", "extract", "url", "markdown")),
    ("enrichment-verification", ("enrich", "verify", "verification", "profile", "email", "company", "identity")),
    ("agent-tools", ("agent", "workflow", "mcp", "tool", "automation", "execute", "operation")),
    ("finance-onchain", ("crypto", "token", "wallet", "defi", "onchain", "market", "price", "transaction")),
    ("research-data", ("research", "dataset", "analytics", "report", "news", "data")),
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _text(resource: dict[str, Any]) -> str:
    parts = [resource.get("serviceName", ""), resource.get("description", "")]
    parts.extend(resource.get("tags") or [])
    parts.append(resource.get("resource", ""))
    return " ".join(str(p) for p in parts).lower()


def classify(resource: dict[str, Any]) -> str:
    text = _text(resource)
    best = (0, "other")
    for category, words in CATEGORY_RULES:
        hits = sum(1 for word in words if word in text)
        if hits > best[0]:
            best = (hits, category)
    return best[1]


def _usd_price(resource: dict[str, Any]) -> float | None:
    """Return price in USD for exact USDC requirements when safely inferable."""
    prices: list[float] = []
    for req in resource.get("accepts") or []:
        if not isinstance(req, dict):
            continue
        asset = str(req.get("asset", "")).lower()
        extra = req.get("extra") if isinstance(req.get("extra"), dict) else {}
        token_name = str(extra.get("name", "")).lower()
        token_symbol = str(extra.get("symbol", "")).lower()
        is_usdc = asset in KNOWN_USDC or "usd coin" in token_name or token_symbol == "usdc"
        if not is_usdc:
            continue
        raw = req.get("amount")
        try:
            atomic = int(str(raw))
        except (TypeError, ValueError):
            continue
        prices.append(atomic / 1_000_000)
    return min(prices) if prices else None


def _host(resource_url: str) -> str:
    try:
        return urllib.parse.urlparse(resource_url).netloc.lower()
    except Exception:
        return ""


@dataclass(frozen=True)
class MarketRow:
    resource: str
    host: str
    service_name: str
    category: str
    price_usd: float | None
    calls_30d: int
    unique_payers_30d: int
    calls_per_payer: float
    last_called_at: str | None
    age_days: float | None
    suspected_farming: bool
    repeat_demand: bool
    estimated_revenue_30d: float | None
    demand_score: float
    opportunity_score: float


def score_resource(resource: dict[str, Any], now: datetime | None = None) -> MarketRow:
    now = now or _utcnow()
    quality = resource.get("quality") if isinstance(resource.get("quality"), dict) else {}
    calls = max(0, int(quality.get("l30DaysTotalCalls") or 0))
    payers = max(0, int(quality.get("l30DaysUniquePayers") or 0))
    cpp = calls / payers if payers else 0.0
    last_called_raw = quality.get("lastCalledAt")
    last_called = _parse_time(last_called_raw)
    age_days = max(0.0, (now - last_called).total_seconds() / 86400.0) if last_called else None

    suspected_farming = calls >= 100 and payers >= 50 and (payers / max(calls, 1)) >= 0.85
    repeat_demand = payers >= 3 and cpp >= 3.0 and not suspected_farming

    recency = math.exp(-((age_days if age_days is not None else 30.0) / 14.0))
    breadth = math.log1p(payers)
    reuse = math.log1p(cpp)
    volume = math.log1p(calls)
    organic_multiplier = 0.08 if suspected_farming else (1.0 if repeat_demand else 0.35)
    demand = breadth * reuse * volume * recency * organic_multiplier

    price = _usd_price(resource)
    revenue = calls * price if price is not None else None
    monetization = math.log1p(max(revenue or 0.0, 0.0)) if price is not None else 0.5
    opportunity = demand * (1.0 + monetization)

    url = str(resource.get("resource") or "")
    return MarketRow(
        resource=url,
        host=_host(url),
        service_name=str(resource.get("serviceName") or ""),
        category=classify(resource),
        price_usd=price,
        calls_30d=calls,
        unique_payers_30d=payers,
        calls_per_payer=cpp,
        last_called_at=str(last_called_raw) if last_called_raw else None,
        age_days=age_days,
        suspected_farming=suspected_farming,
        repeat_demand=repeat_demand,
        estimated_revenue_30d=revenue,
        demand_score=demand,
        opportunity_score=opportunity,
    )


def fetch_catalog(base_url: str = DEFAULT_DISCOVERY_URL, limit: int = 500, timeout: int = 30) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    total: int | None = None
    while total is None or offset < total:
        query = urllib.parse.urlencode({"limit": limit, "offset": offset})
        req = urllib.request.Request(f"{base_url}?{query}", headers={"User-Agent": "prime-agent-x402-market/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.load(resp)
        items = payload.get("items") or []
        if not items:
            break
        rows.extend(items)
        offset += len(items)
        pagination = payload.get("pagination") or {}
        total = int(pagination.get("total") or offset)
        if len(items) < limit and offset >= total:
            break
        time.sleep(0.03)
    return rows


def analyze(resources: Iterable[dict[str, Any]], now: datetime | None = None) -> list[MarketRow]:
    scored = [score_resource(resource, now=now) for resource in resources]
    return sorted(scored, key=lambda row: row.opportunity_score, reverse=True)


def category_summary(rows: Iterable[MarketRow]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = buckets.setdefault(row.category, {
            "category": row.category,
            "resources": 0,
            "calls_30d": 0,
            "unique_payers_sum": 0,
            "estimated_revenue_30d": 0.0,
            "priced_resources": 0,
            "repeat_demand_resources": 0,
        })
        bucket["resources"] += 1
        bucket["calls_30d"] += row.calls_30d
        bucket["unique_payers_sum"] += row.unique_payers_30d
        bucket["repeat_demand_resources"] += int(row.repeat_demand)
        if row.estimated_revenue_30d is not None:
            bucket["estimated_revenue_30d"] += row.estimated_revenue_30d
            bucket["priced_resources"] += 1
    return sorted(buckets.values(), key=lambda b: (b["repeat_demand_resources"], b["calls_30d"]), reverse=True)


def to_markdown(rows: list[MarketRow], top: int) -> str:
    lines = [
        "| Rank | Service | Category | Price | Calls | Payers | Calls/Payer | Revenue est. | Organic | Score |",
        "|---:|---|---|---:|---:|---:|---:|---:|:---:|---:|",
    ]
    for i, row in enumerate(rows[:top], 1):
        name = row.service_name or row.host or row.resource
        price = f"${row.price_usd:.6g}" if row.price_usd is not None else "n/a"
        revenue = f"${row.estimated_revenue_30d:.2f}" if row.estimated_revenue_30d is not None else "n/a"
        lines.append(
            f"| {i} | {name[:48]} | {row.category} | {price} | {row.calls_30d} | "
            f"{row.unique_payers_30d} | {row.calls_per_payer:.2f} | {revenue} | "
            f"{'yes' if row.repeat_demand else 'no'} | {row.opportunity_score:.3f} |"
        )
    return "\n".join(lines)


def emit(rows: list[MarketRow], fmt: str, top: int) -> str:
    selected = rows[:top]
    if fmt == "json":
        return json.dumps({
            "generated_at": _utcnow().isoformat(),
            "count": len(rows),
            "top": [asdict(r) for r in selected],
            "categories": category_summary(rows),
        }, indent=2)
    if fmt == "markdown":
        return to_markdown(rows, top)
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(asdict(selected[0]).keys()) if selected else ["resource"])
    writer.writeheader()
    for row in selected:
        writer.writerow(asdict(row))
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rank public x402 Bazaar resources by observed demand and monetization signals.")
    parser.add_argument("--url", default=DEFAULT_DISCOVERY_URL)
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--format", choices=("json", "csv", "markdown"), default="markdown")
    parser.add_argument("--input", help="Analyze a saved Bazaar JSON response instead of fetching live data.")
    parser.add_argument("--output", help="Write output to this file instead of stdout.")
    args = parser.parse_args(argv)

    if args.input:
        with open(args.input, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        resources = payload.get("items", payload) if isinstance(payload, dict) else payload
    else:
        resources = fetch_catalog(args.url)
    rows = analyze(resources)
    output = emit(rows, args.format, max(1, args.top))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output)
    else:
        sys.stdout.write(output + ("\n" if not output.endswith("\n") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
