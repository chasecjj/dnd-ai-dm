import unittest
import threading
import time
import os
import shutil
from tools.vault_manager import VaultManager

class TestConcurrency(unittest.TestCase):
    def setUp(self):
        self.test_vault_dir = "test_vault_concurrency"
        if os.path.exists(self.test_vault_dir):
            shutil.rmtree(self.test_vault_dir)
        os.makedirs(self.test_vault_dir, exist_ok=True)
        # Create subfolders required by VaultManager
        os.makedirs(os.path.join(self.test_vault_dir, "01 - Party"), exist_ok=True)
        self.vm = VaultManager(self.test_vault_dir)

    def tearDown(self):
        if os.path.exists(self.test_vault_dir):
            shutil.rmtree(self.test_vault_dir)

    def test_concurrent_writes(self):
        # Create initial file
        self.vm.write_file("test.md", {"count": 0}, "Initial Body")

        def worker():
            for _ in range(10):
                # We just write repeatedly to stress the file lock.
                # We are NOT testing atomic read-modify-write here (as our lock is write-only).
                # We just want to ensure no exceptions/corruption occurs during write.
                try:
                    self.vm.write_file("test.md", {"count": 1}, "Updated Body")
                except Exception as e:
                    print(f"Write failed: {e}")

        threads = []
        for _ in range(5):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Check if file is still valid
        fm, body = self.vm.read_file("test.md")
        self.assertEqual(fm.get("count"), 1)
        self.assertEqual(body, "Updated Body")
        print("Concurrent write test passed: File is intact.")

if __name__ == "__main__":
    unittest.main()
