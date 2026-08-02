#include <Arduino.h>
#include <SPI.h>

// ============================================================================
// Primer #2 full standalone hardware test
// ESP32-C3 Mini acts as:
//   - SPI master for the Primer #2 control plane
//   - UART transmitter that emulates Primer #1
//   - secure_enable source that emulates Tiny
//
// IMPORTANT PHYSICAL STRAPS (keep the existing wiring):
//   Primer R12 / fatal_latched_i -> GND
//   Primer R11 / zeroize_ni      -> 3V3
//   Primer T12 / secure_enable_i -> ESP32 GPIO20
//
// The sketch leaves GPIO7 as INPUT until GET_INFO proves target_id == 2.
// This avoids output contention if Primer #1 is still loaded by mistake.
// ============================================================================

// ---------------- Existing SPI wiring ----------------
constexpr uint8_t PIN_SPI_SCK  = 0;   // ESP32 -> Primer P16 / SPI_SCK
constexpr uint8_t PIN_SPI_MOSI = 1;   // ESP32 -> Primer P15 / SPI_MOSI
constexpr uint8_t PIN_SPI_MISO = 3;   // ESP32 <- Primer T15 / SPI_MISO
constexpr uint8_t PIN_SPI_CS_N = 10;  // ESP32 -> Primer R14 / SPI_CS_N

// ---------------- Existing monitor/safety wiring ----------
constexpr uint8_t PIN_HEARTBEAT    = 4;   // ESP32 <- Primer T11 / heartbeat_o
constexpr uint8_t PIN_FAULT        = 5;   // ESP32 <- Primer T13 / fault_o
constexpr uint8_t PIN_IRQ_N        = 6;   // ESP32 <- Primer T14 / irq_no
constexpr uint8_t PIN_UART_TX      = 7;   // ESP32 -> Primer R13 / uart_rx_i
constexpr uint8_t PIN_SECURE_ENABLE = 20; // ESP32 -> Primer T12 / secure_enable_i

constexpr uint32_t SPI_FREQUENCY_HZ = 100000; // conservative bring-up rate
constexpr uint32_t UART_BAUD = 115200;
constexpr size_t SPI_MAX_PAYLOAD = 66;
constexpr size_t SPI_MAX_PACKET = 76;
constexpr size_t UART_FRAME_SIZE = 66;

constexpr uint8_t SPI_MAGIC = 0xA5;
constexpr uint8_t SPI_VERSION = 0x01;
constexpr uint8_t FLAG_RESPONSE = 0x01;
constexpr uint8_t FLAG_ERROR = 0x02;

// Commands
constexpr uint8_t CMD_GET_INFO = 0x01;
constexpr uint8_t CMD_GET_STATUS = 0x02;
constexpr uint8_t CMD_RUN_SELF_TEST = 0x03;
constexpr uint8_t CMD_GET_TXN_RESULT = 0x04;
constexpr uint8_t CMD_RETIRE_TXN_RESULT = 0x05;
constexpr uint8_t CMD_ZEROIZE = 0x06;
constexpr uint8_t CMD_STAGE_SESSION = 0x07;
constexpr uint8_t CMD_COMMIT_SESSION = 0x08;
constexpr uint8_t CMD_ABORT_SESSION = 0x09;
constexpr uint8_t CMD_GET_RX_STATUS = 0x40;
constexpr uint8_t CMD_READ_AUTH_RESULT = 0x41;
constexpr uint8_t CMD_ACK_AUTH_RESULT = 0x42;
constexpr uint8_t CMD_CLEAR_DIAGNOSTIC_COUNTERS = 0x43;

// Error codes used by this test
constexpr uint16_t ERR_OK = 0x0000;
constexpr uint16_t ERR_BAD_CRC = 0x0104;
constexpr uint16_t ERR_RESULT_NOT_READY = 0x0304;
constexpr uint16_t ERR_BAD_SESSION = 0x0402;
constexpr uint16_t ERR_ZEROIZED = 0x0403;
constexpr uint16_t ERR_REPLAY = 0x0501;
constexpr uint16_t ERR_STALE_SEQUENCE = 0x0502;
constexpr uint16_t ERR_BAD_TAG = 0x0503;
constexpr uint16_t ERR_RESULT_PENDING_DROP = 0x0506;
constexpr uint16_t ERR_AUTH_THRESHOLD = 0x0601;

// Session states
constexpr uint8_t SESSION_SELF_TEST_REQUIRED = 1;
constexpr uint8_t SESSION_READY_NO_SESSION = 3;
constexpr uint8_t SESSION_STAGED = 4;
constexpr uint8_t SESSION_COMMITTED_BLOCKED = 5;
constexpr uint8_t SESSION_ACTIVE = 6;
constexpr uint8_t SESSION_ZEROIZE_BUSY = 7;
constexpr uint8_t SESSION_FAULT_LOCKED = 8;

// Transaction states
constexpr uint8_t TXN_ACCEPTED = 1;
constexpr uint8_t TXN_RUNNING = 2;
constexpr uint8_t TXN_SUCCEEDED = 3;
constexpr uint8_t TXN_FAILED = 4;
constexpr uint8_t TXN_ZEROIZED = 5;

// Status flags
constexpr uint8_t PENDING_AUTHENTICATED_RESULT = 0x04;
constexpr uint8_t SECURE_SELF_TEST_PASS = 0x01;
constexpr uint8_t SECURE_SESSION_STAGED = 0x02;
constexpr uint8_t SECURE_ENABLE = 0x04;
constexpr uint8_t SECURE_FAULT_LOCKED = 0x10;

constexpr uint8_t ZEROIZE_ALL = 0xFF;
constexpr uint32_t DIAG_ALL = 0xFFFFFFFFUL;
constexpr uint16_t SELF_TEST_MASK = 0x03E3;

constexpr uint8_t EXPECTED_TARGET_ID = 0x02;
constexpr uint32_t EXPECTED_CAPABILITIES = 0x00001E0FUL;
constexpr uint32_t EXPECTED_BUILD_ID = 0x50320001UL;

constexpr uint32_t DUMMY_SESSION_ID = 0x10203040UL;
constexpr uint32_t ACTIVE_SESSION_ID = 0x11223344UL;
constexpr uint32_t WRONG_SESSION_ID = 0xDEADBEEFUL;

