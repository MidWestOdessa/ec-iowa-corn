"""EC Iowa corn — trader-facing dashboard. Reads web/data.json.

Usage:  uv run streamlit run web/app.py
"""
from __future__ import annotations
import json
import statistics
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
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
/* Agricultural landscape: clearly cool pale-blue sky at top, clearly warm
   wheat-gold field at bottom. Fixed to viewport so the user always sees
   the full sky->field range regardless of scroll position. Streamlit's
   inner containers are forced transparent so they don't cover the gradient. */
html, body, .stApp, [data-testid="stAppViewContainer"] {
  background:
    /* Rolling-field silhouette anchored to bottom of viewport. Two layered
       paths for depth: a paler distant ridgeline behind a richer nearer one.
       Full width, ~180px tall, fixed — completes the sky→field landscape. */
    url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1600 200' preserveAspectRatio='none'><path fill='%23704c1a' fill-opacity='0.09' d='M0 95 C 240 70 500 95 760 75 C 1020 55 1300 90 1600 65 L 1600 200 L 0 200 Z'/><path fill='%23704c1a' fill-opacity='0.18' d='M0 135 C 220 110 500 145 800 120 C 1100 95 1380 135 1600 115 L 1600 200 L 0 200 Z'/></svg>") no-repeat bottom center / 100% 180px fixed,
    /* Subtle horizon glow at viewport midline */
    linear-gradient(180deg, transparent 46%, rgba(220, 165, 90, 0.18) 53%, transparent 60%) fixed,
    /* Sky (cool blue-gray) -> Field (warm wheat gold) */
    linear-gradient(180deg,
      #cad9e2 0%,        /* clear pale sky-blue */
      #d6dde1 18%,
      #e1d8b8 42%,       /* horizon haze */
      #d8ba76 65%,       /* near field */
      #b88e3f 100%       /* deep wheat */
    ) fixed !important;
  background-size: 100% 180px, 100% 100%, 100% 100% !important;
}

/* Force Streamlit's inner content containers to be transparent so the
   gradient actually shows through everywhere, not just under cards' margins. */
section.main, [data-testid="stMain"], [data-testid="stMainBlockContainer"],
.main .block-container, [data-testid="block-container"] {
  background: transparent !important;
}
.stApp::before {
  content: "";
  position: fixed; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, #0a3d3a 0%, #145e58 50%, #c89b3a 100%);
  z-index: 1000;
  opacity: 0.9;
}

/* Cards: bright white with a slightly warmer shadow so they read like
   paper notes sitting on a wheat-colored desk */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: #ffffff !important;
  border: 1px solid rgba(220, 205, 170, 0.7) !important;
  box-shadow:
    0 1px 4px rgba(120, 90, 40, 0.08),
    0 2px 8px rgba(120, 90, 40, 0.04) !important;
}

/* Status bar — soft cream with blur, fits the wheat palette */
.statusbar {
  background: rgba(255, 252, 240, 0.88) !important;
  backdrop-filter: blur(8px);
  border-color: rgba(220, 205, 170, 0.7) !important;
}

/* Tighter, more decisive layout */
.main .block-container { padding-top: 1.8rem; padding-bottom: 2rem; max-width: 1280px; }

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

# ---- Password gate ----
# Single shared password stored in Streamlit Cloud secrets (or .streamlit/secrets.toml
# locally — gitignored). If APP_PASSWORD is not set anywhere, the gate fails open
# with a warning, so local dev without secrets still works.
def _check_password() -> bool:
    if st.session_state.get("dashboard_authenticated"):
        return True
    try:
        expected = st.secrets["APP_PASSWORD"]
    except (KeyError, FileNotFoundError):
        # No password configured — let through but warn (local dev case).
        return True

    # Render a centered login card matching the dashboard aesthetic.
    st.html(
        '<div style="max-width:420px;margin:8vh auto 1rem auto;text-align:center;">'
        '<div style="font-size:3rem;margin-bottom:0.4rem;">🌽</div>'
        '<h1 style="font-size:1.6rem;margin:0;color:#0a3d3a;font-weight:700;">'
        'EC Iowa Corn Dashboard</h1>'
        '<div style="color:#6b7280;font-size:0.95rem;margin-top:0.4rem;">'
        'This dashboard is private. Enter the access password to continue.'
        '</div></div>'
    )
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        pw = st.text_input(
            "Password",
            type="password",
            key="pw_input",
            label_visibility="collapsed",
            placeholder="Password",
        )
    if pw:
        if pw == expected:
            st.session_state["dashboard_authenticated"] = True
            st.rerun()
        else:
            _, mid, _ = st.columns([1, 2, 1])
            with mid:
                st.error("Incorrect password.")
    return False


