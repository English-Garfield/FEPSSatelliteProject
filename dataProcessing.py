"""
sar_log_graphs.py
=================
Processes sar_log.csv and saves a multi-panel dashboard (sar_dashboard.png)
plus individual PNGs for each chart.

Usage:
    python sar_log_graphs.py                      # expects sar_log.csv in cwd
    python sar_log_graphs.py path/to/sar_log.csv  # explicit path
"""

import sys
import pathlib
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Load

csv_path = sys.argv[1] if len(sys.argv) > 1 else "sar_log.csv"
df = pd.read_csv(csv_path)

# Replace OOR (out-of-range) strings with NaN so numeric columns stay clean
df["slant_cm"]  = pd.to_numeric(df["slant_cm"],  errors="coerce")
df["ground_cm"] = pd.to_numeric(df["ground_cm"], errors="coerce")

# Convenience masks
alerted = df["alert"] == 1
valid_range = df["slant_cm"].notna()

print(f"Loaded {len(df)} pulses | alerts: {alerted.sum()} | valid range readings: {valid_range.sum()}")

out_dir = pathlib.Path(".")

# Shared colour scheme
C_MAIN   = "#2563EB"   # blue  – normal
C_ALERT  = "#DC2626"   # red   – alert
C_ACCENT = "#16A34A"   # green – secondary series
C_BG     = "#F8FAFC"

def alert_colours(series):
    """Return a colour per row based on the alert flag at the same index."""
    return [C_ALERT if a else C_MAIN for a in df.loc[series.index, "alert"]]


# ═══════════════════════════════════════════════════════════════════════════════
# Chart helpers
# ═══════════════════════════════════════════════════════════════════════════════

def shade_alerts(ax, pulse, alert):
    """Draw translucent red bars wherever alert == 1."""
    in_block = False
    for i, (p, a) in enumerate(zip(pulse, alert)):
        if a and not in_block:
            x0 = p
            in_block = True
        elif not a and in_block:
            ax.axvspan(x0, p, color=C_ALERT, alpha=0.12, linewidth=0)
            in_block = False
    if in_block:
        ax.axvspan(x0, pulse.iloc[-1], color=C_ALERT, alpha=0.12, linewidth=0)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Slant & Ground Distance Over Time
# ═══════════════════════════════════════════════════════════════════════════════

fig1, ax1 = plt.subplots(figsize=(12, 4), facecolor=C_BG)
ax1.set_facecolor(C_BG)

ax1.plot(df["pulse"], df["slant_cm"],  color=C_MAIN,   lw=1.2, label="Slant distance (cm)", zorder=3)
ax1.plot(df["pulse"], df["ground_cm"], color=C_ACCENT,  lw=1.2, label="Ground distance (cm)", zorder=3, linestyle="--")
shade_alerts(ax1, df["pulse"], df["alert"])

ax1.set_title("Slant & Ground Distance vs Pulse", fontsize=13, fontweight="bold")
ax1.set_xlabel("Pulse #")
ax1.set_ylabel("Distance (cm)")
alert_patch = mpatches.Patch(color=C_ALERT, alpha=0.3, label="Alert region")
ax1.legend(handles=[*ax1.get_legend_handles_labels()[0], alert_patch], fontsize=9)
ax1.grid(axis="y", color="white", linewidth=1.2)
plt.tight_layout()
fig1.savefig(out_dir / "01_distance_over_time.png", dpi=150)
print("Saved 01_distance_over_time.png")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Backscatter (%) Over Time – coloured by alert
# ═══════════════════════════════════════════════════════════════════════════════

fig2, ax2 = plt.subplots(figsize=(12, 4), facecolor=C_BG)
ax2.set_facecolor(C_BG)

colours = [C_ALERT if a else C_MAIN for a in df["alert"]]
ax2.scatter(df["pulse"], df["backscatter_pct"], c=colours, s=6, zorder=3, alpha=0.8)
ax2.plot(df["pulse"], df["backscatter_pct"], color=C_MAIN, lw=0.6, alpha=0.4, zorder=2)

