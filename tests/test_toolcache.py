"""Shared stage cache invariants; all cache roots are isolated in temporary directories."""
import hashlib
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

import toolcache


class ToolCacheTests(unittest.TestCase):
    def test_entry_that_only_removes_files(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            store = toolcache.Store(Path(temp) / "shared")
            self.assertTrue(store.store("b" * 64, source, {}, removed=["stale.png"]))
            self.assertEqual(store.lookup("b" * 64)["removed"], ["stale.png"])

    def test_atomic_concurrent_store_and_second_checkout_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "shared"
            source = Path(temp) / "source"
            source.mkdir()
            data = b"complete-content" * 10000
            (source / "model.bin").write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            store = toolcache.Store(base)
            results = []
            barrier = threading.Barrier(3)
            def writer():
                barrier.wait()
                results.append(store.store("a" * 64, source, {"model.bin": digest}))
            threads = [threading.Thread(target=writer) for _ in range(2)]
            for thread in threads: thread.start()
            barrier.wait()
            while any(thread.is_alive() for thread in threads):
                entry = store.entry("a" * 64)
                if entry.exists():
                    self.assertEqual((entry / "files/model.bin").read_bytes(), data)
            for thread in threads: thread.join()
            self.assertEqual(sorted(results), [False, True])
            self.assertEqual(len(list(store.folder.iterdir())), 1)
            checkout = Path(temp) / "other-output"
            hit = toolcache.Store(base).lookup("a" * 64)
            self.assertIsNotNone(toolcache.Store(base).restore("a" * 64, checkout, hit))
            self.assertEqual((checkout / "model.bin").read_bytes(), data)

    def test_corrupt_entry_is_discarded_and_restore_is_a_miss(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "cache"
            source = Path(temp) / "source"; source.mkdir()
            (source / "asset").write_bytes(b"good")
            store = toolcache.Store(base); key = "b" * 64
            store.store(key, source, {"asset": hashlib.sha256(b"good").hexdigest()})
            (store.entry(key) / "files/asset").write_bytes(b"bad")
            destination = Path(temp) / "checkout"
            self.assertIsNone(store.restore(key, destination))
            self.assertFalse(store.entry(key).exists())
            self.assertFalse((destination / "asset").exists())

    def test_prune_size_lru_and_two_hour_grace(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); store = toolcache.Store(base)
            now = time.time()
            for key, age, value in (("c" * 64, 20000, b"old"), ("d" * 64, 10000, b"new"),
                                    ("e" * 64, 60, b"recent")):
                entry = store.entry(key); (entry / "files").mkdir(parents=True)
                (entry / "files/data").write_bytes(value)
                (entry / "entry.json").write_text('{"key":"%s","files":{}}' % key)
                os.utime(entry, (now-age, now-age))
            total = toolcache.usage(base)
            result = toolcache.prune(base, limit=5, now=now)
            self.assertEqual(result["removed"], 2)
            self.assertFalse(store.entry("c" * 64).exists())
            self.assertFalse(store.entry("d" * 64).exists())
            self.assertTrue(store.entry("e" * 64).exists())
            self.assertGreater(result["total"], result["limit"])


if __name__ == "__main__":
    unittest.main()
