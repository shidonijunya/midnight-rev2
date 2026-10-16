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
    border-radius: 15px;
    transition: width 0.3s ease;
}

.attack-card {
    border: 1px solid #333;
    border-radius: 12px;
    padding: 15px 20px;
    margin: 10px 0;
    background: rgba(255,255,255,0.025);
}

.attack-title {
    font-size: 1.35rem;
    font-weight: 700;
    margin-bottom: 2px;
}

.attack-type {
    font-size: 0.75rem;
    color: #999;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.red-stat {
    border: 2px solid #c62828;
    border-radius: 10px;
    padding: 10px 8px 12px 8px;
    text-align: center;
    background: rgba(180, 20, 20, 0.08);
    height: 100%;
    box-sizing: border-box;
}

.red-stat-label {
    color: #ff5252;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.red-stat-value {
    color: #ff5252;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 2rem;
    font-weight: 800;
    margin-top: 2px;
}

.critical {
    border: 2px solid #ff4b4b;
    border-radius: 10px;
    padding: 10px 15px;
    margin: 10px 0;
    text-align: center;
    font-size: 1.15rem;
    font-weight: 800;
    background: rgba(255, 75, 75, 0.08);
    color: #ff5252;
}

.combo-card {
    border: 1px solid #333;
    border-radius: 10px;
    padding: 12px 16px;
    margin: 5px 0;
    background: rgba(255,255,255,0.02);
    text-align: center;
}

.table-title {
    text-align: center;
    font-size: 1.5rem;
    font-weight: 800;
    margin-bottom: 5px;
}

.table-subtitle {
    text-align: center;
    color: #999;
    margin-bottom: 15px;
}

.matrix-header {
    font-weight: 800;
    text-align: center;
    padding: 8px 3px;
    border-bottom: 2px solid #555;
    font-size: 0.85rem;
}

.matrix-attack {
    font-weight: 700;
    padding: 8px 5px;
    border-bottom: 1px solid #333;
    font-size: 0.82rem;
}

.matrix-value {
    text-align: center;
    font-weight: 800;
    padding: 8px 3px;
    border-bottom: 1px solid #333;
    font-size: 1rem;
}

