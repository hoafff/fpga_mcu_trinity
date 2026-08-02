#include <Arduino.h>
#include <SPI.h>

// Primer #1 -> Primer #2 direct-UART hardware qualification harness.
//
// The ESP32-C3 is only the shared SPI controller and temporary secure-enable
// source. GPIO7 remains INPUT/high-impedance for the entire run; Primer #1 R13
// is the only UART transmitter on the payload net.

// Shared SPI bus.
constexpr uint8_t PIN_SPI_SCK = 0;
constexpr uint8_t PIN_SPI_MOSI = 1;
constexpr uint8_t PIN_SPI_MISO = 3;

// Independent chip selects and IRQ inputs.
constexpr uint8_t PIN_P1_CS_N = 10;
constexpr uint8_t PIN_P2_CS_N = 4;
constexpr uint8_t PIN_P1_IRQ_N = 5;
constexpr uint8_t PIN_P2_IRQ_N = 6;

// Shared safety/control and passive UART monitor tap.
constexpr uint8_t PIN_UART_MONITOR = 7;      // INPUT only; never driven.
constexpr uint8_t PIN_SECURE_ENABLE = 20;   // Drives both Primer T12 pins.

constexpr uint32_t SPI_FREQUENCY_HZ = 100000;
constexpr size_t SPI_MAX_PAYLOAD = 66;
constexpr size_t SPI_MAX_PACKET = 76;

constexpr uint8_t SPI_MAGIC = 0xA5;
constexpr uint8_t SPI_VERSION = 0x01;
constexpr uint8_t FLAG_RESPONSE = 0x01;
constexpr uint8_t FLAG_ERROR = 0x02;

// Shared commands.
constexpr uint8_t CMD_GET_INFO = 0x01;
constexpr uint8_t CMD_GET_STATUS = 0x02;
constexpr uint8_t CMD_RUN_SELF_TEST = 0x03;
constexpr uint8_t CMD_GET_TXN_RESULT = 0x04;
constexpr uint8_t CMD_RETIRE_TXN_RESULT = 0x05;
constexpr uint8_t CMD_STAGE_SESSION = 0x07;
constexpr uint8_t CMD_COMMIT_SESSION = 0x08;

// Primer #1 commands.
constexpr uint8_t CMD_LOAD_TELEMETRY = 0x30;
constexpr uint8_t CMD_ENCRYPT_AND_SEND = 0x31;

// Primer #2 commands.
constexpr uint8_t CMD_GET_RX_STATUS = 0x40;
constexpr uint8_t CMD_READ_AUTH_RESULT = 0x41;
constexpr uint8_t CMD_ACK_AUTH_RESULT = 0x42;
constexpr uint8_t CMD_CLEAR_DIAGNOSTIC_COUNTERS = 0x43;

// Result/error codes used by this gate.
constexpr uint16_t ERR_OK = 0x0000;
constexpr uint16_t ERR_BAD_SESSION = 0x0402;
constexpr uint16_t ERR_RESULT_PENDING_DROP = 0x0506;

// Session/transaction states.
constexpr uint8_t SESSION_SELF_TEST_REQUIRED = 1;
constexpr uint8_t SESSION_READY_NO_SESSION = 3;
constexpr uint8_t SESSION_STAGED = 4;
constexpr uint8_t SESSION_COMMITTED_BLOCKED = 5;
constexpr uint8_t SESSION_ACTIVE = 6;
constexpr uint8_t TXN_ACCEPTED = 1;
constexpr uint8_t TXN_RUNNING = 2;
constexpr uint8_t TXN_SUCCEEDED = 3;

// Status flags.
constexpr uint8_t PENDING_SIDE_EFFECT_RESULT = 0x02;
constexpr uint8_t PENDING_AUTHENTICATED_RESULT = 0x04;
constexpr uint8_t SECURE_SELF_TEST_PASS = 0x01;
constexpr uint8_t SECURE_SESSION_STAGED = 0x02;
constexpr uint8_t SECURE_ENABLE = 0x04;
constexpr uint8_t SECURE_FAULT_LOCKED = 0x10;

// Primer #2 diagnostics: the pending-result negative test is expected; these
// diagnostics are not expected in this gate.
constexpr uint32_t DIAG_BAD_TAG = 0x00000010UL;
constexpr uint32_t DIAG_REPLAY_OR_STALE = 0x00000020UL;
constexpr uint32_t DIAG_FRAME_ERROR = 0x00000040UL;
constexpr uint32_t DIAG_RESULT_PENDING_DROP = 0x00000080UL;
constexpr uint32_t DIAG_ALL = 0xFFFFFFFFUL;

