# qqbot-autopilot

[![version](https://img.shields.io/badge/version-v0.2.0-blue)](CHANGELOG.md) [![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

这套东西是给不会技术的人用的。把仓库 zip 下载下来，解压，双击 `安装.bat`，剩下的事照着黑色窗口来：
扫码、回答几个问题，装完就是一个会在群里说话、会看图、会提醒、会发空间、会点歌的机器人。

底下拼起来的是三块：NapCat 当协议端，AstrBot 当大脑，再加三个插件。版本号和 SHA256 全都锁死。
全程不需要管理员权限，不碰注册表，不装系统服务，所有服务只监听 `127.0.0.1`。

## 默认装法：仓库 zip + 安装.bat

1. 把交付方给你的仓库 zip 解压到一个普通文件夹里（别在压缩包里直接双击）。
2. 双击根目录的 **`安装.bat`**。Windows 或杀毒软件要是拦，就选「仍要运行 / 允许」。
3. 照着黑色窗口一步步走：
   - 选安装盘：默认 `C`，输 `D`/`E` 就装到 `<盘>:\QQBot`；那个盘至少要有 10 GB 空闲。
   - 用手机 QQ **小号**扫 NapCat 窗口或二维码图片里的码（10 分钟内扫完）。
   - 粘贴中转站地址和模型 Key；Key 会明文显示在屏幕上，旁边别站人。
   - 填管理员 QQ 号、白名单群号（可跳过）、要不要「小满」人设、要不要开机自启。
4. 等窗口打出「安装完成」，去群里发一句「在吗」。

装完的目录里有 `启动.bat` / `停止.bat` / `runtime` / `docs` / `安装信息.txt`。以后双击 `启动.bat` 开机，
双击 `停止.bat` 关。卸载就是先停止，再把整个安装目录删掉。

> 不想手输 Key：在 `安装.bat` 旁边放一个 `key.txt`，第一行写中转站地址，第二行写 Key，
> 安装器会自己读并跳过那两次输入。安装成功后会自动删除；若删除失败请手动删除。

## 安装器做了什么

| 阶段 | 内容 |
|---|---|
| 1 环境 | 64 位检查、盘符提问、剩余空间、3001/6099/6185 端口占用；被占用会提示先停旧机器人或重启 |
| 2 组件 | uv 0.12.23 → Python 3.12.15 → NapCat v4.18.41 → AstrBot 4.29.3 与依赖 → 三个固定 commit 插件；全部官方源 + SHA256 |
| 3 配置 | 现场生成本机 token，写 NapCat `webui.json`、AstrBot `cmd_config.json`，不复制示例值 |
| 4 扫码 | 最小化启动 NapCat，打开二维码图片；轮询登录配置，每 2 分钟提醒一次，最多 10 分钟 |
| 5 接线 | 注入 OneBot 模板与 token，重启两端，断言 3001 出现 ESTABLISHED |
| 6 收尾 | 写模型地址/Key、管理员、群白名单、人设、开机自启；做一次最小模型调用，要求 HTTP 200 |
| 7 终验 | 3000/3001/6099/6185 全部只在本机监听，3001 已连接，打印「去群里发在吗」 |

装失败时窗口不会一闪而过，会停住，写清「症状 + 你可以试 + 找谁」；全程日志落在
`<安装目录>\install.log`。安装器重跑会保留 token 和数据，只补齐、更新组件和配置。

## 组件（官方来源，全部固定）

| 组件 | 固定版本 | 来源 |
|---|---|---|
| uv | 0.12.23 | [astral-sh/uv Releases](https://github.com/astral-sh/uv/releases/tag/0.12.23) |
| Python | 3.12.15 | `uv python install 3.12.15`（uv 官方源） |
| NapCatQQ | v4.18.41 | [NapCat Release](https://github.com/NapNeko/NapCatQQ/releases/download/v4.18.41/NapCat.Shell.Windows.Node.zip) |
| AstrBot | 4.29.3 | [PyPI](https://pypi.org/project/astrbot/) ｜ [GitHub](https://github.com/AstrBotDevs/AstrBot) |
| LLMPerception | `be48a2b3` | [仓库](https://github.com/miaoxutao123/astrbot_plugin_LLMPerception) |
| qzone | `f474c50c` | [仓库](https://github.com/Zhalslar/astrbot_plugin_qzone) |
| music | `9022a710` | [仓库](https://github.com/Zhalslar/astrbot_plugin_music) |

完整 URL、大小与 SHA256 见 [`installer/components.json`](installer/components.json)；NapCat 是
`51fbb10e…7d3f0`（124,089,498 B）。pip 依赖默认走清华镜像，镜像失败只回退官方 PyPI 一次；
NapCat / uv / Python / 插件不走任何第三方镜像。安装器已经用不到 7-Zip；`AGENTS.md` 的 agent 路线仍按原协议用 `7zr.exe`。

## 目录

```
qqbot-autopilot/
├── 安装.bat                       # 零 AI 安装器入口（Windows 中文控制台）
├── installer/
│   ├── components.json            # 固定版本、URL、SHA256、插件 commit
│   ├── lib/                       # 组件/配置/扫码等待/端口与 LLM 校验工具
│   └── packages/                  # 离线预置包（不入库，随交付介质分发）
├── launcher/                      # 启动.bat / 停止.bat（安装后位于安装根目录）
├── docs/
│   ├── customer/                  # 对客：使用说明、填 Key、两册 AI 教学手册、post-login
│   ├── internal/                  # 内部：安装清单、交付夜分工卡
│   └── templates/                 # OneBot 模板、人设-小满
├── AGENTS.md                      # 可选：agent 自举协议
├── MAINTENANCE.md                 # 每周巡检与自修白名单
├── CHANGELOG.md
└── README.md
```

仓库不含 `runtime/`、`secrets/`、`installer/packages/`、`安装信息.txt`、日志和 token；它们由交付方预置或在目标机现场生成。
`安装.bat` 用 Windows 中文控制台编码（CP936/GBK）、CRLF、无 BOM；改它时要保持这个编码，不然中文会乱。
v0.1.0 的 IExpress 三件套和根目录旧 `安装包.exe` 已经在 v0.2.0 退役并从工作树删除，历史看 `CHANGELOG.md` 和 git 记录。

> 交付打包：用 `git archive -o qqbot-autopilot.zip HEAD`（或只压缩 git 跟踪的文件）。
> `payload.7z`、`installer/packages/`、`runtime/`、`.tmp/` 是本地产物，不要打进默认交付 zip。

## 弱网 / 离线：installer/packages/

交付方可以把已经校验过的组件，按下面的文件名放进 `installer/packages/`（整个目录不入库）。安装器命中就直接用、
跳过下载；校验不过就回到官方源重下，绝不用第三方包顶替：

| 预置文件 | 组件 |
|---|---|
| `uv-x86_64-pc-windows-msvc.zip` | uv 0.12.23（也支持 `uv.exe`，仅做版本复核） |
| `python-3.12.15-standalone.tar.gz` | Python 3.12.15（解压后复核版本） |
| `NapCat.Shell.Windows.Node.zip` | NapCat v4.18.41 |
| `astrbot_plugin_LLMPerception.zip` / `astrbot_plugin_qzone.zip` / `astrbot_plugin_music.zip` | 三个固定 commit 插件 |
| `wheels/` | 可选：AstrBot 与插件依赖的离线 wheels |

环境变量 `QQBOT_PACKAGES=<目录>` 可以改预置目录。文件名必须一字不差；`latest`、散装 zip、带 `(1)` 的副本
一律当没有。

## 可选：源码自举（agent 路线）

如果你有自己的 agent，也可以把仓库交给它，让它读 [`AGENTS.md`](AGENTS.md) 按 §1–§9 执行：环境调查 → 组件获取 →
配置落盘 → 三个人类检查点（扫码 / Key / 管理员与白名单）→ 四联自检。这条路线仍默认装到 `C:\QQBot`，组件预算 60 分钟，
其余阶段 10 分钟红线；`installer/` 和 agent 路线可以共存，互不依赖。

## 安全与边界

- 所有服务只绑 `127.0.0.1`；不要把 3001/6099/6185 映射到公网，也别把面板暴露到局域网。
- 零管理员、零注册表、零 Windows 服务；只写安装目录（开机自启是你选「是」时，往当前用户启动文件夹放一个快捷方式）。
- token 只存在 `<安装目录>\runtime\secrets\`；模型 Key 只写本机 `cmd_config.json`，不回显、不写日志、不进报告。
- 安装时 Key 输入可见；旁边有人就先清场，或者用 `key.txt` 并装完删除。
- 用 QQ 小号，不用主号；个人号协议有平台风控的风险。

## 已知限制

- 安装器是 `.bat` + Python 脚本，不是签名的 `.exe`；Windows SmartScreen / 杀毒软件可能提示，得人工选「仍要运行 / 允许」。
- 模型 Key 输入可见（按需求保留），没有隐藏输入；用 `key.txt` 能避开旁人看到屏幕。
- 扫码等待最多 10 分钟；超时会停住并提示重跑，已装组件不会重下。
- 组件下载依赖 GitHub / PyPI 可达性；国内弱网建议用 `installer/packages/` 预置。
- 安装器不自动更新组件；换版本必须改 `installer/components.json` 并同步 README / CHANGELOG。
- v0.2.0 的部分固定源（NapCat、qzone/music 插件）可能随上游删除而失效；下载返回 404 时优先用 `installer/packages/` 预置包，或按 `components.json` 更新版本与 SHA256。
- 中转站与 Key 是耗材，额度/地址/模型变更要主人拿主意；安装器只做一次连通性验证。

## 运维

长期在线交给根目录 [`MAINTENANCE.md`](MAINTENANCE.md)：每周巡检七项、自修白名单、辅助用户守则、红线与报障格式。

## 安全与免责

本项目是独立交付套件，和腾讯、NapCat、AstrBot 官方没有隶属关系；请遵守 QQ 平台规则及第三方组件许可。
软件按现状提供，使用风险自负。

## License

MIT，见 [LICENSE](LICENSE)。