.matrix-green { color: #4caf50; }
.matrix-yellow { color: #ffc107; }
.matrix-red { color: #ff5252; }

.status-box {
    border: 1px solid #555;
    border-radius: 8px;
    padding: 7px 10px;
    margin: 5px 0;
    background: rgba(255,255,255,0.03);
    text-align: center;
    font-weight: 700;
}

.manual-result {
    border: 1px solid #555;
    border-radius: 10px;
    padding: 12px;
    margin-top: 10px;
    background: rgba(255,255,255,0.025);
}

.editor-title {
    font-size: 1.6rem;
    font-weight: 800;
    margin-top: 15px;
    margin-bottom: 10px;
}

.phase-badge {
    text-align: center;
    font-size: 0.95rem;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 4px 14px;
    border-radius: 20px;
    display: inline-block;
    margin: 2px auto 12px auto;
}

.phase-badge-wrap {
    text-align: center;
}

.phase-1 {
    color: #4caf50;
    border: 1px solid #4caf50;
    background: rgba(76, 175, 80, 0.08);
}

.phase-2 {
    color: #ffc107;
    border: 1px solid #ffc107;
    background: rgba(255, 193, 7, 0.08);
}

.phase-3 {
    color: #ff5252;
    border: 1px solid #ff5252;
    background: rgba(255, 82, 82, 0.08);
}

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
    shared = load_app_state("boss_config", {}) if shared_enabled() else {}
    raw_shared = shared.get("bosses") if isinstance(shared, dict) else None
    if raw_shared:
        try:
            return {name: dict_to_boss(data) for name, data in raw_shared.items()}
        except (KeyError, ValueError, TypeError):
            pass
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            bosses = {name: dict_to_boss(data) for name, data in raw.items()}
            if bosses:
                return bosses
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass
    bosses = build_default_bosses()
    save_bosses(bosses)
    return bosses


def save_bosses(bosses: dict) -> None:
    raw = {name: boss_to_dict(boss) for name, boss in bosses.items()}
    try:
        tmp_file = DATA_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, DATA_FILE)
    except OSError:
        pass
    if shared_enabled():
        config = load_app_state("boss_config", {}) or {}
        config["bosses"] = raw
        save_app_state("boss_config", config)


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


def roll_specific_attack(boss: Boss, attack_name: str):

    attack = next(a for a in boss.attacks if a.name == attack_name)
    result = attack.execute()

    st.session_state.manual_result = {
        "attack": attack,
        "result": result
    }


def matrix_color(value):
    if value <= 16:
        return "matrix-green"
    elif value <= 23:
        return "matrix-yellow"
    else:
        return "matrix-red"


# ============================================================
# RENDER: RESULTADO DE UM ATAQUE (usado no ataque manual e no turno)
# ============================================================

def render_attack_result(attack: Attack, result: dict):

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("D20", result["natural_roll"])

    with c2:
        st.metric("Bônus", f"+{attack.attack_bonus}")

    with c3:
        st.markdown(
            f"""
            <div class="red-stat">
                <div class="red-stat-label">Total</div>
                <div class="red-stat-value">{result["attack_result"]}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    if result["is_critical"]:
        st.markdown(
            f"""
            <div class="critical">
                💥 CRÍTICO! &nbsp;&nbsp; ×{attack.crit_multiplier}
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("**💀 Dano**")

    damage_col, final_col = st.columns(2)

    with damage_col:
        dados = f"{attack.damage_dice_count}d{attack.damage_dice_sides} + {attack.damage_bonus}"
        st.write(f"`{dados}` → rolagem: **{result['damage_result']}**")

    with final_col:
        st.markdown(
            f"""
            <div class="red-stat">
                <div class="red-stat-label">Dano Final</div>
                <div class="red-stat-value">{result["final_damage"]}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    effect_col, effect_value_col = st.columns(2)

    with effect_col:
        st.markdown(f"**☠️ {attack.effect_name}**")

        if attack.type == "physical":
            if attack.effect_dice_count:
                st.write(f"`{attack.effect_dice_count}d{attack.effect_dice_sides}`")
            else:
                st.write("Nenhum efeito")
        else:
            st.write("Metade do dano final")

    with effect_value_col:
        st.markdown(
            f"""
            <div class="red-stat">
                <div class="red-stat-label">Efeito</div>
                <div class="red-stat-value">{result["effect_value"]}</div>
            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# RENDER: MODO COMBATE
# ============================================================

def render_combat_sidebar(bosses: dict, boss: Boss):

    with st.sidebar:

        st.header("⚙️ Controle do Chefe")

        names = list(bosses.keys())
        selected = st.selectbox(
            "👹 Boss atual",
            names,
            index=names.index(st.session_state.selected_boss)
        )

        if selected != st.session_state.selected_boss:
            st.session_state.selected_boss = selected
            st.session_state.manual_result = None
            st.rerun()

        st.divider()

        st.subheader("🎯 Ataque específico")

        attack_names = [a.name for a in boss.attacks]

        st.selectbox(
            "Escolha o ataque",
            attack_names,
            key=f"selected_attack_{boss.name}"
        )

        if st.button("🎲 ROLAR ATAQUE", use_container_width=True):
            chosen_attack = st.session_state[f"selected_attack_{boss.name}"]
            roll_specific_attack(boss, chosen_attack)
            st.rerun()

        st.divider()

        st.subheader("☠️ Status do chefe")

        status_to_add = st.selectbox("Adicionar condição", STATUS_OPTIONS)

        if st.button("➕ Adicionar status", use_container_width=True):
            if status_to_add not in st.session_state.statuses[boss.name]:
                st.session_state.statuses[boss.name].append(status_to_add)
                st.rerun()

        if st.session_state.statuses[boss.name]:
            st.caption("Status ativos:")
            for status in list(st.session_state.statuses[boss.name]):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"☠️ {status}")
                with col2:
                    if st.button("✕", key=f"remove_{boss.name}_{status}"):
                        st.session_state.statuses[boss.name].remove(status)
                        st.rerun()
        else:
            st.caption("Nenhum status ativo.")

        st.divider()

        st.subheader("🎯 Regras do combo")
        st.write("**60%**"); st.caption("3 ataques físicos")
        st.write("**20%**"); st.caption("2 físicos + 1 área")
        st.write("**10%**"); st.caption("1 físico + 1 área")
        st.write("**10%**"); st.caption("2 ataques em área")

        st.divider()

        current_phase = boss.get_current_phase(st.session_state.boss_hp[boss.name])

        st.subheader("🗡️ Ataques físicos")
        for attack in boss.get_physical_attacks():
            unlocked = attack.id in current_phase.physical_ids
            icon = "✅" if unlocked else "🔒"
            st.write(f"{icon} **{attack.id}.** {attack.name}")

        st.divider()

        st.subheader("🔥 Ataques em área")
        for attack in boss.get_area_attacks():
            unlocked = attack.id in current_phase.area_ids
            icon = "✅" if unlocked else "🔒"
            st.write(f"{icon} **{attack.id}.** {attack.name}")

        st.divider()

        st.write(f"**Turnos realizados:** {st.session_state.turn_numbers[boss.name]}")

        if st.button("🔄 Resetar chefe", use_container_width=True):
            st.session_state.boss_hp[boss.name] = boss.max_hp
            st.session_state.turn_numbers[boss.name] = 0
            st.session_state.histories[boss.name] = []
            st.session_state.current_turns[boss.name] = None
            st.session_state.statuses[boss.name] = []
            st.session_state.manual_result = None
            st.rerun()

        if st.button("🗑️ Limpar histórico", use_container_width=True):
            st.session_state.histories[boss.name] = []
            st.session_state.current_turns[boss.name] = None
            st.session_state.turn_numbers[boss.name] = 0
            st.rerun()

        st.divider()

        if st.button("⚙️ Editor de Bosses", use_container_width=True):
            st.session_state.app_mode = "editor"
            st.session_state.editor_target = st.session_state.selected_boss
            st.session_state.editor_creating = False
            st.rerun()


def render_combat_main(boss: Boss):

    st.markdown('<div class="main-title">⚔️ Simulador de Chefe RPG</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Ferramenta de narração para RPG de mesa</div>',
        unsafe_allow_html=True
    )

    st.markdown('<div class="hp-container">', unsafe_allow_html=True)
    st.markdown(f'<div class="hp-title">{boss.name}</div>', unsafe_allow_html=True)

    hp = st.number_input(
        "HP atual",
        min_value=0,
        max_value=boss.max_hp,
        value=st.session_state.boss_hp[boss.name],
        step=1,
        key=f"hp_input_{boss.name}",
        label_visibility="collapsed"
    )
    st.session_state.boss_hp[boss.name] = hp

    hp_percentage = (st.session_state.boss_hp[boss.name] / boss.max_hp) * 100 if boss.max_hp else 0

    st.markdown(
        f"""
        <div class="hp-value">{st.session_state.boss_hp[boss.name]} / {boss.max_hp}</div>
        <div class="hp-bar-background">
            <div class="hp-bar-fill" style="width: {hp_percentage}%;"></div>
        </div>
        """,
        unsafe_allow_html=True
    )

    phase_index = boss.get_current_phase_index(st.session_state.boss_hp[boss.name])
    phase = boss.ensure_phases()[phase_index]
    phase_number = phase_index + 1
    phase_text = f"FASE {phase_number}"
    if phase.label:
        phase_text += f" — {phase.label.upper()}"

    st.markdown(
        f'<div class="phase-badge-wrap">'
        f'<span class="phase-badge phase-{min(phase_number, 3)}">{phase_text}</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    if st.session_state.statuses[boss.name]:
        status_html = " ".join(
            f'<span class="status-box">☠️ {status}</span>'
            for status in st.session_state.statuses[boss.name]
        )
        st.markdown(
            f'<div style="display:flex;gap:8px;justify-content:center;'
            f'flex-wrap:wrap;margin-top:15px;">{status_html}</div>',
            unsafe_allow_html=True
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # --------------------------------------------------------
    # ATAQUE MANUAL
    # --------------------------------------------------------

    if st.session_state.manual_result:

        attack = st.session_state.manual_result["attack"]
        result = st.session_state.manual_result["result"]

        st.markdown("---")
        st.subheader(f"🎯 Ataque manual — {attack.name}")

        icon = "🗡️" if attack.type == "physical" else "🔥"
        tipo = "ATAQUE FÍSICO" if attack.type == "physical" else "ATAQUE EM ÁREA"

        st.markdown(
            f'<div class="manual-result"><b>{icon} {attack.name}</b><br><small>{tipo}</small></div>',
            unsafe_allow_html=True
        )

        render_attack_result(attack, result)

    # --------------------------------------------------------
    # BOTÃO NOVO TURNO
    # --------------------------------------------------------

    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        if st.button("🎲  NOVO TURNO", type="primary", use_container_width=True):
            new_turn(boss)
            st.rerun()

    # --------------------------------------------------------
    # TURNO ATUAL
    # --------------------------------------------------------

    current_turn = st.session_state.current_turns[boss.name]

    if current_turn:

        st.markdown("---")
        st.header(f"⚔️ Turno {current_turn['number']}")

        st.subheader("🎯 Combo sorteado")

        combo_cols = st.columns(len(current_turn["results"]))

        for i, item in enumerate(current_turn["results"]):
            attack = item["attack"]
            icon = "🗡️" if attack.type == "physical" else "🔥"
            tipo = "Físico" if attack.type == "physical" else "Área"
            with combo_cols[i]:
                st.markdown(
                    f'<div class="combo-card"><b>{icon} {attack.name}</b><br>'
                    f'<small>{tipo}</small></div>',
                    unsafe_allow_html=True
                )

        st.subheader("🎲 Resultados")

        for i, item in enumerate(current_turn["results"], start=1):

            attack = item["attack"]
            result = item["result"]

            icon = "🗡️" if attack.type == "physical" else "🔥"
            tipo = "ATAQUE FÍSICO" if attack.type == "physical" else "ATAQUE EM ÁREA"

            st.markdown(
                f"""
                <div class="attack-card">
                    <div class="attack-title">{icon} {i}. {attack.name}</div>
                    <div class="attack-type">{tipo}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            render_attack_result(attack, result)

            st.markdown("---")

    # --------------------------------------------------------
    # MATRIZ FIXA
    # --------------------------------------------------------

    st.markdown("---")
    st.markdown('<div class="table-title">🎯 Matriz de Reações do Chefe</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="table-subtitle">Valores fixos por ataque — quanto maior, mais difícil</div>',
        unsafe_allow_html=True
    )

    header_cols = st.columns([2.4, 1, 1, 1, 1, 1])
    for col, header in zip(header_cols, ["Ataque"] + MATRIX_COLUMNS):
        with col:
            st.markdown(f'<div class="matrix-header">{header}</div>', unsafe_allow_html=True)

    for attack in boss.attacks:

        values = boss.get_matrix_row(attack.id)
        row_cols = st.columns([2.4, 1, 1, 1, 1, 1])

        with row_cols[0]:
            st.markdown(
                f'<div class="matrix-attack">{attack.id}. {attack.name}</div>',
                unsafe_allow_html=True
            )

        for col, value in zip(row_cols[1:], values):
            color_class = matrix_color(value)
            with col:
                st.markdown(
                    f'<div class="matrix-value {color_class}">{value}</div>',
                    unsafe_allow_html=True
                )

    legend_cols = st.columns(3)
    with legend_cols[0]:
        st.markdown("🟢 **10–16:** menor dificuldade")
    with legend_cols[1]:
        st.markdown("🟡 **17–23:** dificuldade média")
    with legend_cols[2]:
        st.markdown("🔴 **24–30:** maior dificuldade")

    # --------------------------------------------------------
    # HISTÓRICO
    # --------------------------------------------------------

    history = st.session_state.histories[boss.name]

    if len(history) > 1:

        st.markdown("---")
        st.header("📜 Histórico")

        for turn in history[1:]:

            resumo = [item["attack"].name for item in turn["results"]]
            titulo = f"Turno {turn['number']} — " + " + ".join(resumo)

            with st.expander(titulo):
                for i, item in enumerate(turn["results"], start=1):

                    attack = item["attack"]
                    result = item["result"]
                    crit = " 💥 CRÍTICO" if result["is_critical"] else ""

                    st.write(f"**{i}. {attack.name}**{crit}")
                    st.write(
                        f"🎲 {result['natural_roll']} + {attack.attack_bonus} "
                        f"= **{result['attack_result']}**"
                    )
                    st.write(f"💀 Dano: **{result['final_damage']}**")
                    st.write(f"☠️ {attack.effect_name}: **{result['effect_value']}**")

    # --------------------------------------------------------
    # BOTÃO FINAL
    # --------------------------------------------------------

    if current_turn:
        st.markdown("---")
        col_a, col_b, col_c = st.columns([1, 2, 1])
        with col_b:
            if st.button("🎲  PRÓXIMO TURNO", type="primary", use_container_width=True):
                new_turn(boss)
                st.rerun()


# ============================================================
# RENDER: EDITOR DE BOSSES
# ============================================================

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


def render_editor_sidebar(bosses: dict):

    with st.sidebar:

        st.header("⚙️ Editor de Bosses")

        names = list(bosses.keys())

        if names and not st.session_state.editor_creating:

            current = st.session_state.editor_target
            if current not in names:
                current = names[0]

            chosen = st.selectbox(
                "Boss para editar",
                names,
                index=names.index(current),
                key="editor_target_select"
            )

            if chosen != st.session_state.editor_target:
                st.session_state.editor_target = chosen
                st.session_state.confirm_delete = False
                st.rerun()

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            if st.button("➕ Novo Boss", use_container_width=True):
                st.session_state.editor_creating = True
                st.session_state.editor_target = None
                st.session_state.new_boss_counter += 1
                st.session_state.confirm_delete = False
                st.rerun()

        with col2:
            delete_disabled = len(bosses) <= 1 or st.session_state.editor_creating
            if st.button("🗑️ Apagar Boss", use_container_width=True, disabled=delete_disabled):
                st.session_state.delete_target = st.session_state.editor_target
                st.session_state.confirm_delete = True
                st.rerun()

        st.divider()

        if st.button("↩️ Voltar ao combate", use_container_width=True):
            st.session_state.app_mode = "combat"
            st.session_state.editor_creating = False
            st.session_state.confirm_delete = False
            st.rerun()


def render_delete_confirmation(bosses: dict):

    target = st.session_state.delete_target

    st.markdown('<div class="editor-title">🗑️ Apagar boss</div>', unsafe_allow_html=True)
    st.warning(
        f"Tem certeza que deseja apagar **{target}**? "
        f"Essa ação não pode ser desfeita."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Confirmar exclusão", type="primary", use_container_width=True):

            bosses.pop(target, None)
            delete_boss_state(target)
            save_bosses(bosses)

            remaining = list(bosses.keys())
            st.session_state.selected_boss = remaining[0] if remaining else None
            st.session_state.editor_target = remaining[0] if remaining else None
            st.session_state.confirm_delete = False
            st.session_state.delete_target = None
            st.session_state.app_mode = "combat"

            st.success(f"Boss '{target}' apagado.")
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

    title = "➕ Criar novo boss" if creating else f"⚙️ Editando: {editor_target}"
    st.markdown(f'<div class="editor-title">{title}</div>', unsafe_allow_html=True)

    tab_dados, tab_ataques, tab_fases, tab_matriz = st.tabs(
        ["📋 Dados do Boss", "⚔️ Ataques", "🌀 Fases", "🎯 Matriz de Reações"]
    )

    # ---------------------------------------------------
    # DADOS DO BOSS
    # ---------------------------------------------------

    with tab_dados:

        boss_name = st.text_input(
            "Nome do boss",
            value=default_name,
            key=f"{base}_boss_name"
        )

        max_hp = st.number_input(
            "HP máximo",
            min_value=1,
            max_value=100000,
            value=int(default_max_hp),
            step=1,
            key=f"{base}_max_hp"
        )

        hp_atual = st.number_input(
            "HP atual",
            min_value=0,
            max_value=int(max_hp),
            value=min(int(default_hp), int(max_hp)),
            step=1,
            key=f"{base}_hp_atual"
        )

    # ---------------------------------------------------
    # ATAQUES
    # ---------------------------------------------------

    attack_values = []

    with tab_ataques:

        st.caption("Configure os 10 ataques do boss.")

        for i in range(1, 11):

            if source_boss:
                template = source_boss.attacks[i - 1]
            else:
                template = default_attack_template(i)

            with st.expander(f"Ataque {i} — {template.name}", expanded=False):

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

            with col_phys:
                st.caption("🗡️ Ataques físicos desbloqueados")
                selected_physical = []
                for atk in physical_in_editor:
                    checked = st.checkbox(
                        f"{atk.id}. {atk.name}",
                        value=atk.id in phase_default.physical_ids,
                        key=f"{base}_phase{idx}_phys_{atk.id}"
                    )
                    if checked:
                        selected_physical.append(atk.id)

            with col_area:
                st.caption("🔥 Ataques em área desbloqueados")
                selected_area = []
                for atk in area_in_editor:
                    checked = st.checkbox(
                        f"{atk.id}. {atk.name}",
                        value=atk.id in phase_default.area_ids,
                        key=f"{base}_phase{idx}_area_{atk.id}"
                    )
                    if checked:
                        selected_area.append(atk.id)

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

        st.caption("10 ataques × 5 ações = 50 valores. Verde 10–16, amarelo 17–23, vermelho 24–30.")

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
    # SALVAR / CANCELAR
    # ---------------------------------------------------

    st.markdown("---")

    col_save, col_cancel = st.columns([1, 1])

    with col_save:
        save_clicked = st.button("💾 Salvar alterações", type="primary", use_container_width=True)

    with col_cancel:
        cancel_clicked = st.button("↩️ Cancelar", use_container_width=True)

    if cancel_clicked:
        st.session_state.editor_creating = False
        st.session_state.editor_target = st.session_state.selected_boss
        st.session_state.app_mode = "combat"
        st.rerun()

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

        if creating:
            bosses[final_name] = new_boss
            init_boss_state(final_name, int(max_hp), int(hp_atual))

        else:
            old_name = editor_target
            if old_name != final_name:
                del bosses[old_name]
                rename_boss_state(old_name, final_name)
            bosses[final_name] = new_boss
            st.session_state.boss_hp[final_name] = int(hp_atual)

        save_bosses(bosses)

        st.session_state.selected_boss = final_name
        st.session_state.editor_target = final_name
        st.session_state.editor_creating = False
        st.session_state.app_mode = "combat"

        st.success(f"Boss '{final_name}' salvo com sucesso.")
        st.rerun()


def render_editor_main(bosses: dict):

    if st.session_state.confirm_delete:
        render_delete_confirmation(bosses)
    else:
        render_boss_editor_form(bosses)


# ============================================================
# APP PRINCIPAL
#
#              app.py
#                │
#       carrega bosses.json
#                │
#        ┌───────┴───────┐
#        ↓               ↓
#  MODO COMBATE       EDITOR
#        │               │
#  usa dados do      altera dados
#     boss                │
#        │               ↓
#        └────────→ bosses.json
# ============================================================

def render_shared_display_controls(bosses: dict):
    """Configura o painel de cena/chefe consumido pelo painel geral."""
    if not shared_enabled():
        st.sidebar.warning("Configure SUPABASE_URL e SUPABASE_ANON_KEY para sincronizar com o painel geral.")
        return
    config = load_app_state("boss_config", {}) or {}
    display = config.get("display", {}) or {}
    st.sidebar.divider()
    st.sidebar.subheader("Cena compartilhada")
    mode = st.sidebar.radio("Modo exibido", ["Chefe", "Cena narrativa"], index=0 if display.get("mode", "Chefe") == "Chefe" else 1, key="shared_display_mode")
    scene_name = st.sidebar.text_input("Nome da cena", value=display.get("scene_name", "Cena atual"), key="shared_scene_name")
    show_scene = st.sidebar.checkbox("Exibir imagem da cena", value=display.get("show_scene", True), key="shared_show_scene")
    scene_file = st.sidebar.file_uploader("Imagem da cena (PNG/JPG)", type=["png", "jpg", "jpeg"], key="shared_scene_upload")
    if scene_file is not None and st.session_state.get("_scene_upload_name") != scene_file.name:
        mime = scene_file.type or "image/png"
        url = upload_asset(f"scenes/{scene_file.name.replace(' ', '_')}", scene_file.getvalue(), mime)
        if url:
            display["scene_image_url"] = url
            st.session_state["_scene_upload_name"] = scene_file.name
    selected_name = st.session_state.get("selected_boss", next(iter(bosses)))
    boss_file = st.sidebar.file_uploader(f"Imagem do chefe: {selected_name}", type=["png", "jpg", "jpeg"], key="shared_boss_upload")
    boss_images = display.get("boss_images", {}) or {}
    if boss_file is not None and st.session_state.get("_boss_upload_name") != boss_file.name:
        mime = boss_file.type or "image/png"
        url = upload_asset(f"bosses/{selected_name.replace(' ', '_')}_{boss_file.name.replace(' ', '_')}", boss_file.getvalue(), mime)
        if url:
            boss_images[selected_name] = url
            display["boss_images"] = boss_images
            st.session_state["_boss_upload_name"] = boss_file.name
    if st.sidebar.button("Publicar cena no painel", use_container_width=True):
        display.update({"mode": mode, "scene_name": scene_name, "show_scene": show_scene, "boss_images": boss_images})
        config["display"] = display
        save_app_state("boss_config", config)
        st.sidebar.success("Configuração da cena salva.")
    # Publica estado atual do chefe mesmo quando não há upload novo.
    display.update({"mode": mode, "scene_name": scene_name, "show_scene": show_scene, "boss_images": boss_images})
    config["display"] = display
    config["bosses"] = {name: boss_to_dict(boss) for name, boss in bosses.items()}
    save_app_state("boss_config", config)


def publish_current_boss(bosses: dict):
    if not shared_enabled() or not bosses:
        return
    name = st.session_state.get("selected_boss", next(iter(bosses)))
    boss = bosses.get(name)
    if not boss:
        return
    config = load_app_state("boss_config", {}) or {}
    display = config.get("display", {}) or {}
    hp = st.session_state.get("boss_hp", {}).get(name, boss.max_hp)
    save_app_state("table_display", {
        "mode": display.get("mode", "Chefe"),
        "scene_name": display.get("scene_name", "Cena atual"),
        "show_scene": display.get("show_scene", True),
        "scene_image_url": display.get("scene_image_url", ""),
        "boss_name": name,
        "boss_image_url": (display.get("boss_images", {}) or {}).get(name, ""),
        "boss_hp": max(0, min(int(hp), int(boss.max_hp))),
        "boss_max_hp": int(boss.max_hp),
        "updated_at": __import__("datetime").datetime.now().isoformat(),
    })


def main():

    bosses = load_bosses()
    init_session_state(bosses)

    render_shared_display_controls(bosses)
    if st.session_state.app_mode == "editor":
        render_editor_sidebar(bosses)
        render_editor_main(bosses)
    else:
        boss = bosses[st.session_state.selected_boss]
        render_combat_sidebar(bosses, boss)
        render_combat_main(boss)
    publish_current_boss(bosses)


if __name__ == "__main__":
    main()
