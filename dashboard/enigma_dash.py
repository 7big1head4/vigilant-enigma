#!/usr/bin/env python3
# Enigma dashboard — live system and agent stats for the machine Enigma runs on.
#
# Copyright (C) 2026 the Enigma authors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# Standard library only — no pip installs. Reads /proc and /sys directly,
# which keeps the idle footprint near zero on the Raspberry Pi 5 reference
# target. Serves one HTML page (a PWA, so it can be added to a phone's home
# screen), a JSON stats API, a web manifest, and an icon.
#
# The "Enigma agents" panel is live: the Rust kernel streams status.json
# into its state directory while it runs (throttled to 250 ms), and this
# server picks it up on every sample, so agents appear, suspend, and die
# in real time on the page.
#
# Usage:
#   python3 dashboard/enigma_dash.py [--host 0.0.0.0] [--port 8765]
#
# The server binds to all interfaces by default so phones on the LAN can
# reach it. There is NO authentication — only run it on networks you trust.

import argparse
import json
import os
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SAMPLE_INTERVAL = 1.0  # seconds between samples — keeps the page fluid
TOP_PROCESSES = 8

_CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


def read_cpu_times():
    """Per-CPU (busy, total) jiffies from /proc/stat, plus the 'cpu' total."""
    out = {}
    text = _read("/proc/stat") or ""
    for line in text.splitlines():
        if not line.startswith("cpu"):
            continue
        parts = line.split()
        name, fields = parts[0], [int(x) for x in parts[1:]]
        idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
        total = sum(fields)
        out[name] = (total - idle, total)
    return out


def read_meminfo():
    info = {}
    text = _read("/proc/meminfo") or ""
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        info[key] = int(rest.split()[0]) * 1024  # kB -> bytes
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    return {"total": total, "used": total - avail, "available": avail}


def read_net_bytes():
    """Total (rx, tx) bytes across non-loopback interfaces."""
    rx = tx = 0
    text = _read("/proc/net/dev") or ""
    for line in text.splitlines()[2:]:
        name, _, rest = line.partition(":")
        if name.strip() == "lo":
            continue
        fields = rest.split()
        if len(fields) >= 9:
            rx += int(fields[0])
            tx += int(fields[8])
    return rx, tx


def read_temperature():
    """CPU temperature in Celsius, or None. Prefers a cpu-ish thermal zone."""
    best = None
    zones = []
    base = "/sys/class/thermal"
    try:
        zones = [z for z in os.listdir(base) if z.startswith("thermal_zone")]
    except OSError:
        pass
    for zone in zones:
        raw = _read(f"{base}/{zone}/temp")
        if raw is None:
            continue
        try:
            temp = int(raw.strip()) / 1000.0
        except ValueError:
            continue
        ztype = (_read(f"{base}/{zone}/type") or "").strip().lower()
        if "cpu" in ztype or "soc" in ztype:
            return temp
        best = max(best, temp) if best is not None else temp
    return best


