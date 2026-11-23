"""Turn parish night lights into recovery measures after Hurricane Melissa.

Inputs:  data/processed/ntl_daily_parish.csv, ntl_monthly_parish.csv
         data/raw/grade_melissa_damage_by_parish.csv (World Bank GRADE)
Outputs: data/processed/recovery_daily.csv, recovery_summary.csv, summary.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

LANDFALL = pd.Timestamp("2025-10-28")
BASE_START, BASE_END = pd.Timestamp("2025-09-01"), pd.Timestamp("2025-10-26")
MOST_DAMAGED = ["st_elizabeth", "westmoreland", "st_james", "trelawny", "hanover"]


def daily():
    d = pd.read_csv(PROC / "ntl_daily_parish.csv", parse_dates=["date"])
    d = d.sort_values(["parish", "date"])
    base = d[(d.date >= BASE_START) & (d.date <= BASE_END)].groupby("parish")["sum"].median()
    d["baseline"] = d.parish.map(base)
    d["ratio"] = d["sum"] / d["baseline"]
    # A centred 7 day median smooths cloud and gap fill noise.
    d["ratio_7d"] = d.groupby("parish")["ratio"].transform(lambda s: s.rolling(7, center=True, min_periods=4).median())
    d["days_since_landfall"] = (d.date - LANDFALL).dt.days
    return d


def first_day_at(sub, level, hold=7):
    """First day after the low point from which the smoothed share stays at or above
    level for `hold` days in a row. Starting from the low point stops the pre-storm
    days inside the centred window counting as recovery."""
    post = sub[(sub.days_since_landfall >= 1)].sort_values("days_since_landfall")
    early = post[post.days_since_landfall <= 30]
    if early.ratio_7d.dropna().empty:
        return np.nan
    trough = int(early.loc[early.ratio_7d.idxmin(), "days_since_landfall"])
    after = post[post.days_since_landfall >= trough]
    ok = (after.ratio_7d >= level).astype(int).values
    days = after.days_since_landfall.values
    run = 0
    for i, v in enumerate(ok):
        run = run + 1 if v else 0
        if run == hold:
            return int(days[i - hold + 1])
    return np.nan


def summarise(d):
    rows = []
    for p, sub in d.groupby("parish"):
        def at(day):
            s = sub[sub.days_since_landfall == day].ratio_7d
            return float(s.iloc[0]) if len(s) else np.nan
        post = sub[(sub.days_since_landfall >= 1) & (sub.days_since_landfall <= 95)]
        rows.append({
            "parish": p,
            "share_day_3": at(3), "share_day_7": at(7), "share_day_30": at(30), "share_day_60": at(60),
            "lowest_share": float(post.ratio_7d.min()),
            "days_to_80": first_day_at(sub, 0.8), "days_to_90": first_day_at(sub, 0.9),
            # Lost light, in parish-days of normal light, over the first 95 days.
            "light_days_lost": float((1 - post.ratio_7d.clip(upper=1)).sum()),
        })
    s = pd.DataFrame(rows)
    dmg = pd.read_csv(RAW / "grade_melissa_damage_by_parish.csv")
    s = s.merge(dmg, on="parish", how="left")
    s["most_damaged"] = s.parish.isin(MOST_DAMAGED)
    return s.sort_values("light_days_lost", ascending=False)


def monthly():
    path = PROC / "ntl_monthly_parish.csv"
    if not path.exists():
        return None
    m = pd.read_csv(path, parse_dates=["date"])
    m["month"] = m.date.dt.to_period("M")
    tot = m.groupby("month")["sum"].sum()
    yoy = (tot / tot.shift(12) - 1) * 100
    return pd.DataFrame({"national_sum": tot, "yoy_pct": yoy}).reset_index().assign(month=lambda x: x.month.astype(str))


def main():
    d = daily()
    d.to_csv(PROC / "recovery_daily.csv", index=False)
    s = summarise(d)
    s.to_csv(PROC / "recovery_summary.csv", index=False)
    m = monthly()
    if m is not None:
        m.to_csv(PROC / "national_monthly.csv", index=False)

    nat = d.groupby("date").agg(total=("sum", "sum")).reset_index()
    nat["ratio"] = nat.total / nat[(nat.date >= BASE_START) & (nat.date <= BASE_END)].total.median()
    nat["ratio_7d"] = nat.ratio.rolling(7, center=True, min_periods=4).median()
    nat["days_since_landfall"] = (nat.date - LANDFALL).dt.days
    nat.to_csv(PROC / "recovery_national.csv", index=False)

    md, rest = s[s.most_damaged], s[~s.most_damaged]
    corr = float(np.corrcoef(s.damage_pct_of_exposed_value, s.light_days_lost)[0, 1])
    out = {
        "data_through": str(d.date.max().date()),
        "national_share_day_7": float(nat.loc[nat.days_since_landfall == 7, "ratio_7d"].iloc[0]),
        "national_days_to_90": first_day_at(nat.assign(parish="all"), 0.9),
        "most_damaged_share_day_30": float(md.share_day_30.mean()),
        "rest_share_day_30": float(rest.share_day_30.mean()),
        "most_damaged_light_days_lost": float(md.light_days_lost.mean()),
        "rest_light_days_lost": float(rest.light_days_lost.mean()),
        "corr_damage_vs_light_lost": corr,
        "slowest_parish": s.sort_values("days_to_90", ascending=False, na_position="first").parish.iloc[0],
    }
    (PROC / "summary.json").write_text(json.dumps(out, indent=1, default=lambda x: None if pd.isna(x) else x))
    print(json.dumps(out, indent=1, default=str))
    print(s.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
