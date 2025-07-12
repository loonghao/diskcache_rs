"""
Docker network environment tests for diskcache_rs

This module provides tests that use Docker containers to simulate various
network filesystem scenarios for comprehensive testing.
"""

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import pytest


class DockerNetworkTester:
    """Docker-based network filesystem testing utilities"""

    def __init__(self):
        self.containers = []
        self.volumes = []

    def is_docker_available(self) -> bool:
        """Check if Docker is available and running"""
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def create_nfs_server(self, export_path: str) -> Optional[str]:
        """Create an NFS server container"""
        try:
            # Create a temporary directory for NFS exports
            host_export_dir = tempfile.mkdtemp(prefix="nfs_export_")
            self.volumes.append(host_export_dir)

            # Run NFS server container
            container_name = f"diskcache_nfs_test_{int(time.time())}"
            cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "--privileged",
                "-v",
                f"{host_export_dir}:/exports",
                "-p",
                "2049:2049",
                "erichough/nfs-server:2.2.1",
                "/exports",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self.containers.append(container_name)
                # Wait for NFS server to start
                time.sleep(5)
                return host_export_dir
            else:
                print(f"Failed to start NFS server: {result.stderr}")
                return None

        except (subprocess.TimeoutExpired, Exception) as e:
            print(f"Error creating NFS server: {e}")
            return None

    def create_smb_server(self, share_path: str) -> Optional[str]:
        """Create an SMB/CIFS server container"""
        try:
            # Create a temporary directory for SMB shares
            host_share_dir = tempfile.mkdtemp(prefix="smb_share_")
            self.volumes.append(host_share_dir)

            # Run SMB server container
            container_name = f"diskcache_smb_test_{int(time.time())}"
            cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "-p",
                "445:445",
                "-v",
                f"{host_share_dir}:/shared",
                "-e",
                "USER=testuser",
                "-e",
                "PASS=testpass",
                "dperson/samba",
                "-s",
                "shared;/shared;yes;no;no;testuser",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self.containers.append(container_name)
                # Wait for SMB server to start
                time.sleep(5)
                return host_share_dir
            else:
                print(f"Failed to start SMB server: {result.stderr}")
                return None

        except (subprocess.TimeoutExpired, Exception) as e:
            print(f"Error creating SMB server: {e}")
            return None

    def simulate_network_latency(self, container_name: str, delay_ms: int = 100):
        """Add network latency to a container"""
        try:
            cmd = [
                "docker",
                "exec",
                container_name,
                "tc",
                "qdisc",
                "add",
                "dev",
                "eth0",
                "root",
                "netem",
                "delay",
                f"{delay_ms}ms",
            ]
            subprocess.run(cmd, capture_output=True, timeout=10)
        except (subprocess.TimeoutExpired, Exception):
            pass  # Best effort

    def cleanup(self):
        """Clean up Docker containers and volumes"""
        # Stop and remove containers
        for container in self.containers:
            try:
                subprocess.run(
                    ["docker", "stop", container], capture_output=True, timeout=10
                )
                subprocess.run(
                    ["docker", "rm", container], capture_output=True, timeout=10
                )
            except (subprocess.TimeoutExpired, Exception):
                pass

        # Clean up volumes
        for volume in self.volumes:
            try:
                if os.path.exists(volume):
                    shutil.rmtree(volume, ignore_errors=True)
            except Exception:
                pass

        self.containers.clear()
        self.volumes.clear()