def read_throttled():
    """Raspberry Pi firmware throttle flags via vcgencmd, or None elsewhere."""
    try:
        out = subprocess.run(
            ["vcgencmd", "get_throttled"],
            capture_output=True, text=True, timeout=2,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    if "=" not in out:
        return None
    try:
        bits = int(out.strip().split("=")[1], 16)
    except ValueError:
        return None
    return {
        "under_voltage": bool(bits & 0x1),
        "throttled": bool(bits & 0x4),
        "soft_temp_limit": bool(bits & 0x8),
        "was_throttled": bool(bits & 0x40000),
    }


def read_agents():
    """The Enigma kernel's live status.json, or None if no kernel has run.

    Resolution order: $ENIGMA_STATUS (explicit file), then
    $ENIGMA_STATE_DIR/status.json, then ~/.enigma/status.json — matching
    the kernel's KernelConfig::from_env().
    """
    path = os.environ.get("ENIGMA_STATUS")
    if not path:
        state_dir = os.environ.get(
            "ENIGMA_STATE_DIR", os.path.expanduser("~/.enigma"))
        path = os.path.join(state_dir, "status.json")
    raw = _read(path)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None  # mid-write race: keep last known state client-side


def read_processes(prev, dt):
    """Top processes by CPU. prev maps pid -> jiffies; returns (list, new prev)."""
    page = os.sysconf("SC_PAGE_SIZE")
    now = {}
    procs = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        stat = _read(f"/proc/{pid}/stat")
        if stat is None:
            continue
        # comm can contain spaces/parens; split around the last ')'
        rparen = stat.rfind(")")
        name = stat[stat.find("(") + 1:rparen]
        fields = stat[rparen + 2:].split()
        try:
            jiffies = int(fields[11]) + int(fields[12])  # utime + stime
        except (IndexError, ValueError):
            continue
        now[pid] = jiffies
        cpu_pct = 0.0
        if pid in prev and dt > 0:
            cpu_pct = 100.0 * (jiffies - prev[pid]) / _CLK_TCK / dt
        rss = 0
        statm = _read(f"/proc/{pid}/statm")
        if statm:
            try:
                rss = int(statm.split()[1]) * page
            except (IndexError, ValueError):
                pass
        procs.append({"pid": int(pid), "name": name,
                      "cpu": round(cpu_pct, 1), "rss": rss})
    procs.sort(key=lambda p: (p["cpu"], p["rss"]), reverse=True)
    return procs[:TOP_PROCESSES], now


class Sampler(threading.Thread):
    """Background sampler: keeps a ready-to-serve snapshot updated."""

    def __init__(self):
        super().__init__(daemon=True)
        self.lock = threading.Lock()
        self.snapshot = {}
        self._cpu_prev = read_cpu_times()
        self._net_prev = read_net_bytes()
        self._proc_prev = {}
        self._t_prev = time.monotonic()

    def run(self):
        while True:
            time.sleep(SAMPLE_INTERVAL)
            try:
                self.sample()
            except Exception:
                pass  # a bad sample must never kill the dashboard

    def sample(self):
        t = time.monotonic()
        dt = t - self._t_prev

        cpu_now = read_cpu_times()
        cores = []
        total_pct = 0.0
        for name in sorted(cpu_now):
            busy, total = cpu_now[name]
            pbusy, ptotal = self._cpu_prev.get(name, (busy, total))
            dtotal = total - ptotal
            pct = 100.0 * (busy - pbusy) / dtotal if dtotal > 0 else 0.0
            if name == "cpu":
                total_pct = pct
            else:
                cores.append(round(pct, 1))

        rx, tx = read_net_bytes()
        prx, ptx = self._net_prev
        net = {
            "rx_bps": max(0.0, (rx - prx) / dt) if dt > 0 else 0.0,
            "tx_bps": max(0.0, (tx - ptx) / dt) if dt > 0 else 0.0,
        }

        procs, self._proc_prev = read_processes(self._proc_prev, dt)

        uptime_raw = _read("/proc/uptime")
        uptime = float(uptime_raw.split()[0]) if uptime_raw else 0.0
        disk = shutil.disk_usage("/")

        snapshot = {
            "time": time.time(),
            "hostname": os.uname().nodename,
            "kernel": f"{os.uname().sysname} {os.uname().release}",
            "arch": os.uname().machine,
            "uptime_s": uptime,
            "load": list(os.getloadavg()),
            "cpu": {"total_pct": round(total_pct, 1), "cores": cores},
            "memory": read_meminfo(),
            "disk": {"total": disk.total, "used": disk.used},
            "net": net,
            "temp_c": read_temperature(),
            "throttled": read_throttled(),
            "processes": procs,
            "agents": read_agents(),
        }

        with self.lock:
            self.snapshot = snapshot
        self._cpu_prev = cpu_now
        self._net_prev = (rx, tx)
        self._t_prev = t

    def get(self):
        with self.lock:
            return dict(self.snapshot)


MANIFEST = json.dumps({
    "name": "Enigma Dashboard",
    "short_name": "Enigma",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#0d0d0d",
    "theme_color": "#0d0d0d",
    "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
})

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">
<rect width="96" height="96" rx="20" fill="#1a1a19"/>
<path d="M62 26H36v14h22v10H36v14h26v10H26V16h36z" fill="#3987e5"/>
</svg>"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0d0d0d">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/icon.svg">
<title>Enigma · dashboard</title>
<style>
:root {
  --page: #f9f9f7; --surface: #fcfcfb;
  --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --border: rgba(11,11,11,0.10);
  --series-1: #2a78d6; --series-2: #1baf7a;
  --seq-150: #b7d3f6; --seq-250: #86b6ef;
  --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root {
    --page: #0d0d0d; --surface: #1a1a19;
    --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
    --series-1: #3987e5; --series-2: #199e70;
    --seq-150: #20293a; --seq-250: #184f95;
  }
}
* { box-sizing: border-box; margin: 0; }
body {
  background: var(--page); color: var(--ink);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
  padding: 16px; max-width: 1080px; margin: 0 auto;
}
header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
         margin: 4px 2px 14px; }
