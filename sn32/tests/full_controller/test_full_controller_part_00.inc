#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "trinity_full_controller.h"

typedef struct {
    uint8_t session_state;
    uint8_t secure_flags;
    uint32_t session_id;
    uint16_t next_txid;
    bool retained_valid;
    uint16_t retained_txid;
    uint8_t retained_command;
    trinity_transaction_state_t retained_state;
    trinity_error_code_t retained_code;
    uint16_t retained_length;
    uint8_t retained_data[66];
} mock_endpoint_t;

typedef struct {
    uint32_t now;
    bool tiny_fault;
    unsigned commit_toggles;
    mock_endpoint_t p1;
    mock_endpoint_t p2;
    uint8_t telemetry[32];
    bool telemetry_loaded;
    bool auth_pending;
    uint32_t auth_session_id;
    uint64_t auth_sequence;
    uint8_t auth_plaintext[24];
    trinity_error_code_t auth_status;
} mock_bus_t;

static mock_endpoint_t *endpoint(mock_bus_t *bus, uint8_t target) {
    return target == TRINITY_TARGET_PRIMER1 ? &bus->p1 : &bus->p2;
}

static void put_status(mock_endpoint_t *ep, uint8_t out[16]) {
    memset(out, 0, 16);
    out[0] = ep->session_state;
    out[2] = (ep->retained_valid ? 0x02u : 0u);
    out[3] = ep->secure_flags;
    trinity_write_be32(&out[4], ep->session_id);
    trinity_write_be16(&out[10], ep->retained_valid ? ep->retained_txid : 0u);
}

static void set_retained(mock_endpoint_t *ep, uint16_t txid, uint8_t command,
                         trinity_transaction_state_t state,
                         trinity_error_code_t code,
                         const uint8_t *data, uint16_t length) {
    ep->retained_valid = true;
    ep->retained_txid = txid;
    ep->retained_command = command;
    ep->retained_state = state;
    ep->retained_code = code;
    ep->retained_length = length;
    memset(ep->retained_data, 0, sizeof(ep->retained_data));
    if (length != 0u) memcpy(ep->retained_data, data, length);
}

static trinity_error_code_t mock_exchange(
    void *context, uint8_t target, uint8_t command,
    const uint8_t *payload, uint16_t payload_length,
    uint8_t *response, uint16_t response_capacity,
    uint16_t *response_length, uint16_t *issued_txid) {
    mock_bus_t *bus = context;
    mock_endpoint_t *ep = endpoint(bus, target);
    uint16_t txid = ep->next_txid++;
    if (issued_txid != NULL) *issued_txid = txid;
    if (response_length != NULL) *response_length = 0u;
    bus->now += 1u;

    switch (command) {
        case TRINITY_SPI_GET_INFO: {
            uint32_t caps = target == TRINITY_TARGET_PRIMER1
                                ? TRINITY_CONTROLLER_P1_CAPABILITIES
                                : TRINITY_CONTROLLER_P2_CAPABILITIES;
            assert(response_capacity >= 12u);
            memset(response, 0, 12u);
            response[0] = target;
            response[1] = TRINITY_PROTOCOL_VERSION;
            trinity_write_be32(&response[2], caps);
            trinity_write_be32(&response[6],
                               target == TRINITY_TARGET_PRIMER1
                                   ? 0x50310001u : 0x50320001u);
            *response_length = 12u;
            return TRINITY_OK;
        }
        case TRINITY_SPI_GET_STATUS:
            assert(response_capacity >= 16u);
            put_status(ep, response);
            *response_length = 16u;
            return TRINITY_OK;
        case TRINITY_SPI_RUN_SELF_TEST: {
            uint8_t data[2];
            assert(payload_length == 4u);
            data[0] = payload[0]; data[1] = payload[1];
            ep->session_state = TRINITY_SESSION_READY_NO_SESSION;
            ep->secure_flags |= TRINITY_SECURE_SELF_TEST_PASS;
            set_retained(ep, txid, command, TRINITY_TXN_SUCCEEDED,
                         TRINITY_OK, data, sizeof(data));
            return TRINITY_OK;
        }
        case TRINITY_SPI_GET_TXN_RESULT: {
            uint16_t query;
            assert(payload_length == 2u);
