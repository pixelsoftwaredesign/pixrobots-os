import json
import time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

API = "http://localhost:9999/api"

st.set_page_config(
    page_title="PixelOS - Dashboard",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)


def api_get(path: str) -> dict | list | None:
    try:
        req = Request(f"{API}{path}", headers={"Accept": "application/json"})
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except URLError as e:
        st.error(f"API erreur: {e.reason}")
        return None
    except Exception as e:
        st.error(f"Erreur: {e}")
        return None


# ─── Sidebar ──────────────────────────────────────────────
st.sidebar.title("🌿 PixelOS")
st.sidebar.caption("Système d'irrigation intelligent")

page = st.sidebar.radio("Navigation", [
    "📊 Vue d'ensemble",
    "🌱 Détail Espace",
    "📈 Prévisions ML",
    "🚿 RL Irrigation",
    "🔬 Laboratoire",
    "⚠ Alertes",
])

st.sidebar.divider()
if st.sidebar.button("🔄 Rafraîchir", use_container_width=True):
    st.rerun()

st.sidebar.caption(f"{datetime.now().strftime('%H:%M:%S')}")


# ─── HELPERS ──────────────────────────────────────────────

def space_to_df(espaces):
    rows = []
    for e in espaces:
        sensors = e.get("sensors", {})
        controls = e.get("controls", {})
        subs = e.get("sub_zones", {})
        row = {
            "id": e.get("espace_id", ""),
            "label": e.get("label", ""),
            "type": e.get("type", ""),
            "location": e.get("location", ""),
            "sensor_count": len(sensors),
            "control_count": len(controls),
            "subzone_count": len(subs),
            "auto_irrigation": e.get("auto_irrigation", False),
            "auto_climate": e.get("auto_climate", False),
        }
        for s_id, s_val in sensors.items():
            if isinstance(s_val, dict):
                row[f"sensor_{s_id}"] = s_val.get("value", s_val.get("latest", "N/A"))
        rows.append(row)
    return pd.DataFrame(rows)


def sensor_summary(espaces):
    total_s = 0
    sensor_vals = {"temperature": [], "humidite": [], "humidite_sol": []}
    for e in espaces:
        sensors = e.get("sensors", {})
        total_s += len(sensors)
        for s_id, s_val in sensors.items():
            v = None
            if isinstance(s_val, dict):
                v = s_val.get("value", s_val.get("latest"))
            else:
                v = s_val
            if v is not None:
                try:
                    v = float(v)
                except (ValueError, TypeError):
                    continue
                if "temp" in s_id.lower() or "temperature" in s_id.lower():
                    sensor_vals["temperature"].append(v)
                elif "humidite_sol" in s_id.lower() or "soil" in s_id.lower():
                    sensor_vals["humidite_sol"].append(v)
                elif "humidite" in s_id.lower() or "humidity" in s_id.lower():
                    sensor_vals["humidite"].append(v)
    return total_s, sensor_vals


