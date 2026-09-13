/*
 * TB bill-only pulse observer for Arduino Uno.
 *
 * This is an observe-only calibration image. It reads the conditioned TB
 * METER signal on D3/INT1, groups CHANGE edges into a train, reports raw pulse
 * count and timing, and prints an explicitly unverified V1 PHP hypothesis.
 * It never credits an order, drives the TB inhibit pair, accesses I2C, or
 * moves a servo.
 *
 * Required electrical interface:
 *   TB pin 7 BLUE METER+ -> D3 signal node
 *   external 4.7 kOhm pull-up from that node to Arduino 5 V
 *   TB pin 8 PURPLE METER- -> Arduino logic GND
 *   TB pin 5 RED -> separate fused regulated +12 V
 *   TB pin 9 ORANGE -> separate 12 V supply return
 */

#include <Arduino.h>
#include <string.h>

static const uint8_t PIN_METER = 3;       // Uno INT1
static const uint8_t PIN_BILL_INHIBIT = 4;
static const uint8_t PIN_COIN_POWER = 5;
static const uint8_t PIN_PCA_OE = 7;      // active-low; HIGH disables outputs
static const uint8_t EDGE_RING_SIZE = 64; // power of two; 63 usable entries
static const uint32_t TRAIN_GAP_US = 250000UL; // V1 hypothesis only

struct EdgeEvent {
  uint32_t timestampUs;
  uint8_t level;
};

volatile EdgeEvent edgeRing[EDGE_RING_SIZE];
volatile uint8_t edgeHead = 0;
volatile uint8_t edgeTail = 0;
volatile bool edgeOverflow = false;
volatile bool captureEnabled = false;

char commandBuffer[24];
uint8_t commandLength = 0;
bool trainActive = false;
bool pulseOpen = false;
uint16_t fallingPulses = 0;
uint32_t trainStartUs = 0;
uint32_t lastEdgeUs = 0;
uint32_t lastFallingUs = 0;
uint32_t pulseStartUs = 0;
uint32_t pulseWidthMinUs = 0xFFFFFFFFUL;
uint32_t pulseWidthMaxUs = 0;
uint32_t pulseWidthSumUs = 0;
uint16_t pulseWidthSamples = 0;
uint32_t gapMinUs = 0xFFFFFFFFUL;
uint32_t gapMaxUs = 0;
uint32_t gapSumUs = 0;
uint16_t gapSamples = 0;
uint32_t observedTotalCentavos = 0;

uint32_t candidateCentavos(uint16_t pulses) {
  // V1 values from the audit plan. These are not measured calibration.
  if (pulses == 2) return 2000UL;
  if (pulses == 5) return 5000UL;
  if (pulses == 10) return 10000UL;
  return 0;
}

void printMoney(uint32_t centavos) {
  Serial.print(centavos / 100UL);
  Serial.print('.');
  uint8_t cents = (uint8_t)(centavos % 100UL);
  if (cents < 10) Serial.print('0');
  Serial.print(cents);
}

void resetTrain() {
  trainActive = false;
  pulseOpen = false;
  fallingPulses = 0;
  trainStartUs = 0;
  lastEdgeUs = 0;
  lastFallingUs = 0;
  pulseStartUs = 0;
  pulseWidthMinUs = 0xFFFFFFFFUL;
  pulseWidthMaxUs = 0;
  pulseWidthSumUs = 0;
  pulseWidthSamples = 0;
  gapMinUs = 0xFFFFFFFFUL;
  gapMaxUs = 0;
  gapSumUs = 0;
  gapSamples = 0;
}

void clearEdgeRing() {
  noInterrupts();
  edgeTail = edgeHead;
  edgeOverflow = false;
  interrupts();
}

bool popEdge(EdgeEvent &event) {
  noInterrupts();
  if (edgeTail == edgeHead) {
    interrupts();
    return false;
  }
  event.timestampUs = edgeRing[edgeTail].timestampUs;
  event.level = edgeRing[edgeTail].level;
  edgeTail = (uint8_t)((edgeTail + 1U) & (EDGE_RING_SIZE - 1U));
  interrupts();
  return true;
}

