# FastAPI Backend for Image Encryption System

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
from PIL import Image
import io
import base64
import uuid
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

# Import your existing modules
from encryption import (
    encrypt_image, decrypt_image,
    calculate_entropy, calculate_correlation,
    calculate_histogram
)
from preprocessing import handle_non_square_image, reverse_non_square_handling

SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif')

# Initialize FastAPI
app = FastAPI(title="Image Encryption System")
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# CORS middleware (allow frontend to access backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories for uploads and temp files
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# In-memory storage for uploaded images (in production, use database)
image_store = {}

# Encryption parameters
class EncryptParams(BaseModel):
    image_id: str
    arnold_iterations: int = 80
    dna_rule: int = 2
    chaos_x0: float = 0.123456789
    chaos_r: float = 3.9876

# Convert numpy array to base64 string
def image_to_base64(img_array: np.ndarray) -> str:
    img = Image.fromarray(img_array.astype(np.uint8))
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode()

# Create histogram and return as base64
def create_histogram_base64(img_array: np.ndarray, title: str, color: str) -> str:
    plt.figure(figsize=(4, 3))
    plt.hist(img_array.flatten(), bins=256, range=(0, 256), color=color, alpha=0.7)
    plt.title(title)
    plt.xlabel('Pixel Value')
    plt.ylabel('Frequency')
    plt.tight_layout()
    
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=100)
    plt.close()
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode()

# Serve frontend HTML
@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

# Upload image and return basic information
@app.post("/api/upload")
async def upload_image_endpoint(file: UploadFile = File(...)):
    """
    Returns:
        {
            "image_id": "...",
            "filename": "...",
            "format": "JPEG/PNG/BMP",
            "size": [width, height],
            "mode": "L/RGB"
        }
    """
    try:
        # Clear old images before storing new ones
        image_store.clear()
        
        # Read uploaded file
        contents = await file.read()
        img = Image.open(io.BytesIO(contents))
        
        # Generate unique ID
        image_id = str(uuid.uuid4())
        
        # Convert to grayscale if needed
        if img.mode in ['RGB', 'RGBA']:
            img_gray = img.convert('L')
        else:
            img_gray = img
        
        # Store in memory (or save to disk)
        img_array = np.array(img_gray, dtype=np.uint8)
        image_store[image_id] = {
            'array': img_array,
            'filename': file.filename,
            'original_size': img.size
        }
        
        # Return info
        return JSONResponse({
            "success": True,
            "image_id": image_id,
            "filename": file.filename,
            "format": img.format or "Unknown",
            "size": list(img.size),  # [width, height]
            "mode": img_gray.mode,
            "original_preview": image_to_base64(img_array)
        })
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing image: {str(e)}")

