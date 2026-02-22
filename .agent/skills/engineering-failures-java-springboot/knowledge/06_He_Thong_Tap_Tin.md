# Domain 06: Hệ Thống Tập Tin (File System)

> Java/Spring Boot patterns: file I/O, classpath resources, temp files, upload, path traversal.

---

## Pattern 01: Path Traversal

### Phân loại
File / Security / Traversal — CRITICAL 🔴

### Vấn đề
```java
@GetMapping("/download")
public Resource download(@RequestParam String filename) {
    Path path = Paths.get("/uploads/" + filename); // filename = "../../etc/passwd"
    return new FileSystemResource(path);
}
```

### Phát hiện
```bash
rg --type java "Paths\\.get\\(.*\\+|Path\\.of\\(.*\\+" -n
rg --type java "new File\\(.*request\\." -n
```

### Giải pháp
```java
@GetMapping("/download")
public Resource download(@RequestParam String filename) {
    Path basePath = Paths.get("/uploads").toAbsolutePath().normalize();
    Path filePath = basePath.resolve(filename).normalize();
    if (!filePath.startsWith(basePath)) {
        throw new AccessDeniedException("Path traversal detected");
    }
    return new FileSystemResource(filePath);
}
```

### Phòng ngừa
- [ ] Validate resolved path starts with base directory
- [ ] Never concatenate user input into file paths
- Tool: OWASP Path Traversal checks

---

## Pattern 02: Resource Loading Sai

### Phân loại
File / Classpath / Spring — HIGH 🟠

### Vấn đề
```java
// Works in IDE, fails in JAR:
File file = new File("src/main/resources/template.json"); // Doesn't exist in JAR!
// Or:
File file = new ClassPathResource("template.json").getFile(); // Fails in JAR!
```

### Phát hiện
```bash
rg --type java "new File\\(\"src/main/resources" -n
rg --type java "getFile\\(\\)" -n | rg "ClassPathResource|Resource"
```

### Giải pháp
```java
// GOOD: Use InputStream (works in JAR)
@Value("classpath:template.json")
private Resource templateResource;

public String loadTemplate() throws IOException {
    try (InputStream is = templateResource.getInputStream()) {
        return new String(is.readAllBytes(), StandardCharsets.UTF_8);
    }
}

// Or use ResourceLoader:
@Autowired private ResourceLoader resourceLoader;
Resource resource = resourceLoader.getResource("classpath:data.csv");
```

### Phòng ngừa
- [ ] `getInputStream()` not `getFile()` for classpath resources
- [ ] `@Value("classpath:...")` for injection
- Tool: Spring ResourceLoader

---

## Pattern 03: Temp File Không Cleanup

### Phân loại
File / Leak / Temp — MEDIUM 🟡

### Vấn đề
```java
File temp = File.createTempFile("report", ".pdf");
generateReport(temp);
sendEmail(temp);
// temp never deleted → /tmp fills up over time
```

### Phát hiện
```bash
rg --type java "createTempFile|createTempDirectory" -n
rg --type java "Files\\.createTemp" -n
rg --type java "\\.deleteOnExit\\(\\)" -n
```

### Giải pháp
```java
// GOOD: try-with-resources pattern
Path temp = Files.createTempFile("report", ".pdf");
try {
    generateReport(temp);
    sendEmail(temp);
} finally {
    Files.deleteIfExists(temp);
}

// Or use Spring's cleanup:
@Bean
public MultipartConfigElement multipartConfigElement() {
    MultipartConfigFactory factory = new MultipartConfigFactory();
    factory.setLocation(System.getProperty("java.io.tmpdir"));
    return factory.createMultipartConfig();
}
```

### Phòng ngừa
- [ ] `finally` block to delete temp files
- [ ] `Files.deleteIfExists()` over `file.delete()`
- Tool: `java.nio.file.Files`

---

## Pattern 04: File Upload Không Validate

### Phân loại
File / Security / Upload — HIGH 🟠

### Vấn đề
```java
@PostMapping("/upload")
public String upload(@RequestParam MultipartFile file) {
    file.transferTo(new File("/uploads/" + file.getOriginalFilename()));
    // No size limit, no type check, original filename used (path traversal!)
}
```

### Phát hiện
```bash
rg --type java "MultipartFile" -n
rg --type java "getOriginalFilename\\(\\)" -n
rg --type java "transferTo" -n
```

### Giải pháp
```java
@PostMapping("/upload")
public String upload(@RequestParam MultipartFile file) {
    if (file.getSize() > 10_000_000) throw new FileTooLargeException();
    String contentType = file.getContentType();
    if (!Set.of("image/png", "image/jpeg").contains(contentType)) {
        throw new InvalidFileTypeException();
    }
    String safeName = UUID.randomUUID() + getExtension(file.getOriginalFilename());
    Path target = uploadDir.resolve(safeName);
    file.transferTo(target);
    return safeName;
}
```

```yaml
spring:
  servlet:
    multipart:
      max-file-size: 10MB
      max-request-size: 20MB
```

### Phòng ngừa
- [ ] UUID filename, never use original
- [ ] Validate content type and size
- [ ] Configure `max-file-size` in Spring
- Tool: Spring Multipart config

---

## Pattern 05: InputStream Không Close

### Phân loại
File / Leak / Resource — HIGH 🟠

### Vấn đề
```java
InputStream is = new FileInputStream("data.txt");
String content = new String(is.readAllBytes());
// Exception thrown → InputStream never closed → file handle leak
```

### Phát hiện
```bash
rg --type java "new FileInputStream|new FileOutputStream|new BufferedReader" -n
rg --type java "InputStream|OutputStream" -n | rg -v "try.*\\("
```

### Giải pháp
```java
// GOOD: try-with-resources
try (InputStream is = new FileInputStream("data.txt")) {
    String content = new String(is.readAllBytes(), StandardCharsets.UTF_8);
}

// BEST: Use Files utility
String content = Files.readString(Path.of("data.txt"));
List<String> lines = Files.readAllLines(Path.of("data.txt"));
```

### Phòng ngừa
- [ ] Always try-with-resources for `AutoCloseable`
- [ ] `Files.readString()` / `Files.readAllLines()` for simple reads
- Tool: SpotBugs `OBL_UNSATISFIED_OBLIGATION`

---

## Pattern 06: Encoding Không Chỉ Định

### Phân loại
File / Encoding / I18N — MEDIUM 🟡

### Vấn đề
```java
new FileReader("data.txt"); // Uses platform default encoding!
new String(bytes);           // Uses platform default encoding!
// Works on dev (UTF-8) → garbled text on production (ISO-8859-1)
```

### Phát hiện
```bash
rg --type java "new FileReader\\(|new FileWriter\\(" -n
rg --type java "new String\\(.*\\)" -n | rg -v "UTF|charset|Charset"
rg --type java "getBytes\\(\\)" -n | rg -v "UTF|charset"
```

### Giải pháp
```java
// GOOD: Always specify charset
try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {}
String text = new String(bytes, StandardCharsets.UTF_8);
byte[] data = text.getBytes(StandardCharsets.UTF_8);

// Or set JVM default:
// -Dfile.encoding=UTF-8 (Java 17-)
// Java 18+: UTF-8 is default
```

### Phòng ngừa
- [ ] Always explicit `StandardCharsets.UTF_8`
- [ ] `Files.newBufferedReader()` over `new FileReader()`
- Tool: SpotBugs `DM_DEFAULT_ENCODING`
