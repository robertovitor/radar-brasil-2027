"""Regressão da contenção Airtable, sem chamadas externas."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(filename):
    spec = importlib.util.spec_from_file_location('pesquisa_test', ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicResearchTests(unittest.TestCase):
    def test_full_compatibility_chain_publishes_without_airtable_or_token(self):
        # Mesmo uma liberação acidental do Airtable não prevalece sobre modo público.
        with patch.dict(os.environ, {'RADAR_PUBLIC_ONLY': '1', 'RADAR_AIRTABLE_ALLOW': '1',
                                     'AIRTABLE_TOKEN': 'unused-test-token'}):
            compat = load_module('pesquisa_editorial_compat_v5_5.py')
            pe = compat.pe
            self.assertEqual(pe.TOKEN, '')
            with tempfile.TemporaryDirectory() as directory:
                pe.ROOT = Path(directory)
                pe.INBOX = pe.ROOT / 'editorial/inbox.json'
                pe.STATUS = pe.ROOT / 'editorial/pesquisa-status.json'
                preserved = {'Titulo': 'Evento já no inbox', 'Data': '2027-01-01'}
                compat._original_dump(pe.INBOX, {'eventos': [preserved], 'noticias': []})
                news = {'Titulo': 'Notícia pública', 'Link': 'https://www.cbf.com.br/noticia'}
                event = {'Titulo': 'Amistoso feminino', 'Data': '2027-03-01', 'Cidade': 'Recife'}
                pe._v55_official_events = [event]
                with patch.object(pe, 'airtable_read', side_effect=AssertionError('Airtable read')), \
                     patch.object(pe, 'airtable_patch', side_effect=AssertionError('Airtable write')), \
                     patch.object(pe, 'public_research', return_value=(1, [news], 0, 0, [])) as research, \
                     patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected network')), \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(pe.main(), 0)
                    compat._materialize_official_events()
                    compat._materialize_official_events()
                research.assert_called_once()
                inbox = json.loads(pe.INBOX.read_text())
                self.assertEqual(inbox['noticias'], [news])
                self.assertEqual(inbox['eventos'], [preserved, event])
                status = json.loads(pe.STATUS.read_text())
                self.assertEqual(status['stage'], 'completed')
                self.assertEqual(status['modo'], 'publico_sem_airtable')
                self.assertTrue(status['sugestoes_airtable_suspensas'])
                self.assertEqual(status['airtable_reads_total'], 0)
                self.assertEqual(status['airtable_reads'], [])
                self.assertEqual(status['sugestoes_lidas'], 0)
                self.assertEqual(status['sugestoes_noticias_lidas'], 0)
                with patch('urllib.request.urlopen') as network:
                    for operation in (lambda: pe.airtable_read(pe.TABLE_EVENTS),
                                      lambda: pe.airtable_patch(pe.TABLE_EVENTS, 'recTest', {'Status': 'Aprovado'}),
                                      lambda: pe.request_json('https://api.airtable.com/v0/test')):
                        with self.assertRaisesRegex(RuntimeError, 'modo de pesquisa publica'):
                            operation()
                    network.assert_not_called()

    def test_legacy_entry_point_remains_stopped(self):
        with patch.dict(os.environ, {'RADAR_PUBLIC_ONLY': '0', 'RADAR_AIRTABLE_ALLOW': '0'}), \
             patch('urllib.request.urlopen') as network, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                load_module('pesquisa_editorial_compat_v5_5.py')
            self.assertEqual(stopped.exception.code, 0)
            network.assert_not_called()

    def test_public_workflow_has_no_airtable_secret_or_alert_queue(self):
        workflow = (ROOT / '.github/workflows/pesquisa-editorial.yml').read_text()
        self.assertIn('cron: "45 * * * *"', workflow)
        self.assertIn("RADAR_PUBLIC_ONLY: '1'", workflow)
        self.assertIn("RADAR_AIRTABLE_ALLOW: '0'", workflow)
        self.assertNotIn('AIRTABLE_TOKEN', workflow)
        self.assertNotIn('enfileirar_alertas', workflow)
        self.assertIn('python scripts/pesquisa_oportunidades.py', workflow)
        alerts = (ROOT / '.github/workflows/enfileirar-alertas.yml').read_text()
        self.assertNotIn('  schedule:', alerts)
        self.assertNotIn('  push:', alerts)


if __name__ == '__main__':
    unittest.main()
