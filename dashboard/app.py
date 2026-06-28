import json
import time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

API = "http://localhost:8080/api"

st.set_page_config(
    page_title="AgriCol - Dashboard",
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


def api_post(path: str, data: dict) -> bool:
    try:
        body = json.dumps(data).encode()
        req = Request(f"{API}{path}", data=body, headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        with urlopen(req, timeout=5) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        st.error(f"Erreur envoi: {e}")
        return False


# ─── Sidebar ──────────────────────────────────────────────
st.sidebar.image("https://img.icons8.com/color/96/plant-under-sun.png", width=80)
st.sidebar.title("🌿 AgriCol")
st.sidebar.caption("Système d'irrigation intelligent")

page = st.sidebar.radio("Navigation", [
    "📊 Vue d'ensemble",
    "🌱 Détail Zone",
    "🌤 Météo",
    "🚿 Irrigation",
    "⚠ Alertes",
])

st.sidebar.divider()
if st.sidebar.button("🔄 Rafraîchir", use_container_width=True):
    st.rerun()


# ─── HELPERS ──────────────────────────────────────────────
def carte_zone(zone: dict):
    hum = zone.get("derniereHumidite")
    seuil = zone.get("seuilHumidite", 30)
    ok = hum is not None and hum >= seuil

    color = "#2e7d32" if ok else "#c62828"
    st.markdown(f"""
    <div style="border:1px solid #ddd;border-radius:12px;padding:16px;margin-bottom:12px;
                border-left:5px solid {color};background:white;">
        <h4 style="margin:0;">{zone['nom']}</h4>
        <p style="margin:4px 0;color:#666;">{zone.get('culture','N/A')}</p>
        <p style="margin:4px 0;font-size:24px;font-weight:bold;color:{color};">
            {hum if hum is not None else 'N/A'}%
        </p>
        <p style="margin:2px 0;font-size:12px;color:#999;">
            Seuil: {seuil}% | Zone #{zone['id']}
        </p>
    </div>
    """, unsafe_allow_html=True)


def graphique_evolutions(zone_id: int, nom: str):
    mesures = api_get(f"/mesures/{zone_id}")
    if not mesures or len(mesures) == 0:
        st.info("Aucune donnée capteur pour cette zone")
        return

    df = pd.DataFrame(mesures)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["humidite"],
        mode="lines+markers", name="Humidité sol",
        line=dict(color="#2e7d32", width=2),
    ))
    if "temperature" in df.columns and df["temperature"].notna().any():
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["temperature"],
            mode="lines+markers", name="Température air",
            line=dict(color="#e65100", width=2),
            yaxis="y2",
        ))
    if "phSol" in df.columns and df["phSol"].notna().any():
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["phSol"],
            mode="lines+markers", name="pH sol",
            line=dict(color="#1565c0", width=2, dash="dot"),
        ))

    fig.update_layout(
        title=f"Évolution - {nom}",
        xaxis_title="Temps",
        yaxis_title="Humidité (%)",
        yaxis2=dict(title="Température (°C)", overlaying="y", side="right"),
        hovermode="x unified",
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# PAGE: VUE D'ENSEMBLE
# ═══════════════════════════════════════════════════════════
if page == "📊 Vue d'ensemble":
    st.title("📊 Vue d'ensemble")
    zones = api_get("/zones")
    if not zones:
        st.warning("Aucune zone trouvée. Vérifiez que le backend tourne.")
        st.stop()

    # Stats en haut
    total = len(zones)
    actives = sum(1 for z in zones if z.get("active", False))
    alerte = sum(1 for z in zones if z.get("derniereHumidite") is not None
                 and z["derniereHumidite"] < z.get("seuilHumidite", 30))
    hums = [z["derniereHumidite"] for z in zones if z.get("derniereHumidite") is not None]
    moy_hum = round(sum(hums) / len(hums), 1) if hums else 0

    cols = st.columns(4)
    cols[0].metric("🌾 Zones", total)
    cols[1].metric("✅ Actives", actives)
    cols[2].metric("💧 Humidité moy.", f"{moy_hum}%")
    cols[3].metric("⚠ Alertes", alerte, delta_color="inverse")

    st.divider()
    st.subheader("Zones")
    cols_z = st.columns(3)
    for i, zone in enumerate(zones):
        with cols_z[i % 3]:
            carte_zone(zone)

    st.divider()
    st.subheader("Dernières mesures")
    for zone in zones:
        graphique_evolutions(zone["id"], zone["nom"])

# ═══════════════════════════════════════════════════════════
# PAGE: DÉTAIL ZONE
# ═══════════════════════════════════════════════════════════
elif page == "🌱 Détail Zone":
    st.title("🌱 Détail Zone")
    zones = api_get("/zones")
    if not zones:
        st.stop()

    zone_opts = {f"#{z['id']} {z['nom']}": z for z in zones}
    choix = st.selectbox("Sélectionner une zone", list(zone_opts.keys()))
    zone = zone_opts[choix]

    col1, col2, col3 = st.columns(3)
    hum = zone.get("derniereHumidite", "N/A")
    col1.metric("💧 Humidité sol", f"{hum}%" if hum != "N/A" else "N/A")
    col2.metric("🌾 Culture", zone.get("culture", "N/A"))
    col3.metric("📏 Seuil", f"{zone.get('seuilHumidite', 30)}%")

    mesures = api_get(f"/mesures/{zone['id']}")
    if mesures:
        df = pd.DataFrame(mesures)
        cols = ["humidite", "temperature", "phSol", "temperatureSol",
                "humiditeAir", "pression", "ventKmh", "luminositeLux",
                "debitEauLMin", "pressionEauBar"]
        existantes = [c for c in cols if c in df.columns and df[c].notna().any()]
        if existantes:
            st.subheader("Capteurs disponibles")
            chart_type = st.radio("Type de graphique", ["Lignes", "Barres"], horizontal=True)
            fig = px.line if chart_type == "Lignes" else px.bar
            g = fig(df, x="timestamp", y=existantes,
                    title=f"Tous capteurs - {zone['nom']}",
                    labels={"value": "Valeur", "variable": "Capteur"})
            st.plotly_chart(g, use_container_width=True)

    st.divider()
    st.subheader("Actions")
    ouvrir = st.button("💧 Ouvrir vanne", type="primary")
    fermer = st.button("🚫 Fermer vanne")
    if ouvrir:
        ok = api_post("/irrigation/commande", {"zoneId": zone["id"], "ouvrir": True})
        if ok:
            st.success("Vanne ouverte !")
            time.sleep(1)
            st.rerun()
    if fermer:
        ok = api_post("/irrigation/commande", {"zoneId": zone["id"], "ouvrir": False})
        if ok:
            st.success("Vanne fermée !")
            time.sleep(1)
            st.rerun()

# ═══════════════════════════════════════════════════════════
# PAGE: MÉTÉO
# ═══════════════════════════════════════════════════════════
elif page == "🌤 Météo":
    st.title("🌤 Station Météo")
    zones = api_get("/zones")
    if not zones:
        st.stop()

    zone = st.selectbox("Zone", [f"#{z['id']} {z['nom']}" for z in zones])
    zone_id = int(zone.split("#")[1].split()[0])

    mesures = api_get(f"/mesures/{zone_id}")
    if mesures and len(mesures) > 0:
        df = pd.DataFrame(mesures)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")

        derniere = df.iloc[-1]

        cols = st.columns(5)
        cols[0].metric("🌡 Temp air", f"{derniere.get('temperature','N/A')}°C" if derniere.get('temperature') else "N/A")
        cols[1].metric("💧 Hum air", f"{derniere.get('humiditeAir','N/A')}%" if derniere.get('humiditeAir') else "N/A")
        cols[2].metric("🔽 Pression", f"{derniere.get('pression','N/A')} hPa" if derniere.get('pression') else "N/A")
        cols[3].metric("💨 Vent", f"{derniere.get('ventKmh','N/A')} km/h" if derniere.get('ventKmh') else "N/A")
        cols[4].metric("☀ Luminosité", f"{derniere.get('luminositeLux','N/A')} lux" if derniere.get('luminositeLux') else "N/A")

        cols_meteo = ["temperature", "humiditeAir", "pression", "ventKmh", "luminositeLux"]
        exist = [c for c in cols_meteo if c in df.columns and df[c].notna().any()]
        if exist:
            fig = px.line(df, x="timestamp", y=exist,
                          title="Évolution météo",
                          labels={"value": "Valeur", "variable": "Mesure"})
            st.plotly_chart(fig, use_container_width=True)

        if "pluie" in df.columns and df["pluie"].notna().any():
            pluies = df[df["pluie"] == True]
            if len(pluies) > 0:
                st.warning(f"🌧 Pluie détectée {len(pluies)} fois dans les dernières mesures")
    else:
        st.info("Aucune donnée météo")

# ═══════════════════════════════════════════════════════════
# PAGE: IRRIGATION
# ═══════════════════════════════════════════════════════════
elif page == "🚿 Irrigation":
    st.title("🚿 Contrôle Irrigation")
    zones = api_get("/zones")
    if not zones:
        st.stop()

    for zone in zones:
        with st.expander(f"🌾 {zone['nom']} ({zone.get('culture','N/A')})", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            hum = zone.get("derniereHumidite")
            seuil = zone.get("seuilHumidite", 30)
            col1.metric("💧 Humidité", f"{hum}%" if hum else "N/A")
            col2.metric("📏 Seuil", f"{seuil}%")
            besoin = hum < seuil if hum else False
            col3.metric("🚨 Besoin", "OUI" if besoin else "NON",
                        delta_color="inverse")

            if st.button(f"💧 Ouvrir vanne #{zone['id']}", key=f"open_{zone['id']}"):
                ok = api_post("/irrigation/commande", {"zoneId": zone["id"], "ouvrir": True})
                if ok:
                    st.success(f"✅ Vanne {zone['nom']} ouverte")
            if st.button(f"🚫 Fermer vanne #{zone['id']}", key=f"close_{zone['id']}"):
                ok = api_post("/irrigation/commande", {"zoneId": zone["id"], "ouvrir": False})
                if ok:
                    st.success(f"✅ Vanne {zone['nom']} fermée")

            # Consommation eau
            mesures = api_get(f"/mesures/{zone['id']}")
            if mesures:
                df = pd.DataFrame(mesures)
                if "debitEauLMin" in df.columns and df["debitEauLMin"].notna().any():
                    debit = df["debitEauLMin"].iloc[-1]
                    col4.metric("🚰 Débit eau", f"{debit} L/min" if debit else "N/A")
                    fig = px.line(df, x="timestamp", y="debitEauLMin",
                                  title="Débit d'eau (L/min)")
                    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Historique irrigation")
    hist = api_get("/irrigation/historique/1")
    if hist:
        df = pd.DataFrame(hist)
        st.dataframe(df, use_container_width=True)

# ═══════════════════════════════════════════════════════════
# PAGE: ALERTES
# ═══════════════════════════════════════════════════════════
elif page == "⚠ Alertes":
    st.title("⚠ Alertes")
    zones = api_get("/zones")
    if not zones:
        st.stop()

    alertes = []
    for z in zones:
        hum = z.get("derniereHumidite")
        seuil = z.get("seuilHumidite", 30)
        if hum is not None and hum < seuil:
            alertes.append({
                "zone": z["nom"],
                "type": "💧 Sécheresse",
                "message": f"H越小ité {hum}% < seuil {seuil}%",
                "gravite": "Haute",
            })
        if z.get("active") is False:
            alertes.append({
                "zone": z["nom"],
                "type": "⚠ Zone inactive",
                "message": "Zone désactivée",
                "gravite": "Moyenne",
            })

    if alertes:
        st.warning(f"{len(alertes)} alerte(s) en cours")
        df = pd.DataFrame(alertes)
        st.dataframe(df, use_container_width=True, column_config={
            "gravite": st.column_config.TextColumn("Gravité", help="Niveau d'urgence"),
        })
    else:
        st.success("✅ Aucune alerte - toutes les zones sont OK")

    # Alerte mouvement (edge)
    st.divider()
    st.subheader("Détection mouvement")
    st.info("Les alertes mouvement sont publiées via MQTT par l'agent Edge (topic `agricol/alerte/{zoneId}`). Activez l'agent Edge pour les recevoir.")

st.sidebar.divider()
st.sidebar.caption(f"🟢 API connectée | {datetime.now().strftime('%H:%M:%S')}")
