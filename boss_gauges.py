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


def render_gauges(hp, max_hp, raw):
    palette = {"HP": ("#731522", "#ed3444"),
               "Sangramento": ("#571e30", "#963951"),
               "Postura": ("#66512d", "#aa884a")}
    readings = [("HP", 0, max_hp, hp)]
    for key, meter in gauges(raw).items():
        readings.append((LABELS[key], meter["min"], meter["max"], meter["value"]))

    tracks = []
    for label, low, high, value in readings:
        width = max(0, min(100, 100 * (value - low) / (high - low)))
        dark, light = palette[label]
        alignment = "flex-start" if label == "HP" else "center"
        gradient = f"{dark},{light}" if label == "HP" else f"{dark},{light},{dark}"
        tracks.append(
            f'<div role="meter" aria-label="{label}" aria-valuemin="{low}" '
            f'aria-valuemax="{high}" aria-valuenow="{value}" style="box-sizing:border-box;'
            f'width:100%;height:16px;border-radius:9px;border:1px solid #50424a;'
            f'background:#262229;overflow:hidden;display:flex;justify-content:{alignment}">'
            f'<div style="width:{width:.3f}%;height:100%;border-radius:inherit;'
            f'background:linear-gradient(90deg,{gradient})"></div></div>'
        )
    st.markdown('<div style="display:grid;gap:6px;width:100%">' + "".join(tracks) + '</div>',
                unsafe_allow_html=True)
