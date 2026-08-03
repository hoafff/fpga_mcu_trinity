#include "trinity_mlkem.h"

/* One-shot FIPS-202 functions supplied by the exact pinned mlkem-native build. */
void trinity_mlkem512_sha3_256(uint8_t output[32],
                               const uint8_t *input,
                               size_t input_length);
void trinity_mlkem512_shake256(uint8_t *output,
                               size_t output_length,
                               const uint8_t *input,
                               size_t input_length);

void trinity_sha3_256(uint8_t output[32],
                      const uint8_t *input,
                      size_t input_length) {
    trinity_mlkem512_sha3_256(output, input, input_length);
}

void trinity_shake256(uint8_t *output,
                      size_t output_length,
                      const uint8_t *input,
                      size_t input_length) {
    trinity_mlkem512_shake256(output, output_length, input, input_length);
}
