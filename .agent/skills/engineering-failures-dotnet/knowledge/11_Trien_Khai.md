# Domain 11: Triển Khai Và Build (Deployment & Build)

> .NET patterns liên quan đến deployment: self-contained, trimming, AOT, Docker, health checks, config, NuGet.

---

## Pattern 01: Self-Contained Publish Bloat

### Tên
Self-Contained Publish Bloat (Huge Publish Output)

### Phân loại
Deployment / Size / Publishing

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
```bash
dotnet publish -c Release --self-contained
# Output: 150MB+ (includes entire .NET runtime)
```

### Phát hiện
```bash
rg "SelfContained|PublishSingleFile|PublishTrimmed" -n --glob "*.csproj"
```

### Giải pháp
```xml
<PropertyGroup>
    <PublishSingleFile>true</PublishSingleFile>
    <SelfContained>true</SelfContained>
    <PublishTrimmed>true</PublishTrimmed>
    <RuntimeIdentifier>linux-x64</RuntimeIdentifier>
</PropertyGroup>
```
Or use framework-dependent (requires runtime on host): `<SelfContained>false</SelfContained>`

### Phòng ngừa
- [ ] Trimming for self-contained apps
- [ ] Framework-dependent when runtime available
- Tool: `dotnet publish`, `ILLink`

---

## Pattern 02: Trimming Break Reflection

### Tên
Trimming Break Reflection (Trimmed Code Used via Reflection)

### Phân loại
Deployment / Trimming / Reflection

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```csharp
var type = Type.GetType("MyApp.Services.UserService"); // Trimmed away!
var instance = Activator.CreateInstance(type); // NullReferenceException
```

### Phát hiện
```bash
rg --type cs "Activator\.CreateInstance|Type\.GetType|Assembly\.Load" -n
rg "PublishTrimmed" -n --glob "*.csproj"
rg --type cs "\[DynamicallyAccessedMembers\]" -n
```

### Giải pháp
```csharp
// Annotate types used via reflection:
[DynamicallyAccessedMembers(DynamicallyAccessedMemberTypes.PublicConstructors)]
public class UserService { }

// Or preserve in .csproj:
// <TrimmerRootAssembly Include="MyApp.Services" />
```

### Phòng ngừa
- [ ] `[DynamicallyAccessedMembers]` annotations
- [ ] Test trimmed app before deploy
- [ ] `<TrimMode>partial</TrimMode>` for safer trimming
- Tool: `ILLink`, trim warnings

---

## Pattern 03: AOT Compilation Compatibility

### Tên
AOT Compatibility (Native AOT Breaks)

### Phân loại
Deployment / AOT / Compatibility

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```csharp
// These don't work with Native AOT:
var obj = JsonSerializer.Deserialize<User>(json); // Needs source generator
Assembly.LoadFrom("plugin.dll");                   // No dynamic loading
```

### Phát hiện
```bash
rg "PublishAot" -n --glob "*.csproj"
rg --type cs "JsonSerializer\.(De)?[Ss]erialize" -n
rg --type cs "\[JsonSerializable\]" -n
```

### Giải pháp
```csharp
// Source generator for JSON:
[JsonSerializable(typeof(User))]
[JsonSerializable(typeof(List<Order>))]
internal partial class AppJsonContext : JsonSerializerContext { }

// Usage:
var user = JsonSerializer.Deserialize(json, AppJsonContext.Default.User);
```

### Phòng ngừa
- [ ] `IsAotCompatible=true` in csproj
- [ ] JSON source generators
- [ ] Test with `PublishAot` in CI
- Tool: `dotnet publish -p:PublishAot=true`

---

## Pattern 04: Docker Multi-Stage Thiếu

### Tên
Docker Multi-Stage Thiếu (SDK in Production Image)

### Phân loại
Deployment / Docker / Size

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:8.0
COPY . .
RUN dotnet publish -c Release -o /app
CMD ["dotnet", "/app/MyApp.dll"]
# Image: 800MB+ (SDK included)
```

### Phát hiện
```bash
rg "FROM.*dotnet" -n --glob "Dockerfile"
rg "AS build" -n --glob "Dockerfile"
```

### Giải pháp
```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY *.csproj .
RUN dotnet restore
COPY . .
RUN dotnet publish -c Release -o /app

FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /app .
USER $APP_UID
ENTRYPOINT ["dotnet", "MyApp.dll"]
# Image: ~200MB (runtime only)
```

### Phòng ngừa
- [ ] Multi-stage: SDK for build, runtime for deploy
- [ ] `aspnet` base image (not `sdk`)
- [ ] `.dockerignore` to exclude bin/obj
- Tool: Docker multi-stage builds

---

## Pattern 05: Health Check Trong K8s Thiếu

### Tên
Health Check K8s Thiếu (No Readiness/Liveness)

### Phân loại
Deployment / Kubernetes / Health

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
K8s sends traffic before app is ready. Or unhealthy pod keeps receiving requests.

### Phát hiện
```bash
rg --type cs "MapHealthChecks|AddHealthChecks" -n
rg "livenessProbe|readinessProbe" -n --glob "*.yaml" --glob "*.yml"
```

### Giải pháp
```csharp
builder.Services.AddHealthChecks()
    .AddSqlServer(connectionString, name: "db")
    .AddRedis(redisConnection, name: "cache");

