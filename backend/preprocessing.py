# Image Preprocessing Module: Handles image format detection, decoding, and transforms (DCT, DWT)
import numpy as np
from PIL import Image
import cv2, pywt

# Handle non-square images for Arnold transform (Two strategies: padding or tiling)
def handle_non_square_image(image):
    h, w = image.shape
    
    if h == w:
        return image, {'method': 'none', 'original_shape': (h, w)}
    
    # Strategy 1: Pad to square (recommended)
    max_dim = max(h, w)
    padded = np.zeros((max_dim, max_dim), dtype=image.dtype)
    padded[:h, :w] = image
    
    # metadata: information for reversal
    metadata = {
        'method': 'padding',
        'original_shape': (h, w),
        'padded_shape': (max_dim, max_dim)
    }
    
    print(f"Padded {h}x{w} to {max_dim}x{max_dim}")
    
    return padded, metadata 

# Reverse non-square image handling
def reverse_non_square_handling(image,      # Processed square image
                                metadata     # Information from forward processing
                                ): 
    
    if metadata['method'] == 'none':
        return image
    elif metadata['method'] == 'padding':
        h, w = metadata['original_shape']
        return image[:h, :w]
    
    return image # Image with original dimensions
