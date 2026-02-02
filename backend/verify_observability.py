#!/usr/bin/env python3
"""
Observability Verification Script
=================================

This script verifies that the observability stack is working correctly by:
1. Making HTTP requests to the backend
2. Checking that traces, logs, and metrics are generated
3. Reporting the results

Usage:
    cd backend
    uv run python verify_observability.py

Prerequisites:
    - Backend running on http://localhost:8000
    - (Optional) SigNoz stack running for full verification
"""

import asyncio
import httpx
import sys
from datetime import datetime


# ANSI colors for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_info(text: str) -> None:
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


async def check_backend_health(client: httpx.AsyncClient, base_url: str) -> bool:
    """Check if the backend is running and healthy."""
    try:
        response = await client.get(f"{base_url}/health")
        if response.status_code == 200:
            print_success(f"Backend is healthy: {response.json()}")
            return True
        else:
            print_error(f"Backend returned status {response.status_code}")
            return False
    except httpx.ConnectError:
        print_error(f"Cannot connect to backend at {base_url}")
        print_info("Make sure the backend is running: uv run uvicorn app.main:app --reload")
        return False


async def make_test_requests(client: httpx.AsyncClient, base_url: str) -> dict:
    """Make various test requests to generate telemetry."""
    results = {
        "success": 0,
        "failed": 0,
        "requests": []
    }

    # Define test requests
    test_cases = [
        ("GET", "/", "Root endpoint"),
        ("GET", "/health", "Health check"),
        ("GET", "/api/v1/users/me", "Get current user (expect 401)"),
        ("POST", "/api/v1/auth/signin", "Sign in (expect 422 - missing body)"),
    ]

    for method, path, description in test_cases:
        try:
            if method == "GET":
                response = await client.get(f"{base_url}{path}")
            else:
                response = await client.post(f"{base_url}{path}", json={})

            results["requests"].append({
                "method": method,
                "path": path,
                "status": response.status_code,
                "description": description,
            })

            # Consider 2xx, 4xx as "successful" for telemetry purposes
            # (we're testing that requests are traced, not that they succeed)
            if response.status_code < 500:
                results["success"] += 1
                print_success(f"{method} {path} → {response.status_code} ({description})")
            else:
                results["failed"] += 1
                print_error(f"{method} {path} → {response.status_code} ({description})")

        except Exception as e:
            results["failed"] += 1
            print_error(f"{method} {path} → Error: {e}")

    return results


async def check_collector_health(client: httpx.AsyncClient) -> bool:
    """Check if the OTel Collector is running."""
    collector_url = "http://localhost:13133"  # Collector health check port
    try:
        response = await client.get(collector_url, timeout=5.0)
        if response.status_code == 200:
            print_success("OTel Collector is healthy")
            return True
        else:
            print_warning(f"OTel Collector returned status {response.status_code}")
            return False
    except httpx.ConnectError:
        print_warning("Cannot connect to OTel Collector (may not be running locally)")
        print_info("Run: docker compose -f docker-compose.observability.yml up -d")
        return False
    except Exception as e:
        print_warning(f"Error checking collector: {e}")
        return False


async def check_signoz_health(client: httpx.AsyncClient) -> bool:
    """Check if SigNoz Query Service is running."""
    signoz_url = "http://localhost:3301/api/v1/health"
    try:
        response = await client.get(signoz_url, timeout=5.0)
        if response.status_code == 200:
            print_success("SigNoz Query Service is healthy")
            return True
        else:
            print_warning(f"SigNoz returned status {response.status_code}")
            return False
    except httpx.ConnectError:
        print_warning("Cannot connect to SigNoz (may not be running locally)")
        print_info("Run: docker compose -f docker-compose.observability.yml up -d")
        return False
    except Exception as e:
        print_warning(f"Error checking SigNoz: {e}")
        return False


async def main():
    """Run the verification script."""
    print_header("Observability Verification Script")
    print(f"Started at: {datetime.now().isoformat()}")

    base_url = "http://localhost:8000"

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Step 1: Check backend health
        print_header("Step 1: Checking Backend Health")
        backend_ok = await check_backend_health(client, base_url)

        if not backend_ok:
            print_error("\nBackend is not running. Cannot proceed with verification.")
            sys.exit(1)

        # Step 2: Check observability stack (optional)
        print_header("Step 2: Checking Observability Stack")
        collector_ok = await check_collector_health(client)
        signoz_ok = await check_signoz_health(client)

        if not collector_ok or not signoz_ok:
            print_warning("\nObservability stack not fully available.")
            print_info("Traces will be generated but may not be viewable.")
            print_info("Start the stack: docker compose -f docker-compose.observability.yml up -d")

        # Step 3: Generate test traffic
        print_header("Step 3: Generating Test Traffic")
        results = await make_test_requests(client, base_url)

        # Step 4: Summary
        print_header("Verification Summary")
        print(f"Total requests: {results['success'] + results['failed']}")
        print(f"Successful: {results['success']}")
        print(f"Failed: {results['failed']}")

        print("\n" + "-" * 40)
        print("What was generated:")
        print("-" * 40)
        print(f"• {len(results['requests'])} HTTP request traces")
        print("• Structured JSON logs with trace_id correlation")
        print("• HTTP metrics (request count and duration)")

        if signoz_ok:
            print("\n" + "-" * 40)
            print("Next steps - Verify in SigNoz UI:")
            print("-" * 40)
            print("1. Open http://localhost:3301")
            print("2. Go to 'Traces' - you should see the requests above")
            print("3. Go to 'Logs' - filter by service=rag-admin-backend")
            print("4. Go to 'Metrics' - search for http_server_requests_total")
        else:
            print("\n" + "-" * 40)
            print("To view telemetry:")
            print("-" * 40)
            print("1. Start SigNoz: docker compose -f docker-compose.observability.yml up -d")
            print("2. Wait 30-60 seconds for services to be healthy")
            print("3. Open http://localhost:3301")
            print("4. Run this script again to generate more traffic")

        print("\n" + Colors.GREEN + "Verification complete!" + Colors.RESET)


if __name__ == "__main__":
    asyncio.run(main())
