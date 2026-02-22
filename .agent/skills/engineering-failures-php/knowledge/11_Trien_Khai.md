# Domain 11: Triển Khai Và Hạ Tầng (Deployment & Infrastructure)

> PHP/Laravel patterns liên quan đến deployment: version mismatch, extensions, composer, caching, permissions, debug mode.

---

## Pattern 01: PHP Version Mismatch

### Tên
PHP Version Mismatch (Dev vs Production)

### Phân loại
Deployment / Version / Compatibility

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Development: PHP 8.3 (uses match, enum, fibers)
Production:  PHP 8.1
→ Fatal error: syntax error, unexpected token "enum"
```

### Phát hiện

```bash
rg "php.*require" -n --glob "composer.json"
rg "\"php\":" -n --glob "composer.json"
rg "FROM php:" -n --glob "Dockerfile"
```

### Giải pháp

❌ **BAD**
```json
{ "require": { "php": ">=8.0" } }  // Too loose — allows mismatch
```

✅ **GOOD**
```json
{
    "require": { "php": "^8.3" },
    "config": {
        "platform": { "php": "8.3.0" }
    }
}
```

```dockerfile
# Pin exact version:
FROM php:8.3-fpm-alpine
```

```yaml
# CI: Test on same version as production
php-versions: ['8.3']
```

### Phòng ngừa
- [ ] Pin PHP version in `composer.json` with `^`
- [ ] `config.platform.php` to simulate target version
- [ ] Same PHP version in dev, CI, production
- Tool: Docker, `composer check-platform-reqs`

---

## Pattern 02: Extension Thiếu Production

### Tên
Extension Thiếu Production (Missing PHP Extensions)

### Phân loại
Deployment / Extensions / Runtime

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Production deploy → Fatal error: Call to undefined function gd\imagecreate()
Extension installed locally but not on server/container
```

### Phát hiện

```bash
rg "ext-" -n --glob "composer.json"
rg "extension=" -n --glob "php.ini"
rg "docker-php-ext-install" -n --glob "Dockerfile"
```

### Giải pháp

❌ **BAD**: Extensions installed manually, not tracked

✅ **GOOD**
```json
{
    "require": {
        "ext-gd": "*",
        "ext-pdo_mysql": "*",
        "ext-redis": "*",
        "ext-intl": "*"
    }
}
```

```dockerfile
FROM php:8.3-fpm-alpine
RUN apk add --no-cache \
        libpng-dev libjpeg-turbo-dev freetype-dev icu-dev \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install gd pdo_mysql intl opcache \
    && pecl install redis && docker-php-ext-enable redis
```

### Phòng ngừa
- [ ] Declare extensions in `composer.json`
- [ ] `composer check-platform-reqs` in CI
- [ ] Dockerfile installs all required extensions
- Tool: `composer check-platform-reqs`

---

## Pattern 03: Composer.lock Không Commit

### Tên
Composer.lock Không Commit (Missing Lockfile)

### Phân loại
Deployment / Dependencies / Reproducibility

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
.gitignore:
composer.lock  ← WRONG for applications!

CI runs: composer install
→ Gets different versions than development
→ Bug only appears in production
```

### Phát hiện

```bash
rg "composer\.lock" -n --glob ".gitignore"
rg "composer install|composer update" -n --glob "*.yml" --glob "Dockerfile"
```

### Giải pháp

❌ **BAD**
```
# .gitignore:
composer.lock  # Don't ignore for applications!
```

✅ **GOOD**
```bash
# Always commit composer.lock for applications:
git add composer.lock

# CI/Production:
composer install --no-dev --optimize-autoloader --no-interaction

# Never run 'composer update' in CI — only 'composer install'
```

```dockerfile
COPY composer.json composer.lock ./
RUN composer install --no-dev --optimize-autoloader --no-scripts
COPY . .
RUN composer run-script post-autoload-dump
```

### Phòng ngừa
- [ ] Commit `composer.lock` for applications
- [ ] `composer install` (not `update`) in CI/production
- [ ] `--no-dev` for production installs
- Tool: `composer audit`, `composer install`

---

## Pattern 04: Artisan Config Cache Thiếu

### Tên
Config/Route Cache Thiếu (No Cache in Production)

### Phân loại
Deployment / Performance / Laravel

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề

```
Every request in production:
- Loads 20+ config files from disk
- Parses all route files
- Discovers services
→ 50-100ms overhead per request
```

### Phát hiện

```bash
rg "config:cache|route:cache|view:cache" -n --glob "*.sh" --glob "Dockerfile"
rg "optimize" -n --glob "composer.json"
```

### Giải pháp

❌ **BAD**: No caching commands in deployment

✅ **GOOD**
```bash
# Deploy script:
php artisan config:cache    # Compile config into single file
php artisan route:cache     # Compile routes
php artisan view:cache      # Compile Blade templates
php artisan event:cache     # Cache event-listener mappings
php artisan optimize        # Does config + route cache

