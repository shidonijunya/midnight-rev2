"""Regression tests for the Midnight Sun revision (no production credentials)."""
import ast
import importlib
import io
import pathlib
import unittest
from PIL import Image, ImageSequence

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestCoreRules(unittest.TestCase):
    def isolated_function(self, filename, function):
        tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
        module = ast.Module(body=[node], type_ignores=[])
        scope = {}
        exec(compile(ast.fix_missing_locations(module), filename, "exec"), scope)
        return scope[function]

    def test_attribute_modifier_sheet_and_panel(self):
        from game_rules import modificador
        panel = self.isolated_function("painel_geral.py", "attr_mod")
        for value, expected in ((10, 0), (19, 4), (20, 5), (21, 5)):
            self.assertEqual(modificador(value), expected)
            self.assertEqual(panel(value), expected)
        for i in (1, 2, 3):
            source = (ROOT / f"ficha_jogador_{i}.py").read_text(encoding="utf-8")
            self.assertIn("from game_rules import", source)

    def test_uploaded_token_is_persisted_by_all_sheets(self):
        for i, name in enumerate(("Kuro", "Andrias", "Bondobo"), 1):
            source = (ROOT / f"ficha_jogador_{i}.py").read_text(encoding="utf-8")
            self.assertIn('"token_url",', source, name)
            self.assertNotIn('render_image_editor("token"', source, name)

    def test_map_uses_uploaded_token_urls_not_generic_emojis(self):
        source = (ROOT / "tactical_map.py").read_text(encoding="utf-8")
        self.assertIn("row.data.token_url", source)
        self.assertIn(".mob_tokens", source)
        self.assertIn("SEM PNG", source)
        self.assertNotIn("entry.emoji||", source)

    def test_layout_retains_shared_dice_and_scene(self):
        source = (ROOT / "painel_geral.py").read_text(encoding="utf-8")
        self.assertIn("shared_animation()\n        scene_panel()", source)
        self.assertIn("render_defense_buttons(pid)", source)
        self.assertIn("render_skill_buttons(pid)", source)
        self.assertNotIn('st.markdown("#### Mapa tático")', source)
        self.assertNotIn('st.markdown("#### Chefe")', source)

    def test_access_code_hashing(self):
        from auth_unified import hash_password, verify_password
        encoded = hash_password("test-password-muito-longa")
        self.assertTrue(verify_password("test-password-muito-longa", encoded))
        self.assertFalse(verify_password("senha-errada", encoded))

    def test_scene_keeps_entire_frame(self):
        from image_manager import prepare_image
        for size in ((601, 90), (90, 601)):
            original = Image.new("RGBA", size, "red")
            original.putpixel((0, 0), (0, 255, 0, 255))
            raw = io.BytesIO()
            original.save(raw, "PNG")
            with Image.open(io.BytesIO(prepare_image(raw.getvalue(), "scene"))) as result:
                self.assertEqual(result.size, size)
                self.assertEqual(result.convert("RGBA").getpixel((0, 0)), (0, 255, 0, 255))

    def test_static_image_editor(self):
        from image_manager import prepare_image
        image = Image.new("RGB", (30, 30), (255, 30, 30))
        raw = io.BytesIO()
        image.save(raw, format="PNG")
        processed = prepare_image(raw.getvalue(), "portrait")
        with Image.open(io.BytesIO(processed)) as rendered:
            self.assertEqual(rendered.size, (600, 750))

    def test_token_transparency_and_native_resolution(self):
        from image_manager import prepare_image
        original = Image.new("RGBA", (600, 540), (0, 0, 0, 0))
        original.putpixel((40, 40), (255, 0, 0, 255))
        stream = io.BytesIO()
        original.save(stream, format="PNG")
        output = prepare_image(stream.getvalue(), "token")
        with Image.open(io.BytesIO(output)) as token:
            self.assertEqual(token.size, (600, 540))
            self.assertEqual(token.convert("RGBA").getpixel((0, 0))[3], 0)
            self.assertEqual(token.convert("RGBA").getpixel((40, 40)), (255, 0, 0, 255))

    def test_parry_sound_is_character_specific(self):
        panel = (ROOT / "painel_geral.py").read_text(encoding="utf-8")
        stage = (ROOT / "dice3d.py").read_text(encoding="utf-8")
        self.assertIn('"player_id": pid, "defense_key": key', panel)
        self.assertIn('data.get("defense_key") == "parry"', panel)
        self.assertIn('"jogador_2": KURO_PARRY_AUDIO', panel)
        self.assertIn('"jogador_3": ANDRIAS_PARRY_AUDIO', panel)
        self.assertNotIn("def parry_sound_settings()", panel)
        self.assertIn('SPEC.sound_kind === "parry"', stage)
        self.assertIn('if (!enabled || SPEC.idle) return;', stage)
        self.assertIn('setSound(!enabled)', stage)
        from dice3d import DICE_AUDIO
        import base64
        import hashlib
        payload = base64.b64decode(DICE_AUDIO.split(",", 1)[1], validate=True)
        self.assertEqual(hashlib.sha1(b"blob 55725\\0".replace(b"\\0", bytes([0])) + payload).hexdigest(),
                         "291be937c79ab27e746d157adc090f75970ce580")

    def test_bundled_audio_is_decodable_without_upload(self):
        import base64
        from parry_kuro_asset import DATA_URI as kuro
        from parry_andrias_asset import DATA_URI as andrias
        from parry_bondobo_asset import DATA_URI as bondobo
        for uri, expected, mime, magic in (
            (kuro, 134445, 'mpeg', b'ID3'),
            (andrias, 85589, 'webm', bytes.fromhex('1a45dfa3')),
            (bondobo, 42973, 'webm', bytes.fromhex('1a45dfa3')),
        ):
            self.assertTrue(uri.startswith(f"data:audio/{mime};base64,"))
            payload = base64.b64decode(uri.split(",", 1)[1], validate=True)
            self.assertEqual(len(payload), expected)
            self.assertTrue(payload.startswith(magic))


    def test_bottom_ratio_and_simple_dice_labels(self):
        source = (ROOT / "painel_geral.py").read_text(encoding="utf-8")
        self.assertIn("st.columns([1, 1]", source)
        self.assertIn('col.button(f"d{sides}"', source)

    def test_gif_keeps_animation(self):
        from chat_media import _animated_webp
        frames = [Image.new("RGBA", (40, 40), color)
                  for color in ("red", "blue", "green")]
        encoded = io.BytesIO()
        frames[0].save(encoded, format="GIF", save_all=True,
                       append_images=frames[1:], duration=100, loop=0)
        output = _animated_webp(encoded.getvalue())
        with Image.open(io.BytesIO(output)) as animation:
            self.assertTrue(getattr(animation, "is_animated", False))
            self.assertGreaterEqual(getattr(animation, "n_frames", 1), 2)


if __name__ == "__main__":
    unittest.main()
