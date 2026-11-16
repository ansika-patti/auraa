"""
Auraa Academic Benchmark & Metrics Generator
Generates comprehensive quantitative metrics, ablation tables, and slide-ready summaries.
"""

import os
import time
import json
import cv2
import numpy as np

def calculate_ssim(img1, img2):
    if len(img1.shape) == 3:
        img1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    if len(img2.shape) == 3:
        img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    
    h, w = img1.shape
    img2 = cv2.resize(img2, (w, h))

    C1 = (0.01 * 255)**2
    C2 = (0.03 * 255)**2

    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)

    kernel = cv2.getGaussianKernel(11, 1.5)
    window = np.outer(kernel, kernel.transpose())

    mu1 = cv2.filter2D(img1, -1, window)[5:-5, 5:-5]
    mu2 = cv2.filter2D(img2, -1, window)[5:-5, 5:-5]

    mu1_sq = mu1**2
    mu2_sq = mu2**2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = cv2.filter2D(img1**2, -1, window)[5:-5, 5:-5] - mu1_sq
    sigma2_sq = cv2.filter2D(img2**2, -1, window)[5:-5, 5:-5] - mu2_sq
    sigma12 = cv2.filter2D(img1 * img2, -1, window)[5:-5, 5:-5] - mu1_mu2

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))
    return float(ssim_map.mean())

def calculate_edge_precision_recall(img_ref, img_gen, tol=3):
    h, w = img_ref.shape[:2]
    img_gen = cv2.resize(img_gen, (w, h))

    gray_ref = cv2.cvtColor(img_ref, cv2.COLOR_BGR2GRAY) if len(img_ref.shape) == 3 else img_ref
    gray_gen = cv2.cvtColor(img_gen, cv2.COLOR_BGR2GRAY) if len(img_gen.shape) == 3 else img_gen

    e_ref = (cv2.Canny(gray_ref, 100, 200) > 0).astype(np.uint8)
    e_gen = (cv2.Canny(gray_gen, 100, 200) > 0).astype(np.uint8)

    k = np.ones((tol, tol), np.uint8)
    e_ref_dil = cv2.dilate(e_ref, k)
    e_gen_dil = cv2.dilate(e_gen, k)

    # Precision: Gen edges aligned to Ref
    prec = float(np.logical_and(e_gen > 0, e_ref_dil > 0).sum() / (e_gen.sum() + 1e-8))
    # Recall: Ref edges preserved in Gen
    rec = float(np.logical_and(e_ref > 0, e_gen_dil > 0).sum() / (e_ref.sum() + 1e-8))
    f1 = float(2 * prec * rec / (prec + rec + 1e-8))
    iou = float(np.logical_and(e_ref > 0, e_gen > 0).sum() / (np.logical_or(e_ref > 0, e_gen > 0).sum() + 1e-8))

    return prec, rec, f1, iou

def calculate_sharpness(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    assets = os.path.join(root, "assets")

    samples = [1, 2, 3, 4]
    
    print("=" * 88)
    print("        AURAA (STABLE DIFFUSION + CONTROLNET + LORA) BENCHMARK REPORT")
    print("=" * 88)

    records = []
    for s in samples:
        inp_p = os.path.join(assets, f"inp{s}.png")
        con_p = os.path.join(assets, f"con{s}.png")
        prm_p = os.path.join(assets, f"prompt{s}.png")

        if not (os.path.exists(inp_p) and os.path.exists(con_p)):
            continue

        im_in = cv2.imread(inp_p)
        im_con = cv2.imread(con_p)
        im_prm = cv2.imread(prm_p) if os.path.exists(prm_p) else None

        # ControlNet evaluation
        p_c, r_c, f1_c, iou_c = calculate_edge_precision_recall(im_in, im_con, tol=3)
        ssim_c = calculate_ssim(im_in, im_con)
        sharp_c = calculate_sharpness(im_con)

        # Baseline evaluation
        if im_prm is not None:
            p_b, r_b, f1_b, iou_b = calculate_edge_precision_recall(im_in, im_prm, tol=3)
            ssim_b = calculate_ssim(im_in, im_prm)
            sharp_b = calculate_sharpness(im_prm)
        else:
            p_b, r_b, f1_b, iou_b, ssim_b, sharp_b = 0, 0, 0, 0, 0, 0

        records.append({
            "id": f"Room {s:02d}",
            "control": {"p": p_c, "r": r_c, "f1": f1_c, "iou": iou_c, "ssim": ssim_c, "sharp": sharp_c},
            "base": {"p": p_b, "r": r_b, "f1": f1_b, "iou": iou_b, "ssim": ssim_b, "sharp": sharp_b}
        })

    print(f"{'Room ID':<10} | {'Method':<16} | {'Edge Prec':<11} | {'Edge Rec':<11} | {'Edge F1':<10} | {'SSIM':<8} | {'Sharpness':<10}")
    print("-" * 88)
    for r in records:
        c = r["control"]
        b = r["base"]
        print(f"{r['id']:<10} | ControlNet+LoRA  | {c['p']*100:6.2f}%    | {c['r']*100:6.2f}%    | {c['f1']*100:6.2f}%   | {c['ssim']:6.3f}   | {c['sharp']:8.1f}")
        print(f"{'':<10} | Base SD (Prompt) | {b['p']*100:6.2f}%    | {b['r']*100:6.2f}%    | {b['f1']*100:6.2f}%   | {b['ssim']:6.3f}   | {b['sharp']:8.1f}")
        print("-" * 88)

    # Averages
    avg_cp = np.mean([r["control"]["p"] for r in records]) * 100
    avg_cr = np.mean([r["control"]["r"] for r in records]) * 100
    avg_cf1 = np.mean([r["control"]["f1"] for r in records]) * 100
    avg_cssim = np.mean([r["control"]["ssim"] for r in records])
    avg_csharp = np.mean([r["control"]["sharp"] for r in records])

    avg_bp = np.mean([r["base"]["p"] for r in records]) * 100
    avg_br = np.mean([r["base"]["r"] for r in records]) * 100
    avg_bf1 = np.mean([r["base"]["f1"] for r in records]) * 100
    avg_bssim = np.mean([r["base"]["ssim"] for r in records])
    avg_bsharp = np.mean([r["base"]["sharp"] for r in records])

    print(f"{'AVERAGE':<10} | ControlNet+LoRA  | {avg_cp:6.2f}%    | {avg_cr:6.2f}%    | {avg_cf1:6.2f}%   | {avg_cssim:6.3f}   | {avg_csharp:8.1f}")
    print(f"{'':<10} | Base SD (Prompt) | {avg_bp:6.2f}%    | {avg_br:6.2f}%    | {avg_bf1:6.2f}%   | {avg_bssim:6.3f}   | {avg_bsharp:8.1f}")
    print("=" * 88)

if __name__ == "__main__":
    main()
