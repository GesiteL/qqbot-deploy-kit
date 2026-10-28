"""Shared helpers for the QQBot zero-AI installer.

All JSON reads use utf-8-sig; all writes are BOM-less utf-8.
No secret is ever printed by this module.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

INSTALLER_VERSION = "0.2.0"
ASTROBOT_VERSION = "4.29.3"
MODEL_ID = "strawberry-gemini-3.8-flash-high"
MODEL_NAME = "custom/【草莓按次-0.03】gemini-3.8-flash-high"
PROVIDER_SOURCE_ID = "openai_compatible_source"
PLATFORM_ID = "napcat"
PORTS_REQUIRED = (3001, 6099, 6185)
PORTS_ALL = (3000, 3001, 6099, 6185)


class InstallError(RuntimeError):
    pass


def out(msg: str = "") -> None:
    print(msg, flush=True)


def fail(msg: str, code: int = 1) -> "None":
    raise InstallError(msg)


def read_json(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        fail(f"缺少配置文件：{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise InstallError(f"配置文件不是合法 JSON：{path}（{exc}）") from exc


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    dst = path.with_name(path.name + ".bak." + stamp())
    shutil.copy2(path, dst)
    return dst


def write_json(path: Path, data, backup: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup:
        backup_file(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def write_text(path: Path, text: str, backup: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup:
        backup_file(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def ensure_dirs(target: Path) -> None:
    for rel in ("runtime", "logs", "docs", "runtime/secrets", "runtime/.install", "runtime/.downloads"):
        (target / rel).mkdir(parents=True, exist_ok=True)


def target_from_args(value: str) -> Path:
    p = Path(value).expanduser()
    if not p.is_absolute():
        fail("安装目录必须是绝对路径（例如 C:\\QQBot）")
    return p.resolve()


def token_path(target: Path, name: str) -> Path:
    return target / "runtime" / "secrets" / name


def ensure_token(target: Path, name: str) -> str:
    path = token_path(target, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        value = path.read_text(encoding="utf-8-sig").strip()
        if value:
            return value
    value = secrets.token_hex(32)
    path.write_text(value, encoding="utf-8")
    return value


def read_token(target: Path, name: str) -> str:
    path = token_path(target, name)
    if not path.exists():
        fail(f"缺少本机 token：{path.name}")
    value = path.read_text(encoding="utf-8-sig").strip()
    if not value:
        fail(f"本机 token 为空：{path.name}")
    return value


def python_exe(target: Path) -> Path:
    return target / "runtime" / "python" / "python.exe"


def astrbot_root(target: Path) -> Path:
    return target / "runtime" / "astrbot"


def cmd_config_path(target: Path) -> Path:
    return astrbot_root(target) / "data" / "cmd_config.json"


def webui_path(target: Path) -> Path:
    return target / "runtime" / "napcat" / "napcat" / "config" / "webui.json"


def onebot_config_dir(target: Path) -> Path:
    return target / "runtime" / "napcat" / "napcat" / "config"


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None,
        check: bool = False, capture: bool = False) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise InstallError(f"命令失败（退出码 {proc.returncode}）：{' '.join(cmd[:3])}"
                           + (f"\n{detail[-800:]}" if detail else ""))
    return proc


def powershell(script: str, env_extra: dict | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update({k: str(v) for k, v in env_extra.items()})
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )


def _json_list(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        return [data]
    return data or []


def get_listeners(ports=PORTS_ALL) -> list[dict]:
    script = r"""
$ports = @($env:QQBOT_PORTS -split ',' | ForEach-Object { [int]$_ })
$res = @()
foreach ($p in $ports) {
  $conns = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue
  foreach ($x in $conns) {
    $res += [pscustomobject]@{ port = [int]$x.LocalPort; address = [string]$x.LocalAddress; pid = [int]$x.OwningProcess }
  }
}
if ($res.Count -eq 0) { '[]' } else { ConvertTo-Json -InputObject @($res) -Compress }
"""
    proc = powershell(script, {"QQBOT_PORTS": ",".join(str(p) for p in ports)})
    if proc.returncode != 0:
        raise InstallError("无法读取端口状态（PowerShell 调用失败）")
    return _json_list(proc.stdout)


def get_established(port: int) -> list[dict]:
    script = r"""
$res = @()
Get-NetTCPConnection -State Established -LocalPort ([int]$env:QQBOT_PORT) -ErrorAction SilentlyContinue | ForEach-Object {
  $res += [pscustomobject]@{ local = [string]$_.LocalAddress; remote = [string]$_.RemoteAddress; pid = [int]$_.OwningProcess }
}
if ($res.Count -eq 0) { '[]' } else { ConvertTo-Json -InputObject @($res) -Compress }
"""
    proc = powershell(script, {"QQBOT_PORT": str(port)})
    if proc.returncode != 0:
        return []
    try:
        return _json_list(proc.stdout)
    except Exception:
        return []


def wait_connect(ports, timeout: int) -> bool:
    deadline = time.time() + timeout
    pending = set(ports)
    while time.time() < deadline:
        for port in list(pending):
            try:
                with socket.create_connection(("127.0.0.1", int(port)), timeout=1):
                    pending.discard(port)
            except OSError:
                pass
        if not pending:
            return True
        time.sleep(1)
    return False


def stop_processes(target: Path, which: str = "all") -> int:
    if which not in ("all", "napcat", "astrbot"):
        fail("内部错误：which 只能是 all/napcat/astrbot")
    exclude = {str(os.getpid()), str(os.getppid())}
    script = r"""
