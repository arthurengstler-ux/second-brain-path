const { Plugin, ItemView, Notice, requestUrl } = require("obsidian");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");

// Python per platform: macOS ships /usr/bin/python3, Windows uses the py launcher, Linux python3 on PATH.
function pythonCmd() {
  if (process.platform === "win32") return ["py", ["-3"]];
  if (process.platform === "darwin" && fs.existsSync("/usr/bin/python3")) return ["/usr/bin/python3", []];
  return ["python3", []];
}

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
    const msg = c.createDiv({ text: "Second Brain is starting …" });
    msg.style.cssText = "padding:24px;color:var(--text-muted)";
    const ok = await this.plugin.ensureServer();
    if (!ok) {
      msg.setText("Server could not start. Check that Python 3 is installed (python3, or py on Windows) and reload the tab.");
      const b = c.createEl("button", { text: "Try again" });
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
    this.addRibbonIcon("brain-circuit", "Open Second Brain", () => this.openView());
    this.addCommand({ id: "open", name: "Open dashboard", callback: () => this.openView() });
    this.addCommand({ id: "reload", name: "Reload dashboard", callback: () => this.views().forEach(v => v.reload()) });

    // clicks in the dashboard open notes in Obsidian
    this.registerDomEvent(window, "message", (ev) => {
      if (ev.origin !== URL_BASE || !ev.data || ev.data.type !== "brain-open") return;
      const file = this.app.vault.getAbstractFileByPath(String(ev.data.path));
      if (file) this.app.workspace.getLeaf("tab").openFile(file);
    });
    // pass theme changes on to the dashboard
    this.registerEvent(this.app.workspace.on("css-change", () => this.views().forEach(v => v.reload())));

    this.app.workspace.onLayoutReady(async () => {
      await this.ensureServer();
      // open the dashboard on startup if no tab is open yet
      if (!this.app.workspace.getLeavesOfType(VIEW).length) this.openView();
    });
    // check the server every 30 s and restart if needed
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
        const [cmd, pre] = pythonCmd();
        this.proc = spawn(cmd, [...pre, path.join(base, "scripts", "brain.py"), "serve"], { cwd: base, stdio: "ignore", windowsHide: true });
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
