# AIO Graphics Test ZH — 补丁说明

## 修复的三个核心问题

### 1. 汉化问号乱码

**根因**：`shell_imgui.cpp` 中文字体加载依赖 `C:\Windows\Fonts\msyh.ttc` / `simhei.ttf` 等 Windows 专有字体。Winlator 纯净 Wine 前缀中没有这些文件，`CreateFileA` 全部失败 → CJK 字形从未合并进 ImGui 字体 atlas → 所有汉字渲染为 `?`。

**修复**：将 Noto Sans CJK SC（SIL OFL 1.1 开源）子集化到项目实际使用的 316 个字符，zlib 压缩 + ImGui base85 编码后嵌入 EXE。运行时零外部依赖。

**修改文件**：
- `src/font_cjk.inc`（新增）— 嵌入字体数据，153KB
- `src/shell_imgui.cpp` — 删除系统字体探测，改为 `AddFontFromMemoryCompressedBase85TTF(CJKFont_compressed_data_base85, ...)`
- `tools/gen_cjk_font.py`（新增）— 字体子集化 + 压缩 + base85 编码工具
- `CREDITS.md` — 添加 Noto Sans CJK SC 版权声明
- `.github/workflows/build-windows.yml` — 添加注释说明 font_cjk.inc 已入库

**影响范围**：EXE 体积增加约 150KB；启动时字体 atlas 构建增加约 10-30ms；不影响任何渲染逻辑。

**回滚方法**：`git revert` 对应 commit，或恢复旧的系统字体探测代码。

---

### 2. Winlator 双重标题栏

**根因**：代码使用 `WS_OVERLAPPEDWINDOW & ~WS_CAPTION` 意图去掉原生标题栏，但 Winlator 的窗口管理器对该样式仍强制绘制系统标题栏，叠加应用自绘顶部栏形成双重标题栏（窗口套窗口）。

**修复**：
- 运行时检测 Wine 环境（`ntdll.dll!wine_get_version` 导出检测）
- Wine 下使用 `WS_POPUP | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU` + `WS_EX_APPWINDOW`，完全去除系统 chrome
- 应用顶部栏右上角添加真实可点击的最小化 / 最大化还原 / 关闭按钮（关闭按钮悬停红色）
- 标题栏空白区域支持鼠标拖拽移动窗口（`ReleaseCapture` + `WM_NCLBUTTONDOWN HTCAPTION`）
- 双击标题栏切换最大化/还原（标准 caption 行为）
- 原生 Windows 下保持原有行为不变

**修改文件**：
- `src/shell_imgui.cpp` — 添加 `detect_wine()`、`g_is_wine`、`g_shell_hwnd`；条件窗口样式；标题栏控制按钮；拖拽移动

**影响范围**：Wine/Winlator 下窗口外观改变（无系统标题栏，全部自绘）；原生 Windows 下行为不变；全屏模式兼容（`set_window_fullscreen` 已处理样式保存/恢复）。

**回滚方法**：恢复固定 `WS_OVERLAPPEDWINDOW & ~WS_CAPTION`，删除自绘控制按钮代码。

---

### 3. 处理器/GPU 型号显示

**根因**（三个子问题）：
- **GPU 卡在 `Querying...`**：Vulkan 查询在后台线程运行，`vkCreateInstance` 在某些 DXVK 配置下可能阻塞，主线程无超时机制，永远显示 `Querying...`
- **缺少 CPU 型号显示**：代码中完全没有 CPU 信息查询功能
- **GPU 型号可能错误**：llvmpipe 软件渲染设备未被识别和标注；Turnip 设备名包含冗余前缀

