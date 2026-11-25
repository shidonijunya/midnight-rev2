import json
import random
from datetime import datetime, timezone
from html import escape
from dataclasses import dataclass, asdict, field
from typing import List, Optional

import streamlit as st
from boss_runtime import hydrate_runtime, persist_runtime
from shared_backend import (
    compare_and_set_app_state, create_app_state_if_missing, fetch_app_state,
    shared_enabled, upload_asset,
)


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Simulador de Chefe RPG",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="collapsed"
)
from auth_unified import require_role
require_role("mestre")



# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>
.block-container {max-width: 1340px; padding-top: 3.25rem; padding-bottom: 2rem;}
[data-testid="stVerticalBlock"] {gap: .7rem;}
.st-key-boss-overview, .st-key-boss-actions {background: rgba(122,130,155,.07);}
.st-key-boss-overview [data-testid="stProgress"] [role="progressbar"] > div {
    background-color: #b34854;
}
.boss-result {border-bottom:1px solid rgba(150,155,175,.25); padding:.7rem 0;}
.boss-result:first-child {padding-top:0;}
.boss-result:last-child {border:0;}
.boss-result h4 {margin:0 0 .4rem; font-size:1rem; padding:0;}
.boss-result .attack-kind {font-size:.76rem; font-weight:500; opacity:.75; margin-left:.45rem;}
.boss-result .critical {color:#ee9099; font-weight:700;}
.boss-result dl {display:grid; grid-template-columns:repeat(auto-fit,minmax(104px,1fr)); gap:.35rem 1rem; margin:0;}
.boss-result dt {font-size:.78rem; opacity:.8; overflow-wrap:anywhere;}
.boss-result dd {margin:0; font-size:1.25rem; font-weight:700; font-variant-numeric:tabular-nums;}
.boss-result .roll-detail {font-size:.79rem; opacity:.8; margin:.25rem 0 0;}
.boss-matrix {overflow-x:auto;}
.boss-matrix table {width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums;}
.boss-matrix th, .boss-matrix td {padding:.55rem .7rem; border-bottom:1px solid rgba(150,155,175,.25);}
.boss-matrix td {text-align:center; font-weight:650;}
.boss-matrix th[scope="row"] {text-align:left; font-weight:500;}
.matrix-green {background:rgba(78,153,113,.15);}
.matrix-yellow {background:rgba(196,155,63,.16);}
.matrix-red {background:rgba(190,71,82,.18);}
</style>
""", unsafe_allow_html=True)


DICE_OPTIONS = [4, 6, 8, 10, 12, 20]
STATUS_OPTIONS = [
    "Sangramento", "Hemorragia", "Queimadura", "Veneno",
    "Corrupção", "Atordoamento", "Congelamento", "Lentidão", "Paralisia"
]
MATRIX_COLUMNS = ["Parry", "Rolagem", "Bloquear", "Pular", "Correr"]


# ============================================================
# DICE ROLLER
# ============================================================

class DiceRoller:

    @staticmethod
    def roll(dice_count: int, dice_sides: int) -> int:
        if dice_count <= 0 or dice_sides <= 0:
            return 0
        return sum(
            random.randint(1, dice_sides)
            for _ in range(dice_count)
        )

    @staticmethod
    def roll_d20() -> int:
        return random.randint(1, 20)


# ============================================================
# ATTACK
# ============================================================

@dataclass
class Attack:

    id: int
    name: str
    type: str

    attack_bonus: int
    crit_min: int
    crit_max: int
    crit_multiplier: int

    damage_dice_count: int
    damage_dice_sides: int
    damage_bonus: int

    effect_name: str
    effect_dice_count: Optional[int] = None
    effect_dice_sides: Optional[int] = None

    def execute(self):

        natural_roll = DiceRoller.roll_d20()
        attack_result = natural_roll + self.attack_bonus

        is_critical = (
            self.crit_min <= natural_roll <= self.crit_max
        )

        damage_roll = DiceRoller.roll(
            self.damage_dice_count,
            self.damage_dice_sides
        )

        damage_result = damage_roll + self.damage_bonus
        final_damage = damage_result

        if is_critical:
            final_damage = damage_result * self.crit_multiplier

        if self.type == "physical":
            if self.effect_dice_count and self.effect_dice_sides:
                effect_value = DiceRoller.roll(
                    self.effect_dice_count,
                    self.effect_dice_sides
                )
            else:
                effect_value = 0
        else:
            effect_value = final_damage // 2

        return {
            "natural_roll": natural_roll,
            "attack_result": attack_result,
            "is_critical": is_critical,
            "damage_roll": damage_roll,
            "damage_result": damage_result,
            "final_damage": final_damage,
            "effect_value": effect_value
        }


# ============================================================
# FASE (sistema de fases baseado em % de HP)
# ============================================================

@dataclass
class Phase:

    hp_max: int  # limite superior da faixa de HP (%), inclusive
    hp_min: int  # limite inferior da faixa de HP (%), inclusive
    physical_ids: List[int] = field(default_factory=list)
    area_ids: List[int] = field(default_factory=list)
    label: str = ""  # rótulo opcional, ex: "ENFURECIDO", "FINAL"


def default_phases_for_attacks(physical_attacks: List[Attack], area_attacks: List[Attack]) -> List[Phase]:
    """
    Configuração padrão de fases usada quando um Boss ainda não possui
    fases explicitamente configuradas. Baseada nas regras padrão do sistema:

    Fase 1: 100-61% HP -> 3 físicos + 1 área
    Fase 2: 60-31% HP  -> 4 físicos + 3 áreas
    Fase 3: 30-0% HP   -> todos os ataques
    """

    phys_ids = [a.id for a in physical_attacks]
    area_ids = [a.id for a in area_attacks]

    def take(ids, n):
        return ids[:n] if n < len(ids) else list(ids)

    return [
        Phase(hp_max=100, hp_min=61, physical_ids=take(phys_ids, 3), area_ids=take(area_ids, 1)),
        Phase(hp_max=60, hp_min=31, physical_ids=take(phys_ids, 4), area_ids=take(area_ids, 3)),
        Phase(hp_max=30, hp_min=0, physical_ids=list(phys_ids), area_ids=list(area_ids)),
    ]


# ============================================================
# BOSS
# ============================================================

@dataclass
class Boss:

    name: str
    max_hp: int
    attacks: List[Attack]
    action_matrix: dict  # chave = str(attack.id) -> [5 valores]
    phases: List[Phase] = field(default_factory=list)

    def get_physical_attacks(self):
        return [a for a in self.attacks if a.type == "physical"]

    def get_area_attacks(self):
        return [a for a in self.attacks if a.type == "area"]

    def get_matrix_row(self, attack_id):
        return self.action_matrix.get(
            str(attack_id),
            [10, 10, 10, 10, 10]
        )

    def ensure_phases(self):
        """Garante que o Boss tenha uma configuração de fases válida."""
        if not self.phases:
            self.phases = default_phases_for_attacks(
                self.get_physical_attacks(), self.get_area_attacks()
            )
        return self.phases

    def get_current_phase_index(self, current_hp) -> int:
        """Retorna o índice (0-based) da fase correspondente ao HP atual."""

        phases = self.ensure_phases()

        hp_percentage = (current_hp / self.max_hp * 100) if self.max_hp else 0

        # Ordena da fase de maior HP para a de menor HP
        ordered = sorted(
            range(len(phases)),
            key=lambda i: -phases[i].hp_max
        )

        for i in ordered:
            phase = phases[i]
            if phase.hp_min <= hp_percentage <= phase.hp_max:
                return i

        # Fallback: acima de tudo -> primeira fase; abaixo de tudo -> última fase
        if hp_percentage > phases[ordered[0]].hp_max:
            return ordered[0]
        return ordered[-1]

    def get_current_phase(self, current_hp) -> Phase:
        return self.ensure_phases()[self.get_current_phase_index(current_hp)]

    def get_available_attacks_for_phase(self, phase: Phase):

        physical = [
            a for a in self.get_physical_attacks() if a.id in phase.physical_ids
        ]
        area = [
            a for a in self.get_area_attacks() if a.id in phase.area_ids
        ]

        # Rede de segurança: nunca deixar o combo sem opções
        if not physical:
            physical = self.get_physical_attacks() or self.attacks
        if not area:
            area = self.get_area_attacks() or self.attacks

        return physical, area

    def generate_combo(self, current_hp=None):

        if current_hp is None:
            current_hp = self.max_hp

        phase = self.get_current_phase(current_hp)
        physical, area = self.get_available_attacks_for_phase(phase)

        roll = random.random()

        if roll < 0.60:
            # 60% -> 3 ataques físicos
            combo = random.choices(physical, k=3)

        elif roll < 0.80:
            # 20% -> 2 físicos + 1 área
            combo = random.choices(physical, k=2) + random.choices(area, k=1)

        elif roll < 0.90:
            # 10% -> 1 físico + 1 área
            combo = random.choices(physical, k=1) + random.choices(area, k=1)

        else:
            # 10% -> 2 ataques em área
            combo = random.choices(area, k=2)

        return combo


# ============================================================
# SERIALIZAÇÃO (Boss/Attack <-> dict/JSON)
# ============================================================

def attack_to_dict(attack: Attack) -> dict:
    return asdict(attack)


def dict_to_attack(data: dict) -> Attack:
    return Attack(
        id=int(data["id"]),
        name=data["name"],
        type=data["type"],
        attack_bonus=int(data["attack_bonus"]),
        crit_min=int(data["crit_min"]),
        crit_max=int(data["crit_max"]),
        crit_multiplier=int(data["crit_multiplier"]),
        damage_dice_count=int(data["damage_dice_count"]),
        damage_dice_sides=int(data["damage_dice_sides"]),
        damage_bonus=int(data["damage_bonus"]),
        effect_name=data.get("effect_name") or "Nenhum",
        effect_dice_count=(
            int(data["effect_dice_count"])
            if data.get("effect_dice_count") not in (None, "")
            else None
        ),
        effect_dice_sides=(
            int(data["effect_dice_sides"])
            if data.get("effect_dice_sides") not in (None, "")
            else None
        ),
    )


def phase_to_dict(phase: Phase) -> dict:
    return asdict(phase)


def dict_to_phase(data: dict) -> Phase:
    return Phase(
        hp_max=int(data["hp_max"]),
        hp_min=int(data["hp_min"]),
        physical_ids=[int(x) for x in data.get("physical_ids", [])],
        area_ids=[int(x) for x in data.get("area_ids", [])],
        label=data.get("label") or "",
    )


def boss_to_dict(boss: Boss) -> dict:
    return {
        "name": boss.name,
        "max_hp": boss.max_hp,
        "attacks": [attack_to_dict(a) for a in boss.attacks],
        "action_matrix": boss.action_matrix,
        "phases": [phase_to_dict(p) for p in boss.ensure_phases()],
    }


def dict_to_boss(data: dict) -> Boss:
    attacks = [dict_to_attack(a) for a in data["attacks"]]

    phases_data = data.get("phases")
    if phases_data:
        phases = [dict_to_phase(p) for p in phases_data]
    else:
        # Boss antigo sem fases configuradas: cria configuração padrão
        physical_attacks = [a for a in attacks if a.type == "physical"]
        area_attacks = [a for a in attacks if a.type == "area"]
        phases = default_phases_for_attacks(physical_attacks, area_attacks)

    return Boss(
        name=data["name"],
        max_hp=int(data["max_hp"]),
        attacks=attacks,
        action_matrix={
            str(k): list(v) for k, v in data["action_matrix"].items()
        },
        phases=phases,
    )


# ============================================================
# BOSSES PADRÃO (usados apenas se bosses.json não existir)
# ============================================================

def make_attack(
    attack_id, name, attack_type, bonus, crit_min, multiplier,
    damage_count, damage_sides, damage_bonus, effect,
    effect_count=None, effect_sides=None
):
    return Attack(
        id=attack_id, name=name, type=attack_type,
        attack_bonus=bonus, crit_min=crit_min, crit_max=20,
        crit_multiplier=multiplier,
        damage_dice_count=damage_count, damage_dice_sides=damage_sides,
        damage_bonus=damage_bonus, effect_name=effect,
        effect_dice_count=effect_count, effect_dice_sides=effect_sides,
    )


def build_default_bosses() -> dict:

    def matrix_by_id(attacks, matrix_by_name):
        return {
            str(a.id): matrix_by_name[a.name]
            for a in attacks
        }

    warina_attacks = [
        make_attack(1, "Lança Rubra", "physical", 7, 17, 2, 10, 8, 5, "Sangramento", 2, 4),
        make_attack(2, "Corte Crescente", "physical", 6, 19, 2, 6, 8, 2, "Sangramento", 1, 4),
        make_attack(3, "Estocada Veloz", "physical", 5, 18, 3, 8, 6, 3, "Hemorragia", 2, 6),
        make_attack(4, "Martelo Solar", "physical", 8, 20, 4, 12, 6, 4, "Atordoamento", 1, 4),
        make_attack(5, "Gume Carmesim", "physical", 6, 17, 2, 7, 10, 3, "Corrupção", 2, 4),
        make_attack(6, "Chuva de Sangue", "area", 5, 19, 2, 8, 8, 4, "Queimadura"),
        make_attack(7, "Explosão Rubra", "area", 6, 18, 2, 10, 6, 5, "Sangramento em Área"),
        make_attack(8, "Vórtice Carmesim", "area", 4, 20, 3, 6, 10, 2, "Veneno"),
        make_attack(9, "Tempestade de Espinhos", "area", 7, 17, 2, 12, 8, 6, "Sangramento em Área"),
        make_attack(10, "Ruptura Escarlate", "area", 5, 19, 2, 9, 8, 3, "Lentidão"),
    ]
    warina_matrix_name = {
        "Lança Rubra": [28, 21, 17, 13, 11], "Corte Crescente": [24, 29, 19, 15, 12],
        "Estocada Veloz": [18, 25, 14, 22, 10], "Martelo Solar": [30, 23, 27, 16, 19],
        "Gume Carmesim": [26, 20, 18, 12, 15], "Chuva de Sangue": [22, 28, 25, 17, 13],
        "Explosão Rubra": [19, 26, 30, 21, 14], "Vórtice Carmesim": [15, 24, 20, 29, 18],
        "Tempestade de Espinhos": [27, 16, 28, 11, 23], "Ruptura Escarlate": [21, 30, 22, 18, 26],
    }

    kriv_attacks = [
        make_attack(1, "Punho do Abismo", "physical", 8, 18, 2, 9, 8, 4, "Sangramento", 2, 4),
        make_attack(2, "Lâmina Fraturada", "physical", 7, 19, 2, 7, 8, 3, "Corrupção", 1, 6),
        make_attack(3, "Ruptura Sombria", "physical", 6, 17, 3, 10, 6, 2, "Hemorragia", 2, 6),
        make_attack(4, "Investida Negra", "physical", 9, 20, 4, 12, 6, 5, "Atordoamento", 1, 4),
        make_attack(5, "Golpe Brutal", "physical", 7, 18, 2, 8, 10, 4, "Sangramento", 3, 4),
        make_attack(6, "Onda Abissal", "area", 6, 19, 2, 10, 8, 5, "Veneno"),
        make_attack(7, "Chamas Negras", "area", 7, 18, 2, 8, 6, 6, "Queimadura"),
        make_attack(8, "Névoa do Vazio", "area", 5, 20, 3, 7, 10, 3, "Corrupção"),
        make_attack(9, "Colapso Sombrio", "area", 8, 17, 2, 12, 8, 4, "Sangramento em Área"),
        make_attack(10, "Eclipse Mortal", "area", 6, 19, 2, 9, 8, 5, "Lentidão"),
    ]
    kriv_matrix_name = {
        "Punho do Abismo": [17, 22, 27, 11, 16], "Lâmina Fraturada": [23, 28, 12, 17, 22],
        "Ruptura Sombria": [29, 14, 19, 24, 29], "Investida Negra": [15, 20, 25, 30, 14],
        "Golpe Brutal": [21, 26, 10, 15, 20], "Onda Abissal": [27, 11, 16, 21, 26],
        "Chamas Negras": [13, 18, 23, 28, 12], "Névoa do Vazio": [19, 24, 29, 14, 19],
        "Colapso Sombrio": [25, 30, 14, 19, 24], "Eclipse Mortal": [23, 28, 12, 17, 22],
    }

    feng_attacks = [
        make_attack(1, "Garra do Vento", "physical", 6, 18, 2, 8, 8, 3, "Sangramento", 2, 4),
        make_attack(2, "Corte Celeste", "physical", 7, 17, 3, 9, 6, 4, "Atordoamento", 1, 6),
        make_attack(3, "Dança das Lâminas", "physical", 5, 19, 2, 11, 6, 2, "Hemorragia", 2, 6),
        make_attack(4, "Rasgo Tempestuoso", "physical", 8, 20, 4, 10, 8, 5, "Sangramento", 2, 4),
        make_attack(5, "Fúria Oriental", "physical", 6, 18, 2, 7, 10, 4, "Corrupção", 1, 4),
        make_attack(6, "Tufão Celeste", "area", 7, 18, 2, 9, 8, 5, "Lentidão"),
        make_attack(7, "Lâmina de Ar", "area", 5, 19, 3, 8, 6, 4, "Sangramento em Área"),
        make_attack(8, "Raio do Céu", "area", 8, 20, 2, 10, 10, 2, "Atordoamento"),
        make_attack(9, "Tormenta Oriental", "area", 6, 17, 2, 12, 8, 6, "Queimadura"),
        make_attack(10, "Ciclone Azul", "area", 7, 19, 3, 8, 8, 4, "Congelamento"),
    ]
    feng_matrix_name = {
        "Garra do Vento": [24, 29, 13, 18, 23], "Corte Celeste": [30, 14, 19, 24, 29],
        "Dança das Lâminas": [20, 25, 30, 14, 19], "Rasgo Tempestuoso": [26, 11, 16, 21, 26],
        "Fúria Oriental": [22, 27, 12, 17, 22], "Tufão Celeste": [28, 13, 18, 23, 28],
        "Lâmina de Ar": [17, 22, 27, 11, 16], "Raio do Céu": [23, 28, 12, 17, 22],
        "Tormenta Oriental": [29, 14, 19, 24, 29], "Ciclone Azul": [25, 30, 14, 19, 24],
    }

    tairon_attacks = [
        make_attack(1, "Espada do Trovão", "physical", 8, 17, 2, 10, 8, 5, "Atordoamento", 1, 6),
        make_attack(2, "Avanço Imperial", "physical", 7, 19, 3, 8, 10, 3, "Sangramento", 2, 4),
        make_attack(3, "Corte do Exílio", "physical", 6, 18, 2, 9, 8, 4, "Corrupção", 2, 6),
        make_attack(4, "Quebra-Escudo", "physical", 9, 20, 4, 12, 6, 6, "Atordoamento", 1, 4),
        make_attack(5, "Execução Real", "physical", 8, 17, 2, 7, 10, 5, "Hemorragia", 3, 4),
        make_attack(6, "Trovão Imperial", "area", 7, 18, 2, 10, 8, 4, "Atordoamento"),
        make_attack(7, "Tempestade Real", "area", 6, 19, 3, 9, 6, 5, "Sangramento em Área"),
        make_attack(8, "Impacto Celestial", "area", 8, 20, 2, 11, 8, 3, "Queimadura"),
        make_attack(9, "Queda do Relâmpago", "area", 7, 17, 2, 12, 8, 6, "Paralisia"),
        make_attack(10, "Domínio da Guerra", "area", 5, 19, 3, 8, 10, 4, "Lentidão"),
    ]
    tairon_matrix_name = {
        "Espada do Trovão": [11, 16, 21, 26, 30], "Avanço Imperial": [18, 23, 28, 13, 17],
        "Corte do Exílio": [25, 30, 15, 20, 24], "Quebra-Escudo": [29, 14, 19, 24, 28],
        "Execução Real": [21, 26, 11, 16, 21], "Trovão Imperial": [27, 12, 17, 22, 27],
        "Tempestade Real": [23, 28, 13, 18, 23], "Impacto Celestial": [30, 15, 20, 25, 29],
        "Queda do Relâmpago": [26, 11, 16, 21, 26], "Domínio da Guerra": [19, 24, 29, 14, 19],
    }

    laurentius_attacks = [
        make_attack(1, "Foice Dourada", "physical", 7, 18, 2, 9, 8, 4, "Sangramento", 2, 4),
        make_attack(2, "Martelo Sacro", "physical", 8, 20, 3, 10, 6, 5, "Atordoamento", 1, 4),
        make_attack(3, "Lança da Aurora", "physical", 6, 17, 2, 8, 10, 3, "Queimadura", 2, 6),
        make_attack(4, "Corte Absoluto", "physical", 9, 19, 4, 12, 8, 4, "Hemorragia", 2, 4),
        make_attack(5, "Queda do Santo", "physical", 7, 18, 2, 7, 8, 6, "Corrupção", 1, 6),
        make_attack(6, "Aurora Devastadora", "area", 6, 19, 2, 10, 8, 5, "Queimadura"),
        make_attack(7, "Círculo Sagrado", "area", 5, 20, 3, 8, 10, 4, "Congelamento"),
        make_attack(8, "Luz Julgadora", "area", 8, 18, 2, 11, 6, 5, "Atordoamento"),
        make_attack(9, "Chuva Dourada", "area", 7, 17, 2, 12, 8, 6, "Sangramento em Área"),
        make_attack(10, "Cataclismo Divino", "area", 9, 19, 3, 9, 8, 5, "Lentidão"),
    ]
    laurentius_matrix_name = {
        "Foice Dourada": [17, 22, 27, 11, 16], "Martelo Sacro": [24, 29, 14, 19, 24],
        "Lança da Aurora": [21, 26, 10, 15, 20], "Corte Absoluto": [28, 13, 18, 23, 28],
        "Queda do Santo": [30, 15, 20, 25, 29], "Aurora Devastadora": [23, 28, 12, 17, 22],
        "Círculo Sagrado": [19, 24, 29, 14, 19], "Luz Julgadora": [26, 11, 16, 21, 26],
        "Chuva Dourada": [22, 27, 12, 17, 22], "Cataclismo Divino": [29, 14, 19, 24, 28],
    }

    emily_attacks = [
        make_attack(1, "Disparo de Cinzas", "physical", 6, 17, 2, 8, 8, 4, "Queimadura", 2, 4),
        make_attack(2, "Punho Ardente", "physical", 7, 18, 3, 10, 6, 3, "Queimadura", 1, 6),
        make_attack(3, "Corte da Fumaça", "physical", 8, 19, 2, 7, 10, 5, "Veneno", 2, 4),
        make_attack(4, "Ruptura Carmim", "physical", 9, 20, 4, 12, 6, 4, "Hemorragia", 2, 6),
        make_attack(5, "Golpe da Fênix", "physical", 7, 17, 2, 9, 8, 6, "Queimadura", 3, 4),
        make_attack(6, "Inferno de Cinzas", "area", 6, 18, 2, 10, 8, 5, "Queimadura"),
        make_attack(7, "Explosão da Fênix", "area", 8, 19, 3, 9, 6, 6, "Queimadura"),
        make_attack(8, "Fumaça Tóxica", "area", 5, 20, 2, 8, 10, 3, "Veneno"),
        make_attack(9, "Maré de Brasas", "area", 7, 17, 2, 12, 8, 5, "Sangramento em Área"),
        make_attack(10, "Sol Carbonizado", "area", 9, 18, 3, 10, 6, 4, "Corrupção"),
    ]
    emily_matrix_name = {
        "Disparo de Cinzas": [24, 29, 13, 18, 23], "Punho Ardente": [30, 15, 20, 25, 29],
        "Corte da Fumaça": [22, 27, 12, 17, 22], "Ruptura Carmim": [28, 13, 18, 23, 28],
        "Golpe da Fênix": [26, 11, 16, 21, 26], "Inferno de Cinzas": [19, 24, 29, 14, 19],
        "Explosão da Fênix": [25, 30, 15, 20, 25], "Fumaça Tóxica": [21, 26, 10, 15, 20],
        "Maré de Brasas": [27, 12, 17, 22, 27], "Sol Carbonizado": [29, 14, 19, 24, 28],
    }

    boss7_attacks = [
        make_attack(1, "Mandíbula de Ferro", "physical", 8, 18, 2, 10, 8, 5, "Sangramento", 2, 4),
        make_attack(2, "Corte Selvagem", "physical", 6, 17, 3, 8, 6, 4, "Hemorragia", 2, 6),
        make_attack(3, "Investida Bestial", "physical", 9, 20, 4, 12, 6, 5, "Atordoamento", 1, 4),
        make_attack(4, "Punho Demolidor", "physical", 7, 19, 2, 9, 8, 3, "Sangramento", 3, 4),
        make_attack(5, "Rasgo Alfa", "physical", 8, 18, 3, 7, 10, 4, "Corrupção", 1, 6),
        make_attack(6, "Uivo Bestial", "area", 6, 19, 2, 10, 8, 5, "Lentidão"),
        make_attack(7, "Terremoto Selvagem", "area", 7, 17, 2, 12, 6, 6, "Atordoamento"),
        make_attack(8, "Impacto Alfa", "area", 8, 20, 3, 9, 10, 3, "Sangramento em Área"),
        make_attack(9, "Fúria da Matilha", "area", 5, 18, 2, 8, 8, 4, "Sangramento em Área"),
        make_attack(10, "Abalo Primordial", "area", 9, 19, 2, 11, 8, 5, "Queimadura"),
    ]
    boss7_matrix_name = {
        "Mandíbula de Ferro": [12, 17, 22, 27, 30], "Corte Selvagem": [18, 23, 28, 13, 18],
        "Investida Bestial": [25, 30, 15, 20, 25], "Punho Demolidor": [21, 26, 11, 16, 21],
        "Rasgo Alfa": [29, 14, 19, 24, 29], "Uivo Bestial": [23, 28, 13, 18, 23],
        "Terremoto Selvagem": [27, 12, 17, 22, 27], "Impacto Alfa": [30, 15, 20, 25, 30],
        "Fúria da Matilha": [19, 24, 29, 14, 19], "Abalo Primordial": [26, 11, 16, 21, 26],
    }

    boss8_attacks = [
        make_attack(1, "Lâmina Lunar", "physical", 7, 17, 2, 9, 8, 4, "Congelamento", 2, 4),
        make_attack(2, "Corte Prismático", "physical", 8, 18, 3, 8, 10, 3, "Corrupção", 1, 6),
        make_attack(3, "Estocada Astral", "physical", 6, 19, 2, 10, 6, 5, "Sangramento", 2, 4),
        make_attack(4, "Gume Fantasma", "physical", 9, 20, 4, 12, 8, 4, "Hemorragia", 2, 6),
        make_attack(5, "Queda Estelar", "physical", 7, 17, 2, 7, 8, 6, "Atordoamento", 1, 4),
        make_attack(6, "Lua Partida", "area", 6, 19, 2, 10, 8, 5, "Congelamento"),
        make_attack(7, "Chuva Estelar", "area", 8, 18, 3, 9, 6, 4, "Queimadura"),
        make_attack(8, "Vácuo Prismático", "area", 5, 20, 2, 8, 10, 3, "Corrupção"),
        make_attack(9, "Eclipse Lunar", "area", 7, 17, 2, 12, 8, 6, "Lentidão"),
        make_attack(10, "Queda Cósmica", "area", 9, 19, 3, 11, 6, 5, "Sangramento em Área"),
    ]
    boss8_matrix_name = {
        "Lâmina Lunar": [19, 24, 29, 14, 19], "Corte Prismático": [26, 11, 16, 21, 26],
        "Estocada Astral": [22, 27, 12, 17, 22], "Gume Fantasma": [29, 14, 19, 24, 29],
        "Queda Estelar": [24, 29, 13, 18, 23], "Lua Partida": [28, 13, 18, 23, 28],
        "Chuva Estelar": [21, 26, 11, 16, 21], "Vácuo Prismático": [30, 15, 20, 25, 30],
        "Eclipse Lunar": [25, 30, 15, 20, 25], "Queda Cósmica": [27, 12, 17, 22, 27],
    }

    boss9_attacks = [
        make_attack(1, "Machado Negro", "physical", 8, 18, 2, 10, 8, 5, "Sangramento", 2, 6),
        make_attack(2, "Corte do Carrasco", "physical", 7, 19, 3, 9, 6, 4, "Hemorragia", 2, 4),
        make_attack(3, "Golpe Profundo", "physical", 6, 17, 2, 8, 10, 3, "Corrupção", 1, 6),
        make_attack(4, "Investida Sanguínea", "physical", 9, 20, 4, 12, 6, 6, "Sangramento", 3, 4),
        make_attack(5, "Ruptura Final", "physical", 8, 18, 3, 7, 8, 5, "Atordoamento", 1, 4),
        make_attack(6, "Campo de Sangue", "area", 7, 19, 2, 10, 8, 5, "Sangramento em Área"),
        make_attack(7, "Ruptura da Terra", "area", 6, 17, 2, 12, 6, 6, "Atordoamento"),
        make_attack(8, "Tempestade Negra", "area", 8, 20, 3, 9, 10, 3, "Corrupção"),
        make_attack(9, "Execução em Massa", "area", 5, 18, 2, 11, 8, 4, "Lentidão"),
        make_attack(10, "Abismo Aberto", "area", 9, 19, 3, 10, 6, 5, "Veneno"),
    ]
    boss9_matrix_name = {
        "Machado Negro": [23, 28, 13, 18, 23], "Corte do Carrasco": [30, 15, 20, 25, 30],
        "Golpe Profundo": [18, 23, 28, 13, 18], "Investida Sanguínea": [27, 12, 17, 22, 27],
        "Ruptura Final": [25, 30, 15, 20, 25], "Campo de Sangue": [29, 14, 19, 24, 29],
        "Ruptura da Terra": [21, 26, 11, 16, 21], "Tempestade Negra": [28, 13, 18, 23, 28],
        "Execução em Massa": [24, 29, 14, 19, 24], "Abismo Aberto": [26, 11, 16, 21, 26],
    }

    boss10_attacks = [
        make_attack(1, "Espada Vazia", "physical", 7, 17, 2, 9, 8, 4, "Corrupção", 2, 4),
        make_attack(2, "Corte Nulo", "physical", 8, 18, 3, 10, 6, 5, "Sangramento", 1, 6),
        make_attack(3, "Estocada Sombria", "physical", 6, 19, 2, 8, 10, 3, "Hemorragia", 2, 6),
        make_attack(4, "Golpe Terminal", "physical", 9, 20, 4, 12, 8, 6, "Atordoamento", 1, 4),
        make_attack(5, "Execução Vazia", "physical", 8, 17, 3, 7, 8, 5, "Corrupção", 2, 4),
        make_attack(6, "Silêncio Absoluto", "area", 6, 19, 2, 10, 8, 5, "Lentidão"),
        make_attack(7, "Colapso do Nada", "area", 7, 18, 3, 9, 6, 4, "Corrupção"),
        make_attack(8, "Vazio Crescente", "area", 8, 20, 2, 8, 10, 3, "Veneno"),
        make_attack(9, "Fim do Mundo", "area", 9, 17, 2, 12, 8, 6, "Sangramento em Área"),
        make_attack(10, "Zero Final", "area", 10, 19, 4, 11, 6, 5, "Atordoamento"),
    ]
    boss10_matrix_name = {
        "Espada Vazia": [14, 19, 24, 29, 18], "Corte Nulo": [27, 12, 17, 22, 27],
        "Estocada Sombria": [23, 28, 13, 18, 23], "Golpe Terminal": [30, 15, 20, 25, 30],
        "Execução Vazia": [26, 11, 16, 21, 26], "Silêncio Absoluto": [21, 26, 11, 16, 21],
        "Colapso do Nada": [29, 14, 19, 24, 29], "Vazio Crescente": [25, 30, 15, 20, 25],
        "Fim do Mundo": [28, 13, 18, 23, 28], "Zero Final": [30, 15, 20, 25, 30],
    }

    definitions = [
        ("Warina", 60, warina_attacks, warina_matrix_name),
        ("Kriv", 50, kriv_attacks, kriv_matrix_name),
        ("Feng", 65, feng_attacks, feng_matrix_name),
        ("Tairon", 70, tairon_attacks, tairon_matrix_name),
        ("Laurentius", 80, laurentius_attacks, laurentius_matrix_name),
        ("Emily Burns", 55, emily_attacks, emily_matrix_name),
        ("Boss 7", 75, boss7_attacks, boss7_matrix_name),
        ("Boss 8", 90, boss8_attacks, boss8_matrix_name),
        ("Boss 9", 100, boss9_attacks, boss9_matrix_name),
        ("Boss 10", 120, boss10_attacks, boss10_matrix_name),
    ]

    bosses = {}

    for name, max_hp, attacks, matrix_name in definitions:
        physical_attacks = [a for a in attacks if a.type == "physical"]
        area_attacks = [a for a in attacks if a.type == "area"]
        bosses[name] = Boss(
            name=name,
            max_hp=max_hp,
            attacks=attacks,
            action_matrix=matrix_by_id(attacks, matrix_name),
            phases=default_phases_for_attacks(physical_attacks, area_attacks),
        )

    return bosses


# ============================================================
# CARREGAR / SALVAR BOSSES.JSON
# ============================================================

def load_bosses() -> dict:
    """Supabase is authoritative. A failed read can NEVER reset stored bosses."""
    if not shared_enabled():
        st.error("A biblioteca de chefes requer o Supabase para preservar os dados.")
        st.stop()
    result = fetch_app_state("boss_config")
    if result["status"] == "error":
        st.error("Falha de leitura do Supabase. Os chefes permaneceram inalterados.")
        st.stop()
    config = result["data"] if result["status"] == "found" else {}
    raw = config.get("bosses") if isinstance(config, dict) else None
    if raw:
        try:
            return {name: dict_to_boss(data) for name, data in raw.items()}
        except (KeyError, ValueError, TypeError) as exc:
            st.error(f"Dados de chefes inválidos; nenhuma configuração será substituída: {exc}")
            st.stop()
    defaults = build_default_bosses()
    fresh = dict(config) if isinstance(config, dict) else {}
    fresh["bosses"] = {name: boss_to_dict(boss) for name, boss in defaults.items()}
    if result["status"] == "found":
        ok = compare_and_set_app_state("boss_config", result["updated_at"], fresh)
    else:
        ok = create_app_state_if_missing("boss_config", fresh)
    if ok:
        return defaults
    # Another master may have created the library. Read it, never overwrite it.
    latest = fetch_app_state("boss_config")
    if latest["status"] == "found" and (latest["data"] or {}).get("bosses"):
        return {name: dict_to_boss(data) for name, data in latest["data"]["bosses"].items()}
    st.error("Não foi possível inicializar a biblioteca sem conflitos. Atualize a página.")
    st.stop()


def save_bosses(bosses: dict) -> bool:
    """Write only intended boss definitions while preserving scene and mob tokens."""
    raw = {name: boss_to_dict(boss) for name, boss in bosses.items()}
    result = fetch_app_state("boss_config")
    if result["status"] == "error":
        st.error("Não foi possível confirmar a versão da biblioteca. Nada foi sobrescrito.")
        return False
    config = dict(result["data"] or {})
    config["bosses"] = raw
    if result["status"] == "found":
        ok = compare_and_set_app_state("boss_config", result["updated_at"], config)
    else:
        ok = create_app_state_if_missing("boss_config", config)
    if not ok:
        st.error("Outra sessão alterou a biblioteca. Atualize antes de salvar.")
    return ok


# ============================================================
# ESTADO DA SESSÃO
# ============================================================

def init_session_state(bosses: dict):

    if "selected_boss" not in st.session_state:
        st.session_state.selected_boss = next(iter(bosses))

    if st.session_state.selected_boss not in bosses:
        st.session_state.selected_boss = next(iter(bosses))

    dict_fields = [
        "boss_hp", "turn_numbers", "histories",
        "current_turns", "statuses"
    ]

    for field in dict_fields:
        if field not in st.session_state or not isinstance(st.session_state[field], dict):
            st.session_state[field] = {}

    for name, boss in bosses.items():
        if name not in st.session_state.boss_hp:
            st.session_state.boss_hp[name] = boss.max_hp
        else:
            st.session_state.boss_hp[name] = min(
                st.session_state.boss_hp[name], boss.max_hp
            )
        st.session_state.turn_numbers.setdefault(name, 0)
        st.session_state.histories.setdefault(name, [])
        st.session_state.current_turns.setdefault(name, None)
        st.session_state.statuses.setdefault(name, [])

    # Remove entradas de bosses que não existem mais
    for field in dict_fields:
        for key in list(st.session_state[field].keys()):
            if key not in bosses:
                del st.session_state[field][key]

    if "manual_result" not in st.session_state:
        st.session_state.manual_result = None

    if "app_mode" not in st.session_state:
        st.session_state.app_mode = "combat"

    if "editor_target" not in st.session_state:
        st.session_state.editor_target = None

    if "editor_creating" not in st.session_state:
        st.session_state.editor_creating = False

    if "new_boss_counter" not in st.session_state:
        st.session_state.new_boss_counter = 0

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

    if "delete_target" not in st.session_state:
        st.session_state.delete_target = None


def rename_boss_state(old_name, new_name):
    """Migra HP/turnos/histórico/status de um nome de boss para outro."""

    for field in ["boss_hp", "turn_numbers", "histories", "current_turns", "statuses"]:
        state_dict = st.session_state[field]
        if old_name in state_dict:
            state_dict[new_name] = state_dict.pop(old_name)


def init_boss_state(name, max_hp, hp_atual):
    st.session_state.boss_hp[name] = hp_atual
    st.session_state.turn_numbers.setdefault(name, 0)
    st.session_state.histories.setdefault(name, [])
    st.session_state.current_turns.setdefault(name, None)
    st.session_state.statuses.setdefault(name, [])


def delete_boss_state(name):
    for field in ["boss_hp", "turn_numbers", "histories", "current_turns", "statuses"]:
        st.session_state[field].pop(name, None)


# ============================================================
# LÓGICA DE COMBATE
# ============================================================

def new_turn(boss: Boss):

    current_hp = st.session_state.boss_hp[boss.name]
    combo = boss.generate_combo(current_hp)

    results = [
        {"attack": attack, "result": attack.execute()}
        for attack in combo
    ]

    st.session_state.turn_numbers[boss.name] += 1

    turn_data = {
        "number": st.session_state.turn_numbers[boss.name],
        "results": results
    }

    st.session_state.current_turns[boss.name] = turn_data
    st.session_state.histories[boss.name].insert(0, turn_data)


def matrix_color(value):
    if value <= 16:
        return "matrix-green"
    if value <= 23:
        return "matrix-yellow"
    return "matrix-red"


def render_attack_result(attack: Attack, result: dict, number=None):
    kind = "Físico" if attack.type == "physical" else "Área"
    title = f"{number}. {attack.name}" if number is not None else attack.name
    critical = (
        f' · <span class="critical">Crítico ×{attack.crit_multiplier}</span>'
        if result["is_critical"] else ""
    )
    effect = ""
    if attack.type == "area" or attack.effect_dice_count or result["effect_value"]:
        effect = f'<div><dt>{escape(attack.effect_name)}</dt><dd>{int(result["effect_value"])}</dd></div>'
    dice = f"{attack.damage_dice_count}d{attack.damage_dice_sides}{attack.damage_bonus:+d}"
    st.markdown(
        f'<article class="boss-result">'
        f'<h4>{escape(title)} <span class="attack-kind">{kind}</span>{critical}</h4>'
        f'<dl><div><dt>Ataque</dt><dd>{int(result["attack_result"])}</dd></div>'
        f'<div><dt>Dano final</dt><dd>{int(result["final_damage"])}</dd></div>{effect}</dl>'
        f'<p class="roll-detail">d20 {int(result["natural_roll"])} ({attack.attack_bonus:+d})'
        f' · {dice} → {int(result["damage_result"])}</p></article>',
        unsafe_allow_html=True,
    )


def render_matrix(boss: Boss):
    headers = "".join(f'<th scope="col">{escape(label)}</th>' for label in MATRIX_COLUMNS)
    rows = []
    for attack in boss.attacks:
        values = "".join(
            f'<td class="{matrix_color(value)}">{value}</td>'
            for value in boss.get_matrix_row(attack.id)
        )
        rows.append(f'<tr><th scope="row">{attack.id}. {escape(attack.name)}</th>{values}</tr>')
    st.markdown(
        '<div class="boss-matrix"><table>'
        f'<thead><tr><th scope="col">Ataque</th>{headers}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>',
        unsafe_allow_html=True,
    )
    st.caption("10–16 · dificuldade menor  |  17–23 · média  |  24–30 · maior")


def reset_encounter(boss: Boss):
    state = st.session_state
    clear_encounter_history(boss.name)
    state.boss_hp[boss.name] = boss.max_hp
    state.statuses[boss.name] = []
    state.manual_result = None
    state.pop("encounter_history_turn", None)


def clear_encounter_history(name):
    state = st.session_state
    state.histories[name] = []
    state.current_turns[name] = None
    state.turn_numbers[name] = 0



def attack_option(attack):
    kind = "Físico" if attack.type == "physical" else "Área"
    return f"{attack.id}. {attack.name} · {kind}"


def render_combat_main(bosses: dict):
    state = st.session_state
    selected = st.selectbox(
        "Chefe em combate", list(bosses), index=list(bosses).index(state.selected_boss),
        key="combat_boss", width=460,
    )
    if selected != state.selected_boss:
        state.selected_boss = selected
        state.manual_result = None
        state.pop("encounter_history_turn", None)
    boss = bosses[selected]
    name = boss.name
    if state.pop(f"reset_controls_{name}", False):
        state.pop(f"combat_status_{name}", None)
        state.pop(f"combat_hp_{name}", None)

    overview, battle = st.columns([1, 1.8], gap="medium")
    with overview, st.container(border=True, key="boss-overview"):
        hp_key = f"combat_hp_{name}"
        if hp_key not in state:
            state[hp_key] = state.boss_hp[name]
        hp = st.number_input("HP atual", min_value=0, max_value=boss.max_hp,
                             step=1, key=hp_key)
        state.boss_hp[name] = hp
        st.progress(hp / boss.max_hp, text=f"{hp} / {boss.max_hp} HP")
        phase_number = boss.get_current_phase_index(hp) + 1
        phase = boss.ensure_phases()[phase_number - 1]
        st.markdown(f"**Fase {phase_number}**" + (f" · {phase.label}" if phase.label else ""))
        conditions = state.statuses[name]
        state.statuses[name] = st.multiselect(
            "Condições do chefe", list(dict.fromkeys(STATUS_OPTIONS + conditions)),
            default=conditions, key=f"combat_status_{name}",
        )
        with st.popover("Ataques da fase"):
            physical = [attack for attack in boss.get_physical_attacks() if attack.id in phase.physical_ids]
            area = [attack for attack in boss.get_area_attacks() if attack.id in phase.area_ids]
            st.markdown("**Físicos**")
            st.write(", ".join(attack.name for attack in physical) or "—")
            st.markdown("**Em área**")
            st.write(", ".join(attack.name for attack in area) or "—")
        with st.popover("Reiniciar combate"):
            st.caption("Restaure o HP máximo e apague os turnos e as condições deste chefe.")
            if st.button("Confirmar reinício", key=f"reset_{name}"):
                reset_encounter(boss)
                state[f"reset_controls_{name}"] = True
                finish_boss_run(bosses)
                st.rerun()

    with battle:
        with st.container(border=True, key="boss-actions"):
            roll_col, manual_col = st.columns([1, 1.5], vertical_alignment="bottom")
            with roll_col:
                if st.button("Rolar turno",
                             type="primary", use_container_width=True, disabled=not boss.attacks):
                    new_turn(boss)
                    state["combat_view"] = "Turno"
            with manual_col, st.popover("Ataque manual", use_container_width=True):
                choices = {attack.id: attack for attack in boss.attacks}
                chosen = st.selectbox("Ataque", list(choices), format_func=lambda key: attack_option(choices[key]),
                                      key=f"combat_attack_{name}")
                if st.button("Rolar ataque", disabled=chosen is None, key="roll_manual"):
                    attack = choices[chosen]
                    state.manual_result = {"attack": attack, "result": attack.execute()}
                    state["combat_view"] = "Turno"

        view = st.radio("Visualização", ["Turno", "Matriz de reações", "Histórico"],
                        horizontal=True, label_visibility="collapsed", key="combat_view")
        if view == "Matriz de reações":
            render_matrix(boss)
        elif view == "Histórico":
            history = state.histories[name]
            if not history:
                st.caption("Nenhum turno registrado.")
                return
            turns = {turn["number"]: turn for turn in history}
            turn_number = st.selectbox("Turno registrado", list(turns), key="encounter_history_turn")
            with st.popover("Limpar histórico"):
                st.caption("Apague os turnos registrados e reinicie a contagem.")
                if st.button("Confirmar limpeza"):
                    clear_encounter_history(name)
                    finish_boss_run(bosses)
                    st.rerun()
            render_turn(turns[turn_number])
        else:
            manual = state.manual_result
            if manual:
                with st.container(border=True):
                    heading, close = st.columns([3, 1], vertical_alignment="center")
                    heading.markdown("**Ataque manual**")
                    if close.button("Dispensar", key="dismiss_manual"):
                        state.manual_result = None
                    else:
                        render_attack_result(manual["attack"], manual["result"])
            turn = state.current_turns[name]
            if turn:
                st.subheader(f"Turno {turn['number']}")
                render_turn(turn)
            elif not manual:
                st.caption("Inicie um turno para sortear o combo do chefe.")


def render_turn(turn):
    if not turn["results"]:
        st.caption("Este turno ficou sem ataques disponíveis na biblioteca.")
        return
    with st.container(border=True):
        for number, item in enumerate(turn["results"], start=1):
            render_attack_result(item["attack"], item["result"], number)


def default_attack_template(i):
    return Attack(
        id=i,
        name=f"Ataque {i}",
        type="physical" if i <= 5 else "area",
        attack_bonus=5,
        crit_min=18,
        crit_max=20,
        crit_multiplier=2,
        damage_dice_count=6,
        damage_dice_sides=6,
        damage_bonus=2,
        effect_name="Nenhum",
        effect_dice_count=2 if i <= 5 else None,
        effect_dice_sides=4 if i <= 5 else None,
    )


def default_matrix_template():
    return {str(i): [15, 15, 15, 15, 15] for i in range(1, 11)}


def editor_key_base():
    if st.session_state.editor_creating:
        return f"NEW{st.session_state.new_boss_counter}"
    return f"EX_{st.session_state.editor_target}"


def render_library_controls(bosses: dict):
    state = st.session_state
    names = list(bosses)
    selector, add, actions = st.columns([2, 1, 1], vertical_alignment="bottom")
    if not state.editor_creating:
        if state.editor_target not in bosses:
            state.editor_target = state.selected_boss
        chosen = selector.selectbox("Chefe na biblioteca", names, index=names.index(state.editor_target),
                                    key="editor_target_select")
        if chosen != state.editor_target:
            state.editor_target = chosen
            state.confirm_delete = False
    if add.button("Novo chefe", use_container_width=True, disabled=state.editor_creating):
        state.editor_creating = True
        state.editor_target = None
        state.new_boss_counter += 1
        state.confirm_delete = False
        st.rerun()
    if state.editor_creating:
        if actions.button("Voltar à lista", use_container_width=True):
            state.editor_creating = False
            state.editor_target = state.selected_boss
            st.rerun()
    else:
        with actions.popover("Ações da biblioteca", use_container_width=True):
            if st.button("Duplicar chefe", use_container_width=True):
                base_name = state.editor_target
                proposed = f"{base_name} (cópia)"
                suffix = 2
                while proposed in bosses:
                    proposed = f"{base_name} (cópia {suffix})"
                    suffix += 1
                cloned = dict_to_boss(boss_to_dict(bosses[base_name]))
                cloned.name = proposed
                bosses[proposed] = cloned
                if save_bosses(bosses):
                    init_boss_state(proposed, cloned.max_hp, cloned.max_hp)
                    state.editor_target = proposed
                    state.selected_boss = proposed
                    state.manual_result = None
                    state.pop("editor_target_select", None)
                    finish_boss_run(bosses)
                    st.rerun()
                bosses.pop(proposed, None)
            if st.button("Excluir chefe", disabled=len(bosses) <= 1, use_container_width=True):
                state.delete_target = state.editor_target
                state.confirm_delete = True
                st.rerun()


def render_delete_confirmation(bosses: dict):

    target = st.session_state.delete_target

    st.subheader("Excluir chefe")
    st.warning(
        f"Tem certeza que deseja apagar **{target}**? "
        f"Essa ação não pode ser desfeita."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Confirmar exclusão", type="primary", use_container_width=True):

            removed = bosses.pop(target, None)
            if not save_bosses(bosses):
                if removed is not None:
                    bosses[target] = removed
                st.error("Não foi possível confirmar a exclusão. Nenhum boss foi apagado do banco.")
                st.stop()
            delete_boss_state(target)

            remaining = list(bosses.keys())
            st.session_state.selected_boss = remaining[0] if remaining else None
            st.session_state.editor_target = remaining[0] if remaining else None
            st.session_state.confirm_delete = False
            st.session_state.delete_target = None
            st.session_state.app_mode = "combat"

            st.session_state.manual_result = None
            finish_boss_run(bosses)
            st.rerun()

    with col2:
        if st.button("❌ Cancelar", use_container_width=True):
            st.session_state.confirm_delete = False
            st.session_state.delete_target = None
            st.rerun()


def render_boss_editor_form(bosses: dict):

    creating = st.session_state.editor_creating
    editor_target = st.session_state.editor_target

    if creating:
        source_boss = None
        default_name = ""
        default_max_hp = 50
        default_hp = 50
        default_matrix = default_matrix_template()
        template_attacks = [default_attack_template(i) for i in range(1, 11)]
        default_phases = default_phases_for_attacks(
            [a for a in template_attacks if a.type == "physical"],
            [a for a in template_attacks if a.type == "area"],
        )
    else:
        if editor_target not in bosses:
            st.info("Selecione um boss na barra lateral para editar.")
            return
        source_boss = bosses[editor_target]
        default_name = source_boss.name
        default_max_hp = source_boss.max_hp
        default_hp = st.session_state.boss_hp.get(editor_target, source_boss.max_hp)
        default_matrix = source_boss.action_matrix
        default_phases = source_boss.ensure_phases()

    base = editor_key_base()

    title = "Novo chefe" if creating else "Ficha do chefe"
    st.subheader(title)

    tab_dados, tab_ataques, tab_fases, tab_matriz = st.tabs(
        ["Dados", "Ataques", "Fases", "Matriz de reações"]
    )

    # ---------------------------------------------------
    # DADOS DO BOSS
    # ---------------------------------------------------

    with tab_dados:

        details, maximum, health = st.columns([2, 1, 1])
        boss_name = details.text_input("Nome", value=default_name, key=f"{base}_boss_name")
        max_hp = maximum.number_input("HP máximo", min_value=1, max_value=100000,
                                      value=int(default_max_hp), step=1, key=f"{base}_max_hp")
        hp_atual = health.number_input("HP atual", min_value=0, max_value=int(max_hp),
                                       value=min(int(default_hp), int(max_hp)), step=1,
                                       key=f"{base}_hp_atual")

    # ---------------------------------------------------
    # ATAQUES
    # ---------------------------------------------------

    attack_values = []

    with tab_ataques:

        attack_count = st.number_input("Quantidade de ataques", 1, 20,
            value=len(source_boss.attacks) if source_boss else 10,
            key=f"{base}_attack_count",
            help="Pode misturar ataques físicos e de área em qualquer quantidade.")

        for i in range(1, int(attack_count) + 1):

            if source_boss and i <= len(source_boss.attacks):
                template = source_boss.attacks[i - 1]
            else:
                template = default_attack_template(i)

            with st.expander(f"{i}. {st.session_state.get(f'{base}_atk{i}_name') or template.name}"):


                a_key = f"{base}_atk{i}"

                name = st.text_input("Nome do ataque", value=template.name, key=f"{a_key}_name")

                type_options = ["physical", "area"]
                type_labels = {"physical": "🗡️ Físico", "area": "🔥 Área"}

                atype = st.selectbox(
                    "Tipo",
                    type_options,
                    index=type_options.index(template.type),
                    format_func=lambda v: type_labels[v],
                    key=f"{a_key}_type"
                )

                col1, col2, col3 = st.columns(3)
                with col1:
                    attack_bonus = st.number_input(
                        "Bônus de ataque", value=int(template.attack_bonus),
                        step=1, key=f"{a_key}_bonus"
                    )
                with col2:
                    crit_min = st.number_input(
                        "Crítico mín.", min_value=1, max_value=20,
                        value=int(template.crit_min), step=1, key=f"{a_key}_critmin"
                    )
                with col3:
                    crit_max = st.number_input(
                        "Crítico máx.", min_value=1, max_value=20,
                        value=int(template.crit_max), step=1, key=f"{a_key}_critmax"
                    )

                crit_multiplier = st.number_input(
                    "Multiplicador de crítico", min_value=1, max_value=10,
                    value=int(template.crit_multiplier), step=1, key=f"{a_key}_critmult"
                )

                col4, col5, col6 = st.columns(3)

                with col4:
                    damage_dice_count = st.number_input(
                        "Qtd. dados de dano", min_value=1, max_value=30,
                        value=int(template.damage_dice_count), step=1, key=f"{a_key}_dcount"
                    )
                with col5:
                    dmg_options = sorted(set(DICE_OPTIONS + [template.damage_dice_sides]))
                    damage_dice_sides = st.selectbox(
                        "Tipo de dado de dano",
                        dmg_options,
                        index=dmg_options.index(template.damage_dice_sides),
                        format_func=lambda v: f"d{v}",
                        key=f"{a_key}_dsides"
                    )
                with col6:
                    damage_bonus = st.number_input(
                        "Bônus de dano", min_value=0, max_value=100,
                        value=int(template.damage_bonus), step=1, key=f"{a_key}_dbonus"
                    )

                effect_name = st.text_input(
                    "Nome do efeito (use 'Nenhum' se não houver)",
                    value=template.effect_name,
                    key=f"{a_key}_effname"
                )

                effect_dice_count = None
                effect_dice_sides = None

                if atype == "physical":

                    has_effect = st.checkbox(
                        "Efeito rola dados",
                        value=template.effect_dice_count is not None,
                        key=f"{a_key}_haseffect"
                    )

                    if has_effect:
                        col7, col8 = st.columns(2)
                        with col7:
                            effect_dice_count = st.number_input(
                                "Qtd. dados do efeito", min_value=1, max_value=30,
                                value=int(template.effect_dice_count or 1),
                                step=1, key=f"{a_key}_ecount"
                            )
                        with col8:
                            eff_options = sorted(set(
                                DICE_OPTIONS + [template.effect_dice_sides or 4]
                            ))
                            effect_dice_sides = st.selectbox(
                                "Tipo de dado do efeito",
                                eff_options,
                                index=eff_options.index(template.effect_dice_sides or 4),
                                format_func=lambda v: f"d{v}",
                                key=f"{a_key}_esides"
                            )
                else:
                    st.caption("Ataques em área causam efeito igual à metade do dano final (automático).")

                attack_values.append(Attack(
                    id=i,
                    name=name.strip() or f"Ataque {i}",
                    type=atype,
                    attack_bonus=int(attack_bonus),
                    crit_min=int(crit_min),
                    crit_max=int(crit_max),
                    crit_multiplier=int(crit_multiplier),
                    damage_dice_count=int(damage_dice_count),
                    damage_dice_sides=int(damage_dice_sides),
                    damage_bonus=int(damage_bonus),
                    effect_name=effect_name.strip() or "Nenhum",
                    effect_dice_count=int(effect_dice_count) if effect_dice_count else None,
                    effect_dice_sides=int(effect_dice_sides) if effect_dice_sides else None,
                ))

    # ---------------------------------------------------
    # FASES
    # ---------------------------------------------------

    phase_values = []

    with tab_fases:

        st.caption(
            "Defina as 3 fases do boss com base na porcentagem de HP atual "
            "(HP atual / HP máximo × 100) e quais ataques ficam desbloqueados em cada uma."
        )

        physical_in_editor = [a for a in attack_values if a.type == "physical"]
        area_in_editor = [a for a in attack_values if a.type == "area"]

        phase_defaults = list(default_phases)
        while len(phase_defaults) < 3:
            phase_defaults.append(Phase(hp_max=0, hp_min=0))

        phase_names = ["Fase 1", "Fase 2", "Fase 3"]

        for idx in range(3):

            phase_default = phase_defaults[idx]

            st.markdown(f"**{phase_names[idx]}**")

            col_max, col_min, col_label = st.columns([1, 1, 2])

            with col_max:
                hp_max = st.number_input(
                    "HP máx. (%)",
                    min_value=0, max_value=100,
                    value=int(phase_default.hp_max),
                    step=1,
                    key=f"{base}_phase{idx}_hpmax"
                )
            with col_min:
                hp_min = st.number_input(
                    "HP mín. (%)",
                    min_value=0, max_value=100,
                    value=int(phase_default.hp_min),
                    step=1,
                    key=f"{base}_phase{idx}_hpmin"
                )
            with col_label:
                phase_label = st.text_input(
                    "Rótulo (opcional, ex: ENFURECIDO, FINAL)",
                    value=phase_default.label,
                    key=f"{base}_phase{idx}_label"
                )

            col_phys, col_area = st.columns(2)

            physical_names = {atk.id: atk.name for atk in physical_in_editor}
            area_names = {atk.id: atk.name for atk in area_in_editor}
            selected_physical = col_phys.multiselect(
                "Ataques físicos", list(physical_names),
                default=[atk_id for atk_id in phase_default.physical_ids if atk_id in physical_names],
                format_func=physical_names.__getitem__, key=f"{base}_phase{idx}_physical"
            )
            selected_area = col_area.multiselect(
                "Ataques em área", list(area_names),
                default=[atk_id for atk_id in phase_default.area_ids if atk_id in area_names],
                format_func=area_names.__getitem__, key=f"{base}_phase{idx}_area"
            )

            phase_values.append(Phase(
                hp_max=int(hp_max),
                hp_min=int(hp_min),
                physical_ids=selected_physical,
                area_ids=selected_area,
                label=phase_label.strip(),
            ))

            st.markdown("---")

    # ---------------------------------------------------
    # MATRIZ
    # ---------------------------------------------------

    matrix_values = {}

    with tab_matriz:

        st.caption(f"{len(attack_values)} ataques × 5 defesas. Verde 10–16, amarelo 17–23, vermelho 24–30.")

        header_cols = st.columns([2.2, 1, 1, 1, 1, 1])
        for col, header in zip(header_cols, ["Ataque"] + MATRIX_COLUMNS):
            with col:
                st.markdown(f"**{header}**")

        for atk in attack_values:

            row = default_matrix.get(str(atk.id), [15, 15, 15, 15, 15])
            row_cols = st.columns([2.2, 1, 1, 1, 1, 1])

            with row_cols[0]:
                st.write(f"{atk.id}. {atk.name}")

            row_values = []
            for j, (col, col_name) in enumerate(zip(row_cols[1:], MATRIX_COLUMNS)):
                with col:
                    val = st.number_input(
                        col_name,
                        min_value=1,
                        max_value=30,
                        value=int(row[j]) if j < len(row) else 15,
                        step=1,
                        key=f"{base}_matrix_{atk.id}_{j}",
                        label_visibility="collapsed"
                    )
                    row_values.append(int(val))

            matrix_values[str(atk.id)] = row_values

    # ---------------------------------------------------
    # Salvar ficha
    # ---------------------------------------------------
    save_clicked = st.button("Salvar chefe", type="primary")

    if save_clicked:

        final_name = boss_name.strip()

        if not final_name:
            st.error("O nome do boss não pode ficar em branco.")
            return

        name_conflict = (
            final_name in bosses
            and (creating or final_name != editor_target)
        )

        if name_conflict:
            st.error(f"Já existe um boss chamado '{final_name}'. Escolha outro nome.")
            return

        new_boss = Boss(
            name=final_name,
            max_hp=int(max_hp),
            attacks=attack_values,
            action_matrix=matrix_values,
            phases=phase_values,
        )

        updated = dict(bosses)
        if not creating and editor_target != final_name:
            del updated[editor_target]
        updated[final_name] = new_boss
        if not save_bosses(updated):
            return
        bosses.update(updated)
        if creating:
            init_boss_state(final_name, int(max_hp), int(hp_atual))
        else:
            if editor_target != final_name:
                del bosses[editor_target]
                rename_boss_state(editor_target, final_name)
            st.session_state.boss_hp[final_name] = int(hp_atual)

        st.session_state.selected_boss = final_name
        st.session_state.editor_target = final_name
        st.session_state.editor_creating = False
        st.session_state.app_mode = "combat"

        st.session_state.manual_result = None
        finish_boss_run(bosses)
        st.rerun()



# ============================================================
# IMPORTAÇÃO DE BOSS VIA JSON
# ============================================================

def _norm_type(value) -> str:
    value = str(value or "").strip().lower()
    if value in ("physical", "fisico", "físico", "fisica", "física"):
        return "physical"
    if value in ("area", "área"):
        return "area"
    raise ValueError(
        f"Tipo de ataque inválido: '{value}'. Use 'physical' ou 'area'."
    )


def boss_from_import_json(data: dict) -> Boss:
    """Valida e converte um objeto JSON em Boss sem alterar o estado do app."""

    if not isinstance(data, dict):
        raise ValueError("O JSON do boss precisa ser um objeto.")

    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("Falta o campo 'name'.")

    try:
        max_hp = int(data["max_hp"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("Falta 'max_hp' ou ele não é um número.")
    if max_hp < 1:
        raise ValueError("'max_hp' precisa ser maior que zero.")

    raw_attacks = data.get("attacks")
    if not isinstance(raw_attacks, list) or not (1 <= len(raw_attacks) <= 20):
        received = len(raw_attacks) if isinstance(raw_attacks, list) else 0
        raise ValueError(
            f"'attacks' deve conter de 1 a 20 ataques (recebidos: {received})."
        )

    attacks = []
    for index, raw in enumerate(raw_attacks, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Ataque {index} não é um objeto JSON.")

        attack_data = dict(raw)
        attack_data["id"] = index

        try:
            attack_data["type"] = _norm_type(attack_data.get("type"))
            attack_data.setdefault("name", f"Ataque {index}")
            attack_data.setdefault("attack_bonus", 0)
            attack_data.setdefault("crit_min", 20)
            attack_data.setdefault("crit_max", 20)
            attack_data.setdefault("crit_multiplier", 2)
            attack_data.setdefault("damage_bonus", 0)
            attack_data.setdefault("effect_name", "Nenhum")

            if "damage_dice_count" not in attack_data:
                raise ValueError("Falta 'damage_dice_count'.")
            if "damage_dice_sides" not in attack_data:
                raise ValueError("Falta 'damage_dice_sides'.")

            if attack_data["type"] == "area":
                attack_data["effect_dice_count"] = None
                attack_data["effect_dice_sides"] = None

            attack = dict_to_attack(attack_data)

            if not attack.name.strip():
                raise ValueError("O ataque precisa ter um nome.")
            if attack.damage_dice_count < 1 or attack.damage_dice_sides < 2:
                raise ValueError("Os dados de dano precisam ser positivos (ex.: 2d6).")
            if attack.crit_multiplier < 1:
                raise ValueError("'crit_multiplier' precisa ser pelo menos 1.")
            if not (1 <= attack.crit_min <= attack.crit_max <= 20):
                raise ValueError("O intervalo crítico precisa respeitar 1 ≤ crit_min ≤ crit_max ≤ 20.")

            if attack.type == "physical":
                if attack.effect_dice_count is not None and attack.effect_dice_count < 1:
                    raise ValueError("'effect_dice_count' precisa ser positivo.")
                if attack.effect_dice_sides is not None and attack.effect_dice_sides < 2:
                    raise ValueError("'effect_dice_sides' precisa ser pelo menos 2.")

        except (ValueError, TypeError, KeyError) as error:
            attack_name = raw.get("name", "?")
            raise ValueError(f"Ataque {index} ('{attack_name}'): {error}") from error

        attacks.append(attack)

    # Os chefes antigos com 5+5 continuam válidos. Novos inimigos podem ter
    # apenas os ataques necessários, sem exigir pares físicos/em área.

    # ---------------- Matriz de reações ----------------
    raw_matrix = data.get("action_matrix") or {}
    matrix = {str(attack.id): [15, 15, 15, 15, 15] for attack in attacks}
    name_to_id = {attack.name.strip().casefold(): attack.id for attack in attacks}

    def clean_matrix_row(row, label):
        if not isinstance(row, list) or len(row) != 5:
            raise ValueError(
                f"Matriz '{label}' precisa ter 5 valores na ordem "
                "Parry, Rolagem, Bloquear, Pular e Correr."
            )
        try:
            values = [int(value) for value in row]
        except (TypeError, ValueError):
            raise ValueError(f"Matriz '{label}': todos os valores precisam ser números.")
        if any(value < 10 or value > 30 for value in values):
            raise ValueError(f"Matriz '{label}': os valores precisam estar entre 10 e 30.")
        return values

    if isinstance(raw_matrix, list):
        if len(raw_matrix) > len(attacks):
            raise ValueError("'action_matrix' não pode ter mais linhas que ataques.")
        for index, row in enumerate(raw_matrix, start=1):
            matrix[str(index)] = clean_matrix_row(row, index)
    elif isinstance(raw_matrix, dict):
        for key, row in raw_matrix.items():
            normalized_key = str(key).strip()
            if normalized_key in matrix:
                attack_id = normalized_key
            elif normalized_key.casefold() in name_to_id:
                attack_id = str(name_to_id[normalized_key.casefold()])
            else:
                raise ValueError(
                    f"Matriz: '{key}' não corresponde a um ID de 1 a 10 "
                    "ou ao nome exato de um ataque."
                )
            matrix[attack_id] = clean_matrix_row(row, key)
    else:
        raise ValueError("'action_matrix' precisa ser um objeto ou uma lista.")

    # ---------------- Fases ----------------
    phases_data = data.get("phases")
    if phases_data:
        if not isinstance(phases_data, list) or len(phases_data) != 3:
            raise ValueError(
                "'phases' precisa conter exatamente 3 fases. "
                "Também é possível omitir o campo para usar as fases padrão."
            )

        phases = []
        valid_physical_ids = {
            attack.id for attack in attacks if attack.type == "physical"
        }
        valid_area_ids = {
            attack.id for attack in attacks if attack.type == "area"
        }

        for index, phase_data in enumerate(phases_data, start=1):
            if not isinstance(phase_data, dict):
                raise ValueError(f"Fase {index} precisa ser um objeto JSON.")
            try:
                phase = dict_to_phase(phase_data)
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"Fase {index}: dados inválidos: {error}") from error

            if not (0 <= phase.hp_min <= phase.hp_max <= 100):
                raise ValueError(
                    f"Fase {index}: use limites entre 0 e 100, "
                    "com hp_min menor ou igual a hp_max."
                )

            invalid_physical = set(phase.physical_ids) - valid_physical_ids
            invalid_area = set(phase.area_ids) - valid_area_ids
            if invalid_physical or invalid_area:
                raise ValueError(
                    f"Fase {index}: IDs físicos/área incompatíveis com os tipos dos ataques."
                )

            phases.append(phase)
    else:
        phases = default_phases_for_attacks(
            [attack for attack in attacks if attack.type == "physical"],
            [attack for attack in attacks if attack.type == "area"],
        )

    return Boss(
        name=name,
        max_hp=max_hp,
        attacks=attacks,
        action_matrix=matrix,
        phases=phases,
    )


def render_json_import(bosses: dict):
    with st.expander("Importar JSON", expanded=False):
        st.caption(
            "Cole um JSON ou envie um arquivo .json. É possível importar um boss "
            "ou vários no formato {\"Nome\": {...}, \"Outro\": {...}}."
        )

        uploaded_file = st.file_uploader(
            "Arquivo .json", type=["json"], key="import_json_file"
        )
        pasted_json = st.text_area(
            "Ou cole o JSON aqui", height=220, key="import_json_text"
        )
        overwrite = st.checkbox(
            "Sobrescrever se já existir boss com o mesmo nome",
            value=False,
            key="import_json_overwrite",
        )

        if not st.button("📥 Importar", type="primary", key="import_json_btn"):
            return

        try:
            raw_text = (
                uploaded_file.getvalue().decode("utf-8-sig")
                if uploaded_file is not None
                else pasted_json
            )
        except UnicodeDecodeError:
            st.error("O arquivo precisa estar codificado em UTF-8.")
            return

        if not raw_text or not raw_text.strip():
            st.error("Cole um JSON ou envie um arquivo.")
            return

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as error:
            st.error(f"JSON inválido: {error}")
            return

        if isinstance(parsed, list):
            candidates = parsed
        elif isinstance(parsed, dict) and "attacks" in parsed:
            candidates = [parsed]
        elif isinstance(parsed, dict):
            candidates = []
            for boss_name, boss_data in parsed.items():
                if not isinstance(boss_data, dict):
                    st.error(f"Os dados de '{boss_name}' precisam ser um objeto JSON.")
                    return
                candidate = dict(boss_data)
                candidate.setdefault("name", boss_name)
                candidates.append(candidate)
        else:
            st.error("Formato não reconhecido. Envie um boss, uma lista ou um objeto de bosses.")
            return

        if not candidates:
            st.error("Nenhum boss foi encontrado no JSON.")
            return

        imported = []
        seen_names = set()

        # Valida todos antes de salvar qualquer um: importação é atômica.
        for candidate in candidates:
            try:
                new_boss = boss_from_import_json(candidate)
            except ValueError as error:
                candidate_name = (
                    candidate.get("name", "?")
                    if isinstance(candidate, dict)
                    else "?"
                )
                st.error(f"Erro em '{candidate_name}': {error}")
                return

            normalized_name = new_boss.name.casefold()
            if normalized_name in seen_names:
                st.error(f"O JSON contém mais de um boss chamado '{new_boss.name}'.")
                return
            seen_names.add(normalized_name)

            existing_name = next(
                (name for name in bosses if name.casefold() == normalized_name),
                None,
            )
            if existing_name is not None and not overwrite:
                st.error(
                    f"Já existe um boss chamado '{existing_name}'. "
                    "Marque a opção de sobrescrever ou altere o nome no JSON."
                )
                return

            imported.append((new_boss, existing_name))

        updated = dict(bosses)
        for new_boss, existing_name in imported:
            if existing_name is not None and existing_name != new_boss.name:
                del updated[existing_name]
            updated[new_boss.name] = new_boss
        if not save_bosses(updated):
            return

        for new_boss, existing_name in imported:
            if existing_name is not None:
                if existing_name != new_boss.name:
                    del bosses[existing_name]
                    rename_boss_state(existing_name, new_boss.name)

                # Remove valores antigos dos widgets do editor.
                old_prefix = f"EX_{existing_name}_"
                for key in list(st.session_state.keys()):
                    if isinstance(key, str) and key.startswith(old_prefix):
                        del st.session_state[key]

                current_hp = st.session_state.boss_hp.get(
                    new_boss.name, new_boss.max_hp
                )
                st.session_state.boss_hp[new_boss.name] = min(
                    max(0, int(current_hp)), new_boss.max_hp
                )
            else:
                init_boss_state(
                    new_boss.name, new_boss.max_hp, new_boss.max_hp
                )

            bosses[new_boss.name] = new_boss

        last_imported_name = imported[-1][0].name
        st.session_state.selected_boss = last_imported_name
        st.session_state.editor_target = last_imported_name
        st.session_state.editor_creating = False
        st.session_state.confirm_delete = False

        st.session_state.manual_result = None
        st.session_state.pop("editor_target_select", None)
        finish_boss_run(bosses)
        st.rerun()


def render_editor_main(bosses: dict):

    if st.session_state.confirm_delete:
        render_delete_confirmation(bosses)
    else:
        render_json_import(bosses)
        render_boss_editor_form(bosses)


def render_shared_display_controls():
    record = fetch_app_state("boss_config")
    if record["status"] != "found":
        st.error("Não foi possível carregar a cena publicada.")
        return
    config = dict(record["data"])
    display = dict(config.get("display") or {})
    name = st.session_state.selected_boss
    image = (display.get("boss_images") or {}).get(name)
    scene, tokens = st.columns([1.4, 1], gap="medium")
    with scene, st.container(border=True):
        st.subheader("Exibição no painel")
        st.caption(f"Chefe selecionado · {name}")
        if image:
            st.image(image, width=160)
        with st.form("publish_boss_scene"):
            mode = st.radio("Modo", ["Chefe", "Cena narrativa"], horizontal=True,
                            index=0 if display.get("mode", "Chefe") == "Chefe" else 1)
            scene_name = st.text_input("Nome da cena", value=display.get("scene_name", "Cena atual"))
            show_scene = st.checkbox("Exibir imagem da cena", value=display.get("show_scene", True))
            portrait = st.file_uploader("Retrato deste chefe", type=["png", "jpg", "jpeg", "webp"],
                                        key=f"scene_portrait_{name}")
            if st.form_submit_button("Publicar no painel", type="primary"):
                if portrait:
                    from uuid import uuid4
                    suffix = portrait.name.rsplit(".", 1)[-1].lower()
                    url = upload_asset(f"bosses/portraits/{uuid4().hex}.{suffix}",
                                       portrait.getvalue(), portrait.type)
                    if not url:
                        st.error("Não foi possível enviar o retrato.")
                        return
                    display["boss_images"] = {**(display.get("boss_images") or {}), name: url}
                display.update(mode=mode, scene_name=scene_name, show_scene=show_scene)
                config["display"] = display
                if compare_and_set_app_state("boss_config", record["updated_at"], config):
                    st.session_state["_boss_display_changed"] = True
                else:
                    st.error("A configuração mudou em outra sessão. Tente publicar novamente.")

    with tokens, st.container(border=True):
        st.subheader("Tokens de inimigos")
        slot = st.selectbox("Token", range(1, 6), format_func=lambda n: f"Mob {n}")
        token_id = f"mob_{slot}"
        mob_tokens = dict(config.get("mob_tokens") or {})
        if mob_tokens.get(token_id):
            st.image(mob_tokens[token_id], width=88)
        file = st.file_uploader("Imagem do token", type=["png", "webp", "jpg", "jpeg"],
                                key=f"mob_token_{slot}")
        if st.button("Publicar token", disabled=file is None):
            from image_manager import prepare_image
            from uuid import uuid4
            try:
                data = prepare_image(file.getvalue(), "token")
            except ValueError as exc:
                st.error(str(exc))
                return
            url = upload_asset(f"bosses/tokens/{token_id}_{uuid4().hex}.webp", data, "image/webp")
            if not url:
                st.error("Não foi possível enviar o token.")
                return
            mob_tokens[token_id] = url
            config["mob_tokens"] = mob_tokens
            if compare_and_set_app_state("boss_config", record["updated_at"], config):
                st.success(f"Mob {slot} publicado no mapa.")
            else:
                st.error("A configuração mudou em outra sessão. Tente publicar novamente.")


def publish_current_boss(bosses: dict):
    name = st.session_state.selected_boss
    boss = bosses[name]
    config_record = fetch_app_state("boss_config")
    current_record = fetch_app_state("table_display")
    if config_record["status"] != "found" or current_record["status"] == "error":
        return False

    display = config_record["data"].get("display") or {}
    previous = current_record["data"] or {}
    hp = st.session_state.boss_hp[name]
    values = {
        "mode": display.get("mode", "Chefe"),
        "scene_name": display.get("scene_name", "Cena atual"),
        "show_scene": display.get("show_scene", True),
        "scene_image_url": previous.get("scene_image_url", display.get("scene_image_url", "")),
        "boss_name": name,
        "boss_image_url": (display.get("boss_images") or {}).get(name, ""),
        "boss_hp": max(0, min(int(hp), int(boss.max_hp))),
        "boss_max_hp": int(boss.max_hp),
    }
    if all(previous.get(key) == value for key, value in values.items()):
        return True
    published = {**previous, **values, "updated_at": datetime.now(timezone.utc).isoformat()}
    if current_record["status"] == "missing":
        return create_app_state_if_missing("table_display", published)
    return compare_and_set_app_state("table_display", current_record["updated_at"], published)


def finish_boss_run(bosses):
    state = st.session_state
    if persist_runtime(bosses, st.session_state):
        state["_boss_display_changed"] = True
    if state.get("_boss_runtime_conflict"):
        st.error("Outra sessão modificou o combate. Recarregue a página para buscar a versão atual.")
    elif state.get("_boss_display_changed") and publish_current_boss(bosses):
        state.pop("_boss_display_changed", None)
        if state.app_mode == "scene":
            st.success("Exibição atualizada no painel.")


def main():
    bosses = load_bosses()
    init_session_state(bosses)
    hydrate_runtime(bosses, st.session_state)
    state = st.session_state

    st.title("Simulador de chefe")
    navigation = st.columns(3, gap="small")
    for col, (label, mode) in zip(navigation, (("Combate", "combat"), ("Biblioteca", "editor"), ("Cena", "scene"))):
        if col.button(label, key=f"boss_nav_{mode}", use_container_width=True,
                      type="primary" if state.app_mode == mode else "secondary"):
            if state.app_mode != mode:
                state.app_mode = mode
                if mode == "editor":
                    state.editor_target = state.selected_boss
                    state.editor_creating = False
                    state.confirm_delete = False
                st.rerun()

    if state.app_mode == "editor":
        render_library_controls(bosses)
        render_editor_main(bosses)
    elif state.app_mode == "scene":
        render_shared_display_controls()
    else:
        render_combat_main(bosses)

    finish_boss_run(bosses)


if __name__ == "__main__":
    main()
