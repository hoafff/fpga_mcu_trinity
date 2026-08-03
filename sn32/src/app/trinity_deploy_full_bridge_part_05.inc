static bool full_diagnostic_state_ready(void) {
    return g_controller.state == TRINITY_SYSTEM_READY_NO_KEYPAIR ||
           g_controller.state == TRINITY_SYSTEM_READY_NO_SESSION;
}

static trinity_error_code_t full_run_self_test_iterations(
    uint8_t target_mask,
    uint16_t test_mask,
    uint16_t iterations) {
    uint16_t index;
    trinity_error_code_t rc = TRINITY_OK;
    for (index = 0u; index < iterations; ++index) {
        rc = trinity_controller_run_self_test(&g_controller, target_mask,
                                              test_mask, 8000u);
        if (rc != TRINITY_OK) break;
        progress();
    }
    return rc;
}

static void full_handle_diagnostic_test(const trinity_pc_frame_t *req,
                                        bool ascon_test) {
    uint8_t result[6];
    uint16_t iterations;
    uint16_t test_mask;
    uint8_t target_mask;
    trinity_error_code_t rc;
    if (!request_length_is(req, 4u) || req->payload[1] != 0u ||
        req->payload[0] > (uint8_t)TRINITY_TEST_PROFILE_DIAGNOSTIC) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    iterations = trinity_read_be16(&req->payload[2]);
    if (iterations == 0u || iterations > 1000u) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, iterations);
        return;
    }
    if (!full_diagnostic_state_ready()) {
        response_error(req, TRINITY_BAD_STATE, TRINITY_SOURCE_SN32, 0u);
        return;
    }
    test_mask = ascon_test
                    ? TRINITY_TEST_ASCON
                    : (TRINITY_TEST_NTT | TRINITY_TEST_INTT |
                       TRINITY_TEST_BASEMUL);
    target_mask = ascon_test
                      ? (TRINITY_READY_PRIMER1 | TRINITY_READY_PRIMER2)
                      : TRINITY_READY_PRIMER1;
    if (!managed_transaction_begin(req)) return;
    rc = full_run_self_test_iterations(target_mask, test_mask, iterations);
    result[0] = req->payload[0];
    result[1] = target_mask;
    trinity_write_be16(&result[2], iterations);
    trinity_write_be16(&result[4], test_mask);
    managed_transaction_finish(rc, rc == TRINITY_OK ? result : NULL,
                               rc == TRINITY_OK ? sizeof(result) : 0u);
    managed_transaction_respond(req);
}

static void full_handle_ntt_test(const trinity_pc_frame_t *req) {
    full_handle_diagnostic_test(req, false);
}

static void full_handle_ascon_test(const trinity_pc_frame_t *req) {
    full_handle_diagnostic_test(req, true);
}

static void full_build_benchmark_telemetry(uint32_t iteration,
                                           uint8_t payload[32]) {
    uint8_t index;
    memset(payload, 0, 32u);
    payload[0] = 0x02u;
    payload[2] = 0xBEu;
    payload[3] = 0xEFu;
    payload[4] = 0x53u;
    payload[5] = 0x4Eu;
    for (index = 0u; index < 24u; ++index)
        payload[8u + index] = (uint8_t)(iteration + index);
}
