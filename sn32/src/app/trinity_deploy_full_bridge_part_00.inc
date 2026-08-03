/* Full dual-Primer controller binding for the SN32F407 deploy target. */

static bool g_session_commit_level;

static endpoint_t *full_endpoint(uint8_t target_id) {
    if (target_id == TRINITY_TARGET_PRIMER1) return &g_p1;
    if (target_id == TRINITY_TARGET_PRIMER2) return &g_p2;
    return NULL;
}

static trinity_error_code_t full_exchange(
    void *context,
    uint8_t target_id,
    uint8_t command,
    const uint8_t *payload,
    uint16_t payload_length,
    uint8_t *response_payload,
    uint16_t response_capacity,
    uint16_t *response_length,
    uint16_t *issued_txid) {
    endpoint_t *ep = full_endpoint(target_id);
    trinity_error_code_t rc;
    (void)context;
    if (ep == NULL || response_length == NULL) return TRINITY_BAD_STATE;
    *response_length = 0u;
    rc = endpoint_exchange(ep, command, payload, payload_length, issued_txid);
    if (rc != TRINITY_OK) return rc;
    if (g_spi_rsp.payload_length > response_capacity ||
        (g_spi_rsp.payload_length != 0u && response_payload == NULL))
        return TRINITY_BAD_LENGTH;
    if (g_spi_rsp.payload_length != 0u)
        memcpy(response_payload, g_spi_rsp.payload, g_spi_rsp.payload_length);
    *response_length = g_spi_rsp.payload_length;
    return TRINITY_OK;
}

static uint32_t full_now_ms(void *context) {
    (void)context;
    return g_ms;
}

static void full_progress(void *context) {
    (void)context;
    progress();
}

static bool full_tiny_fault_active(void *context) {
    (void)context;
#if FPST_SN32F407_HARNESS_VERIFIED
    return !gpio_read(FPST_SN32F407_TINY_FAULT_N_PORT,
                      FPST_SN32F407_TINY_FAULT_N_PIN);
#else
    return false;
#endif
}

static void full_session_commit_toggle(void *context) {
    (void)context;
    g_session_commit_level = !g_session_commit_level;
    gpio_write(FPST_SN32F407_SESSION_COMMIT_PORT,
               FPST_SN32F407_SESSION_COMMIT_PIN,
               g_session_commit_level);
}

static void full_sync_endpoint(endpoint_t *legacy,
                               const trinity_controller_endpoint_t *full) {
    if (legacy == NULL || full == NULL) return;
    legacy->ready = full->ready;
    legacy->capabilities = full->capabilities;
    legacy->build_id = full->build_id;
    legacy->session_state = full->session_state;
    legacy->operation_state = full->operation_state;
    legacy->pending_flags = full->pending_flags;
    legacy->secure_flags = full->secure_flags;
    legacy->session_id = full->session_id;
    legacy->last_error = full->last_error;
    legacy->active_transaction_id = full->active_transaction_id;
    legacy->diagnostic_summary = full->diagnostic_summary;
}
