    if (g_error.code == TRINITY_FRAME_TIMEOUT ||
        g_error.code == TRINITY_BAD_MAGIC ||
        g_error.code == TRINITY_BAD_CRC ||
        g_error.code == TRINITY_TRANSACTION_CONFLICT)
        mask |= TRINITY_FAULT_TRANSPORT;
    return mask;
}

static uint8_t system_state(void) {
    if (g_fault) return (uint8_t)TRINITY_SYSTEM_ERROR;
    return (uint8_t)g_controller.state;
}

static uint32_t pc_request_fingerprint(const trinity_pc_frame_t *req) {
    uint8_t material[4u + TRINITY_PC_MAX_PAYLOAD];
    if (req == NULL || req->payload_length > TRINITY_PC_MAX_PAYLOAD) return 0u;
    material[0] = req->command;
    material[1] = req->flags;
    trinity_write_be16(&material[2], req->payload_length);
    if (req->payload_length != 0u)
        memcpy(&material[4], req->payload, req->payload_length);
    return trinity_crc32c(material, 4u + req->payload_length);
}

static void response_begin(const trinity_pc_frame_t *req) {
    memset(&g_pc_rsp, 0, sizeof(g_pc_rsp));
    g_pc_rsp.version = TRINITY_PROTOCOL_VERSION;
    g_pc_rsp.command = req->command;
    g_pc_rsp.flags = TRINITY_FLAG_RESPONSE;
    g_pc_rsp.transaction_id = req->transaction_id;
}

static trinity_error_code_t response_send(void) {
    size_t raw_len = 0u;
    size_t wire_len = 0u;
    trinity_error_code_t rc = trinity_pc_encode_raw(
        &g_pc_rsp, g_pc_raw, sizeof(g_pc_raw), &raw_len);
