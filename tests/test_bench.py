import json
import os
import random
import unittest

from trbench import ids
from trbench.__main__ import DATA, PER_TYPE, dump
from trbench.docs import SCHEMAS, VARIANTS, build_dataset
from trbench.score import aggregate, fold, parse_date, parse_decimal, parse_output, score_item


class Ids(unittest.TestCase):
    def test_public_reference_values(self):
        # Examples published by the IBAN registry and a widely used test TCKN.
        self.assertTrue(ids.is_iban("TR33 0006 1005 1978 6457 8413 26"))
        self.assertTrue(ids.is_iban("GB82 WEST 1234 5698 7654 32"))
        self.assertFalse(ids.is_iban("TR34 0006 1005 1978 6457 8413 26"))
        self.assertTrue(ids.is_tckn("10000000146"))
        self.assertFalse(ids.is_tckn("10000000147"))

    def test_generated_ids_are_valid(self):
        rng = random.Random(0)
        for _ in range(200):
            self.assertTrue(ids.is_vkn(ids.make_vkn(rng)))
            self.assertTrue(ids.is_tckn(ids.make_tckn(rng)))
            self.assertTrue(ids.is_iban(ids.make_iban(rng, "90001")))


class Normalisation(unittest.TestCase):
    def test_amounts(self):
        for s in ["1.234,56 TL", "1234.56", "TL 1.234,56", "1,234.56", 1234.56, "1.234,56 ₺"]:
            self.assertEqual(parse_decimal(s), parse_decimal("1234.56"), s)
        self.assertEqual(parse_decimal("%20"), 20)
        self.assertEqual(parse_decimal("1.234"), 1234)

    def test_dates(self):
        for s in ["2026-11-17", "17.11.2026", "17/11/2026", "17 Kasım 2026", "17 Kasim 2026", "17 November 2026"]:
            self.assertEqual(parse_date(s).isoformat(), "2026-11-17", s)
        self.assertIsNone(parse_date("31.02.2026"))

    def test_turkish_fold(self):
        self.assertEqual(fold("IŞIK İnşaat A.Ş."), fold("isik insaat AS"))

    def test_json_parsing(self):
        self.assertEqual(parse_output('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertIsNone(parse_output('Here you go: {"a": 1}'))
        self.assertIsNone(parse_output("[1]"))
        self.assertEqual(parse_output('<thought>hmm {"b": 2}</thought>\n{"a": 1}'), {"a": 1})


class Scoring(unittest.TestCase):
    def setUp(self):
        self.row = next(r for r in build_dataset(2) if r["doc_type"] == "cargo_notice")
        self.gold = self.row["gold"]

    def test_perfect_prediction(self):
        s = score_item("cargo_notice", self.gold, json.dumps(self.gold))
        self.assertEqual((s["fp"], s["fn"], s["halluc"]), (0, 0, 0))
        self.assertEqual(aggregate([s])["f1"], 1.0)

    def test_hallucination_and_invalid_json(self):
        pred = {k: (v if v is not None else "2026-01-01") for k, v in self.gold.items()}
        pred["extra_field"] = "x"
        s = score_item("cargo_notice", self.gold, json.dumps(pred))
        nulls = sum(v is None for v in self.gold.values())
        self.assertEqual(s["halluc"], nulls + 1)
        bad = score_item("cargo_notice", self.gold, "not json")
        self.assertFalse(bad["json_valid"])
        self.assertEqual(bad["fn"], sum(v is not None for v in self.gold.values()))


class Dataset(unittest.TestCase):
    def test_committed_dataset_is_reproducible(self):
        with open(DATA, encoding="utf-8") as f:
            self.assertEqual(f.read(), dump(build_dataset(PER_TYPE)))

    def test_shape(self):
        rows = build_dataset(PER_TYPE)
        self.assertEqual(len(rows), 4 * PER_TYPE * len(VARIANTS))
        for r in rows:
            self.assertEqual(set(r["gold"]), {n for n, _, _ in SCHEMAS[r["doc_type"]]})
            self.assertTrue(r["synthetic"])
        # every optional field is null somewhere, so the hallucination metric can fire
        for t, schema in SCHEMAS.items():
            for name, _, desc in schema:
                if "null" in desc:
                    self.assertTrue(any(r["gold"][name] is None for r in rows if r["doc_type"] == t), name)

    def test_ascii_variant_has_no_turkish_letters(self):
        for r in build_dataset(1):
            if r["variant"] == "ascii":
                self.assertFalse(set(r["text"]) & set("ıİşŞğĞüÜöÖçÇ"))


if __name__ == "__main__":
    unittest.main()
