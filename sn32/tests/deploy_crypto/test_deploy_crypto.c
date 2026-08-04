#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "trinity_deploy_crypto.h"

static bool force_mismatch;
static unsigned keygen_calls;
static unsigned encaps_calls;
static trinity_mlkem512_low_ram_workspace_t *bound_workspace;

void trinity_controller_secure_clear(void *buffer, size_t length) {
    volatile uint8_t *cursor = (volatile uint8_t *)buffer;
    while (length-- != 0u) *cursor++ = 0u;
}

void trinity_secure_zero(void *buffer, size_t length) {
    trinity_controller_secure_clear(buffer, length);
}

int trinity_constant_time_equal(const uint8_t *a,
                                const uint8_t *b,
                                size_t length) {
    uint8_t difference = 0u;
    while (length-- != 0u) difference |= *a++ ^ *b++;
    return difference == 0u;
}

void trinity_mlkem512_bind_low_ram_workspace(
    trinity_mlkem512_low_ram_workspace_t *workspace) {
    bound_workspace = workspace;
}

void trinity_shake256(uint8_t *output,
                      size_t output_length,
                      const uint8_t *input,
                      size_t input_length) {
    size_t index;
    assert(input_length != 0u);
    for (index = 0u; index < output_length; ++index)
        output[index] = (uint8_t)(input[index % input_length] ^
                                  (uint8_t)(index * 29u + 7u));
}

void trinity_sha3_256(uint8_t output[32],
                      const uint8_t *input,
                      size_t input_length) {
    size_t index;
    memset(output, 0, 32u);
    for (index = 0u; index < input_length; ++index)
        output[index % 32u] ^= (uint8_t)(input[index] + (uint8_t)index);
}

trinity_error_code_t trinity_mlkem512_keygen_deterministic(
    uint8_t public_key[800], uint8_t secret_key[1632],
    const uint8_t coins[64]) {
    size_t index;
    ++keygen_calls;
    for (index = 0u; index < 800u; ++index)
        public_key[index] = (uint8_t)(coins[index % 64u] ^ (uint8_t)index);
    for (index = 0u; index < 1632u; ++index)
        secret_key[index] = (uint8_t)(coins[index % 64u] + (uint8_t)index);
    memcpy(&secret_key[TRINITY_MLKEM512_PUBLIC_KEY_IN_SECRET_KEY_OFFSET],
           public_key, 800u);
    return TRINITY_OK;
}

trinity_error_code_t trinity_mlkem512_keygen(uint8_t public_key[800],
                                              uint8_t secret_key[1632]) {
    (void)public_key;
    (void)secret_key;
    return TRINITY_NOT_SUPPORTED;
}

trinity_error_code_t trinity_mlkem512_encaps_deterministic(
    uint8_t ciphertext[768], uint8_t shared_secret[32],
    const uint8_t public_key[800], const uint8_t coins[32]) {
    size_t index;
    ++encaps_calls;
    memset(ciphertext, 0, 768u);
    for (index = 0u; index < 32u; ++index) {
        shared_secret[index] = (uint8_t)(public_key[index] ^ coins[index]);
        ciphertext[index] = shared_secret[index];
    }
    for (index = 32u; index < 768u; ++index)
        ciphertext[index] = (uint8_t)(public_key[index % 800u] + (uint8_t)index);
    return TRINITY_OK;
}

trinity_error_code_t trinity_mlkem512_encaps(uint8_t ciphertext[768],
                                              uint8_t shared_secret[32],
                                              const uint8_t public_key[800]) {
    (void)ciphertext;
    (void)shared_secret;
    (void)public_key;
    return TRINITY_NOT_SUPPORTED;
}

trinity_error_code_t trinity_mlkem512_decaps(
    uint8_t shared_secret[32], const uint8_t ciphertext[768],
    const uint8_t secret_key[1632]) {
    (void)secret_key;
    memcpy(shared_secret, ciphertext, 32u);
    if (force_mismatch) shared_secret[0] ^= 1u;
    return TRINITY_OK;
}

