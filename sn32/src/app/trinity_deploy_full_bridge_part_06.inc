static void full_handle_benchmark(const trinity_pc_frame_t *req) {
    const uint16_t unsupported =
        TRINITY_BENCH_MLKEM_KEYGEN | TRINITY_BENCH_MLKEM_ENCAPS |
        TRINITY_BENCH_MLKEM_DECAPS;
    uint8_t result[16];
    uint8_t telemetry[32];
    trinity_controller_auth_result_t auth;
    uint16_t operation_mask;
    uint32_t iterations;
    uint32_t index;
    uint32_t started;
    trinity_error_code_t rc = TRINITY_OK;
    bool needs_self_test;
    bool needs_payload;

    if (!request_length_is(req, 8u) || req->payload[1] != 0u) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    operation_mask = trinity_read_be16(&req->payload[2]);
    iterations = trinity_read_be32(&req->payload[4]);
    if (operation_mask == 0u || iterations == 0u || iterations > 1000u) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, operation_mask);
        return;
    }
    if ((operation_mask & unsupported) != 0u) {
        response_error(req, TRINITY_NOT_SUPPORTED,
                       TRINITY_SOURCE_SN32, operation_mask & unsupported);
        return;
    }
    needs_self_test = (operation_mask &
        (TRINITY_BENCH_NTT | TRINITY_BENCH_INTT | TRINITY_BENCH_BASEMUL |
         TRINITY_BENCH_ASCON_ENCRYPT | TRINITY_BENCH_ASCON_DECRYPT)) != 0u;
    needs_payload = (operation_mask &
        (TRINITY_BENCH_PAYLOAD_UART | TRINITY_BENCH_END_TO_END)) != 0u;
    if (needs_self_test && !full_diagnostic_state_ready()) {
        response_error(req, TRINITY_BAD_STATE, TRINITY_SOURCE_SN32, 0u);
        return;
    }
    if (needs_payload && g_controller.state != TRINITY_SYSTEM_ACTIVE) {
        response_error(req, TRINITY_BAD_STATE, TRINITY_SOURCE_SN32, 0u);
        return;
    }
    if (!managed_transaction_begin(req)) return;
    started = g_ms;
    for (index = 0u; index < iterations && rc == TRINITY_OK; ++index) {
        if ((operation_mask &
             (TRINITY_BENCH_NTT | TRINITY_BENCH_INTT |
              TRINITY_BENCH_BASEMUL)) != 0u) {
            rc = trinity_controller_run_self_test(
                &g_controller, TRINITY_READY_PRIMER1,
                TRINITY_TEST_NTT | TRINITY_TEST_INTT | TRINITY_TEST_BASEMUL,
                8000u);
        }
        if (rc == TRINITY_OK && (operation_mask &
            (TRINITY_BENCH_ASCON_ENCRYPT |
             TRINITY_BENCH_ASCON_DECRYPT)) != 0u) {
            rc = trinity_controller_run_self_test(
                &g_controller,
                TRINITY_READY_PRIMER1 | TRINITY_READY_PRIMER2,
                TRINITY_TEST_ASCON, 8000u);
        }
        if (rc == TRINITY_OK &&
            (operation_mask & TRINITY_BENCH_SPI) != 0u) {
            if ((req->payload[0] & TRINITY_READY_PRIMER1) != 0u)
                rc = trinity_controller_transport_stress(&g_controller, 2u, 1u);
            if (rc == TRINITY_OK &&
                (req->payload[0] & TRINITY_READY_PRIMER2) != 0u)
                rc = trinity_controller_transport_stress(&g_controller, 3u, 1u);
        }
        if (rc == TRINITY_OK && needs_payload) {
            full_build_benchmark_telemetry(index, telemetry);
            rc = trinity_controller_send_telemetry(&g_controller, telemetry,
                                                   2000u, &auth);
        }
        progress();
    }
    trinity_write_be16(&result[0], operation_mask);
    trinity_write_be16(&result[2], req->payload[0]);
    trinity_write_be32(&result[4], index);
    trinity_write_be32(&result[8], (uint32_t)(g_ms - started));
    trinity_write_be32(&result[12], (uint32_t)g_controller.current_sequence);
    managed_transaction_finish(rc, result, sizeof(result));
    (void)response_send();
}

static void full_handle_run_demo(const trinity_pc_frame_t *req) {
    trinity_controller_session_material_t material;
    trinity_controller_auth_result_t auth;
    uint8_t telemetry[32];
    uint8_t seed_input[36];
    uint8_t result[14];
    uint16_t frame_count;
    uint16_t index;
    trinity_error_code_t rc = TRINITY_OK;

    if (!request_length_is(req, 40u) || req->payload[1] != 0u ||
        req->payload[0] > 1u) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    if (req->payload[0] == 1u) {
        response_error(req, TRINITY_NOT_SUPPORTED,
                       TRINITY_SOURCE_SN32, 0u);
        return;
    }
    frame_count = trinity_read_be16(&req->payload[2]);
    if (frame_count == 0u) frame_count = 64u;
    if (frame_count > 64u ||
        (g_controller.state != TRINITY_SYSTEM_READY_NO_KEYPAIR &&
         g_controller.state != TRINITY_SYSTEM_READY_NO_SESSION &&
         g_controller.state != TRINITY_SYSTEM_ACTIVE)) {
        response_error(req, frame_count > 64u ? TRINITY_BAD_LENGTH
                                               : TRINITY_BAD_STATE,
                       TRINITY_SOURCE_SN32, frame_count);
        return;
    }
    if (!managed_transaction_begin(req)) return;

    if (!g_crypto.keypair_valid) {
        rc = trinity_deploy_crypto_generate_keypair(
            &g_crypto, 1u, &req->payload[8]);
        if (rc == TRINITY_OK)
            g_controller.state = TRINITY_SYSTEM_READY_NO_SESSION;
    }
    if (rc == TRINITY_OK && g_controller.state != TRINITY_SYSTEM_ACTIVE) {
        memset(&material, 0, sizeof(material));
        rc = trinity_deploy_crypto_create_session(
            &g_crypto, 1u, &req->payload[8], &material);
        if (rc == TRINITY_OK)
            rc = trinity_controller_activate_session(
                &g_controller, &material, TRINITY_MODE_DEMO_DETERMINISTIC,
                20000u);
        trinity_controller_secure_clear(&material, sizeof(material));
    }

    memcpy(seed_input, &req->payload[8], 32u);
    for (index = 0u; index < frame_count && rc == TRINITY_OK; ++index) {
        memset(telemetry, 0, sizeof(telemetry));
        telemetry[0] = 0x02u;
        telemetry[2] = req->payload[6];
        telemetry[3] = req->payload[7];
        telemetry[4] = req->payload[4];
        telemetry[5] = req->payload[5];
        trinity_write_be32(&seed_input[32], index);
        trinity_shake256(&telemetry[8], 24u, seed_input, sizeof(seed_input));
        rc = trinity_controller_send_telemetry(&g_controller, telemetry,
                                               2000u, &auth);
        progress();
    }
    trinity_controller_secure_clear(seed_input, sizeof(seed_input));
    trinity_write_be16(&result[0], index);
    trinity_write_be32(&result[2],
                       g_controller.session_material_valid
                           ? g_controller.session.session_id : 0u);
    trinity_write_be64(&result[6], g_controller.current_sequence);
    managed_transaction_finish(rc, result, sizeof(result));
    (void)response_send();
}
