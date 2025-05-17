# Job Search Application Test Suite

This repository contains comprehensive unit tests for a job search application that helps users find and analyze relevant job listings. The tests cover all the major components of the application while avoiding writing to a real database.

## Features

The application has the following features which are thoroughly tested:

- Database management with SQLite
- User authentication and preference management
- Job listing scraping from LinkedIn
- Automated job analysis using OpenAI's API
- Scheduling of automated job search and analysis tasks
- Comprehensive job search and filtering
- Utility functions for formatting and security

## Test Structure

The test suite consists of the following main test files:

1. `test_db_manager.py`: Tests for the database manager singleton class
2. `test_models.py`: Tests for database models and table creation
3. `test_database_service.py`: Tests for database operations service
4. `test_preference_service.py`: Tests for user preference management
5. `test_user_service.py`: Tests for user authentication and management
6. `test_analysis_service.py`: Tests for job analysis with OpenAI
7. `test_scraper_service.py`: Tests for LinkedIn job scraping
8. `test_scheduler_service.py`: Tests for scheduling automated tasks
9. `test_orchestrator_service.py`: Tests for the high-level orchestrator
10. `test_utilities.py`: Tests for utility functions

Additionally, the repository includes:

- `conftest.py`: Pytest fixtures for database setup and sample data

## Testing Approach

The tests are designed with the following principles:

1. **Mock Dependencies**: External services and dependencies are mocked to avoid network calls and external state.
2. **In-Memory Database**: SQLite in-memory database is used for testing database operations.
3. **Component Isolation**: Each component is tested in isolation with mocked dependencies.
4. **Comprehensive Coverage**: All public methods and edge cases are tested.
5. **Fixture Reuse**: Common test fixtures are provided for reuse across test files.

## Running the Tests

### Prerequisites

- Python 3.11 or higher
- pip package manager

### Setup

1. Clone the repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

### Running All Tests

```bash
pytest
```

### Running Specific Test Files

```bash
pytest test_db_manager.py
```

### Running with Coverage

```bash
pytest --cov=.
```

## Test Implementation Details

### Database Tests

- Tests use an in-memory SQLite database to avoid writing to disk
- The singleton pattern of DatabaseManager is tested properly
- Transaction handling, rollback, and connection pooling are verified

### Service Tests

- All service dependencies are mocked
- Tests cover both successful and error scenarios
- State management and complex workflows are thoroughly tested

### Utility Tests

- Formatting functions are tested with various inputs
- Security utilities are tested for correctness and edge cases

## Best Practices Used

- Proper test isolation with setUp and tearDown
- Descriptive test names that indicate what's being tested
- Comprehensive assertions to verify expected behavior
- Mocking external dependencies to ensure unit test isolation
- Parameterized tests for similar test cases with different inputs
- Proper cleanup of resources in tearDown methods

## Contributing

To add or modify tests:

1. Follow the existing test structure and naming conventions
2. Ensure all assertions are meaningful and descriptive
3. Mock all external dependencies
4. Make sure tests don't have side effects on other tests
5. Add appropriate documentation for new test cases

## License

This test suite is provided for educational purposes.
