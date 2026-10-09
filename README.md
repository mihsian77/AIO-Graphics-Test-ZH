# AIO Graphics Test 中文版

Winlator / 各类 Android Wine 容器下的图形诊断和性能测试工具。一个 exe 丢进容器就能跑，
覆盖 Vulkan、OpenGL、Direct3D 8/9/10/11/12、DirectDraw，自带 HDR 检测、磁盘测速、
GPU 信息查看和基准测试，不需要额外装任何东西。

这是 [The412Banner/AIO-Graphics-Test](https://github.com/The412Banner/AIO-Graphics-Test) 的中文汉化分支，
针对 Winlator 触屏环境做了字体、窗口、UI 适配。

## 下载

到 [Releases](https://github.com/mihsian77/AIO-Graphics-Test-ZH/releases) 页面下载最新的
`AIO-Graphics-Test-CN-64bit.exe`（或 32bit 版本），放进容器直接运行，不用安装。
容器自带的 `vulkan-1.dll` 就能用。

## 和原版的区别

- 界面、测试名、HDR 诊断面板、磁盘测速、GPU 信息全部汉化
- 嵌入 Noto Sans CJK 中文字体子集，不依赖容器里有没有中文字体，不会出现问号乱码
- Wine/Winlator 下字体按高分辨率加载，不被容器 DPI 缩放拖糊
- 去掉 Wine 下的双重标题栏，单窗口模式
- 窗口顶部区域可拖拽，默认尺寸适配手机容器分辨率
- CPU 信息在 Box64 环境下显示 ARM64，不报一堆无意义的 Cortex 核心名
- GPU 名称自动清理 Turnip/Qualcomm 前缀和 (TM) 等杂字符
- HDR 数值面板的滚动条支持触屏拖拽和点击跳转
- 技术术语保留英文原名并在括号里加中文说明

## 界面

单窗口设计，右侧是测试列表，左侧是渲染区域：

- 左侧实时渲染选中的测试项，切换不用开新窗口
- HUD 显示当前 API、实时 FPS、帧时间曲线
- 底部信息栏显示分辨率、呈现模式、转换路径（比如 `d3d11 -> DXVK -> Turnip`）、GPU 和 CPU
- 支持列表/网格两种视图，深色/浅色主题
- 搜索框可以快速过滤测试项

## 测试内容

**图形后端**：Vulkan、OpenGL、Direct3D 12/11/10/9/8、DirectDraw (DX7)，
同一个立方体走不同 API，方便定位哪个转换层出了问题。

**D3D11 场景**：旋转立方体、纹理贴图、实例化绘制、曲面细分、计算着色器粒子、
几何着色器爆炸、原子操作、海豚、色带测试、不同压力级别的绘制测试。

**渲染演示**：自由视角、行星飞行、光线步进、海洋、曼德布洛特集、星云、
太空、沙漠、城市景观、卡通着色、材质捕获等。

**缩放测试**：组合测试卡、区域板、分辨率楔形、线条对角线、棋盘格、硬边、色带等。

**HDR 测试**：HDR10/scRGB/SDR 三种模式切换，亮度色块、PQ 渐变、色带对比、
色域对比，数值面板里有完整的 DXGI 交换链和 Vulkan 表面诊断信息。

**工具**：GPU 信息（Vulkan + OpenGL 能力查询）、基准测试（多场景跑分记录）、
磁盘测速（顺序/随机读写，支持真实闪存模式绕过缓存）。

## 命令行

也可以命令行直接跑指定测试，参数和原版一致，比如：

```
AIO-Graphics-Test-CN-64bit.exe vulkan
AIO-Graphics-Test-CN-64bit.exe dx11 --scene spin
AIO-Graphics-Test-CN-64bit.exe --force-gl
```

## 编译

用 GitHub Actions 自动构建，支持 x86_64 和 i686 双架构。本地编译需要 MinGW-w64，
具体编译参数看 `.github/workflows/build-windows.yml`。

中文字体子集用 `tools/gen_cjk_font.py` 重新生成，需要系统装了 Noto Sans CJK 和 fonttools：

```bash
python3 tools/gen_cjk_font.py \
  --ttc /usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc \
  --font-number 2 --src src --out src/font_cjk.inc --symbol CJKFont
```

## 源码结构

- `src/shell_imgui.cpp` — 主界面（ImGui shell、字体加载、窗口、测试列表、工具页）
- `src/hdr_scene.cpp` — HDR 测试卡和数值诊断面板
- `src/gpuinfo.c` — Vulkan / OpenGL 适配器信息查询
- `src/cpuinfo.c` — CPU 和内存信息（含 Box64 检测）
- `src/font_cjk.inc` — 嵌入的中文字体子集（base85 + stb 压缩）
- `tools/gen_cjk_font.py` — 字体子集化脚本
- `tools/binary_to_compressed_c.cpp` — ImGui 官方字体编码工具

## 致谢

原版作者 [The412Banner](https://github.com/The412Banner)，
基于 Khronos [Vulkan-Tools vkcube](https://github.com/KhronosGroup/Vulkan-Tools)（Apache-2.0），
UI 用 [Dear ImGui](https://github.com/ocornut/imgui)，
中文字体用 [Noto Sans CJK](https://fonts.google.com/noto/specimen/Noto+Sans+SC)。

## 许可证

Apache-2.0，和原版一致。
