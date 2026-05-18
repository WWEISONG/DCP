title = "\n---$(shell tput bold)$(shell tput setaf 2)$1 $(shell tput sgr0)\n"

# Docker Desktop on macOS does not require sudo; Linux distros usually do.
# Override with: make DOCKER="sudo docker" build
DOCKER ?= docker

build:
	@echo $(call title, "Building containers........")
	$(DOCKER) compose build

run:
	@echo $(call title, "Running containers.........")
	$(DOCKER) compose up -d

local: build run

clean:
	@echo $(call title, "Cleaning up.................")
	$(DOCKER) compose down --volumes --remove-orphans

client:
	@echo $(call title, "Running client.................")
	$(DOCKER) compose run --entrypoint "python tests/client.py ./tests/A.jpg -o client_volume/signed-images" client
