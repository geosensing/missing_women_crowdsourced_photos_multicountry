.PHONY: benchmark bib sample sample-images figs note lint clean

STREETSCOPE ?= ../streetscope

benchmark:
	python3 scripts/01_gpt4o_benchmark.py \
		--input $(STREETSCOPE)/data/mumbai/validation_results.csv

bib:
	python3 scripts/02_build_bibliography.py

sample:
	python3 scripts/03_select_cities.py

sample-images:
	python3 scripts/04_sample_images.py

figs:
	uv run --with matplotlib --with pandas --with numpy python3 scripts/07_make_note_outputs.py
	python3 scripts/08_pixel_threshold_check.py

note: figs
	cd ms && latexmk -pdf -interaction=nonstopmode note.tex

lint:
	python3 -m black --check --line-length 100 scripts/
	python3 -m isort --check-only --profile black --line-length 100 scripts/
	python3 -m flake8 --max-line-length 100 scripts/

clean:
	rm -rf outputs/
