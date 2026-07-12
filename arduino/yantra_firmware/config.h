// ============================================================
//  Yantra Rakshak - Node configuration
//  Edit these per machine before flashing.
//  NO SENSORS REQUIRED - all data is generated on the MCU.
// ============================================================
#pragma once

// ---- Machine identity ----
#define MACHINE_ID    "MOTOR-01"        // unique per node
#define MACHINE_TYPE  "motor"           // motor | pump | lathe | compressor
#define LOCATION      "Winding Section A"
#define MACHINE_RPM   2880              // rated speed - affects synthetic freq

// ---- Fault to inject (change per node for variety) ----
// 0 = auto-detect from features
// 1 = BEARING_WEAR   (high kurtosis, impulsive spikes)
// 2 = IMBALANCE      (dominant 1x running frequency)
// 3 = LUBRICATION    (elevated broadband noise)
// 4 = OVERHEAT       (rising temperature signal)
#define FAULT_MODE    1

// ---- How fast the machine degrades (per publish tick) ----
// 0.010 = gradual (~3 min to CRITICAL)
// 0.020 = fast     (~1.5 min to CRITICAL)
// 0.005 = slow     (~6 min to CRITICAL)
#define DEGRADE_RATE  0.012f

// ---- Sampling ----
#define SAMPLE_RATE_HZ    1000
#define PUBLISH_EVERY_MS  2000          // publish a health event every 2 s

// ---- Anomaly thresholds ----
#define WARN_THRESHOLD  1.5f
#define CRIT_THRESHOLD  2.5f

// ============================================================
//  CONNECTION MODE
//  Option A (default): USB Serial -> laptop bridge (no Wi-Fi)
//  Option B: direct Wi-Fi HTTP POST to laptop
// ============================================================
#define WIFI_ENABLED  0   // set to 1 for Wi-Fi mode

// ---- Only needed if WIFI_ENABLED 1 ----
#define WIFI_SSID     "YOUR_WIFI"
#define WIFI_PASS     "YOUR_PASSWORD"
#define CLOUD_HOST    "192.168.1.50"    // your laptop LAN IP (run: ipconfig)
#define CLOUD_PORT    8010
#define CLOUD_PATH    "/api/ingest"
