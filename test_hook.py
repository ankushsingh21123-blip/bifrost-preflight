import subprocess
import unittest
from unittest.mock import patch
from precommit_entry import main

class HookTests(unittest.TestCase):
    def test_empty(self):
        with patch('precommit_entry.subprocess.run') as run:
            self.assertEqual(main([]),0)
            run.assert_not_called()
    def test_defined_statuses(self):
        for code in (0,1,2):
            with self.subTest(code=code), patch('precommit_entry.subprocess.run',return_value=subprocess.CompletedProcess([],code)):
                self.assertEqual(main(['config.json']),code)
    def test_signal_and_unexpected_statuses_fail_closed(self):
        for code in (-9,-15,3,127,None,False):
            with self.subTest(code=code), patch('precommit_entry.subprocess.run',return_value=subprocess.CompletedProcess([],code)):
                self.assertEqual(main(['config.json']),2)
    def test_mixed_signal_then_good(self):
        with patch('precommit_entry.subprocess.run',side_effect=[subprocess.CompletedProcess([],-9),subprocess.CompletedProcess([],0)]):
            self.assertEqual(main(['a/config.json','b/config.json']),2)
    def test_spawn_failure(self):
        with patch('precommit_entry.subprocess.run',side_effect=OSError('private detail')):
            self.assertEqual(main(['config.json']),2)

if __name__=='__main__': unittest.main()
