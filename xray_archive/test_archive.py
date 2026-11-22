import unittest
from pathlib import Path
from unittest.mock import patch

import archive


def fixture(name):
    return patch("archive.fetch", return_value=(Path(__file__).parent / "fixtures" / name).read_bytes())


class ArchiveTests(unittest.TestCase):
    def test_rosat(self):
        with fixture("ros.xml") as fetch:
            result = archive.query_survey("rosat", 187.2779, 2.0524)
        params = fetch.call_args.args[1]
        self.assertEqual(params["-source"], "J/A+A/588/A103/cat2rxs")
        self.assertEqual(params["-c.rs"], 90)
        self.assertEqual(result["matches"][0]["count_rate_cps"], 7.8635)

    def test_erosita_limit(self):
        with fixture("eros.xml") as fetch:
            result = archive.query_survey("erosita", 140.7857, -61.7383, limit=1)
        self.assertEqual(fetch.call_args.args[1]["-out.max"], 2)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches"][0]["flux"], 1.55737944e-13)

    def test_empty_catalogue(self):
        with fixture("no_match.xml"):
            self.assertEqual(archive.query_survey("erosita", 15.234, 5.678, 1)["matches"], [])

    def test_hiligt_detection(self):
        with fixture("response.json"):
            row, = archive.query_hiligt(187.2779, 2.0524, "RosatSurvey")["observations"]
        self.assertIsNone(row["flux_upper_limit"])
        self.assertGreater(row["flux"], 0)
        self.assertEqual(row["obsid"], "931734")

    def test_hiligt_upper_limit(self):
        with fixture("limit.json") as fetch:
            row, = archive.query_hiligt(15.234, 5.678, "RosatSurvey")["observations"]
        self.assertEqual(fetch.call_args.args[1]["ulsig"], 3)
        self.assertIsNone(row["flux"])
        self.assertEqual(row["flux_upper_limit"], 3.4435681839e-13)
        self.assertEqual(row["band_keV"], [0.2, 2.0])

    def test_no_observation(self):
        with fixture("empty.json"):
            self.assertEqual(archive.query_hiligt(15.234, 5.678)["observations"], [])

    def test_archive_errors(self):
        with patch("archive.fetch", return_value=b'[{"_status":"Failed"}]'), self.assertRaises(ValueError):
            archive.query_hiligt(10, 20)
        with patch("archive.fetch", return_value=b'<VOTABLE><INFO name="Error"/></VOTABLE>'), self.assertRaises(ValueError):
            archive.query_survey("rosat", 10, 20)

    def test_invalid_inputs(self):
        with patch("archive.fetch") as fetch:
            for call in (lambda: archive.query_survey("rosat", float("nan"), 0),
                         lambda: archive.query_survey("erosita", 0, 0, -1),
                         lambda: archive.query_hiligt(360, 90),
                         lambda: archive.query_hiligt(0, 0, mission="unknown")):
                with self.assertRaises(ValueError):
                    call()
            fetch.assert_not_called()
