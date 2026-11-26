#!/usr/bin/env python3
"""Synthetic single-channel sleep EEG epochs (W, N1, N2, N3, REM) rendered as SVG.

Signals are randomized, NOT real recordings. Morphology follows AASM-style
descriptions: alpha 8-13 Hz (W), low-amplitude mixed-frequency 4-7 Hz + vertex
waves (N1), spindles 11-16 Hz + K-complexes >=0.5 s (N2), slow waves 0.5-2 Hz
>75 uV p-p in >=20% of epoch (N3), LAMF + 2-6 Hz sawtooth waves (REM).

Display convention: surface-negative is plotted UP (clinical EEG convention).

Usage: python3 sleep_eeg_svg.py [--seed N] [--seconds 30] [--out DIR]
"""
import argparse, os
import numpy as np

FS = 200.0  # Hz


# ---------- signal building blocks ----------
def colored_noise(rng, n, exponent=1.0, f_lo=0.3, f_hi=35.0):
    """1/f^exponent noise band-limited to the AASM EEG display band (0.3-35 Hz)."""
    f = np.fft.rfftfreq(n, 1 / FS)
    spec = rng.normal(size=f.size) + 1j * rng.normal(size=f.size)
    amp = np.zeros_like(f)
    band = (f >= f_lo) & (f <= f_hi)
    amp[band] = 1 / f[band] ** (exponent / 2)
    x = np.fft.irfft(spec * amp, n)
    return x / x.std()


def band_noise(rng, n, f_lo, f_hi):
    """Narrow-band random oscillation (e.g. theta, alpha)."""
    f = np.fft.rfftfreq(n, 1 / FS)
    spec = rng.normal(size=f.size) + 1j * rng.normal(size=f.size)
    spec[(f < f_lo) | (f > f_hi)] = 0
    x = np.fft.irfft(spec, n)
    return x / x.std()


def slow_envelope(rng, n, rate=0.3, floor=0.2):
    """Waxing/waning envelope in [floor, 1]."""
    e = band_noise(rng, n, 0.05, rate)
    e = (e - e.min()) / (e.max() - e.min())
    return floor + (1 - floor) * e


def hann_burst(n_len):
    return np.hanning(n_len)


def add_spindle(rng, x, t0):
    dur = rng.uniform(0.6, 1.5)
    f = rng.uniform(12.0, 14.0)
    amp = rng.uniform(18, 35)
    n_len = int(dur * FS)
    i0 = int(t0 * FS)
    if i0 + n_len >= x.size:
        return
    t = np.arange(n_len) / FS
    x[i0:i0 + n_len] += amp * hann_burst(n_len) * np.sin(2 * np.pi * f * t + rng.uniform(0, 2 * np.pi))


def add_k_complex(rng, x, t0):
    """Sharp surface-negative wave immediately followed by slower positive component; total >= 0.5 s."""
    neg_d = rng.uniform(0.15, 0.25)
    pos_d = rng.uniform(0.45, 0.75)
    neg_a = rng.uniform(70, 130)
    pos_a = rng.uniform(50, 90)
    i0 = int(t0 * FS)
    nn, npos = int(neg_d * FS), int(pos_d * FS)
    if i0 + nn + npos >= x.size:
        return
    # sharper rise than fall for the negative peak
    tn = np.linspace(0, 1, nn)
    neg = np.sin(np.pi * tn ** 0.7)
    tp = np.linspace(0, 1, npos)
    pos = np.sin(np.pi * tp) ** 1.3
    x[i0:i0 + nn] += neg_a * neg          # negative -> plotted up
    x[i0 + nn:i0 + nn + npos] -= pos_a * pos
    # small preceding positive dip (common morphology), smoothed
    pre = int(0.12 * FS)
    if i0 - pre > 0:
        x[i0 - pre:i0] -= 12 * np.sin(np.pi * np.linspace(0, 1, pre))
    return (t0 + neg_d + pos_d)


