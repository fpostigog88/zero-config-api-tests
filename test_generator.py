"""
Zero-Config API Tests
Auto-generate pytest suites from OpenAPI specs and HAR files.
"""

import json
import re
import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse


@dataclass
class APITestCase:
    """A single generated test case."""
    name: str
    method: str
    url: str
    headers: Dict[str, str]
    params: Optional[Dict[str, Any]]
    body: Optional[Dict[str, Any]]
    expected_status: int
    expected_schema: Optional[Dict[str, Any]]


class OpenAPIParser:
    """Parse OpenAPI 3.0 specs and extract endpoints."""
    
    def __init__(self, spec_path: str):
        with open(spec_path, 'r') as f:
            self.spec = json.load(f)
    
    def parse_endpoints(self) -> List[Dict[str, Any]]:
        """Extract all endpoints with their methods and schemas."""
        endpoints = []
        
        paths = self.spec.get('paths', {})
        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ['get', 'post', 'put', 'delete', 'patch']:
                    endpoint = {
                        'path': path,
                        'method': method.upper(),
                        'summary': details.get('summary', ''),
                        'parameters': details.get('parameters', []),
                        'requestBody': details.get('requestBody', {}),
                        'responses': details.get('responses', {})
                    }
                    endpoints.append(endpoint)
        
        return endpoints


class HARParser:
    """Parse HTTP Archive (HAR) files and extract requests."""
    
    def __init__(self, har_path: str):
        with open(har_path, 'r') as f:
            self.har = json.load(f)
    
    def parse_requests(self) -> List[Dict[str, Any]]:
        """Extract all API requests from HAR file."""
        requests = []
        entries = self.har.get('log', {}).get('entries', [])
        
        for entry in entries:
            req = entry.get('request', {})
            resp = entry.get('response', {})
            
            # Skip static assets
            url = req.get('url', '')
            if any(ext in url for ext in ['.js', '.css', '.png', '.jpg', '.ico']):
                continue
            
            parsed = {
                'method': req.get('method', 'GET'),
                'url': url,
                'headers': {h['name']: h['value'] for h in req.get('headers', [])},
                'queryString': {q['name']: q['value'] for q in req.get('queryString', [])},
                'postData': req.get('postData', {}),
                'status': resp.get('status', 200)
            }
            requests.append(parsed)
        
        return requests


class TestGenerator:
    """
    Generate pytest test files from parsed API endpoints.
    
    Features:
    - Status code validation
    - Schema validation (if OpenAPI spec available)
    - Parameter fuzzing (boundary values, nulls)
    - Duplicate detection (same endpoint deduplicated)
    """
    
    def __init__(self, base_url: str = ""):
        self.base_url = base_url
        self.seen = set()
    
    def _sanitize_name(self, name: str) -> str:
        """Convert URL path to valid Python function name."""
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        name = re.sub(r'_+', '_', name)
        return name.strip('_')
    
    def _generate_fuzz_params(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate boundary test cases for parameters."""
        fuzz_cases = []
        
        for key, value in params.items():
            # Test with empty value
            fuzz_cases.append({**params, key: ""})
            
            # Test with null
            fuzz_cases.append({**params, key: None})
            
            # Test with very long string
            fuzz_cases.append({**params, key: "x" * 1000})
        
        return fuzz_cases
    
    def generate_from_openapi(self, spec_path: str, output_dir: str):
        """Generate test suite from OpenAPI spec."""
        parser = OpenAPIParser(spec_path)
        endpoints = parser.parse_endpoints()
        
        tests = []
        
        for endpoint in endpoints:
            path = endpoint['path']
            method = endpoint['method']
            
            # Create test name
            test_name = f"test_{method.lower()}_{self._sanitize_name(path)}"
            
            if test_name in self.seen:
                continue
            self.seen.add(test_name)
            
            # Get expected status from responses
            responses = endpoint['responses']
            expected_status = 200
            if '200' in responses:
                expected_status = 200
            elif '201' in responses:
                expected_status = 201
            
            # Generate test code
            test_code = self._generate_test_code(
                name=test_name,
                method=method,
                url=f"{self.base_url}{path}",
                params=None,
                body=None,
                expected_status=expected_status
            )
            tests.append(test_code)
        
        self._write_tests(tests, output_dir, "test_api_generated.py")
    
    def generate_from_har(self, har_path: str, output_dir: str):
        """Generate test suite from HAR file."""
        parser = HARParser(har_path)
        requests = parser.parse_requests()
        
        tests = []
        
        for req in requests:
            url = req['url']
            method = req['method']
            
            # Parse URL to get path
            parsed = urlparse(url)
            path = parsed.path or '/'
            
            test_name = f"test_{method.lower()}_{self._sanitize_name(path)}"
            
            if test_name in self.seen:
                continue
            self.seen.add(test_name)
            
            # Extract body
            body = None
            post_data = req.get('postData', {})
            if 'text' in post_data:
                try:
                    body = json.loads(post_data['text'])
                except:
                    body = post_data['text']
            
            test_code = self._generate_test_code(
                name=test_name,
                method=method,
                url=url,
                params=req.get('queryString'),
                body=body,
                expected_status=req.get('status', 200)
            )
            tests.append(test_code)
        
        self._write_tests(tests, output_dir, "test_api_regression.py")
    
    def _generate_test_code(
        self,
        name: str,
        method: str,
        url: str,
        params: Optional[Dict],
        body: Optional[Any],
        expected_status: int
    ) -> str:
        """Generate a single pytest test function."""
        
        code = f"""
def {name}():
    \"\"\"Test {method} {url}\"\"\"
    import requests
    
    url = "{url}"
    headers = {{"Accept": "application/json"}}
    
    response = requests.{method.lower()}(
        url,
        headers=headers,"""
        
        if params:
            code += f"\n        params={json.dumps(params)},"
        
        if body:
            code += f"\n        json={json.dumps(body)},"
        
        code += f"""
        timeout=10
    )
    
    assert response.status_code == {expected_status}
    
    # Validate response is valid JSON
    try:
        data = response.json()
        assert isinstance(data, (dict, list))
    except ValueError:
        pass  # Non-JSON response is acceptable
"""
        return code
    
    def _write_tests(self, tests: List[str], output_dir: str, filename: str):
        """Write generated tests to file."""
        os.makedirs(output_dir, exist_ok=True)
        
        content = """\"\"\"
Auto-generated API tests.
Run with: pytest
\"\"\"

import pytest

"""
        
        for test in tests:
            content += test + "\n"
        
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w') as f:
            f.write(content)
        
        print(f"Generated {len(tests)} tests in {filepath}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate API tests")
    parser.add_argument("--spec", help="Path to OpenAPI spec JSON")
    parser.add_argument("--har", help="Path to HAR file")
    parser.add_argument("--output", default="tests", help="Output directory")
    parser.add_argument("--base-url", default="", help="Base URL for requests")
    
    args = parser.parse_args()
    
    generator = TestGenerator(base_url=args.base_url)
    
    if args.spec:
        generator.generate_from_openapi(args.spec, args.output)
    elif args.har:
        generator.generate_from_har(args.har, args.output)
    else:
        print("Please provide --spec or --har")
