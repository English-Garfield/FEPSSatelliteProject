#include <Wire.h>
#include <Adafruit_BMP280.h>
#include <math.h>

#define LED_PIN   13
#define LDR_PIN   A0
#define TRIG_PIN  4
#define ECHO_PIN  5

Adafruit_BMP280 bmp;

// ── SAR geometry thresholds 
// Slant range: distance from sensor  to target
const float NEAR_RANGE_CM = 10.0;
const float FAR_RANGE_CM = 80.0;
const float ALERT_RANGE_CM = 30.0;

// Backscatter amplitude: LDR fraction 0-100%
const float LOW_BACKSCATTER = 10.0;  // very dark
const float HIGH_BACKSCATTER = 85.0;  // high-return surface

// Atmospheric layer thresholds
const float TEMP_ALERT_C = 35.0;  // thermal anomaly threshold
const int LDR_DARK_THRESH = 300;   // raw ADC for pulse-modulate LED

const unsigned long SAMPLE_MS = 500;  // synthetic aperture dwell = 500 ms

bool bmpOk = false;
unsigned long lastSample = 0;
unsigned long pulseCount = 0; // counts transmitted pulses

float cachedRange = -1;
float cachedAmp = 50;
float cachedTemp = 20;

// Helpers
void printBar(int w) {
  for (int i = 0; i < w; i++) Serial.print('=');
  Serial.println();
}

// Horizontal text-bar proportional to a 0-100 value 
void printAmplitudeBar(float pct) {
  int bars = constrain((int)(pct / 10.0), 0, 10);
  Serial.print('[');
  for (int i = 0; i < 10; i++) Serial.print(i < bars ? '#' : ' ');
  Serial.print(']');
}

// Setup 
void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  // Power-on blink — 3 pulses like a radar 
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH); delay(120);
    digitalWrite(LED_PIN, LOW);  delay(120);
  }

  // BMP280 — try both I2C addresses
  bmpOk = bmp.begin(0x76);
  if (!bmpOk) bmpOk = bmp.begin(0x77);
  if (bmpOk) {
    bmp.setSampling(
      Adafruit_BMP280::MODE_NORMAL,
      Adafruit_BMP280::SAMPLING_X2,
      Adafruit_BMP280::SAMPLING_X16,
      Adafruit_BMP280::FILTER_X16,
      Adafruit_BMP280::STANDBY_MS_500
    );
  }

  // Header
  Serial.println();
  printBar(62);
  Serial.println(F("  SAR-style Sensor Aperture Radar"));
  printBar(62);
  Serial.println(F("  Sensor mapping:"));
  Serial.println(F("    HC-SR04  ->  Slant range  (cm)"));
  Serial.println(F("    LDR      ->  Backscatter amplitude  (%)"));
  Serial.println(F("    BMP280   ->  Temp (C) + Pressure (hPa)"));
  Serial.println(F("    LED D13  ->  Alert indicator"));
  Serial.print(F("    BMP280   :  "));
  Serial.println(bmpOk ? F("OK") : F("NOT FOUND - temp/pressure disabled"));
  printBar(62);
  Serial.println();

  // Column headers — SAR terminology
  Serial.println(F("  Pulse#   Slant range    Backscatter           Temp       Pressure    Alert"));
  Serial.println(F("  ------   -----------    -------------------   --------   ---------   -----"));
}

// slant-range measurement 
// Equivalent to the two-way travel time of radar pulse.
// Returns distance in cm, or -1 if out of range / no echo.
float readSlantRange() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long us = pulseIn(ECHO_PIN, HIGH, 30000UL); // 30 ms timeout ~ 5 m
  if (us == 0) return -1.0;
  float cm = (us / 2.0) * 0.0343;
  return (cm > 400.0) ? -1.0 : cm;
}

// backscatter amplitude
// High ADC reading -> strong radar return.
// Returned as percentage 0-100.
float readBackscatterPct() {
  return (analogRead(LDR_PIN) / 1023.0) * 100.0;
}

// Derive SAR geometry values
// Look angle: angle between ground and slant.
// Assumes a fixed platform altitude of FAR_RANGE_CM for illustration.
float lookAngleDeg(float rangeCm) {
  if (rangeCm <= 0) return 0;
  float alt = FAR_RANGE_CM; // nominal platform height
  float clamped = constrain(rangeCm, 1.0, alt);
  return degrees(asin(clamped / alt)); // simplified flat-earth
}

// Ground range: horizontal component of slant range
float groundRangeCm(float slantCm) {
  if (slantCm <= 0) return -1;
  float la = radians(lookAngleDeg(slantCm));
  return slantCm * cos(la);
}

