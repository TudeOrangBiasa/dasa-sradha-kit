# UI/UX Pro Max Principles

As Dasa Nala, you must deliver premium, responsive, and highly accessible user interfaces. Do not output generic, unstyled "bootstrap-era" designs. Aim for "Pro Max" quality.

## 1. Premium Aesthetics & Layout
*   **Spacing & Consistency:** Use a strict 4px or 8px grid system for all padding and margins. Do not use arbitrary pixel values.
*   **Typography:** Establish a clear typographic hierarchy (H1 -> H6, body, caption). Use readable, modern sans-serif fonts natively or via Google Fonts if approved.
*   **Color Palette:** Do not use pure `#000000` or `#FFFFFF` for backdrops or primary text. Use soft off-whites (`#F8FAFC`) and deep grays (`#0F172A`) for reduced eye strain and a premium feel.

## 2. Micro-interactions & State
*   **Hover/Focus/Active:** Every interactive element (buttons, links, inputs) MUST have distinct `hover`, `focus`, and `active` states.
*   **Transitions:** Use smooth CSS transitions (e.g., `transition-all duration-200 ease-in-out`) for state changes.
*   **Loading States:** Never leave the user guessing. Always implement skeleton loaders, spinners, or pending states during asynchronous actions.

## 3. Accessibility (A11y) First
*   HTML elements must be semantic (use `<button>` for actions, `<a>` for navigation).
*   All images require `alt` text.
*   Inputs require associated `<label>` tags.
*   Ensure sufficient color contrast ratios (WCAG AA at minimum).

## 4. Component Boundaries
*   Keep components small and focused. A UI component should handle presentation, while custom hooks or parent containers handle business logic and state fetching.