def add_vertex_wave(rng, x, t0):
    """Monophasic surface-negative sharp transient, < 0.5 s (typically < 200 ms)."""
    d = rng.uniform(0.12, 0.22)
    a = rng.uniform(45, 85)
    n_len = int(d * FS)
    i0 = int(t0 * FS)
    if i0 + n_len >= x.size:
        return
    t = np.linspace(0, 1, n_len)
    shape = np.where(t < 0.45, (t / 0.45) ** 1.6, ((1 - t) / 0.55) ** 1.2)
    x[i0:i0 + n_len] += a * shape


def add_sawtooth_train(rng, x, t0):
    """Train of serrated/triangular 2-6 Hz waves (slow rise, fast fall)."""
    f = rng.uniform(2.5, 4.5)
    cycles = rng.integers(4, 9)
    amp = rng.uniform(25, 45)
    n_len = int(cycles / f * FS)
    i0 = int(t0 * FS)
    if i0 + n_len >= x.size:
        return
    t = np.arange(n_len) / FS
    phase = (t * f) % 1.0
    saw = np.where(phase < 0.75, phase / 0.75, (1 - phase) / 0.25) * 2 - 1
    x[i0:i0 + n_len] += amp * np.hanning(n_len) ** 0.4 * saw


def place_events(rng, seconds, k, min_gap, margin=1.0):
    """k random onset times with a minimum spacing."""
    for _ in range(500):
        t = np.sort(rng.uniform(margin, seconds - margin - 2.0, size=k))
        if k < 2 or np.all(np.diff(t) > min_gap):
            return t
    return np.linspace(margin, seconds - margin - 2.0, k)


# ---------- stage generators (output in microvolts, negative-up convention) ----------
def gen_wake(rng, n, seconds):
    x = 6 * colored_noise(rng, n, 1.0)
    x += 4 * band_noise(rng, n, 14, 25)                       # low-amplitude beta
    alpha_f = rng.uniform(9.0, 11.0)
    alpha = band_noise(rng, n, alpha_f - 0.8, alpha_f + 0.8)
    x += 22 * alpha * slow_envelope(rng, n, 0.4, floor=0.35)  # waxing/waning alpha, >50% of epoch
    return x


def gen_n1(rng, n, seconds):
    x = 7 * colored_noise(rng, n, 1.2)
    x += 12 * band_noise(rng, n, 4, 7) * slow_envelope(rng, n, 0.5, 0.4)  # LAMF, theta-dominant
    # brief residual alpha fragments (< 50% of epoch)
    a = band_noise(rng, n, 8.5, 10.5)
    mask = np.zeros(n)
    for t0 in rng.uniform(0, seconds - 3, size=2):
        i0, L = int(t0 * FS), int(rng.uniform(1.0, 2.5) * FS)
        mask[i0:i0 + L] = np.hanning(len(mask[i0:i0 + L]))
    x += 12 * a * mask
    for t0 in place_events(rng, seconds, int(rng.integers(2, 4)), 4.0):
        add_vertex_wave(rng, x, t0)
    return x


def gen_n2(rng, n, seconds):
    x = 8 * colored_noise(rng, n, 1.4)
    x += 10 * band_noise(rng, n, 4, 7) * slow_envelope(rng, n, 0.5, 0.4)
    x += 6 * band_noise(rng, n, 1, 3)
    kc_times = place_events(rng, seconds, int(rng.integers(1, 3)), 8.0)
    for t0 in kc_times:
        end = add_k_complex(rng, x, t0)
        if end and rng.random() < 0.6:                  # KC often followed by a spindle
            add_spindle(rng, x, end + rng.uniform(0.05, 0.3))
    for t0 in rng.uniform(1, seconds - 2, size=int(rng.integers(2, 4))):
        if np.all(np.abs(kc_times - t0) > 2.0):
            add_spindle(rng, x, t0)
    return x


def gen_n3(rng, n, seconds):
    x = 8 * colored_noise(rng, n, 1.6)
    x += 5 * band_noise(rng, n, 4, 7)
    sw = band_noise(rng, n, 0.6, 1.8)
    env = slow_envelope(rng, n, 0.15, floor=0.55)
    x += 55 * sw * env                                    # ~110-200 uV p-p slow waves
    if rng.random() < 0.5:                                # spindles may persist in N3
        add_spindle(rng, x, rng.uniform(2, seconds - 3))
    return x


