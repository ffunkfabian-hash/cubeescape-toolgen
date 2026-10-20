"""Concept geometry of cubeescape-formgen (Toolgen 0.18, TG-A): import with provenance, the loader's checks and Toolgen's
rules on top of the spec (scripts/import_concepts.py, scripts/tool_assets/concept_spec.py). Pure Python, no Blender."""
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts/tool_assets"))
sys.path.insert(0, str(ROOT / "toolgen"))

import concept_spec  # noqa: E402
import import_concepts  # noqa: E402
import weapon_designs as designs  # noqa: E402
import generate_tools  # noqa: E402
from generate_tools import CONCEPTS, SourceIndex, catalog, expand, stage_sources  # noqa: E402

FOLDER = ROOT / CONCEPTS
TOOLS = {tool["id"]: tool for tool in catalog()}
PROFILES = json.loads((ROOT / "data/viewmodels.json").read_text())["tools"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ProvenanceTests(unittest.TestCase):
    def test_imported_sheets_match_their_provenance(self):
        self.assertEqual([], import_concepts.check(FOLDER))

    def test_provenance_names_the_release_and_every_file_hash(self):
        record = concept_spec.provenance(FOLDER)
        # KG02 since claude-v0.15 (formgen 143e542: the bolt lever p32, DS 0.15 "Rackshot"); claude-v0.14 had 295b5149...
        source = record["releases"]["claude-v0.15"]
        self.assertEqual("ffunkfabian-hash/cubeescape-formgen", source["repository"])
        self.assertEqual(("claude-v0.15", "143e542"), (source["release"], source["commit"]))
        self.assertEqual("8a4bc0d0a4cd71136eaa173ba81808714aca8b4f53f856f69d6e8e83b68e48fa", source["asset_sha256"])
        self.assertEqual("1940d929b383dcde1d5902c1248dae1a7e973cf84600b7a1242c1eb7020b41f8", record["imported"]["KG02"]["sha256"])
        self.assertEqual(("cubeescape-design/geometry-spec", 1), (source["format"], source["format_version"]))
        self.assertEqual(159, len(source["files"]))
        self.assertEqual(source["asset_files"], len(source["files"]))
        for sheet, entry in record["imported"].items():
            self.assertEqual(record["releases"][entry["release"]]["files"][sheet], entry["sha256"])

    def test_every_concept_weapon_has_its_sheet(self):
        self.assertEqual({"assault_rifle": "KG02"}, designs.DESIGN_PICK)
        imported = concept_spec.provenance(FOLDER)["imported"]
        for tool_id, sheet in designs.DESIGN_PICK.items():
            with self.subTest(tool=tool_id):
                self.assertEqual(tool_id, imported[sheet]["toolgen_id"])
                self.assertEqual("G", imported[sheet]["variant"])     # formgen plan decision 1 (19.10.2026)
                self.assertEqual(sheet, TOOLS[tool_id]["concept"])


class LoaderTests(unittest.TestCase):
    def copy_folder(self, change=None, entry=None):
        folder = Path(tempfile.mkdtemp())
        data = (FOLDER / "KG02.geo.json").read_bytes()
        if change:
            spec = json.loads(data)
            change(spec)
            data = json.dumps(spec).encode()
        (folder / "KG02.geo.json").write_bytes(data)
        record = concept_spec.provenance(FOLDER)
        record["imported"]["KG02"]["sha256"] = entry or sha(data)
        (folder / concept_spec.PROVENANCE).write_text(json.dumps(record))
        return folder

    def test_a_changed_file_is_refused(self):
        folder = self.copy_folder(lambda spec: spec["parts"][0].update(color="#FFFFFF"),
                                  entry=concept_spec.provenance(FOLDER)["imported"]["KG02"]["sha256"])
        with self.assertRaises(concept_spec.ConceptError):
            concept_spec.load("KG02.geo.json", folder)

    def test_another_format_version_is_refused(self):
        folder = self.copy_folder(lambda spec: spec.update(format_version=2))
        with self.assertRaises(concept_spec.ConceptError):
            concept_spec.load("KG02.geo.json", folder)

    def test_unknown_fields_are_ignored(self):
        folder = self.copy_folder(lambda spec: spec.update(future_block={"x": 1}))
        meshes, _ = concept_spec.plan(concept_spec.load("KG02.geo.json", folder))
        reference, _ = concept_spec.plan(concept_spec.load("KG02.geo.json"))
        self.assertEqual(json.dumps(reference, sort_keys=True), json.dumps(meshes, sort_keys=True))

    def test_a_file_without_provenance_is_refused(self):
        with self.assertRaises(concept_spec.ConceptError):
            concept_spec.load("KG05.geo.json")


class ImportTests(unittest.TestCase):
    """import_concepts.py reads a local copy of the release asset; hashes are checked before anything is written."""

    def fake_release(self, folder, content=None):
        data = (FOLDER / "KG02.geo.json").read_bytes() if content is None else content
        other = json.loads((FOLDER / "KG02.geo.json").read_bytes())
        other["sheet"]["id"] = "KG03"
        other = json.dumps(other).encode()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("geo/KG02.geo.json", data)
            archive.writestr("geo/KG03.geo.json", other)
        path = folder / "claude-geo-test.zip"
        path.write_bytes(buffer.getvalue())
        golden = folder / "golden.json"
        golden.write_text(json.dumps({"geo": {"KG02": sha((FOLDER / "KG02.geo.json").read_bytes()), "KG03": sha(other)}}))
        return path, golden

    def test_import_writes_the_sheet_and_its_provenance(self):
        folder = Path(tempfile.mkdtemp())
        path, golden = self.fake_release(folder)
        target = folder / "concepts"
        record = import_concepts.import_sheets(path, ["KG02"], "test-release", "abc1234", sha(path.read_bytes()), golden,
                                               today="2026-10-20", folder=target)
        self.assertEqual((FOLDER / "KG02.geo.json").read_bytes(), (target / "KG02.geo.json").read_bytes())
        self.assertEqual("test-release", record["imported"]["KG02"]["release"])
        self.assertEqual([], import_concepts.check(target))

    def test_sheets_of_two_releases_keep_their_provenance(self):
        """Sightline 20.10.2026: KG02 from claude-v0.15, the other sheets stay claude-v0.14 (codex sol finding)."""
        folder = Path(tempfile.mkdtemp())
        target = folder / "concepts"
        path, golden = self.fake_release(folder)
        import_concepts.import_sheets(path, ["KG03"], "old", "abc1234", sha(path.read_bytes()), golden, folder=target)
        newer = folder / "new"
        newer.mkdir()
        path2, golden2 = self.fake_release(newer)
        record = import_concepts.import_sheets(path2, ["KG02"], "new", "def5678", sha(path2.read_bytes()), golden2,
                                               folder=target)
        self.assertEqual({"KG02": "new", "KG03": "old"}, {k: v["release"] for k, v in record["imported"].items()})
        self.assertEqual({"new", "old"}, set(record["releases"]))
        self.assertEqual([], import_concepts.check(target))

    def test_nothing_is_written_when_a_later_sheet_fails(self):
        folder = Path(tempfile.mkdtemp())
        path, golden = self.fake_release(folder)
        with self.assertRaises(SystemExit):
            import_concepts.import_sheets(path, ["KG02", "KG99"], "test-release", "abc1234", sha(path.read_bytes()), golden,
                                          folder=folder / "c")
        self.assertFalse((folder / "c" / "KG02.geo.json").exists())

    def test_a_wrong_zip_hash_is_refused(self):
        folder = Path(tempfile.mkdtemp())
        path, golden = self.fake_release(folder)
        with self.assertRaises(SystemExit):
            import_concepts.import_sheets(path, ["KG02"], "test-release", "abc1234", "0" * 64, golden, folder=folder / "c")
        self.assertFalse((folder / "c").exists())

    def test_a_file_off_the_golden_list_is_refused(self):
        folder = Path(tempfile.mkdtemp())
        path, golden = self.fake_release(folder, content=b'{"format": "cubeescape-design/geometry-spec"}')
        with self.assertRaises(SystemExit):
            import_concepts.import_sheets(path, ["KG02"], "test-release", "abc1234", sha(path.read_bytes()), golden,
                                          folder=folder / "c")


class PlanTests(unittest.TestCase):
    """Toolgen's rules on top of the spec (docs/TECHNIK.md › Konzeptmodelle)."""

    @classmethod
    def setUpClass(cls):
        cls.spec = concept_spec.load("KG02.geo.json")
        cls.meshes, cls.report = concept_spec.plan(copy.deepcopy(cls.spec))

    def test_the_plan_is_deterministic(self):
        again, report = concept_spec.plan(concept_spec.load("KG02.geo.json"))
        self.assertEqual(json.dumps(self.meshes, sort_keys=True), json.dumps(again, sort_keys=True))
        self.assertEqual(json.dumps(self.report, sort_keys=True), json.dumps(report, sort_keys=True))

    def test_glass_is_left_out_and_the_window_open(self):
        glass = [part["id"] for part in self.spec["parts"] if part["glass"]]
        self.assertEqual(["p28"], glass)
        self.assertEqual(glass, self.report["glass_omitted"])
        self.assertFalse(any(set(glass) & set(mesh["ids"]) for mesh in self.meshes))

    def test_every_mesh_is_closed_with_outward_normals(self):
        for mesh in self.meshes:
            with self.subTest(mesh=mesh["name"]):
                self.assertTrue(concept_spec.is_closed(mesh["faces"]))
                self.assertGreater(concept_spec.volume(mesh["vertices"], mesh["faces"]), 0)
                self.assertEqual(len(mesh["faces"]), len(mesh["hard"]))

    def test_open_parts_are_merged_with_their_look_and_closed_parts_stay_alone(self):
        self.assertEqual([["p24", "p25", "p26", "p27"]], self.report["merged"])
        ids = [part_id for mesh in self.meshes for part_id in mesh["ids"]]
        self.assertEqual(sorted(part["id"] for part in self.spec["parts"] if not part["glass"]), sorted(ids))
        for mesh in self.meshes:
            parts = [part for part in self.spec["parts"] if part["id"] in mesh["ids"]]
            self.assertEqual(1, len({concept_spec.look(part) for part in parts}), mesh["ids"])

    def test_late_resolution_returns_a_list(self):
        """codex sol finding: a resolution that needs the last pass returned the fix dictionary instead of the list."""
        box = lambda name, x0: {"name": name, "faces": [[0, 1, 2, 3], [4, 7, 6, 5], [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3],
                                                        [3, 7, 4, 0]],
                                "vertices": [[x0, 0, 0], [x0 + .01, 0, 0], [x0 + .01, .01, 0], [x0, .01, 0],
                                             [x0, 0, .01], [x0 + .01, 0, .01], [x0 + .01, .01, .01], [x0, .01, .01]]}
        meshes = [box("a", 0.0), box("b", 0.0)]
        for mesh in meshes:
            mesh["faces"] = [list(reversed(face)) for face in mesh["faces"]]
        fixes = concept_spec.resolve_coplanar(meshes)
        self.assertIsInstance(fixes, list)
        self.assertEqual([], concept_spec.coplanar_pairs(meshes))
        json.dumps(fixes)

    def test_no_coplanar_faces_remain(self):
        self.assertEqual([], concept_spec.coplanar_pairs(self.meshes))
        self.assertEqual(["SM_PG_Part_p05"], [fix["moved"] for fix in self.report["coplanar_fixes"]])
        self.assertEqual(6, self.report["coplanar_fixes"][0]["faces"])          # the spec's finding: 6 face pairs
        self.assertEqual(["p04", "p05"], self.spec["checks"]["coplanar"][0]["parts"])

    def test_the_coplanar_rule_finds_the_spec_finding(self):
        raw = []
        for part in self.spec["parts"]:
            if part["id"] in ("p04", "p05"):
                raw.append({"name": part["name"], "vertices": [list(v) for v in part["mesh"]["vertices"]],
                            "faces": part["mesh"]["faces"]})
        self.assertTrue(concept_spec.coplanar_pairs(raw))

    def test_bevels_follow_the_part_size(self):
        for mesh in self.meshes:
            with self.subTest(mesh=mesh["name"]):
                if mesh["glow"]:
                    self.assertEqual(0.0, mesh["bevel_m"])
                else:
                    self.assertTrue(0 < mesh["bevel_m"] <= concept_spec.BEVEL_MAX_M)
        widths = {mesh["name"]: mesh["bevel_m"] for mesh in self.meshes}
        self.assertEqual(concept_spec.BEVEL_MAX_M, widths["SM_PG_Gehaeuse_p09"])   # housing 2 mm
        self.assertEqual(concept_spec.BEVEL_MIN_M, widths["SM_PG_Visierschiene_p15"])   # small parts 0.5 mm

    def test_materials_cover_the_channels(self):
        self.assertEqual(set(concept_spec.CHANNELS), {"MT_Primary", "MT_Secondary", "MT_Accent", "MT_Metal", "MT_Detail",
                                                      "MT_Emission", "MT_Energy"})
        for mesh in self.meshes:
            self.assertEqual(concept_spec.CHANNELS[mesh["channel"]], mesh["material"])

    def test_the_window_frame_gets_no_collider(self):
        self.assertEqual(["SM_PG_Rahmen_p24"], self.report["no_collision"])

    def test_the_magazine_hangs_under_the_reload_node(self):
        found = concept_spec.layout("KG02.geo.json", ["Anim_Bolt"])
        self.assertEqual([], found["empty"])     # claude-v0.15: the bolt lever p32 (moving bolt) hangs under Anim_Bolt
        nodes = {mesh["name"]: mesh["node"] for mesh in found["meshes"] if mesh["node"]}
        self.assertEqual({"SM_PG_Magazin_p07": "Anim_Magazine", "SM_PG_Ladehebel_p32": "Anim_Bolt"}, nodes)


class SocketTests(unittest.TestCase):
    def test_sockets_follow_toolgens_rules(self):
        spec = concept_spec.load("KG02.geo.json")
        found = concept_spec.sockets(spec)
        self.assertEqual(spec["sight"]["socket_sight_rear_m"], found["Socket_Sight"])
        self.assertNotEqual(spec["anchors"]["Socket_Sight"]["position_m"], found["Socket_Sight"], "rail top is not the sight")
        self.assertEqual(spec["sight"]["socket_reticle_m"], found["Socket_Reticle"])
        self.assertNotIn("Socket_Eye", found, "Socket_Eye only for scopes")
        for name in ("Socket_Hand", "Socket_Muzzle", "Socket_CenterOfMass", "Socket_SupportHand"):
            self.assertEqual(spec["anchors"][name]["position_m"], found[name])

    def test_a_scope_gets_its_eye(self):
        spec = copy.deepcopy(concept_spec.load("KG02.geo.json"))
        spec["sight"]["kind"] = "scope"
        self.assertEqual(spec["sight"]["socket_eye_m"], concept_spec.sockets(spec)["Socket_Eye"])

    def test_the_hold_data_is_the_measured_concept(self):
        spec = concept_spec.load("KG02.geo.json")
        hold = concept_spec.hold(spec)
        self.assertEqual(hold["grip_tilt_degrees"], designs.DESIGNS["assault_rifle"]["grip_tilt_degrees"])
        self.assertEqual(hold["grip_tilt_degrees"], TOOLS["assault_rifle"]["hold"]["grip_tilt_degrees"])
        self.assertEqual(hold["sight_kind"], TOOLS["assault_rifle"]["hold"]["sight_kind"])
        self.assertEqual("Socket_Reticle", TOOLS["assault_rifle"]["hold"]["reticle_socket"])
        self.assertEqual(hold["grip_radius"], PROFILES["assault_rifle"]["grip_radius"])
        self.assertEqual(hold["support_radius"], PROFILES["assault_rifle"]["support_radius"])

    def test_the_named_support_correction_is_applied_and_held(self):
        """User decision 20.10.2026 (cubeescape-rules#1): KG02's Socket_SupportHand takes the Toolgen value 10 cm behind the
        spec anchor on the same handguard (first-person framing rule); named in data/concepts/corrections.json."""
        spec = concept_spec.load("KG02.geo.json")
        entry = concept_spec.corrections("KG02")["anchors"]["Socket_SupportHand"]
        self.assertEqual(spec["anchors"]["Socket_SupportHand"]["position_m"], entry["spec_m"])
        self.assertEqual([0.0, -0.25, 0.1161], entry["toolgen_m"])
        self.assertIn("Ego-Bildregel", entry["reason"])
        self.assertIn("Nutzer 20.10.2026", entry["decision"])
        found = concept_spec.layout("KG02.geo.json", [])
        self.assertEqual(entry["toolgen_m"], found["sockets"]["Socket_SupportHand"])
        self.assertEqual(["Socket_SupportHand"], [item["anchor"] for item in found["report"]["corrections"]])
        part = next(part for part in spec["parts"] if part["id"] == spec["support"]["part"])
        low, high = part["bounds_m"]
        self.assertTrue(all(low[i] <= entry["toolgen_m"][i] <= high[i] for i in range(3)), "on the handguard")
        self.assertEqual(entry["spec_m"][2], entry["toolgen_m"][2], "same height as the spec")

    def test_a_correction_for_a_changed_spec_value_is_refused(self):
        folder = Path(tempfile.mkdtemp())
        for name in ("KG02.geo.json", concept_spec.PROVENANCE):
            (folder / name).write_bytes((FOLDER / name).read_bytes())
        record = json.loads((FOLDER / concept_spec.CORRECTIONS).read_text())
        record["sheets"]["KG02"]["anchors"]["Socket_SupportHand"]["spec_m"] = [0.0, -0.3, 0.1161]
        (folder / concept_spec.CORRECTIONS).write_text(json.dumps(record))
        with self.assertRaises(concept_spec.ConceptError):
            concept_spec.layout("KG02.geo.json", [], where=folder)


class PipelineTests(unittest.TestCase):
    def test_the_world_stage_key_holds_the_sheet_and_its_provenance(self):
        tool = TOOLS["assault_rifle"]
        run = next(run for run in expand(tool, "quick") if run.name == "world")
        sources = stage_sources(run, tool, SourceIndex())
        self.assertIn("data/concepts/KG02.geo.json", sources)
        self.assertIn("data/concepts/provenance.json", sources)
        self.assertIn("scripts/tool_assets/concept_kit.py", sources)

    def test_only_the_concept_tool_depends_on_concept_files(self):
        """codex sol finding (20.10.2026): a sheet import must not rebuild weapons without a concept."""
        index = SourceIndex()
        for tool_id, tool in TOOLS.items():
            for run in expand(tool, "quick"):
                concept = [path for path in stage_sources(run, tool, index) if path.startswith(CONCEPTS + "/")]
                with self.subTest(tool=tool_id, stage=run.name):
                    if not tool.get("concept"):
                        self.assertEqual([], concept)
                    else:
                        self.assertTrue(set(concept) <= generate_tools.concept_sources(tool))
        # the concept tool's world stage carries its sheet and both shared files, each with a filled own entry
        tool = TOOLS["assault_rifle"]
        world = next(run for run in expand(tool, "quick") if run.name == "world")
        found = {path for path in stage_sources(world, tool, index) if path.startswith(CONCEPTS + "/")}
        self.assertEqual(generate_tools.concept_sources(tool), found)
        self.assertEqual("KG02", tool["concept"])
        for name in generate_tools.CONCEPT_SHARED:
            data = json.loads((FOLDER / name).read_text())
            self.assertIsNotNone(data.get("imported", data.get("sheets", {})).get("KG02"), name)

    def test_shared_concept_files_count_with_the_own_entry_only(self):
        tool = TOOLS["assault_rifle"]
        index = SourceIndex()
        before = generate_tools.source_digest("data/concepts/provenance.json", tool, index)
        other = dict(tool, concept="KG06")
        self.assertNotEqual(before, generate_tools.source_digest("data/concepts/provenance.json", other, index))
        self.assertEqual(before, generate_tools.source_digest("data/concepts/provenance.json", tool, index))
        # a change of the own entry changes the digest (temporary copy of the repository's concept files)
        root = Path(tempfile.mkdtemp())
        (root / CONCEPTS).mkdir(parents=True)
        record = json.loads((FOLDER / "provenance.json").read_text())
        record["imported"]["KG02"]["imported"] = "2099-01-01"
        (root / CONCEPTS / "provenance.json").write_text(json.dumps(record))
        moved = type("Index", (), {"root": root})()
        self.assertNotEqual(before, generate_tools.source_digest("data/concepts/provenance.json", tool, moved))

    def test_the_authoring_copy_carries_the_concepts(self):
        source = (ROOT / "toolgen/generate_tools.py").read_text()
        self.assertIn('shutil.copytree(ROOT / CONCEPTS, authors / "concepts")', source)
        self.assertEqual("concepts", concept_spec.FOLDERS[0].name)

    def test_no_network_in_the_build(self):
        for path in ("scripts/tool_assets/concept_spec.py", "scripts/tool_assets/concept_kit.py", "toolgen/generate_tools.py"):
            text = (ROOT / path).read_text()
            for word in ("urllib", "requests", "http://", "https://", "gh release"):
                self.assertNotIn(word, text, (path, word))


if __name__ == "__main__":
    unittest.main()
