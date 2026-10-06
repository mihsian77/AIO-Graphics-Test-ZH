// AIO Graphics Test - CPU / system information query.
//
// Reads the processor name, core count, clock speed and total physical memory
// from the Windows registry + system API. Used by the ImGui shell's telemetry
// strip and GPU Info tool page. All functions are synchronous and fast (<1 ms);
// no background thread needed.
//
// On Wine/Winlator the registry key HKLM\HARDWARE\DESCRIPTION\System\
// CentralProcessor\0 is populated by Wine's ntdll (it reads the host CPUID),
// so ProcessorNameString is usually available. If not, we fall back to a
// cpuid-based brand string read.
//
// Copyright (c) 2026 The412Banner. Licensed under Apache-2.0 (see LICENSE).

#ifndef AIO_CPUINFO_H
#define AIO_CPUINFO_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct AioCpuInfo {
    int  ok;                // 1 if any field was populated, 0 if total failure
    char name[128];         // ProcessorNameString (e.g. "Qualcomm Snapdragon 8 Gen 3")
    char identifier[128];   // ProcessorIdentifier (e.g. "Intel64 Family 6 Model 154 ...")
    int  cores;             // number of logical processors (GetSystemInfo)
    int  mhz;               // ~MHz from registry, 0 if unavailable
    char memory[32];        // total physical memory, human-readable (e.g. "12.0 GB")
    uint64_t memory_bytes;  // total physical memory in bytes
} AioCpuInfo;

// Query CPU + memory info. Fills every field; ok=0 only if even GetSystemInfo
// failed (essentially impossible). Safe to call from the main thread.
void aio_cpuinfo_query(AioCpuInfo *out);

#ifdef __cplusplus
}
#endif

#endif  // AIO_CPUINFO_H