# ═══════════════════════════════════════════════════════════
# PAGE: VUE D'ENSEMBLE
# ═══════════════════════════════════════════════════════════
if page == "📊 Vue d'ensemble":
    st.title("📊 Vue d'ensemble PixelOS")
    espaces = api_get("/spaces/list")
    if not espaces:
        st.warning("Aucun espace trouvé. Vérifiez PixelOS Web (port 9999).")
        st.stop()

    total_s, s_vals = sensor_summary(espaces)
    n_espaces = len(espaces)
    auto_i = sum(1 for e in espaces if e.get("auto_irrigation"))
    auto_c = sum(1 for e in espaces if e.get("auto_climate"))
    avg_temp = round(sum(s_vals["temperature"]) / len(s_vals["temperature"]), 1) if s_vals["temperature"] else 0
    avg_hum = round(sum(s_vals["humidite_sol"]) / len(s_vals["humidite_sol"]), 1) if s_vals["humidite_sol"] else 0

    cols = st.columns(5)
    cols[0].metric("🌾 Espaces", n_espaces)
    cols[1].metric("📡 Capteurs", total_s)
    cols[2].metric("🌡 Temp moy", f"{avg_temp}°C")
    cols[3].metric("💧 Humidité sol", f"{avg_hum}%")
    cols[4].metric("🔄 Auto irrigation", auto_i)

    st.divider()
    st.subheader("Espaces")
    df = space_to_df(espaces)
    cols_view = ["label", "type", "location", "sensor_count", "control_count",
                 "auto_irrigation", "auto_climate"]
    st.dataframe(df[cols_view] if all(c in df.columns for c in cols_view) else df,
                 use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Topologie des espaces")
    fig = go.Figure()
    for e in espaces:
        sensors = e.get("sensors", {})
        subs = e.get("sub_zones", {})
        fig.add_trace(go.Bar(
            name=e.get("label", e.get("espace_id", "?")),
            x=["Capteurs", "Sous-zones", "Contrôles"],
            y=[len(sensors), len(subs), len(e.get("controls", {}))],
        ))
    fig.update_layout(barmode="group", height=300,
                      margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

# ═══════════════════════════════════════════════════════════
# PAGE: DÉTAIL ESPACE
# ═══════════════════════════════════════════════════════════
elif page == "🌱 Détail Espace":
    st.title("🌱 Détail Espace")
    espaces = api_get("/spaces/list")
    if not espaces:
        st.stop()

    espace_opts = {f"{e.get('label', e.get('espace_id', '?'))}": e for e in espaces}
    choix = st.selectbox("Sélectionner un espace", list(espace_opts.keys()))
    espace = espace_opts[choix]
    eid = espace.get("espace_id", "")

    col1, col2, col3 = st.columns(3)
    col1.metric("🏷 Type", espace.get("type", "N/A"))
    col2.metric("📍 Location", espace.get("location", "N/A"))
    col3.metric("🔖 Label", espace.get("label", "N/A"))

    st.divider()
    st.subheader("Capteurs")
    sensors = espace.get("sensors", {})
    if sensors:
        s_rows = []
        for s_id, s_val in sensors.items():
            v = s_val.get("value", s_val.get("latest", "N/A")) if isinstance(s_val, dict) else s_val
            u = s_val.get("unit", "") if isinstance(s_val, dict) else ""
            t = s_val.get("type", s_val.get("sensor_type", "")) if isinstance(s_val, dict) else ""
            s_rows.append({"ID": s_id, "Type": t, "Valeur": v, "Unité": u})
        st.dataframe(pd.DataFrame(s_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Aucun capteur")

    st.subheader("Contrôles")
    controls = espace.get("controls", {})
    if controls:
        c_rows = []
        for c_id, c_val in controls.items():
            state = c_val.get("state", "off") if isinstance(c_val, dict) else "off"
            c_rows.append({"ID": c_id, "État": state})
        st.dataframe(pd.DataFrame(c_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Aucun contrôle")

    st.subheader("Sous-zones")
    subs = espace.get("sub_zones", {})
    if subs:
        z_rows = []
        for z_id, z_val in subs.items():
            product = z_val.get("product_id", "—") if isinstance(z_val, dict) else "—"
            planted = z_val.get("planted_at", "—") if isinstance(z_val, dict) else "—"
            z_rows.append({"Zone": z_id, "Produit": product, "Planté le": planted})
        st.dataframe(pd.DataFrame(z_rows), use_container_width=True, hide_index=True)

    st.divider()
    if st.button("📡 Lire capteurs", type="primary"):
        result = api_get(f"/spaces/{eid}")
        if result:
            st.success("Capteurs lus")
            st.rerun()
        else:
            st.error("Erreur lecture")

# ═══════════════════════════════════════════════════════════
# PAGE: PRÉVISIONS ML
# ═══════════════════════════════════════════════════════════
elif page == "📈 Prévisions ML":
    st.title("📈 Prévisions ML - Irrigation")
    onnx_stats = api_get("/ml/onnx/stats")
    if onnx_stats:
        st.json(onnx_stats)
    else:
        st.info("Moteur ONNX non disponible")

    st.divider()
    st.subheader("Pipeline ML")
    versions = api_get("/ml/pipeline/versions")
    if versions:
        df = pd.DataFrame(versions)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Derniers runs d'entraînement")
    runs = api_get("/tsdb/training?limit=10")
    if runs:
        df = pd.DataFrame(runs)
        for c in ["run_id", "model_name", "status", "mae", "r2_score"]:
            if c not in df.columns:
                df[c] = "N/A"
        st.dataframe(df[["run_id", "model_name", "status", "mae", "r2_score"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("Aucun run d'entraînement")

    st.divider()
    st.subheader("Edge Inference")
    edge_stats = api_get("/ml/edge/stats")
    if edge_stats:
        st.json(edge_stats)
    else:
        st.info("Edge inference non disponible")

# ═══════════════════════════════════════════════════════════
# PAGE: RL IRRIGATION
# ═══════════════════════════════════════════════════════════
elif page == "🚿 RL Irrigation":
    st.title("🚿 Reinforcement Learning - Irrigation")
    espaces = api_get("/spaces/list")
    zone_opts = {}
    for e in (espaces or []):
        eid = e.get("espace_id", "")
        zone_opts[f"{e.get('label', eid)} ({eid})"] = eid
    if not zone_opts:
        zone_opts = {"serre_a": "serre_a", "serre_b": "serre_b"}

    choix = st.selectbox("Zone RL", list(zone_opts.keys()))
    zone_id = zone_opts[choix]

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Stats RL", use_container_width=True):
            stats = api_get(f"/rl/stats?zone={zone_id}")
            if stats:
                st.json(stats)
    with col2:
        if st.button("📜 Historique RL", use_container_width=True):
            hist = api_get(f"/rl/history?zone={zone_id}&limit=20")
            if hist:
                df = pd.DataFrame(hist)
                if "ts" in df.columns and "reward" in df.columns:
                    st.line_chart(df.set_index("ts")["reward"])

    st.divider()
    st.subheader("Simulation pas RL")
    with st.form("rl_step"):
        moisture = st.number_input("Humidité sol (%)", 0.0, 100.0, 45.0)
        temp = st.number_input("Température (°C)", -10.0, 50.0, 22.0)
        hour = st.number_input("Heure", 0, 23, datetime.now().hour)
        submitted = st.form_submit_button("🚀 Choisir action")
        if submitted:
            result = api_get(f"/rl/best?zone={zone_id}&moisture={moisture}&temp={temp}&hour={hour}")
            if result:
                st.success(f"Action recommandée: **{result.get('action_label', 'N/A')}**")
                st.json(result)

# ═══════════════════════════════════════════════════════════
# PAGE: LABORATOIRE
# ═══════════════════════════════════════════════════════════
elif page == "🔬 Laboratoire":
    st.title("🔬 Laboratoire")
    lab_stats = api_get("/lab/stats")
    if lab_stats:
        st.json(lab_stats)
    else:
        st.warning("Module laboratoire non disponible")

# ═══════════════════════════════════════════════════════════
# PAGE: ALERTES
# ═══════════════════════════════════════════════════════════
elif page == "⚠ Alertes":
    st.title("⚠ Alertes")
    espaces = api_get("/spaces/list")
    if not espaces:
        st.stop()

    alertes = []
    for e in espaces:
        sensors = e.get("sensors", {})
        for s_id, s_val in sensors.items():
            v = None
            if isinstance(s_val, dict):
                v = s_val.get("value", s_val.get("latest"))
                t = s_val.get("type", "")
            else:
                v = s_val
                t = ""
            if v is not None:
                try:
                    v = float(v)
                except (ValueError, TypeError):
                    continue
                if t == "temperature" and (v < 5 or v > 40):
                    alertes.append({"espace": e.get("label", e.get("espace_id")),
                                    "capteur": s_id, "valeur": v, "type": "🌡 Température",
                                    "gravité": "Haute"})
                if ("humidite" in t or "soil" in s_id.lower()) and v < 20:
                    alertes.append({"espace": e.get("label", e.get("espace_id")),
                                    "capteur": s_id, "valeur": v, "type": "💧 Sécheresse",
                                    "gravité": "Haute"})
                if ("humidite" in t or "soil" in s_id.lower()) and v > 80:
                    alertes.append({"espace": e.get("label", e.get("espace_id")),
                                    "capteur": s_id, "valeur": v, "type": "💧 Excès eau",
                                    "gravité": "Moyenne"})

    if alertes:
        st.warning(f"{len(alertes)} alerte(s) en cours")
        df = pd.DataFrame(alertes)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.success("✅ Aucune alerte - tous les espaces sont OK")