constexpr uint8_t SESSION_KEY[16] = {
  0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
  0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF
};

constexpr uint8_t NONCE_PREFIX[8] = {
  0x10, 0x21, 0x32, 0x43, 0x54, 0x65, 0x76, 0x87
};

constexpr uint8_t EXPECTED_PLAINTEXT[24] = {
  0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
  0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10,
  0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x00
};

// Byte-exact vectors taken from the Primer #2 RTL regression.
constexpr uint8_t FRAME_SEQ1[UART_FRAME_SIZE] = {
  0xA5, 0x5A, 0x01, 0x02, 0x12, 0x34, 0x11, 0x22, 0x33, 0x44, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x18, 0x33, 0x44, 0x00, 0x00,
  0x00, 0x00, 0x0C, 0x32, 0x0E, 0x28, 0x03, 0x7E, 0x35, 0xD1, 0xB8, 0x55,
  0xC2, 0x90, 0x82, 0x6D, 0x37, 0x9B, 0x13, 0x70, 0x3B, 0xA3, 0x78, 0xB2,
  0xCC, 0x30, 0x65, 0x71, 0xAF, 0x37, 0xED, 0x85, 0x4B, 0x37, 0xA8, 0x9E,
  0x92, 0xC0, 0xD8, 0x61, 0x90, 0x1A
};

constexpr uint8_t FRAME_SEQ2[UART_FRAME_SIZE] = {
  0xA5, 0x5A, 0x01, 0x02, 0x12, 0x34, 0x11, 0x22, 0x33, 0x44, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x18, 0x33, 0x44, 0x00, 0x00,
  0x00, 0x00, 0xC7, 0x58, 0xB1, 0x11, 0x5B, 0xA6, 0xF9, 0xEA, 0xC5, 0xE8,
  0x7E, 0x54, 0x16, 0xC6, 0x55, 0xAB, 0x85, 0xA9, 0x7C, 0xE3, 0x85, 0x91,
  0x53, 0x57, 0x72, 0xFF, 0x8A, 0xC1, 0xF0, 0x85, 0xD5, 0xB7, 0x4F, 0x79,
  0x4F, 0x7E, 0xC8, 0xAE, 0x3F, 0x17
};

constexpr uint8_t FRAME_SEQ3[UART_FRAME_SIZE] = {
  0xA5, 0x5A, 0x01, 0x02, 0x12, 0x34, 0x11, 0x22, 0x33, 0x44, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x00, 0x18, 0x33, 0x44, 0x00, 0x00,
  0x00, 0x00, 0x48, 0x0E, 0xDA, 0xA2, 0x03, 0x7C, 0x4E, 0x7E, 0x42, 0x4B,
  0xD2, 0xB4, 0xB7, 0xAC, 0x77, 0x98, 0x38, 0x9A, 0xB0, 0xA6, 0x6E, 0xF5,
  0xB4, 0x74, 0x65, 0xBC, 0x0E, 0x43, 0x3B, 0xA0, 0x53, 0x2F, 0x9F, 0x64,
  0x29, 0x30, 0x14, 0xED, 0x15, 0xD9
};

SPISettings primerSpiSettings(SPI_FREQUENCY_HZ, MSBFIRST, SPI_MODE0);
HardwareSerial PrimerUart(1);

volatile uint32_t heartbeatEdges = 0;
uint16_t nextTxid = 0x1000;
bool uartTxEnabled = false;
bool testAborted = false;
uint16_t passCount = 0;
uint16_t failCount = 0;

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

void IRAM_ATTR heartbeatISR() {
  heartbeatEdges++;
}

uint16_t allocTxid() {
  return nextTxid++;
}

void printDivider(const char *title) {
  Serial.println();
  Serial.print("========== ");
  Serial.print(title);
  Serial.println(" ==========");
}

void printHex(const uint8_t *data, size_t length) {
  for (size_t i = 0; i < length; ++i) {
    if (data[i] < 0x10) Serial.print('0');
    Serial.print(data[i], HEX);
    if (i + 1 < length) Serial.print(' ');
  }
  Serial.println();
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
  for (int i = 7; i >= 0; --i) {
    p[i] = static_cast<uint8_t>(value);
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
         (static_cast<uint32_t>(p[2]) << 8) |
         static_cast<uint32_t>(p[3]);
}

uint64_t readBe64(const uint8_t *p) {
  uint64_t value = 0;
  for (size_t i = 0; i < 8; ++i) value = (value << 8) | p[i];
  return value;
}

uint16_t crc16CcittFalse(const uint8_t *data, size_t length) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < length; ++i) {
    crc ^= static_cast<uint16_t>(data[i]) << 8;
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x8000)
              ? static_cast<uint16_t>((crc << 1) ^ 0x1021)
              : static_cast<uint16_t>(crc << 1);
    }
  }
  return crc;
}

void recordResult(const char *name, bool passed) {
  Serial.printf("%-38s : %s\n", name, passed ? "PASS" : "FAIL");
  if (passed) ++passCount;
  else ++failCount;
}

bool requireStep(const char *name, bool passed) {
  recordResult(name, passed);
  if (!passed) {
    testAborted = true;
    digitalWrite(PIN_SECURE_ENABLE, LOW);
    Serial.println("Critical failure: remaining destructive tests are stopped.");
  }
  return passed;
}

bool waitForIrqLow(uint32_t timeoutMs) {
  const uint32_t started = millis();
  while (digitalRead(PIN_IRQ_N) != LOW) {
    if (millis() - started >= timeoutMs) {
      Serial.println("ERROR: timeout waiting for IRQ_N LOW");
      return false;
    }
    delay(1);
  }
  return true;
}


