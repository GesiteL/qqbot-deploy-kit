@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 936 >nul
title QQBot 安装器 v0.2.0
cd /d "%~dp0"

set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
set "VERSION=0.2.0"
set "MANIFEST=%SRC%\installer\components.json"
set "PKGDIR=%SRC%\installer\packages"
if defined QQBOT_PACKAGES set "PKGDIR=%QQBOT_PACKAGES%"
set "LOG=%SRC%\install.log"
set "TARGET="
set "PY="
set "SYMPTOM="
set "ADVICE="
set "PYTHONIOENCODING=gbk:replace"
set "TAREXE=%SystemRoot%\System32\tar.exe"
if not exist "%TAREXE%" set "TAREXE="

call :banner
call :log "INSTALL_START version=%VERSION%"

if not exist "%MANIFEST%" goto missing
if not exist "%SRC%\installer\lib\components.py" goto missing
if not exist "%SRC%\installer\lib\config.py" goto missing
if not exist "%SRC%\installer\lib\verify.py" goto missing
if not exist "%SRC%\installer\lib\wait_login.py" goto missing
if not exist "%SRC%\installer\lib\process_ctl.py" goto missing
if not exist "%SRC%\launcher\启动.bat" goto missing
if not exist "%SRC%\launcher\停止.bat" goto missing
if not exist "%SRC%\docs\templates\onebot11-template.json" goto missing
if not exist "%SRC%\docs\templates\人设-小满.md" goto missing

call :stage 1 7 "环境检查与安装位置"
call :check_env
if errorlevel 1 goto fail_env
call :ask_target
if errorlevel 1 goto fail_env
call :copy_app_files
if errorlevel 1 goto fail_env

call :stage 2 7 "安装组件（首次约 10-30 分钟）"
call :bootstrap_uv
if errorlevel 1 goto fail_components
call :bootstrap_python
if errorlevel 1 goto fail_components
call :run_components
if errorlevel 1 goto fail_components

call :stage 3 7 "生成配置"
"%PY%" "%SRC%\installer\lib\config.py" init --target "%TARGET%"
if errorlevel 1 goto fail_config
call :log "CONFIG_INIT_OK"

call :stage 4 7 "扫码登录"
call :prepare_qr
if errorlevel 1 goto fail_login
call :start_napcat
if errorlevel 1 goto fail_login
call :wait_ports 6099 120
if errorlevel 1 goto fail_login
call :open_qr
"%PY%" "%SRC%\installer\lib\wait_login.py" --target "%TARGET%" --timeout 600
if errorlevel 1 goto fail_login
call :stop_napcat
if errorlevel 1 goto fail_login
"%PY%" "%SRC%\installer\lib\config.py" apply-onebot --target "%TARGET%" --uin-file "%TARGET%\runtime\.install\uin.txt"
if errorlevel 1 goto fail_login
call :log "ONEBOT_CONFIG_OK"

call :stage 5 7 "连接 AstrBot 并填写模型与管理员"
call :start_astrbot
if errorlevel 1 goto fail_connect
call :wait_ports 3001,6185 180
if errorlevel 1 goto fail_connect
call :start_napcat
if errorlevel 1 goto fail_connect
call :wait_ports 6099 120
if errorlevel 1 goto fail_connect
"%PY%" "%SRC%\installer\lib\verify.py" assert-connection --timeout 90
if errorlevel 1 goto fail_connect
call :log "ONEBOT_CONNECTED"

call :ask_key
if errorlevel 1 goto fail_config
call :ask_admin
if errorlevel 1 goto fail_config
call :ask_groups
call :ask_persona
call :ask_autostart
call :stop_astrbot
if errorlevel 1 goto fail_final
call :apply_user
if errorlevel 1 goto fail_config
call :start_astrbot
if errorlevel 1 goto fail_final
call :wait_ports 3001,6185 180
if errorlevel 1 goto fail_final
"%PY%" "%SRC%\installer\lib\verify.py" assert-connection --timeout 90
if errorlevel 1 goto fail_final

call :stage 6 7 "模型连通性检查"
"%PY%" "%SRC%\installer\lib\verify.py" llm --target "%TARGET%"
if errorlevel 1 goto fail_final

call :stage 7 7 "终验与收尾"
"%PY%" "%SRC%\installer\lib\verify.py" ports
if errorlevel 1 goto fail_final
if /i "%AUTOSTART%"=="yes" call :do_autostart
"%PY%" "%SRC%\installer\lib\config.py" install-info --target "%TARGET%"
if errorlevel 1 goto fail_final
goto success

:missing
set "SYMPTOM=安装文件不完整，找不到 installer 或 launcher 或 docs\templates"
set "ADVICE=重新解压仓库 zip，确认 安装.bat 与 installer 文件夹在同一层，再双击 安装.bat"
goto fail

