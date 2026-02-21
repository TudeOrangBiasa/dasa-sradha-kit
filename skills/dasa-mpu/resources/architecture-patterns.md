# Architecture & Backend Patterns

As Dasa Mpu, you define the structural integrity of the project. You must enforce predictable, layered, and scalable architectural patterns.

## 1. Layered Architecture (Domain-Driven Design)
Separate concerns explicitly. A standard backend should follow these layers:
*   **Controllers / API Routes:** Handle HTTP requests, parse inputs, and format responses. No business logic belongs here.
*   **Services / Use Cases:** Contain the core business logic. They orchestrate data flow but do not directly query the database.
*   **Repositories / Data Access:** Handle all database queries, ORM interactions, and third-party API fetches.

## 2. API Design & RESTful Standards
*   Use noun-based endpoint paths (e.g., `/users`, strictly plural).
*   Return standard HTTP status codes (`200 OK`, `201 Created`, `400 Bad Request`, `401 Unauthorized`, `404 Not Found`, `500 Server Error`).
*   Paginate collection endpoints by default (e.g., `?limit=20&page=1`).
*   Return structured error formats commonly modeled as `{ "error": { "code": "...", "message": "..." } }`.

## 3. Database Design Patterns
*   Normalize databases for transactional (OLTP) workloads to avoid data anomalies.
*   Use UUIDv4 or ULID for primary keys in distributed systems.
*   Always include `created_at` and `updated_at` timestamps on all tables.
*   Design indexes based heavily on the read-access patterns.

## 4. Security by Architecture
*   Never store secrets in code. Assume all environment variables will be injected seamlessly.
*   Implement explicit rate-limiting and CORS boundaries at the API gateway or entry point level.