// Drain a response mailbox that may have been created by CS/SCK glitches while
// the ESP32 was booting. At the clean reset state there are no retained/auth
// results, so IRQ_N LOW here means a stale response mailbox is pending.
//
// We clock the maximum possible packet length. This guarantees that the FPGA's
// tx_bits_sent reaches mailbox_length and clears mailbox_pending on CS rising.
bool drainStartupMailbox() {
  if (digitalRead(PIN_IRQ_N) != LOW) {
    Serial.println("Startup mailbox: empty");
    return true;
  }

  Serial.println("Startup IRQ_N is LOW: draining stale SPI mailbox before GET_INFO");

  for (uint8_t attempt = 0; attempt < 3; ++attempt) {
    uint8_t stale[SPI_MAX_PACKET] {};

    SPI.beginTransaction(primerSpiSettings);
    digitalWrite(PIN_SPI_CS_N, LOW);
    delayMicroseconds(20);
    for (size_t i = 0; i < SPI_MAX_PACKET; ++i) {
      stale[i] = SPI.transfer(0x00);
    }
    delayMicroseconds(20);
    digitalWrite(PIN_SPI_CS_N, HIGH);
    SPI.endTransaction();
    delay(10);

    Serial.printf("Startup drain attempt %u, first 16 RX bytes: ",
                  static_cast<unsigned>(attempt + 1));
    printHex(stale, 16);

    if (digitalRead(PIN_IRQ_N) == HIGH) {
      Serial.println("Startup mailbox drained successfully");
      return true;
    }
  }

  Serial.println("ERROR: IRQ_N remained LOW after startup mailbox drain");
  return false;
}

bool sendRequestPacket(
    uint8_t command,
    uint16_t transactionId,
    const uint8_t *payload,
    uint16_t payloadLength,
    bool corruptCrc = false) {
  if (payloadLength > SPI_MAX_PAYLOAD) {
    Serial.println("ERROR: SPI request payload too large");
    return false;
  }

  uint8_t packet[SPI_MAX_PACKET] {};
  const size_t packetLength = 10 + payloadLength;
  packet[0] = SPI_MAGIC;
  packet[1] = SPI_VERSION;
  packet[2] = command;
  packet[3] = 0x00;
  writeBe16(&packet[4], transactionId);
  writeBe16(&packet[6], payloadLength);
  if (payloadLength && payload) memcpy(&packet[8], payload, payloadLength);

  uint16_t crc = crc16CcittFalse(packet, 8 + payloadLength);
  if (corruptCrc) crc ^= 0x0001;
  writeBe16(&packet[8 + payloadLength], crc);

  Serial.print(corruptCrc ? "TX (bad CRC): " : "TX: ");
  printHex(packet, packetLength);

  SPI.beginTransaction(primerSpiSettings);
  digitalWrite(PIN_SPI_CS_N, LOW);
  delayMicroseconds(10);
  for (size_t i = 0; i < packetLength; ++i) SPI.transfer(packet[i]);
  delayMicroseconds(10);
  digitalWrite(PIN_SPI_CS_N, HIGH);
  SPI.endTransaction();
  return true;
}

bool readResponseRaw(
    uint8_t expectedCommand,
    uint16_t expectedTransactionId,
    SpiResponse &response,
    uint32_t timeoutMs = 1000) {
  response = SpiResponse {};
  if (!waitForIrqLow(timeoutMs)) return false;

  SPI.beginTransaction(primerSpiSettings);
  digitalWrite(PIN_SPI_CS_N, LOW);
  delayMicroseconds(10);

  for (size_t i = 0; i < 8; ++i) response.packet[i] = SPI.transfer(0x00);
  response.payloadLength = readBe16(&response.packet[6]);
  if (response.payloadLength > SPI_MAX_PAYLOAD) {
    digitalWrite(PIN_SPI_CS_N, HIGH);
    SPI.endTransaction();
    Serial.printf("ERROR: invalid response payload length %u\n", response.payloadLength);
    Serial.print("RX header: ");
    printHex(response.packet, 8);
    return false;
  }

  response.packetLength = 10 + response.payloadLength;
  for (size_t i = 8; i < response.packetLength; ++i) {
    response.packet[i] = SPI.transfer(0x00);
  }

  delayMicroseconds(10);
  digitalWrite(PIN_SPI_CS_N, HIGH);
  SPI.endTransaction();
  delay(3);

  Serial.print("RX: ");
  printHex(response.packet, response.packetLength);

  if (response.packet[0] != SPI_MAGIC || response.packet[1] != SPI_VERSION) {
    Serial.println("ERROR: invalid response magic/version");
    return false;
  }
  if (response.packet[2] != expectedCommand) {
    Serial.printf("ERROR: response command expected 0x%02X got 0x%02X\n",
                  expectedCommand, response.packet[2]);
    return false;
  }
  if ((response.packet[3] & FLAG_RESPONSE) == 0) {
    Serial.printf("ERROR: response flag missing: 0x%02X\n", response.packet[3]);
    return false;
  }
  if (readBe16(&response.packet[4]) != expectedTransactionId) {
    Serial.printf("ERROR: response TXID expected 0x%04X got 0x%04X\n",
                  expectedTransactionId, readBe16(&response.packet[4]));
    return false;
  }

  const uint16_t calculated = crc16CcittFalse(response.packet, 8 + response.payloadLength);
  const uint16_t received = readBe16(&response.packet[8 + response.payloadLength]);
  if (calculated != received) {
    Serial.printf("ERROR: response CRC expected 0x%04X got 0x%04X\n",
                  calculated, received);
    return false;
  }
  return true;
}

bool transactRaw(
    uint8_t command,
    uint16_t transactionId,
    const uint8_t *payload,
    uint16_t payloadLength,
    SpiResponse &response,
    uint32_t timeoutMs = 1000,
    bool corruptCrc = false) {
  if (!sendRequestPacket(command, transactionId, payload, payloadLength, corruptCrc)) {
    return false;
  }
  delay(15); // response mailbox construction margin
  return readResponseRaw(command, transactionId, response, timeoutMs);
}

bool decodeErrorResponse(
    const SpiResponse &response,
    uint16_t &errorCode,
    uint8_t &sessionState,
    uint8_t &operationState,
    uint16_t &detail) {
  if ((response.packet[3] & FLAG_ERROR) == 0 || response.payloadLength != 6) {
    return false;
  }
  const uint8_t *p = &response.packet[8];
  errorCode = readBe16(&p[0]);
  sessionState = p[2];
  operationState = p[3];
  detail = readBe16(&p[4]);
  return true;
}

