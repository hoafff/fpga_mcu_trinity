static void mock_commit_low(void *context) {
    mock_bus_t *bus = context;
    bus->commit_level = false;
    bus->commit_low_calls += 1u;
}

static void mock_commit_high(void *context) {
    mock_bus_t *bus = context;
    assert(!bus->commit_level);
    bus->commit_level = true;
    bus->commit_high_calls += 1u;
    if (bus->activate_on_commit) {
        bus->p1.session_state = TRINITY_SESSION_ACTIVE;
        bus->p2.session_state = TRINITY_SESSION_ACTIVE;
        bus->p1.secure_flags |= TRINITY_SECURE_ENABLE;
        bus->p2.secure_flags |= TRINITY_SECURE_ENABLE;
    }
}

int main(void) {
    mock_bus_t bus;
    trinity_controller_t controller;
    trinity_controller_ops_t ops;
    trinity_controller_session_material_t session;
    trinity_controller_auth_result_t result;
    uint8_t telemetry[32];
    uint32_t expected_failure_detail;
    unsigned i;

    memset(&bus, 0, sizeof(bus));
    bus.commit_level = true;
    bus.activate_on_commit = true;
    bus.retained_not_ready_reads = 3u;
    bus.p1.session_state = TRINITY_SESSION_SELF_TEST_REQUIRED;
    bus.p2.session_state = TRINITY_SESSION_SELF_TEST_REQUIRED;
    bus.p1.next_txid = 0x1100u;
    bus.p2.next_txid = 0x2200u;
    memset(&ops, 0, sizeof(ops));
    ops.context = &bus;
    ops.exchange = mock_exchange;
    ops.now_ms = mock_now;
    ops.progress = mock_progress;
    ops.session_commit_low = mock_commit_low;
    ops.session_commit_high = mock_commit_high;
    ops.tiny_fault_active = mock_tiny_fault;

    trinity_controller_init(&controller, &ops);
    assert(trinity_controller_probe_all(&controller) == TRINITY_OK);
    assert(trinity_controller_ready_mask(&controller) == 0x0Fu);
    assert(controller.state == TRINITY_SYSTEM_SELF_TEST_REQUIRED);

    bus.fail_get_status_target = TRINITY_TARGET_PRIMER1;
    bus.fail_get_status_count = 1u;
    assert(trinity_controller_refresh_status(&controller) ==
           TRINITY_TRANSACTION_CONFLICT);
    assert(controller.last_error == TRINITY_TRANSACTION_CONFLICT);
    assert((trinity_controller_fault_mask(&controller) &
            TRINITY_FAULT_TRANSPORT) != 0u);
    assert(trinity_controller_refresh_status(&controller) == TRINITY_OK);
    assert(controller.last_error == TRINITY_OK);
    assert((trinity_controller_fault_mask(&controller) &
            TRINITY_FAULT_TRANSPORT) == 0u);
    assert(trinity_controller_ready_mask(&controller) == 0x0Fu);
    controller.last_error = TRINITY_BAD_LENGTH;
    assert((trinity_controller_fault_mask(&controller) &
            TRINITY_FAULT_TRANSPORT) != 0u);
    controller.last_error = TRINITY_OK;

    assert(trinity_controller_run_self_test(&controller,
        TRINITY_READY_PRIMER1 | TRINITY_READY_PRIMER2,
        0x013Eu, 1000u) == TRINITY_OK);
    assert(controller.last_error == TRINITY_OK);
    assert(bus.retained_not_ready_reads == 0u);

    memset(&session, 0, sizeof(session));
    session.session_id = 0x11223344u;
    for (i = 0u; i < sizeof(session.key); ++i) session.key[i] = (uint8_t)i;
    for (i = 0u; i < sizeof(session.nonce_prefix); ++i)
        session.nonce_prefix[i] = (uint8_t)(0xA0u + i);
    assert(trinity_controller_activate_session(&controller, &session,
        TRINITY_MODE_KAT, 1000u) == TRINITY_OK);
    assert(controller.state == TRINITY_SYSTEM_ACTIVE);
    assert(bus.commit_low_calls == 1u);
    assert(bus.commit_high_calls == 1u);
    assert(bus.commit_level);

    memset(telemetry, 0, sizeof(telemetry));
    telemetry[0] = 2u;
    telemetry[2] = 0x12u; telemetry[3] = 0x34u;
    telemetry[4] = 0x33u; telemetry[5] = 0x44u;
    for (i = 0u; i < 24u; ++i) telemetry[8u + i] = (uint8_t)(i + 1u);
    assert(trinity_controller_send_telemetry(&controller, telemetry,
        1000u, &result) == TRINITY_OK);
    assert(result.valid && result.sequence == 1u);
    assert(memcmp(result.plaintext, &telemetry[8], 24u) == 0);
    bus.auth_pending = true;
    assert(trinity_controller_send_telemetry(&controller, telemetry,
        1000u, &result) == TRINITY_RESULT_PENDING);
    bus.auth_pending = false;
    telemetry[8] = 0xA5u;
    assert(trinity_controller_send_telemetry(&controller, telemetry,
        1000u, &result) == TRINITY_OK);
    assert(result.sequence == 2u && result.plaintext[0] == 0xA5u);

    assert(trinity_controller_transport_stress(&controller, 2u, 8u) == TRINITY_OK);
    assert(trinity_controller_transport_stress(&controller, 3u, 8u) == TRINITY_OK);
    assert(trinity_controller_transport_stress(&controller, 4u, 1u) == TRINITY_NOT_SUPPORTED);

    assert(trinity_controller_zeroize(&controller, TRINITY_ZEROIZE_ALL,
        1000u) == TRINITY_OK);
    assert(!controller.session_material_valid);
    assert(!controller.last_result.valid);
    assert(controller.current_sequence == 0u);
    assert(!bus.commit_level);
    assert(bus.commit_low_calls >= 2u);

    /* Re-enter READY_NO_SESSION and prove a failed enable edge keeps the exact
     * pre-zeroize endpoint snapshot in last_error_detail. */
    bus.activate_on_commit = false;
    bus.p1.session_state = TRINITY_SESSION_READY_NO_SESSION;
    bus.p2.session_state = TRINITY_SESSION_READY_NO_SESSION;
    bus.p1.secure_flags = TRINITY_SECURE_SELF_TEST_PASS;
    bus.p2.secure_flags = TRINITY_SECURE_SELF_TEST_PASS;
    controller.p1.session_state = TRINITY_SESSION_READY_NO_SESSION;
    controller.p2.session_state = TRINITY_SESSION_READY_NO_SESSION;
    controller.p1.secure_flags = TRINITY_SECURE_SELF_TEST_PASS;
    controller.p2.secure_flags = TRINITY_SECURE_SELF_TEST_PASS;
    controller.state = TRINITY_SYSTEM_READY_NO_SESSION;
    session.session_id = 0x55667788u;
    assert(trinity_controller_activate_session(&controller, &session,
        TRINITY_MODE_KAT, 1000u) == TRINITY_SESSION_COMMIT_FAILED);
    expected_failure_detail = TRINITY_SESSION_FAILURE_DETAIL_PACK(
        TRINITY_SESSION_FAILURE_PHASE_ACTIVE_WAIT,
        TRINITY_SESSION_COMMITTED_BLOCKED,
        TRINITY_SESSION_COMMITTED_BLOCKED,
        TRINITY_SECURE_SELF_TEST_PASS | TRINITY_SECURE_SESSION_STAGED,
        TRINITY_SECURE_SELF_TEST_PASS | TRINITY_SECURE_SESSION_STAGED);
    assert(controller.last_error == TRINITY_SESSION_COMMIT_FAILED);
    assert(controller.last_error_detail == expected_failure_detail);
    assert(controller.state == TRINITY_SYSTEM_FAULT_LOCKED);

    bus.tiny_fault = true;
    assert(trinity_controller_probe_all(&controller) == TRINITY_FAULT_LOCKED);
    assert((trinity_controller_fault_mask(&controller) & TRINITY_FAULT_TINY1P5) != 0u);

    puts("PASS: delayed retained-result polling does not latch a false controller error");
    puts("PASS: a complete refresh clears the active transport fault");
    puts("PASS: dual-endpoint probe, retained self-test, staged/committed activation");
    puts("PASS: repeatable LOW>=2ms to HIGH commit edge and zeroize deassertion");
    puts("PASS: failed activation retains pre-zeroize P1/P2 state and secure flags");
    puts("PASS: direct P1->P2 telemetry authentication, ACK and pending-result protection");
    puts("PASS: zeroize clears local session/result state and Tiny fault is fail-closed");
    return 0;
}
