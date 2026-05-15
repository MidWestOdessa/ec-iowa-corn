"""EC Iowa corn — trader-facing dashboard. Reads web/data.json.

Usage:  uv run streamlit run web/app.py
"""
from __future__ import annotations
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


DATA = Path(__file__).parent / "data.json"

# ---- Page setup ----
st.set_page_config(
    page_title="EC Iowa Corn — Yield Forecast",
    page_icon="🌽",
    layout="wide",
)

# ---- Load snapshot ----
if not DATA.exists():
    st.error(f"Snapshot file not found: {DATA}.  Run `python -m web.snapshot` first.")
    st.stop()

snap = json.loads(DATA.read_text())
forecast = snap["forecast"]
history = snap["history"]
conditions = snap["conditions"]


# ---- Header ----
st.title("🌽 EC Iowa Corn — Yield Forecast")
col_h1, col_h2, col_h3 = st.columns([2, 1, 1])
col_h1.caption(f"District 60 · {snap['total_corn_acres']:,} corn acres · 9 counties")
col_h2.caption(f"**As of:** {snap['as_of']}")
col_h3.caption(f"**Forecast year:** {forecast['year']}")
st.divider()


# ---- Hero: 2026 forecast ----
st.subheader(f"📈 Indicative {forecast['year']} yield")

hero_l, hero_m, hero_r = st.columns([1.2, 1, 1])
hero_l.metric(
    label="Forecast (bu/ac)",
    value=f"{forecast['indicative_bu_ac']:.1f}",
    delta=None,
    help="Point estimate. Real forecast firms up once peak-July SubStress lands.",
)
hero_m.metric(
    label="95% band low",
    value=f"{forecast['band_low_95']:.1f}",
)
hero_r.metric(
    label="95% band high",
    value=f"{forecast['band_high_95']:.1f}",
)

total_bu = forecast['indicative_bu_ac'] * snap['total_corn_acres']
st.caption(
    f"At forecast yield × {snap['total_corn_acres']:,} acres ≈ "
    f"**{total_bu/1_000_000:.1f}M bushels** total district production. "
    f"Model: `{forecast['method']}`. "
    f"LOOCV MAE = {forecast['loocv_mae']} bu/ac on historical."
)

with st.expander("ℹ️ Forecast inputs + caveats", expanded=False):
    st.json(forecast['inputs'])
    st.caption(forecast.get('calibration_note', ''))
    st.markdown(f"**Fit stats:** R² = {forecast['fit_stats']['r_squared']}, "
                f"MAE = {forecast['fit_stats']['mae']} bu/ac. "
                f"Training: {forecast['fit_stats']['training_years']}.")

st.divider()


# ---- Actual vs Predicted history ----
st.subheader("📊 Model track record — actual vs predicted")

df = pd.DataFrame(history)
df_in = df[~df['excluded']].copy()
df_out = df[df['excluded']].copy()

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df_in['year'], y=df_in['actual'],
    mode='lines+markers', name='Actual yield',
    line=dict(color='#1f77b4', width=3),
    marker=dict(size=10),
))
fig.add_trace(go.Scatter(
    x=df_in['year'], y=df_in['predicted'],
    mode='lines+markers', name='Model prediction',
    line=dict(color='#ff7f0e', width=2, dash='dash'),
    marker=dict(size=8, symbol='diamond'),
))
if len(df_out):
    fig.add_trace(go.Scatter(
        x=df_out['year'], y=df_out['actual'],
        mode='markers', name='Excluded (exogenous shock)',
        marker=dict(size=14, symbol='x', color='red'),
        text=df_out['note'],
        hovertemplate='%{x}: actual %{y} (excluded)<br>%{text}',
    ))

fig.update_layout(
    xaxis_title='Year',
    yaxis_title='Yield (bu/ac)',
    height=440,
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
    hovermode='x unified',
)
st.plotly_chart(fig, use_container_width=True)