bool transactSuccess(
    uint8_t command,
    uint16_t transactionId,
    const uint8_t *payload,
    uint16_t payloadLength,
    SpiResponse &response,
    uint32_t timeoutMs = 1000) {
  if (!transactRaw(command, transactionId, payload, payloadLength,
                   response, timeoutMs, false)) {
    return false;
  }
  if (response.packet[3] & FLAG_ERROR) {
    uint16_t code = 0, detail = 0;
    uint8_t session = 0, operation = 0;
    if (decodeErrorResponse(response, code, session, operation, detail)) {
      Serial.printf("FPGA ERROR code=0x%04X session=%u operation=%u detail=0x%04X\n",
                    code, session, operation, detail);
    } else {
      Serial.println("ERROR: malformed FPGA error response");
    }
    return false;
  }
  return true;
}

bool transactExpectedError(
    uint8_t command,
    const uint8_t *payload,
    uint16_t payloadLength,
    uint16_t expectedError,
    bool corruptCrc = false) {
  const uint16_t txid = allocTxid();
  SpiResponse response {};
  if (!transactRaw(command, txid, payload, payloadLength,
                   response, 1000, corruptCrc)) {
    return false;
  }

  uint16_t code = 0, detail = 0;
  uint8_t session = 0, operation = 0;
  if (!decodeErrorResponse(response, code, session, operation, detail)) {
    Serial.println("ERROR: expected an FPGA error response");
    return false;
  }
  Serial.printf("Expected error: code=0x%04X session=%u operation=%u detail=0x%04X\n",
                code, session, operation, detail);
  return code == expectedError;
}

bool getInfo() {
  printDivider("GET_INFO");
  const uint16_t txid = allocTxid();
  SpiResponse response {};
  if (!transactSuccess(CMD_GET_INFO, txid, nullptr, 0, response)) return false;
  if (response.payloadLength != 12) return false;

  const uint8_t *p = &response.packet[8];
  const uint8_t targetId = p[0];
  const uint8_t version = p[1];
  const uint32_t capabilities = readBe32(&p[2]);
  const uint32_t buildId = readBe32(&p[6]);
  const uint16_t reserved = readBe16(&p[10]);

  Serial.printf("target_id    = %u\n", targetId);
  Serial.printf("protocol     = %u\n", version);
  Serial.printf("capabilities = 0x%08lX\n", static_cast<unsigned long>(capabilities));
  Serial.printf("build_id     = 0x%08lX\n", static_cast<unsigned long>(buildId));
  Serial.printf("reserved     = 0x%04X\n", reserved);

  return targetId == EXPECTED_TARGET_ID &&
         version == SPI_VERSION &&
         capabilities == EXPECTED_CAPABILITIES &&
         buildId == EXPECTED_BUILD_ID &&
         reserved == 0;
}

bool getStatus(StatusInfo &status, bool verbose = true) {
  const uint16_t txid = allocTxid();
  SpiResponse response {};
  if (!transactSuccess(CMD_GET_STATUS, txid, nullptr, 0, response)) return false;
  if (response.payloadLength != 16) return false;
  const uint8_t *p = &response.packet[8];
  status.sessionState = p[0];
  status.operationState = p[1];
  status.pendingFlags = p[2];
  status.secureFlags = p[3];
  status.sessionId = readBe32(&p[4]);
  status.lastError = readBe16(&p[8]);
  status.activeTransactionId = readBe16(&p[10]);
  status.diagnosticSummary = readBe32(&p[12]);

  if (verbose) {
    Serial.printf("STATUS session=%u operation=%u pending=0x%02X secure=0x%02X ",
                  status.sessionState, status.operationState,
                  status.pendingFlags, status.secureFlags);
    Serial.printf("session_id=0x%08lX last_error=0x%04X active_txid=0x%04X diag=0x%08lX\n",
                  static_cast<unsigned long>(status.sessionId),
                  status.lastError, status.activeTransactionId,
                  static_cast<unsigned long>(status.diagnosticSummary));
  }
  return true;
}

bool getRxStatus(RxStatusInfo &status, bool verbose = true) {
  const uint16_t txid = allocTxid();
  SpiResponse response {};
  if (!transactSuccess(CMD_GET_RX_STATUS, txid, nullptr, 0, response)) return false;
  if (response.payloadLength != 16) return false;
  const uint8_t *p = &response.packet[8];
  status.rxState = p[0];
  status.authPending = p[1] != 0;
  status.acceptEnabled = p[2] != 0;
  status.consecutiveBadTags = p[3];
  status.activeSessionId = readBe32(&p[4]);
  status.lastAcceptedSequence = readBe64(&p[8]);

  if (verbose) {
    Serial.printf("RX_STATUS state=%u auth_pending=%u accept=%u bad_tags=%u ",
                  status.rxState, status.authPending, status.acceptEnabled,
                  status.consecutiveBadTags);
    Serial.printf("session=0x%08lX last_seq=%llu\n",
                  static_cast<unsigned long>(status.activeSessionId),
                  static_cast<unsigned long long>(status.lastAcceptedSequence));
  }
  return true;
}

bool waitForSessionState(uint8_t expected, uint32_t timeoutMs, StatusInfo *out = nullptr) {
  const uint32_t started = millis();
  while (millis() - started < timeoutMs) {
    StatusInfo status {};
    if (!getStatus(status, false)) return false;
    if (status.sessionState == expected) {
      if (out) *out = status;
      getStatus(status, true);
      return true;
    }
    delay(20);
  }
  Serial.printf("ERROR: timeout waiting for session state %u\n", expected);
  return false;
}

bool waitForLastError(uint16_t expected, uint32_t timeoutMs, StatusInfo *out = nullptr) {
  const uint32_t started = millis();
  while (millis() - started < timeoutMs) {
    StatusInfo status {};
    if (!getStatus(status, false)) return false;
    if (status.lastError == expected) {
      if (out) *out = status;
      getStatus(status, true);
      return true;
    }
    delay(20);
  }
  Serial.printf("ERROR: timeout waiting for last_error 0x%04X\n", expected);
  return false;
}

bool waitForAuthPending(uint32_t timeoutMs, RxStatusInfo *out = nullptr) {
  const uint32_t started = millis();
  while (millis() - started < timeoutMs) {
    RxStatusInfo status {};
    if (!getRxStatus(status, false)) return false;
    if (status.authPending) {
      if (out) *out = status;
      getRxStatus(status, true);
      return true;
    }
    delay(20);
  }
  Serial.println("ERROR: timeout waiting for authenticated result");
  return false;
}