app.MapHealthChecks("/healthz/live", new HealthCheckOptions
{
    Predicate = _ => false // Liveness: app running?
});
app.MapHealthChecks("/healthz/ready", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready")
});
```

```yaml
# K8s:
livenessProbe:
  httpGet: { path: /healthz/live, port: 8080 }
  initialDelaySeconds: 10
readinessProbe:
  httpGet: { path: /healthz/ready, port: 8080 }
  initialDelaySeconds: 5
```

### Phòng ngừa
- [ ] Separate liveness and readiness probes
- [ ] Check dependencies in readiness
- Tool: `AspNetCore.HealthChecks.*` NuGet

---

## Pattern 06: Configuration Transformation Sai

### Tên
Config Transformation Sai (Wrong appsettings per Environment)

### Phân loại
Deployment / Configuration / Environment

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```json
// appsettings.json:
{ "ConnectionStrings": { "Default": "Server=localhost;..." } }
// appsettings.Production.json missing → production uses localhost!
```

### Phát hiện
```bash
rg "appsettings\.\w+\.json" -n --glob "*.csproj"
rg "ASPNETCORE_ENVIRONMENT|DOTNET_ENVIRONMENT" -n --glob "*.yml"
rg --type cs "GetConnectionString|Configuration\[" -n
```

### Giải pháp
```csharp
var builder = WebApplication.CreateBuilder(args);
// Loads: appsettings.json → appsettings.{env}.json → env vars → secrets

// NEVER hardcode secrets in appsettings:
// Use env vars or Key Vault:
builder.Configuration.AddAzureKeyVault(vaultUri, credential);
```

```yaml
# docker-compose:
environment:
  - ASPNETCORE_ENVIRONMENT=Production
  - ConnectionStrings__Default=Server=prod-db;...
```

### Phòng ngừa
- [ ] `ASPNETCORE_ENVIRONMENT` set in deployment
- [ ] Secrets via env vars or Key Vault
- [ ] Never commit production connection strings
- Tool: `dotnet user-secrets`, Azure Key Vault

---

## Pattern 07: Assembly Versioning Inconsistent

### Tên
Assembly Versioning Inconsistent

### Phân loại
Deployment / Versioning / Assembly

### Mức nghiêm trọng
MEDIUM 🟡

### Vấn đề
```
Multiple assemblies with different version strategies.
No way to identify deployed version at runtime.
```

### Phát hiện
```bash
rg "Version|AssemblyVersion|FileVersion" -n --glob "*.csproj"
rg "InformationalVersion" -n --glob "*.csproj"
```

### Giải pháp
```xml
<!-- Directory.Build.props (shared across projects): -->
<PropertyGroup>
    <Version>1.2.3</Version>
    <AssemblyVersion>1.0.0.0</AssemblyVersion>
    <FileVersion>1.2.3.0</FileVersion>
    <InformationalVersion>1.2.3+abc1234</InformationalVersion>
</PropertyGroup>
```

```bash
# CI: inject version:
dotnet publish -p:Version=1.2.3 -p:InformationalVersion="1.2.3+$(git rev-parse --short HEAD)"
```

### Phòng ngừa
- [ ] `Directory.Build.props` for shared versioning
- [ ] CI injects version from git tag
- [ ] `InformationalVersion` includes commit hash
- Tool: `MinVer`, `GitVersion`

---

## Pattern 08: NuGet Package Vulnerability

### Tên
NuGet Vulnerability (Known CVE in Dependencies)

### Phân loại
Deployment / Security / NuGet

### Mức nghiêm trọng
HIGH 🟠

### Vấn đề
```
dotnet list package --vulnerable
> System.Text.Json 7.0.0 has known vulnerability (CVE-2024-xxx)
```

### Phát hiện
```bash
rg "PackageReference" -n --glob "*.csproj"
```

### Giải pháp
```bash
# Audit:
dotnet list package --vulnerable --include-transitive

# Update:
dotnet add package System.Text.Json --version 8.0.5

# CI gate:
dotnet restore && dotnet list package --vulnerable --format json
```

```xml
<!-- Directory.Build.props: Treat warnings as errors -->
<PropertyGroup>
    <NuGetAudit>true</NuGetAudit>
    <NuGetAuditLevel>moderate</NuGetAuditLevel>
    <NuGetAuditMode>all</NuGetAuditMode>
</PropertyGroup>
```

### Phòng ngừa
- [ ] `dotnet list package --vulnerable` in CI
- [ ] `NuGetAudit=true` in Directory.Build.props
- [ ] Dependabot for auto-updates
- Tool: `dotnet list package --vulnerable`, Dependabot
