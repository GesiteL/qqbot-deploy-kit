"""Write QQBot configuration: tokens, NapCat webui/onebot, AstrBot, persona."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qqbot_lib as lib  # noqa: E402

TSINGHUA = "https://pypi.tuna.tsinghua.edu.cn/simple"
PERSONA_FILE = "人设-小满.md"
ONEBOT_TEMPLATE = "onebot11-template.json"


def log(msg: str) -> None:
    print(msg, flush=True)


def write_webui(target: Path, token: str) -> None:
    path = lib.webui_path(target)
    data = lib.read_json(path, default={}) if path.exists() else {}
    data.update({
        "host": "127.0.0.1",
        "port": 6099,
        "token": token,
        "loginRate": data.get("loginRate", 10),
        "autoLoginAccount": data.get("autoLoginAccount", ""),
        "disableWebUI": False,
        "accessControlMode": "none",
        "ipWhitelist": [],
        "ipBlacklist": [],
        "enableXForwardedFor": False,
        "enable2FA": False,
        "totpSecret": "",
    })
    lib.write_json(path, data)


def run_astrbot_init(target: Path, log_path: Path) -> None:
    root = lib.astrbot_root(target)
    py = lib.python_exe(target)
    env = dict(os.environ)
    env["ASTRBOT_ROOT"] = str(root)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [str(py), "-m", "astrbot.cli", "init", "-y"],
        cwd=str(root), env=env, text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=180,
    )
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(proc.stdout or "")
        fh.write(proc.stderr or "")
    if proc.returncode != 0:
        raise lib.InstallError("AstrBot 初始化失败（astrbot.cli init）。请把 install.log 发给交付方。")


def generate_cmd_config(target: Path) -> None:
    path = lib.cmd_config_path(target)
    if path.exists():
        return
    root = lib.astrbot_root(target)
    py = lib.python_exe(target)
    env = dict(os.environ)
    env["ASTRBOT_ROOT"] = str(root)
    env["PYTHONIOENCODING"] = "utf-8"
    log("  首次生成 AstrBot 配置（约 10-30 秒）...")
    creation = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    proc = subprocess.Popen(
        [str(py), "-m", "astrbot.cli", "run"],
        cwd=str(root), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=creation,
    )
    deadline = time.time() + 120
    try:
        while time.time() < deadline:
            if path.exists():
                time.sleep(1.0)
                break
            if proc.poll() is not None:
                break
            time.sleep(0.5)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
    if not path.exists():
        raise lib.InstallError("AstrBot 配置生成失败（cmd_config.json 没有出现）。请把 install.log 发给交付方。")


def configure_cmd_config(target: Path, token: str) -> None:
    path = lib.cmd_config_path(target)
    config = lib.read_json(path)
    dashboard = config.setdefault("dashboard", {})
    dashboard["enable"] = True
    dashboard["host"] = "127.0.0.1"
    dashboard["port"] = 6185

    platform = config.get("platform")
    if not isinstance(platform, list):
        platform = []
    found = False
    for item in platform:
        if item.get("id") == lib.PLATFORM_ID:
            item.update({
                "type": "aiocqhttp",
                "enable": True,
                "ws_reverse_host": "127.0.0.1",
                "ws_reverse_port": 3001,
                "ws_reverse_token": token,
            })
            found = True
    if not found:
        platform.append({
            "id": lib.PLATFORM_ID,
            "type": "aiocqhttp",
            "enable": True,
            "ws_reverse_host": "127.0.0.1",
            "ws_reverse_port": 3001,
            "ws_reverse_token": token,
        })
    config["platform"] = platform

    settings = config.setdefault("platform_settings", {})
    settings["enable_id_white_list"] = True
    if not settings.get("id_whitelist"):
        settings["id_whitelist"] = []
    settings["wl_ignore_admin_on_group"] = False
    settings["wl_ignore_admin_on_friend"] = False
    settings["friend_message_needs_wake_prefix"] = False
    settings["id_whitelist_log"] = True
    config["wake_prefix"] = [""]
    config["pypi_index_url"] = TSINGHUA
    agent = config.setdefault("agent_runner", {})
    agent.setdefault("config", {}).setdefault("persona", {}).setdefault("persona_id", "default")
    lib.write_json(path, config)


def cmd_init(args) -> int:
    target = lib.target_from_args(args.target)
    lib.ensure_dirs(target)
    log_path = target / "install.log"
    log("=== 配置初始化 ===")
    webui_token = lib.ensure_token(target, "napcat-webui-token.txt")
    onebot_token = lib.ensure_token(target, "onebot-token.txt")
    write_webui(target, webui_token)
    log("  NapCat webui.json 已写入（token 已生成/保留）。")
    run_astrbot_init(target, log_path)
    generate_cmd_config(target)
    configure_cmd_config(target, onebot_token)
    log("  AstrBot 配置已写入（dashboard=127.0.0.1:6185，OneBot=127.0.0.1:3001）。")
    log("=== 配置初始化完成 ===")
    return 0


def prepare_login(args) -> int:
    target = lib.target_from_args(args.target)
    config_dir = lib.onebot_config_dir(target)
    config_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = target / "runtime" / "napcat" / "napcat" / "cache"
    if cache_dir.exists():
        for qr in cache_dir.glob("qrcode*.png"):
            try:
                qr.unlink()
            except OSError:
                pass
    backup = target / "runtime" / ".install" / "backup" / ("onebot-" + lib.stamp())
    moved = 0
    for pattern in ("onebot11_*.json", "onebot11.json"):
        for path in config_dir.glob(pattern):
            backup.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(backup / path.name))
            moved += 1
    if moved:
        log(f"  已备份并移走 {moved} 个旧 OneBot 配置。")
    template = target / "docs" / "templates" / ONEBOT_TEMPLATE
    if not template.exists():
        raise lib.InstallError("缺少 OneBot 模板：docs\\templates\\onebot11-template.json")
    log("  登录前准备完成；请扫描 NapCat 窗口或二维码图片。")
    return 0


def read_uin(args) -> str:
    if args.uin:
        uin = args.uin.strip()
    else:
        path = Path(args.uin_file)
        if not path.exists():
            raise lib.InstallError("没有拿到登录 QQ 号（等待登录失败）")
        uin = path.read_text(encoding="utf-8-sig").strip()
    if not re.fullmatch(r"\d{5,11}", uin):
        raise lib.InstallError("登录返回的 QQ 号格式异常，已停止。请重新扫码后重试。")
    return uin


def apply_onebot(args) -> int:
    target = lib.target_from_args(args.target)
    uin = read_uin(args)
    token = lib.read_token(target, "onebot-token.txt")
    template = target / "docs" / "templates" / ONEBOT_TEMPLATE
    if not template.exists():
        raise lib.InstallError("缺少 OneBot 模板：docs\\templates\\onebot11-template.json")
    text = template.read_text(encoding="utf-8-sig")
    if "{{ONEBOT_TOKEN}}" not in text:
        raise lib.InstallError("OneBot 模板缺少 {{ONEBOT_TOKEN}} 占位符")
    payload = text.replace("{{ONEBOT_TOKEN}}", token)
    try:
        data = json.loads(payload)
    except Exception as exc:
        raise lib.InstallError(f"OneBot 配置生成后不是合法 JSON（模板可能损坏）：{exc}") from exc
    config_dir = lib.onebot_config_dir(target)
    config_dir.mkdir(parents=True, exist_ok=True)
    dest = config_dir / f"onebot11_{uin}.json"
    lib.write_json(dest, data)
    log("  OneBot 配置已写入（token 已注入，QQ 号不回显）。")
    return 0


def upsert_provider(config: dict, base: str, key: str) -> None:
    sources = config.get("provider_sources")
    if not isinstance(sources, list):
        sources = []
    found = False
    for src in sources:
        if src.get("id") == lib.PROVIDER_SOURCE_ID:
            src.update({
                "provider": "openai",
                "type": "openai_chat_completion",
                "provider_type": "chat_completion",
                "enable": True,
                "key": [key],
                "api_base": base,
                "timeout": 120,
                "proxy": "",
                "custom_headers": {},
            })
            found = True
    if not found:
        sources.append({
            "id": lib.PROVIDER_SOURCE_ID,
            "provider": "openai",
            "type": "openai_chat_completion",
            "provider_type": "chat_completion",
            "enable": True,
            "key": [key],
            "api_base": base,
            "timeout": 120,
            "proxy": "",
            "custom_headers": {},
        })
    config["provider_sources"] = sources

    providers = config.get("provider")
    if not isinstance(providers, list):
        providers = []
    found = False
    for item in providers:
        if item.get("id") == lib.MODEL_ID:
            item.update({
                "provider_source_id": lib.PROVIDER_SOURCE_ID,
                "model": lib.MODEL_NAME,
                "modalities": ["text"],
                "custom_extra_body": {},
                "enable": True,
            })
            found = True
    if not found:
        providers.append({
            "id": lib.MODEL_ID,
            "provider_source_id": lib.PROVIDER_SOURCE_ID,
            "model": lib.MODEL_NAME,
            "modalities": ["text"],
            "custom_extra_body": {},
            "enable": True,
        })
    config["provider"] = providers


def persona_schema() -> str:
    return """
