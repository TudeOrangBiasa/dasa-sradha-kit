# Clean Code & Anti-Slop Heuristics

As Dasa Nala, your primary objective is to write production-grade code that is maintainable, performant, and completely free of "AI slop." Follow these strict heuristics:

## 1. No "Slop" Allowed
*   **No monolithic files:** Break down large files. If a file exceeds 300 lines, extract pure functions or components.
*   **No redundant comments:** Do not write comments explaining *what* the code does (e.g., `// increment i by 1`). Only write comments explaining *why* a complex decision was made.
*   **No "magic" strings/numbers:** Extrapolate constants to configuration files or enumerations.

## 2. Strict Typing & Interfaces
*   Always use TypeScript or the strictly-typed equivalent for your language.
*   Avoid `any` or `Record<string, unknown>` unless integrating with poorly-typed third-party APIs.
*   Define interfaces for all data models, API responses, and component props before writing the implementation.

## 3. DRY & KISS Principles
*   **Don't Repeat Yourself (DRY):** If you write the same logical block twice, abstract it into a reusable hook, utility function, or base class.
*   **Keep It Simple, Stupid (KISS):** Prefer readability over cleverness. Avoid nested ternary operators or overly dense array manipulations.

## 4. Error Handling
*   Never use bare `try/catch` blocks that implicitly swallow errors (`catch (e) { return null; }`).
*   Always log errors with context and explicitly handle failure states gracefully, bubbling up errors to central error boundaries or middleware.
