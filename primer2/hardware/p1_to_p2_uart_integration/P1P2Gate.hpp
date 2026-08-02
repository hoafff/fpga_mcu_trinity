#pragma once

bool testSequence1AndWrongAck() {
  if (!loadTelemetry(PLAINTEXT_SEQ1) || !encryptAndSend(1)) return false;
  if (!waitForAuthPending(1, 2500)) return false;

  AuthResult result {};
  if (!readAuthResult(result) ||
      !verifyAuthResult(result, 1, PLAINTEXT_SEQ1)) {
    return false;
  }

  if (!expectWrongAckRejected(1)) return false;
  RxStatusInfo pending {};
  if (!getRxStatus(pending, true) || !pending.authPending ||
      pending.lastAcceptedSequence != 1) {
    return false;
  }

  if (!ackAuthResult(SESSION_ID, 1)) return false;
  RxStatusInfo released {};
  return getRxStatus(released, true) && !released.authPending &&
         released.lastAcceptedSequence == 1;
}

bool testSequence2AndPendingProtection() {
  if (!loadTelemetry(PLAINTEXT_SEQ2) || !encryptAndSend(2)) return false;
  if (!waitForAuthPending(2, 2500)) return false;

  AuthResult firstRead {};
  if (!readAuthResult(firstRead) ||
      !verifyAuthResult(firstRead, 2, PLAINTEXT_SEQ2)) {
    return false;
  }

  // P1 sends sequence 3 while P2 still owns the authenticated sequence-2
  // result. P2 must drop the new frame and keep sequence 2 byte-exact.
  if (!loadTelemetry(PLAINTEXT_PENDING_PROBE) || !encryptAndSend(3)) {
    return false;
  }
  StatusInfo dropStatus {};
  if (!waitForLastError(primer2, ERR_RESULT_PENDING_DROP,
                        2000, &dropStatus)) {
    return false;
  }

  RxStatusInfo pending {};
  if (!getRxStatus(pending, true) || !pending.authPending ||
      pending.lastAcceptedSequence != 2 || pending.consecutiveBadTags != 0) {
    return false;
  }

  AuthResult secondRead {};
  if (!readAuthResult(secondRead) ||
      !verifyAuthResult(secondRead, 2, PLAINTEXT_SEQ2)) {
    return false;
  }

  if (!ackAuthResult(SESSION_ID, 2)) return false;
  RxStatusInfo released {};
  return getRxStatus(released, true) && !released.authPending &&
         released.lastAcceptedSequence == 2;
}

bool verifyFinalState() {
  StatusInfo p1 {};
  StatusInfo p2 {};
  RxStatusInfo rx {};
  if (!getStatus(primer1, p1, true) ||
      !getStatus(primer2, p2, true) ||
      !getRxStatus(rx, true)) {
    return false;
  }

  const uint32_t forbiddenP2Diagnostics =
      DIAG_BAD_TAG | DIAG_REPLAY_OR_STALE | DIAG_FRAME_ERROR;

  return p1.sessionState == SESSION_ACTIVE &&
         p2.sessionState == SESSION_ACTIVE &&
         p1.sessionId == SESSION_ID && p2.sessionId == SESSION_ID &&
         (p1.pendingFlags & PENDING_SIDE_EFFECT_RESULT) == 0 &&
         (p2.pendingFlags & PENDING_AUTHENTICATED_RESULT) == 0 &&
         (p1.secureFlags & SECURE_FAULT_LOCKED) == 0 &&
         (p2.secureFlags & SECURE_FAULT_LOCKED) == 0 &&
         p2.lastError == ERR_RESULT_PENDING_DROP &&
         (p2.diagnosticSummary & DIAG_RESULT_PENDING_DROP) != 0 &&
         (p2.diagnosticSummary & forbiddenP2Diagnostics) == 0 &&
         rx.acceptEnabled && !rx.authPending &&
         rx.lastAcceptedSequence == 2 && rx.consecutiveBadTags == 0;
}