bool waitForBadTagCount(uint8_t expected, uint32_t timeoutMs, RxStatusInfo *out = nullptr) {
  const uint32_t started = millis();
  while (millis() - started < timeoutMs) {
    RxStatusInfo status {};
    if (!getRxStatus(status, false)) return false;
    if (status.consecutiveBadTags == expected) {
      if (out) *out = status;
      getRxStatus(status, true);
      return true;
    }
    delay(20);
  }
  Serial.printf("ERROR: timeout waiting for bad-tag count %u\n", expected);
  return false;
}

bool queryTransactionResult(uint16_t originalTxid, TransactionResult &result) {
  uint8_t payload[2] {};
  writeBe16(payload, originalTxid);
  SpiResponse response {};
  if (!transactSuccess(CMD_GET_TXN_RESULT, allocTxid(), payload, sizeof(payload), response)) {
    return false;
  }
  if (response.payloadLength < 10) return false;
  const uint8_t *p = &response.packet[8];
  result.originalTxid = readBe16(&p[0]);
  result.transactionState = p[2];
  result.originalCommand = p[3];
  result.resultCode = readBe16(&p[4]);
  result.resultLength = readBe16(&p[6]);
  if (result.resultLength > sizeof(result.resultData) ||
      response.payloadLength != 10 + result.resultLength) {
    return false;
  }
  memset(result.resultData, 0, sizeof(result.resultData));
  if (result.resultLength) memcpy(result.resultData, &p[10], result.resultLength);
  Serial.printf("TXN_RESULT original=0x%04X state=%u cmd=0x%02X code=0x%04X length=%u\n",
                result.originalTxid, result.transactionState,
                result.originalCommand, result.resultCode, result.resultLength);
  return result.originalTxid == originalTxid;
}

bool waitTransactionFinal(uint16_t originalTxid, TransactionResult &result, uint32_t timeoutMs) {
  const uint32_t started = millis();
  while (millis() - started < timeoutMs) {
    if (!queryTransactionResult(originalTxid, result)) return false;
    if (result.transactionState != TXN_ACCEPTED &&
        result.transactionState != TXN_RUNNING) {
      return true;
    }
    delay(20);
  }
  Serial.println("ERROR: retained transaction did not complete");
  return false;
}

bool retireTransaction(uint16_t originalTxid) {
  uint8_t payload[2] {};
  writeBe16(payload, originalTxid);
  SpiResponse response {};
  return transactSuccess(CMD_RETIRE_TXN_RESULT, allocTxid(),
                         payload, sizeof(payload), response) &&
         response.payloadLength == 0;
}

bool issueRetainedAndWait(
    uint8_t command,
    const uint8_t *payload,
    uint16_t payloadLength,
    TransactionResult &result,
    uint32_t timeoutMs = 3000) {
  const uint16_t originalTxid = allocTxid();
  SpiResponse response {};
  if (!transactSuccess(command, originalTxid, payload, payloadLength, response)) return false;
  if (response.payloadLength != 0) return false;
  if (!waitTransactionFinal(originalTxid, result, timeoutMs)) return false;
  if (!retireTransaction(originalTxid)) return false;
  return result.originalCommand == command;
}

void buildStagePayload(uint32_t sessionId, uint8_t payload[28]) {
  memset(payload, 0, 28);
  writeBe32(&payload[0], sessionId);
  memcpy(&payload[4], SESSION_KEY, sizeof(SESSION_KEY));
  memcpy(&payload[20], NONCE_PREFIX, sizeof(NONCE_PREFIX));
}

bool stageSession(uint32_t sessionId) {
  uint8_t payload[28] {};
  buildStagePayload(sessionId, payload);
  SpiResponse response {};
  return transactSuccess(CMD_STAGE_SESSION, allocTxid(),
                         payload, sizeof(payload), response) &&
         response.payloadLength == 0;
}

bool commitSession(uint32_t sessionId) {
  uint8_t payload[4] {};
  writeBe32(payload, sessionId);
  TransactionResult result {};
  if (!issueRetainedAndWait(CMD_COMMIT_SESSION, payload, sizeof(payload), result)) {
    return false;
  }
  return result.transactionState == TXN_SUCCEEDED &&
         result.resultCode == ERR_OK &&
         result.resultLength == 0;
}

bool abortSession(uint32_t sessionId) {
  uint8_t payload[4] {};
  writeBe32(payload, sessionId);
  SpiResponse response {};
  return transactSuccess(CMD_ABORT_SESSION, allocTxid(),
                         payload, sizeof(payload), response) &&
         response.payloadLength == 0;
}

bool clearDiagnostics() {
  uint8_t payload[4] {};
  writeBe32(payload, DIAG_ALL);
  SpiResponse response {};
  return transactSuccess(CMD_CLEAR_DIAGNOSTIC_COUNTERS, allocTxid(),
                         payload, sizeof(payload), response) &&
         response.payloadLength == 0;
}

bool readAuthResult(AuthResult &result) {
  SpiResponse response {};
  if (!transactSuccess(CMD_READ_AUTH_RESULT, allocTxid(),
                       nullptr, 0, response)) {
    return false;
  }
  if (response.payloadLength != 38) return false;
  const uint8_t *p = &response.packet[8];
  result.sessionId = readBe32(&p[0]);
  result.sequence = readBe64(&p[4]);
  memcpy(result.plaintext, &p[12], sizeof(result.plaintext));
  result.status = readBe16(&p[36]);

  Serial.printf("AUTH_RESULT session=0x%08lX sequence=%llu status=0x%04X\n",
                static_cast<unsigned long>(result.sessionId),
                static_cast<unsigned long long>(result.sequence),
                result.status);
  Serial.print("plaintext: ");
  printHex(result.plaintext, sizeof(result.plaintext));
  return true;
}

bool verifyAuthResult(const AuthResult &result, uint64_t expectedSequence) {
  return result.sessionId == ACTIVE_SESSION_ID &&
         result.sequence == expectedSequence &&
         result.status == ERR_OK &&
         memcmp(result.plaintext, EXPECTED_PLAINTEXT,
                sizeof(EXPECTED_PLAINTEXT)) == 0;
}

