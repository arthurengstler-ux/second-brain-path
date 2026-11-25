const { Plugin, ItemView, Notice, requestUrl } = require("obsidian");
const path = require("path");
const { spawn } = require("child_process");

const VIEW = "brain-dashboard";
const PORT = 8765;
const URL_BASE = `http://localhost:${PORT}`;

async function serverUp() {
  try { const r = await requestUrl({ url: `${URL_BASE}/api/version`, throw: false }); return r.status === 200; }
  catch (e) { return false; }
}

class BrainView extends ItemView {
  constructor(leaf, plugin) { super(leaf); this.plugin = plugin; }
  getViewType() { return VIEW; }
  getDisplayText() { return "Second Brain"; }
  getIcon() { return "brain-circuit"; }
  async onOpen() { await this.load_(); }
  async load_() {
    const c = this.containerEl.children[1];
    c.empty();
    c.style.padding = "0"; c.style.overflow = "hidden";
    const msg = c.createDiv({ text: "Second Brain startet …" });
    msg.style.cssText = "padding:24px;color:var(--text-muted)";
    const ok = await this.plugin.ensureServer();
    if (!ok) {
      msg.setText("Server konnte nicht starten. Prüfe, ob /usr/bin/python3 existiert, und lade den Tab neu.");
      const b = c.createEl("button", { text: "Erneut versuchen" });
      b.style.margin = "0 24px"; b.onclick = () => this.load_();
      return;
    }
    msg.remove();
    const theme = document.body.classList.contains("theme-dark") ? "dark" : "light";
    this.frame = c.createEl("iframe", { attr: { src: `${URL_BASE}/?embed=1&theme=${theme}` } });
    this.frame.style.cssText = "width:100%;height:100%;border:0;display:block";
  }
  reload() { if (this.frame) this.load_(); }
}

module.exports = class BrainDashboard extends Plugin {
  async onload() {
    this.registerView(VIEW, (leaf) => new BrainView(leaf, this));
    this.addRibbonIcon("brain-circuit", "Second Brain öffnen", () => this.openView());
    this.addCommand({ id: "open", name: "Dashboard öffnen", callback: () => this.openView() });
    this.addCommand({ id: "reload", name: "Dashboard neu laden", callback: () => this.views().forEach(v => v.reload()) });

    // Klicks im Dashboard öffnen Notizen in Obsidian
    this.registerDomEvent(window, "message", (ev) => {
      if (ev.origin !== URL_BASE || !ev.data || ev.data.type !== "brain-open") return;
      const file = this.app.vault.getAbstractFileByPath(String(ev.data.path));
      if (file) this.app.workspace.getLeaf("tab").openFile(file);
    });
    // Theme-Wechsel an das Dashboard weitergeben
    this.registerEvent(this.app.workspace.on("css-change", () => this.views().forEach(v => v.reload())));

    this.app.workspace.onLayoutReady(async () => {
      await this.ensureServer();
      // Dashboard beim Start immer öffnen, falls noch kein Tab offen ist
      if (!this.app.workspace.getLeavesOfType(VIEW).length) this.openView();
    });
    // Server alle 30 s prüfen und bei Bedarf neu starten
    this.registerInterval(window.setInterval(() => this.ensureServer(), 30000));
  }
  views() { return this.app.workspace.getLeavesOfType(VIEW).map(l => l.view).filter(v => v instanceof BrainView); }
  async openView() {
    const existing = this.app.workspace.getLeavesOfType(VIEW)[0];
    if (existing) return this.app.workspace.revealLeaf(existing);
    const leaf = this.app.workspace.getLeaf("tab");
    await leaf.setViewState({ type: VIEW, active: true });
    this.app.workspace.revealLeaf(leaf);
  }
  async ensureServer() {
    if (await serverUp()) return true;
    if (!this.starting) {
      const base = this.app.vault.adapter.getBasePath();
      try {
        this.proc = spawn("/usr/bin/python3", [path.join(base, "scripts", "brain.py"), "serve"], { cwd: base, stdio: "ignore" });
        this.proc.on("error", (e) => new Notice("Second Brain: " + e.message));
        this.proc.on("exit", () => { this.proc = null; this.starting = null; });
      } catch (e) { new Notice("Second Brain: " + e.message); return false; }
      this.starting = true;
    }
    for (let i = 0; i < 20; i++) {
      await new Promise(r => setTimeout(r, 250));
      if (await serverUp()) return true;
    }
    return false;
  }
  onunload() { if (this.proc) this.proc.kill(); }
};