bool takeOverflow() {
  noInterrupts();
  bool overflow = edgeOverflow;
  edgeOverflow = false;
  interrupts();
  return overflow;
}

void meterEdgeISR() {
  if (!captureEnabled) return;
  uint8_t next = (uint8_t)((edgeHead + 1U) & (EDGE_RING_SIZE - 1U));
  if (next == edgeTail) {
    edgeOverflow = true;
    return;
  }
  edgeRing[edgeHead].timestampUs = micros();
  edgeRing[edgeHead].level = (uint8_t)digitalRead(PIN_METER);
  edgeHead = next;
}

void printStatus() {
  Serial.println(F("BILL_OBSERVER:STATUS"));
  Serial.println(F("MODE=OBSERVE_ONLY"));
  Serial.println(F("PIN_D3=TB_METER_CHANGE"));
  Serial.println(F("EXTERNAL_PULLUP=4.7K_TO_ARDUINO_5V_REQUIRED"));
  Serial.println(F("MAPPING=UNVERIFIED_V1_HYPOTHESIS"));
  Serial.println(F("MAPPING=2_PULSES_PHP20;5_PULSES_PHP50;10_PULSES_PHP100"));
  Serial.println(F("TRAIN_GAP_US=250000_HYPOTHESIS"));
  Serial.print(F("ARMED="));
  Serial.println(captureEnabled ? F("1") : F("0"));
  Serial.println(F("ORDER_CREDIT=0"));
  Serial.println(F("INHIBIT_DRIVER=D4_NOT_DRIVEN"));
  Serial.println(F("COIN_POWER=D5_OFF"));
  Serial.println(F("PCA_OUTPUTS=D7_DISABLED"));
  Serial.println(F("COMMANDS=ARM,DISARM,STATUS,HELP"));
}

void printTiming(uint32_t minValue, uint32_t maxValue, uint32_t sumValue,
                 uint16_t samples, const __FlashStringHelper *name) {
  Serial.print(name);
  Serial.print(F("_MIN_US="));
  if (!samples) Serial.println(F("NA"));
  else Serial.println(minValue);
  Serial.print(name);
  Serial.print(F("_MAX_US="));
  if (!samples) Serial.println(F("NA"));
  else Serial.println(maxValue);
  Serial.print(name);
  Serial.print(F("_AVG_US="));
  if (!samples) Serial.println(F("NA"));
  else Serial.println(sumValue / samples);
}

void finishTrain() {
  if (!trainActive || fallingPulses == 0) {
    resetTrain();
    return;
  }

  uint32_t durationUs = lastEdgeUs - trainStartUs;
  uint32_t valueCentavos = candidateCentavos(fallingPulses);
  Serial.println(F("BILL_EVENT:BEGIN"));
  Serial.print(F("RAW_PULSES="));
  Serial.println(fallingPulses);
  Serial.print(F("CANDIDATE_PHP="));
  if (valueCentavos) printMoney(valueCentavos);
  else Serial.print(F("UNKNOWN"));
  Serial.println();
  Serial.print(F("CANDIDATE_CENTAVOS="));
  Serial.println(valueCentavos);
  Serial.println(F("MAPPING_STATUS=UNVERIFIED_HYPOTHESIS_DO_NOT_CREDIT"));
  Serial.print(F("TRAIN_START_US="));
  Serial.println(trainStartUs);
  Serial.print(F("TRAIN_END_US="));
  Serial.println(lastEdgeUs);
  Serial.print(F("TRAIN_DURATION_US="));
  Serial.println(durationUs);
  printTiming(pulseWidthMinUs, pulseWidthMaxUs, pulseWidthSumUs,
              pulseWidthSamples, F("PULSE_WIDTH"));
  printTiming(gapMinUs, gapMaxUs, gapSumUs, gapSamples,
              F("INTERPULSE_GAP"));
  if (valueCentavos) {
    observedTotalCentavos += valueCentavos;
    Serial.print(F("OBSERVED_TOTAL_PHP="));
    printMoney(observedTotalCentavos);
    Serial.println();
  }
  Serial.println(F("ORDER_CREDIT=0"));
  Serial.println(F("BILL_EVENT:END"));
  resetTrain();
}

