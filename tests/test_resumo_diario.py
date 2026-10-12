import copy
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("digest", Path(__file__).parents[1] / "scripts/resumo_diario.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW = "2026-10-13T00:00:00Z"  # 21h de 12/10 em Brasília
EMAIL = "subscriber@example.invalid"


def state():
    return {"started_at": "2026-10-12T03:00:00Z", "last_observed_at": "2026-10-12T03:00:00Z",
            "seen": [], "pending": {}, "deliveries": {}, "subscribers_refreshed_at": NOW,
            "unsubscribes_checked_at": NOW, "gmail_unsubscribes_checked_at": NOW,
            "subscribers": {EMAIL: {"subscriptions": {
                k: {"confirmed_at": "2026-10-01T00:00:00Z"} for k in ("events", "news")}}},
            "api_budget": {"used": {"2026-10": 5}, "limits": {"2026-10": 29}, "default_limit": 45}}


def observe(s):
    m.observe(s, [{"ID": "evt-1", "Titulo": "Evento", "Data": "2027-06-24", "Link": "https://example.invalid/event"}],
              [{"Titulo": "Notícia", "Link": "https://example.invalid/news", "Resumo": "Resumo"}], NOW)


class DailyDigestTests(unittest.TestCase):
    def test_combines_topics_one_email_per_local_day(self):
        s = state(); observe(s)
        drafts = m.plan(s, NOW)
        self.assertEqual(len(drafts), 1)
        self.assertEqual(len(drafts[0]["item_keys"]), 2)
        self.assertIn("2026-10-12:", drafts[0]["key"])
        m.reserve(s, drafts[0], NOW)
        self.assertEqual(m.plan(s, NOW), [])
        with self.assertRaises(ValueError): m.finish(s, NOW)
        m.mark_sent(s, drafts[0]["key"], "real-gmail-id", NOW)
        m.finish(s, NOW)
        observe(s)
        self.assertEqual(m.plan(s, NOW), [])

    def test_checkbox_unsubscribe_applies_to_selected_topic(self):
        s = state(); observe(s)
        m.refresh_unsubscribes(s, {"records": [{"cellValuesByFieldId": {
            "fldnfgNsfFRy630Vx": EMAIL, "fldmBNL8o8KRNiJp8": True,
            "fld4HYNbrTRgdxQ18": {"name": "Notícias"}, "flddfJQosqnaN7qNk": {"name": "Pendente"}}}]}, NOW)
        self.assertEqual(m.plan(s, NOW)[0]["item_keys"], ["events:evt-1"])
        s["gmail_unsubscribes"] = {EMAIL: ["events", "news"]}
        self.assertEqual(m.plan(s, NOW), [])

    def test_baseline_and_known_old_publication_are_not_backfill(self):
        s = state(); s["seen"] = ["events:evt-1", "news:https://example.invalid/news"]
        observe(s)
        self.assertEqual(m.plan(s, NOW), [])
        s = state()
        m.observe(s, [], [{"Link": "https://example.invalid/old", "Titulo": "Antiga"}], NOW,
                  {"news:https://example.invalid/old": "2026-10-11T00:00:00Z"})
        self.assertEqual(m.plan(s, NOW), [])

    def test_subscriber_confirmation_is_not_historical_debt(self):
        s = state(); observe(s)
        for sub in s["subscribers"][EMAIL]["subscriptions"].values():
            sub["confirmed_at"] = "2026-10-12T15:00:00Z"
        self.assertEqual(m.plan(s, NOW), [])
        s["pending"]["events:evt-1"]["published_at"] = "2026-10-12T16:00:00Z"
        self.assertEqual(len(m.plan(s, NOW)[0]["item_keys"]), 1)

    def test_incomplete_roster_and_stale_checks_fail_closed(self):
        s = state(); observe(s)
        with self.assertRaises(ValueError):
            m.refresh_unsubscribes(s, {"records": [], "nextCursor": "more"}, NOW)
        with self.assertRaises(ValueError):
            m.refresh_subscribers(s, {"records": [], "metadata": {"totalRecordCount": 1}}, {"records": []}, NOW)
        s["unsubscribes_checked_at"] = "2026-10-12T20:00:00Z"
        with self.assertRaises(ValueError): m.plan(s, NOW)
        s["unsubscribes_checked_at"] = NOW
        s["subscribers_refreshed_at"] = "2026-10-01T00:00:00Z"
        with self.assertRaises(ValueError): m.plan(s, NOW)

    def test_only_active_confirmed_consent_is_cached(self):
        s = state(); f = m.FIELDS["events"]
        good = {"id": "rec-example", "cellValuesByFieldId": {
            f["email"]: EMAIL, f["consent"]: True, f["status"]: {"name": "Ativo"},
            f["confirmation"]: {"name": "Confirmado"}}}
        bad = copy.deepcopy(good); bad["cellValuesByFieldId"][f["consent"]] = False
        m.refresh_subscribers(s, {"records": [bad]}, {"records": [ ]}, NOW)
        self.assertEqual(s["subscribers"], {})
        m.refresh_subscribers(s, {"records": [good]}, {"records": []}, NOW)
        self.assertEqual(list(s["subscribers"][EMAIL]["subscriptions"]), ["events"])

    def test_html_is_escaped_and_unsafe_urls_omitted(self):
        s = state()
        m.observe(s, [{"ID": "x", "Titulo": "<img src=x onerror=alert(1)>", "Link": "javascript:alert(1)"}], [], NOW)
        body = m.plan(s, NOW)[0]["html"]
        self.assertNotIn("<img", body)
        self.assertNotIn("javascript:", body)
        self.assertIn("mailto:", body)

    def test_api_budget_and_public_private_boundary(self):
        s = state(); m.charge_api(s, NOW, 24)
        with self.assertRaises(ValueError): m.charge_api(s, NOW, 1)
        with self.assertRaises(ValueError): m.private_path(Path(__file__).parents[1] / "alertas/private.json")


if __name__ == "__main__":
    unittest.main()
