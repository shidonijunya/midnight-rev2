import json
import os
import random
from dataclasses import dataclass, asdict, field
from typing import List, Optional

import streamlit as st
from shared_backend import load_app_state, save_app_state, shared_enabled, upload_asset


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Simulador de Chefe RPG",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# ARQUIVO DE DADOS
# ============================================================

DATA_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "GEISONFODA.json"
)


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}

.main-title {
    text-align: center;
    font-size: 2.5rem;
    font-weight: 800;
    margin-bottom: 0.2rem;
}

.subtitle {
    text-align: center;
    color: #999;
    margin-bottom: 1.5rem;
}

.hp-container {
    border: 1px solid #333;
    border-radius: 14px;
    padding: 18px 25px 22px 25px;
    margin: 10px auto 20px auto;
    max-width: 700px;
    background: rgba(255,255,255,0.025);
}

.hp-title {
    text-align: center;
    font-size: 1.1rem;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #ddd;
    margin-bottom: 8px;
}

.hp-value {
    text-align: center;
    font-size: 2.2rem;
    font-weight: 800;
    margin-bottom: 10px;
}

.hp-bar-background {
    width: 100%;
    height: 25px;
    background: #262626;
    border-radius: 15px;
    overflow: hidden;
    border: 1px solid #444;
}

.hp-bar-fill {
    height: 100%;
    background: #d32f2f;
