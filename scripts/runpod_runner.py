from __future__ import annotations

import asyncio
import os
import posixpath
import signal
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = "/workspace/vibecomfy"


def runpod_lifecycle_root() -> Path:
    configured = os.getenv("VIBECOMFY_RUNPOD_LIFECYCLE_ROOT")
    if configured:
        return Path(configured)
    return ROOT.parent / "runpod-lifecycle"


RUNPOD_LIFECYCLE = runpod_lifecycle_root()


class PodGuard:
    def __init__(
        self,
        *,
        name_prefix: str,
        max_runtime_seconds_env: str = "VIBECOMFY_RUNPOD_MAX_RUNTIME_SECONDS",
        default_max_runtime_seconds: int = 7200,
    ) -> None:
        self.name_prefix = name_prefix
        self.max_runtime_seconds_env = max_runtime_seconds_env
        self.default_max_runtime_seconds = default_max_runtime_seconds
        self.pod = None
        self._watchdog: asyncio.Task[None] | None = None

    async def launch(self):
        load_dotenv, runpod_config, launch = _runpod_lifecycle()
        load_dotenv(runpod_lifecycle_root() / ".env")
        config_kwargs = {
            "storage_name": os.getenv("VIBECOMFY_RUNPOD_STORAGE", "Peter"),
            "storage_volumes": (),
            "gpu_type": os.getenv("VIBECOMFY_RUNPOD_GPU", "NVIDIA GeForce RTX 4090"),
            "ram_tiers": (32, 16),
        }
        if os.getenv("VIBECOMFY_RUNPOD_CONTAINER_DISK_GB"):
            config_kwargs["container_disk_gb"] = int(os.environ["VIBECOMFY_RUNPOD_CONTAINER_DISK_GB"])
        if os.getenv("VIBECOMFY_RUNPOD_DISK_SIZE_GB"):
            config_kwargs["disk_size_gb"] = int(os.environ["VIBECOMFY_RUNPOD_DISK_SIZE_GB"])
        self.pod = await launch(runpod_config.from_env(**config_kwargs), name=f"{self.name_prefix}-{int(time.time())}")
        self._start_watchdog()
        return self.pod

    async def terminate(self) -> None:
        if self._watchdog is not None:
            self._watchdog.cancel()
            self._watchdog = None
        if self.pod is not None:
            try:
                await self.pod.terminate()
            except Exception as exc:
                if "not found" in str(exc).lower():
                    print(f"pod_already_terminated={self.pod.id}", flush=True)
                else:
                    raise

    def _start_watchdog(self) -> None:
        seconds = int(os.getenv(self.max_runtime_seconds_env, str(self.default_max_runtime_seconds)))
        self._watchdog = asyncio.create_task(self._terminate_after(seconds))

    async def _terminate_after(self, seconds: int) -> None:
        try:
            await asyncio.sleep(seconds)
            if self.pod is not None:
                print(f"watchdog_terminating_pod={self.pod.id}", flush=True)
                await self.pod.terminate()
        except asyncio.CancelledError:
            return


def should_skip(path: Path, root: Path, exclude_set: set[str]) -> bool:
    rel = path.relative_to(root).as_posix()
    parts = Path(rel).parts
    return (
        any(rel == item or rel.startswith(f"{item}/") or item in parts for item in exclude_set)
        or path.suffix in {".pyc", ".pyo"}
    )


def upload_dir(sftp, local: Path, remote: str, exclude_set: set[str]) -> None:
    try:
        sftp.mkdir(remote)
    except OSError:
        pass
    for child in local.iterdir():
        if should_skip(child, ROOT, exclude_set):
            continue
        remote_child = posixpath.join(remote, child.name)
        if child.is_dir():
            upload_dir(sftp, child, remote_child, exclude_set)
        else:
            sftp.put(str(child), remote_child)


def install_signal_handlers(loop) -> None:
    def _handle_signal() -> None:
        raise KeyboardInterrupt

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass


