"""Midnight Sun: single authenticated entry point.

Role numbers map to app entrypoints (Kuro/Andrias/Bondobo), while record IDs
are rotated in legacy Supabase: 1->2, 2->3, 3->1. Never remap records blindly.

Run: streamlit run app_unificado.py
"""
import streamlit as st
from auth_unified import login_gate, logout

st.set_page_config(page_title="Midnight Sun", page_icon="🌘", layout="wide")
role = login_gate()
st.sidebar.title("🌘 Midnight Sun")
st.sidebar.caption({"mestre":"Mestre","jogador_1":"Kuro","jogador_2":"Andrias","jogador_3":"Bondobo"}[role])
if st.sidebar.button("Sair", use_container_width=True):
    logout()

if role == "mestre":
    pages = {
        "Mesa": [st.Page("painel_geral.py", title="Painel", icon="🎲")],
        "Mestre": [st.Page("app_boss.py", title="Boss e cenas", icon="⚔️")],
        "Fichas": [
            st.Page("ficha_jogador_1.py", title="Kuro", icon="📜"),
            st.Page("ficha_jogador_2.py", title="Andrias", icon="📜"),
            st.Page("ficha_jogador_3.py", title="Bondobo", icon="📜"),
        ],
    }
else:
    pages = {
        "Jogador": [st.Page("ficha_" + role + ".py", title="Minha ficha", icon="📜")],
        "Mesa": [st.Page("painel_geral.py", title="Painel", icon="🎲")],
    }

st.navigation(pages, position="sidebar").run()