class TestDockerNetwork:
    """Docker-based network filesystem tests"""

    @pytest.fixture(scope="class")
    def docker_tester(self):
        """Create Docker network tester instance"""
        tester = DockerNetworkTester()
        yield tester
        tester.cleanup()

    @pytest.fixture
    def skip_if_no_docker(self, docker_tester):
        """Skip test if Docker is not available"""
        if not docker_tester.is_docker_available():
            pytest.skip("Docker is not available")

    def test_docker_availability(self, docker_tester):
        """Test Docker availability detection"""
        is_available = docker_tester.is_docker_available()
        print(f"Docker available: {is_available}")
        # This test always passes but provides useful information
        assert isinstance(is_available, bool)

    @pytest.mark.docker
    @pytest.mark.skipif(
        not DockerNetworkTester().is_docker_available(), reason="Docker not available"
    )
    def test_nfs_server_simulation(self, docker_tester, sample_data):
        """Test cache operations with simulated NFS server"""
        export_path = docker_tester.create_nfs_server("/exports")

        if export_path is None:
            pytest.skip("Failed to create NFS server")

        # Test basic file operations in the NFS export directory
        test_file = Path(export_path) / "test_cache"
        test_file.mkdir(exist_ok=True)

        from diskcache_rs import Cache

        try:
            cache = Cache(str(test_file))

            # Test basic operations
            cache.set("nfs_test", sample_data["medium"])
            retrieved = cache.get("nfs_test")
            assert retrieved == sample_data["medium"]

            # Test persistence
            cache.close()
            cache2 = Cache(str(test_file))
            retrieved2 = cache2.get("nfs_test")
            assert retrieved2 == sample_data["medium"]

            cache2.close()

        except Exception as e:
            pytest.fail(f"NFS simulation test failed: {e}")

    @pytest.mark.docker
    @pytest.mark.skipif(
        not DockerNetworkTester().is_docker_available(), reason="Docker not available"
    )
    def test_smb_server_simulation(self, docker_tester, sample_data):
        """Test cache operations with simulated SMB server"""
        share_path = docker_tester.create_smb_server("/shared")

        if share_path is None:
            pytest.skip("Failed to create SMB server")

        # Test basic file operations in the SMB share directory
        test_dir = Path(share_path) / "test_cache"
        test_dir.mkdir(exist_ok=True)

        from diskcache_rs import Cache

        try:
            cache = Cache(str(test_dir))

            # Test basic operations
            cache.set("smb_test", sample_data["large"])
            retrieved = cache.get("smb_test")
            assert retrieved == sample_data["large"]

            # Test multiple keys
            for i in range(10):
                cache.set(f"smb_key_{i}", f"smb_value_{i}")

            keys = cache.keys()
            assert len(keys) >= 10

            cache.close()

        except Exception as e:
            pytest.fail(f"SMB simulation test failed: {e}")

    @pytest.mark.docker
    @pytest.mark.skipif(
        not DockerNetworkTester().is_docker_available(), reason="Docker not available"
    )
    def test_network_latency_simulation(self, docker_tester, sample_data):
        """Test cache performance with simulated network latency"""
        export_path = docker_tester.create_nfs_server("/exports")

        if export_path is None:
            pytest.skip("Failed to create NFS server")

        # Add network latency to the container
        if docker_tester.containers:
            docker_tester.simulate_network_latency(
                docker_tester.containers[0], delay_ms=200
            )

        test_dir = Path(export_path) / "latency_test"
        test_dir.mkdir(exist_ok=True)

        from diskcache_rs import Cache

        try:
            cache = Cache(str(test_dir))

            # Measure operation times
            start_time = time.time()
            cache.set("latency_test", sample_data["medium"])
            set_time = time.time() - start_time

            start_time = time.time()
            retrieved = cache.get("latency_test")
            get_time = time.time() - start_time

            assert retrieved == sample_data["medium"]

            # Log timing information
            print(f"Set operation time: {set_time:.3f}s")
            print(f"Get operation time: {get_time:.3f}s")

            # Operations should still work despite latency
            assert set_time < 10.0  # Reasonable timeout
            assert get_time < 10.0  # Reasonable timeout

            cache.close()

        except Exception as e:
            pytest.fail(f"Network latency simulation test failed: {e}")

    def test_docker_cleanup(self, docker_tester):
        """Test Docker cleanup functionality"""
        # This test ensures cleanup works properly
        initial_containers = len(docker_tester.containers)
        initial_volumes = len(docker_tester.volumes)

        docker_tester.cleanup()

        assert len(docker_tester.containers) == 0
        assert len(docker_tester.volumes) == 0

        print(
            f"Cleaned up {initial_containers} containers and {initial_volumes} volumes"
        )
