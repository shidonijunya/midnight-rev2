"""Midnight Sun: single authenticated entry point.

Run: streamlit run app_unificado.py
"""
import streamlit as st
from auth_unified import login_gate, logout

st.set_page_config(page_title="Midnight Sun", page_icon="🌘", layout="wide")
role = login_gate()
st.sidebar.title("🌘 Midnight Sun")
st.sidebar.caption("Mestre" if role == "mestre" else "Jogador")
if st.sidebar.button("Sair", use_container_width=True):
    logout()

if role == "mestre":
    pages = {
        "Mesa": [st.Page("painel_geral.py", title="Painel", icon="🎲")],
        "Mestre": [st.Page("app_boss.py", title="Boss e cenas", icon="⚔️")],
        "Fichas": [
            st.Page("ficha_jogador_1.py", title="Jogador 1", icon="📜"),
            st.Page("ficha_jogador_2.py", title="Jogador 2", icon="📜"),
            st.Page("ficha_jogador_3.py", title="Jogador 3", icon="📜"),
        ],
    }
else:
    pages = {
        "Jogador": [st.Page("ficha_" + role + ".py", title="Minha ficha", icon="📜")],
        "Mesa": [st.Page("painel_geral.py", title="Painel", icon="🎲")],
    }

st.navigation(pages, position="sidebar").run()