# Residual summary
df_valid = df_in.dropna(subset=['residual'])
if len(df_valid):
    abs_mae = df_valid['residual'].abs().mean()
    bias = df_valid['residual'].mean()
    over_under = "underpredicts" if bias > 0 else "overpredicts"
    st.caption(
        f"On {len(df_valid)} included training years: mean residual (actual − pred) = "
        f"**{bias:+.1f} bu/ac** (model {over_under} on average), "
        f"mean absolute error = **{abs_mae:.1f} bu/ac**. "
        f"Excluded years marked ❌ are exogenous shocks (derecho, disease)."
    )

st.divider()


# ---- Current conditions ----
st.subheader("🛰️ Current district conditions")

c1, c2, c3 = st.columns(3)

# Soil moisture card
with c1:
    st.markdown("**Soil moisture (latest CASMA)**")
    lc = conditions.get('latest_casma')
    if lc:
        st.caption(f"As of week {lc['iso_week']} (Mon {lc['monday']})")
        moisture_df = pd.DataFrame([
            {"Depth": "Topsoil",  **lc['top']},
            {"Depth": "Subsoil",  **lc['sub']},
        ])
        moisture_df = moisture_df.rename(columns={
            "vs": "Very Short %", "s": "Short %",
            "a": "Adequate %",    "su": "Surplus %",
        })
        st.dataframe(moisture_df, hide_index=True, use_container_width=True)
        # Quick visual: stacked bar
        fig_m = go.Figure()
        for cat, color in [("Very Short %", "#d62728"), ("Short %", "#ff7f0e"),
                           ("Adequate %", "#2ca02c"), ("Surplus %", "#1f77b4")]:
            fig_m.add_trace(go.Bar(
                name=cat, y=moisture_df['Depth'], x=moisture_df[cat],
                orientation='h', marker_color=color,
            ))
        fig_m.update_layout(
            barmode='stack', height=160,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(range=[0, 100], title="% of acres"),
            showlegend=False,
        )
        st.plotly_chart(fig_m, use_container_width=True)
    else:
        st.caption("No CASMA data yet.")

# GDD progression
with c2:
    st.markdown("**GDD50 cumulative (2026, from May 1)**")
    gdd_series = conditions.get('gdd_series', [])
    if gdd_series:
        gdf = pd.DataFrame(gdd_series)
        latest = gdf.iloc[-1]
        st.metric("Latest cumulative", f"{latest['gdd']:.1f}",
                  help=f"As of {latest['monday']}")
        fig_g = go.Figure()
        fig_g.add_trace(go.Scatter(
            x=gdf['monday'], y=gdf['gdd'],
            mode='lines+markers',
            line=dict(color='#ff7f0e', width=2),
            marker=dict(size=8),
        ))
        fig_g.update_layout(
            height=160, margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title=None, yaxis_title="GDD50",
        )
        st.plotly_chart(fig_g, use_container_width=True)
    else:
        st.caption("GDD data not yet populated.")

# Crop progress
with c3:
    st.markdown("**Crop progress (latest reported)**")
    cp = conditions['crop_progress']
    rows = []
    label_map = {
        "planted": "Planted", "emerged": "Emerged", "silking": "Silking",
        "doughing": "Doughing", "dented": "Dented",
        "corn_mature": "Mature", "corn_harvested": "Harvested",
    }
    for k, label in label_map.items():
        info = cp[k]
        if info['latest_pct'] is not None:
            rows.append({
                "Stage": label,
                "%": f"{info['latest_pct']:.0f}",
                "Week": info['latest_iso_week'],
                "As of Mon": info['latest_monday'],
            })
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.caption("No stages have nonzero values yet.")

st.divider()

# Footer
st.caption(
    f"Snapshot generated by `web/snapshot.py` from "
    f"`Corn Progress EC Iowa 2021 2025 v5.xlsx`. "
    f"To refresh, re-run snapshot from the project root: "
    f"`uv run python -m web.snapshot`."
)
