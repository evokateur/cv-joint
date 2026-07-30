.PHONY: install reinstall uninstall test test-all clean

install:
	uv tool install --editable .

reinstall:
	uv tool install --editable --reinstall .

uninstall:
	uv tool uninstall cv-joint

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