CREATE TABLE IF NOT EXISTS personas (
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    id INTEGER NOT NULL,
    persona_id VARCHAR(255) NOT NULL,
    system_prompt TEXT NOT NULL,
    begin_dialogs JSON,
    tools JSON,
    skills JSON,
    custom_error_message TEXT,
    folder_id VARCHAR(36),
    sort_order INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uix_persona_id UNIQUE (persona_id)
)
"""


def write_persona(target: Path) -> None:
    template = target / "docs" / "templates" / PERSONA_FILE
    if not template.exists():
        raise lib.InstallError("缺少人设模板：docs\\templates\\人设-小满.md")
    prompt = template.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if not prompt.strip():
        raise lib.InstallError("人设模板为空")
    db = lib.astrbot_root(target) / "data" / "data_v4.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        shutil.copy2(db, db.with_name(db.name + ".bak." + lib.stamp()))
    con = sqlite3.connect(str(db), timeout=10)
    try:
        con.execute("PRAGMA busy_timeout=5000")
        con.execute(persona_schema())
        now = datetime.now().isoformat(sep=" ")
        row = con.execute("SELECT id, system_prompt FROM personas WHERE persona_id='default'").fetchone()
        if row:
            con.execute(
                "UPDATE personas SET system_prompt=?, updated_at=? WHERE persona_id='default'",
                (prompt, now),
            )
        else:
            next_id = con.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM personas").fetchone()[0]
            con.execute(
                "INSERT INTO personas (created_at,updated_at,id,persona_id,system_prompt,"
                "begin_dialogs,tools,skills,custom_error_message,folder_id,sort_order) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (now, now, next_id, "default", prompt, "[]", "[]", "[]", None, None, 0),
            )
        con.commit()
        stored = con.execute("SELECT system_prompt FROM personas WHERE persona_id='default'").fetchone()[0]
        if stored != prompt:
            raise lib.InstallError("人设写入后校验不一致，已停止")
    finally:
        con.close()
    log("  默认人设「小满」已写入（校验通过）。")


def apply_user(args) -> int:
    target = lib.target_from_args(args.target)
    base = lib.validate_base_url(os.environ.get("QQBOT_BASE", ""))
    key = lib.validate_key(os.environ.get("QQBOT_KEY", ""))
    admin = (os.environ.get("QQBOT_ADMIN") or "").strip().lstrip("\ufeff").strip()
    if not lib.valid_qq(admin):
        raise lib.InstallError("管理员 QQ 号格式不对（只能是 5-11 位数字）")
    groups = lib.parse_groups(os.environ.get("QQBOT_GROUPS", ""))
    path = lib.cmd_config_path(target)
    config = lib.read_json(path)
    upsert_provider(config, base, key)
    settings = config.setdefault("platform_settings", {})
    whitelist = [f"napcat:GroupMessage:{gid}" for gid in groups]
    whitelist.append(f"napcat:FriendMessage:{admin}")
    settings["enable_id_white_list"] = True
    settings["id_whitelist"] = whitelist
    settings["wl_ignore_admin_on_group"] = False
    settings["wl_ignore_admin_on_friend"] = False
    settings["friend_message_needs_wake_prefix"] = False
    settings["id_whitelist_log"] = True
    config["wake_prefix"] = [""]
    config["admins_id"] = [admin]
    config["pypi_index_url"] = TSINGHUA
    if args.persona == "yes":
        write_persona(target)
    lib.write_json(path, config)
    log(f"  模型地址与 Key 已写入（Key 已隐藏）；管理员 1 个；白名单群 {len(groups)} 个。")
    return 0


def install_info(args) -> int:
    target = lib.target_from_args(args.target)
    drive = target.drive.rstrip(":\\") or "C"
    lines = [
        "QQBot 安装信息",
        "==========================================",
        f"安装目录：{target}",
        f"安装盘符：{drive}",
        f"安装时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"安装器版本：v{lib.INSTALLER_VERSION}",
        "组件版本：NapCat v4.18.41 / AstrBot 4.29.3 / Python 3.12.15",
        "说明：卸载 = 先运行 停止.bat，再删除整个安装目录；删除本文件不影响运行。",
        "",
    ]
    path = target / "安装信息.txt"
    path.write_text("\r\n".join(lines), encoding="utf-8-sig")
    log("  安装信息.txt 已写入。")
    return 0


def set_autostart(args) -> int:
    target = lib.target_from_args(args.target)
    appdata = (os.environ.get("APPDATA") or "").strip()
    if not appdata:
        raise lib.InstallError("找不到当前用户的启动文件夹（APPDATA 为空）")
    startup = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True, exist_ok=True)
    script = r"""
