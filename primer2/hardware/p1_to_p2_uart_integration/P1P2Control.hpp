#pragma once

bool getInfo(Device &device) {
  SpiResponse response {};
  const uint16_t txid = allocateTxid(device);
  if (!transactSuccess(device, CMD_GET_INFO, txid, nullptr, 0, response)) {
    return false;
  }
  if (response.payloadLength != 12) return false;
  const uint8_t *p = &response.packet[8];
  const uint8_t targetId = p[0];
  const uint8_t protocol = p[1];
  const uint32_t capabilities = readBe32(&p[2]);
  const uint32_t buildId = readBe32(&p[6]);
  const uint16_t reserved = readBe16(&p[10]);
  Serial.printf("%s INFO target=%u protocol=%u caps=0x%08lX build=0x%08lX\n",
                device.name, targetId, protocol,
                static_cast<unsigned long>(capabilities),
                static_cast<unsigned long>(buildId));
  return targetId == device.expectedTargetId &&
         protocol == SPI_VERSION &&
         capabilities == device.expectedCapabilities &&
         buildId == device.expectedBuildId && reserved == 0;
}

bool getStatus(Device &device, StatusInfo &status, bool verbose = true) {
  SpiResponse response {};
  if (!transactSuccess(device, CMD_GET_STATUS, allocateTxid(device),
                       nullptr, 0, response)) {
    return false;
  }
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
    Serial.printf("%s STATUS session=%u op=%u pending=0x%02X secure=0x%02X ",
                  device.name, status.sessionState, status.operationState,
                  status.pendingFlags, status.secureFlags);
    Serial.printf("sid=0x%08lX error=0x%04X txid=0x%04X diag=0x%08lX\n",
                  static_cast<unsigned long>(status.sessionId), status.lastError,
                  status.activeTransactionId,
                  static_cast<unsigned long>(status.diagnosticSummary));
  }
  return true;
}

bool waitForSessionState(
    Device &device,
    uint8_t expected,
    uint32_t timeoutMs,
    StatusInfo *out = nullptr) {
  const uint32_t started = millis();
  while (millis() - started < timeoutMs) {
    StatusInfo status {};
    if (!getStatus(device, status, false)) return false;
    if (status.sessionState == expected) {
      if (out != nullptr) *out = status;
      getStatus(device, status, true);
      return true;
    }
    delay(20);
  }
  return false;
}

bool waitForLastError(
    Device &device,
    uint16_t expected,
    uint32_t timeoutMs,
    StatusInfo *out = nullptr) {
  const uint32_t started = millis();
  while (millis() - started < timeoutMs) {
    StatusInfo status {};
    if (!getStatus(device, status, false)) return false;
    if (status.lastError == expected) {
      if (out != nullptr) *out = status;
      getStatus(device, status, true);
      return true;
    }
    delay(20);
  }
  return false;
}

