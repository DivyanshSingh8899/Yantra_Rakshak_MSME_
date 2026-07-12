// ============================================================
//  YANTRA RAKSHAK  -  Arduino UNO Q  |  NO-SENSOR build
// ------------------------------------------------------------
//  No MPU-6050 or MEMS mic required.
//  The MCU generates synthetic vibration data that faithfully
//  mimics a rotating machine (healthy baseline + injected faults
//  that grow over time), runs the same feature extraction and
//  anomaly scoring pipeline, and outputs structured JSON over
//  USB Serial (for the laptop bridge) OR over Wi-Fi HTTP
//  (if WIFI_ENABLED is set to 1 in config.h).
//
//  Flash, open the Serial Monitor at 115200 baud, and you will
//  see health events streaming out. The laptop bridge
//  (node/arduino_bridge.py) reads those and forwards them to
//  the FastAPI dashboard.
// ============================================================

#include <math.h>
#include "config.h"

// ---- optional Wi-Fi (only compiled if WIFI_ENABLED 1) ----
#if WIFI_ENABLED
  #include <WiFi.h>
  #include <HTTPClient.h>
#endif

// ============================================================
// Synthetic vibration generator
// Simulates a machine that starts healthy and gradually drifts
// into one of four fault modes based on FAULT_MODE in config.h
// ============================================================

static float health     = 1.0f;   // 1.0 = perfect, 0.0 = fully faulted
static float temp_c     = 35.0f;
static uint32_t tick    = 0;

// Baseline statistics (captured during "calibration" on boot)
static float base_rms   = 0.0f;
static float base_kurt  = 0.0f;
static float base_crest = 0.0f;
static float base_freq  = (float)MACHINE_RPM / 60.0f;  // Hz

#define WINDOW 128
static float win[WINDOW];

// ---- pseudo-random (LCG) so we get the same sequence every boot ----
static uint32_t _seed = 12345;
float frand() {
  _seed = _seed * 1664525UL + 1013904223UL;
  return (float)(_seed >> 16) / 65535.0f;  // 0..1
}
float frandn() {
  // Box-Muller (approx with two uniform samples)
  float u = frand() + 1e-6f, v = frand();
  return sqrtf(-2.0f * logf(u)) * cosf(2.0f * 3.14159f * v);
}

// Fill window with synthetic vibration at current health level
void fillWindow() {
  float sev = 1.0f - health;   // 0 healthy .. 1 faulted
  float dt   = 1.0f / SAMPLE_RATE_HZ;

  for (int i = 0; i < WINDOW; i++) {
    float t = i * dt;
    // base sinusoid at running frequency
    float s = 0.15f * sinf(2.0f * 3.14159f * base_freq * t);
    // always-on sensor noise
    s += 0.02f * frandn();

#if FAULT_MODE == 1   // BEARING_WEAR: impulsive spikes
    if (frand() < (0.04f + sev * 0.25f))
      s += (0.4f + frand() * 0.8f) * sev;
    s += 0.2f * sev * sinf(2.0f * 3.14159f * 8.0f * base_freq * t);

#elif FAULT_MODE == 2  // IMBALANCE: strong 1x growth
    s += (0.7f * sev) * sinf(2.0f * 3.14159f * base_freq * t);

#elif FAULT_MODE == 3  // LUBRICATION: raised noise floor
    s += 0.25f * sev * frandn();

#elif FAULT_MODE == 4  // OVERHEAT: mild vibration + rising temp
    s += 0.3f * sev * sinf(2.0f * 3.14159f * base_freq * t);
    temp_c = 35.0f + sev * 45.0f;
#endif

    win[i] = s;
  }
}

// ============================================================
// Feature extraction  (same maths as node/anomaly.py)
// ============================================================
struct Feats { float rms, kurt, crest, freq; };

Feats extractFeats() {
  float mean = 0;
  for (int i = 0; i < WINDOW; i++) mean += win[i];
  mean /= WINDOW;

  float ss = 0, peak = 0, m4 = 0;
  for (int i = 0; i < WINDOW; i++) {
    float d = win[i] - mean;
    ss   += d * d;
    if (fabsf(d) > peak) peak = fabsf(d);
  }
  float var = ss / WINDOW;
  float sd  = sqrtf(var) + 1e-6f;
  for (int i = 0; i < WINDOW; i++) {
    float z = (win[i] - mean) / sd;
    m4 += z * z * z * z;
  }

  // dominant frequency via zero-crossing count
  uint16_t cross = 0;
  for (int i = 1; i < WINDOW; i++)
    if (win[i-1] < 0 && win[i] >= 0) cross++;
  float dur  = (float)WINDOW / SAMPLE_RATE_HZ;
  float freq = (dur > 0) ? cross / dur : base_freq;

  Feats f;
  f.rms   = sqrtf(var);
  f.kurt  = (m4 / WINDOW) - 3.0f;
  f.crest = (f.rms > 1e-6f) ? peak / f.rms : 0.0f;
  f.freq  = freq;
  return f;
}

// ============================================================
// Anomaly scoring  (same as node/anomaly.py)
// ============================================================
float base_rms_sd   = 0.01f;
float base_kurt_sd  = 0.20f;
float base_crest_sd = 0.15f;
float base_freq_sd  = 4.0f;
float base_temp     = 35.0f;
float base_temp_sd  = 1.5f;

