"""Regressões cirúrgicas da fila editorial; não usa rede, Airtable nem Meta."""
import datetime as dt
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import preparar_post_instagram_curado as editorial


def today_brt():
    return dt.datetime.now(ZoneInfo("America/Sao_Paulo")).date()


class InstagramEventSelectionTests(unittest.TestCase):
    def test_event_administrative_date_does_not_expire_future_event(self):
        today = today_brt()
        future = today + dt.timedelta(days=15)
        received = today - dt.timedelta(days=2)
        event = {
            "Data": future.isoformat(),
            "Titulo": "Evento de futebol feminino rumo à Copa de 2027",
            "Observacoes": (
                "Programação para a Copa Feminina; etapas até a Copa 2027. "
                f"Sugestão recebida em {received:%d/%m/%Y}."
            ),
        }
        self.assertEqual(
            editorial.stale_operational_date("evento", event, today),
            (None, ""),
        )

    def test_expired_event_or_structured_deadline_stays_blocked(self):
        today = today_brt()
        past = (today - dt.timedelta(days=1)).isoformat()
        future = (today + dt.timedelta(days=15)).isoformat()
        self.assertEqual(
            editorial.stale_operational_date("evento", {"Data": past}, today)[1],
            "event_date_passed",
        )
        self.assertEqual(
            editorial.stale_operational_date(
                "evento", {"Data": future, "PrazoInscricao": past}, today
            )[1],
            "application_deadline_passed",
        )

    def test_youth_and_explicit_exclusion_stay_out_of_instagram(self):
        self.assertTrue(editorial.base({
            "Titulo": "Em Busca da Camisa #1 — etapa de Americana",
            "Categoria": "Capacitação e formação no futebol feminino",
            "Observacoes": (
                "Atividade de categorias de base: não tratar como pauta "
                "de Instagram da Seleção principal."
            ),
        }))
        self.assertTrue(editorial.base({
            "Titulo": "Seleção feminina Sub-17 disputa amistoso",
        }))
        self.assertFalse(editorial.base({
            "Titulo": "Encontro de torcedores para a Copa Feminina 2027",
            "Categoria": "Ativação de torcida",
        }))

    def test_recent_new_event_precedes_newer_news(self):
        today = today_brt()
        event = {
            "ID": "EVT-TEST-RECENT",
            "Titulo": "Ativação de torcedores para a Copa Feminina 2027",
            "Data": (today + dt.timedelta(days=12)).isoformat(),
            "Observacoes": "Encontro aberto ao público.",
        }
        news = {
            "Titulo": "Novos preparativos para a Copa Feminina 2027",
            "Data": today.isoformat(),
            "Link": "https://example.org/news-recent",
            "Resumo": "Planejamento das cidades-sede.",
            "Veiculo": "Portal",
        }
        pending = [
            "instagram:evento:evt-test-recent",
            "instagram:noticia:https://example.org/news-recent",
        ]
        ranked = editorial.candidates([event], [news], [], set(), pending)
        self.assertEqual([r["type"] for r in ranked], ["evento", "noticia"])

    def test_old_backlog_event_not_promoted_in_front_of_new_news(self):
        today = today_brt()
        event = {
            "ID": "EVT-TEST-OLD",
            "Titulo": "Encontro de torcedores para a Copa Feminina 2027",
            "Data": (today + dt.timedelta(days=20)).isoformat(),
        }
        news = {
            "Titulo": "Copa Feminina 2027 anuncia nova ação",
            "Data": today.isoformat(),
            "Link": "https://example.org/news-new",
            "Veiculo": "Portal",
        }
        pending = (
            ["instagram:evento:evt-test-old"]
            + [f"instagram:noticia:placeholder-{i}" for i in range(41)]
            + ["instagram:noticia:https://example.org/news-new"]
        )
        ranked = editorial.candidates([event], [news], [], set(), pending)
        self.assertEqual([r["type"] for r in ranked], ["noticia", "evento"])

    def test_opportunity_eligibility_unchanged(self):
        today = today_brt()
        opportunity = {
            "ID": "OPP-TEST",
            "Titulo": "FIFA abre oportunidade de trabalho",
            "Link": "https://example.org/jobs",
            "Status": "Inscrições abertas",
            "PrazoInscricao": (today + dt.timedelta(days=10)).isoformat(),
            "DataDescoberta": today.isoformat(),
        }
        ranked = editorial.candidates([], [], [opportunity], set(), [
            "instagram:oportunidade:opp-test",
        ])
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["type"], "oportunidade")


if __name__ == "__main__":
    unittest.main()