bool ackAuthResult(uint32_t sessionId, uint64_t sequence) {
  uint8_t payload[12] {};
  writeBe32(&payload[0], sessionId);
  writeBe64(&payload[4], sequence);
  SpiResponse response {};
  return transactSuccess(CMD_ACK_AUTH_RESULT, allocTxid(),
                         payload, sizeof(payload), response) &&
         response.payloadLength == 0;
}

bool expectAckError(uint32_t sessionId, uint64_t sequence, uint16_t expectedError) {
  uint8_t payload[12] {};
  writeBe32(&payload[0], sessionId);
  writeBe64(&payload[4], sequence);
  return transactExpectedError(CMD_ACK_AUTH_RESULT,
                               payload, sizeof(payload), expectedError);
}

bool enablePrimer2UartTx() {
  if (uartTxEnabled) return true;
  PrimerUart.begin(UART_BAUD, SERIAL_8N1, -1, PIN_UART_TX);
  delay(20);
  uartTxEnabled = true;
  Serial.println("GPIO7 is now UART TX -> Primer #2 R13.");
  return true;
}

bool sendUartFrame(const uint8_t *frame, const char *label) {
  if (!uartTxEnabled) {
    Serial.println("ERROR: UART TX has not been enabled");
    return false;
  }
  delay(5); // >1 ms inter-frame idle requirement
  Serial.print("UART TX ");
  Serial.print(label);
  Serial.print(": ");
  printHex(frame, UART_FRAME_SIZE);
  const size_t written = PrimerUart.write(frame, UART_FRAME_SIZE);
  PrimerUart.flush();
  delay(15);
  return written == UART_FRAME_SIZE;
}

bool testHeartbeatWindow(uint32_t windowMs, uint32_t minimumEdges) {
  noInterrupts();
  const uint32_t startEdges = heartbeatEdges;
  interrupts();
  const uint32_t started = millis();
  while (millis() - started < windowMs) delay(10);
  noInterrupts();
  const uint32_t endEdges = heartbeatEdges;
  interrupts();
  const uint32_t delta = endEdges - startEdges;
  Serial.printf("heartbeat edges in %lu ms = %lu\n",
                static_cast<unsigned long>(windowMs),
                static_cast<unsigned long>(delta));
  return delta >= minimumEdges;
}

bool runSelfTest() {
  uint8_t payload[4] {};
  writeBe16(&payload[0], SELF_TEST_MASK);
  payload[2] = 0;
  payload[3] = 0;
  TransactionResult result {};
  if (!issueRetainedAndWait(CMD_RUN_SELF_TEST, payload, sizeof(payload),
                            result, 5000)) {
    return false;
  }
  return result.transactionState == TXN_SUCCEEDED &&
         result.resultCode == ERR_OK &&
         result.resultLength == 2 &&
         readBe16(result.resultData) == SELF_TEST_MASK;
}

bool runZeroizeAll() {
  uint8_t payload[4] = {ZEROIZE_ALL, 0, 0, 0};
  const uint16_t originalTxid = allocTxid();
  SpiResponse response {};
  if (!transactSuccess(CMD_ZEROIZE, originalTxid,
                       payload, sizeof(payload), response)) {
    return false;
  }

  // The command is already accepted and CORE_ZEROIZE is active, so it is now
  // safe to lower secure_enable for the next provisioning cycle.
  digitalWrite(PIN_SECURE_ENABLE, LOW);

  TransactionResult result {};
  if (!waitTransactionFinal(originalTxid, result, 3000)) return false;
  if (!retireTransaction(originalTxid)) return false;
  if (result.transactionState != TXN_ZEROIZED ||
      result.resultCode != ERR_ZEROIZED) {
    return false;
  }

  StatusInfo status {};
  return waitForSessionState(SESSION_READY_NO_SESSION, 2000, &status) &&
         status.sessionId == 0 &&
         (status.pendingFlags & PENDING_AUTHENTICATED_RESULT) == 0 &&
         digitalRead(PIN_FAULT) == LOW;
}

bool provisionAndActivate() {
  digitalWrite(PIN_SECURE_ENABLE, LOW);
  delay(5);
  if (!stageSession(ACTIVE_SESSION_ID)) return false;

  StatusInfo staged {};
  if (!waitForSessionState(SESSION_STAGED, 1000, &staged)) return false;
  if (staged.sessionId != ACTIVE_SESSION_ID ||
      (staged.secureFlags & SECURE_SESSION_STAGED) == 0) {
    return false;
  }

  if (!commitSession(ACTIVE_SESSION_ID)) return false;
  StatusInfo committed {};
  if (!waitForSessionState(SESSION_COMMITTED_BLOCKED, 1000, &committed)) return false;
  if (committed.sessionId != ACTIVE_SESSION_ID) return false;

  digitalWrite(PIN_SECURE_ENABLE, HIGH);
  StatusInfo active {};
  if (!waitForSessionState(SESSION_ACTIVE, 1000, &active)) return false;
  if (active.sessionId != ACTIVE_SESSION_ID ||
      (active.secureFlags & SECURE_ENABLE) == 0) {
    return false;
  }

  RxStatusInfo rx {};
  return getRxStatus(rx, true) && rx.acceptEnabled &&
         rx.activeSessionId == ACTIVE_SESSION_ID &&
         rx.lastAcceptedSequence == 0;
}

bool acceptReadAndAck(const uint8_t *frame, const char *label, uint64_t sequence) {
  if (!sendUartFrame(frame, label)) return false;
  RxStatusInfo rx {};
  if (!waitForAuthPending(2000, &rx)) return false;
  if (rx.lastAcceptedSequence != sequence) return false;

  AuthResult result {};
  if (!readAuthResult(result) || !verifyAuthResult(result, sequence)) return false;

  // First prove that a wrong session ACK does not release the result.
  if (!expectAckError(ACTIVE_SESSION_ID ^ 1UL, sequence, ERR_BAD_SESSION)) return false;
  if (!getRxStatus(rx, true) || !rx.authPending) return false;

  if (!ackAuthResult(ACTIVE_SESSION_ID, sequence)) return false;
  if (!getRxStatus(rx, true)) return false;
  return !rx.authPending && rx.lastAcceptedSequence == sequence;
}

