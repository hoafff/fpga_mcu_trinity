        ep, TRINITY_SPI_GET_INFO, NULL, 0u, NULL);
    if (rc != TRINITY_OK) return rc;
    if (g_spi_rsp.payload_length != 12u ||
        g_spi_rsp.payload[0] != ep->id ||
        g_spi_rsp.payload[1] != TRINITY_PROTOCOL_VERSION ||
        g_spi_rsp.payload[10] != 0u ||
        g_spi_rsp.payload[11] != 0u)
        return TRINITY_BAD_STATE;
    ep->capabilities = trinity_read_be32(&g_spi_rsp.payload[2]);
    ep->build_id = trinity_read_be32(&g_spi_rsp.payload[6]);
    return TRINITY_OK;
}

static trinity_error_code_t endpoint_get_status(endpoint_t *ep) {
    trinity_error_code_t rc = endpoint_exchange(
        ep, TRINITY_SPI_GET_STATUS, NULL, 0u, NULL);
    if (rc != TRINITY_OK) return rc;
    if (g_spi_rsp.payload_length != 16u) return TRINITY_BAD_LENGTH;
    ep->session_state = g_spi_rsp.payload[0];
    ep->operation_state = g_spi_rsp.payload[1];
    ep->pending_flags = g_spi_rsp.payload[2];
    ep->secure_flags = g_spi_rsp.payload[3];
    ep->session_id = trinity_read_be32(&g_spi_rsp.payload[4]);
    ep->last_error = trinity_read_be16(&g_spi_rsp.payload[8]);
    ep->active_transaction_id = trinity_read_be16(&g_spi_rsp.payload[10]);
    ep->diagnostic_summary = trinity_read_be32(&g_spi_rsp.payload[12]);
    ep->ready = true;
    return TRINITY_OK;
}

static trinity_error_code_t probe(endpoint_t *ep) {
    trinity_error_code_t rc;
    endpoint_clear(ep);
    rc = endpoint_get_info(ep);
    if (rc == TRINITY_OK) rc = endpoint_get_status(ep);
    if (rc != TRINITY_OK) {
        ep->last_error = (uint16_t)rc;
        set_error(rc, endpoint_source(ep), ep->id);
    }
    return rc;
}

static uint8_t ready_mask(void) {
    uint8_t mask = TRINITY_READY_SN32;
    if (g_p1.ready) mask |= TRINITY_READY_PRIMER1;
#if TRINITY_DEPLOY_P1_BRINGUP_ONLY == 0
    if (g_p2.ready) mask |= TRINITY_READY_PRIMER2;
#endif
    return mask;
}

static uint8_t fault_mask(void) {
    uint8_t mask = g_fault ? TRINITY_FAULT_SN32 : 0u;
    if (!g_p1.ready ||
        g_p1.session_state == (uint8_t)TRINITY_SESSION_FAULT_LOCKED)
        mask |= TRINITY_FAULT_PRIMER1;
#if TRINITY_DEPLOY_P1_BRINGUP_ONLY == 0
    if (!g_p2.ready ||
        g_p2.session_state == (uint8_t)TRINITY_SESSION_FAULT_LOCKED)
        mask |= TRINITY_FAULT_PRIMER2;
#endif
