from __future__ import annotations

from typing import Any

from ..models import DeviceConfig
from .base import BaseTransport, TransportError

try:
    import paramiko
except ImportError:  # pragma: no cover
    paramiko = None


class SshTransport(BaseTransport):
    name = "ssh"

    def _client(self) -> Any:
        if paramiko is None:
            raise TransportError("paramiko dependency is not installed.")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self.device.fallback_ip or self.device.host,
                port=self.device.ssh_port,
                username=self.device.username,
                password=self.device.password,
                key_filename=self.device.private_key,
                timeout=self.device.timeout_seconds,
                look_for_keys=False,
                allow_agent=False,
            )
            return client
        except Exception as exc:  # pragma: no cover
            raise TransportError(f"ssh connection failed for {self.device.name}: {exc}") from exc

    def _run_command(self, command: str) -> dict[str, Any]:
        client = self._client()
        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=self.device.timeout_seconds)
            exit_status = stdout.channel.recv_exit_status()
            return {
                "command": command,
                "exit_status": exit_status,
                "stdout": stdout.read().decode("utf-8", errors="replace"),
                "stderr": stderr.read().decode("utf-8", errors="replace"),
            }
        finally:
            client.close()

    def ping(self) -> dict[str, Any]:
        result = self._run_command(":put \"mcp-ok\"")
        return {"reachable": result["exit_status"] == 0, "transport": self.name, "stdout": result["stdout"].strip()}

    def print_resource(self, path: str, **params: Any) -> Any:
        args = " ".join(f"{key}={value}" for key, value in params.items())
        if path in {"/system/resource", "/ip/dns"}:
            command = f"{path} print {args}".strip()
        else:
            command = f"{path} print without-paging {args}".strip()
        result = self._run_command(command)
        if result["exit_status"] != 0:
            raise TransportError(f"ssh print failed for {path}: {result['stderr'] or result['stdout']}")
        return {"path": path, "raw": result["stdout"]}

    def export_config(self, *, hide_sensitive: bool = True) -> Any:
        command = "/export terse"
        if hide_sensitive:
            command += " hide-sensitive"
        result = self._run_command(command)
        if result["exit_status"] != 0:
            raise TransportError(f"ssh export failed: {result['stderr'] or result['stdout']}")
        return {"raw": result["stdout"]}

    def run_script(self, script: str) -> Any:
        wrapped = f":do {{ {script} }} on-error={{ :put error }}"
        result = self._run_command(wrapped)
        if result["exit_status"] != 0:
            raise TransportError(f"ssh script execution failed: {result['stderr'] or result['stdout']}")
        return {"stdout": result["stdout"], "stderr": result["stderr"], "exit_status": result["exit_status"]}