async def run_pod(
    remote_script: str,
    *,
    name_prefix: str,
    exclude: set[str],
    upload_mode: Literal["sftp_walk", "tarball"] = "sftp_walk",
    timeout: int,
) -> int:
    guard = PodGuard(name_prefix=name_prefix, default_max_runtime_seconds=max(timeout * 2, 7200))
    install_signal_handlers(asyncio.get_running_loop())
    try:
        pod = await guard.launch()
        print(f"pod_id={pod.id}", flush=True)
        await pod.wait_ready(timeout=300)
        ssh_details = await pod._ensure_ssh_details()
        print(f"pod_ssh=root@{ssh_details['ip']} -p {ssh_details['port']}", flush=True)
        code, stdout, stderr = await pod.exec_ssh("nvidia-smi -L", timeout=60)
        print(stdout.strip(), flush=True)
        if code != 0:
            print(stderr, flush=True)
            return code

        if upload_mode == "tarball":
            await _upload_tarball(pod, exclude)
        else:
            client = pod.open_ssh_client()
            try:
                sftp = client.open_sftp()
                try:
                    upload_dir(sftp, ROOT, REMOTE_ROOT, exclude)
                finally:
                    sftp.close()
            finally:
                client.close()
        print("upload_complete=true", flush=True)

        code, stdout, stderr = await pod.exec_ssh(remote_script, timeout=timeout)
        print(stdout, flush=True)
        if stderr.strip():
            print(stderr, flush=True)
        return code
    finally:
        await guard.terminate()
        print("terminated_launched_pod=true", flush=True)


async def run_pod_detached(
    remote_script: str,
    *,
    name_prefix: str,
    exclude: set[str],
    upload_mode: Literal["sftp_walk", "tarball"] = "sftp_walk",
    timeout: int,
    poll_interval: int = 60,
) -> int:
    guard = PodGuard(name_prefix=name_prefix, default_max_runtime_seconds=max(timeout * 2, 7200))
    install_signal_handlers(asyncio.get_running_loop())
    try:
        pod = await guard.launch()
        print(f"pod_id={pod.id}", flush=True)
        await pod.wait_ready(timeout=300)
        ssh_details = await pod._ensure_ssh_details()
        print(f"pod_ssh=root@{ssh_details['ip']} -p {ssh_details['port']}", flush=True)
        code, stdout, stderr = await pod.exec_ssh("nvidia-smi -L", timeout=60)
        print(stdout.strip(), flush=True)
        if code != 0:
            print(stderr, flush=True)
            return code

        if upload_mode == "tarball":
            await _upload_tarball(pod, exclude)
        else:
            client = pod.open_ssh_client()
            try:
                sftp = client.open_sftp()
                try:
                    upload_dir(sftp, ROOT, REMOTE_ROOT, exclude)
                finally:
                    sftp.close()
            finally:
                client.close()
        print("upload_complete=true", flush=True)

        await _upload_remote_script(pod, remote_script)
        launch_command = (
            f"cd {REMOTE_ROOT} && mkdir -p out/corpus_matrix "
            "&& rm -f out/corpus_matrix/exit_code "
            "&& nohup bash /tmp/vibecomfy-remote-run.sh "
            "> /tmp/vibecomfy-remote-live.log 2>&1; "
            'rc=$?; printf "%s" "$rc" > out/corpus_matrix/exit_code; exit "$rc"'
        )
        code, stdout, stderr = await pod.exec_ssh(f"nohup bash -lc {launch_command!r} >/tmp/vibecomfy-launch.log 2>&1 & echo $!", timeout=30)
        if stdout.strip():
            print(f"remote_pid={stdout.strip()}", flush=True)
        if code != 0:
            print(stderr, flush=True)
            return code

        start = time.monotonic()
        last_snapshot = ""
        while True:
            if time.monotonic() - start > timeout:
                print(f"detached_timeout={timeout}", flush=True)
                return 124
            status_command = f"""
cd {REMOTE_ROOT}
echo "=== POLL $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
if [ -f out/corpus_matrix/results.tsv ]; then echo "--- RESULTS ---"; cat out/corpus_matrix/results.tsv; fi
if [ -f out/corpus_matrix/ready_results.tsv ]; then echo "--- READY ---"; cat out/corpus_matrix/ready_results.tsv; fi
echo "--- MEDIA ---"
find out/corpus_matrix output -maxdepth 5 -type f \\( -name '*.png' -o -name '*.mp4' -o -name '*.webp' -o -name '*.webm' \\) -printf '%TY-%Tm-%Td %TH:%TM %s %p\\n' 2>/dev/null | sort | tail -80
echo "--- LOG ---"
tail -80 /tmp/vibecomfy-remote-live.log 2>/dev/null || true
tail -80 out/corpus_matrix/live.log 2>/dev/null || true
echo "--- EXIT ---"
cat out/corpus_matrix/exit_code 2>/dev/null || true
"""
            try:
                code, stdout, stderr = await pod.exec_ssh(status_command, timeout=60)
            except Exception as exc:
                print(f"poll_ssh_failed={exc}", flush=True)
                await asyncio.sleep(poll_interval)
                continue
            snapshot = stdout.strip()
            if snapshot and snapshot != last_snapshot:
                print(snapshot, flush=True)
                last_snapshot = snapshot
            if stderr.strip():
                print(stderr, flush=True)
            if code != 0:
                return code
            exit_code = _parse_detached_exit(stdout)
            if exit_code is not None:
                try:
                    await _download_artifacts(pod)
                except OSError as exc:
                    print(f"artifact_download_failed={exc}", flush=True)
                return exit_code
            await asyncio.sleep(poll_interval)
    finally:
        await guard.terminate()
        print("terminated_launched_pod=true", flush=True)