constexpr uint16_t P1_SELF_TEST_MASK = 0x013E;
constexpr uint16_t P2_SELF_TEST_MASK = 0x03E3;

constexpr uint32_t SESSION_ID = 0x11223344UL;
constexpr uint8_t SESSION_KEY[16] = {
  0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
  0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF
};
constexpr uint8_t NONCE_PREFIX[8] = {
  0x10, 0x21, 0x32, 0x43, 0x54, 0x65, 0x76, 0x87
};

// Distinct payloads prove that P2 returns the current authenticated plaintext,
// rather than stale data from an earlier sequence.
constexpr uint8_t PLAINTEXT_SEQ1[24] = {
  0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
  0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10,
  0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x00
};
constexpr uint8_t PLAINTEXT_SEQ2[24] = {
  0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7,
  0xA8, 0xA9, 0xAA, 0xAB, 0xAC, 0xAD, 0xAE, 0xAF,
  0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7
};
constexpr uint8_t PLAINTEXT_PENDING_PROBE[24] = {
  0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7,
  0xC8, 0xC9, 0xCA, 0xCB, 0xCC, 0xCD, 0xCE, 0xCF,
  0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7
};

struct Device {
  const char *name;
  uint8_t csPin;
  uint8_t irqPin;
  uint8_t expectedTargetId;
  uint32_t expectedCapabilities;
  uint32_t expectedBuildId;
  uint16_t nextTxid;
};

Device primer1 {
  "P1", PIN_P1_CS_N, PIN_P1_IRQ_N, 0x01, 0x000011FFUL, 0x50310001UL, 0x1100
};
Device primer2 {
  "P2", PIN_P2_CS_N, PIN_P2_IRQ_N, 0x02, 0x00001E0FUL, 0x50320001UL, 0x2200
};

SPISettings primerSpiSettings(SPI_FREQUENCY_HZ, MSBFIRST, SPI_MODE0);
uint16_t passCount = 0;
uint16_t failCount = 0;
bool testAborted = false;

struct SpiResponse {
  uint8_t packet[SPI_MAX_PACKET] {};
  size_t packetLength = 0;
  uint16_t payloadLength = 0;
};

struct StatusInfo {
  uint8_t sessionState = 0;
  uint8_t operationState = 0;
  uint8_t pendingFlags = 0;
  uint8_t secureFlags = 0;
  uint32_t sessionId = 0;
  uint16_t lastError = 0;
  uint16_t activeTransactionId = 0;
  uint32_t diagnosticSummary = 0;
};

struct RxStatusInfo {
  uint8_t rxState = 0;
  bool authPending = false;
  bool acceptEnabled = false;
  uint8_t consecutiveBadTags = 0;
  uint32_t activeSessionId = 0;
  uint64_t lastAcceptedSequence = 0;
};

struct TransactionResult {
  uint16_t originalTxid = 0;
  uint8_t transactionState = 0;
  uint8_t originalCommand = 0;
  uint16_t resultCode = 0;
  uint16_t resultLength = 0;
  uint8_t resultData[16] {};
};

struct AuthResult {
  uint32_t sessionId = 0;
  uint64_t sequence = 0;
  uint8_t plaintext[24] {};
  uint16_t status = 0;
};

uint16_t allocateTxid(Device &device) {
  return device.nextTxid++;
}

void writeBe16(uint8_t *p, uint16_t value) {
  p[0] = static_cast<uint8_t>(value >> 8);
  p[1] = static_cast<uint8_t>(value);
}

void writeBe32(uint8_t *p, uint32_t value) {
  p[0] = static_cast<uint8_t>(value >> 24);
  p[1] = static_cast<uint8_t>(value >> 16);
  p[2] = static_cast<uint8_t>(value >> 8);
  p[3] = static_cast<uint8_t>(value);
}

void writeBe64(uint8_t *p, uint64_t value) {
  for (int index = 7; index >= 0; --index) {
    p[index] = static_cast<uint8_t>(value);
    value >>= 8;
  }
}

uint16_t readBe16(const uint8_t *p) {
  return (static_cast<uint16_t>(p[0]) << 8) |
         static_cast<uint16_t>(p[1]);
}

