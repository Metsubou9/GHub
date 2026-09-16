import os
import sys
import unittest
import sqlite3
from datetime import datetime, timezone

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.config_loader import load_games_config, load_optimizer_config, get_base_dir
from core.game_detector import entry_for, ping_hosts_for, settings_for
from core.collector_abstract import Sample
from modules.optimizer.profiles import get_optimizer
from main import fmt


class TestConfigLoader(unittest.TestCase):
    def test_get_base_dir(self):
        base = get_base_dir()
        self.assertTrue(os.path.isdir(base))
        self.assertTrue(os.path.exists(os.path.join(base, 'config', 'games.yaml')))

    def test_load_games_config(self):
        cfg = load_games_config()
        self.assertIn('games', cfg)
        self.assertIn('profiles', cfg)
        self.assertIn('defaults', cfg)
        self.assertTrue(len(cfg['games']) > 0)

    def test_load_optimizer_config(self):
        opt = load_optimizer_config()
        self.assertIn('profiles', opt)
        profiles = opt['profiles']
        self.assertIn('default', profiles)
        self.assertIn('performance', profiles)
        self.assertIn('aggressive', profiles)


class TestGameDetector(unittest.TestCase):
    def setUp(self):
        self.cfg = load_games_config()

    def test_entry_for_known_game(self):
        entry = entry_for(self.cfg, 'osu!')
        self.assertIsNotNone(entry)
        self.assertEqual(entry.get('name'), 'osu!')
        self.assertIn('osu!.exe', entry.get('processes', []))

    def test_entry_for_unknown_game(self):
        entry = entry_for(self.cfg, 'NonExistentGame123')
        self.assertIsNone(entry)

    def test_settings_for_singleplayer(self):
        entry = entry_for(self.cfg, 'osu!')
        sett = settings_for(self.cfg, entry)
        self.assertEqual(sett.get('net'), 'off')
        self.assertTrue(sett.get('frame_ms'))

    def test_settings_for_multiplayer(self):
        entry = entry_for(self.cfg, 'Dota 2')
        sett = settings_for(self.cfg, entry)
        self.assertEqual(sett.get('net'), 'match')

    def test_ping_hosts(self):
        hosts = ping_hosts_for(self.cfg, 'Dota 2')
        self.assertTrue(isinstance(hosts, list))
        self.assertTrue(len(hosts) > 0)


class TestFormat(unittest.TestCase):
    def test_fmt_idle(self):
        s = Sample(fps=None, cpu_pct=15.0, cpu_temp=45.0, gpu_pct=20.0, gpu_temp=50.0)
        res = fmt(s, None, None)
        self.assertIn('idle', res)
        self.assertIn('FPS --', res)
        self.assertIn('CPU 15.0% 45.0C', res)
        self.assertIn('GPU 50.0C 20.0%', res)

    def test_fmt_active_game(self):
        s = Sample(fps=144.0, ping_ms=25.0, loss_pct=0.0, cpu_pct=30.0, cpu_temp=55.0, gpu_pct=70.0, gpu_temp=62.0)
        entry = {'name': 'Dota 2', 'net': 'match'}
        res = fmt(s, 'Dota 2', entry, frame_ms=6.94, match_ip='146.66.155.1')
        self.assertIn('Dota 2', res)
        self.assertIn('FPS 144.0', res)
        self.assertIn('PING 25.0ms loss 0.0% (match)', res)


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        schema_path = os.path.join(BASE_DIR, 'core', 'schema.sql')
        with open(schema_path, encoding='utf-8') as f:
            self.con.executescript(f.read())
        # Migration test
        cols = [r[1] for r in self.con.execute('PRAGMA table_info(samples)')]
        if 'frame_ms' not in cols:
            self.con.execute('ALTER TABLE samples ADD COLUMN frame_ms REAL')
            self.con.commit()

    def tearDown(self):
        self.con.close()

    def test_session_lifecycle(self):
        from core.storage import start_session, end_session, insert_sample
        sid = start_session(self.con, 'TestGame', 'test.exe')
        self.assertIsInstance(sid, int)

        s = Sample(fps=60.0, ping_ms=30.0, loss_pct=0.0, cpu_pct=10.0, frame_ms=16.6)
        insert_sample(self.con, sid, s)

        row = self.con.execute('SELECT COUNT(*), AVG(fps), AVG(frame_ms) FROM samples WHERE session_id=?', (sid,)).fetchone()
        self.assertEqual(row[0], 1)
        self.assertAlmostEqual(row[1], 60.0)
        self.assertAlmostEqual(row[2], 16.6, places=1)

        end_session(self.con, sid)
        sess = self.con.execute('SELECT started_at, ended_at FROM sessions WHERE id=?', (sid,)).fetchone()
        self.assertIsNotNone(sess[0])
        self.assertIsNotNone(sess[1])


class TestOptimizer(unittest.TestCase):
    def test_get_optimizer(self):
        opt = get_optimizer()
        self.assertIsNotNone(opt)

    def test_apply_profile_non_existent(self):
        opt = get_optimizer()
        # Should not raise exception
        opt.apply_profile('non_existent_proc_xyz_99999.exe', {'priority': 'high', 'affinity': [0, 1]})


if __name__ == '__main__':
    unittest.main()
