static void full_handle_generate_keypair(const trinity_pc_frame_t *req) {
    trinity_error_code_t rc;
    uint8_t digest[32];
    if (!request_length_is(req, 33u) || req->payload[0] > 1u) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    if (g_controller.state != TRINITY_SYSTEM_READY_NO_KEYPAIR &&
        g_controller.state != TRINITY_SYSTEM_READY_NO_SESSION) {
        response_error(req, TRINITY_BAD_STATE, TRINITY_SOURCE_SN32, 0u);
        return;
    }
    if (!managed_transaction_begin(req)) return;
    rc = trinity_deploy_crypto_generate_keypair(
        &g_crypto, req->payload[0], &req->payload[1]);
    if (rc == TRINITY_OK)
        rc = trinity_deploy_crypto_public_key_hash(&g_crypto, digest);
    if (rc == TRINITY_OK)
        g_controller.state = TRINITY_SYSTEM_READY_NO_SESSION;
    managed_transaction_finish(rc, rc == TRINITY_OK ? digest : NULL,
                               rc == TRINITY_OK ? sizeof(digest) : 0u);
    trinity_controller_secure_clear(digest, sizeof(digest));
    (void)response_send();
}

static void full_handle_create_session(const trinity_pc_frame_t *req) {
    trinity_controller_session_material_t material;
    trinity_error_code_t rc;
    trinity_mode_t mode;
    uint8_t result[12];
    if (!request_length_is(req, 33u) || req->payload[0] > 2u) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    if (req->payload[0] == 2u) {
        response_error(req, TRINITY_NOT_SUPPORTED,
                       TRINITY_SOURCE_SN32, 0u);
        return;
    }
    if (g_controller.state != TRINITY_SYSTEM_READY_NO_SESSION ||
        !g_crypto.keypair_valid) {
        response_error(req, TRINITY_BAD_STATE, TRINITY_SOURCE_SN32, 0u);
        return;
    }
    if (!managed_transaction_begin(req)) return;
    memset(&material, 0, sizeof(material));
    rc = trinity_deploy_crypto_create_session(
        &g_crypto, req->payload[0], &req->payload[1], &material);
    mode = req->payload[0] == 1u ? TRINITY_MODE_KAT
                                 : TRINITY_MODE_DEMO_DETERMINISTIC;
    if (rc == TRINITY_OK)
        rc = trinity_controller_activate_session(&g_controller, &material,
                                                 mode, 20000u);
    if (rc == TRINITY_OK) {
        trinity_write_be32(&result[0], material.session_id);
        trinity_write_be64(&result[4], g_controller.current_sequence);
    }
    trinity_controller_secure_clear(&material, sizeof(material));
    managed_transaction_finish(rc, rc == TRINITY_OK ? result : NULL,
                               rc == TRINITY_OK ? sizeof(result) : 0u);
    trinity_controller_secure_clear(result, sizeof(result));
    (void)response_send();
}
