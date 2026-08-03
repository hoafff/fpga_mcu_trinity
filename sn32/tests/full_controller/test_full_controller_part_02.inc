static void mock_commit(void *context) {
    mock_bus_t *bus = context;
    bus->commit_toggles += 1u;
    bus->p1.session_state = TRINITY_SESSION_ACTIVE;
    bus->p2.session_state = TRINITY_SESSION_ACTIVE;
    bus->p1.secure_flags |= TRINITY_SECURE_ENABLE;
    bus->p2.secure_flags |= TRINITY_SECURE_ENABLE;
}

int main(void) {
    mock_bus_t bus;
    trinity_controller_t controller;
    trinity_controller_ops_t ops;
    trinity_controller_session_material_t session;
    trinity_controller_auth_result_t result;
    uint8_t telemetry[32];
    unsigned i;

    memset(&bus, 0, sizeof(bus));
    bus.p1.session_state = TRINITY_SESSION_SELF_TEST_REQUIRED;
    bus.p2.session_state = TRINITY_SESSION_SELF_TEST_REQUIRED;
    bus.p1.next_txid = 0x1100u;
    bus.p2.next_txid = 0x2200u;
    memset(&ops, 0, sizeof(ops));
    ops.context = &bus;
    ops.exchange = mock_exchange;
    ops.now_ms = mock_now;
    ops.progress = mock_progress;
    ops.session_commit_toggle = mock_commit;
    ops.tiny_fault_active = mock_tiny_fault;

    trinity_controller_init(&controller, &ops);
    assert(trinity_controller_probe_all(&controller) == TRINITY_OK);
    assert(trinity_controller_ready_mask(&controller) == 0x0Fu);
    assert(controller.state == TRINITY_SYSTEM_SELF_TEST_REQUIRED);

    assert(trinity_controller_run_self_test(&controller,
        TRINITY_READY_PRIMER1 | TRINITY_READY_PRIMER2,
        0x013Eu, 1000u) == TRINITY_OK);

    memset(&session, 0, sizeof(session));
    session.session_id = 0x11223344u;
    for (i = 0u; i < sizeof(session.key); ++i) session.key[i] = (uint8_t)i;
    for (i = 0u; i < sizeof(session.nonce_prefix); ++i)
        session.nonce_prefix[i] = (uint8_t)(0xA0u + i);
    assert(trinity_controller_activate_session(&controller, &session,
        TRINITY_MODE_KAT, 1000u) == TRINITY_OK);
    assert(controller.state == TRINITY_SYSTEM_ACTIVE);
    assert(bus.commit_toggles == 1u);

    memset(telemetry, 0, sizeof(telemetry));
    telemetry[0] = 2u;
    telemetry[2] = 0x12u; telemetry[3] = 0x34u;
    telemetry[4] = 0x33u; telemetry[5] = 0x44u;
    for (i = 0u; i < 24u; ++i) telemetry[8u + i] = (uint8_t)(i + 1u);
    assert(trinity_controller_send_telemetry(&controller, telemetry,
        1000u, &result) == TRINITY_OK);
    assert(result.valid && result.sequence == 1u);
    assert(memcmp(result.plaintext, &telemetry[8], 24u) == 0);
    bus.auth_pending = true; /* P2 must protect an unacknowledged result. */
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

    bus.tiny_fault = true;
    assert(trinity_controller_probe_all(&controller) == TRINITY_FAULT_LOCKED);
    assert((trinity_controller_fault_mask(&controller) & TRINITY_FAULT_TINY1P5) != 0u);

    puts("PASS: dual-endpoint probe, retained self-test, staged/committed activation");
    puts("PASS: direct P1->P2 telemetry authentication, ACK and pending-result protection");
    puts("PASS: zeroize clears local session/result state and Tiny fault is fail-closed");
    return 0;
}
