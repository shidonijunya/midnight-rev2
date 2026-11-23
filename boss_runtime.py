"""Persistência versionada do estado de combate, mantendo bosses e fichas existentes.

O contrato persiste apenas dados simples (IDs de ataques e resultados);
a sessão reconstrói objetos Attack usando a biblioteca de bosses já carregada.
"""
from shared_backend import (
    load_app_state_record, create_app_state_if_missing, compare_and_set_app_state,
)


def _turn_to_data(turn):
    if not isinstance(turn, dict):
        return None
    return {
        "number": turn.get("number", 0),
        "results": [
            {"attack_id": getattr(item.get("attack"), "id", None),
             "result": item.get("result") or {}}
            for item in turn.get("results", []) if isinstance(item, dict)
        ],
    }


def _turn_from_data(turn, boss):
    if not isinstance(turn, dict):
        return None
    by_id = {attack.id: attack for attack in boss.attacks}
    return {
        "number": turn.get("number", 0),
        "results": [
            {"attack": by_id[item["attack_id"]], "result": item.get("result") or {}}
            for item in turn.get("results", [])
            if isinstance(item, dict) and item.get("attack_id") in by_id
        ],
    }


def pack_runtime(bosses, state):
    snapshot = {"selected_boss": state.get("selected_boss"), "bosses": {}}
    for name, boss in bosses.items():
        history = state.get("histories", {}).get(name, []) or []
        snapshot["bosses"][name] = {
            "hp": max(0, min(int(state.get("boss_hp", {}).get(name, boss.max_hp)), boss.max_hp)),
            "turn": int(state.get("turn_numbers", {}).get(name, 0)),
            "current": _turn_to_data(state.get("current_turns", {}).get(name)),
            "history": [_turn_to_data(t) for t in history[:100]],
            "statuses": list(state.get("statuses", {}).get(name, [])),
        }
    return snapshot


def apply_runtime(bosses, state, snapshot):
    if not isinstance(snapshot, dict):
        return
    if snapshot.get("selected_boss") in bosses:
        state["selected_boss"] = snapshot["selected_boss"]
    for name, values in (snapshot.get("bosses") or {}).items():
        if name not in bosses or not isinstance(values, dict):
            continue
        boss = bosses[name]
        state["boss_hp"][name] = max(0, min(int(values.get("hp", boss.max_hp)), boss.max_hp))
        state["turn_numbers"][name] = max(0, int(values.get("turn", 0)))
        state["current_turns"][name] = _turn_from_data(values.get("current"), boss)
        state["histories"][name] = [
            turn for item in values.get("history", [])[:100]
            if (turn := _turn_from_data(item, boss)) is not None
        ]
        state["statuses"][name] = list(values.get("statuses") or [])


def hydrate_runtime(bosses, state):
    """At first visit, prefer the last persisted battle over local defaults."""
    if state.get("_boss_runtime_loaded"):
        return
    record = load_app_state_record("boss_runtime")
    if record and isinstance(record.get("data"), dict):
        apply_runtime(bosses, state, record["data"])
        state["_boss_runtime_revision"] = record["updated_at"]
    else:
        # Compatible with the pre-runtime deployment: keep the current boss HP.
        record_display = load_app_state_record("table_display")
        view = (record_display or {}).get("data") or {}
        name = view.get("boss_name")
        if name in bosses and view.get("boss_hp") is not None:
            state["boss_hp"][name] = max(0, min(int(view["boss_hp"]), bosses[name].max_hp))
        state["_boss_runtime_revision"] = None
    state["_boss_runtime_baseline"] = pack_runtime(bosses, state)
    state["_boss_runtime_loaded"] = True


def persist_runtime(bosses, state):
    """Return True only when local changes were durably saved via revision CAS."""
    current = pack_runtime(bosses, state)
    if current == state.get("_boss_runtime_baseline"):
        return False
    revision = state.get("_boss_runtime_revision")
    if revision:
        ok = compare_and_set_app_state("boss_runtime", revision, current)
    else:
        ok = create_app_state_if_missing("boss_runtime", current)
    if not ok:
        # No silent overwrite: leave the DB untouched and ask for a refresh.
        state["_boss_runtime_conflict"] = True
        return False
    latest = load_app_state_record("boss_runtime")
    state["_boss_runtime_revision"] = (latest or {}).get("updated_at")
    state["_boss_runtime_baseline"] = current
    state["_boss_runtime_conflict"] = False
    return True
