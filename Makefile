.PHONY: install reinstall uninstall test test-all clean cv upwork-cv cover-letter

OPEN =
ifeq ($(shell uname), Darwin)
OPEN = open
else ifeq ($(shell uname), Linux)
OPEN = xdg-open
endif

install:
	uv tool install --editable .

reinstall:
	uv tool install --editable --reinstall .

uninstall:
	uv tool uninstall cv-joint

cv:
	uv run cv-joint render cv data/cv.yaml -o output/cv.pdf
	@if [ -n "$(OPEN)" ]; then $(OPEN) output/cv.pdf; fi

upwork-cv:
	uv run cv-joint render cv data/cv.yaml --template upwork-cv.tex -o output/upwork-cv.pdf
	@if [ -n "$(OPEN)" ]; then $(OPEN) output/upwork-cv.pdf; fi

cover-letter:
	uv run cv-joint render cover-letter data/cover-letter.json -o output/cover-letter.pdf
	@if [ -n "$(OPEN)" ]; then $(OPEN) output/cover-letter.pdf; fi

clean:
	echo "Cleaning up pdflatex build artifacts..."
	rm -f output/*.aux
	rm -f output/*.fdb_latexmk
	rm -f output/*.fls
	rm -f output/*.log
	rm -f output/*.out
	rm -f output/*.synctex.gz

test:
	uv run pytest tests/ --tb=short

test-all:
	uv run pytest tests/ --tb=short -m ""
