#include "trinity_mlkem.h"

#include <stddef.h>
#include <string.h>

#define MLK_CONFIG_API_PARAMETER_SET 512
#define MLK_CONFIG_API_NAMESPACE_PREFIX trinity_mlkem512
#define MLK_CONFIG_API_NO_SUPERCOP
#include "mlkem_native.h"

/* These one-shot FIPS-202 functions are part of the exact pinned upstream
 * implementation and use MLK_CONFIG_NAMESPACE_PREFIX at link time.
 */
void trinity_mlkem512_sha3_256(uint8_t output[32],
                               const uint8_t *input,
                               size_t input_length);
void trinity_mlkem512_shake256(uint8_t *output,
                               size_t output_length,
                               const uint8_t *input,
                               size_t input_length);

static trinity_error_code_t trinity_upstream_result(int result,
                                                     void *primary_output,
                                                     size_t primary_length,
                                                     void *secondary_output,
                                                     size_t secondary_length) {
    trinity_error_code_t error = trinity_mlkem_backend_error();
    if (result != 0 && error == TRINITY_OK) {
        error = TRINITY_INTERNAL_FAULT;
        trinity_mlkem_backend_latch_error(error, (uint32_t)(unsigned int)(-result));
    }
    if (error != TRINITY_OK) {
        trinity_secure_zero(primary_output, primary_length);
        trinity_secure_zero(secondary_output, secondary_length);
    }
    return error;
}

trinity_error_code_t trinity_mlkem512_keygen_deterministic(
    uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES],
    const uint8_t coins[TRINITY_MLKEM_KEYGEN_COINS_BYTES]) {
    int result;
    if (public_key == NULL || secret_key == NULL || coins == NULL) {
        return TRINITY_INTERNAL_FAULT;
    }
    trinity_mlkem_backend_clear_error();
    result = trinity_mlkem512_keypair_derand(public_key, secret_key, coins);
    return trinity_upstream_result(result,
                                   public_key, TRINITY_MLKEM512_PUBLIC_KEY_BYTES,
                                   secret_key, TRINITY_MLKEM512_SECRET_KEY_BYTES);
}

trinity_error_code_t trinity_mlkem512_encaps_deterministic(
    uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    const uint8_t coins[TRINITY_MLKEM_ENCAPS_COINS_BYTES]) {
    int result;
    if (ciphertext == NULL || shared_secret == NULL || public_key == NULL || coins == NULL) {
        return TRINITY_INTERNAL_FAULT;
    }
    trinity_mlkem_backend_clear_error();
    result = trinity_mlkem512_enc_derand(ciphertext, shared_secret, public_key, coins);
    return trinity_upstream_result(result,
                                   ciphertext, TRINITY_MLKEM512_CIPHERTEXT_BYTES,
                                   shared_secret, TRINITY_MLKEM_SHARED_SECRET_BYTES);
}

trinity_error_code_t trinity_mlkem512_decaps(
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    const uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES]) {
    int result;
    if (shared_secret == NULL || ciphertext == NULL || secret_key == NULL) {
        return TRINITY_INTERNAL_FAULT;
    }
    trinity_mlkem_backend_clear_error();
    result = trinity_mlkem512_dec(shared_secret, ciphertext, secret_key);
    return trinity_upstream_result(result,
                                   shared_secret, TRINITY_MLKEM_SHARED_SECRET_BYTES,
                                   NULL, 0u);
}

trinity_error_code_t trinity_mlkem512_keygen(
    uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES]) {
    uint8_t coins[TRINITY_MLKEM_KEYGEN_COINS_BYTES];
    trinity_error_code_t error;
    if (public_key == NULL || secret_key == NULL) {
        return TRINITY_INTERNAL_FAULT;
    }
    trinity_mlkem_backend_clear_error();
    error = trinity_mlkem_backend_entropy(coins, sizeof(coins));
    if (error == TRINITY_OK) {
        error = trinity_mlkem512_keygen_deterministic(public_key, secret_key, coins);
    } else {
        trinity_secure_zero(public_key, TRINITY_MLKEM512_PUBLIC_KEY_BYTES);
        trinity_secure_zero(secret_key, TRINITY_MLKEM512_SECRET_KEY_BYTES);
    }
    trinity_secure_zero(coins, sizeof(coins));
    return error;
}

trinity_error_code_t trinity_mlkem512_encaps(
    uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES]) {
    uint8_t coins[TRINITY_MLKEM_ENCAPS_COINS_BYTES];
    trinity_error_code_t error;
    if (ciphertext == NULL || shared_secret == NULL || public_key == NULL) {
        return TRINITY_INTERNAL_FAULT;
    }
    trinity_mlkem_backend_clear_error();
    error = trinity_mlkem_backend_entropy(coins, sizeof(coins));
    if (error == TRINITY_OK) {
        error = trinity_mlkem512_encaps_deterministic(ciphertext, shared_secret,
                                                      public_key, coins);
    } else {
        trinity_secure_zero(ciphertext, TRINITY_MLKEM512_CIPHERTEXT_BYTES);
        trinity_secure_zero(shared_secret, TRINITY_MLKEM_SHARED_SECRET_BYTES);
    }
    trinity_secure_zero(coins, sizeof(coins));
    return error;
}

trinity_error_code_t trinity_kdf_derive_session(
    trinity_session_material_t *material,
    const uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES]) {
    static const uint8_t domain[] = {
        'T', 'R', 'I', 'N', 'I', 'T', 'Y', '-', 'K', 'D', 'F', '-', 'v', '1'
    };
    uint8_t ciphertext_hash[32];
    uint8_t input[sizeof(domain) + 1u + TRINITY_MLKEM_SHARED_SECRET_BYTES + 32u];
    uint8_t output[TRINITY_KDF_OUTPUT_BYTES];
    size_t offset = 0u;

    if (material == NULL || shared_secret == NULL || ciphertext == NULL) {
        return TRINITY_INTERNAL_FAULT;
    }

    trinity_mlkem512_sha3_256(ciphertext_hash, ciphertext,
                              TRINITY_MLKEM512_CIPHERTEXT_BYTES);
    memcpy(input + offset, domain, sizeof(domain));
    offset += sizeof(domain);
    input[offset++] = 0u;
    memcpy(input + offset, shared_secret, TRINITY_MLKEM_SHARED_SECRET_BYTES);
    offset += TRINITY_MLKEM_SHARED_SECRET_BYTES;
    memcpy(input + offset, ciphertext_hash, sizeof(ciphertext_hash));
    offset += sizeof(ciphertext_hash);

    trinity_mlkem512_shake256(output, sizeof(output), input, offset);
    memcpy(material->ascon_key, output, TRINITY_ASCON_KEY_BYTES);
    memcpy(material->nonce_prefix, output + TRINITY_ASCON_KEY_BYTES,
           TRINITY_NONCE_PREFIX_BYTES);
    material->session_id = ((uint32_t)output[24] << 24) |
                           ((uint32_t)output[25] << 16) |
                           ((uint32_t)output[26] << 8) |
                           (uint32_t)output[27];

    trinity_secure_zero(output, sizeof(output));
    trinity_secure_zero(input, sizeof(input));
    trinity_secure_zero(ciphertext_hash, sizeof(ciphertext_hash));
    return TRINITY_OK;
}

void trinity_session_material_zeroize(trinity_session_material_t *material) {
    if (material != NULL) {
        trinity_secure_zero(material, sizeof(*material));
    }
}
