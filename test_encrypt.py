"""
Batch Multi-threaded Encryption Benchmark
Usage: python batch_test.py --input_dir /path/to/dataset
Output: benchmark_results.csv + summary statistics
"""

import numpy as np
from PIL import Image
import os, random
import csv
import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from tqdm import tqdm
from tqdm.contrib.concurrent import thread_map

from encryption import (
    encrypt_image, decrypt_image,
    calculate_entropy, calculate_correlation,
    calculate_histogram
)
from preprocessing import handle_non_square_image, reverse_non_square_handling

# Fixed Random Seed (note that os.urandom cannot be fixed since read from system entropy pool)
random.seed(42)
np.random.seed(42)

# Encryption parameters (fixed for fair comparison)
PARAMS = {
    'arnold_iterations': 80,
    'dna_rule': 2,
    'chaos_x0': 0.123456789,
    'chaos_r': 3.9876
}

SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif')

print_lock = Lock()

def safe_print(msg):
    tqdm.write(msg)
    #with print_lock:
    #    print(msg)

# Process a single image: encrypt, decrypt, analyze. Returns a dict of metrics, or None if failed.
def process_image(img_path: str) -> dict:
    filename = os.path.basename(img_path)
    
    try:
        # Load and convert to grayscale
        img = Image.open(img_path).convert('L')
        original = np.array(img, dtype=np.uint8)

        # Handle non-square
        if original.shape[0] != original.shape[1]:
            square, pad_meta = handle_non_square_image(original)
        else:
            square = original
            pad_meta = {'method': 'none', 'original_shape': original.shape}

        verbose = False
        # Encrypt
        #t0 = time.time()
        encrypted, enc_meta = encrypt_image(square, **PARAMS, verbose=verbose)
        #enc_time = time.time() - t0

        # Decrypt
        #t0 = time.time()
        decrypted_square = decrypt_image(encrypted, enc_meta, verbose=verbose)
        #dec_time = time.time() - t0

        # Remove padding
        if pad_meta['method'] != 'none':
            decrypted = reverse_non_square_handling(decrypted_square, pad_meta)
        else:
            decrypted = decrypted_square

        # Metrics
        enc_entropy = calculate_entropy(encrypted)

        corr_h = calculate_correlation(encrypted, 'horizontal')
        corr_v = calculate_correlation(encrypted, 'vertical')
        corr_d = calculate_correlation(encrypted, 'diagonal')

        enc_hist = calculate_histogram(encrypted)
        mean_count = float(enc_hist.mean())
        std_count  = float(enc_hist.std())
        uniformity = (1 - std_count / mean_count) * 100

        mse = float(np.mean((original.astype(float) - decrypted.astype(float)) ** 2))
        perfect_match = bool(np.array_equal(original, decrypted))
        
        total_pixels = square.shape[0] * square.shape[1]

        result = {
            'filename':      filename,
            'size':          f"{original.shape[1]}x{original.shape[0]}",
            'enc_entropy':   round(enc_entropy, 4),
            'corr_h':        round(corr_h, 4),
            'corr_v':        round(corr_v, 4),
            'corr_d':        round(corr_d, 4),
            'uniformity':    round(uniformity, 2),
            'mse':           round(mse, 6),
            'perfect_match': perfect_match,
            #'enc_time_per_kpx': round(enc_time / total_pixels * 1000, 4),
            #'dec_time_per_kpx': round(dec_time / total_pixels * 1000, 4),
            'status':        'OK'
        }

        safe_print(f"  [OK] {filename:40s} entropy={enc_entropy:.4f}  uniformity={uniformity:.1f}%  match={perfect_match}")
        return result

    except Exception as e:
        safe_print(f"  [FAIL] {filename}: {e}")
        return {
            'filename': filename, 'status': f'ERROR: {e}',
            'enc_entropy': None, 'corr_h': None, 'corr_v': None,
            'corr_d': None, 'uniformity': None, 'mse': None,
            'perfect_match': None, 
            #'enc_time_per_kpx': None, 'dec_time_per_kpx': None,
            'size': None
        }