bool testNegativeSequenceCases() {
  // Replay sequence 1.
  if (!sendUartFrame(FRAME_SEQ1, "replay seq1")) return false;
  StatusInfo status {};
  if (!waitForLastError(ERR_REPLAY, 1500, &status)) return false;

  RxStatusInfo rx {};
  if (!getRxStatus(rx, true) || rx.lastAcceptedSequence != 1 ||
      rx.consecutiveBadTags != 0 || rx.authPending) {
    return false;
  }

  // Wrong session, otherwise based on the valid seq2 vector.
  uint8_t wrongSession[UART_FRAME_SIZE] {};
  memcpy(wrongSession, FRAME_SEQ2, sizeof(wrongSession));
  wrongSession[6] ^= 0x01; // first session-ID byte in the full 66-byte frame
  if (!sendUartFrame(wrongSession, "wrong session")) return false;
  if (!waitForLastError(ERR_BAD_SESSION, 1500, &status)) return false;

  // Sequence zero.
  uint8_t sequenceZero[UART_FRAME_SIZE] {};
  memcpy(sequenceZero, FRAME_SEQ2, sizeof(sequenceZero));
  memset(&sequenceZero[10], 0, 8); // full-frame offsets for body sequence[0..7]
  if (!sendUartFrame(sequenceZero, "sequence zero")) return false;
  if (!waitForLastError(ERR_STALE_SEQUENCE, 1500, &status)) return false;

  // Forward gap: seq3 when seq2 has not yet been accepted.
  if (!sendUartFrame(FRAME_SEQ3, "forward gap seq3")) return false;
  if (!waitForLastError(ERR_STALE_SEQUENCE, 1500, &status)) return false;

  return getRxStatus(rx, true) &&
         rx.lastAcceptedSequence == 1 &&
         rx.consecutiveBadTags == 0 &&
         !rx.authPending;
}

bool testPendingResultProtection() {
  if (!sendUartFrame(FRAME_SEQ3, "valid seq3")) return false;
  RxStatusInfo rx {};
  if (!waitForAuthPending(2000, &rx) || rx.lastAcceptedSequence != 3) return false;

  // Send another sync/frame while result is pending. It must not overwrite seq3.
  if (!sendUartFrame(FRAME_SEQ3, "frame while result pending")) return false;
  StatusInfo status {};
  if (!waitForLastError(ERR_RESULT_PENDING_DROP, 1500, &status)) return false;

  if (!getRxStatus(rx, true) || !rx.authPending ||
      rx.lastAcceptedSequence != 3) {
    return false;
  }

  AuthResult result {};
  if (!readAuthResult(result) || !verifyAuthResult(result, 3)) return false;
  if (!ackAuthResult(ACTIVE_SESSION_ID, 3)) return false;
  return getRxStatus(rx, true) && !rx.authPending &&
         rx.lastAcceptedSequence == 3;
}

bool testBadTagThreshold() {
  uint8_t badTagFrame[UART_FRAME_SIZE] {};
  memcpy(badTagFrame, FRAME_SEQ1, sizeof(badTagFrame));
  badTagFrame[50] ^= 0x01; // first tag byte; sequence remains eligible seq1

  for (uint8_t attempt = 1; attempt <= 2; ++attempt) {
    char label[32] {};
    snprintf(label, sizeof(label), "bad tag #%u", attempt);
    if (!sendUartFrame(badTagFrame, label)) return false;
    RxStatusInfo rx {};
    if (!waitForBadTagCount(attempt, 2000, &rx)) return false;
    StatusInfo status {};
    if (!waitForLastError(ERR_BAD_TAG, 1000, &status)) return false;
    if (rx.lastAcceptedSequence != 0 || rx.authPending ||
        digitalRead(PIN_FAULT) != LOW) {
      return false;
    }
  }

  if (!sendUartFrame(badTagFrame, "bad tag #3 -> expected fault")) return false;

  StatusInfo finalStatus {};
  const uint32_t started = millis();
  bool locked = false;
  while (millis() - started < 3000) {
    if (!getStatus(finalStatus, false)) return false;
    if (finalStatus.sessionState == SESSION_FAULT_LOCKED &&
        digitalRead(PIN_FAULT) == HIGH) {
      locked = true;
      break;
    }
    delay(20);
  }
  getStatus(finalStatus, true);

  return locked &&
         finalStatus.lastError == ERR_AUTH_THRESHOLD &&
         (finalStatus.secureFlags & SECURE_FAULT_LOCKED) != 0 &&
         finalStatus.sessionId == 0;
}

