import os
import fastf1
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from fastf1.plotting import team_color

# cache directory
CACHE_DIR = os.path.join(os.getcwd(), "data_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

st.set_page_config(page_title="TelemetryXF1 — The F1 Telemetry Visualizer", layout="wide")
st.title("🏎️ TelemetryXF1")
st.caption("The F1 Telemetry Visualizer · Powered by FastF1 · Built by Tony")

@st.cache_data(show_spinner=False)
def list_events(year: int) -> pd.DataFrame:
    sched = fastf1.get_event_schedule(year, include_testing=False)
    return sched[["EventName", "RoundNumber", "EventFormat", "EventDate"]]

@st.cache_data(show_spinner=True)
def load_session(year: int, round_number: int, session_name: str):
    ses = fastf1.get_session(year, round_number, session_name)
    ses.load(laps=True, telemetry=True, weather=True)
    return ses

def _driver_team(session, code: str) -> str:
    laps = session.laps.pick_driver(code)
    if not laps.empty and "Team" in laps.columns and pd.notna(laps.iloc[0]["Team"]):
        return str(laps.iloc[0]["Team"])
    try:
        info = session.get_driver(code)
        if isinstance(info, dict) and "TeamName" in info and info["TeamName"]:
            return str(info["TeamName"])
    except Exception:
        pass
    return "Unknown"

@st.cache_data(show_spinner=True)
def load_driver_laps(session, driver_code: str) -> pd.DataFrame:
    laps = session.laps.pick_driver(driver_code).copy()
    laps.reset_index(drop=True, inplace=True)
    if not laps.empty:
        lt = laps["LapTime"].astype(str).fillna("NaT")
        laps["LapLabel"] = laps["LapNumber"].astype(str) + " · " + lt
    return laps

@st.cache_data(show_spinner=True)
def load_lap_telemetry(session, lap) -> pd.DataFrame:
    tel = lap.get_telemetry().reset_index(drop=True)
    if "Brake" in tel.columns:
        tel["Brake"] = tel["Brake"].astype(int)
    return tel

# Sidebar
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/en/e/e3/F1.svg", width=100)
    st.header("Session Controls")

    year = st.number_input("Season", min_value=2018, max_value=2025, value=2024, step=1)
    events = list_events(year)
    event_name = st.selectbox("Grand Prix", events["EventName"].tolist())
    round_number = int(events.loc[events["EventName"] == event_name, "RoundNumber"].iloc[0])

    session_name = st.selectbox("Session", ["R", "Q", "FP1", "FP2", "FP3"], index=0)

    with st.spinner("Loading session telemetry..."):
        session = load_session(year, round_number, session_name)

    drivers = sorted(session.drivers)
    d1 = st.selectbox("Driver A", drivers, index=0)
    d2 = st.selectbox("Driver B", drivers, index=min(1, len(drivers)-1))

    laps_d1 = load_driver_laps(session, d1)
    laps_d2 = load_driver_laps(session, d2)

    lap1 = st.selectbox("Lap A", laps_d1["LapLabel"] if not laps_d1.empty else [])
    lap2 = st.selectbox("Lap B", laps_d2["LapLabel"] if not laps_d2.empty else [])

    show_delta = st.checkbox("Align by Distance (Delta Mode)", value=True)

col1, col2 = st.columns(2)

if not laps_d1.empty and not laps_d2.empty and lap1 and lap2:
    lnum1 = int(str(lap1).split(" · ")[0])
    lnum2 = int(str(lap2).split(" · ")[0])

    lap_a = session.laps.pick_driver(d1).pick_lap(lnum1)
    lap_b = session.laps.pick_driver(d2).pick_lap(lnum2)

    tel_a = load_lap_telemetry(session, lap_a)
    tel_b = load_lap_telemetry(session, lap_b)

    if show_delta:
        try:
            _, tel_a_aligned, tel_b_aligned = fastf1.utils.delta_time(lap_a, lap_b)
        except Exception:
            tel_a_aligned, tel_b_aligned = tel_a.copy(), tel_b.copy()
    else:
        tel_a_aligned, tel_b_aligned = tel_a.copy(), tel_b.copy()

    x_a = tel_a_aligned["Distance"] if "Distance" in tel_a_aligned else tel_a_aligned.index
    x_b = tel_b_aligned["Distance"] if "Distance" in tel_b_aligned else tel_b_aligned.index

    team_a = _driver_team(session, d1)
    team_b = _driver_team(session, d2)
    try:
        color_a = team_color(team_a)
    except Exception:
        color_a = "#1f77b4"
    try:
        color_b = team_color(team_b)
    except Exception:
        color_b = "#ff7f0e"

    with col1:
        st.subheader("Speed vs Distance")
        fig = go.Figure()
        if "Speed" in tel_a_aligned:
            fig.add_trace(go.Scatter(x=x_a, y=tel_a_aligned["Speed"], name=f"{d1}", mode="lines", line=dict(color=color_a)))
        if "Speed" in tel_b_aligned:
            fig.add_trace(go.Scatter(x=x_b, y=tel_b_aligned["Speed"], name=f"{d2}", mode="lines", line=dict(color=color_b)))
        fig.update_layout(xaxis_title="Distance (m)", yaxis_title="Speed (km/h)")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Throttle and Brake")
        fig2 = go.Figure()
        if "Throttle" in tel_a_aligned:
            fig2.add_trace(go.Scatter(x=x_a, y=tel_a_aligned["Throttle"], name=f"{d1} throttle", mode="lines", line=dict(color=color_a)))
        if "Brake" in tel_a_aligned:
            fig2.add_trace(go.Scatter(x=x_a, y=tel_a_aligned["Brake"]*100, name=f"{d1} brake%", mode="lines", line=dict(color=color_a, dash="dash")))
        if "Throttle" in tel_b_aligned:
            fig2.add_trace(go.Scatter(x=x_b, y=tel_b_aligned["Throttle"], name=f"{d2} throttle", mode="lines", line=dict(color=color_b)))
        if "Brake" in tel_b_aligned:
            fig2.add_trace(go.Scatter(x=x_b, y=tel_b_aligned["Brake"]*100, name=f"{d2} brake%", mode="lines", line=dict(color=color_b, dash="dash")))
        fig2.update_layout(xaxis_title="Distance (m)", yaxis_title="Input (%)")
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.subheader("Gear and RPM")
        fig3 = go.Figure()
        if "nGear" in tel_a_aligned:
            fig3.add_trace(go.Scatter(x=x_a, y=tel_a_aligned["nGear"], name=f"{d1} gear", mode="lines", line=dict(color=color_a)))
        if "nGear" in tel_b_aligned:
            fig3.add_trace(go.Scatter(x=x_b, y=tel_b_aligned["nGear"], name=f"{d2} gear", mode="lines", line=dict(color=color_b)))
        if "RPM" in tel_a_aligned:
            fig3.add_trace(go.Scatter(x=x_a, y=tel_a_aligned["RPM"]/1000, name=f"{d1} RPM x1000", mode="lines", line=dict(color=color_a, dash="dot")))
        if "RPM" in tel_b_aligned:
            fig3.add_trace(go.Scatter(x=x_b, y=tel_b_aligned["RPM"]/1000, name=f"{d2} RPM x1000", mode="lines", line=dict(color=color_b, dash="dot")))
        fig3.update_layout(xaxis_title="Distance (m)", yaxis_title="Gear / RPM x1000")
        st.plotly_chart(fig3, use_container_width=True)

        st.subheader("Track Map")
        if all(k in tel_a.columns for k in ["X", "Y"]) and all(k in tel_b.columns for k in ["X", "Y"]):
            map_fig = go.Figure()
            map_fig.add_trace(go.Scatter(x=tel_a["X"], y=tel_a["Y"], mode="lines", name=f"{d1}", line=dict(color=color_a)))
            map_fig.add_trace(go.Scatter(x=tel_b["X"], y=tel_b["Y"], mode="lines", name=f"{d2}", line=dict(color=color_b)))
            map_fig.update_yaxes(scaleanchor="x", scaleratio=1)
            map_fig.update_layout(xaxis_title="X", yaxis_title="Y")
            st.plotly_chart(map_fig, use_container_width=True)
        else:
            st.info("Track position data not available for this session or lap.")
else:
    st.warning("Select valid drivers and laps to render telemetry.")
