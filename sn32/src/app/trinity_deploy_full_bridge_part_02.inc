    g_host_txn.result_length = result_length;
    memset(g_host_txn.result_data, 0, sizeof(g_host_txn.result_data));
    if (result_length != 0u && result != NULL)
        memcpy(g_host_txn.result_data, result, result_length);
    full_sync_legacy_status();
}

static void full_handle_run_self_test(const trinity_pc_frame_t *req) {
    trinity_error_code_t rc;
    uint8_t result[2];
    uint8_t target_mask;
    uint16_t test_mask;
    if (!request_length_is(req, 4u) ||
        req->payload[1] > (uint8_t)TRINITY_TEST_PROFILE_DIAGNOSTIC) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    target_mask = req->payload[0];
    test_mask = trinity_read_be16(&req->payload[2]);
    if (!managed_transaction_begin(req)) return;
    rc = trinity_controller_run_self_test(&g_controller, target_mask,
                                          test_mask, 8000u);
    trinity_write_be16(result, test_mask);
    managed_transaction_finish(rc, rc == TRINITY_OK ? result : NULL,
                               rc == TRINITY_OK ? sizeof(result) : 0u);
    (void)response_send();
}

static void full_handle_close_session(const trinity_pc_frame_t *req) {
    trinity_error_code_t rc;
    if (!request_length_is(req, 0u)) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    if (!managed_transaction_begin(req)) return;
    rc = trinity_controller_close_session(&g_controller, 20000u);
    managed_transaction_finish(rc, NULL, 0u);
    (void)response_send();
}

static void full_handle_zeroize(const trinity_pc_frame_t *req) {
    trinity_error_code_t rc;
    if (!request_length_is(req, 1u)) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    if (!managed_transaction_begin(req)) return;
    rc = trinity_controller_zeroize(&g_controller, req->payload[0], 20000u);
    if (req->payload[0] == TRINITY_ZEROIZE_ALL)
        trinity_deploy_crypto_zeroize(&g_crypto);
    managed_transaction_finish(rc, NULL, 0u);
    (void)response_send();
}

static void full_handle_send_telemetry(const trinity_pc_frame_t *req) {
    trinity_controller_auth_result_t result;
    trinity_error_code_t rc;
    uint8_t wire[38];
    if (!request_length_is(req, 32u)) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    if (!managed_transaction_begin(req)) return;
    rc = trinity_controller_send_telemetry(&g_controller, req->payload,
                                           2000u, &result);
    if (rc == TRINITY_OK) {
        trinity_write_be32(&wire[0], result.session_id);
        trinity_write_be64(&wire[4], result.sequence);
        memcpy(&wire[12], result.plaintext, sizeof(result.plaintext));
        trinity_write_be16(&wire[36], (uint16_t)result.status);
    }
    managed_transaction_finish(rc, rc == TRINITY_OK ? wire : NULL,
                               rc == TRINITY_OK ? sizeof(wire) : 0u);