:fail_env
if not defined SYMPTOM set "SYMPTOM=环境检查或安装位置没有通过"
if not defined ADVICE set "ADVICE=按上面的提示处理后，重新双击 安装.bat"
goto fail

:fail_components
if not defined SYMPTOM set "SYMPTOM=组件没有装完"
if not defined ADVICE set "ADVICE=检查网络或代理后重新运行安装器；已经装好的组件会自动跳过，不会重下"
goto fail

:fail_config
if not defined SYMPTOM set "SYMPTOM=配置没有写完"
if not defined ADVICE set "ADVICE=检查上面提示的地址/Key/QQ/群号格式，或确认文件没有被占用，然后重试"
goto fail

:fail_login
if not defined SYMPTOM set "SYMPTOM=扫码登录没有完成"
if not defined ADVICE set "ADVICE=确认用手机 QQ 小号扫 NapCat 窗口里的码并点了确认；重新运行安装器可重试"
goto fail

:fail_connect
if not defined SYMPTOM set "SYMPTOM=NapCat 没有连上 AstrBot"
if not defined ADVICE set "ADVICE=先运行 停止.bat 释放端口，再重新运行安装器；若反复失败，把 install.log 发给交付方"
goto fail

:fail_final
if not defined SYMPTOM set "SYMPTOM=最后检查没有通过"
if not defined ADVICE set "ADVICE=检查模型地址/Key/额度，确认 3001、6099、6185 没有被其他软件占用，然后重试"
goto fail

:fail
echo.
echo ============================================================
echo   安装没有完成
echo ------------------------------------------------------------
echo   现在看到：%SYMPTOM%
echo   你可以试：%ADVICE%
if not defined TARGET goto fail_no_target
echo   还不行：把 %TARGET%\install.log 发给交付方
goto fail_hint_done
:fail_no_target
echo   还不行：把本窗口截图发给交付方
:fail_hint_done
echo ============================================================
if not defined TARGET goto fail_no_rollback
echo   想彻底重来：先双击 %TARGET%\停止.bat，再把这个目录改名或删除，然后重新运行 安装.bat。
:fail_no_rollback
if defined PY if exist "%PY%" if exist "%TARGET%" if exist "%SRC%\installer\lib\process_ctl.py" "%PY%" "%SRC%\installer\lib\process_ctl.py" --target "%TARGET%" --which all >nul 2>&1
set "FAILMSG=%SYMPTOM% / %ADVICE%"
powershell -NoProfile -Command "Add-Content -LiteralPath $env:LOG -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' FAIL ' + $env:FAILMSG) -Encoding UTF8"
set "FAILMSG="
call :log "FAIL"
echo.
echo 按任意键关闭本窗口...
pause >nul
exit /b 1

:success
call :cleanup
echo.
echo ============================================================
echo   安装完成
echo ------------------------------------------------------------
echo   安装目录：%TARGET%
echo   控制台：http://127.0.0.1:6185
echo   NapCat：http://127.0.0.1:6099
echo.
echo   去群里发一句「在吗」，看它回不回。
echo   以后开机：双击 启动.bat；关闭：双击 停止.bat。
echo   卸载：先双击 停止.bat，再删除整个安装目录。
echo ============================================================
if /i not "%AUTOSTART%"=="yes" goto success_no_autostart
echo   已设置开机自启。
:success_no_autostart
call :log "INSTALL_SUCCESS"
echo.
echo 按任意键关闭本窗口...
pause >nul
exit /b 0

:banner
echo.
echo ############################################################
echo #                                                          #
echo #              QQBot 安装器  v0.2.0                        #
echo #      零 AI 安装：扫码、回答几个问题，其余自动完成        #
echo #                                                          #
echo ############################################################
echo.
exit /b 0

:log
if not exist "%LOG%" echo. > "%LOG%" 2>nul
>>"%LOG%" echo [%TIME%] %~1
exit /b 0

:stage
echo.
echo ============================================================
echo   第 %~1 步 / 共 %~2 步：%~3
echo ============================================================
echo.
call :log "STAGE %~1/%~2"
exit /b 0

