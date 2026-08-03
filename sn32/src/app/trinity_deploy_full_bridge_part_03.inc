    managed_transaction_respond(req);
}

static void full_handle_read_last_result(const trinity_pc_frame_t *req) {
    const trinity_controller_auth_result_t *result = &g_controller.last_result;
    if (!request_length_is(req, 0u)) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    if (!result->valid) {
        response_error(req, TRINITY_RESULT_NOT_READY,
                       TRINITY_SOURCE_PRIMER2, 0u);
        return;
    }
    g_pc_rsp.payload_length = 38u;
    trinity_write_be32(&g_pc_rsp.payload[0], result->session_id);
    trinity_write_be64(&g_pc_rsp.payload[4], result->sequence);
    memcpy(&g_pc_rsp.payload[12], result->plaintext,
           sizeof(result->plaintext));
    trinity_write_be16(&g_pc_rsp.payload[36], (uint16_t)result->status);
    (void)response_send();
}

static void full_handle_transport_stress(const trinity_pc_frame_t *req) {
    trinity_controller_auth_result_t auth;
    trinity_error_code_t rc = TRINITY_OK;
    uint8_t telemetry[32];
    uint8_t result[8];
    uint32_t count;
    uint32_t completed = 0u;
    uint8_t index;
    if (!request_length_is(req, 8u) || req->payload[1] != 0u ||
        req->payload[2] != 0u || req->payload[3] != 0u) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }
    count = trinity_read_be32(&req->payload[4]);
    if (count == 0u || count > 1000u || req->payload[0] < 1u ||
        req->payload[0] > 4u) {
        response_error(req, TRINITY_BAD_LENGTH,
                       TRINITY_SOURCE_HOST_PROTOCOL, req->payload[0]);
        return;
    }
    if (req->payload[0] == 1u) {
        /* PC-UART stress requires the host to originate multiple framed
         * requests; a single command cannot internally loop back UART0. */
        response_error(req, TRINITY_NOT_SUPPORTED,
                       TRINITY_SOURCE_HOST_PROTOCOL, 1u);
        return;
    }
    if (req->payload[0] == 4u &&
        g_controller.state != TRINITY_SYSTEM_ACTIVE) {
        response_error(req, TRINITY_BAD_STATE, TRINITY_SOURCE_SN32, 4u);
        return;
    }
    if (!managed_transaction_begin(req)) return;
    if (req->payload[0] == 2u || req->payload[0] == 3u) {
        rc = trinity_controller_transport_stress(&g_controller,
                                                  req->payload[0], count);
        if (rc == TRINITY_OK) completed = count;
    } else {
        memset(telemetry, 0, sizeof(telemetry));
        telemetry[0] = 0x02u;
        telemetry[4] = 0x53u;
        telemetry[5] = 0x54u;
        while (completed < count && rc == TRINITY_OK) {
            for (index = 0u; index < 24u; ++index)
                telemetry[8u + index] = (uint8_t)(completed + index);
            rc = trinity_controller_send_telemetry(&g_controller, telemetry,
                                                   2000u, &auth);
            if (rc == TRINITY_OK) ++completed;
            progress();
        }
    }
    result[0] = req->payload[0];
    result[1] = result[2] = result[3] = 0u;
    trinity_write_be32(&result[4], completed);
    managed_transaction_finish(rc, result, sizeof(result));
    managed_transaction_respond(req);
}