if not _check_password():
    st.stop()


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
# We treat the headline as "Pending" until we have a real peak-July SubStress
# observation. Before that, what the model spits out is a preliminary value
# computed against historical-median stress — useful as context but NOT a
# tradable forecast. We surface that as small print, not the hero number.
total_bu = forecast['indicative_bu_ac'] * snap['total_corn_acres']
st.markdown(
    f"""<div class="hero-card">
        <h2>{forecast['year']} crop year yield forecast</h2>
        <div>
            <span style="font-size:3.4rem;font-weight:800;color:#d8af52;font-style:italic;
                         letter-spacing:-0.02em;line-height:1;">Pending</span>
        </div>
        <div class="hero-range">
            Final forecast lands once peak-July SubStress is observed (late July).
        </div>
        <div class="hero-sub" style="margin-top:1rem;">
            <strong style="color:rgba(255,255,255,0.92);">Preliminary placeholder</strong>
            (using historical-median stress, NOT 2026's actual signal):
            <span style="color:rgba(255,255,255,0.85);">
            ~{forecast['indicative_bu_ac']:.1f} bu/ac &nbsp;·&nbsp;
            95% band {forecast['band_low_95']:.1f} – {forecast['band_high_95']:.1f}
            </span>
        </div>
        <div class="hero-sub" style="margin-top:0.5rem;font-size:0.85rem;">
            Model: {forecast['method']}. Real 2026 SubStress_Jul not yet
            observed; using {forecast['inputs']['substress_jul_used']}% (10-year median)
            as a stand-in. Don't trade on this — it's a sanity check, not a forecast.
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

    # 4a. GDD trajectory — view-mode toggle
    with st.container(border=True):
        view_mode = st.radio(
            "GDD trajectory view",
            options=["Historical range + current year", "Year overlay"],
            horizontal=True,
            label_visibility="collapsed",
            help="The range view shades the min/max envelope across all "
                 "selected historical years and overlays 2026 on top — easier "
                 "to see where this year sits relative to normal. The overlay "
                 "view draws each year as its own line (gets crowded with 4+ "
                 "years).",
        )
        st.markdown(f"### GDD50 trajectory — {min(selected_years)} → {max(selected_years)}")

        fig_gdd = go.Figure()

        if view_mode == "Historical range + current year":
            # Compute per-ISO-week min/median/max across selected non-2026 years
            historical_years = [y for y in selected_years if y != "2026"]
            by_week: dict[int, list[float]] = {}
            for yr_str in historical_years:
                for w in hw.get(yr_str) or []:
                    g = w.get("gdd")
                    if isinstance(g, (int, float)):
                        by_week.setdefault(w["iso_week"], []).append(float(g))
            sorted_weeks = sorted(by_week.keys())

            if sorted_weeks:
                medians = [statistics.median(by_week[wk]) for wk in sorted_weeks]
                mins    = [min(by_week[wk]) for wk in sorted_weeks]
                maxs    = [max(by_week[wk]) for wk in sorted_weeks]

                # Shaded min-max band (drawn first as max line, then min with fill='tonexty')
                fig_gdd.add_trace(go.Scatter(
                    x=sorted_weeks, y=maxs,
                    mode='lines', line=dict(width=0, color='rgba(108,117,125,0)'),
                    showlegend=False, hoverinfo='skip',
                ))
                fig_gdd.add_trace(go.Scatter(
                    x=sorted_weeks, y=mins,
                    mode='lines', line=dict(width=0, color='rgba(108,117,125,0)'),
                    fill='tonexty', fillcolor='rgba(108, 117, 125, 0.20)',
                    name=f'Historical min-max ({len(historical_years)} yrs)',
                    hoverinfo='skip',
                ))
                # Median line
                fig_gdd.add_trace(go.Scatter(
                    x=sorted_weeks, y=medians,
                    mode='lines', name='Historical median',
                    line=dict(color='#6b7280', width=2, dash='dot'),
                ))

            # 2026 (current year) — bold on top
            if "2026" in selected_years:
                xs, ys = [], []
                for w in hw.get("2026") or []:
                    g = w.get("gdd")
                    if isinstance(g, (int, float)):
                        xs.append(w["iso_week"])
                        ys.append(g)
                if xs:
                    fig_gdd.add_trace(go.Scatter(
                        x=xs, y=ys,
                        mode='lines+markers', name='2026 (current)',
                        line=dict(color='#0a3d3a', width=4),
                        marker=dict(size=9, color='#0a3d3a'),
                    ))
        else:
            # Multi-year overlay (legacy view)
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

    # 4b. Find latest "active" week for 2026 = latest week with planted > 0 or
    # emerged > 0. We use ">0" not "is not None" because the late-week stage
    # formulas evaluate to literal 0 (their IFERROR fallback when GDD has no
    # data yet) — those aren't real readings.
    def _is_active(w: dict) -> bool:
        for s in ("planted", "emerged"):
            v = w.get(s)
            if isinstance(v, (int, float)) and v > 0:
                return True
        return False

    latest_2026_week = None
    if "2026" in selected_years:
        for w in (hw.get("2026") or [])[::-1]:
            if _is_active(w):
                latest_2026_week = w["iso_week"]
                break
    if latest_2026_week is None:
        # Fall back to the latest active week any selected year has
        all_weeks = []
        for yr in selected_years:
            for w in hw.get(yr) or []:
                if _is_active(w):
                    all_weeks.append(w["iso_week"])
        latest_2026_week = max(all_weeks) if all_weeks else None

    # ---- Week selector ----------------------------------------------------
    # Drives BOTH the crop-progress and soil-moisture comparison tables below.
    # Defaults to the latest 2026 active week (where Planted/Emerged > 0).
    # User can pick any ISO week from 2026's full date range to explore.
    week_pool = hw.get("2026") or []

    def _has_moisture(w: dict) -> bool:
        for k in ("top_vs", "top_s", "top_a", "top_su",
                 "sub_vs", "sub_s", "sub_a", "sub_su"):
            if isinstance(w.get(k), (int, float)):
                return True
        return False

    def _label_for_week(year: str, iso_wk: int | None) -> str | None:
        if iso_wk is None:
            return None
        for w in hw.get(year) or []:
            if w.get("iso_week") == iso_wk and w.get("monday"):
                d = datetime.fromisoformat(w["monday"]).date()
                return f"{d.strftime('%b')} {d.day}"
        return None

    # Compute latest weeks with data for the dropdown HINT text.
    latest_moisture_week_2026 = None
    for w in week_pool[::-1]:
        if _has_moisture(w):
            latest_moisture_week_2026 = w["iso_week"]
            break

    # Build the dropdown options from 2026's full dates row.
    def _fmt_week(w: dict) -> str:
        d = datetime.fromisoformat(w["monday"]).date()
        tag = ""
        if w["iso_week"] == latest_2026_week:
            tag = "  ← latest crop progress"
        elif w["iso_week"] == latest_moisture_week_2026:
            tag = "  ← latest CASMA"
        return f"Week {w['iso_week']:02d}  ·  Mon {d.strftime('%b %d')}{tag}"

    week_labels = [_fmt_week(w) for w in week_pool]
    label_to_iso = {_fmt_week(w): w["iso_week"] for w in week_pool}
    default_idx = 0
    for i, w in enumerate(week_pool):
        if w["iso_week"] == latest_2026_week:
            default_idx = i
            break

    selected_label = st.selectbox(
        "Comparison week",
        options=week_labels,
        index=default_idx,
        help="Pick which ISO week the crop-progress + soil-moisture comparison tables below use.",
    )
    selected_week = label_to_iso[selected_label]
    selected_week_label = _label_for_week("2026", selected_week) or f"wk {selected_week}"
    label_at = f"week of {selected_week_label}"

    cmp1, cmp2 = st.columns(2, gap="medium")

    with cmp1:
        with st.container(border=True):
            st.markdown(f"### Crop progress at {label_at}")
            stage_labels = {
                "planted": "Planted", "emerged": "Emerged",
                "silking": "Silking", "doughing": "Doughing",
                "dented": "Dented", "corn_mature": "Mature",
                "corn_harvested": "Harvested",
                "ge_state": "G+E condition (state)",
                "pf_state": "P+F condition (state)",
            }
            rows = []
            for stage, label in stage_labels.items():
                row = {"Stage": label}
                for yr in selected_years:
                    weeks = hw.get(yr) or []
                    match = next((w for w in weeks if w["iso_week"] == selected_week), None)
                    v = match.get(stage) if match else None
                    row[yr] = f"{v:.0f}%" if isinstance(v, (int, float)) else "—"
                rows.append(row)
            df_cmp = pd.DataFrame(rows)
            st.dataframe(df_cmp, hide_index=True, use_container_width=True, height=330)
            st.caption(
                f"EC district NASS / GDD-model % at ISO week {selected_week} ({label_at}). "
                "G+E and P+F are Iowa state-level corn condition ratings."
            )

    with cmp2:
        with st.container(border=True):
            st.markdown(f"### Soil moisture at {label_at}")
            rows = []
            for depth_label, vs_key, s_key in [
                ("Topsoil VS+S (stress)", "top_vs", "top_s"),
                ("Subsoil VS+S (stress)", "sub_vs", "sub_s"),
            ]:
                row = {"Metric": depth_label}
                for yr in selected_years:
                    weeks = hw.get(yr) or []
                    match = next((w for w in weeks if w["iso_week"] == selected_week), None)
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
                    match = next((w for w in weeks if w["iso_week"] == selected_week), None)
                    v = match.get(su_key) if match else None
                    row[yr] = f"{v:.1f}%" if isinstance(v, (int, float)) else "—"
                rows.append(row)
            df_stress = pd.DataFrame(rows)
            st.dataframe(df_stress, hide_index=True, use_container_width=True, height=215)

            # Footer note: which weeks 2026 actually has data for, since
            # picking a too-recent week shows "—" in the 2026 column.
            stage_info = (
                f"2026 latest crop progress: <strong>wk {latest_2026_week}</strong>"
                if latest_2026_week is not None else "2026 crop progress: none"
            )
            moisture_info = (
                f"2026 latest CASMA: <strong>wk {latest_moisture_week_2026}</strong>"
                if latest_moisture_week_2026 is not None else "2026 CASMA: none"
            )
            st.html(
                f"<div style='font-size:0.82rem;color:#6b7280;margin-top:0.3rem;'>"
                f"VS+S = drought stress; Surplus = excess moisture. "
                f"At ISO week {selected_week} ({label_at}). "
                f"&nbsp;·&nbsp; {stage_info} &nbsp;·&nbsp; {moisture_info}"
                f"</div>"
            )

# ---- 7-day weather outlook (NWS, live, cached 6 hours) ----
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_nws_forecast() -> list[dict] | None:
    """7-day forecast for Cedar Rapids Airport area via NWS api.weather.gov."""
    lat, lon = 41.884, -91.71
    headers = {"User-Agent": "ec_iowa_corn dashboard (local)"}
    try:
        r = requests.get(f"https://api.weather.gov/points/{lat},{lon}", headers=headers, timeout=10)
        r.raise_for_status()
        url = r.json()["properties"]["forecast"]
        r2 = requests.get(url, headers=headers, timeout=10)
        r2.raise_for_status()
        return r2.json()["properties"]["periods"]
    except Exception:
        return None


def _gdd50_predicted(tmax: float, tmin: float) -> float:
    """Mirror noaa.compute_gdd50_daily so dashboard is independent."""
    tmax_c = max(min(tmax, 86), 50)
    tmin_c = max(min(tmin, 86), 50)
    return max(0.0, (tmax_c + tmin_c) / 2 - 50)


def _weather_icon(short_forecast: str) -> str:
    s = (short_forecast or "").lower()
    if "thunderstorm" in s or "thunder" in s: return "⛈️"
    if "shower" in s:                          return "🌦️"
    if "rain" in s or "drizzle" in s:          return "🌧️"
    if "snow" in s or "flurr" in s:            return "❄️"
    if "fog" in s or "haze" in s or "mist" in s: return "🌫️"
    if "windy" in s or "breezy" in s:          return "💨"
    if "partly sunny" in s or "partly cloudy" in s or "mostly cloudy" in s: return "⛅"
    if "mostly sunny" in s or "sunny" in s or "clear" in s: return "☀️"
    if "cloudy" in s or "overcast" in s:       return "☁️"
    return "🌤️"


def _temp_color(t) -> str:
    """Color a temperature value by range — cool blues -> warm reds."""
    if t is None:
        return "#6b7280"
    if t < 32:  return "#1e3a8a"   # below freezing — deep blue
    if t < 45:  return "#2563eb"   # cold — blue
    if t < 60:  return "#0891b2"   # cool — teal
    if t < 72:  return "#10b981"   # mild — green
    if t < 82:  return "#f59e0b"   # warm — amber
    if t < 92:  return "#ea580c"   # hot — orange
    return "#dc2626"               # very hot — red


fc = fetch_nws_forecast()
if fc:
    st.markdown('<h2><span class="section-pill">05</span>7-day outlook — Cedar Rapids</h2>',
                unsafe_allow_html=True)
    with st.container(border=True):
        # Group NWS periods by calendar date.
        daily: dict[str, dict] = {}
        for p in fc:
            try:
                start_date = datetime.fromisoformat(p["startTime"]).date()
            except Exception:
                continue
            key = start_date.isoformat()
            entry = daily.setdefault(key, {
                "date": start_date, "name": None,
                "high": None, "low": None, "short": "", "pop": None,
            })
            if p.get("isDaytime"):
                entry["high"] = p.get("temperature")
                entry["short"] = p.get("shortForecast", entry["short"])
                entry["name"] = p["name"]
            else:
                entry["low"] = p.get("temperature")
                if not entry["short"]:
                    entry["short"] = p.get("shortForecast", "")
                if not entry["name"]:
                    entry["name"] = p["name"].replace(" Night", "")
            pop = p.get("probabilityOfPrecipitation", {}).get("value")
            if pop is not None:
                entry["pop"] = max(entry.get("pop") or 0, pop)

        days = sorted(daily.values(), key=lambda x: x["date"])[:7]
        gdd_week_total = 0.0

        # Build the entire 7-day forecast as ONE flex row — no per-day cards,
        # just subtle 1px dividers between cells inside a single unified panel.
        cells_html = []
        for i, d in enumerate(days):
            icon = _weather_icon(d.get("short") or "")
            hi, lo = d.get("high"), d.get("low")
            hi_col = _temp_color(hi)
            short_name = (d.get("name") or d["date"].strftime("%a")).replace(" Afternoon", "")
            if len(short_name) > 11:
                short_name = short_name[:11]
            short_fc = d.get("short") or ""
            if len(short_fc) > 24:
                short_fc = short_fc[:21] + "..."
            pop = d.get("pop") or 0
            pop_html = (f"<div style='margin-top:0.3rem;font-size:0.7rem;color:#1e40af;font-weight:600;'>"
                        f"☔ {pop}%</div>") if pop >= 20 else ""
            gdd_html = ""
            if hi is not None and lo is not None:
                g = _gdd50_predicted(float(hi), float(lo))
                gdd_week_total += g
                gdd_html = (f"<div style='margin-top:0.25rem;font-size:0.7rem;color:#6b7280;"
                            f"letter-spacing:0.04em;'>GDD ≈ {g:.1f}</div>")
            lo_html = (f"<span style='font-size:1rem;color:#9ca3af;font-weight:500;'>"
                       f" / {lo}°</span>" if lo is not None else "")
            divider = "" if i == len(days) - 1 else "border-right:1px solid #e5e7eb;"
            date_label = d['date'].strftime('%b %d')
            hi_display = f"{hi}" if hi is not None else "–"
            # Build compact one-line HTML to avoid Streamlit markdown indent-as-code issues
            cell = (
                f'<div style="flex:1;text-align:center;padding:0.6rem 0.55rem;{divider}">'
                f'<div style="font-size:1.9rem;line-height:1;margin-bottom:0.3rem;">{icon}</div>'
                f'<div style="font-weight:700;font-size:0.88rem;color:#1a2330;">{short_name}</div>'
                f'<div style="font-size:0.7rem;color:#9ca3af;letter-spacing:0.03em;margin-bottom:0.55rem;">{date_label}</div>'
                f'<div style="font-size:1.7rem;font-weight:700;color:{hi_col};line-height:1;">{hi_display}°{lo_html}</div>'
                f'<div style="font-size:0.72rem;margin-top:0.55rem;color:#6b7280;line-height:1.35;min-height:1.9em;">{short_fc}</div>'
                f'{pop_html}{gdd_html}'
                f'</div>'
            )
            cells_html.append(cell)

        strip_html = (
            '<div style="display:flex;background:linear-gradient(180deg,#ffffff 0%,#f8fafc 100%);'
            'border-radius:10px;padding:0.4rem 0.2rem;margin-top:0.2rem;">'
            + "".join(cells_html)
            + '</div>'
        )
        st.html(strip_html)

        footer_html = (
            f'<div style="margin-top:1.1rem;font-size:0.85rem;color:#4b5563;">'
            f'<strong style="color:#1a2330;">7-day GDD50 contribution</strong> from forecast: '
            f'<span style="color:#0a3d3a;font-weight:700;">≈ {gdd_week_total:.1f}</span>'
            f'&nbsp;·&nbsp; <span style="color:#9ca3af;font-size:0.8rem;">'
            f'NWS api.weather.gov · refreshes every 6 hours</span></div>'
        )
        st.html(footer_html)
else:
    st.caption("NWS forecast unavailable right now — try refreshing the page.")

st.divider()
st.caption(
    f"Snapshot generated from `Corn Progress EC Iowa 2021 2025 v5.xlsx` "
    f"by `web/snapshot.py`. "
    f"Refresh: `uv run python -m web.snapshot` after each weekly update."
)