bool runGate() {
  printDivider("P1 -> P2 DIRECT UART INTEGRATION");
  Serial.println("GPIO7 remains INPUT/high-impedance; P1 is the only UART driver.");

  if (!requireStep("P1 GET_INFO target/build/capabilities", getInfo(primer1))) return false;
  if (!requireStep("P2 GET_INFO target/build/capabilities", getInfo(primer2))) return false;

  StatusInfo p1Initial {};
  StatusInfo p2Initial {};
  const bool initialStates =
      getStatus(primer1, p1Initial, true) &&
      getStatus(primer2, p2Initial, true) &&
      p1Initial.sessionState == SESSION_SELF_TEST_REQUIRED &&
      p2Initial.sessionState == SESSION_SELF_TEST_REQUIRED &&
      digitalRead(PIN_SECURE_ENABLE) == LOW;
  if (!requireStep("Both targets initially fail-closed", initialStates)) return false;

  if (!requireStep("P1 retained self-test", runSelfTest(primer1, P1_SELF_TEST_MASK))) {
    return false;
  }
  if (!requireStep("P2 retained self-test", runSelfTest(primer2, P2_SELF_TEST_MASK))) {
    return false;
  }

  StatusInfo p1Ready {};
  StatusInfo p2Ready {};
  const bool bothReady =
      waitForSessionState(primer1, SESSION_READY_NO_SESSION, 2500, &p1Ready) &&
      waitForSessionState(primer2, SESSION_READY_NO_SESSION, 2500, &p2Ready) &&
      (p1Ready.secureFlags & SECURE_SELF_TEST_PASS) != 0 &&
      (p2Ready.secureFlags & SECURE_SELF_TEST_PASS) != 0;
  if (!requireStep("Both self-tests -> READY_NO_SESSION", bothReady)) return false;
  if (!requireStep("P2 diagnostic counters cleared", clearP2Diagnostics())) return false;

  if (!requireStep("Same session staged/committed/activated", provisionBoth())) return false;
  if (!requireStep("Sequence 1 byte-exact + wrong ACK held", testSequence1AndWrongAck())) {
    return false;
  }
  if (!requireStep("Sequence 2 byte-exact + pending protection",
                   testSequence2AndPendingProtection())) {
    return false;
  }
  if (!requireStep("Final active/fault/diagnostic state", verifyFinalState())) return false;

  return true;
}

void printFinalSummary(bool overall) {
  printDivider("FINAL SUMMARY");
  Serial.printf("PASS count = %u\n", passCount);
  Serial.printf("FAIL count = %u\n", failCount);
  Serial.printf("GPIO7 mode = INPUT/high-impedance (never changed)\n");
  Serial.printf("UART monitor level = %d\n", digitalRead(PIN_UART_MONITOR));
  Serial.printf("OVERALL = %s\n", overall ? "PASS" : "FAIL");
  if (overall) {
    Serial.println("P1 -> P2 direct UART integration: PASS");
    Serial.println("SN32 integration: NOT CLAIMED");
    Serial.println("Tiny integration: NOT CLAIMED");
    Serial.println("Full-system qualification: NOT CLAIMED");
  }
}

void setup() {
  // Establish safe levels before USB serial startup and before SPI.begin().
  pinMode(PIN_P1_CS_N, OUTPUT);
  pinMode(PIN_P2_CS_N, OUTPUT);
  deselectBoth();

  pinMode(PIN_SECURE_ENABLE, OUTPUT);
  digitalWrite(PIN_SECURE_ENABLE, LOW);

  pinMode(PIN_P1_IRQ_N, INPUT);
  pinMode(PIN_P2_IRQ_N, INPUT);
  pinMode(PIN_UART_MONITOR, INPUT);  // Mandatory: never changed to OUTPUT.

  Serial.begin(115200);
  delay(1500);

  SPI.begin(PIN_SPI_SCK, PIN_SPI_MISO, PIN_SPI_MOSI, -1);
  Serial.println();
  Serial.println("Primer #1 -> Primer #2 UART integration harness started");
  Serial.printf("CS P1=%d P2=%d, secure=%d, UART monitor=%d\n",
                digitalRead(PIN_P1_CS_N), digitalRead(PIN_P2_CS_N),
                digitalRead(PIN_SECURE_ENABLE), digitalRead(PIN_UART_MONITOR));

  delay(2000);
  if (!drainStartupMailbox(primer1) || !drainStartupMailbox(primer2)) {
    ++failCount;
    testAborted = true;
    printFinalSummary(false);
    return;
  }

  const bool overall = runGate();
  printFinalSummary(overall);
}

void loop() {
  static uint32_t lastReport = 0;
  const uint32_t now = millis();
  if (now - lastReport >= 1000) {
    Serial.printf("monitor secure=%d P1_irq_n=%d P2_irq_n=%d uart=%d aborted=%d\n",
                  digitalRead(PIN_SECURE_ENABLE), digitalRead(PIN_P1_IRQ_N),
                  digitalRead(PIN_P2_IRQ_N), digitalRead(PIN_UART_MONITOR),
                  testAborted ? 1 : 0);
    lastReport = now;
  }
}
