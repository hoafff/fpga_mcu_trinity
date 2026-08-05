            query = trinity_read_be16(payload);
            if (!ep->retained_valid || query != ep->retained_txid)
                return TRINITY_RESULT_NOT_READY;
            if (bus->retained_not_ready_reads != 0u) {
                bus->retained_not_ready_reads -= 1u;
                return TRINITY_RESULT_NOT_READY;
            }
            assert(response_capacity >= (uint16_t)(10u + ep->retained_length));
            trinity_write_be16(&response[0], query);
            response[2] = (uint8_t)ep->retained_state;
            response[3] = ep->retained_command;
            trinity_write_be16(&response[4], (uint16_t)ep->retained_code);
            trinity_write_be16(&response[6], ep->retained_length);
            response[8] = response[9] = 0u;
            memcpy(&response[10], ep->retained_data, ep->retained_length);
            *response_length = (uint16_t)(10u + ep->retained_length);
            return TRINITY_OK;
        }
        case TRINITY_SPI_RETIRE_TXN_RESULT:
            ep->retained_valid = false;
            return TRINITY_OK;
        case TRINITY_SPI_STAGE_SESSION:
            assert(payload_length == 28u);
            ep->staged_session_id = trinity_read_be32(payload);
            /* Real Primer GET_STATUS still exposes active_session_id=0 here. */
            ep->session_id = 0u;
            ep->session_state = TRINITY_SESSION_STAGED;
            ep->secure_flags |= TRINITY_SECURE_SESSION_STAGED;
            return TRINITY_OK;
        case TRINITY_SPI_COMMIT_SESSION:
            assert(payload_length == 4u);
            assert(trinity_read_be32(payload) == ep->staged_session_id);
            ep->session_id = ep->staged_session_id;
            ep->staged_session_id = 0u;
            ep->session_state = TRINITY_SESSION_COMMITTED_BLOCKED;
            set_retained(ep, txid, command, TRINITY_TXN_SUCCEEDED,
                         TRINITY_OK, NULL, 0u);
            return TRINITY_OK;
        case TRINITY_SPI_ABORT_SESSION:
            ep->session_state = TRINITY_SESSION_READY_NO_SESSION;
            ep->staged_session_id = 0u;
            ep->session_id = 0u;
            ep->secure_flags &= (uint8_t)~(TRINITY_SECURE_SESSION_STAGED |
                                           TRINITY_SECURE_ENABLE);
            return TRINITY_OK;
        case TRINITY_SPI_ZEROIZE:
            ep->session_state = TRINITY_SESSION_READY_NO_SESSION;
            ep->staged_session_id = 0u;
            ep->session_id = 0u;
            ep->secure_flags = TRINITY_SECURE_SELF_TEST_PASS;
            set_retained(ep, txid, command, TRINITY_TXN_ZEROIZED,
                         TRINITY_ZEROIZED, NULL, 0u);
            return TRINITY_OK;
        case TRINITY_SPI_LOAD_TELEMETRY:
            assert(target == TRINITY_TARGET_PRIMER1);
            assert(payload_length == 32u);
            memcpy(bus->telemetry, payload, 32u);
            bus->telemetry_loaded = true;
            return TRINITY_OK;
        case TRINITY_SPI_ENCRYPT_AND_SEND: {
            uint8_t data[14];
            assert(target == TRINITY_TARGET_PRIMER1);
            assert(bus->telemetry_loaded);
            bus->auth_pending = true;
            bus->auth_session_id = ep->session_id;
            bus->auth_sequence += 1u;
            memcpy(bus->auth_plaintext, &bus->telemetry[8], 24u);
            bus->auth_status = TRINITY_OK;
            trinity_write_be32(&data[0], bus->auth_session_id);
            trinity_write_be64(&data[4], bus->auth_sequence);
            trinity_write_be16(&data[12], TRINITY_CONTROLLER_UART_FRAME_BYTES);
            set_retained(ep, txid, command, TRINITY_TXN_SUCCEEDED,
                         TRINITY_OK, data, sizeof(data));
            return TRINITY_OK;
        }
        case TRINITY_SPI_GET_RX_STATUS:
            assert(target == TRINITY_TARGET_PRIMER2);
            assert(response_capacity >= 16u);
            memset(response, 0, 16u);
            response[0] = bus->auth_pending ? 4u : 0u;
            response[1] = bus->auth_pending ? 1u : 0u;
            response[2] = 1u;
            trinity_write_be32(&response[4], bus->p2.session_id);
            trinity_write_be64(&response[8], bus->auth_sequence);
            *response_length = 16u;
            return TRINITY_OK;
        case TRINITY_SPI_READ_AUTH_RESULT:
            if (!bus->auth_pending) return TRINITY_RESULT_NOT_READY;
            assert(response_capacity >= 38u);
            trinity_write_be32(&response[0], bus->auth_session_id);
            trinity_write_be64(&response[4], bus->auth_sequence);
            memcpy(&response[12], bus->auth_plaintext, 24u);
            trinity_write_be16(&response[36], (uint16_t)bus->auth_status);
            *response_length = 38u;
            return TRINITY_OK;
        case TRINITY_SPI_ACK_AUTH_RESULT:
            assert(payload_length == 12u);
            if (trinity_read_be32(&payload[0]) != bus->auth_session_id)
                return TRINITY_BAD_SESSION;
            if (trinity_read_be64(&payload[4]) != bus->auth_sequence)
                return TRINITY_STALE_SEQUENCE;
            bus->auth_pending = false;
            return TRINITY_OK;
        case TRINITY_SPI_CLEAR_DIAGNOSTIC_COUNTERS:
            assert(payload_length == 4u);
            return TRINITY_OK;
        default:
            return TRINITY_BAD_COMMAND;
    }
}

static uint32_t mock_now(void *context) {
    return ((mock_bus_t *)context)->now;
}
static void mock_progress(void *context) {
    ((mock_bus_t *)context)->now += 1u;
}
static bool mock_tiny_fault(void *context) {
    return ((mock_bus_t *)context)->tiny_fault;
}