bool queryTransactionResult(
    Device &device,
    uint16_t originalTxid,
    TransactionResult &result) {
  uint8_t payload[2] {};
  writeBe16(payload, originalTxid);
  SpiResponse response {};
  if (!transactSuccess(device, CMD_GET_TXN_RESULT, allocateTxid(device),
                       payload, sizeof(payload), response)) {
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
  if (result.resultLength != 0) {
    memcpy(result.resultData, &p[10], result.resultLength);
  }
  Serial.printf("%s TXN original=0x%04X state=%u cmd=0x%02X code=0x%04X len=%u\n",
                device.name, result.originalTxid, result.transactionState,
                result.originalCommand, result.resultCode, result.resultLength);
  return result.originalTxid == originalTxid;
}

bool waitTransactionFinal(
    Device &device,
    uint16_t originalTxid,
    TransactionResult &result,
    uint32_t timeoutMs) {
  const uint32_t started = millis();
  while (millis() - started < timeoutMs) {
    if (!queryTransactionResult(device, originalTxid, result)) return false;
    if (result.transactionState != TXN_ACCEPTED &&
        result.transactionState != TXN_RUNNING) {
      return true;
    }
    delay(20);
  }
  return false;
}

bool retireTransaction(Device &device, uint16_t originalTxid) {
  uint8_t payload[2] {};
  writeBe16(payload, originalTxid);
  SpiResponse response {};
  return transactSuccess(device, CMD_RETIRE_TXN_RESULT, allocateTxid(device),
                         payload, sizeof(payload), response) &&
         response.payloadLength == 0;
}

bool issueRetainedAndWait(
    Device &device,
    uint8_t command,
    const uint8_t *payload,
    uint16_t payloadLength,
    TransactionResult &result,
    uint32_t timeoutMs = 5000) {
  const uint16_t originalTxid = allocateTxid(device);
  SpiResponse response {};
  if (!transactSuccess(device, command, originalTxid,
                       payload, payloadLength, response)) {
    return false;
  }
  if (response.payloadLength != 0) return false;
  if (!waitTransactionFinal(device, originalTxid, result, timeoutMs)) return false;
  if (!retireTransaction(device, originalTxid)) return false;
  return result.originalCommand == command;
}

bool runSelfTest(Device &device, uint16_t mask) {
  uint8_t payload[4] {};
  writeBe16(payload, mask);
  TransactionResult result {};
  if (!issueRetainedAndWait(device, CMD_RUN_SELF_TEST, payload, sizeof(payload),
                            result, 8000)) {
    return false;
  }
  return result.transactionState == TXN_SUCCEEDED &&
         result.resultCode == ERR_OK &&
         result.resultLength == 2 &&
         readBe16(result.resultData) == mask;
}

void buildStagePayload(uint8_t payload[28]) {
  memset(payload, 0, 28);
  writeBe32(&payload[0], SESSION_ID);
  memcpy(&payload[4], SESSION_KEY, sizeof(SESSION_KEY));
  memcpy(&payload[20], NONCE_PREFIX, sizeof(NONCE_PREFIX));
}

bool stageSession(Device &device) {
  uint8_t payload[28] {};
  buildStagePayload(payload);
  SpiResponse response {};
  return transactSuccess(device, CMD_STAGE_SESSION, allocateTxid(device),
                         payload, sizeof(payload), response) &&
         response.payloadLength == 0;
}

bool commitSession(Device &device) {
  uint8_t payload[4] {};
  writeBe32(payload, SESSION_ID);
  TransactionResult result {};
  if (!issueRetainedAndWait(device, CMD_COMMIT_SESSION,
                            payload, sizeof(payload), result)) {
    return false;
  }
  return result.transactionState == TXN_SUCCEEDED &&
         result.resultCode == ERR_OK &&
         result.resultLength == 0;
}

bool clearP2Diagnostics() {
  uint8_t payload[4] {};
  writeBe32(payload, DIAG_ALL);
  SpiResponse response {};
  return transactSuccess(primer2, CMD_CLEAR_DIAGNOSTIC_COUNTERS,
                         allocateTxid(primer2), payload, sizeof(payload),
                         response) && response.payloadLength == 0;
}

bool getRxStatus(RxStatusInfo &status, bool verbose = true) {
  SpiResponse response {};
  if (!transactSuccess(primer2, CMD_GET_RX_STATUS, allocateTxid(primer2),
                       nullptr, 0, response)) {
    return false;
  }
  if (response.payloadLength != 16) return false;
  const uint8_t *p = &response.packet[8];
  status.rxState = p[0];
  status.authPending = p[1] != 0;
  status.acceptEnabled = p[2] != 0;
  status.consecutiveBadTags = p[3];
  status.activeSessionId = readBe32(&p[4]);
  status.lastAcceptedSequence = readBe64(&p[8]);
  if (verbose) {
    Serial.printf("P2 RX state=%u auth_pending=%u accept=%u bad_tags=%u ",
                  status.rxState, status.authPending, status.acceptEnabled,
                  status.consecutiveBadTags);
    Serial.printf("sid=0x%08lX last_seq=%llu\n",
                  static_cast<unsigned long>(status.activeSessionId),
                  static_cast<unsigned long long>(status.lastAcceptedSequence));
  }
  return true;
}

bool waitForAuthPending(uint64_t expectedSequence, uint32_t timeoutMs) {
  const uint32_t started = millis();
  while (millis() - started < timeoutMs) {
    RxStatusInfo status {};
    if (!getRxStatus(status, false)) return false;
    if (status.authPending && status.lastAcceptedSequence == expectedSequence) {
      getRxStatus(status, true);
      return true;
    }
    delay(20);
  }
  return false;
}

bool readAuthResult(AuthResult &result) {
  SpiResponse response {};
  if (!transactSuccess(primer2, CMD_READ_AUTH_RESULT, allocateTxid(primer2),
                       nullptr, 0, response)) {
    return false;
  }
  if (response.payloadLength != 38) return false;
  const uint8_t *p = &response.packet[8];
  result.sessionId = readBe32(&p[0]);
  result.sequence = readBe64(&p[4]);
  memcpy(result.plaintext, &p[12], sizeof(result.plaintext));
  result.status = readBe16(&p[36]);
  Serial.printf("P2 AUTH sid=0x%08lX seq=%llu status=0x%04X plaintext=",
                static_cast<unsigned long>(result.sessionId),
                static_cast<unsigned long long>(result.sequence), result.status);
  printHex(result.plaintext, sizeof(result.plaintext));
  return true;
}

bool verifyAuthResult(
    const AuthResult &result,
    uint64_t expectedSequence,
    const uint8_t expectedPlaintext[24]) {
  return result.sessionId == SESSION_ID &&
         result.sequence == expectedSequence &&
         result.status == ERR_OK &&
         memcmp(result.plaintext, expectedPlaintext, 24) == 0;
}

bool ackAuthResult(uint32_t sessionId, uint64_t sequence) {
  uint8_t payload[12] {};
  writeBe32(&payload[0], sessionId);
  writeBe64(&payload[4], sequence);
  SpiResponse response {};
  return transactSuccess(primer2, CMD_ACK_AUTH_RESULT, allocateTxid(primer2),
                         payload, sizeof(payload), response) &&
         response.payloadLength == 0;
}

bool expectWrongAckRejected(uint64_t sequence) {
  uint8_t payload[12] {};
  writeBe32(&payload[0], SESSION_ID ^ 1UL);
  writeBe64(&payload[4], sequence);
  return transactExpectedError(primer2, CMD_ACK_AUTH_RESULT,
                               payload, sizeof(payload), ERR_BAD_SESSION);
}

bool loadTelemetry(const uint8_t plaintext[24]) {
  uint8_t payload[32] {};
  payload[0] = 0x02;  // message type
  payload[1] = 0x00;
  payload[2] = 0x12;  // flags 0x1234
  payload[3] = 0x34;
  payload[4] = 0x33;  // source ID 0x3344
  payload[5] = 0x44;
  payload[6] = 0x00;
  payload[7] = 0x00;
  memcpy(&payload[8], plaintext, 24);
  SpiResponse response {};
  return transactSuccess(primer1, CMD_LOAD_TELEMETRY, allocateTxid(primer1),
                         payload, sizeof(payload), response) &&
         response.payloadLength == 0;
}

bool encryptAndSend(uint64_t expectedSequence) {
  TransactionResult result {};
  if (!issueRetainedAndWait(primer1, CMD_ENCRYPT_AND_SEND,
                            nullptr, 0, result, 5000)) {
    return false;
  }
  if (result.transactionState != TXN_SUCCEEDED ||
      result.resultCode != ERR_OK || result.resultLength != 14) {
    return false;
  }
  const uint32_t resultSessionId = readBe32(&result.resultData[0]);
  const uint64_t resultSequence = readBe64(&result.resultData[4]);
  const uint16_t bytesSent = readBe16(&result.resultData[12]);
  Serial.printf("P1 UART retained result sid=0x%08lX seq=%llu bytes=%u\n",
                static_cast<unsigned long>(resultSessionId),
                static_cast<unsigned long long>(resultSequence), bytesSent);
  delay(5);  // Preserve more than 1 ms inter-frame idle.
  return resultSessionId == SESSION_ID &&
         resultSequence == expectedSequence && bytesSent == 66;
}

bool provisionBoth() {
  digitalWrite(PIN_SECURE_ENABLE, LOW);
  delay(10);

  if (!stageSession(primer1) || !stageSession(primer2)) return false;

  StatusInfo p1Staged {};
  StatusInfo p2Staged {};
  if (!waitForSessionState(primer1, SESSION_STAGED, 1500, &p1Staged) ||
      !waitForSessionState(primer2, SESSION_STAGED, 1500, &p2Staged)) {
    return false;
  }
  if ((p1Staged.secureFlags & SECURE_SESSION_STAGED) == 0 ||
      (p2Staged.secureFlags & SECURE_SESSION_STAGED) == 0) {
    return false;
  }

  if (!commitSession(primer1) || !commitSession(primer2)) return false;

  StatusInfo p1Committed {};
  StatusInfo p2Committed {};
  if (!waitForSessionState(primer1, SESSION_COMMITTED_BLOCKED,
                           1500, &p1Committed) ||
      !waitForSessionState(primer2, SESSION_COMMITTED_BLOCKED,
                           1500, &p2Committed)) {
    return false;
  }
  if (p1Committed.sessionId != SESSION_ID ||
      p2Committed.sessionId != SESSION_ID) {
    return false;
  }

  digitalWrite(PIN_SECURE_ENABLE, HIGH);

  StatusInfo p1Active {};
  StatusInfo p2Active {};
  if (!waitForSessionState(primer1, SESSION_ACTIVE, 1500, &p1Active) ||
      !waitForSessionState(primer2, SESSION_ACTIVE, 1500, &p2Active)) {
    return false;
  }
  if (p1Active.sessionId != SESSION_ID || p2Active.sessionId != SESSION_ID ||
      (p1Active.secureFlags & SECURE_ENABLE) == 0 ||
      (p2Active.secureFlags & SECURE_ENABLE) == 0) {
    return false;
  }

  RxStatusInfo rx {};
  return getRxStatus(rx, true) && rx.acceptEnabled && !rx.authPending &&
         rx.activeSessionId == SESSION_ID && rx.lastAcceptedSequence == 0;
}

#include "P1P2Gate.hpp"
