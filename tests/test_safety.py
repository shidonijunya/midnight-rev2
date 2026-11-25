"""Functional safety tests; no production Supabase credentials required."""
import copy
import unittest
from unittest.mock import patch

import shared_backend
from boss_runtime import pack_runtime, apply_runtime
from game_rules import modificador, calc_hp_max, calc_mana_max, calc_estamina_max


class Response:
    def __init__(self, data):
        self.data = data


class FakeClient:
    """Small PostgREST mock that simulates a racing writer on the first update."""
    def __init__(self, race=False, fail=False):
        self.row = {"data": {"estamina_atual": 100, "mana_atual": 60, "hp_atual": 50},
                    "updated_at": "revision-a"}
        self.race = race
        self.fail = fail
        self.updates = 0

    def table(self, name):
        if name == "app_state":
            raise RuntimeError("History table unavailable in this unit mock")
        return FakeQuery(self)


class FakeQuery:
    def __init__(self, client):
        self.client = client
        self.filters = {}
        self.payload = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def limit(self, *args):
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def execute(self):
        c = self.client
        if c.fail:
            raise RuntimeError("database offline")
        if self.payload is None:
            return Response([copy.deepcopy(c.row)])
        c.updates += 1
        if c.race and c.updates == 1:
            c.row["data"]["estamina_atual"] = 70
            c.row["updated_at"] = "revision-external"
        if self.filters.get("updated_at") != c.row["updated_at"]:
            return Response([])
        c.row = copy.deepcopy(self.payload)
        return Response([{"player_id": "jogador_2"}])


class SafetyTests(unittest.TestCase):
    def test_read_failure_is_not_missing_character(self):
        fake = FakeClient(fail=True)
        with patch.object(shared_backend, "get_client", return_value=fake):
            result = shared_backend.fetch_character("jogador_2")
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["data"])

    def test_concurrent_stamina_spends_recompute_from_fresh_value(self):
        fake = FakeClient(race=True)
        with patch.object(shared_backend, "get_client", return_value=fake):
            ok, data, error = shared_backend.change_resources_atomic(
                "jogador_2", {"estamina_atual": -20})
        self.assertTrue(ok, error)
        self.assertEqual(fake.updates, 2)
        self.assertEqual(data["estamina_atual"], 50)
        self.assertEqual(fake.row["data"]["estamina_atual"], 50)

    def test_insufficient_resources_does_not_overdraw(self):
        fake = FakeClient()
        with patch.object(shared_backend, "get_client", return_value=fake):
            ok, data, error = shared_backend.change_resources_atomic(
                "jogador_2", {"estamina_atual": -200})
        self.assertFalse(ok)
        self.assertEqual(fake.updates, 0)
        self.assertIn("insuficiente", error)

    def test_skill_and_resource_formula_unchanged(self):
        self.assertEqual(modificador(20), 5)
        self.assertEqual(calc_hp_max(20, 15)[0], 120)
        self.assertGreater(calc_mana_max(10, 10, 10), 0)
        self.assertGreater(calc_estamina_max(10, 10, 10), 0)

    def test_boss_runtime_round_trip_preserves_turns(self):
        class Attack:
            id = 1
        class Boss:
            attacks = [Attack()]
            max_hp = 200
        bosses = {"Kriv": Boss()}
        source = {"selected_boss": "Kriv", "boss_hp": {"Kriv": 73},
                  "turn_numbers": {"Kriv": 4},
                  "histories": {"Kriv": [{"number": 4, "results": [
                      {"attack": Attack(), "result": {"final_damage": 17}}]}]},
                  "current_turns": {"Kriv": None},
                  "statuses": {"Kriv": ["Atordoado"]}}
        snapshot = pack_runtime(bosses, source)
        target = {"boss_hp": {}, "turn_numbers": {}, "histories": {},
                  "current_turns": {}, "statuses": {}}
        apply_runtime(bosses, target, snapshot)
        self.assertEqual(target["boss_hp"]["Kriv"], 73)
        self.assertEqual(target["turn_numbers"]["Kriv"], 4)
        self.assertEqual(target["histories"]["Kriv"][0]["results"][0]["attack"].id, 1)

    def test_boss_attack_count_is_configurable(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        code = (root / "app_boss.py").read_text(encoding="utf-8")
        self.assertIn('1 <= len(raw_attacks) <= 20', code)
        self.assertIn('"Quantidade de ataques"', code)
        self.assertNotIn('physical_count != 5 or area_count != 5', code)
        self.assertIn('hydrate_runtime(bosses, st.session_state)', code)
        self.assertIn('persist_runtime(bosses, st.session_state)', code)

    def test_security_mode_is_explicit_and_browser_map_hides_anon_key(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        auth = (root / "auth_unified.py").read_text(encoding="utf-8")
        map_code = (root / "tactical_map.py").read_text(encoding="utf-8")
        self.assertIn("MIDNIGHT_SECURE_MODE", auth)
        self.assertIn('anon = "" if secure_mode_enabled()', map_code)
        self.assertTrue((root / "security_cutover.sql").exists())

    def test_fog_area_effects_share_a_single_poll(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        map_code = (root / "tactical_map.py").read_text(encoding="utf-8")
        for tool in ("fog_hide", "fog_reveal", "area_circle", "area_cone", "area_line"):
            self.assertIn(tool, map_code)
        self.assertIn("battle_effects", map_code)
        self.assertIn("key=in.(battle_grid,battle_effects,battle_fog,battle_areas)", map_code)
        self.assertNotIn("async function pollEffects()", map_code)

    def test_variable_weapons_keep_existing_data_in_source(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        for i in (1, 2, 3):
            source = (root / f"ficha_jogador_{i}.py").read_text(encoding="utf-8")
            self.assertIn('"weapon_slots_count": 5', source)
            self.assertIn('for i in range(NUM_ARMAS)', source)
            self.assertIn('Quantidade de armas', source)
            self.assertNotIn("def render_planejador_turno():", source)


if __name__ == "__main__":
    unittest.main()