$ErrorActionPreference = 'Stop'
$root = $env:QQBOT_TARGET
$which = $env:QQBOT_WHICH
$exclude = @()
foreach ($part in ($env:QQBOT_EXCLUDE -split ',')) {
  if ($part -match '^\d+$') { $exclude += [int]$part }
}
$prefixes = @()
if ($which -eq 'all' -or $which -eq 'napcat') { $prefixes += "$root\runtime\napcat\" }
if ($which -eq 'all' -or $which -eq 'astrbot') {
  $prefixes += "$root\runtime\astrbot\"
  $prefixes += "$root\runtime\python\"
}
$ids = @()
foreach ($x in @(Get-CimInstance Win32_Process -ErrorAction Stop)) {
  if ($x.ProcessId -eq $PID -or $exclude -contains [int]$x.ProcessId) { continue }
  $hit = $false
  if ($x.ExecutablePath) {
    foreach ($p in $prefixes) {
      if ($x.ExecutablePath.StartsWith($p, [StringComparison]::OrdinalIgnoreCase)) { $hit = $true; break }
    }
  }
  if (-not $hit -and $x.CommandLine) {
    foreach ($p in $prefixes) {
      if ($x.CommandLine.IndexOf($p, [StringComparison]::OrdinalIgnoreCase) -ge 0) { $hit = $true; break }
    }
  }
  if ($hit) { $ids += [int]$x.ProcessId }
}
$ids = @($ids | Sort-Object -Unique)
foreach ($id in $ids) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
$ids.Count
"""
    proc = powershell(script, {
        "QQBOT_TARGET": str(target),
        "QQBOT_WHICH": which,
        "QQBOT_EXCLUDE": ",".join(exclude),
    })
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise InstallError(f"停止旧进程失败（PowerShell 返回 {proc.returncode}）：{detail[-500:]}")
    try:
        return int((proc.stdout or "").strip().splitlines()[-1])
    except Exception as exc:
        detail = (proc.stdout or "").strip()
        raise InstallError(f"停止旧进程失败：PowerShell 输出异常：{detail[-500:]}") from exc


def is_loopback(address: str) -> bool:
    return address in ("127.0.0.1", "::1")


def validate_ascii_path(path_str: str) -> None:
    if any(ord(ch) > 127 for ch in path_str):
        fail("安装路径包含非 ASCII 字符，请换一个盘符")
    if " " in path_str:
        fail("安装路径包含空格，请换一个盘符")


def validate_base_url(value: str) -> str:
    value = (value or "").strip().lstrip("\ufeff").strip()
    if not value:
        fail("中转站地址为空")
    if any(ch in value for ch in (" ", "\t", "\r", "\n", '"', "'")):
        fail("中转站地址包含空格或非法字符")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme == "https" and parsed.netloc:
        pass
    elif parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost"):
        pass
    else:
        fail("中转站地址必须以 https:// 开头（本机测试可用 http://127.0.0.1）")
    if not parsed.hostname:
        fail("中转站地址缺少主机名")
    return value.rstrip("/")


def validate_key(value: str) -> str:
    value = (value or "").strip().lstrip("\ufeff").strip()
    if not value:
        fail("模型 Key 为空")
    if len(value) < 8 or len(value) > 512:
        fail("模型 Key 长度异常")
    if any(ch.isspace() for ch in value):
        fail("模型 Key 包含空格或换行")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        fail("模型 Key 包含控制字符")
    if '"' in value or "'" in value:
        fail("模型 Key 包含引号，请确认复制正确")
    return value


def extract_key(config: dict) -> str:
    sources = config.get("provider_sources") or []
    for src in sources:
        if src.get("id") == PROVIDER_SOURCE_ID:
            key = src.get("key")
            if isinstance(key, list):
                return str(key[0]) if key else ""
            return str(key or "")
    return ""


def llm_probe(target: Path, timeout: int = 60) -> tuple[int, str]:
    config = read_json(cmd_config_path(target))
    base = ""
    key = ""
    for src in config.get("provider_sources") or []:
        if src.get("id") == PROVIDER_SOURCE_ID:
            base = str(src.get("api_base") or "").strip()
            raw_key = src.get("key")
            key = str(raw_key[0]) if isinstance(raw_key, list) and raw_key else str(raw_key or "")
            break
    model = ""
    for item in config.get("provider") or []:
        if item.get("id") == MODEL_ID:
            model = str(item.get("model") or "").strip()
            break
    if not base or not key or not model:
        fail("模型配置不完整（请重新运行安装器填写地址与 Key）")
    if base.endswith("/chat/completions"):
        url = base
    else:
        url = base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "stream": False,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(256)
            return int(resp.status), "ok"
    except urllib.error.HTTPError as exc:
        return int(exc.code), str(exc.reason or "HTTP error")
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, OSError):
            reason = reason.strerror or str(reason)
        return 0, str(reason)
    except Exception as exc:  # noqa: BLE001 - only used for a human-readable summary
        return 0, exc.__class__.__name__


def parse_groups(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[,，;；\s]+", raw.strip().lstrip("\ufeff").strip())
    result = []
    for part in parts:
        if not part:
            continue
        if not re.fullmatch(r"\d{5,11}", part):
            fail(f"群号格式不对：{part}（只能是 5-11 位数字）")
        if part not in result:
            result.append(part)
    return result


def valid_qq(value: str) -> bool:
    return bool(re.fullmatch(r"\d{5,11}", (value or "").strip().lstrip("\ufeff").strip()))
