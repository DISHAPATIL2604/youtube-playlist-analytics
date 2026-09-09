"""
frontend/app.py — YouTube Playlist Analytics Dashboard.

Dark-themed, YouTube Studio-inspired Streamlit UI that communicates
with the FastAPI backend via HTTP.
"""
import os
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
REQUEST_TIMEOUT = 120  # seconds

# ---------------------------------------------------------------------------
# Page configuration & global CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="YouTube Playlist Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DARK_CSS = """
<style>
/* ── Base dark background ── */
.stApp { background-color: #0f0f0f; color: #e8e8e8; }
section[data-testid="stSidebar"] { background-color: #0f0f0f; }
header[data-testid="stHeader"] { background-color: #0f0f0f; }

/* ── Typography ── */
h1, h2, h3, h4 { color: #ffffff; }
p, span, label { color: #aaaaaa; }

/* ── Input fields ── */
.stTextInput > div > div > input {
    background-color: #1e1e1e;
    border: 1px solid #333;
    color: #ffffff;
    border-radius: 6px;
}
.stTextInput > div > div > input:focus {
    border-color: #ff0000;
    box-shadow: 0 0 0 2px rgba(255,0,0,0.2);
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #ff0000, #cc0000);
    color: white;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    padding: 0.5rem 1.5rem;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #ff3333, #ee0000);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(255,0,0,0.4);
}

/* ── KPI metric cards ── */
.kpi-card {
    background: linear-gradient(145deg, #1a1a1a, #222222);
    border: 1px solid #2d2d2d;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    text-align: center;
    margin-bottom: 1rem;
    transition: transform 0.2s ease, border-color 0.2s ease;
}
.kpi-card:hover {
    transform: translateY(-2px);
    border-color: #ff0000;
}
.kpi-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #888;
    margin-bottom: 0.4rem;
}
.kpi-value {
    font-size: 1.85rem;
    font-weight: 700;
    color: #ffffff;
    line-height: 1;
}
.kpi-icon {
    font-size: 1.3rem;
    margin-bottom: 0.5rem;
}

/* ── Section headers ── */
.section-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin: 2rem 0 1rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid #2d2d2d;
}
.section-title {
    font-size: 1.15rem;
    font-weight: 600;
    color: #ffffff;
    margin: 0;
}

/* ── Ranked video cards ── */
.video-rank-card {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 0.8rem;
    margin-bottom: 0.6rem;
    display: flex;
    gap: 0.8rem;
    align-items: flex-start;
    transition: border-color 0.2s ease;
}
.video-rank-card:hover { border-color: #555; }
.rank-badge {
    background: #333;
    color: #ff0000;
    font-weight: 700;
    font-size: 0.85rem;
    min-width: 28px;
    height: 28px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
}

/* ── Dataframe ── */
.stDataFrame { border-radius: 10px; overflow: hidden; }

/* ── Alert/info boxes ── */
.stAlert { border-radius: 8px; }

/* ── Divider ── */
hr { border-color: #2d2d2d; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] { background: #1a1a1a; border-radius: 8px; }
.stTabs [data-baseweb="tab"] { color: #aaa; }
.stTabs [aria-selected="true"] { color: #fff; }

/* ── Spinner ── */
.stSpinner > div { border-top-color: #ff0000 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #1a1a1a; }
::-webkit-scrollbar-thumb { background: #444; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #666; }
</style>
"""

st.markdown(DARK_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Plotly dark theme config
# ---------------------------------------------------------------------------

PLOTLY_LAYOUT = dict(
    paper_bgcolor="#0f0f0f",
    plot_bgcolor="#141414",
    font=dict(color="#cccccc", family="Inter, sans-serif"),
    xaxis=dict(gridcolor="#2a2a2a", linecolor="#333", tickcolor="#555"),
    yaxis=dict(gridcolor="#2a2a2a", linecolor="#333", tickcolor="#555"),
    margin=dict(l=50, r=30, t=50, b=50),
    hovermode="x unified",
)

COLORS = {
    "red": "#ff0000",
    "blue": "#4fc3f7",
    "green": "#81c784",
    "yellow": "#ffd54f",
    "purple": "#ce93d8",
    "orange": "#ffb74d",
    "teal": "#4db6ac",
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def format_number(n: int) -> str:
    """Format large numbers with K/M/B suffix."""
    if n is None:
        return "0"
    n = int(n)
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_rate(r: float) -> str:
    return f"{r:.3f}%"


def duration_to_str(seconds: int) -> str:
    """Convert seconds to MM:SS or HH:MM:SS string."""
    if not seconds:
        return "0:00"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def api_post(endpoint: str, payload: dict) -> Dict:
    """POST to FastAPI backend. Returns response dict or raises on error."""
    url = f"{BACKEND_URL}{endpoint}"
    response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def api_get(endpoint: str) -> Dict:
    """GET from FastAPI backend."""
    url = f"{BACKEND_URL}{endpoint}"
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------

def render_kpi_card(icon: str, label: str, value: str):
    """Render a single KPI card as HTML."""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-icon">{icon}</div>
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(icon: str, title: str):
    """Render a styled section header."""
    st.markdown(
        f"""
        <div class="section-header">
            <span style="font-size:1.2rem">{icon}</span>
            <span class="section-title">{title}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(kpis: Dict):
    """Render the 7-card KPI overview section."""
    render_section_header("📈", "Overview")

    cols = st.columns(4)
    kpi_data = [
        ("👁️", "Total Views", format_number(kpis["total_views"])),
        ("👍", "Total Likes", format_number(kpis["total_likes"])),
        ("💬", "Total Comments", format_number(kpis["total_comments"])),
        ("🎬", "Total Videos", format_number(kpis["total_videos"])),
    ]
    for col, (icon, label, value) in zip(cols, kpi_data):
        with col:
            render_kpi_card(icon, label, value)

    cols2 = st.columns(4)
    kpi_data2 = [
        ("📊", "Avg Views", format_number(int(kpis["avg_views"]))),
        ("🤙", "Avg Likes", format_number(int(kpis["avg_likes"]))),
        ("🗨️", "Avg Comments", format_number(int(kpis["avg_comments"]))),
        ("🔥", "Avg Engagement", format_rate(kpis["avg_engagement_rate"])),
    ]
    for col, (icon, label, value) in zip(cols2, kpi_data2):
        with col:
            render_kpi_card(icon, label, value)


def build_dataframe(videos: List[Dict]) -> pd.DataFrame:
    """Convert video response list to enriched analytics DataFrame."""
    rows = []
    for rank, v in enumerate(videos, start=1):
        pub = v.get("published_at")
        pub_str = ""
        if pub:
            try:
                pub_str = datetime.fromisoformat(pub.replace("Z", "+00:00")).strftime("%Y-%m-%d")
            except Exception:
                pub_str = str(pub)[:10]

        rows.append(
            {
                "Rank": rank,
                "Video ID": v["video_id"],
                "Title": v["title"],
                "Views": v["views"],
                "Likes": v["likes"],
                "Comments": v["comments"],
                "Published": pub_str,
                "Duration": duration_to_str(v.get("duration_seconds", 0)),
                "Like Rate %": round(v.get("like_rate", 0), 4),
                "Comment Rate %": round(v.get("comment_rate", 0), 4),
                "Engagement Rate %": round(v.get("engagement_rate", 0), 4),
                "Thumbnail": v.get("thumbnail_url", ""),
                "Channel": v.get("channel_name", ""),
            }
        )
    return pd.DataFrame(rows)


def render_trend_charts(df: pd.DataFrame):
    """Render interactive Plotly trend charts."""
    render_section_header("📉", "Trend Analytics")

    if df.empty:
        st.info("No data available for charts.")
        return

    # Sort by published date for trend lines
    df_time = df.dropna(subset=["Published"]).sort_values("Published")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["👁️ Views", "👍 Likes", "💬 Comments", "Views vs Likes", "Views vs Comments"]
    )

    with tab1:
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=df_time["Title"].apply(lambda t: t[:35] + "…" if len(t) > 35 else t),
                y=df_time["Views"],
                marker_color=COLORS["red"],
                name="Views",
                hovertemplate="<b>%{x}</b><br>Views: %{y:,}<extra></extra>",
            )
        )
        fig.update_layout(**PLOTLY_LAYOUT, title="Views per Video", xaxis_tickangle=-40)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df_time["Published"],
                y=df_time["Likes"],
                mode="lines+markers",
                line=dict(color=COLORS["blue"], width=2),
                marker=dict(size=6),
                name="Likes",
                hovertemplate="<b>%{x}</b><br>Likes: %{y:,}<extra></extra>",
                fill="tozeroy",
                fillcolor="rgba(79,195,247,0.1)",
            )
        )
        fig.update_layout(**PLOTLY_LAYOUT, title="Likes Over Time")
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df_time["Published"],
                y=df_time["Comments"],
                mode="lines+markers",
                line=dict(color=COLORS["green"], width=2),
                marker=dict(size=6),
                name="Comments",
                hovertemplate="<b>%{x}</b><br>Comments: %{y:,}<extra></extra>",
                fill="tozeroy",
                fillcolor="rgba(129,199,132,0.1)",
            )
        )
        fig.update_layout(**PLOTLY_LAYOUT, title="Comments Over Time")
        st.plotly_chart(fig, use_container_width=True)

    with tab4:
        fig = px.scatter(
            df,
            x="Views",
            y="Likes",
            hover_name="Title",
            color="Engagement Rate %",
            color_continuous_scale=[[0, "#333"], [0.5, "#ff6600"], [1, "#ff0000"]],
            size="Engagement Rate %",
            size_max=25,
            title="Views vs Likes",
        )
        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_traces(
            hovertemplate="<b>%{hovertext}</b><br>Views: %{x:,}<br>Likes: %{y:,}<extra></extra>"
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab5:
        fig = px.scatter(
            df,
            x="Views",
            y="Comments",
            hover_name="Title",
            color="Engagement Rate %",
            color_continuous_scale=[[0, "#333"], [0.5, "#4fc3f7"], [1, "#ff0000"]],
            size="Engagement Rate %",
            size_max=25,
            title="Views vs Comments",
        )
        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_traces(
            hovertemplate="<b>%{hovertext}</b><br>Views: %{x:,}<br>Comments: %{y:,}<extra></extra>"
        )
        st.plotly_chart(fig, use_container_width=True)


def render_top_videos_section(df: pd.DataFrame):
    """Render Top 10 ranked videos for Views, Likes, and Comments."""
    render_section_header("🏆", "Top Content")

    tab1, tab2, tab3 = st.tabs(
        ["🥇 Most Viewed", "👍 Most Liked", "💬 Most Commented"]
    )

    for tab, col_name, icon, color in [
        (tab1, "Views", "👁️", COLORS["red"]),
        (tab2, "Likes", "👍", COLORS["blue"]),
        (tab3, "Comments", "💬", COLORS["green"]),
    ]:
        with tab:
            top10 = df.nlargest(10, col_name).reset_index(drop=True)
            if top10.empty:
                st.info("No data available.")
                continue

            for i, row in top10.iterrows():
                thumb = row["Thumbnail"]
                col_a, col_b = st.columns([1, 4])
                with col_a:
                    if thumb:
                        st.image(thumb, width=120)
                    else:
                        st.markdown("🎬")
                with col_b:
                    rank_num = i + 1
                    title_text = row["Title"]
                    st.markdown(
                        f"**#{rank_num}** {title_text}",
                        help=title_text,
                    )
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Views", format_number(row["Views"]))
                    m2.metric("Likes", format_number(row["Likes"]))
                    m3.metric("Comments", format_number(row["Comments"]))
                st.markdown("<hr style='margin:0.5rem 0;border-color:#222'>", unsafe_allow_html=True)


def render_video_table(df: pd.DataFrame):
    """Render the searchable/sortable full video table."""
    render_section_header("📋", "All Videos")

    if df.empty:
        st.info("No videos found.")
        return

    # Search filter
    search = st.text_input(
        "🔍 Search videos",
        placeholder="Filter by title...",
        key="video_search",
    )
    if search:
        df = df[df["Title"].str.contains(search, case=False, na=False)]

    display_df = df[
        [
            "Rank",
            "Title",
            "Views",
            "Likes",
            "Comments",
            "Published",
            "Duration",
            "Like Rate %",
            "Comment Rate %",
            "Engagement Rate %",
        ]
    ].copy()

    # Numeric formatting for display
    display_df["Views"] = display_df["Views"].apply(lambda x: f"{int(x):,}")
    display_df["Likes"] = display_df["Likes"].apply(lambda x: f"{int(x):,}")
    display_df["Comments"] = display_df["Comments"].apply(lambda x: f"{int(x):,}")
    display_df["Like Rate %"] = display_df["Like Rate %"].apply(lambda x: f"{x:.3f}%")
    display_df["Comment Rate %"] = display_df["Comment Rate %"].apply(lambda x: f"{x:.3f}%")
    display_df["Engagement Rate %"] = display_df["Engagement Rate %"].apply(lambda x: f"{x:.3f}%")

    st.dataframe(
        display_df,
        use_container_width=True,
        height=450,
        hide_index=True,
    )

    # Download CSV
    csv = df.drop(columns=["Thumbnail"]).to_csv(index=False)
    st.download_button(
        label="⬇️ Download CSV",
        data=csv,
        file_name="playlist_analytics.csv",
        mime="text/csv",
    )


def render_engagement_chart(df: pd.DataFrame):
    """Render a horizontal bar chart of engagement rates."""
    if df.empty:
        return

    render_section_header("💡", "Engagement Rate by Video")

    top15 = df.nlargest(15, "Engagement Rate %").sort_values("Engagement Rate %")
    short_titles = top15["Title"].apply(lambda t: t[:45] + "…" if len(t) > 45 else t)

    fig = go.Figure(
        go.Bar(
            x=top15["Engagement Rate %"],
            y=short_titles,
            orientation="h",
            marker=dict(
                color=top15["Engagement Rate %"],
                colorscale=[[0, "#333"], [0.5, "#cc4400"], [1, "#ff0000"]],
                showscale=False,
            ),
            hovertemplate="<b>%{y}</b><br>Engagement: %{x:.3f}%<extra></extra>",
        )
    )
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Top 15 Videos by Engagement Rate",
        xaxis_title="Engagement Rate (%)",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():
    # ── Header ──────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:1rem;margin-bottom:0.5rem">
            <span style="font-size:2.2rem">📊</span>
            <div>
                <h1 style="margin:0;font-size:1.9rem;color:#fff">
                    YouTube Playlist Analytics
                </h1>
                <p style="margin:0;color:#888;font-size:0.85rem">
                    Powered by YouTube Data API v3 · FastAPI · PostgreSQL
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── URL input & action buttons ───────────────────────────────────────────
    col_input, col_btn, col_refresh = st.columns([6, 1.5, 1.5])

    with col_input:
        playlist_url = st.text_input(
            "YouTube Playlist URL",
            placeholder="https://www.youtube.com/playlist?list=PLxxxxxxxxxx",
            label_visibility="collapsed",
        )

    with col_btn:
        analyze_clicked = st.button("🔍 Analyze", use_container_width=True, type="primary")

    with col_refresh:
        refresh_clicked = st.button("🔄 Refresh", use_container_width=True)

    # ── Trigger logic ────────────────────────────────────────────────────────
    trigger = analyze_clicked or (
        refresh_clicked and "last_playlist_url" in st.session_state
    )

    # Use last URL for refresh
    if refresh_clicked and not playlist_url and "last_playlist_url" in st.session_state:
        playlist_url = st.session_state["last_playlist_url"]

    if trigger and playlist_url:
        st.session_state["last_playlist_url"] = playlist_url

        with st.spinner("⏳ Fetching playlist data from YouTube…"):
            try:
                data = api_post("/playlist/analyze", {"playlist_url": playlist_url})
                st.session_state["analytics_data"] = data
                st.success(
                    f"✅ **{data['playlist']['title']}** — "
                    f"{data['kpis']['total_videos']} videos loaded successfully!"
                )
            except requests.exceptions.ConnectionError:
                st.error(
                    "❌ **Cannot connect to the backend.** "
                    "Make sure FastAPI is running at: `" + BACKEND_URL + "`"
                )
                return
            except requests.exceptions.Timeout:
                st.error(
                    "⏱️ **Request timed out.** "
                    "The playlist may be very large. Please try again."
                )
                return
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                try:
                    detail = e.response.json().get("detail", str(e))
                except Exception:
                    detail = str(e)

                if status_code == 422:
                    st.error(f"🔗 **Invalid URL:** {detail}")
                elif status_code == 404:
                    st.error(f"🔍 **Not Found:** {detail}")
                elif status_code == 403:
                    st.error(f"🔑 **API Key Error:** {detail}")
                elif status_code == 429:
                    st.warning(f"⚠️ **Quota Exceeded:** {detail}")
                else:
                    st.error(f"🚨 **Error {status_code}:** {detail}")
                return
            except Exception as e:
                st.error(f"🚨 **Unexpected error:** {str(e)}")
                return
    elif trigger and not playlist_url:
        st.warning("⚠️ Please enter a YouTube Playlist URL.")

    # ── Render dashboard ─────────────────────────────────────────────────────
    if "analytics_data" not in st.session_state:
        _render_empty_state()
        return

    data = st.session_state["analytics_data"]
    playlist_info = data["playlist"]
    kpis = data["kpis"]
    videos = data["videos"]

    if not videos:
        st.warning("⚠️ This playlist has no videos with accessible statistics.")
        return

    # Playlist info bar
    st.markdown(
        f"""
        <div style="background:#1a1a1a;border:1px solid #2d2d2d;border-radius:10px;
                    padding:1rem 1.5rem;margin:1rem 0;display:flex;
                    align-items:center;justify-content:space-between">
            <div>
                <span style="color:#ff0000;font-weight:700;font-size:1.05rem">
                    {playlist_info['title']}
                </span>
                <span style="color:#888;font-size:0.85rem;margin-left:1rem">
                    {playlist_info.get('channel_name', '')}
                </span>
            </div>
            <div style="color:#666;font-size:0.8rem">
                Last updated: {playlist_info.get('updated_at', '')[:19].replace('T', ' ')} UTC
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Build DataFrame
    df = build_dataframe(videos)

    # Sort by views by default
    df = df.sort_values("Views", ascending=False).reset_index(drop=True)
    df["Rank"] = range(1, len(df) + 1)

    # Sections
    render_kpis(kpis)
    st.markdown("---")
    render_trend_charts(df)
    st.markdown("---")
    render_engagement_chart(df)
    st.markdown("---")
    render_top_videos_section(df)
    st.markdown("---")
    render_video_table(df)

    # Footer
    st.markdown(
        """
        <div style="text-align:center;color:#444;font-size:0.75rem;margin-top:3rem;
                    padding:1rem;border-top:1px solid #1a1a1a">
            YouTube Playlist Analytics · Built with Streamlit + FastAPI + PostgreSQL
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_empty_state():
    """Render the welcome / empty state when no playlist is loaded."""
    st.markdown(
        """
        <div style="text-align:center;padding:4rem 2rem;color:#555">
            <div style="font-size:5rem;margin-bottom:1.5rem">📊</div>
            <h2 style="color:#888;font-weight:400">Enter a YouTube Playlist URL to get started</h2>
            <p style="color:#555;max-width:500px;margin:1rem auto">
                Paste any public YouTube playlist URL above and click <strong style="color:#ff0000">Analyze</strong>
                to see detailed analytics including views, likes, comments,
                engagement rates, trend charts, and more.
            </p>
            <div style="display:flex;gap:2rem;justify-content:center;margin-top:2rem;flex-wrap:wrap">
                <div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:10px;
                            padding:1rem 1.5rem;min-width:160px">
                    <div style="font-size:1.5rem">👁️</div>
                    <div style="color:#aaa;margin-top:0.3rem;font-size:0.85rem">View Analytics</div>
                </div>
                <div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:10px;
                            padding:1rem 1.5rem;min-width:160px">
                    <div style="font-size:1.5rem">📈</div>
                    <div style="color:#aaa;margin-top:0.3rem;font-size:0.85rem">Trend Charts</div>
                </div>
                <div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:10px;
                            padding:1rem 1.5rem;min-width:160px">
                    <div style="font-size:1.5rem">🏆</div>
                    <div style="color:#aaa;margin-top:0.3rem;font-size:0.85rem">Top Content</div>
                </div>
                <div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:10px;
                            padding:1rem 1.5rem;min-width:160px">
                    <div style="font-size:1.5rem">💾</div>
                    <div style="color:#aaa;margin-top:0.3rem;font-size:0.85rem">Export CSV</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
