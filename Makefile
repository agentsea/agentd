VMS_DIR := .vms
JAMMY := $(VMS_DIR)/jammy.img
META_DIR := ./meta
TEMPLATE_FILE := user-data.tpl
OUTPUT_FILE := $(META_DIR)/user-data
SSH_KEY_FILE := $(shell [ -f ~/.ssh/id_rsa.pub ] && echo ~/.ssh/id_rsa.pub || echo ~/.ssh/id_ed25519.pub)
JAMMY_LATEST := ./.vms/jammy/latest/jammy.qcow2

$(JAMMY):
	@mkdir -p $(VMS_DIR)
	@test -f $(JAMMY) || (echo "Downloading jammy..." && curl -o $(JAMMY) https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img && echo "Download complete.")
	qemu-img resize $(JAMMY) +10G

.PHONY: download-jammy
download-jammy: $(JAMMY)

.PHONY: prepare-user-data
prepare-user-data:
	@mkdir -p $(META_DIR)
	@SSH_KEY=$$(cat $(SSH_KEY_FILE)); \
	 sed "s|{{ ssh_public_key }}|$$SSH_KEY|" $(TEMPLATE_FILE) > $(OUTPUT_FILE)
	@echo "User-data file prepared at $(OUTPUT_FILE)."

.PHONY: run-meta
run-meta:
	python3 -m http.server 8060 --directory ./meta

.PHONY: run-jammy
run-jammy: prepare-user-data
	xorriso -as mkisofs -o cidata.iso -V "cidata" -J -r -iso-level 3 meta/
	qemu-system-x86_64 -nographic -hda $(JAMMY_LATEST) \
	-m 4G -smp 2 -netdev user,id=vmnet,hostfwd=tcp::6080-:6080,hostfwd=tcp::8000-:8000,hostfwd=tcp::2222-:22 \
	-device e1000,netdev=vmnet -cdrom cidata.iso 
 # -smbios type=1,serial=ds='nocloud;s=http://10.0.2.2:8060/';

.PHONY: clean
clean:
	rm -rf $(VMS_DIR)

.PHONY: pack
pack: user-data
	./pack.sh

.PHONY: user-data
user-data:
	# hdiutil makehybrid -o cidata.iso -hfs -joliet -iso -default-volume-name cidata root_meta/
	xorriso -as mkisofs -o cidata_root.iso -V "cidata" -J -r -iso-level 3 root_meta/

.PHONY: push-latest
push-latest:
	gsutil cp .vms/jammy/latest/jammy.qcow2 gs://agentsea-vms/jammy/latest/agentd-jammy.qcow2
	gsutil acl ch -u AllUsers:R gs://agentsea-vms/jammy/latest/agentd-jammy.qcow2

.PHONY: exp-deps
exp-deps:
	poetry export -f requirements.txt --output requirements.txt --without-hashes

.PHONY: run-latest-auth
run-latest-auth:
	docker run -d \
		--platform linux/arm64 \
		--name=webtop \
		--security-opt seccomp=unconfined \
		-e PUID=1000 \
		-e PGID=1000 \
		-e CUSTOM_USER=agentd \
		-e PASSWORD=agentd \
		-e TZ=Etc/UTC \
		-p 3000:3000 \
		-p 3001:3001 \
		-p 8000:8000 \
		--restart unless-stopped \
		us-docker.pkg.dev/agentsea-dev/agentd/desktop-webtop:efc7aed

.PHONY: run-latest
run-latest:
	docker run -d \
		--platform linux/arm64 \
		--name=webtop \
		--security-opt seccomp=unconfined \
		-e TZ=Etc/UTC \
		-p 3000:3000 \
		-p 3001:3001 \
		-p 8000:8000 \
		--restart unless-stopped \
		us-docker.pkg.dev/agentsea-dev/agentd/desktop-webtop:773b6aa
# us-docker.pkg.dev/agentsea-dev/agentd/desktop-webtop:latest


.PHONY: dev
dev:
	docker run -d \
		--platform linux/arm64 \
		--name=webtop \
		--security-opt seccomp=unconfined \
		-e TZ=Etc/UTC \
		-p 3000:3000 \
		-p 3001:3001 \
		-p 8000:8000 \
		--restart unless-stopped \
		-v $(shell pwd)/agentd:/config/app/agentd \
		us-docker.pkg.dev/agentsea-dev/agentd/desktop-webtop:latest