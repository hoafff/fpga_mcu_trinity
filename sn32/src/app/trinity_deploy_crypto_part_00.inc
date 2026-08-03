#include "trinity_deploy_config.h"
#include "trinity_deploy_crypto.h"

#include <string.h>

static const uint8_t keygen_domain[] = {
    'T','R','I','N','I','T','Y','-','M','L','K','E','M','-','K','G','-','v','1'
};
static const uint8_t encaps_domain[] = {
    'T','R','I','N','I','T','Y','-','M','L','K','E','M','-','E','N','C','-','v','1'
};

static bool seed_is_zero(const uint8_t seed[32]) {
    uint8_t aggregate = 0u;
    size_t index;
    if (seed == NULL) return true;
    for (index = 0u; index < 32u; ++index) aggregate |= seed[index];
    return aggregate == 0u;
}

#if TRINITY_DEPLOY_ENABLE_MLKEM
static void expand_seed(uint8_t *output,
                        size_t output_length,
                        const uint8_t *domain,
                        size_t domain_length,
                        const uint8_t seed[32]) {
    uint8_t input[64];
    size_t length = 0u;
    if (domain_length > 31u) domain_length = 31u;
    memcpy(&input[length], domain, domain_length);
    length += domain_length;
    input[length++] = 0u;
    memcpy(&input[length], seed, 32u);
    length += 32u;
    trinity_shake256(output, output_length, input, length);
    trinity_secure_zero(input, sizeof(input));
}
#endif

void trinity_deploy_crypto_init(trinity_deploy_crypto_t *crypto) {
    if (crypto == NULL) return;
    memset(crypto, 0, sizeof(*crypto));
}

void trinity_deploy_crypto_zeroize(trinity_deploy_crypto_t *crypto) {
    if (crypto == NULL) return;
    trinity_secure_zero(crypto, sizeof(*crypto));
}

trinity_error_code_t trinity_deploy_crypto_generate_keypair(
    trinity_deploy_crypto_t *crypto,
    uint8_t mode,
    const uint8_t seed[32]) {
#if TRINITY_DEPLOY_ENABLE_MLKEM
    trinity_error_code_t rc;
    if (crypto == NULL || seed == NULL || mode > 1u)
        return mode > 1u ? TRINITY_NOT_SUPPORTED : TRINITY_INTERNAL_FAULT;
    if (mode == 1u && seed_is_zero(seed)) return TRINITY_BAD_LENGTH;

    trinity_secure_zero(crypto->public_key, sizeof(crypto->public_key));
    trinity_secure_zero(crypto->secret_key, sizeof(crypto->secret_key));
    trinity_secure_zero(&crypto->workspace, sizeof(crypto->workspace));
    crypto->keypair_valid = false;

    if (mode == 1u) {
        expand_seed(crypto->workspace.keygen_coins,
                    sizeof(crypto->workspace.keygen_coins),
                    keygen_domain, sizeof(keygen_domain), seed);
        rc = trinity_mlkem512_keygen_deterministic(
            crypto->public_key, crypto->secret_key,
            crypto->workspace.keygen_coins);
    } else {
        rc = trinity_mlkem512_keygen(crypto->public_key, crypto->secret_key);
    }
    trinity_secure_zero(&crypto->workspace, sizeof(crypto->workspace));
    if (rc != TRINITY_OK) {
        trinity_secure_zero(crypto->public_key, sizeof(crypto->public_key));
        trinity_secure_zero(crypto->secret_key, sizeof(crypto->secret_key));
        return rc;
    }
    crypto->keypair_valid = true;
    crypto->keypair_generation += 1u;
    if (crypto->keypair_generation == 0u) crypto->keypair_generation = 1u;
    return TRINITY_OK;
#else
    (void)crypto;
    (void)mode;
    (void)seed;
    return TRINITY_NOT_SUPPORTED;
#endif
}
