# Build all PixOS APKs

all: build-all

build-all:
	@echo "Building all PixOS apps..."
	@set -e; for app in pixos pixos-messenger pixconnect pixos-livestream pixos-office pixos-phone pixos-nop; do \
		echo "=== $$app ==="; \
		cd $$app && ../gradlew assembleDebug --no-daemon && cd ..; \
	done
	@mkdir -p dist
	@find . -path "*/build/outputs/apk/debug/*.apk" -exec cp {} dist/ \;
	@echo "=== APKs in dist/ ==="
	@ls -lh dist/

clean:
	@for app in pixos pixos-messenger pixconnect pixos-livestream pixos-office pixos-phone pixos-nop; do \
		cd $$app && rm -rf app/build && cd ..; \
	done
	rm -rf dist

.PHONY: all build-all clean