# collect all images' path
def collect_images(input_dir: str):
    paths = []
    for root, _, files in os.walk(input_dir):
        for f in files:
            if f.lower().endswith(SUPPORTED_FORMATS):
                paths.append(os.path.join(root, f))
    return sorted(paths)

# Compute mean ± std for each numeric metric
def summarize(results):
    metrics = ['enc_entropy', 'corr_h', 'corr_v', 'corr_d',
               'uniformity', 'mse', 
               #'enc_time_per_kpx', 'dec_time_per_kpx'
               ]

    ok = [r for r in results if r['status'] == 'OK']
    n  = len(ok)

    print("\n" + "=" * 65)
    print(f"BENCHMARK SUMMARY  ({n} images succeeded, "
          f"{len(results)-n} failed)")
    print("=" * 65)

    rows = []
    for m in metrics:
        vals = np.array([r[m] for r in ok if r[m] is not None], dtype=float)
        if len(vals) == 0:
            continue
        mean, std = round(vals.mean(), 4), round(vals.std(), 4)
        rows.append((m, mean, std, vals.min(), vals.max()))
        print(f"  {m:20s}  mean={mean:8.4f}  std={std:7.4f}"
              f"  min={vals.min():.4f}  max={vals.max():.4f}")

    # Perfect match rate
    matches = sum(1 for r in ok if r['perfect_match'])
    print(f"\n  {'perfect_match_rate':20s}  {matches}/{n} = {matches/n*100:.1f}%")

    # Quality flags
    good_entropy   = sum(1 for r in ok if r['enc_entropy'] and r['enc_entropy'] > 7.9)
    good_uniformity= sum(1 for r in ok if r['uniformity']  and r['uniformity']  > 70)
    print(f"\n  Entropy   > 7.9  : {good_entropy}/{n}")
    print(f"  Uniformity > 70% : {good_uniformity}/{n}")
    print("=" * 65)

    return rows, matches, n

# save the results into csv
def save_csv(output_path, results, rows,  matches, n):
    fieldnames = ['filename', 'size', 'status', 'enc_entropy',
                  'corr_h', 'corr_v', 'corr_d', 'uniformity',
                  'mse', 'perfect_match', 
                  #'enc_time_per_kpx', 'dec_time_per_kpx'
                  ]
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
        
        f.write('\n')
        
        writer = csv.writer(f)
        writer.writerow(['metric', 'mean', 'std', 'min', 'max'])
        for row in rows:
            writer.writerow(row)
        writer.writerow(['perfect_match_rate', f'{matches}/{n}', '', '', ''])
        
    print(f"\nTest results saved to: {output_path}")

def main():
    test_set   = 'aerials' # 'misc' 'sequences' 'textures' 'aerials'
    input_dir  = f"E:\\Image Encryption and Watermarking System\\{test_set}"   # dataset path
    output_csv = f"{test_set}_results.csv"     # output path
    workers    = 8

    # Collect images
    img_paths = collect_images(input_dir)
    if not img_paths:
        print(f"No supported images found in: {input_dir}")
        return

    print(f"Found {len(img_paths)} images in '{input_dir}'")
    print(f"Running with {workers} threads ...\n")

    # Parallel processing
    results = list(thread_map(process_image, img_paths, max_workers=workers, desc="Testing"))

    #results = []
    #with ThreadPoolExecutor(max_workers=workers) as executor:
    #    futures = {executor.submit(process_image, p): p for p in img_paths}
    #    for future in tqdm(as_completed(futures), total=len(futures), desc="Testing"):
    #        results.append(future.result())

    # Sort by filename for readability
    results.sort(key=lambda r: r['filename'])

    # Summary + CSV
    rows,  matches, n = summarize(results)
    save_csv(output_csv, results, rows,  matches, n)

if __name__ == '__main__':
    main()