def _runpod_lifecycle():
    import sys

    sys.path.insert(0, str(runpod_lifecycle_root() / "src"))
    from dotenv import load_dotenv
    from runpod_lifecycle import RunPodConfig, launch

    return load_dotenv, RunPodConfig, launch


async def _upload_remote_script(pod, remote_script: str) -> None:
    handle = tempfile.NamedTemporaryFile(prefix="vibecomfy-remote-run-", suffix=".sh", mode="w", delete=False)
    script_path = Path(handle.name)
    try:
        handle.write(remote_script)
        handle.write("\n")
        handle.close()
        client = pod.open_ssh_client()
        try:
            sftp = client.open_sftp()
            try:
                sftp.put(str(script_path), "/tmp/vibecomfy-remote-run.sh", confirm=False)
            finally:
                sftp.close()
        finally:
            client.close()
        code, stdout, stderr = await pod.exec_ssh("chmod +x /tmp/vibecomfy-remote-run.sh", timeout=30)
        if code != 0:
            print(stdout, flush=True)
            print(stderr, flush=True)
            raise RuntimeError(f"remote script chmod failed with exit code {code}")
    finally:
        script_path.unlink(missing_ok=True)


async def _download_artifacts(pod) -> None:
    local_root = ROOT / "out" / "runpod_artifacts" / str(int(time.time()))
    local_root.mkdir(parents=True, exist_ok=True)
    remote_archive = "/tmp/vibecomfy-artifacts.tar.gz"
    code, stdout, stderr = await pod.exec_ssh(
        f"cd {REMOTE_ROOT} && cp /tmp/vibecomfy-remote-live.log out/corpus_matrix/remote_live.log 2>/dev/null || true; "
        f"tar -czf {remote_archive} out/corpus_matrix output out/runs 2>/tmp/vibecomfy-artifact-tar.err || cat /tmp/vibecomfy-artifact-tar.err",
        timeout=300,
    )
    if code != 0:
        print(stdout, flush=True)
        if stderr.strip():
            print(stderr, flush=True)
        print("artifact_download_failed=archive", flush=True)
        return
    client = pod.open_ssh_client()
    try:
        sftp = client.open_sftp()
        try:
            archive = local_root / "artifacts.tar.gz"
            sftp.get(remote_archive, str(archive))
        finally:
            sftp.close()
    except Exception as exc:
        print(f"artifact_download_failed={exc}", flush=True)
        return
    finally:
        client.close()
    with tarfile.open(local_root / "artifacts.tar.gz", "r:gz") as tar:
        tar.extractall(local_root)
    print(f"artifact_downloaded={local_root.relative_to(ROOT)}", flush=True)


def _parse_detached_exit(stdout: str) -> int | None:
    lines = stdout.splitlines()
    for index, line in enumerate(lines):
        if line == "--- EXIT ---" and index + 1 < len(lines):
            value = lines[index + 1].strip()
            if value.isdigit():
                return int(value)
    return None


async def _upload_tarball(pod, exclude: set[str]) -> None:
    tar_path = _build_upload_tarball(exclude)
    try:
        client = pod.open_ssh_client()
        try:
            sftp = client.open_sftp()
            try:
                sftp.put(str(tar_path), "/tmp/vibecomfy-upload.tar.gz", confirm=False)
            finally:
                sftp.close()
        finally:
            client.close()
        code, stdout, stderr = await pod.exec_ssh(
            f"rm -rf {REMOTE_ROOT} && mkdir -p {REMOTE_ROOT} && tar --no-same-owner -xzf /tmp/vibecomfy-upload.tar.gz -C {REMOTE_ROOT}",
            timeout=300,
        )
        if code != 0:
            print(stdout, flush=True)
            print(stderr, flush=True)
            raise RuntimeError(f"remote tarball extraction failed with exit code {code}")
    finally:
        tar_path.unlink(missing_ok=True)


def _build_upload_tarball(exclude: set[str]) -> Path:
    handle = tempfile.NamedTemporaryFile(prefix="vibecomfy-upload-", suffix=".tar.gz", delete=False)
    tar_path = Path(handle.name)
    handle.close()
    with tarfile.open(tar_path, "w:gz") as tar:
        for path in ROOT.rglob("*"):
            if should_skip(path, ROOT, exclude):
                continue
            tar.add(path, arcname=path.relative_to(ROOT))
    return tar_path