void processEdge(const EdgeEvent &event) {
  Serial.print(F("EDGE_LEVEL="));
  Serial.print(event.level ? F("HIGH") : F("LOW"));
  Serial.print(F(";TIMESTAMP_US="));
  Serial.println(event.timestampUs);

  lastEdgeUs = event.timestampUs;
  if (!event.level) {
    if (!trainActive) {
      resetTrain();
      trainActive = true;
      trainStartUs = event.timestampUs;
    }
    fallingPulses++;
    if (lastFallingUs) {
      uint32_t gap = event.timestampUs - lastFallingUs;
      if (gap < gapMinUs) gapMinUs = gap;
      if (gap > gapMaxUs) gapMaxUs = gap;
      gapSumUs += gap;
      gapSamples++;
    }
    lastFallingUs = event.timestampUs;
    pulseStartUs = event.timestampUs;
    pulseOpen = true;
  } else if (trainActive && pulseOpen) {
    uint32_t width = event.timestampUs - pulseStartUs;
    if (width < pulseWidthMinUs) pulseWidthMinUs = width;
    if (width > pulseWidthMaxUs) pulseWidthMaxUs = width;
    pulseWidthSumUs += width;
    pulseWidthSamples++;
    pulseOpen = false;
  }
}

void drainEdges() {
  if (takeOverflow()) {
    captureEnabled = false;
    resetTrain();
    Serial.println(F("FAULT=EDGE_RING_OVERFLOW;ARM_REQUIRED"));
    clearEdgeRing();
    return;
  }
  EdgeEvent event;
  while (popEdge(event)) processEdge(event);
  if (trainActive && (uint32_t)(micros() - lastEdgeUs) >= TRAIN_GAP_US) {
    finishTrain();
  }
}

void armObserver() {
  resetTrain();
  clearEdgeRing();
  captureEnabled = true;
  Serial.println(F("ARMED=1;OBSERVE_ONLY=1;ORDER_CREDIT=0"));
}

void disarmObserver() {
  captureEnabled = false;
  drainEdges();
  if (trainActive) finishTrain();
  clearEdgeRing();
  Serial.println(F("ARMED=0;OBSERVE_ONLY=1;ORDER_CREDIT=0"));
}

void processCommand() {
  commandBuffer[commandLength] = '\0';
  if (!strcmp(commandBuffer, "ARM")) armObserver();
  else if (!strcmp(commandBuffer, "DISARM")) disarmObserver();
  else if (!strcmp(commandBuffer, "STATUS")) printStatus();
  else if (!strcmp(commandBuffer, "HELP")) {
    Serial.println(F("COMMANDS=ARM,DISARM,STATUS,HELP"));
  } else if (commandLength > 0) {
    Serial.println(F("ERR=UNKNOWN_COMMAND"));
  }
  commandLength = 0;
}

void readCommands() {
  while (Serial.available() > 0) {
    char value = (char)Serial.read();
    if (value == '\n' || value == '\r') {
      processCommand();
    } else if (commandLength < sizeof(commandBuffer) - 1U) {
      commandBuffer[commandLength++] = value;
    } else {
      commandLength = 0;
      Serial.println(F("ERR=COMMAND_TOO_LONG"));
    }
  }
}

void setup() {
  // Observer safety: no inhibit drive, coin power off, PCA OE disabled.
  pinMode(PIN_METER, INPUT);
  pinMode(PIN_BILL_INHIBIT, INPUT);
  pinMode(PIN_COIN_POWER, OUTPUT);
  digitalWrite(PIN_COIN_POWER, LOW);
  pinMode(PIN_PCA_OE, OUTPUT);
  digitalWrite(PIN_PCA_OE, HIGH);

  Serial.begin(115200);
  attachInterrupt(digitalPinToInterrupt(PIN_METER), meterEdgeISR, CHANGE);
  delay(100);
  Serial.println(F("MENDO_BILL_OBSERVER:READY"));
  Serial.println(F("NO_ORDER_CREDIT_NO_INHIBIT_DRIVE_NO_SERVO"));
  printStatus();
  Serial.println(F("SEND=ARM_WHEN_READY_TO_CAPTURE_TB_METER"));
}

void loop() {
  readCommands();
  drainEdges();
}
