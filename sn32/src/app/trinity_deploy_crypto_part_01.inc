trinity_error_code_t trinity_deploy_crypto_create_session(
    trinity_deploy_crypto_t *crypto,
    uint8_t mode,
    const uint8_t seed[32],
    trinity_controller_session_material_t *material) {
#if TRINITY_DEPLOY_ENABLE_MLKEM
    trinity_session_material_t derived;
    trinity_error_code_t rc;
    if (crypto == NULL || seed == NULL || material == NULL)
        return TRINITY_INTERNAL_FAULT;
    if (mode > 1u) return TRINITY_NOT_SUPPORTED;
    if (!crypto->keypair_valid) return TRINITY_BAD_STATE;
    if (mode == 1u && seed_is_zero(seed)) return TRINITY_BAD_LENGTH;

    memset(&derived, 0, sizeof(derived));
    trinity_secure_zero(&crypto->workspace, sizeof(crypto->workspace));
    if (mode == 1u) {
        expand_seed(crypto->workspace.session.encaps_coins,
                    sizeof(crypto->workspace.session.encaps_coins),
                    encaps_domain, sizeof(encaps_domain), seed);
        rc = trinity_mlkem512_encaps_deterministic(
            crypto->workspace.session.ciphertext,
            crypto->workspace.session.encapsulated_secret,
            crypto->public_key,
            crypto->workspace.session.encaps_coins);
    } else {
        rc = trinity_mlkem512_encaps(
            crypto->workspace.session.ciphertext,
            crypto->workspace.session.encapsulated_secret,
            crypto->public_key);
    }
    if (rc == TRINITY_OK) {
        rc = trinity_mlkem512_decaps(
            crypto->workspace.session.decapsulated_secret,
            crypto->workspace.session.ciphertext,
            crypto->secret_key);
    }
    if (rc == TRINITY_OK && !trinity_constant_time_equal(
            crypto->workspace.session.encapsulated_secret,
            crypto->workspace.session.decapsulated_secret,
            TRINITY_MLKEM_SHARED_SECRET_BYTES)) {
        rc = TRINITY_MLKEM_SHARED_SECRET_MISMATCH;
    }
    if (rc == TRINITY_OK) {
        rc = trinity_kdf_derive_session(
            &derived,
            crypto->workspace.session.encapsulated_secret,
            crypto->workspace.session.ciphertext);
    }
    if (rc == TRINITY_OK && derived.session_id == 0u)
        rc = TRINITY_SESSION_ID_COLLISION;
    if (rc == TRINITY_OK) {
        memcpy(material->key, derived.ascon_key, sizeof(material->key));
        memcpy(material->nonce_prefix, derived.nonce_prefix,
               sizeof(material->nonce_prefix));
        material->session_id = derived.session_id;
    } else {
        trinity_controller_secure_clear(material, sizeof(*material));
    }
    trinity_session_material_zeroize(&derived);
    trinity_secure_zero(&crypto->workspace, sizeof(crypto->workspace));
    return rc;
#else
    (void)crypto;
    (void)mode;
    (void)seed;
    if (material != NULL)
        trinity_controller_secure_clear(material, sizeof(*material));
    return TRINITY_NOT_SUPPORTED;
#endif
}

trinity_error_code_t trinity_deploy_crypto_public_key_hash(
    const trinity_deploy_crypto_t *crypto,
    uint8_t digest[32]) {
#if TRINITY_DEPLOY_ENABLE_MLKEM
    if (crypto == NULL || digest == NULL) return TRINITY_INTERNAL_FAULT;
    if (!crypto->keypair_valid) return TRINITY_BAD_STATE;
    trinity_sha3_256(digest, crypto->public_key, sizeof(crypto->public_key));
    return TRINITY_OK;
#else
    (void)crypto;
    if (digest != NULL) trinity_controller_secure_clear(digest, 32u);
    return TRINITY_NOT_SUPPORTED;
#endif
}
