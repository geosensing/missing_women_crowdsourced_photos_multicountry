.PHONY: benchmark bib sample sample-images figs note test lint clean

STREETSCOPE ?= ../mw_bikecam_india

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
	python3 scripts/14_combine_rounds.py
	uv run --with matplotlib --with pandas --with jinja2 --with numpy python3 scripts/07_make_note_outputs.py
	python3 scripts/08_pixel_threshold_check.py
	uv run --with pandas --with jinja2 --with numpy python3 scripts/10_eval_calibration.py

	python3 scripts/11_photo_context.py
	python3 scripts/12_resident_population.py

note: figs
	cd ms && latexmk -pdf -interaction=nonstopmode note.tex

test:
	python3 -m unittest discover -s tests

lint:
	python3 -m black --check --line-length 100 scripts/ tests/
	python3 -m isort --check-only --profile black --line-length 100 scripts/ tests/
	python3 -m flake8 --max-line-length 100 scripts/ tests/

clean:
	cd ms && latexmk -c note.tex
