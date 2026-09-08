"""Read-only JSON API. App factory so tests inject their own store/config."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from collector.changes import apply_transform, to_bands
from collector.config import Config
from collector.panels import build_dashboard
from collector.store import Store

RANGE_DAYS = {"1y": 365, "5y": 5 * 365, "10y": 10 * 365}


def _fetcher_healthy(f: dict) -> bool:
    if not f["last_error_at"]:
        return True
    if not f["last_success"]:
        return False
    return f["last_success"] >= f["last_error_at"]


def create_app(store: Store, cfg: Config) -> FastAPI:
    app = FastAPI(title="os-bloom collector", docs_url=None, redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])
    series_by_id = {s.id: s for s in cfg.series}
    cycle_by_id = {s.id: s for s in cfg.cycle_series}
    index_names = {i.symbol: i.name for i in cfg.indexes}
    bond_names = {f"{b.country}{b.tenor}": f"{b.country} {b.tenor} yield" for b in cfg.bonds}
    cb_names = {f"{c.country}CB": c.label for c in cfg.cb_rates}
    ref_labels = {}
    for a in cfg.refs.aave:
        ref_labels[a.supply_id] = a.supply_label
        ref_labels[a.borrow_id] = a.borrow_label
    for p in cfg.refs.pendle:
        ref_labels[p.implied_id] = p.implied_label
        ref_labels[p.underlying_id] = p.underlying_label
    for f in cfg.refs.funding:
        ref_labels[f.id] = f.label

    @app.get("/api/dashboard")
    def dashboard() -> dict:
        return build_dashboard(store, cfg.indexes, now=datetime.now(timezone.utc),
                               cycle_series=cfg.cycle_series, cycle_tabs=cfg.cycle_tabs)

    @app.get("/api/series/{series_id}")
    def series(series_id: str, range: Literal["1y", "5y", "10y", "max"] = "10y") -> dict:
        scfg = series_by_id.get(series_id)
        if scfg is not None:
            points = apply_transform(store.points(f"macro:{series_id}"), scfg.transform)
            name, unit = scfg.name, scfg.unit
        elif series_id in cycle_by_id:
            ccfg = cycle_by_id[series_id]
            points = apply_transform(store.points(f"cycle:{series_id}"), ccfg.transform)
            name, unit = ccfg.name, ccfg.unit
        elif series_id in ref_labels:
            points = store.points(f"ref:{series_id}")  # already daily percent, no transform
            name, unit = ref_labels[series_id], "%"
        elif series_id in index_names:
            points = store.points(f"idx:{series_id}")
            name, unit = index_names[series_id], "px"
        elif series_id in bond_names:
            points = store.points(f"yield:{series_id}")
            name, unit = bond_names[series_id], "%"
        elif series_id in cb_names:
            points = store.points(f"cb:{series_id[:-2]}")  # USCB -> cb:US
            name, unit = cb_names[series_id], "%"
        else:
            raise HTTPException(status_code=404, detail=f"unknown series: {series_id}")
        if range != "max":
            cutoff = (datetime.now(timezone.utc) - timedelta(days=RANGE_DAYS[range])).date()
            points = {d: v for d, v in points.items() if d >= cutoff}
        return {
            "id": series_id, "name": name, "unit": unit,
            "points": [[d.isoformat(), v] for d, v in sorted(points.items())],
        }

    @app.get("/api/recessions")
    def recessions() -> dict:
        bands = to_bands(store.points("cycle:usrec"))
        return {"bands": [[a.isoformat(), b.isoformat()] for a, b in bands]}

    @app.get("/api/backtest")
    def run_backtest(symbols: str = "GC", strategy: str = "gex_confluence", start: str = "2026-08-01", end: str = "2026-09-08", stop: str = "40", target: str = "80") -> dict:
        import subprocess
        import os
        from glob import glob
        
        cwd = os.path.join(os.path.dirname(__file__), '..', 'backtester')
        
        # Clean up old reports
        for f in glob(os.path.join(cwd, 'reports', '*.txt')):
            os.remove(f)

        sym_list = symbols.split(",") if symbols else ["GC"]

        try:
            # We want to override the stop and target ticks for the specific strategy.
            # We can write a temporary yaml config to pass to the engine!
            import yaml
            override_cfg = {
                "default_stop_ticks": int(stop),
                "default_target_ticks": int(target)
            }
            cfg_path = os.path.join(cwd, "config", "ui_override.yaml")
            with open(cfg_path, "w") as f:
                yaml.dump(override_cfg, f)

            cmd = [
                'python', 'main.py', '--generate-synthetic', '--symbols'
            ] + sym_list + [
                '--strategy', strategy, '--config', cfg_path,
                '--start', start, '--end', end, '--report'
            ]
            
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
            
            output = f"Command: {' '.join(cmd)}\n\n"
            output += result.stdout + "\n" + result.stderr
            
            # Read report
            report_files = glob(os.path.join(cwd, 'reports', '*.txt'))
            if report_files:
                with open(report_files[-1], 'r') as f:
                    output += "\n\n=== REPORT ===\n" + f.read()
            
            return {"status": "success", "output": output}
        except Exception as e:
            return {"status": "error", "output": str(e)}

    @app.get("/api/dynamic-stop")
    def dynamic_stop(symbol: str = "GC") -> dict:
        import os
        import sys
        cwd = os.path.join(os.path.dirname(__file__), '..', 'backtester')
        sys.path.append(cwd)
        
        try:
            from stop_loss import RegimeStopLossCalculator
            import pandas as pd
            import numpy as np
            
            # Fetch synthetic data or real data
            # For demonstration, we use synthetic data simulating recent volatility
            dates = pd.date_range("2026-01-01", periods=100)
            df = pd.DataFrame({
                "Close": np.linspace(2000, 2100, 100) + np.random.normal(0, 10, 100),
                "High": np.linspace(2005, 2105, 100) + np.random.normal(0, 10, 100),
                "Low": np.linspace(1995, 2095, 100) - np.random.normal(0, 10, 100),
            }, index=dates)
            
            calc = RegimeStopLossCalculator(n_components=2)
            res = calc.calculate_dynamic_stop(df, base_stop_ticks=40)
            res["symbol"] = symbol
            return res
        except Exception as e:
            return {"error": str(e)}

    @app.get("/api/menthorq")
    def menthorq() -> dict:
        d = store.doc("menthorq_levels")
        return d.payload if d else {}

    @app.get("/healthz")
    def healthz() -> dict:
        fetchers = store.statuses()
        return {"ok": all(_fetcher_healthy(f) for f in fetchers), "fetchers": fetchers}

    return app







