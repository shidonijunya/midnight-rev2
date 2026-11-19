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
        for name, fun in (
            ("ficha_jogador_1.py", "modificador"),
            ("ficha_jogador_2.py", "modificador"),
            ("ficha_jogador_3.py", "modificador"),
            ("painel_geral.py", "attr_mod"),
        ):
            func = self.isolated_function(name, fun)
            self.assertEqual(func(10), 0)
            self.assertEqual(func(19), 4)
            self.assertEqual(func(20), 5, name)
            self.assertEqual(func(21), 5)

    def test_access_code_hashing(self):
        from auth_unified import hash_password, verify_password
        encoded = hash_password("test-password-muito-longa")
        self.assertTrue(verify_password("test-password-muito-longa", encoded))
        self.assertFalse(verify_password("senha-errada", encoded))

    def test_static_image_editor(self):
        from image_manager import prepare_image
        image = Image.new("RGB", (30, 30), (255, 30, 30))
        raw = io.BytesIO()
        image.save(raw, format="PNG")
        processed = prepare_image(raw.getvalue(), "portrait")
        with Image.open(io.BytesIO(processed)) as rendered:
            self.assertEqual(rendered.size, (600, 750))

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
