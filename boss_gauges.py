"""Barras compartilhadas do chefe."""
import streamlit as st

LABELS = {"bleed": "Sangramento", "posture": "Postura"}


def gauges(raw=None):
    raw = {} if raw is None else raw
    if not isinstance(raw, dict):
        raise ValueError("gauges deve ser um objeto.")
    result = {}
    for key, label in LABELS.items():
        entry = raw.get(key, {})
        if not isinstance(entry, dict):
            raise ValueError(f"{label}: informe min, max e value.")
        try:
            low = int(entry.get("min", 0))
            high = int(entry.get("max", 100))
            value = int(entry.get("value", low))
        except (ValueError, TypeError):
            raise ValueError(f"{label}: os valores devem ser inteiros.")
        if not low <= value <= high or low >= high:
            raise ValueError(f"{label}: confira o mínimo, o máximo e o valor atual.")
        result[key] = {"min": low, "max": high, "value": value}
    return result


def render_gauges(raw):
    for key, entry in gauges(raw).items():
        low, high, value = entry["min"], entry["max"], entry["value"]
        width = 100 * (value - low) / (high - low)
        color = "#823147" if key == "bleed" else "#97783f"
        st.markdown(
            f'<div style="font-size:.78rem;font-weight:650">{LABELS[key]} · {value} / {high}</div>'
            f'<div role="meter" aria-label="{LABELS[key]}" aria-valuemin="{low}" '
            f'aria-valuemax="{high}" aria-valuenow="{value}" style="height:9px;background:#25252d;'
            f'border:1px solid #49434a;border-radius:3px;overflow:hidden;display:flex;justify-content:center">'
            f'<div style="height:100%;width:{width:.2f}%;background:{color}"></div></div>',
            unsafe_allow_html=True,
        )
