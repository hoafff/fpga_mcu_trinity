static void handle_request(const trinity_pc_frame_t *req) {
    response_begin(req);
    if (req->flags != 0u) {
        response_error(req, TRINITY_BAD_FLAGS, TRINITY_SOURCE_HOST_PROTOCOL, 0u);
        return;
    }

    /*
     * PC UART remains live while the automatic startup/periodic probe runs.
     * Local telemetry is safe to serve reentrantly, but any command that could
     * start another SPI or crypto operation must fail closed instead of nesting
     * inside the active probe call stack.
     */
    if (g_automatic_probe_active &&
        req->command != TRINITY_PC_PING &&
        req->command != TRINITY_PC_GET_SYSTEM_INFO &&
        req->command != TRINITY_PC_GET_SYSTEM_STATUS &&
        req->command != TRINITY_PC_GET_LAST_ERROR &&
        req->command != TRINITY_PC_GET_FIRST_SPI_FAILURE) {
        response_error(req, TRINITY_BUSY, TRINITY_SOURCE_SN32, 0u);
        return;
    }

    switch (req->command) {
        case TRINITY_PC_PING:
            handle_ping(req);
            break;
        case TRINITY_PC_GET_SYSTEM_INFO:
            handle_get_system_info(req);
            break;
        case TRINITY_PC_GET_SYSTEM_STATUS:
            handle_get_system_status(req);
            break;
        case TRINITY_PC_GET_LAST_ERROR:
            handle_get_last_error(req);
            break;
        case TRINITY_PC_RUN_SELF_TEST:
            handle_run_self_test(req);
            break;
        case TRINITY_PC_GET_TXN_RESULT:
            handle_get_txn_result(req);
            break;
        case TRINITY_PC_RETIRE_TXN_RESULT:
            handle_retire_txn_result(req);
            break;
        case TRINITY_PC_SPI_DIAGNOSTIC:
            handle_spi_diagnostic(req);
            break;
        case TRINITY_PC_GET_FIRST_SPI_FAILURE:
            handle_get_first_spi_failure(req);
            break;
        case TRINITY_PC_GENERATE_KEYPAIR:
            full_handle_generate_keypair(req);
            break;
        case TRINITY_PC_CREATE_SESSION:
            full_handle_create_session(req);
            break;
        case TRINITY_PC_CLOSE_SESSION:
            full_handle_close_session(req);
            break;
        case TRINITY_PC_ZEROIZE_SYSTEM:
            full_handle_zeroize(req);
            break;
        case TRINITY_PC_SEND_ONE_TELEMETRY:
            full_handle_send_telemetry(req);
            break;
        case TRINITY_PC_RUN_DEMO:
            full_handle_run_demo(req);
            break;
        case TRINITY_PC_READ_LAST_RESULT:
            full_handle_read_last_result(req);
            break;
        case TRINITY_PC_RUN_NTT_TEST:
            full_handle_ntt_test(req);
            break;
        case TRINITY_PC_RUN_ASCON_TEST:
            full_handle_ascon_test(req);
            break;
        case TRINITY_PC_RUN_BENCHMARK:
            full_handle_benchmark(req);
            break;
        case TRINITY_PC_RUN_TRANSPORT_STRESS:
            full_handle_transport_stress(req);
            break;
        case TRINITY_PC_REQUEST_FAULT_CLEAR:
            response_error(req, TRINITY_NOT_SUPPORTED,
                           TRINITY_SOURCE_TINY1P5, 0u);
            break;
        case TRINITY_PC_INJECT_TEST_FAULT:
            response_error(req, TRINITY_NOT_SUPPORTED,
                           TRINITY_SOURCE_SN32, 0u);
            break;
        default:
            response_error(req, TRINITY_NOT_SUPPORTED,
                           TRINITY_SOURCE_SN32, 0u);
            break;
    }
    g_active_host_txid = g_host_txn.valid ? g_host_txn.host_txid : 0u;
