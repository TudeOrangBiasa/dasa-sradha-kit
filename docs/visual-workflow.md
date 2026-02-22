# Visual Design Workflow (v5.1)

The Dasa Sradha Kit supports a "Visual-to-Code" workflow. This allows Dasa Nala to natively convert Figma designs (mockups, screenshots) into high-fidelity UI code without requiring massive vision-context blowout in the LLM.

## Workflow Execution

### 1. Export Designs
- Take your Figma mockups, screenshots, or any visual reference.
- Export them as PNG, JPG, or WebP.

### 2. Place in Reference Directory
- Drop those images directly into:
  ```
  .design-memory/reference/
  ```

### 3. Organic AI Analysis
You no longer need to write a massive prompt explaining your design. Just say:

> "Build the homepage using the designs I placed in the reference folder."

The baseline AI (with Zero-Command Orchestration) will automatically:
1. Trigger **Dasa Mpu** to analyze the images.
2. Formulate the UI component tree in `.artifacts/architecture-state.toon`.
3. Auto-trigger `design_memory_sync.py` to compress the visual knowledge into text semantic TOONs.
4. Pass the compressed semantics to **Dasa Nala** who writes the Next.js/React/Astro code.

### Bypassing Vision Blowout
Because LLMs have limited, expensive context windows, Dasa Sradha avoids passing 20 raw PNGs into every turn. Instead:
- Raw PNGs stay in `.design-memory/reference/`.
- `design_engine.py` restricts spacing, corners, and palettes to prevent hallucination.
- `design_memory_sync.py` bridges the visual-to-text gap internally.
