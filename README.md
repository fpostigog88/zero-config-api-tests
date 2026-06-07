# Zero-Config API Tests

Auto-generate API test suites from OpenAPI specs and HAR files. No manual test writing.

## Why This Exists

Writing API tests is tedious. Most endpoints follow patterns from their spec. This tool reads your OpenAPI spec or HAR recording and generates a complete pytest suite with edge cases, parameter fuzzing, and response validation.

## Features

- **OpenAPI Ingestion**: Parse Swagger/OpenAPI 3.0 specs and generate tests
- **HAR Replay**: Record browser traffic, generate regression tests
- **Parameter Fuzzing**: Test boundary values, nulls, and type mismatches
- **Response Validation**: Validate status codes, schemas, and headers
- **pytest Output**: Generated code is plain pytest, fully editable

## Quick Start

```bash
# From OpenAPI spec
python generate_tests.py --spec openapi.json --output tests/

# From HAR file
python generate_tests.py --har recording.har --output tests/

# Run generated tests
cd tests && pytest
```

## Architecture

Generator pipeline: `Parse → Analyze → Template → Write`. Each stage is a plugin.

Built by [Felipe Postigo](https://www.felipepostigo.com)