:check_env
echo [检查] 系统、PowerShell 与端口...
if /i not "%PROCESSOR_ARCHITECTURE%"=="AMD64" goto env_arch
where powershell >nul 2>&1
if errorlevel 1 goto env_ps
set "BUSY="
for /f "delims=" %%i in ('powershell -NoProfile -Command "$p=@(); foreach($x in 3001,6099,6185){ if(Get-NetTCPConnection -State Listen -LocalPort $x -ErrorAction SilentlyContinue){$p+=$x} }; if($p.Count -gt 0){$p -join ','}else{'FREE'}"') do set "BUSY=%%i"
if not defined BUSY set "BUSY=UNKNOWN"
if /i "%BUSY%"=="FREE" goto env_ports_ok
if /i "%BUSY%"=="UNKNOWN" goto env_ports_unknown
set "SYMPTOM=端口 %BUSY% 被占用，旧机器人可能还在运行"
set "ADVICE=先双击旧目录里的 停止.bat，或重启电脑后再运行安装器；不要同时开两份机器人"
exit /b 1
:env_arch
set "SYMPTOM=这台电脑不是 64 位 Intel/AMD Windows"
set "ADVICE=本安装器只支持 Windows 11 x64，请换一台电脑或联系交付方"
exit /b 1
:env_ps
set "SYMPTOM=系统里找不到 PowerShell"
set "ADVICE=Windows 11 自带的 PowerShell 被删除了；请恢复系统组件后再试"
exit /b 1
:env_ports_unknown
set "SYMPTOM=读不到端口占用状态"
set "ADVICE=确认系统 PowerShell 能正常运行，然后重试"
exit /b 1
:env_ports_ok
echo [OK] 端口 3001/6099/6185 空闲。
exit /b 0

:ask_target
echo.
echo [第 1 步] 选择安装位置
echo   机器人只装在一个文件夹里：盘符:\QQBot
echo   不写注册表、不装系统服务、不需要管理员权限。
echo.
set "D="
set /p "D=请输入盘符，直接回车 = C 盘： "
if not defined D set "D=C"
set "D=%D: =%"
set "D=%D::=%"
set "D=%D:\=%"
set "D=%D:/=%"
set "D=%D:QQBot=%"
echo %D%| findstr /r "^[A-Za-z]$" >nul
if errorlevel 1 goto target_bad
for %%d in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do if /i "%D%"=="%%d" set "D=%%d"
if /i "%D%"=="A" goto target_bad
if /i "%D%"=="B" goto target_bad
if not exist "%D%:\" goto target_bad
set "FREEGB="
for /f "delims=" %%i in ('powershell -NoProfile -Command "$d=Get-PSDrive -Name %D% -ErrorAction SilentlyContinue; if($d){[math]::Floor($d.Free/1GB)}"') do set "FREEGB=%%i"
if not defined FREEGB goto target_nofree
if %FREEGB% LSS 10 goto target_low
set "TARGET=%D%:\QQBot"
set "TCONFIRM=0"
if exist "%TARGET%\" set "TCONFIRM=1"
if "%TCONFIRM%"=="1" call :confirm_target
if "%TCONFIRM%"=="1" if errorlevel 1 goto target_cancel
if not exist "%TARGET%\runtime" mkdir "%TARGET%\runtime"
if not exist "%TARGET%\logs" mkdir "%TARGET%\logs"
if not exist "%TARGET%\docs" mkdir "%TARGET%\docs"
if not exist "%TARGET%\runtime\secrets" mkdir "%TARGET%\runtime\secrets"
if not exist "%TARGET%\runtime\.install" mkdir "%TARGET%\runtime\.install"
if not exist "%TARGET%\runtime\.downloads" mkdir "%TARGET%\runtime\.downloads"
if not exist "%TARGET%\runtime" goto target_nodir
if not exist "%TARGET%\docs" goto target_nodir
call :adopt_log
echo [OK] 安装目录：%TARGET%
echo [OK] %D% 盘剩余 %FREEGB% GB。
exit /b 0
:target_bad
set "SYMPTOM=盘符不对或这个盘不存在"
set "ADVICE=输入 C/D/E/F 这样的单个字母；直接回车是 C 盘"
exit /b 1
:target_nofree
set "SYMPTOM=读不到 %D% 盘的剩余空间"
set "ADVICE=确认这是本机固定硬盘，不是网络盘或光驱；换一个盘再试"
exit /b 1
:target_low
set "SYMPTOM=%D% 盘只剩 %FREEGB% GB，少于 10 GB"
set "ADVICE=清理磁盘空间，或换一个剩余空间大于 10 GB 的盘"
exit /b 1
:target_nodir
set "SYMPTOM=无法创建安装目录 %TARGET%"
set "ADVICE=换一个盘，或检查这个目录是否只读、被另一个程序占用"
exit /b 1
:target_cancel
set "TARGET="
set "SYMPTOM=你取消了本次安装"
set "ADVICE=没有改动任何文件；想装的时候重新双击 安装.bat"
exit /b 1

