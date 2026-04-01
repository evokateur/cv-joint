.PHONY: install uninstall test test-all clean cv upwork-cv cover-letter

OPEN =
ifeq ($(shell uname), Darwin)
OPEN = open
else ifeq ($(shell uname), Linux)
OPEN = xdg-open
endif

install:
	uv tool install --editable .

uninstall:
	uv tool uninstall cv-joint

cv:
	uv run build-cv data/cv.yaml output/cv.tex
	uv run pdflatex --output-directory=output output/cv.tex
	@if [ -n "$(OPEN)" ]; then $(OPEN) output/cv.pdf; fi

upwork-cv:
	uv run build-cv data/cv.yaml output/upwork-cv.tex --template upwork-cv.tex
	uv run pdflatex --output-directory=output output/upwork-cv.tex
	@if [ -n "$(OPEN)" ]; then $(OPEN) output/upwork-cv.pdf; fi

cover-letter:
	uv run build-cover-letter data/cover-letter.json output/cover-letter.tex
	uv run pdflatex --output-directory=output output/cover-letter.tex
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
