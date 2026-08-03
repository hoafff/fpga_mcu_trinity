#ifndef TRINITY_DEPLOY_CRYPTO_H
#define TRINITY_DEPLOY_CRYPTO_H

#include <stdbool.h>
#include <stdint.h>

#include "trinity_full_controller.h"
#include "trinity_mlkem.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    bool keypair_valid;
    uint32_t keypair_generation;
    uint8_t public_key_hash[32];
    uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES];
    union {
        struct {
            uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES];
            uint8_t coins[TRINITY_MLKEM_KEYGEN_COINS_BYTES];
        } keygen;
        struct {
            uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES];
            uint8_t encapsulated_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES];
            uint8_t decapsulated_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES];
            uint8_t encaps_coins[TRINITY_MLKEM_ENCAPS_COINS_BYTES];
        } session;
    } workspace;
} trinity_deploy_crypto_t;

void trinity_deploy_crypto_init(trinity_deploy_crypto_t *crypto);
void trinity_deploy_crypto_zeroize(trinity_deploy_crypto_t *crypto);

trinity_error_code_t trinity_deploy_crypto_generate_keypair(
    trinity_deploy_crypto_t *crypto,
    uint8_t mode,
    const uint8_t seed[32]);

trinity_error_code_t trinity_deploy_crypto_create_session(
    trinity_deploy_crypto_t *crypto,
    uint8_t mode,
    const uint8_t seed[32],
    trinity_controller_session_material_t *material);

trinity_error_code_t trinity_deploy_crypto_public_key_hash(
    const trinity_deploy_crypto_t *crypto,
    uint8_t digest[32]);

#ifdef __cplusplus
}
#endif

#endif