$target = $env:QQBOT_TARGET
$lnk = $env:QQBOT_LNK
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = Join-Path $target '启动.bat'
$s.WorkingDirectory = $target
$s.WindowStyle = 7
$s.Description = 'QQBot 启动'
$s.Save()
"""
    proc = lib.powershell(script, {"QQBOT_TARGET": str(target), "QQBOT_LNK": str(startup / "QQBot 启动.lnk")})
    if proc.returncode != 0:
        raise lib.InstallError("开机自启快捷方式创建失败（不影响本次安装，可稍后手动创建）")
    log("  开机自启快捷方式已写入当前用户启动文件夹。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "prepare-login", "apply-onebot", "apply-user", "install-info", "set-autostart"):
        p = sub.add_parser(name)
        p.add_argument("--target", required=True)
    p = sub.choices["apply-onebot"]
    p.add_argument("--uin", default="")
    p.add_argument("--uin-file", default="")
    p = sub.choices["apply-user"]
    p.add_argument("--persona", choices=("yes", "no"), default="yes")
    args = parser.parse_args()
    try:
        if args.command == "init":
            return cmd_init(args)
        if args.command == "prepare-login":
            return prepare_login(args)
        if args.command == "apply-onebot":
            return apply_onebot(args)
        if args.command == "apply-user":
            return apply_user(args)
        if args.command == "install-info":
            return install_info(args)
        if args.command == "set-autostart":
            return set_autostart(args)
        raise lib.InstallError("未知命令")
    except lib.InstallError as exc:
        print(f"[错误] {exc}", flush=True)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] 配置阶段出现未预期问题：{exc.__class__.__name__}: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