uint32_t readBe32(const uint8_t *p) {
  return (static_cast<uint32_t>(p[0]) << 24) |
         (static_cast<uint32_t>(p[1]) << 16) |
         (static_ccast<uint32_t>(p[2]) << 8) |
         static_cast<uint32_t>(p[3]);
}

uint64_t readBe64(const uint8_t *p) {
  uint64_t value = 0;
  for (size_t index = 0; index < 8; ++index) {
    value = (value << 8) | p[index];
  }
  return value;
}

uint16_t crc16CcittFalse(const uint8_t *data, size_t length) {
  uint16_t crc = 0xFFFF;
  for (size_t index = 0; index < length; ++index) {
    crc ^= static_cast<uint16_t>(data[index]) << 8;
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x8000)
              ? static_cast<uint16_t>((crc << 1) ^ 0x1021)
              : static_cast<uint16_t>(crc << 1);
    }
  }
  return crc;
}

void printHex(const uint8_t *data, size_t length) {
  for (size_t index = 0; index < length; ++index) {
    if (data[index] < 0x10) Serial.print('0');
    Serial.print(data[index], HEX);
    if (index + 1 < length) Serial.print(' ');
  }
  Serial.println();
}

void printDivider(const char *title) {
  Serial.println();
  Serial.print("========== ");
  Serial.print(title);
  Serial.println(" ==========");
}

void recordResult(const char *name, bool passed) {
  Serial.printf("%-46s : %s\n", name, passed ? "PASS" : "FAIL");
  if (passed) {
    ++passCount;
  } else {
    ++failCount;
  }
}

bool requireStep(const char *name, bool passed) {
  recordResult(name, passed);
  if (!passed) {
    testAborted = true;
    digitalWrite(PIN_SECURE_ENABLE, LOW);
    Serial.println("Critical failure: secure_enable forced LOW; test stopped.");
  }
  return passed;
}

void deselectBoth() {
  digitalWrite(PIN_P1_CS_N, HIGH);
  digitalWrite(PIN_P2_CS_N, HIGH);
}

bool waitForIrqLow(Device &device, uint32_t timeoutMs) {
  const uint32_t started = millis();
  while (digitalRead(device.irqPin) != LOW) {
    if (millis() - started >= timeoutMs) {
      Serial.printf("%s ERROR: timeout waiting for IRQ_N LOW\n", device.name);
      return false;
    }
    delay(1);
  }
  return true;
}

bool drainStartupMailbox(Device &device) {
  if (digitalRead(device.irqPin) != LOW) {
    Serial.printf("%s startup mailbox: empty\n", device.name);
    return true;
  }

  Serial.printf("%s startup IRQ_N LOW: draining stale mailbox\n", device.name);
  for (uint8_t attempt = 0; attempt < 3; ++attempt) {
    uint8_t stale[SPI_MAX_PACKET] {};
    deselectBoth();
    SPI.beginTransaction(primerSpiSettings);
    digitalWrite(device.csPin, LOW);
    delayMicroseconds(20);
    for (size_t index = 0; index < SPI_MAX_PACKET; ++index) {
      stale[index] = SPI.transfer(0x00);
    }
    delayMicroseconds(20);
    digitalWrite(device.csPin, HIGH);
    SPI.endTransaction();
    delay(10);

    Serial.printf("%s drain attempt %u, first 16 bytes: ",
                  device.name, static_cast<unsigned>(attempt + 1));
    printHex(stale, 16);
    if (digitalRead(device.irqPin) == HIGH) return true;
  }
  return false;
}

bool sendRequestPacket(
    Device &device,
    uint8_t command,
    uint16_t transactionId,
    const uint8_t *payload,
    uint16_t payloadLength) {
  if (payloadLength > SPI_MAX_PAYLOAD) return false;

  uint8_t packet[SPI_MAX_PACKET] {};
  const size_t packetLength = 10 + payloadLength;
  packet[0] = SPI_MAGIC;
  packet[1] = SPI_VERSION;
  packet[2] = command;
  packet[3] = 0;
  writeBe16(&packet[4], transactionId);
  writeBe16(&packet[6], payloadLength);
  if (payloadLength != 0 && payload != nullptr) {
    memcpy(&packet[8], payload, payloadLength);
  }
  writeBe16(&packet[8 + payloadLength],
            crc16CcittFalse(packet, 8 + payloadLength));

  Serial.printf("%s TX cmd=0x%02X txid=0x%04X: ",
                device.name, command, transactionId);
  printHex(packet, packetLength);

  deselectBoth();
  SPI.beginTransaction(primerSpiSettings);
  digitalWrite(device.csPin, LOW);
  delayMicroseconds(10);
  for (size_t index = 0; index < packetLength; ++index) {
    SPI.transfer(packet[index]);
  }
  delayMicroseconds(10);
  digitalWrite(device.csPin, HIGH);
  SPI.endTransaction();
  return true;
}