ax2.set_title("Backscatter % vs Pulse", fontsize=13, fontweight="bold")
ax2.set_xlabel("Pulse #")
ax2.set_ylabel("Backscatter (%)")
normal_patch = mpatches.Patch(color=C_MAIN,  label="Normal")
alert_patch  = mpatches.Patch(color=C_ALERT, label="Alert")
ax2.legend(handles=[normal_patch, alert_patch], fontsize=9)
ax2.grid(axis="y", color="white", linewidth=1.2)
plt.tight_layout()
fig2.savefig(out_dir / "02_backscatter_over_time.png", dpi=150)
print("Saved 02_backscatter_over_time.png")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. LDR Raw vs Backscatter scatter – coloured by alert
# ═══════════════════════════════════════════════════════════════════════════════

fig3, ax3 = plt.subplots(figsize=(7, 5), facecolor=C_BG)
ax3.set_facecolor(C_BG)

ax3.scatter(df.loc[~alerted, "ldr_raw"], df.loc[~alerted, "backscatter_pct"],
            c=C_MAIN,  s=12, alpha=0.6, label="Normal", zorder=3)
ax3.scatter(df.loc[ alerted, "ldr_raw"], df.loc[ alerted, "backscatter_pct"],
            c=C_ALERT, s=18, alpha=0.8, label="Alert",  zorder=4)

ax3.set_title("LDR Raw vs Backscatter %", fontsize=13, fontweight="bold")
ax3.set_xlabel("LDR Raw")
ax3.set_ylabel("Backscatter (%)")
ax3.legend(fontsize=9)
ax3.grid(color="white", linewidth=1.2)
plt.tight_layout()
fig3.savefig(out_dir / "03_ldr_vs_backscatter.png", dpi=150)
print("Saved 03_ldr_vs_backscatter.png")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Alert timeline (strip chart)
# ═══════════════════════════════════════════════════════════════════════════════

fig4, ax4 = plt.subplots(figsize=(12, 2), facecolor=C_BG)
ax4.set_facecolor(C_BG)

ax4.fill_between(df["pulse"], df["alert"], step="mid", color=C_ALERT, alpha=0.7)
ax4.set_xlim(df["pulse"].min(), df["pulse"].max())
ax4.set_ylim(-0.05, 1.3)
ax4.set_yticks([0, 1])
ax4.set_yticklabels(["Normal", "Alert"])
ax4.set_title("Alert Timeline", fontsize=13, fontweight="bold")
ax4.set_xlabel("Pulse #")
ax4.grid(axis="x", color="white", linewidth=1.2)
plt.tight_layout()
fig4.savefig(out_dir / "04_alert_timeline.png", dpi=150)
print("Saved 04_alert_timeline.png")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Temperature & Pressure (twin axes)
# ═══════════════════════════════════════════════════════════════════════════════

fig5, ax5a = plt.subplots(figsize=(12, 4), facecolor=C_BG)
ax5a.set_facecolor(C_BG)
ax5b = ax5a.twinx()

l1, = ax5a.plot(df["pulse"], df["temp_c"],      color=C_MAIN,   lw=1.4, label="Temp (°C)")
l2, = ax5b.plot(df["pulse"], df["pressure_hpa"], color=C_ACCENT, lw=1.4, label="Pressure (hPa)", linestyle="--")

ax5a.set_title("Temperature & Pressure vs Pulse", fontsize=13, fontweight="bold")
ax5a.set_xlabel("Pulse #")
ax5a.set_ylabel("Temperature (°C)", color=C_MAIN)
ax5b.set_ylabel("Pressure (hPa)",   color=C_ACCENT)
ax5a.tick_params(axis="y", labelcolor=C_MAIN)
ax5b.tick_params(axis="y", labelcolor=C_ACCENT)
ax5a.legend(handles=[l1, l2], fontsize=9, loc="upper left")
ax5a.grid(axis="y", color="white", linewidth=1.2)
plt.tight_layout()
fig5.savefig(out_dir / "05_temp_pressure.png", dpi=150)
print("Saved 05_temp_pressure.png")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Dashboard – all panels tiled
# ═══════════════════════════════════════════════════════════════════════════════