trinity_error_code_t trinity_kdf_derive_session(
    trinity_session_material_t *material,
    const uint8_t shared_secret[32], const uint8_t ciphertext[768]) {
    memcpy(material->ascon_key, shared_secret, 16u);
    memcpy(material->nonce_prefix, &ciphertext[32], 8u);
    material->session_id = UINT32_C(0x11223344);
    return TRINITY_OK;
}

void trinity_session_material_zeroize(trinity_session_material_t *material) {
    trinity_secure_zero(material, sizeof(*material));
}

static bool all_zero(const void *buffer, size_t length) {
    const uint8_t *bytes = (const uint8_t *)buffer;
    uint8_t aggregate = 0u;
    while (length-- != 0u) aggregate |= *bytes++;
    return aggregate == 0u;
}

int main(void) {
    trinity_deploy_crypto_t crypto;
    trinity_controller_session_material_t material;
    uint8_t seed[32];
    uint8_t digest[32];
    size_t index;

    assert(sizeof(crypto) <= 3520u);
    assert(sizeof(crypto.workspace) ==
           TRINITY_MLKEM512_LOW_RAM_WORKSPACE_BYTES);
    for (index = 0u; index < sizeof(seed); ++index)
        seed[index] = (uint8_t)(index + 1u);

    trinity_deploy_crypto_init(&crypto);
    assert(bound_workspace == &crypto.workspace.low_ram);
    assert((((uintptr_t)bound_workspace) &
            (TRINITY_MLKEM512_LOW_RAM_WORKSPACE_ALIGNMENT - 1u)) == 0u);
    assert(all_zero(&crypto, sizeof(crypto)));
    assert(trinity_deploy_crypto_generate_keypair(&crypto, 1u, seed) ==
           TRINITY_OK);
    assert(crypto.keypair_valid && crypto.keypair_generation == 1u);
    assert(keygen_calls == 1u);
    assert(all_zero(&crypto.workspace, sizeof(crypto.workspace)));

    assert(trinity_deploy_crypto_public_key_hash(&crypto, digest) == TRINITY_OK);
    assert(!all_zero(digest, sizeof(digest)));
    assert(memcmp(digest, crypto.public_key_hash, sizeof(digest)) == 0);

    memset(&material, 0, sizeof(material));
    assert(trinity_deploy_crypto_create_session(&crypto, 1u, seed,
                                                &material) == TRINITY_OK);
    assert(encaps_calls == 1u);
    assert(material.session_id == UINT32_C(0x11223344));
    assert(!all_zero(material.key, sizeof(material.key)));
    assert(all_zero(&crypto.workspace, sizeof(crypto.workspace)));

    force_mismatch = true;
    memset(&material, 0xA5, sizeof(material));
    assert(trinity_deploy_crypto_create_session(&crypto, 1u, seed,
                                                &material) ==
           TRINITY_MLKEM_SHARED_SECRET_MISMATCH);
    assert(all_zero(&material, sizeof(material)));
    force_mismatch = false;

    memset(seed, 0, sizeof(seed));
    assert(trinity_deploy_crypto_generate_keypair(&crypto, 1u, seed) ==
           TRINITY_OK);
    assert(keygen_calls == 2u);
    assert(trinity_deploy_crypto_create_session(&crypto, 0u, seed,
                                                &material) == TRINITY_OK);
    assert(encaps_calls == 3u);

    seed[0] = 1u;
    assert(trinity_deploy_crypto_generate_keypair(&crypto, 0u, seed) ==
           TRINITY_BAD_LENGTH);
    assert(trinity_deploy_crypto_create_session(&crypto, 0u, seed,
                                                &material) == TRINITY_BAD_LENGTH);
    assert(trinity_deploy_crypto_generate_keypair(&crypto, 2u, seed) ==
           TRINITY_NOT_SUPPORTED);

    trinity_deploy_crypto_zeroize(&crypto);
    assert(all_zero(&crypto, sizeof(crypto)));
    puts("PASS: deploy ML-KEM scratch and session storage are phase-shared");
    puts("PASS: deterministic/demo policies, KEM self-check and explicit zeroization");
    return 0;
}
