---
description: Autonomously generate realistic database fixtures and UI seed data. Example: /dasa-seed "Generate 50 realistic users and 200 blog posts"
---

```bash
if [ ! -f .dasa-sradha ]; then
  echo "This repository is not initialized. Run /dasa-init first."
  exit 1
fi
```

# Native Database Seeder Workflow

This workflow uses a 3-agent orchestration chain to generate highly realistic, production-ready fake data for local testing and UI development.

- **Phase 1: Dasa Dwipa (The Scout)**
  Assume the identity of Dasa Dwipa.
  Sweep the current codebase specifically looking for the active Database Schema (e.g., `schema.sql`, `prisma/schema.prisma`, `database/migrations/`, or active Mongoose models).
  Read the schema definitions to establish exactly what columns, types, and foreign key relationships exist. Do NOT modify any code.

- **Phase 2: Dasa Mpu (The Architect)**
  Assume the identity of Dasa Mpu.
  Read Dwipa's extracted database schema and the user's `$ARGUMENTS`.
  Generate a massively dense, highly realistic JSON file adhering perfectly to the schema. Do not use generic "test1" data. Use robust, varied simulated data (e.g., realistic names, emails, UUIDs, dates, and prose).
  Save this mock data to `.artifacts/active-seed-data.json`.

- **Phase 3: Dasa Nala (The Builder)**
  Assume the identity of Dasa Nala.
  Read the generated `.artifacts/active-seed-data.json`.
  Your goal is to inject this data into the active application. 
  If the user's tech stack (check `.agent/dasa.config.toon`) supports native seeders (e.g., Laravel's `artisan db:seed`, Prisma's `seed.ts`), write the necessary code to consume the JSON file and execute the seeder.
  If the application is strictly a frontend, ensure the mock JSON file is correctly wired into the local state management or API mocking layer (e.g., MSW or Redux).
  
- **Phase 4: Completion**
  Stop and tell the user: "Proses Seeding Database selesai. Data fiktif yang realistis telah dibuat dan dimasukkan ke dalam lingkungan pengembangan (Development Environment) Anda."
