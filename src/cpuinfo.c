// AIO Graphics Test - CPU / system information query (see cpuinfo.h).
//
// Copyright (c) 2026 The412Banner. Licensed under Apache-2.0 (see LICENSE).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "cpuinfo.h"

// Read a string value from the registry. Returns 1 on success, 0 on failure.
static int reg_read_str(HKEY root, const char *subkey, const char *value,
                        char *out, size_t out_size) {
    HKEY h;
    if (RegOpenKeyExA(root, subkey, 0, KEY_READ, &h) != ERROR_SUCCESS)
        return 0;
    DWORD type = 0, size = (DWORD)out_size;
    LONG rc = RegQueryValueExA(h, value, NULL, &type, (LPBYTE)out, &size);
    RegCloseKey(h);
    if (rc != ERROR_SUCCESS || (type != REG_SZ && type != REG_EXPAND_SZ))
        return 0;
    out[out_size - 1] = '\0';
    return 1;
}

// Read a DWORD value from the registry. Returns 1 on success.
static int reg_read_dword(HKEY root, const char *subkey, const char *value, DWORD *out) {
    HKEY h;
    if (RegOpenKeyExA(root, subkey, 0, KEY_READ, &h) != ERROR_SUCCESS)
        return 0;
    DWORD type = 0, size = sizeof(DWORD);
    LONG rc = RegQueryValueExA(h, value, NULL, &type, (LPBYTE)out, &size);
    RegCloseKey(h);
    return rc == ERROR_SUCCESS && type == REG_DWORD;
}

// Read the CPU brand string directly via cpuid (fallback when registry is empty,
// e.g. a minimal Wine prefix that didn't populate HKLM\HARDWARE).
static void cpuid_brand_string(char *out, size_t out_size) {
    // cpuid leaf 0x80000002..0x80000004 return the 48-byte brand string.
    char brand[49] = {0};
    DWORD supported = 0;
    __asm__ __volatile__(
        "mov $0x80000000, %%eax\n"
        "cpuid\n"
        "mov %%eax, %0\n"
        : "=r"(supported) : : "eax", "ebx", "ecx", "edx");
    if (supported < 0x80000004) {
        strncpy(out, "Unknown CPU", out_size - 1);
        out[out_size - 1] = '\0';
        return;
    }
    DWORD *p = (DWORD *)brand;
    for (int leaf = 0x80000002; leaf <= 0x80000004; leaf++) {
        DWORD a, b, c, d;
        __asm__ __volatile__(
            "cpuid\n"
            : "=a"(a), "=b"(b), "=c"(c), "=d"(d)
            : "a"(leaf));
        *p++ = a; *p++ = b; *p++ = c; *p++ = d;
    }
    brand[48] = '\0';
    // Trim leading spaces (Intel/AMD brand strings are space-padded).
    const char *s = brand;
    while (*s == ' ') s++;
    strncpy(out, s, out_size - 1);
    out[out_size - 1] = '\0';
}

static void format_memory(uint64_t bytes, char *out, size_t out_size) {
    const char *units[] = {"B", "KB", "MB", "GB", "TB"};
    double val = (double)bytes;
    int ui = 0;
    while (val >= 1024.0 && ui < 4) { val /= 1024.0; ui++; }
    snprintf(out, out_size, "%.1f %s", val, units[ui]);
}

void aio_cpuinfo_query(AioCpuInfo *out) {
    memset(out, 0, sizeof(*out));

    // Core count + architecture (always available).
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    out->cores = (int)si.dwNumberOfProcessors;

    // Registry: CPU name, identifier, clock speed.
    static const char *key = "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0";
    if (!reg_read_str(HKEY_LOCAL_MACHINE, key, "ProcessorNameString",
                       out->name, sizeof(out->name))) {
        // Fallback: direct cpuid brand string.
        cpuid_brand_string(out->name, sizeof(out->name));
    } else {
        // Under Winlator/Box64 the registry ProcessorNameString is a Wine stub
        // ("Box64 vX.Y on Unknown CPU..."). cpuid is intercepted by Box64 and
        // returns the same string, so don't bother — show a clean label instead.
        if (strstr(out->name, "Box64") || strstr(out->name, "box64") ||
            strstr(out->name, "Wine CPU")) {
            snprintf(out->name, sizeof(out->name), "ARM64 (Box64)");
        }
    }
    reg_read_str(HKEY_LOCAL_MACHINE, key, "ProcessorIdentifier",
                 out->identifier, sizeof(out->identifier));
    DWORD mhz = 0;
    if (reg_read_dword(HKEY_LOCAL_MACHINE, key, "~MHz", &mhz))
        out->mhz = (int)mhz;

    // Total physical memory.
    MEMORYSTATUSEX msx;
    msx.dwLength = sizeof(msx);
    if (GlobalMemoryStatusEx(&msx)) {
        out->memory_bytes = msx.ullTotalPhys;
        format_memory(msx.ullTotalPhys, out->memory, sizeof(out->memory));
    } else {
        strncpy(out->memory, "unknown", sizeof(out->memory) - 1);
    }

    out->ok = (out->name[0] != '\0') ? 1 : 0;
}
