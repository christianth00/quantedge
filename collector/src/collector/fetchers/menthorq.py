
from __future__ import annotations
import json
import logging
from collector.http import GetText
from collector.store import Store

log = logging.getLogger(__name__)

async def fetch_menthorq(tickers: list[str], token: str, store: Store, get_text: GetText) -> str:
    url = "https://api.menthorq.io/getDailyLevels"
    out = {}
    
    headers = {
        "X-Api-Key": token
    }

    for ticker in tickers:
        try:
            params = {
                "ticker": ticker,
                "level_type": "gamma",
                "platform": "quantower",
                "user_id": "osbloom"
            }
            res = await get_text(url, params=params, headers=headers)
            data = json.loads(res)
            
            levels_array = data.get("levels", [])
            if levels_array:
                # Get the first item from the levels array
                level_values = levels_array[0].get("level_values", [])
                out[ticker] = {item["name"]: item["value"] for item in level_values}
            else:
                log.warning("No levels returned for MenthorQ ticker %s", ticker)

        except Exception as e:
            log.warning("MenthorQ fetch failed for %s: %s", ticker, e)
            
    store.put_doc("menthorq_levels", out, "menthorq")
    return "menthorq"

