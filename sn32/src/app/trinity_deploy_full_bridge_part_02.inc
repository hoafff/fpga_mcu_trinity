    g_host_txn.result_length = result_length;
    memset(g_host_txn.result_data, 0, sizeof(g_host_txn.result_data));
    if (result_length != 0u && result != NULL)
        memcpy(g_host_txn.result_data, result, result_length);

    full_sync_legacy_status();
    g_host_txn.result_system_state = system_state();
    g_host_txn.result_related_target_txid = g_host_txn.target_txid;
    if (rc == TRINITY_OK) {
        g_host_txn.result_source = (uint8_t)TRINITY_SOURCE_SN32;
    } else if (g_controller.last_error == rc) {
        g_host_txn.result_source = (uint8_t)g_controller.last_error_source;
        set_error(rc, g_controller.last_error_source,
                  g_controller.last_error_detail);
    } else if (g_error.code == rc) {
        g_host_txn.result_source = (uint8_t)g_error.source;
    } else {
        g_host_txn.result_source = (uint8_t)TRINITY_SOURCE_SN32;
        set_error(rc, TRINITY_SOURCE_SN32, g_host_txn.target_txid);
    }
}

static trinity_error_code_t full_sn32_self_test(uint16_t test_mask) {
    static const uint8_t crc_vector[9] = {
        '1','2','3','4','5','6','7','8','9'
    };
    uint8_t scratch[16];
    uint8_t index;

    if ((test_mask & TRINITY_TEST_PROTOCOL) != 0u &&
        trinity_crc16_ccitt_false(crc_vector, sizeof(crc_vector)) != 0x29B1u)
        return TRINITY_SELF_TEST_FAILED;

    if ((test_mask & TRINITY_TEST_MEMORY) != 0u) {
        for (index = 0u; index < sizeof(scratch); ++index)
            scratch[index] = (uint8_t)(0xA5u ^ index);
        for (index = 0u; index < sizeof(scratch); ++index) {
            if (scratch[index] != (uint8_t)(0xA5u ^ index)) {
                trinity_controller_secure_clear(scratch, sizeof(scratch));
                return TRINITY_SELF_TEST_FAILED;
            }
        }
    }

    if ((test_mask & TRINITY_TEST_ZEROIZE) != 0u) {
        memset(scratch, 0xA5, sizeof(scratch));
        trinity_controller_secure_clear(scratch, sizeof(scratch));
        for (index = 0u; index < sizeof(scratch); ++index) {
            if (scratch[index] != 0u) return TRINITY_SELF_TEST_FAILED;
        }
    }

    if ((test_mask & TRINITY_TEST_SESSION) != 0u) {
        if (g_controller.state == TRINITY_SYSTEM_ACTIVE) {
            if (!g_session_commit_level ||
                !g_controller.session_material_valid)
                return TRINITY_SELF_TEST_FAILED;
        } else if (g_session_commit_level) {
            return TRINITY_SELF_TEST_FAILED;
        }
    }

    if ((test_mask & TRINITY_TEST_HEARTBEAT) != 0u &&
        (g_fault || (uint32_t)(g_ms - g_progress_ms) > PROGRESS_LEASE_MS))
        return TRINITY_HEARTBEAT_TIMEOUT;

    if (guard_check() != FPST_P010_VIOLATION_NONE)
        return TRINITY_FAULT_LOCKED;
    trinity_controller_secure_clear(scratch, sizeof(scratch));
    return TRINITY_OK;
}

static trinity_error_code_t full_tiny_self_test(uint16_t test_mask) {
    (void)test_mask;
#if FPST_SN32F407_HARNESS_VERIFIED
    return full_tiny_fault_active(NULL) ? TRINITY_FAULT_LOCKED : TRINITY_OK;
#else
    return TRINITY_NOT_SUPPORTED;
#endif
}

static void full_handle_run_self_test(const trinity_pc_frame_t *req) {
    const uint8_t allowed_targets =
        TRINITY_READY_SN32 | TRINITY_READY_PRIMER1 |
        TRINITY_READY_PRIMER2 | TRINITY_READY_TINY1P5;
    trinity_error_code_t rc = TRINITY_OK;
    uint8_t result[2];
    uint8_t target_mask;
    uint8_t primer_mask;
    uint16_t test_mask;
    if (!request_length_is(req, 4u) ||
        req->payload[1] > (uint8_t)TRINITY_TEST_PROFILE_DIAGNOSTIC) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    target_mask = req->payload[0];
    test_mask = trinity_read_be16(&req->payload[2]);
    if (target_mask == 0u || (target_mask & (uint8_t)~allowed_targets) != 0u ||
        test_mask == 0u) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, target_mask);
        return;
    }
    if (!managed_transaction_begin(req)) return;

    if ((target_mask & TRINITY_READY_SN32) != 0u)
        rc = full_sn32_self_test(test_mask);
    if (rc == TRINITY_OK &&
        (target_mask & TRINITY_READY_TINY1P5) != 0u)
        rc = full_tiny_self_test(test_mask);
    primer_mask = target_mask &
                  (TRINITY_READY_PRIMER1 | TRINITY_READY_PRIMER2);
    if (rc == TRINITY_OK && primer_mask != 0u)
        rc = trinity_controller_run_self_test(&g_controller, primer_mask,
                                              test_mask, 8000u);

    trinity_write_be16(result, test_mask);
    managed_transaction_finish(rc, rc == TRINITY_OK ? result : NULL,
                               rc == TRINITY_OK ? sizeof(result) : 0u);
    managed_transaction_respond(req);
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
    managed_transaction_respond(req);
}

static void full_handle_zeroize(const trinity_pc_frame_t *req) {
    const bool emergency_all =
        request_length_is(req, 1u) &&
        req->payload[0] == TRINITY_ZEROIZE_ALL;
    trinity_error_code_t rc;
    if (!request_length_is(req, 1u)) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }

    /*
     * A full zeroize is the fail-safe escape hatch. A previously completed
     * failed managed command must never block it with RESULT_PENDING. The old
     * retained host result is discarded locally before the zeroize transaction
     * is admitted. No running command can be preempted here because PC commands
     * execute synchronously; progress() only drains UART bytes.
     */
    if (emergency_all && g_host_txn.valid) {
        memset(&g_host_txn, 0, sizeof(g_host_txn));
        g_active_host_txid = 0u;
    }
    if (!managed_transaction_begin(req)) return;

    rc = trinity_controller_zeroize(&g_controller, req->payload[0], 20000u);
    if (req->payload[0] == TRINITY_ZEROIZE_ALL)
        trinity_deploy_crypto_zeroize(&g_crypto);

    if (rc == TRINITY_OK && emergency_all) {
        g_fault = false;
        g_tiny_fault_contained = false;
        g_error.code = TRINITY_OK;
        g_error.source = TRINITY_SOURCE_SN32;
        g_error.detail = 0u;
        g_controller.last_error = TRINITY_OK;
        g_controller.last_error_source = TRINITY_SOURCE_SN32;
        g_controller.last_error_detail = 0u;
        g_controller.state = TRINITY_SYSTEM_READY_NO_SESSION;
        g_trinity_deploy_last_error = TRINITY_OK;
        g_trinity_deploy_marker = DEPLOY_MARKER_OK;
    }

    managed_transaction_finish(rc, NULL, 0u);
    managed_transaction_respond(req);
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
