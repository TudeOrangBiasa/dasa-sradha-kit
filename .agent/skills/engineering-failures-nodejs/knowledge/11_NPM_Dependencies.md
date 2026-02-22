# Domain 11: NPM Và Dependencies

> Node.js patterns liên quan đến NPM: supply chain, lockfiles, semver, bundle size, native addons, CVE.

---

## Pattern 01: Supply Chain Attack

### Tên
Supply Chain Attack (Malicious Package)

### Phân loại
Dependencies / Security / Supply Chain

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề
Malicious code injected into dependency (e.g., event-stream, colors). Runs on install or import.

### Phát hiện
```bash
rg "postinstall|preinstall" -n --glob "package.json"
```

### Giải pháp
```bash
npm audit --production
# .npmrc:
# ignore-scripts=true
```

### Phòng ngừa
- [ ] `npm audit` in CI
- [ ] `ignore-scripts=true` in `.npmrc`
- Tool: `socket.dev`, `snyk`

---

## Pattern 02: Dependency Confusion

### Tên
Dependency Confusion (Private/Public Name Clash)

### Phân loại
Dependencies / Security / Registry

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề
Attacker publishes higher-version package with same name as private package on public npm.

### Phát hiện
```bash
rg "@\w+/" -n --glob "package.json"
rg "registry" -n --glob ".npmrc"
```

### Giải pháp
```ini
# .npmrc:
@mycompany:registry=https://npm.mycompany.com/
```

### Phòng ngừa
- [ ] Scoped registry in `.npmrc`
- [ ] Claim scope on public npm
- Tool: `.npmrc` scoped registries

---

## Pattern 03: Lockfile Không Commit

### Tên
Lockfile Không Commit (Missing package-lock.json)

### Phân loại
Dependencies / Reproducibility

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
Without lockfile, `npm install` resolves different versions each time → non-reproducible builds.

### Phát hiện
```bash
rg "package-lock|pnpm-lock" -n --glob ".gitignore"
```

### Giải pháp
```bash
git add package-lock.json
# CI: npm ci (not npm install)
# pnpm: pnpm install --frozen-lockfile
```

### Phòng ngừa
- [ ] Commit lockfile for applications
- [ ] `npm ci` in CI/production
- Tool: `npm ci`, `--frozen-lockfile`

---

## Pattern 04: Semantic Versioning Trust

### Tên
Semver Trust (Caret Range Breaks)

### Phân loại
Dependencies / Versioning

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
`^2.0.0` allows 2.x.x — library publishes breaking minor → build breaks.

### Phát hiện
```bash
rg '"\^' -n --glob "package.json"
```

### Giải pháp
```ini
# .npmrc:
save-exact=true
```
Rely on lockfile + `npm ci` for exact versions.

### Phòng ngừa
- [ ] `save-exact=true` for critical deps
- [ ] Renovate/Dependabot for controlled updates
- Tool: `npm outdated`, Renovate

---

## Pattern 05: Deprecated Package

### Tên
Deprecated Package (Unmaintained Dependency)

### Phân loại
Dependencies / Maintenance

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
Deprecated packages receive no security patches. E.g., `request`, `moment`.

### Phát hiện
```bash
rg "request|moment" -n --glob "package.json"
```

### Giải pháp
```
request → got, undici
moment → dayjs, date-fns
node-sass → sass
```

### Phòng ngừa
- [ ] `npm outdated` monthly
- [ ] Renovate for auto-updates
- Tool: `npm outdated`

---

## Pattern 06: Postinstall Script Nguy Hiểm

### Tên
Postinstall Script (Arbitrary Code on Install)

### Phân loại
Dependencies / Security / Scripts

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
Packages run arbitrary scripts on `npm install` via postinstall hooks.

### Phát hiện
```bash
rg "postinstall|preinstall" -n --glob "node_modules/*/package.json" | head -10
```

### Giải pháp
```ini
# .npmrc:
ignore-scripts=true
```
Manually run `npx node-gyp rebuild` for native addons.

### Phòng ngừa
- [ ] `ignore-scripts=true`
- [ ] Audit scripts of new dependencies
- Tool: `socket.dev`

---

## Pattern 07: Bundle Size Bloat

### Tên
Bundle Size Bloat (Full Library Import)

### Phân loại
Dependencies / Performance / Bundle

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
```typescript
import _ from 'lodash';       // 72KB
import moment from 'moment';  // 67KB
```

### Phát hiện
```bash
rg --type ts --type js "import .* from 'lodash'" -n
rg --type ts --type js "import .* from 'moment'" -n
```

### Giải pháp
```typescript
import get from 'lodash/get';        // ~1KB
import { format } from 'date-fns';   // Tree-shakeable
const value = obj?.a?.b;             // Native optional chaining
```

### Phòng ngừa
- [ ] Check `bundlephobia.com` before adding deps
- [ ] Named imports for tree-shaking
- Tool: `size-limit`, `webpack-bundle-analyzer`

---

## Pattern 08: Native Addon Build Fail

### Tên
Native Addon Build Fail (node-gyp Issues)

### Phân loại
Dependencies / Build / Native

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
`npm install bcrypt` → `gyp ERR!` — missing python/make/gcc or wrong platform.

### Phát hiện
```bash
rg "bcrypt|sharp|canvas|sqlite3" -n --glob "package.json"
```

### Giải pháp
Use pure JS alternatives: `bcrypt → bcryptjs`, `node-sass → sass`. Docker: `apk add python3 make g++`.

### Phòng ngừa
- [ ] Pure JS alternatives when possible
- [ ] Docker with build tools for native addons
- Tool: `prebuild`, Docker

---

## Pattern 09: Peer Dependency Conflict

### Tên
Peer Dependency Conflict (Version Mismatch)

### Phân loại
Dependencies / Resolution

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
`ERESOLVE unable to resolve dependency tree` — peer dependency version mismatch.

### Phát hiện
```bash
rg "peerDependencies" -n --glob "package.json"
```

### Giải pháp
```json
{ "overrides": { "react-modal": { "react": "$react" } } }
```
```bash
npm ls react  # Diagnose
npm explain react-modal
```

### Phòng ngừa
- [ ] `npm ls` to check duplicates
- [ ] `overrides` for intentional forcing
- Tool: `npm ls`, `npm explain`

---

## Pattern 10: CVE Trong Dependencies

### Tên
CVE Trong Dependencies (Known Vulnerabilities)

### Phân loại
Dependencies / Security / CVE

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
`npm audit` → found 15 vulnerabilities (3 critical). Known CVEs in dependency tree.

### Phát hiện
```bash
rg "audit" -n --glob "*.yml"
```

### Giải pháp
```bash
npm audit --production --audit-level=high  # CI gate
npm audit fix
```

### Phòng ngừa
- [ ] `npm audit` in CI (fail on high+)
- [ ] Dependabot/Renovate for auto-updates
- Tool: `npm audit`, Snyk