**修复**：
- **GPU 查询超时**：8 秒超时，超时后显示 "GPU 超时"，并尝试用 GL_RENDERER 字符串作为 fallback
- **CPU 信息查询**：新增 `cpuinfo.c/.h`，从注册表 `HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0` 读取 `ProcessorNameString` / `~MHz`，`GetSystemInfo` 读取核心数，`GlobalMemoryStatusEx` 读取内存总量；注册表不可用时 fallback 到 `cpuid` 指令直接读取品牌字符串
- **GPU 名称后处理**：检测 llvmpipe/softpipe/lavapipe 并设置 `software=1` 标志（telemetry 中红色显示）；清理 Turnip/Adreno 设备名（去掉 "Turnip " / "Qualcomm " 前缀和 "(TM)"）
- **telemetry strip 增加 CPU 格**：显示 CPU 型号 + 核心数（长型号自动截断为 27 字符 + "..."）

**修改文件**：
- `src/cpuinfo.c`（新增）— CPU/内存信息查询
- `src/cpuinfo.h`（新增）— 头文件
- `src/gpuinfo.h` — `AioVkInfo` 新增 `software` 字段
- `src/gpuinfo.c` — GPU 名称后处理（llvmpipe 检测、Adreno 名称清理）
- `src/shell_imgui.cpp` — CPU 查询启动、GPU 超时逻辑、telemetry 5 格布局、软件渲染红色警告
- `.github/workflows/build-windows.yml` — 编译/链接列表添加 `cpuinfo`

**影响范围**：telemetry strip 从 4 格变为 5 格；启动时增加一次注册表读取（<1ms）；GPU Info 结构新增字段（向后兼容）。

**回滚方法**：`git revert` 对应 commit；telemetry 恢复 4 格布局。

---

## 独家优化方向（已设计，待实施）

以下是基于项目架构和 Winlator/Turnip 目标平台设计的独家优化，按价值优先级排序：

1. **全后端性能对比矩阵** — 一键运行所有 8 个后端的 5 秒快速基准，生成横向柱状对比图，直观显示哪个翻译层最快/最慢
2. **DXVK/Turnip/Mesa 版本自动探针** — 自动检测并显示容器内完整图形栈版本（DXVK、VKD3D、Turnip/Mesa、Wine）
3. **帧时间百分位与卡顿分析** — P1/P0.1 low FPS、帧时间分布直方图、卡顿计数、着色器编译卡顿检测
4. **触控体验增强** — 触摸输入时自动增大行高、左右滑动切换测试、双指缩放调整渲染分辨率
5. **测试报告一键导出** — 生成包含所有后端性能数据 + CPU/GPU/驱动版本的文本/JSON 报告
6. **内存/显存实时监控** — 进程私有内存 + GPU 显存使用实时显示

---

## 验证方法

1. **CI 构建**：32/64 位均绿色编译（GitHub Actions `build-windows.yml`）
2. **纯净 Wine 前缀验证**：在无系统中文字体的 Wine 前缀中运行，确认：
   - 所有汉字正常显示（非 `?`）
   - 仅一个标题栏（应用自绘，无系统标题栏）
   - 最小化/最大化/关闭按钮功能正常
   - 标题栏可拖拽移动窗口
   - GPU 型号在 8 秒内显示，或超时后显示 fallback
   - CPU 型号和核心数正确显示
3. **Winlator 真机验证**：在实际 Winlator 容器中运行，确认所有功能
4. **原生 Windows 验证**：在 Windows 10/11 上运行，确认行为与之前一致（无回归）
5. **字体数据验证**：`font_cjk.inc` 经 base85 解码 + zlib 解压后与原始子集 TTF 字节一致（已验证）

---

## 文件清单

### 修改的文件（5 个）
- `.github/workflows/build-windows.yml`
- `CREDITS.md`
- `src/gpuinfo.c`
- `src/gpuinfo.h`
- `src/shell_imgui.cpp`

### 新增的文件（4 个）
- `src/cpuinfo.c`
- `src/cpuinfo.h`
- `src/font_cjk.inc`
- `tools/gen_cjk_font.py`

### 文档（1 个）
- `PATCH_NOTES.md`（本文件）