fig6 = plt.figure(figsize=(16, 14), facecolor=C_BG)
fig6.suptitle("SAR Log Dashboard", fontsize=16, fontweight="bold", y=0.98)

gs = fig6.add_gridspec(4, 2, hspace=0.45, wspace=0.35)

#  panel A: distance
axA = fig6.add_subplot(gs[0, :])
axA.set_facecolor(C_BG)
axA.plot(df["pulse"], df["slant_cm"],  color=C_MAIN,  lw=1.2, label="Slant (cm)")
axA.plot(df["pulse"], df["ground_cm"], color=C_ACCENT, lw=1.2, label="Ground (cm)", linestyle="--")
shade_alerts(axA, df["pulse"], df["alert"])
axA.set_title("Distance vs Pulse", fontweight="bold")
axA.set_xlabel("Pulse #"); axA.set_ylabel("cm")
axA.legend(fontsize=8); axA.grid(axis="y", color="white")

# panel B: backscatter
axB = fig6.add_subplot(gs[1, :])
axB.set_facecolor(C_BG)
axB.scatter(df["pulse"], df["backscatter_pct"], c=colours, s=5, alpha=0.8)
axB.set_title("Backscatter % vs Pulse", fontweight="bold")
axB.set_xlabel("Pulse #"); axB.set_ylabel("%")
axB.legend(handles=[normal_patch, alert_patch], fontsize=8)
axB.grid(axis="y", color="white")

#  panel C: LDR vs backscatter scatter
axC = fig6.add_subplot(gs[2, 0])
axC.set_facecolor(C_BG)
axC.scatter(df.loc[~alerted, "ldr_raw"], df.loc[~alerted, "backscatter_pct"], c=C_MAIN,  s=8, alpha=0.6, label="Normal")
axC.scatter(df.loc[ alerted, "ldr_raw"], df.loc[ alerted, "backscatter_pct"], c=C_ALERT, s=12, alpha=0.8, label="Alert")
axC.set_title("LDR Raw vs Backscatter", fontweight="bold")
axC.set_xlabel("LDR Raw"); axC.set_ylabel("%")
axC.legend(fontsize=8); axC.grid(color="white")

# panel D: alert timeline
axD = fig6.add_subplot(gs[2, 1])
axD.set_facecolor(C_BG)
axD.fill_between(df["pulse"], df["alert"], step="mid", color=C_ALERT, alpha=0.7)
axD.set_xlim(df["pulse"].min(), df["pulse"].max())
axD.set_ylim(-0.05, 1.3); axD.set_yticks([0, 1]); axD.set_yticklabels(["Normal", "Alert"])
axD.set_title("Alert Timeline", fontweight="bold")
axD.set_xlabel("Pulse #"); axD.grid(axis="x", color="white")

# panel E: temp & pressure
axE1 = fig6.add_subplot(gs[3, :])
axE1.set_facecolor(C_BG)
axE2 = axE1.twinx()
axE1.plot(df["pulse"], df["temp_c"],       color=C_MAIN,   lw=1.2, label="Temp (°C)")
axE2.plot(df["pulse"], df["pressure_hpa"], color=C_ACCENT, lw=1.2, label="Pressure (hPa)", linestyle="--")
axE1.set_title("Temperature & Pressure vs Pulse", fontweight="bold")
axE1.set_xlabel("Pulse #"); axE1.set_ylabel("°C", color=C_MAIN)
axE2.set_ylabel("hPa", color=C_ACCENT)
axE1.tick_params(axis="y", labelcolor=C_MAIN)
axE2.tick_params(axis="y", labelcolor=C_ACCENT)
axE1.legend(handles=[l1, l2], fontsize=8, loc="upper left")
axE1.grid(axis="y", color="white")

fig6.savefig(out_dir / "sar_dashboard.png", dpi=150, bbox_inches="tight")
print("Saved sar_dashboard.png")

print("\nDone. Output files:")
for f in sorted(out_dir.glob("*.png")):
    print(" ", f)