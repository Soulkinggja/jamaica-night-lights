"""Download NASA Black Marble night lights for Jamaica and sum them by parish.

Runs in GitHub Actions (it needs internet access to NASA). It writes one CSV per
product to data/processed and keeps going if a month fails.

Environment:
    NASA_TOKEN  NASA Earthdata bearer token (stored as a GitHub secret)

Products:
    VNP46A2  daily, moonlight and atmosphere corrected, gap filled (500 m)
    VNP46A3  monthly composite (500 m)
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.polygon import orient
import pandas as pd
from blackmarble import bm_raster
from exactextract import exact_extract

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
CACHE = ROOT / ".cache" / "blackmarble"
for p in (RAW, OUT, CACHE):
    p.mkdir(parents=True, exist_ok=True)

TOKEN = os.environ.get("NASA_TOKEN", "")
DAILY_VAR = "Gap_Filled_DNB_BRDF-Corrected_NTL"
MONTHLY_VAR = "NearNadir_Composite_Snow_Free"
DAILY_START, DAILY_END = dt.date(2025, 9, 1), dt.date(2026, 2, 28)
MONTHLY_START = dt.date(2022, 1, 1)


def slug(name: str) -> str:
    s = name.lower().replace("saint ", "st ").replace("st. ", "st ")
    return "".join(c if c.isalnum() else "_" for c in s).strip("_")


def clockwise(geom):
    """Plotly's map draws rings wound clockwise; standard GeoJSON winds them the other way."""
    if isinstance(geom, Polygon):
        return orient(geom, sign=-1.0)
    if isinstance(geom, MultiPolygon):
        return MultiPolygon([orient(p, sign=-1.0) for p in geom.geoms])
    return geom


def parishes() -> gpd.GeoDataFrame:
    """Jamaica's 14 parishes from geoBoundaries (CC BY 4.0)."""
    path = RAW / "jamaica_parishes.geojson"
    if not path.exists():
        meta = json.load(urllib.request.urlopen(
            "https://www.geoboundaries.org/api/current/gbOpen/JAM/ADM1/"))
        urllib.request.urlretrieve(meta["gjDownloadURL"], path)
    g = gpd.read_file(path).to_crs(4326)
    g["parish"] = g["shapeName"].map(slug)
    g = g[["parish", "geometry"]]
    # A light copy for the app's map.
    light = g.copy()
    light["geometry"] = light.geometry.simplify(0.003, preserve_topology=True).map(clockwise)
    light.to_file(OUT / "parishes_simplified.geojson", driver="GeoJSON")
    return g


def zonal(g: gpd.GeoDataFrame, product: str, dates: list, variable: str) -> pd.DataFrame:
    ds = bm_raster(g, product_id=product, date_range=dates, token=TOKEN,
                   variable=variable, output_directory=CACHE, output_skip_if_exists=True)
    da = ds[variable]
    if da.rio.crs is None:
        da = da.rio.write_crs(4326)
    rows = []
    for t in da["time"].values:
        r = da.sel(time=t)
        stats = exact_extract(r, g, ["sum", "mean", "count"], include_cols=["parish"], output="pandas")
        stats["date"] = pd.Timestamp(t).date()
        rows.append(stats)
    return pd.concat(rows, ignore_index=True)


def months(a: dt.date, b: dt.date):
    d = a.replace(day=1)
    while d <= b:
        yield d
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)


def run_daily(g):
    out = OUT / "ntl_daily_parish.csv"
    done = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=["date"])
    have = set(done["date"].astype(str))
    parts = [done] if len(done) else []
    for m in months(DAILY_START, DAILY_END):
        end = min((m.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1), DAILY_END)
        dates = [m + dt.timedelta(days=i) for i in range((end - m).days + 1)]
        dates = [d for d in dates if str(d) not in have]
        if not dates:
            continue
        try:
            parts.append(zonal(g, "VNP46A2", dates, DAILY_VAR))
            print(f"daily {m:%Y-%m}: {len(dates)} days", flush=True)
            pd.concat(parts).to_csv(out, index=False)  # save as we go
        except Exception as e:  # a missing tile or a NASA outage should not stop the run
            print(f"daily {m:%Y-%m} failed: {e}", flush=True)


def run_monthly(g):
    out = OUT / "ntl_monthly_parish.csv"
    last = dt.date.today().replace(day=1) - dt.timedelta(days=45)
    dates = list(months(MONTHLY_START, last))
    try:
        df = zonal(g, "VNP46A3", dates, MONTHLY_VAR)
        df.to_csv(out, index=False)
        print(f"monthly: {len(dates)} months", flush=True)
    except Exception as e:
        print(f"monthly failed: {e}", flush=True)


if __name__ == "__main__":
    if not TOKEN:
        sys.exit("NASA_TOKEN is not set. Add it as a repository secret.")
    g = parishes()
    print("parishes:", sorted(g.parish), flush=True)
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "monthly"):
        run_monthly(g)
    if which in ("all", "daily"):
        run_daily(g)
