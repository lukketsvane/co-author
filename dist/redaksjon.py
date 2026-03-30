#!/usr/bin/env python3
"""
redaksjon.py — Redaksjonell arkitektur for autonome agentar.

Organiser, konfigurer og køyr redaksjonelle prosjekt med konfigurerbare
agentar (stab), sesjonsstyring, og prosjekthandtering.

Bruk:
    python dist/redaksjon.py              # Interaktiv TUI
    python dist/redaksjon.py list         # Vis prosjekt
    python dist/redaksjon.py staff        # Vis tilgjengeleg stab
    python dist/redaksjon.py new          # Nytt prosjekt
    python dist/redaksjon.py open <slug>  # Opne prosjekt
    python dist/redaksjon.py prompt <prosjekt> <agent>  # Generer systemprompt
    python dist/redaksjon.py build <slug> # Bygg PDF frå siste utkast
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DIST_DIR = Path(__file__).parent.resolve()
STAB_DIR = DIST_DIR / "tools" / "stab"
ROOT_DIR = DIST_DIR.parent
PROJECTS_DIR = ROOT_DIR / "projects"

# ---------------------------------------------------------------------------
# YAML — bruk PyYAML om tilgjengeleg, elles enkel parser/skrivar
# ---------------------------------------------------------------------------

try:
    import yaml

    def load_yaml(path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_yaml(path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

except ImportError:
    # Minimal YAML-liknande fallback med JSON
    def load_yaml(path: Path) -> dict:
        text = path.read_text(encoding="utf-8")
        # Prøv JSON først (sessions brukar JSON)
        if text.strip().startswith("{"):
            return json.loads(text)
        # Enkel YAML-parse for nøkkel: verdi
        data = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("---"):
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                val = val.strip().strip("'\"")
                if val.lower() == "true":
                    val = True
                elif val.lower() == "false":
                    val = False
                elif val.isdigit():
                    val = int(val)
                data[key.strip()] = val
        return data

    def save_yaml(path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Rich — valfritt, for penare TUI
# ---------------------------------------------------------------------------

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

    class _Console:
        def print(self, *a, **kw):
            text = str(a[0]) if a else ""
            # Strip rich markup
            text = re.sub(r"\[/?[a-z_ ]+\]", "", text)
            print(text)

        def rule(self, title="", **kw):
            w = os.get_terminal_size((80, 24)).columns
            if title:
                side = (w - len(title) - 2) // 2
                print(f"{'─' * side} {title} {'─' * side}")
            else:
                print("─" * w)

    console = _Console()


# ---------------------------------------------------------------------------
# Agent display — colored, bold output showing who is doing what
# ---------------------------------------------------------------------------

# Color assignments per role
AGENT_COLORS = {
    "wittgenstein":       ("bold cyan",    "W"),
    "mathematikar":       ("bold magenta", "T"),
    "michael_levin":      ("bold green",   "L"),
    "design_og_print":    ("bold yellow",  "D"),
    "nynorsk_akademikar": ("bold blue",    "N"),
    "system":             ("bold white",   "SYS"),
}


def agent_say(agent_id: str, message: str, action: str = ""):
    """Display a colored, bold message from a specific agent."""
    color, short = AGENT_COLORS.get(agent_id, ("bold white", agent_id[:3].upper()))
    if HAS_RICH:
        prefix = f"[{color}][{short}][/{color}]"
        if action:
            console.print(f"  {prefix} [dim]{action}:[/dim] {message}")
        else:
            console.print(f"  {prefix} {message}")
    else:
        # ANSI fallback
        codes = {
            "bold cyan": "\033[1;36m", "bold magenta": "\033[1;35m",
            "bold green": "\033[1;32m", "bold yellow": "\033[1;33m",
            "bold blue": "\033[1;34m", "bold white": "\033[1;37m",
        }
        c = codes.get(color, "\033[1m")
        reset = "\033[0m"
        if action:
            print(f"  {c}[{short}]{reset} {action}: {message}")
        else:
            print(f"  {c}[{short}]{reset} {message}")


def agent_phase(phase: str, description: str = ""):
    """Display a phase separator."""
    if HAS_RICH:
        console.rule(f"[bold]{phase}[/bold]")
        if description:
            console.print(f"  [dim]{description}[/dim]")
    else:
        w = os.get_terminal_size((80, 24)).columns
        side = (w - len(phase) - 2) // 2
        print(f"\n{'━' * side} {phase} {'━' * side}")
        if description:
            print(f"  {description}")


# ═══════════════════════════════════════════════════════════════════════════
# STAB (staff) management
# ═══════════════════════════════════════════════════════════════════════════

def load_all_staff() -> dict:
    """Last alle .yaml-filer frå stab/."""
    staff = {}
    if not STAB_DIR.exists():
        return staff
    for f in sorted(STAB_DIR.glob("*.yaml")):
        try:
            data = load_yaml(f)
            sid = data.get("id", f.stem)
            staff[sid] = data
            staff[sid]["_path"] = str(f)
        except Exception as e:
            console.print(f"  [red]Feil ved lasting av {f.name}: {e}[/red]")
    return staff


def display_staff(staff: dict):
    """Vis tilgjengeleg stab."""
    if HAS_RICH:
        table = Table(title="Tilgjengeleg stab", show_lines=True)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Namn", style="bold")
        table.add_column("Rolle", style="green")
        table.add_column("Skildring", max_width=50)
        table.add_column("Modell", style="dim")
        for sid, s in staff.items():
            desc = s.get("description", "").strip()
            if len(desc) > 80:
                desc = desc[:77] + "..."
            table.add_row(
                sid,
                s.get("name", "?"),
                s.get("role", "?"),
                desc,
                s.get("default_model", ""),
            )
        console.print(table)
    else:
        print("\n  Tilgjengeleg stab:")
        print(f"  {'ID':<22} {'Namn':<22} {'Rolle':<18}")
        print(f"  {'─'*22} {'─'*22} {'─'*18}")
        for sid, s in staff.items():
            print(f"  {sid:<22} {s.get('name','?'):<22} {s.get('role','?'):<18}")


def create_staff_interactive():
    """Lag ein ny stabsmedlem interaktivt."""
    console.rule("Ny stabsmedlem")

    sid = input("  ID (kort, utan mellomrom): ").strip()
    if not sid:
        return

    name = input("  Fullt namn: ").strip()
    role = input("  Rolle (t.d. forfattar, redaktoer, kritikar): ").strip()
    description = input("  Kort skildring: ").strip()

    print("  Systemprompt (fleire linjer, avslut med tom linje):")
    prompt_lines = []
    while True:
        line = input("    ")
        if not line.strip():
            break
        prompt_lines.append(line)

    models = ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"]
    print("  Modell:")
    for i, m in enumerate(models, 1):
        print(f"    {i}. {m}")
    mc = input("  Val [2]: ").strip()
    try:
        model = models[int(mc) - 1]
    except (ValueError, IndexError):
        model = models[1]

    print("  Avgrensingar (ei per linje, tom = ferdig):")
    constraints = []
    while True:
        c = input("    - ").strip()
        if not c:
            break
        constraints.append(c)

    print("  Ferdigheiter (ei per linje, tom = ferdig):")
    skills = []
    while True:
        s = input("    - ").strip()
        if not s:
            break
        skills.append(s)

    data = {
        "id": sid,
        "name": name,
        "role": role,
        "description": description,
        "default_model": model,
        "system_prompt": "\n".join(prompt_lines),
    }
    if constraints:
        data["constraints"] = constraints
    if skills:
        data["skills"] = skills

    out = STAB_DIR / f"{sid}.yaml"
    save_yaml(out, data)
    print(f"\n  Stabsmedlem '{name}' lagra til {out}")


# ═══════════════════════════════════════════════════════════════════════════
# PROSJEKT management
# ═══════════════════════════════════════════════════════════════════════════

def slugify(name: str) -> str:
    """Lag ein filsystem-trygg slug frå eit prosjektnamn."""
    s = name.lower()
    for src, dst in [("å", "a"), ("ø", "o"), ("æ", "ae"), (" ", "-")]:
        s = s.replace(src, dst)
    return re.sub(r"[^a-z0-9\-]", "", s)


def list_projects() -> list:
    """Vis alle prosjekt."""
    if not PROJECTS_DIR.exists():
        return []
    projects = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        pfile = d / "project.yaml"
        if d.is_dir() and pfile.exists():
            try:
                data = load_yaml(pfile)
                data["_dir"] = str(d)
                data["_slug"] = d.name
                projects.append(data)
            except Exception:
                pass
    return projects


def display_projects(projects: list):
    """Vis prosjektliste."""
    if not projects:
        print("  Ingen prosjekt funne.")
        return
    if HAS_RICH:
        table = Table(title="Prosjekt")
        table.add_column("#", style="dim")
        table.add_column("Namn", style="bold")
        table.add_column("Stab", style="cyan")
        table.add_column("Modell", style="green")
        table.add_column("Sesjonar", justify="right")
        for i, p in enumerate(projects, 1):
            n_sessions = len(list_sessions(Path(p["_dir"])))
            table.add_row(
                str(i),
                p.get("name", "?"),
                ", ".join(p.get("staff", [])),
                p.get("config", {}).get("default_model", "?"),
                str(n_sessions),
            )
        console.print(table)
    else:
        for i, p in enumerate(projects, 1):
            n_sessions = len(list_sessions(Path(p["_dir"])))
            print(f"  {i}. {p.get('name','?')} [{', '.join(p.get('staff',[]))}] ({n_sessions} sesjonar)")


def create_project_interactive(staff: dict) -> str | None:
    """Lag eit nytt prosjekt interaktivt."""
    console.rule("Nytt prosjekt")

    name = input("  Prosjektnamn: ").strip()
    if not name:
        print("  Avbrote.")
        return None

    slug = slugify(name)
    project_dir = PROJECTS_DIR / slug
    if project_dir.exists():
        print(f"  Prosjektet '{slug}' finst allereie. Bruk 'open'.")
        return slug

    description = input("  Skildring: ").strip()

    print("  Mål (ei per linje, tom = ferdig):")
    goals = []
    while True:
        g = input("    - ").strip()
        if not g:
            break
        goals.append(g)

    # Stabsval
    print()
    display_staff(staff)
    print("\n  Vel stab (kommaseparert ID, eller 'alle'):")
    staff_input = input("  Stab: ").strip()
    if staff_input.lower() == "alle":
        selected = list(staff.keys())
    else:
        selected = [s.strip() for s in staff_input.split(",") if s.strip() in staff]

    # Modellval
    models = ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"]
    print("\n  Vel standard språkmodell:")
    for i, m in enumerate(models, 1):
        print(f"    {i}. {m}")
    mc = input("  Val [2]: ").strip()
    try:
        model = models[int(mc) - 1]
    except (ValueError, IndexError):
        model = models[1]

    # Nettsøk
    web = input("  Tillat nettsøk? (j/n) [n]: ").strip().lower() == "j"

    # Språk
    lang = input("  Språk [nynorsk]: ").strip() or "nynorsk"

    # Bygg prosjekt
    project = {
        "name": name,
        "slug": slug,
        "description": description,
        "goals": goals,
        "staff": selected,
        "config": {
            "default_model": model,
            "web_search": web,
            "language": lang,
        },
        "created": datetime.now().isoformat(timespec="seconds"),
    }

    # Opprett mapper
    for sub in ["context", "sessions", "output", "log", "redaksjon"]:
        (project_dir / sub).mkdir(parents=True, exist_ok=True)

    save_yaml(project_dir / "project.yaml", project)

    # Tom references.bib
    bib = project_dir / "references.bib"
    bib.write_text(
        f"% references.bib — {name}\n"
        f"% Opprettet {datetime.now().strftime('%Y-%m-%d')}\n\n",
        encoding="utf-8",
    )

    print(f"\n  Prosjekt '{name}' opprettet i {project_dir}/")
    return slug


# ═══════════════════════════════════════════════════════════════════════════
# SESJON management
# ═══════════════════════════════════════════════════════════════════════════

def list_sessions(project_dir: Path) -> list:
    """List sesjonar for eit prosjekt."""
    sdir = Path(project_dir) / "sessions"
    if not sdir.exists():
        return []
    sessions = []
    for f in sorted(sdir.glob("*.yaml")):
        try:
            data = load_yaml(f)
            data["_path"] = str(f)
            sessions.append(data)
        except Exception:
            pass
    return sessions


def create_session(project_dir: Path, project: dict) -> str:
    """Opprett ny sesjon."""
    sdir = project_dir / "sessions"
    sdir.mkdir(exist_ok=True)

    existing = list(sdir.glob("*.yaml"))
    num = len(existing) + 1
    sid = f"session_{num:03d}"

    desc = input("  Sesjonskildring: ").strip() or f"Sesjon {num}"

    # Stab for denne sesjonen (kan overstyre prosjektstab)
    proj_staff = project.get("staff", [])
    print(f"  Stab [{', '.join(proj_staff)}] (Enter for standard, eller skriv nye):")
    staff_override = input("  > ").strip()
    if staff_override:
        session_staff = [s.strip() for s in staff_override.split(",")]
    else:
        session_staff = proj_staff

    # Modell for denne sesjonen
    proj_model = project.get("config", {}).get("default_model", "claude-sonnet-4-6")
    models = ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"]
    print(f"  Modell [{proj_model}] (Enter for standard):")
    for i, m in enumerate(models, 1):
        marker = " <-" if m == proj_model else ""
        print(f"    {i}. {m}{marker}")
    mc = input("  > ").strip()
    if mc:
        try:
            session_model = models[int(mc) - 1]
        except (ValueError, IndexError):
            session_model = proj_model
    else:
        session_model = proj_model

    session = {
        "id": sid,
        "project": project.get("name", ""),
        "description": desc,
        "created": datetime.now().isoformat(timespec="seconds"),
        "updated": datetime.now().isoformat(timespec="seconds"),
        "status": "active",
        "staff": session_staff,
        "config": {
            "model": session_model,
            "web_search": project.get("config", {}).get("web_search", False),
        },
        "history": [],
        "notes": "",
    }

    save_yaml(sdir / f"{sid}.yaml", session)
    print(f"  Sesjon '{sid}' opprettet.")
    return sid


def log_action(session_path: Path, agent_id: str, action: str, details: str = ""):
    """Logg ei handling i sesjonen."""
    session = load_yaml(session_path)
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agent": agent_id,
        "action": action,
    }
    if details:
        entry["details"] = details
    if "history" not in session:
        session["history"] = []
    session["history"].append(entry)
    session["updated"] = datetime.now().isoformat(timespec="seconds")
    # Fjern interne felt
    clean = {k: v for k, v in session.items() if not k.startswith("_")}
    save_yaml(session_path, clean)


# ═══════════════════════════════════════════════════════════════════════════
# BYGG (auto-build PDF/DOCX)
# ═══════════════════════════════════════════════════════════════════════════

import subprocess
import shutil
import glob as globmod


def detect_build_type(project_dir: Path) -> str:
    """Detect whether project uses LaTeX or Markdown drafts."""
    utkast_dir = project_dir / "utkast"
    if not utkast_dir.exists():
        return "none"
    # Check latest utkast folder
    utkast_folders = sorted(utkast_dir.iterdir(), reverse=True)
    for folder in utkast_folders:
        if folder.is_dir():
            tex_files = list(folder.glob("*.tex"))
            md_files = list(folder.glob("*.md"))
            if tex_files:
                return "latex"
            if md_files:
                return "markdown"
    return "none"


def find_latest_draft(project_dir: Path, ext: str = ".tex") -> Path | None:
    """Find the most recent draft file."""
    utkast_dir = project_dir / "utkast"
    if not utkast_dir.exists():
        return None
    for folder in sorted(utkast_dir.iterdir(), reverse=True):
        if folder.is_dir():
            files = sorted(folder.glob(f"*{ext}"), reverse=True)
            if files:
                return files[0]
    return None


def build_latex(project_dir: Path, draft_path: Path) -> Path | None:
    """Build PDF from LaTeX source. Returns path to PDF or None."""
    output_dir = project_dir / "output"
    output_dir.mkdir(exist_ok=True)

    # Copy .tex to output dir for compilation
    tex_name = draft_path.name
    stem = draft_path.stem
    work_tex = output_dir / tex_name

    # Copy all .tex files from the draft folder (main + \input files)
    for tex_file in draft_path.parent.glob("*.tex"):
        shutil.copy2(tex_file, output_dir / tex_file.name)

    # Copy references.bib if exists
    bib_src = project_dir / "references.bib"
    if bib_src.exists():
        shutil.copy2(bib_src, output_dir / "references.bib")

    # Check for pdflatex
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        console.print("  [red]pdflatex ikkje funne. Installer MiKTeX eller TeX Live.[/red]")
        return None

    biber = shutil.which("biber")

    agent_say("design_og_print", f"Kompilerer {tex_name}", "bygg")

    # Clean stale aux files that may reference old packages
    for ext in [".aux", ".bcf", ".bbl", ".blg", ".run.xml", ".out", ".toc", ".log"]:
        stale = output_dir / f"{stem}{ext}"
        if stale.exists():
            stale.unlink()

    # Pass 1
    r = subprocess.run(
        [pdflatex, "-interaction=nonstopmode", tex_name],
        cwd=str(output_dir), capture_output=True, text=True, timeout=120
    )
    # Check for real errors (lines starting with !)
    errors = [l for l in r.stdout.splitlines() if l.startswith("!")]
    if errors:
        console.print(f"  [red]LaTeX-feil:[/red]")
        for e in errors[:5]:
            console.print(f"    {e}")
        return None

    # Biber pass (only if .bcf was generated, meaning biblatex is used)
    bcf = output_dir / f"{stem}.bcf"
    if biber and bcf.exists():
        subprocess.run(
            [biber, stem],
            cwd=str(output_dir), capture_output=True, text=True, timeout=60
        )

    # Pass 2 + 3
    for _ in range(2):
        subprocess.run(
            [pdflatex, "-interaction=nonstopmode", tex_name],
            cwd=str(output_dir), capture_output=True, text=True, timeout=120
        )

    pdf_path = output_dir / f"{stem}.pdf"
    if pdf_path.exists():
        size_kb = pdf_path.stat().st_size / 1024
        agent_say("design_og_print", f"PDF bygd: {pdf_path.name} ({size_kb:.0f} KB)", "ferdig")
        return pdf_path
    else:
        console.print("  [red]PDF vart ikkje generert.[/red]")
        return None


def build_markdown(project_dir: Path, draft_path: Path) -> Path | None:
    """Build PDF from Markdown via build script or pandoc."""
    output_dir = project_dir / "output"
    output_dir.mkdir(exist_ok=True)

    # Check for a build script in the project
    build_scripts = list((project_dir / "redaksjon").glob("build_*.py"))
    if not build_scripts:
        build_scripts = list(project_dir.glob("build_*.py"))

    if build_scripts:
        script = build_scripts[0]
        console.print(f"  Køyrer {script.name}...")
        r = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(project_dir), capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0:
            # Find the newest PDF in output
            pdfs = sorted(output_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
            if pdfs:
                console.print(f"  [green]PDF bygd: {pdfs[0].name}[/green]")
                return pdfs[0]

    # Fallback: try pandoc
    pandoc = shutil.which("pandoc")
    if pandoc:
        stem = draft_path.stem
        out_pdf = output_dir / f"{stem}.pdf"
        console.print(f"  Bygger via pandoc...")
        r = subprocess.run(
            [pandoc, str(draft_path), "-o", str(out_pdf),
             "--pdf-engine=pdflatex"],
            capture_output=True, text=True, timeout=120
        )
        if out_pdf.exists():
            console.print(f"  [green]PDF bygd: {out_pdf.name}[/green]")
            return out_pdf

    console.print("  [red]Ingen byggmetode tilgjengeleg (ingen build_*.py eller pandoc).[/red]")
    return None


def build_project(project_dir: Path, project: dict) -> Path | None:
    """Auto-detect and build the project. Returns path to PDF."""
    build_type = detect_build_type(project_dir)

    if build_type == "latex":
        draft = find_latest_draft(project_dir, ".tex")
        if draft:
            console.print(f"  Utkast: {draft.relative_to(project_dir)}")
            return build_latex(project_dir, draft)
    elif build_type == "markdown":
        draft = find_latest_draft(project_dir, ".md")
        if draft:
            console.print(f"  Utkast: {draft.relative_to(project_dir)}")
            return build_markdown(project_dir, draft)
    else:
        console.print("  [yellow]Ingen utkast funne i utkast/.[/yellow]")
        return None


def update_references(project_dir: Path, new_entries: list[dict] | None = None):
    """Add new BibTeX entries to references.bib if not already present."""
    bib_path = project_dir / "references.bib"
    if not bib_path.exists():
        bib_path.write_text(
            f"% references.bib\n"
            f"% Opprettet {datetime.now().strftime('%Y-%m-%d')}\n\n",
            encoding="utf-8"
        )

    if not new_entries:
        return

    existing = bib_path.read_text(encoding="utf-8")
    added = 0
    for entry in new_entries:
        key = entry.get("key", "")
        if key and key not in existing:
            existing += f"\n{entry.get('bibtex', '')}\n"
            added += 1

    if added:
        bib_path.write_text(existing, encoding="utf-8")
        console.print(f"  [green]{added} nye referansar lagt til references.bib[/green]")


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEMPROMPT generering
# ═══════════════════════════════════════════════════════════════════════════

def generate_system_prompt(
    staff_member: dict,
    project: dict,
    session: dict | None = None,
) -> str:
    """Generer komplett systemprompt for ein agent."""
    parts = []

    # Identitet
    parts.append(f"# {staff_member.get('name', 'Agent')}")
    parts.append(f"**Rolle:** {staff_member.get('role', 'ukjend')}")
    parts.append("")

    # Systemprompt
    sp = staff_member.get("system_prompt", "")
    if sp:
        parts.append(sp.strip())
        parts.append("")

    # Prosjektkontekst
    parts.append("---")
    parts.append("## Prosjektkontekst")
    parts.append(f"**Prosjekt:** {project.get('name', '?')}")
    if project.get("description"):
        parts.append(f"**Skildring:** {project['description']}")
    goals = project.get("goals", [])
    if goals:
        parts.append("**Mål:**")
        for g in goals:
            parts.append(f"- {g}")

    config = project.get("config", {})
    if config.get("language"):
        parts.append(f"\n**Språk:** {config['language']}")

    # Avgrensingar
    constraints = staff_member.get("constraints", [])
    if constraints:
        parts.append("\n## Avgrensingar")
        for c in constraints:
            parts.append(f"- {c}")

    # Sesjonskontekst
    if session:
        parts.append(f"\n## Sesjon")
        parts.append(f"**ID:** {session.get('id', '?')}")
        parts.append(f"**Skildring:** {session.get('description', '')}")
        history = session.get("history", [])
        if history:
            parts.append(f"\n**Tidlegare handlingar i denne sesjonen:**")
            for h in history[-10:]:
                ts = h.get("timestamp", "?")[:16]
                parts.append(f"- [{ts}] {h.get('agent','?')}: {h.get('action','')}")

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# TUI — Menyar
# ═══════════════════════════════════════════════════════════════════════════

def pick(title: str, options: list[str], back_label: str = "Tilbake") -> int:
    """Vis meny, returner 0-basert indeks eller -1 for tilbake."""
    print()
    if HAS_RICH:
        console.print(f"[bold]{title}[/bold]")
    else:
        print(f"  {title}")

    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print(f"  0. {back_label}")

    try:
        c = int(input("\n  > ").strip())
        return c - 1 if c > 0 else -1
    except (ValueError, EOFError):
        return -1


# ─── Hovudmeny ─────────────────────────────────────────────────────────

def main_menu():
    """Interaktiv hovudmeny."""
    while True:
        staff = load_all_staff()
        projects = list_projects()

        print()
        if HAS_RICH:
            console.print(
                Panel.fit(
                    "[bold]REDAKSJON[/bold]\n"
                    "Redaksjonell arkitektur for autonome agentar",
                    border_style="blue",
                )
            )
        else:
            console.rule("REDAKSJON")

        console.print(
            f"  Stab: {len(staff)} tilgjengelege  |  Prosjekt: {len(projects)}"
        )

        choice = pick(
            "Hovudmeny",
            [
                "Nytt prosjekt",
                "Opne prosjekt",
                "Vis stab",
                "Lag ny stabsmedlem",
            ],
            back_label="Avslutt",
        )

        if choice == -1:
            print("  Ha det!")
            break
        elif choice == 0:
            create_project_interactive(staff)
        elif choice == 1:
            project_select_menu(projects, staff)
        elif choice == 2:
            display_staff(staff)
            input("\n  [Enter for å gå tilbake] ")
        elif choice == 3:
            create_staff_interactive()


# ─── Prosjektval ───────────────────────────────────────────────────────

def project_select_menu(projects: list, staff: dict):
    """Vel eit prosjekt å opne."""
    if not projects:
        print("  Ingen prosjekt funne. Lag eit nytt fyrst.")
        return

    display_projects(projects)
    names = [p.get("name", "?") for p in projects]
    choice = pick("Vel prosjekt", names)
    if choice >= 0:
        project_menu(projects[choice], staff)


# ─── Prosjektmeny ─────────────────────────────────────────────────────

def project_menu(project: dict, staff: dict):
    """Meny for eit spesifikt prosjekt."""
    project_dir = Path(project["_dir"])

    while True:
        sessions = list_sessions(project_dir)
        active = [s for s in sessions if s.get("status") == "active"]

        print()
        if HAS_RICH:
            console.print(
                Panel.fit(
                    f"[bold]{project.get('name','?')}[/bold]\n"
                    f"{project.get('description','')}",
                    border_style="green",
                )
            )
        else:
            console.rule(project.get("name", "?"))
            print(f"  {project.get('description', '')}")

        cfg = project.get("config", {})
        console.print(f"  Stab: {', '.join(project.get('staff', []))}")
        console.print(
            f"  Modell: {cfg.get('default_model','?')}  |  "
            f"Nettsøk: {'ja' if cfg.get('web_search') else 'nei'}  |  "
            f"Språk: {cfg.get('language','?')}"
        )
        console.print(f"  Sesjonar: {len(sessions)} ({len(active)} aktive)")

        choice = pick(
            "Prosjektmeny",
            [
                "Ny sesjon",
                "Vis / fortset sesjonar",
                "Generer systemprompt",
                "Bygg PDF",
                "Konfigurasjon",
                "Vis references.bib",
                "Vis prosjektfiler",
            ],
        )

        if choice == -1:
            break
        elif choice == 0:
            create_session(project_dir, project)
        elif choice == 1:
            session_list_menu(project_dir, project, staff)
        elif choice == 2:
            prompt_menu(project, staff)
        elif choice == 3:
            result = build_project(project_dir, project)
            if result:
                console.print(f"  Output: {result}")
            input("\n  [Enter] ")
        elif choice == 4:
            configure_project(project_dir, project, staff)
        elif choice == 5:
            bib = project_dir / "references.bib"
            if bib.exists():
                print(bib.read_text(encoding="utf-8"))
            else:
                print("  Ingen references.bib.")
            input("\n  [Enter] ")
        elif choice == 6:
            show_project_files(project_dir)


def show_project_files(project_dir: Path):
    """Vis filstruktur for prosjektet."""
    print(f"\n  {project_dir}/")
    for root, dirs, files in os.walk(project_dir):
        level = len(Path(root).relative_to(project_dir).parts)
        indent = "  " + "  " * level
        dirname = Path(root).name
        if level > 0:
            print(f"{indent}{dirname}/")
        for f in sorted(files):
            print(f"{indent}  {f}")
    input("\n  [Enter] ")


# ─── Sesjonsliste ─────────────────────────────────────────────────────

def session_list_menu(project_dir: Path, project: dict, staff: dict):
    """Vis og handter sesjonar."""
    sessions = list_sessions(project_dir)
    if not sessions:
        print("  Ingen sesjonar. Lag ein ny.")
        return

    icons = {"active": "▶", "paused": "⏸", "completed": "✓"}
    names = []
    for s in sessions:
        icon = icons.get(s.get("status", ""), "?")
        names.append(
            f"{icon} {s.get('id','?')}: {s.get('description','')} ({s.get('status','')})"
        )

    choice = pick("Sesjonar", names)
    if choice >= 0:
        session_menu(sessions[choice], project_dir, project, staff)


# ─── Sesjonsmeny ──────────────────────────────────────────────────────

def session_menu(session: dict, project_dir: Path, project: dict, staff: dict):
    """Meny for ein spesifikk sesjon."""
    session_path = Path(session["_path"])

    while True:
        # Last på nytt
        session = load_yaml(session_path)
        session["_path"] = str(session_path)

        print()
        console.rule(f"{session.get('id','?')} — {session.get('description','')}")
        status = session.get("status", "?")
        model = session.get("config", {}).get("model", "?")
        console.print(f"  Status: {status}  |  Modell: {model}")
        console.print(f"  Stab: {', '.join(session.get('staff', []))}")

        history = session.get("history", [])
        if history:
            print("\n  Siste handlingar:")
            for h in history[-5:]:
                ts = h.get("timestamp", "?")[:16]
                print(f"    [{ts}] {h.get('agent','?')}: {h.get('action','')}")

        is_active = status == "active"
        toggle = "Pause sesjon" if is_active else "Aktiver sesjon"

        choice = pick(
            "Sesjon",
            [
                "Logg handling",
                toggle,
                "Marker fullført",
                "Vis full historikk",
                "Legg til notat",
                "Generer prompt for agent i sesjon",
            ],
        )

        if choice == -1:
            break
        elif choice == 0:
            log_action_interactive(session_path, project, staff)
        elif choice == 1:
            new_status = "paused" if is_active else "active"
            session["status"] = new_status
            session["updated"] = datetime.now().isoformat(timespec="seconds")
            save_yaml(
                session_path,
                {k: v for k, v in session.items() if not k.startswith("_")},
            )
            print(f"  Status: {new_status}")
        elif choice == 2:
            session["status"] = "completed"
            session["updated"] = datetime.now().isoformat(timespec="seconds")
            save_yaml(
                session_path,
                {k: v for k, v in session.items() if not k.startswith("_")},
            )
            print("  Sesjon fullført.")
        elif choice == 3:
            if not history:
                print("  Ingen historikk.")
            else:
                for h in history:
                    ts = h.get("timestamp", "?")[:16]
                    det = h.get("details", "")
                    det_str = f" — {det}" if det else ""
                    print(
                        f"  [{ts}] {h.get('agent','?')}: {h.get('action','')}{det_str}"
                    )
            input("\n  [Enter] ")
        elif choice == 4:
            note = input("  Notat: ").strip()
            if note:
                existing = session.get("notes", "")
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                session["notes"] = f"{existing}\n[{ts}] {note}".strip()
                session["updated"] = datetime.now().isoformat(timespec="seconds")
                save_yaml(
                    session_path,
                    {k: v for k, v in session.items() if not k.startswith("_")},
                )
                print("  Notat lagra.")
        elif choice == 5:
            prompt_menu(project, staff, session)


def log_action_interactive(session_path: Path, project: dict, staff: dict):
    """Logg ei handling interaktivt."""
    proj_staff = project.get("staff", [])
    if not proj_staff:
        print("  Ingen stab.")
        return

    names = []
    for sid in proj_staff:
        s = staff.get(sid, {})
        names.append(f"{s.get('name', sid)}")
    choice = pick("Vel agent", names)
    if choice < 0:
        return

    agent_id = proj_staff[choice]
    action = input("  Handling: ").strip()
    details = input("  Detaljar (valfritt): ").strip()
    log_action(session_path, agent_id, action, details)
    print("  Handling logga.")


# ─── Prompt-generering ────────────────────────────────────────────────

def prompt_menu(project: dict, staff: dict, session: dict | None = None):
    """Generer og vis/lagre systemprompt."""
    proj_staff = project.get("staff", [])
    if not proj_staff:
        print("  Ingen stab konfigurert.")
        return

    all_staff = load_all_staff()
    names = []
    for sid in proj_staff:
        s = all_staff.get(sid, {})
        names.append(s.get("name", sid))
    names.append("— Alle (samla) —")

    choice = pick("Generer systemprompt for", names)
    if choice < 0:
        return

    if choice == len(proj_staff):
        # Alle
        for sid in proj_staff:
            s = all_staff.get(sid, {})
            if s:
                prompt = generate_system_prompt(s, project, session)
                console.rule(s.get("name", sid))
                print(prompt)
        console.rule()
    else:
        sid = proj_staff[choice]
        s = all_staff.get(sid, {})
        if s:
            prompt = generate_system_prompt(s, project, session)
            print(f"\n{prompt}")

            save = input("\n  Lagre til fil? (j/n) [n]: ").strip().lower()
            if save == "j":
                pdir = Path(project["_dir"])
                out = pdir / "output" / f"systemprompt_{sid}.md"
                out.parent.mkdir(exist_ok=True)
                out.write_text(prompt, encoding="utf-8")
                print(f"  Lagra til {out}")

    input("\n  [Enter] ")


# ─── Konfigurasjon ────────────────────────────────────────────────────

def configure_project(project_dir: Path, project: dict, staff: dict):
    """Endre prosjektkonfigurasjon."""
    while True:
        config = project.get("config", {})
        print(f"\n  Konfigurasjon: {project.get('name', '?')}")
        print(f"    1. Modell:    {config.get('default_model', '?')}")
        print(f"    2. Nettsøk:   {'ja' if config.get('web_search') else 'nei'}")
        print(f"    3. Språk:     {config.get('language', '?')}")
        print(f"    4. Stab:      {', '.join(project.get('staff', []))}")
        print(f"    5. Mål:       {len(project.get('goals', []))} definerte")
        print(f"    0. Tilbake")

        try:
            c = int(input("\n  > ").strip())
        except (ValueError, EOFError):
            break

        if c == 0:
            break
        elif c == 1:
            models = ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"]
            for i, m in enumerate(models, 1):
                marker = " <-" if m == config.get("default_model") else ""
                print(f"    {i}. {m}{marker}")
            try:
                config["default_model"] = models[int(input("  > ").strip()) - 1]
            except (ValueError, IndexError):
                pass
        elif c == 2:
            config["web_search"] = not config.get("web_search", False)
        elif c == 3:
            config["language"] = input("  Nytt språk: ").strip() or config.get(
                "language", "nynorsk"
            )
        elif c == 4:
            display_staff(load_all_staff())
            si = input("  Ny stab (kommaseparert): ").strip()
            if si:
                project["staff"] = [s.strip() for s in si.split(",")]
        elif c == 5:
            print("  Noverande mål:")
            for g in project.get("goals", []):
                print(f"    - {g}")
            print("  Legg til nye (tom = ferdig):")
            while True:
                g = input("    - ").strip()
                if not g:
                    break
                project.setdefault("goals", []).append(g)

        project["config"] = config
        save_yaml(
            project_dir / "project.yaml",
            {k: v for k, v in project.items() if not k.startswith("_")},
        )
        print("  Lagra.")


# ═══════════════════════════════════════════════════════════════════════════
# CLI — kommandolinjegrensesnitt
# ═══════════════════════════════════════════════════════════════════════════

def cli():
    """Handter kommandolinjeargument."""
    PROJECTS_DIR.mkdir(exist_ok=True)
    STAB_DIR.mkdir(parents=True, exist_ok=True)

    args = sys.argv[1:]
    if not args:
        main_menu()
        return

    cmd = args[0]

    if cmd == "list":
        projects = list_projects()
        display_projects(projects)

    elif cmd == "staff":
        display_staff(load_all_staff())

    elif cmd == "new":
        create_project_interactive(load_all_staff())

    elif cmd == "open":
        if len(args) < 2:
            print("Bruk: redaksjon.py open <prosjekt-slug>")
            return
        slug = args[1]
        pdir = PROJECTS_DIR / slug
        if not (pdir / "project.yaml").exists():
            print(f"Prosjekt '{slug}' ikkje funne.")
            # Vis tilgjengelege
            projects = list_projects()
            if projects:
                print("Tilgjengelege:")
                for p in projects:
                    print(f"  {p['_slug']}")
            return
        project = load_yaml(pdir / "project.yaml")
        project["_dir"] = str(pdir)
        project["_slug"] = slug
        project_menu(project, load_all_staff())

    elif cmd == "prompt":
        if len(args) < 3:
            print("Bruk: redaksjon.py prompt <prosjekt-slug> <agent-id>")
            return
        slug, agent_id = args[1], args[2]
        pdir = PROJECTS_DIR / slug
        if not (pdir / "project.yaml").exists():
            print(f"Prosjekt '{slug}' ikkje funne.")
            return
        project = load_yaml(pdir / "project.yaml")
        project["_dir"] = str(pdir)
        all_staff = load_all_staff()
        if agent_id not in all_staff:
            print(f"Agent '{agent_id}' ikkje funnen. Tilgjengelege:")
            for sid in all_staff:
                print(f"  {sid}")
            return
        session = None
        if len(args) >= 4:
            sf = pdir / "sessions" / f"{args[3]}.yaml"
            if sf.exists():
                session = load_yaml(sf)
        print(generate_system_prompt(all_staff[agent_id], project, session))

    elif cmd == "session":
        if len(args) < 2:
            print("Bruk: redaksjon.py session <prosjekt-slug>")
            return
        slug = args[1]
        pdir = PROJECTS_DIR / slug
        if not (pdir / "project.yaml").exists():
            print(f"Prosjekt '{slug}' ikkje funne.")
            return
        sessions = list_sessions(pdir)
        icons = {"active": "▶", "paused": "⏸", "completed": "✓"}
        for s in sessions:
            icon = icons.get(s.get("status", ""), "?")
            print(
                f"  {icon} {s.get('id','?')}: {s.get('description','')} [{s.get('status','')}]"
            )

    elif cmd == "build":
        if len(args) < 2:
            print("Bruk: redaksjon.py build <prosjekt-slug>")
            return
        slug = args[1]
        pdir = PROJECTS_DIR / slug
        if not (pdir / "project.yaml").exists():
            print(f"Prosjekt '{slug}' ikkje funne.")
            return
        project = load_yaml(pdir / "project.yaml")
        project["_dir"] = str(pdir)
        result = build_project(pdir, project)
        if result:
            print(f"  Output: {result}")

    elif cmd in ("help", "--help", "-h"):
        print(__doc__)

    else:
        print(f"Ukjend kommando: {cmd}")
        print("Bruk: redaksjon.py [list|staff|new|open|prompt|session|build|help]")


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cli()