:confirm_target
set "KNOWN=0"
if exist "%TARGET%\安装信息.txt" set "KNOWN=1"
if exist "%TARGET%\runtime\astrbot\data" set "KNOWN=1"
if "%KNOWN%"=="1" goto confirm_known
echo.
echo [提示] %TARGET% 已经存在，但不像 QQBot 安装目录。
set "ANS=N"
set /p "ANS=继续会写入这个目录，继续？[y/N]： "
if /i "%ANS:~0,1%"=="y" exit /b 0
echo [提示] 已取消，没有改动文件。
exit /b 1
:confirm_known
echo.
echo [提示] 检测到已有 QQBot 安装：会保留 token 与数据，只更新组件和配置。
set "ANS=Y"
set /p "ANS=继续更新？[Y/n]： "
if /i "%ANS:~0,1%"=="n" exit /b 1
exit /b 0

:adopt_log
if /i "%SRC%"=="%TARGET%" goto adopt_log_same
if exist "%TARGET%\install.log" copy /y "%TARGET%\install.log" "%TARGET%\install.log.bak" >nul 2>&1
if exist "%LOG%" copy /y "%LOG%" "%TARGET%\install.log" >nul 2>&1
if exist "%LOG%" del /f /q "%LOG%" >nul 2>&1
:adopt_log_same
set "LOG=%TARGET%\install.log"
call :log "TARGET=%TARGET%"
exit /b 0

:copy_app_files
echo [准备] 复制启动器、说明与模板...
if /i "%SRC%"=="%TARGET%" goto copy_launchers
xcopy /e /i /y "%SRC%\docs\customer" "%TARGET%\docs\customer\" >nul
if errorlevel 1 goto copy_fail
xcopy /e /i /y "%SRC%\docs\templates" "%TARGET%\docs\templates\" >nul
if errorlevel 1 goto copy_fail
:copy_launchers
copy /y "%SRC%\launcher\启动.bat" "%TARGET%\启动.bat" >nul
if errorlevel 1 goto copy_fail
copy /y "%SRC%\launcher\停止.bat" "%TARGET%\停止.bat" >nul
if errorlevel 1 goto copy_fail
if exist "%SRC%\README.md" copy /y "%SRC%\README.md" "%TARGET%\README.md" >nul
if exist "%SRC%\MAINTENANCE.md" copy /y "%SRC%\MAINTENANCE.md" "%TARGET%\MAINTENANCE.md" >nul
if exist "%SRC%\LICENSE" copy /y "%SRC%\LICENSE" "%TARGET%\LICENSE" >nul
if not exist "%TARGET%\docs\templates\onebot11-template.json" goto copy_fail
if not exist "%TARGET%\docs\templates\人设-小满.md" goto copy_fail
call :log "APP_FILES_OK"
exit /b 0
:copy_fail
set "SYMPTOM=复制启动器或模板失败"
set "ADVICE=确认安装目录可写，或换一个盘；不要从只读的压缩包里直接运行"
exit /b 1

