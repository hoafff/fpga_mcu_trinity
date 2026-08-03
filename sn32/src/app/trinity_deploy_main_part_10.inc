static uint8_t system_state(void) {
    if (g_controller.state == TRINITY_SYSTEM_FAULT_LOCKED)
        return (uint8_t)TRINITY_SYSTEM_FAULT_LOCKED;
    if (g_fault) return (uint8_t)TRINITY_SYSTEM_ERROR;
    return (uint8_t)g_controller.state;
}

static uint32_t pc_request_fingerprint(const trinity_pc_frame_t *req) {
    if (req == NULL || req->payload_length > TRINITY_PC_MAX_PAYLOAD) return 0u;
    g_pc_raw[0] = req->command;
    g_pc_raw[1] = req->flags;
    trinity_write_be16(&g_pc_raw[2], req->payload_length);
    if (req->payload_length != 0u)
        memcpy(&g_pc_raw[4], req->payload, req->payload_length);
    return trinity_crc32c(g_pc_raw, 4u + req->payload_length);
}

static void response_begin(const trinity_pc_frame_t *req) {
    const uint8_t command = req->command;
    const uint16_t transaction_id = req->transaction_id;
    memset(&g_pc_rsp, 0, sizeof(g_pc_rsp));
    g_pc_rsp.version = TRINITY_PROTOCOL_VERSION;
    g_pc_rsp.command = command;
    g_pc_rsp.flags = TRINITY_FLAG_RESPONSE;
    g_pc_rsp.transaction_id = transaction_id;
}

static trinity_error_code_t response_send(void) {
    size_t raw_len = 0u;
    size_t wire_len = 0u;
    trinity_error_code_t rc = trinity_pc_encode_raw(
        &g_pc_rsp, g_pc_raw, sizeof(g_pc_raw), &raw_len);
