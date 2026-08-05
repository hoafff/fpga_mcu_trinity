/* Full dual-Primer controller binding for the SN32F407 deploy target. */

static bool g_session_commit_level;
static bool g_session_commit_readback_at_high;
static bool g_tiny_fault_contained;

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

static void full_session_commit_low(void *context) {
    (void)context;
    g_session_commit_level = false;
    gpio_set_mode(FPST_SN32F407_SESSION_COMMIT_PORT,
                  FPST_SN32F407_SESSION_COMMIT_PIN, true);
    gpio_set_cfg(FPST_SN32F407_SESSION_COMMIT_PORT,
                 FPST_SN32F407_SESSION_COMMIT_PIN,
                 GPIO_NO_PULL_SCHMITT);
    gpio_write(FPST_SN32F407_SESSION_COMMIT_PORT,
               FPST_SN32F407_SESSION_COMMIT_PIN, false);
}

static void full_session_commit_high(void *context) {
    (void)context;
    gpio_set_mode(FPST_SN32F407_SESSION_COMMIT_PORT,
                  FPST_SN32F407_SESSION_COMMIT_PIN, true);
    gpio_set_cfg(FPST_SN32F407_SESSION_COMMIT_PORT,
                 FPST_SN32F407_SESSION_COMMIT_PIN,
                 GPIO_NO_PULL_SCHMITT);
    gpio_write(FPST_SN32F407_SESSION_COMMIT_PORT,
               FPST_SN32F407_SESSION_COMMIT_PIN, true);
    g_session_commit_level = true;
    g_session_commit_readback_at_high =
        gpio_read(FPST_SN32F407_SESSION_COMMIT_PORT,
                  FPST_SN32F407_SESSION_COMMIT_PIN);
}

static void full_contain_tiny_fault(void) {
    if (g_tiny_fault_contained || !full_tiny_fault_active(NULL)) return;
    g_tiny_fault_contained = true;
    g_fault = true;
    full_session_commit_low(NULL);
    cs_all_high();
    trinity_deploy_crypto_zeroize(&g_crypto);
    trinity_controller_secure_clear(&g_controller.session,
                                    sizeof(g_controller.session));
    trinity_controller_forget_last_result(&g_controller);
    g_controller.session_material_valid = false;
    g_controller.commit_issued = false;
    g_controller.current_sequence = 0u;
    g_controller.state = TRINITY_SYSTEM_FAULT_LOCKED;
    g_controller.last_error = TRINITY_FAULT_LOCKED;
    g_controller.last_error_source = TRINITY_SOURCE_TINY1P5;
    g_controller.last_error_detail = FPST_SN32F407_TINY_FAULT_N_PIN;
    memset(&g_host_txn, 0, sizeof(g_host_txn));
    g_active_host_txid = 0u;
    set_error(TRINITY_FAULT_LOCKED, TRINITY_SOURCE_TINY1P5,
              FPST_SN32F407_TINY_FAULT_N_PIN);
    g_trinity_deploy_marker = DEPLOY_MARKER_ERR;
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
