"""Garante títulos de oportunidades em português, sem rede nem chamadas à Meta."""
import datetime as dt
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import preparar_post_instagram_curado as editorial
import publicar_instagram as publisher


class OpportunityPortugueseTitleTests(unittest.TestCase):
    def test_talent_pool_title_and_caption_are_translated(self):
        original = "Talent Pool – People with Disabilities | 8 Host Cities"
        translated = "Banco de talentos para pessoas com deficiência nas oito cidades-sede"
        self.assertTrue(editorial.looks_english_title(original))
        self.assertEqual(editorial.art_title_pt("oportunidade", original, organization="FIFA"), translated)
        today = dt.datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        opportunity = {
            "ID": "OPP-LANG-TEST",
            "Titulo": original,
            "Link": "https://example.org/opportunity",
            "Status": "Inscrições abertas",
            "Categoria": "Trabalho",
            "Organizacao": "FIFA",
            "Resumo": "Oportunidade profissional da FIFA relacionada à Copa Feminina 2027 no Brasil.",
            "DataDescoberta": today.isoformat(),
        }
        result = editorial.candidates([], [], [opportunity], set(), [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], original)  # Fonte preservada
        self.assertEqual(result[0]["art_title"], translated)
        self.assertTrue(result[0]["caption"].startswith("🎯 " + translated))
        self.assertFalse(publisher.is_english_opportunity_headline(result[0]["art_title"]))

    def test_other_english_job_and_portuguese_original(self):
        translated = editorial.art_title_pt(
            "oportunidade", "Digital Product Manager",
            summary="Oportunidade profissional da FIFA ligada à Copa Feminina 2027 no Brasil, com atuação em produtos digitais.",
            organization="FIFA", category="Trabalho",
        )
        self.assertFalse(publisher.is_english_opportunity_headline(translated))
        native = "FIFA abre vaga de gestão de energia para sete cidades-sede"
        self.assertEqual(editorial.art_title_pt("oportunidade", native), native)
        self.assertFalse(publisher.is_english_opportunity_headline(native))

    def test_final_gate_blocks_english_caption_and_english_art(self):
        base = {"source_type": "oportunidade", "approved": True, "image_url": "https://example.org/image.jpg"}
        with self.assertRaisesRegex(publisher.InstagramError, "título"):
            publisher.validate_post(dict(base, caption="🎯 Talent Pool – People with Disabilities | 8 Host Cities"), True)
        with self.assertRaisesRegex(publisher.InstagramError, "título"):
            publisher.validate_post(dict(base, caption="🎯 Banco de talentos para pessoas com deficiência",
                                         art_title="Talent Pool – People with Disabilities | 8 Host Cities"), True)
        publisher.validate_post(dict(base, caption="🎯 Banco de talentos para pessoas com deficiência nas oito cidades-sede",
                                     art_title="Banco de talentos para pessoas com deficiência nas oito cidades-sede"), True)

    def test_news_untouched_by_opportunity_only_gate(self):
        publisher.validate_post({
            "source_type": "noticia",
            "approved": True,
            "image_url": "https://example.org/image.jpg",
            "caption": "📰 Digital Product Manager",
        }, True)


if __name__ == "__main__":
    unittest.main()
