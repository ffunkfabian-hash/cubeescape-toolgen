"""The shared contract schema (ce_contract, 0.22) and the frozen contract formats 1-3 of `--contract`."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolgen"))
sys.path.insert(0, str(ROOT / "scripts"))
import shared_tools  # noqa: E402
import generate_tools  # noqa: E402

ce_contract = shared_tools.use("ce_contract")


class ContractSchemaTests(unittest.TestCase):
    def test_old_formats_have_no_shared_schema(self):
        # Codex review of the Lockstep merge: the v4 schema allows format 4 and 5 only, --contract 1-3 is still offered.
        lowest = min(int(p.stem.rsplit(".v", 1)[1]) for p in ce_contract.CONTRACTS.glob("unity_contract.v*.json"))
        self.assertEqual(lowest, 4)
        older = [contract for contract in generate_tools.CONTRACTS if contract < lowest]
        self.assertEqual(older, [1, 2, 3])
        name = ce_contract.schema_for({"format": 3}, Path("unity_contract.json"))
        schema = ce_contract.load_schema(name)
        self.assertTrue(ce_contract.validate({"format": 3}, schema, schema), "v4 schema rejects format 3")

    def test_verify_output_validates_only_formats_with_a_schema(self):
        source = (ROOT / "scripts/verify_output.py").read_text(encoding="utf-8")
        guard = source.index('if document["format"] >= SHARED_SCHEMA_MIN_FORMAT:')
        self.assertLess(guard, source.index("ce_contract.check_file(path, None)"))


if __name__ == "__main__":
    unittest.main()
