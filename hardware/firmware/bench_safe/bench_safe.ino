/*
 * USB-only bench diagnostic for the Mendo Uno.
 *
 * This image deliberately does not implement cash acceptance, pulse capture,
 * I2C/PCA9685 access, or dispensing. It is safe for identifying the board and
 * checking the serial link while the TB, Allan acceptor, PCA9685, and servos
 * are disconnected.
 */

#include <Arduino.h>
#include <string.h>

static const uint8_t PIN_COIN = 2;
static const uint8_t PIN_BILL = 3;
static const uint8_t PIN_BILL_INHIBIT = 4;
static const uint8_t PIN_COIN_POWER = 5;
static const uint8_t PIN_PCA_OE = 7; // PCA9685 OE is active-low
static const uint8_t PIN_INTERLOCK = 8;

static char commandBuffer[32];
static uint8_t commandLength = 0;

void holdAllHardwareSafe() {
  // Do not drive the unknown TB inhibit polarity from this diagnostic image.
  pinMode(PIN_BILL_INHIBIT, INPUT);
  pinMode(PIN_COIN, INPUT);
  pinMode(PIN_BILL, INPUT);

  // The planned fail-off coin-power control is low/off.
  pinMode(PIN_COIN_POWER, OUTPUT);
  digitalWrite(PIN_COIN_POWER, LOW);

  // Active-low OE: HIGH means PCA outputs disabled.
  pinMode(PIN_PCA_OE, OUTPUT);
  digitalWrite(PIN_PCA_OE, HIGH);

  pinMode(PIN_INTERLOCK, INPUT_PULLUP);
}

void printStatus() {
  Serial.println(F("MENDO_SAFE_DIAGNOSTIC:STATUS"));
  Serial.println(F("BOARD=ATMEGA328P_UNO"));
  Serial.println(F("MODE=USB_ONLY"));
  Serial.println(F("ACCEPTORS=DISABLED"));
  Serial.println(F("D2=INPUT_COIN_NOT_DRIVEN"));
  Serial.println(F("D3=INPUT_BILL_NOT_DRIVEN"));
  Serial.println(F("D4=INPUT_INHIBIT_NOT_DRIVEN"));
  Serial.println(F("D5=LOW_COIN_POWER_OFF"));
  Serial.println(F("D7=HIGH_PCA_OE_DISABLED"));
  Serial.println(F("I2C=PCA_NOT_ACCESSED"));
  Serial.println(F("DISPENSING=NOT_IMPLEMENTED"));
  Serial.println(F("WARNING=DISCONNECT_TB_AND_SERVOS_BEFORE_TESTING"));
}

void processCommand() {
  commandBuffer[commandLength] = '\0';
  if (!strcmp(commandBuffer, "PING")) {
    Serial.println(F("PONG"));
  } else if (!strcmp(commandBuffer, "STATUS")) {
    printStatus();
  } else if (!strcmp(commandBuffer, "HELP")) {
    Serial.println(F("COMMANDS=PING,STATUS,HELP"));
  } else if (commandLength > 0) {
    Serial.println(F("ERR=UNKNOWN_COMMAND"));
  }
  commandLength = 0;
}

void setup() {
  holdAllHardwareSafe();
  Serial.begin(115200);
  delay(100);
  Serial.println(F("MENDO_SAFE_DIAGNOSTIC:READY"));
  Serial.println(F("NO_CASH_NO_SERVO_NO_I2C"));
  printStatus();
}

void loop() {
  holdAllHardwareSafe();
  while (Serial.available() > 0) {
    char value = (char)Serial.read();
    if (value == '\n' || value == '\r') {
      processCommand();
    } else if (commandLength < sizeof(commandBuffer) - 1) {
      commandBuffer[commandLength++] = value;
    } else {
      commandLength = 0;
      Serial.println(F("ERR=COMMAND_TOO_LONG"));
    }
  }
}