float anomalyScore(Feats f) {
  float devs[5] = {
    fabsf(f.rms   - base_rms)   / base_rms_sd,
    fabsf(f.kurt  - base_kurt)  / base_kurt_sd,
    fabsf(f.crest - base_crest) / base_crest_sd,
    fabsf(f.freq  - base_freq)  / base_freq_sd,
    fabsf(temp_c  - base_temp)  / base_temp_sd,
  };
  float excess = 0;
  for (int i = 0; i < 5; i++)
    excess += (devs[i] > 1.0f) ? min(devs[i] - 1.0f, 10.0f) : 0.0f;
  return 1.0f + 0.55f * (excess / 5.0f);
}

// ============================================================
// Calibration: capture healthy baseline (30 windows)
// ============================================================
void calibrate() {
  Serial.println(F("{\"status\":\"calibrating\"}"));
  float sr=0, sk=0, sc=0, sf=0;
  float sr2=0, sk2=0, sc2=0, sf2=0;
  const int N = 30;
  for (int k = 0; k < N; k++) {
    health = 1.0f;   // always healthy during calibration
    fillWindow();
    Feats f = extractFeats();
    sr += f.rms;   sr2 += f.rms   * f.rms;
    sk += f.kurt;  sk2 += f.kurt  * f.kurt;
    sc += f.crest; sc2 += f.crest * f.crest;
    sf += f.freq;  sf2 += f.freq  * f.freq;
    delay(50);
  }
  base_rms   = sr / N;
  base_kurt  = sk / N;
  base_crest = sc / N;
  base_freq  = sf / N;

  auto sd = [&](float s, float s2, float floor_) {
    float v = s2/N - (s/N)*(s/N);
    return max(sqrtf(v > 0 ? v : 0), floor_);
  };
  base_rms_sd   = sd(sr, sr2, 0.01f);
  base_kurt_sd  = sd(sk, sk2, 0.20f);
  base_crest_sd = sd(sc, sc2, 0.15f);
  base_freq_sd  = sd(sf, sf2, 4.0f);

  Serial.println(F("{\"status\":\"calibration_done\"}"));
}

// ============================================================
// Fault classification
// ============================================================
const char* classify(Feats f, float mse) {
#if FAULT_MODE == 1
  return "BEARING_WEAR";
#elif FAULT_MODE == 2
  return "IMBALANCE";
#elif FAULT_MODE == 3
  return "LUBRICATION";
#elif FAULT_MODE == 4
  return "OVERHEAT";
#else
  if (fabsf(temp_c - base_temp) > 15.0f) return "OVERHEAT";
  if (f.kurt - base_kurt > 1.5f)         return "BEARING_WEAR";
  if (f.rms  - base_rms  > base_rms_sd * 3.0f
      && fabsf(f.freq - base_freq) < 5.0f) return "IMBALANCE";
  return "LUBRICATION";
#endif
}

// ============================================================
// JSON output over Serial
// ============================================================
void emitJSON(Feats f, float mse, const char* fault,
              const char* severity, float conf) {
  Serial.print(F("{\"machine_id\":\""));
  Serial.print(F(MACHINE_ID));
  Serial.print(F("\",\"machine_type\":\""));
  Serial.print(F(MACHINE_TYPE));
  Serial.print(F("\",\"location\":\""));
  Serial.print(F(LOCATION));
  Serial.print(F("\",\"rpm\":"));
  Serial.print(MACHINE_RPM);
  Serial.print(F(",\"fault_type\":\""));
  Serial.print(fault);
  Serial.print(F("\",\"severity\":\""));
  Serial.print(severity);
  Serial.print(F("\",\"confidence\":"));
  Serial.print(conf, 2);
  Serial.print(F(",\"mse_score\":"));
  Serial.print(mse, 3);
  Serial.print(F(",\"features\":{\"rms\":"));
  Serial.print(f.rms, 4);
  Serial.print(F(",\"kurtosis\":"));
  Serial.print(f.kurt, 3);
  Serial.print(F(",\"crest_factor\":"));
  Serial.print(f.crest, 3);
  Serial.print(F(",\"peak_freq_hz\":"));
  Serial.print(f.freq, 1);
  Serial.print(F(",\"temp_c\":"));
  Serial.print(temp_c, 1);
  Serial.println(F("}}"));
}

// ============================================================
// Wi-Fi HTTP publish (only if WIFI_ENABLED 1)
// ============================================================
#if WIFI_ENABLED
void wifiPublish(const char* body) {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  String url = String("http://") + CLOUD_HOST + ":" + CLOUD_PORT + CLOUD_PATH;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.POST(String(body));
  http.end();
}
#endif

// ============================================================
// Arduino setup / loop
// ============================================================
void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

#if WIFI_ENABLED
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) delay(500);
#endif

  calibrate();
}

void loop() {
  tick++;

  // Degrade health over time (fault grows after ~20 ticks)
  if (tick > 20) {
    health -= DEGRADE_RATE;
    if (health < 0.05f) health = 0.05f;
  }
  // ambient temperature wobble
  temp_c += (frand() - 0.5f) * 0.4f;
  temp_c = max(30.0f, min(temp_c, 50.0f));

  fillWindow();
  Feats f   = extractFeats();
  float mse = anomalyScore(f);

  const char* severity;
  if      (mse >= CRIT_THRESHOLD) severity = "CRITICAL";
  else if (mse >= WARN_THRESHOLD) severity = "WARNING";
  else                             severity = "OK";

  const char* fault = (strcmp(severity, "OK") == 0)
    ? "NORMAL" : classify(f, mse);

  float conf = min(0.99f, 0.55f + (mse - 1.0f) * 0.35f);
  if (strcmp(severity, "OK") == 0)
    conf = min(0.99f, 1.2f - (mse - 1.0f));

  emitJSON(f, mse, fault, severity, conf);

  delay(PUBLISH_EVERY_MS);
}
