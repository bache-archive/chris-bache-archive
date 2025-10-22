ENV_FILE=tools/.env

.PHONY: init harvest open doc

init:
	@[ -f $(ENV_FILE) ] || cp tools/.env.example $(ENV_FILE)
	@echo "Edit $(ENV_FILE) with real hosts/keys."

harvest:
	python3 tools/harvest_quote_packs.py

open:
	@echo "Open docs/educational to curate:"
	@ls -1 docs/educational

doc:
	@echo "Edit docs/educational/$$id/index.md + keep sources.json for provenance."
	@echo "Usage: make doc id=shamanic-persona"
