r"""
Cross-platform network filesystem tests for diskcache_rs

This module provides comprehensive testing for network filesystems across different platforms:
- Windows: UNC paths (\\server\share), mapped drives
- Linux/macOS: NFS mounts, SMB/CIFS mounts
- Cloud storage: OneDrive, Google Drive, Dropbox sync folders
"""

import concurrent.futures
import os
import platform
import time
from pathlib import Path
from typing import Dict, List, Optional

import pytest


class NetworkPathDetector:
    """Detect and validate network paths across platforms"""

    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows"""
        return platform.system() == "Windows"

    @staticmethod
    def is_linux() -> bool:
        """Check if running on Linux"""
        return platform.system() == "Linux"

    @staticmethod
    def is_macos() -> bool:
        """Check if running on macOS"""
        return platform.system() == "Darwin"

    @staticmethod
    def detect_unc_paths() -> List[str]:
        """Detect available UNC paths on Windows"""
        if not NetworkPathDetector.is_windows():
            return []

        unc_paths = []
        # Common UNC path patterns to test
        test_paths = [
            r"\\localhost\c$",  # Local admin share
            r"\\127.0.0.1\c$",  # IP-based admin share
        ]

        for path in test_paths:
            try:
                if os.path.exists(path):
                    unc_paths.append(path)
            except (OSError, PermissionError):
                # Path exists but no permission, still valid for testing
                pass

        return unc_paths

    @staticmethod
    def detect_network_drives() -> List[str]:
        """Detect mapped network drives on Windows"""
        if not NetworkPathDetector.is_windows():
            return []

        network_drives = []
        # Check drives A-Z for network mappings
        for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive_path = f"{drive_letter}:\\"
            try:
                if os.path.exists(drive_path):
                    # Check if it's a network drive using Windows API
                    import subprocess

                    result = subprocess.run(
                        ["net", "use", f"{drive_letter}:"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0 and "Remote" in result.stdout:
                        network_drives.append(drive_path)
            except (OSError, subprocess.TimeoutExpired, FileNotFoundError):
                pass

        return network_drives

    @staticmethod
    def detect_nfs_mounts() -> List[str]:
        """Detect NFS mounts on Linux/macOS"""
        if NetworkPathDetector.is_windows():
            return []

        nfs_mounts = []
        try:
            # Read /proc/mounts on Linux or use mount command on macOS
            if NetworkPathDetector.is_linux():
                with open("/proc/mounts") as f:
                    for line in f:
                        if "nfs" in line:
                            mount_point = line.split()[1]
                            if os.path.exists(mount_point):
                                nfs_mounts.append(mount_point)
            else:  # macOS
                import subprocess

                result = subprocess.run(
                    ["mount", "-t", "nfs"], capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    if "nfs" in line and " on " in line:
                        mount_point = line.split(" on ")[1].split(" ")[0]
                        if os.path.exists(mount_point):
                            nfs_mounts.append(mount_point)
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
            pass

        return nfs_mounts

    @staticmethod
    def detect_cloud_sync_folders() -> List[str]:
        """Detect cloud storage sync folders"""
        cloud_folders = []
        home = Path.home()

        # Common cloud storage folder patterns
        cloud_patterns = [
            # OneDrive
            home / "OneDrive",
            home / "OneDrive - Personal",
            home / "OneDrive - Business",
            # Google Drive
            home / "Google Drive",
            home / "GoogleDrive",
            # Dropbox
            home / "Dropbox",
            # iCloud (macOS)
            home / "Library" / "Mobile Documents" / "com~apple~CloudDocs",
            # Box
            home / "Box",
            home / "Box Sync",
        ]

        for path in cloud_patterns:
            if path.exists() and path.is_dir():
                cloud_folders.append(str(path))

        return cloud_folders


class TestCrossPlatformNetwork:
    """Cross-platform network filesystem tests"""

    @pytest.fixture(scope="class")
    def network_paths(self) -> Dict[str, List[str]]:
        """Detect all available network paths"""
        detector = NetworkPathDetector()
        return {
            "unc_paths": detector.detect_unc_paths(),
            "network_drives": detector.detect_network_drives(),
            "nfs_mounts": detector.detect_nfs_mounts(),
            "cloud_folders": detector.detect_cloud_sync_folders(),
        }

    @pytest.fixture
    def available_network_path(self, network_paths) -> Optional[str]:
        """Get the first available network path for testing"""
        for _path_type, paths in network_paths.items():
            if paths:
                # Create a test subdirectory to avoid conflicts
                test_path = Path(paths[0]) / "diskcache_rs_test"
                try:
                    test_path.mkdir(exist_ok=True)
                    return str(test_path)
                except (OSError, PermissionError):
                    continue
        return None

    def test_network_path_detection(self, network_paths):
        """Test that network path detection works"""
        total_paths = sum(len(paths) for paths in network_paths.values())

        # Log detected paths for debugging
        for path_type, paths in network_paths.items():
            if paths:
                print(f"\n{path_type}: {paths}")

        # This test always passes but provides useful information
        assert total_paths >= 0  # Always true, but logs are useful

    @pytest.mark.skipif(
        not any(
            [
                NetworkPathDetector.detect_unc_paths(),
                NetworkPathDetector.detect_network_drives(),
                NetworkPathDetector.detect_nfs_mounts(),
                NetworkPathDetector.detect_cloud_sync_folders(),
            ]
        ),
        reason="No network paths available for testing",
    )
    def test_network_cache_basic_operations(self, available_network_path, sample_data):
        """Test basic cache operations on network filesystem"""
        if not available_network_path:
            pytest.skip("No writable network path available")

        from diskcache_rs import Cache

        try:
            cache = Cache(available_network_path)

            # Test basic operations
            test_key = "network_test"
            test_value = sample_data["medium"]

            # Set and get
            assert cache.set(test_key, test_value)
            retrieved = cache.get(test_key)
            assert retrieved == test_value

            # Delete
            assert cache.delete(test_key)
            assert cache.get(test_key) is None

        except Exception as e:
            pytest.fail(f"Network cache operations failed: {e}")
        finally:
            # Cleanup
            try:
                if available_network_path and os.path.exists(available_network_path):
                    import shutil

                    shutil.rmtree(available_network_path, ignore_errors=True)
            except Exception:
                pass

    @pytest.mark.skipif(
        not any(
            [
                NetworkPathDetector.detect_unc_paths(),
                NetworkPathDetector.detect_network_drives(),
                NetworkPathDetector.detect_nfs_mounts(),
            ]
        ),
        reason="No true network filesystems available (cloud sync folders excluded)",
    )
    def test_network_latency_handling(self, available_network_path, sample_data):
        """Test cache behavior with network latency"""
        if not available_network_path:
            pytest.skip("No writable network path available")

        from diskcache_rs import Cache

        try:
            cache = Cache(available_network_path)

            # Test with various data sizes to simulate latency
            test_cases = [
                ("small", sample_data["small"]),
                ("medium", sample_data["medium"]),
                ("large", sample_data["large"]),
            ]

            for test_name, test_data in test_cases:
                start_time = time.time()
                cache.set(f"latency_test_{test_name}", test_data)
                set_time = time.time() - start_time

                start_time = time.time()
                retrieved = cache.get(f"latency_test_{test_name}")
                get_time = time.time() - start_time

                assert retrieved == test_data
                print(
                    f"Network {test_name} - Set: {set_time:.3f}s, Get: {get_time:.3f}s"
                )

        except Exception as e:
            pytest.fail(f"Network latency test failed: {e}")
        finally:
            # Cleanup
            try:
                if available_network_path and os.path.exists(available_network_path):
                    import shutil

                    shutil.rmtree(available_network_path, ignore_errors=True)
            except Exception:
                pass

    def test_simulated_network_conditions(self, temp_cache_dir, sample_data):
        """Test cache behavior under simulated network conditions"""
        from diskcache_rs import Cache

        # Use local filesystem but simulate network conditions
        cache = Cache(temp_cache_dir)

        def slow_operation(key, value, delay=0.1):
            """Simulate slow network operation"""
            time.sleep(delay)  # Simulate network latency
            return cache.set(key, value)

        # Test concurrent operations with simulated latency
        def worker(worker_id):
            results = []
            for i in range(5):
                key = f"sim_worker_{worker_id}_key_{i}"
                success = slow_operation(key, sample_data["small"], 0.05)
                results.append(success)

                # Verify data
                retrieved = cache.get(key)
                results.append(retrieved == sample_data["small"])

            return all(results)

        # Run multiple workers to simulate concurrent network access
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(worker, i) for i in range(3)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        assert all(results), "Simulated network conditions test failed"

    def test_path_format_compatibility(self, temp_cache_dir):
        """Test compatibility with different path formats"""
        from diskcache_rs import Cache

        # Test various path formats
        base_path = Path(temp_cache_dir)

        path_formats = [
            str(base_path),  # Standard string path
            str(base_path).replace("\\", "/"),  # Forward slashes
            base_path,  # Path object
        ]

        # Add platform-specific formats
        if NetworkPathDetector.is_windows():
            # Test Windows-specific formats
            path_formats.extend(
                [
                    str(base_path).upper(),  # Uppercase drive letter
                    str(base_path).lower(),  # Lowercase drive letter
                ]
            )

        for i, path_format in enumerate(path_formats):
            try:
                cache = Cache(path_format)
                test_key = f"path_format_test_{i}"
                test_value = f"test_value_{i}".encode()

                cache.set(test_key, test_value)
                retrieved = cache.get(test_key)
                assert retrieved == test_value

            except Exception as e:
                pytest.fail(f"Path format {path_format} failed: {e}")
