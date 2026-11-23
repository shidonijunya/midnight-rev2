"""Fórmulas canônicas do Midnight Sun — sem Streamlit ou efeitos colaterais.

Mantém exatamente os cálculos já usados nas fichas. Novas mecânicas não
devem ser adicionadas aqui sem aprovação explícita das regras.
"""
from math import ceil


def modificador(valor):
    return (valor - 10) // 2


def bonus_nao_treinado(mod):
    return mod // 2


def bonus_treinado(mod):
    return mod + (mod // 2) + 1


def arredondar_para_cima(valor):
    return ceil(round(valor, 6))


def calc_hp_max(constituicao, fortitude):
    hp_const = 50 + (constituicao - 10) * 6
    hp_fort = (fortitude - 10) * 2
    return hp_const + hp_fort, hp_const, hp_fort


def calc_mana_max(carisma, sabedoria, inteligencia):
    return arredondar_para_cima(carisma * 1.7 + sabedoria * 1.7 + inteligencia * 2.3)


def calc_estamina_max(fortitude, forca, destreza):
    return arredondar_para_cima(fortitude * 4.6 + forca * 1.2 + destreza * 1.2)


def calc_peso_max(fortitude, constituicao):
    return round(fortitude + constituicao * 0.4, 2)


def formatar_peso(valor):
    if float(valor).is_integer():
        return str(int(valor))
    return f"{valor:.2f}".rstrip("0").rstrip(".")
