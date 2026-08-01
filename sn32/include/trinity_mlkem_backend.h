#ifndef TRINITY_MLKEM_BACKEND_H
#define TRINITY_MLKEM_BACKEND_H

#include <stddef.h>
#include <stdint.h>

#include "trinity_protocol_common.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef int (*trinity_entropy_provider_t)(uint8_t *output,
                                          size_t output_length,
                                          void *context);

void trinity_secure_zero(void *buffer, size_t length);
int trinity_constant_time_equal(const uint8_t *a, const uint8_t *b, size_t length);

void trinity_mlkem_backend_set_entropy_provider(trinity_entropy_provider_t provider,
                                                 void *context);
trinity_error_code_t trinity_mlkem_backend_entropy(uint8_t *output, size_t length);

void trinity_mlkem_backend_clear_error(void);
void trinity_mlkem_backend_latch_error(trinity_error_code_t error,
                                       uint32_t detail);
trinity_error_code_t trinity_mlkem_backend_error(void);
uint32_t trinity_mlkem_backend_error_detail(void);

/* Required by the pinned mlkem-native randomized API. Trinity production
 * wrappers normally obtain coins explicitly and call the deterministic API,
 * but the symbol is provided so the complete upstream translation units link.
 */
void randombytes(uint8_t *output, size_t output_length);

#ifdef __cplusplus
}
#endif

#endif
