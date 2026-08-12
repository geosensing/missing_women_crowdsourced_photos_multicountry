.PHONY: benchmark bib lint clean

STREETSCOPE ?= ../streetscope

benchmark:
	python3 scripts/01_gpt4o_benchmark.py \
		--input $(STREETSCOPE)/data/mumbai/validation_results.csv

bib:
	python3 scripts/02_build_bibliography.py

lint:
	python3 -m black --check --line-length 100 scripts/
	python3 -m isort --check-only --profile black --line-length 100 scripts/
	python3 -m flake8 --max-line-length 100 scripts/

clean:
	rm -rf outputs/
