"""Generate synthetic chest X-ray-like grayscale PNG images for the demo."""
import numpy as np
from PIL import Image, ImageFilter
from pathlib import Path

ROOT   = Path(__file__).parent.parent
OUTDIR = ROOT / "assets" / "xrays"
OUTDIR.mkdir(parents=True, exist_ok=True)

STUDIES = [
    ("xray_01.png", [],                                    42),
    ("xray_02.png", ["Cardiomegaly"],                      43),
    ("xray_03.png", ["Pleural Effusion","Cardiomegaly"],   44),
    ("xray_04.png", ["Pneumonia","Consolidation"],         45),
    ("xray_05.png", ["Atelectasis"],                       46),
    ("xray_06.png", ["Nodule"],                            47),
    ("xray_07.png", ["Pneumothorax"],                      48),
    ("xray_08.png", ["Mass"],                              49),
]


def generate_xray(width: int = 512, height: int = 512,
                  findings: list = None, seed: int = 42) -> Image.Image:
    """Return a PIL grayscale image resembling a chest X-ray PA view."""
    np.random.seed(seed)
    if findings is None:
        findings = []

    W, H = width, height
    cx, cy = W / 2, H / 2
    img = np.zeros((H, W), dtype=np.float32)

    yy, xx = np.mgrid[0:H, 0:W]

    # ── Chest outline ─────────────────────────────────────────────────────────
    chest = ((xx - cx) ** 2 / (cx * 0.88) ** 2 +
             (yy - cy * 0.96) ** 2 / (cy * 0.92) ** 2) < 1
    img[chest] = 35

    # ── Lung fields (darker — air) ────────────────────────────────────────────
    lL = ((xx - cx * 0.57) ** 2 / (cx * 0.26) ** 2 +
          (yy - cy * 0.84) ** 2 / (cy * 0.36) ** 2) < 1
    rL = ((xx - cx * 1.43) ** 2 / (cx * 0.26) ** 2 +
          (yy - cy * 0.84) ** 2 / (cy * 0.36) ** 2) < 1
    img[lL] = 14
    img[rL] = 14

    # ── Mediastinum / heart ───────────────────────────────────────────────────
    heart = ((xx - cx * 0.91) ** 2 / (cx * 0.19) ** 2 +
             (yy - cy * 1.06) ** 2 / (cy * 0.22) ** 2) < 1
    img[heart] = 125

    # ── Aortic knob ───────────────────────────────────────────────────────────
    aorta = ((xx - cx * 0.84) ** 2 + (yy - cy * 0.60) ** 2) < (W * 0.05) ** 2
    img[aorta] = 145

    # ── Trachea ───────────────────────────────────────────────────────────────
    trachea = (np.abs(xx - cx) < W * 0.025) & (yy < cy * 0.58)
    img[trachea] = 8

    # ── Spine ─────────────────────────────────────────────────────────────────
    spine = (np.abs(xx - cx) < W * 0.025) & (yy > cy * 0.38) & (yy < cy * 1.65)
    img[spine] = np.maximum(img[spine], 195)

    # ── Clavicles ─────────────────────────────────────────────────────────────
    for x in range(int(cx * 0.20), int(cx)):
        cy_clav = int(cy * 0.27 - cy * 0.09 * (x - cx * 0.20) / (cx * 0.80))
        if 0 <= cy_clav < H:
            img[max(0, cy_clav - 2):cy_clav + 3, x] = 210
    for x in range(int(cx), int(cx * 1.80)):
        cy_clav = int(cy * 0.27 + cy * 0.09 * (x - cx) / (cx * 0.80))
        if 0 <= cy_clav < H:
            img[max(0, cy_clav - 2):cy_clav + 3, x] = 210

    # ── Ribs ──────────────────────────────────────────────────────────────────
    for i in range(12):
        rib_y0 = cy * 0.24 + i * cy * 0.12
        rw = 2
        for side, x0, x1, xref, sign in [
            ("L", int(cx*0.22), int(cx*0.88), cx*0.22, 1),
            ("R", int(cx*1.12), int(cx*1.78), cx*1.78, -1),
        ]:
            span = abs(x1 - x0)
            for x in range(x0, x1):
                arc = int(rib_y0 + cy * 0.07 * np.sin(np.pi * abs(x - xref) / span))
                if 0 <= arc - rw and arc + rw < H:
                    img[arc - rw:arc + rw + 1, x] = np.maximum(
                        img[arc - rw:arc + rw + 1, x], 195)

    # ── Diaphragm ─────────────────────────────────────────────────────────────
    for x in range(int(cx * 0.22), int(cx * 0.90)):
        d = int(cy * 1.36 - cy * 0.10 * np.sin(np.pi * (x - cx*0.22) / (cx*0.68)))
        if 0 <= d < H:
            img[d:min(H, d+3), x] = 190
    for x in range(int(cx * 1.10), int(cx * 1.78)):
        d = int(cy * 1.42 - cy * 0.09 * np.sin(np.pi * (cx*1.78 - x) / (cx*0.68)))
        if 0 <= d < H:
            img[d:min(H, d+3), x] = 190

    # ── Pulmonary vascular markings ───────────────────────────────────────────
    for lung_mask, x_base in [(lL, cx * 0.40), (rL, cx * 1.30)]:
        for _ in range(18):
            vx = int(np.random.uniform(x_base * 0.8, x_base * 1.2))
            vy = int(np.random.uniform(cy * 0.28, cy * 0.65))
            ln = int(np.random.uniform(25, 90))
            ang = np.random.uniform(-0.5, 0.5)
            intens = float(np.random.uniform(28, 65))
            for j in range(ln):
                px_ = int(vx + j * np.sin(ang))
                py_ = int(vy + j * np.cos(ang))
                if (0 <= px_ < W and 0 <= py_ < H and lung_mask[py_, px_]):
                    img[py_, px_] = min(255, img[py_, px_] + intens * (1 - j / ln))

    # ── Findings ──────────────────────────────────────────────────────────────
    for f in findings:
        if f == "Cardiomegaly":
            hc = ((xx - cx * 0.88) ** 2 / (cx * 0.28) ** 2 +
                  (yy - cy * 1.03) ** 2 / (cy * 0.26) ** 2) < 1
            img[hc] = np.maximum(img[hc], 118)

        elif f == "Pleural Effusion":
            eff = (yy > cy * 1.22) & rL
            img[eff] = 155

        elif f == "Pneumothorax":
            ptx = (xx < cx * 0.38) & lL
            img[ptx] = 5
            line_x = int(cx * 0.39)
            img[int(cy*0.22):int(cy*0.88), line_x:line_x+3] = 205

        elif f in ("Nodule", "Mass"):
            sz = 11 if f == "Nodule" else 32
            nx, ny = int(cx * 1.50), int(cy * 0.57)
            nod = ((xx - nx) ** 2 + (yy - ny) ** 2) < sz ** 2
            img[nod] = 170

        elif f == "Atelectasis":
            atel_y0 = int(cy * 1.20)
            atel_y1 = int(cy * 1.27)
            img[atel_y0:atel_y1, int(cx*0.35):int(cx*0.82)] = 145

        elif f in ("Pneumonia", "Consolidation"):
            con = ((xx - cx * 1.42) ** 2 / (cx * 0.24) ** 2 +
                   (yy - cy * 1.12) ** 2 / (cy * 0.20) ** 2) < 1
            img[con] = np.where(img[con] < 132, 132, img[con])

        elif f == "Infiltration":
            inf = ((xx - cx * 0.60) ** 2 / (cx * 0.20) ** 2 +
                   (yy - cy * 1.05) ** 2 / (cy * 0.18) ** 2) < 1
            img[inf] = np.where(img[inf] < 120, 120, img[inf])

    # ── Noise + blur ──────────────────────────────────────────────────────────
    img = np.clip(img + np.random.normal(0, 5.5, img.shape), 0, 255).astype(np.uint8)
    pil = Image.fromarray(img, mode="L").filter(ImageFilter.GaussianBlur(radius=1.2))
    return pil


if __name__ == "__main__":
    for fname, findings, seed in STUDIES:
        out = OUTDIR / fname
        img = generate_xray(512, 512, findings=findings, seed=seed)
        img.save(out)
        print(f"  {fname}  findings={findings or ['No Finding']}")
    print(f"\n{len(STUDIES)} X-ray images written to {OUTDIR}")
