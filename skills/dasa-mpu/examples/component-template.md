# Dasa Mpu Component Template Guidelines
**Owner: Dasa Mpu (The Implementer)**

When required to build User Interface components for an application, use the following generic structural template. This ensures separation of concerns, readability, and immediate readiness for testing by Dwipa.

## React / Next.js Component Structure

```tsx
import React, { useState, useEffect } from 'react';
// 1. Imports (External libraries first, internal second)
import { Button } from '@/components/ui';
import { fetchUserDetails } from '@/services/api';

// 2. Interfaces / Types
interface UserProfileProps {
  userId: string;
  className?: string;
}

// 3. Component Definition
export const UserProfile: React.FC<UserProfileProps> = ({ userId, className }) => {
  // A. State & Refs
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // B. Effects & Lifecycle
  useEffect(() => {
    // Data fetching logic here
  }, [userId]);

  // C. Helper / Event Handlers
  const handleAction = () => {
    // Event execution logic
  };

  // D. Render (Early returns for loading/error states)
  if (loading) return <div>Loading...</div>;

  // E. Main render (Using semantic HTML and accessible attributes)
  return (
    <section className={`p-4 bg-white rounded shadow ${className}`}>
      <header>
        <h2>{data?.name}</h2>
      </header>
      <main>
        {/* Component Body */}
        <Button onClick={handleAction}>Edit Profile</Button>
      </main>
    </section>
  );
};

export default UserProfile;
```

## Core Mpu Directives
- **Separation:** Keep heavy business logic outside directly executed render paths.
- **Accessibility:** Always include alt tags, aria-labels, and semantic HTML5 tags (`<main>`, `<section>`, `<nav>`).
- **Styling:** Rely on the framework established in `.agent/dasa.config.toon` (e.g., Tailwind classes). Do not mix CSS-in-JS and inline styles unless required.