bool readResponseRaw(
    Device &device,
    uint8_t expectedCommand,
    uint16_t expectedTransactionId,
    SpiResponse &response,
    uint32_t timeoutMs = 1000) {
  response = SpiResponse {};
  if (!waitForIrqLow(device, timeoutMs)) return false;

  deselectBoth();
  SPI.beginTransaction(primerSpiSettings);
  digitalWrite(device.csPin, LOW);
  delayMicroseconds(10);
  for (size_t index = 0; index < 8; ++index) {
    response.packet[index] = SPI.transfer(0x00);
  }
  response.payloadLength = readBe16(&response.packet[6]);
  if (response.payloadLength > SPI_MAX_PAYLOAD) {
    digitalWrite(device.csPin, HIGH);
    SPI.endTransaction();
    return false;
  }
  response.packetLength = 10 + response.payloadLength;
  for (size_t index = 8; index < response.packetLength; ++index) {
    response.packet[index] = SPI.transfer(0x00);
  }
  delayMicroseconds(10);
  digitalWrite(device.csPin, HIGH);
  SPI.endTransaction();
  delay(3);

  Serial.printf("%s RX: ", device.name);
  printHex(response.packet, response.packetLength);

  if (response.packet[0] != SPI_MAGIC || response.packet[1] != SPI_VERSION) {
    return false;
  }
  if (response.packet[2] != expectedCommand ||
      (response.packet[3] & FLAG_RESPONSE) == 0 ||
      readBe16(&response.packet[4]) != expectedTransactionId) {
    return false;
  }
  const uint16_t calculated =
      crc16CcittFalse(response.packet, 8 + response.payloadLength);
  const uint16_t received =
      readBe16(&response.packet[8 + response.payloadLength]);
  return calculated == received;
}

bool transactRaw(
    Device &device,
    uint8_t command,
    uint16_t transactionId,
    const uint8_t *payload,
    uint16_t payloadLength,
    SpiResponse &response,
    uint32_t timeoutMs = 1000) {
  if (!sendRequestPacket(device, command, transactionId, payload, payloadLength)) {
    return false;
  }
  delay(15);
  return readResponseRaw(device, command, transactionId, response, timeoutMs);
}

bool decodeErrorResponse(const SpiResponse &response, uint16_t &errorCode) {
  if ((response.packet[3] & FLAG_ERROR) == 0 || response.payloadLength != 6) {
    return false;
  }
  errorCode = readBe16(&response.packet[8]);
  return true;
}

bool transactSuccess(
    Device &device,
    uint8_t command,
    uint16_t transactionId,
    const uint8_t *payload,
    uint16_t payloadLength,
    SpiResponse &response,
    uint32_t timeoutMs = 1000) {
  if (!transactRaw(device, command, transactionId, payload, payloadLength,
                   response, timeoutMs)) {
    return false;
  }
  if ((response.packet[3] & FLAG_ERROR) != 0) {
    uint16_t errorCode = 0;
    decodeErrorResponse(response, errorCode);
    Serial.printf("%s FPGA ERROR 0x%04X\n", device.name, errorCode);
    return false;
  }
  return true;
}

bool transactExpectedError(
    Device &device,
    uint8_t command,
    const uint8_t *payload,
    uint16_t payloadLength,
    uint16_t expectedError) {
  const uint16_t txid = allocateTxid(device);
  SpiResponse response {};
  if (!transactRaw(device, command, txid, payload, payloadLength, response)) {
    return false;
  }
  uint16_t actualError = 0;
  if (!decodeErrorResponse(response, actualError)) return false;
  Serial.printf("%s expected error=0x%04X actual=0x%04X\n",
                device.name, expectedError, actualError);
  return actualError == expectedError;
}

#include "P1P2Control.hpp"