:bootstrap_uv
echo [组件 1/3] 检查 uv 0.12.23 ...
set "UVOK=0"
call :uv_version_ok
if "%UVOK%"=="1" goto uv_ready
if exist "%TARGET%\runtime\uv" move "%TARGET%\runtime\uv" "%TARGET%\runtime\.install\backup\uv-%RANDOM%%RANDOM%" >nul 2>&1
set "CJ=%MANIFEST%"
set "UV_URL="
set "UV_SHA="
set "UV_PKG="
set "UV_EXE_PKG="
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$c=Get-Content -LiteralPath $env:CJ -Raw | ConvertFrom-Json; $c.uv.url"`) do set "UV_URL=%%i"
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$c=Get-Content -LiteralPath $env:CJ -Raw | ConvertFrom-Json; $c.uv.sha256"`) do set "UV_SHA=%%i"
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$c=Get-Content -LiteralPath $env:CJ -Raw | ConvertFrom-Json; $c.uv.package"`) do set "UV_PKG=%%i"
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "$c=Get-Content -LiteralPath $env:CJ -Raw | ConvertFrom-Json; $c.uv.exe_package"`) do set "UV_EXE_PKG=%%i"
if not defined UV_PKG set "UV_PKG=uv-x86_64-pc-windows-msvc.zip"
if not defined UV_EXE_PKG set "UV_EXE_PKG=uv.exe"
if not defined UV_URL goto uv_manifest_bad
if not defined UV_SHA goto uv_manifest_bad
if not exist "%PKGDIR%\%UV_EXE_PKG%" goto uv_try_zip
if not exist "%TARGET%\runtime\uv" mkdir "%TARGET%\runtime\uv"
copy /y "%PKGDIR%\%UV_EXE_PKG%" "%TARGET%\runtime\uv\uv.exe" >nul 2>&1
set "UVOK=0"
call :uv_version_ok
if "%UVOK%"=="1" goto uv_preloaded
echo [警告] 预置 uv.exe 版本不对，改用官方压缩包。
del /f /q "%TARGET%\runtime\uv\uv.exe" >nul 2>&1
:uv_try_zip
set "UVFROM=local"
set "UVZIP=%PKGDIR%\%UV_PKG%"
if exist "%UVZIP%" goto uv_verify
:uv_download
set "UVFROM=download"
set "UVZIP=%TARGET%\runtime\.downloads\%UV_PKG%"
if exist "%UVZIP%" del /f /q "%UVZIP%" >nul 2>&1
call :download "%UV_URL%" "%UVZIP%" "uv"
if errorlevel 1 goto uv_download_fail
:uv_verify
call :sha_check "%UVZIP%" "%UV_SHA%" "uv"
if not errorlevel 1 goto uv_extract
if /i "%UVFROM%"=="download" goto uv_hash_fail
echo [警告] 预置 uv 包校验失败，按协议改用官方源。
goto uv_download
:uv_extract
if exist "%TARGET%\runtime\uv" move "%TARGET%\runtime\uv" "%TARGET%\runtime\.install\backup\uv-%RANDOM%%RANDOM%" >nul 2>&1
mkdir "%TARGET%\runtime\uv" >nul 2>&1
if not defined TAREXE goto uv_extract_ps
"%TAREXE%" -xf "%UVZIP%" -C "%TARGET%\runtime\uv" 2>nul
if exist "%TARGET%\runtime\uv\uv.exe" goto uv_check_exe
:uv_extract_ps
set "UZ=%UVZIP%"
set "UD=%TARGET%\runtime\uv"
powershell -NoProfile -Command "Expand-Archive -LiteralPath $env:UZ -DestinationPath $env:UD -Force"
if not exist "%TARGET%\runtime\uv\uv.exe" goto uv_extract_fail
:uv_check_exe
set "UVOK=0"
call :uv_version_ok
if not "%UVOK%"=="1" goto uv_version_fail
:uv_ready
echo [OK] uv 0.12.23 已存在。
call :log "UV_OK"
exit /b 0
:uv_preloaded
echo [OK] uv 0.12.23 就绪。
call :log "UV_OK"
exit /b 0
:uv_manifest_bad
set "SYMPTOM=installer\components.json 不完整，读不到 uv 地址"
set "ADVICE=重新解压仓库 zip，不要只复制 安装.bat"
exit /b 1
:uv_download_fail
set "SYMPTOM=uv 下载失败"
set "ADVICE=检查网络或代理；也可以把 uv 压缩包放到 installer\packages 后重试"
exit /b 1
:uv_hash_fail
set "SYMPTOM=uv 的 SHA256 校验失败"
set "ADVICE=删除 runtime\.downloads 里的 uv 文件后重试；不要用第三方来源的包"
exit /b 1
:uv_extract_fail
set "SYMPTOM=uv 压缩包解不开"
set "ADVICE=删除 runtime\.downloads 里的 uv 文件后重试"
exit /b 1
:uv_version_fail
set "SYMPTOM=uv 装好后版本不是 0.12.23"
set "ADVICE=删除 runtime\uv 后重试；如果还不行，把 install.log 发给交付方"
exit /b 1

:uv_version_ok
set "UVOK=0"
if not exist "%TARGET%\runtime\uv\uv.exe" exit /b 0
set "UV=%TARGET%\runtime\uv\uv.exe"
set "UVVER="
set "UVVERFILE=%TARGET%\runtime\.install\uvver.txt"
powershell -NoProfile -Command "& $env:UV --version" > "%UVVERFILE%" 2>nul
set /p UVVER=<"%UVVERFILE%"
del /f /q "%UVVERFILE%" >nul 2>&1
if not defined UVVER exit /b 0
echo %UVVER%| findstr /c:"0.12.23" >nul
if errorlevel 1 exit /b 0
set "UVOK=1"
exit /b 0

:bootstrap_python
echo [组件 2/3] 检查 Python 3.12.15 ...
set "PY=%TARGET%\runtime\python\python.exe"
set "PYOK=0"
call :python_version_ok
if "%PYOK%"=="1" goto python_ready
if exist "%TARGET%\runtime\python" move "%TARGET%\runtime\python" "%TARGET%\runtime\.install\backup\python-%RANDOM%%RANDOM%" >nul 2>&1
set "PYPKG=%PKGDIR%\python-3.12.15-standalone.tar.gz"
if not exist "%PYPKG%" goto py_via_uv
if not defined TAREXE goto py_via_uv
set "PYEX=%TARGET%\runtime\.python-extract"
if exist "%PYEX%" rd /s /q "%PYEX%" >nul 2>&1
mkdir "%PYEX%" >nul 2>&1
"%TAREXE%" -xzf "%PYPKG%" -C "%PYEX%" 2>nul
if errorlevel 1 goto py_pkg_bad
set "PYS=%PYEX%"
set "PYT=%TARGET%"
powershell -NoProfile -Command "$src=Get-ChildItem -LiteralPath $env:PYS -Recurse -Filter python.exe | Select-Object -First 1; if(-not $src){exit 1}; Copy-Item (Split-Path $src.FullName -Parent) (Join-Path $env:PYT 'runtime\python') -Recurse -Force"
if errorlevel 1 goto py_pkg_bad
if exist "%PYEX%" rd /s /q "%PYEX%" >nul 2>&1
set "PYOK=0"
call :python_version_ok
if not "%PYOK%"=="1" goto py_pkg_bad
echo [OK] 使用预置 Python 3.12.15。
call :log "PYTHON_PRELOADED"
exit /b 0
:py_pkg_bad
if exist "%TARGET%\runtime\python" move "%TARGET%\runtime\python" "%TARGET%\runtime\.install\backup\python-%RANDOM%%RANDOM%" >nul 2>&1
echo [警告] 预置 Python 不可用，改用官方 uv 安装。
:py_via_uv
if not exist "%TARGET%\runtime\uv\uv.exe" goto py_no_uv
set "UV=%TARGET%\runtime\uv\uv.exe"
set "UV_PYTHON_INSTALL_DIR=%TARGET%\runtime\.uv\python"
set "UV_CACHE_DIR=%TARGET%\runtime\.uv\cache"
set "UV_NO_MODIFY_PATH=1"
echo [组件] 用 uv 安装 Python 3.12.15，需要联网，可能几分钟...
powershell -NoProfile -Command "& $env:UV python install 3.12.15"
if not errorlevel 1 goto py_copy
echo [提示] 第一次失败，重试一次...
powershell -NoProfile -Command "& $env:UV python install 3.12.15"
if errorlevel 1 goto py_install_fail
:py_copy
if exist "%TARGET%\runtime\python" move "%TARGET%\runtime\python" "%TARGET%\runtime\.install\backup\python-%RANDOM%%RANDOM%" >nul 2>&1
set "PYT=%TARGET%"
powershell -NoProfile -Command "$py=(& $env:UV python find 3.12.15 | Select-Object -Last 1); if(-not $py){exit 1}; Copy-Item (Split-Path $py -Parent) (Join-Path $env:PYT 'runtime\python') -Recurse -Force"
if errorlevel 1 goto py_copy_fail
set "PYOK=0"
call :python_version_ok
if not "%PYOK%"=="1" goto py_version_fail
echo [OK] Python 3.12.15 就绪。
call :log "PYTHON_OK"
exit /b 0
:python_ready
echo [OK] Python 3.12.15 已存在。
exit /b 0
:py_no_uv
set "SYMPTOM=uv 不存在，无法安装 Python"
set "ADVICE=重新运行安装器；如果还不行，把 install.log 发给交付方"
exit /b 1
:py_install_fail
set "SYMPTOM=Python 3.12.15 下载/安装失败"
set "ADVICE=检查网络或代理；也可以把 python-3.12.15-standalone.tar.gz 放到 installer\packages 后重试"
exit /b 1
:py_copy_fail
set "SYMPTOM=Python 安装后复制到 runtime\python 失败"
set "ADVICE=确认安装目录可写，然后重试"
exit /b 1
:py_version_fail
set "SYMPTOM=Python 装好后版本不是 3.12.15"
set "ADVICE=删除 runtime\python 与 runtime\.uv 后重试"
exit /b 1

:python_version_ok
set "PYOK=0"
set "PY=%TARGET%\runtime\python\python.exe"
if not exist "%PY%" exit /b 0
set "PYVER="
set "PYVERFILE=%TARGET%\runtime\.install\pyver.txt"
powershell -NoProfile -Command "& $env:PY --version" > "%PYVERFILE%" 2>nul
set /p PYVER=<"%PYVERFILE%"
del /f /q "%PYVERFILE%" >nul 2>&1
if not defined PYVER exit /b 0
echo %PYVER%| findstr /c:"3.12.15" >nul
if errorlevel 1 exit /b 0
set "PYOK=1"
exit /b 0

:run_components
echo [组件 3/3] 安装 NapCat、AstrBot 与插件...
"%PY%" "%SRC%\installer\lib\components.py" --target "%TARGET%" --packages "%PKGDIR%" --manifest "%MANIFEST%"
if errorlevel 1 exit /b 1
call :log "COMPONENTS_OK"
exit /b 0

:download
set "DL_URL=%~1"
set "DL_DEST=%~2"
set "DL_NAME=%~3"
if not defined DL_URL goto download_fail
where curl >nul 2>&1
if errorlevel 1 goto download_ps
if exist "%DL_DEST%" del /f /q "%DL_DEST%" >nul 2>&1
call :log "DOWNLOAD %DL_NAME%"
curl.exe -fL --http1.1 --retry 2 --retry-delay 2 --connect-timeout 20 --max-time 1800 -o "%DL_DEST%" "%DL_URL%"
if errorlevel 1 exit /b 1
exit /b 0
:download_ps
call :log "DOWNLOAD_PS %DL_NAME%"
set "DL_DEST_ENV=%DL_DEST%"
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri $env:DL_URL -OutFile $env:DL_DEST_ENV -UseBasicParsing -TimeoutSec 1800; exit 0 } catch { exit 1 }"
if errorlevel 1 exit /b 1
exit /b 0
:download_fail
exit /b 1

:sha_check
set "SHA_FILE=%~1"
set "SHA_EXPECT=%~2"
set "SHA_NAME=%~3"
set "SHA_GOT="
for /f "delims=" %%h in ('powershell -NoProfile -Command "if(Test-Path -LiteralPath $env:SHA_FILE){(Get-FileHash -LiteralPath $env:SHA_FILE -Algorithm SHA256).Hash}"') do set "SHA_GOT=%%h"
if not defined SHA_GOT goto sha_fail
if /i not "%SHA_GOT%"=="%SHA_EXPECT%" goto sha_fail
echo [OK] %SHA_NAME% 的 SHA256 校验通过。
exit /b 0
:sha_fail
echo [错误] %SHA_NAME% 的 SHA256 校验失败。
exit /b 1

:start_napcat
set "NPEXE=%TARGET%\runtime\napcat\node.exe"
set "NPDIR=%TARGET%\runtime\napcat"
if not exist "%NPEXE%" goto start_napcat_fail
powershell -NoProfile -Command "Start-Process -FilePath $env:NPEXE -ArgumentList 'index.js' -WorkingDirectory $env:NPDIR -WindowStyle Minimized"
if errorlevel 1 goto start_napcat_fail
call :log "NAPCAT_STARTED"
exit /b 0
:start_napcat_fail
set "SYMPTOM=NapCat 启动失败"
set "ADVICE=确认 runtime\napcat\node.exe 存在；如果杀毒软件拦截了，请允许后重试"
exit /b 1

:start_astrbot
set "ABPY=%TARGET%\runtime\python\python.exe"
set "ABDIR=%TARGET%\runtime\astrbot"
set "ASTRBOT_ROOT=%ABDIR%"
if not exist "%ABPY%" goto start_astrbot_fail
if not exist "%ABDIR%\data\cmd_config.json" goto start_astrbot_fail
powershell -NoProfile -Command "Start-Process -FilePath $env:ABPY -ArgumentList '-m','astrbot.cli','run' -WorkingDirectory $env:ABDIR -WindowStyle Minimized"
if errorlevel 1 goto start_astrbot_fail
call :log "ASTRBOT_STARTED"
exit /b 0
:start_astrbot_fail
set "SYMPTOM=AstrBot 启动失败"
set "ADVICE=确认组件安装完成；如果杀毒软件拦截了 python.exe，请允许后重试"
exit /b 1

:stop_napcat
"%PY%" "%SRC%\installer\lib\process_ctl.py" --target "%TARGET%" --which napcat --wait-ports 6099
exit /b %ERRORLEVEL%

:stop_astrbot
"%PY%" "%SRC%\installer\lib\process_ctl.py" --target "%TARGET%" --which astrbot --wait-ports 3001,6185
exit /b %ERRORLEVEL%

:prepare_qr
"%PY%" "%SRC%\installer\lib\config.py" prepare-login --target "%TARGET%"
if errorlevel 1 exit /b 1
call :log "PREPARE_LOGIN_OK"
exit /b 0

:open_qr
set "QR=%TARGET%\runtime\napcat\napcat\cache\qrcode.png"
set /a QI=0
:open_qr_loop
if exist "%QR%" goto open_qr_do
set /a QI+=1
if %QI% GEQ 15 exit /b 0
ping -n 3 127.0.0.1 >nul
goto open_qr_loop
:open_qr_do
echo [提示] 已打开二维码图片；也可以直接看任务栏里的 NapCat 黑色窗口。
start "" "%QR%"
exit /b 0

:wait_ports
"%PY%" "%SRC%\installer\lib\verify.py" wait --ports "%~1" --timeout %~2
exit /b %ERRORLEVEL%

:ask_key
set "BASE="
set "KEY="
if not exist "%SRC%\key.txt" goto ask_key_manual
(
  set /p "BASE="
  set /p "KEY="
) < "%SRC%\key.txt"
if not defined BASE goto ask_key_manual
if not defined KEY goto ask_key_manual
echo [提示] 已从 key.txt 读取地址与 Key（Key 不回显）。安装完成后请删除 key.txt。
goto ask_key_done
:ask_key_manual
echo.
echo [模型配置] 请粘贴中转站地址与模型 Key。地址通常以 /v1 结尾。
echo [提示] Key 输入时会显示在屏幕上，请确认周围无人。
set /a KT=0
:ask_key_loop
set /a KT+=1
set "BASE="
set /p "BASE=中转站地址： "
set "KEY="
set /p "KEY=模型 API Key： "
if not defined BASE goto ask_key_retry
if not defined KEY goto ask_key_retry
goto ask_key_done
:ask_key_retry
echo [提示] 地址或 Key 不能为空。
if %KT% GEQ 2 goto ask_key_fail
goto ask_key_loop
:ask_key_fail
set "SYMPTOM=中转站地址或 Key 为空"
set "ADVICE=重新运行安装器，完整粘贴地址与 Key；不要把 Key 发到群里"
exit /b 1
:ask_key_done
exit /b 0

:ask_admin
set /a AT=0
:ask_admin_loop
set /a AT+=1
set "ADMIN="
set /p "ADMIN=管理员 QQ 号（5-11 位数字）： "
set "ADMIN=%ADMIN: =%"
if not defined ADMIN goto ask_admin_retry
echo %ADMIN%| findstr /r "^[0-9][0-9]*$" >nul
if errorlevel 1 goto ask_admin_retry
if "%ADMIN:~4%"=="" goto ask_admin_retry
if not "%ADMIN:~11%"=="" goto ask_admin_retry
exit /b 0
:ask_admin_retry
echo [提示] 管理员 QQ 号只能填 5-11 位数字。
if %AT% GEQ 2 goto ask_admin_fail
goto ask_admin_loop
:ask_admin_fail
set "SYMPTOM=管理员 QQ 号格式不对"
set "ADVICE=重新运行安装器，填 5-11 位数字的 QQ 号"
exit /b 1

:ask_groups
echo.
set "GROUPS="
set /p "GROUPS=白名单群号（多个用逗号分隔；直接回车 = 不拉群）： "
exit /b 0

:ask_persona
set "PERSONA=yes"
set "ANS="
set /p "ANS=加载默认人设「小满」？[Y/n]： "
if /i "%ANS:~0,1%"=="n" set "PERSONA=no"
exit /b 0

:ask_autostart
set "AUTOSTART=no"
set "ANS="
set /p "ANS=要不要开机自启？[y/N]： "
if /i "%ANS:~0,1%"=="y" set "AUTOSTART=yes"
exit /b 0

:apply_user
set "QQBOT_BASE=%BASE%"
set "QQBOT_KEY=%KEY%"
set "QQBOT_ADMIN=%ADMIN%"
set "QQBOT_GROUPS=%GROUPS%"
"%PY%" "%SRC%\installer\lib\config.py" apply-user --target "%TARGET%" --persona "%PERSONA%"
set "RC=%ERRORLEVEL%"
set "QQBOT_KEY="
set "QQBOT_BASE="
set "QQBOT_ADMIN="
set "QQBOT_GROUPS="
set "KEY="
set "BASE="
if not "%RC%"=="0" exit /b 1
if exist "%SRC%\key.txt" del /f /q "%SRC%\key.txt" >nul 2>&1
if exist "%SRC%\key.txt" echo [提示] key.txt 自动删除失败，请手动删除。
call :log "USER_CONFIG_OK"
exit /b 0

:do_autostart
"%PY%" "%SRC%\installer\lib\config.py" set-autostart --target "%TARGET%"
if not errorlevel 1 goto autostart_done
echo [提示] 开机自启没有设置成功，不影响本次安装；可以以后再手动设置。
:autostart_done
exit /b 0

:cleanup
echo [收尾] 清理安装缓存...
if exist "%TARGET%\runtime\.downloads" rd /s /q "%TARGET%\runtime\.downloads" >nul 2>&1
if exist "%TARGET%\runtime\.extract" rd /s /q "%TARGET%\runtime\.extract" >nul 2>&1
if exist "%TARGET%\runtime\.python-extract" rd /s /q "%TARGET%\runtime\.python-extract" >nul 2>&1
if exist "%TARGET%\runtime\.uv" rd /s /q "%TARGET%\runtime\.uv" >nul 2>&1
call :log "CLEANUP_OK"
exit /b 0

exit /b 0
