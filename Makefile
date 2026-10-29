.PHONY: docs check

docs:
	@if command -v tree >/dev/null 2>&1; then tree docs; else find docs -type f | sort; fi

check:
	python3 -m unittest discover -s scripts -p 'test_*.py'
	python3 scripts/check_docs.py
