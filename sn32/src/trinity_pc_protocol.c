#include "trinity_pc_protocol.h"

#include <string.h>

trinity_error_code_t trinity_cobs_encode(const uint8_t *input, size_t input_length,
                                          uint8_t *output, size_t output_capacity,
                                          size_t *output_length) {
    size_t read_index = 0u, write_index = 1u, code_index = 0u;
    uint8_t code = 1u;
    if (output == NULL || output_length == NULL || (input == NULL && input_length != 0u)) {
        return TRINITY_INTERNAL_FAULT;
    }
    if (output_capacity == 0u) return TRINITY_BAD_LENGTH;
    while (read_index < input_length) {
        if (input[read_index] == 0u) {
            output[code_index] = code;
            code_index = write_index++;
            code = 1u;
            if (write_index > output_capacity) return TRINITY_BAD_LENGTH;
            ++read_index;
        } else {
            if (write_index >= output_capacity) return TRINITY_BAD_LENGTH;
            output[write_index++] = input[read_index++];
            ++code;
            if (code == 0xFFu) {
                output[code_index] = code;
                code_index = write_index++;
                code = 1u;
                if (write_index > output_capacity) return TRINITY_BAD_LENGTH;
            }
        }
    }
    output[code_index] = code;
    *output_length = write_index;
    return TRINITY_OK;
}

trinity_error_code_t trinity_cobs_decode(const uint8_t *input, size_t input_length,
                                          uint8_t *output, size_t output_capacity,
                                          size_t *output_length) {
    size_t read_index = 0u, write_index = 0u, i;
    if (input == NULL || output == NULL || output_length == NULL || input_length == 0u) {
        return TRINITY_MALFORMED_FRAME;
    }
    while (read_index < input_length) {
        uint8_t code = input[read_index++];
        size_t count;
        if (code == 0u) return TRINITY_MALFORMED_FRAME;
        count = (size_t)code - 1u;
        if (read_index + count > input_length) return TRINITY_MALFORMED_FRAME;
        if (write_index + count + ((code != 0xFFu && read_index + count < input_length) ? 1u : 0u) > output_capacity) {
            return TRINITY_BAD_LENGTH;
        }
        for (i = 0u; i < count; ++i) output[write_index++] = input[read_index++];
        if (code != 0xFFu && read_index < input_length) output[write_index++] = 0u;
    }
    *output_length = write_index;
    return TRINITY_OK;
}

trinity_error_code_t trinity_pc_encode_raw(const trinity_pc_frame_t *frame,
                                            uint8_t *output, size_t output_capacity,
                                            size_t *output_length) {
    size_t total;
    uint16_t crc;
    if (frame == NULL || output == NULL || output_length == NULL) return TRINITY_INTERNAL_FAULT;
    if (frame->version != TRINITY_PROTOCOL_VERSION) return TRINITY_BAD_VERSION;
    if (!trinity_flags_valid(frame->flags)) return TRINITY_BAD_FLAGS;
    if (frame->payload_length > TRINITY_PC_MAX_PAYLOAD) return TRINITY_BAD_LENGTH;
    total = TRINITY_PC_HEADER_SIZE + frame->payload_length + TRINITY_PC_CRC_SIZE;
    if (output_capacity < total) return TRINITY_BAD_LENGTH;
    output[0] = frame->version;
    output[1] = frame->command;
    output[2] = frame->flags;
    output[3] = 0u;
    trinity_write_be16(output + 4, frame->transaction_id);
    trinity_write_be16(output + 6, frame->payload_length);
    memcpy(output + TRINITY_PC_HEADER_SIZE, frame->payload, frame->payload_length);
    crc = trinity_crc16_ccitt_false(output, total - 2u);
    trinity_write_be16(output + total - 2u, crc);
    *output_length = total;
    return TRINITY_OK;
}

trinity_error_code_t trinity_pc_decode_raw(const uint8_t *input, size_t input_length,
                                            trinity_pc_frame_t *frame) {
    uint16_t payload_length, expected_crc, actual_crc;
    size_t expected_length;
    if (input == NULL || frame == NULL) return TRINITY_INTERNAL_FAULT;
    if (input_length < TRINITY_PC_HEADER_SIZE + TRINITY_PC_CRC_SIZE) return TRINITY_BAD_LENGTH;
    if (input[0] != TRINITY_PROTOCOL_VERSION) return TRINITY_BAD_VERSION;
    if (!trinity_flags_valid(input[2]) || input[3] != 0u) return TRINITY_BAD_FLAGS;
    payload_length = trinity_read_be16(input + 6);
    if (payload_length > TRINITY_PC_MAX_PAYLOAD) return TRINITY_BAD_LENGTH;
    expected_length = TRINITY_PC_HEADER_SIZE + payload_length + TRINITY_PC_CRC_SIZE;
    if (input_length != expected_length) return TRINITY_BAD_LENGTH;
    expected_crc = trinity_read_be16(input + input_length - 2u);
    actual_crc = trinity_crc16_ccitt_false(input, input_length - 2u);
    if (expected_crc != actual_crc) return TRINITY_BAD_CRC;
    frame->version = input[0];
    frame->command = input[1];
    frame->flags = input[2];
    frame->transaction_id = trinity_read_be16(input + 4);
    frame->payload_length = payload_length;
    memcpy(frame->payload, input + TRINITY_PC_HEADER_SIZE, payload_length);
    return TRINITY_OK;
}

trinity_error_code_t trinity_pc_encode_wire(const trinity_pc_frame_t *frame,
                                             uint8_t *output, size_t output_capacity,
                                             size_t *output_length) {
    uint8_t raw[TRINITY_PC_MAX_RAW_FRAME];
    size_t raw_length, encoded_length;
    trinity_error_code_t status;
    if (output_capacity < 2u) return TRINITY_BAD_LENGTH;
    status = trinity_pc_encode_raw(frame, raw, sizeof(raw), &raw_length);
    if (status != TRINITY_OK) return status;
    status = trinity_cobs_encode(raw, raw_length, output, output_capacity - 1u, &encoded_length);
    if (status != TRINITY_OK) return status;
    output[encoded_length] = 0u;
    *output_length = encoded_length + 1u;
    return TRINITY_OK;
}

trinity_error_code_t trinity_pc_decode_wire(const uint8_t *input, size_t input_length,
                                             trinity_pc_frame_t *frame) {
    uint8_t raw[TRINITY_PC_MAX_RAW_FRAME];
    size_t raw_length, i;
    trinity_error_code_t status;
    if (input == NULL || input_length < 2u || input[input_length - 1u] != 0u) return TRINITY_MALFORMED_FRAME;
    for (i = 0u; i + 1u < input_length; ++i) if (input[i] == 0u) return TRINITY_MALFORMED_FRAME;
    status = trinity_cobs_decode(input, input_length - 1u, raw, sizeof(raw), &raw_length);
    if (status != TRINITY_OK) return status;
    return trinity_pc_decode_raw(raw, raw_length, frame);
}
