CC ?= cc
CFLAGS ?= -std=c11 -Wall -Wextra -Werror
CPPFLAGS += -DTRINITY_DEPLOY_ENABLE_MLKEM=1 -I../../include -I../../config -I../../src/app
SOURCES = ../../src/app/trinity_deploy_crypto.c test_deploy_crypto.c

.PHONY: test clean

test: test_deploy_crypto
	./test_deploy_crypto

test_deploy_crypto: $(SOURCES)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(SOURCES) -o $@

clean:
	rm -f test_deploy_crypto
