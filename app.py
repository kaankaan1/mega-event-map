import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import json
import requests
import random
import re
from streamlit_autorefresh import st_autorefresh

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Cancast Live Attendee Map", layout="wide", initial_sidebar_state="auto")

# --- SESSION STATES (Spam Koruması İçin) ---
if 'has_submitted' not in st.session_state:
    st.session_state.has_submitted = False
if 'new_user_loc' not in st.session_state:
    st.session_state.new_user_loc = None

# --- DEV EKRAN MODU (GİZLİ LİNK) KONTROLÜ ---
is_live_mode = st.query_params.get("mode") == "live"
if is_live_mode:
    st_autorefresh(interval=30 * 1000, key="datarefresh")

# --- CSS HACKS ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;} 
            footer {visibility: hidden;}    
            .stApp { background-color: white !important; color: black !important; }
            [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { color: black !important; }
            [data-testid="collapsedControl"] svg { fill: black !important; }
            div.stButton > button { background-color: #E31A1C !important; color: white !important; border: none; }
            div.stButton > button:hover { background-color: #B71C1C !important; color: white !important; }
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    if 'firebase_credentials' in st.secrets:
        key_dict = dict(st.secrets["firebase_credentials"])
        db_url = st.secrets["firebase_database"]["url"]
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': db_url})
    else:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred, {'databaseURL': 'https://cancastlivemap-b9214-default-rtdb.firebaseio.com/'})

DEFAULT_COORDS = [44.3011, -78.3333]

# --- SIDEBAR: ADMIN PANEL ---
with st.sidebar:
    st.header("🔒 Admin Access")
    admin_pass = st.text_input("Enter Password:", type="password")
    
    if admin_pass == "Cancast2026":
        st.success("Unlocked!")
        st.divider()
        st.subheader("🏢 Add Exhibitor (Red Star)")
        ex_company = st.text_input("Company Name:")
        ex_code = st.text_input("Vendor Postal Code:", max_chars=7)
        
        if st.button("Drop Exhibitor Pin"):
            clean_ex = re.sub(r'[^A-Z0-9]', '', ex_code.upper())
            if len(clean_ex) >= 3 and ex_company:
                try:
                    api_key = st.secrets["GOOGLE_MAPS_API_KEY"]
                    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={clean_ex},+Canada&key={api_key}"
                    response = requests.get(url).json()
                    if response['status'] == 'OK':
                        loc = response['results'][0]['geometry']['location']
                        city_n = clean_ex
                        components = response['results'][0]['address_components']
                        for comp in components:
                            if "locality" in comp["types"] or "postal_town" in comp["types"]:
                                city_n = comp["long_name"]
                                break
                        if city_n == clean_ex:
                            for comp in components:
                                if "administrative_area_level_3" in comp["types"] or "sublocality" in comp["types"] or "neighborhood" in comp["types"]:
                                    city_n = comp["long_name"]
                                    break
                        db.reference('attendees').push({
                            "lat": loc['lat'], "lon": loc['lng'], "city": city_n, "type": "exhibitor", "company": ex_company
                        })
                        st.success(f"{ex_company} added!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Enter both Company Name and Code.")

        st.divider()
        st.subheader("📊 Data Management")
        ref_admin = db.reference('attendees')
        data_dict_admin = ref_admin.get()
        data_list_admin = list(data_dict_admin.values()) if data_dict_admin else []
        
        if data_list_admin:
            att_count = sum(1 for d in data_list_admin if d.get("type", "attendee") == "attendee")
            exh_count = sum(1 for d in data_list_admin if d.get("type") == "exhibitor")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background-color: #E6F2FF; border-radius: 8px; border: 1px solid #B3D7FF;">
                        <p style="margin:0; font-size: 14px; color: #0056B3; font-weight: bold;">📍 Attendees</p>
                        <p style="margin:0; font-size: 26px; color: #007BFF; font-weight: bold;">{att_count}</p>
                    </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background-color: #FFEBEE; border-radius: 8px; border: 1px solid #FFCDD2;">
                        <p style="margin:0; font-size: 14px; color: #C62828; font-weight: bold;">⭐ Exhibitors</p>
                        <p style="margin:0; font-size: 26px; color: #F44336; font-weight: bold;">{exh_count}</p>
                    </div>
                """, unsafe_allow_html=True)
            st.write("")
            df = pd.DataFrame(data_list_admin)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Data (CSV)", data=csv, file_name='cancast_event_data.csv', mime='text/csv')
            st.divider() 
            if st.button("🗑️ Wipe All Data"):
                db.reference('attendees').delete()
                st.cache_data.clear()
                st.rerun()
        else:
            st.info("No data yet.")

# --- MAIN PAGE UI ---
col_l, col_m, col_r = st.columns([1, 1.5, 1])
with col_m:
    try: st.image("logo.png", use_container_width=True)
    except: pass

st.markdown("<h1 style='text-align: center;'>📍 What area are you coming in from?</h1>", unsafe_allow_html=True)

if not st.session_state.has_submitted:
    st.markdown("<p style='text-align: center;'>Enter your Canadian postal code to see how far our community reaches:</p>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        postal_code_input = st.text_input("Postal Code (e.g., P1B 8G6):", max_chars=7, label_visibility="collapsed", placeholder="P1B 8G6")
        submit_button = st.button("Submit", use_container_width=True)

    if submit_button and postal_code_input:
        clean_code = re.sub(r'[^A-Z0-9]', '', postal_code_input.upper())
        if len(clean_code) >= 3:
            try:
                api_key = st.secrets["GOOGLE_MAPS_API_KEY"]
                url = f"https://maps.googleapis.com/maps/api/geocode/json?address={clean_code},+Canada&key={api_key}"
                response = requests.get(url).json()
                if response['status'] == 'OK':
                    location = response['results'][0]['geometry']['location']
                    city_name = clean_code
                    components = response['results'][0]['address_components']
                    for comp in components:
                        if "locality" in comp["types"] or "postal_town" in comp["types"]:
                            city_name = comp["long_name"]
                            break
                    if city_name == clean_code:
                        for comp in components:
                            if "administrative_area_level_3" in comp["types"] or "sublocality" in comp["types"] or "neighborhood" in comp["types"]:
                                city_name = comp["long_name"]
                                break
                    db.reference('attendees').push({
                        "lat": location['lat'], "lon": location['lng'], "city": city_name, "type": "attendee" 
                    })
                    st.session_state.new_user_loc = {"lat": location['lat'], "lon": location['lng'], "city": city_name}
                    st.session_state.has_submitted = True
                    st.cache_data.clear()
                    st.rerun() 
                else:
                    st.error("Postal code not found. Please try again.")
            except Exception as e:
                st.error(f"Service error: {e}")
        else:
            st.error("Please enter a valid code.")
else:
    st.success("🎉 Thank you! Your location has been added to the map.")

# --- FETCH & RENDER MAP (30 SANİYE KALKAN) ---
st.divider()

@st.cache_data(ttl=30)
def get_cached_data():
    ref = db.reference('attendees')
    d_dict = ref.get()
    return list(d_dict.values()) if d_dict else []

data_list = get_cached_data()

# --- SUNUCU TARAFINDA VERİ GRUPLAMASI ---
attendee_summary = {}
exhibitors = []

for data in data_list:
    if data.get("type") == "exhibitor":
        exhibitors.append(data)
    else:
        city = data.get("city", "Unknown")
        if city not in attendee_summary:
            attendee_summary[city] = {"lat": data.get("lat"), "lon": data.get("lon"), "count": 0}
        attendee_summary[city]["count"] += 1

st.markdown("<p style='text-align: center; font-size: 18px;'><b>Legend:</b> ⭐ Exhibitors (Red Stars) &nbsp; | &nbsp; 📍 Attendees (Blue Pins)</p>", unsafe_allow_html=True)

# Performans ve Görsellik İçin Hafif Harita Altlığı: CartoDB Positron
m = folium.Map(location=DEFAULT_COORDS, zoom_start=6, tiles="cartodbpositron")
marker_cluster = MarkerCluster(maxClusterRadius=35).add_to(m)

for ex in exhibitors:
    comp_name = ex.get("company", "Exhibitor")
    random.seed(comp_name)
    jitter_lat = random.uniform(-0.003, 0.003)
    jitter_lon = random.uniform(-0.003, 0.003)
    folium.Marker(
        location=[ex["lat"] + jitter_lat, ex["lon"] + jitter_lon], tooltip=comp_name, icon=folium.Icon(color="red", icon="star", prefix="fa")
    ).add_to(m)

for city, info in attendee_summary.items():
    count = info["count"]
    is_newest = False
    
    if st.session_state.new_user_loc and st.session_state.new_user_loc["city"] == city:
        is_newest = True

    popup_text = f"<div style='text-align:center;'><b>{city}</b><br>Attendees: {count}</div>"
    tooltip_text = f"{city} ({count} Attendees)"

    if is_newest:
        folium.Marker(
            location=[info["lat"], info["lon"]], popup=popup_text, tooltip="📍 You are here!", icon=folium.Icon(color="orange", icon="star")
        ).add_to(m)
    else:
        folium.Marker(
            location=[info["lat"], info["lon"]], popup=popup_text, tooltip=tooltip_text, icon=folium.Icon(color="blue", icon="users", prefix="fa")
        ).add_to(marker_cluster)

st_folium(m, use_container_width=True, height=500, returned_objects=[])
