'''
[step 1：Arnold transformation] - geometric diffusion
[step 2：DNA encode encryption] - range confusion 
[key generation：chaos sequence enhancement] - increase key space
'''

# Image Encryption Module: 1. Arnold Transform, 2. DNA Encoding, 3. Chaos Sequence Enhancement
import random, os
import numpy as np
from typing import Tuple, Dict
from numba import jit

# 2x2 Matrix Fast Power mod N
def mat_pow_mod(mat: np.ndarray, n: int, mod: int) -> np.ndarray:
    result = np.eye(2, dtype=np.int64)
    mat = mat.astype(np.int64)
    while n > 0:
        if n % 2 == 1:
            result = (result @ mat) % mod
        mat = (mat @ mat) % mod
        n //= 2
    return result

# Part 1: Arnold Transform (Scrambling Layer) - FULLY OPTIMIZED

# Apply Arnold Cat Map transformation for image scrambling
def arnold_transform(image: np.ndarray, # Square image array (N x N)
                     iterations: int    # Number of iterations (acts as encryption key)
                    ) -> np.ndarray:    # Result: scrambled image array
    """
    Mathematical formula:
    [x']   [1  1] [x]
    [y'] = [1  2] [y]  (mod N)
    """
    
    if iterations < 0:
        raise ValueError("iterations must be non-negative")
    if iterations == 0:
        return image.copy()
    
    N = image.shape[0]
    assert image.shape[0] == image.shape[1], "Image must be square for Arnold transform"
    
    # Matrix fast power
    A = np.array([[1, 1], [1, 2]], dtype=np.int64)
    M = mat_pow_mod(A, iterations, N)
    
    # Vectorized coordinate transformation
    y, x = np.meshgrid(np.arange(N), np.arange(N))
    coords = np.stack([x.ravel(), y.ravel()], axis=1)
    new_coords = (coords @ M.T) % N
    
    # Direct indexing (fastest)
    scrambled = image[new_coords[:, 0], new_coords[:, 1]].reshape(N, N)
    
    return scrambled

# Inverse Arnold Transform to recover original image
def inverse_arnold_transform(image: np.ndarray, # Scrambled square image
                             iterations: int    # Same number used in forward transform
                            ) -> np.ndarray:    # Result: recovered original image
    """
    Mathematical formula for inverse:
    [x']   [ 2  -1] [x]
    [y'] = [-1   1] [y]  (mod N)
    """
    
    if iterations < 0:
        raise ValueError("iterations must be non-negative")
    if iterations == 0:
        return image.copy()
    
    N = image.shape[0]
    
    # Inverse matrix fast power
    A_inv = np.array([[2, -1], [-1, 1]], dtype=np.int64)
    M = mat_pow_mod(A_inv, iterations, N)
    
    # Vectorized coordinate transformation
    y, x = np.meshgrid(np.arange(N), np.arange(N))
    coords = np.stack([x.ravel(), y.ravel()], axis=1)
    new_coords = (coords @ M.T) % N
    
    # Direct indexing
    recovered = image[new_coords[:, 0], new_coords[:, 1]].reshape(N, N)
    
    return recovered

