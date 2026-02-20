# Dasa Sradha Kit

Multi-agent orchestration framework for [Antigravity Desktop IDE](https://github.com/vudovn/antigravity-kit) on Linux. Uses a workflows-only architecture for task planning, strict continuation, and Indonesian persona-based skill routing.

---

## English

### What's Inside

```
~/.gemini/
  scripts/
    dasa-init                   # Bootstrap script for repos
    dasa-uninstall              # Kit uninstaller
    dasa-sradha-kit/
      workflows/                # Master workflow templates
        dasa-init.md            # /dasa-init
        dasa-plan.md            # /dasa-plan
        dasa-start-work.md      # /dasa-start-work
        dasa-status.md          # /dasa-status
        dasa-uninstall.md       # /dasa-uninstall
  antigravity/
    skills/                     # 10 flat persona skills
      dasa-patih.md             # Patih (Architect)
      dasa-mpu.md               # Mpu (Implementer)
      dasa-nala.md              # Nala (Admiral - Orchestrator)
      dasa-rsi.md               # Rsi (Debugger)
      dasa-sastra.md            # Sastra (Librarian)
      dasa-widya.md             # Widya (Analyst)
      dasa-indra.md             # Indra (Investigating)
      dasa-dharma.md            # Dharma (Ethics/Safety)
      dasa-kala.md              # Kala (Time/Risk)
      dasa-dwipa.md             # Dwipa (Reviewer)
```

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/vudovn/dasa-sradha-kit.git
   cd dasa-sradha-kit
   ```
2. Run the installer:
   ```bash
   ./install.sh
   ```
   This installs global scripts, master templates, and the 10 persona skills to `~/.gemini/`.

### Setup in a Repository

To activate the kit in a project, run the bootstrap command from your repository root:

```bash
~/.gemini/scripts/dasa-init
```

This will:
- Create an empty `.dasa-sradha` marker file (activation guard).
- Copy the 5 workflow templates to `.agent/workflows/`.
- Prepare the `.artifacts/` directory for task state.

### Workflows

| Command | Workflow | Purpose |
|---------|----------|---------|
| `/dasa-init` | `dasa-init.md` | Re-bootstrap or sync workflows in a repo |
| `/dasa-plan` | `dasa-plan.md` | Initialize or update a work plan (boulder.json) |
| `/dasa-start-work` | `dasa-start-work.md` | Select next task, resume work, or mark as done |
| `/dasa-status` | `dasa-status.md` | Show active task and pending plan progress |
| `/dasa-uninstall` | `dasa-uninstall.md` | Remove kit files and marker from the repository |

### Guard Mechanism

All workflows (except init) check for the presence of the `.dasa-sradha` file at the project root. If missing, the workflow will fast-fail to prevent accidental execution in non-kit repositories.

---

## Bahasa Indonesia

### Isi Framework

Dasa Sradha Kit menggunakan arsitektur *workflows-only* yang terintegrasi langsung dengan Antigravity IDE. Tidak ada perintah Python eksternal; semua logika dijalankan melalui workflow asli.

### Instalasi

1. Clone repositori:
   ```bash
   git clone https://github.com/vudovn/dasa-sradha-kit.git
   cd dasa-sradha-kit
   ```
2. Jalankan installer:
   ```bash
   ./install.sh
   ```

### Konfigurasi Projek

Jalankan perintah berikut di direktori utama projek Anda untuk mengaktifkan kit:

```bash
~/.gemini/scripts/dasa-init
```

Perintah ini akan membuat file penanda `.dasa-sradha` dan menyalin template workflow ke folder `.agent/workflows/` projek Anda.

### Alur Kerja (Workflows)

- `/dasa-init`: Menginisialisasi atau memperbarui alur kerja di repositori.
- `/dasa-plan`: Membuat atau memperbarui rencana kerja (boulder).
- `/dasa-start-work`: Memilih tugas berikutnya atau menandai tugas selesai.
- `/dasa-status`: Menampilkan status aktif dan kemajuan rencana.
- `/dasa-uninstall`: Menghapus alur kerja dan penanda dari repositori.

### 10 Persona Dasa Sradha

Skill kit ini dibagi menjadi 10 persona dengan keahlian spesifik:

1. **Patih**: Arsitek sistem dan desain tingkat tinggi.
2. **Mpu**: Implementer fitur dan penulisan kode.
3. **Nala**: Orkesstrator dan manajemen delegasi tugas.
4. **Rsi**: Debugging dan analisis akar masalah.
5. **Sastra**: Librarian untuk riset dan pencarian referensi kode.
6. **Widya**: Analisis risiko dan kasus tepi (*edge cases*).
7. **Indra**: Investigasi dan eksplorasi sistem.
8. **Dharma**: Penjaga etika, keamanan, dan standar kode.
9. **Kala**: Manajemen waktu, dependensi, dan prioritas.
10. **Dwipa**: Reviewer kode dan validasi kualitas.

---

## Documentation

Detailed specifications are available in the `docs/` directory:

- `command-contracts.md`: Behavioral contracts for workflows.
- `artifact-layout-spec.md`: Structure of the `.artifacts/` state directory.
- `skill-routing-spec.md`: Persona selection and routing logic.
- `dasa-schema-v1.md`: Technical format of the task state file.
- `dasa-recovery-spec.md`: State corruption recovery workflows.
- `qa-recipes.md`: Testing and verification scenarios.
- `GEMINI_V0.md`: Historical design reference for the legacy system.

## License

MIT
