"""One client must never see another client's jobs, and never dictate its own identity.

Adapted from the SDK scaffold test: the operation changed, the property being checked did
not. It matters more here than in the scaffold, because a job's outputs can contain a whole
character sheet.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tool import create_runtime                                     # noqa: E402


class IsolationTests(unittest.TestCase):
    def test_jobs_are_private_to_their_client(self):
        with tempfile.TemporaryDirectory() as root, create_runtime(root) as runtime:
            alice = runtime.authenticate(runtime.create_client('Alice')['token'])
            bob = runtime.authenticate(runtime.create_client('Bob')['token'])
            session = runtime.create_session(alice)
            job = runtime.submit(alice, session['sessionId'], 'list_personas', {})
            result = runtime.wait(alice, job['jobId'])
            self.assertEqual(result['state'], 'Completed')
            self.assertIn('personas', result['outputs'])
            self.assertEqual(runtime.list_jobs(bob), [])

    def test_every_declared_operation_has_a_handler(self):
        with tempfile.TemporaryDirectory() as root, create_runtime(root) as runtime:
            declared = {operation['id'] for operation in runtime.descriptor['operations']}
            self.assertEqual(declared - set(runtime._handlers), set())


if __name__ == '__main__':
    unittest.main()
