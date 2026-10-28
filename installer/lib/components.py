"""Install pinned components: NapCat, AstrBot + dependencies, and three plugins.

Every download is checked against the SHA256 recorded in installer/components.json.
Local packages under installer/packages/ are used first; a failed local check
falls back to the official URL (never to a third-party mirror).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qqbot_lib as lib  # noqa: E402


class Log:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(path, "a", encoding="utf-8", buffering=1)

    def __call__(self, msg: str = "") -> None:
        print(msg, flush=True)
        self.fh.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

    def close(self) -> None:
        try:
            self.fh.close()
        except Exception:
            pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, log: Log, name: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error = ""
    for attempt in range(1, 3):
        if dest.exists():
            dest.unlink()
        log(f"  下载 {name}（第 {attempt}/2 次）...")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": f"qqbot-installer/{lib.INSTALLER_VERSION}",
                "Accept": "*/*",
            })
            with urllib.request.urlopen(req, timeout=90) as resp, dest.open("wb") as fh:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                last_report = 0
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if done - last_report >= 10 * 1024 * 1024:
                        last_report = done
                        if total:
                            log(f"    {done // (1024 * 1024)} / {max(1, total // (1024 * 1024))} MB")
                        else:
                            log(f"    {done // (1024 * 1024)} MB")
            if dest.stat().st_size == 0:
                raise OSError("下载结果为空文件")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if dest.exists():
                try:
                    dest.unlink()
                except OSError:
                    pass
            if attempt < 2:
                log(f"  下载失败，2 秒后重试：{exc}")
                time.sleep(2)
    raise lib.InstallError(
        f"下载失败：{name}。请检查网络/代理；若网络受限，可把官方组件放到 installer\\packages\\ 后重试。"
        f"（{last_error[:160]}）"
    )


def obtain(entry: dict, packages: Path, downloads: Path, log: Log, label: str) -> Path:
    local_name = entry.get("package") or ""
    expected = (entry.get("sha256") or "").lower()
    size = entry.get("size")
    if local_name:
        local = packages / local_name
        if local.exists():
            got = sha256_file(local)
            if expected and got != expected:
                log(f"  [警告] 预置包 {local_name} 的 SHA256 不对，按协议改用官方源。")
            elif size and local.stat().st_size != size:
                log(f"  [警告] 预置包 {local_name} 的大小不对，按协议改用官方源。")
            else:
                log(f"  使用预置包：{local}")
                return local
    dest = downloads / local_name
    download(entry["url"], dest, log, label)
    got = sha256_file(dest)
    if expected and got.lower() != expected:
        raise lib.InstallError(
            f"组件校验失败：{label} 的 SHA256 与固定值不一致。已停止（未使用该文件）。"
            "请删除 runtime\\.downloads 里的同名文件后重试。"
        )
    if size and dest.stat().st_size != size:
        raise lib.InstallError(
            f"组件校验失败：{label} 的大小应为 {size} 字节，实际 {dest.stat().st_size} 字节。"
        )
    log(f"  SHA256 校验通过：{label}")
    return dest


def safe_extract_zip(zip_path: Path, dest: Path, log: Log) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.infolist()
        for idx, info in enumerate(members, 1):
            name = info.filename
            parts = PurePosixPath(name).parts
            if not parts or name.startswith("/") or "\\" in name or ".." in parts or ":" in parts[0]:
                raise lib.InstallError(f"压缩包内含非法路径，已停止：{name}")
            if name.startswith("__MACOSX/"):
                continue
            zf.extract(info, dest)
            if idx % 100 == 0:
                log(f"    解压 {idx}/{len(members)} ...")


def quarantine(path: Path, install_dir: Path, label: str, log: Log) -> None:
    if not path.exists():
        return
    backup_root = install_dir / "runtime" / ".install" / "backup"
    backup_root.mkdir(parents=True, exist_ok=True)
    dst = backup_root / f"{label}-{lib.stamp()}"
    suffix = 1
    while dst.exists():
        suffix += 1
        dst = backup_root / f"{label}-{lib.stamp()}-{suffix}"
    shutil.move(str(path), str(dst))
    log(f"  旧目录已移到：{dst}")


def install_napcat(manifest: dict, target: Path, packages: Path, downloads: Path, log: Log) -> None:
    entry = manifest["napcat"]
    final = target / "runtime" / "napcat"
    if (final / "index.js").exists() and (final / "node.exe").exists():
        log("  NapCat 已存在，跳过。")
        return
    log(f"  安装 NapCat {entry['version']} ...")
    zpath = obtain(entry, packages, downloads, log, "NapCat")
    temp = target / "runtime" / ".extract" / ("napcat-" + lib.stamp())
    if temp.exists():
        shutil.rmtree(temp)
    safe_extract_zip(zpath, temp, log)
    source = temp
    if not (source / "index.js").exists():
        candidates = list(temp.rglob("index.js"))
        if len(candidates) == 1:
            source = candidates[0].parent
        else:
            raise lib.InstallError("NapCat 压缩包结构异常：找不到唯一的 index.js")
    if not (source / "node.exe").exists():
        raise lib.InstallError("NapCat 压缩包缺少 node.exe")
    quarantine(final, target, "napcat", log)
    shutil.copytree(source, final)
    shutil.rmtree(temp, ignore_errors=True)
    if not (final / "index.js").exists() or not (final / "node.exe").exists():
        raise lib.InstallError("NapCat 解压后缺少 index.js 或 node.exe")
    log("  NapCat 安装完成。")


def module_version(dist: str) -> str | None:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


def pip_install(target: Path, manifest: dict, packages: Path, log: Log) -> None:
    uv = target / "runtime" / "uv" / "uv.exe"
    py = lib.python_exe(target)
    if not py.exists():
        raise lib.InstallError("运行时 Python 不存在，无法安装 AstrBot。请重新运行安装器。")
    pins = manifest["astrbot"]["packages"]
    checks = manifest["astrbot"]["checks"]
    need = False
    for dist, version in checks.items():
        current = module_version(dist)
        if current != version:
            need = True
    if module_version("astrbot") == manifest["astrbot"]["version"] and not need:
        log(f"  AstrBot {manifest['astrbot']['version']} 与依赖已存在，跳过。")
        return
    if not uv.exists():
        raise lib.InstallError("uv 不存在，无法安装 Python 依赖。请重新运行安装器。")

    env = dict(os.environ)
    env["UV_CACHE_DIR"] = str(target / "runtime" / ".uv" / "cache")
    env["UV_PYTHON_INSTALL_DIR"] = str(target / "runtime" / ".uv" / "python")
    env["PYTHONIOENCODING"] = "utf-8"

    base_cmd = [str(uv), "pip", "install", "--break-system-packages", "--python", str(py)]
    wheels = packages / "wheels"
    if wheels.is_dir() and any(wheels.glob("*.whl")):
        log("  尝试离线 wheels ...")
        cmd = base_cmd + ["--no-index", "--find-links", str(wheels)] + pins
        if run_visible(cmd, target, env, log):
            verify_versions(manifest, log)
            return
        log("  离线 wheels 不完整，改用网络源。")

    indexes = [manifest["astrbot"]["index"], manifest["astrbot"]["fallback"]]
    for idx, index in enumerate(indexes, 1):
        log(f"  安装依赖（源 {idx}/2）：{index}")
        cmd = base_cmd + ["--index-url", index] + pins
        if run_visible(cmd, target, env, log):
            verify_versions(manifest, log)
            return
        if idx < len(indexes):
            log("  该源安装失败，改用官方 PyPI 重试一次。")
    raise lib.InstallError(
        "AstrBot 依赖安装失败。清华镜像与官方 PyPI 都没有成功；请检查网络后重试，"
        "或把 wheels 放到 installer\\packages\\wheels\\。"
    )


def run_visible(cmd: list[str], cwd: Path, env: dict, log: Log) -> bool:
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log("    " + line)
    return proc.wait() == 0


def verify_versions(manifest: dict, log: Log) -> None:
    for dist, version in manifest["astrbot"]["checks"].items():
        current = module_version(dist)
        if current != version:
            raise lib.InstallError(f"依赖版本不对：{dist} 应为 {version}，实际 {current}")
    log("  依赖版本复核通过。")


def install_plugins(manifest: dict, target: Path, packages: Path, downloads: Path, log: Log) -> None:
    plugins_root = target / "runtime" / "astrbot" / "data" / "plugins"
    plugins_root.mkdir(parents=True, exist_ok=True)
    total = len(manifest["plugins"])
    for idx, entry in enumerate(manifest["plugins"], 1):
        name = entry["dir"]
        final = plugins_root / name
        log(f"  插件 {idx}/{total}：{name} @ {entry['commit'][:8]}")
        if (final / "main.py").exists():
            log("    已存在，跳过。")
            continue
        zpath = obtain(entry, packages, downloads, log, f"插件 {name}")
        temp = target / "runtime" / ".extract" / (name + "-" + lib.stamp())
        if temp.exists():
            shutil.rmtree(temp)
        safe_extract_zip(zpath, temp, log)
        children = [p for p in temp.iterdir()]
        source = children[0] if len(children) == 1 and children[0].is_dir() else temp
        if not (source / "main.py").exists():
            raise lib.InstallError(f"插件 {name} 压缩包结构异常：找不到 main.py")
        quarantine(final, target, name, log)
        shutil.copytree(source, final)
        shutil.rmtree(temp, ignore_errors=True)
        log("    安装完成。")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--packages", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    target = lib.target_from_args(args.target)
    packages = Path(args.packages).resolve()
    manifest = lib.read_json(Path(args.manifest).resolve())
    lib.ensure_dirs(target)
    log = Log(target / "install.log")
    downloads = target / "runtime" / ".downloads"
    try:
        log("=== 组件安装开始 ===")
        install_napcat(manifest, target, packages, downloads, log)
        log("=== AstrBot 与依赖 ===")
        pip_install(target, manifest, packages, log)
        log("=== 插件 ===")
        install_plugins(manifest, target, packages, downloads, log)
        log("=== 组件安装完成 ===")
        return 0
    except lib.InstallError as exc:
        log(f"[错误] {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001
        log(f"[错误] 组件安装出现未预期问题：{exc.__class__.__name__}: {exc}")
        return 2
    finally:
        log.close()


if __name__ == "__main__":
    sys.exit(main())