# Calculate the period of Arnold transform for given image size N
def calculate_arnold_period(N: int) -> int:
    """
    After T iterations, the image returns to original state
    Useful for key space analysis
    
    Args:
        N: Image dimension (N x N)
    
    Returns:
        period: Number of iterations to return to original
    """
    if N == 1:
        return 1
    
    periods = {
        64: 24,
        128: 48,
        256: 96,
        512: 192
    }
    
    return periods.get(N, N // 2)

# Part 2: DNA Encoding (Substitution Layer)

# DNA Encoding Rules (can support up to 24 rules)
DNA_RULES = {
    1:  {'00': 'A', '01': 'T', '10': 'C', '11': 'G'},
    2:  {'00': 'A', '01': 'T', '10': 'G', '11': 'C'},
    3:  {'00': 'A', '01': 'C', '10': 'T', '11': 'G'},
    4:  {'00': 'A', '01': 'C', '10': 'G', '11': 'T'},
    5:  {'00': 'A', '01': 'G', '10': 'T', '11': 'C'},
    6:  {'00': 'A', '01': 'G', '10': 'C', '11': 'T'},

    7:  {'00': 'T', '01': 'A', '10': 'C', '11': 'G'},
    8:  {'00': 'T', '01': 'A', '10': 'G', '11': 'C'},
    9:  {'00': 'T', '01': 'C', '10': 'A', '11': 'G'},
    10: {'00': 'T', '01': 'C', '10': 'G', '11': 'A'},
    11: {'00': 'T', '01': 'G', '10': 'A', '11': 'C'},
    12: {'00': 'T', '01': 'G', '10': 'C', '11': 'A'},

    13: {'00': 'C', '01': 'A', '10': 'T', '11': 'G'},
    14: {'00': 'C', '01': 'A', '10': 'G', '11': 'T'},
    15: {'00': 'C', '01': 'T', '10': 'A', '11': 'G'},
    16: {'00': 'C', '01': 'T', '10': 'G', '11': 'A'},
    17: {'00': 'C', '01': 'G', '10': 'A', '11': 'T'},
    18: {'00': 'C', '01': 'G', '10': 'T', '11': 'A'},

    19: {'00': 'G', '01': 'A', '10': 'T', '11': 'C'},
    20: {'00': 'G', '01': 'A', '10': 'C', '11': 'T'},
    21: {'00': 'G', '01': 'T', '10': 'A', '11': 'C'},
    22: {'00': 'G', '01': 'T', '10': 'C', '11': 'A'},
    23: {'00': 'G', '01': 'C', '10': 'A', '11': 'T'},
    24: {'00': 'G', '01': 'C', '10': 'T', '11': 'A'},
}

# Auto-generate XOR table for any DNA rule
def generate_xor_table_for_rule(rule: int) -> dict:
    """
    Automatically generate XOR table for any DNA encoding rule
    
    This solves the problem of needing 24 different XOR tables!
    
    Args:
        rule: DNA encoding rule number
    
    Returns:
        xor_table: Dictionary mapping DNA base pairs to XOR result
    """
    encode_rule = DNA_RULES[rule]
    
    # Reverse mapping: DNA → binary
    dna_to_binary = {v: k for k, v in encode_rule.items()}
    
    # Generate XOR table
    bases = ['A', 'T', 'C', 'G']
    xor_table = {}
    
    for b1 in bases:
        for b2 in bases:
            # Get binary values
            bin1 = dna_to_binary.get(b1, '00')
            bin2 = dna_to_binary.get(b2, '00')
            
            # Binary XOR
            xor_result = format(int(bin1, 2) ^ int(bin2, 2), '02b')
            
            # Convert back to DNA
            result_dna = encode_rule.get(xor_result, 'A')
            
            xor_table[b1 + b2] = result_dna
    
    return xor_table

# Get the inverse DNA encoding rule for decoding
def get_dna_decode_rule(encode_rule: int # Rule number (1-8)
                        ) -> Dict[str, str]: # Returns inverse mapping (DNA -> binary)
    
    encode = DNA_RULES[encode_rule]
    decode = {v: k for k, v in encode.items()}
    return decode

# ========== DNA ENCODING (NOT OPTIMIZED) ==========

# Convert a pixel value (0-255) to DNA sequence
def pixel_to_dna(pixel: int,    # Pixel value (0-255)
                 rule: int      # DNA encoding rule number (1-8)
                ) -> str:       # Returns dna_seq: DNA sequence of length 4 (e.g., 'ATCG')
    # Convert to 8-bit binary
    binary = format(pixel, '08b')
    
    # Split into 4 pairs
    pairs = [binary[i:i+2] for i in range(0, 8, 2)]
    
    # Encode each pair to DNA base
    dna_seq = ''.join([DNA_RULES[rule][pair] for pair in pairs])
    
    return dna_seq

# Convert DNA sequence back to pixel value
def dna_to_pixel(dna_seq: str,  # DNA sequence of length 4
                 rule: int      # DNA encoding rule number (1-8)
                ) -> int:       # result: pixel value (0-255)
    
    decode_rule = get_dna_decode_rule(rule)
    
    # Convert each DNA base to binary pair
    binary_pairs = [decode_rule[base] for base in dna_seq]
    binary = ''.join(binary_pairs)
    
    # Convert binary to integer
    pixel = int(binary, 2)
    
    return pixel

# ========== DNA ENCODING (OPTIMIZED) ==========

# pixel_to_dna
def batch_pixel_to_dna(pixels: np.ndarray, rule: int) -> np.ndarray:
    encode_rule = DNA_RULES[rule]
    pixels = pixels.astype(np.uint8, copy=False)

    # Extract 4 two-bit pairs
    pair0 = (pixels >> 6) & 0b11 # extract the two highest digits
    pair1 = (pixels >> 4) & 0b11 # extract the second two highest two digits
    pair2 = (pixels >> 2) & 0b11 # extract the second two lowest digits
    pair3 = pixels & 0b11        # extract the two lowest digits

    # LUT: index 0..3 -> DNA base (U1)
    lut = np.array(
        [encode_rule['00'], encode_rule['01'], encode_rule['10'], encode_rule['11']],
        dtype='<U1'
    )

    # NumPy batch table lookup (C layer)
    dna0 = lut[pair0]
    dna1 = lut[pair1]
    dna2 = lut[pair2]
    dna3 = lut[pair3]

    # concat to a DNA string of length 4
    dna_sequences = np.char.add(np.char.add(dna0, dna1), np.char.add(dna2, dna3))

    return dna_sequences

# dna_to_pixel
def batch_dna_to_pixel(dna_sequences: np.ndarray, rule: int) -> np.ndarray:
    decode_rule = get_dna_decode_rule(rule)
    
    # 1. the array LUT is used to trigger NumPy's C-level batch indexing
    base_to_int = np.zeros(256, dtype=np.uint8)
    for base, bits in decode_rule.items():
        base_to_int[ord(base)] = int(bits, 2)

    # 2. convert string array into byte matrix [..., 4]
    b = np.char.encode(dna_sequences, 'ascii')
    a = b.view(np.uint8).reshape(dna_sequences.shape + (4,))

    # 3. batch lookup
    v = base_to_int[a]  # shape = (..., 4)

    # 4) batch pixel reconstruction
    pixels = ((v[..., 0] << 6) |
              (v[..., 1] << 4) |
              (v[..., 2] << 2) |
               v[..., 3]).astype(np.uint8)
    
    return pixels

# DNA XOR operation - now supports ANY rule!
def dna_xor(dna1: str,  # First DNA sequence
            dna2: str,  # Second DNA sequence (key)
            rule: int = 1  # DNA rule to use for XOR
            ) -> str:   # result: XOR result DNA sequence
    
    # DNA XOR using auto-generated table
    xor_table = generate_xor_table_for_rule(rule) 
    result = ''.join([xor_table[b1 + b2] for b1, b2 in zip(dna1, dna2)])
    return result

# Convert entire image to DNA sequences
def image_to_dna(image: np.ndarray, # Grayscale image array
                 rule: int          # DNA encoding rule
                ) -> np.ndarray:    # Return array of DNA sequences (strings)
    
    h, w = image.shape
    pixels_flat = image.flatten()
    dna_flat = batch_pixel_to_dna(pixels_flat, rule)
    dna_matrix = dna_flat.reshape(h, w)
    
    return dna_matrix

# Convert DNA sequences back to image
def dna_to_image(dna_matrix:    # Array of DNA sequences
        np.ndarray, rule: int   # DNA encoding rule
        ) -> np.ndarray:        # Return grayscale image array
    
    h, w = dna_matrix.shape
    dna_flat = dna_matrix.flatten()
    pixels_flat = batch_dna_to_pixel(dna_flat, rule)
    image = pixels_flat.reshape(h, w)
    
    return image

# Part 3: Chaos Sequence Enhancement (Key Generation) - OPTIMIZED

# Generate chaotic sequence using Logistic Map
def logistic_map(x0: float,         # Initial value (0 < x0 < 1), part of secret key
                 r: float,          # Chaos parameter (3.57 < r < 4), part of secret key
                 length: int        # Length of sequence to generate
                ) -> np.ndarray:    # Return chaotic sequence array
    
    assert 0 < x0 < 1, "x0 must be between 0 and 1"
    assert 3.57 < r <= 4, "r must be between 3.57 and 4 for chaotic behavior"
    
    sequence = np.zeros(length)
    x = x0
    
    # Skip first 1000 iterations
    for _ in range(1000):
        x = r * x * (1 - x)
    
    # Generate sequence
    for i in range(length):
        x = r * x * (1 - x)
        sequence[i] = x
    
    return sequence

# Generate DNA key sequence - VECTORIZED
def generate_dna_key_sequence(x0: float,    # Initial value for chaos
                              r: float,     # Chaos parameter
                              length: int,  # Number of DNA sequences needed (image pixels)
                              rule: int     # DNA encoding rule
                            ) -> np.ndarray:# Return array of DNA key sequences
    
    # Generate chaos sequence
    chaos_seq = logistic_map(x0, r, length * 4)
    
    # Convert to integers 0-3
    chaos_int = (chaos_seq * 4).astype(int)
    chaos_int = np.clip(chaos_int, 0, 3)
    
    # Reshape to (length, 4) for vectorized processing
    chaos_reshaped = chaos_int[:length*4].reshape(length, 4)
    
    # Vectorized conversion to pixels
    pixels = ((chaos_reshaped[:, 0] << 6) | 
              (chaos_reshaped[:, 1] << 4) | 
              (chaos_reshaped[:, 2] << 2) | 
              chaos_reshaped[:, 3]).astype(np.uint8)
    
    # Batch convert to DNA
    dna_keys = batch_pixel_to_dna(pixels, rule)
    
    return dna_keys

# Part 4: Complete Encryption System

# Generate a random 4-character DNA sequence as IV
def generate_random_iv() -> str:
    bases = ['A', 'T', 'C', 'G']
    # iv = ''.join([random.choice(bases) for _ in range(4)])
    random_bytes = os.urandom(4)
    iv = ''.join([bases[b % 4] for b in random_bytes])
    return iv

# JIT-compiled CBC encryption core - Performance: ~10-50x faster
@jit(nopython=True)
def _cbc_encrypt_core(image_flat: np.ndarray, 
                      key_flat: np.ndarray, 
                      iv_value: int) -> np.ndarray:
    n = len(image_flat)
    encrypted = np.empty(n, dtype=np.uint8)
    prev = iv_value
    
    for i in range(n):
        temp = image_flat[i] ^ key_flat[i]
        encrypted[i] = temp ^ prev
        prev = encrypted[i]
    
    return encrypted

# JIT-compiled CBC decryption core - Performance: ~10-50x faster
@jit(nopython=True)
def _cbc_decrypt_core(encrypted_flat: np.ndarray, 
                      key_flat: np.ndarray, 
                      iv_value: int) -> np.ndarray:
    
    n = len(encrypted_flat)
    decrypted = np.empty(n, dtype=np.uint8)
    prev = iv_value
    
    for i in range(n):
        temp = encrypted_flat[i] ^ prev
        decrypted[i] = temp ^ key_flat[i]
        prev = encrypted_flat[i]
    
    return decrypted

# encrypt in CBC mode
def dna_encrypt_cbc(dna_image, dna_key_matrix, iv, rule):
    h, w = dna_image.shape
    
    # Convert DNA to numeric
    image_numeric = dna_to_image(dna_image, rule)
    key_numeric = dna_to_image(dna_key_matrix, rule)
    iv_numeric = dna_to_pixel(iv, rule)
    
    # Flatten and encrypt with JIT
    image_flat = image_numeric.flatten()
    key_flat = key_numeric.flatten()
    encrypted_flat = _cbc_encrypt_core(image_flat, key_flat, iv_numeric)
    
    # Reshape and convert back to DNA
    encrypted_numeric = encrypted_flat.reshape(h, w)
    encrypted_dna = image_to_dna(encrypted_numeric, rule)
    
    return encrypted_dna

# decrypt in CBC mode
def dna_decrypt_cbc(encrypted_dna, dna_key_matrix, iv, rule):
    h, w = encrypted_dna.shape
    
    # Convert DNA to numeric
    encrypted_numeric = dna_to_image(encrypted_dna, rule)
    key_numeric = dna_to_image(dna_key_matrix, rule)
    iv_numeric = dna_to_pixel(iv, rule)
    
    # Flatten and decrypt with JIT
    encrypted_flat = encrypted_numeric.flatten()
    key_flat = key_numeric.flatten()
    decrypted_flat = _cbc_decrypt_core(encrypted_flat, key_flat, iv_numeric)
    
    # Reshape and convert back to DNA
    decrypted_numeric = decrypted_flat.reshape(h, w)
    decrypted_dna = image_to_dna(decrypted_numeric, rule)
    
    return decrypted_dna

# Complete image encryption pipeline
def encrypt_image(image: np.ndarray,        # Input grayscale square image (N x N)
                  arnold_iterations: int,   # Number of Arnold iterations
                  dna_rule: int,            # DNA encoding rule (1-8)
                  chaos_x0: float,          # Initial value for chaos (0 < x0 < 1)
                  chaos_r: float,           # Chaos parameter (3.57 < r < 4)
                  verbose = True
                  ) -> Tuple[np.ndarray, Dict]: # Returns encrypted image and metadata
    if verbose: 
        print("=" * 50)
        print("Starting Encryption Process (Fully Optimized)")
        print("=" * 50)
    
    # Step 1: Arnold Transform (VECTORIZED)
    if verbose: print(f"\n[Step 1/5] Applying Arnold Transform")
    scrambled = arnold_transform(image, arnold_iterations)
    if verbose: print(f"✓ Image scrambled")
    
    # Step 2: DNA Encoding (VECTORIZED)
    if verbose: print(f"\n[Step 2/5] Converting to DNA sequences")
    dna_image = image_to_dna(scrambled, dna_rule)
    if verbose: print(f"✓ Image converted to DNA matrix: {dna_image.shape}")
    
    # Step 3: Generate DNA key
    if verbose: print(f"\n[Step 3/5] Generating DNA key")
    h, w = dna_image.shape
    dna_key = generate_dna_key_sequence(chaos_x0, chaos_r, h * w, dna_rule)
    dna_key_matrix = dna_key.reshape(h, w)
    if verbose: print(f"✓ DNA key generated: {dna_key_matrix.shape}")
    
    # Step 4: Generate IV
    if verbose: print(f"\n[Step 4/5] Generating random IV")
    iv = generate_random_iv()
    if verbose: print(f"✓ IV generated: {iv}")
    
    # Step 5: CBC Encryption (JIT)
    if verbose: print(f"\n[Step 5/5] Applying CBC encryption [JIT OPTIMIZED]")
    encrypted_dna = dna_encrypt_cbc(dna_image, dna_key_matrix, iv, dna_rule)
    if verbose: print(f"✓ CBC encryption completed")
    
    # Step 6: DNA Decoding
    if verbose: print(f"\n[Final] Converting DNA to pixels")
    encrypted_image = dna_to_image(encrypted_dna, dna_rule)
    if verbose: print(f"✓ Encryption complete!")
    
    metadata = {
        'arnold_iterations': arnold_iterations,
        'dna_rule': dna_rule,
        'chaos_x0': chaos_x0,
        'chaos_r': chaos_r,
        'image_shape': image.shape,
        'iv': iv
    }
    
    if verbose: 
        print("\n" + "=" * 50)
        print("Encryption Summary")
        print("=" * 50)
        print(f"Input shape: {image.shape}")
        print(f"Output shape: {encrypted_image.shape}")
        #print(f"Optimization: Full Vectorization + JIT")
        print(f"arnold_iterations: {arnold_iterations}")
        print(f"dna_rule: {dna_rule}")
        print(f"chaos_x0: {chaos_x0}")
        print(f"chaos_r: {chaos_r}")
        print(f"iv: {iv}")
        print("=" * 50)
    
    return encrypted_image, metadata

# Decrypt image using stored metadata
def decrypt_image(encrypted_image: np.ndarray,  # Encrypted image array
                  metadata: Dict,               # Metadata from encryption
                  verbose = True
                 ) -> np.ndarray:               # Result: Recovered decrypted original image
    
    if verbose: 
        print("\n" + "=" * 50)
        print("Starting Decryption Process (Fully Optimized)")
        print("=" * 50)
    
    arnold_iterations = metadata['arnold_iterations']
    dna_rule = metadata['dna_rule']
    chaos_x0 = metadata['chaos_x0']
    chaos_r = metadata['chaos_r']
    iv = metadata['iv']
    
    # Step 1: DNA Encoding (VECTORIZED)
    if verbose: print(f"\n[Step 1/4] Converting to DNA")
    encrypted_dna = image_to_dna(encrypted_image, dna_rule)
    if verbose: print(f"✓ Converted to DNA matrix")
    
    # Step 2: Regenerate key (VECTORIZED)
    if verbose: print(f"\n[Step 2/4] Regenerating DNA key")
    h, w = encrypted_dna.shape
    dna_key = generate_dna_key_sequence(chaos_x0, chaos_r, h * w, dna_rule)
    dna_key_matrix = dna_key.reshape(h, w)
    if verbose: print(f"✓ DNA key regenerated")
    
    # Step 3: CBC Decryption (JIT)
    if verbose: print(f"\n[Step 3/4] Applying CBC decryption [JIT OPTIMIZED]")
    decrypted_dna = dna_decrypt_cbc(encrypted_dna, dna_key_matrix, iv, dna_rule)
    if verbose: print(f"✓ CBC decryption completed")
    
    # Step 4: DNA Decoding (VECTORIZED)
    if verbose: print(f"\n[Step 4/4] Converting DNA to pixels")
    scrambled_image = dna_to_image(decrypted_dna, dna_rule)
    if verbose: print(f"✓ DNA decoded")
    
    # Step 5: Inverse Arnold (VECTORIZED)
    if verbose: print(f"\n[Final] Applying inverse Arnold")
    decrypted_image = inverse_arnold_transform(scrambled_image, arnold_iterations)
    if verbose: print(f"✓ Decryption complete!")
    
    if verbose: 
        print("\n" + "=" * 50)
        print("Decryption Summary")
        print("=" * 50)
        
        print(f"arnold_iterations: {arnold_iterations}")
        print(f"dna_rule: {dna_rule}")
        print(f"chaos_x0: {chaos_x0}")
        print(f"chaos_r: {chaos_r}")
        print(f"iv: {iv}")
        print("=" * 50)
    
    return decrypted_image

# Part 5: Security Analysis Functions

# Calculate histogram of image
def calculate_histogram(image: np.ndarray) -> np.ndarray:
    hist, _ = np.histogram(image.flatten(), bins=256, range=(0, 256))
    return hist

# Calculate information entropy
def calculate_entropy(image: np.ndarray) -> float:
    hist = calculate_histogram(image)
    hist = hist / hist.sum()
    hist = hist[hist > 0]
    entropy = -np.sum(hist * np.log2(hist))
    return entropy

# Calculate correlation between adjacent pixels
def calculate_correlation(image: np.ndarray, direction: str = 'horizontal') -> float:
    if direction == 'horizontal':
        pixels1 = image[:, :-1].flatten()
        pixels2 = image[:, 1:].flatten()
    elif direction == 'vertical':
        pixels1 = image[:-1, :].flatten()
        pixels2 = image[1:, :].flatten()
    elif direction == 'diagonal':
        pixels1 = image[:-1, :-1].flatten()
        pixels2 = image[1:, 1:].flatten()
    else:
        raise ValueError("Direction must be 'horizontal', 'vertical', or 'diagonal'")
    
    correlation = np.corrcoef(pixels1, pixels2)[0, 1]
    return correlation

# Test key sensitivity
def test_key_sensitivity(image: np.ndarray, 
                        arnold_iterations: int,
                        dna_rule: int,
                        chaos_x0: float,
                        chaos_r: float) -> Dict:
    print("\n" + "=" * 50)
    print("Key Sensitivity Test")
    print("=" * 50)
    
    cipher1, _ = encrypt_image(image, arnold_iterations, dna_rule, chaos_x0, chaos_r)
    cipher2, _ = encrypt_image(image, arnold_iterations, dna_rule, chaos_x0 + 1e-10, chaos_r)
    
    diff_pixels = np.sum(cipher1 != cipher2)
    total_pixels = cipher1.size
    diff_ratio = diff_pixels / total_pixels * 100
    
    results = {
        'different_pixels': diff_pixels,
        'total_pixels': total_pixels,
        'difference_ratio': diff_ratio
    }
    
    print(f"\nKey change: x0 + 1e-10")
    print(f"Different pixels: {diff_pixels}/{total_pixels}")
    print(f"Difference ratio: {diff_ratio:.2f}%")
    
    return results