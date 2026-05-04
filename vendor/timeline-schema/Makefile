PKG := $(CURDIR)

.PHONY: install build gen test check check-codegen clean

install:
	npm install
	pip install -e python
	pip install datamodel-code-generator

build:
	npm run build

gen:
	python scripts/gen_python_types.py

test:
	npm test
	cd python && python -m unittest discover -s ../tests

check: check-codegen test

check-codegen:
	bash scripts/check-codegen.sh

clean:
	rm -rf typescript/dist node_modules
	rm -f python/banodoco_timeline_schema/generated.py
	rm -f python/banodoco_timeline_schema/timeline.schema.json