// Incidence angle: angle between beam centre and surface normal.
// For flat terrain, incidence angle == look angle.
float incidenceAngleDeg(float slantCm) {
  return lookAngleDeg(slantCm);
}

// LED alert logic
// Priority 1 — thermal anomaly (BMP280 overheat): solid ON
// Priority 2 — target inside near-range alert zone: fast blink
// Priority 3 — dark scene (low backscatter): slow breathe via PWM
// Default     — LED off
void updateLED(float rangeCm, float ampPct, float t) {
  static unsigned long lastToggle = 0;
  static int fadeVal = 0;
  static int fadeDir = 5;
  unsigned long now = millis();

  // Thermal anomaly — steady beam (solid on)
  if (t >= TEMP_ALERT_C) {
    digitalWrite(LED_PIN, HIGH);
    return;
  }

  // Target in alert zone — fast pulse (100 ms)
  if (rangeCm > 0 && rangeCm <= ALERT_RANGE_CM) {
    if (now - lastToggle >= 100) {
      lastToggle = now;
      digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    }
    return;
  }

  // Low backscatter / dark 
  if (analogRead(LDR_PIN) < LDR_DARK_THRESH) {
    fadeVal += fadeDir;
    if (fadeVal >= 255 || fadeVal <= 0) fadeDir = -fadeDir;
    analogWrite(LED_PIN, fadeVal);
    return;
  }

  // Clear sky, no alert — off
  digitalWrite(LED_PIN, LOW);
}

// Print one row
void printRow(unsigned long pulse, float slant, float ground,
              int lightRaw, float amp, float temp, float press, bool alert) {

  char buf[16];

  // Pulse counter
  Serial.print(F("  "));
  sprintf(buf, "%6lu", pulse);
  Serial.print(buf);
  Serial.print(F("   "));

  // Slant range
  if (slant < 0) {
    Serial.print(F("OOR          "));
  } else {
    dtostrf(slant, 5, 1, buf);
    Serial.print(buf);
    Serial.print(F("cm  gr:"));
    dtostrf(ground, 5, 1, buf);
    Serial.print(buf);
    Serial.print(F("cm  "));
  }

  // Backscatter amplitude bar + value
  printAmplitudeBar(amp);
  dtostrf(amp, 4, 0, buf);
  Serial.print(buf);
  Serial.print(F("%  "));

  // Temperature
  if (isnan(temp)) {
    Serial.print(F("  N/A      "));
  } else {
    dtostrf(temp, 5, 1, buf);
    Serial.print(buf);
    Serial.print(F("C   "));
  }

  // Pressure
  if (isnan(press)) {
    Serial.print(F("  N/A       "));
  } else {
    dtostrf(press, 7, 1, buf);
    Serial.print(buf);
    Serial.print(F("hPa  "));
  }

  // Alert indicator
  if (alert) {
    Serial.print(F("  *** ALERT ***"));
  } else {
    Serial.print(F("  --"));
  }

  Serial.println();

  // Every 20 pulses: print a summary "synthetic aperture" line
  if (pulse > 0 && pulse % 20 == 0) {
    Serial.println(F("  -- synthetic aperture complete (20 pulses) --"));
    Serial.println(F("  Pulse#   Slant range    Backscatter           Temp       Pressure    Alert"));
    Serial.println(F("  ------   -----------    -------------------   --------   ---------   -----"));
  }
}

// ── Main loop ──────────────────────────────
void loop() {
  unsigned long now = millis();

  // LED runs continuously between samples
  updateLED(cachedRange, cachedAmp, cachedTemp);

  // Gate readings to SAMPLE_MS (synthetic aperture dwell time)
  if (now - lastSample < SAMPLE_MS) return;
  lastSample = now;
  pulseCount++;

  //  Acquire 
  float slant = readSlantRange();
  float amp = readBackscatterPct();
  int lightRaw = analogRead(LDR_PIN);
  float temp = bmpOk ? bmp.readTemperature() : NAN;
  float press = bmpOk ? bmp.readPressure() / 100.0 : NAN;

  // Derived SAR geometry
  float ground = groundRangeCm(slant);

  // Cache for LED routine
  cachedRange = slant;
  cachedAmp = amp;
  cachedTemp = isnan(temp) ? 20.0 : temp;

  // Alert if target inside near-range zone OR thermal anomaly
  bool alertOn = (slant > 0 && slant <= ALERT_RANGE_CM) || (!isnan(temp) && temp >= TEMP_ALERT_C);

  printRow(pulseCount, slant, ground, lightRaw, amp, temp, press, alertOn);
}
