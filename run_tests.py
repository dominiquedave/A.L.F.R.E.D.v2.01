#!/usr/bin/env python3
"""
A.L.F.R.E.D. Test Runner Script

This script provides a comprehensive test runner that handles:
- Unit test execution with coverage reporting
- Code formatting with Black
- Import sorting with isort
- Linting with flake8
- Pre-commit hook management

Usage:
    python run_tests.py                    # Run all tests with coverage
    python run_tests.py --unit             # Run only unit tests
    python run_tests.py --format           # Format code with Black and isort
    python run_tests.py --lint             # Run linting checks
    python run_tests.py --install-hooks    # Install pre-commit hooks
    python run_tests.py --all              # Run tests, format, and lint
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output"""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_header(message):
    """Print a formatted header message"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_success(message):
    """Print a success message"""
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")


def print_error(message):
    """Print an error message"""
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")


def print_warning(message):
    """Print a warning message"""
    print(f"{Colors.WARNING}⚠ {message}{Colors.ENDC}")


def run_command(command, description, capture_output=False):
    """
    Run a shell command and handle output

    Args:
        command: Command to run as string or list
        description: Human readable description of the command
        capture_output: If True, capture output instead of streaming

    Returns:
        True if command succeeded, False otherwise
    """
    print(f"{Colors.OKCYAN}Running: {description}{Colors.ENDC}")

    try:
        if capture_output:
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            if result.stdout:
                print(result.stdout)
        else:
            result = subprocess.run(command, shell=True, check=True)

        print_success(f"{description} completed successfully")
        return True

    except subprocess.CalledProcessError as e:
        print_error(f"{description} failed with exit code {e.returncode}")
        if capture_output and e.stderr:
            print(f"Error output: {e.stderr}")
        return False


def install_test_dependencies():
    """Install test dependencies"""
    print_header("Installing Test Dependencies")

    # Install test requirements
    success = run_command("pip install -r requirements-test.txt", "Installing test dependencies")

    if success:
        print_success("Test dependencies installed successfully")
    else:
        print_error("Failed to install test dependencies")

    return success


def run_unit_tests(coverage=True):
    """Run unit tests with optional coverage"""
    print_header("Running Unit Tests")

    if coverage:
        command = "pytest tests/unit/ -v --cov=shared --cov=agent --cov=coordinator --cov-report=term-missing --cov-report=html"
        description = "Unit tests with coverage"
    else:
        command = "pytest tests/unit/ -v"
        description = "Unit tests without coverage"

    success = run_command(command, description)

    if success:
        print_success("Unit tests passed")
        if coverage:
            print(f"{Colors.OKCYAN}Coverage report generated in htmlcov/index.html{Colors.ENDC}")
    else:
        print_error("Unit tests failed")

    return success


def run_integration_tests():
    """Run integration tests"""
    print_header("Running Integration Tests")

    if not os.path.exists("tests/integration"):
        print_warning("No integration tests found, skipping...")
        return True

    success = run_command("pytest tests/integration/ -v --tb=short", "Integration tests")

    if success:
        print_success("Integration tests passed")
    else:
        print_error("Integration tests failed")

    return success


def format_code():
    """Format code with Black and isort"""
    print_header("Formatting Code")

    success = True

    # Run Black
    black_success = run_command(
        "black --line-length 100 shared/ agent/ coordinator/ tests/", "Formatting code with Black"
    )

    # Run isort
    isort_success = run_command(
        "isort --profile black --line-length 100 shared/ agent/ coordinator/ tests/",
        "Sorting imports with isort",
    )

    success = black_success and isort_success

    if success:
        print_success("Code formatting completed")
    else:
        print_error("Code formatting had issues")

    return success


def run_linting():
    """Run code linting with flake8"""
    print_header("Running Linting")

    success = run_command(
        "flake8 --max-line-length=100 --ignore=E203,W503,E501 shared/ agent/ coordinator/",
        "Linting code with flake8",
    )

    if success:
        print_success("Linting passed")
    else:
        print_error("Linting found issues")

    return success


def install_pre_commit_hooks():
    """Install pre-commit hooks"""
    print_header("Installing Pre-commit Hooks")

    success = True

    # Install pre-commit
    install_success = run_command("pip install pre-commit", "Installing pre-commit")

    # Install hooks
    hooks_success = run_command("pre-commit install", "Installing pre-commit hooks")

    success = install_success and hooks_success

    if success:
        print_success("Pre-commit hooks installed")
        print(f"{Colors.OKCYAN}Hooks will now run automatically on git commit{Colors.ENDC}")
    else:
        print_error("Failed to install pre-commit hooks")

    return success


def check_coverage():
    """Check if coverage meets minimum requirements"""
    print_header("Checking Coverage Requirements")

    success = run_command(
        "coverage report --fail-under=80", "Checking 80% coverage requirement", capture_output=True
    )

    if success:
        print_success("Coverage requirements met (≥80%)")
    else:
        print_error("Coverage requirements not met (<80%)")
        print_warning("Consider adding more tests to improve coverage")

    return success


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description="A.L.F.R.E.D. Test Runner")
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--format", action="store_true", help="Format code with Black and isort")
    parser.add_argument("--lint", action="store_true", help="Run linting checks")
    parser.add_argument("--install-hooks", action="store_true", help="Install pre-commit hooks")
    parser.add_argument("--install-deps", action="store_true", help="Install test dependencies")
    parser.add_argument("--coverage", action="store_true", help="Check coverage requirements")
    parser.add_argument("--all", action="store_true", help="Run tests, format, and lint")
    parser.add_argument("--no-coverage", action="store_true", help="Run tests without coverage")

    args = parser.parse_args()

    # Print banner
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("    ╔═══════════════════════════════════════════════════════════════╗")
    print("    ║                    A.L.F.R.E.D. Test Runner                  ║")
    print("    ║              Advanced Testing & Quality Assurance            ║")
    print("    ╚═══════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")

    # Track overall success
    overall_success = True

    # Handle specific operations
    if args.install_deps:
        overall_success &= install_test_dependencies()

    if args.install_hooks:
        overall_success &= install_pre_commit_hooks()

    if args.format:
        overall_success &= format_code()

    if args.lint:
        overall_success &= run_linting()

    if args.unit:
        overall_success &= run_unit_tests(coverage=not args.no_coverage)

    if args.integration:
        overall_success &= run_integration_tests()

    if args.coverage:
        overall_success &= check_coverage()

    if args.all:
        overall_success &= format_code()
        overall_success &= run_linting()
        overall_success &= run_unit_tests(coverage=not args.no_coverage)
        overall_success &= run_integration_tests()
        overall_success &= check_coverage()

    # Default behavior: run tests with coverage
    if not any(
        [
            args.unit,
            args.integration,
            args.format,
            args.lint,
            args.install_hooks,
            args.install_deps,
            args.coverage,
            args.all,
        ]
    ):
        overall_success &= run_unit_tests(coverage=not args.no_coverage)
        if not args.no_coverage:
            overall_success &= check_coverage()

    # Print final results
    print_header("Test Runner Summary")

    if overall_success:
        print_success("All operations completed successfully! 🎉")
        sys.exit(0)
    else:
        print_error("Some operations failed. Please check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
