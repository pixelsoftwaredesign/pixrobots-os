# AgriCol - Makefile pour daemon gateway OpenBSD
CC = cc
CFLAGS = -Wall -Wextra -O2 -std=c99
LDFLAGS = -lpaho-mqtt3c

PREFIX = /usr/local
BINDIR = $(PREFIX)/libexec/agricol

all: serial_gateway

serial_gateway: serial_gateway.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)
	strip $@

install: serial_gateway
	mkdir -p $(DESTDIR)$(BINDIR)
	install -m 755 serial_gateway $(DESTDIR)$(BINDIR)/
	install -m 644 ../nodes.conf $(DESTDIR)/etc/agricol/

clean:
	rm -f serial_gateway *.o
