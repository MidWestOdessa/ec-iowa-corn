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
    initial_sidebar_state="collapsed",
)

# ---- Custom styling ----
CUSTOM_CSS = """
<style>
/* Tighter, more decisive layout */
.main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1280px; }

/* Brand palette */
:root {
  --teal-900: #0a3d3a;
  --teal-700: #145e58;
  --teal-500: #2d8b81;
  --amber-600: #c89b3a;
  --amber-500: #d8af52;
  --cream:    #f7f8fa;
  --slate-700:#1a2330;
  --slate-500:#4a5568;
  --slate-400:#6b7280;
  --slate-200:#e4e7eb;
  --green-600:#2d8659;
  --red-600:  #b94e4e;
}

/* Typography */
h1, h2, h3, h4 {
  color: var(--teal-900) !important;
  font-weight: 700 !important;
  letter-spacing: -0.01em !important;
}
h1 { font-size: 2.4rem !important; margin-bottom: 0.25rem !important; }
h2 { font-size: 1.5rem !important; margin-top: 0.5rem !important; }
h3 { font-size: 1.1rem !important; text-transform: uppercase; letter-spacing: 0.04em !important; color: var(--teal-700) !important; }

/* Hero forecast metric — much bigger */
div[data-testid="stMetricValue"] {
  font-size: 2.6rem !important;
  font-weight: 700 !important;
  color: var(--teal-900) !important;
  line-height: 1.1 !important;
}
div[data-testid="stMetricLabel"] {
  color: var(--slate-500) !important;
  text-transform: uppercase;
  letter-spacing: 0.08em !important;
  font-size: 0.72rem !important;
  font-weight: 600 !important;
}
div[data-testid="stMetricDelta"] { font-size: 0.9rem !important; }

/* Cards (containers with border) */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: #ffffff;
  border: 1px solid var(--slate-200) !important;
  border-radius: 14px !important;
  padding: 1.25rem 1.5rem !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  margin-bottom: 0 !important;
}

/* Custom hero card backdrop */
.hero-card {
  background: linear-gradient(135deg, #0a3d3a 0%, #145e58 100%);
  color: #fafafa;
  border-radius: 16px;
  padding: 1.5rem 2rem;
  margin: 0.5rem 0 1.5rem 0;
  box-shadow: 0 4px 14px rgba(10, 61, 58, 0.18);
}
.hero-card h2 { color: #ffffff !important; margin-top: 0 !important; }
.hero-card .hero-value {
  font-size: 4rem; font-weight: 800; line-height: 1.0;
  color: var(--amber-500); letter-spacing: -0.02em;
}
.hero-card .hero-unit { font-size: 1.1rem; color: rgba(255,255,255,0.75); margin-left: 0.3rem; }
.hero-card .hero-range { color: rgba(255,255,255,0.85); font-size: 1.05rem; margin-top: 0.5rem; }
.hero-card .hero-sub { color: rgba(255,255,255,0.7); font-size: 0.95rem; margin-top: 1rem; }
.hero-card .hero-bushels {
  display: inline-block; padding: 0.4rem 0.8rem; margin-top: 0.6rem;
  background: rgba(216, 175, 82, 0.15); border: 1px solid rgba(216, 175, 82, 0.4);
  border-radius: 8px; font-size: 0.95rem; color: var(--amber-500); font-weight: 600;
}

/* Footer / caption refinement */
.stCaption, [data-testid="stCaptionContainer"] {
  color: var(--slate-400) !important;
  font-size: 0.83rem !important;
}

/* Divider */
hr { border-color: var(--slate-200) !important; margin: 1.5rem 0 !important; }

/* Top status bar */
.statusbar {
  display: flex; justify-content: space-between; align-items: baseline;
  background: #ffffff; border: 1px solid var(--slate-200); border-radius: 10px;
  padding: 0.6rem 1rem; margin-bottom: 1rem; font-size: 0.85rem;
}
.statusbar .left { color: var(--slate-500); }
.statusbar .right { color: var(--teal-700); font-weight: 600; }

/* Section pill */
.section-pill {
  display: inline-block; padding: 0.18rem 0.6rem;
  background: var(--amber-600); color: #fff; border-radius: 999px;
  font-size: 0.65rem; letter-spacing: 0.1em; font-weight: 700;
  text-transform: uppercase; margin-right: 0.6rem; vertical-align: middle;
}

/* Tables */
[data-testid="stDataFrame"] { border-radius: 8px; }
[data-testid="stDataFrame"] thead tr th {
  background: var(--cream) !important; color: var(--teal-900) !important;
  font-weight: 600 !important;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---- Load snapshot ----
if not DATA.exists():
    st.error(f"Snapshot file not found: {DATA}.  Run `python -m web.snapshot` first.")
    st.stop()

snap = json.loads(DATA.read_text())
forecast = snap["forecast"]
history = snap["history"]
conditions = snap["conditions"]


# ---- Title + status bar ----
st.markdown('<h1>🌽 EC Iowa Corn — Yield Forecast</h1>', unsafe_allow_html=True)
st.markdown(
    f"""<div class="statusbar">
        <div class="left">District 60 · {snap['total_corn_acres']:,} corn acres · 9 counties</div>
        <div class="right">As of {snap['as_of']} · Forecast year {forecast['year']}</div>
    </div>""",
    unsafe_allow_html=True,
)


# ---- Hero forecast card ----
total_bu = forecast['indicative_bu_ac'] * snap['total_corn_acres']
st.markdown(
    f"""<div class="hero-card">
        <h2>Indicative {forecast['year']} yield forecast</h2>
        <div>
            <span class="hero-value">{forecast['indicative_bu_ac']:.1f}</span>
            <span class="hero-unit">bu / ac</span>
        </div>
        <div class="hero-range">
            95% band: <strong>{forecast['band_low_95']:.1f}</strong> &mdash; <strong>{forecast['band_high_95']:.1f}</strong> bu/ac
            &nbsp;·&nbsp; LOOCV MAE = {forecast['loocv_mae']:.2f}
        </div>
        <div class="hero-bushels">
            ≈ {total_bu/1_000_000:.1f}M bushels district total at forecast
        </div>
        <div class="hero-sub">
            Model: {forecast['method']}. Peak-July SubStress not yet observed —
            forecast firms up late July. Currently using {forecast['inputs']['substress_jul_used']}% as the
            stand-in (10-year median).
        </div>
    </div>""",
    unsafe_allow_html=True,
)

with st.expander("Forecast inputs + fit statistics", expanded=False):
    fs = forecast['fit_stats']
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("R²", f"{fs['r_squared']:.3f}")
    c2.metric("MAE", f"{fs['mae']} bu/ac")
    c3.metric("LOOCV MAE", f"{fs['loocv_mae']} bu/ac")
    c4.metric("Training years", fs['training_years'])
    st.caption("Inputs used:")
    st.json(forecast['inputs'])
    st.caption(forecast.get('calibration_note', ''))


# ---- Model track record ----
st.markdown('<h2><span class="section-pill">02</span>Model track record</h2>',
            unsafe_allow_html=True)

with st.container(border=True):
    df = pd.DataFrame(history)
    df_in = df[~df['excluded']].copy()
    df_out = df[df['excluded']].copy()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_in['year'], y=df_in['actual'],
        mode='lines+markers', name='Actual yield',
        line=dict(color='#0a3d3a', width=3),
        marker=dict(size=10, color='#0a3d3a'),
    ))
    fig.add_trace(go.Scatter(
        x=df_in['year'], y=df_in['predicted'],
        mode='lines+markers', name='Model prediction',
        line=dict(color='#c89b3a', width=2, dash='dash'),
        marker=dict(size=8, symbol='diamond', color='#c89b3a'),
    ))
    if len(df_out):
        fig.add_trace(go.Scatter(
            x=df_out['year'], y=df_out['actual'],
            mode='markers', name='Excluded (exogenous shock)',
            marker=dict(size=15, symbol='x-thin', color='#b94e4e', line=dict(width=3, color='#b94e4e')),
            text=df_out['note'],
            hovertemplate='<b>%{x}</b>: actual %{y:.1f}<br>%{text}<extra></extra>',
        ))

    fig.update_layout(
        xaxis_title='Year',
        yaxis_title='Yield (bu/ac)',
        height=400,
        margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01,
                    bgcolor='rgba(255,255,255,0.9)'),
        hovermode='x unified',
        plot_bgcolor='#fafbfc',
        font=dict(color='#1a2330'),
    )
    fig.update_xaxes(gridcolor='#e4e7eb', linecolor='#e4e7eb')
    fig.update_yaxes(gridcolor='#e4e7eb', linecolor='#e4e7eb')
    st.plotly_chart(fig, use_container_width=True)

    df_valid = df_in.dropna(subset=['residual'])
    if len(df_valid):
        abs_mae = df_valid['residual'].abs().mean()
        bias = df_valid['residual'].mean()
        over_under = "underpredicts" if bias > 0 else "overpredicts"
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Training years (included)", f"{len(df_valid)}")
        col_b.metric("Mean residual", f"{bias:+.1f} bu/ac",
                     help=f"Model {over_under} on average")
        col_c.metric("Mean absolute error", f"{abs_mae:.1f} bu/ac")
        st.caption(
            f"❌ markers in red show excluded exogenous shocks: derecho (2020) and Southern Rust (2025)."
        )


# ---- Current conditions ----
st.markdown('<h2><span class="section-pill">03</span>Current district conditions</h2>',
            unsafe_allow_html=True)

c1, c2, c3 = st.columns(3, gap="medium")

# Soil moisture card
with c1:
    with st.container(border=True):
        st.markdown("### Soil moisture")
        lc = conditions.get('latest_casma')
        if lc:
            st.caption(f"Latest CASMA · wk {lc['iso_week']} · Mon {lc['monday']}")
            moisture_df = pd.DataFrame([
                {"Depth": "Topsoil", **lc['top']},
                {"Depth": "Subsoil", **lc['sub']},
            ])
            moisture_df = moisture_df.rename(columns={
                "vs": "Very Short",   "s": "Short",
                "a": "Adequate",      "su": "Surplus",
            })
            # Stacked bar
            fig_m = go.Figure()
            palette = {
                "Very Short": "#b94e4e", "Short": "#c89b3a",
                "Adequate":   "#2d8659", "Surplus": "#145e58",
            }
            for cat, color in palette.items():
                fig_m.add_trace(go.Bar(
                    name=cat, y=moisture_df['Depth'], x=moisture_df[cat],
                    orientation='h', marker_color=color,
                    text=[f"{v:.0f}%" if v >= 5 else "" for v in moisture_df[cat]],
                    textposition='inside', textfont=dict(color='white', size=11),
                ))
            fig_m.update_layout(
                barmode='stack', height=180,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis=dict(range=[0, 100], title=None, gridcolor='#e4e7eb'),
                yaxis=dict(title=None),
                showlegend=True,
                legend=dict(orientation='h', y=-0.15, x=0),
                plot_bgcolor='#fafbfc',
                font=dict(color='#1a2330', size=11),
            )
            st.plotly_chart(fig_m, use_container_width=True)
        else:
            st.caption("No CASMA data yet.")

# GDD progression
with c2:
    with st.container(border=True):
        st.markdown("### GDD50 cumulative")
        gdd_series = conditions.get('gdd_series', [])
        if gdd_series:
            gdf = pd.DataFrame(gdd_series)
            latest = gdf.iloc[-1]
            st.metric("Latest", f"{latest['gdd']:.1f}", help=f"As of {latest['monday']}")
            fig_g = go.Figure()
            fig_g.add_trace(go.Scatter(
                x=gdf['monday'], y=gdf['gdd'],
                mode='lines+markers',
                line=dict(color='#c89b3a', width=3),
                marker=dict(size=9, color='#c89b3a'),
                fill='tozeroy', fillcolor='rgba(200, 155, 58, 0.15)',
            ))
            fig_g.update_layout(
                height=180, margin=dict(l=10, r=10, t=10, b=10),
                xaxis=dict(title=None, gridcolor='#e4e7eb'),
                yaxis=dict(title="GDD50", gridcolor='#e4e7eb'),
                plot_bgcolor='#fafbfc',
                font=dict(color='#1a2330', size=11),
            )
            st.plotly_chart(fig_g, use_container_width=True)
        else:
            st.caption("GDD data not yet populated.")

# Crop progress
with c3:
    with st.container(border=True):
        st.markdown("### Crop progress")
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
                    "Wk": info['latest_iso_week'],
                    "As of": info['latest_monday'],
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=300)
        else:
            st.caption("No stages have nonzero values yet.")

# ---- Multi-year comparison ----
hw = snap.get("history_weekly", {})
if hw:
    st.markdown('<h2><span class="section-pill">04</span>Multi-year comparison</h2>',
                unsafe_allow_html=True)

    YEAR_COLORS = {
        "2021": "#94a3b8",   # light slate
        "2022": "#c89b3a",   # amber
        "2023": "#475569",   # darker slate
        "2024": "#2d8659",   # green (strong year, 231 bu/ac)
        "2025": "#b94e4e",   # red (Southern Rust outlier)
        "2026": "#0a3d3a",   # dark teal (current year, bold)
    }
    YEAR_DASH = {
        "2021": "dot", "2022": "dot", "2023": "dash",
        "2024": "dash", "2025": "dashdot", "2026": "solid",
    }
    AVAILABLE_YEARS = sorted([y for y in hw.keys() if hw[y]])

    # Year selector — defaults to all
    selected_years = st.multiselect(
        "Years to compare",
        options=AVAILABLE_YEARS,
        default=AVAILABLE_YEARS,
        help="Pick which years overlay on the chart and appear in the tables below.",
    )
    if not selected_years:
        st.warning("Select at least one year above.")
        st.stop()

    # 4a. GDD trajectory overlay
    with st.container(border=True):
        st.markdown(f"### GDD50 trajectory — {min(selected_years)} → {max(selected_years)}")
        st.caption("Cumulative GDD by ISO week. 2026 (solid teal) vs other selected years.")
        fig_gdd = go.Figure()
        for yr_str in selected_years:
            weeks = hw.get(yr_str) or []
            xs, ys = [], []
            for w in weeks:
                if w.get("gdd") is not None:
                    xs.append(w["iso_week"])
                    ys.append(w["gdd"])
            if not xs:
                continue
            is_current = (yr_str == "2026")
            fig_gdd.add_trace(go.Scatter(
                x=xs, y=ys, mode='lines+markers', name=yr_str,
                line=dict(
                    color=YEAR_COLORS.get(yr_str, '#888'),
                    width=4 if is_current else 2,
                    dash=YEAR_DASH.get(yr_str, 'solid'),
                ),
                marker=dict(size=8 if is_current else 5),
            ))
        fig_gdd.update_layout(
            xaxis_title='ISO week',
            yaxis_title='GDD50 cumulative',
            height=400,
            margin=dict(l=10, r=10, t=20, b=10),
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01,
                        bgcolor='rgba(255,255,255,0.9)'),
            hovermode='x unified',
            plot_bgcolor='#fafbfc',
            font=dict(color='#1a2330'),
        )
        fig_gdd.update_xaxes(gridcolor='#e4e7eb', linecolor='#e4e7eb')
        fig_gdd.update_yaxes(gridcolor='#e4e7eb', linecolor='#e4e7eb')
        st.plotly_chart(fig_gdd, use_container_width=True)

    # 4b. Comparison tables at the latest 2026 week (if 2026 is selected) or
    # the most-recent week any selected year has stage data.
    latest_2026_week = None
    if "2026" in selected_years:
        for w in (hw.get("2026") or [])[::-1]:
            if any(w.get(s) is not None for s in ["planted", "emerged"]):
                latest_2026_week = w["iso_week"]
                break
    if latest_2026_week is None:
        # Fall back to the latest week any selected year has stage data
        all_weeks = []
        for yr in selected_years:
            for w in hw.get(yr) or []:
                if any(w.get(s) is not None for s in ["planted", "emerged"]):
                    all_weeks.append(w["iso_week"])
        latest_2026_week = max(all_weeks) if all_weeks else None

    cmp1, cmp2 = st.columns(2, gap="medium")

    with cmp1:
        with st.container(border=True):
            st.markdown(f"### Crop progress at wk {latest_2026_week}" if latest_2026_week else "### Crop progress comparison")
            if latest_2026_week is None:
                st.caption("No selected year has stage data yet.")
            else:
                stage_labels = {
                    "planted": "Planted", "emerged": "Emerged",
                    "silking": "Silking", "doughing": "Doughing",
                    "dented": "Dented", "corn_mature": "Mature",
                    "corn_harvested": "Harvested",
                }
                rows = []
                for stage, label in stage_labels.items():
                    row = {"Stage": label}
                    for yr in selected_years:
                        weeks = hw.get(yr) or []
                        match = next((w for w in weeks if w["iso_week"] == latest_2026_week), None)
                        v = match.get(stage) if match else None
                        row[yr] = f"{v:.0f}%" if isinstance(v, (int, float)) else "—"
                    rows.append(row)
                df_cmp = pd.DataFrame(rows)
                st.dataframe(df_cmp, hide_index=True, use_container_width=True, height=290)
                st.caption(f"EC district NASS / GDD-model % at ISO week {latest_2026_week}.")

    with cmp2:
        with st.container(border=True):
            st.markdown(f"### Soil moisture at wk {latest_2026_week}" if latest_2026_week else "### Soil moisture comparison")
            if latest_2026_week is None:
                st.caption("No selected year has soil-moisture data yet.")
            else:
                rows = []
                for depth_label, vs_key, s_key in [
                    ("Topsoil VS+S (stress)", "top_vs", "top_s"),
                    ("Subsoil VS+S (stress)", "sub_vs", "sub_s"),
                ]:
                    row = {"Metric": depth_label}
                    for yr in selected_years:
                        weeks = hw.get(yr) or []
                        match = next((w for w in weeks if w["iso_week"] == latest_2026_week), None)
                        if match and isinstance(match.get(vs_key), (int, float)) and isinstance(match.get(s_key), (int, float)):
                            v = match[vs_key] + match[s_key]
                            row[yr] = f"{v:.1f}%"
                        else:
                            row[yr] = "—"
                    rows.append(row)
                for depth_label, su_key in [
                    ("Topsoil Surplus (wet)", "top_su"),
                    ("Subsoil Surplus (wet)", "sub_su"),
                ]:
                    row = {"Metric": depth_label}
                    for yr in selected_years:
                        weeks = hw.get(yr) or []
                        match = next((w for w in weeks if w["iso_week"] == latest_2026_week), None)
                        v = match.get(su_key) if match else None
                        row[yr] = f"{v:.1f}%" if isinstance(v, (int, float)) else "—"
                    rows.append(row)
                df_stress = pd.DataFrame(rows)
                st.dataframe(df_stress, hide_index=True, use_container_width=True, height=215)
                st.caption(f"VS+S = drought stress; Surplus = excess moisture. ISO week {latest_2026_week}.")

st.divider()
st.caption(
    f"Snapshot generated from `Corn Progress EC Iowa 2021 2025 v5.xlsx` "
    f"by `web/snapshot.py`. "
    f"Refresh: `uv run python -m web.snapshot` after each weekly update."
)
