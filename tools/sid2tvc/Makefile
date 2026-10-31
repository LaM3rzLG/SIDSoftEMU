CC ?= cc
CFLAGS ?= -O2 -std=c99 -Wall -Wextra -ffp-contract=off

sid2tvc: sid2tvc.c
	$(CC) $(CFLAGS) -o $@ sid2tvc.c

clean:
	rm -f sid2tvc sid2tvc.exe