bool runAllTests() {
  printDivider("PRIMER #2 FULL HARDWARE TEST");
  Serial.println("Keep R12->GND, R11->3V3, T12->GPIO20 and common GND.");
  Serial.println("The final bad-tag test deliberately leaves Primer #2 FAULT_LOCKED.");

  if (!requireStep("Heartbeat before protocol", testHeartbeatWindow(1200, 5))) return false;
  if (!requireStep("FAULT initially LOW", digitalRead(PIN_FAULT) == LOW)) return false;
  if (!requireStep("GET_INFO target/build/capabilities", getInfo())) return false;

  // Only now is it safe to turn GPIO7 into an output.
  if (!requireStep("Enable GPIO7 UART TX after target check", enablePrimer2UartTx())) return false;

  StatusInfo initial {};
  const bool initialOk = getStatus(initial, true) &&
                         initial.sessionState == SESSION_SELF_TEST_REQUIRED &&
                         initial.sessionId == 0 &&
                         digitalRead(PIN_FAULT) == LOW;
  if (!requireStep("Initial fail-closed state", initialOk)) return false;

  if (!requireStep("READ before authentication rejected",
                   transactExpectedError(CMD_READ_AUTH_RESULT, nullptr, 0,
                                         ERR_RESULT_NOT_READY))) return false;

  if (!requireStep("SPI corrupted CRC rejected",
                   transactExpectedError(CMD_GET_STATUS, nullptr, 0,
                                         ERR_BAD_CRC, true))) return false;

  if (!requireStep("RUN_SELF_TEST retained result", runSelfTest())) return false;

  StatusInfo ready {};
  const bool selfTestReady = waitForSessionState(SESSION_READY_NO_SESSION, 2000, &ready) &&
                             (ready.secureFlags & SECURE_SELF_TEST_PASS) != 0;
  if (!requireStep("Self-test gate -> READY_NO_SESSION", selfTestReady)) return false;
  if (!requireStep("Clear diagnostic counters", clearDiagnostics())) return false;

  printDivider("STAGE / ABORT LIFECYCLE");
  if (!requireStep("Stage dummy session", stageSession(DUMMY_SESSION_ID))) return false;
  if (!requireStep("Dummy session reaches STAGED",
                   waitForSessionState(SESSION_STAGED, 1000))) return false;

  uint8_t wrongAbortPayload[4] {};
  writeBe32(wrongAbortPayload, WRONG_SESSION_ID);
  if (!requireStep("Wrong-session ABORT rejected",
                   transactExpectedError(CMD_ABORT_SESSION,
                                         wrongAbortPayload,
                                         sizeof(wrongAbortPayload),
                                         ERR_BAD_SESSION))) return false;
  if (!requireStep("Correct ABORT clears staged session",
                   abortSession(DUMMY_SESSION_ID) &&
                   waitForSessionState(SESSION_READY_NO_SESSION, 1000))) return false;

  printDivider("PROVISION / ACTIVATE");
  if (!requireStep("Stage + commit + activate", provisionAndActivate())) return false;

  printDivider("VALID SEQUENCE 1");
  if (!requireStep("Valid seq1 decrypt/read/ACK",
                   acceptReadAndAck(FRAME_SEQ1, "valid seq1", 1))) return false;

  printDivider("REPLAY / STALE / SESSION FILTERS");
  if (!requireStep("Replay, stale, gap, wrong-session rejection",
                   testNegativeSequenceCases())) return false;

  printDivider("VALID SEQUENCE 2");
  if (!requireStep("Valid seq2 decrypt/read/ACK",
                   acceptReadAndAck(FRAME_SEQ2, "valid seq2", 2))) return false;

  printDivider("PENDING RESULT PROTECTION");
  if (!requireStep("Pending result cannot be overwritten",
                   testPendingResultProtection())) return false;

  printDivider("COMMAND ZEROIZE");
  if (!requireStep("ZEROIZE_ALL retained result and scrub", runZeroizeAll())) return false;

  printDivider("RE-PROVISION AFTER ZEROIZE");
  if (!requireStep("Re-stage + commit + activate", provisionAndActivate())) return false;

  printDivider("THREE BAD TAGS -> FAULT LOCK");
  if (!requireStep("Bad-tag threshold fault + zeroize", testBadTagThreshold())) return false;

  if (!requireStep("Heartbeat continues in FAULT_LOCKED",
                   testHeartbeatWindow(1200, 5))) return false;

  return true;
}

void printFinalSummary(bool overall) {
  printDivider("FINAL SUMMARY");
  Serial.printf("PASS count = %u\n", passCount);
  Serial.printf("FAIL count = %u\n", failCount);
  Serial.printf("OVERALL    = %s\n", overall ? "PASS" : "FAIL");
  Serial.printf("pins: heartbeat=%d fault=%d irq_n=%d secure_enable=%d\n",
                digitalRead(PIN_HEARTBEAT),
                digitalRead(PIN_FAULT),
                digitalRead(PIN_IRQ_N),
                digitalRead(PIN_SECURE_ENABLE));
  Serial.println();
  Serial.println("Not exercised without rewiring:");
  Serial.println("- external fatal_latched_i assertion (R12 is strapped to GND)");
  Serial.println("- external zeroize_ni pulse (R11 is strapped to 3V3)");
  Serial.println();
  if (overall) {
    Serial.println("Expected final state: FAULT_LOCKED after deliberate third bad tag.");
    Serial.println("Reprogram SRAM or reset the FPGA before another clean test run.");
  } else {
    Serial.println("Do not continue integration. Copy the complete Serial Monitor log.");
  }
}

void setup() {
  // Drive safety/control pins before the USB-serial startup delay. In
  // particular, CS_N must not float or pulse LOW while the FPGA is alive.
  pinMode(PIN_SPI_CS_N, OUTPUT);
  digitalWrite(PIN_SPI_CS_N, HIGH);

  pinMode(PIN_SECURE_ENABLE, OUTPUT);
  digitalWrite(PIN_SECURE_ENABLE, LOW);

  pinMode(PIN_HEARTBEAT, INPUT);
  pinMode(PIN_FAULT, INPUT);
  pinMode(PIN_IRQ_N, INPUT);

  // Keep R13 high-impedance until the FPGA identifies itself as Primer #2.
  pinMode(PIN_UART_TX, INPUT);

  Serial.begin(115200);
  delay(1500);

  attachInterrupt(digitalPinToInterrupt(PIN_HEARTBEAT), heartbeatISR, CHANGE);
  SPI.begin(PIN_SPI_SCK, PIN_SPI_MISO, PIN_SPI_MOSI, PIN_SPI_CS_N);

  Serial.println();
  Serial.println("Primer #2 ESP32-C3 standalone qualification started");
  Serial.printf("Initial pins: heartbeat=%d fault=%d irq_n=%d secure=%d\n",
                digitalRead(PIN_HEARTBEAT), digitalRead(PIN_FAULT),
                digitalRead(PIN_IRQ_N), digitalRead(PIN_SECURE_ENABLE));

  delay(2000); // FPGA configuration/startup margin

  if (!drainStartupMailbox()) {
    testAborted = true;
    ++failCount;
    printFinalSummary(false);
    return;
  }

  const bool overall = runAllTests();
  printFinalSummary(overall);
}

void loop() {
  static uint32_t lastReport = 0;
  static uint32_t previousEdges = 0;
  const uint32_t now = millis();
  if (now - lastReport >= 1000) {
    noInterrupts();
    const uint32_t currentEdges = heartbeatEdges;
    interrupts();
    const uint32_t edgesPerSecond = currentEdges - previousEdges;
    Serial.printf("monitor heartbeat=%d edges/s=%lu fault=%d irq_n=%d secure=%d\n",
                  digitalRead(PIN_HEARTBEAT),
                  static_cast<unsigned long>(edgesPerSecond),
                  digitalRead(PIN_FAULT),
                  digitalRead(PIN_IRQ_N),
                  digitalRead(PIN_SECURE_ENABLE));
    previousEdges = currentEdges;
    lastReport = now;
  }
}
