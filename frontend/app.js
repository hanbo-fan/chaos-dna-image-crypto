// javascript
    let currentImageId = null;
    const API_BASE = '';  // Same origin

    // File input handler
    document.getElementById('file-input').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        await uploadImage(file);
    });

    async function uploadImage(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(`${API_BASE}/api/upload`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                currentImageId = data.image_id;
                
                // Update image info
                document.getElementById('info-filename').textContent = data.filename;
                document.getElementById('info-format').textContent = data.format;
                document.getElementById('info-size').textContent = `${data.size[0]} × ${data.size[1]}`;
                document.getElementById('info-mode').textContent = data.mode === 'L' ? 'Grayscale' : 'RGB';

                // Show image info state
                document.getElementById('initial-state').style.display = 'none';
                document.getElementById('image-info-state').style.display = 'block';
            } else {
                alert('Upload failed!');
            }
        } catch (error) {
            console.error('Upload error:', error);
            alert('Upload failed: ' + error.message);
        }
    }

    async function startEncryption() {
        if (!currentImageId) return;

        // Show loading
        document.getElementById('image-info-state').style.display = 'none';
        document.getElementById('loading-state').style.display = 'block';

        try {
            const response = await fetch(`${API_BASE}/api/encrypt`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    image_id: currentImageId,
                    arnold_iterations: 80,
                    dna_rule: 2,
                    chaos_x0: 0.123456789,
                    chaos_r: 3.9876
                })
            });

            const data = await response.json();

            if (data.success) {
                displayResults(data);
                
                // Show results
                document.getElementById('loading-state').style.display = 'none';
                document.getElementById('results-state').style.display = 'block';
            } else {
                alert('Encryption failed!');
                document.getElementById('loading-state').style.display = 'none';
                document.getElementById('image-info-state').style.display = 'block';
            }
        } catch (error) {
            console.error('Encryption error:', error);
            alert('Encryption failed: ' + error.message);
            document.getElementById('loading-state').style.display = 'none';
            document.getElementById('image-info-state').style.display = 'block';
        }
    }

    function padToSquare(base64) {
    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
                const size = Math.max(img.width, img.height);
                const canvas = document.createElement('canvas');
                canvas.width = size;
                canvas.height = size;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = '#FFFFFF';
                ctx.fillRect(0, 0, size, size);
                ctx.drawImage(img, 0, 0);
                resolve(canvas.toDataURL('image/png'));
            };
        img.src = base64;
        });
    }

    async function displayResults(data) {
        // Padding images
        //const paddedOriginal = await padToSquare('data:image/png;base64,' + data.images.original);
        //const paddedDecrypted = await padToSquare('data:image/png;base64,' + data.images.decrypted);
        
        // Display images
        document.getElementById('img-original').src = 'data:image/png;base64,' + data.images.original;
        document.getElementById('img-encrypted').src = 'data:image/png;base64,' + data.images.encrypted;
        document.getElementById('img-decrypted').src = 'data:image/png;base64,' + data.images.decrypted;

        // Display hist
        document.getElementById('hist-original').src = 'data:image/png;base64,' + data.images.hist_original;
        document.getElementById('hist-encrypted').src = 'data:image/png;base64,' + data.images.hist_encrypted;
        document.getElementById('hist-decrypted').src = 'data:image/png;base64,' + data.images.hist_decrypted;

        // Display security analysis
        const sa = data.security_analysis;
        
        // Entropy
        document.getElementById('entropy-original').textContent = sa.entropy.original + ' bits/pixel';
        document.getElementById('entropy-encrypted').textContent = sa.entropy.encrypted + ' bits/pixel';
        //document.getElementById('entropy-encrypted').style.color = 'red';
        document.getElementById('entropy-decrypted').textContent = sa.entropy.decrypted + ' bits/pixel';
        document.getElementById('entropy-quality').innerHTML = 
            `<span class="badge badge-${sa.entropy.quality === 'GOOD' ? 'good' : 'weak'}">${sa.entropy.quality}</span>`;

        // Correlation
        document.getElementById('corr-original-h').textContent = sa.correlation.horizontal.original;
        document.getElementById('corr-encrypted-h').textContent = sa.correlation.horizontal.encrypted;

        document.getElementById('corr-original-v').textContent = sa.correlation.vertical.original;
        document.getElementById('corr-encrypted-v').textContent = sa.correlation.vertical.encrypted;

        document.getElementById('corr-original-d').textContent = sa.correlation.diagonal.original;
        document.getElementById('corr-encrypted-d').textContent = sa.correlation.diagonal.encrypted;

        // Histogram uniformity
        document.getElementById('hist-mean').textContent = sa.histogram_uniformity.mean_count;
        document.getElementById('hist-std').textContent = sa.histogram_uniformity.std_count;
        document.getElementById('hist-uniformity').textContent = sa.histogram_uniformity.uniformity_score + '%';
        document.getElementById('hist-quality').innerHTML = 
            `<span class="badge badge-${sa.histogram_uniformity.quality === 'GOOD' ? 'good' : 'weak'}">${sa.histogram_uniformity.quality}</span>`;

        // Decryption accuracy
        document.getElementById('mse').textContent = sa.decryption_accuracy.mse;
        const matchEl = document.getElementById('perfect-match');
        if (sa.decryption_accuracy.perfect_match) {
            matchEl.textContent = '✓ YES';
            matchEl.style.color = 'green';
        } else {
            matchEl.textContent = '✗ NO';
            matchEl.style.color = 'red';
        }

        // Key sensitivity
        const ks = data.key_sensitivity;
        document.getElementById('key-diff-pixels').textContent = `${ks.different_pixels} / ${ks.total_pixels}`;
        document.getElementById('key-total-pixels').textContent = ks.total_pixels;
        document.getElementById('key-diff-ratio').textContent = ks.difference_ratio + '%';

    }

    function resetUpload() {
        currentImageId = null;
        document.getElementById('file-input').value = '';
        document.getElementById('initial-state').style.display = 'block';
        document.getElementById('image-info-state').style.display = 'none';
        document.getElementById('results-state').style.display = 'none';
    }