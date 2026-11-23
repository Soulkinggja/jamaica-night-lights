"""Jamaica Night Lights Recovery Tracker

How fast each parish got its lights back after Hurricane Melissa, measured from
NASA Black Marble satellite images.

Run locally:  streamlit run app.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent
PROC = ROOT / "data" / "processed"

BLUE = "#2a78d6"
ORANGE = "#e07b39"
GREY = "#a3a29b"
INK = "#0b0b0b"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
MOST_DAMAGED = ["st_elizabeth", "westmoreland", "st_james", "trelawny", "hanover"]
NAMES = {"st_elizabeth": "St. Elizabeth", "westmoreland": "Westmoreland", "st_james": "St. James",
         "trelawny": "Trelawny", "hanover": "Hanover", "manchester": "Manchester", "st_ann": "St. Ann",
         "clarendon": "Clarendon", "st_catherine": "St. Catherine", "st_andrew": "St. Andrew",
         "st_mary": "St. Mary", "portland": "Portland", "st_thomas": "St. Thomas", "kingston": "Kingston"}

st.set_page_config(page_title="Jamaica Night Lights Recovery", page_icon="🌃", layout="wide")


def style(fig, height=380, ytitle=None):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="white",
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(color=INK, size=13),
                      legend=dict(orientation="h", y=1.1, x=0))
    fig.update_xaxes(showgrid=False, linecolor=AXIS)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, title=ytitle)
    return fig


st.title("Jamaica Night Lights Recovery Tracker")
st.caption("How fast each parish got its lights back after Hurricane Melissa (landfall 28 October 2025), "
           "measured from NASA Black Marble satellite images of the island at night.")

if not (PROC / "recovery_daily.csv").exists():
    st.info("The satellite data is being processed. The pipeline runs in GitHub Actions and "
            "fills this page once NASA's files are downloaded.")
    st.stop()

d = pd.read_csv(PROC / "recovery_daily.csv", parse_dates=["date"])
s = pd.read_csv(PROC / "recovery_summary.csv")
nat = pd.read_csv(PROC / "recovery_national.csv", parse_dates=["date"])
S = json.loads((PROC / "summary.json").read_text())
d["name"] = d.parish.map(NAMES)
s["name"] = s.parish.map(NAMES)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Island's light, one week after landfall", f"{S['national_share_day_7']:.0%}", help="Share of normal night light, 7 day median.")
c2.metric("Days until the island reached 90%", f"{S['national_days_to_90']:.0f}" if S["national_days_to_90"] else "Not yet")
c3.metric("Five hardest hit parishes at day 30", f"{S['most_damaged_share_day_30']:.0%}",
          f"rest of island {S['rest_share_day_30']:.0%}", delta_color="off")
c4.metric("Link between damage and lost light", f"{S['corr_damage_vs_light_lost']:.2f}",
          help="Correlation across the 14 parishes between World Bank damage share and light lost.")

st.divider()
st.subheader("How the lights came back, parish by parish")
st.write("Each line is a parish's night light as a share of its normal level before the storm (1 September to "
         "26 October 2025), smoothed over seven days. The five parishes the World Bank estimates were hit "
         "hardest are in orange.")
pick = st.multiselect("Highlight parishes", sorted(NAMES.values()), default=["St. Elizabeth", "Westmoreland", "Kingston"])
win = d[(d.days_since_landfall >= -20) & (d.days_since_landfall <= 100)]
fig = go.Figure()
for p, sub in win.groupby("parish"):
    hot = NAMES[p] in pick
    color = ORANGE if p in MOST_DAMAGED else BLUE
    fig.add_scatter(x=sub.days_since_landfall, y=sub.ratio_7d, mode="lines", name=NAMES[p],
                    line=dict(color=color if hot else GREY, width=2.5 if hot else 1),
                    opacity=1 if hot else 0.45, showlegend=hot,
                    hovertemplate=NAMES[p] + "<br>day %{x}: %{y:.0%}<extra></extra>")
fig.add_vline(x=0, line=dict(color=AXIS, dash="dash"))
fig.add_hline(y=1, line=dict(color=AXIS, width=1))
fig.update_yaxes(tickformat=".0%", rangemode="tozero")
fig.update_xaxes(title="Days since landfall")
st.plotly_chart(style(fig, 420, "Share of normal light"), width="stretch")

st.divider()
left, right = st.columns([1.1, 1])
with left:
    st.subheader("Where the dark lasted longest")
    geo_path = PROC / "parishes_simplified.geojson"
    if geo_path.exists():
        geo = json.loads(geo_path.read_text())
        day = st.slider("Days after landfall", 1, 90, 30)
        snap = d[d.days_since_landfall == day][["parish", "ratio_7d"]]
        m = px.choropleth_map(snap, geojson=geo, locations="parish", featureidkey="properties.parish",
                              color="ratio_7d", range_color=(0.2, 1.05), color_continuous_scale="Blues_r",
                              map_style="white-bg", center={"lat": 18.12, "lon": -77.3}, zoom=7.2,
                              labels={"ratio_7d": "Share of normal light"})
        m.update_layout(height=360, margin=dict(l=0, r=0, t=0, b=0), coloraxis_colorbar=dict(tickformat=".0%"))
        st.plotly_chart(m, width="stretch")
with right:
    st.subheader("More damage, more light lost")
    s["label"] = s.name.where(s.most_damaged | (s.light_days_lost >= s.light_days_lost.quantile(0.75)), "")
    sc = px.scatter(s, x="damage_pct_of_exposed_value", y="light_days_lost", text="label", hover_name="name",
                    color=s.most_damaged.map({True: "Five hardest hit", False: "Other parishes"}),
                    color_discrete_map={"Five hardest hit": ORANGE, "Other parishes": BLUE},
                    labels={"damage_pct_of_exposed_value": "Damage, % of exposed value (World Bank)",
                            "light_days_lost": "Light lost, days of normal light", "color": ""})
    sc.update_traces(textposition="top center", marker=dict(size=10))
    st.plotly_chart(style(sc, 360), width="stretch")

st.divider()
st.subheader("Recovery table")
tbl = s[["name", "damage_pct_of_exposed_value", "share_day_7", "share_day_30", "days_to_90", "light_days_lost"]].copy()
tbl.columns = ["Parish", "Damage %", "Light at day 7", "Light at day 30", "Days to 90%", "Light days lost"]
st.dataframe(tbl.style.format({"Damage %": "{:.1f}", "Light at day 7": "{:.0%}", "Light at day 30": "{:.0%}",
                               "Days to 90%": "{:.0f}", "Light days lost": "{:.1f}"}, na_rep="not yet"),
             hide_index=True, width="stretch")

with st.expander("About the data and method"):
    st.markdown(
        "- **Night lights:** NASA Black Marble VNP46A2, daily, 500 m, corrected for moonlight and the "
        "atmosphere, with cloud gaps filled from earlier clear nights. Monthly composites: VNP46A3.\n"
        "- **Parishes:** geoBoundaries (CC BY 4.0). Light is summed over each parish with exactextract.\n"
        "- **Normal level:** each parish's median daily light from 1 September to 26 October 2025.\n"
        "- **Damage:** World Bank GRADE rapid damage estimate for Hurricane Melissa.\n"
        "- **Limits:** gap filling can carry old light into cloudy nights, so short dips can be understated. "
        "Light measures power and activity, not damage to homes. Generators and solar can light a parish "
        "before the grid returns.\n"
        f"- Data through {S['data_through']}. Code: github.com/Soulkinggja/jamaica-night-lights")
    st.download_button("Download parish recovery table (CSV)", s.to_csv(index=False).encode(), "recovery_summary.csv")
