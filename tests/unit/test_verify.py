import unittest
from types import SimpleNamespace

import verify


class VerificationScriptTests(unittest.TestCase):
    def test_nonzero_subcheck_is_propagated_and_stops_execution(self):
        calls = []

        def runner(command, cwd):
            calls.append(command)
            return SimpleNamespace(returncode=7 if len(calls) == 2 else 0)

        status = verify.run_commands([["one"], ["two"], ["three"]], runner=runner)
        self.assertEqual(status, 7)
        self.assertEqual(calls, [["one"], ["two"]])


if __name__ == "__main__":
    unittest.main()
