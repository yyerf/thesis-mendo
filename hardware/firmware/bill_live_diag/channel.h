// Channel state for the TB74 live pulse diagnostic.
//
// This lives in a header because the Arduino 1.x builder injects auto-generated
// function prototypes directly after the includes; any struct used in a
// function signature must already be visible at that point.

#ifndef MENDO_BILL_LIVE_DIAG_CHANNEL_H
#define MENDO_BILL_LIVE_DIAG_CHANNEL_H

#include <Arduino.h>

struct Channel {
  uint8_t pin;
  const __FlashStringHelper *name;
  volatile uint16_t *rawEdges;

  uint8_t rawLevel;
  uint8_t stableLevel;
  uint32_t lastRawChangeMs;

  bool trainActive;
  uint32_t trainStartMs;
  uint32_t lastActivityMs;
  uint16_t rawAtTrainStart;

  uint32_t lowStartMs;
  bool lowOpen;

  uint16_t pulses;
  uint32_t prevLowStartMs;

  uint16_t lowMin, lowMax;
  uint32_t lowSum;
  uint16_t perMin, perMax;
  uint32_t perSum;
  uint16_t perCount;
  uint16_t fastRejects;  // sub-80 ms intervals: impossible for real credit
};

#endif