header h1 { font-size: 17px; font-weight: 650; }
header .sub { color: var(--muted); font-size: 12.5px; }
header .dot { width: 8px; height: 8px; border-radius: 50%;
              background: var(--good); align-self: center; }
header .dot.stale { background: var(--critical); }
.grid { display: grid; gap: 10px;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); }
.row { display: grid; gap: 10px; margin-top: 10px;
       grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
.card { background: var(--surface); border: 1px solid var(--border);
        border-radius: 10px; padding: 14px 16px; min-width: 0; }
.card h2 { font-size: 12px; font-weight: 600; color: var(--ink-2);
           margin-bottom: 8px; }
.tile .value { font-size: 30px; font-weight: 650; letter-spacing: -0.01em; }
.tile .value small { font-size: 15px; font-weight: 500; color: var(--ink-2); }
.tile .meta { color: var(--muted); font-size: 12px; margin-top: 2px; }
.meter { height: 6px; border-radius: 3px; background: var(--seq-150);
         margin-top: 10px; overflow: hidden; }
.meter i { display: block; height: 100%; border-radius: 3px; width: 0;
           background: var(--series-1); transition: width .6s ease; }
.status { display: inline-flex; align-items: center; gap: 5px;
          font-size: 12px; color: var(--ink-2); margin-top: 2px; }
.status .sw { width: 9px; height: 9px; border-radius: 50%; }
.spark { display: block; width: 100%; height: 36px; margin-top: 8px; }
.cores { display: flex; flex-direction: column; gap: 6px; }
.core { display: grid; grid-template-columns: 34px 1fr 44px; gap: 8px;
        align-items: center; }
.core .lbl { color: var(--muted); font-size: 11.5px; }
.core .val { color: var(--ink-2); font-size: 11.5px; text-align: right;
             font-variant-numeric: tabular-nums; }
.core .track { height: 12px; background: var(--seq-150); border-radius: 3px;
               overflow: hidden; }
.core .track i { display: block; height: 100%; background: var(--series-1);
                 border-radius: 0 3px 3px 0; transition: width .6s ease; }
.legend { display: flex; gap: 14px; font-size: 12px; color: var(--ink-2);
          margin-bottom: 6px; }
.legend .key { display: inline-flex; align-items: center; gap: 6px; }
.legend .sw { width: 14px; height: 3px; border-radius: 2px; }
#netchart { width: 100%; height: 120px; display: block; }
.tooltip { position: fixed; pointer-events: none; background: var(--surface);
           border: 1px solid var(--border); border-radius: 6px;
           padding: 6px 9px; font-size: 12px; color: var(--ink-2);
           box-shadow: 0 2px 8px rgba(0,0,0,.15); display: none; z-index: 5; }
.tooltip b { color: var(--ink); font-variant-numeric: tabular-nums; }
table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
th { text-align: left; color: var(--muted); font-weight: 500;
     border-bottom: 1px solid var(--grid); padding: 3px 6px 5px; }
td { padding: 4px 6px; border-bottom: 1px solid var(--grid);
     color: var(--ink-2); font-variant-numeric: tabular-nums; }
td:first-child { color: var(--ink); }
th:nth-child(n+3), td:nth-child(n+3) { text-align: right; }
.agents .empty { color: var(--muted); font-size: 12.5px; padding: 8px 0; }
.agents .counts { color: var(--ink-2); font-size: 12.5px; margin-bottom: 8px; }
.agent { display: grid; grid-template-columns: 14px 1fr 130px; gap: 8px;
         align-items: center; padding: 5px 0;
         border-bottom: 1px solid var(--grid); }
.agent:last-child { border-bottom: 0; }
.agent .sw { width: 9px; height: 9px; border-radius: 50%; }
.agent .who { min-width: 0; overflow: hidden; text-overflow: ellipsis;
              white-space: nowrap; font-size: 12.5px; }
.agent .who small { color: var(--muted); }
.agent .tok { text-align: right; }
.agent .tok .txt { color: var(--ink-2); font-size: 11.5px;
                   font-variant-numeric: tabular-nums; }
.agent .tok .meter { margin-top: 3px; height: 4px; }
footer { color: var(--muted); font-size: 11.5px; margin: 14px 2px; }
</style>
</head>
<body>
<header>
  <span class="dot" id="livedot"></span>
  <h1>Enigma</h1>
  <span class="sub" id="hostline">connecting…</span>
</header>

<div class="grid">
  <div class="card tile">
    <h2>CPU</h2>
    <div class="value" id="cpu-val">–<small> %</small></div>
    <div class="meta" id="cpu-meta"></div>
    <svg class="spark" id="cpu-spark" preserveAspectRatio="none"></svg>
  </div>
  <div class="card tile">
    <h2>Memory</h2>
    <div class="value" id="mem-val">–</div>
    <div class="meta" id="mem-meta"></div>
    <div class="meter"><i id="mem-bar"></i></div>
  </div>
  <div class="card tile">
    <h2>Temperature</h2>
    <div class="value" id="temp-val">–</div>
    <div class="status" id="temp-status"></div>
    <div class="meter"><i id="temp-bar"></i></div>
  </div>
  <div class="card tile">
    <h2>Disk (/)</h2>
    <div class="value" id="disk-val">–</div>
    <div class="meta" id="disk-meta"></div>
    <div class="meter"><i id="disk-bar"></i></div>
  </div>
</div>

<div class="row">
  <div class="card">
    <h2>CPU cores</h2>
    <div class="cores" id="cores"></div>
  </div>
  <div class="card">
    <h2>Network</h2>
    <div class="legend">
      <span class="key"><span class="sw" style="background:var(--series-1)"></span>Download</span>
      <span class="key"><span class="sw" style="background:var(--series-2)"></span>Upload</span>
    </div>
    <svg id="netchart" preserveAspectRatio="none"></svg>
  </div>
</div>

<div class="row">
  <div class="card">
    <h2>Top processes</h2>
    <table>
      <thead><tr><th>Name</th><th>PID</th><th>CPU %</th><th>Memory</th></tr></thead>
      <tbody id="procs"></tbody>
    </table>
  </div>
  <div class="card agents">
    <h2>Enigma agents</h2>
    <div id="agents"><div class="empty">
      No kernel state found — run the Enigma runtime (see core/) and its
      agents will appear here live: spawning, suspending, spending tokens.
    </div></div>
  </div>
</div>

<footer id="foot"></footer>
<div class="tooltip" id="tip"></div>

<script>
"use strict";
const HISTORY = 90;
const hist = { cpu: [], rx: [], tx: [] };
let lastOk = 0;

const $ = id => document.getElementById(id);
const css = name =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const esc = s => String(s).replace(/[<>&"]/g,
  c => ({"<":"&lt;",">":"&gt;","&":"&amp;",'"':"&quot;"}[c]));

function fmtBytes(b, perSec) {
  const u = perSec ? ["B/s","KB/s","MB/s","GB/s"] : ["B","KB","MB","GB","TB"];
  let i = 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return (b >= 100 ? b.toFixed(0) : b >= 10 ? b.toFixed(1) : b.toFixed(2))
         + " " + u[i];
}
function fmtUptime(s) {
  const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600),
        m = Math.floor(s % 3600 / 60);
  return (d ? d + "d " : "") + h + "h " + m + "m";
}
function push(arr, v) { arr.push(v); if (arr.length > HISTORY) arr.shift(); }

function sparkline(svg, data, color, fillWash) {
  const W = svg.clientWidth || 200, H = svg.clientHeight || 36;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  if (data.length < 2) { svg.innerHTML = ""; return; }
  const max = Math.max(...data, 1e-9);
  const span = Math.max(data.length - 1, 1);
  const pts = data.map((v, i) =>
    [(i / span) * W, H - 2 - (v / max) * (H - 6)]);
  const line = pts.map((p, i) =>
    (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const last = pts[pts.length - 1];
  let html = "";
  if (fillWash) {
    html += `<path d="${line} L${last[0].toFixed(1)} ${H} L${pts[0][0].toFixed(1)} ${H} Z"
             fill="${color}" opacity="0.1"/>`;
  }
  html += `<path d="${line}" fill="none" stroke="${color}"
           stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
  html += `<circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="4"
           fill="${color}" stroke="${css("--surface")}" stroke-width="2"/>`;
  svg.innerHTML = html;
}

function severity(v, warn, bad) {
  if (v >= bad) return "var(--critical)";
  if (v >= warn) return "var(--serious)";
  return "var(--series-1)";
}

let netGeom = null;
function render(s) {
  $("hostline").textContent =
    `${s.hostname} · ${s.kernel} · ${s.arch} · up ${fmtUptime(s.uptime_s)}`;

  // CPU tile
  push(hist.cpu, s.cpu.total_pct);
  $("cpu-val").innerHTML = s.cpu.total_pct.toFixed(0) + "<small> %</small>";
  $("cpu-meta").textContent =
    "load " + s.load.map(x => x.toFixed(2)).join(" · ");
  sparkline($("cpu-spark"), hist.cpu, css("--series-1"), true);

  // Memory tile
  const m = s.memory, mp = m.total ? 100 * m.used / m.total : 0;
  $("mem-val").innerHTML = fmtBytes(m.used).replace(/ /, "<small> ") +
                           "</small>";
  $("mem-meta").textContent = `of ${fmtBytes(m.total)} (${mp.toFixed(0)}%)`;
  $("mem-bar").style.width = mp.toFixed(1) + "%";
  $("mem-bar").style.background = severity(mp, 80, 92);

  // Temperature tile
  if (s.temp_c != null) {
    $("temp-val").innerHTML =
      s.temp_c.toFixed(1) + "<small> °C</small>";
    const t = s.throttled;
    const hot = s.temp_c >= 80, warm = s.temp_c >= 70;
    const col = hot ? "var(--critical)" : warm ? "var(--serious)"
                                               : "var(--good)";
    let label = hot ? "⚠ hot" : warm ? "△ warm" : "✓ normal";
    if (t && (t.throttled || t.under_voltage)) {
      label += t.throttled ? " · throttled" : " · under-voltage";
    }
    $("temp-status").innerHTML =
      `<span class="sw" style="background:${col}"></span>${label}`;
    $("temp-bar").style.width = Math.min(100, s.temp_c / 90 * 100) + "%";
    $("temp-bar").style.background = col;
  } else {
    $("temp-val").textContent = "—";
    $("temp-status").textContent = "no sensor found";
    $("temp-bar").style.width = "0";
  }

  // Disk tile
  const d = s.disk, dp = d.total ? 100 * d.used / d.total : 0;
  $("disk-val").innerHTML = fmtBytes(d.used).replace(/ /, "<small> ") +
                            "</small>";
  $("disk-meta").textContent = `of ${fmtBytes(d.total)} (${dp.toFixed(0)}%)`;
  $("disk-bar").style.width = dp.toFixed(1) + "%";
  $("disk-bar").style.background = severity(dp, 80, 92);

  // Cores
  $("cores").innerHTML = s.cpu.cores.map((c, i) => `
    <div class="core"><span class="lbl">cpu${i}</span>
      <span class="track"><i style="width:${c}%"></i></span>
      <span class="val">${c.toFixed(0)}%</span></div>`).join("");

  // Network chart (two series, shared scale, tooltip via netGeom)
  push(hist.rx, s.net.rx_bps); push(hist.tx, s.net.tx_bps);
  const svg = $("netchart");
  const W = svg.clientWidth || 400, H = svg.clientHeight || 120;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const max = Math.max(...hist.rx, ...hist.tx, 1024);
  const span = Math.max(hist.rx.length - 1, 1);
  const toPts = a => a.map((v, i) =>
    [(i / span) * W, H - 4 - (v / max) * (H - 14)]);
  const path = p => p.map((q, i) =>
    (i ? "L" : "M") + q[0].toFixed(1) + " " + q[1].toFixed(1)).join(" ");
  const rp = toPts(hist.rx), tp = toPts(hist.tx);
  svg.innerHTML =
    `<line x1="0" y1="${H-4}" x2="${W}" y2="${H-4}"
       stroke="${css("--grid")}" stroke-width="1"/>` +
    `<text x="2" y="11" fill="${css("--muted")}"
       font-size="10">${fmtBytes(max, true)}</text>` +
    `<path d="${path(rp)}" fill="none" stroke="${css("--series-1")}"
       stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>` +
    `<path d="${path(tp)}" fill="none" stroke="${css("--series-2")}"
       stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>` +
    `<g id="net-cursor"></g>`;
  netGeom = { W, H, rx: hist.rx.slice(), tx: hist.tx.slice() };

  // Processes
  $("procs").innerHTML = s.processes.map(p => `
    <tr><td>${esc(p.name)}</td><td>${p.pid}</td>
        <td>${p.cpu.toFixed(1)}</td><td>${fmtBytes(p.rss)}</td></tr>`).join("");

  renderAgents(s.agents);

  $("foot").textContent =
    `Enigma dashboard · refreshed ${new Date(s.time * 1000)
      .toLocaleTimeString()} · every 1s`;
}

function renderAgents(a) {
  if (!a || !Array.isArray(a.agents)) return; // keep placeholder / last state
  const el = $("agents");
  if (a.agents.length === 0) {
    el.innerHTML = `<div class="empty">Kernel is up — no agents yet.</div>`;
    return;
  }
  const stateOf = ag => (ag.state && ag.state.state) || "?";
  const n = s => a.agents.filter(ag => stateOf(ag) === s).length;
  const dot = {
    running: "var(--good)", suspended: "var(--muted)",
    dead: "var(--critical)",
  };
  const rows = a.agents.map(ag => {
    const st = stateOf(ag);
    const reason = (ag.state && ag.state.reason) || "";
    const max = ag.token_budget;
    const pct = max ? Math.min(100, 100 * ag.tokens_used / max) : 0;
    const tokTxt = max == null
      ? `${ag.tokens_used} tok · ∞`
      : `${ag.tokens_used}/${max} tok`;
    return `<div class="agent" title="${esc(st)}${reason ?
        " — " + esc(reason) : ""}">
      <span class="sw" style="background:${dot[st] || "var(--muted)"}"></span>
      <span class="who">${esc(ag.name)} <small>· ${esc(ag.kind)}${
        ag.parent != null ? " · ↳ of agent-" + ag.parent : ""}</small></span>
      <span class="tok"><span class="txt">${tokTxt}</span>
        ${max != null ? `<span class="meter"><i style="width:${pct}%;
          background:${pct >= 92 ? "var(--critical)" : pct >= 80 ?
          "var(--serious)" : "var(--series-1)"}"></i></span>` : ""}
      </span></div>`;
  }).join("");
  el.innerHTML = `<div class="counts">${n("running")} running ·
    ${n("suspended")} suspended · ${n("dead")} dead ·
    ${(a.stats && a.stats.dispatched) || 0} messages</div>${rows}`;
}

// Crosshair tooltip for the network chart
const tip = $("tip");
$("netchart").addEventListener("mousemove", ev => {
  if (!netGeom || netGeom.rx.length < 2) return;
  const r = ev.currentTarget.getBoundingClientRect();
  const frac = (ev.clientX - r.left) / r.width;
  const last = netGeom.rx.length - 1;
  const i = Math.max(0, Math.min(last, Math.round(frac * last)));
  const cur = ev.currentTarget.querySelector("#net-cursor");
  const x = (i / last) * netGeom.W;
  cur.innerHTML =
    `<line x1="${x}" y1="0" x2="${x}" y2="${netGeom.H}"
       stroke="${css("--muted")}" stroke-width="1" opacity="0.5"/>`;
  tip.style.display = "block";
  tip.style.left = (ev.clientX + 14) + "px";
  tip.style.top = (ev.clientY - 10) + "px";
  tip.innerHTML = `↓ <b>${fmtBytes(netGeom.rx[i], true)}</b> &nbsp;
                   ↑ <b>${fmtBytes(netGeom.tx[i], true)}</b>`;
});
$("netchart").addEventListener("mouseleave", ev => {
  tip.style.display = "none";
  const cur = ev.currentTarget.querySelector("#net-cursor");
  if (cur) cur.innerHTML = "";
});

async function tick() {
  try {
    const res = await fetch("/api/stats", { cache: "no-store" });
    const s = await res.json();
    if (s && s.time) { render(s); lastOk = Date.now(); }
  } catch (e) { /* keep last render */ }
  $("livedot").className =
    "dot" + (Date.now() - lastOk > 5000 ? " stale" : "");
}
tick();
setInterval(tick, 1000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    sampler = None  # set in main()

    def _send(self, body, ctype, cache="no-store"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self._send(PAGE, "text/html; charset=utf-8")
        elif path == "/api/stats":
            self._send(json.dumps(self.sampler.get()), "application/json")
        elif path == "/manifest.webmanifest":
            self._send(MANIFEST, "application/manifest+json",
                       cache="max-age=3600")
        elif path == "/icon.svg":
            self._send(ICON_SVG, "image/svg+xml", cache="max-age=86400")
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        pass  # stay quiet; this runs as a long-lived service


def main():
    ap = argparse.ArgumentParser(
        description="Enigma live system-stats dashboard (stdlib only)")
    ap.add_argument("--host", default="0.0.0.0",
                    help="bind address (default: all interfaces; "
                         "no auth — trusted networks only)")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    sampler = Sampler()
    sampler.sample()  # prime so the first request has data
    sampler.start()
    Handler.sampler = sampler

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Enigma dashboard on http://{args.host}:{args.port}/ "
          f"(Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
