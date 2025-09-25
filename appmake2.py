import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
import folium
from streamlit_folium import st_folium

# ---------------------
# PAGE CONFIG
# ---------------------
st.set_page_config(layout="wide", page_title="Crop Health + Soil Dashboard")

# ---------------------
# EARTH ENGINE AUTH
# ---------------------
SERVICE_ACCOUNT = st.secrets["google_earth_engine"]["client_email"]
PRIVATE_KEY = st.secrets["google_earth_engine"]["private_key"]

credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, key_data=PRIVATE_KEY)
ee.Initialize(credentials)

# ---------------------
# DASHBOARD TITLE
# ---------------------
st.title("🌱 Crop Health & Soil Dashboard")

# ---------------------
# USER INPUT
# ---------------------
lat = st.number_input("Enter Latitude", value=22.5726, format="%.6f")
lon = st.number_input("Enter Longitude", value=88.3639, format="%.6f")

start_date = st.date_input("Start Date", value=pd.to_datetime("2024-01-01"))
end_date = st.date_input("End Date", value=pd.to_datetime("2024-01-31"))

if st.button("Analyze Location"):
    point = ee.Geometry.Point([lon, lat])

    # ---------------------
    # NDVI CALCULATION
    # ---------------------
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR")
          .filterBounds(point)
          .filterDate(str(start_date), str(end_date))
          .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 10)))

    def add_ndvi(img):
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
        return img.addBands(ndvi)

    ndvi_img = s2.map(add_ndvi).median().select("NDVI")

    mean_ndvi = ndvi_img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=point.buffer(30),
        scale=10
    ).get("NDVI").getInfo()

    if mean_ndvi is None:
        status = "No Data"
        color = "gray"
        ndvi_str = "N/A"
    elif mean_ndvi > 0.5:
        status = "Healthy"
        color = "green"
        ndvi_str = f"{mean_ndvi:.3f}"
    elif mean_ndvi > 0.2:
        status = "Moderately Healthy"
        color = "orange"
        ndvi_str = f"{mean_ndvi:.3f}"
    else:
        status = "Non-Healthy"
        color = "red"
        ndvi_str = f"{mean_ndvi:.3f}"

    # ---------------------
    # SOIL INFORMATION (OpenLandMap)
    # ---------------------
    soil_info = {}

    # Organic Carbon
    soil_oc = ee.Image("OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02")
    soil_oc_band = "ocd_usda.6a1c_m_sl1_250m"
    oc_val = soil_oc.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=point.buffer(250),
        scale=250
    ).get(soil_oc_band).getInfo()
    soil_info["Organic Carbon (g/kg)"] = f"{oc_val:.2f}" if oc_val else "No Data"

    # Soil pH
    soil_ph = ee.Image("OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02")
    soil_ph_band = "phh2o_usda.4c1a2a_m_sl1_250m"
    ph_val = soil_ph.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=point.buffer(250),
        scale=250
    ).get(soil_ph_band).getInfo()
    soil_info["Soil pH (H2O)"] = f"{ph_val:.2f}" if ph_val else "No Data"

    # Sand Fraction
    soil_sand = ee.Image("OpenLandMap/SOL/SOL_SAND-Content_USDA-3A1A1A_M/v02")
    soil_sand_band = "sand_usda.3a1a1a_m_sl1_250m"
    sand_val = soil_sand.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=point.buffer(250),
        scale=250
    ).get(soil_sand_band).getInfo()
    soil_info["Sand Fraction (%)"] = f"{sand_val:.2f}" if sand_val else "No Data"

    # Clay Fraction
    soil_clay = ee.Image("OpenLandMap/SOL/SOL_CLAY-Content_USDA-3A1A1A_M/v02")
    soil_clay_band = "clay_usda.3a1a1a_m_sl1_250m"
    clay_val = soil_clay.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=point.buffer(250),
        scale=250
    ).get(soil_clay_band).getInfo()
    soil_info["Clay Fraction (%)"] = f"{clay_val:.2f}" if clay_val else "No Data"

    # ---------------------
    # MAP VISUALIZATION
    # ---------------------
    m = geemap.Map(center=[lat, lon], zoom=12)

    ndvi_vis = {
        "min": 0.0,
        "max": 1.0,
        "palette": ["red", "yellow", "green"]
    }
    m.add_layer(ndvi_img, ndvi_vis, "NDVI Background")

    popup_text = f"NDVI: {ndvi_str}\nStatus: {status}\n"
    for k, v in soil_info.items():
        popup_text += f"{k}: {v}\n"

    folium.Marker(
        location=[lat, lon],
        popup=popup_text,
        icon=folium.Icon(color=color)
    ).add_to(m)

    # Legend
    legend_html = """
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 160px; 
                border:2px solid grey; z-index:9999; font-size:14px;
                background-color:white; padding: 10px;">
    <b>Legend</b><br>
    <i class="fa fa-map-marker" style="color:green"></i> Healthy<br>
    <i class="fa fa-map-marker" style="color:orange"></i> Moderate<br>
    <i class="fa fa-map-marker" style="color:red"></i> Non-Healthy<br>
    <i class="fa fa-map-marker" style="color:gray"></i> No Data
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # ---------------------
    # RESULTS
    # ---------------------
    st.subheader("📊 Results")
    st.write(f"**Latitude:** {lat}, **Longitude:** {lon}")
    st.write(f"**NDVI:** {ndvi_str} → **{status} vegetation**")

    st.write("### 🌍 Soil Properties")
    st.json(soil_info)

    st_folium(m, width="100%", height=600)