def gen_rem(rng, n, seconds):
    x = 7 * colored_noise(rng, n, 1.1)
    x += 10 * band_noise(rng, n, 4, 7) * slow_envelope(rng, n, 0.5, 0.4)
    x += 6 * band_noise(rng, n, 8, 11) * slow_envelope(rng, n, 0.4, 0.1)  # some alpha, slower than W
    x += 3 * band_noise(rng, n, 16, 30)
    for t0 in place_events(rng, seconds, int(rng.integers(1, 3)), 6.0):
        add_sawtooth_train(rng, x, t0)
    return x


STAGES = [
    ("W", "Wake (eyes closed)", gen_wake),
    ("N1", "N1", gen_n1),
    ("N2", "N2", gen_n2),
    ("N3", "N3", gen_n3),
    ("REM", "REM (stage R)", gen_rem),
]


# ---------- SVG rendering ----------
PX_PER_S = 60.0
PX_PER_UV = 0.8


def path_d(x, y0):
    t = np.arange(x.size) / FS * PX_PER_S
    y = y0 - x * PX_PER_UV
    pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(t, y))
    return "M" + pts


def scale_bar(x0, y0, color):
    s = PX_PER_S
    v = 50 * PX_PER_UV
    return (f'<g id="scale" fill="none" stroke="{color}" stroke-width="1.5">'
            f'<path d="M{x0},{y0 - v} V{y0} H{x0 + s}"/></g>'
            f'<g font-family="Helvetica, Arial, sans-serif" font-size="12" fill="{color}">'
            f'<text x="{x0 + s / 2}" y="{y0 + 15}" text-anchor="middle">1 s</text>'
            f'<text x="{x0 - 6}" y="{y0 - v / 2 + 4}" text-anchor="end">50 µV</text></g>')


def svg_single(x, label, seconds, color="#1a1a1a"):
    w = seconds * PX_PER_S + 100
    h = 320
    y0 = 150
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h}" width="{w:.0f}" height="{h}">\n'
            f'<title>Synthetic EEG – {label}</title>\n'
            f'<text id="label" x="10" y="22" font-family="Helvetica, Arial, sans-serif" font-size="16" '
            f'font-weight="600" fill="{color}">{label}</text>\n'
            f'<g id="trace" transform="translate(80,0)"><path d="{path_d(x, y0)}" fill="none" '
            f'stroke="{color}" stroke-width="1.1" stroke-linejoin="round" stroke-linecap="round"/></g>\n'
            f'{scale_bar(w - 90, h - 30, color)}\n</svg>\n')


def svg_stacked(traces, seconds, color="#1a1a1a"):
    row = 230
    w = seconds * PX_PER_S + 140
    h = row * len(traces) + 60
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h}" width="{w:.0f}" height="{h}">',
             '<title>Synthetic sleep EEG – all stages</title>']
    for i, (code, label, x) in enumerate(traces):
        y0 = row * i + row / 2 + 10
        parts.append(f'<text x="10" y="{y0 + 5}" font-family="Helvetica, Arial, sans-serif" '
                     f'font-size="16" font-weight="600" fill="{color}">{code}</text>')
        parts.append(f'<g id="trace-{code}" transform="translate(110,0)"><path d="{path_d(x, y0)}" '
                     f'fill="none" stroke="{color}" stroke-width="1.1" stroke-linejoin="round"/></g>')
    parts.append(scale_bar(w - 90, h - 25, color))
    parts.append("</svg>\n")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--out", default="sleep_eeg_svg")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    n = int(a.seconds * FS)
    os.makedirs(a.out, exist_ok=True)
    traces = []
    for code, label, gen in STAGES:
        x = gen(rng, n, a.seconds)
        x = np.clip(x, -180, 180)
        traces.append((code, label, x))
        with open(os.path.join(a.out, f"eeg_{code}.svg"), "w") as f:
            f.write(svg_single(x, label, a.seconds))
    with open(os.path.join(a.out, "eeg_all_stages.svg"), "w") as f:
        f.write(svg_stacked(traces, a.seconds))
    print("written to", a.out)


if __name__ == "__main__":
    main()
