VMS_DIR := .vms
JAMMY := $(VMS_DIR)/jammy.img
META_DIR := ./meta
TEMPLATE_FILE := user-data.tpl.yaml
OUTPUT_FILE := $(META_DIR)/user-data
SSH_KEY_FILE := $(shell [ -f ~/.ssh/id_rsa.pub ] && echo ~/.ssh/id_rsa.pub || echo ~/.ssh/id_ed25519.pub)

$(JAMMY):
	@mkdir -p $(VMS_DIR)
	@test -f $(JAMMY) || (echo "Downloading jammy..." && curl -o $(JAMMY) https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img && echo "Download complete.")

.PHONY: download-jammy
download-jammy: $(JAMMY)

.PHONY: prepare-user-data
prepare-user-data:
	@mkdir -p $(META_DIR)
	@SSH_KEY=$$(cat $(SSH_KEY_FILE)); \
	 sed "s|{ ssh_key }|$$SSH_KEY|" $(TEMPLATE_FILE) > $(OUTPUT_FILE)
	@echo "User-data file prepared at $(OUTPUT_FILE)."


.PHONY: build-jammy
run-jammy: download-jammy
	@echo "Starting HTTP server on port 8060 in the background..."
	@python3 -m http.server 8060 --directory . > /dev/null 2>&1 & \
	SERVER_PID=$$!; \
	trap "echo 'Stopping HTTP server...'; kill $$SERVER_PID" EXIT; \
	echo "Running QEMU..."; \
	qemu-system-x86_64 -nographic -hda $(JAMMY) \
	-m 4G -smp 2 -netdev user,id=vmnet,hostfwd=tcp::6080-:6080,hostfwd=tcp::8000-:8000,hostfwd=tcp::2222-:22 \
	-device e1000,netdev=vmnet -smbios type=1,serial=ds='nocloud;s=http://10.0.2.2:8060/'; \
	echo "QEMU has exited."

.PHONY: clean
clean:
	rm -rf $(VMS_DIR)