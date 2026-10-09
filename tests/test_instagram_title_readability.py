"""Regride o bloqueio do título sem consultar fontes externas ou publicar."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import preparar_post_instagram_v2 as executor
import instagram_visual_policy as visual

base = executor.base
TITLE = 'CBF confirma paralisação das quatro divisões para a Copa do Mundo Feminina - CNN Brasil'


class TitleReadabilityTests(unittest.TestCase):
    def test_real_five_line_fallback_passes_final_selection(self):
        candidate = {'key': 'instagram:noticia:test-layout', 'type': 'noticia',
                     'title': TITLE, 'caption': '📰 ' + TITLE + '\n\nResumo e fonte', 'subtitle': ''}
        original_cwd = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                os.chdir(directory)
                with patch.object(base, 'candidates', return_value=[candidate]), \
                     patch.object(base, 'choose_news_bank_image', return_value=None), \
                     patch.object(base, 'policy_visual_mode', return_value='legacy'), \
                     patch.object(base, 'find_commons_image', return_value=None), \
                     patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected network')), \
                     contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(base.main(), 0)
                batch = json.loads(Path('instagram/fila/automatica/lote-atual.json').read_text())
                post = json.loads(Path(batch['posts'][0]).read_text())
                self.assertTrue(post['TITLE_READABILITY_OK'])
                self.assertEqual(post['title_lines'], 5)
                self.assertEqual(post['original_title'], TITLE)
                self.assertEqual(post['caption'], candidate['caption'])
                self.assertNotIn('…', post['art_title'])
                self.assertEqual(post['visual_mode'], 'fallback_visual')
                image = Path('instagram/artes') / (post['id'] + '.jpg')
                with Image.open(image) as rendered:
                    self.assertEqual(rendered.size, (1080, 1080))
                self.assertIn('title_layout_policy=text_fallback', output.getvalue())
        finally:
            os.chdir(original_cwd)

    def test_photo_limits_and_renderer_rejections_remain_enforced(self):
        self.assertTrue(base.title_readability_ok(True, 68, 5, text_fallback=True))
        self.assertFalse(base.title_readability_ok(True, 68, 5))
        self.assertFalse(base.title_readability_ok(True, 50, 4))
        self.assertTrue(base.title_readability_ok(True, 58, 4))
        self.assertFalse(base.title_readability_ok(False, 68, 5, text_fallback=True))
        self.assertFalse(base.title_readability_ok(True, 31, 5, text_fallback=True))
        self.assertFalse(base.title_readability_ok(True, 68, 6, text_fallback=True))
        self.assertFalse(base.title_readability_ok(True, 68, 0, text_fallback=True))

    def test_illustrated_news_variants_render_without_name_error(self):
        keys = {}
        for index in range(100):
            item = {'key': f'news-{index}', 'title': 'Brasil prepara a Copa Feminina 2027'}
            keys.setdefault(visual._variant_for(item, 4), item)
        self.assertEqual(set(keys), {0, 1, 2, 3})
        with tempfile.TemporaryDirectory() as directory:
            for variant, item in keys.items():
                with self.subTest(variant=variant):
                    output = Path(directory) / f'news-{variant}.jpg'
                    readable, font_size, lines, metadata = visual.render_news_art(
                        str(output), item, font=base.font, wrap=base.wrap,
                        fit_title=executor.fit_title_complete)
                    self.assertTrue(base.title_readability_ok(readable, font_size, lines))
                    self.assertNotIn('…', metadata['art_title'])
                    with Image.open(output) as rendered:
                        self.assertEqual(rendered.size, (1080, 1080))


if __name__ == '__main__':
    unittest.main()