# Or in Dockerfile:
RUN php artisan optimize
```

```json
// composer.json:
{
    "scripts": {
        "post-autoload-dump": [
            "@php artisan optimize"
        ]
    }
}
```

### Phòng ngừa
- [ ] `php artisan optimize` in deploy script
- [ ] Never use closures in routes (breaks route:cache)
- [ ] Never use `env()` outside config files (breaks config:cache)
- Tool: `php artisan optimize`, deployment scripts

---

## Pattern 05: File Permission 777

### Tên
File Permission 777 (Overly Permissive)

### Phân loại
Deployment / Security / Permissions

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```bash
chmod -R 777 storage/  # "Fix" for permission errors
# Any user/process can read, write, execute
# Security vulnerability: arbitrary file upload → code execution
```

### Phát hiện

```bash
rg "chmod.*777" -n --glob "*.sh" --glob "Dockerfile"
rg "chmod.*-R" -n --glob "*.sh" --glob "Dockerfile"
```

### Giải pháp

❌ **BAD**
```bash
chmod -R 777 storage/ bootstrap/cache/
```

✅ **GOOD**
```bash
# Correct permissions:
chown -R www-data:www-data storage/ bootstrap/cache/
chmod -R 775 storage/ bootstrap/cache/
chmod -R 644 storage/logs/*.log

# Dockerfile:
RUN chown -R www-data:www-data /app/storage /app/bootstrap/cache \
    && chmod -R 775 /app/storage /app/bootstrap/cache
USER www-data
```

### Phòng ngừa
- [ ] Never use 777 permissions
- [ ] `www-data` owner for web-writable directories
- [ ] 755 for directories, 644 for files
- Tool: `stat`, `namei -l`

---

## Pattern 06: Debug Mode On Production

### Tên
Debug Mode On Production (APP_DEBUG=true)

### Phân loại
Deployment / Security / Configuration

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
.env on production:
APP_DEBUG=true
APP_ENV=local

Exposes: stack traces, SQL queries, env variables, file paths
→ Information disclosure vulnerability
```

### Phát hiện

```bash
rg "APP_DEBUG|APP_ENV" -n --glob ".env*"
rg "debug.*true" -n --glob ".env.production"
```

### Giải pháp

❌ **BAD**
```env
APP_DEBUG=true
APP_ENV=local
```

✅ **GOOD**
```env
# .env.production:
APP_DEBUG=false
APP_ENV=production

# Additional security:
APP_KEY=base64:...  # Generated, never committed
```

```php
// config/app.php — verify at boot:
if (app()->isProduction() && config('app.debug')) {
    throw new RuntimeException('Debug mode must be off in production!');
}
```

### Phòng ngừa
- [ ] `APP_DEBUG=false` in production
- [ ] CI check for debug mode
- [ ] Never commit `.env` to git
- Tool: `php artisan env`, deployment checklist

---

## Pattern 07: .env File Exposed

### Tên
.env File Exposed (Environment File Accessible)

### Phân loại
Deployment / Security / Secrets

### Mức nghiêm trọng
CRITICAL 🔴

### Vấn đề

```
https://example.com/.env  → Returns .env contents!
Leaks: database credentials, API keys, app key
Nginx/Apache not configured to block dotfiles
```

### Phát hiện

```bash
rg "\.env" -n --glob ".gitignore"
rg "deny.*\." -n --glob "nginx*" --glob "*.conf"
rg "\.htaccess" -n --glob "public/"
```

### Giải pháp

❌ **BAD**: No web server protection for dotfiles

✅ **GOOD**
```nginx
# nginx.conf:
server {
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }

    # Only serve from public/:
    root /app/public;
}
```

```apache
# .htaccess:
<FilesMatch "^\.">
    Require all denied
</FilesMatch>
```

```
# .gitignore:
.env
.env.local
.env.*.local
```

### Phòng ngừa
- [ ] Block dotfiles in web server config
- [ ] Document root = `public/` only
- [ ] `.env` in `.gitignore`
- Tool: `curl -I https://site/.env` to verify

---

## Pattern 08: Queue Worker Không Restart

### Tên
Queue Worker Không Restart Sau Deploy (Stale Code)

### Phân loại
Deployment / Queue / Hot Reload

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề

```
Deploy new code → Web serves new code
But queue workers still running OLD code (loaded in memory)
→ Jobs use old logic, old classes → errors, data corruption
```

### Phát hiện

```bash
rg "queue:work|queue:listen|horizon" -n --glob "*.sh" --glob "supervisor*"
rg "queue:restart" -n --glob "*.sh" --glob "deploy*"
```

### Giải pháp

❌ **BAD**: Deploy without restarting workers

✅ **GOOD**
```bash
# deploy.sh:
php artisan down
git pull origin main
composer install --no-dev --optimize-autoloader
php artisan migrate --force
php artisan optimize
php artisan queue:restart  # Signal workers to restart after current job
php artisan up

# Or use Horizon:
php artisan horizon:terminate
```

```ini
# supervisor.conf:
[program:queue-worker]
command=php /app/artisan queue:work --sleep=3 --tries=3 --max-time=3600
autostart=true
autorestart=true
stopwaitsecs=3600
```

### Phòng ngừa
- [ ] `queue:restart` in every deploy script
- [ ] Supervisor for process management
- [ ] `--max-time` to auto-restart workers periodically
- Tool: Supervisor, Laravel Horizon
