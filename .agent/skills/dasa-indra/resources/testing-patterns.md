# Testing Patterns & QA Rules

As Dasa Indra, your duty is to ensure the reliability and resilience of the system. You must enforce thorough and efficient testing patterns.

## 1. Unit Testing
*   **Isolate Logic:** Unit tests should test pure functions, complex algorithms, or isolated components without mocking massive dependency trees. If mocking takes more than 10 lines of code, the architecture is flawed.
*   **Arrange, Act, Assert:** Group tests logically into an AAA (Arrange, Act, Assert) structure.
*   **Edge Cases:** Focus heavily on nulls, undefined values, out-of-bounds inputs, and empty states. Do not merely test the "happy path."

## 2. Integration Testing
*   Test how modules interact with databases and external services.
*   Use actual test databases (e.g., testcontainers, in-memory instances) instead of mocking repositories, unless connecting is fundamentally impossible.
*   Verify side effects. If an API creates a user, verify the user actually exists in the database.

## 3. End-to-End (E2E) Testing
*   Write E2E tests focusing on core user journeys (e.g., "User can sign up and verify email"). Do not test every minor button click.
*   Wait for visual changes (e.g., "spinner disappears," "toast notification appears") before assertions to prevent flaky tests.
*   Do not rely on unstable CSS selectors (like `#app > div:nth-child(3)`). Use predictable `.test-*`, `data-testid`, or native semantic element selectors.

## 4. General Assertions Rule
*   Do not assert multiple unrelated outcomes in a single test block.
*   Clear database state and mock calls aggressively between tests in the `beforeEach` or `afterEach` cycle.
