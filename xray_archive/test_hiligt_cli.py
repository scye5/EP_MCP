import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import hiligt


class HiLIGTCommandTests(unittest.TestCase):
    def test_blackbody_upper_limit(self):
        response = (Path(__file__).parent / "fixtures" / "limit.json").read_bytes()
        argv = ["hiligt.py", "query", "15.234", "5.678", "--mission", "RosatSurvey",
                "--blackbody-ev", "100", "--no-catalogue"]
        with patch("sys.argv", argv), patch("archive.fetch", return_value=response) as fetch:
            with redirect_stdout(io.StringIO()) as output:
                hiligt.main()
        params = fetch.call_args.args[1]
        self.assertEqual((params["model"], params["specparam"], params["usecat"]), ("bbody", 0.1, "no"))
        row, = json.loads(output.getvalue())["observations"]
        self.assertGreater(row["count_rate_upper_limit_cps"], 0)
        self.assertIsNone(row["count_rate_cps"])