# Encrypt image and return all results
@app.post("/api/encrypt")
async def encrypt_image_endpoint(params: EncryptParams):
    """    
    Returns:
        {
            "success": true,
            "images": {
                "original": "base64...",
                "encrypted": "base64...",
                "decrypted": "base64...",
                "hist_original": "base64...",
                "hist_encrypted": "base64...",
                "hist_decrypted": "base64..."
            },
            "security_analysis": {
                "entropy": {...},
                "correlation": {...},
                "histogram_uniformity": {...},
                "decryption_accuracy": {...}
            },
            "key_sensitivity": {
                "different_pixels": 0,
                "total_pixels": 0,
                "difference_ratio": 0.0
            }
        }
    """
    try:
        # Get image from store
        if params.image_id not in image_store:
            raise HTTPException(status_code=404, detail="Image not found")
        
        original_array = image_store[params.image_id]['array']
        
        print(f"Processing image: {original_array.shape}")
        
        # Handle non-square images
        if original_array.shape[0] != original_array.shape[1]:
            square_image, padding_metadata = handle_non_square_image(original_array)
        else:
            square_image = original_array
            padding_metadata = {'method': 'none', 'original_shape': original_array.shape}
        
        print(f"Square image: {square_image.shape}")
        
        # Encrypt
        encrypted_array, enc_metadata = encrypt_image(
            square_image,
            arnold_iterations=params.arnold_iterations,
            dna_rule=params.dna_rule,
            chaos_x0=params.chaos_x0,
            chaos_r=params.chaos_r
        )
        
        print(f"Encrypted: {encrypted_array.shape}")
        
        # Decrypt
        decrypted_square = decrypt_image(encrypted_array, enc_metadata)
        
        # Remove padding if needed
        if padding_metadata['method'] != 'none':
            decrypted_array = reverse_non_square_handling(decrypted_square, padding_metadata)
        else:
            decrypted_array = decrypted_square
        
        print(f"Decrypted: {decrypted_array.shape}")
        
        # Generate histograms
        hist_original = create_histogram_base64(original_array, "Original Histogram", "blue")
        hist_encrypted = create_histogram_base64(encrypted_array, "Encrypted Histogram", "red")
        hist_decrypted = create_histogram_base64(decrypted_array, "Decrypted Histogram", "green")
        
        # Security Analysis
        orig_entropy = calculate_entropy(original_array)
        enc_entropy = calculate_entropy(encrypted_array)
        dec_entropy = calculate_entropy(decrypted_array)
        
        orig_corr_h = calculate_correlation(original_array, 'horizontal')
        enc_corr_h = calculate_correlation(encrypted_array, 'horizontal')
        dec_corr_h = calculate_correlation(decrypted_array, 'horizontal')
        
        orig_corr_v = calculate_correlation(original_array, 'vertical')
        enc_corr_v = calculate_correlation(encrypted_array, 'vertical')
        dec_corr_v = calculate_correlation(decrypted_array, 'vertical')
        
        orig_corr_d = calculate_correlation(original_array, 'diagonal')
        enc_corr_d = calculate_correlation(encrypted_array, 'diagonal')
        dec_corr_d = calculate_correlation(decrypted_array, 'diagonal')
        
        # Histogram uniformity
        enc_hist = calculate_histogram(encrypted_array)
        mean_count = float(enc_hist.mean())
        std_count = float(enc_hist.std())
        uniformity = (1 - std_count / mean_count) * 100
        
        # Decryption accuracy
        mse = float(np.mean((original_array.astype(float) - decrypted_array.astype(float)) ** 2))
        perfect_match = bool(np.array_equal(original_array, decrypted_array))
        
        print("")
        # Key Sensitivity Test - Encrypt with a slightly different key
        cipher1 = encrypted_array
        cipher2_key_diff, _ = encrypt_image(
            square_image,
            arnold_iterations=params.arnold_iterations,
            dna_rule=params.dna_rule,
            chaos_x0=params.chaos_x0 + 1e-10,
            chaos_r=params.chaos_r
        )
        
        diff_pixels = int(np.sum(cipher1 != cipher2_key_diff))
        total_pixels = int(cipher1.size)
        diff_ratio = (diff_pixels / total_pixels) * 100
        
        # Return results
        return JSONResponse({
            "success": True,
            "images": {
                "original": image_to_base64(original_array),
                "encrypted": image_to_base64(encrypted_array),
                "decrypted": image_to_base64(decrypted_array),
                "hist_original": hist_original,
                "hist_encrypted": hist_encrypted,
                "hist_decrypted": hist_decrypted
            },
            "security_analysis": {
                "entropy": {
                    "original": round(orig_entropy, 4),
                    "encrypted": round(enc_entropy, 4),
                    "decrypted": round(dec_entropy, 4),
                    "quality": "GOOD" if enc_entropy > 7.9 else "WEAK"
                },
                "correlation": {
                    "horizontal": {
                        "original": round(orig_corr_h, 4),
                        "encrypted": round(enc_corr_h, 4),
                        "decrypted": round(dec_corr_h, 4)
                    },
                    "vertical": {
                        "original": round(orig_corr_v, 4),
                        "encrypted": round(enc_corr_v, 4),
                        "decrypted": round(dec_corr_v, 4)
                    },
                    "diagonal": {
                        "original": round(orig_corr_d, 4),
                        "encrypted": round(enc_corr_d, 4),
                        "decrypted": round(dec_corr_d, 4)
                    }
                },
                "histogram_uniformity": {
                    "mean_count": round(mean_count, 2),
                    "std_count": round(std_count, 2),
                    "uniformity_score": round(uniformity, 2),
                    "quality": "GOOD" if uniformity > 70 else "WEAK"
                },
                "decryption_accuracy": {
                    "mse": round(mse, 6),
                    "perfect_match": perfect_match
                },
            },
            "key_sensitivity": {
                "different_pixels": diff_pixels,
                "total_pixels": total_pixels,
                "difference_ratio": round(diff_ratio, 2)
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Encryption error: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)